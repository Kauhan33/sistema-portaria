"""
Página Painel: quatro números do movimento (no campus agora, entradas de
hoje, permanência média e com veículo) e dois gráficos (pessoas por tipo de
acesso e entradas nos últimos 7 dias). Os números vêm do banco
(banco.resumo_painel, calculado no SQL); o desenho fica em graficos.py.
O administrador exporta os registros de um período para planilha (CSV).
"""

import tkinter as tk
from datetime import datetime, timedelta

from . import backup, mensagens
from .componentes import (Aviso, Botao, Cabecalho, Cartao, Dialogo,
                          campo_rotulado, plural, titulo_cartao)
from .consultas import formatar_duracao
from .estilo import COR, ESPACO_CARTOES, FONTE, ICONE, MARGEM, px
from .graficos import desenhar_barras_horizontais, desenhar_barras_verticais
from .usuarios import eh_admin
from .validacao import TIPOS_ACESSO

PLURAL_TIPO = {"Aluno": "Alunos", "Professor": "Professores",
               "Funcionário": "Funcionários", "Visitante": "Visitantes",
               "Entregador": "Entregadores",
               "Prestador de serviço": "Prestadores"}
# (chave, rótulo); o primeiro é o destaque
NUMEROS = [("dentro", "No campus agora"), ("hoje", "Entradas hoje"),
           ("permanencia", "Permanência média"), ("veiculos", "Com veículo")]
ALTURA_GRAFICO = 230
FORMATO_DIA = "%d/%m/%Y"


