"""
Versão 2.2 — V3 / RN37: lotação do estacionamento (vagas, aviso com
confirmação, "Bloquear quando lotado" com a senha do administrador),
conferida também no banco.
"""

import os
import tempfile
import unittest
from datetime import datetime, timedelta

from portaria import dados, veiculos
from portaria.senhas import gerar_hash

from .test_dados import registro
from .test_interface import BaseInterface

PLACAS = ["ABC1234", "BRA2E19", "QWE1234", "XYZ9A87"]
CPFS = ["52998224725", "11144477735", "39053344705", "86288366757"]


class TestLotacaoPura(unittest.TestCase):
    def test_contagem_e_limite_exato(self):
        self.assertFalse(veiculos.esta_lotado(49, 50))
        self.assertTrue(veiculos.esta_lotado(50, 50))           # 50/50
        self.assertTrue(veiculos.esta_lotado(51, 50))
        self.assertEqual(veiculos.texto_lotacao(47, 50), "Estacionamento 47/50")
        self.assertEqual(veiculos.regra_lotado(50, 50),
                         "Estacionamento lotado (50/50)")

    def test_zero_vagas_desliga_o_controle(self):
        self.assertFalse(veiculos.esta_lotado(300, 0))
        self.assertEqual(veiculos.texto_lotacao(300, 0), "")

    def test_ler_vagas(self):
        self.assertEqual(veiculos.ler_vagas(" 50 "), (50, ""))
        self.assertEqual(veiculos.ler_vagas("0"), (0, ""))
        self.assertEqual(veiculos.ler_vagas("9999"), (9999, ""))
        for errado in ("", "-1", "10000", "5a", "1.5"):
            with self.subTest(errado=errado):
                valor, erro = veiculos.ler_vagas(errado)
                self.assertIsNone(valor)
                self.assertIn("0 a 9999", erro)


