"""
Protótipo do novo visual — SÓ biblioteca padrão (tkinter + ctypes).
Tokens de design e componentes desenhados (cantos arredondados com
anti-serrilhado feito "na mão": a cor de cada pixel do canto é misturada
com a cor do fundo, que sempre é conhecida).
"""

import ctypes
import math
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

# ----------------------------------------------------------------------
# Escala (DPI). Com o processo "DPI aware" o Windows não borra a janela,
# mas tudo que é medido em pixels precisa ser multiplicado pela escala.
# ----------------------------------------------------------------------
ESCALA = 1.0


def ligar_nitidez():
    """Chame ANTES de criar o tk.Tk(). Devolve a escala (ex.: 1.25)."""
    global ESCALA
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        ESCALA = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
    except (AttributeError, OSError):
        ESCALA = 1.0
    return ESCALA


def px(n):
    return max(1, round(n * ESCALA))


# ----------------------------------------------------------------------
# Tokens
# ----------------------------------------------------------------------
COR = {
    # marca
    "marca": "#D9001B",          # vermelho UNA
    "marca_escura": "#B80017",
    "marca_tinta": "#FDECEE",
    # neutros
    "fundo": "#F3F4F6",          # fundo da janela
    "lateral": "#EEF0F3",        # barra lateral
    "superficie": "#FFFFFF",     # cartões, campos
    "superficie_2": "#F8F9FB",   # cabeçalho de tabela, zebra
    "borda": "#E1E4EA",          # contorno de cartão (decorativo)
    "borda_campo": "#C5CBD5",
    "traco_campo": "#8C95A6",    # linha de baixo do campo (3:1)
    "texto": "#1B2330",
    "texto_2": "#475467",
    "texto_3": "#5B6578",
    "selecao": "#E3E9F4",
    "hover": "#E8EBF0",
    # ação principal
    "primario": "#1B2330",
    "primario_hover": "#2E3A4D",
    "primario_press": "#10161F",
    "foco": "#1F5FBF",
    # estados: (texto, fundo, borda)
    "sucesso": ("#0B6B3A", "#E8F5EE", "#B5DEC5"),
    "alerta": ("#8A4600", "#FFF4E0", "#F2D29B"),
    "erro": ("#B00017", "#FDECEE", "#F3BAC2"),
    "info": ("#1D4E9E", "#EAF1FC", "#BCD0F0"),
    "neutro": ("#475467", "#F3F4F6", "#E1E4EA"),
    # placa Mercosul
    "placa_azul": "#0B3C9C",
}
CORES_TIPO = {"Aluno": "#1D4E9E", "Professor": "#6B3FA0",
              "Funcionário": "#0B6B3A", "Visitante": "#8A4600",
              "Entregador": "#B00017", "Prestador de serviço": "#475467"}

ICONE = {  # Segoe Fluent Icons (Win 11) / Segoe MDL2 Assets (Win 10)
    "entrada": chr(0xE8AB), "pessoas": chr(0xE716), "bloqueio": chr(0xE733),
    "painel": chr(0xE9F9), "usuarios": chr(0xE7EF), "sair": chr(0xE7E8),
    "busca": chr(0xE721), "mais": chr(0xE710), "lixo": chr(0xE74D), "editar": chr(0xE70F),
    "relogio": chr(0xE823), "desfazer": chr(0xE7A7), "carro": chr(0xE804),
    "ok": chr(0xE73E), "alerta": chr(0xE7BA), "erro": chr(0xE783), "info": chr(0xE946),
    "pessoa": chr(0xE77B), "cadeado": chr(0xE72E), "seta": chr(0xE72A),
}


