"""Testa a tela de verdade: preenche campos e clica nos botões (janela oculta)."""

import json
import os
import shutil
import sqlite3
import tempfile
import tkinter as tk
import unittest
from datetime import date, datetime, timedelta
from unittest import mock

from portaria import dados
from portaria.componentes import Botao
from portaria.interface import AppPortaria
from portaria.usuarios import (LIMITE_TENTATIVAS, MINUTOS_INATIVIDADE,
                               autenticar, gerar_hash)
from portaria.validacao import FORMATO, converter_data

VISITA_ANTIGA = {"nome": "Beto Rocha", "cpf": "11144477735",
                 "celular": "31933334444", "placa": "QWE1234",
                 "tipo": "Professor", "entrada": "15/10/2026 07:00",
                 "saida": "15/10/2026 12:00"}


def ha_uma_hora():
    return (datetime.now() - timedelta(hours=1)).strftime(FORMATO)


def agora_menos(minutos):
    """Momento de hoje (não vira ontem perto da meia-noite)."""
    momento = max(datetime.now() - timedelta(minutes=minutos),
                  datetime.now().replace(hour=0, minute=0))
    return momento.strftime(FORMATO)


def agora_texto():
    return datetime.now().strftime(FORMATO)


def criar_usuario(banco, nome, login, perfil, senha, autor=None):
    """Sem autor só cria o primeiro usuário (primeiro acesso)."""
    id_ = banco.criar_usuario(nome, login, perfil, gerar_hash(senha), autor)
    return {"id": id_, "login": login, "nome": nome, "perfil": perfil}


class BaseInterface(unittest.TestCase):
    """
    Uma janela Tk (oculta) por classe de teste: criar e destruir um tk.Tk()
    custa caro. Cada teste monta o app numa janela Toplevel nova, filha dela.
    """
    entrar_como = "admin"      # "admin", "porteiro" ou None (abre no login)
    com_usuarios = True        # False = banco vazio (primeiro acesso)

    @classmethod
    def setUpClass(cls):
        try:
            cls.raiz = tk.Tk()
        except tk.TclError:
            raise unittest.SkipTest("sem tela disponível para o Tkinter")
        cls.raiz.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.raiz.destroy()

    def nova_janela(self):
        janela = tk.Toplevel(self.raiz)
        janela.withdraw()
        return janela

    def setUp(self):
        self.janela = self.nova_janela()
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho_db = os.path.join(self.pasta.name, "portaria.db")
        self.caminho_json = os.path.join(self.pasta.name, "registros_portaria.json")

        # caixas de mensagem e de diálogo viram "falsas" para o teste não travar
        self.msg = mock.MagicMock()
        self.msg.askyesno.return_value = True
        self.dialogo = mock.MagicMock()
        self.arquivo = mock.MagicMock()           # "Salvar como"
        # todas as telas usam portaria.mensagens: um patch só cobre tudo
        patcher = mock.patch.multiple("portaria.mensagens", messagebox=self.msg,
                                      simpledialog=self.dialogo,
                                      filedialog=self.arquivo)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.banco = dados.Banco(self.caminho_db)
        if self.com_usuarios:
            self.admin = criar_usuario(self.banco, "Ana Admin", "ana.admin",
                                       "admin", "senha123")
            self.porteiro = criar_usuario(self.banco, "Paulo Porteiro", "paulo",
                                          "porteiro", "senha456", "ana.admin")
        usuario = {"admin": getattr(self, "admin", None),
                   "porteiro": getattr(self, "porteiro", None)}.get(self.entrar_como)
        self.app = AppPortaria(self.caminho_db, self.janela,
                               json_antigo=self.caminho_json, usuario=usuario)

    def tearDown(self):
        # cancela os temporizadores (ex.: o aviso que some em 10 s) para não
        # dispararem no teste seguinte, que usa a mesma janela Tk
        for ident in self.raiz.tk.splitlist(self.raiz.tk.call("after", "info")):
            self.raiz.tk.call("after", "cancel", ident)
        self.app.janela.destroy()
        self.pasta.cleanup()

    def no_banco(self):
        return self.banco.listar()

    def acoes(self):
        return [(e["usuario"], e["acao"]) for e in self.banco.listar_eventos()]

    def preencher(self, nome="Ana Silva", cpf="52998224725",
                  celular="31987654321", placa="", tipo="Visitante"):
        self.app.nome.insert(0, nome)
        self.app.cpf.insert(0, cpf)
        self.app.celular.insert(0, celular)
        self.app.var_placa.set(placa)
        self.app.tipo.set(tipo)

    def cadastrar_um(self):
        self.preencher()
        self.app.cadastrar()
        return self.app.tabela.get_children()[0]

    def botoes(self, widget):
        """Textos de todos os botões desenhados (Botao) dentro de `widget`."""
        achados = []
        for filho in widget.winfo_children():
            if isinstance(filho, Botao):
                achados.append(filho.cget("text"))
            achados.extend(self.botoes(filho))
        return achados

    def buscar(self, texto):
        """Digita na busca do Movimento (procura no histórico inteiro)."""
        self.app.busca.delete(0, tk.END)
        self.app.busca.insert(0, texto)
        self.app.tela_cadastro.atualizar_tabela()

    def textos(self, widget):
        """Texto de todos os widgets dentro de `widget` que têm a opção text."""
        textos = []
        for filho in widget.winfo_children():
            if "text" in filho.keys():
                textos.append(str(filho.cget("text")))
            textos.extend(self.textos(filho))
        return textos


class TestCadastroComoAdmin(BaseInterface):
    def test_cadastrar_salva_no_banco_e_limpa_o_formulario(self):
        self.preencher(placa="abc1d23")
        self.app.cadastrar()
        # sem caixinha para fechar: o aviso aparece no rodapé do Movimento
        self.msg.showinfo.assert_not_called()
        self.assertIn("Entrada de Ana registrada", self.app.lbl_aviso.cget("text"))
        salvos = self.no_banco()
        self.assertEqual(len(salvos), 1)
        self.assertEqual(salvos[0]["placa"], "ABC1D23")
        self.assertEqual(self.app.nome.get(), "")
        self.assertEqual(self.app.tabela.get_children(), (str(salvos[0]["id"]),))
        self.assertIn(("ana.admin", "Cadastro de entrada"), self.acoes())

    def test_cadastro_invalido_mostra_erro_e_nao_salva(self):
        self.preencher(nome="123 456")
        self.app.cadastrar()
        self.msg.showerror.assert_called_once()
        self.assertEqual(self.no_banco(), [])

    def test_registrar_saida_e_excluir(self):
        linha = self.cadastrar_um()
        self.app.tabela.selection_set(linha)
        self.app.registrar_saida()
        self.assertIsNotNone(converter_data(self.no_banco()[0]["saida"]))
        self.assertEqual(self.app.tabela.item(linha)["text"], "Saiu")
        self.assertNotEqual(self.app.tabela.item(linha)["values"][-1], "—")

        self.app.tabela.selection_set(linha)
        self.app.excluir_selecionado()
        self.assertEqual(self.no_banco(), [])
        self.assertEqual(self.app.tabela.get_children(), ())
        exclusao = self.banco.listar_eventos()[0]
        self.assertEqual((exclusao["usuario"], exclusao["acao"]),
                         ("ana.admin", "Exclusão de registro"))
        self.assertIn("Ana Silva", exclusao["detalhe"])

    def test_admin_ve_botao_excluir_e_aba_usuarios(self):
        self.assertIsNotNone(self.app.btn_excluir)
        self.assertIn("Excluir", self.botoes(self.app.aba_cad))
        self.assertIsNotNone(self.app.aba_usuarios)
        self.assertEqual(self.app.lbl_usuario.cget("text"), "Ana Admin")
        self.assertEqual(self.app.lbl_perfil.cget("text"), "Administrador")

    def test_rotulo_mostra_formato_legivel(self):  # falha F4 da v1
        textos = self.textos(self.app.aba_cad)
        self.assertTrue(any("dd/mm/aaaa hh:mm" in t for t in textos))
        self.assertFalse(any("%d" in t for t in textos))

    def test_enter_cadastra_na_aba_cadastro(self):
        self.preencher()
        self.app.cadastrar(event=mock.Mock())          # como se fosse o Enter
        self.assertEqual(len(self.no_banco()), 1)

    def test_enter_fora_da_aba_cadastro_nao_cadastra(self):
        self.preencher()
        for aba in (self.app.aba_pessoas, self.app.aba_bloqueios,
                    self.app.aba_dash, self.app.aba_usuarios):
            with self.subTest(aba=str(aba)):
                self.app.abas.select(aba)
                self.app.cadastrar(event=mock.Mock())
                self.assertEqual(self.no_banco(), [])
        self.msg.showerror.assert_not_called()
        self.msg.showinfo.assert_not_called()


