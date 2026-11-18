"""
Versão 3.5: página Aparência (cor da barra lateral e dos botões, tema e
letra de cada usuário, banco v16), o histórico da pessoa com o carro com
que cada visita entrou e saiu, e o entregador que só deixa a encomenda no
Cadastro.
"""

import os
import re
import sqlite3
import tempfile
import tkinter as tk
import unittest
from datetime import datetime
from unittest import mock

from portaria import componentes, dados, dados_modulos, estilo, interface
from portaria.componentes import Botao, BotaoTk
from portaria.estilo import COR
from portaria.senhas import gerar_hash
from portaria.tela_aparencia import AbaAparencia, OpcaoVisual
from portaria.tela_cadastro import (CAMPOS_DA_ENCOMENDA, DICA_CPF,
                                    DICA_ENTREGA)
from portaria.tela_pessoas import descrever_veiculo
from portaria.tela_veiculo import LEVA
from portaria.usuarios import TEMA_PADRAO
from portaria.validacao import (MAXIMO_DESCRICAO_ENCOMENDA, MAXIMO_LOCAL,
                                MAXIMO_NOME, MAXIMO_REMETENTE)

from .test_autorizados import (BRUNO, CARLA, EVA, BaseAutorizadosNaTela,
                               BaseAutorizadosNoBanco)
from .test_dados import registro, versao_do_arquivo
from .test_interface import AGORA, BaseInterface
from .test_regras_no_banco import BaseRegras

LATERAIS = ("grafite", "vermelho", "branco")
BOTOES = ("vermelho", "azul", "branco")
HEX = re.compile(r"^#[0-9A-F]{6}$")


def padrao_de_volta():
    estilo.usar_aparencia(estilo.LATERAL_PADRAO, estilo.BOTOES_PADRAO)
    estilo.usar_tema("claro")


# ======================================================================
# 1) Aparência: as cores (estilo.py), sem janela
# ======================================================================
class TestCoresDaAparencia(unittest.TestCase):
    def setUp(self):
        estilo.usar_tema("claro")
        self.addCleanup(padrao_de_volta)

    def usar(self, tema, lateral, botoes):
        estilo.usar_tema(tema)
        estilo.usar_aparencia(lateral, botoes)

    def test_nomes_batem_com_o_que_o_banco_aceita(self):
        self.assertEqual(tuple(estilo.NOMES_DA_LATERAL),
                         dados_modulos.CORES_DA_LATERAL)
        self.assertEqual(tuple(estilo.NOMES_DOS_BOTOES),
                         dados_modulos.CORES_DOS_BOTOES)
        self.assertEqual((estilo.LATERAL_PADRAO, estilo.BOTOES_PADRAO),
                         dados_modulos.APARENCIA_PADRAO)
        self.assertEqual(dados_modulos.APARENCIA_PADRAO,
                         ("grafite", "vermelho"))

    def test_cada_tema_tem_todas_as_opcoes(self):
        for tema in ("claro", "escuro"):
            with self.subTest(tema=tema):
                self.assertEqual(set(estilo.LATERAIS[tema]), set(LATERAIS))
                self.assertEqual(set(estilo.BOTOES[tema]), set(BOTOES))
                self.assertEqual(estilo.LATERAIS[tema]["grafite"], {})
                self.assertEqual(estilo.BOTOES[tema]["vermelho"], {})

    def test_opcoes_so_trocam_tokens_que_existem(self):
        tokens_do_botao = {"botao", "botao_hover", "botao_press",
                           "botao_texto", "botao_borda", "botao_dica",
                           "botao_foco"}
        for tema in ("claro", "escuro"):
            paleta = set(estilo.PALETAS[tema])
            for tabela in (estilo.LATERAIS[tema], estilo.BOTOES[tema]):
                for opcao, cores in tabela.items():
                    with self.subTest(tema=tema, opcao=opcao):
                        self.assertLessEqual(set(cores),
                                             paleta | tokens_do_botao)
                        for valor in cores.values():
                            self.assertRegex(valor, HEX)

    def test_tokens_novos_existem_em_todas_as_combinacoes(self):
        novos = ("botao", "botao_hover", "botao_press", "botao_texto",
                 "botao_borda", "botao_dica", "botao_foco",
                 "lateral_simbolo", "lateral_simbolo_traco",
                 "lateral_contorno")
        for tema in ("claro", "escuro"):
            for lateral in LATERAIS:
                for botoes in BOTOES:
                    self.usar(tema, lateral, botoes)
                    for token in novos:
                        with self.subTest(tema=tema, lateral=lateral,
                                          botoes=botoes, token=token):
                            self.assertIn(token, COR)
                            if token not in ("botao_borda",
                                             "lateral_contorno"):
                                self.assertRegex(COR[token], HEX)

    def test_contraste_wcag_em_todas_as_combinacoes(self):
        """2 temas x 3 laterais x 3 botões = 18 combinações."""
        for tema in ("claro", "escuro"):
            for lateral in LATERAIS:
                for botoes in BOTOES:
                    self.usar(tema, lateral, botoes)
                    for descricao, frente, fundo, minimo in \
                            estilo.pares_de_contraste():
                        with self.subTest(tema=tema, lateral=lateral,
                                          botoes=botoes, par=descricao):
                            self.assertGreaterEqual(
                                estilo.contraste(frente, fundo), minimo,
                                f"{frente} sobre {fundo}")

    def test_botao_simbolo_e_foco_se_destacam_do_fundo(self):
        """Além da lista: o botão principal se vê no cartão (pela cor ou
        pelo contorno), o símbolo se vê na barra e o anel de foco no
        cartão (3:1, WCAG 1.4.11)."""
        for tema in ("claro", "escuro"):
            for lateral in LATERAIS:
                for botoes in BOTOES:
                    self.usar(tema, lateral, botoes)
                    c = COR
                    pares = [
                        ("botão / cartão", c["botao_borda"] or c["botao"],
                         c["superficie"]),
                        ("símbolo / barra", c["lateral_simbolo"],
                         c["lateral"]),
                        ("foco do botão / cartão", c["botao_foco"],
                         c["superficie"]),
                        ("traço do item ativo / barra", c["lateral_marca"],
                         c["lateral"])]
                    for nome, frente, fundo in pares:
                        with self.subTest(tema=tema, lateral=lateral,
                                          botoes=botoes, par=nome):
                            self.assertGreaterEqual(
                                estilo.contraste(frente, fundo), 3.0)

    def test_padrao_e_o_de_antes(self):
        self.usar("claro", "grafite", "vermelho")
        self.assertEqual(COR["lateral"], estilo.PALETAS["claro"]["lateral"])
        self.assertEqual(COR["botao"], COR["primario"])
        self.assertEqual(COR["botao_texto"], COR["texto_invertido"])
        self.assertEqual(COR["botao_foco"], COR["foco"])
        self.assertEqual(COR["botao_borda"], "")
        self.assertEqual(COR["lateral_contorno"], "")

    def test_azul_muda_o_primario_e_o_botao(self):
        for tema in ("claro", "escuro"):
            with self.subTest(tema=tema):
                self.usar(tema, "grafite", "azul")
                azul = estilo.BOTOES[tema]["azul"]["primario"]
                self.assertEqual(COR["primario"], azul)
                self.assertEqual(COR["botao"], azul)
                self.assertNotEqual(COR["primario"],
                                    estilo.PALETAS[tema]["primario"])

    def test_branco_muda_so_o_botao(self):
        for tema in ("claro", "escuro"):
            with self.subTest(tema=tema):
                self.usar(tema, "grafite", "branco")
                self.assertEqual(COR["primario"],
                                 estilo.PALETAS[tema]["primario"])
                self.assertEqual(COR["botao"], "#FFFFFF")
                self.assertEqual(COR["botao_texto"], "#1B2330")
        self.usar("claro", "grafite", "branco")
        self.assertEqual(COR["botao_borda"], "#1B2330")      # contorno
        self.usar("escuro", "grafite", "branco")
        self.assertEqual(COR["botao_borda"], "")     # no escuro já se vê

    def test_lateral_vermelha_tem_o_simbolo_branco(self):
        for tema in ("claro", "escuro"):
            with self.subTest(tema=tema):
                self.usar(tema, "vermelho", "vermelho")
                self.assertEqual(COR["lateral_simbolo"], "#FFFFFF")
                self.assertEqual(COR["lateral_simbolo_traco"], COR["lateral"])

    def test_lateral_branca_tem_o_fio_no_claro(self):
        self.usar("claro", "branco", "vermelho")
        self.assertEqual(COR["lateral"], "#FFFFFF")
        self.assertRegex(COR["lateral_contorno"], HEX)
        self.usar("claro", "grafite", "vermelho")
        self.assertEqual(COR["lateral_contorno"], "")

    def test_usar_aparencia_diz_se_mudou_e_ignora_cor_estranha(self):
        self.assertFalse(estilo.usar_aparencia("grafite", "vermelho"))
        self.assertTrue(estilo.usar_aparencia("vermelho", "azul"))
        self.assertFalse(estilo.usar_aparencia("vermelho", "azul"))
        self.assertEqual(estilo.APARENCIA, {"lateral": "vermelho",
                                            "botoes": "azul"})
        for estranha in (None, "", "rosa", "VERMELHO", "'; DROP TABLE x"):
            with self.subTest(cor=estranha):
                estilo.usar_aparencia(estranha, estranha)
                self.assertEqual(estilo.APARENCIA, {"lateral": "grafite",
                                                    "botoes": "vermelho"})
                self.assertEqual(COR["lateral"],
                                 estilo.PALETAS["claro"]["lateral"])
                estilo.usar_aparencia("vermelho", "azul")

    def test_trocar_o_tema_mantem_a_aparencia(self):
        self.usar("claro", "vermelho", "azul")
        estilo.usar_tema("escuro")
        self.assertEqual(COR["lateral"],
                         estilo.LATERAIS["escuro"]["vermelho"]["lateral"])
        self.assertEqual(COR["primario"],
                         estilo.BOTOES["escuro"]["azul"]["primario"])

    def test_as_mesmas_chaves_de_cor_em_toda_combinacao(self):
        """Nenhuma combinação perde um token (KeyError numa tela)."""
        chaves = None
        for tema in ("claro", "escuro"):
            for lateral in LATERAIS:
                for botoes in BOTOES:
                    self.usar(tema, lateral, botoes)
                    if chaves is None:
                        chaves = set(COR)
                    self.assertEqual(set(COR), chaves)


