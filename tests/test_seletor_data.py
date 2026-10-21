"""Seletor de data e hora (calendário + relógio desenhados no Canvas)."""

import tkinter as tk
import unittest
from datetime import date, datetime
from types import SimpleNamespace

from portaria import componentes, estilo
from portaria import seletor_data as s

AGORA = datetime(2026, 10, 21, 10, 7)
# notebook 1366x768 a 125%: área útil de uns 1366x670 px
TELA_PEQUENA = (0, 0, 1366, 670)


class TestContasDoMostrador(unittest.TestCase):
    R = 100

    def test_horas_no_anel_de_fora_e_no_de_dentro(self):
        fora, dentro = self.R * s.ANEL_FORA, self.R * s.ANEL_DENTRO
        self.assertEqual(s.hora_no_ponto(0, -fora, self.R), 0)      # em cima
        self.assertEqual(s.hora_no_ponto(fora, 0, self.R), 3)       # direita
        self.assertEqual(s.hora_no_ponto(0, fora, self.R), 6)
        self.assertEqual(s.hora_no_ponto(0, -dentro, self.R), 12)
        self.assertEqual(s.hora_no_ponto(-dentro, 0, self.R), 21)
        self.assertEqual(s.hora_no_ponto(0, dentro, self.R), 18)

    def test_minutos_pelo_angulo_com_ajuste_fino(self):
        self.assertEqual(s.minuto_no_ponto(0, -80), 0)
        self.assertEqual(s.minuto_no_ponto(80, 0), 15)
        self.assertEqual(s.minuto_no_ponto(0, 80), 30)
        dx, dy = s.ponto_no_mostrador(17, 60, self.R, s.ANEL_FORA)
        self.assertEqual(s.minuto_no_ponto(dx, dy), 17)

    POPUP = (375, 450)                            # o pop-up a 125%

    def test_abre_embaixo_do_campo(self):
        self.assertEqual(s.posicao_na_tela((100, 200, 290, 45), (300, 400),
                                           (0, 0, 1920, 1040)),
                         (100, 200 + 45 + s.FOLGA))

    def test_sem_espaco_embaixo_abre_em_cima(self):
        x, y = s.posicao_na_tela((100, 560, 290, 45), self.POPUP, (0, 0, 1366, 1040))
        self.assertEqual(y, 1040 - 1040 + 560 - 450 - s.FOLGA)

    def test_tela_baixa_abre_ao_lado_sem_cobrir_o_campo(self):
        x, y = s.posicao_na_tela((830, 295, 230, 45), self.POPUP, TELA_PEQUENA)
        self.assertEqual(x, 830 - 375 - s.FOLGA)               # à esquerda
        self.assertLessEqual(y + 450, 670)
        x, y = s.posicao_na_tela((340, 295, 230, 45), self.POPUP, TELA_PEQUENA)
        self.assertEqual(x, 340 + 230 + s.FOLGA)               # à direita

    def test_nunca_sai_da_tela(self):
        casos = [(1300, 300), (-50, 5), (1200, 640), (600, 250), (0, 600)]
        largura, altura = self.POPUP
        for x, y in casos:
            with self.subTest(x=x, y=y):
                px_, py_ = s.posicao_na_tela((x, y, 230, 45), self.POPUP,
                                             TELA_PEQUENA)
                self.assertGreaterEqual(px_, 0)
                self.assertGreaterEqual(py_, 0)
                self.assertLessEqual(px_ + largura, 1366)
                self.assertLessEqual(py_ + altura, 670)

    def test_cabe_em_1366x670_a_125(self):
        self.assertLessEqual(round(s.ALTURA * 1.25) + 2, 670)
        self.assertLessEqual(round(s.LARGURA * 1.25) + 2, 1366)

    def test_le_o_que_ja_esta_no_campo(self):
        self.assertEqual(s.ler_valor("03/11/2025 18:30", s.DATA_HORA, AGORA),
                         datetime(2025, 11, 3, 18, 30))
        self.assertEqual(s.ler_valor("lixo", s.DATA_HORA, AGORA), AGORA)
        self.assertEqual(s.ler_valor("07:30", s.HORA, AGORA),
                         AGORA.replace(hour=7, minute=30))


