"""
O enunciado da Atividade A3 conferido item por item, na ordem em que ele
pede: Tela 1 (Login), Tela 2 (Cadastro), Tela 3 (Controle de entrada e saída),
os requisitos técnicos e os desafios extras. docs/ENUNCIADO_A3.md aponta para
cada classe daqui.
"""
import ast
import ctypes
import os
import sqlite3
import sys
import tkinter as tk
import unittest
from datetime import timedelta
from tkinter import ttk
from unittest import mock

import portaria
from portaria import dados, horarios
from portaria.componentes import BotaoTk, CampoTexto
from portaria.tela_cadastro import COLUNAS_PRESTADOR, COLUNAS_VISIVEIS, FILTROS
from portaria.validacao import (CATEGORIAS_OCORRENCIA, FORMATO, MAXIMO_EMPRESA,
                                MAXIMO_MOTIVO_VISITA, TIPOS_ACESSO)

from .test_interface import AGORA, VISITA_ANTIGA, BaseInterface, agora_menos

ANA, BETO, CARLA = "52998224725", "11144477735", "39053344705"
PRESTADOR = "Prestador de serviço"


def widgets(pai):
    """Todos os widgets dentro de `pai`."""
    for filho in pai.winfo_children():
        yield filho
        yield from widgets(filho)


class TestTela1Login(BaseInterface):
    """Tela 1: Entry usuário e senha, Checkbutton, Button entrar e limpar,
    Label, Imagem/Logo, e as funções pedidas."""
    entrar_como = None

    def setUp(self):
        super().setUp()
        self.tela = self.app.tela_login
        self.usuario, self.senha = self.tela.campos[0], self.tela.senhas[0]

    def test_componentes_do_enunciado(self):
        tela = self.tela
        self.assertIsInstance(self.usuario, tk.Entry)
        self.assertIsInstance(self.senha, tk.Entry)
        self.assertIsInstance(tela.chk_mostrar, tk.Checkbutton)
        self.assertIsInstance(tela.btn_acao, tk.Button)
        self.assertIsInstance(tela.btn_limpar, tk.Button)
        self.assertEqual(tela.btn_acao.cget("text"), "Entrar")
        self.assertEqual(tela.btn_limpar.cget("text"), "Limpar")
        tipos = [type(w) for w in widgets(self.app.janela)]
        self.assertIn(tk.Label, tipos)

    def test_logo_e_uma_imagem_de_verdade(self):
        self.assertIsInstance(self.tela.logo, tk.PhotoImage)
        self.assertGreater(self.tela.logo.width(), 32)
        rotulos = [w for w in widgets(self.app.janela)
                   if isinstance(w, tk.Label) and w.cget("image")]
        self.assertTrue(any(str(self.tela.logo) == w.cget("image")
                            for w in rotulos))

    def test_arquivo_do_logo_existe_e_vai_no_exe(self):
        raiz = os.path.dirname(os.path.dirname(portaria.__file__))
        self.assertTrue(os.path.exists(os.path.join(raiz, "assets",
                                                    "logo_portaria.png")))
        with open(os.path.join(raiz, "build_exe.py"), encoding="utf-8") as f:
            self.assertIn("logo_portaria.png", f.read())

    def test_sem_o_arquivo_do_logo_o_login_nao_quebra(self):
        with mock.patch("portaria.tela_login.imagem_do_logo", return_value=None):
            self.app._trocar_corpo()
            self.app.mostrar_login() if hasattr(self.app, "mostrar_login") else None

    def test_senha_comeca_escondida_e_o_checkbutton_mostra(self):
        self.senha.insert(0, "segredo1")
        self.assertEqual(self.senha.cget("show"), "•")
        self.tela.chk_mostrar.invoke()
        self.assertTrue(self.tela.var_mostrar.get())
        self.assertEqual(self.senha.cget("show"), "")
        self.assertEqual(self.senha.get(), "segredo1")
        self.tela.chk_mostrar.invoke()
        self.assertEqual(self.senha.cget("show"), "•")

    def test_limpar_esvazia_esconde_a_senha_e_o_erro(self):
        self.usuario.insert(0, "ana.admin")
        self.senha.insert(0, "errada")
        self.tela.chk_mostrar.invoke()
        self.tela.entrar()
        self.assertTrue(self.tela.lbl_erro.cget("text"))
        self.tela.btn_limpar.invoke()
        self.assertEqual((self.usuario.get(), self.senha.get()), ("", ""))
        self.assertFalse(self.tela.var_mostrar.get())
        self.assertEqual(self.senha.cget("show"), "•")
        self.assertEqual(self.tela.faixa.winfo_manager(), "")

    def test_impede_campos_vazios(self):
        for usuario, senha in (("", ""), ("ana", ""), ("", "x"), ("   ", "   ")):
            with self.subTest(usuario=usuario, senha=senha):
                self.tela.limpar()
                self.usuario.insert(0, usuario)
                self.senha.insert(0, senha)
                self.tela.entrar()
                self.assertIn("Informe", self.tela.lbl_erro.cget("text"))
                self.assertIsNone(self.app.usuario)

    def test_dados_incorretos_dao_mensagem_de_erro(self):
        self.usuario.insert(0, "ana.admin")
        self.senha.insert(0, "senha-errada")
        self.tela.entrar()
        self.assertIsNone(self.app.usuario)
        self.assertTrue(self.tela.lbl_erro.cget("text"))

    def test_usuario_que_nao_existe_da_a_mesma_mensagem(self):
        """Não entrega quais usuários existem."""
        self.usuario.insert(0, "ana.admin")
        self.senha.insert(0, "senha-errada")
        self.tela.entrar()
        com_usuario = self.tela.lbl_erro.cget("text")
        self.tela.limpar()
        self.usuario.insert(0, "ninguem")
        self.senha.insert(0, "senha-errada")
        self.tela.entrar()
        self.assertEqual(self.tela.lbl_erro.cget("text"), com_usuario)


