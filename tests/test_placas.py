"""
RN47 (versão 2.5): uma pessoa pode ter mais de uma placa no cadastro.
O banco (placas_pessoa, esquema v12) e a migração de um banco da 2.4.
"""
import os
import sqlite3
import unittest
from datetime import date

from portaria import dados
from portaria.validacao import MAXIMO_PLACAS_PESSOA, validar_placas

from .test_dados import rebaixar_para_v11, registro, versao_do_arquivo
from .test_regras_no_banco import BaseRegras

ANA = "52998224725"
BETO = "11144477735"


class TestValidarPlacas(unittest.TestCase):
    def test_normaliza_tira_repetidas_e_mantem_a_ordem(self):
        self.assertEqual(validar_placas(["abc-1d23", " NEY4829", "ABC1D23", ""]),
                         (True, "", ["ABC1D23", "NEY4829"]))

    def test_placa_invalida_e_nomeada_na_mensagem(self):
        ok, msg, lista = validar_placas(["ABC1D23", "XY12"])
        self.assertFalse(ok)
        self.assertIn("XY12", msg)
        self.assertEqual(lista, [])

    def test_no_maximo_cinco(self):
        placas = [f"ABC1D2{i}" for i in range(MAXIMO_PLACAS_PESSOA + 1)]
        ok, msg, _ = validar_placas(placas)
        self.assertFalse(ok)
        self.assertIn(f"No máximo {MAXIMO_PLACAS_PESSOA} placas", msg)
        self.assertTrue(validar_placas(placas[:-1])[0])


class TestPlacasNoBanco(BaseRegras):
    def cadastrar(self, placas, cpf=ANA, autor="paulo"):
        return self.banco.cadastrar_pessoa(cpf, "Ana Souza", "31987654321",
                                           placas, "Aluno", autor)

    def test_cadastro_com_varias_placas_principal_primeiro(self):
        self.cadastrar(["NEY4829", "abc1d23"])
        p = self.banco.buscar_pessoa(ANA)
        self.assertEqual(p["placa"], "NEY4829")              # a principal
        self.assertEqual(p["placas"], ["NEY4829", "ABC1D23"])
        self.assertEqual(self.banco.placas_da_pessoa(p["id"]),
                         ["NEY4829", "ABC1D23"])
        evento = self.banco.listar_eventos()[0]
        self.assertIn("placas NEY4829, ABC1D23", evento["detalhe"])

    def test_cadastro_com_uma_placa_ou_nenhuma_continua_valendo(self):
        self.cadastrar("ABC1D23")
        self.assertEqual(self.banco.buscar_pessoa(ANA)["placas"], ["ABC1D23"])
        self.cadastrar("", cpf=BETO)
        self.assertEqual(self.banco.buscar_pessoa(BETO)["placas"], [])

    def test_cadastro_recusa_placa_invalida_e_passar_do_maximo(self):
        with self.assertRaises(dados.ErroDados) as erro:
            self.cadastrar(["ABC1D23", "AB12"])
        self.assertIn("AB12", str(erro.exception))
        with self.assertRaises(dados.ErroDados):
            self.cadastrar([f"ABC1D2{i}" for i in range(6)])
        self.assertIsNone(self.banco.buscar_pessoa(ANA))

    def test_editar_inclui_e_tira_placas(self):
        self.cadastrar(["ABC1D23", "NEY4829"])
        p = self.banco.buscar_pessoa(ANA)
        self.banco.atualizar_pessoa(p["id"], p["nome"], p["celular"],
                                    ["NEY4829", "QWE1E34"], p["tipo"],
                                    autor="paulo")
        p = self.banco.buscar_pessoa(ANA)
        self.assertEqual(p["placas"], ["NEY4829", "QWE1E34"])
        detalhe = self.banco.listar_eventos()[0]["detalhe"]
        self.assertIn("incluída(s): QWE1E34", detalhe)
        self.assertIn("tirada(s): ABC1D23", detalhe)
        # sem placa nenhuma
        self.banco.atualizar_pessoa(p["id"], p["nome"], p["celular"], [],
                                    p["tipo"], autor="paulo")
        self.assertEqual(self.banco.buscar_pessoa(ANA)["placas"], [])
        self.assertEqual(self.banco.buscar_pessoa(ANA)["placa"], "")

    def test_tirar_a_placa_remove_quem_podia_retirar_aquele_carro(self):
        self.cadastrar(["ABC1D23", "NEY4829"])
        self.banco.adicionar_autorizado(ANA, BETO, "Beto Rocha", None, "ana",
                                        placa="NEY4829")
        self.banco.adicionar_autorizado(ANA, BETO, "Beto Rocha", None, "ana")
        self.assertEqual(len(self.banco.listar_autorizados("NEY4829")), 1)
        p = self.banco.buscar_pessoa(ANA)
        self.banco.atualizar_pessoa(p["id"], p["nome"], p["celular"],
                                    ["ABC1D23"], p["tipo"], autor="ana")
        self.assertEqual(self.banco.listar_autorizados("NEY4829"), [])
        self.assertEqual(len(self.banco.listar_autorizados("ABC1D23")), 1)
        self.assertIn("1 autorizado(s)", self.banco.listar_eventos()[0]["detalhe"])

    def test_autorizado_so_para_um_carro_da_pessoa(self):
        self.cadastrar(["ABC1D23"])
        with self.assertRaises(dados.ErroDados) as erro:
            self.banco.adicionar_autorizado(ANA, BETO, "Beto Rocha", None,
                                            "ana", placa="NEY4829")
        self.assertIn("não está no cadastro", str(erro.exception))

    def test_visita_com_outro_carro_guarda_a_placa(self):
        self.cadastrar(["ABC1D23"])
        self.banco.inserir(registro(cpf=ANA, nome="Ana Souza", placa="NEY4829",
                                    entrada="19/10/2026 08:00"), autor="paulo")
        p = self.banco.buscar_pessoa(ANA)
        self.assertEqual(p["placa"], "NEY4829")        # veio com ele por último
        self.assertEqual(p["placas"], ["NEY4829", "ABC1D23"])

    def test_visita_a_pe_nao_mexe_nas_placas(self):
        self.cadastrar(["ABC1D23", "NEY4829"])
        self.banco.inserir(registro(cpf=ANA, nome="Ana Souza", placa="",
                                    entrada="19/10/2026 08:00"), autor="paulo")
        self.assertEqual(self.banco.buscar_pessoa(ANA)["placas"],
                         ["ABC1D23", "NEY4829"])

    def test_busca_acha_pela_segunda_placa(self):
        self.cadastrar(["ABC1D23", "NEY4829"])
        self.cadastrar("", cpf=BETO)
        achadas = self.banco.buscar_pessoas("ney-48")
        self.assertEqual([p["cpf"] for p in achadas], [ANA])
        self.assertEqual([p["cpf"] for p in self.banco.buscar_pessoas("ney4829")],
                         [ANA])

    def test_excluir_pessoa_apaga_as_placas(self):
        self.cadastrar(["ABC1D23", "NEY4829"])
        p = self.banco.buscar_pessoa(ANA)
        self.banco.excluir_pessoa(p["id"], "ana")
        con = sqlite3.connect(self.caminho)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM placas_pessoa")
                         .fetchone()[0], 0)
        con.close()

    def test_a_mesma_placa_pode_ser_de_duas_pessoas(self):
        """O carro da família: os dois cadastros mostram a placa."""
        self.cadastrar(["ABC1D23"])
        self.cadastrar(["ABC1D23"], cpf=BETO)
        self.assertEqual(self.banco.buscar_pessoa(BETO)["placas"], ["ABC1D23"])