# ======================================================================
# 1) Aparência no banco (v16)
# ======================================================================
class TestAparenciaNoBanco(BaseRegras):
    def test_padrao_para_quem_nunca_escolheu(self):
        for login in ("ana", "paulo"):
            self.assertEqual(self.banco.aparencia_do_usuario(login),
                             ("grafite", "vermelho"))

    def test_cada_usuario_guarda_a_sua(self):
        self.banco.definir_aparencia("branco", "azul", "paulo")
        self.assertEqual(self.banco.aparencia_do_usuario("paulo"),
                         ("branco", "azul"))
        self.assertEqual(self.banco.aparencia_do_usuario("ana"),
                         ("grafite", "vermelho"))
        self.banco.definir_aparencia("vermelho", "branco", "ana")
        self.assertEqual(self.banco.aparencia_do_usuario("paulo"),
                         ("branco", "azul"))

    def test_todas_as_combinacoes_validas_sao_aceitas(self):
        for lateral in LATERAIS:
            for botoes in BOTOES:
                self.banco.definir_aparencia(lateral, botoes, "paulo")
                self.assertEqual(self.banco.aparencia_do_usuario("paulo"),
                                 (lateral, botoes))

    def test_cor_desconhecida_e_recusada(self):
        self.banco.definir_aparencia("vermelho", "azul", "paulo")
        for lateral, botoes in (("rosa", "azul"), ("vermelho", "verde"),
                                ("", "azul"), (None, None),
                                ("Vermelho", "azul"), ("vermelho ", "azul"),
                                ("azul", "grafite"),      # trocadas
                                ("'; DROP TABLE usuarios; --", "azul")):
            with self.subTest(lateral=lateral, botoes=botoes):
                with self.assertRaises(dados.ErroDados):
                    self.banco.definir_aparencia(lateral, botoes, "paulo")
        self.assertEqual(self.banco.aparencia_do_usuario("paulo"),
                         ("vermelho", "azul"))

    def test_sem_sessao_inexistente_ou_inativo_e_recusado(self):
        with self.assertRaises(dados.ErroDados):
            self.banco.definir_aparencia("vermelho", "azul", None)
        with self.assertRaises(dados.ErroDados):
            self.banco.definir_aparencia("vermelho", "azul", "fantasma")
        id_paulo = self.banco.buscar_usuario("paulo")["id"]
        self.banco.definir_ativo(id_paulo, False, "ana")
        with self.assertRaises(dados.ErroDados):
            self.banco.definir_aparencia("vermelho", "azul", "paulo")
        self.assertEqual(self.banco.aparencia_do_usuario("paulo"),
                         ("grafite", "vermelho"))

    def test_quem_ainda_vai_trocar_a_senha_nao_muda(self):
        self.banco.criar_usuario("Rita Nova", "rita", "porteiro",
                                 gerar_hash("senha-rita"), autor="ana",
                                 trocar_senha=True)
        with self.assertRaises(dados.ErroDados):
            self.banco.definir_aparencia("vermelho", "azul", "rita")

    def test_nao_vai_para_o_historico(self):
        antes = len(self.banco.listar_eventos())
        self.banco.definir_aparencia("branco", "branco", "ana")
        self.assertEqual(len(self.banco.listar_eventos()), antes)
        self.assertTrue(self.banco.verificar_historico()["integro"])

    def test_valor_estranho_gravado_por_fora_vira_o_padrao(self):
        con = sqlite3.connect(self.caminho)
        con.execute("UPDATE usuarios SET lateral = 'rosa', botoes = 'azul' "
                    "WHERE login = 'paulo'")
        con.execute("UPDATE usuarios SET lateral = 'branco', botoes = '' "
                    "WHERE login = 'ana'")
        con.commit()
        con.close()
        self.assertEqual(self.banco.aparencia_do_usuario("paulo"),
                         ("grafite", "azul"))
        self.assertEqual(self.banco.aparencia_do_usuario("ana"),
                         ("branco", "vermelho"))

    def test_usuario_inexistente_tem_o_padrao(self):
        self.assertEqual(self.banco.aparencia_do_usuario("ninguem"),
                         ("grafite", "vermelho"))
        self.assertEqual(self.banco.aparencia_do_usuario(None),
                         ("grafite", "vermelho"))

    def test_colunas_novas_no_esquema(self):
        # 3.6: o banco v17 continua com as colunas da 3.5
        self.assertGreaterEqual(dados.VERSAO_ESQUEMA, 16)
        self.assertEqual(versao_do_arquivo(self.caminho), dados.VERSAO_ESQUEMA)
        con = sqlite3.connect(self.caminho)
        colunas = {c[1]: c for c in con.execute("PRAGMA table_info(usuarios)")}
        con.close()
        self.assertEqual(colunas["lateral"][4], "'grafite'")   # o default
        self.assertEqual(colunas["botoes"][4], "'vermelho'")
        self.assertEqual(colunas["lateral"][3], 1)              # NOT NULL


class TestMigracaoV16(unittest.TestCase):
    """3.5: o banco da 3.4 (v15) ganha a aparência de cada usuário."""

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.caminho = os.path.join(self.pasta.name, "portaria.db")
        relogio = lambda: datetime(2026, 10, 19, 10)        # noqa: E731
        banco = dados.Banco(self.caminho, relogio=relogio)
        banco.criar_usuario("Ana Admin", "ana", "admin", gerar_hash("senha123"))
        banco.criar_usuario("Paulo Porteiro", "paulo", "porteiro",
                            gerar_hash("senha456"), autor="ana",
                            trocar_senha=False)
        banco.definir_tema("escuro", "paulo")
        banco.definir_letra("grande", "paulo")
        banco.inserir(registro(entrada="19/10/2026 08:00"), autor="paulo")
        self.eventos = len(banco.listar_eventos())
        del banco
        con = sqlite3.connect(self.caminho)          # como a 3.4 deixava
        con.execute("ALTER TABLE usuarios DROP COLUMN lateral")
        con.execute("ALTER TABLE usuarios DROP COLUMN botoes")
        con.execute("PRAGMA user_version = 15")
        con.execute("UPDATE meta SET valor = '15' WHERE chave = "
                    "'versao_esquema'")
        con.commit()
        con.close()
        self.relogio = relogio

    def colunas(self):
        con = sqlite3.connect(self.caminho)
        nomes = {c[1] for c in con.execute("PRAGMA table_info(usuarios)")}
        con.close()
        return nomes

    def test_banco_da_3_4_ganha_as_colunas_com_o_padrao(self):
        self.assertEqual(versao_do_arquivo(self.caminho), 15)
        self.assertNotIn("lateral", self.colunas())
        banco = dados.Banco(self.caminho, relogio=self.relogio)
        self.assertEqual(versao_do_arquivo(self.caminho), dados.VERSAO_ESQUEMA)
        self.assertLessEqual({"lateral", "botoes"}, self.colunas())
        for login in ("ana", "paulo"):
            self.assertEqual(banco.aparencia_do_usuario(login),
                             ("grafite", "vermelho"))
        # o resto não se perde
        self.assertEqual(banco.buscar_usuario("paulo")["tema"], "escuro")
        self.assertEqual(banco.letra_do_usuario("paulo"), "grande")
        self.assertEqual(len(banco.listar()), 1)
        self.assertGreaterEqual(len(banco.listar_eventos()), self.eventos)
        self.assertTrue(banco.verificar_historico()["integro"])
        # e a escolha já pode ser gravada
        banco.definir_aparencia("vermelho", "azul", "paulo")
        self.assertEqual(banco.aparencia_do_usuario("paulo"),
                         ("vermelho", "azul"))
        del banco

    def test_faz_o_backup_de_v15(self):
        banco = dados.Banco(self.caminho, relogio=self.relogio)
        del banco
        backups = os.listdir(os.path.join(self.pasta.name, "backups"))
        self.assertTrue(any("-de-v15-" in f for f in backups), backups)
        self.assertTrue(any(f"antes-v{dados.VERSAO_ESQUEMA}" in f
                            for f in backups), backups)

    def test_migrar_duas_vezes_nao_estraga(self):
        dados.Banco(self.caminho, relogio=self.relogio)
        banco = dados.Banco(self.caminho, relogio=self.relogio)
        self.assertEqual(versao_do_arquivo(self.caminho), dados.VERSAO_ESQUEMA)
        self.assertEqual(banco.aparencia_do_usuario("ana"),
                         ("grafite", "vermelho"))
        del banco

    def test_passo_v16_e_idempotente(self):
        banco = dados.Banco(self.caminho, relogio=self.relogio)
        banco.definir_aparencia("branco", "branco", "ana")
        con = sqlite3.connect(self.caminho)
        dados_modulos.passo_v16(banco, con, 15)        # de novo: nada muda
        con.commit()
        con.close()
        self.assertEqual(banco.aparencia_do_usuario("ana"),
                         ("branco", "branco"))
        del banco


# ======================================================================
# 1) Página Aparência (janela oculta)
# ======================================================================
class BaseAparencia(BaseInterface):
    def setUp(self):
        super().setUp()
        self.addCleanup(estilo.usar_letra, "normal")
        self.addCleanup(estilo.usar_aparencia, estilo.LATERAL_PADRAO,
                        estilo.BOTOES_PADRAO)

    def abrir(self):
        self.app.ir_para(self.app.aba_aparencia)
        return self.app.tela_aparencia

    def escolher(self, grupo, valor):
        self.abrir().opcoes[(grupo, valor)].invocar()
        return self.app.tela_aparencia

    def entrar_pela_tela(self, login, senha):
        tela = self.app.tela_login
        tela.campo_login.delete(0, tk.END)
        tela.campo_login.insert(0, login)
        tela.campo_senha.insert(0, senha)
        tela.entrar()

    def simbolo(self):
        """O símbolo (a cancela) no alto da barra lateral: um rótulo com a
        imagem desenhada pelo programa."""
        def primeiro(widget):
            for filho in widget.winfo_children():
                if hasattr(filho, "cores") and hasattr(filho, "imagem"):
                    return filho
                achado = primeiro(filho)
                if achado is not None:
                    return achado
            return None
        return primeiro(self.app.lateral)

    @staticmethod
    def preenchimentos(simbolo):
        """As cores do símbolo: a da placa e a da cancela."""
        return set(simbolo.cores)

    def fios(self):
        return [f for f in self.app.lateral.winfo_children()
                if isinstance(f, tk.Frame) and int(f.cget("width")) == 1]