class Fontes:
    def __init__(self):
        fam = set(tkfont.families())

        def escolher(*opcoes):
            return next((f for f in opcoes if f in fam), "Segoe UI")

        disp = escolher("Segoe UI Variable Display Semib", "Segoe UI Semibold")
        texto = escolher("Segoe UI Variable Text", "Segoe UI")
        semi = escolher("Segoe UI Variable Text Semibold", "Segoe UI Semibold")
        self.numero = escolher("Bahnschrift")
        self.numero_semi = escolher("Bahnschrift SemiBold", "Bahnschrift")
        self.placa = escolher("Bahnschrift SemiBold SemiConden",
                              "Bahnschrift SemiBold", "Bahnschrift")
        self.icone_fam = escolher("Segoe Fluent Icons", "Segoe MDL2 Assets")
        # escala tipográfica (pt): 9 · 10 · 12 · 14 · 18 · 28
        self.titulo_pagina = (disp, 18)
        self.titulo_grande = (disp, 28)
        self.titulo_cartao = (semi, 12)
        self.corpo = (texto, 10)
        self.corpo_semi = (semi, 10)
        self.rotulo = (semi, 9)
        self.dica = (texto, 9)
        self.botao = (semi, 10)
        self.kpi = (self.numero_semi, 26)

    def icone(self, tamanho=12):
        return (self.icone_fam, tamanho)


# ----------------------------------------------------------------------
# Cantos arredondados anti-serrilhados
# ----------------------------------------------------------------------
_cache = {}


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(c):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in c)


def _canto(r, preench, fundo, borda, esp):
    """Linhas de cores do canto superior esquerdo (r x r pixels)."""
    cp, cf = _rgb(preench), _rgb(fundo)
    cb = _rgb(borda) if borda else cp
    n = 4  # sub-amostras por eixo
    linhas = []
    for y in range(r):
        linha = []
        for x in range(r):
            soma = [0.0, 0.0, 0.0]
            for i in range(n):
                for j in range(n):
                    d = math.hypot(r - (x + (i + .5) / n), r - (y + (j + .5) / n))
                    c = cf if d > r else (cb if borda and d > r - esp else cp)
                    for k in range(3):
                        soma[k] += c[k]
            linha.append(_hex([v / (n * n) for v in soma]))
        linhas.append(linha)
    return linhas


def cantos(r, preench, fundo, borda=None, esp=1):
    chave = (r, preench, fundo, borda, esp)
    if chave in _cache:
        return _cache[chave]
    tl = _canto(r, preench, fundo, borda, esp)
    variantes = {"nw": tl,
                 "ne": [list(reversed(l)) for l in tl],
                 "sw": list(reversed(tl)),
                 "se": [list(reversed(l)) for l in reversed(tl)]}
    imgs = {}
    for nome, linhas in variantes.items():
        img = tk.PhotoImage(width=r, height=r)
        img.put(" ".join("{" + " ".join(l) + "}" for l in linhas), to=(0, 0))
        imgs[nome] = img
    _cache[chave] = imgs
    return imgs