class TestPopUp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.raiz = tk.Tk()
        except tk.TclError:
            raise unittest.SkipTest("sem tela disponível para o Tkinter")
        estilo.aplicar_tema(cls.raiz)
        cls.raiz.geometry("+200+200")

    @classmethod
    def tearDownClass(cls):
        cls.raiz.destroy()

    def setUp(self):
        self.pai = tk.Frame(self.raiz)
        self.pai.pack()
        self.addCleanup(self.pai.destroy)
        self.addCleanup(componentes.fechar_seletor)
        self.escolhidos = []

    def campo(self, modo, texto=""):
        campo = componentes.Campo(self.pai, seletor=modo, relogio=lambda: AGORA,
                                  ao_escolher=lambda: self.escolhidos.append(1))
        campo.pack()
        campo.entrada.insert(0, texto)
        self.raiz.update_idletasks()
        campo.abrir_seletor()
        return campo, campo.seletor_aberto

    def test_data_e_hora_calendario_depois_relogio(self):
        campo, pop = self.campo(s.DATA_HORA)
        self.assertEqual((pop.etapa, pop.mes), (s.CALENDARIO, (2026, 10)))
        self.assertTrue(pop.cv.find_withtag("d2026-10-21"))       # hoje
        pop.mudar_mes(1)
        pop.mudar_mes(1)
        pop.mudar_mes(1)
        self.assertEqual(pop.mes, (2027, 1))
        pop.mudar_ano(-2)
        self.assertEqual(pop.mes, (2025, 1))
        pop.escolher_dia(date(2025, 1, 31))
        self.assertEqual(pop.etapa, s.HORAS)
        dx, dy = s.ponto_no_mostrador(6, 12, estilo.px(s.RAIO), s.ANEL_DENTRO)
        pop._clique_hora(dx, dy)                         # clique no 18
        self.assertEqual((pop.etapa, pop.valor.hour), (s.MINUTOS, 18))
        pop.escolher_minuto(35)
        pop.ajustar_minuto(1)
        pop.confirmar()
        self.assertEqual(campo.entrada.get(), "31/01/2025 18:36")
        self.assertFalse(pop.existe())
        self.assertEqual(self.escolhidos, [1])

    def test_so_data_e_so_hora(self):
        campo, pop = self.campo(s.DATA)
        pop.escolher_dia(date(2026, 12, 25))
        self.assertEqual(campo.entrada.get(), "25/12/2026")
        campo, pop = self.campo(s.HORA, "07:30")
        self.assertEqual((pop.etapa, pop.valor.hour, pop.valor.minute),
                         (s.HORAS, 7, 30))
        pop.escolher_hora(22)
        pop.confirmar()
        self.assertEqual(campo.entrada.get(), "22:30")

    def test_agora_usa_o_relogio_do_app(self):
        campo, pop = self.campo(s.DATA_HORA, "01/01/2020 08:00")
        self.assertEqual(pop.mes, (2020, 1))                  # abre no valor
        pop.agora()
        self.assertEqual(campo.entrada.get(), "21/10/2026 10:07")

    def test_esc_fecha_sem_mudar_o_campo(self):
        campo, pop = self.campo(s.DATA_HORA, "01/01/2020 08:00")
        self.assertEqual(campo._tecla_com_seletor(
            SimpleNamespace(keysym="Escape")), "break")
        self.assertFalse(pop.existe())
        self.assertEqual(campo.entrada.get(), "01/01/2020 08:00")

    def test_digitar_fecha_e_continua_digitando(self):
        campo, pop = self.campo(s.DATA_HORA)
        self.assertIsNone(campo._tecla_com_seletor(SimpleNamespace(keysym="2")))
        self.assertFalse(pop.existe())

    def test_clique_fora_fecha(self):
        campo, pop = self.campo(s.DATA)
        componentes._clique_fora_do_seletor(SimpleNamespace(widget=campo.entrada))
        self.assertTrue(pop.existe())                       # no próprio campo
        componentes._clique_fora_do_seletor(SimpleNamespace(widget=self.pai))
        self.assertFalse(pop.existe())

    def test_um_pop_up_por_vez_e_dentro_da_tela(self):
        campo1, pop1 = self.campo(s.DATA)
        campo2, pop2 = self.campo(s.HORA)
        self.assertFalse(pop1.existe())
        x0, y0, x1, y1 = s.area_util(pop2.janela)
        x, y = pop2.posicao
        self.assertTrue(x0 <= x and x + pop2.janela.winfo_reqwidth() <= x1)
        self.assertTrue(y0 <= y and y + pop2.janela.winfo_reqheight() <= y1)

    def test_campo_desativado_nao_abre(self):
        campo = componentes.Campo(self.pai, seletor=s.HORA)
        campo.entrada.config(state="disabled")
        campo.abrir_seletor()
        self.assertIsNone(campo.seletor_aberto)


if __name__ == "__main__":
    unittest.main()