class TestPaginaAparencia(BaseAparencia):
    def test_item_aparencia_e_o_ultimo_do_menu(self):
        textos = [i.cget("text") for i in self.app.itens_menu.values()]
        self.assertEqual(textos[-1], "Aparência")
        self.assertEqual(textos.count("Aparência"), 1)
        list(self.app.itens_menu.values())[-1].comando()
        self.assertEqual(self.app.abas.select(), str(self.app.aba_aparencia))
        self.assertIsInstance(self.app.tela_aparencia, AbaAparencia)
        self.assertTrue(self.app.itens_menu[str(self.app.aba_aparencia)].ativo)

    def test_menu_da_conta_sem_os_radios_de_tema_e_letra(self):
        menu = self.app.menu_usuario
        rotulos = [menu.entrycget(i, "label")
                   for i in range(menu.index("end") + 1)
                   if menu.type(i) != "separator"]
        self.assertIn(interface.ITEM_APARENCIA, rotulos)
        self.assertFalse([r for r in rotulos
                          if r.startswith(("Tema:", "Letra:"))])
        tipos = {menu.type(i) for i in range(menu.index("end") + 1)}
        self.assertNotIn("radiobutton", tipos)
        self.assertIs(self.app.abrir_aparencia(), self.app.tela_aparencia)
        self.assertEqual(self.app.abas.select(), str(self.app.aba_aparencia))

    def test_quatro_grupos_com_as_opcoes_e_o_padrao_marcado(self):
        tela = self.abrir()
        grupos = {}
        for (grupo, valor), opcao in tela.opcoes.items():
            self.assertIsInstance(opcao, OpcaoVisual)
            grupos.setdefault(grupo, []).append(valor)
        self.assertEqual(grupos, {"lateral": list(LATERAIS),
                                  "botoes": list(BOTOES),
                                  "tema": ["claro", "escuro", "sistema"],
                                  "letra": ["normal", "grande", "maior"]})
        self.assertEqual({g: tela.escolhida(g) for g in grupos},
                         {"lateral": "grafite", "botoes": "vermelho",
                          "tema": "sistema", "letra": "normal"})
        for grupo in grupos:                       # uma só marcada por grupo
            marcadas = [v for (g, v), o in tela.opcoes.items()
                        if g == grupo and o.escolhida]
            self.assertEqual(len(marcadas), 1, grupo)
        self.assertEqual(tela.opcoes[("lateral", "vermelho")].cget("text"),
                         "Vermelho")
        self.assertEqual(tela.btn_padrao.cget("text"), "Restaurar o padrão")

    def test_prevas_desenham_sem_erro(self):
        self.janela.deiconify()
        self.janela.geometry("1280x800")
        tela = self.abrir()
        self.janela.update()
        for (grupo, valor), opcao in tela.opcoes.items():
            with self.subTest(grupo=grupo, valor=valor):
                self.assertGreater(opcao.winfo_width(), 20)
                self.assertTrue(opcao.find_all())          # desenhou algo
        opcao = tela.opcoes[("lateral", "branco")]
        opcao.event_generate("<Enter>")                    # hover redesenha
        opcao.event_generate("<Leave>")
        self.janela.update()

    def test_escolher_a_lateral_vermelha(self):
        tela = self.escolher("lateral", "vermelho")
        self.assertEqual(self.banco.aparencia_do_usuario("ana.admin"),
                         ("vermelho", "vermelho"))
        self.assertEqual(estilo.APARENCIA["lateral"], "vermelho")
        self.assertEqual(self.app.lateral.cget("bg").upper(),
                         estilo.LATERAIS["claro"]["vermelho"]["lateral"])
        # a página foi remontada e reaberta, com a escolha marcada
        self.assertEqual(self.app.abas.select(), str(self.app.aba_aparencia))
        self.assertEqual(tela.escolhida("lateral"), "vermelho")
        self.assertEqual(tela.escolhida("botoes"), "vermelho")
        # o símbolo fica branco, com a cancela da cor da barra
        cores = self.preenchimentos(self.simbolo())
        self.assertIn("#FFFFFF", cores)
        self.assertIn(COR["lateral"].upper(), cores)
        self.assertNotIn(estilo.PALETAS["claro"]["lateral_simbolo"], cores)

    def test_lateral_branca_tem_o_fio_e_a_grafite_nao(self):
        self.assertEqual(self.fios(), [])
        self.escolher("lateral", "branco")
        fio, = self.fios()
        self.assertEqual(fio.cget("bg").upper(), COR["lateral_contorno"])
        self.assertEqual(fio.pack_info()["side"], "right")
        self.assertEqual(self.app.lateral.cget("bg").upper(), "#FFFFFF")
        self.escolher("lateral", "grafite")
        self.assertEqual(self.fios(), [])
        cores = self.preenchimentos(self.simbolo())
        self.assertIn(estilo.PALETAS["claro"]["lateral_simbolo"], cores)

    def test_escolher_botoes_azuis(self):
        tela = self.escolher("botoes", "azul")
        azul = estilo.BOTOES["claro"]["azul"]["primario"]
        self.assertEqual(self.banco.aparencia_do_usuario("ana.admin"),
                         ("grafite", "azul"))
        self.assertEqual(tela.escolhida("botoes"), "azul")
        self.assertEqual((COR["primario"], COR["botao"]), (azul, azul))
        botao = self.app.tela_cadastro.btn_cadastrar        # remontado
        self.assertIn(azul, {chave[0] for chave in botao._imagens})
        self.assertEqual(botao.cget("fg").upper(), COR["texto_invertido"])
        desenhado = Botao(self.app.corpo, "Salvar", variante="primario")
        self.assertEqual(desenhado.cores["normal"], azul)
        self.assertEqual(desenhado._cor_do_foco(), COR["botao_foco"])

    def test_escolher_botoes_brancos(self):
        self.escolher("botoes", "branco")
        botao = self.app.tela_cadastro.btn_cadastrar
        self.assertEqual(botao.cget("fg").upper(), "#1B2330")
        self.assertIn(("#FFFFFF", "#1B2330"),
                      {chave[:2] for chave in botao._imagens})
        desenhado = Botao(self.app.corpo, "Salvar", variante="primario")
        self.assertEqual((desenhado.cores["normal"], desenhado.cor_borda,
                          desenhado.cor_texto),
                         ("#FFFFFF", "#1B2330", "#1B2330"))
        # o "primario" (caixa marcada, calendário) continua vermelho
        self.assertEqual(COR["primario"], estilo.PALETAS["claro"]["primario"])
        secundario = Botao(self.app.corpo, "Voltar", variante="secundario")
        self.assertEqual(secundario.cores["normal"], COR["superficie"])

    def test_caixa_marcada_fica_azul_com_os_botoes_azuis(self):
        """Corrigido na 3.5 (achado por este teste): a imagem da caixa marcada fica no cache por tema
        (componentes._cache) e não é refeita ao escolher os botões azuis:
        a caixa continua vermelha."""
        _, marcada = componentes.imagens_da_caixa(self.janela)
        t = estilo.px(18)
        ponto = (int(t * 0.3), int(t * 0.2))
        self.assertEqual("#%02X%02X%02X" % marcada.get(*ponto),
                         estilo.PALETAS["claro"]["primario"])
        self.escolher("botoes", "azul")
        imagem = self.app.tela_cadastro.chk_entra.cget("selectimage")
        cor = self.janela.tk.call(imagem, "get", *ponto)
        cor = "#%02X%02X%02X" % tuple(int(v) for v in
                                       self.janela.tk.splitlist(cor))
        self.assertEqual(cor, estilo.BOTOES["claro"]["azul"]["primario"])

    def test_espaco_e_enter_escolhem(self):
        self.janela.deiconify()
        self.janela.update()
        for tecla, (grupo, valor) in (("<space>", ("lateral", "branco")),
                                      ("<Return>", ("botoes", "azul"))):
            with self.subTest(tecla=tecla):
                opcao = self.abrir().opcoes[(grupo, valor)]
                opcao.focus_force()
                self.janela.update()
                opcao.event_generate(tecla)
                self.janela.update()
                self.assertEqual(self.app.tela_aparencia.escolhida(grupo),
                                 valor)
        self.janela.withdraw()
        self.assertEqual(self.banco.aparencia_do_usuario("ana.admin"),
                         ("branco", "azul"))
        self.assertEqual(self.no_banco(), [])          # Enter não cadastrou
        self.msg.showerror.assert_not_called()

    def test_escolher_a_que_ja_esta_marcada_nao_remonta(self):
        tela = self.abrir()
        with mock.patch.object(self.app, "_remontar") as remontar:
            tela.opcoes[("lateral", "grafite")].invocar()
            tela.opcoes[("botoes", "vermelho")].invocar()
        remontar.assert_not_called()
        self.assertIs(self.app.tela_aparencia, tela)

    def test_tema_e_letra_pela_pagina(self):
        tela = self.escolher("tema", "escuro")
        self.assertEqual(estilo.TEMA["atual"], "escuro")
        self.assertEqual(tela.escolhida("tema"), "escuro")
        tela = self.escolher("letra", "maior")
        self.assertEqual(estilo.ZOOM, estilo.ZOOMS["maior"])
        self.assertEqual(self.banco.letra_do_usuario("ana.admin"), "maior")
        self.assertEqual(tela.escolhida("letra"), "maior")
        self.assertEqual(tela.escolhida("tema"), "escuro")

    def test_tema_claro_com_o_windows_claro_fica_marcado(self):
        """Corrigido na 3.5 (achado por este teste): com a preferência "Do Windows" e o Windows no claro,
        escolher "Claro" grava no banco mas as cores não mudam, a janela
        não é remontada e a página continua marcando "Do Windows"."""
        tela = self.escolher("tema", "claro")
        self.assertEqual(self.banco.buscar_usuario("ana.admin")["tema"],
                         "claro")
        self.assertEqual(self.app.tela_aparencia.escolhida("tema"), "claro")

    def test_cores_juntas_com_o_tema_escuro(self):
        self.escolher("lateral", "vermelho")
        self.escolher("botoes", "azul")
        tela = self.escolher("tema", "escuro")
        self.assertEqual(COR["lateral"],
                         estilo.LATERAIS["escuro"]["vermelho"]["lateral"])
        self.assertEqual(COR["primario"],
                         estilo.BOTOES["escuro"]["azul"]["primario"])
        self.assertEqual((tela.escolhida("lateral"), tela.escolhida("botoes"),
                          tela.escolhida("tema")),
                         ("vermelho", "azul", "escuro"))

    def test_restaurar_o_padrao_numa_remontagem_so(self):
        self.escolher("lateral", "branco")
        self.escolher("botoes", "azul")
        self.escolher("tema", "escuro")
        tela = self.escolher("letra", "grande")
        with mock.patch.object(self.app, "_remontar",
                               wraps=self.app._remontar) as remontar:
            tela.btn_padrao.invocar()
        self.assertEqual(remontar.call_count, 1)
        self.assertEqual(self.banco.aparencia_do_usuario("ana.admin"),
                         ("grafite", "vermelho"))
        self.assertEqual(self.banco.buscar_usuario("ana.admin")["tema"],
                         TEMA_PADRAO)
        self.assertEqual(self.banco.letra_do_usuario("ana.admin"), "normal")
        self.assertEqual(estilo.APARENCIA, {"lateral": "grafite",
                                            "botoes": "vermelho"})
        self.assertEqual(estilo.TEMA["atual"], "claro")   # Windows (simulado)
        self.assertEqual(estilo.ZOOM, 1.0)
        self.assertEqual((self.app.var_tema.get(), self.app.var_letra.get()),
                         (TEMA_PADRAO, "normal"))
        tela = self.app.tela_aparencia
        self.assertEqual(self.app.abas.select(), str(self.app.aba_aparencia))
        self.assertEqual({g: tela.escolhida(g) for g in
                          ("lateral", "botoes", "tema", "letra")},
                         {"lateral": "grafite", "botoes": "vermelho",
                          "tema": "sistema", "letra": "normal"})
        self.assertEqual(self.app.tela_cadastro.ultimo_aviso,
                         "Aparência de volta ao padrão.")
        self.assertEqual(self.fios(), [])

    def test_restaurar_sem_nada_mudado_nao_remonta(self):
        tela = self.abrir()
        with mock.patch.object(self.app, "_remontar") as remontar:
            self.assertTrue(self.app.restaurar_aparencia())
        remontar.assert_not_called()
        self.assertIs(self.app.tela_aparencia, tela)

    def test_restaurar_com_o_tema_claro_escolhido_marca_do_windows(self):
        """Corrigido na 3.5 (achado por este teste): com o tema "Claro" escolhido e o Windows no claro,
        "Restaurar o padrão" grava "sistema" mas nada muda na tela (não
        remonta): a página continua marcando "Claro"."""
        self.banco.definir_tema("claro", "ana.admin")
        self.app.usuario["tema"] = "claro"
        self.app.var_tema.set("claro")
        self.app._remontar()
        tela = self.abrir()
        self.assertEqual(tela.escolhida("tema"), "claro")
        tela.btn_padrao.invocar()
        self.assertEqual(self.banco.buscar_usuario("ana.admin")["tema"],
                         "sistema")
        self.assertEqual(self.app.tela_aparencia.escolhida("tema"), "sistema")

    def test_escolha_persiste_depois_de_sair_e_entrar(self):
        self.escolher("lateral", "vermelho")
        self.escolher("botoes", "branco")
        self.app.sair()
        # a tela de login volta às cores de sempre
        self.assertEqual(estilo.APARENCIA, {"lateral": "grafite",
                                            "botoes": "vermelho"})
        self.assertEqual(COR["lateral"], estilo.PALETAS["claro"]["lateral"])
        self.assertEqual(COR["botao"], estilo.PALETAS["claro"]["primario"])
        self.assertEqual(COR["botao_texto"], COR["texto_invertido"])
        principais = [b for b in self._botoes(self.app.corpo)
                      if b.variante == "primario"]
        self.assertTrue(principais)
        for b in principais:
            if isinstance(b, BotaoTk):
                self.assertEqual(b.cget("fg").upper(), COR["texto_invertido"])
            else:
                self.assertEqual(b.cores["normal"],
                                 estilo.PALETAS["claro"]["primario"])
        self.entrar_pela_tela("ana.admin", "senha123")
        self.assertEqual(estilo.APARENCIA, {"lateral": "vermelho",
                                            "botoes": "branco"})
        self.assertEqual(self.app.lateral.cget("bg").upper(),
                         estilo.LATERAIS["claro"]["vermelho"]["lateral"])
        self.assertEqual(self.app.tela_cadastro.btn_cadastrar.cget("fg")
                         .upper(), "#1B2330")
        tela = self.abrir()
        self.assertEqual((tela.escolhida("lateral"), tela.escolhida("botoes")),
                         ("vermelho", "branco"))

    def test_outro_usuario_nao_herda_a_escolha(self):
        self.escolher("lateral", "branco")
        self.escolher("botoes", "azul")
        self.app.sair()
        self.entrar_pela_tela("paulo", "senha456")
        self.assertEqual(self.app.usuario["login"], "paulo")
        self.assertEqual(estilo.APARENCIA, {"lateral": "grafite",
                                            "botoes": "vermelho"})
        self.assertEqual(self.app.lateral.cget("bg").upper(),
                         estilo.PALETAS["claro"]["lateral"])
        self.assertEqual(COR["primario"], estilo.PALETAS["claro"]["primario"])
        self.assertEqual(self.fios(), [])
        self.assertEqual(self.banco.aparencia_do_usuario("paulo"),
                         ("grafite", "vermelho"))

    def test_trava_e_volta_com_as_cores_do_usuario(self):
        self.escolher("lateral", "vermelho")
        self.app.travar()
        self.assertEqual(estilo.APARENCIA["lateral"], "grafite")   # login
        self.entrar_pela_tela("ana.admin", "senha123")
        self.assertEqual(estilo.APARENCIA["lateral"], "vermelho")
        self.assertEqual(self.app.abas.select(), str(self.app.aba_aparencia))

    def test_formulario_do_cadastro_sobrevive_a_troca_de_cor(self):
        app = self.app
        app.tela_cadastro.var_cpf.set("5299822")          # ainda digitando
        app.nome.insert(0, "Ana Silva")
        app.celular.insert(0, "31987654321")
        app.tipo.set("Visitante")
        app.motivo.insert(0, "Reunião de obra")
        app.anfitriao.insert(0, "Diretoria")
        app.entrada.delete(0, tk.END)
        app.entrada.insert(0, "21/10/2026 09:30")
        cadastro = app.tela_cadastro
        self.escolher("lateral", "branco")
        self.escolher("botoes", "azul")
        self.assertIsNot(app.tela_cadastro, cadastro)       # remontou
        self.assertEqual(app.tela_cadastro.var_cpf.get(), "5299822")
        self.assertEqual((app.nome.get(), app.celular.get(), app.tipo.get(),
                          app.motivo.get(), app.anfitriao.get(),
                          app.entrada.get()),
                         ("Ana Silva", "31987654321", "Visitante",
                          "Reunião de obra", "Diretoria", "21/10/2026 09:30"))
        self.assertEqual(self.no_banco(), [])

    def test_erro_ao_gravar_nao_troca_as_cores(self):
        con = sqlite3.connect(self.caminho_db)       # outra estação desativou
        con.execute("UPDATE usuarios SET ativo = 0 WHERE login = 'ana.admin'")
        con.commit()
        con.close()
        self.escolher("lateral", "vermelho")
        self.msg.showerror.assert_called()
        self.assertEqual(estilo.APARENCIA["lateral"], "grafite")
        self.assertEqual(self.banco.aparencia_do_usuario("ana.admin"),
                         ("grafite", "vermelho"))

    def test_todas_as_paginas_abrem_nas_cores_extremas(self):
        self.janela.deiconify()
        for tema, lateral, botoes in (("claro", "branco", "branco"),
                                      ("escuro", "vermelho", "azul")):
            self.escolher("tema", tema)
            self.escolher("lateral", lateral)
            self.escolher("botoes", botoes)
            for aba in list(self.app.itens_menu):
                with self.subTest(tema=tema, pagina=aba):
                    self.app.ir_para(self.app.janela.nametowidget(aba))
                    self.janela.update()
        self.janela.withdraw()

    def _botoes(self, widget):
        achados = []
        for filho in widget.winfo_children():
            if isinstance(filho, (Botao, BotaoTk)):
                achados.append(filho)
            achados.extend(self._botoes(filho))
        return achados