class TestLoginValidoAbreAPrincipal(BaseInterface):
    entrar_como = None

    def test_login_valido_abre_a_tela_principal(self):
        tela = self.app.tela_login
        tela.campos[0].insert(0, "ana.admin")
        tela.senhas[0].insert(0, "senha123")
        tela.btn_acao.invoke()
        self.assertIsNotNone(self.app.usuario)
        self.assertEqual(self.app.abas.select(), str(self.app.aba_cad))


class TestPrimeiroAcessoComCheckbutton(BaseInterface):
    entrar_como = None
    com_usuarios = False

    def test_mostra_as_duas_senhas_e_limpar_nao_apaga_o_que_nao_deve(self):
        tela = self.app.tela_login
        self.assertEqual(len(tela.senhas), 2)
        tela.campo_senha.insert(0, "segredo1")
        tela.campo_confirmacao.insert(0, "segredo1")
        tela.chk_mostrar.invoke()
        for caixa in tela.senhas:
            self.assertEqual(caixa.cget("show"), "")
        tela.btn_limpar.invoke()
        for caixa in tela.campos:
            self.assertEqual(caixa.get(), "")
        for caixa in tela.senhas:
            self.assertEqual(caixa.cget("show"), "•")


class BaseCadastro(BaseInterface):
    def preencher_tudo(self, cpf=ANA, nome="Ana Silva", celular="31987654321",
                       tipo="Visitante", empresa="Alfa Ltda", motivo="Reunião",
                       placa=""):
        app = self.app
        for campo, valor in ((app.cpf, cpf), (app.nome, nome),
                             (app.celular, celular), (app.empresa, empresa),
                             (app.motivo, motivo)):
            campo.delete(0, tk.END)
            campo.insert(0, valor)
        app.var_placa.set(placa)
        app.tipo.set(tipo)

    def erro(self):
        return self.msg.showerror.call_args[0][1]


