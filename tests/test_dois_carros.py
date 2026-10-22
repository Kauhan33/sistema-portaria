"""
Versão 2.2 — V5 / RN40: dois carros da mesma pessoa no estacionamento.
Achado no teste do aluno: a pessoa sai a pé deixando o carro A, volta com
o carro B e, na saída, só o B era oferecido. Regras puras (veiculos.py),
banco (inclusive direto, sem a tela) e tela.
"""

import os
import tempfile
import tkinter as tk
import unittest
from datetime import timedelta

from portaria import dados, excecoes, veiculos
from portaria.senhas import gerar_hash
from portaria.tela_veiculo import A_PE, ENTRAR, ENTRAR_COM_SENHA, JA_SAIU

from .test_dados import registro
from .test_interface import AGORA, BaseInterface

ANA = "52998224725"


def senha_da_ana(justificativa="Conferido com a câmera da cancela"):
    return {"autorizado_por": "ana", "senha": "senha-da-ana",
            "regras": ["RN40"], "justificativa": justificativa}


class TestRegrasPuras(unittest.TestCase):
    def test_limite_de_dois_carros(self):
        self.assertEqual(veiculos.MAXIMO_CARROS_POR_PESSOA, 2)
        self.assertFalse(veiculos.precisa_senha_para_outro_carro(0))
        self.assertFalse(veiculos.precisa_senha_para_outro_carro(1))
        self.assertTrue(veiculos.precisa_senha_para_outro_carro(2))
        self.assertTrue(veiculos.precisa_senha_para_outro_carro(3))

    def test_texto_do_aviso(self):
        self.assertEqual(veiculos.aviso_outro_carro(
            "Carla Nogueira", [("BRA2E19", "08:20")]),
            "Carla já tem o BRA2E19 no estacionamento desde 08:20")
        self.assertEqual(veiculos.aviso_outro_carro(
            "Carla Nogueira", [("BRA2E19", "08:20"), ("ABC-1234", "09:00")]),
            "Carla já tem 2 carros no estacionamento")

    def test_o_carro_da_visita_vem_primeiro(self):
        antigo = {"id": 1, "registro_id": 10, "entrada": "21/10/2026 08:00"}
        novo = {"id": 2, "registro_id": 11, "entrada": "21/10/2026 09:00"}
        self.assertEqual([e["id"] for e in veiculos.ordem_dos_carros(
            [antigo, novo], 11)], [2, 1])
        self.assertEqual([e["id"] for e in veiculos.ordem_dos_carros(
            [novo, antigo], 99)], [1, 2])


class BaseDoisCarrosNoBanco(unittest.TestCase):
    """Ana entra com ABC1234 às 08:00, sai a pé às 09:00 e volta com
    XYZ9A87 às 09:30."""

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.banco = dados.Banco(os.path.join(self.pasta.name, "portaria.db"))
        self.banco.criar_usuario("Ana Admin", "ana", "admin",
                                 gerar_hash("senha-da-ana"))
        self.banco.criar_usuario("Paulo Porteiro", "paulo", "porteiro", "h",
                                 autor="ana", trocar_senha=False)
        primeira = self.banco.inserir(registro(placa="ABC1234",
                                               entrada="19/10/2026 08:00"),
                                      autor="paulo")
        self.banco.registrar_saidas([primeira], "19/10/2026 09:00",
                                    autor="paulo")
        self.volta = self.banco.inserir(registro(placa="XYZ9A87",
                                                 entrada="19/10/2026 09:30"),
                                        autor="paulo")
        self.a = self.banco.estadia_aberta(placa="ABC1234")
        self.b = self.banco.estadia_aberta(placa="XYZ9A87")

    def tearDown(self):
        self.pasta.cleanup()

    def abertos(self):
        return [e["placa"] for e in self.banco.estadias_abertas_do_cpf(ANA)]

    def acoes(self):
        return [e["acao"] for e in self.banco.listar_eventos()]