class TestPaginaAparenciaDoPorteiro(BaseAparencia):
    entrar_como = "porteiro"

    def test_porteiro_ve_a_pagina_e_escolhe_a_sua(self):
        textos = [i.cget("text") for i in self.app.itens_menu.values()]
        self.assertEqual(textos[-1], "Aparência")
        self.assertNotIn("Usuários", textos)
        tela = self.escolher("lateral", "vermelho")
        self.assertEqual(tela.escolhida("lateral"), "vermelho")
        self.assertEqual(self.banco.aparencia_do_usuario("paulo"),
                         ("vermelho", "vermelho"))
        self.assertEqual(self.banco.aparencia_do_usuario("ana.admin"),
                         ("grafite", "vermelho"))
        self.app.sair()
        self.entrar_pela_tela("ana.admin", "senha123")
        self.assertEqual(estilo.APARENCIA["lateral"], "grafite")


# ======================================================================
# 2) Histórico da pessoa: como entrou e como saiu
# ======================================================================
class TestDescreverVeiculo(unittest.TestCase):
    """A função que monta a linha (sem banco)."""

    def visita(self, **mudancas):
        r = {"cpf": CARLA, "placa": "", "saida": "19/10/2026 10:00",
             "saiu_com": None, "carro_ficou": False, "com_estadia": True}
        r.update(mudancas)
        return r

    def carro(self, placa="BRA2E19", cpf=CARLA, nome="Carla Nogueira"):
        return {"placa": placa, "cpf": cpf, "nome": nome}

    def test_os_textos(self):
        casos = [
            (dict(placa="BRA2E19", saiu_com=self.carro()),
             "Entrou de carro (BRA2E19) · saiu de carro"),
            (dict(placa="BRA2E19", carro_ficou=True),
             "Entrou de carro (BRA2E19) · saiu a pé, o carro ficou no "
             "estacionamento"),
            (dict(cpf=BRUNO, saiu_com=self.carro("RIO3F45")),
             "Entrou a pé · saiu com o carro RIO3F45, de Carla Nogueira"),
            (dict(), "Entrou a pé · saiu a pé"),
            (dict(saiu_com=self.carro()),
             "Entrou a pé · saiu com o carro BRA2E19"),       # voltou buscar
            (dict(placa="QWE1234", saiu_com=self.carro("QWE1234")),
             "Entrou de carro (QWE-1234) · saiu de carro"),   # placa antiga
            (dict(saida="", placa="BRA2E19"), "Entrou de carro (BRA2E19)"),
            (dict(saida=""), "Entrou a pé"),
        ]
        for mudancas, esperado in casos:
            with self.subTest(esperado=esperado):
                self.assertEqual(descrever_veiculo(self.visita(**mudancas)),
                                 esperado)

    def test_visita_aberta_nao_diz_como_saiu(self):
        for mudancas in (dict(placa="BRA2E19"), dict(saiu_com=self.carro()),
                         dict(carro_ficou=True, placa="BRA2E19")):
            texto = descrever_veiculo(self.visita(saida="", **mudancas))
            self.assertNotIn("saiu", texto)

    def test_carro_ficou_sem_placa_nao_aparece(self):
        self.assertEqual(descrever_veiculo(self.visita(carro_ficou=True)),
                         "Entrou a pé · saiu a pé")

    def test_legado_sem_estadia_saiu_de_carro(self):
        """Antes do esquema v8 (e na demonstração) o carro não tinha
        estadia: saía junto com a pessoa."""
        self.assertEqual(
            descrever_veiculo(self.visita(placa="BRA2E19", com_estadia=False)),
            "Entrou de carro (BRA2E19) · saiu de carro")
        self.assertEqual(
            descrever_veiculo(self.visita(placa="BRA2E19", com_estadia=False,
                                          carro_ficou=True)),
            "Entrou de carro (BRA2E19) · saiu de carro")
        # a pé e sem estadia: continua a pé
        self.assertEqual(descrever_veiculo(self.visita(com_estadia=False)),
                         "Entrou a pé · saiu a pé")

    def test_dicionario_sem_as_chaves_novas(self):
        """Sem "com_estadia" vale como com estadia (a pé)."""
        r = {"cpf": CARLA, "placa": "BRA2E19", "saida": "19/10/2026 10:00"}
        self.assertEqual(descrever_veiculo(r), "Entrou de carro (BRA2E19) · "
                                               "saiu a pé")
        self.assertEqual(descrever_veiculo({}), "Entrou a pé")