def ret_arredondado(cv, x0, y0, x1, y1, r, preench, fundo, borda=None, esp=1,
                    tag="fundo"):
    r = max(1, min(r, (x1 - x0) // 2, (y1 - y0) // 2))
    im = cantos(r, preench, fundo, borda, esp)
    for (x, y), nome in [((x0, y0), "nw"), ((x1 - r, y0), "ne"),
                         ((x0, y1 - r), "sw"), ((x1 - r, y1 - r), "se")]:
        cv.create_image(x, y, image=im[nome], anchor="nw", tags=tag)
    cv.create_rectangle(x0 + r, y0, x1 - r, y1, fill=preench, width=0, tags=tag)
    cv.create_rectangle(x0, y0 + r, x1, y1 - r, fill=preench, width=0, tags=tag)
    if borda:
        for a, b, c, d in [(x0 + r, y0, x1 - r, y0 + esp),
                           (x0 + r, y1 - esp, x1 - r, y1),
                           (x0, y0 + r, x0 + esp, y1 - r),
                           (x1 - esp, y0 + r, x1, y1 - r)]:
            cv.create_rectangle(a, b, c, d, fill=borda, width=0, tags=tag)


# ----------------------------------------------------------------------
# Componentes
# ----------------------------------------------------------------------
class Cartao(tk.Frame):
    """Superfície branca, cantos de 8 px, contorno sutil. Conteúdo em .miolo."""

    def __init__(self, pai, fundo_pai, pad=20, raio=8, cor=None, borda=None):
        super().__init__(pai, bg=fundo_pai)
        self.cor = cor or COR["superficie"]
        self.borda = borda if borda is not None else COR["borda"]
        self.fundo_pai, self.raio = fundo_pai, px(raio)
        self.cv = tk.Canvas(self, bg=fundo_pai, highlightthickness=0, bd=0)
        self.cv.place(x=0, y=0, relwidth=1, relheight=1)
        self.miolo = tk.Frame(self, bg=self.cor)
        self.miolo.pack(fill="both", expand=True, padx=px(pad), pady=px(pad))
        self.cv.bind("<Configure>", self._desenhar)

    def _desenhar(self, e=None):
        self.cv.delete("all")
        w, h = self.cv.winfo_width(), self.cv.winfo_height()
        ret_arredondado(self.cv, 0, 0, w, h, self.raio, self.cor, self.fundo_pai,
                        self.borda or None)


class Botao(tk.Canvas):
    """Botão desenhado: primario, secundario, perigo, fantasma ou marca."""

    VARIANTES = {
        #            fundo, hover, press, texto, borda
        "primario": (COR["primario"], COR["primario_hover"], COR["primario_press"],
                     "#FFFFFF", None),
        "marca": (COR["marca"], COR["marca_escura"], "#9A0013", "#FFFFFF", None),
        "secundario": (COR["superficie"], COR["superficie_2"], COR["hover"],
                       COR["texto"], COR["borda_campo"]),
        "perigo": (COR["superficie"], COR["erro"][1], "#F9D9DE",
                   COR["erro"][0], COR["erro"][2]),
        "fantasma": (None, COR["hover"], "#DDE1E8", COR["texto"], None),
    }

    def __init__(self, pai, texto, comando=None, variante="secundario",
                 icone=None, fontes=None, fundo_pai=COR["superficie"],
                 largura=None, altura=36, dica_tecla=None):
        self.f = fontes
        self.texto, self.comando, self.icone = texto, comando, icone
        self.dica_tecla = dica_tecla
        self.fundo_pai = fundo_pai
        fundo, hov, prs, tx, bd = self.VARIANTES[variante]
        self.cores = {"normal": fundo or fundo_pai, "hover": hov, "press": prs}
        self.cor_texto, self.cor_borda = tx, bd
        fonte = tkfont.Font(family=fontes.botao[0], size=fontes.botao[1])
        larg_txt = fonte.measure(texto)
        larg_ico = px(22) if icone else 0
        larg_tecla = fonte.measure(dica_tecla) + px(10) if dica_tecla else 0
        w = largura or (larg_txt + larg_ico + larg_tecla + px(32))
        super().__init__(pai, width=w, height=px(altura), bg=fundo_pai,
                         highlightthickness=0, bd=0, cursor="hand2", takefocus=1)
        self.estado, self.focado = "normal", False
        self.bind("<Configure>", lambda e: self._desenhar())
        self.bind("<Enter>", lambda e: self._muda("hover"))
        self.bind("<Leave>", lambda e: self._muda("normal"))
        self.bind("<ButtonPress-1>", lambda e: self._muda("press"))
        self.bind("<ButtonRelease-1>", self._soltar)
        self.bind("<FocusIn>", lambda e: self._foco(True))
        self.bind("<FocusOut>", lambda e: self._foco(False))
        self.bind("<space>", lambda e: self.invocar())

    # mesma "cara" de um tk.Button para quem lê o texto (ex.: testes)
    def cget(self, chave):
        return self.texto if chave == "text" else super().cget(chave)

    def invocar(self):
        if self.comando:
            self.comando()

    def _soltar(self, e):
        dentro = 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height()
        self._muda("hover" if dentro else "normal")
        if dentro:
            self.invocar()

    def _muda(self, estado):
        self.estado = estado
        self._desenhar()

    def _foco(self, sim):
        self.focado = sim
        self._desenhar()

    def _desenhar(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            return
        cor = self.cores[self.estado]
        borda, esp = self.cor_borda, 1
        if self.focado:
            borda, esp = COR["foco"], px(2)
        if cor != self.fundo_pai or borda:
            ret_arredondado(self, 0, 0, w, h, px(6), cor, self.fundo_pai, borda, esp)
        larg_ico = px(22) if self.icone else 0
        fonte = (self.f.botao[0], self.f.botao[1])
        f = tkfont.Font(family=fonte[0], size=fonte[1])
        total = larg_ico + f.measure(self.texto)
        if self.dica_tecla:
            total += px(10) + f.measure(self.dica_tecla)
        x = (w - total) / 2
        if self.icone:
            self.create_text(x, h / 2, text=self.icone, anchor="w",
                             font=self.f.icone(11), fill=self.cor_texto)
            x += larg_ico
        self.create_text(x, h / 2, text=self.texto, anchor="w", font=fonte,
                         fill=self.cor_texto)
        if self.dica_tecla:
            x += f.measure(self.texto) + px(10)
            cor_tecla = "#AEB7C6" if self.cor_texto == "#FFFFFF" else COR["texto_3"]
            self.create_text(x, h / 2, text=self.dica_tecla, anchor="w",
                             font=self.f.dica, fill=cor_tecla)


class Campo(tk.Frame):
    """
    Caixa de texto no estilo Windows 11: cantos de 4 px, contorno claro e
    linha de baixo mais escura; com foco a linha de baixo vira 2 px azul.
    `widget` pode ser "entry" ou "combo". O widget real fica em .entrada.
    """

    def __init__(self, pai, fontes, fundo_pai=COR["superficie"], widget="entry",
                 icone=None, acao_icone=None, largura=None, **kw):
        super().__init__(pai, bg=fundo_pai, height=px(36))
        if largura:
            self.config(width=px(largura))
        self.pack_propagate(False)
        self.grid_propagate(False)
        self.fundo_pai, self.focado = fundo_pai, False
        self.cv = tk.Canvas(self, bg=fundo_pai, highlightthickness=0, bd=0)
        self.cv.place(x=0, y=0, relwidth=1, relheight=1)
        if widget == "combo":
            self.entrada = ttk.Combobox(self, style="Liso.TCombobox",
                                        font=fontes.corpo, **kw)
        else:
            self.entrada = tk.Entry(self, relief="flat", bd=0, font=fontes.corpo,
                                    bg=COR["superficie"], fg=COR["texto"],
                                    insertbackground=COR["texto"],
                                    disabledbackground=COR["superficie_2"], **kw)
        dir_ = px(36) if icone else px(10)
        self.entrada.place(x=px(10) if widget == "entry" else px(4), rely=0.5,
                           anchor="w", relwidth=1, width=-(px(10) + dir_)
                           if widget == "entry" else -px(8))
        if icone:
            b = tk.Label(self, text=icone, font=fontes.icone(11), bg=COR["superficie"],
                         fg=COR["texto_2"], cursor="hand2")
            b.place(relx=1, rely=0.5, anchor="e", x=-px(10))
            if acao_icone:
                b.bind("<Button-1>", lambda e: acao_icone())
        self.entrada.bind("<FocusIn>", lambda e: self._foco(True), add="+")
        self.entrada.bind("<FocusOut>", lambda e: self._foco(False), add="+")
        self.cv.bind("<Configure>", lambda e: self._desenhar())

    def _foco(self, sim):
        self.focado = sim
        self._desenhar()

    def _desenhar(self):
        cv = self.cv
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        r = px(4)
        ret_arredondado(cv, 0, 0, w, h, r, COR["superficie"], self.fundo_pai,
                        COR["borda_campo"])
        cor, esp = (COR["foco"], px(2)) if self.focado else (COR["traco_campo"], 1)
        cv.create_rectangle(r, h - esp, w - r, h, fill=cor, width=0)


class Aviso(tk.Frame):
    """Faixa de status com ícone (sucesso / alerta / erro / info / neutro)."""

    def __init__(self, pai, fontes, fundo_pai=COR["superficie"]):
        super().__init__(pai, bg=fundo_pai)
        self.f, self.fundo_pai = fontes, fundo_pai
        self.cv = tk.Canvas(self, bg=fundo_pai, highlightthickness=0, bd=0)
        self.cv.place(x=0, y=0, relwidth=1, relheight=1)
        self.interno = tk.Frame(self)
        self.interno.pack(fill="x", padx=px(12), pady=px(9))
        self.lbl_icone = tk.Label(self.interno, font=fontes.icone(11))
        self.lbl_icone.pack(side="left", padx=(0, px(8)))
        self.lbl = tk.Label(self.interno, font=fontes.corpo_semi, anchor="w",
                            justify="left")
        self.lbl.pack(side="left", fill="x", expand=True)
        self.acao = None
        self.cv.bind("<Configure>", lambda e: self._desenhar())
        self.tipo = "neutro"

    def mostrar(self, tipo, texto, icone, acao=None):
        self.tipo = tipo
        tx, fu, _ = COR[tipo]
        for w in (self.interno, self.lbl_icone, self.lbl):
            w.config(bg=fu)
        self.lbl_icone.config(text=icone, fg=tx)
        self.lbl.config(text=texto, fg=tx)
        if self.acao:
            self.acao.destroy()
            self.acao = None
        if acao:
            self.acao = tk.Label(self.interno, text=acao, bg=fu, fg=tx,
                                 font=(self.f.rotulo[0], 9, "underline"),
                                 cursor="hand2")
            self.acao.pack(side="right")
        self._desenhar()

    def _desenhar(self):
        self.cv.delete("all")
        w, h = self.cv.winfo_width(), self.cv.winfo_height()
        if w < 4:
            return
        tx, fu, bd = COR[self.tipo]
        ret_arredondado(self.cv, 0, 0, w, h, px(6), fu, self.fundo_pai, bd)


class Placa(tk.Canvas):
    """Placa Mercosul desenhada (faixa azul 'BRASIL' + caracteres DIN)."""

    def __init__(self, pai, fontes, fundo_pai, largura=210):
        w = px(largura)
        super().__init__(pai, width=w, height=round(w * 0.33), bg=fundo_pai,
                         highlightthickness=0, bd=0)
        self.f, self.fundo_pai, self.texto = fontes, fundo_pai, ""
        self.bind("<Configure>", lambda e: self._desenhar())

    def mostrar(self, texto):
        self.texto = texto
        self._desenhar()

    def _desenhar(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10:
            return
        r = px(7)
        if not self.texto:
            ret_arredondado(self, 0, 0, w, h, r, COR["superficie_2"],
                            self.fundo_pai, COR["borda_campo"])
            self.create_text(w / 2, h / 2 - px(9), text="Sem veículo (a pé)",
                             font=self.f.corpo_semi, fill=COR["texto_2"])
            self.create_text(w / 2, h / 2 + px(11), text="ABC1234 ou ABC1D23",
                             font=self.f.dica, fill=COR["texto_3"])
            return
        ret_arredondado(self, 0, 0, w, h, r, "#FFFFFF", self.fundo_pai,
                        "#1B2330", px(2))
        faixa = round(h * 0.26)
        e = px(2)
        ret_arredondado(self, e, e, w - e, e + faixa + r, r - 1, COR["placa_azul"],
                        "#FFFFFF")
        self.create_rectangle(e, e + faixa, w - e, e + faixa + r, fill="#FFFFFF",
                              width=0)
        self.create_text(w / 2, e + faixa / 2 + 1, text="BRASIL",
                         font=(self.f.numero_semi, 7), fill="#FFFFFF")
        # bandeirinha
        bx, by = w - e - px(16), e + px(4)
        self.create_rectangle(bx, by, bx + px(11), by + faixa - px(8),
                              fill="#009B3A", width=0)
        self.create_text(e + px(10), e + faixa / 2 + 1, text="BR", anchor="w",
                         font=(self.f.numero_semi, 6), fill="#FFFFFF")
        self.create_text(w / 2, e + faixa + (h - faixa - e) / 2 + 1,
                         text=self.texto, font=(self.f.placa, 22),
                         fill="#1B2330")


class ItemMenu(tk.Canvas):
    """Item da barra lateral: ícone + texto; ativo = pílula branca + traço UNA."""

    def __init__(self, pai, fontes, texto, icone, ativo=False, contador=None):
        super().__init__(pai, height=px(40), bg=COR["lateral"],
                         highlightthickness=0, bd=0, cursor="hand2", takefocus=1)
        self.f, self.texto, self.icone = fontes, texto, icone
        self.ativo, self.hover, self.contador = ativo, False, contador
        self.bind("<Configure>", lambda e: self._desenhar())
        self.bind("<Enter>", lambda e: self._h(True))
        self.bind("<Leave>", lambda e: self._h(False))

    def _h(self, sim):
        self.hover = sim
        self._desenhar()

    def _desenhar(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if self.ativo or self.hover:
            cor = COR["superficie"] if self.ativo else COR["hover"]
            ret_arredondado(self, 0, px(2), w, h - px(2), px(6), cor, COR["lateral"])
        if self.ativo:
            ret_arredondado(self, px(4), h / 2 - px(9), px(7), h / 2 + px(9), px(1),
                            COR["marca"], COR["superficie"])
        cor_tx = COR["texto"] if self.ativo else COR["texto_2"]
        self.create_text(px(18), h / 2, text=self.icone, anchor="w",
                         font=self.f.icone(12), fill=cor_tx)
        self.create_text(px(46), h / 2, text=self.texto, anchor="w",
                         font=self.f.corpo_semi if self.ativo else self.f.corpo,
                         fill=cor_tx)
        if self.contador:
            self.create_text(w - px(12), h / 2, text=self.contador, anchor="e",
                             font=self.f.dica, fill=COR["texto_3"])


def circulo_iniciais(pai, fontes, iniciais, fundo_pai, tamanho=32,
                     cor=COR["texto"]):
    t = px(tamanho)
    cv = tk.Canvas(pai, width=t, height=t, bg=fundo_pai, highlightthickness=0, bd=0)
    ret_arredondado(cv, 0, 0, t, t, t // 2, cor, fundo_pai)
    cv.create_text(t / 2, t / 2, text=iniciais, fill="#FFFFFF",
                   font=(fontes.rotulo[0], 9))
    return cv


def marca_cancela(pai, fundo_pai, tamanho=36, cor=COR["marca"], traco="#FFFFFF"):
    """Símbolo do sistema: uma cancela (poste + braço) num quadrado vermelho."""
    t = px(tamanho)
    cv = tk.Canvas(pai, width=t, height=t, bg=fundo_pai, highlightthickness=0, bd=0)
    ret_arredondado(cv, 0, 0, t, t, px(8), cor, fundo_pai)
    u = t / 36
    cv.create_rectangle(8 * u, 9 * u, 13 * u, 26 * u, fill=traco, width=0)      # poste
    cv.create_rectangle(6 * u, 25 * u, 15 * u, 28 * u, fill=traco, width=0)     # base
    cv.create_rectangle(13 * u, 11 * u, 30 * u, 17 * u, fill=traco, width=0)    # braço
    for x in (17, 24):  # listras do braço, por dentro do contorno branco
        cv.create_rectangle(x * u, 12.5 * u, (x + 3) * u, 15.5 * u, fill=cor,
                            width=0)
    return cv


def aplicar_estilo_ttk(raiz, f):
    """Estilos ttk (tema clam) para tabela, combobox e barra de rolagem."""
    s = ttk.Style(raiz)
    s.theme_use("clam")
    s.configure("Liso.TCombobox", fieldbackground=COR["superficie"],
                background=COR["superficie"], foreground=COR["texto"],
                bordercolor=COR["superficie"], lightcolor=COR["superficie"],
                darkcolor=COR["superficie"], arrowcolor=COR["texto_2"],
                arrowsize=px(12), padding=(px(6), px(4)), relief="flat")
    s.map("Liso.TCombobox",
          fieldbackground=[("readonly", COR["superficie"])],
          selectbackground=[("readonly", COR["superficie"])],
          selectforeground=[("readonly", COR["texto"])],
          background=[("active", COR["superficie"]), ("pressed", COR["superficie"])],
          bordercolor=[("focus", COR["superficie"])],
          lightcolor=[("focus", COR["superficie"])])
    raiz.option_add("*TCombobox*Listbox.font", f.corpo)
    raiz.option_add("*TCombobox*Listbox.selectBackground", COR["selecao"])
    raiz.option_add("*TCombobox*Listbox.selectForeground", COR["texto"])

    s.configure("Tabela.Treeview", background=COR["superficie"],
                fieldbackground=COR["superficie"], foreground=COR["texto"],
                bordercolor=COR["superficie"], lightcolor=COR["superficie"],
                darkcolor=COR["superficie"], rowheight=px(34), font=f.corpo,
                borderwidth=0, relief="flat")
    s.map("Tabela.Treeview", background=[("selected", COR["selecao"])],
          foreground=[("selected", COR["texto"])])
    s.configure("Tabela.Treeview.Heading", background=COR["superficie_2"],
                foreground=COR["texto_2"], font=f.rotulo, relief="flat",
                borderwidth=0, bordercolor=COR["borda"],
                lightcolor=COR["superficie_2"], darkcolor=COR["borda"],
                padding=(px(10), px(8)))
    s.map("Tabela.Treeview.Heading", background=[("active", COR["hover"])])
    # sem o triângulo de árvore e sem o retângulo pontilhado de foco
    s.layout("Tabela.Treeview.Item", [
        ("Treeitem.padding", {"sticky": "nswe", "children": [
            ("Treeitem.image", {"side": "left", "sticky": ""}),
            ("Treeitem.text", {"side": "left", "sticky": ""})]})])
    s.layout("Tabela.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    s.layout("Fina.Vertical.TScrollbar", [
        ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    s.configure("Fina.Vertical.TScrollbar", troughcolor=COR["superficie"],
                background="#CDD3DC", bordercolor=COR["superficie"],
                lightcolor="#CDD3DC", darkcolor="#CDD3DC", arrowsize=px(8),
                gripcount=0, relief="flat")
    s.map("Fina.Vertical.TScrollbar", background=[("active", "#AEB7C6")])
    return s


def bolinha(cor, fundo="#FFFFFF", d=None):
    """Imagem de um ponto colorido (para a coluna Situação da tabela)."""
    d = d or px(8)
    im = cantos(d // 2, cor, fundo)
    img = tk.PhotoImage(width=d + px(6), height=d)
    for nome, (x, y) in {"nw": (0, 0), "ne": (d // 2, 0), "sw": (0, d // 2),
                         "se": (d // 2, d // 2)}.items():
        img.tk.call(img, "copy", im[nome], "-to", x, y)
    img.put(fundo, to=(d, 0, d + px(6), d))
    return img