class TestTela2Cadastro(BaseCadastro):
    """Tela 2: Entry nome, CPF, telefone e empresa; Combobox tipo de acesso;
    DateEntry data; Entry horário; Text motivo; Button cadastrar, limpar e
    cancelar; Label."""

    def test_componentes_do_enunciado(self):
        tela = self.app.tela_cadastro
        for campo in (tela.nome, tela.cpf, tela.celular, tela.empresa,
                      tela.campo_data_entrada, tela.campo_hora_entrada):
            self.assertIsInstance(campo, tk.Entry)
        self.assertIsInstance(tela.tipo, ttk.Combobox)
        self.assertEqual(list(tela.tipo.cget("values")), TIPOS_ACESSO)
        self.assertIsInstance(tela.motivo, CampoTexto)
        self.assertIsInstance(tela.motivo.texto, tk.Text)
        for botao, texto in ((tela.btn_cadastrar, "Cadastrar"),
                             (tela.btn_limpar, "Limpar"),
                             (tela.btn_cancelar, "Cancelar")):
            self.assertIsInstance(botao, tk.Button)
            self.assertEqual(botao.cget("text"), texto)
        textos = self.textos(self.app.aba_cad)
        for rotulo in ("Nome completo *", "CPF *", "Telefone *", "Empresa *",
                       "Tipo de acesso *", "Data *", "Horário *",
                       "Motivo da visita *", "* campos obrigatórios"):
            self.assertIn(rotulo, textos)

    def test_as_tres_colunas_do_formulario_tem_a_mesma_largura(self):
        self.janela.deiconify()
        for tamanho in ("1093x536", "1180x760"):
            self.janela.geometry(tamanho)
            self.janela.update()
            tela = self.app.tela_cadastro
            larguras = [c.winfo_width() for c in (tela.pecas["celular"][1],
                                                  tela.pecas["placa"][1],
                                                  tela.pecas["tipo"][1])]
            self.assertLessEqual(max(larguras) - min(larguras), 14, larguras)

    def test_data_abre_o_calendario(self):
        campo = self.app.tela_cadastro.pecas["data"][1]
        self.assertEqual(campo.modo_seletor, "data")
        campo.abrir_seletor()
        pop = campo.seletor_aberto
        pop.escolher_dia((AGORA - timedelta(days=2)).date())
        pop.confirmar()
        self.assertEqual(self.app.tela_cadastro.campo_data_entrada.get(),
                         (AGORA - timedelta(days=2)).strftime("%d/%m/%Y"))

    def test_data_e_horario_comecam_em_agora(self):
        tela = self.app.tela_cadastro
        self.assertEqual(tela.campo_data_entrada.get(), AGORA.strftime("%d/%m/%Y"))
        self.assertEqual(tela.campo_hora_entrada.get(), AGORA.strftime("%H:%M"))
        self.assertEqual(tela.entrada.get(), AGORA.strftime(FORMATO))

    def test_cada_campo_obrigatorio(self):
        casos = {"nome": "nome", "celular": "telefone", "tipo": "tipo",
                 "empresa": "empresa", "motivo": "motivo"}
        for campo, trecho in casos.items():
            with self.subTest(campo=campo):
                self.msg.reset_mock()
                self.app.limpar()
                self.preencher_tudo(**{campo: ""})
                self.app.tela_cadastro.btn_cadastrar.invoke()
                self.assertEqual(self.no_banco(), [])
                self.assertIn(trecho, self.erro().lower())

    def test_so_espacos_nao_contam(self):
        self.preencher_tudo(empresa="    ", motivo="  \n  ")
        self.app.tela_cadastro.btn_cadastrar.invoke()
        self.assertEqual(self.no_banco(), [])
        self.assertIn("empresa", self.erro().lower())

    def test_cpf_vazio_ou_invalido_e_recusado(self):
        for cpf in ("", "12345678900", "11111111111", "5299822472"):
            with self.subTest(cpf=cpf):
                self.msg.reset_mock()
                self.app.limpar()
                self.preencher_tudo(cpf=cpf)
                self.app.tela_cadastro.btn_cadastrar.invoke()
                self.assertEqual(self.no_banco(), [])
                self.assertIn("CPF", self.erro())

    def test_data_ou_horario_invalidos(self):
        tela = self.app.tela_cadastro
        for data, hora in (("99/99/2026", "10:00"), (AGORA.strftime("%d/%m/%Y"), "25:00"),
                           ("", "10:00"), (AGORA.strftime("%d/%m/%Y"), "")):
            with self.subTest(data=data, hora=hora):
                self.msg.reset_mock()
                self.app.limpar()
                self.preencher_tudo()
                tela.campo_data_entrada.delete(0, tk.END)
                tela.campo_data_entrada.insert(0, data)
                tela.campo_hora_entrada.delete(0, tk.END)
                tela.campo_hora_entrada.insert(0, hora)
                self.app.tela_cadastro.btn_cadastrar.invoke()
                self.assertEqual(self.no_banco(), [])
                self.msg.showerror.assert_called()

    def test_salva_tudo_no_sqlite(self):
        self.preencher_tudo()
        self.app.tela_cadastro.btn_cadastrar.invoke()
        con = sqlite3.connect(self.caminho_db)
        linha = con.execute("SELECT nome, cpf, celular, tipo, empresa, motivo "
                            "FROM registros").fetchone()
        pessoa = con.execute("SELECT empresa FROM pessoas").fetchone()
        con.close()
        self.assertEqual(linha, ("Ana Silva", ANA, "31987654321", "Visitante",
                                 "Alfa Ltda", "Reunião"))
        self.assertEqual(pessoa, ("Alfa Ltda",))

    def test_gera_codigo_e_confirma_depois_de_salvar(self):
        self.preencher_tudo()
        self.app.tela_cadastro.btn_cadastrar.invoke()
        texto = self.app.lbl_pessoa.cget("text")
        self.assertIn("Código 001", texto)
        self.assertIn("com sucesso", texto)
        self.assertEqual(self.app.tela_cadastro.aviso_pessoa.tipo, "sucesso")
        self.assertEqual(self.app.cpf.get(), "")       # formulário limpo

    def test_cada_cadastro_tem_o_seu_codigo(self):
        self.preencher_tudo()
        self.app.cadastrar()
        self.preencher_tudo(cpf=BETO, nome="Beto Rocha")
        self.app.cadastrar()
        self.assertIn("Código 002", self.app.lbl_pessoa.cget("text"))
        codigos = [self.app.tabela.set(i, "Codigo")
                   for i in self.app.tabela.get_children()]
        self.assertEqual(sorted(codigos), ["001", "002"])

    def test_nao_duplica_a_entrada_em_aberto(self):
        self.preencher_tudo()
        self.app.tela_cadastro.btn_cadastrar.invoke()
        self.preencher_tudo()
        self.app.tela_cadastro.btn_cadastrar.invoke()
        self.assertEqual(len(self.no_banco()), 1)
        self.assertIn("sem saída", self.erro().lower())

    def test_limpar_esvazia_todos_os_campos(self):
        self.preencher_tudo(placa="ABC1D23")
        self.app.tela_cadastro.btn_limpar.invoke()
        for campo in (self.app.cpf, self.app.nome, self.app.celular,
                      self.app.empresa, self.app.motivo):
            self.assertEqual(campo.get(), "")
        self.assertEqual(self.app.var_placa.get(), "")
        self.assertEqual(self.app.tipo.get(), "")
        self.assertEqual(self.app.entrada.get(), AGORA.strftime(FORMATO))

    def test_cancelar_descarta_e_vai_ao_controle(self):
        self.preencher_tudo()
        self.app.tela_cadastro.btn_cancelar.invoke()
        self.assertEqual(self.no_banco(), [])
        self.assertEqual(self.app.cpf.get(), "")
        self.assertEqual(self.app.abas.select(), str(self.app.aba_controle))

    def test_cpf_de_quem_ja_veio_traz_empresa_e_ultimo_motivo(self):
        self.banco.inserir(dict(VISITA_ANTIGA, empresa="UNA", motivo="Aula"))
        self.app.cpf.insert(0, BETO)
        self.assertEqual(self.app.nome.get(), "Beto Rocha")
        self.assertEqual(self.app.empresa.get(), "UNA")
        self.assertEqual(self.app.motivo.get(), "Aula")

    def test_cadastro_antigo_sem_empresa_pede_para_completar(self):
        self.banco.inserir(dict(VISITA_ANTIGA, empresa="", motivo=""))
        self.app.cpf.insert(0, BETO)
        self.app.tela_cadastro.btn_cadastrar.invoke()
        self.assertEqual(len(self.no_banco()), 1)
        self.assertIn("empresa", self.erro().lower())
        self.app.empresa.insert(0, "UNA")
        self.app.motivo.insert(0, "Aula")
        self.app.tela_cadastro.btn_cadastrar.invoke()
        self.assertEqual(len(self.no_banco()), 2)
        self.assertEqual(self.banco.buscar_pessoa(BETO)["empresa"], "UNA")

    def test_motivo_tem_limite_e_contador(self):
        tela = self.app.tela_cadastro
        tela.motivo.insert(0, "x" * (MAXIMO_MOTIVO_VISITA + 50))
        self.assertEqual(len(tela.motivo.get()), MAXIMO_MOTIVO_VISITA)
        self.assertEqual(tela.contador_motivo.cget("text"),
                         f"{MAXIMO_MOTIVO_VISITA}/{MAXIMO_MOTIVO_VISITA}")
        self.assertEqual(self.app.empresa.master.maximo, MAXIMO_EMPRESA)

    def test_motivo_colado_com_quebras_vira_uma_linha_so(self):
        tela = self.app.tela_cadastro
        self.raiz.clipboard_clear()
        self.raiz.clipboard_append("linha um\nlinha dois\r\n\tfim")
        tela.motivo._colar()
        self.assertEqual(tela.motivo.get(), "linha um linha dois fim")
        self.preencher_tudo(motivo="a\nb")
        self.app.cadastrar()
        self.assertEqual(self.no_banco()[0]["motivo"], "a b")

    def test_enter_no_motivo_cadastra_e_nao_quebra_a_linha(self):
        self.preencher_tudo()
        self.janela.deiconify()
        self.janela.update()
        texto = self.app.motivo.texto
        texto.focus_force()
        self.janela.update()
        texto.event_generate("<Return>")
        self.janela.withdraw()
        self.assertEqual(len(self.no_banco()), 1)
        self.assertEqual(self.no_banco()[0]["motivo"], "Reunião")

    def test_codigo_e_sql_injection_no_motivo_nao_quebram(self):
        for texto in ("'; DROP TABLE registros; --", '<b>"oi"</b>',
                      "ação ção 😀 ñ", "{chaves} [colchetes] $var"):
            with self.subTest(texto=texto):
                self.app.limpar()
                self.banco.excluir_todos = None
                self.preencher_tudo(motivo=texto, empresa=texto)
                self.app.cadastrar()
                ultimo = self.no_banco()[-1]
                self.assertEqual((ultimo["motivo"], ultimo["empresa"]),
                                 (texto, texto))
                self.app.tabela.selection_set(
                    self.app.tabela.get_children()[0])
                self.app.registrar_saida()

    def test_cpf_no_motivo_vai_mascarado_na_tela_do_porteiro(self):
        """O motivo aparece para todos: não é lugar de CPF inteiro."""
        self.preencher_tudo(motivo="Acompanha 111.444.777-35 e CPF 39053344705")
        self.app.cadastrar()
        motivo = self.no_banco()[0]["motivo"]
        self.assertNotIn("111.444.777-35", motivo)
        self.assertNotIn(CARLA, motivo)