class TestLinhaDesatualizada(BaseInterface):
    """B3: outra estação já deu a saída (ou excluiu) e esta tela não sabe."""

    def setUp(self):
        super().setUp()
        self.preencher()
        self.app.cadastrar()
        self.preencher(nome="Beto Rocha", cpf="11144477735")
        self.app.cadastrar()
        self.ana, self.beto = sorted(r["id"] for r in self.no_banco())

    def test_saida_ja_dada_em_outra_estacao(self):
        self.banco.registrar_saida(self.ana, agora_texto(), autor="paulo")
        tela = self.app.tela_cadastro
        tela.avisar("")
        tela.registrar_saida_da_linha(str(self.ana))
        self.assertIn("já tinha saída ou foi excluída em outra estação",
                      self.msg.showwarning.call_args[0][1])
        self.assertNotIn("registrada", self.app.lbl_aviso.cget("text"))
        self.assertIsNone(tela._para_desfazer)
        self.assertEqual(self.app.tabela.item(str(self.ana))["text"], "Saiu")

    def test_registro_excluido_em_outra_estacao(self):
        self.banco.excluir([self.ana], autor="ana.admin")
        self.app.tela_cadastro.registrar_saida_da_linha(str(self.ana))
        self.assertIn("foi excluída em outra estação",
                      self.msg.showwarning.call_args[0][1])
        self.assertFalse(self.app.tabela.exists(str(self.ana)))

    def test_desfazer_so_o_que_esta_estacao_gravou(self):
        saida_da_outra = agora_texto()
        self.banco.registrar_saida(self.ana, saida_da_outra, autor="paulo")
        self.app.tabela.selection_set([str(self.ana), str(self.beto)])
        tela = self.app.tela_cadastro
        tela.registrar_saida()
        self.assertIn("Saída de Beto registrada", self.app.lbl_aviso.cget("text"))
        self.assertEqual(tela._para_desfazer, [self.beto])
        tela.desfazer_saida()
        self.assertEqual(self.banco.buscar(self.ana)["saida"], saida_da_outra)
        self.assertEqual(self.banco.buscar(self.beto)["saida"], "")

    def test_enter_com_o_foco_na_tabela_nao_cadastra(self):
        # a tecla vai para quem tem o foco: a janela precisa estar visível
        self.app.janela.deiconify()
        self.app.janela.update()
        self.app.tabela.focus_force()
        self.app.janela.update()
        self.app.tabela.event_generate("<Return>")
        self.app.janela.withdraw()
        self.msg.showerror.assert_not_called()
        self.assertEqual(len(self.no_banco()), 2)


class TestMovimento(BaseInterface):
    """A tabela mostra o dia (hoje + quem está no campus); a busca vai ao
    histórico inteiro."""
    entrar_como = "porteiro"

    def setUp(self):
        super().setUp()
        self.antiga = self.banco.inserir(dict(VISITA_ANTIGA))         # já saiu
        self.aberta = self.banco.inserir(dict(                           # dias dentro
            VISITA_ANTIGA, nome="Duda Reis", cpf="39053344705",
            entrada="15/10/2026 08:00", saida=""))
        self.hoje = self.banco.inserir({
            "nome": "Ana Silva", "cpf": "52998224725", "celular": "31987654321",
            "placa": "", "tipo": "Visitante", "entrada": agora_menos(minutos=2),
            "saida": agora_menos(minutos=1)})
        self.app.atualizar_tabela()

    def linhas(self):
        return set(self.app.tabela.get_children())

    def test_tabela_tem_so_o_movimento_do_dia(self):
        self.assertEqual(self.linhas(), {str(self.aberta), str(self.hoje)})
        # B9: "hoje" conta só as entradas de hoje (a aberta é de 15/10)
        self.assertIn("1 entrada hoje", self.app.lbl_status.cget("text"))

    def test_busca_acha_registro_antigo(self):
        self.buscar("beto")
        self.assertEqual(self.linhas(), {str(self.antiga)})
        self.assertIn("1 registro encontrado", self.app.lbl_status.cget("text"))
        self.buscar("")
        self.assertEqual(self.linhas(), {str(self.aberta), str(self.hoje)})

    def test_validar_confere_sobreposicao_com_visita_fora_da_tabela(self):
        # a visita antiga (15/10 07:00-12:00) não está na tabela, mas conta
        self.preencher(nome="Beto Rocha", cpf="11144477735")
        for campo, valor in [(self.app.entrada, "15/10/2026 08:00"),
                             (self.app.saida, "15/10/2026 09:00")]:
            campo.delete(0, tk.END)
            campo.insert(0, valor)
        self.app.cadastrar()
        self.assertIn("já tem um registro nesse período",
                      self.msg.showerror.call_args[0][1])
        self.assertEqual(len(self.no_banco()), 3)

    def test_porteiro_ve_o_cpf_mascarado(self):  # privacidade
        cpf = self.app.tabela.item(str(self.hoje))["values"][1]
        self.assertEqual(cpf, "***.982.247-**")

    def test_no_formulario_o_cpf_digitado_continua_visivel(self):
        self.app.cpf.insert(0, "52998224725")
        self.assertEqual(self.app.cpf.get(), "52998224725")


class TestMovimentoAdmin(BaseInterface):
    def test_admin_ve_o_cpf_completo(self):
        self.banco.inserir({"nome": "Ana Silva", "cpf": "52998224725",
                            "celular": "31987654321", "placa": "",
                            "tipo": "Visitante", "entrada": ha_uma_hora(),
                            "saida": ""})
        self.app.atualizar_tabela()
        linha = self.app.tabela.get_children()[0]
        self.assertEqual(self.app.tabela.item(linha)["values"][1], "529.982.247-25")


class TestDashboard(BaseInterface):
    def valor(self, chave):
        return self.app.cards[chave][0].cget("text")

    def apoio(self, chave):
        return self.app.cards[chave][1].cget("text")

    def test_sem_registros_mostra_zeros(self):
        self.assertEqual(set(self.app.cards),
                         {"dentro", "hoje", "permanencia", "veiculos"})
        self.assertEqual(self.valor("dentro"), "0")
        self.assertEqual(self.valor("hoje"), "0")
        self.assertEqual(self.valor("permanencia"), "—")
        self.assertEqual(self.apoio("permanencia"), "sem saídas registradas")
        self.assertIn("0 registros desde o início",
                      self.app.tela_dashboard.lbl_subtitulo.cget("text"))

    def test_numeros_acompanham_os_registros(self):
        self.banco.inserir(dict(VISITA_ANTIGA))                  # 5 h, com placa
        self.banco.inserir({"nome": "Ana Silva", "cpf": "52998224725",
                            "celular": "31987654321", "placa": "",
                            "tipo": "Visitante", "entrada": agora_menos(1),
                            "saida": ""})
        self.app.atualizar_tabela()
        self.assertEqual(self.valor("dentro"), "1")
        self.assertEqual(self.valor("hoje"), "1")
        self.assertEqual(self.valor("veiculos"), "1")
        self.assertEqual(self.apoio("veiculos"), "de 2 registros")
        self.assertEqual(self.valor("permanencia"), "5h 00min")
        self.assertEqual(self.apoio("permanencia"), "em 1 visita encerrada")
        self.assertIn("2 registros desde o início",
                      self.app.tela_dashboard.lbl_subtitulo.cget("text"))
        # os seis cartões por tipo viraram o gráfico "Pessoas por tipo"
        tipos = {rotulo: (total, extra) for rotulo, total, extra
                 in self.app.tela_dashboard.dados["tipos"]}
        self.assertEqual(tipos["Visitantes"], (1, "1 no campus"))
        self.assertEqual(tipos["Professores"], (1, "0 no campus"))
        self.assertEqual(tipos["Alunos"], (0, "0 no campus"))
        dias = self.app.tela_dashboard.dados["dias"]
        self.assertEqual(len(dias), 7)
        self.assertEqual(dias[-1][1], 1)                         # hoje

    def test_exportar_csv(self):
        self.banco.inserir(dict(VISITA_ANTIGA))
        caminho = os.path.join(self.pasta.name, "saida.csv")
        self.arquivo.asksaveasfilename.return_value = caminho
        dialogo = self.app.tela_dashboard.abrir_exportacao()
        dialogo.janela.withdraw()
        dialogo.periodo(date(2026, 10, 1), date(2026, 10, 31))
        dialogo.exportar()
        with open(caminho, encoding="utf-8-sig") as f:
            linhas = f.read().splitlines()
        self.assertEqual(len(linhas), 2)                 # cabeçalho + 1 visita
        self.assertIn("111.444.777-35", linhas[1])
        self.assertIn("1 registro exportado", self.msg.showinfo.call_args[0][1])
        self.assertIn(("ana.admin", "Exportação de registros"), self.acoes())

    def test_exportar_com_data_invalida_nao_pede_arquivo(self):
        dialogo = self.app.tela_dashboard.abrir_exportacao()
        dialogo.janela.withdraw()
        dialogo.desde.delete(0, tk.END)
        dialogo.desde.insert(0, "31/02/2026")
        dialogo.exportar()
        self.assertIn("Data inválida", dialogo.lbl_erro.cget("text"))
        self.arquivo.asksaveasfilename.assert_not_called()