class TestLotacaoNoBanco(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.banco = dados.Banco(os.path.join(self.pasta.name, "portaria.db"),
                                 relogio=lambda: datetime(2026, 10, 19, 10, 0))
        self.banco.criar_usuario("Ana Admin", "ana", "admin",
                                 gerar_hash("senha-da-ana"))
        self.banco.criar_usuario("Paulo Porteiro", "paulo", "porteiro", "h",
                                 autor="ana", trocar_senha=False)

    def tearDown(self):
        self.pasta.cleanup()

    def entrar(self, i, **extra):
        return self.banco.inserir(registro(cpf=CPFS[i], placa=PLACAS[i],
                                           entrada="19/10/2026 08:00"),
                                  autor="paulo", **extra)

    def acoes(self):
        return [e["acao"] for e in self.banco.listar_eventos()]

    def test_comeca_sem_controle(self):
        for i in range(3):
            self.entrar(i)
        self.assertEqual(self.banco.ocupacao_estacionamento(), (3, 0, False))

    def test_lotado_so_entra_com_a_confirmacao(self):
        self.banco.salvar_lotacao(2, False, autor="ana")
        self.entrar(0)
        self.entrar(1)
        with self.assertRaises(dados.ErroDados) as erro:
            self.entrar(2)
        self.assertIn("Estacionamento lotado (2/2)", str(erro.exception))
        self.assertEqual(len(self.banco.listar()), 2)
        self.entrar(2, lotado_confirmado=True)
        self.assertIn(dados.LOTACAO_CONFIRMADA, self.acoes())
        # a pé não conta como carro
        self.banco.inserir(registro(cpf=CPFS[3], placa="",
                                    entrada="19/10/2026 08:00"), autor="paulo")

    def test_bloquear_quando_lotado_exige_a_senha(self):
        self.banco.salvar_lotacao(1, True, autor="ana")
        self.entrar(0)
        pedido = {"autorizado_por": "ana", "regras": ["lotado"],
                  "justificativa": "Evento da reitoria hoje"}
        casos = [dict(lotado_confirmado=True),
                 dict(autorizacao_lotacao=dict(pedido, com_senha=True)),
                 dict(autorizacao_lotacao=dict(pedido, senha="errada"))]
        for extra in casos:
            with self.subTest(extra=extra):
                with self.assertRaises(dados.ErroDados):
                    self.entrar(1, **extra)
        self.entrar(1, autorizacao_lotacao=dict(pedido, senha="senha-da-ana"))
        evento = next(e for e in self.banco.listar_eventos()
                      if e["acao"] == dados.LOTACAO_LIBERADA)
        self.assertEqual(evento["usuario"], "ana")
        self.assertIn("Estacionamento lotado (1/1)".lower(),
                      evento["detalhe"].lower())
        self.assertIn("Operador: paulo", evento["detalhe"])

    def test_so_administrador_muda_e_vai_ao_historico(self):
        with self.assertRaises(dados.ErroDados):
            self.banco.salvar_lotacao(50, False, autor="paulo")
        for errado in (-1, 10_000, "50", True):
            with self.assertRaises(dados.ErroDados):
                self.banco.salvar_lotacao(errado, False, autor="ana")
        self.assertEqual(self.banco.salvar_lotacao(50, True, autor="ana"), 2)
        self.assertEqual(self.banco.salvar_lotacao(50, True, autor="ana"), 0)
        config = self.banco.ler_configuracao()
        self.assertEqual((config.vagas, config.bloquear_lotado), (50, True))
        detalhe = next(e["detalhe"] for e in self.banco.listar_eventos()
                       if e["acao"] == "Configuração alterada")
        self.assertIn("Vagas: 0 → 50", detalhe)


class TestLotacaoNaTela(BaseInterface):
    entrar_como = "porteiro"

    def setUp(self):
        super().setUp()
        self.banco.salvar_lotacao(2, False, autor="ana.admin")
        hora = (self.agora - timedelta(hours=1)).strftime("%d/%m/%Y %H:%M")
        for i in range(2):
            self.banco.inserir(registro(cpf=CPFS[i], placa=PLACAS[i],
                                        tipo="Professor", entrada=hora),
                               autor="paulo")
        self.app.atualizar_tabela()
        self.tela = self.app.tela_cadastro

    def entrar_de_carro(self):
        self.preencher(cpf=CPFS[2], placa=PLACAS[2], tipo="Professor")
        self.app.cadastrar()

    def test_cabecalho_mostra_a_ocupacao(self):
        self.assertTrue(self.tela.lbl_estacionamento.cget("text").endswith(
            "Estacionamento 2/2"))

    def test_lotado_avisa_e_pede_confirmacao(self):
        self.msg.askyesno.return_value = False
        self.entrar_de_carro()
        titulo, texto = self.msg.askyesno.call_args[0][:2]
        self.assertEqual(titulo, "Estacionamento lotado")
        self.assertIn("Estacionamento lotado (2/2)", texto)
        self.assertEqual(len(self.no_banco()), 2)
        self.msg.askyesno.return_value = True
        self.app.cadastrar()
        self.assertEqual(len(self.no_banco()), 3)
        self.assertTrue(self.tela.lbl_estacionamento.cget("text").endswith(
            "Estacionamento 3/2"))

    def test_bloquear_quando_lotado_pede_a_senha(self):
        self.banco.salvar_lotacao(2, True, autor="ana.admin")
        self.entrar_de_carro()                       # cancelou a senha
        self.assertEqual(len(self.no_banco()), 2)
        self.assertTrue(self.autorizacoes[0].pede_senha)
        self.autorizar_com_senha(justificativa="Evento com convidados")
        self.app.cadastrar()
        self.assertEqual(len(self.no_banco()), 3)
        self.assertIn(("ana.admin", dados.LOTACAO_LIBERADA), self.acoes())

    def test_sem_controle_nao_mostra_nada(self):
        self.banco.salvar_lotacao(0, False, autor="ana.admin")
        self.app.atualizar_tabela()
        self.assertEqual(self.tela.lbl_estacionamento.cget("text"), "")
        self.entrar_de_carro()
        self.assertEqual(len(self.no_banco()), 3)
        self.msg.askyesno.assert_not_called()


class TestLotacaoEmConfiguracoes(BaseInterface):
    def test_salva_vagas_e_bloquear(self):
        pagina = self.app.tela_configuracoes
        self.assertEqual(pagina.vagas.get(), "0")
        pagina.vagas.delete(0, "end")
        for digito in "123456":                         # para em 4 dígitos
            pagina.vagas.insert("end", digito)
        self.assertEqual(pagina.vagas.get(), "1234")
        pagina.vagas.delete(0, "end")
        pagina.vagas.insert(0, "50")
        pagina.alternador_lotado.alternar()
        pagina.salvar_funcionamento()
        config = self.banco.ler_configuracao()
        self.assertEqual((config.vagas, config.bloquear_lotado), (50, True))
        self.assertIn("Salvo", pagina.faixa_funcionamento.lbl.cget("text"))

    def test_vagas_vazias_sao_recusadas(self):
        pagina = self.app.tela_configuracoes
        pagina.vagas.delete(0, "end")
        pagina.salvar_funcionamento()
        self.assertIn("Vagas", pagina.faixa_funcionamento.lbl.cget("text"))


if __name__ == "__main__":
    unittest.main()
