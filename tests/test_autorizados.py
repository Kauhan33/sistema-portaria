"""
Versão 2.2 — V1 / RN35: pessoas autorizadas a retirar o veículo sem o
dono e sem senha. Regras puras (veiculos.py), o banco (inclusive ataques
diretos, sem a tela) e a tela (saída pelo CPF, pela placa, Desfazer,
ficha da pessoa e a coluna "Pode retirar").
"""

import os
import tempfile
import unittest
from datetime import date, datetime, timedelta

from portaria import dados, veiculos
from portaria.senhas import gerar_hash
from portaria.tela_veiculo import LEVA, NAO_LEVA

from .test_dados import registro
from .test_interface import BaseInterface

CARLA, BRUNO, DAVI, EVA = ("52998224725", "11144477735", "39053344705",
                           "86288366757")
HOJE = date(2026, 10, 19)


class TestRegrasPuras(unittest.TestCase):
    def autorizado(self, **mudancas):
        base = {"ativo": True, "valido_ate": None}
        base.update(mudancas)
        return base

    def test_quem_cadastra(self):
        self.assertTrue(veiculos.pode_cadastrar_autorizado(True, False)[0])
        self.assertTrue(veiculos.pode_cadastrar_autorizado(False, True)[0])
        ok, motivo = veiculos.pode_cadastrar_autorizado(False, False)
        self.assertFalse(ok)
        self.assertIn("dono precisa estar no campus", motivo)

    def test_pode_levar(self):
        vale = self.autorizado(valido_ate=HOJE)
        self.assertEqual(veiculos.pode_levar(vale, HOJE, True, False), (True, ""))
        casos = [(None, HOJE, True, False, "lista"),
                 (self.autorizado(ativo=False), HOJE, True, False, "removida"),
                 (vale, HOJE + timedelta(days=1), True, False, "venceu"),
                 (vale, HOJE, False, False, "outro veículo"),
                 (vale, HOJE, True, True, "bloqueado")]
        for autorizado, dia, a_pe, bloqueado, trecho in casos:
            with self.subTest(trecho=trecho):
                ok, motivo = veiculos.pode_levar(autorizado, dia, a_pe,
                                                 bloqueado)
                self.assertFalse(ok)
                self.assertIn(trecho, motivo)

    def test_validar_formulario(self):
        dono = {"cpf": CARLA, "placa": "BRA2E19"}
        dados_, erro = veiculos.validar_autorizado(dono, BRUNO, " Bruno  Almeida ",
                                                   "", HOJE)
        self.assertEqual(erro, "")
        self.assertEqual((dados_["nome"], dados_["valido_ate"]),
                         ("Bruno Almeida", None))
        dados_, _ = veiculos.validar_autorizado(dono, BRUNO, "Bruno Almeida",
                                                "31/12/2026", HOJE)
        self.assertEqual(dados_["valido_ate"], date(2026, 12, 31))
        for cpf, nome, validade, trecho in (
                ("11111111111", "Bruno Almeida", "", "CPF inválido"),
                (CARLA, "Carla Nogueira", "", "próprio carro"),
                (BRUNO, "Bruno", "", "nome completo"),
                (BRUNO, "Bruno " + "a" * 80, "", "no máximo"),
                (BRUNO, "Bruno Almeida", "18/10/2026", "antes de hoje"),
                (BRUNO, "Bruno Almeida", "31/02/2026", "data inválida")):
            with self.subTest(trecho=trecho):
                dados_, erro = veiculos.validar_autorizado(dono, cpf, nome,
                                                           validade, HOJE)
                self.assertIsNone(dados_)
                self.assertIn(trecho, erro)
        _, erro = veiculos.validar_autorizado({"cpf": CARLA, "placa": ""},
                                              BRUNO, "Bruno Almeida", "", HOJE)
        self.assertIn("não tem veículo", erro)