class TestMigracaoV11ParaV12(BaseRegras):
    """Versão 2.5: um banco da 2.4 (v11) ganha placas_pessoa com a placa
    do cadastro e as placas das visitas, sem perder nada e com backup."""

    def test_v11_vira_v12_com_as_placas_das_visitas(self):
        self.banco.inserir(registro(cpf=ANA, placa="NEY4829",
                                    entrada="16/10/2026 08:00",
                                    saida="16/10/2026 12:00"), autor="paulo")
        self.banco.inserir(registro(cpf=ANA, placa="ABC1D23",
                                    entrada="19/10/2026 08:00"), autor="paulo")
        self.banco.cadastrar_pessoa(BETO, "Beto Rocha", "31987654321", "",
                                    "Aluno", "ana")
        antes = (self.banco.listar(), self.banco.listar_estacionamento(),
                 len(self.banco.listar_eventos(limite=10_000)))
        rebaixar_para_v11(self.caminho)
        self.assertEqual(versao_do_arquivo(self.caminho), 11)
        banco = dados.Banco(self.caminho, relogio=lambda: self.AGORA)
        self.assertEqual(versao_do_arquivo(self.caminho), dados.VERSAO_ESQUEMA)
        self.assertEqual((banco.listar(), banco.listar_estacionamento(),
                          len(banco.listar_eventos(limite=10_000))), antes)
        ana = banco.buscar_pessoa(ANA)
        self.assertEqual(ana["placa"], "ABC1D23")
        self.assertEqual(ana["placas"], ["ABC1D23", "NEY4829"])
        self.assertEqual(banco.buscar_pessoa(BETO)["placas"], [])
        backups = os.listdir(os.path.join(self.pasta.name, "backups"))
        self.assertTrue(any(f"antes-v{dados.VERSAO_ESQUEMA}-de-v11" in b
                            for b in backups))

    def test_migrar_de_novo_nao_duplica(self):
        """Banco rebaixado por um programa antigo: o passo roda de novo."""
        self.banco.inserir(registro(cpf=ANA, placa="NEY4829"), autor="paulo")
        con = sqlite3.connect(self.caminho)
        con.execute("PRAGMA user_version = 11")
        con.close()
        banco = dados.Banco(self.caminho, relogio=lambda: self.AGORA)
        self.assertEqual(banco.buscar_pessoa(ANA)["placas"], ["NEY4829"])


if __name__ == "__main__":
    unittest.main()