class TestPorteiro(BaseInterface):
    entrar_como = "porteiro"

    def test_porteiro_cadastra_e_registra_saida(self):
        linha = self.cadastrar_um()
        self.app.tabela.selection_set(linha)
        self.app.registrar_saida()
        self.assertTrue(self.no_banco()[0]["saida"])
        self.assertIn(("paulo", "Saída registrada"), self.acoes())

    def test_porteiro_nao_ve_botao_excluir_nem_aba_usuarios(self):  # RN02
        self.assertIsNone(self.app.btn_excluir)
        botoes = self.botoes(self.app.aba_cad)     # os botões são desenhados
        self.assertIn("Corrigir", botoes)          # (a busca enxerga Botao)
        self.assertNotIn("Excluir", botoes)
        self.assertIsNone(self.app.aba_usuarios)
        self.assertIsNone(self.app.tela_usuarios)

    def test_porteiro_nao_exporta_csv(self):
        self.assertIsNone(self.app.tela_dashboard.btn_exportar)
        self.assertNotIn("Exportar CSV", self.botoes(self.app.aba_dash))
        self.assertIsNone(self.app.tela_dashboard.abrir_exportacao())
        self.assertIn("Somente o administrador", self.msg.showerror.call_args[0][1])
        self.arquivo.asksaveasfilename.assert_not_called()

    def test_porteiro_ve_a_aba_pessoas(self):
        self.assertIsNotNone(self.app.tela_pessoas)

    def test_porteiro_nao_consegue_excluir(self):  # RN02
        linha = self.cadastrar_um()
        self.app.tabela.selection_set(linha)
        self.app.excluir_selecionado()
        self.msg.showerror.assert_called_with(
            "Acesso negado", "Somente o administrador pode excluir registros.")
        self.assertEqual(len(self.no_banco()), 1)


class TestLogin(BaseInterface):
    entrar_como = None

    def tentar_login(self, login, senha):
        tela = self.app.tela_login
        tela.campo_login.delete(0, tk.END)
        tela.campo_login.insert(0, login)
        tela.campo_senha.delete(0, tk.END)
        tela.campo_senha.insert(0, senha)
        tela.entrar()

    def test_abre_na_tela_de_login_com_senha_oculta(self):  # RNF02
        self.assertIsNone(self.app.usuario)
        self.assertFalse(self.app.tela_login.primeiro_acesso)
        self.assertEqual(self.app.tela_login.campo_senha.cget("show"), "•")
        self.assertFalse(self.app.sessao.winfo_ismapped())

    def test_login_certo_entra_no_sistema(self):
        self.tentar_login(" Ana.Admin ", "senha123")
        self.assertEqual(self.app.usuario["login"], "ana.admin")
        self.assertTrue(hasattr(self.app, "aba_cad"))
        self.assertIn(("ana.admin", "Entrou no sistema"), self.acoes())

    def test_senha_errada_nao_entra(self):
        self.tentar_login("ana.admin", "errada")
        self.assertIsNone(self.app.usuario)
        self.assertIn("incorretos", self.app.tela_login.lbl_erro.cget("text"))
        self.assertEqual(self.app.tela_login.campo_senha.get(), "")
        self.assertIn(("ana.admin", "Login recusado"), self.acoes())

    def test_enter_em_qualquer_campo_confirma(self):  # Q13
        tela = self.app.tela_login
        self.assertEqual(tela.campos, [tela.campo_login, tela.campo_senha])
        # vale mesmo com cada campo dentro do seu próprio Frame
        for caixa in tela.campos:
            self.assertIsNot(caixa.master, tela.miolo)
            self.assertTrue(caixa.bind("<Return>"))
            self.assertTrue(caixa.bind("<KP_Enter>"))

    def test_usuario_desativado_nao_entra(self):
        self.banco.definir_ativo(self.porteiro["id"], False, "ana.admin")
        self.tentar_login("paulo", "senha456")
        self.assertIsNone(self.app.usuario)

    def test_bloqueio_depois_de_muitas_tentativas(self):
        agora = [datetime(2026, 10, 19, 19, 0)]
        self.app.relogio = lambda: agora[0]
        for _ in range(LIMITE_TENTATIVAS):
            self.tentar_login("ana.admin", "errada")
        self.tentar_login("ana.admin", "senha123")      # certa, mas bloqueado
        self.assertIsNone(self.app.usuario)
        self.assertIn("Aguarde", self.app.tela_login.lbl_erro.cget("text"))
        agora[0] += timedelta(seconds=31)
        self.tentar_login("ana.admin", "senha123")
        self.assertEqual(self.app.usuario["login"], "ana.admin")

    def test_bloqueio_continua_ao_abrir_o_programa_de_novo(self):
        agora = datetime.now()
        self.app.relogio = lambda: agora
        for _ in range(LIMITE_TENTATIVAS):
            self.tentar_login("paulo", "errada")
        self.app.janela.destroy()                       # fechou o programa
        self.janela = self.nova_janela()
        self.app = AppPortaria(self.caminho_db, self.janela,
                               relogio=lambda: agora + timedelta(seconds=5))
        self.tentar_login("paulo", "senha456")
        self.assertIsNone(self.app.usuario)
        self.assertIn("Aguarde 25 s", self.app.tela_login.lbl_erro.cget("text"))

    def test_faixa_de_erro_so_aparece_com_erro(self):
        tela = self.app.tela_login
        self.assertEqual(tela.faixa.winfo_manager(), "")
        self.tentar_login("", "")
        self.assertEqual(tela.faixa.winfo_manager(), "pack")
        self.assertIn("Informe o usuário", tela.lbl_erro.cget("text"))

    def test_sair_volta_para_o_login(self):
        self.tentar_login("paulo", "senha456")
        self.app.sair()
        self.assertIsNone(self.app.usuario)
        self.assertEqual(self.janela.bind("<Return>"), "")
        self.assertEqual(self.janela.bind("<F2>"), "")
        self.assertIn(("paulo", "Saiu do sistema"), self.acoes())
        self.tentar_login("ana.admin", "senha123")      # outro usuário entra
        self.assertEqual(self.app.usuario["perfil"], "admin")


class TestPrimeiroAcesso(BaseInterface):
    entrar_como = None
    com_usuarios = False

    def preencher_admin(self, senha="segredo1", confirmacao="segredo1"):
        tela = self.app.tela_login
        tela.campo_nome.insert(0, "Carla Dias")
        tela.campo_login.insert(0, "carla")
        tela.campo_senha.insert(0, senha)
        tela.campo_confirmacao.insert(0, confirmacao)
        tela.criar_administrador()

    def test_banco_vazio_pede_para_criar_o_administrador(self):
        tela = self.app.tela_login
        self.assertTrue(tela.primeiro_acesso)
        self.assertEqual(tela.campos, [tela.campo_nome, tela.campo_login,
                                       tela.campo_senha, tela.campo_confirmacao])
        self.assertTrue(all(c.bind("<Return>") for c in tela.campos))

    def test_senha_curta_e_recusada(self):
        self.preencher_admin(senha="123", confirmacao="123")
        self.assertIn("pelo menos", self.app.tela_login.lbl_erro.cget("text"))
        self.assertFalse(self.banco.tem_usuarios())

    def test_cria_administrador_e_entra(self):
        self.preencher_admin()
        self.assertEqual(self.app.usuario["perfil"], "admin")
        self.assertIsNotNone(autenticar(self.banco, "carla", "segredo1"))

    def test_importa_o_json_da_v1_mesmo_antes_do_login(self):
        self.app.janela.destroy()
        with open(self.caminho_json, "w", encoding="utf-8") as f:
            json.dump([{"nome": "Ana Silva", "cpf": "52998224725",
                        "celular": "31987654321", "placa": "", "tipo": "Aluno",
                        "entrada": "15/10/2026 08:00", "saida": ""}], f)
        self.janela = self.nova_janela()
        self.app = AppPortaria(self.caminho_db, self.janela,
                               json_antigo=self.caminho_json)
        self.assertIn("1 registro(s)", self.msg.showinfo.call_args[0][1])
        self.preencher_admin()
        self.assertEqual(len(self.app.tabela.get_children()), 1)


