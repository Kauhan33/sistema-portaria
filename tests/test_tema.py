"""Modo noturno: paletas e contraste, preferência de cada usuário no banco
e a troca de tema com o programa aberto (janela oculta)."""

import os
import sqlite3
import sys
import tempfile
import tkinter as tk
import unittest
from unittest import mock

from portaria import componentes, dados, estilo
from portaria.estilo import COR, ESTADO
from portaria.usuarios import TEMA_PADRAO, TEMAS, entrar, gerar_hash

from .test_dados import rebaixar_para_v8, versao_do_arquivo
from .test_interface import BaseInterface


def windows_no(tema):
    """Simula o Windows no tema claro ou escuro (a leitura do registro)."""
    return mock.patch("portaria.estilo.windows_usa_tema_escuro",
                      return_value=tema == "escuro")


class TestPaletas(unittest.TestCase):
    def tearDown(self):
        estilo.usar_tema("claro")

    def test_os_dois_temas_tem_os_mesmos_tokens(self):
        claro, escuro = estilo.PALETAS["claro"], estilo.PALETAS["escuro"]
        self.assertEqual(claro.keys(), escuro.keys())
        self.assertEqual(estilo.ESTADOS["claro"].keys(),
                         estilo.ESTADOS["escuro"].keys())
        self.assertEqual(estilo.TIPOS_POR_TEMA["claro"].keys(),
                         estilo.TIPOS_POR_TEMA["escuro"].keys())

    def test_preferencias_do_menu_sao_as_do_banco(self):
        self.assertEqual(tuple(estilo.PREFERENCIAS_TEMA), TEMAS)
        self.assertEqual(estilo.PREFERENCIA_PADRAO, TEMA_PADRAO)

    def test_contraste_wcag_aa_em_todos_os_pares_dos_dois_temas(self):
        for tema in ("claro", "escuro"):
            estilo.usar_tema(tema)
            for descricao, frente, fundo, minimo in estilo.pares_de_contraste():
                with self.subTest(tema=tema, par=descricao):
                    self.assertGreaterEqual(
                        estilo.contraste(frente, fundo), minimo,
                        f"{frente} sobre {fundo}")

    def test_formula_do_contraste(self):
        self.assertAlmostEqual(estilo.contraste("#000000", "#FFFFFF"), 21)
        self.assertAlmostEqual(estilo.contraste("#777777", "#777777"), 1)
        self.assertAlmostEqual(estilo.contraste("#767676", "#FFFFFF"), 4.54,
                               places=2)

    def test_usar_tema_troca_o_conteudo_dos_mesmos_dicionarios(self):
        cor, estado = COR, ESTADO
        self.assertTrue(estilo.usar_tema("escuro"))
        self.assertIs(estilo.COR, cor)
        self.assertIs(estilo.ESTADO, estado)
        self.assertEqual(COR["fundo"], estilo.PALETAS["escuro"]["fundo"])
        self.assertEqual(ESTADO["erro"], estilo.ESTADOS["escuro"]["erro"])
        self.assertFalse(estilo.usar_tema("escuro"))     # já estava

    def test_placa_continua_branca_no_escuro(self):
        estilo.usar_tema("escuro")
        self.assertEqual(COR["placa_fundo"], "#FFFFFF")
        self.assertLess(estilo.luminancia(COR["fundo"]), 0.05)

    def test_seguir_o_windows(self):
        for windows, esperado in (("claro", "claro"), ("escuro", "escuro")):
            with windows_no(windows):
                self.assertEqual(estilo.resolver_tema("sistema"), esperado)
                self.assertEqual(estilo.resolver_tema("claro"), "claro")
                self.assertEqual(estilo.resolver_tema("escuro"), "escuro")

    def test_leitura_do_registro_do_windows(self):
        def winreg_com(valor=None, erro=None):
            falso = mock.MagicMock()
            if erro:
                falso.OpenKey.side_effect = erro
            falso.QueryValueEx.return_value = (valor, 4)
            return mock.patch.dict(sys.modules, {"winreg": falso})

        with winreg_com(0):
            self.assertTrue(estilo.windows_usa_tema_escuro())
        with winreg_com(1):
            self.assertFalse(estilo.windows_usa_tema_escuro())
        with winreg_com(erro=OSError("sem a chave")):
            self.assertFalse(estilo.windows_usa_tema_escuro())