class AbaDashboard:
    def __init__(self, aba, app):
        self.aba = aba
        self.app = app
        self.cards = {}                            # chave -> (valor, apoio)
        self.dados = {"tipos": [], "dias": []}     # dados prontos dos gráficos
        self.btn_exportar = None
        self.dialogo = None

        cab = Cabecalho(aba, "Painel").posicionar()
        self.lbl_subtitulo = cab.subtitulo
        if eh_admin(app.usuario):       # exportação: só administrador
            self.btn_exportar = Botao(cab.acoes, "Exportar CSV",
                                      self.abrir_exportacao, "secundario",
                                      icone=ICONE["baixar"],
                                      fundo_pai=COR["fundo"])
            self.btn_exportar.pack()
        self._montar_numeros()
        self._montar_graficos()
        self.atualizar()

    # --------------------------------------------------------------
    # Montagem
    # --------------------------------------------------------------
    def _montar_numeros(self):
        linha = tk.Frame(self.aba, bg=COR["fundo"])
        linha.pack(fill="x", padx=px(MARGEM - ESPACO_CARTOES // 2))
        linha.columnconfigure(tuple(range(len(NUMEROS))), weight=1,
                              uniform="numeros")
        for coluna, (chave, rotulo) in enumerate(NUMEROS):
            cartao = Cartao(linha, pad=18)
            cartao.grid(row=0, column=coluna, sticky="nsew",
                        padx=px(ESPACO_CARTOES // 2))
            m = cartao.miolo
            tk.Label(m, text=rotulo, font=FONTE["corpo_semi"], bg=COR["superficie"],
                     fg=COR["texto_2"]).pack(anchor="w")
            destaque = coluna == 0
            valor = tk.Label(m, text="0", bg=COR["superficie"],
                             font=FONTE["kpi_destaque" if destaque else "kpi"],
                             fg=COR["sucesso"] if destaque else COR["texto"])
            valor.pack(anchor="w", pady=(px(2), 0))
            apoio = tk.Label(m, text="", font=FONTE["dica"], bg=COR["superficie"],
                             fg=COR["texto_3"])
            apoio.pack(anchor="w", side="bottom")
            self.cards[chave] = (valor, apoio)

    def _montar_graficos(self):
        area = tk.Frame(self.aba, bg=COR["fundo"])
        area.pack(fill="both", expand=True, padx=px(MARGEM - ESPACO_CARTOES // 2),
                  pady=(px(ESPACO_CARTOES), px(MARGEM)))
        area.columnconfigure((0, 1), weight=1, uniform="g")
        area.rowconfigure(0, weight=1)
        self.cv_tipos = self._novo_grafico(area, 0, "Pessoas por tipo de acesso",
                                           "todas as visitas")
        self.cv_dias = self._novo_grafico(area, 1, "Entradas nos últimos 7 dias",
                                          "hoje em destaque")

    def _novo_grafico(self, area, coluna, titulo, apoio):
        cartao = Cartao(area, pad=18)
        cartao.grid(row=0, column=coluna, sticky="nsew",
                    padx=px(ESPACO_CARTOES // 2))
        cab = tk.Frame(cartao.miolo, bg=COR["superficie"])
        cab.pack(fill="x", pady=(0, px(12)))
        titulo_cartao(cab, titulo).pack(side="left")
        tk.Label(cab, text=apoio, font=FONTE["dica"], bg=COR["superficie"],
                 fg=COR["texto_3"]).pack(side="right")
        cv = tk.Canvas(cartao.miolo, bg=COR["superficie"], height=px(ALTURA_GRAFICO),
                       highlightthickness=0, bd=0)
        cv.pack(fill="both", expand=True)
        cv.bind("<Configure>", self.redesenhar_graficos)
        return cv

    # --------------------------------------------------------------
    # Dados
    # --------------------------------------------------------------
    def atualizar(self):
        """Relê os números do banco (calculados no SQL)."""
        hoje = self.app.relogio().date()
        ok, r = self.app.tentar(self.app.banco.resumo_painel, hoje)
        if not ok:
            return
        por_tipo = r["por_tipo"]
        self.lbl_subtitulo.config(
            text=f"{plural(r['total'], 'registro', 'registros')} desde o início"
                 f"  ·  {plural(r['saidas'], 'visita encerrada', 'visitas encerradas')}")
        self._mostrar("dentro", r["dentro"], "entradas ainda sem saída")
        self._mostrar("hoje", r["entradas_hoje"], hoje.strftime(FORMATO_DIA))
        if r["permanencia_media"] is not None:
            self._mostrar("permanencia", formatar_duracao(r["permanencia_media"]),
                          f"em {plural(r['saidas'], 'visita encerrada', 'visitas encerradas')}")
        else:
            self._mostrar("permanencia", "—", "sem saídas registradas")
        self._mostrar("veiculos", r["com_veiculo"],
                      f"de {plural(r['total'], 'registro', 'registros')}")

        self.dados["tipos"] = [
            (PLURAL_TIPO.get(t, t), por_tipo[t][0], f"{por_tipo[t][1]} no campus")
            for t in TIPOS_ACESSO]
        self.dados["dias"] = [(d.strftime("%d/%m"), n)
                              for d, n in r["por_dia"].items()]
        self.redesenhar_graficos()

    def _mostrar(self, chave, valor, apoio):
        self.cards[chave][0].config(text=str(valor))
        self.cards[chave][1].config(text=apoio)

    def redesenhar_graficos(self, event=None):
        desenhar_barras_horizontais(self.cv_tipos, self.dados["tipos"])
        desenhar_barras_verticais(self.cv_dias, self.dados["dias"])

    # --------------------------------------------------------------
    # Exportar CSV (só administrador)
    # --------------------------------------------------------------
    def abrir_exportacao(self):
        if not eh_admin(self.app.usuario):
            mensagens.erro("Acesso negado",
                           "Somente o administrador exporta os registros.")
            return None
        self.dialogo = DialogoExportar(self.app)
        return self.dialogo


class DialogoExportar(Dialogo):
    """Escolha do período (com atalhos) e do arquivo para exportar."""

    def __init__(self, app):
        self.app = app
        super().__init__(app.janela, "Exportar registros",
                         "As visitas com entrada no período vão para uma "
                         "planilha (CSV) que abre no Excel.", largura=420,
                         ao_usar=app.registrar_uso)
        hoje = app.relogio().date()
        atalhos = tk.Frame(self.miolo, bg=COR["superficie"])
        atalhos.pack(fill="x", pady=(0, px(14)))
        for texto, inicio in [("Hoje", hoje),
                              ("Últimos 7 dias", hoje - timedelta(days=6)),
                              ("Este mês", hoje.replace(day=1))]:
            Botao(atalhos, texto, lambda i=inicio: self.periodo(i, hoje),
                  "secundario", altura=30).pack(side="left", padx=(0, px(8)))
        datas = tk.Frame(self.miolo, bg=COR["superficie"])
        datas.pack(fill="x")
        datas.columnconfigure((0, 1), weight=1, uniform="d")
        grupo, campo = campo_rotulado(datas, "De", "dd/mm/aaaa")
        grupo.grid(row=0, column=0, sticky="ew", padx=(0, px(12)))
        self.desde = campo.entrada
        grupo, campo = campo_rotulado(datas, "Até", "dd/mm/aaaa")
        grupo.grid(row=0, column=1, sticky="ew")
        self.ate = campo.entrada
        self.faixa = Aviso(self.miolo)
        self.faixa.mostrar("alerta", "O arquivo leva CPF e celular completos: "
                                     "guarde-o com o mesmo cuidado do sistema.")
        self.faixa.pack(fill="x", pady=(px(16), 0))
        self.lbl_erro = self.faixa.lbl
        self.periodo(hoje.replace(day=1), hoje)
        self.adicionar_botao("Escolher arquivo e exportar", self.exportar,
                             "primario")
        self.adicionar_botao("Cancelar", self.fechar)
        self.abrir(confirmar=self.exportar, foco=self.desde)

    def periodo(self, desde, ate):
        for caixa, dia in ((self.desde, desde), (self.ate, ate)):
            caixa.delete(0, tk.END)
            caixa.insert(0, dia.strftime(FORMATO_DIA))

    def _data(self, caixa):
        try:
            return datetime.strptime(caixa.get().strip(), FORMATO_DIA).date()
        except ValueError:
            return None

    def exportar(self):
        desde, ate = self._data(self.desde), self._data(self.ate)
        if desde is None or ate is None:
            self.faixa.mostrar("erro", "Data inválida. Use o formato dd/mm/aaaa.")
            return
        if ate < desde:
            self.faixa.mostrar("erro", "A data final não pode ser anterior à "
                                       "inicial.")
            return
        caminho = mensagens.salvar_como(
            "Exportar registros",
            f"portaria-{desde:%Y-%m-%d}-a-{ate:%Y-%m-%d}.csv", parent=self.janela)
        if not caminho:
            return
        ok, quantos = self.app.tentar(backup.exportar_csv, self.app.banco,
                                      caminho, desde, ate, self.app.autor)
        if not ok:
            return
        self.fechar()
        mensagens.info("Exportar registros",
                       f"{plural(quantos, 'registro exportado', 'registros exportados')}"
                       f" para:\n{caminho}")