class TestSessao(BaseInterface):
    entrar_como = "porteiro"

    def test_menu_lateral_tem_as_paginas_do_perfil(self):
        textos = [i.cget("text") for i in self.app.itens_menu.values()]
        self.assertEqual(textos, ["Entrada e saída", "Pessoas", "Bloqueios",
                                  "Painel"])               # porteiro: sem Usuários
        self.assertTrue(self.app.itens_menu[str(self.app.aba_cad)].ativo)

    def test_ir_para_acende_o_item_do_menu(self):
        self.app.ir_para(self.app.aba_bloqueios)
        self.assertEqual(self.app.abas.select(), str(self.app.aba_bloqueios))
        ativos = [i.cget("text") for i in self.app.itens_menu.values() if i.ativo]
        self.assertEqual(ativos, ["Bloqueios"])

    def test_contadores_da_barra_lateral(self):
        self.banco.inserir(dict(VISITA_ANTIGA))
        self.banco.bloquear("placa", "ABC1234", "Motivo válido", "ana.admin")
        self.app.atualizar_tabela()
        self.assertEqual(self.app.itens_menu[str(self.app.aba_pessoas)].contador, "1")
        self.assertEqual(self.app.itens_menu[str(self.app.aba_bloqueios)].contador,
                         "1")

    def test_paginas_montadas_na_primeira_visita(self):
        def montadas():
            return {n for n in ("tela_pessoas", "tela_bloqueios", "tela_dashboard")
                    if n in vars(self.app)}

        self.assertEqual(montadas(), set())         # só a Entrada e saída
        self.app.ir_para(self.app.aba_pessoas)
        self.assertEqual(montadas(), {"tela_pessoas"})
        self.assertEqual(len(self.app.aba_pessoas.winfo_children()), 2)
        self.app.ir_para(self.app.aba_cad)
        self.app.ir_para(self.app.aba_pessoas)      # não monta de novo
        self.assertEqual(len(self.app.aba_pessoas.winfo_children()), 2)
        self.app.sair()
        self.app.entrar(self.porteiro)              # nova sessão: começa do zero
        self.assertEqual(montadas(), set())

    def test_f2_de_outra_pagina_volta_para_a_entrada_e_saida(self):
        self.app.ir_para(self.app.aba_dash)
        self.app.ir_para_saida_rapida()
        self.assertEqual(self.app.abas.select(), str(self.app.aba_cad))

    def test_trocar_minha_senha(self):
        menu = self.app.menu_usuario
        self.assertEqual(menu.entrycget(0, "label"), "Trocar minha senha")
        menu.invoke(0)
        dialogo = self.app.janela_senha
        dialogo.janela.withdraw()
        dialogo.atual.insert(0, "senha456")
        dialogo.nova.insert(0, "outrasenha9")
        dialogo.confirmacao.insert(0, "outrasenha9")
        dialogo.salvar()
        self.assertFalse(dialogo.janela.winfo_exists())
        self.assertIsNotNone(autenticar(self.banco, "paulo", "outrasenha9"))
        self.assertIn(("paulo", "Senha alterada"), self.acoes())

    def test_trocar_senha_com_a_atual_errada(self):
        dialogo = self.app.trocar_senha()
        dialogo.janela.withdraw()
        dialogo.atual.insert(0, "errada")
        dialogo.nova.insert(0, "outrasenha9")
        dialogo.confirmacao.insert(0, "outrasenha9")
        dialogo.salvar()
        self.assertIn("atual não confere", dialogo.lbl_erro.cget("text"))
        self.assertTrue(dialogo.janela.winfo_exists())
        self.assertIsNotNone(autenticar(self.banco, "paulo", "senha456"))

    def test_sai_sozinho_depois_de_um_tempo_sem_uso(self):
        agora = [datetime(2026, 10, 19, 19, 0)]
        self.app.relogio = lambda: agora[0]
        self.app.registrar_uso()                 # tecla ou mouse
        agora[0] += timedelta(minutes=MINUTOS_INATIVIDADE - 1)
        self.assertFalse(self.app.conferir_inatividade())
        self.app.registrar_uso()                 # usou de novo: zera
        agora[0] += timedelta(minutes=MINUTOS_INATIVIDADE - 1)
        self.assertFalse(self.app.conferir_inatividade())
        self.assertEqual(self.app.usuario["login"], "paulo")
        agora[0] += timedelta(minutes=1)
        self.assertTrue(self.app.conferir_inatividade())
        self.assertIsNone(self.app.usuario)
        self.assertIn("sem uso", self.app.tela_login.lbl_erro.cget("text"))
        self.assertIn(("paulo", "Sessão encerrada por inatividade"), self.acoes())

    def test_inatividade_fecha_as_janelas_abertas(self):
        dialogo = self.app.trocar_senha()
        self.app.relogio = lambda: datetime.now() + timedelta(hours=1)
        self.app.conferir_inatividade()
        self.assertFalse(dialogo.janela.winfo_exists())

    def test_teclado_e_mouse_contam_como_uso(self):
        self.assertTrue(self.janela.bind("<KeyPress>"))
        self.assertTrue(self.janela.bind("<Motion>"))


class TestSessaoExpiraComCaixaAberta(BaseInterface):
    """
    B1/N01: o tempo de inatividade corre enquanto uma caixa nativa (Sim/Não,
    "Salvar como", senha) está aberta. Aqui a caixa falsa encerra a sessão
    (como o temporizador faria) e só então responde. Nada pode ser gravado.
    """

    def expirar_e_responder(self, resposta):
        def caixa(*args, **kwargs):
            self.app.sair(inatividade=True)
            return resposta
        return caixa

    def assert_sessao_encerrada_avisada(self):
        self.assertIsNone(self.app.usuario)
        self.assertIn(mock.call("Sessão encerrada",
                                "A sessão foi encerrada. Entre novamente."),
                      self.msg.showwarning.call_args_list)

    def test_excluir(self):
        linha = self.cadastrar_um()
        self.app.tabela.selection_set(linha)
        tela = self.app.tela_cadastro
        self.msg.askyesno.side_effect = self.expirar_e_responder(True)
        tela.excluir_selecionado()
        self.assertEqual(len(self.no_banco()), 1)
        self.assertNotIn("Exclusão de registro", [a for _, a in self.acoes()])
        self.assert_sessao_encerrada_avisada()

    def test_desativar_usuario(self):
        aba = self.app.tela_usuarios
        aba.tabela.selection_set(str(self.porteiro["id"]))
        self.msg.askyesno.side_effect = self.expirar_e_responder(True)
        aba.alternar_ativo()
        self.assertTrue(self.banco.buscar_usuario("paulo")["ativo"])
        self.assert_sessao_encerrada_avisada()

    def test_redefinir_senha(self):
        aba = self.app.tela_usuarios
        aba.tabela.selection_set(str(self.porteiro["id"]))
        self.dialogo.askstring.side_effect = self.expirar_e_responder("novasenha9")
        aba.redefinir_senha()
        self.assertIsNotNone(autenticar(self.banco, "paulo", "senha456"))
        self.assert_sessao_encerrada_avisada()

    def test_bloquear_e_remover_bloqueio(self):
        aba = self.app.tela_bloqueios
        aba.tipo.set("Placa")
        aba.valor.insert(0, "ABC1234")
        aba.motivo.insert(0, "Motivo válido")
        self.msg.askyesno.side_effect = self.expirar_e_responder(True)
        aba.bloquear()
        self.assertEqual(self.banco.listar_bloqueios(), [])
        self.assert_sessao_encerrada_avisada()

        self.app.entrar(self.admin)
        self.banco.bloquear("placa", "ABC1234", "Motivo válido", "ana.admin")
        aba = self.app.tela_bloqueios
        aba.atualizar()
        aba.tabela.selection_set(aba.tabela.get_children()[0])
        aba.remover()
        self.assertEqual(len(self.banco.listar_bloqueios()), 1)

    def test_exportar_csv(self):
        self.banco.inserir(dict(VISITA_ANTIGA))
        caminho = os.path.join(self.pasta.name, "saida.csv")
        self.arquivo.asksaveasfilename.side_effect = self.expirar_e_responder(
            caminho)
        dialogo = self.app.tela_dashboard.abrir_exportacao()
        dialogo.periodo(date(2026, 10, 1), date(2026, 10, 31))
        dialogo.exportar()
        self.assertFalse(os.path.exists(caminho))
        self.assertNotIn("Exportação de registros", [a for _, a in self.acoes()])
        self.assert_sessao_encerrada_avisada()

    def test_saida_rapida_de_varios(self):
        for cpf in ("52998224725", "11144477735"):
            self.preencher(cpf=cpf, placa="ABC1234")
            self.app.cadastrar()
        tela = self.app.tela_cadastro
        tela.campo_saida_rapida.insert(0, "ABC1234")
        self.msg.askyesno.side_effect = self.expirar_e_responder(True)
        tela.saida_rapida()
        self.assertTrue(all(not r["saida"] for r in self.no_banco()))
        self.assert_sessao_encerrada_avisada()

    def test_inatividade_fecha_janelas_dentro_das_paginas(self):
        # o "Redefinir senha" (simpledialog) é filho da página, não da janela
        aba = self.app.tela_usuarios
        filha = tk.Toplevel(aba.aba)
        self.app.sair(inatividade=True)
        self.assertFalse(filha.winfo_exists())

    def test_sem_sessao_nada_vai_ao_banco(self):
        self.app.sair()
        self.assertFalse(self.app.gravar(self.banco.inserir, dict(VISITA_ANTIGA)))
        ok, _ = self.app.tentar(self.banco.excluir, [1], autor=None)
        self.assertFalse(ok)
        self.assertEqual(self.no_banco(), [])
        self.assert_sessao_encerrada_avisada()