class BaseAutorizadosNoBanco(unittest.TestCase):
    """Carla deixou o BRA2E19 no estacionamento e saiu a pé; Bruno está no
    campus a pé."""

    def setUp(self):
        self.agora = datetime(2026, 10, 19, 10, 0)
        self.pasta = tempfile.TemporaryDirectory()
        self.banco = dados.Banco(os.path.join(self.pasta.name, "portaria.db"),
                                 relogio=lambda: self.agora)
        self.banco.criar_usuario("Ana Admin", "ana", "admin",
                                 gerar_hash("senha-da-ana"))
        self.banco.criar_usuario("Paulo Porteiro", "paulo", "porteiro", "h",
                                 autor="ana", trocar_senha=False)
        self.carla = self.banco.inserir(registro(
            cpf=CARLA, nome="Carla Nogueira", placa="BRA2E19",
            entrada="19/10/2026 08:00"), autor="paulo")
        self.carro = self.banco.estadia_aberta(placa="BRA2E19")["id"]
        self.bruno = self.entrar(BRUNO, "Bruno Almeida")

    def tearDown(self):
        self.pasta.cleanup()

    def entrar(self, cpf, nome, placa="", entrada="19/10/2026 08:30"):
        return self.banco.inserir(registro(cpf=cpf, nome=nome, placa=placa,
                                           entrada=entrada), autor="paulo")

    def carla_sai_a_pe(self):
        self.banco.registrar_saidas([self.carla], "19/10/2026 09:00",
                                    autor="paulo")

    def autorizar(self, cpf=BRUNO, nome="Bruno Almeida", valido_ate=None,
                  autor="ana"):
        return self.banco.adicionar_autorizado(CARLA, cpf, nome, valido_ate,
                                               autor=autor)

    def bruno_sai_com_o_carro(self, saida="19/10/2026 10:00", visita=None):
        visita = visita or self.bruno
        return self.banco.registrar_saidas([visita], saida, autor="paulo",
                                           com_veiculo={visita: self.carro})

    def no_estacionamento(self):
        return self.banco.estadia_aberta(placa="BRA2E19") is not None

    def eventos(self, acao):
        return [e for e in self.banco.listar_eventos() if e["acao"] == acao]


class TestQuemCadastra(BaseAutorizadosNoBanco):
    def test_porteiro_com_o_dono_fora_e_recusado_direto_no_banco(self):
        self.carla_sai_a_pe()
        with self.assertRaises(dados.ErroDados) as erro:
            self.autorizar(autor="paulo")
        self.assertIn("dono precisa estar no campus", str(erro.exception))
        self.assertEqual(self.banco.listar_autorizados("BRA2E19"), [])

    def test_porteiro_com_o_dono_no_campus_cadastra(self):
        self.autorizar(autor="paulo")
        evento, = self.eventos(dados.AUTORIZADO_ADICIONADO)
        self.assertEqual(evento["usuario"], "paulo")
        self.assertIn("dono presente", evento["detalhe"])
        self.assertIn("***.444.777-**", evento["detalhe"])     # mascarado
        self.assertTrue(self.banco.listar_autorizados("BRA2E19")[0]
                        ["dono_presente"])

    def test_administrador_cadastra_com_o_dono_fora(self):
        self.carla_sai_a_pe()
        self.autorizar(valido_ate=date(2026, 12, 31))
        autorizado, = self.banco.listar_autorizados("BRA2E19")
        self.assertEqual((autorizado["nome"], autorizado["valido_ate"],
                          autorizado["dono_presente"]),
                         ("Bruno Almeida", date(2026, 12, 31), False))
        self.assertIn("fora do campus",
                      self.eventos(dados.AUTORIZADO_ADICIONADO)[0]["detalhe"])

    def test_dados_invalidos_e_repetidos_sao_recusados(self):
        self.autorizar()
        casos = [dict(cpf=BRUNO),                          # repetido
                 dict(cpf=CARLA, nome="Carla Nogueira"),   # o próprio dono
                 dict(cpf="11111111111"),
                 dict(cpf=DAVI, nome="Davi " + "x" * 80),
                 dict(cpf=DAVI, nome="Davi Souza",
                      valido_ate=date(2026, 10, 18))]
        for caso in casos:
            with self.subTest(caso=caso):
                with self.assertRaises(dados.ErroDados):
                    self.autorizar(**caso)
        self.assertEqual(len(self.banco.listar_autorizados("BRA2E19")), 1)

    def test_sem_usuario_ou_dono_desconhecido_nada_grava(self):
        with self.assertRaises(dados.ErroDados):
            self.autorizar(autor=None)
        with self.assertRaises(dados.ErroDados):
            self.banco.adicionar_autorizado(EVA, BRUNO, "Bruno Almeida", None,
                                            autor="ana")