class TestTela3Controle(BaseCadastro):
    """Tela 3: Entry pesquisa, Combobox filtro, Treeview com Código, Nome, CPF,
    Tipo de acesso, Entrada, Saída e Situação; Registrar Entrada, Registrar
    Saída, Atualizar e Voltar; Label."""

    def setUp(self):
        super().setUp()
        self.tela = self.app.tela_cadastro
        self.app.ir_para(self.app.aba_controle)

    def entrar(self, cpf=ANA, nome="Ana Silva", tipo="Visitante", saida="",
               empresa="Alfa Ltda", motivo="Reunião", entrada=None):
        return self.banco.inserir(
            {"nome": nome, "cpf": cpf, "celular": "31987654321", "placa": "",
             "tipo": tipo, "entrada": entrada or agora_menos(30), "saida": saida,
             "empresa": empresa, "motivo": motivo}, autor="ana.admin")

    def linhas(self):
        tab = self.tela.tabela
        return [(tab.item(i)["text"], tab.set(i, "Nome"))
                for i in tab.get_children()]

    def selecionar(self, id_):
        self.tela.atualizar()
        self.tela.tabela.selection_set(str(id_))

    def test_componentes_do_enunciado(self):
        tela = self.tela
        self.assertIsInstance(tela.busca, tk.Entry)
        self.assertIsInstance(tela.filtro, ttk.Combobox)
        self.assertEqual(tela.filtro.get(), "Todos")
        self.assertIsInstance(tela.tabela, ttk.Treeview)
        for botao, texto in ((tela.btn_entrada_controle, "Registrar entrada"),
                             (tela.btn_saida, "Registrar saída"),
                             (tela.btn_atualizar, "Atualizar"),
                             (tela.btn_voltar, "Voltar")):
            self.assertIsInstance(botao, tk.Button)
            self.assertEqual(botao.cget("text"), texto)

    def test_colunas_do_enunciado(self):
        tab = self.tela.tabela
        titulos = [tab.heading("#0", "text")] + [
            tab.heading(c, "text") for c in tab["displaycolumns"]]
        for titulo in ("Código", "Nome", "CPF", "Tipo de acesso", "Entrada",
                       "Saída", "Situação"):
            self.assertIn(titulo, titulos)

    def test_situacao_dentro_ou_saiu(self):
        aberta = self.entrar()
        self.tela.atualizar()
        self.assertEqual(self.tela.tabela.item(str(aberta))["text"], "Dentro")
        self.selecionar(aberta)
        self.tela.btn_saida.invoke()
        self.assertEqual(self.tela.tabela.item(str(aberta))["text"], "Saiu")

    def test_pesquisa_localiza_por_nome_cpf_e_empresa(self):
        self.entrar()
        self.entrar(cpf=BETO, nome="Beto Rocha", empresa="Beta Serviços")
        self.tela.atualizar()
        for texto, esperado in (("beto", "Beto Rocha"), (ANA, "Ana Silva"),
                                ("beta serv", "Beto Rocha")):
            with self.subTest(texto=texto):
                self.buscar(texto)
                self.assertEqual([n for _, n in self.linhas()], [esperado])
        self.buscar("não existe")
        self.assertEqual(self.linhas(), [])

    def test_filtro_todos_dentro_saiu_e_tipos(self):
        self.entrar()
        saiu = self.entrar(cpf=BETO, nome="Beto Rocha", tipo="Professor")
        self.banco.registrar_saidas([saiu], AGORA.strftime(FORMATO), autor="ana.admin")
        self.tela.atualizar()
        self.assertEqual(list(self.tela.filtro.cget("values")), FILTROS)
        casos = {"Todos": {"Ana Silva", "Beto Rocha"}, "Dentro": {"Ana Silva"},
                 "Saiu": {"Beto Rocha"}, "Professor": {"Beto Rocha"},
                 "Visitante": {"Ana Silva"}, "Aluno": set()}
        for filtro, esperado in casos.items():
            with self.subTest(filtro=filtro):
                self.tela.filtro.set(filtro)
                self.tela.filtro.event_generate("<<ComboboxSelected>>")
                self.janela.update()
                self.assertEqual({n for _, n in self.linhas()}, esperado)

    def test_pesquisa_acha_pelo_codigo(self):
        ana = self.entrar()
        self.entrar(cpf=BETO, nome="Beto Rocha")
        self.buscar(f"{ana:03d}")
        self.assertEqual([n for _, n in self.linhas()], ["Ana Silva"])

    def test_filtro_vai_ao_banco_antes_do_limite(self):
        """Uma visita antiga aparece mesmo com muitas visitas mais novas."""
        antiga = self.banco.inserir(dict(VISITA_ANTIGA, placa="", nome="Ana Velha",
                                         cpf=CARLA, tipo="Professor"), autor="ana.admin")
        with mock.patch("portaria.tela_cadastro.LIMITE_BUSCA", 1):
            self.entrar()                   # "ana", mais nova e Visitante
            self.tela.filtro.set("Professor")
            self.buscar("ana")
            self.assertEqual(self.tela.tabela.get_children(), (str(antiga),))
            self.tela.filtro.set("Saiu")
            self.buscar("ana")
            self.assertEqual(self.tela.tabela.get_children(), (str(antiga),))
            self.tela.filtro.set("Dentro")
            self.buscar("ana")
            self.assertEqual([n for _, n in self.linhas()], ["Ana Silva"])

    def test_formulario_e_filtro_sobrevivem_a_troca_de_tema(self):
        self.preencher_tudo()
        self.tela.filtro.set("Saiu")
        self.app.trocar_tema("escuro")
        tela = self.app.tela_cadastro
        self.assertEqual(tela.empresa.get(), "Alfa Ltda")
        self.assertEqual(tela.motivo.get(), "Reunião")
        self.assertEqual(tela.filtro.get(), "Saiu")
        self.assertEqual(self.app.abas.select(), str(self.app.aba_controle))

    def test_filtro_e_pesquisa_juntos(self):
        self.entrar()
        self.entrar(cpf=BETO, nome="Ana Rocha", tipo="Professor")
        self.tela.filtro.set("Professor")
        self.buscar("ana")
        self.assertEqual([n for _, n in self.linhas()], ["Ana Rocha"])

    def test_filtro_mostra_contagem_e_volta_ao_todos_sem_perder_linhas(self):
        self.entrar()
        self.tela.filtro.set("Saiu")
        self.tela.atualizar()
        self.assertIn("0 registros", self.tela.lbl_status.cget("text"))
        self.tela.filtro.set("Todos")
        self.tela.atualizar_tabela()
        self.assertEqual(len(self.linhas()), 1)

    def test_prestador_mostra_empresa_e_motivo(self):
        """Desafio extra: registro de prestadores de serviços."""
        self.entrar(tipo=PRESTADOR, empresa="Clima Frio", motivo="Ar-condicionado")
        self.tela.filtro.set(PRESTADOR)
        self.tela.atualizar()
        tab = self.tela.tabela
        self.assertEqual(tuple(tab["displaycolumns"]), COLUNAS_PRESTADOR)
        linha = tab.get_children()[0]
        self.assertEqual((tab.set(linha, "Empresa"), tab.set(linha, "Motivo")),
                         ("Clima Frio", "Ar-condicionado"))
        self.tela.filtro.set("Todos")
        self.tela.atualizar_tabela()
        self.assertEqual(tuple(tab["displaycolumns"]), COLUNAS_VISIVEIS)

    def test_registrar_entrada_com_horario_automatico(self):
        ontem = (AGORA - timedelta(days=1)).strftime(FORMATO)
        anterior = self.banco.inserir(dict(VISITA_ANTIGA, placa=""), autor="ana.admin")
        self.tela.atualizar()
        self.buscar("beto")
        self.tela.tabela.selection_set(str(anterior))
        self.tela.btn_entrada_controle.invoke()
        del ontem
        visitas = [r for r in self.no_banco() if not r["saida"]]
        self.assertEqual(len(visitas), 1)
        self.assertEqual(visitas[0]["entrada"], AGORA.strftime(FORMATO))
        self.assertEqual(visitas[0]["empresa"], "UNA")
        self.assertEqual(visitas[0]["motivo"], "Aula")

    def test_impede_segunda_entrada_sem_saida(self):
        aberta = self.entrar()
        self.selecionar(aberta)
        self.tela.btn_entrada_controle.invoke()
        self.assertEqual(len(self.no_banco()), 1)
        self.assertIn("sem saída", self.msg.showerror.call_args[0][1].lower())

    def test_registrar_entrada_sem_selecao_avisa(self):
        self.tela.btn_entrada_controle.invoke()
        self.msg.showwarning.assert_called()
        self.assertEqual(self.no_banco(), [])

    def test_registrar_entrada_com_cadastro_antigo_abre_o_cadastro(self):
        antiga = self.banco.inserir(dict(VISITA_ANTIGA, empresa="", motivo="",
                                         placa=""), autor="ana.admin")
        self.tela.atualizar()
        self.buscar("beto")
        self.tela.tabela.selection_set(str(antiga))
        self.tela.btn_entrada_controle.invoke()
        self.assertEqual(self.app.abas.select(), str(self.app.aba_cad))
        self.assertEqual(self.app.cpf.get(), BETO)
        self.assertEqual(len(self.no_banco()), 1)
        self.assertIn("empresa", self.app.lbl_pessoa.cget("text"))

    def test_registrar_saida_com_horario_automatico(self):
        aberta = self.entrar()
        self.selecionar(aberta)
        self.tela.btn_saida.invoke()
        self.assertEqual(self.banco.buscar(aberta)["saida"],
                         AGORA.strftime(FORMATO))

    def test_registrar_saida_sem_selecao_avisa(self):
        self.tela.btn_saida.invoke()
        self.msg.showwarning.assert_called()

    def test_saida_de_quem_ja_saiu_e_recusada(self):
        aberta = self.entrar()
        self.selecionar(aberta)
        self.tela.btn_saida.invoke()
        momento = self.banco.buscar(aberta)["saida"]
        self.tela.tabela.selection_set(str(aberta))
        self.tela.btn_saida.invoke()
        self.assertEqual(self.banco.buscar(aberta)["saida"], momento)

    def test_tabela_atualiza_depois_de_cada_operacao(self):
        self.preencher_tudo()
        self.app.cadastrar()
        self.assertEqual(self.linhas(), [("Dentro", "Ana Silva")])
        self.tela.tabela.selection_set(self.tela.tabela.get_children()[0])
        self.tela.btn_saida.invoke()
        self.assertEqual(self.linhas(), [("Saiu", "Ana Silva")])

    def test_atualizar_le_o_que_a_outra_estacao_gravou(self):
        self.tela.atualizar()
        self.entrar()                       # gravado sem passar pela tela
        self.assertEqual(self.linhas(), [])
        self.tela.btn_atualizar.invoke()
        self.assertEqual(self.linhas(), [("Dentro", "Ana Silva")])

    def test_voltar_vai_ao_cadastro(self):
        self.tela.btn_voltar.invoke()
        self.assertEqual(self.app.abas.select(), str(self.app.aba_cad))

    def test_botoes_seguem_na_lista_de_veiculos(self):
        self.janela.deiconify()
        self.tela.seletor_lista.selecionar("Veículos")
        self.janela.update()
        self.assertTrue(self.tela.btn_saida.winfo_ismapped())
        self.assertTrue(self.tela.btn_voltar.winfo_ismapped())
        self.assertFalse(self.tela.btn_entrada_controle.winfo_ismapped())
        self.tela.seletor_lista.selecionar("Pessoas")
        self.janela.update()
        self.assertTrue(self.tela.btn_entrada_controle.winfo_ismapped())

    def test_enter_no_controle_nao_cadastra(self):
        self.preencher_tudo()
        self.app.ir_para(self.app.aba_controle)
        self.app.cadastrar(event=mock.Mock())
        self.assertEqual(self.no_banco(), [])

    def test_f2_deixa_o_foco_no_comando(self):
        self.janela.deiconify()
        self.app.ir_para(self.app.aba_dash)
        self.janela.update()
        self.app.ir_para_saida_rapida()
        self.janela.focus_force()
        self.app.ir_para_saida_rapida()
        self.janela.update()
        self.assertEqual(self.janela.focus_get(), self.tela.campo_saida_rapida)