class TestAbertura(BaseInterface):
    """Backup diário, avisos para o administrador e log de erros."""
    entrar_como = None

    def test_backup_diario_criado_na_abertura(self):
        nome = f"portaria-{date.today():%Y-%m-%d}.db"
        self.assertTrue(os.path.exists(
            os.path.join(self.pasta.name, "backups", nome)))

    def test_banco_v5_sem_backup_possivel_nao_derruba_o_programa(self):  # B4
        self.app.janela.destroy()
        dados.Banco(self.caminho_db)
        con = sqlite3.connect(self.caminho_db)
        con.executescript("DROP TABLE tentativas_login; PRAGMA user_version = 5;")
        con.close()
        shutil.rmtree(os.path.join(self.pasta.name, "backups"))
        with open(os.path.join(self.pasta.name, "backups"), "w") as f:
            f.write("não é pasta")
        self.app = AppPortaria(self.caminho_db, self.nova_janela())
        self.assertIsNone(self.app.banco)
        self.assertIn("cópia de segurança", self.msg.showerror.call_args[0][1])

    def test_backup_diario_que_falha_so_avisa_o_admin(self):  # B4
        self.app.janela.destroy()
        shutil.rmtree(os.path.join(self.pasta.name, "backups"))
        with open(os.path.join(self.pasta.name, "backups"), "w") as f:
            f.write("não é pasta")
        self.app = AppPortaria(self.caminho_db, self.nova_janela(),
                               usuario=self.admin)
        self.assertIsNotNone(self.app.banco)
        aviso = self.msg.showwarning.call_args[0][1]
        self.assertIn("backup diário", aviso)
        self.assertNotRegex(aviso, "Errno|WinError")   # sem o erro técnico

    def entrar(self, login, senha):
        tela = self.app.tela_login
        tela.campo_login.insert(0, login)
        tela.campo_senha.insert(0, senha)
        tela.entrar()

    def test_avisos_da_migracao_aparecem_so_para_o_admin(self):
        self.app.avisos_admin = ["2 visita(s) receberam saída automática."]
        self.entrar("paulo", "senha456")
        self.msg.showwarning.assert_not_called()
        self.app.sair()
        self.entrar("ana.admin", "senha123")
        self.assertIn("saída automática", self.msg.showwarning.call_args[0][1])
        self.app.sair()
        self.msg.showwarning.reset_mock()
        self.entrar("ana.admin", "senha123")            # só uma vez
        self.msg.showwarning.assert_not_called()

    def test_erro_do_banco_mostra_o_simples_e_loga_o_detalhe(self):
        def falha():
            raise dados.ErroDados("Erro no banco de dados.", detalhe="disk I/O error")
        self.app.entrar(self.admin)
        with self.assertLogs("portaria.dados", "WARNING") as log:
            ok, _ = self.app.tentar(falha)
        self.assertFalse(ok)
        self.msg.showerror.assert_called_with("Erro", "Erro no banco de dados.")
        self.assertIn("disk I/O error", "\n".join(log.output))

    def test_erro_inesperado_na_tela_vai_para_o_log(self):
        try:
            raise ZeroDivisionError("divisão por zero")
        except ZeroDivisionError as e:
            erro = e
        with self.assertLogs("portaria.dados", "ERROR") as log:
            self.janela.report_callback_exception(ZeroDivisionError, erro,
                                                  erro.__traceback__)
        titulo, texto = self.msg.showerror.call_args[0]
        self.assertEqual(titulo, "Erro inesperado")
        self.assertNotIn("ZeroDivision", texto)
        self.assertIn("ZeroDivisionError", "\n".join(log.output))


class TestAbaUsuarios(BaseInterface):
    def setUp(self):
        super().setUp()
        self.aba = self.app.tela_usuarios

    def linha_de(self, login):
        return next(i for i in self.aba.tabela.get_children()
                    if self.aba.tabela.item(i)["values"][0] == login)

    def test_lista_os_usuarios(self):
        logins = [self.aba.tabela.item(i)["values"][0]
                  for i in self.aba.tabela.get_children()]
        self.assertEqual(logins, ["ana.admin", "paulo"])

    def novo(self, nome, login, senha="segredo1"):
        """Botão "Novo usuário": preenche o diálogo e cria."""
        dialogo = self.aba.novo_usuario()
        dialogo.janela.withdraw()
        dialogo.nome.insert(0, nome)
        dialogo.login.insert(0, login)
        dialogo.senha.insert(0, senha)
        dialogo.confirmacao.insert(0, senha)
        dialogo.criar()
        return dialogo

    def test_criar_porteiro(self):
        dialogo = self.novo("Maria Souza", "Maria.Souza")
        novo = autenticar(self.banco, "maria.souza", "segredo1")
        self.assertEqual(novo["perfil"], "porteiro")
        self.linha_de("maria.souza")      # aparece na lista
        self.assertFalse(dialogo.janela.winfo_exists())     # o diálogo fechou
        self.assertIn(("ana.admin", "Usuário criado"), self.acoes())

    def test_login_repetido_e_recusado(self):
        dialogo = self.novo("Outro Paulo", "paulo")
        self.assertIn("Já existe", dialogo.lbl_erro.cget("text"))
        self.assertTrue(dialogo.janela.winfo_exists())      # continua aberto

    def test_botao_diz_desativar_ou_ativar(self):
        self.aba.tabela.selection_set(self.linha_de("paulo"))
        self.aba._ao_selecionar()
        self.assertEqual(self.aba.btn_ativo.cget("text"), "Desativar")
        self.aba.alternar_ativo()
        self.aba.tabela.selection_set(self.linha_de("paulo"))
        self.aba._ao_selecionar()
        self.assertEqual(self.aba.btn_ativo.cget("text"), "Ativar")

    def test_filtro_da_atividade(self):
        self.cadastrar_um()
        self.aba.atualizar()
        self.aba.busca.insert(0, "cadastro de")
        self.aba._mostrar_eventos()
        acoes = {self.aba.historico.item(i)["values"][2]
                 for i in self.aba.historico.get_children()}
        self.assertEqual(acoes, {"Cadastro de entrada"})

    def test_admin_nao_desativa_a_si_mesmo(self):
        self.aba.tabela.selection_set(self.linha_de("ana.admin"))
        self.aba.alternar_ativo()
        self.assertIn("próprio", self.msg.showerror.call_args[0][1])

    def test_desativar_e_reativar_porteiro(self):
        self.aba.tabela.selection_set(self.linha_de("paulo"))
        self.aba.alternar_ativo()
        self.assertIsNone(autenticar(self.banco, "paulo", "senha456"))
        linha = self.aba.tabela.item(self.linha_de("paulo"))
        self.assertEqual((linha["values"][3], linha["text"]),
                         ("Desativado", "Desativado"))
        self.aba.tabela.selection_set(self.linha_de("paulo"))
        self.aba.alternar_ativo()
        self.assertIsNotNone(autenticar(self.banco, "paulo", "senha456"))

    def test_redefinir_senha(self):
        self.dialogo.askstring.side_effect = ["novasenha", "novasenha"]
        self.aba.tabela.selection_set(self.linha_de("paulo"))
        self.aba.redefinir_senha()
        self.assertIsNone(autenticar(self.banco, "paulo", "senha456"))
        self.assertIsNotNone(autenticar(self.banco, "paulo", "novasenha"))
        self.assertIn(("ana.admin", "Senha redefinida"), self.acoes())

    def test_historico_mostra_as_acoes(self):
        self.cadastrar_um()
        self.aba.atualizar()
        acoes = [self.aba.historico.item(i)["values"][2]
                 for i in self.aba.historico.get_children()]
        self.assertEqual(acoes[0], "Cadastro de entrada")


