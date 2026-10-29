"""
Tela, rodada 5: tamanho máximo de TODOS os campos (RN33). Toda caixa de
texto do programa tem um máximo (digitação e colagem), e os textos longos
(justificativa, motivo) mostram o contador "123/200".
"""

import tkinter as tk

from portaria.componentes import Campo
from portaria.tela_autorizacao import JanelaAutorizacao
from portaria.tela_login import TelaLogin

from .test_interface import VISITA_ANTIGA, BaseInterface, ha_uma_hora


def entradas(widget):
    """Todas as caixas de texto (tk.Entry) dentro de `widget`."""
    achadas = [widget] if widget.winfo_class() == "Entry" else []
    for filho in widget.winfo_children():
        achadas += entradas(filho)
    return achadas


def digitar(caixa, texto):
    caixa.delete(0, tk.END)
    for letra in texto:
        caixa.insert(tk.END, letra)
    return caixa.get()


# ----------------------------------------------------------------------
# RN33: tamanho máximo em todos os campos
# ----------------------------------------------------------------------
class TestTamanhoDosCampos(BaseInterface):
    entrar_como = "admin"

    def abrir_tudo(self):
        """Abre todas as páginas e diálogos que têm caixa de texto."""
        for pagina in ("tela_pessoas", "tela_dashboard",
                       "tela_usuarios", "tela_configuracoes"):
            getattr(self.app, pagina)
        dialogos = [self.app.tela_usuarios.novo_usuario(),
                    self.app.trocar_senha(),
                    self.app.tela_dashboard.abrir_exportacao()]
        self.app.tela_usuarios.tabela.selection_set(str(self.porteiro["id"]))
        dialogos.append(self.app.tela_usuarios.redefinir_senha())
        dialogos.append(JanelaAutorizacao(self.app, ["Regra"], "Teste",
                                          so_com_senha=True))
        self.banco.inserir(dict(VISITA_ANTIGA, entrada=ha_uma_hora(),
                                saida=""), autor="paulo")
        self.app.atualizar_tabela()
        self.app.tabela.selection_set(self.app.tabela.get_children()[0])
        self.app.editar_selecionado()
        dialogos.append(self.app.janela_edicao)
        return dialogos

    def test_nenhuma_caixa_de_texto_fica_sem_maximo(self):
        dialogos = self.abrir_tudo()
        caixas = entradas(self.app.janela)
        for dialogo in dialogos:
            caixas += entradas(dialogo.janela)
        self.assertGreater(len(caixas), 40)
        for caixa in caixas:
            with self.subTest(caixa=str(caixa)):
                campo = caixa.master
                self.assertIsInstance(campo, Campo)
                self.assertGreater(campo.maximo, 0)
                if str(caixa.cget("state")) == "normal":
                    self.assertEqual(str(caixa.cget("validate")), "key")
                    digitar(caixa, "9" * (campo.maximo + 5))
                    self.assertLessEqual(len(caixa.get()), campo.maximo)
        for dialogo in dialogos:
            dialogo.fechar()

    def test_limite_de_cada_campo(self):
        dialogos = self.abrir_tudo()
        novo, senha, exportar, redefinir, autorizacao, edicao = dialogos
        pessoas, usuarios = self.app.tela_pessoas, self.app.tela_usuarios
        config = self.app.tela_configuracoes
        desativar = self.app.tela_pessoas.desativadas.desativar()
        dialogos.append(desativar)
        nova = self.app.tela_pessoas.nova_pessoa()
        dialogos.append(nova)
        casos = [
            (self.app.nome, 80), (self.app.cpf, 11), (self.app.celular, 11),
            (self.app.tela_cadastro.pecas["placa"][1].entrada, 7),
            (self.app.entrada, 16), (self.app.saida, 16),
            (self.app.busca, 60), (self.app.campo_saida_rapida, 200),
            (pessoas.busca, 60), (nova.nome, 80), (nova.celular, 11),
            (nova.caixa_placa, 7), (nova.cpf, 11),
            (usuarios.busca, 60),
            (novo.nome, 80), (novo.login, 20), (novo.senha, 64),
            (novo.confirmacao, 64),
            (senha.atual, 64), (senha.nova, 64), (senha.confirmacao, 64),
            (redefinir.senha, 64), (redefinir.confirmacao, 64),
            (autorizacao.login, 20), (autorizacao.senha, 64),
            (autorizacao.justificativa, 200),
            (desativar.valor, 11), (desativar.motivo, 200),
            (config.data_feriado, 10), (config.nome_feriado, 80),
            (config.data_evento, 10), (config.abre_evento, 5),
            (config.fecha_evento, 5), (config.nome_evento, 80),
            (config.minutos_aviso, 3), (config.horas_retroativo, 2),
            (config.dias[0][1], 5), (config.dias[0][2], 5),
            (exportar.desde, 10), (exportar.ate, 10),
            (edicao.nome, 80), (edicao.celular, 11), (edicao.entrada, 16),
            (edicao.saida, 16), (edicao.caixa_placa, 7),
        ]
        for caixa, maximo in casos:
            with self.subTest(caixa=str(caixa), maximo=maximo):
                self.assertEqual(caixa.master.maximo, maximo)
        for dialogo in dialogos:
            dialogo.fechar()

    def test_nome_colado_longo_entra_cortado_no_cadastro(self):
        campo = self.app.nome.master
        campo.colar("Maria " + "Silva " * 30)
        self.assertEqual(len(self.app.nome.get()), 80)

    def test_contador_da_justificativa_e_do_motivo(self):
        dialogo = JanelaAutorizacao(self.app, ["Regra"], "Teste")
        contador = dialogo.justificativa.master.contador
        self.assertEqual(contador.cget("text"), "0/200")
        dialogo.justificativa.insert(0, "Evento da reitoria")
        self.assertEqual(contador.cget("text"), "18/200")
        dialogo.fechar()
        desativar = self.app.tela_pessoas.desativadas.desativar()
        contador = desativar.motivo.master.contador
        self.assertEqual(contador.cget("text"), "0/200")
        desativar.motivo.master.colar("m" * 300)
        self.assertEqual(contador.cget("text"), "200/200")
        desativar.fechar()

    def test_justificativa_longa_e_recusada_pela_validacao(self):
        dialogo = JanelaAutorizacao(self.app, ["Regra"], "Teste")
        dialogo.justificativa.config(validate="none")   # se a tela falhasse
        dialogo.justificativa.insert(0, "j" * 201)
        dialogo.confirmar()
        self.assertEqual(dialogo.erro, "Justificativa: no máximo 200 caracteres.")
        self.assertIsNone(dialogo.resultado)
        dialogo.fechar()


class TestTamanhoNoLogin(BaseInterface):
    entrar_como = None

    def test_login_e_senha(self):
        login = self.app.tela_login
        self.assertEqual(digitar(login.campo_login, "u" * 30), "u" * 20)
        self.assertEqual(len(digitar(login.campo_senha, "s" * 90)), 64)


class TestTamanhoNoPrimeiroAcesso(BaseInterface):
    entrar_como = None
    com_usuarios = False

    def test_nome_login_e_senhas(self):
        tela = self.app.tela_login
        self.assertIsInstance(tela, TelaLogin)
        self.assertEqual(len(digitar(tela.campo_nome, "N" * 99)), 80)
        self.assertEqual(len(digitar(tela.campo_login, "l" * 99)), 20)
        self.assertEqual(len(digitar(tela.campo_senha, "s" * 99)), 64)
        self.assertEqual(len(digitar(tela.campo_confirmacao, "s" * 99)), 64)
