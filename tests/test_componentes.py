"""Testa as peças de tela de componentes.py (janela oculta)."""

import tkinter as tk
import unittest
from datetime import datetime

from portaria import componentes, estilo
from portaria.estilo import COR, ESTADO


class TestComponentes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.raiz = tk.Tk()
        except tk.TclError:
            raise unittest.SkipTest("sem tela disponível para o Tkinter")
        cls.raiz.withdraw()
        estilo.aplicar_tema(cls.raiz)

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

    # --- campos e restrições de digitação (as mesmas em todas as telas)
    def test_campo_numeros_so_aceita_digitos_ate_o_limite(self):
        campo = componentes.Campo(self.pai, numeros=4)
        self.assertEqual(self.digitar(campo.entrada, "1a2-345"), "1234")
        self.assertEqual(campo.var.get(), "1234")

    def test_campo_placa_maiuscula_e_restrita(self):
        campo = componentes.Campo(self.pai, placa=True)
        self.assertEqual(self.digitar(campo.entrada, "abc-1d234"), "ABC1D23")
        self.assertEqual(campo.var.get(), "ABC1D23")

    def test_campo_aceita_var_de_fora_e_valor_inicial(self):
        var = tk.StringVar(value="ABC1234")
        campo = componentes.Campo(self.pai, placa=True, var=var)
        self.assertEqual(campo.entrada.get(), "ABC1234")

    def test_campo_senha_esconde_o_texto(self):
        campo = componentes.Campo(self.pai, senha=True)
        self.assertEqual(campo.entrada.cget("show"), "•")

    def test_campo_lista_de_escolha(self):
        campo = componentes.Campo(self.pai, opcoes=["Aluno", "Visitante"])
        campo.entrada.set("Visitante")
        self.assertEqual(campo.entrada.get(), "Visitante")
        self.assertEqual(str(campo.entrada.cget("state")), "readonly")

    def test_dica_de_campo_vazio_some_ao_digitar(self):
        campo = componentes.Campo(self.pai, dica_vazio="CPF ou placa")
        self.assertEqual(campo.lbl_vazio.winfo_manager(), "place")
        campo.entrada.insert(0, "1")
        self.assertEqual(campo.lbl_vazio.winfo_manager(), "")
        self.assertEqual(campo.entrada.get(), "1")   # a dica não é texto do campo

    def test_icone_do_campo_executa_a_acao(self):
        chamado = []
        campo = componentes.Campo(self.pai, icone="x",
                                  acao_icone=lambda: chamado.append(1))
        self.assertEqual(campo.lbl_icone.cget("text"), "x")
        self.assertTrue(campo.lbl_icone.bind("<Button-1>"))
        campo.usar_icone()
        self.assertEqual(chamado, [1])

    def test_campo_rotulado_tem_rotulo_e_apoio(self):
        grupo, campo = componentes.campo_rotulado(self.pai, "Entrada",
                                               "dd/mm/aaaa hh:mm")
        textos = []
        for filho in grupo.winfo_children():
            textos += [w.cget("text") for w in filho.winfo_children()
                       if isinstance(w, tk.Label)]
        self.assertEqual(textos, ["Entrada", "dd/mm/aaaa hh:mm"])
        self.assertIsInstance(campo, componentes.Campo)

    # --- botões
    def test_botao_le_o_texto_e_aciona(self):
        cliques = []
        b = componentes.Botao(self.pai, "Salvar", lambda: cliques.append(1),
                              "primario")
        self.assertEqual(b.cget("text"), "Salvar")
        b.invocar()
        self.assertEqual(b._tecla(None), "break")      # Enter/Espaço acionam
        self.assertEqual(cliques, [1, 1])

    def test_botao_desativado_nao_aciona(self):
        cliques = []
        b = componentes.Botao(self.pai, "Remover", lambda: cliques.append(1))
        b.definir_ativo(False)
        b.invocar()
        self.assertEqual((cliques, b.cget("state")), ([], "disabled"))
        b.definir_ativo(True)
        b.invocar()
        self.assertEqual(cliques, [1])

    def test_botao_troca_texto_e_variante(self):
        b = componentes.Botao(self.pai, "Desativar", variante="perigo")
        b.definir_texto("Ativar", "secundario")
        self.assertEqual((b.cget("text"), b.variante), ("Ativar", "secundario"))

    # --- faixa de aviso, placa, tabela
    def test_aviso_muda_de_estado(self):
        aviso = componentes.Aviso(self.pai)
        aviso.mostrar("erro", "CPF bloqueado: teste", acao="Ver bloqueio",
                      comando=lambda: None)
        self.assertEqual(aviso.lbl.cget("text"), "CPF bloqueado: teste")
        self.assertEqual(aviso.lbl.cget("fg"), ESTADO["erro"][0])
        self.assertEqual(aviso.acao.cget("text"), "Ver bloqueio")
        aviso.mostrar("sucesso", "ok")
        self.assertIsNone(aviso.acao)

    def test_placa_guarda_texto_e_bloqueio(self):
        placa = componentes.Placa(self.pai)
        placa.mostrar("ABC1D23", bloqueada=True)
        self.assertEqual((placa.texto, placa.bloqueada), ("ABC1D23", True))
        placa.mostrar("")
        self.assertEqual(placa.texto, "")

    def test_tabela_com_situacao_zebra_e_colunas_escondidas(self):
        colunas = [("a", "A", 50, "w"), ("b", "B", 50, "w")]
        quadro, tab = componentes.tabela(self.pai, colunas, situacao="Situação",
                                         mostrar=("b",))
        self.assertEqual(tab["columns"], ("a", "b"))
        self.assertEqual(tab["displaycolumns"], ("b",))
        self.assertEqual(len(quadro.winfo_children()), 2)     # tabela + rolagem
        componentes.inserir_linha(tab, 0, ("1", "2"), iid="x", situacao="No campus",
                                  cor=ESTADO["sucesso"][0])
        componentes.inserir_linha(tab, 1, ("3", "4"), iid="y", situacao="Saiu",
                                  cor=COR["barra"])
        self.assertEqual(tab.item("x")["text"], "No campus")
        self.assertTrue(tab.item("x")["image"])
        self.assertEqual(tab.item("y")["tags"], ["zebra"])
        _, tab = componentes.tabela(self.pai, colunas, rolagem=False)
        self.assertEqual(len(tab.master.winfo_children()), 1)

    def test_bolinha_e_png_com_transparencia(self):
        img = componentes.bolinha(self.pai, "#0B6B3A")
        self.assertIs(img, componentes.bolinha(self.pai, "#0B6B3A"))   # cache
        self.assertEqual(img.height(), estilo.px(8))

    def test_tabela_de_eventos(self):
        _, tab = componentes.tabela_eventos(self.pai, (10, 10, 10, 10), 3)
        evento = {"momento": "m", "usuario": "u", "acao": "a", "detalhe": "d"}
        componentes.preencher_eventos(tab, [evento, evento])
        componentes.preencher_eventos(tab, [evento])          # substitui
        linhas = tab.get_children()
        self.assertEqual(len(linhas), 1)
        self.assertEqual(tab.item(linhas[0])["values"], ["m", "u", "a", "d"])

    def test_alternador_liga_e_desliga(self):
        var = tk.BooleanVar(value=False)
        chamado = []
        alt = componentes.Alternador(self.pai, "Mostrar removidos", var,
                                     lambda: chamado.append(var.get()))
        alt.alternar()
        alt.alternar()
        self.assertEqual(chamado, [True, False])
        self.assertEqual(alt.cget("text"), "Mostrar removidos")

    def test_cartao_monta_no_miolo(self):
        cartao = componentes.Cartao(self.pai)
        self.assertIs(cartao.miolo.master, cartao)
        self.assertEqual(cartao.miolo.cget("bg"), COR["superficie"])

    def test_data_por_extenso(self):
        self.assertEqual(componentes.data_por_extenso(datetime(2026, 10, 19)),
                         "Segunda-feira, 19 de outubro")

    def test_px_usa_a_escala(self):
        antiga = estilo.ESCALA
        self.addCleanup(setattr, estilo, "ESCALA", antiga)
        estilo.ESCALA = 1.25
        self.assertEqual((estilo.px(36), estilo.px(0.1)), (45, 1))


if __name__ == "__main__":
    unittest.main()