class TestQuemLevaOCarro(BaseAutorizadosNoBanco):
    def setUp(self):
        super().setUp()
        self.autorizar(valido_ate=date(2026, 10, 19))     # só hoje
        self.carla_sai_a_pe()

    def test_autorizado_no_campus_leva_sem_senha(self):
        self.assertEqual(self.bruno_sai_com_o_carro(), [self.bruno])
        self.assertFalse(self.no_estacionamento())
        evento, = self.eventos(dados.VEICULO_COM_AUTORIZADO)
        self.assertEqual(evento["usuario"], "ana")         # quem autorizou
        for trecho in ("Placa BRA2E19 levada por Bruno Almeida",
                       "autorizado por ana em 19/10/2026",
                       "dono: Carla Nogueira", "Operador: paulo"):
            self.assertIn(trecho, evento["detalhe"])
        self.assertNotIn(BRUNO, evento["detalhe"])
        self.assertEqual(self.eventos(dados.VEICULO_SEM_DONO), [])

    def assert_pede_senha(self, visita=None, saida="19/10/2026 10:00"):
        with self.assertRaises(dados.ErroDados) as erro:
            self.bruno_sai_com_o_carro(saida, visita)
        self.assertIn("só sai com o dono", str(erro.exception))
        self.assertTrue(self.no_estacionamento())
        self.assertEqual(self.eventos(dados.VEICULO_COM_AUTORIZADO), [])

    def test_vencido_pede_senha(self):
        self.agora = datetime(2026, 10, 20, 8, 0)          # venceu ontem
        self.assert_pede_senha(saida="20/10/2026 08:00")

    def test_removido_pede_senha_e_o_porteiro_remove(self):
        autorizado, = self.banco.listar_autorizados("BRA2E19")
        self.banco.remover_autorizado(autorizado["id"], autor="paulo")
        self.assertEqual(self.banco.listar_autorizados("BRA2E19"), [])
        removido, = self.banco.listar_autorizados("BRA2E19",
                                                  incluir_removidos=True)
        self.assertEqual((removido["ativo"], removido["removido_por"]),
                         (False, "paulo"))
        self.assertIn(("paulo", dados.AUTORIZADO_REMOVIDO),
                      [(e["usuario"], e["acao"])
                       for e in self.banco.listar_eventos()])
        with self.assertRaises(dados.ErroDados):        # não remove de novo
            self.banco.remover_autorizado(autorizado["id"], autor="paulo")
        self.assert_pede_senha()

    def test_bloqueado_pede_senha(self):
        self.banco.bloquear("cpf", BRUNO, "Motivo de teste", "ana")
        self.assert_pede_senha()

    def test_quem_entrou_com_outro_carro_pede_senha(self):
        self.banco.registrar_saidas([self.bruno], "19/10/2026 09:10",
                                    autor="paulo")
        visita = self.entrar(BRUNO, "Bruno Almeida", placa="XYZ9A87",
                             entrada="19/10/2026 09:20")
        self.assert_pede_senha(visita)

    def test_quem_nao_esta_na_lista_pede_senha(self):
        davi = self.entrar(DAVI, "Davi Souza")
        self.assert_pede_senha(davi)

    def test_autorizado_de_outra_placa_pede_senha(self):
        eva = self.entrar(EVA, "Eva Lima", placa="QWE1234",
                          entrada="19/10/2026 07:00")
        self.banco.adicionar_autorizado(EVA, DAVI, "Davi Souza", None,
                                        autor="ana")
        davi = self.entrar(DAVI, "Davi Souza")
        self.assert_pede_senha(davi)                       # não é do BRA2E19
        self.assertTrue(self.banco.buscar(eva))

    def test_desfazer_devolve_o_carro_ao_estacionamento(self):
        self.bruno_sai_com_o_carro()
        self.assertEqual(self.banco.desfazer_saidas(
            [self.bruno], autor="paulo", saida="19/10/2026 10:00"), 1)
        self.assertTrue(self.no_estacionamento())
        self.assertEqual(self.banco.buscar(self.bruno)["saida"], "")

    def test_consultas_da_tela(self):
        dia = self.agora.date()
        self.assertEqual(self.banco.contar_autorizados(dia), {"BRA2E19": 1})
        self.assertEqual(self.banco.contar_autorizados(date(2026, 10, 20)), {})
        levaveis = self.banco.veiculos_que_pode_levar(BRUNO, dia)
        self.assertEqual([e["placa"] for e in levaveis], ["BRA2E19"])
        self.assertEqual(levaveis[0]["autorizado"]["criado_por"], "ana")
        self.assertEqual(self.banco.veiculos_que_pode_levar(DAVI, dia), [])
        no_campus, = self.banco.autorizados_no_campus("BRA2E19", dia)
        self.assertEqual(no_campus["registro_id"], self.bruno)
        self.banco.bloquear("cpf", BRUNO, "Motivo de teste", "ana")
        self.assertEqual(self.banco.veiculos_que_pode_levar(BRUNO, dia), [])
        self.assertEqual(self.banco.autorizados_no_campus("BRA2E19", dia), [])