class TestImagensPorTema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.raiz = tk.Tk()
        except tk.TclError:
            raise unittest.SkipTest("sem tela disponível para o Tkinter")
        cls.raiz.withdraw()

    @classmethod
    def tearDownClass(cls):
        estilo.usar_tema("claro")
        cls.raiz.destroy()

    def test_cada_tema_tem_o_seu_cache_de_imagens(self):
        estilo.usar_tema("claro")
        claro = componentes.cantos(self.raiz, 6, COR["superficie"], COR["fundo"])
        estilo.usar_tema("escuro")
        escuro = componentes.cantos(self.raiz, 6, COR["superficie"], COR["fundo"])
        self.assertIsNot(claro["nw"], escuro["nw"])
        self.assertEqual(set(self.raiz.imagens_guarita), {"claro", "escuro"})
        estilo.usar_tema("claro")         # volta: reaproveita as do claro
        self.assertIs(componentes.cantos(self.raiz, 6, COR["superficie"],
                                         COR["fundo"])["nw"], claro["nw"])


class TestTemaNoBanco(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = os.path.join(self.pasta.name, "portaria.db")
        self.banco = dados.Banco(self.caminho)
        self.banco.criar_usuario("Ana Admin", "ana", "admin", gerar_hash("senha123"))
        self.banco.criar_usuario("Paulo", "paulo", "porteiro",
                                 gerar_hash("senha456"), autor="ana",
                                 trocar_senha=False)

    def tearDown(self):
        self.pasta.cleanup()

    def test_usuario_novo_segue_o_windows(self):
        self.assertEqual(self.banco.buscar_usuario("paulo")["tema"], "sistema")

    def test_cada_usuario_guarda_o_seu_tema(self):
        self.banco.definir_tema("escuro", autor="ana")
        self.banco.definir_tema("claro", autor="paulo")
        self.assertEqual(self.banco.buscar_usuario("ana")["tema"], "escuro")
        self.assertEqual(self.banco.buscar_usuario("paulo")["tema"], "claro")

    def test_login_devolve_o_tema_do_usuario(self):
        self.banco.definir_tema("escuro", autor="paulo")
        usuario, _ = entrar(self.banco, "paulo", "senha456")
        self.assertEqual(usuario["tema"], "escuro")

    def test_tema_desconhecido_ou_sem_sessao_e_recusado(self):
        with self.assertRaises(dados.ErroDados):
            self.banco.definir_tema("rosa", autor="ana")
        with self.assertRaises(dados.ErroDados):
            self.banco.definir_tema("escuro", autor=None)

    def test_tema_nao_vai_para_o_historico(self):
        antes = len(self.banco.listar_eventos())
        self.banco.definir_tema("escuro", autor="ana")
        self.assertEqual(len(self.banco.listar_eventos()), antes)

    def test_migracao_da_v8_poe_os_usuarios_antigos_no_claro(self):
        rebaixar_para_v8(self.caminho)
        banco = dados.Banco(self.caminho)
        self.assertEqual(versao_do_arquivo(self.caminho), dados.VERSAO_ESQUEMA)
        self.assertEqual(banco.buscar_usuario("ana")["tema"], "claro")
        backups = os.listdir(os.path.join(self.pasta.name, "backups"))
        self.assertIn(f"antes-v{dados.VERSAO_ESQUEMA}-de-v8", backups[0])
        # quem for criado depois da migração começa seguindo o Windows
        banco.criar_usuario("Carla", "carla", "porteiro", gerar_hash("senha789"),
                            autor="ana", trocar_senha=False)
        self.assertEqual(banco.buscar_usuario("carla")["tema"], "sistema")

    def test_migracao_que_falha_nao_deixa_a_coluna_pela_metade(self):
        rebaixar_para_v8(self.caminho)

        def passo_que_falha(banco, con, versao):
            dados._passo_v9(banco, con, versao)
            raise sqlite3.OperationalError("falha simulada")

        migracoes = [(alvo, passo_que_falha if alvo == 9 else passo)
                     for alvo, passo in dados.MIGRACOES]
        with mock.patch.object(dados, "MIGRACOES", migracoes):
            with self.assertRaises(dados.ErroDados):
                dados.Banco(self.caminho)
        self.assertEqual(versao_do_arquivo(self.caminho), 8)
        con = sqlite3.connect(self.caminho)
        colunas = {c[1] for c in con.execute("PRAGMA table_info(usuarios)")}
        con.close()
        self.assertNotIn("tema", colunas)


class BaseTema(BaseInterface):
    def fundos(self, widget):
        """Cores de fundo de todos os Frame/Label dentro de `widget`."""
        cores = set()
        for filho in widget.winfo_children():
            if isinstance(filho, (tk.Frame, tk.Label)) and not isinstance(
                    filho, tk.Toplevel):
                cores.add(str(filho.cget("bg")).upper())
            cores |= self.fundos(filho)
        return cores

    def assert_sem_fundo_claro(self, widget):
        """Nenhum Frame/Label com fundo claro esquecido (o "buraco" branco
        no tema escuro). A placa é um Canvas: fica de fora."""
        claros = {c for c in self.fundos(widget)
                  if c.startswith("#") and estilo.luminancia(c) > 0.3}
        self.assertEqual(claros, set())


class TestTrocaDeTemaSemFechar(BaseTema):
    def test_trocar_mantem_sessao_pagina_e_formulario(self):
        self.app.ir_para(self.app.aba_pessoas)
        self.app.tela_cadastro.var_cpf.set("5299822")
        self.app.nome.insert(0, "Ana Silva")
        self.app.tipo.set("Visitante")
        self.app.entrada.delete(0, tk.END)
        self.app.entrada.insert(0, "21/10/2026 09:30")
        usuario = self.app.usuario

        self.assertTrue(self.app.trocar_tema("escuro"))

        self.assertEqual(estilo.TEMA["atual"], "escuro")
        self.assertIs(self.app.usuario, usuario)
        self.assertEqual(self.app.abas.select(), str(self.app.aba_pessoas))
        self.assertTrue(self.app.itens_menu[str(self.app.aba_pessoas)].ativo)
        self.assertEqual(self.app.tela_cadastro.var_cpf.get(), "5299822")
        self.assertEqual(self.app.nome.get(), "Ana Silva")
        self.assertEqual(self.app.tipo.get(), "Visitante")
        self.assertEqual(self.app.entrada.get(), "21/10/2026 09:30")
        self.assertEqual(self.app.corpo.cget("bg"), COR["fundo"])
        self.assertEqual(self.app.lateral.cget("bg"), COR["lateral"])
        self.assertEqual(self.app.var_tema.get(), "escuro")

    def test_escolha_fica_gravada_e_vale_no_proximo_login(self):
        self.app.trocar_tema("escuro")
        self.assertEqual(self.banco.buscar_usuario("ana.admin")["tema"], "escuro")
        self.app.sair()
        self.assertEqual(estilo.TEMA["atual"], "claro")   # login: Windows claro
        tela = self.app.tela_login
        tela.campo_login.insert(0, "ana.admin")
        tela.campo_senha.insert(0, "senha123")
        tela.entrar()
        self.assertEqual(estilo.TEMA["atual"], "escuro")
        self.assertEqual(self.app.lateral.cget("bg"), COR["lateral"])

    def test_todas_as_paginas_montam_no_escuro_sem_fundo_claro(self):
        self.app.trocar_tema("escuro")
        self.cadastrar_um()
        for pagina in ("aba_cad", "aba_pessoas", "aba_dash",
                       "aba_usuarios", "aba_configuracoes"):
            with self.subTest(pagina=pagina):
                self.app.ir_para(getattr(self.app, pagina))
                self.app.janela.update_idletasks()
                self.assert_sem_fundo_claro(getattr(self.app, pagina))
        self.assert_sem_fundo_claro(self.app.lateral)

    def test_dialogos_abertos_depois_da_troca_ficam_escuros(self):
        self.app.trocar_tema("escuro")
        self.cadastrar_um()
        self.app.tabela.selection_set(self.app.tabela.get_children()[0])
        self.app.editar_selecionado()
        corrigir = self.app.tela_cadastro.janela_edicao.janela
        self.assertEqual(corrigir.cget("bg"), COR["superficie"])
        self.assert_sem_fundo_claro(corrigir)
        senha = self.app.trocar_senha().janela
        self.assertEqual(senha.cget("bg"), COR["superficie"])
        self.assert_sem_fundo_claro(senha)

    def test_dialogo_aberto_fecha_na_troca(self):
        senha = self.app.trocar_senha().janela
        self.app.trocar_tema("escuro")
        self.assertFalse(senha.winfo_exists())

    def test_mesmo_tema_nao_remonta(self):
        tela = self.app.tela_cadastro
        self.app.trocar_tema("claro")          # o Windows (simulado) é claro
        self.assertIs(self.app.tela_cadastro, tela)
        self.assertEqual(self.banco.buscar_usuario("ana.admin")["tema"], "claro")

    def test_seguir_o_windows_escuro(self):
        with windows_no("escuro"):
            self.app.trocar_tema("sistema")
        self.assertEqual(estilo.TEMA["atual"], "escuro")

    def test_voltar_ao_claro(self):
        self.app.trocar_tema("escuro")
        self.app.trocar_tema("claro")
        self.assertEqual(estilo.TEMA["atual"], "claro")
        self.assertEqual(self.app.corpo.cget("bg"), estilo.PALETAS["claro"]["fundo"])

    def test_menu_da_conta_tem_o_tema(self):
        menu = self.app.menu_usuario
        rotulos = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)
                   if menu.type(i) != "separator"]
        self.assertEqual(rotulos, ["Trocar minha senha",
                                   "Gerar novos códigos de recuperação",
                                   "Tema: Claro",
                                   "Tema: Escuro", "Tema: Seguir o Windows",
                                   "Sair"])
        escuro = next(i for i in range(menu.index("end") + 1)
                      if menu.type(i) == "radiobutton"
                      and menu.entrycget(i, "value") == "escuro")
        menu.invoke(escuro)
        self.assertEqual(estilo.TEMA["atual"], "escuro")
        self.assertEqual(self.app.var_tema.get(), "escuro")


class TestTemaPorUsuario(BaseTema):
    entrar_como = None

    def entrar_como_usuario(self, login, senha):
        tela = self.app.tela_login
        tela.campo_login.insert(0, login)
        tela.campo_senha.insert(0, senha)
        tela.entrar()

    def test_usuarios_diferentes_com_temas_diferentes(self):
        self.banco.definir_tema("escuro", autor="ana.admin")
        self.banco.definir_tema("claro", autor="paulo")
        self.entrar_como_usuario("ana.admin", "senha123")
        self.assertEqual(estilo.TEMA["atual"], "escuro")
        self.app.sair()
        self.entrar_como_usuario("paulo", "senha456")
        self.assertEqual(estilo.TEMA["atual"], "claro")

    def test_login_segue_o_windows(self):
        self.banco.definir_tema("escuro", autor="ana.admin")
        with windows_no("escuro"):
            self.app.mostrar_login()
        self.assertEqual(estilo.TEMA["atual"], "escuro")
        self.assert_sem_fundo_claro(self.app.corpo)
        with windows_no("claro"):
            self.app.mostrar_login()
        self.assertEqual(estilo.TEMA["atual"], "claro")


if __name__ == "__main__":
    unittest.main()