class TestComoEntrouESaiuNoBanco(BaseAutorizadosNoBanco):
    """Carla deixou o BRA2E19 às 08:00; Bruno entrou a pé às 08:30."""

    def visitas(self, cpf):
        pessoa = self.banco.buscar_pessoa(cpf)
        return self.banco.visitas_da_pessoa(pessoa["id"])

    def textos(self, cpf):
        return [descrever_veiculo(v) for v in self.visitas(cpf)]

    def test_chaves_novas_em_toda_visita(self):
        for v in self.visitas(CARLA) + self.visitas(BRUNO):
            self.assertLessEqual({"saiu_com", "carro_ficou", "com_estadia"},
                                 set(v))
        carla, = self.visitas(CARLA)
        bruno, = self.visitas(BRUNO)
        self.assertTrue(carla["com_estadia"])
        self.assertFalse(bruno["com_estadia"])

    def test_visitas_abertas(self):
        self.assertEqual(self.textos(CARLA), ["Entrou de carro (BRA2E19)"])
        self.assertEqual(self.textos(BRUNO), ["Entrou a pé"])

    def test_dono_sai_de_carro(self):
        self.banco.registrar_saidas([self.carla], "19/10/2026 09:00",
                                    autor="paulo", com_veiculo={self.carla})
        v, = self.visitas(CARLA)
        self.assertEqual(v["saiu_com"], {"placa": "BRA2E19", "cpf": CARLA,
                                         "nome": "Carla Nogueira"})
        self.assertFalse(v["carro_ficou"])
        self.assertEqual(self.textos(CARLA),
                         ["Entrou de carro (BRA2E19) · saiu de carro"])

    def test_dono_sai_a_pe_e_o_carro_fica(self):
        self.carla_sai_a_pe()
        v, = self.visitas(CARLA)
        self.assertIsNone(v["saiu_com"])
        self.assertTrue(v["carro_ficou"])
        self.assertEqual(self.textos(CARLA),
                         ["Entrou de carro (BRA2E19) · saiu a pé, o carro "
                          "ficou no estacionamento"])

    def test_a_pe_e_a_pe(self):
        self.banco.registrar_saidas([self.bruno], "19/10/2026 09:00",
                                    autor="paulo")
        self.assertEqual(self.textos(BRUNO), ["Entrou a pé · saiu a pé"])

    def test_autorizado_leva_o_carro_de_outra_pessoa(self):
        """RN35: Bruno, da lista do BRA2E19, sai com o carro da Carla."""
        self.autorizar()
        self.carla_sai_a_pe()
        self.assertEqual(self.bruno_sai_com_o_carro(), [self.bruno])
        bruno, = self.visitas(BRUNO)
        self.assertEqual(bruno["saiu_com"], {"placa": "BRA2E19", "cpf": CARLA,
                                             "nome": "Carla Nogueira"})
        self.assertEqual(self.textos(BRUNO),
                         ["Entrou a pé · saiu com o carro BRA2E19, de Carla "
                          "Nogueira"])
        # para a Carla, o carro ficou quando ela saiu (saiu depois, com ele)
        self.assertEqual(self.textos(CARLA),
                         ["Entrou de carro (BRA2E19) · saiu a pé, o carro "
                          "ficou no estacionamento"])

    def test_nome_do_dono_e_o_do_cadastro_atual(self):
        self.autorizar()
        self.carla_sai_a_pe()
        self.bruno_sai_com_o_carro()
        con = sqlite3.connect(os.path.join(self.pasta.name, "portaria.db"))
        con.execute("UPDATE pessoas SET nome = 'Carla Nogueira Souza' "
                    "WHERE cpf = ?", (CARLA,))
        con.commit()
        con.close()
        self.assertEqual(self.textos(BRUNO),
                         ["Entrou a pé · saiu com o carro BRA2E19, de Carla "
                          "Nogueira Souza"])

    def test_dono_sai_a_pe_e_volta_para_buscar_o_carro(self):
        self.carla_sai_a_pe()                                       # 09:00
        volta = self.entrar(CARLA, "Carla Nogueira",
                            entrada="19/10/2026 09:30")             # a pé
        self.banco.registrar_saidas([volta], "19/10/2026 10:00",
                                    autor="paulo", com_veiculo={volta})
        self.assertFalse(self.no_estacionamento())
        recente, antiga = self.visitas(CARLA)
        self.assertEqual(recente["id"], volta)
        self.assertEqual(recente["saiu_com"]["placa"], "BRA2E19")
        self.assertFalse(recente["com_estadia"])
        self.assertTrue(antiga["carro_ficou"])
        self.assertEqual(self.textos(CARLA),
                         ["Entrou a pé · saiu com o carro BRA2E19",
                          "Entrou de carro (BRA2E19) · saiu a pé, o carro "
                          "ficou no estacionamento"])

    def test_desfazer_a_saida_apaga_o_carro_da_saida(self):
        self.autorizar()
        self.carla_sai_a_pe()
        self.bruno_sai_com_o_carro()
        self.assertEqual(self.banco.desfazer_saidas([self.bruno],
                                                    autor="paulo"), 1)
        self.assertTrue(self.no_estacionamento())
        bruno, = self.visitas(BRUNO)
        self.assertIsNone(bruno["saiu_com"])
        self.assertEqual(self.textos(BRUNO), ["Entrou a pé"])
        self.banco.registrar_saidas([self.bruno], "19/10/2026 10:00",
                                    autor="paulo")
        self.assertEqual(self.textos(BRUNO), ["Entrou a pé · saiu a pé"])

    def test_visita_ja_lancada_com_saida_saiu_de_carro(self):
        self.banco.inserir(registro(cpf=EVA, nome="Eva Martins",
                                    placa="RIO3F45",
                                    entrada="18/10/2026 08:00",
                                    saida="18/10/2026 12:00"), autor="paulo")
        self.assertEqual(self.textos(EVA),
                         ["Entrou de carro (RIO3F45) · saiu de carro"])

    def test_visita_antiga_sem_estadia_saiu_de_carro(self):
        """Caso legado (dados de antes do esquema v8): placa na visita e
        nenhuma estadia ligada a ela."""
        id_ = self.banco.inserir(registro(cpf=EVA, nome="Eva Martins",
                                          placa="RIO3F45",
                                          entrada="18/10/2026 08:00",
                                          saida="18/10/2026 12:00"),
                                 autor="paulo")
        con = sqlite3.connect(os.path.join(self.pasta.name, "portaria.db"))
        con.execute("DELETE FROM estadias_veiculo WHERE registro_id = ?",
                    (id_,))
        con.commit()
        con.close()
        v, = self.visitas(EVA)
        self.assertEqual((v["saiu_com"], v["carro_ficou"], v["com_estadia"]),
                         (None, False, False))
        self.assertEqual(self.textos(EVA),
                         ["Entrou de carro (RIO3F45) · saiu de carro"])

    def test_anonimizada_nao_mostra_nome_nem_placa(self):
        """Corrigido na 3.5 (LGPD; achado por este teste): a anonimização não mexe em estadias_veiculo, e o
        histórico 3.5 lê o carro de lá: a visita anonimizada mostra
        "saiu com o carro BRA2E19, de Carla Nogueira"."""
        self.banco.registrar_saidas([self.carla], "19/10/2026 09:00",
                                    autor="paulo", com_veiculo={self.carla})
        pessoa = self.banco.buscar_pessoa(CARLA)["id"]
        self.banco.anonimizar_pessoa(pessoa, "Pedido do titular por e-mail",
                                     "ana")
        texto = " ".join(descrever_veiculo(v)
                         for v in self.banco.visitas_da_pessoa(pessoa))
        self.assertNotIn("Carla", texto)
        self.assertNotIn("BRA2E19", texto)
        for v in self.banco.visitas_da_pessoa(pessoa):
            self.assertNotEqual((v["saiu_com"] or {}).get("cpf"), CARLA)


