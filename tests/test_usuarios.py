import os
import tempfile
import unittest

from portaria import dados
from portaria.usuarios import (LIMITE_TENTATIVAS, SEGUNDOS_BLOQUEIO,
                               ControleTentativas, autenticar, conferir_senha,
                               gerar_hash, pode_desativar, pode_excluir,
                               validar_novo_usuario, validar_senha)

ADMIN = {"id": 1, "login": "ana", "perfil": "admin", "ativo": True}
ADMIN_2 = {"id": 2, "login": "bia", "perfil": "admin", "ativo": True}
PORTEIRO = {"id": 3, "login": "paulo", "perfil": "porteiro", "ativo": True}


class TestSenha(unittest.TestCase):
    def test_hash_confere_so_com_a_senha_certa(self):
        guardado = gerar_hash("segredo1")
        self.assertTrue(conferir_senha("segredo1", guardado))
        self.assertFalse(conferir_senha("segredo2", guardado))
        self.assertFalse(conferir_senha("", guardado))

    def test_senha_nao_aparece_no_que_e_guardado(self):  # RNF02
        guardado = gerar_hash("segredo1")
        self.assertNotIn("segredo1", guardado)
        self.assertTrue(guardado.startswith("pbkdf2_sha256$"))

    def test_mesma_senha_gera_hash_diferente_por_causa_do_sal(self):
        self.assertNotEqual(gerar_hash("segredo1"), gerar_hash("segredo1"))

    def test_valor_guardado_estragado_nunca_confere(self):
        for guardado in ["", "texto qualquer", "md5$1$aa$bb", None]:
            with self.subTest(guardado=guardado):
                self.assertFalse(conferir_senha("segredo1", guardado))

    def test_validar_senha(self):
        self.assertEqual(validar_senha("segredo1", "segredo1"), (True, ""))
        self.assertIn("pelo menos", validar_senha("abc", "abc")[1])
        self.assertIn("confirmação", validar_senha("segredo1", "segredo2")[1])


class TestNovoUsuario(unittest.TestCase):
    def validar(self, **mudancas):
        campos = dict(nome="Maria Souza", login="maria.souza", senha="segredo1",
                      confirmacao="segredo1", perfil="porteiro",
                      logins_existentes={"ana"})
        campos.update(mudancas)
        return validar_novo_usuario(**campos)

    def test_usuario_valido(self):
        self.assertEqual(self.validar(), (True, ""))

    def test_recusas(self):
        casos = {
            "nome sem sobrenome": (dict(nome="Maria"), "nome completo"),
            "nome com número": (dict(nome="Maria 2"), "nome completo"),
            "login curto": (dict(login="ma"), "Usuário inválido"),
            "login com espaço": (dict(login="maria souza"), "Usuário inválido"),
            "login repetido": (dict(login="ana"), "Já existe"),
            "perfil inexistente": (dict(perfil="chefe"), "perfil"),
            "senha curta": (dict(senha="123", confirmacao="123"), "pelo menos"),
        }
        for caso, (mudanca, trecho) in casos.items():
            with self.subTest(caso):
                ok, msg = self.validar(**mudanca)
                self.assertFalse(ok)
                self.assertIn(trecho, msg)


class TestAutenticar(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.banco = dados.Banco(os.path.join(self.pasta.name, "portaria.db"))
        self.id = self.banco.criar_usuario("Ana Admin", "ana", "admin",
                                           gerar_hash("segredo1"))

    def tearDown(self):
        self.pasta.cleanup()

    def test_login_certo_devolve_usuario_sem_a_senha(self):
        self.assertEqual(autenticar(self.banco, "ana", "segredo1"),
                         {"id": self.id, "login": "ana", "nome": "Ana Admin",
                          "perfil": "admin"})

    def test_login_ignora_maiusculas_e_espacos(self):
        self.assertIsNotNone(autenticar(self.banco, "  ANA ", "segredo1"))

    def test_senha_errada_ou_usuario_inexistente(self):
        self.assertIsNone(autenticar(self.banco, "ana", "errada"))
        self.assertIsNone(autenticar(self.banco, "ninguem", "segredo1"))

    def test_usuario_desativado_nao_entra(self):
        self.banco.definir_ativo(self.id, False)
        self.assertIsNone(autenticar(self.banco, "ana", "segredo1"))


class TestPermissoes(unittest.TestCase):
    def test_so_admin_exclui(self):  # RN02
        self.assertTrue(pode_excluir(ADMIN))
        self.assertFalse(pode_excluir(PORTEIRO))
        self.assertFalse(pode_excluir(None))

    def test_nao_pode_desativar_a_si_mesmo(self):
        ok, msg = pode_desativar(ADMIN, ADMIN, admins_ativos=2)
        self.assertFalse(ok)
        self.assertIn("próprio", msg)

    def test_nao_pode_ficar_sem_administrador(self):
        ok, msg = pode_desativar(ADMIN_2, ADMIN, admins_ativos=1)
        self.assertFalse(ok)
        self.assertIn("pelo menos um administrador", msg)

    def test_pode_desativar_outro_admin_ou_porteiro(self):
        self.assertTrue(pode_desativar(ADMIN_2, ADMIN, admins_ativos=2)[0])
        self.assertTrue(pode_desativar(PORTEIRO, ADMIN, admins_ativos=1)[0])


class TestTentativas(unittest.TestCase):
    def setUp(self):
        self.agora = [1000.0]
        self.controle = ControleTentativas(relogio=lambda: self.agora[0])

    def test_bloqueia_depois_do_limite_e_libera_com_o_tempo(self):
        for _ in range(LIMITE_TENTATIVAS - 1):
            self.controle.registrar_falha()
        self.assertEqual(self.controle.segundos_restantes(), 0)
        self.controle.registrar_falha()
        self.assertEqual(self.controle.segundos_restantes(), SEGUNDOS_BLOQUEIO)
        self.agora[0] += SEGUNDOS_BLOQUEIO
        self.assertEqual(self.controle.segundos_restantes(), 0)

    def test_acerto_zera_as_falhas(self):
        for _ in range(LIMITE_TENTATIVAS - 1):
            self.controle.registrar_falha()
        self.controle.registrar_sucesso()
        self.controle.registrar_falha()
        self.assertEqual(self.controle.segundos_restantes(), 0)


if __name__ == "__main__":
    unittest.main()
