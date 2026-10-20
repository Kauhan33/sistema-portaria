import os
import sqlite3
from datetime import datetime, timedelta
import tempfile
import unittest
from unittest import mock

from portaria import dados, usuarios
from portaria.usuarios import (LIMITE_TENTATIVAS, SEGUNDOS_BLOQUEIO,
                               ControleTentativas, autenticar, conferir_senha,
                               entrar, gerar_hash, pode_desativar, pode_editar,
                               pode_excluir, pode_gerenciar_bloqueios,
                               trocar_senha, validar_novo_usuario,
                               validar_senha, validar_troca_senha)

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

    def test_senha_minima_de_8_caracteres(self):  # S07
        self.assertIn("pelo menos 8", validar_senha("segred7", "segred7")[1])
        self.assertTrue(validar_senha("segredo8", "segredo8")[0])
        longa = "a1" * 65
        self.assertIn("no máximo", validar_senha(longa, longa)[1])

    def test_senha_comum_ou_igual_ao_login_e_recusada(self):  # S07
        for senha in ("12345678", "Senha123", "portaria123"):
            with self.subTest(senha=senha):
                self.assertIn("fácil", validar_senha(senha, senha)[1])
        self.assertIn("fácil", validar_senha("maria.souza", "maria.souza",
                                             login="maria.souza")[1])

    def test_padrao_de_producao_e_600_mil_iteracoes(self):  # S15
        self.assertGreaterEqual(usuarios.ITERACOES_PADRAO, 600_000)

    def test_gerar_hash_le_as_iteracoes_na_hora(self):
        with mock.patch.object(usuarios, "ITERACOES", 1234):
            self.assertEqual(gerar_hash("segredo1").split("$")[1], "1234")
        self.assertEqual(gerar_hash("segredo1").split("$")[1],
                         str(usuarios.ITERACOES))

    def test_sessao_expira_por_inatividade(self):  # S05 (a tela liga)
        self.assertGreater(usuarios.MINUTOS_INATIVIDADE, 0)


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
            "senha igual ao login": (dict(senha="maria.souza",
                                          confirmacao="maria.souza"), "fácil"),
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

    def test_hash_antigo_continua_entrando_e_e_atualizado(self):  # S15
        # o padrão antigo tinha menos iterações (200 mil); nos testes o
        # "atual" é ITERACOES (baixado), então o antigo aqui é menor ainda
        antigo = gerar_hash("segredo1", iteracoes=usuarios.ITERACOES // 5)
        self.banco.definir_senha(self.id, antigo)
        self.assertIsNotNone(autenticar(self.banco, "ana", "segredo1"))
        novo = self.banco.buscar_usuario("ana")["senha"]
        self.assertNotEqual(novo, antigo)
        self.assertEqual(novo.split("$")[1], str(usuarios.ITERACOES))
        self.assertIsNotNone(autenticar(self.banco, "ana", "segredo1"))

    def test_senha_errada_nao_atualiza_o_hash(self):
        antigo = gerar_hash("segredo1", iteracoes=usuarios.ITERACOES // 5)
        self.banco.definir_senha(self.id, antigo)
        self.assertIsNone(autenticar(self.banco, "ana", "errada"))
        self.assertEqual(self.banco.buscar_usuario("ana")["senha"], antigo)


class TestEntrar(unittest.TestCase):
    """Login com tentativas guardadas no banco (S06) e sem vazar texto (S11)."""

    AGORA = datetime(2026, 10, 20, 8, 0)

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = os.path.join(self.pasta.name, "portaria.db")
        self.banco = dados.Banco(self.caminho)
        self.banco.criar_usuario("Ana Admin", "ana", "admin", gerar_hash("segredo1"))
        self.banco.criar_usuario("Paulo Porteiro", "paulo", "porteiro",
                                 gerar_hash("segredo2"))

    def tearDown(self):
        self.pasta.cleanup()

    def errar(self, vezes, login="ana", agora=None):
        motivo = ""
        for _ in range(vezes):
            usuario, motivo = entrar(self.banco, login, "errada", agora or self.AGORA)
            self.assertIsNone(usuario)
        return motivo

    def test_login_certo(self):
        usuario, motivo = entrar(self.banco, " ANA ", "segredo1", self.AGORA)
        self.assertEqual((usuario["login"], usuario["perfil"], motivo),
                         ("ana", "admin", ""))
        self.assertNotIn("senha", usuario)

    def test_campos_vazios(self):
        self.assertEqual(entrar(self.banco, " ", "x", self.AGORA),
                         (None, "Informe o usuário e a senha."))
        self.assertIsNone(entrar(self.banco, "ana", "", self.AGORA)[0])

    def test_bloqueio_sobrevive_a_reabrir_o_programa(self):  # S06
        self.errar(LIMITE_TENTATIVAS - 1)
        self.banco = dados.Banco(self.caminho)        # fechou e abriu de novo
        motivo = self.errar(1)
        self.assertIn(f"Aguarde {SEGUNDOS_BLOQUEIO} s", motivo)
        # durante o bloqueio, nem a senha certa entra
        usuario, motivo = entrar(dados.Banco(self.caminho), "ana", "segredo1",
                                 self.AGORA + timedelta(seconds=10))
        self.assertIsNone(usuario)
        self.assertIn(f"Aguarde {SEGUNDOS_BLOQUEIO - 10} s", motivo)
        depois = self.AGORA + timedelta(seconds=SEGUNDOS_BLOQUEIO)
        self.assertIsNotNone(entrar(self.banco, "ana", "segredo1", depois)[0])

    def test_bloqueio_cresce_a_cada_vez(self):
        self.assertIn(f"Aguarde {SEGUNDOS_BLOQUEIO} s",
                      self.errar(LIMITE_TENTATIVAS))
        depois = self.AGORA + timedelta(seconds=SEGUNDOS_BLOQUEIO)
        self.assertIn(f"Aguarde {2 * SEGUNDOS_BLOQUEIO} s",
                      self.errar(LIMITE_TENTATIVAS, agora=depois))
        self.assertEqual(usuarios.segundos_de_bloqueio(50),
                         usuarios.SEGUNDOS_BLOQUEIO_MAXIMO)

    def test_bloqueio_e_por_login(self):
        self.errar(LIMITE_TENTATIVAS)
        self.assertIsNotNone(entrar(self.banco, "paulo", "segredo2", self.AGORA)[0])

    def test_acerto_zera_as_falhas(self):
        self.errar(LIMITE_TENTATIVAS - 1)
        self.assertIsNotNone(entrar(self.banco, "ana", "segredo1", self.AGORA)[0])
        self.assertEqual(self.errar(LIMITE_TENTATIVAS - 1),
                         "Usuário ou senha incorretos.")

    def test_login_recusado_fica_no_historico(self):
        self.errar(1)
        evento = self.banco.listar_eventos()[0]
        self.assertEqual((evento["usuario"], evento["acao"]), ("ana", "Login recusado"))

    def test_senha_digitada_no_campo_usuario_nao_e_gravada(self):  # S11
        entrar(self.banco, "MinhaSenha#2026", "x", self.AGORA)
        evento = self.banco.listar_eventos()[0]
        self.assertEqual((evento["usuario"], evento["acao"]),
                         (usuarios.LOGIN_INEXISTENTE, "Login recusado"))
        con = sqlite3.connect(self.caminho)
        tudo = str([con.execute(f"SELECT * FROM {t}").fetchall()
                    for t in ("auditoria", "tentativas_login")])
        con.close()
        self.assertNotIn("minhasenha", tudo.lower())

    def test_usuario_desativado_nao_entra(self):
        self.banco.definir_ativo(2, False)
        usuario, motivo = entrar(self.banco, "paulo", "segredo2", self.AGORA)
        self.assertIsNone(usuario)
        self.assertEqual(motivo, "Usuário ou senha incorretos.")


class TestTrocarSenha(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.banco = dados.Banco(os.path.join(self.pasta.name, "portaria.db"))
        self.banco.criar_usuario("Paulo Porteiro", "paulo", "porteiro",
                                 gerar_hash("segredo2"))
        self.paulo = autenticar(self.banco, "paulo", "segredo2")

    def tearDown(self):
        self.pasta.cleanup()

    def test_validacao_da_troca(self):
        guardado = gerar_hash("segredo2")
        casos = {
            "senha atual errada": (("errada", "nova.senha9", "nova.senha9"), "atual"),
            "nova igual à atual": (("segredo2", "segredo2", "segredo2"), "diferente"),
            "nova curta": (("segredo2", "abc", "abc"), "pelo menos"),
            "nova comum": (("segredo2", "12345678", "12345678"), "fácil"),
            "confirmação": (("segredo2", "nova.senha9", "outra"), "confirmação"),
        }
        for caso, (args, trecho) in casos.items():
            with self.subTest(caso):
                ok, msg = validar_troca_senha(guardado, *args, login="paulo")
                self.assertFalse(ok)
                self.assertIn(trecho, msg)
        self.assertEqual(validar_troca_senha(guardado, "segredo2", "nova.senha9",
                                             "nova.senha9"), (True, ""))

    def test_trocar_a_propria_senha(self):
        ok, _ = trocar_senha(self.banco, self.paulo, "errada", "nova.senha9",
                             "nova.senha9")
        self.assertFalse(ok)
        ok, msg = trocar_senha(self.banco, self.paulo, "segredo2", "nova.senha9",
                               "nova.senha9")
        self.assertTrue(ok, msg)
        self.assertIsNone(autenticar(self.banco, "paulo", "segredo2"))
        self.assertIsNotNone(autenticar(self.banco, "paulo", "nova.senha9"))
        evento = self.banco.listar_eventos()[0]
        self.assertEqual((evento["usuario"], evento["acao"]),
                         ("paulo", "Senha alterada"))


class TestPermissoes(unittest.TestCase):
    def test_so_admin_exclui(self):  # RN02
        self.assertTrue(pode_excluir(ADMIN))
        self.assertFalse(pode_excluir(PORTEIRO))
        self.assertFalse(pode_excluir(None))

    def test_so_admin_gerencia_bloqueios(self):
        self.assertTrue(pode_gerenciar_bloqueios(ADMIN))
        self.assertFalse(pode_gerenciar_bloqueios(PORTEIRO))

    def test_quem_pode_corrigir_registro(self):  # RN11
        agora = datetime(2026, 10, 17, 0, 10)
        virou_a_noite = {"entrada": "16/10/2026 23:50"}   # 20 min atrás
        de_ontem_cedo = {"entrada": "15/10/2026 23:00"}   # mais de 24 h
        no_futuro = {"entrada": "17/10/2026 08:00"}
        self.assertTrue(pode_editar(ADMIN, de_ontem_cedo, agora)[0])
        self.assertTrue(pode_editar(PORTEIRO, virou_a_noite, agora)[0])
        ok, msg = pode_editar(PORTEIRO, de_ontem_cedo, agora)
        self.assertFalse(ok)
        self.assertIn("administrador", msg)
        self.assertFalse(pode_editar(PORTEIRO, no_futuro, agora)[0])
        self.assertFalse(pode_editar(None, virou_a_noite, agora)[0])

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