class TestControleDoPorteiro(BaseCadastro):
    entrar_como = "porteiro"

    def test_porteiro_tem_o_fluxo_inteiro_com_cpf_mascarado(self):
        self.preencher_tudo()
        self.app.tela_cadastro.btn_cadastrar.invoke()
        tela = self.app.tela_cadastro
        linha = tela.tabela.get_children()[0]
        self.assertIn("*", tela.tabela.set(linha, "CPF"))
        self.assertNotIn(ANA, tela.tabela.set(linha, "CPF"))
        tela.tabela.selection_set(linha)
        tela.btn_saida.invoke()
        self.assertTrue(self.no_banco()[0]["saida"])
        tela.tabela.selection_set(linha)
        tela.btn_entrada_controle.invoke()
        self.assertEqual(len(self.no_banco()), 2)
        self.assertIsNone(tela.btn_excluir)


class TestOcorrencias(BaseInterface):
    """Desafio extra: registro de ocorrências (RN49)."""

    def setUp(self):
        super().setUp()
        self.app.ir_para(self.app.aba_ocorrencias)
        self.aba = self.app.tela_ocorrencias

    def registrar(self, categoria="Veículo", texto="Carro sobre a calçada",
                  cpf="", placa=""):
        d = self.aba.nova()
        d.categoria.set(categoria)
        d.texto.insert(0, texto)
        d.cpf.insert(0, cpf)
        d.placa.insert(0, placa)
        return d, d.salvar()

    def test_registra_e_aparece_no_livro(self):
        _, ok = self.registrar()
        self.assertTrue(ok)
        linha = self.aba.tabela.get_children()[0]
        self.assertEqual(self.aba.tabela.item(linha)["text"], "Aberta")
        self.assertEqual(self.aba.tabela.set(linha, "categoria"), "Veículo")
        self.assertEqual(self.aba.tabela.set(linha, "autor"), "ana.admin")
        self.assertIn("1 ocorrência", self.aba.lbl_total.cget("text"))
        self.assertIn("Ocorrência registrada",
                      [a for _, a in self.acoes()])

    def test_validacao(self):
        casos = (("", "Texto suficiente", "", "", "categoria"),
                 ("Veículo", "abc", "", "", "pelo menos"),
                 ("Veículo", "Texto suficiente", "12345678900", "", "CPF"),
                 ("Veículo", "Texto suficiente", "", "ABC", "Placa"))
        for categoria, texto, cpf, placa, trecho in casos:
            with self.subTest(trecho=trecho):
                d, ok = self.registrar(categoria, texto, cpf, placa)
                self.assertFalse(ok)
                self.assertIn(trecho, d.faixa.lbl.cget("text"))
                d.fechar()
        self.assertEqual(self.banco.listar_ocorrencias(), [])

    def test_categoria_so_da_lista(self):
        d = self.aba.nova()
        self.assertEqual(list(d.categoria.cget("values")), CATEGORIAS_OCORRENCIA)
        self.assertEqual(str(d.categoria.cget("state")), "readonly")
        d.fechar()

    def test_filtros_e_pesquisa(self):
        self.registrar("Veículo", "Carro sobre a calçada")
        self.registrar("Equipamento", "Cancela travada")
        tabela = self.aba.tabela
        self.aba.filtro.set("Equipamento")
        self.aba.atualizar()
        self.assertEqual(len(tabela.get_children()), 1)
        self.aba.filtro.set("Todas as categorias")
        self.aba.busca.insert(0, "calçada")
        self.aba.atualizar()
        self.assertEqual(len(tabela.get_children()), 1)
        self.aba.busca.delete(0, tk.END)
        self.aba.atualizar()
        self.assertEqual(len(tabela.get_children()), 2)

    def test_resolver_e_filtro_so_abertas(self):
        self.registrar()
        tabela = self.aba.tabela
        linha = tabela.get_children()[0]
        tabela.selection_set(linha)
        self.janela.update()
        self.aba.btn_resolver.invocar()
        self.assertEqual(tabela.item(linha)["text"], "Resolvida")
        tabela.selection_set(linha)
        self.janela.update()
        self.assertEqual(self.aba.btn_resolver.cget("state"), "disabled")
        self.assertIn("Resolvida em", self.aba.faixa.lbl.cget("text"))
        self.aba.chk_abertas.invoke()
        self.assertEqual(tabela.get_children(), ())

    def test_resolver_duas_vezes_em_duas_estacoes(self):
        self.registrar()
        id_ = self.banco.listar_ocorrencias()[0]["id"]
        self.aba.tabela.selection_set(str(id_))
        self.banco.resolver_ocorrencia(id_, "ana.admin")    # a outra estação
        self.aba.resolver()
        self.msg.showerror.assert_called()
        self.assertEqual(self.aba.tabela.item(str(id_))["text"], "Resolvida")

    def test_excluir_pede_confirmacao_e_fica_no_historico(self):
        self.registrar()
        linha = self.aba.tabela.get_children()[0]
        self.aba.tabela.selection_set(linha)
        self.msg.askyesno.return_value = False
        self.aba.excluir()
        self.assertEqual(len(self.banco.listar_ocorrencias()), 1)
        self.msg.askyesno.return_value = True
        self.aba.excluir()
        self.assertEqual(self.banco.listar_ocorrencias(), [])
        self.assertIn("Ocorrência excluída", [a for _, a in self.acoes()])

    def test_cpf_digitado_na_descricao_vai_mascarado(self):
        self.registrar(texto="Discussão com o visitante 111.444.777-35 e "
                             "CPF 39053344705 na portaria")
        texto = self.banco.listar_ocorrencias()[0]["texto"]
        self.assertNotIn("111.444.777-35", texto)
        self.assertNotIn(CARLA, texto)

    def test_descricao_com_quebras_e_limite(self):
        d = self.aba.nova()
        d.texto.insert(0, "y" * 900)
        self.assertEqual(len(d.texto.get()), 500)
        d.fechar()

    def test_enter_na_descricao_grava(self):
        self.janela.deiconify()
        d = self.aba.nova()
        d.categoria.set("Veículo")
        d.texto.insert(0, "Texto suficiente")
        d.janela.update()
        d.texto.texto.focus_force()
        d.janela.update()
        d.texto.texto.event_generate("<Return>")
        self.assertEqual(len(self.banco.listar_ocorrencias()), 1)

    def test_tela_reabre_depois_do_tema_e_do_login(self):
        self.registrar()
        self.app.entrar(self.porteiro)
        self.app.ir_para(self.app.aba_ocorrencias)
        self.assertEqual(len(self.app.tela_ocorrencias.tabela.get_children()), 1)
        self.assertIsNone(self.app.tela_ocorrencias.btn_excluir)