class TestDoisCarrosNoBanco(BaseDoisCarrosNoBanco):
    def test_sai_com_o_a_e_o_b_fica(self):
        self.banco.registrar_saidas([self.volta], "19/10/2026 10:00",
                                    autor="paulo",
                                    com_veiculo={self.volta: self.a["id"]})
        self.assertEqual(self.abertos(), ["XYZ9A87"])

    def test_sai_com_o_b_e_o_a_fica(self):
        self.banco.registrar_saidas([self.volta], "19/10/2026 10:00",
                                    autor="paulo",
                                    com_veiculo={self.volta: self.b["id"]})
        self.assertEqual(self.abertos(), ["ABC1234"])

    def test_a_pe_deixa_os_dois(self):
        self.banco.registrar_saidas([self.volta], "19/10/2026 10:00",
                                    autor="paulo")
        self.assertEqual(self.abertos(), ["ABC1234", "XYZ9A87"])

    def test_uma_saida_fecha_no_maximo_um_carro(self):
        self.banco.registrar_saidas([self.volta], "19/10/2026 10:00",
                                    autor="paulo", com_veiculo={self.volta})
        self.assertEqual(len(self.abertos()), 1)

    def test_desfazer_devolve_o_carro_certo(self):
        self.banco.registrar_saidas([self.volta], "19/10/2026 10:00",
                                    autor="paulo",
                                    com_veiculo={self.volta: self.a["id"]})
        self.banco.desfazer_saidas([self.volta], autor="paulo",
                                   saida="19/10/2026 10:00")
        self.assertEqual(self.abertos(), ["ABC1234", "XYZ9A87"])

    def terceiro(self, **extra):
        self.banco.registrar_saidas([self.volta], "19/10/2026 10:00",
                                    autor="paulo")
        return self.banco.inserir(registro(placa="QWE1D23",
                                           entrada="19/10/2026 10:30"),
                                  autor="paulo", **extra)

    def test_terceiro_carro_sem_senha_e_recusado_direto_no_banco(self):
        for extra in ({}, {"autorizacao_carros": dict(senha_da_ana(),
                                                      com_senha=True,
                                                      senha="errada")}):
            with self.subTest(extra=list(extra)):
                with self.assertRaises(dados.ErroDados) as erro:
                    self.terceiro(**extra)
                self.assertIn("2 carros" if not extra else "incorretos",
                              str(erro.exception))
        self.assertEqual(self.abertos(), ["ABC1234", "XYZ9A87"])
        self.assertEqual(len(self.banco.listar()), 2)

    def test_terceiro_carro_com_a_senha_entra_e_vai_as_excecoes(self):
        self.terceiro(autorizacao_carros=senha_da_ana())
        self.assertEqual(len(self.abertos()), 3)
        self.assertIn(dados.OUTRO_CARRO_LIBERADO, self.acoes())

    def test_ja_saiu_sem_senha_e_recusado(self):
        self.banco.registrar_saidas([self.volta], "19/10/2026 10:00",
                                    autor="paulo")
        marca = dict(senha_da_ana(), com_senha=True)
        del marca["senha"]
        for autorizacao in (None, marca):
            with self.assertRaises(dados.ErroDados):
                self.banco.inserir(registro(placa="QWE1D23",
                                            entrada="19/10/2026 10:30"),
                                   autor="paulo", carro_ja_saiu=self.a["id"],
                                   autorizacao_ja_saiu=autorizacao)
        self.assertEqual(self.abertos(), ["ABC1234", "XYZ9A87"])

    def test_ja_saiu_com_senha_fecha_o_carro_e_entra_com_o_terceiro(self):
        self.banco.registrar_saidas([self.volta], "19/10/2026 10:00",
                                    autor="paulo")
        self.banco.inserir(registro(placa="QWE1D23",
                                    entrada="19/10/2026 10:30"),
                           autor="paulo", carro_ja_saiu=self.a["id"],
                           autorizacao_ja_saiu=senha_da_ana())
        self.assertEqual(self.abertos(), ["XYZ9A87", "QWE1D23"])
        evento = next(e for e in self.banco.listar_eventos()
                      if e["acao"] == dados.CARRO_JA_SAIU)
        linha = excecoes.ler_excecao(dict(evento, nome="", cpf=""))
        self.assertEqual(linha["tipos"], ["Carro que já tinha saído"])
        self.assertEqual(linha["autorizou"], "ana")
        self.assertEqual(linha["operava"], "paulo")

    def test_ja_saiu_so_vale_para_carro_da_propria_pessoa(self):
        outro = self.banco.inserir(registro(cpf="11144477735", placa="JKL4M56",
                                            entrada="19/10/2026 09:40"),
                                   autor="paulo")
        alheio = self.banco.estadia_aberta(placa="JKL4M56")
        self.banco.registrar_saidas([self.volta], "19/10/2026 10:00",
                                    autor="paulo")
        with self.assertRaises(dados.ErroDados):
            self.banco.inserir(registro(placa="QWE1D23",
                                        entrada="19/10/2026 10:30"),
                               autor="paulo", carro_ja_saiu=alheio["id"],
                               autorizacao_ja_saiu=senha_da_ana())
        self.assertIsNotNone(self.banco.estadia_aberta(placa="JKL4M56"))
        self.assertTrue(self.banco.buscar(outro))

    def test_correcao_nao_abre_um_terceiro_carro(self):
        self.banco.registrar_saidas([self.volta], "19/10/2026 10:00",
                                    autor="paulo")
        id_ = self.banco.inserir(registro(placa="", entrada="19/10/2026 10:30"),
                                 autor="paulo")
        atual = self.banco.buscar(id_)
        with self.assertRaises(dados.ErroDados):
            self.banco.editar(id_, dict(atual, placa="QWE1D23"), ["Placa"],
                              autor="ana")
        self.assertEqual(len(self.abertos()), 2)


