"""Testa as peças de tela de componentes.py (janela oculta)."""

import tkinter as tk
import unittest
from datetime import datetime
from unittest import mock

from portaria import componentes, estilo, validacao
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
        campo = componentes.Campo(self.pai, dica_vazio="CPF ou placa",
                                  maximo=14)
        self.assertEqual(campo.lbl_vazio.winfo_manager(), "place")
        campo.entrada.insert(0, "1")
        self.assertEqual(campo.lbl_vazio.winfo_manager(), "")
        self.assertEqual(campo.entrada.get(), "1")   # a dica não é texto do campo

    def test_icone_do_campo_executa_a_acao(self):
        chamado = []
        campo = componentes.Campo(self.pai, icone="x", maximo=60,
                                  acao_icone=lambda: chamado.append(1))
        self.assertEqual(campo.lbl_icone.cget("text"), "x")
        self.assertTrue(campo.lbl_icone.bind("<Button-1>"))
        campo.usar_icone()
        self.assertEqual(chamado, [1])

    def test_campo_rotulado_tem_rotulo_e_apoio(self):
        grupo, campo = componentes.campo_rotulado(self.pai, "Entrada",
                                               "dd/mm/aaaa hh:mm",
                                               maximo=16)
        textos = []
        for filho in grupo.winfo_children():
            textos += [w.cget("text") for w in filho.winfo_children()
                       if isinstance(w, tk.Label)]
        self.assertEqual(textos, ["Entrada", "dd/mm/aaaa hh:mm"])
        self.assertIsInstance(campo, componentes.Campo)

    # --- tamanho máximo: digitação, colagem e contador
    def colar(self, campo, texto):
        """O que o Ctrl+V (<<Paste>>) chama, com a área de transferência
        trocada por `texto` (o teste não mexe na do Windows). O Tk só
        entrega o evento a janela visível: os testes chamam a ligação."""
        self.assertIn("_colar_da_area_de_transferencia",
                      campo.entrada.bind("<<Paste>>"))
        with mock.patch.object(campo.entrada, "clipboard_get",
                               return_value=texto):
            self.assertEqual(campo._colar_da_area_de_transferencia(), "break")
        return campo.entrada.get()

    def test_todo_campo_de_texto_precisa_de_um_maximo(self):
        with self.assertRaises(ValueError):
            componentes.Campo(self.pai)
        lista = componentes.Campo(self.pai, opcoes=["Aluno"])   # só escolhe
        self.assertFalse(hasattr(lista, "maximo"))

    def test_maximo_de_cada_tipo_de_campo(self):
        casos = [({"maximo": validacao.MAXIMO_NOME}, 80),
                 ({"numeros": 11}, 11),
                 ({"placa": True}, 7),
                 ({"senha": True}, validacao.MAXIMO_SENHA),
                 ({"seletor": "data_hora"}, 16),
                 ({"seletor": "data"}, 10),
                 ({"seletor": "hora"}, 5)]
        for opcoes, maximo in casos:
            with self.subTest(opcoes=opcoes):
                campo = componentes.Campo(self.pai, **opcoes)
                self.assertEqual(campo.maximo, maximo)

    def test_digitar_nao_passa_do_maximo(self):
        for opcoes, texto, esperado in [
                ({"maximo": 5}, "abcdefgh", "abcde"),
                ({"senha": True}, "s" * 70, "s" * 64),
                ({"seletor": "data_hora"}, "21/10/2026 10:009", "21/10/2026 10:00"),
                ({"seletor": "data"}, "21/10/20266", "21/10/2026"),
                ({"seletor": "hora"}, "07:300", "07:30"),
                ({"numeros": 11}, "529982247251", "52998224725"),
                ({"placa": True}, "ABC1D234", "ABC1D23")]:
            with self.subTest(opcoes=opcoes):
                campo = componentes.Campo(self.pai, **opcoes)
                self.assertEqual(self.digitar(campo.entrada, texto), esperado)

    def test_colar_texto_maior_corta_no_maximo(self):
        campo = componentes.Campo(self.pai, maximo=validacao.MAXIMO_NOME)
        self.assertEqual(self.colar(campo, "Ana " + "x" * 200), "Ana " + "x" * 76)
        self.assertEqual(len(campo.entrada.get()), 80)

    def test_colar_no_meio_so_entra_o_que_cabe(self):
        campo = componentes.Campo(self.pai, maximo=10)
        campo.entrada.insert(0, "12345678")
        campo.entrada.icursor(4)
        self.assertEqual(self.colar(campo, "abcdef"), "1234ab5678")

    def test_colar_substitui_a_selecao(self):
        campo = componentes.Campo(self.pai, maximo=6)
        campo.entrada.insert(0, "abcdef")
        campo.entrada.selection_range(0, 3)
        campo.entrada.icursor(0)
        self.assertEqual(self.colar(campo, "XYZW"), "XYZdef")

    def test_colar_cpf_formatado_no_campo_de_numeros(self):
        campo = componentes.Campo(self.pai, numeros=11)
        self.assertEqual(self.colar(campo, "529.982.247-25 extra 99"),
                         "52998224725")

    def test_colar_placa_com_hifen_e_minuscula(self):
        campo = componentes.Campo(self.pai, placa=True)
        self.assertEqual(self.colar(campo, "abc-1d23xyz"), "ABC1D23")

    def test_colar_senha_e_datas_cortam_no_maximo(self):
        for opcoes, texto, esperado in [
                ({"senha": True}, "p" * 100, "p" * 64),
                ({"seletor": "data_hora"}, "21/10/2026 10:00:59", "21/10/2026 10:00"),
                ({"seletor": "data"}, "21/10/2026 10:00", "21/10/2026"),
                ({"seletor": "hora"}, "07:30:00", "07:30")]:
            with self.subTest(opcoes=opcoes):
                campo = componentes.Campo(self.pai, **opcoes)
                self.assertEqual(self.colar(campo, texto), esperado)

    def test_colar_quebra_de_linha_vira_espaco(self):
        campo = componentes.Campo(self.pai, maximo=60)
        self.assertEqual(self.colar(campo, "linha um\r\nlinha dois"),
                         "linha um linha dois")

    def test_colar_em_campo_somente_leitura_nao_faz_nada(self):
        campo = componentes.Campo(self.pai, numeros=11)
        campo.entrada.insert(0, "123")
        campo.entrada.config(state="readonly")
        self.assertEqual(self.colar(campo, "456"), "123")

    def test_contador_mostra_usados_e_maximo(self):
        _, campo = componentes.campo_rotulado(
            self.pai, "Justificativa", maximo=validacao.MAXIMO_JUSTIFICATIVA,
            contador=True)
        self.assertEqual(campo.contador.cget("text"), "0/200")
        self.assertEqual(str(campo.contador.cget("fg")), COR["texto_3"])
        campo.entrada.insert(0, "Evento da reitoria")
        self.assertEqual(campo.contador.cget("text"), "18/200")
        self.colar(campo, "x" * 500)
        self.assertEqual(campo.contador.cget("text"), "200/200")
        self.assertEqual(str(campo.contador.cget("fg")), COR["alerta"])

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