class TestPreenchimentoAutomatico(BaseInterface):
    entrar_como = "porteiro"

    def setUp(self):
        super().setUp()
        self.banco.inserir(dict(VISITA_ANTIGA))

    def digitar_cpf(self, cpf):
        self.app.cpf.delete(0, tk.END)
        self.app.cpf.insert(0, cpf)

    def campos(self):
        a = self.app
        return (a.nome.get(), a.celular.get(), a.var_placa.get(), a.tipo.get())

    def dica(self):
        return self.app.lbl_pessoa.cget("text")

    def test_cpf_de_quem_ja_veio_preenche_os_dados(self):
        self.digitar_cpf("11144477735")
        self.assertEqual(self.campos(),
                         ("Beto Rocha", "31933334444", "QWE1234", "Professor"))
        self.assertIn("Já cadastrado", self.dica())
        cad = self.app.tela_cadastro              # ficha ao lado do formulário
        self.assertEqual(cad.lbl_visitas.cget("text"), "1")
        self.assertEqual(cad.lbl_ultima.cget("text"), "15/10")
        self.assertEqual(cad.lbl_tipo.cget("text"), "Professor")
        self.assertEqual(cad.desenho_placa.texto, "QWE1234")
        self.assertEqual(cad.aviso_pessoa.tipo, "sucesso")

    def test_basta_o_cpf_para_cadastrar_a_entrada(self):
        self.digitar_cpf("11144477735")
        self.app.cadastrar()
        self.assertEqual(len(self.no_banco()), 2)
        self.assertEqual(self.banco.buscar_pessoa("11144477735")["visitas"], 2)

    def test_cpf_novo_nao_preenche_nada(self):
        self.digitar_cpf("52998224725")
        self.assertEqual(self.campos(), ("", "", "", ""))
        self.assertIn("Pessoa nova", self.dica())

    def test_cpf_invalido_avisa_na_hora(self):
        self.digitar_cpf("12345678900")
        self.assertIn("CPF inválido", self.dica())

    def test_nao_apaga_o_que_ja_foi_digitado(self):
        self.app.nome.insert(0, "Roberto Rocha")
        self.digitar_cpf("11144477735")
        self.assertEqual(self.app.nome.get(), "Roberto Rocha")
        self.assertEqual(self.app.celular.get(), "31933334444")

    def test_trocar_o_cpf_desfaz_so_o_que_foi_preenchido_sozinho(self):
        self.digitar_cpf("11144477735")
        self.app.celular.delete(0, tk.END)
        self.app.celular.insert(0, "31900001111")      # porteiro corrigiu
        self.app.cpf.delete(10, tk.END)                 # apagou um dígito
        self.assertEqual(self.campos(), ("", "31900001111", "", ""))

    def test_avisa_quando_a_pessoa_ja_esta_no_campus(self):
        self.banco.inserir(dict(VISITA_ANTIGA, entrada=ha_uma_hora(), saida=""))
        self.digitar_cpf("11144477735")
        self.assertIn("está no campus desde", self.dica())
        self.assertEqual(self.app.tela_cadastro.aviso_pessoa.tipo, "alerta")

    def test_link_da_faixa_registra_a_saida(self):
        self.banco.inserir(dict(VISITA_ANTIGA, entrada=ha_uma_hora(), saida=""))
        self.digitar_cpf("11144477735")
        aviso = self.app.tela_cadastro.aviso_pessoa
        self.assertEqual(aviso.acao.cget("text"), "Registrar saída")
        self.app.tela_cadastro._saida_de("11144477735")    # clique no link
        self.assertTrue(all(r["saida"] for r in self.no_banco()))
        self.assertIn("Já cadastrado", self.dica())       # pode entrar de novo

    def test_limpar_volta_ao_inicio(self):
        self.digitar_cpf("11144477735")
        self.app.limpar()
        self.assertEqual(self.campos(), ("", "", "", ""))
        self.assertIn("Digite o CPF primeiro", self.dica())


class TestAbaPessoas(BaseInterface):
    def setUp(self):
        super().setUp()
        self.banco.inserir(dict(VISITA_ANTIGA))
        self.banco.inserir({"nome": "Ana Silva", "cpf": "52998224725",
                            "celular": "31987654321", "placa": "",
                            "tipo": "Visitante", "entrada": ha_uma_hora(),
                            "saida": ""})
        self.aba = self.app.tela_pessoas
        self.aba.atualizar()
        self.beto = self.banco.buscar_pessoa("11144477735")["id"]
        self.ana = self.banco.buscar_pessoa("52998224725")["id"]

    def selecionar(self, id_pessoa):
        self.aba.tabela.selection_set(str(id_pessoa))
        self.aba.ao_selecionar()

    def valores(self, id_pessoa):
        return self.aba.tabela.item(str(id_pessoa))["values"]

    def test_lista_pessoas_com_visitas_e_situacao(self):
        self.assertEqual(self.aba.tabela.get_children(),
                         (str(self.ana), str(self.beto)))   # ordem alfabética
        self.assertEqual(self.valores(self.ana)[-1], "No campus")
        self.assertEqual(self.valores(self.beto)[5:], [1, "15/10/2026 07:00", "—"])
        self.assertIn("1 no campus agora", self.aba.lbl_total.cget("text"))
        self.assertEqual(self.aba.tabela.item(str(self.ana))["text"], "No campus")

    def test_busca(self):
        self.aba.busca.insert(0, "beto")
        self.aba.atualizar()
        self.assertEqual(self.aba.tabela.get_children(), (str(self.beto),))

    def test_selecionar_preenche_o_formulario(self):
        self.assertEqual(self.aba.vazio.winfo_manager(), "place")  # ficha vazia
        self.selecionar(self.beto)
        self.assertEqual(self.aba.vazio.winfo_manager(), "")
        self.assertEqual(self.aba.nome.get(), "Beto Rocha")
        self.assertEqual(self.aba.var_placa.get(), "QWE1234")
        self.assertEqual(self.aba.lbl_titulo.cget("text"), "Beto Rocha")
        self.assertIn("111.444.777-35", self.aba.lbl_cpf.cget("text"))
        self.assertEqual(self.aba.lbl_visitas.cget("text"), "1")
        self.assertEqual(self.aba.desenho_placa.texto, "QWE1234")

    def test_placa_e_celular_so_aceitam_o_formato(self):  # Q04
        self.selecionar(self.beto)
        for caixa, digitado, esperado in [
                (self.aba.celular, "31a9-8", "3198"),
                (self.aba.caixa_placa, "abc-1d234", "ABC1D23")]:
            caixa.delete(0, tk.END)
            for letra in digitado:
                caixa.insert(tk.END, letra)
            self.assertEqual(caixa.get(), esperado)

    def test_salvar_alteracoes(self):
        self.selecionar(self.beto)
        self.aba.celular.delete(0, tk.END)
        self.aba.celular.insert(0, "31955556666")
        self.aba.salvar()
        self.assertEqual(self.banco.buscar_pessoa("11144477735")["celular"],
                         "31955556666")
        self.assertIn(("ana.admin", "Dados de pessoa alterados"), self.acoes())

    def test_salvar_dados_invalidos_e_recusado(self):
        self.selecionar(self.beto)
        self.aba.nome.delete(0, tk.END)
        self.aba.nome.insert(0, "Beto")
        self.aba.salvar()
        self.assertIn("nome completo", self.msg.showerror.call_args[0][1])
        self.assertEqual(self.banco.buscar_pessoa("11144477735")["nome"],
                         "Beto Rocha")

    def test_registrar_entrada_abre_o_cadastro_preenchido(self):
        self.selecionar(self.beto)
        self.aba.registrar_entrada()
        self.assertEqual(self.app.abas.select(), str(self.app.aba_cad))
        self.assertEqual(self.app.cpf.get(), "11144477735")
        self.assertEqual(self.app.nome.get(), "Beto Rocha")

    def test_quem_esta_no_campus_nao_ganha_outra_entrada(self):
        self.selecionar(self.ana)
        self.aba.registrar_entrada()
        self.assertIn("já está no campus", self.msg.showwarning.call_args[0][1])
        self.assertEqual(self.app.cpf.get(), "")

    def test_acao_sem_selecao_avisa(self):
        self.aba.salvar()
        self.assertIn("Selecione", self.msg.showwarning.call_args[0][1])