class TestHistoricoNaFicha(BaseAutorizadosNaTela):
    """Bruno, autorizado, leva o carro da Carla pela saída do Controle."""

    def setUp(self):
        super().setUp()
        self.banco.adicionar_autorizado(CARLA, BRUNO, "Bruno Almeida", None,
                                        autor="paulo")
        self.carla_sai_a_pe()

    def ficha(self, cpf):
        self.app.ir_para(self.app.aba_pessoas)
        tela = self.app.tela_pessoas
        tela.abrir_ficha(self.banco.buscar_pessoa(cpf))
        tela.seletor_ficha.selecionar("Visitas")
        return tela.lista_visitas.get("1.0", tk.END)

    def test_ficha_mostra_quem_levou_o_carro_de_quem(self):
        self.responder_veiculo = LEVA
        self.saida_rapida(BRUNO)
        self.assertIsNone(self.banco.estadia_aberta(placa="BRA2E19"))
        texto = self.ficha(BRUNO)
        self.assertIn("Entrou a pé · saiu com o carro BRA2E19, de Carla "
                      "Nogueira", texto)
        texto = self.ficha(CARLA)
        self.assertIn("Entrou de carro (BRA2E19) · saiu a pé, o carro ficou "
                      "no estacionamento", texto)
        visita, = self.app.tela_pessoas.visitas
        self.assertEqual(visita["veiculo"], "Entrou de carro (BRA2E19) · "
                                            "saiu a pé, o carro ficou no "
                                            "estacionamento")

    def test_ficha_com_a_visita_aberta_so_diz_como_entrou(self):
        texto = self.ficha(BRUNO)
        self.assertIn("Entrou a pé\n", texto)
        self.assertNotIn("saiu", texto.split("Entrou a pé")[1].split("\n")[0])

    def test_sem_levar_o_carro_sai_a_pe(self):
        self.banco.registrar_saidas([self.bruno], self.agora.strftime(
            "%d/%m/%Y %H:%M"), autor="paulo")
        texto = self.ficha(BRUNO)
        self.assertIn("Entrou a pé · saiu a pé", texto)


# ======================================================================
# 3) Entregador no Cadastro
# ======================================================================
CAMPOS_DA_PESSOA = {"cpf", "nome", "celular", "placa", "data", "hora",
                    "saida", "motivo", "anfitriao"}


# 3.6: o destinatário da encomenda é uma pessoa do cadastro (sem visita)
DESTINATARIOS = ("Helena Souza", "Rafael Lima", "Marcos Lima", "Ana d'Ávila",
                 " ".join(("  Helena   Souza  " + "x" * 200)[:MAXIMO_NOME]
                          .split()))


class BaseEntregador(BaseInterface):
    def setUp(self):
        super().setUp()
        self.tela = self.app.tela_cadastro
        for n, nome in enumerate(DESTINATARIOS):
            self.banco.cadastrar_pessoa(
                dados_modulos.cpf_ficticio(284759163 + n), nome,
                "31987654321", "", "Funcionário", "ana.admin")

    def visiveis(self):
        self.janela.update_idletasks()
        return {chave for chave, (rotulo, campo) in self.tela.pecas.items()
                if campo.winfo_manager()}

    def rotulos_visiveis(self):
        self.janela.update_idletasks()
        return {chave for chave, (rotulo, campo) in self.tela.pecas.items()
                if rotulo.winfo_manager()}

    def entrega(self, destinatario="Helena Souza", bloco="Bloco B",
                remetente="Correios", descricao="Envelope registrado"):
        self.app.tipo.set("Entregador")
        t = self.tela
        for campo, valor in ((t.destinatario, destinatario), (t.bloco, bloco),
                             (t.remetente, remetente),
                             (t.descricao, descricao)):
            campo.delete(0, tk.END)
            campo.insert(0, valor)

    def destravar(self, login, senha):
        tela = self.app.tela_login
        tela.campo_login.delete(0, tk.END)
        tela.campo_login.insert(0, login)
        tela.campo_senha.insert(0, senha)
        tela.entrar()


class TestEntregadorSoDeixaAEntrega(BaseEntregador):
    def test_formulario_vira_o_da_encomenda(self):
        self.app.tipo.set("Entregador")
        t = self.tela
        self.assertTrue(t.so_entrega())
        self.assertFalse(t.var_entra.get())
        esperado = {"tipo"} | set(CAMPOS_DA_ENCOMENDA)
        self.assertEqual(self.visiveis(), esperado)
        self.assertEqual(self.rotulos_visiveis(), esperado)
        self.assertEqual(t.chk_entra.winfo_manager(), "grid")
        self.assertEqual(t.chk_entra.cget("text"), "Vai entrar na unidade")
        self.assertEqual(t.btn_cadastrar.cget("text"), "Registrar encomenda")
        self.assertEqual(t.ficha.winfo_manager(), "")
        self.assertEqual(t.divisor_ficha.winfo_manager(), "")
        self.assertEqual(t.lbl_pessoa.cget("text"), DICA_ENTREGA)
        self.assertEqual(t.titulo_form.cget("text"), "Entrega")
        self.assertEqual(t.titulo_visita.cget("text"), "Encomenda")

    def test_campos_da_pessoa_somem_de_verdade(self):
        self.janela.deiconify()
        self.janela.geometry("1280x800")
        self.app.tipo.set("Entregador")
        self.janela.update()
        t = self.tela
        for chave in CAMPOS_DA_PESSOA:
            with self.subTest(campo=chave):
                self.assertFalse(t.pecas[chave][1].winfo_ismapped())
        for chave in CAMPOS_DA_ENCOMENDA:
            with self.subTest(campo=chave):
                self.assertTrue(t.pecas[chave][1].winfo_ismapped())
        self.assertTrue(t.chk_entra.winfo_ismapped())
        self.assertTrue(t.btn_cadastrar.winfo_ismapped())
        self.janela.withdraw()

    def test_outros_tipos_nao_tem_a_encomenda_nem_a_marca(self):
        for tipo in ("", "Aluno", "Professor", "Funcionário", "Visitante",
                     "Prestador de serviço"):
            with self.subTest(tipo=tipo):
                self.app.tipo.set(tipo)
                self.assertFalse(self.tela.so_entrega())
                self.assertFalse(set(CAMPOS_DA_ENCOMENDA) & self.visiveis())
                self.assertEqual(self.tela.chk_entra.winfo_manager(), "")
                self.assertEqual(self.tela.btn_cadastrar.cget("text"),
                                 "Cadastrar")
                self.assertEqual(self.tela.ficha.winfo_manager(), "pack")

    def test_registrar_encomenda_vai_para_encomendas_sem_visita(self):
        self.entrega()
        self.tela.btn_cadastrar.invoke()
        encomenda, = self.banco.listar_encomendas()
        self.assertEqual((encomenda["destinatario"], encomenda["setor"],
                          encomenda["remetente"], encomenda["descricao"],
                          encomenda["recebida_por"], encomenda["retirada_em"]),
                         ("Helena Souza", "Bloco B", "Correios",
                          "Envelope registrado", "ana.admin", ""))
        self.assertEqual(encomenda["recebida_em"], "21/10/2026 10:00")
        self.assertEqual(self.no_banco(), [])                # nenhuma visita
        self.assertEqual(self.banco.buscar_pessoa("52998224725"), None)
        self.assertIn(("ana.admin", "Encomenda recebida"), self.acoes())
        self.assertNotIn(("ana.admin", "Cadastro de entrada"), self.acoes())
        self.msg.showerror.assert_not_called()

    def test_confirmacao_limpa_e_leva_a_encomendas(self):
        self.entrega()
        self.tela.cadastrar()
        t = self.tela
        texto = t.lbl_pessoa.cget("text")
        self.assertEqual(texto, "Encomenda nº 001 para Helena Souza "
                                "registrada.")
        self.assertEqual(t.aviso_pessoa.tipo, "sucesso")
        self.assertEqual(t.aviso_pessoa.acao.cget("text"), "Ver encomendas")
        self.assertEqual(t.ultimo_aviso, texto)
        # o formulário volta limpo e ao normal
        self.assertEqual((self.app.tipo.get(), t.destinatario.get(),
                          t.bloco.get(), t.remetente.get(),
                          t.descricao.get()), ("", "", "", "", ""))
        self.assertFalse(t.var_entra.get())
        self.assertEqual(t.btn_cadastrar.cget("text"), "Cadastrar")
        self.assertEqual(t.ficha.winfo_manager(), "pack")
        # a segunda é a nº 002
        self.entrega(destinatario="Rafael Lima", remetente="Kalunga",
                     bloco="", descricao="")
        t.cadastrar()
        self.assertIn("Encomenda nº 002 para Rafael Lima",
                      t.lbl_pessoa.cget("text"))
        # "Ver encomendas" abre a página com as duas aguardando
        t.aviso_pessoa.comando()
        self.assertEqual(self.app.abas.select(), str(self.app.aba_encomendas))
        pagina = self.app.tela_encomendas
        linhas = pagina.tabela.get_children()
        self.assertEqual(len(linhas), 2)
        destinatarios = {pagina.tabela.set(l, "destinatario") for l in linhas}
        self.assertEqual(destinatarios, {"Helena Souza", "Rafael Lima"})
        for linha in linhas:
            self.assertEqual(pagina.tabela.item(linha)["text"],
                             "Aguardando retirada")
        self.assertIn("2 aguardando", pagina.lbl_total.cget("text"))

    def test_enter_registra_a_encomenda(self):
        self.entrega()
        self.app.cadastrar(event=mock.Mock())           # Enter num campo
        self.assertEqual(len(self.banco.listar_encomendas()), 1)
        self.assertEqual(self.no_banco(), [])

    def test_enter_na_descricao_registra_uma_vez_so(self):
        self.entrega()
        self.janela.deiconify()
        self.janela.update()
        texto = self.tela.descricao.texto
        texto.focus_force()
        self.janela.update()
        texto.event_generate("<Return>")
        self.janela.withdraw()
        self.assertEqual(len(self.banco.listar_encomendas()), 1)
        self.msg.showerror.assert_not_called()          # sem o 2º Enter
        self.assertEqual(self.no_banco(), [])

    def test_enter_fora_do_cadastro_nao_registra(self):
        self.entrega()
        self.app.ir_para(self.app.aba_controle)
        self.app.cadastrar(event=mock.Mock())
        self.assertEqual(self.banco.listar_encomendas(), [])

    def test_destinatario_e_remetente_obrigatorios(self):
        for destinatario, remetente, trecho in (
                ("", "Correios", "destinatário"),
                ("   ", "Correios", "destinatário"),
                ("Helena Souza", "", "remetente"),
                ("Helena Souza", "  ", "remetente"),
                ("", "", "destinatário")):
            with self.subTest(destinatario=destinatario, remetente=remetente):
                self.msg.reset_mock()
                self.entrega(destinatario=destinatario, remetente=remetente)
                self.assertIsNone(self.tela.registrar_encomenda())
                self.msg.showerror.assert_called_once()
                titulo, mensagem = self.msg.showerror.call_args[0][:2]
                self.assertEqual(titulo, "Dados inválidos")
                self.assertIn(trecho, mensagem.lower())
                # nada some do formulário
                self.assertEqual(self.tela.bloco.get(), "Bloco B")
                self.assertTrue(self.tela.so_entrega())
        self.assertEqual(self.banco.listar_encomendas(), [])
        self.assertEqual(self.no_banco(), [])

    def test_tamanhos_e_espacos(self):
        """Colar texto comprido corta no máximo de cada campo; os espaços
        a mais saem antes de gravar."""
        self.app.tipo.set("Entregador")
        t = self.tela
        t.pecas["destinatario"][1].colar("  Helena   Souza  " + "x" * 200)
        t.pecas["remetente"][1].colar("C" * 300)
        t.pecas["bloco"][1].colar("B" * 200)
        t.descricao.insert(0, "D" * 500)
        self.assertEqual(len(t.destinatario.get()), MAXIMO_NOME)
        self.assertEqual(len(t.remetente.get()), MAXIMO_REMETENTE)
        self.assertEqual(len(t.bloco.get()), MAXIMO_LOCAL)
        self.assertEqual(len(t.descricao.get()), MAXIMO_DESCRICAO_ENCOMENDA)
        self.assertEqual(t.registrar_encomenda(), 1)
        e, = self.banco.listar_encomendas()
        self.assertTrue(e["destinatario"].startswith("Helena Souza x"))
        self.assertEqual((len(e["remetente"]), len(e["setor"]),
                          len(e["descricao"])),
                         (MAXIMO_REMETENTE, MAXIMO_LOCAL,
                          MAXIMO_DESCRICAO_ENCOMENDA))

    def test_digitar_alem_do_maximo_nao_entra(self):
        self.app.tipo.set("Entregador")
        self.tela.destinatario.insert(0, "x" * (MAXIMO_NOME + 1))
        self.assertEqual(self.tela.destinatario.get(), "")
        self.tela.destinatario.insert(0, "x" * MAXIMO_NOME)
        self.assertEqual(len(self.tela.destinatario.get()), MAXIMO_NOME)

    def test_cpf_na_descricao_vai_mascarado(self):
        self.entrega(descricao="Entregue por 529.982.247-25")
        self.tela.cadastrar()
        e, = self.banco.listar_encomendas()
        self.assertNotIn("529.982.247-25", e["descricao"])
        self.assertNotIn("52998224725", e["descricao"])

    def test_texto_com_marcacao_e_sql_e_gravado_como_texto(self):
        self.entrega(destinatario="Ana d'Ávila",
                     remetente="'; DROP TABLE encomendas; --",
                     descricao="<b>frágil</b>")
        self.tela.cadastrar()
        e, = self.banco.listar_encomendas()
        self.assertEqual((e["destinatario"], e["remetente"], e["descricao"]),
                         ("Ana d'Ávila", "'; DROP TABLE encomendas; --",
                          "<b>frágil</b>"))

    def test_sair_da_entrega_volta_a_faixa_de_antes(self):
        self.app.tipo.set("Entregador")
        self.assertEqual(self.tela.lbl_pessoa.cget("text"), DICA_ENTREGA)
        self.app.tipo.set("Visitante")
        self.assertEqual(self.tela.lbl_pessoa.cget("text"), DICA_CPF)
        self.assertEqual(self.tela.titulo_form.cget("text"), "Pessoa")
        self.assertEqual(self.tela.ficha.winfo_manager(), "pack")

    def test_limpar_volta_ao_normal(self):
        self.entrega()
        self.app.limpar()
        self.assertFalse(self.tela.so_entrega())
        self.assertEqual(self.tela.destinatario.get(), "")
        self.assertEqual(self.tela.btn_cadastrar.cget("text"), "Cadastrar")
        self.assertFalse(set(CAMPOS_DA_ENCOMENDA) & self.visiveis())


