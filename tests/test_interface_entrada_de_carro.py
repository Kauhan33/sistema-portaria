"""
Tela, rodada 5: a pergunta "de carro ou a pé?" na entrada de quem tem placa
cadastrada (RN34). Relógio do app fixo (AGORA, uma quarta-feira às 10:00).
"""

from datetime import timedelta

from portaria.tela_veiculo import A_PE, COM_CARRO, OUTRO_CARRO

from .test_interface import AGORA, VISITA_ANTIGA, BaseInterface

BETO = "11144477735"
ANA = "52998224725"


# ----------------------------------------------------------------------
# RN34: "vai entrar de carro?" para quem tem placa cadastrada
# ----------------------------------------------------------------------
class TestEntradaDeCarroOuAPe(BaseInterface):
    entrar_como = "porteiro"

    def setUp(self):
        super().setUp()
        self.banco.inserir(dict(VISITA_ANTIGA))       # Beto veio de QWE1234
        self.tela = self.app.tela_cadastro
        self.vistos = []

    def responder(self, valor):
        """Responde a pergunta e guarda o título, o botão do Enter e a
        variante de cada botão."""
        def responder(dialogo):
            botoes = {texto: variante for texto, _, variante in dialogo.opcoes}
            self.vistos.append((dialogo.janela.title(), dialogo.padrao, botoes))
            if valor == "enter":
                dialogo.escolher(dialogo.padrao)
            elif valor is not None:
                dialogo.escolher(valor)
        self.responder_veiculo = responder

    def entrar_pelo_cpf(self, cpf=BETO):
        self.app.limpar()
        self.app.cpf.insert(0, cpf)
        self.app.cadastrar()

    def ultima(self):
        return max(self.no_banco(), key=lambda r: r["id"])

    def test_de_carro_abre_a_estadia(self):
        self.responder(COM_CARRO)
        self.entrar_pelo_cpf()
        self.assertEqual(self.perguntas_veiculo, ["Beto vai entrar de carro?"])
        self.assertEqual(self.ultima()["placa"], "QWE1234")
        self.assertEqual(self.banco.estadia_aberta(placa="QWE1234")["cpf"], BETO)

    def test_a_pe_entra_sem_placa_e_nao_abre_estadia(self):
        self.responder(A_PE)
        self.entrar_pelo_cpf()
        self.assertEqual(len(self.no_banco()), 2)
        self.assertEqual(self.ultima()["placa"], "")
        self.assertIsNone(self.banco.estadia_aberta(placa="QWE1234"))

    def test_cancelar_nao_grava(self):
        self.responder(None)
        self.entrar_pelo_cpf()
        self.assertEqual(len(self.no_banco()), 1)
        self.assertIsNone(self.banco.estadia_aberta(placa="QWE1234"))

    def test_com_outro_carro_volta_ao_campo_placa(self):
        self.responder(OUTRO_CARRO)
        self.entrar_pelo_cpf()
        self.assertEqual(len(self.no_banco()), 1)
        self.assertEqual(self.app.var_placa.get(), "")
        self.app.var_placa.set("XYZ9A87")             # digita a outra
        self.app.cadastrar()
        self.assertEqual(len(self.perguntas_veiculo), 1)   # não pergunta de novo
        self.assertEqual(self.ultima()["placa"], "XYZ9A87")

    def test_enter_destaca_de_carro_se_a_ultima_visita_foi_de_carro(self):
        self.responder("enter")
        self.entrar_pelo_cpf()
        titulo, padrao, botoes = self.vistos[0]
        self.assertEqual(padrao, COM_CARRO)
        self.assertEqual(botoes["De carro — QWE-1234"], "primario")
        self.assertEqual(botoes["A pé"], "secundario")
        self.assertEqual(self.ultima()["placa"], "QWE1234")

    def test_enter_destaca_a_pe_se_a_ultima_visita_foi_a_pe(self):
        self.banco.inserir(dict(VISITA_ANTIGA, placa="",
                                entrada="16/10/2026 07:00",
                                saida="16/10/2026 12:00"))
        self.responder("enter")
        self.entrar_pelo_cpf()
        _, padrao, botoes = self.vistos[0]
        self.assertEqual(padrao, A_PE)
        self.assertEqual(botoes["A pé"], "primario")
        self.assertEqual(self.ultima()["placa"], "")

    def test_vindo_da_pagina_pessoas_tambem_pergunta(self):
        pessoas = self.app.tela_pessoas
        pessoas.atualizar()
        pessoa = self.banco.buscar_pessoa(BETO)
        pessoas.tabela.selection_set(str(pessoa["id"]))
        pessoas.ao_selecionar()
        pessoas.registrar_entrada()                   # leva ao formulário
        self.responder(COM_CARRO)
        self.app.cadastrar()
        self.assertEqual(self.perguntas_veiculo, ["Beto vai entrar de carro?"])
        self.assertIsNotNone(self.banco.estadia_aberta(placa="QWE1234"))

    def test_placa_digitada_a_mao_nao_pergunta(self):
        self.app.limpar()
        self.app.cpf.insert(0, BETO)
        self.app.var_placa.set("XYZ9A87")             # trocou a sugerida
        self.app.cadastrar()
        self.assertEqual(self.perguntas_veiculo, [])
        self.assertEqual(self.ultima()["placa"], "XYZ9A87")

    def test_placa_apagada_a_mao_nao_pergunta_e_entra_a_pe(self):
        self.app.limpar()
        self.app.cpf.insert(0, BETO)
        self.app.var_placa.set("")
        self.app.cadastrar()
        self.assertEqual(self.perguntas_veiculo, [])
        self.assertEqual(self.ultima()["placa"], "")

    def test_carro_ja_no_estacionamento_nao_pergunta(self):
        self.responder(COM_CARRO)
        self.entrar_pelo_cpf()                        # entra de carro
        self.responder(A_PE)
        self.tela.campo_saida_rapida.insert(0, BETO)
        self.tela.saida_rapida()                      # sai a pé, carro fica
        self.agora = AGORA + timedelta(minutes=30)
        self.perguntas_veiculo.clear()
        self.app.limpar()
        self.app.cpf.insert(0, BETO)                  # volta a pé
        self.assertIn("O carro QWE-1234 está no estacionamento",
                      self.app.lbl_pessoa.cget("text"))
        self.app.cadastrar()
        self.assertEqual(self.perguntas_veiculo, [])
        self.assertEqual(self.ultima()["placa"], "")

    def test_sem_placa_cadastrada_nao_pergunta(self):
        self.banco.inserir({"nome": "Ana Silva", "cpf": ANA,
                            "celular": "31987654321", "placa": "",
                            "tipo": "Visitante", "entrada": "15/10/2026 08:00",
                            "saida": "15/10/2026 09:00"})
        self.entrar_pelo_cpf(ANA)
        self.assertEqual(self.perguntas_veiculo, [])
        self.assertEqual(len(self.no_banco()), 3)

    def test_de_carro_com_placa_bloqueada_e_recusado(self):
        self.banco.bloquear("placa", "QWE1234", "Carro com restrição",
                            "ana.admin")
        self.responder(COM_CARRO)
        self.entrar_pelo_cpf()
        self.assertEqual(len(self.no_banco()), 1)
        self.assertIn("Acesso negado", self.msg.showerror.call_args[0][0])
