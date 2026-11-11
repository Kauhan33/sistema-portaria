"""
O visual da 3.1: os componentes novos continuam sendo os widgets do Tkinter
que o enunciado pede (tk.Button, tk.Checkbutton), agora desenhados no estilo
do sistema, e as telas seguem a ordem em que o porteiro trabalha.
"""
import tkinter as tk
import unittest

from portaria import estilo
from portaria.componentes import (BotaoTk, CampoTexto, Chip, checkbutton,
                                  imagem_arredondada, imagens_da_caixa)
from portaria.estilo import COR

from .test_interface import BaseInterface


class BaseComponente(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.raiz = tk.Tk()
        except tk.TclError:
            raise unittest.SkipTest("sem tela disponível para o Tkinter")
        cls.raiz.geometry("400x300+0+0")

    @classmethod
    def tearDownClass(cls):
        cls.raiz.destroy()

    def setUp(self):
        self.addCleanup(estilo.usar_tema, "claro")
        self.quadro = tk.Frame(self.raiz, bg=COR["superficie"])
        self.quadro.pack(fill="both", expand=True)
        self.addCleanup(self.quadro.destroy)
        self.cliques = []

    def botao(self, variante="primario", **opcoes):
        b = BotaoTk(self.quadro, "Cadastrar", lambda: self.cliques.append(1),
                    variante, **opcoes)
        b.pack(anchor="w")
        self.raiz.update()
        return b

    def clicar(self, widget, dentro=True):
        widget.event_generate("<Enter>")
        widget.event_generate("<ButtonPress-1>", x=5, y=5)
        widget.event_generate("<ButtonRelease-1>", x=5 if dentro else -40, y=5)
        self.raiz.update()


class TestBotaoTk(BaseComponente):
    def test_e_um_tk_button_com_fundo_em_imagem(self):
        b = self.botao()
        self.assertIsInstance(b, tk.Button)
        self.assertEqual(b.cget("text"), "Cadastrar")
        self.assertTrue(b.cget("image"))
        self.assertEqual(str(b.cget("compound")), "center")
        self.assertEqual(int(b.cget("bd")), 0)

    def test_clique_aciona_uma_vez(self):
        b = self.botao()
        self.clicar(b)
        self.assertEqual(self.cliques, [1])

    def test_soltar_fora_do_botao_nao_aciona(self):
        b = self.botao()
        self.clicar(b, dentro=False)
        self.assertEqual(self.cliques, [])

    def test_invoke_enter_e_espaco_acionam(self):
        b = self.botao()
        b.invoke()
        b.focus_force()
        self.raiz.update()
        b.event_generate("<Return>")
        b.event_generate("<space>")
        self.raiz.update()
        self.assertEqual(self.cliques, [1, 1, 1])

    def test_desativado_nao_aciona_por_nenhum_caminho(self):
        b = self.botao()
        b.definir_ativo(False)
        self.assertEqual(b.cget("state"), "disabled")
        self.assertEqual(b["state"], "disabled")
        self.clicar(b)
        b.invoke()
        b.invocar()
        b.event_generate("<Return>")
        self.assertEqual(self.cliques, [])
        self.assertEqual(str(b.cget("fg")), COR["texto_3"])
        b.definir_ativo(True)
        self.assertEqual(b.cget("state"), "normal")
        self.clicar(b)
        self.assertEqual(self.cliques, [1])

    def test_mouse_e_foco_trocam_a_imagem_de_fundo(self):
        b = self.botao()
        normal = b.cget("image")
        b.event_generate("<Enter>")
        em_cima = b.cget("image")
        b.event_generate("<ButtonPress-1>", x=5, y=5)
        apertado = b.cget("image")
        b.event_generate("<ButtonRelease-1>", x=-40, y=5)
        self.assertEqual(len({normal, em_cima, apertado}), 3)
        self.assertEqual(b.cget("image"), normal)
        b.focus_force()
        self.raiz.update()
        self.assertNotEqual(b.cget("image"), normal)      # anel de foco

    def test_cada_variante_tem_a_sua_cor_de_texto(self):
        esperado = {"primario": COR["texto_invertido"],
                    "secundario": COR["texto"], "fantasma": COR["texto"],
                    "perigo": estilo.ESTADO["erro"][0]}
        for variante, cor in esperado.items():
            with self.subTest(variante=variante):
                self.assertEqual(str(self.botao(variante).cget("fg")), cor)

    def test_so_o_primario_e_preenchido_de_vermelho(self):
        """Uma ação principal por tela: o perigo tem texto vermelho, mas o
        fundo é o da superfície."""
        primario = self.botao("primario")
        perigo = self.botao("perigo")
        self.raiz.update()

        def cor_do_meio(b):
            pixel = self.raiz.tk.call(b.cget("image"), "get", 4,
                                      b.winfo_height() // 2)
            return "#%02X%02X%02X" % tuple(int(v) for v in pixel)
        self.assertEqual(cor_do_meio(primario), COR["primario"])
        self.assertEqual(cor_do_meio(perigo), COR["superficie"])

    def test_fundo_acompanha_o_tamanho_do_botao(self):
        b = BotaoTk(self.quadro, "Entrar", None, "primario")
        b.pack(fill="x")
        self.raiz.update()
        imagem = b.cget("image")
        largura = int(self.raiz.tk.call("image", "width", imagem))
        self.assertGreater(b.winfo_width(), 300)
        self.assertEqual(largura, b.winfo_width())

    def test_trocar_o_texto_ajusta_a_largura(self):
        b = self.botao()
        antes = b.winfo_width()
        b.definir_texto("Cadastrar outra pessoa agora")
        self.raiz.update()
        self.assertEqual(b.cget("text"), "Cadastrar outra pessoa agora")
        self.assertGreater(b.winfo_width(), antes)

    def test_no_tema_escuro_usa_as_cores_do_tema(self):
        estilo.usar_tema("escuro")
        b = BotaoTk(self.quadro, "Entrar", None, "primario",
                    fundo_pai=COR["superficie"])
        self.assertEqual(str(b.cget("bg")), COR["superficie"])
        self.assertEqual(str(b.cget("fg")), COR["texto_invertido"])

    def test_imagem_arredondada_tem_os_cantos_da_cor_do_fundo(self):
        img = imagem_arredondada(self.raiz, 60, 30, 8, "#D9001B", "#FFFFFF")
        self.assertEqual(img.get(0, 0), (255, 255, 255))
        self.assertEqual(img.get(30, 15), (217, 0, 27))
        self.assertEqual((img.width(), img.height()), (60, 30))

    def test_imagem_pequena_demais_nao_quebra(self):
        img = imagem_arredondada(self.raiz, 1, 1, 8, "#D9001B", "#FFFFFF")
        self.assertGreaterEqual(img.width(), 2)


class TestCheckbutton(BaseComponente):
    def test_e_um_tk_checkbutton_com_a_caixa_desenhada(self):
        var = tk.BooleanVar(self.raiz, False)
        chk = checkbutton(self.quadro, "Mostrar senha", var)
        chk.pack()
        self.assertIsInstance(chk, tk.Checkbutton)
        self.assertEqual(chk.cget("text"), "Mostrar senha")
        self.assertTrue(chk.cget("image"))
        self.assertTrue(chk.cget("selectimage"))
        self.assertNotEqual(chk.cget("image"), chk.cget("selectimage"))

    def test_clicar_marca_e_desmarca(self):
        chamadas = []
        var = tk.BooleanVar(self.raiz, False)
        chk = checkbutton(self.quadro, "Só abertas", var,
                          lambda: chamadas.append(var.get()))
        chk.pack()
        chk.invoke()
        chk.invoke()
        self.assertEqual(chamadas, [True, False])

    def test_caixa_marcada_e_vermelha_e_a_desmarcada_e_clara(self):
        desmarcada, marcada = imagens_da_caixa(self.raiz)
        meio = desmarcada.height() // 2
        self.assertEqual("#%02X%02X%02X" % desmarcada.get(meio, meio),
                         COR["superficie"])
        # (o meio da marcada é o "visto"; perto do canto de cima é o fundo)
        self.assertEqual("#%02X%02X%02X" % marcada.get(meio, 3), COR["primario"])
        # o canto é transparente: a caixa serve em qualquer fundo
        self.assertTrue(desmarcada.transparency_get(0, 0))

    def test_cada_tema_tem_as_suas_imagens(self):
        claras = imagens_da_caixa(self.raiz)
        estilo.usar_tema("escuro")
        escuras = imagens_da_caixa(self.raiz)
        self.assertNotEqual(str(claras[0]), str(escuras[0]))
        self.assertIs(imagens_da_caixa(self.raiz), escuras)   # guardadas


class TestCampoTextoEChip(BaseComponente):
    def test_campo_de_texto_tem_a_moldura_do_campo(self):
        campo = CampoTexto(self.quadro, 50)
        campo.pack(fill="x")
        self.raiz.update()
        self.assertTrue(campo.cv.find_all())            # moldura desenhada
        campo.texto.focus_force()
        self.raiz.update()
        self.assertTrue(campo.focado)
        campo.insert(0, "x" * 80)
        self.assertEqual(len(campo.get()), 50)

    def test_chip_mostra_o_texto(self):
        chip = Chip(self.quadro)
        chip.lbl.config(text="Estacionamento 3/50")
        chip.pack()
        self.raiz.update()
        self.assertEqual(chip.lbl.cget("text"), "Estacionamento 3/50")
        self.assertEqual(str(chip.lbl.cget("bg")), COR["superficie"])
        self.assertEqual(str(Chip(self.quadro, estado="sucesso").lbl.cget("fg")),
                         estilo.ESTADO["sucesso"][0])


class TestTelasRepaginadas(BaseInterface):
    def setUp(self):
        super().setUp()
        self.tela = self.app.tela_cadastro
        self.janela.deiconify()
        self.janela.geometry("1180x760+0+0")
        self.janela.update()

    def test_tab_segue_a_ordem_da_tela_no_cadastro(self):
        tela = self.tela
        ordem = [tela.cpf, tela.nome, tela.celular, tela.empresa, tela.tipo,
                 tela.campo_data_entrada, tela.campo_hora_entrada,
                 tela.pecas["placa"][1].entrada, tela.cracha,
                 tela.motivo.texto, tela.anfitriao, tela.saida,
                 tela.btn_cadastrar, tela.btn_limpar, tela.btn_cancelar]
        visitados, w = [], tela.cpf
        for _ in range(40):
            if w in ordem:
                visitados.append(w)
            if w is tela.btn_cancelar:
                break
            w = w.tk_focusNext()
        self.assertEqual(visitados, ordem)

    def test_blocos_pessoa_e_visita(self):
        tela = self.tela
        self.assertEqual(tela.titulo_form.cget("text"), "Pessoa")
        self.assertEqual(tela.titulo_visita.cget("text"), "Visita")
        y = lambda w: w.winfo_rooty()                       # noqa: E731
        self.assertLess(y(tela.titulo_form), y(tela.cpf))
        self.assertLess(y(tela.empresa), y(tela.titulo_visita))
        self.assertLess(y(tela.titulo_visita), y(tela.campo_data_entrada))
        self.assertLess(y(tela.motivo.texto), y(tela.btn_cadastrar))

    def test_um_botao_principal_por_tela(self):
        tela = self.tela
        self.assertEqual(tela.btn_cadastrar.variante, "primario")
        self.assertEqual({tela.btn_limpar.variante, tela.btn_cancelar.variante},
                         {"secundario", "fantasma"})
        self.assertEqual(tela.btn_entrada_controle.variante, "primario")
        for botao in (tela.btn_saida, tela.btn_corrigir, tela.btn_atualizar,
                      tela.btn_voltar, tela.btn_excluir):
            self.assertNotEqual(botao.variante, "primario")
        self.assertEqual(self.app.tela_pessoas.btn_nova.variante, "secundario")

    def test_excluir_fica_longe_das_acoes_do_dia_a_dia(self):
        self.app.ir_para(self.app.aba_controle)
        self.janela.update()
        tela = self.tela
        direita = tela.btn_voltar.winfo_rootx() + tela.btn_voltar.winfo_width()
        self.assertGreater(tela.btn_excluir.winfo_rootx() - direita, 40)

    def test_etiqueta_do_estacionamento_some_sem_controle_de_vagas(self):
        self.app.ir_para(self.app.aba_controle)
        self.janela.update()
        tela = self.tela
        self.assertEqual(tela.chip_estacionamento.winfo_manager(), "")
        self.banco.salvar_lotacao(50, False, autor="ana.admin")
        tela.atualizar()
        self.janela.update()
        self.assertEqual(tela.chip_estacionamento.winfo_manager(), "pack")
        self.assertTrue(tela.lbl_estacionamento.cget("text").endswith("0/50"))

    def test_menu_lateral_grafite_com_o_item_ativo_em_destaque(self):
        self.assertEqual(str(self.app.lateral.cget("bg")), COR["lateral"])
        ativo = self.app.itens_menu[str(self.app.aba_cad)]
        outro = self.app.itens_menu[str(self.app.aba_controle)]
        self.assertTrue(ativo.ativo)
        self.assertFalse(outro.ativo)
        self.app.ir_para(self.app.aba_controle)
        self.assertTrue(outro.ativo)

    def test_tema_escuro_remonta_com_os_componentes_novos(self):
        self.app.trocar_tema("escuro")
        tela = self.app.tela_cadastro
        self.assertIsInstance(tela.btn_cadastrar, tk.Button)
        self.assertEqual(str(tela.btn_cadastrar.cget("bg")), COR["superficie"])
        self.assertEqual(str(self.app.lateral.cget("bg")), COR["lateral"])


class TestLoginRepaginado(BaseInterface):
    entrar_como = None

    def test_painel_grafite_com_o_braco_da_cancela(self):
        tela = self.app.tela_login
        self.janela.deiconify()
        self.janela.update()
        self.assertEqual(str(tela.cancela.master.cget("bg")),
                         COR["painel_login"])
        blocos = tela.cancela.find_all()
        self.assertGreater(len(blocos), 3)
        cores = {tela.cancela.itemcget(b, "fill") for b in blocos}
        self.assertEqual(cores, {COR["marca"], COR["texto_sobre_marca"]})

    def test_mostrar_senha_e_a_caixa_desenhada(self):
        tela = self.app.tela_login
        self.assertTrue(tela.chk_mostrar.cget("selectimage"))
        tela.chk_mostrar.invoke()
        self.assertEqual(tela.senhas[0].cget("show"), "")


if __name__ == "__main__":
    unittest.main()