class TestEntregadorQueVaiEntrar(BaseEntregador):
    def test_marcar_vai_entrar_volta_o_cadastro_da_pessoa(self):
        self.entrega()
        self.tela.chk_entra.invoke()
        t = self.tela
        self.assertTrue(t.var_entra.get())
        self.assertFalse(t.so_entrega())
        self.assertEqual(self.visiveis(), CAMPOS_DA_PESSOA | {"tipo"})
        self.assertEqual(t.chk_entra.winfo_manager(), "grid")
        self.assertEqual(t.btn_cadastrar.cget("text"), "Cadastrar")
        self.assertEqual(t.ficha.winfo_manager(), "pack")
        self.assertEqual(t.titulo_form.cget("text"), "Pessoa")
        # desmarcar volta à entrega com o que estava digitado
        t.chk_entra.invoke()
        self.assertTrue(t.so_entrega())
        self.assertEqual((t.destinatario.get(), t.remetente.get()),
                         ("Helena Souza", "Correios"))

    def test_entregador_que_entra_e_cadastrado_como_visita(self):
        self.preencher(tipo="Entregador")       # CPF e nome já digitados
        t = self.tela
        self.assertTrue(t.var_entra.get())
        self.assertFalse(t.so_entrega())
        self.app.motivo.delete(0, tk.END)
        self.app.motivo.insert(0, "Entrega de móveis no bloco B")
        self.app.anfitriao.insert(0, "Almoxarifado")
        self.app.cadastrar()
        r, = self.no_banco()
        self.assertEqual((r["tipo"], r["motivo"], r["anfitriao"]),
                         ("Entregador", "Entrega de móveis no bloco B",
                          "Almoxarifado"))
        self.assertEqual(self.banco.listar_encomendas(), [])

    def test_com_cpf_ou_nome_ja_digitado_a_marca_vem_ligada(self):
        for campo, valor in (("cpf", "52998224725"), ("cpf", "529"),
                             ("nome", "Ana Silva")):
            with self.subTest(campo=campo, valor=valor):
                self.app.limpar()
                getattr(self.app, campo).insert(0, valor)
                self.app.tipo.set("Entregador")
                self.assertTrue(self.tela.var_entra.get())
                self.assertFalse(self.tela.so_entrega())
        self.app.limpar()
        self.app.nome.insert(0, "   ")                    # só espaços
        self.app.tipo.set("Entregador")
        self.assertTrue(self.tela.so_entrega())

    def test_cpf_de_quem_e_cadastrado_como_entregador(self):
        self.banco.inserir(registro(cpf=EVA, nome="Eva Martins", placa="",
                                    tipo="Entregador", motivo="Entrega",
                                    entrada="20/10/2026 08:00",
                                    saida="20/10/2026 08:30"),
                           autor="ana.admin")
        self.app.cpf.insert(0, EVA)
        t = self.tela
        self.assertEqual(self.app.tipo.get(), "Entregador")
        self.assertTrue(t.var_entra.get())
        self.assertFalse(t.so_entrega())
        self.assertIn("motivo", self.visiveis())
        self.app.cadastrar()
        self.assertEqual(len(self.no_banco()), 2)
        self.assertEqual(self.banco.listar_encomendas(), [])

    def test_ficha_da_pessoa_entregador_vem_para_entrar(self):
        self.banco.inserir(registro(cpf=EVA, nome="Eva Martins", placa="",
                                    tipo="Entregador", motivo="Entrega",
                                    entrada="20/10/2026 08:00",
                                    saida="20/10/2026 08:30"),
                           autor="ana.admin")
        self.app.ir_para(self.app.aba_pessoas)
        pessoas = self.app.tela_pessoas
        pessoas.abrir_ficha(self.banco.buscar_pessoa(EVA))
        pessoas.registrar_entrada()
        self.assertEqual(self.app.abas.select(), str(self.app.aba_cad))
        self.assertEqual(self.app.tipo.get(), "Entregador")
        self.assertTrue(self.tela.var_entra.get())
        self.assertFalse(self.tela.so_entrega())

    def test_autorizacao_de_entregador_vem_para_entrar(self):
        self.app.ir_para(self.app.aba_autorizacoes)
        pagina = self.app.tela_autorizacoes
        d = pagina.novo()
        d.cpf.insert(0, "52998224725")
        d.nome.insert(0, "Ana Silva")
        d.tipo.set("Entregador")
        d.anfitriao.insert(0, "Almoxarifado")
        d.motivo.insert(0, "Entrega de móveis")
        self.assertTrue(d.salvar())
        pagina.registrar_entrada()
        self.assertEqual(self.app.abas.select(), str(self.app.aba_cad))
        self.assertEqual(self.app.tipo.get(), "Entregador")
        self.assertTrue(self.tela.var_entra.get())
        self.assertFalse(self.tela.so_entrega())
        self.assertEqual(self.app.anfitriao.get(), "Almoxarifado")
        self.app.celular.insert(0, "31987654321")
        self.app.cadastrar()
        r, = self.no_banco()
        self.assertEqual(r["tipo"], "Entregador")


class TestRascunhoDaEncomenda(BaseEntregador):
    def test_travar_e_voltar_mantem_o_rascunho(self):
        self.entrega()
        self.app.travar()
        self.assertIsNone(self.app.usuario)
        self.destravar("ana.admin", "senha123")
        t = self.app.tela_cadastro
        self.assertTrue(t.so_entrega())
        self.assertEqual((self.app.tipo.get(), t.destinatario.get(),
                          t.bloco.get(), t.remetente.get(), t.descricao.get()),
                         ("Entregador", "Helena Souza", "Bloco B", "Correios",
                          "Envelope registrado"))
        self.assertEqual(t.btn_cadastrar.cget("text"), "Registrar encomenda")
        self.assertEqual(t.ficha.winfo_manager(), "")
        t.cadastrar()
        self.assertEqual(len(self.banco.listar_encomendas()), 1)

    def test_travar_mantem_o_vai_entrar(self):
        self.app.tipo.set("Entregador")
        self.tela.chk_entra.invoke()
        self.app.nome.insert(0, "Eva Martins")
        self.app.travar()
        self.destravar("ana.admin", "senha123")
        t = self.app.tela_cadastro
        self.assertTrue(t.var_entra.get())
        self.assertFalse(t.so_entrega())
        self.assertEqual(self.app.nome.get(), "Eva Martins")
        self.assertEqual(t.btn_cadastrar.cget("text"), "Cadastrar")

    def test_troca_de_turno_descarta_o_rascunho(self):
        self.entrega()
        self.app.travar()
        self.destravar("paulo", "senha456")
        t = self.app.tela_cadastro
        self.assertFalse(t.so_entrega())
        self.assertEqual(t.destinatario.get(), "")

    def test_rascunho_sobrevive_a_troca_de_cor(self):
        self.addCleanup(estilo.usar_aparencia, "grafite", "vermelho")
        self.entrega()
        self.assertTrue(self.app.trocar_aparencia(botoes="azul"))
        t = self.app.tela_cadastro
        self.assertIsNot(t, self.tela)
        self.assertTrue(t.so_entrega())
        self.assertEqual((t.destinatario.get(), t.remetente.get(),
                          t.bloco.get(), t.descricao.get()),
                         ("Helena Souza", "Correios", "Bloco B",
                          "Envelope registrado"))
        self.assertEqual(t.btn_cadastrar.cget("text"), "Registrar encomenda")

    def test_faixa_da_entrega_volta_depois_da_remontagem(self):
        """Corrigido na 3.5 (achado por este teste): ao remontar (troca de cor, de tema, de letra) ou ao
        destravar a guarita com o rascunho da encomenda, o CPF (vazio) é
        devolvido por último e a faixa vira "Digite o CPF primeiro..."
        com o campo CPF escondido; devia continuar a dica da entrega."""
        self.addCleanup(estilo.usar_aparencia, "grafite", "vermelho")
        self.entrega()
        self.assertEqual(self.tela.lbl_pessoa.cget("text"), DICA_ENTREGA)
        self.app.trocar_aparencia(botoes="azul")
        t = self.app.tela_cadastro
        self.assertTrue(t.so_entrega())
        self.assertEqual(t.lbl_pessoa.cget("text"), DICA_ENTREGA)

    def test_ler_formulario_guarda_entra_e_os_campos(self):
        self.entrega()
        estado = self.tela.ler_formulario()
        self.assertEqual((estado["entra"], estado["destinatario"],
                          estado["bloco"], estado["remetente"],
                          estado["descricao"]),
                         (False, "Helena Souza", "Bloco B", "Correios",
                          "Envelope registrado"))
        self.tela.chk_entra.invoke()
        self.assertTrue(self.tela.ler_formulario()["entra"])


