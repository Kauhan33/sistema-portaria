"""
Aba Dashboard: cards com os números do movimento e dois gráficos (pessoas
por tipo de acesso e entradas nos últimos 7 dias). Os números vêm de
consultas.resumo(); o desenho dos gráficos fica em graficos.py.
"""

import tkinter as tk
from datetime import datetime

from .consultas import formatar_duracao, resumo
from .estilo import COR, CORES_RESUMO, CORES_TIPO, COR_GRAFICO_DIAS, FONTE
from .graficos import desenhar_barras_horizontais, desenhar_barras_verticais
from .validacao import TIPOS_ACESSO

PLURAL_TIPO = {"Aluno": "Alunos", "Professor": "Professores",
               "Funcionário": "Funcionários", "Visitante": "Visitantes",
               "Entregador": "Entregadores",
               "Prestador de serviço": "Prestadores"}
CARDS_RESUMO = [("total", "TOTAL DE REGISTROS"), ("dentro", "DENTRO AGORA"),
                ("hoje", "ENTRADAS HOJE"), ("veiculos", "COM VEÍCULO"),
                ("permanencia", "PERMANÊNCIA MÉDIA")]
ALTURA_GRAFICO = 260


class AbaDashboard:
    def __init__(self, aba, app):
        self.aba = aba
        self.app = app
        self.cards = {}                            # chave -> (valor, apoio)
        self.dados = {"tipos": [], "dias": []}     # dados prontos dos gráficos

        self._montar_cards(TIPOS_ACESSO, PLURAL_TIPO, CORES_TIPO, pady=(14, 0))
        self._montar_cards([c for c, _ in CARDS_RESUMO], dict(CARDS_RESUMO),
                           CORES_RESUMO)
        self._montar_graficos()

    # --------------------------------------------------------------
    # Montagem
    # --------------------------------------------------------------
    def _montar_cards(self, chaves, titulos, cores, pady=0):
        """Uma linha de cards de mesma largura, um para cada chave."""
        linha = tk.Frame(self.aba, bg=COR["fundo"])
        linha.pack(fill="x", padx=15, pady=pady)
        linha.columnconfigure(tuple(range(len(chaves))), weight=1,
                              uniform=f"cards{len(chaves)}")
        for coluna, chave in enumerate(chaves):
            self._criar_card(linha, coluna, chave, titulos[chave], cores[chave])

    def _criar_card(self, pai, coluna, chave, titulo, cor):
        caixa = tk.Frame(pai, bg=COR["superficie"],
                         highlightbackground=COR["borda"], highlightthickness=1)
        caixa.grid(row=0, column=coluna, sticky="nsew", padx=5, pady=5)
        tk.Frame(caixa, bg=cor, height=4).pack(fill="x")
        tk.Label(caixa, text=titulo, bg=COR["superficie"],
                 fg=COR["texto_rotulo"], font=FONTE["rotulo"]
                 ).pack(anchor="w", padx=12, pady=(8, 0))
        valor = tk.Label(caixa, text="0", bg=COR["superficie"],
                         fg=COR["texto"], font=FONTE["kpi"])
        valor.pack(anchor="w", padx=12)
        apoio = tk.Label(caixa, text="", bg=COR["superficie"],
                         fg=COR["texto_apoio"], font=FONTE["dica"])
        apoio.pack(anchor="w", padx=12, pady=(0, 8))
        self.cards[chave] = (valor, apoio)

    def _montar_graficos(self):
        area = tk.Frame(self.aba, bg=COR["fundo"])
        area.pack(fill="both", expand=True, padx=15, pady=(6, 14))
        area.columnconfigure((0, 1), weight=1, uniform="g")
        area.rowconfigure(0, weight=1)
        self.cv_tipos, self.cv_dias = [self._novo_canvas(area, c) for c in (0, 1)]

    def _novo_canvas(self, area, coluna):
        cv = tk.Canvas(area, bg=COR["superficie"], height=ALTURA_GRAFICO,
                       highlightbackground=COR["borda"], highlightthickness=1)
        cv.grid(row=0, column=coluna, sticky="nsew", padx=5, pady=5)
        cv.bind("<Configure>", self.redesenhar_graficos)
        return cv

    # --------------------------------------------------------------
    # Dados
    # --------------------------------------------------------------
    def atualizar(self):
        """Recalcula os números a partir de app.registros."""
        hoje = datetime.now().date()
        r = resumo(self.app.registros, hoje)
        por_tipo = r["por_tipo"]

        for t in TIPOS_ACESSO:
            total_t, dentro_t = por_tipo[t]
            self._mostrar(t, total_t, f"{dentro_t} dentro agora")
        self._mostrar("total", r["total"], "desde o início")
        self._mostrar("dentro", r["dentro"],
                      f"{r['total'] - r['dentro']} já saíram")
        self._mostrar("hoje", r["entradas_hoje"], hoje.strftime("%d/%m/%Y"))
        self._mostrar("veiculos", r["com_veiculo"], "registros com placa")
        if r["permanencia_media"] is not None:
            self._mostrar("permanencia", formatar_duracao(r["permanencia_media"]),
                          f"{r['saidas']} saídas")
        else:
            self._mostrar("permanencia", "—", "sem saídas registradas")

        total = r["total"]
        self.dados["tipos"] = [
            (PLURAL_TIPO.get(t, t), por_tipo[t][0],
             f"{por_tipo[t][0]} ({por_tipo[t][0] * 100 // total if total else 0}%)"
             f" · {por_tipo[t][1]} dentro",
             CORES_TIPO.get(t, COR["texto_vazio"]))
            for t in TIPOS_ACESSO]
        self.dados["dias"] = [(d.strftime("%d/%m"), n)
                              for d, n in r["por_dia"].items()]
        self.redesenhar_graficos()

    def _mostrar(self, chave, valor, apoio):
        self.cards[chave][0].config(text=str(valor))
        self.cards[chave][1].config(text=apoio)

    def redesenhar_graficos(self, event=None):
        desenhar_barras_horizontais(self.cv_tipos, "Pessoas por tipo de acesso",
                                    self.dados["tipos"])
        desenhar_barras_verticais(self.cv_dias, "Entradas nos últimos 7 dias",
                                  self.dados["dias"], COR_GRAFICO_DIAS)
