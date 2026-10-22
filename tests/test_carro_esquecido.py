"""
Versão 2.2 — V2 / RN36: alerta de "carro esquecido" antes do fechamento
(dentro da janela de aviso que já existe), com relógio fixo.
"""

import unittest
from datetime import datetime, timedelta

from portaria import horarios

from .test_dados import registro
from .test_interface import BaseInterface

QUARTA = datetime(2026, 10, 21)        # fecha às 23:00, aviso de 30 min


def estadia(dentro=False, entrada="21/10/2026 20:00", tipo="Professor"):
    return {"placa": "BRA2E19", "nome": "Carla Nogueira", "tipo": tipo,
            "entrada": entrada, "responsavel_dentro": dentro}


class TestCarrosEsquecidosPuros(unittest.TestCase):
    def setUp(self):
        self.config = horarios.configuracao_padrao()

    def test_so_dentro_da_janela_de_aviso(self):
        fora_da_janela = QUARTA.replace(hour=22, minute=29)
        dentro = QUARTA.replace(hour=22, minute=40)
        self.assertEqual(horarios.carros_esquecidos(
            self.config, [estadia()], fora_da_janela), [])
        self.assertEqual(len(horarios.carros_esquecidos(
            self.config, [estadia()], dentro)), 1)
        self.assertEqual(horarios.aviso_carros_esquecidos(
            self.config, [estadia(), estadia()], dentro),
            "2 carros com o dono fora do campus — fechamento às 23:00")
        self.assertEqual(horarios.aviso_carros_esquecidos(
            self.config, [estadia()], dentro),
            "1 carro com o dono fora do campus — fechamento às 23:00")

    def test_dono_no_campus_ou_carro_pendente_nao_contam(self):
        dentro = QUARTA.replace(hour=22, minute=40)
        self.assertEqual(horarios.carros_esquecidos(
            self.config, [estadia(dentro=True)], dentro), [])
        ontem = estadia(entrada="20/10/2026 08:00")      # já é pendente
        self.assertEqual(horarios.carros_esquecidos(self.config, [ontem],
                                                    dentro), [])

    def test_sem_aviso_configurado_nao_avisa(self):
        self.config.minutos_aviso = 0
        self.assertEqual(horarios.aviso_carros_esquecidos(
            self.config, [estadia()], QUARTA.replace(hour=22, minute=40)), "")


class TestFaixaDoCarroEsquecido(BaseInterface):
    entrar_como = "porteiro"

    def setUp(self):
        super().setUp()
        self.agora = QUARTA.replace(hour=22, minute=0)
        self.carla = self.banco.inserir(registro(
            cpf="52998224725", nome="Carla Nogueira", placa="BRA2E19",
            tipo="Professor", entrada="21/10/2026 20:00"), autor="paulo")
        self.banco.registrar_saidas([self.carla], "21/10/2026 21:00",
                                    autor="paulo")      # saiu a pé
        self.tela = self.app.tela_cadastro
        self.app.atualizar_tabela()

    def faixa(self):
        return self.tela.faixa_esquecidos

    def test_aparece_so_na_janela_de_aviso_e_leva_aos_veiculos(self):
        self.assertFalse(self.faixa().winfo_manager())      # 22:00: cedo
        self.agora = QUARTA.replace(hour=22, minute=40)
        self.tela.ao_passar_o_tempo()
        self.assertTrue(self.faixa().winfo_manager())
        self.assertEqual(self.faixa().lbl.cget("text"),
                         "1 carro com o dono fora do campus — fechamento às "
                         "23:00")
        self.faixa().comando()                              # "Ver veículos"
        self.assertEqual(self.tela.lista, "Veículos")

    def test_some_quando_o_dono_volta(self):
        self.agora = QUARTA.replace(hour=22, minute=40)
        self.tela.ao_passar_o_tempo()
        self.assertTrue(self.faixa().winfo_manager())
        self.banco.inserir(registro(cpf="52998224725", nome="Carla Nogueira",
                                    placa="", tipo="Professor",
                                    entrada="21/10/2026 22:40"), autor="paulo")
        self.app.atualizar_tabela()
        self.assertFalse(self.faixa().winfo_manager())

    def test_some_quando_o_carro_sai(self):
        self.agora = QUARTA.replace(hour=22, minute=45)
        self.app.atualizar_tabela()
        self.assertTrue(self.faixa().winfo_manager())
        self.autorizar_com_senha()
        self.tela.campo_saida_rapida.insert(0, "BRA2E19")
        self.tela.saida_rapida()
        self.assertIsNone(self.banco.estadia_aberta(placa="BRA2E19"))
        self.assertFalse(self.faixa().winfo_manager())


if __name__ == "__main__":
    unittest.main()