class TestSaidaRapida(BaseInterface):
    entrar_como = "porteiro"

    def setUp(self):
        super().setUp()
        entrada = ha_uma_hora()
        pessoas = [("Beto Rocha", "11144477735", "QWE1234"),
                   ("Ana Silva", "52998224725", "QWE1234"),     # mesma carona
                   ("Duda Reis", "39053344705", "")]
        self.ids = {}
        for nome, cpf, placa in pessoas:
            self.ids[nome.split()[0]] = self.banco.inserir(
                {"nome": nome, "cpf": cpf, "celular": "31987654321",
                 "placa": placa, "tipo": "Visitante", "entrada": entrada,
                 "saida": ""})
        self.app.registros = self.banco.listar()
        self.app.atualizar_tabela()

    def saida(self, nome):
        return next(r["saida"] for r in self.no_banco()
                    if r["id"] == self.ids[nome])

    def digitar(self, texto):
        self.app.campo_saida_rapida.delete(0, tk.END)
        self.app.campo_saida_rapida.insert(0, texto)
        return self.app.saida_rapida()

    def aviso(self):
        return self.app.lbl_aviso.cget("text")

    def desfazer_visivel(self):
        return self.app.btn_desfazer.winfo_manager() != ""   # está no layout

    def test_saida_pelo_cpf_formatado(self):
        resultado = self.digitar("111.444.777-35")
        self.assertEqual(resultado, "break")       # Enter não cadastra nada
        self.assertTrue(self.saida("Beto"))
        self.assertEqual(self.saida("Ana"), "")
        self.assertEqual(self.app.campo_saida_rapida.get(), "")
        self.assertIn("Saída de Beto registrada", self.aviso())
        self.assertTrue(self.desfazer_visivel())
        self.msg.showinfo.assert_not_called()      # não trava com caixinha
        self.assertIn(("paulo", "Saída registrada"), self.acoes())

    def test_placa_de_duas_pessoas_pergunta_antes(self):
        self.msg.askyesno.return_value = False
        self.digitar("qwe-1234")
        self.assertIn("Beto Rocha", self.msg.askyesno.call_args[0][1])
        self.assertEqual((self.saida("Beto"), self.saida("Ana")), ("", ""))
        self.msg.askyesno.return_value = True
        self.digitar("qwe-1234")
        self.assertTrue(self.saida("Beto") and self.saida("Ana"))
        self.assertIn("Beto e Ana", self.aviso())

    def test_cpf_ou_placa_sem_ninguem_dentro(self):
        for texto in ["12345678909", "111444777", "ZZZ9999"]:
            with self.subTest(texto=texto):
                self.digitar(texto)
                self.assertIn("Ninguém no campus", self.msg.showerror.call_args[0][1])
        self.assertTrue(all(not r["saida"] for r in self.no_banco()))

    def test_quem_ja_saiu_nao_e_encontrado_de_novo(self):
        self.digitar("39053344705")
        self.digitar("39053344705")
        self.assertIn("Ninguém no campus", self.msg.showerror.call_args[0][1])

    def test_campo_vazio_avisa(self):
        self.digitar("  ")
        self.assertIn("Digite o CPF", self.msg.showwarning.call_args[0][1])

    def test_duplo_clique_na_linha(self):
        self.assertTrue(self.app.tabela.bind("<Double-1>"))
        self.app.registrar_saida_da_linha(str(self.ids["Duda"]))
        self.assertTrue(self.saida("Duda"))
        self.assertIn("Saída de Duda", self.aviso())

    def test_duplo_clique_em_quem_ja_saiu(self):
        self.app.registrar_saida_da_linha(str(self.ids["Duda"]))
        self.app.registrar_saida_da_linha(str(self.ids["Duda"]))
        self.assertIn("já tem a saída", self.msg.showinfo.call_args[0][1])

    def test_botao_com_varias_linhas_selecionadas(self):
        self.app.tabela.selection_set([str(self.ids["Beto"]), str(self.ids["Duda"])])
        self.app.registrar_saida()
        self.assertTrue(self.saida("Beto") and self.saida("Duda"))
        self.assertEqual(self.saida("Ana"), "")

    def test_desfazer_volta_a_pessoa_para_dentro(self):
        self.digitar("11144477735")
        self.app.desfazer_saida()
        self.assertEqual(self.saida("Beto"), "")
        self.assertIn("Saída desfeita", self.aviso())
        self.assertFalse(self.desfazer_visivel())
        self.assertIn(("paulo", "Saída desfeita"), self.acoes())
        linha = self.app.tabela.item(str(self.ids["Beto"]))
        self.assertEqual((linha["text"], linha["values"][-1]), ("No campus", "—"))

    def test_f2_vai_para_a_saida_rapida(self):
        self.assertTrue(self.janela.bind("<F2>"))


class CasosCorrigir:
    """Testes da janela Corrigir que valem para porteiro e administrador."""

    def setUp(self):
        super().setUp()
        self.hoje = self.banco.inserir(dict(VISITA_ANTIGA, entrada=ha_uma_hora(),
                                            saida=""), autor="paulo")
        self.antigo = self.banco.inserir(dict(VISITA_ANTIGA, nome="Ana Silva",
                                              cpf="52998224725"))
        self.app.registros = self.banco.listar()
        self.app.atualizar_tabela()

    def abrir(self, id_):
        if not self.app.tabela.exists(str(id_)):
            self.buscar("Ana Silva")     # registro antigo: só aparece buscando
        self.app.tabela.selection_set(str(id_))
        self.app.editar_selecionado()
        janela = getattr(self.app, "janela_edicao", None)
        if janela:
            janela.janela.withdraw()
        return janela

    def trocar(self, campo, valor):
        campo.delete(0, tk.END)
        campo.insert(0, valor)

    def test_corrige_registro_de_hoje(self):
        edicao = self.abrir(self.hoje)
        self.assertEqual(edicao.nome.get(), "Beto Rocha")
        self.trocar(edicao.nome, "Roberto Rocha")
        edicao.salvar()
        self.assertEqual(self.banco.buscar(self.hoje)["nome"], "Roberto Rocha")
        self.assertFalse(edicao.janela.winfo_exists())
        self.assertIn("corrigido", self.app.lbl_aviso.cget("text"))
        evento = self.banco.eventos_do_registro(self.hoje)[-1]
        self.assertEqual((evento["usuario"], evento["acao"]),
                         (self.app.usuario["login"], "Registro corrigido"))
        self.assertIn("Nome: Beto Rocha → Roberto Rocha", evento["detalhe"])
        linha = self.app.tabela.item(str(self.hoje))["values"]
        self.assertEqual(linha[0], "Roberto Rocha")

    def test_janela_mostra_o_historico_do_registro(self):
        edicao = self.abrir(self.hoje)
        acoes = [edicao.historico.item(i)["values"][2]
                 for i in edicao.historico.get_children()]
        self.assertEqual(acoes, ["Cadastro de entrada"])
        edicao.historico.selection_set(edicao.historico.get_children()[0])
        edicao.mostrar_detalhe()
        self.assertIn("Cadastro de entrada por paulo",
                      edicao.lbl_detalhe.cget("text"))

    def test_cpf_celular_e_placa_so_aceitam_o_formato(self):  # Q04
        edicao = self.abrir(self.hoje)
        for campo, digitado, esperado in [
                (edicao.cpf, "1a1.4", "114"), (edicao.celular, "31x9", "319")]:
            campo.delete(0, tk.END)
            for letra in digitado:
                campo.insert(tk.END, letra)
            self.assertEqual(campo.get(), esperado)
        edicao.caixa_placa.delete(0, tk.END)
        for letra in "qwe-1e34x":
            edicao.caixa_placa.insert(tk.END, letra)
        self.assertEqual(edicao.var_placa.get(), "QWE1E34")

    def test_sem_alteracao_avisa(self):
        edicao = self.abrir(self.hoje)
        edicao.salvar()
        self.assertEqual(self.msg.showinfo.call_args[0][1], "Nada foi alterado.")

    def test_correcao_passa_pelas_mesmas_validacoes(self):
        edicao = self.abrir(self.hoje)
        self.trocar(edicao.nome, "Beto 123")
        edicao.salvar()
        self.assertIn("apenas letras", self.msg.showerror.call_args[0][1])
        self.assertEqual(self.banco.buscar(self.hoje)["nome"], "Beto Rocha")

    def test_nao_pode_colocar_saida_antes_da_entrada(self):
        edicao = self.abrir(self.hoje)
        self.trocar(edicao.saida, "01/01/2026 00:00")
        edicao.salvar()
        self.assertIn("anterior à entrada", self.msg.showerror.call_args[0][1])

    def test_nao_burla_o_bloqueio_pela_correcao(self):  # S01 da revisão
        self.banco.bloquear("cpf", "39053344705", "Ameaçou um aluno", "ana.admin")
        edicao = self.abrir(self.hoje)
        self.trocar(edicao.cpf, "39053344705")
        edicao.salvar()
        titulo, msg = self.msg.showerror.call_args[0]
        self.assertEqual(titulo, "Acesso negado")
        self.assertIn("Ameaçou um aluno", msg)
        self.assertEqual(self.banco.buscar(self.hoje)["cpf"], "11144477735")

    def test_selecionar_varios_avisa(self):
        self.buscar("Professor")          # os dois aparecem na busca
        self.app.tabela.selection_set([str(self.hoje), str(self.antigo)])
        self.app.editar_selecionado()
        self.assertIn("um registro só", self.msg.showwarning.call_args[0][1])


class TestCorrigirComoPorteiro(CasosCorrigir, BaseInterface):
    entrar_como = "porteiro"

    def test_porteiro_nao_corrige_registro_antigo(self):  # RN11
        self.assertIsNone(self.abrir(self.antigo))
        self.assertIn("últimas 24 horas",
                      self.msg.showerror.call_args[0][1])

    def test_porteiro_nao_move_registro_para_outro_dia(self):
        edicao = self.abrir(self.hoje)
        self.trocar(edicao.entrada, "10/10/2026 08:00")
        edicao.salvar()
        self.assertIn("últimas 24 horas", self.msg.showerror.call_args[0][1])
        self.assertTrue(edicao.janela.winfo_exists())


class TestCorrigirComoAdmin(CasosCorrigir, BaseInterface):
    entrar_como = "admin"

    def test_admin_corrige_registro_antigo_e_cpf(self):
        edicao = self.abrir(self.antigo)
        self.trocar(edicao.cpf, "39053344705")
        edicao.salvar()
        self.assertEqual(self.banco.buscar(self.antigo)["cpf"], "39053344705")
        self.assertIsNone(self.banco.buscar_pessoa("52998224725"))