# ----------------------------------------------------------------------
# Tela
# ----------------------------------------------------------------------
class TestDoisCarrosNaTela(BaseInterface):
    entrar_como = "porteiro"

    def setUp(self):
        super().setUp()
        self.tela = self.app.tela_cadastro
        self.preencher(cpf=ANA, placa="ABC1234", tipo="Professor")
        self.app.cadastrar()
        self.responder_veiculo = A_PE
        self.saida_rapida(ANA)                        # sai a pé, ABC fica
        self.agora = AGORA + timedelta(hours=1)
        self.perguntas_veiculo.clear()

    def saida_rapida(self, texto):
        self.tela.campo_saida_rapida.delete(0, tk.END)
        self.tela.campo_saida_rapida.insert(0, texto)
        self.tela.saida_rapida()

    def entrar_com(self, placa, resposta="principal"):
        self.app.limpar()
        self.preencher(cpf=ANA, placa=placa, tipo="Professor")
        self.responder_veiculo = resposta
        self.app.cadastrar()

    def abertos(self):
        return [e["placa"] for e in self.banco.estadias_abertas_do_cpf(ANA)]

    def test_entrada_com_outro_carro_avisa_e_ficam_os_dois(self):
        vistos = []

        def responder(dialogo):
            vistos.append([texto for texto, _, _ in dialogo.opcoes])
            dialogo.escolher(dialogo.padrao)
        self.entrar_com("XYZ9A87", responder)
        self.assertEqual(self.perguntas_veiculo,
                         ["Ana já tem o ABC-1234 no estacionamento desde "
                          "10:00"])
        self.assertEqual(vistos[0], ["Entrar — ficam os dois",
                                     "O ABC-1234 já saiu"])
        self.assertEqual(self.abertos(), ["ABC1234", "XYZ9A87"])

    def test_cancelar_nao_grava(self):
        self.entrar_com("XYZ9A87", None)
        self.assertEqual(len(self.no_banco()), 1)
        self.assertEqual(self.abertos(), ["ABC1234"])

    def test_ja_saiu_pede_a_senha_e_corrige(self):
        estadia = self.banco.estadia_aberta(placa="ABC1234")
        self.entrar_com("XYZ9A87", (JA_SAIU, estadia["id"]))   # sem senha
        self.assertEqual(len(self.no_banco()), 1)
        self.assertTrue(self.autorizacoes[0].veiculo)
        self.autorizar_com_senha(justificativa="Câmera mostra a saída às 09:50")
        self.entrar_com("XYZ9A87", (JA_SAIU, estadia["id"]))
        self.assertEqual(self.abertos(), ["XYZ9A87"])
        self.assertIn(("ana.admin", dados.CARRO_JA_SAIU), self.acoes())

    def test_terceiro_carro_so_com_a_senha(self):
        self.entrar_com("XYZ9A87")
        self.saida_rapida(ANA)                        # (escolhe o da visita)
        self.banco.registrar_saidas(
            [max(r["id"] for r in self.no_banco())],
            (AGORA + timedelta(hours=1)).strftime("%d/%m/%Y %H:%M"),
            autor="paulo")                            # garante: sai a pé
        self.app.atualizar_tabela()
        abertos_antes = self.abertos()
        self.entrar_com("QWE1D23", ENTRAR_COM_SENHA)  # cancela a senha
        self.assertEqual(self.abertos(), abertos_antes)
        self.assertTrue(self.autorizacoes[-1].pede_senha)

    def test_saida_pergunta_uma_vez_com_os_dois_carros(self):
        self.entrar_com("XYZ9A87")
        vistos = []

        def responder(dialogo):
            vistos.append((dialogo.janela.title(),
                           [texto for texto, _, _ in dialogo.opcoes]))
            dialogo.escolher(dialogo.padrao)
        self.responder_veiculo = responder
        self.saida_rapida(ANA)
        titulo, botoes = vistos[0]
        self.assertEqual(titulo, "Com qual carro Ana está saindo?")
        self.assertEqual(botoes, ["XYZ9A87 — desde 11:00",
                                  "ABC-1234 — desde 10:00",
                                  "A pé — os carros ficam"])
        self.assertEqual(len(vistos), 1)              # uma pergunta só
        self.assertEqual(self.abertos(), ["ABC1234"])  # saiu com o da visita

    def test_a_pe_deixa_os_dois_e_o_desfazer(self):
        self.entrar_com("XYZ9A87")
        self.responder_veiculo = A_PE
        self.saida_rapida(ANA)
        self.assertEqual(self.abertos(), ["ABC1234", "XYZ9A87"])
        self.assertIn("os carros XYZ9A87, ABC-1234 ficam",
                      self.tela.lbl_aviso.cget("text"))

    def test_desfazer_devolve_o_carro_escolhido(self):
        self.entrar_com("XYZ9A87")
        antigo = self.banco.estadia_aberta(placa="ABC1234")["id"]
        self.responder_veiculo = antigo
        self.saida_rapida(ANA)
        self.assertEqual(self.abertos(), ["XYZ9A87"])
        self.tela.desfazer_saida()
        self.assertEqual(self.abertos(), ["ABC1234", "XYZ9A87"])

    def test_saida_pela_placa_a_continua_perguntando_se_saiu_junto(self):
        self.entrar_com("XYZ9A87")
        self.perguntas_veiculo.clear()
        self.responder_veiculo = "principal"          # saiu junto
        self.saida_rapida("ABC1234")
        self.assertEqual(self.perguntas_veiculo, ["Ana saiu junto com o carro?"])
        self.assertEqual(self.abertos(), ["XYZ9A87"])


if __name__ == "__main__":
    unittest.main()
