"""
Versão 2.2 — B3 / RN38: códigos de recuperação do administrador (8 de uso
único, só o hash no banco, "Esqueci a senha" no login, novos códigos
invalidam os antigos, faixa "Só existe 1 administrador ativo").
"""

import os
import sqlite3
import tempfile
import tkinter as tk
import unittest
from datetime import datetime, timedelta

from portaria import dados, senhas, usuarios
from portaria.tela_recuperacao import (JanelaCodigos, apagar_temporarios,
                                       pagina_de_impressao)

from .test_interface import BaseInterface

AGORA = datetime(2026, 10, 21, 10, 0)


class TestCodigosPuros(unittest.TestCase):
    def test_oito_codigos_no_formato_sem_ambiguos(self):
        codigos = senhas.gerar_codigos()
        self.assertEqual(len(codigos), 8)
        self.assertEqual(len(set(codigos)), 8)
        for codigo in codigos:
            self.assertRegex(codigo, r"^[A-Z0-9]{4}-[A-Z0-9]{4}$")
            self.assertFalse(set(codigo) & set("01OIL"))

    def test_normalizar_aceita_minusculas_espacos_e_sem_hifen(self):
        self.assertEqual(senhas.normalizar_codigo(" k7qm-2f9x "), "K7QM2F9X")
        self.assertEqual(senhas.normalizar_codigo("K7QM 2F9X"), "K7QM2F9X")
        for invalido in ("", "K7QM-2F9", "K7QM-2F9XX", "K0QM-2F9X", "K7QM_2F9X"):
            self.assertEqual(senhas.normalizar_codigo(invalido), "")