class TestOcorrenciasNoBanco(BaseInterface):
    def test_porteiro_nao_exclui_nem_com_a_tela_burlada(self):
        id_ = self.banco.registrar_ocorrencia("Outra", "Texto suficiente", "paulo")
        with self.assertRaises(dados.ErroDados):
            self.banco.excluir_ocorrencia(id_, "paulo")
        self.assertEqual(len(self.banco.listar_ocorrencias()), 1)

    def test_usuario_inexistente_nao_registra(self):
        with self.assertRaises(dados.ErroDados):
            self.banco.registrar_ocorrencia("Outra", "Texto suficiente", "ninguem")

    def test_busca_antes_do_limite_acha_a_antiga(self):
        self.banco.registrar_ocorrencia("Outra", "Agulha no palheiro", "paulo")
        for i in range(5):
            self.banco.registrar_ocorrencia("Outra", f"Texto número {i}", "paulo")
        achadas = self.banco.listar_ocorrencias(texto="agulha", limite=2)
        self.assertEqual(len(achadas), 1)

    def test_sql_injection_na_busca_e_no_texto(self):
        malicioso = "x'); DROP TABLE ocorrencias; --"
        self.banco.registrar_ocorrencia("Outra", malicioso, "paulo")
        self.assertEqual(self.banco.listar_ocorrencias(texto=malicioso)[0]["texto"],
                         malicioso)