# ----------------------------------------------------------------------
# Tela
# ----------------------------------------------------------------------
class BaseAutorizadosNaTela(BaseInterface):
    entrar_como = "porteiro"

    def setUp(self):
        super().setUp()
        hora = (self.agora - timedelta(hours=2)).strftime("%d/%m/%Y %H:%M")
        self.carla = self.banco.inserir(
            registro(cpf=CARLA, nome="Carla Nogueira", placa="BRA2E19",
                     tipo="Professor", entrada=hora), autor="paulo")
        self.carro = self.banco.estadia_aberta(placa="BRA2E19")["id"]
        self.bruno = self.banco.inserir(
            registro(cpf=BRUNO, nome="Bruno Almeida", placa="",
                     tipo="Professor", entrada=hora), autor="paulo")
        self.app.atualizar_tabela()
        self.tela = self.app.tela_cadastro

    def carla_sai_a_pe(self):
        self.banco.registrar_saidas(
            [self.carla], (self.agora - timedelta(hours=1)).strftime(
                "%d/%m/%Y %H:%M"), autor="paulo")
        self.app.atualizar_tabela()

    def saida_rapida(self, texto):
        self.tela.campo_saida_rapida.insert(0, texto)
        self.tela.saida_rapida()


class TestSaidaComAutorizadoNaTela(BaseAutorizadosNaTela):
    def setUp(self):
        super().setUp()
        self.banco.adicionar_autorizado(CARLA, BRUNO, "Bruno Almeida", None,
                                        autor="paulo")       # Carla presente
        self.carla_sai_a_pe()

    def test_saida_pelo_cpf_pergunta_e_leva_o_carro_sem_senha(self):
        self.responder_veiculo = LEVA
        self.saida_rapida(BRUNO)
        self.assertEqual(self.perguntas_veiculo,
                         ["Vai levar o carro BRA2E19 de Carla?"])
        self.assertEqual(self.autorizacoes, [])             # sem senha
        self.assertIsNone(self.banco.estadia_aberta(placa="BRA2E19"))
        self.assertTrue(self.banco.buscar(self.bruno)["saida"])
        self.assertIn("levou o carro BRA2E19 de Carla",
                      self.tela.lbl_aviso.cget("text"))

    def test_nao_sai_a_pe_e_o_carro_fica(self):
        self.responder_veiculo = NAO_LEVA
        self.saida_rapida(BRUNO)
        self.assertTrue(self.banco.buscar(self.bruno)["saida"])
        self.assertIsNotNone(self.banco.estadia_aberta(placa="BRA2E19"))

    def test_cancelar_nao_grava_nada(self):
        self.responder_veiculo = None
        self.saida_rapida(BRUNO)
        self.assertEqual(self.banco.buscar(self.bruno)["saida"], "")

    def test_saida_pela_placa_pergunta_ao_autorizado_no_campus(self):
        self.responder_veiculo = LEVA
        self.saida_rapida("BRA2E19")
        self.assertEqual(self.perguntas_veiculo,
                         ["Vai levar o carro BRA2E19 de Carla?"])
        self.assertEqual(self.autorizacoes, [])
        self.assertIsNone(self.banco.estadia_aberta(placa="BRA2E19"))
        self.assertTrue(self.banco.buscar(self.bruno)["saida"])

    def test_pela_placa_sem_ninguem_levar_continua_pedindo_a_senha(self):
        self.respostas_veiculo(NAO_LEVA, None)    # não leva; cancela a senha
        self.saida_rapida("BRA2E19")
        self.assertEqual(self.perguntas_veiculo[-1], "O veículo só sai com o dono")
        self.assertIsNotNone(self.banco.estadia_aberta(placa="BRA2E19"))

    def test_desfazer_devolve_o_carro_e_a_pessoa(self):
        self.responder_veiculo = LEVA
        self.saida_rapida(BRUNO)
        self.tela.desfazer_saida()
        self.assertIsNotNone(self.banco.estadia_aberta(placa="BRA2E19"))
        self.assertEqual(self.banco.buscar(self.bruno)["saida"], "")

    def test_coluna_pode_retirar_na_lista_de_veiculos(self):
        self.tela.seletor_lista.selecionar("Veículos")
        linha = self.tela.tabela_veiculos.item(str(self.carro))
        self.assertEqual(linha["values"][4], 1)


