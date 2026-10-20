"""Testa as peças de tela de componentes.py (janela oculta)."""

import tkinter as tk
import unittest

from portaria import componentes


class TestComponentes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.raiz = tk.Tk()
        except tk.TclError:
            raise unittest.SkipTest("sem tela disponível para o Tkinter")
        cls.raiz.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.raiz.destroy()

    def setUp(self):
        self.pai = tk.Frame(self.raiz)
        self.addCleanup(self.pai.destroy)

    def digitar(self, caixa, texto):
        for letra in texto:
            caixa.insert(tk.END, letra)
        return caixa.get()

    def test_entrada_numeros_so_aceita_digitos_ate_o_limite(self):
        caixa = componentes.entrada_numeros(self.pai, 4)
        self.assertEqual(self.digitar(caixa, "1a2-345"), "1234")

    def test_entrada_placa_maiuscula_e_restrita(self):
        caixa, var = componentes.entrada_placa(self.pai)
        self.assertEqual(self.digitar(caixa, "abc-1d234"), "ABC1D23")
        self.assertEqual(var.get(), "ABC1D23")

    def test_entrada_placa_sem_restricao_so_poe_maiuscula(self):
        caixa, var = componentes.entrada_placa(
            self.pai, tk.StringVar(value="xyz"), restringir=False)
        self.assertEqual(self.digitar(caixa, "-1"), "XYZ-1")

    def test_campo_tem_rotulo_e_caixa(self):
        grupo, caixa = componentes.campo(self.pai, "Nome completo")
        textos = [w.cget("text") for w in grupo.winfo_children()
                  if "text" in w.keys()]
        self.assertEqual(textos, ["Nome completo"])
        self.assertIs(caixa.master, grupo)

    def test_tabela_com_e_sem_rolagem(self):
        colunas = [("a", "A", 50, "w"), ("b", "B", 50, "center")]
        quadro, tab = componentes.tabela(self.pai, colunas)
        self.assertEqual(tab["columns"], ("a", "b"))
        self.assertEqual(len(quadro.winfo_children()), 2)     # tabela + rolagem
        quadro, tab = componentes.tabela(self.pai, colunas, rolagem=False)
        self.assertEqual(len(quadro.winfo_children()), 1)

    def test_tabela_de_eventos(self):
        _, tab = componentes.tabela_eventos(self.pai, (10, 10, 10, 10), 3)
        evento = {"momento": "m", "usuario": "u", "acao": "a", "detalhe": "d"}
        componentes.preencher_eventos(tab, [evento, evento])
        componentes.preencher_eventos(tab, [evento])          # substitui
        linhas = tab.get_children()
        self.assertEqual(len(linhas), 1)
        self.assertEqual(tab.item(linhas[0])["values"], ["m", "u", "a", "d"])

    def test_cartao_com_e_sem_faixa(self):
        caixa, miolo = componentes.cartao(self.pai)
        self.assertEqual(len(caixa.winfo_children()), 2)      # faixa + miolo
        caixa, miolo = componentes.cartao(self.pai, faixa=False)
        self.assertEqual(caixa.winfo_children(), [miolo])


if __name__ == "__main__":
    unittest.main()