class TestLinguagemComEmpresaEMotivo(BaseCadastro):
    def comando(self, linha):
        tela = self.app.tela_cadastro
        tela.campo_saida_rapida.delete(0, tk.END)
        tela.campo_saida_rapida.insert(0, linha)
        tela.saida_rapida()
        return tela.comando

    def test_entrada_nova_com_tudo(self):
        self.comando(f'entrada {ANA} visitante nome "Ana Silva" cel 31987654321 '
                     'empresa "Alfa Ltda" motivo "Reunião"')
        r = self.no_banco()[0]
        self.assertEqual((r["empresa"], r["motivo"]), ("Alfa Ltda", "Reunião"))

    def test_entrada_nova_sem_empresa_e_recusada_como_no_formulario(self):
        self.comando(f'entrada {ANA} visitante nome "Ana Silva" cel 31987654321')
        self.assertEqual(self.no_banco(), [])

    def test_quem_ja_veio_reaproveita_empresa_e_motivo(self):
        self.banco.inserir(dict(VISITA_ANTIGA, placa=""))
        self.comando(f"entrada {BETO}")
        aberta = [r for r in self.no_banco() if not r["saida"]][0]
        self.assertEqual((aberta["empresa"], aberta["motivo"]), ("UNA", "Aula"))

    def test_motivo_novo_troca_o_da_ultima_visita(self):
        self.banco.inserir(dict(VISITA_ANTIGA, placa=""))
        self.comando(f'entrada {BETO} motivo "Banca de TCC"')
        aberta = [r for r in self.no_banco() if not r["saida"]][0]
        self.assertEqual(aberta["motivo"], "Banca de TCC")

    def test_cadastrar_e_editar_empresa(self):
        self.comando(f'cadastrar {CARLA} professor nome "Carla Nogueira" '
                     'cel 31987654321 empresa "UNA"')
        self.assertEqual(self.banco.buscar_pessoa(CARLA)["empresa"], "UNA")
        self.comando(f'editar {CARLA} empresa "Alfa Ltda"')
        self.assertEqual(self.banco.buscar_pessoa(CARLA)["empresa"], "Alfa Ltda")

    def test_empresa_vazia_e_recusada(self):
        self.comando(f'cadastrar {CARLA} professor nome "Carla Nogueira" '
                     'cel 31987654321 empresa ""')
        self.assertIsNone(self.banco.buscar_pessoa(CARLA))

    def test_editar_cadastro_antigo_sem_informar_empresa(self):
        self.banco.cadastrar_pessoa(CARLA, "Carla Nogueira", "31987654321", "",
                                    "Professor", "ana.admin")
        self.comando(f"editar {CARLA} cel 31999990000")
        self.assertEqual(self.banco.buscar_pessoa(CARLA)["celular"], "31999990000")


