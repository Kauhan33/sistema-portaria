"""
Versão 2.2 — S07 / RN39: troca de senha obrigatória no primeiro login
depois de o administrador criar o usuário ou redefinir a senha dele, e
senha nunca igual ao login (também na redefinição pelo administrador).
"""

import os
import tempfile
import tkinter as tk
import unittest

from portaria import dados, usuarios
from portaria.senhas import gerar_hash

from .test_dados import registro
from .test_interface import BaseInterface


class TestTrocaDeSenhaNoBanco(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.banco = dados.Banco(os.path.join(self.pasta.name, "portaria.db"))
        self.banco.criar_usuario("Ana Admin", "ana", "admin",
                                 gerar_hash("senha-da-ana"))
        self.id_paulo = self.banco.criar_usuario(
            "Paulo Porteiro", "paulo", "porteiro", gerar_hash("provisoria1"),
            autor="ana")

    def tearDown(self):
        self.pasta.cleanup()

    def test_primeiro_acesso_nao_precisa_trocar_e_criado_precisa(self):
        self.assertFalse(self.banco.buscar_usuario("ana")["trocar_senha"])
        self.assertTrue(self.banco.buscar_usuario("paulo")["trocar_senha"])

    def test_com_a_troca_pendente_o_banco_recusa_qualquer_operacao(self):
        with self.assertRaises(dados.ErroDados) as erro:
            self.banco.inserir(registro(), autor="paulo")
        self.assertIn("Defina a sua senha", str(erro.exception))
        self.assertEqual(self.banco.listar(), [])

    def test_trocar_a_propria_tira_a_pendencia(self):
        ok, msg = usuarios.definir_senha_inicial(self.banco, "paulo",
                                                 "minha-senha-9",
                                                 "minha-senha-9")
        self.assertTrue(ok, msg)
        self.assertFalse(self.banco.buscar_usuario("paulo")["trocar_senha"])
        self.banco.inserir(registro(), autor="paulo")
        self.assertIn(("paulo", "Senha alterada"),
                      [(e["usuario"], e["acao"])
                       for e in self.banco.listar_eventos()])

    def test_redefinida_pelo_administrador_volta_a_pedir(self):
        usuarios.definir_senha_inicial(self.banco, "paulo", "minha-senha-9",
                                       "minha-senha-9")
        self.banco.definir_senha(self.id_paulo, gerar_hash("provisoria2"),
                                 autor="ana")
        self.assertTrue(self.banco.buscar_usuario("paulo")["trocar_senha"])

    def test_nova_senha_nao_pode_ser_a_provisoria_nem_o_login(self):
        for nova, trecho in (("provisoria1", "diferente"),
                             ("paulo", "pelo menos"),
                             ("senha123", "fácil")):
            ok, msg = usuarios.definir_senha_inicial(self.banco, "paulo",
                                                     nova, nova)
            self.assertFalse(ok)
            self.assertIn(trecho, msg)
        self.assertTrue(self.banco.buscar_usuario("paulo")["trocar_senha"])
        ok, _ = usuarios.validar_senha("paulo.porteiro", "paulo.porteiro",
                                       "paulo.porteiro")
        self.assertFalse(ok)                          # igual ao login

    def test_administrador_com_troca_pendente_nao_redefine_outros(self):
        id_bia = self.banco.criar_usuario("Bia Admin", "bia", "admin",
                                          gerar_hash("provisoria3"),
                                          autor="ana")
        with self.assertRaises(dados.ErroDados):
            self.banco.definir_senha(self.id_paulo, gerar_hash("x"),
                                     autor="bia")
        self.banco.definir_senha(id_bia, gerar_hash("a-da-bia-1"), autor="bia")
        self.assertFalse(self.banco.buscar_usuario("bia")["trocar_senha"])

    def test_login_avisa_que_precisa_trocar(self):
        usuario, _ = usuarios.entrar(self.banco, "paulo", "provisoria1")
        self.assertTrue(usuarios.precisa_trocar_senha(usuario))
        usuario, _ = usuarios.entrar(self.banco, "ana", "senha-da-ana")
        self.assertFalse(usuarios.precisa_trocar_senha(usuario))


class TestDefinaSuaSenhaNaTela(BaseInterface):
    entrar_como = None

    def setUp(self):
        super().setUp()
        self.novo = self.banco.criar_usuario(
            "Bruno Almeida", "bruno.almeida", "porteiro", gerar_hash("provisoria1"),
            autor="ana.admin")

    def entrar(self, login, senha):
        tela = self.app.tela_login
        tela.campo_login.insert(0, login)
        tela.campo_senha.insert(0, senha)
        tela.entrar()

    def test_usuario_criado_entra_direto_na_troca_de_senha(self):
        self.entrar("bruno.almeida", "provisoria1")
        tela = self.app.tela_login
        self.assertEqual(tela.formulario, "definir_senha")
        self.assertIsNone(self.app.usuario)            # nenhuma outra tela
        tela.campo_nova.insert(0, "minha-senha-9")
        tela.campo_confirmacao.insert(0, "minha-senha-9")
        tela.definir_senha()
        self.assertEqual(self.app.usuario["login"], "bruno.almeida")
        self.assertIsNotNone(usuarios.autenticar(self.banco, "bruno.almeida",
                                                 "minha-senha-9"))

    def test_senha_igual_ao_login_e_recusada_na_troca(self):
        self.entrar("bruno.almeida", "provisoria1")
        tela = self.app.tela_login
        tela.campo_nova.insert(0, "Bruno.Almeida")
        tela.campo_confirmacao.insert(0, "Bruno.Almeida")
        tela.definir_senha()
        self.assertIn("fácil de adivinhar", tela.lbl_erro.cget("text"))
        tela.campo_nova.insert(0, "provisoria1")
        tela.campo_confirmacao.insert(0, "provisoria1")
        tela.definir_senha()
        self.assertIn("diferente", tela.lbl_erro.cget("text"))
        self.assertIsNone(self.app.usuario)

    def test_quem_ja_definiu_entra_direto(self):
        self.entrar("paulo", "senha456")
        self.assertEqual(self.app.usuario["login"], "paulo")


class TestRedefinirSenhaIgualAoLogin(BaseInterface):
    def test_redefinicao_recusa_senha_igual_ao_login(self):
        aba = self.app.tela_usuarios
        self.banco.criar_usuario("Carla Nogueira", "carla.nog", "porteiro",
                                 gerar_hash("provisoria1"), autor="ana.admin")
        aba.atualizar()
        id_carla = self.banco.buscar_usuario("carla.nog")["id"]
        aba.tabela.selection_set(str(id_carla))
        dialogo = aba.redefinir_senha()
        dialogo.senha.insert(0, "Carla.Nog")          # o login, em maiúsculas
        dialogo.confirmacao.insert(0, "Carla.Nog")
        dialogo.salvar()
        self.assertIn("fácil de adivinhar", dialogo.faixa.lbl.cget("text"))
        self.assertIsNone(usuarios.autenticar(self.banco, "carla.nog",
                                              "Carla.Nog"))
        dialogo.fechar()

    def test_redefinida_pede_troca_no_proximo_login(self):
        aba = self.app.tela_usuarios
        aba.tabela.selection_set(str(self.porteiro["id"]))
        dialogo = aba.redefinir_senha()
        dialogo.senha.insert(0, "provisoria9")
        dialogo.confirmacao.insert(0, "provisoria9")
        dialogo.salvar()
        self.assertTrue(self.banco.buscar_usuario("paulo")["trocar_senha"])


if __name__ == "__main__":
    unittest.main()