class TestEncomendaDoPorteiro(BaseEntregador):
    entrar_como = "porteiro"

    def test_porteiro_registra_e_a_pagina_mostra(self):
        self.entrega(destinatario="Marcos Lima", bloco="", descricao="")
        self.tela.cadastrar()
        e, = self.banco.listar_encomendas()
        self.assertEqual((e["recebida_por"], e["setor"]), ("paulo", ""))
        self.app.ir_para(self.app.aba_encomendas)
        pagina = self.app.tela_encomendas
        linha, = pagina.tabela.get_children()
        self.assertEqual(pagina.tabela.set(linha, "destinatario"),
                         "Marcos Lima")
        self.assertEqual(pagina.tabela.item(linha)["text"],
                         "Aguardando retirada")


if __name__ == "__main__":
    unittest.main()


# ----------------------------------------------------------------------
# O símbolo novo (3.5: "Cancela suave"), na barra lateral, no login e no .ico
# ----------------------------------------------------------------------
RAIZ_DO_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _imagem(raiz, t, cor, traco, grande=False):
    return tk.PhotoImage(master=raiz, format="png",
                         data=componentes._png_da_cancela(t, cor, traco, grande))


def _pixel(t, u, grande=False):
    """O pixel da imagem t x t que fica no ponto u (em unidades 0..256)."""
    margem = 8 if grande else 0
    k = t * (256 - 2 * margem) / 256 / 256
    return tuple(int(margem * t / 256 + v * k) for v in u)


class TestDesenhoDaCancela(unittest.TestCase):
    """O desenho em si (sem a janela do programa): placa, cancela, bordas."""

    def setUp(self):
        self.raiz = tk.Tk()
        self.raiz.withdraw()
        self.addCleanup(self.raiz.destroy)

    def cor(self, img, xy):
        return tuple(img.get(*xy))

    def test_cantos_transparentes_e_placa_opaca(self):
        img = _imagem(self.raiz, 36, "#FFFFFF", "#B00017")
        self.assertEqual((img.width(), img.height()), (36, 36))
        for canto in ((0, 0), (35, 0), (0, 35), (35, 35)):
            self.assertTrue(img.transparency_get(*canto), canto)
        self.assertFalse(img.transparency_get(18, 18))

    def test_placa_e_cancela_nas_cores_pedidas(self):
        img = _imagem(self.raiz, 36, "#FFFFFF", "#B00017")
        self.assertEqual(self.cor(img, _pixel(36, (200, 170))),
                         (255, 255, 255))                       # só placa
        self.assertEqual(self.cor(img, _pixel(36, (74, 146))),
                         (0xB0, 0x00, 0x17))                    # o poste
        self.assertEqual(self.cor(img, _pixel(36, (72, 220))),
                         (255, 255, 255))                       # abaixo da base

    def test_parafuso_e_listras_sao_recortes(self):
        img = _imagem(self.raiz, 72, "#FFFFFF", "#B00017")
        self.assertEqual(self.cor(img, _pixel(72, (72, 96))),
                         (255, 255, 255))                       # parafuso
        self.assertEqual(self.cor(img, _pixel(72, (125, 96))),
                         (255, 255, 255))                       # 1ª listra
        self.assertEqual(self.cor(img, _pixel(72, (150, 96))),
                         (0xB0, 0x00, 0x17))                    # entre listras

    def test_bordas_suaves_sem_serrilhado(self):
        """Nas bordas o pixel mistura as duas cores (antes eram blocos)."""
        img = _imagem(self.raiz, 36, "#FFFFFF", "#B00017")
        cores = {self.cor(img, (x, y)) for x in range(36) for y in range(36)
                 if not img.transparency_get(x, y)}
        self.assertGreater(len(cores), 10)

    def test_placa_vermelha_tem_esmalte_mais_claro_em_cima(self):
        img = _imagem(self.raiz, 36, "#D9001B", "#FFFFFF")
        cima = self.cor(img, _pixel(36, (230, 40)))
        baixo = self.cor(img, _pixel(36, (230, 230)))
        self.assertGreater(sum(cima), sum(baixo))
        for r, g, b in (cima, baixo):
            self.assertGreater(r, 150)
            self.assertLess(g, 60)

    def test_placa_branca_sem_esmalte(self):
        img = _imagem(self.raiz, 36, "#FFFFFF", "#B00017")
        self.assertEqual(self.cor(img, _pixel(36, (230, 40))),
                         self.cor(img, _pixel(36, (230, 230))))

    def test_grande_tem_o_braco_erguido(self):
        """Em 48 px lógicos ou mais o braço sobe 12 graus, como no .ico."""
        ponto = (187, 71)        # acima do braço deitado, dentro do erguido
        grande = _imagem(self.raiz, 112, "#FFFFFF", "#B00017", grande=True)
        deitado = _imagem(self.raiz, 112, "#FFFFFF", "#B00017")
        self.assertEqual(self.cor(grande, _pixel(112, ponto, True)),
                         (0xB0, 0x00, 0x17))
        self.assertEqual(self.cor(deitado, _pixel(112, ponto)),
                         (255, 255, 255))

    def test_desenhar_e_rapido(self):
        import time
        inicio = time.perf_counter()
        componentes._png_da_cancela(90, "#D9001B", "#FFFFFF")  # 36 em 250%
        self.assertLess(time.perf_counter() - inicio, 0.5)

    def test_imagem_guardada_por_tamanho_e_cor(self):
        a = componentes.imagem_da_cancela(self.raiz, 36, "#D9001B", "#FFFFFF")
        b = componentes.imagem_da_cancela(self.raiz, 36, "#D9001B", "#FFFFFF")
        c = componentes.imagem_da_cancela(self.raiz, 36, "#FFFFFF", "#B00017")
        self.assertIs(a, b)
        self.assertIsNot(a, c)


class TestArquivosDoIcone(unittest.TestCase):
    """assets/portaria.ico (janela e .exe) e assets/logo_portaria.png."""

    def test_ico_tem_todos_os_tamanhos(self):
        import struct
        with open(os.path.join(RAIZ_DO_PROJETO, "assets", "portaria.ico"),
                  "rb") as f:
            dados_ico = f.read()
        reservado, tipo, n = struct.unpack("<HHH", dados_ico[:6])
        self.assertEqual((reservado, tipo), (0, 1))
        lados = {dados_ico[6 + 16 * i] or 256 for i in range(n)}
        self.assertEqual(lados, {16, 24, 32, 48, 64, 128, 256})

    def test_logo_do_login_placa_branca_cancela_vermelha(self):
        raiz = tk.Tk()
        raiz.withdraw()
        self.addCleanup(raiz.destroy)
        logo = tk.PhotoImage(master=raiz, file=os.path.join(
            RAIZ_DO_PROJETO, "assets", "logo_portaria.png"))
        self.assertEqual((logo.width(), logo.height()), (72, 72))
        self.assertTrue(logo.transparency_get(0, 0))
        self.assertEqual(tuple(logo.get(*_pixel(72, (200, 170), True))),
                         (255, 255, 255))
        self.assertEqual(tuple(logo.get(*_pixel(72, (74, 146), True))),
                         (217, 0, 27))

    def test_gerador_e_o_programa_usam_as_mesmas_medidas(self):
        with open(os.path.join(RAIZ_DO_PROJETO, "assets", "gerar_icone.py"),
                  encoding="utf-8") as f:
            gerador = f.read()
        self.assertIn("cx, cy, meia = 72, 96, 18", gerador)
        self.assertIn("for x in (124, 166, 208)", gerador)
        self.assertEqual(componentes.EIXO_DA_CANCELA, (72, 96))
        self.assertEqual(componentes.MEIA_ALTURA_DO_BRACO, 18)
        self.assertEqual(componentes.LISTRAS_DO_BRACO, (124, 166, 208))


class TestSimboloNaJanela(BaseAparencia):
    def test_simbolo_da_barra_e_uma_imagem_de_36(self):
        simbolo = self.simbolo()
        self.assertIsInstance(simbolo, tk.Label)
        self.assertEqual(int(simbolo.imagem.width()), estilo.px(36))
        self.assertEqual(simbolo.cget("bg").upper(), COR["lateral"].upper())

    def test_cores_do_simbolo_em_cada_barra_e_tema(self):
        for tema in ("claro", "escuro"):
            self.app.trocar_tema(tema)
            for lateral in LATERAIS:
                with self.subTest(tema=tema, lateral=lateral):
                    self.app.trocar_aparencia(lateral=lateral,
                                              botoes="vermelho")
                    self.assertEqual(self.simbolo().cores,
                                     (COR["lateral_simbolo"].upper(),
                                      COR["lateral_simbolo_traco"].upper()))

    def test_login_mostra_o_logo_novo(self):
        self.app.sair()
        tela = self.app.tela_login
        self.assertIsNotNone(tela.logo)
        self.assertEqual(int(tela.logo.width()), 72)