class TestRequisitosTecnicos(unittest.TestCase):
    """Os requisitos para todos os grupos, no código-fonte do sistema."""

    @classmethod
    def setUpClass(cls):
        raiz = os.path.dirname(portaria.__file__)
        cls.fontes = {}
        for pasta, _, arquivos in os.walk(raiz):
            for nome in arquivos:
                if nome.endswith(".py"):
                    with open(os.path.join(pasta, nome), encoding="utf-8") as f:
                        cls.fontes[nome] = f.read()
        cls.todas = "\n".join(cls.fontes.values())
        cls.arvore = [ast.parse(f) for f in cls.fontes.values()]

    def contar(self, tipo):
        return sum(isinstance(n, tipo) for a in self.arvore for n in ast.walk(a))

    def test_widgets_pedidos(self):
        for trecho in ("tk.Entry(", "tk.Button", "tk.Label(", "ttk.Combobox(",
                       "tk.Checkbutton(", "ttk.Treeview(", "tk.Text(",
                       "tk.PhotoImage("):
            self.assertIn(trecho, self.todas, trecho)

    def test_estruturas_pedidas(self):
        for tipo in (ast.If, ast.For, ast.While, ast.FunctionDef, ast.Try):
            self.assertGreater(self.contar(tipo), 0, tipo.__name__)

    def test_bibliotecas_pedidas(self):
        for trecho in ("import sqlite3", "import tkinter", "from datetime import",
                       "import csv"):
            self.assertIn(trecho, self.todas, trecho)

    def test_so_biblioteca_padrao(self):
        """Tkinter, SQLite3, Datetime e CSV: nada para instalar."""
        permitidos = set(sys.stdlib_module_names) | {"portaria"}
        for arvore in self.arvore:
            for no in ast.walk(arvore):
                if isinstance(no, ast.Import):
                    nomes = [a.name for a in no.names]
                elif isinstance(no, ast.ImportFrom) and not no.level:
                    nomes = [no.module]
                else:
                    continue
                for nome in nomes:
                    self.assertIn(nome.split(".")[0], permitidos)


class TestSemVazamentoDeRecursos(BaseCadastro):
    """Uma portaria fica aberta o dia inteiro: usar as telas não pode ir
    consumindo os objetos gráficos do Windows (o limite é 10 mil por processo
    e, estourado, o Tk derruba o programa)."""

    def objetos_graficos(self):
        k, u = ctypes.windll.kernel32, ctypes.windll.user32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        u.GetGuiResources.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        return u.GetGuiResources(k.GetCurrentProcess(), 0)

    def um_ciclo(self, i):
        tela = self.app.tela_cadastro
        self.app.ir_para(self.app.aba_cad)
        self.preencher_tudo(motivo=f"Ciclo {i}")
        self.app.cadastrar()
        self.app.ir_para(self.app.aba_controle)
        tela.tabela.selection_set(tela.tabela.get_children()[0])
        tela.btn_saida.invoke()
        tela.tabela.selection_set(tela.tabela.get_children()[0])
        tela.editar_selecionado()
        tela.janela_edicao.fechar()
        for aba in (self.app.aba_pessoas, self.app.aba_ocorrencias,
                    self.app.aba_dash, self.app.aba_usuarios,
                    self.app.aba_configuracoes):
            self.app.ir_para(aba)
        self.app.tela_ocorrencias.nova().fechar()
        self.janela.update()

    @unittest.skipUnless(sys.platform == "win32", "contador do Windows")
    def test_usar_as_telas_nao_consome_objetos_graficos(self):
        self.agora = AGORA.replace(hour=8)
        for i in range(3):                  # as imagens e fontes em cache
            self.agora += timedelta(minutes=2)
            self.um_ciclo(i)
        antes = self.objetos_graficos()
        for i in range(25):
            self.agora += timedelta(minutes=2)
            self.um_ciclo(i)
        depois = self.objetos_graficos()
        self.assertLess((depois - antes) / 25, 1,
                        f"{antes} -> {depois} objetos em 25 ciclos")


class TestSituacaoNaLinguagem(BaseCadastro):
    def test_constantes_do_enunciado(self):
        self.assertEqual((horarios.NO_CAMPUS, horarios.SAIU), ("Dentro", "Saiu"))


if __name__ == "__main__":
    unittest.main()