class BaseCodigos(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = os.path.join(self.pasta.name, "portaria.db")
        self.banco = dados.Banco(self.caminho, relogio=lambda: AGORA)
        self.banco.criar_usuario("Ana Admin", "ana", "admin",
                                 senhas.gerar_hash("senha-da-ana"))
        self.ana = self.banco.buscar_usuario("ana")
        self.codigos = usuarios.gerar_codigos_recuperacao(self.banco, self.ana)

    def tearDown(self):
        self.pasta.cleanup()

    def recuperar(self, codigo, nova="senha-nova-77", login="ana",
                  agora=AGORA):
        return usuarios.recuperar_senha(self.banco, login, codigo, nova, nova,
                                        agora=agora)

    def acoes(self):
        return [(e["usuario"], e["acao"]) for e in self.banco.listar_eventos()]


class TestCodigosNoBanco(BaseCodigos):
    def test_codigo_certo_troca_a_senha_e_nao_funciona_de_novo(self):
        ok, msg = self.recuperar(self.codigos[3].lower())
        self.assertTrue(ok, msg)
        self.assertIsNotNone(usuarios.autenticar(self.banco, "ana",
                                                 "senha-nova-77"))
        self.assertEqual(self.banco.codigos_restantes("ana"), 7)
        ok, _ = self.recuperar(self.codigos[3], nova="outra-senha-88")
        self.assertFalse(ok)
        self.assertIsNone(usuarios.autenticar(self.banco, "ana",
                                              "outra-senha-88"))
        self.assertIn(("ana", dados.CODIGO_RECUPERACAO_USADO), self.acoes())

    def test_codigo_errado_conta_como_tentativa(self):
        ok, msg = self.recuperar("AAAA-BBBB")
        self.assertFalse(ok)
        self.assertIn("incorretos", msg)
        self.assertEqual(self.banco.ler_tentativas_login("ana")[0], 1)
        self.assertIn(("ana", dados.RECUPERACAO_RECUSADA), self.acoes())

    def test_cinco_erros_travam_ate_o_codigo_certo_e_o_login(self):
        for i in range(senhas.LIMITE_TENTATIVAS):
            self.recuperar(f"AAAA-BBB{i + 2}")
        ok, msg = self.recuperar(self.codigos[0])
        self.assertFalse(ok)
        self.assertIn("Aguarde", msg)
        usuario, motivo = usuarios.entrar(self.banco, "ana", "senha-da-ana",
                                          agora=AGORA)
        self.assertIsNone(usuario)                  # mesmo bloqueio do login
        ok, _ = self.recuperar(self.codigos[0], agora=AGORA + timedelta(minutes=1))
        self.assertTrue(ok)

    def test_senha_nova_fraca_nao_gasta_o_codigo(self):
        ok, msg = self.recuperar(self.codigos[0], nova="ana")
        self.assertFalse(ok)
        self.assertEqual(self.banco.codigos_restantes("ana"), 8)
        self.assertEqual(self.banco.ler_tentativas_login("ana")[0], 0)

    def test_gerar_novos_codigos_invalida_os_antigos(self):
        novos, motivo = usuarios.gerar_novos_codigos(self.banco, self.ana,
                                                     "senha-errada")
        self.assertIsNone(novos)
        self.assertIn("não confere", motivo)
        novos, _ = usuarios.gerar_novos_codigos(self.banco, self.ana,
                                                "senha-da-ana")
        self.assertEqual(len(novos), 8)
        self.assertFalse(self.recuperar(self.codigos[0])[0])
        self.assertTrue(self.recuperar(novos[0])[0])

    def test_so_o_hash_vai_para_o_banco_e_o_codigo_nao_vai_ao_historico(self):
        self.recuperar(self.codigos[1])
        self.recuperar("AAAA-BBBB")
        con = sqlite3.connect(self.caminho)
        tudo = " ".join(str(c) for tabela in ("codigos_recuperacao",
                                              "auditoria", "usuarios")
                        for linha in con.execute(f"SELECT * FROM {tabela}")
                        for c in linha)
        con.close()
        for codigo in self.codigos:
            self.assertNotIn(codigo, tudo)
            self.assertNotIn(codigo.replace("-", ""), tudo)
        self.assertNotIn("AAAA", tudo)

    def test_so_o_proprio_administrador_gera_os_dele(self):
        self.banco.criar_usuario("Bia Admin", "bia", "admin", "h",
                                 autor="ana", trocar_senha=False)
        self.banco.criar_usuario("Paulo Porteiro", "paulo", "porteiro", "h",
                                 autor="ana", trocar_senha=False)
        for autor in ("bia", "paulo"):
            with self.assertRaises(dados.ErroDados):
                self.banco.salvar_codigos_recuperacao(self.ana["id"], ["x"],
                                                      autor=autor)
        self.assertTrue(self.recuperar(self.codigos[0])[0])

    def test_login_inexistente_e_porteiro_sem_codigo(self):
        ok, msg = self.recuperar(self.codigos[0], login="ninguem")
        self.assertFalse(ok)
        self.assertEqual(self.banco.ler_tentativas_login(
            usuarios.CHAVE_LOGIN_INEXISTENTE)[0], 1)

    def test_um_administrador_ativo_pede_um_segundo(self):
        self.assertTrue(usuarios.precisa_de_outro_admin(
            self.banco.listar_usuarios()))
        self.banco.criar_usuario("Bia Admin", "bia", "admin", "h",
                                 autor="ana", trocar_senha=False)
        self.assertFalse(usuarios.precisa_de_outro_admin(
            self.banco.listar_usuarios()))

    def test_pagina_de_impressao_tem_os_codigos(self):
        pagina = pagina_de_impressao(self.codigos, "ana", AGORA)
        for codigo in self.codigos:
            self.assertIn(codigo, pagina)
        self.assertIn("window.print()", pagina)


class TestCodigosNoPrimeiroAcesso(BaseInterface):
    entrar_como = None
    com_usuarios = False

    def criar_admin(self):
        tela = self.app.tela_login
        tela.campo_nome.insert(0, "Carla Dias")
        tela.campo_login.insert(0, "carla")
        tela.campo_senha.insert(0, "segredo1")
        tela.campo_confirmacao.insert(0, "segredo1")
        tela.criar_administrador()

    def test_mostra_os_oito_codigos_uma_vez_e_entra(self):
        self.criar_admin()
        self.assertEqual(len(self.codigos_mostrados), 1)
        self.assertEqual(len(self.codigos_mostrados[0]), 8)
        self.assertEqual(self.app.usuario["login"], "carla")
        self.assertEqual(self.banco.codigos_restantes("carla"), 8)

    def test_continuar_so_com_guardei_e_imprimir_abre_o_navegador(self):
        vistos = []

        def responder(janela):
            janela.continuar()                         # sem marcar
            vistos.append((janela.confirmado, janela.faixa.lbl.cget("text"),
                           janela.btn_continuar.ativo))
            janela.imprimir()
            janela.alternador.alternar()
            janela.continuar()
            vistos.append(janela.confirmado)
        self.responder_codigos = responder
        self.criar_admin()
        confirmado, texto, ativo = vistos[0]
        self.assertFalse(confirmado)
        self.assertFalse(ativo)
        self.assertIn("Guardei", texto)
        self.assertTrue(vistos[1])
        self.navegador.open.assert_called_once()
        caminho = self.navegador.open.call_args[0][0][len("file:///"):]
        self.assertTrue(os.path.exists(caminho))
        apagar_temporarios()
        self.assertFalse(os.path.exists(caminho))


class TestEsqueciASenhaNaTela(BaseInterface):
    entrar_como = None

    def setUp(self):
        super().setUp()
        self.codigos = usuarios.gerar_codigos_recuperacao(
            self.banco, self.banco.buscar_usuario("ana.admin"))

    def preencher(self, codigo, nova="senha-nova-77"):
        tela = self.app.tela_login
        tela.campo_login.insert(0, "ana.admin")
        tela.mostrar_esqueci()
        self.assertEqual(tela.campo_login.get(), "ana.admin")   # veio junto
        tela.campo_codigo.insert(0, codigo)
        tela.campo_nova.insert(0, nova)
        tela.campo_confirmacao.insert(0, nova)
        tela.recuperar()
        return tela

    def test_codigo_certo_volta_ao_login_com_a_senha_nova(self):
        tela = self.preencher(self.codigos[0])
        self.assertEqual(tela.formulario, "entrar")
        self.assertIn("Senha redefinida", tela.lbl_erro.cget("text"))
        tela.campo_senha.insert(0, "senha-nova-77")
        tela.entrar()
        self.assertEqual(self.app.usuario["login"], "ana.admin")

    def test_codigo_errado_mostra_o_erro_e_fica(self):
        tela = self.preencher("ABCD-EFGH")
        self.assertEqual(tela.formulario, "esqueci")
        self.assertIn("incorretos", tela.lbl_erro.cget("text"))
        self.assertEqual(tela.campo_codigo.get(), "")

    def test_campo_do_codigo_para_em_9(self):
        tela = self.app.tela_login
        tela.mostrar_esqueci()
        for letra in "K7QM-2F9XAAAA":
            tela.campo_codigo.insert(tk.END, letra)
        self.assertEqual(tela.campo_codigo.get(), "K7QM-2F9X")


class TestCodigosNoMenuEPainel(BaseInterface):
    def test_menu_gera_novos_codigos_com_a_senha_atual(self):
        antigos = usuarios.gerar_codigos_recuperacao(
            self.banco, self.banco.buscar_usuario("ana.admin"))
        janela = self.app.gerar_novos_codigos()
        janela.senha.insert(0, "errada")
        janela.gerar()
        self.assertIn("não confere", janela.faixa.lbl.cget("text"))
        janela.senha.insert(0, "senha123")
        janela.gerar()
        self.assertEqual(len(self.codigos_mostrados), 1)
        self.assertNotEqual(self.codigos_mostrados[0], antigos)
        ok, _ = usuarios.recuperar_senha(self.banco, "ana.admin", antigos[0],
                                         "senha-nova-77", "senha-nova-77",
                                         agora=self.agora)
        self.assertFalse(ok)

    def test_painel_avisa_quando_so_existe_um_administrador(self):
        painel = self.app.tela_dashboard
        self.assertTrue(painel.faixa_admin.winfo_manager())
        self.assertIn("Crie um segundo", painel.faixa_admin.lbl.cget("text"))
        self.banco.criar_usuario("Bia Admin", "bia", "admin", "h",
                                 autor="ana.admin")
        painel.atualizar()
        self.assertFalse(painel.faixa_admin.winfo_manager())


class TestCodigosParaOPorteiro(BaseInterface):
    entrar_como = "porteiro"

    def test_porteiro_nao_ve_o_item_nem_a_faixa(self):
        menu = self.app.menu_usuario
        rotulos = [menu.entrycget(i, "label")
                   for i in range(menu.index("end") + 1)
                   if menu.type(i) != "separator"]
        self.assertNotIn("Gerar novos códigos de recuperação", rotulos)
        self.assertIsNone(self.app.gerar_novos_codigos())
        self.assertFalse(self.app.tela_dashboard.faixa_admin.winfo_manager())


if __name__ == "__main__":
    unittest.main()