class TestBloqueioNoCadastro(BaseInterface):
    entrar_como = "porteiro"

    def setUp(self):
        super().setUp()
        self.banco.inserir(dict(VISITA_ANTIGA))
        self.banco.bloquear("cpf", "11144477735", "Ameaçou um aluno", "ana.admin")
        self.banco.bloquear("placa", "XYZ9A87", "Veículo furtado", "ana.admin")

    def test_alerta_ao_digitar_cpf_bloqueado(self):
        self.app.cpf.insert(0, "11144477735")
        dica = self.app.lbl_pessoa.cget("text")
        self.assertIn("CPF bloqueado: Ameaçou um aluno", dica)
        self.assertEqual(self.app.tela_cadastro.aviso_pessoa.tipo, "erro")
        self.assertEqual(self.app.nome.get(), "Beto Rocha")   # ainda preenche

    def test_alerta_ao_digitar_placa_bloqueada(self):
        self.app.var_placa.set("xyz9a87")
        self.assertEqual(self.app.lbl_dica_placa.cget("text"), "bloqueada")
        self.assertIn("Placa bloqueada: Veículo furtado",
                      self.app.lbl_placa_status.cget("text"))
        self.assertTrue(self.app.tela_cadastro.desenho_placa.bloqueada)
        self.app.var_placa.set("XYZ9A8")                       # apagou um
        self.assertEqual(self.app.lbl_dica_placa.cget("text"), "opcional")
        self.assertEqual(self.app.lbl_placa_status.cget("text"), "")
        self.assertFalse(self.app.tela_cadastro.desenho_placa.bloqueada)

    def test_cadastro_de_cpf_bloqueado_e_recusado_e_registrado(self):  # RN12
        self.app.cpf.insert(0, "11144477735")
        self.app.cadastrar()
        titulo, msg = self.msg.showerror.call_args[0]
        self.assertEqual(titulo, "Acesso negado")
        self.assertIn("Ameaçou um aluno", msg)
        self.assertEqual(len(self.no_banco()), 1)             # só a visita antiga
        self.assertIn(("paulo", "Entrada recusada (bloqueio)"), self.acoes())

    def test_bloqueio_vem_antes_das_outras_validacoes(self):
        self.app.var_placa.set("XYZ9A87")                      # só a placa
        self.app.cadastrar()
        self.assertEqual(self.msg.showerror.call_args[0][0], "Acesso negado")

    def test_pessoa_bloqueada_aparece_na_aba_pessoas(self):
        self.app.tela_pessoas.atualizar()
        id_ = str(self.banco.buscar_pessoa("11144477735")["id"])
        linha = self.app.tela_pessoas.tabela.item(id_)
        self.assertEqual((linha["values"][-1], linha["text"]),
                         ("Bloqueado", "Bloqueado"))
        self.assertEqual(linha["values"][1], "***.444.777-**")    # porteiro

    def test_porteiro_ve_a_lista_mas_nao_gerencia(self):
        aba = self.app.tela_bloqueios
        self.app.abas.select(self.app.aba_bloqueios)
        self.app.ao_trocar_aba()                 # abrir a aba recarrega
        self.assertIsNone(aba.form)
        self.assertIsNone(aba.btn_remover)
        self.assertEqual(len(aba.tabela.get_children()), 2)
        valores = {aba.tabela.item(i)["values"][1] for i in aba.tabela.get_children()}
        self.assertEqual(valores, {"***.444.777-**", "XYZ9A87"})   # CPF mascarado
        aba.bloquear()
        self.assertIn("Somente o administrador", self.msg.showerror.call_args[0][1])


class TestAbaBloqueios(BaseInterface):
    def setUp(self):
        super().setUp()
        self.aba = self.app.tela_bloqueios

    def preencher(self, tipo, valor, motivo):
        self.aba.tipo.set(tipo)
        self.aba.valor.delete(0, tk.END)
        self.aba.valor.insert(0, valor)
        self.aba.motivo.delete(0, tk.END)
        self.aba.motivo.insert(0, motivo)
        self.aba.bloquear()

    def test_admin_bloqueia_cpf(self):
        self.preencher("CPF", "111.444.777-35", "Ameaçou um aluno")
        self.assertIn("Bloquear o CPF 111.444.777-35",
                      self.msg.askyesno.call_args[0][1])
        b = self.banco.listar_bloqueios()[0]
        self.assertEqual((b["valor"], b["criado_por"]), ("11144477735", "ana.admin"))
        self.assertEqual(len(self.aba.tabela.get_children()), 1)
        self.assertEqual(self.aba.valor.get(), "")

    def test_formulario_abre_e_fecha_pelo_botao(self):
        self.assertEqual(self.aba.form.winfo_manager(), "")
        self.aba.alternar_formulario()
        self.assertEqual(self.aba.form.winfo_manager(), "pack")
        self.preencher("Placa", "ABC1234", "Motivo válido")
        self.assertEqual(self.aba.form.winfo_manager(), "")     # fechou ao bloquear

    def test_remover_so_com_bloqueio_ativo_selecionado(self):
        self.preencher("Placa", "ABC1234", "Motivo válido")
        self.assertEqual(self.aba.btn_remover.cget("state"), "disabled")
        self.aba.tabela.selection_set(self.aba.tabela.get_children()[0])
        self.aba._ao_selecionar()
        self.assertEqual(self.aba.btn_remover.cget("state"), "normal")

    def test_admin_ve_o_cpf_bloqueado_completo(self):
        self.preencher("CPF", "111.444.777-35", "Ameaçou um aluno")
        linha = self.aba.tabela.get_children()[0]
        self.assertEqual(self.aba.tabela.item(linha)["values"][1], "111.444.777-35")

    def test_cancelar_a_confirmacao_nao_bloqueia(self):
        self.msg.askyesno.return_value = False
        self.preencher("Placa", "abc-1234", "Estacionou em local proibido")
        self.assertEqual(self.banco.listar_bloqueios(), [])

    def test_dados_invalidos(self):
        self.preencher("CPF", "111.444.777-35", "ab")
        self.assertIn("motivo", self.msg.showerror.call_args[0][1])
        self.preencher("Placa", "AB1", "Motivo válido")
        self.assertIn("Placa inválida", self.msg.showerror.call_args[0][1])

    def test_bloqueio_repetido(self):
        self.preencher("Placa", "ABC1234", "Motivo válido")
        self.preencher("Placa", "abc-1234", "Outro motivo")
        self.assertIn("Esta placa já está bloqueada", self.msg.showerror.call_args[0][1])

    def test_avisa_se_a_pessoa_bloqueada_esta_no_campus(self):
        self.banco.inserir(dict(VISITA_ANTIGA, entrada=ha_uma_hora(), saida=""))
        self.app.registros = self.banco.listar()
        self.preencher("CPF", "11144477735", "Ameaçou um aluno")
        self.assertIn("No campus agora: Beto Rocha",
                      self.msg.showinfo.call_args[0][1])

    def test_remover_bloqueio_e_ver_removidos(self):
        self.preencher("CPF", "11144477735", "Ameaçou um aluno")
        id_ = self.aba.tabela.get_children()[0]
        self.aba.tabela.selection_set(id_)
        self.aba.remover()
        self.assertEqual(self.aba.tabela.get_children(), ())
        self.aba.ver_removidos.set(True)
        self.aba.atualizar()
        linha = self.aba.tabela.item(id_)
        self.assertEqual(linha["text"], "Removido")
        self.assertIn("por ana.admin", linha["values"][-1])
        self.assertIn("situacao", self.aba.tabela["displaycolumns"])
        self.assertIn(("ana.admin", "Bloqueio removido"), self.acoes())

    def test_depois_de_remover_a_entrada_volta_a_ser_aceita(self):
        self.preencher("CPF", "52998224725", "Motivo válido")
        self.aba.tabela.selection_set(self.aba.tabela.get_children()[0])
        self.aba.remover()
        self.app.cpf.insert(0, "52998224725")
        self.app.nome.insert(0, "Ana Silva")
        self.app.celular.insert(0, "31987654321")
        self.app.tipo.set("Visitante")
        self.app.cadastrar()
        self.assertEqual(len(self.no_banco()), 1)


class TestContratoDoApp(BaseInterface):
    def test_nomes_antigos_apontam_para_a_aba_cadastro(self):
        cadastro = self.app.tela_cadastro
        self.assertIs(self.app.cpf, cadastro.cpf)
        self.assertIs(self.app.tabela, cadastro.tabela)
        self.assertEqual(self.app.cadastrar, cadastro.cadastrar)
        self.assertIs(self.app.cards, self.app.tela_dashboard.cards)
        with self.assertRaises(AttributeError):
            self.app.nao_existe

    def test_telas_nao_usam_nada_privado_do_app(self):  # Q10
        pasta = os.path.dirname(dados.__file__)
        for arquivo in os.listdir(pasta):
            if arquivo.startswith("tela_"):
                with self.subTest(arquivo=arquivo):
                    with open(os.path.join(pasta, arquivo), encoding="utf-8") as f:
                        self.assertNotRegex(f.read(), r"app\._")


if __name__ == "__main__":
    unittest.main()