class TestFichaQuemPodeRetirar(BaseAutorizadosNaTela):
    def abrir_ficha(self, cpf=CARLA):
        pessoas = self.app.tela_pessoas
        pessoas.atualizar()
        pessoa = self.banco.buscar_pessoa(cpf)
        pessoas.tabela.selection_set(str(pessoa["id"]))
        pessoas.ao_selecionar()
        pessoas.seletor_ficha.selecionar("Veículo")
        return pessoas

    def test_porteiro_adiciona_com_o_dono_no_campus(self):
        pessoas = self.abrir_ficha()
        self.assertTrue(pessoas.btn_adicionar_autorizado.ativo)
        dialogo = pessoas.adicionar_autorizado()
        dialogo.cpf.insert(0, BRUNO)
        self.assertEqual(dialogo.nome.get(), "Bruno Almeida")   # já veio
        dialogo.salvar()
        self.assertFalse(dialogo.janela.winfo_exists())
        self.assertEqual(len(pessoas.tabela_autorizados.get_children()), 1)
        linha = pessoas.tabela_autorizados.item(
            pessoas.tabela_autorizados.get_children()[0])
        self.assertEqual(linha["values"][1], "***.444.777-**")  # mascarado
        self.assertEqual(pessoas.seletor_ficha.itens["Veículo"][0].cget("text"),
                         "Veículo (1)")

    def test_porteiro_com_o_dono_fora_nao_adiciona(self):
        self.carla_sai_a_pe()
        pessoas = self.abrir_ficha()
        self.assertFalse(pessoas.btn_adicionar_autorizado.ativo)
        self.assertIn("dono precisa estar no campus",
                      pessoas.lbl_dono_fora.cget("text"))
        self.assertIsNone(pessoas.adicionar_autorizado())

    def test_dados_invalidos_ficam_no_dialogo(self):
        pessoas = self.abrir_ficha()
        dialogo = pessoas.adicionar_autorizado()
        dialogo.cpf.insert(0, CARLA)
        dialogo.nome.delete(0, "end")
        dialogo.nome.insert(0, "Carla Nogueira")
        dialogo.salvar()
        self.assertIn("próprio carro", dialogo.lbl_erro.cget("text"))
        self.assertEqual(self.banco.listar_autorizados("BRA2E19"), [])
        dialogo.fechar()

    def test_remover_pede_confirmacao_e_vai_ao_historico(self):
        self.banco.adicionar_autorizado(CARLA, BRUNO, "Bruno Almeida", None,
                                        autor="paulo")
        pessoas = self.abrir_ficha()
        pessoas.tabela_autorizados.selection_set(
            pessoas.tabela_autorizados.get_children()[0])
        pessoas.remover_autorizado()
        self.assertEqual(self.banco.listar_autorizados("BRA2E19"), [])
        self.assertIn(("paulo", dados.AUTORIZADO_REMOVIDO), self.acoes())

    def test_pessoa_sem_placa_mostra_sem_veiculo(self):
        pessoas = self.abrir_ficha(BRUNO)
        self.assertIn("Sem veículo", pessoas.lbl_veiculo.cget("text"))
        self.assertFalse(pessoas.botoes_veiculo.winfo_manager())


class TestFichaComoAdministrador(BaseAutorizadosNaTela):
    entrar_como = "admin"

    def test_administrador_adiciona_com_o_dono_fora_e_com_validade(self):
        self.carla_sai_a_pe()
        pessoas = self.app.tela_pessoas
        pessoas.atualizar()
        pessoas.tabela.selection_set(str(self.banco.buscar_pessoa(CARLA)["id"]))
        pessoas.ao_selecionar()
        self.assertTrue(pessoas.btn_adicionar_autorizado.ativo)
        dialogo = pessoas.adicionar_autorizado()
        dialogo.cpf.insert(0, DAVI)
        dialogo.nome.insert(0, "Davi Souza")
        dialogo.validade.insert(0, "31/12/2026")
        dialogo.salvar()
        autorizado, = self.banco.listar_autorizados("BRA2E19")
        self.assertEqual(autorizado["valido_ate"], date(2026, 12, 31))
        linha = pessoas.tabela_autorizados.item(str(autorizado["id"]))
        self.assertEqual(linha["values"][2], "até 31/12/2026")


if __name__ == "__main__":
    unittest.main()
