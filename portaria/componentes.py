"""
Peças de tela reutilizáveis do sistema de design "Guarita": cartões,
botões e campos desenhados, faixas de aviso, tabelas, placa (Mercosul ou
antiga),
itens da barra lateral e diálogos.

As telas dizem O QUE montar (ex.: Campo(pai, numeros=11)); o COMO (cor,
fonte, cantos arredondados, validação da digitação) fica aqui, num lugar
só. Nenhuma peça se posiciona sozinha: grid ou pack é decisão da tela.

Cantos arredondados sem serrilhado: o Canvas do Tk não suaviza bordas, então
cada canto é uma imagem pequena em que a cor de cada pixel é misturada com
a cor do fundo (que sempre é conhecida). As bolinhas da tabela são PNG com
transparência gerados aqui mesmo (zlib + struct, biblioteca padrão).
"""

import base64
import math
import re
import struct
import tkinter as tk
import tkinter.font as tkfont
import zlib
from datetime import datetime
from tkinter import ttk

from .estilo import (ALTURA_CAMPO, COR, ESTADO, FONTE, ICONE, MARGEM, TEMA,
                     fonte_icone, pintar_barra_de_titulo, px)
from .validacao import (MAXIMO_DATA, MAXIMO_DATA_HORA, MAXIMO_HORA,
                        MAXIMO_PLACA, MAXIMO_SENHA, placa_antiga)

TAMANHO_PLACA = MAXIMO_PLACA
MAXIMO_DO_SELETOR = {"data_hora": MAXIMO_DATA_HORA, "data": MAXIMO_DATA,
                     "hora": MAXIMO_HORA}
# Na tela pequena as colunas das tabelas encolhem até 85% da largura de projeto
ENCOLHER_ATE = 0.85
COLUNAS_EVENTOS = [("momento", "Data e hora"), ("usuario", "Usuário"),
                   ("acao", "Ação"), ("detalhe", "Detalhe")]
DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
ICONE_DO_ESTADO = {"sucesso": "ok", "alerta": "alerta", "erro": "erro",
                   "info": "info", "neutro": "info"}
ESPERA_BUSCA_MS = 300     # pausa na digitação antes de buscar


def data_por_extenso(momento=None):
    """'Segunda-feira, 19 de outubro'."""
    momento = momento or datetime.now()
    return (f"{DIAS[momento.weekday()]}, {momento.day} de "
            f"{MESES[momento.month - 1]}").capitalize()


def plural(n, singular, plural_):
    return f"{n} {singular if n == 1 else plural_}"


# ----------------------------------------------------------------------
# Imagens: cantos arredondados e bolinhas (guardadas por janela raiz)
# ----------------------------------------------------------------------
def _cache(widget):
    """Imagens já feitas do tema em uso, guardadas na janela raiz: uma imagem
    do Tk só vale para o interpretador que a criou (os testes criam várias
    raízes). Cada tema tem o seu cache: voltar ao tema anterior reaproveita
    as imagens dele."""
    raiz = widget._root()
    if not hasattr(raiz, "imagens_guarita"):
        raiz.imagens_guarita = {}
    return raiz.imagens_guarita.setdefault(TEMA["atual"], {})


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(c):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in c)


def _canto(r, preench, fundo, borda, esp):
    """Cores do canto superior esquerdo (r x r pixels), com 4x4 amostras
    por pixel: o pixel da beirada fica com a mistura das cores."""
    cp, cf = _rgb(preench), _rgb(fundo)
    cb = _rgb(borda) if borda else cp
    n = 4
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


def cantos(widget, r, preench, fundo, borda=None, esp=1):
    """As 4 imagens de canto (nw, ne, sw, se) para essas cores."""
    cache = _cache(widget)
    chave = ("canto", r, preench, fundo, borda, esp)
    if chave not in cache:
        tl = _canto(r, preench, fundo, borda, esp)
        variantes = {"nw": tl,
                     "ne": [list(reversed(l)) for l in tl],
                     "sw": list(reversed(tl)),
                     "se": [list(reversed(l)) for l in reversed(tl)]}
        imagens = {}
        for nome, linhas in variantes.items():
            img = tk.PhotoImage(master=widget, width=r, height=r)
            img.put(" ".join("{" + " ".join(l) + "}" for l in linhas), to=(0, 0))
            imagens[nome] = img
        cache[chave] = imagens
    return cache[chave]


def ret_arredondado(cv, x0, y0, x1, y1, r, preench, fundo, borda=None, esp=1,
                    tag="fundo"):
    """Retângulo de cantos arredondados (com contorno opcional) no Canvas."""
    x0, y0, x1, y1 = (int(v) for v in (x0, y0, x1, y1))
    r = max(1, min(r, (x1 - x0) // 2, (y1 - y0) // 2))
    im = cantos(cv, r, preench, fundo, borda, esp)
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


def _png_rgba(largura, altura, pixels):
    """PNG (bytes) a partir de linhas de (r, g, b, a). Só biblioteca padrão."""
    bruto = b"".join(b"\x00" + bytes(v for px_ in linha for v in px_)
                     for linha in pixels)

    def bloco(tipo, dados):
        return (struct.pack(">I", len(dados)) + tipo + dados
                + struct.pack(">I", zlib.crc32(tipo + dados) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + bloco(b"IHDR", struct.pack(">IIBBBBB", largura, altura, 8, 6, 0, 0, 0))
            + bloco(b"IDAT", zlib.compress(bruto)) + bloco(b"IEND", b""))


def bolinha(widget, cor):
    """Ponto colorido com fundo transparente (coluna Situação das tabelas):
    fica certo em linha branca, zebrada ou selecionada."""
    cache = _cache(widget)
    chave = ("bolinha", cor)
    if chave not in cache:
        d, folga = px(8), px(8)
        r, (cr, cg, cb) = d / 2, _rgb(cor)
        n = 4
        linhas = []
        for y in range(d):
            linha = []
            for x in range(d + folga):
                dentro = sum(math.hypot(x + (i + .5) / n - r, y + (j + .5) / n - r) <= r
                             for i in range(n) for j in range(n))
                linha.append((cr, cg, cb, round(255 * dentro / (n * n))))
            linhas.append(linha)
        dados = base64.b64encode(_png_rgba(d + folga, d, linhas))
        cache[chave] = tk.PhotoImage(master=widget, data=dados, format="png")
    return cache[chave]


# ----------------------------------------------------------------------
# Cartão
# ----------------------------------------------------------------------
class Cartao(tk.Frame):
    """Superfície branca, cantos de 8 px e contorno sutil. Monte em .miolo."""

    def __init__(self, pai, fundo_pai=None, pad=20, raio=8, cor=None,
                 borda=None):
        fundo_pai = fundo_pai or COR["fundo"]
        super().__init__(pai, bg=fundo_pai)
        self.cor = cor or COR["superficie"]
        self.borda = COR["borda"] if borda is None else borda
        self.fundo_pai, self.raio = fundo_pai, px(raio)
        self.cv = tk.Canvas(self, bg=fundo_pai, highlightthickness=0, bd=0)
        self.cv.place(x=0, y=0, relwidth=1, relheight=1)
        self.miolo = tk.Frame(self, bg=self.cor)
        self.miolo.pack(fill="both", expand=True, padx=px(pad), pady=px(pad))
        self.cv.bind("<Configure>", self._desenhar)

    def _desenhar(self, event=None):
        self.cv.delete("all")
        w, h = self.cv.winfo_width(), self.cv.winfo_height()
        if w > 4 and h > 4:
            ret_arredondado(self.cv, 0, 0, w, h, self.raio, self.cor,
                            self.fundo_pai, self.borda or None)


def titulo_cartao(pai, texto, fundo=None):
    return tk.Label(pai, text=texto, font=FONTE["titulo_cartao"],
                    bg=fundo or COR["superficie"], fg=COR["texto"])


# ----------------------------------------------------------------------
# Botões
# ----------------------------------------------------------------------
class Botao(tk.Canvas):
    """
    Botão desenhado: "primario" (um por tela), "secundario", "perigo",
    "fantasma" ou "marca". Responde ao mouse e ao teclado (Tab leva o foco;
    Espaço ou Enter acionam) e mostra o anel de foco azul.
    Para quem lê o texto (ex.: testes), cget("text") funciona como num
    tk.Button; invocar() aciona como um clique.
    """

    @staticmethod
    def cores_da_variante(variante):
        """(fundo, hover, pressionado, texto, borda) no tema em uso (lidas na
        hora: uma tabela fixa ficaria com as cores do tema do import)."""
        return {
            "primario": (COR["primario"], COR["primario_hover"],
                         COR["primario_press"], COR["texto_invertido"], None),
            "marca": (COR["marca"], COR["marca_escura"], COR["marca_press"],
                      COR["texto_sobre_marca"], None),
            "secundario": (COR["superficie"], COR["superficie_2"], COR["hover"],
                           COR["texto"], COR["borda_campo"]),
            "perigo": (COR["superficie"], ESTADO["erro"][1], COR["erro_press"],
                       ESTADO["erro"][0], ESTADO["erro"][2]),
            "fantasma": (None, COR["hover"], COR["press"], COR["texto"], None),
        }[variante]

    def __init__(self, pai, texto, comando=None, variante="secundario",
                 icone=None, fundo_pai=None, largura=None, altura=ALTURA_CAMPO,
                 dica_tecla=None):
        self.fundo_pai = fundo_pai or COR["superficie"]
        self.texto, self.comando, self.icone = texto, comando, icone
        self.dica_tecla, self.variante = dica_tecla, variante
        self.largura_fixa = largura
        self.ativo, self.estado, self.focado = True, "normal", False
        fundo, hover, press, self.cor_texto, self.cor_borda = \
            self.cores_da_variante(variante)
        self.cores = {"normal": fundo or self.fundo_pai, "hover": hover,
                      "press": press}
        self.fonte = tkfont.Font(root=pai, font=FONTE["botao"])
        super().__init__(pai, width=self._largura_natural(), height=px(altura),
                         bg=self.fundo_pai, highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=1)
        self.bind("<Configure>", lambda e: self._desenhar())
        self.bind("<Enter>", lambda e: self._mudar("hover"))
        self.bind("<Leave>", lambda e: self._mudar("normal"))
        self.bind("<ButtonPress-1>", lambda e: self._mudar("press"))
        self.bind("<ButtonRelease-1>", self._soltar)
        self.bind("<FocusIn>", lambda e: self._foco(True))
        self.bind("<FocusOut>", lambda e: self._foco(False))
        for tecla in ("<space>", "<Return>", "<KP_Enter>"):
            self.bind(tecla, self._tecla)

    def _largura_natural(self):
        if self.largura_fixa:
            return px(self.largura_fixa)
        largura = self.fonte.measure(self.texto) + px(32)
        if self.icone:
            largura += px(24)
        if self.dica_tecla:
            largura += self.fonte.measure(self.dica_tecla) + px(10)
        return largura

    # mesma "cara" de um tk.Button para quem lê o texto
    def cget(self, chave):
        if chave == "text":
            return self.texto
        if chave == "state":
            return "normal" if self.ativo else "disabled"
        return super().cget(chave)

    def definir_texto(self, texto, variante=None):
        """Troca o texto (e a variante, ex.: Desativar → Ativar)."""
        self.texto = texto
        if variante and variante != self.variante:
            self.variante = variante
            fundo, hover, press, self.cor_texto, self.cor_borda = \
                self.cores_da_variante(variante)
            self.cores = {"normal": fundo or self.fundo_pai, "hover": hover,
                          "press": press}
        self.config(width=self._largura_natural())
        self._desenhar()

    def definir_ativo(self, ativo):
        """Desativado: cinza, não responde ao clique nem ao teclado."""
        self.ativo = bool(ativo)
        self.config(cursor="hand2" if self.ativo else "arrow",
                    takefocus=1 if self.ativo else 0)
        self._desenhar()

    def invocar(self):
        if self.ativo and self.comando:
            self.comando()

    def _tecla(self, event):
        self.invocar()
        return "break"           # o Enter não chega à janela (não cadastra)

    def _soltar(self, event):
        dentro = (0 <= event.x < self.winfo_width()
                  and 0 <= event.y < self.winfo_height())
        self._mudar("hover" if dentro else "normal")
        if dentro:
            self.invocar()

    def _mudar(self, estado):
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
        cor_texto, borda, esp = self.cor_texto, self.cor_borda, 1
        cor = self.cores[self.estado] if self.ativo else self.cores["normal"]
        if not self.ativo:
            cor_texto = COR["texto_3"]
            if self.variante in ("primario", "marca"):
                cor, cor_texto = COR["hover"], COR["texto_3"]
            borda = COR["borda"] if borda else None
        if self.focado and self.ativo:
            borda, esp = COR["foco"], px(2)
        if cor != self.fundo_pai or borda:
            ret_arredondado(self, 0, 0, w, h, px(6), cor, self.fundo_pai,
                            borda, esp)
        largura_icone = px(24) if self.icone else 0
        total = largura_icone + self.fonte.measure(self.texto)
        if self.dica_tecla:
            total += px(10) + self.fonte.measure(self.dica_tecla)
        x = (w - total) / 2
        if self.icone:
            self.create_text(x, h / 2, text=self.icone, anchor="w",
                             font=fonte_icone(11), fill=cor_texto)
            x += largura_icone
        self.create_text(x, h / 2, text=self.texto, anchor="w",
                         font=FONTE["botao"], fill=cor_texto)
        if self.dica_tecla:
            x += self.fonte.measure(self.texto) + px(10)
            sobre_primario = cor_texto == COR["texto_invertido"]
            self.create_text(x, h / 2, text=self.dica_tecla, anchor="w",
                             font=FONTE["dica"],
                             fill=COR["dica_invertida"] if sobre_primario
                             else COR["texto_3"])


class BotaoIcone(tk.Label):
    """Ícone clicável (ex.: sair, mais opções), com foco de teclado."""

    def __init__(self, pai, icone, comando, fundo_pai, tamanho=12,
                 descricao="", folga=6):
        super().__init__(pai, text=icone, font=fonte_icone(tamanho),
                         bg=fundo_pai, fg=COR["texto_2"], cursor="hand2",
                         padx=px(folga), pady=px(4), takefocus=1,
                         highlightthickness=px(2), highlightcolor=COR["foco"],
                         highlightbackground=fundo_pai)
        self.comando, self.fundo_pai, self.descricao = comando, fundo_pai, descricao
        self.bind("<Enter>", lambda e: self.config(bg=COR["hover"]))
        self.bind("<Leave>", lambda e: self.config(bg=self.fundo_pai))
        self.bind("<Button-1>", lambda e: self.invocar(e))
        for tecla in ("<space>", "<Return>", "<KP_Enter>"):
            self.bind(tecla, lambda e: (self.invocar(e), "break")[1])

    def invocar(self, event=None):
        if self.comando:
            self.comando()


def link(pai, texto, comando, fundo=None, cor=None):
    """Texto sublinhado que age como botão ("Desfazer", "Registrar saída")."""
    rotulo = tk.Label(pai, text=texto, font=FONTE["link"],
                      bg=fundo or COR["superficie"], fg=cor or COR["foco"],
                      cursor="hand2", takefocus=1)
    rotulo.bind("<Button-1>", lambda e: comando())
    rotulo.bind("<Return>", lambda e: (comando(), "break")[1])
    rotulo.bind("<space>", lambda e: (comando(), "break")[1])
    return rotulo


# ----------------------------------------------------------------------
# Campos
# ----------------------------------------------------------------------
def _digito(c):
    return c.isascii() and c.isdigit()


def _letra_ou_digito(c):
    return c.isascii() and c.isalnum()


class Campo(tk.Frame):
    """
    Caixa de texto no estilo Windows 11: cantos de 4 px, contorno claro e
    linha de baixo mais escura; com foco a linha de baixo vira 2 px azul.
    O widget real fica em .entrada (tk.Entry, ou ttk.Combobox se `opcoes`)
    e o texto em .var. Restrições de digitação (as mesmas em todas as telas):
        numeros=11   só dígitos, no máximo 11 (CPF, celular)
        placa=True   letras e números, até 7, sempre em maiúscula
        maximo=N     no máximo N caracteres (validacao.MAXIMO_*)
    TODA caixa de texto tem um máximo: o de numeros/placa, o do seletor
    (data e hora 16, data 10, hora 5), o da senha (64) ou `maximo`. Sem
    nenhum deles o Campo nem é criado (ValueError): nenhum campo fica sem.
    A digitação não passa do máximo; ao COLAR um texto maior, entra só o
    que cabe (cortado no máximo, sem aviso) e, em campos de números ou de
    placa, só os caracteres aceitos (colar "529.982.247-25" no CPF dá
    52998224725). Quebras de linha coladas viram espaço.
    icone + acao_icone: ícone clicável dentro do campo.
    dica_vazio: texto cinza mostrado enquanto o campo está vazio.
    seletor="data_hora" | "data" | "hora": clicar no campo (ou no ícone)
        abre o calendário/relógio (seletor_data.py); `relogio` é o "agora"
        dele e `ao_escolher` é chamado depois de preencher. Digitar
        continua valendo: a primeira tecla fecha o pop-up.
    """

    def __init__(self, pai, fundo_pai=None, opcoes=None, numeros=None,
                 placa=False, senha=False, icone=None, acao_icone=None,
                 dica_vazio="", largura=None, var=None, seletor=None,
                 relogio=None, ao_escolher=None, maximo=None, **kw):
        self.fundo_pai = fundo_pai or COR["superficie"]
        super().__init__(pai, bg=self.fundo_pai, height=px(ALTURA_CAMPO))
        if largura:
            self.config(width=px(largura))
        self.pack_propagate(False)
        self.grid_propagate(False)
        self.focado = False
        self.var = var if var is not None else tk.StringVar(self)
        self.cv = tk.Canvas(self, bg=self.fundo_pai, highlightthickness=0, bd=0)
        self.cv.place(x=0, y=0, relwidth=1, relheight=1)

        if opcoes is not None:
            self.entrada = ttk.Combobox(self, style="Liso.TCombobox",
                                        font=FONTE["corpo"], values=list(opcoes),
                                        state="readonly", textvariable=self.var,
                                        **kw)
            self.entrada.place(x=px(4), rely=0.5, anchor="w", relwidth=1,
                               width=-px(8))
        else:
            self.maximo = (maximo or numeros or (TAMANHO_PLACA if placa else None)
                           or MAXIMO_DO_SELETOR.get(seletor)
                           or (MAXIMO_SENHA if senha else None))
            if not self.maximo:
                raise ValueError("Campo de texto sem tamanho máximo: informe "
                                 "maximo= (validacao.MAXIMO_*).")
            self.aceito = (_digito if numeros
                           else _letra_ou_digito if placa else None)
            kw.update(validate="key", validatecommand=(
                self.register(self._aceita), "%P"))
            if placa:
                self.var.trace_add("write", self._maiuscula)
            if senha:
                kw["show"] = "•"
            self.entrada = tk.Entry(self, relief="flat", bd=0, font=FONTE["corpo"],
                                    bg=COR["superficie"], fg=COR["texto"],
                                    insertbackground=COR["texto"],
                                    disabledbackground=COR["superficie_2"],
                                    disabledforeground=COR["texto_3"],
                                    selectbackground=COR["selecao"],
                                    selectforeground=COR["texto"],
                                    textvariable=self.var, **kw)
            direita = px(36) if icone else px(10)
            self.entrada.place(x=px(10), rely=0.5, anchor="w", relwidth=1,
                               width=-(px(10) + direita))
            self.entrada.bind("<<Paste>>", self._colar_da_area_de_transferencia)
        self.modo_seletor, self.relogio = seletor, relogio
        self.ao_escolher, self.seletor_aberto = ao_escolher, None
        if seletor:
            icone = icone or ICONE["calendario" if seletor == "data" else "relogio"]
            acao_icone = self.abrir_seletor
            self.entrada.bind("<Button-1>", self.abrir_seletor, add="+")
            self.entrada.bind("<Key>", self._tecla_com_seletor, add="+")
        self.acao_icone, self.lbl_icone = acao_icone, None
        if icone:
            self.lbl_icone = tk.Label(self, text=icone, font=fonte_icone(11),
                                      bg=COR["superficie"], fg=COR["texto_2"],
                                      cursor="hand2" if acao_icone else "")
            self.lbl_icone.place(relx=1, rely=0.5, anchor="e", x=-px(10))
            self.lbl_icone.bind("<Button-1>", lambda e: self.usar_icone())
        self.lbl_vazio = None
        if dica_vazio:
            self.lbl_vazio = tk.Label(self, text=dica_vazio, font=FONTE["corpo"],
                                      bg=COR["superficie"], fg=COR["texto_3"],
                                      anchor="w", cursor="xterm")
            self.lbl_vazio.bind("<Button-1>", lambda e: self.entrada.focus_set())
            self.var.trace_add("write", lambda *a: self._mostrar_vazio())
            self._mostrar_vazio()
        self.entrada.bind("<FocusIn>", lambda e: self._foco(True), add="+")
        self.entrada.bind("<FocusOut>", lambda e: self._foco(False), add="+")
        self.cv.bind("<Configure>", lambda e: self._desenhar())

    def abrir_seletor(self, event=None):
        """Abre o calendário/relógio embaixo do campo (um por vez)."""
        if str(self.entrada.cget("state")) == "disabled":
            return
        if self.seletor_aberto is not None and self.seletor_aberto.existe():
            return
        from .seletor_data import SeletorDataHora   # (importa componentes)
        fechar_seletor()
        self.seletor_aberto = SeletorDataHora(self, self.modo_seletor,
                                              self.relogio, self.ao_escolher)
        _SELETOR["aberto"] = self.seletor_aberto
        topo = self.winfo_toplevel()
        if not getattr(topo, "fecha_seletor_ligado", False):
            topo.bind("<Button-1>", _clique_fora_do_seletor, add="+")
            topo.fecha_seletor_ligado = True

    def _tecla_com_seletor(self, event):
        """Digitar fecha o pop-up (e o texto entra no campo); Esc só fecha."""
        if self.seletor_aberto is not None and self.seletor_aberto.existe():
            self.seletor_aberto.fechar()
            if event.keysym == "Escape":
                return "break"
        return None

    def usar_icone(self):
        """O que o clique no ícone faz (ex.: relógio = data e hora de agora)."""
        if self.acao_icone:
            self.acao_icone()
            self.entrada.focus_set()

    def _aceita(self, texto):
        """validatecommand (%P = o texto como ficaria): digitar e colar não
        passam do máximo nem de caracteres que o campo não aceita."""
        if len(texto) > self.maximo:
            return False
        return self.aceito is None or all(self.aceito(c) for c in texto)

    def _colar_da_area_de_transferencia(self, event=None):
        try:
            texto = self.entrada.clipboard_get()
        except tk.TclError:              # área de transferência vazia
            return "break"
        self.colar(texto)
        return "break"                   # o Tk não cola de novo, inteiro

    def colar(self, texto):
        """Cola `texto` no cursor (no lugar da seleção), só com o que cabe:
        o resto é cortado no máximo do campo."""
        caixa = self.entrada
        if str(caixa.cget("state")) != "normal":
            return
        if caixa.selection_present():
            caixa.delete("sel.first", "sel.last")
        if self.aceito is not None:
            texto = "".join(c for c in texto if self.aceito(c))
        else:
            texto = re.sub(r"[\r\n\t]+", " ", texto)
        cabe = max(self.maximo - len(caixa.get()), 0)
        if texto[:cabe]:
            caixa.insert("insert", texto[:cabe])

    def _maiuscula(self, *args):
        texto = self.var.get()
        if texto != texto.upper():
            self.var.set(texto.upper())

    def _mostrar_vazio(self):
        if self.var.get():
            self.lbl_vazio.place_forget()
        else:
            self.lbl_vazio.place(x=px(10) + 1, rely=0.5, anchor="w")

    def _foco(self, sim):
        self.focado = sim
        self._desenhar()

    def _desenhar(self):
        cv = self.cv
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 10:
            return
        r = px(4)
        ret_arredondado(cv, 0, 0, w, h, r, COR["superficie"], self.fundo_pai,
                        COR["borda_campo"])
        cor, esp = (COR["foco"], px(2)) if self.focado else (COR["traco_campo"], 1)
        cv.create_rectangle(r, h - esp, w - r, h, fill=cor, width=0)


class EsperaDigitacao:
    """
    Busca enquanto se digita sem travar a tela (RNF03): `acao` só roda
    depois de `espera` ms sem teclas que mudem o texto. Digitar um CPF de
    11 dígitos faz uma busca, não onze; Shift, setas e Tab não buscam.
    """

    def __init__(self, entrada, acao, espera=ESPERA_BUSCA_MS):
        self.entrada, self.acao, self.espera = entrada, acao, espera
        self._timer = None
        self._visto = entrada.get()
        entrada.bind("<KeyRelease>", self._ao_soltar_tecla, add="+")

    def _ao_soltar_tecla(self, event=None):
        texto = self.entrada.get()
        if texto == self._visto:
            return
        self._visto = texto
        self.cancelar()
        self._timer = self.entrada.after(self.espera, self._disparar)

    def cancelar(self):
        if self._timer is not None:
            self.entrada.after_cancel(self._timer)
            self._timer = None

    def _disparar(self):
        self._timer = None
        self.acao()


_SELETOR = {"aberto": None}       # o calendário/relógio aberto agora


def fechar_seletor():
    aberto = _SELETOR["aberto"]
    if aberto is not None:
        aberto.fechar()
    _SELETOR["aberto"] = None


def _clique_fora_do_seletor(event):
    """Clique em qualquer lugar da janela fora do campo fecha o pop-up."""
    aberto = _SELETOR["aberto"]
    if aberto is None or not aberto.existe():
        return
    campo = aberto.campo
    if event.widget not in (campo.entrada, campo.lbl_icone):
        fechar_seletor()


def rotulo_campo(pai, texto, apoio="", fundo=None):
    """
    Rótulo de campo com o apoio cinza ao lado ("Entrada  dd/mm/aaaa hh:mm").
    Devolve (frame, rótulo do apoio); o apoio pode mudar depois.
    """
    fundo = fundo or COR["superficie"]
    linha = tk.Frame(pai, bg=fundo)
    tk.Label(linha, text=texto, font=FONTE["rotulo"], bg=fundo,
             fg=COR["texto"]).pack(side="left")
    lbl_apoio = tk.Label(linha, text=apoio, font=FONTE["dica"], bg=fundo,
                         fg=COR["texto_3"])
    lbl_apoio.pack(side="left", padx=(px(8), 0))
    return linha, lbl_apoio


def campo_rotulado(pai, texto, apoio="", fundo=None, contador=False,
                   **opcoes_campo):
    """Rótulo em cima + Campo embaixo, num Frame. Devolve (grupo, campo).
    contador=True: "0/200" discreto à direita do rótulo (textos longos)."""
    fundo = fundo or COR["superficie"]
    grupo = tk.Frame(pai, bg=fundo)
    linha, _ = rotulo_campo(grupo, texto, apoio, fundo)
    linha.pack(fill="x", pady=(0, px(4)))
    campo = Campo(grupo, fundo_pai=fundo, **opcoes_campo)
    campo.pack(fill="x")
    if contador:
        campo.contador = Contador(linha, campo, fundo)
        campo.contador.pack(side="right")
    return grupo, campo


class Contador(tk.Label):
    """Quantos caracteres o campo tem e o máximo ("123/200"), em cinza
    discreto; no limite fica na cor de alerta (não cabe mais nada)."""

    def __init__(self, pai, campo, fundo=None):
        super().__init__(pai, font=FONTE["dica"], bg=fundo or COR["superficie"])
        self.campo = campo
        campo.var.trace_add("write", lambda *a: self.atualizar())
        self.atualizar()

    def atualizar(self):
        usados, maximo = len(self.campo.var.get()), self.campo.maximo
        self.config(text=f"{usados}/{maximo}",
                    fg=COR["alerta"] if usados >= maximo else COR["texto_3"])


# ----------------------------------------------------------------------
# Faixa de aviso
# ----------------------------------------------------------------------
class Aviso(tk.Frame):
    """
    Faixa de status: sucesso, alerta, erro, info ou neutro, com ícone à
    esquerda e uma ação opcional sublinhada à direita. O texto fica em
    .lbl (um tk.Label).
    """

    def __init__(self, pai, fundo_pai=None):
        self.fundo_pai = fundo_pai or COR["superficie"]
        super().__init__(pai, bg=self.fundo_pai)
        self.tipo = "neutro"
        self.cv = tk.Canvas(self, bg=self.fundo_pai, highlightthickness=0, bd=0)
        self.cv.place(x=0, y=0, relwidth=1, relheight=1)
        self.interno = tk.Frame(self)
        self.interno.pack(fill="x", padx=px(12), pady=px(9))
        self.lbl_icone = tk.Label(self.interno, font=fonte_icone(11))
        self.lbl_icone.pack(side="left", anchor="n", padx=(0, px(8)),
                            pady=(px(2), 0))
        self.lbl = tk.Label(self.interno, font=FONTE["corpo_semi"], anchor="w",
                            justify="left")
        self.lbl.pack(side="left", fill="x", expand=True)
        self.acao = self.comando = None
        self.cv.bind("<Configure>", self._ao_redimensionar)
        self.mostrar("neutro", "")

    def mostrar(self, tipo, texto, icone=None, acao=None, comando=None):
        """Troca estado e texto; `acao` + `comando` = link à direita."""
        self.tipo = tipo
        cor_texto, cor_fundo, _ = ESTADO[tipo]
        icone = icone or ICONE[ICONE_DO_ESTADO[tipo]]
        for w in (self.interno, self.lbl_icone, self.lbl):
            w.config(bg=cor_fundo)
        self.lbl_icone.config(text=icone, fg=cor_texto)
        self.lbl.config(text=texto, fg=cor_texto)
        if self.acao is not None:
            self.acao.destroy()
            self.acao = None
        self.comando = comando if acao else None     # o que o link faz
        if acao:
            self.acao = link(self.interno, acao, comando or (lambda: None),
                             fundo=cor_fundo, cor=cor_texto)
            self.acao.pack(side="right", anchor="n", padx=(px(12), 0),
                           before=self.lbl)
        self._ao_redimensionar()

    def definir_respiro(self, vertical):
        """Espaço acima e abaixo do texto (px lógicos): menor na tela baixa."""
        self.interno.pack_configure(pady=px(vertical))

    def _ao_redimensionar(self, event=None):
        # menos as margens internas e o ícone
        largura = self.cv.winfo_width() - px(60)
        if self.acao is not None:
            largura -= self.acao.winfo_reqwidth()
        self.lbl.config(wraplength=max(largura, px(120)))
        self._desenhar()

    def _desenhar(self):
        self.cv.delete("all")
        w, h = self.cv.winfo_width(), self.cv.winfo_height()
        if w < 10:
            return
        _, cor_fundo, cor_borda = ESTADO[self.tipo]
        ret_arredondado(self.cv, 0, 0, w, h, px(6), cor_fundo, self.fundo_pai,
                        cor_borda)


# ----------------------------------------------------------------------
# Placa: Mercosul ou antiga
# ----------------------------------------------------------------------
class Placa(tk.Canvas):
    """
    Placa desenhada. Mercosul (ABC1D23): branca, faixa azul "BRASIL" e
    caracteres DIN. Antiga (ABC1234, validacao.placa_antiga): cinza claro,
    moldura escura, faixa superior cinza e o hífen (ABC-1234). Sem placa:
    caixa clara "Sem veículo (a pé)". Desativada (`bloqueada`): borda e
    caracteres vermelhos.

    O fundo do Canvas (o que aparece fora dos cantos arredondados) é o do
    widget pai, lido a cada desenho: no tema escuro é o cartão escuro, e
    acompanha a troca de tema sem reiniciar. `fundo_pai` fica só para quem
    já passava a cor (é usado se o pai não tiver cor de fundo).
    """

    def __init__(self, pai, fundo_pai=None, largura=200):
        self.fundo_padrao = fundo_pai
        w = px(largura)
        super().__init__(pai, width=w, height=round(w * 0.33),
                         bg=self._fundo_do_pai(pai), highlightthickness=0, bd=0)
        self.texto, self.bloqueada = "", False
        self.bind("<Configure>", lambda e: self._desenhar())

    def _fundo_do_pai(self, pai=None):
        try:
            return (pai or self.master).cget("bg")
        except (tk.TclError, AttributeError):
            return self.fundo_padrao or COR["superficie"]

    @property
    def fundo_pai(self):
        return self._fundo_do_pai()

    @property
    def antiga(self):
        """A placa mostrada é do modelo antigo (cinza, com hífen)?"""
        return placa_antiga(self.texto)

    def mostrar(self, texto, bloqueada=False):
        self.texto, self.bloqueada = texto or "", bloqueada
        self._desenhar()

    def _desenhar(self):
        self.delete("all")
        fundo = self._fundo_do_pai()
        if self.cget("bg") != fundo:
            self.configure(bg=fundo)
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10:        # ainda não apareceu: o tamanho pedido
            w, h = int(self.cget("width")), int(self.cget("height"))
        r = px(7)
        if not self.texto:
            ret_arredondado(self, 0, 0, w, h, r, COR["superficie_2"],
                            fundo, COR["borda_campo"])
            self.create_text(w / 2, h / 2 - px(9), text="Sem veículo (a pé)",
                             font=FONTE["corpo_semi"], fill=COR["texto_2"])
            self.create_text(w / 2, h / 2 + px(11), text="ABC1234 ou ABC1D23",
                             font=FONTE["dica"], fill=COR["texto_3"])
            return
        if self.antiga:
            self._desenhar_antiga(w, h, r, fundo)
        else:
            self._desenhar_mercosul(w, h, r, fundo)

    def _desenhar_mercosul(self, w, h, r, fundo):
        branco = COR["placa_fundo"]
        cor_texto = COR["placa_erro"] if self.bloqueada else COR["placa_texto"]
        e = px(3) if self.bloqueada else px(2)
        ret_arredondado(self, 0, 0, w, h, r, branco, fundo, cor_texto, e)
        faixa = round(h * 0.26)
        # os cantos da faixa azul se misturam com a MOLDURA (não com o
        # branco da placa): no tema escuro não sobra recorte branco
        ret_arredondado(self, e, e, w - e, e + faixa + r, max(1, r - e),
                        COR["placa_azul"], cor_texto)
        self.create_rectangle(e, e + faixa, w - e, e + faixa + r,
                              fill=branco, width=0)
        self.create_text(w / 2, e + faixa / 2 + 1, text="BRASIL",
                         font=FONTE["placa_pequena"], fill=branco)
        bx, by = w - e - px(16), e + px(4)
        self.create_rectangle(bx, by, bx + px(11), by + max(faixa - px(8), 2),
                              fill=COR["placa_verde"], width=0)
        self.create_text(e + px(10), e + faixa / 2 + 1, text="BR", anchor="w",
                         font=(FONTE["placa_pequena"][0], 6), fill=branco)
        self._caracteres(w, e + faixa, h - e, self.texto, cor_texto)

    def _desenhar_antiga(self, w, h, r, fundo):
        """Modelo antigo: cinza claro, moldura escura, faixa de cima cinza
        (sem o "BRASIL" do Mercosul) e caracteres pretos com hífen."""
        cinza = COR["placa_cinza"]
        moldura = COR["placa_erro"] if self.bloqueada else COR["placa_moldura"]
        cor_texto = COR["placa_erro"] if self.bloqueada else COR["placa_preto"]
        e = px(3)
        ret_arredondado(self, 0, 0, w, h, r, cinza, fundo, moldura, e)
        faixa = round(h * 0.2)
        ret_arredondado(self, e, e, w - e, e + faixa + r, max(1, r - e),
                        COR["placa_cinza_faixa"], moldura)
        self.create_rectangle(e, e + faixa, w - e, e + faixa + r,
                              fill=cinza, width=0)
        self.create_rectangle(e, e + faixa, w - e, e + faixa + 1,
                              fill=moldura, width=0)
        furo = max(2, px(2))       # os dois parafusos da faixa
        for x in (e + px(12), w - e - px(12)):
            self.create_oval(x - furo, e + faixa / 2 - furo, x + furo,
                             e + faixa / 2 + furo, fill=moldura, width=0)
        # o hífen aparece já durante a digitação (NEY-48)
        texto = self.texto.strip().upper()
        self._caracteres(w, e + faixa + 1, h - e, f"{texto[:3]}-{texto[3:]}",
                         cor_texto)

    def _caracteres(self, w, topo, base, texto, cor):
        """Os caracteres centralizados entre a faixa e a borda de baixo;
        a fonte diminui se o texto não couber (ABC-1234 tem 8)."""
        familia, tamanho = FONTE["placa"][0], FONTE["placa"][1]
        fonte = tkfont.Font(root=self, family=familia, size=tamanho)
        while tamanho > 8 and fonte.measure(texto) > w - px(16):
            tamanho -= 1
            fonte.configure(size=tamanho)
        self.create_text(w / 2, topo + (base - topo) / 2 + 1, text=texto,
                         font=(familia, tamanho), fill=cor)


# ----------------------------------------------------------------------
# Barra lateral e marca
# ----------------------------------------------------------------------
class ItemMenu(tk.Canvas):
    """Item da barra lateral: ícone + texto (+ contador). O ativo tem
    pílula branca e o traço vermelho UNA à esquerda."""

    def __init__(self, pai, texto, icone, comando, contador=""):
        super().__init__(pai, height=px(40), bg=COR["lateral"],
                         highlightthickness=0, bd=0, cursor="hand2", takefocus=1)
        self.texto, self.icone, self.comando = texto, icone, comando
        self.ativo = self.hover = self.focado = False
        self.contador = contador
        self.bind("<Configure>", lambda e: self._desenhar())
        self.bind("<Enter>", lambda e: self._mudar("hover", True))
        self.bind("<Leave>", lambda e: self._mudar("hover", False))
        self.bind("<FocusIn>", lambda e: self._mudar("focado", True))
        self.bind("<FocusOut>", lambda e: self._mudar("focado", False))
        self.bind("<Button-1>", lambda e: self.comando())
        for tecla in ("<space>", "<Return>", "<KP_Enter>"):
            self.bind(tecla, lambda e: (self.comando(), "break")[1])

    def cget(self, chave):
        return self.texto if chave == "text" else super().cget(chave)

    def _mudar(self, atributo, valor):
        setattr(self, atributo, valor)
        self._desenhar()

    def definir_ativo(self, ativo):
        self._mudar("ativo", ativo)

    def definir_contador(self, contador):
        self._mudar("contador", contador)

    def _desenhar(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10:
            return
        lateral = COR["lateral"]
        if self.ativo or self.hover or self.focado:
            cor = COR["superficie"] if self.ativo else COR["hover"]
            borda = COR["foco"] if self.focado else None
            ret_arredondado(self, 0, px(2), w, h - px(2), px(6), cor, lateral,
                            borda, px(2))
        if self.ativo:
            ret_arredondado(self, px(4), h / 2 - px(9), px(7), h / 2 + px(9), 1,
                            COR["marca"], COR["superficie"])
        cor_texto = COR["texto"] if self.ativo else COR["texto_2"]
        self.create_text(px(18), h / 2, text=self.icone, anchor="w",
                         font=fonte_icone(12), fill=cor_texto)
        self.create_text(px(46), h / 2, text=self.texto, anchor="w",
                         font=FONTE["corpo_semi"] if self.ativo else FONTE["corpo"],
                         fill=cor_texto)
        if self.contador:
            self.create_text(w - px(12), h / 2, text=self.contador, anchor="e",
                             font=FONTE["dica"], fill=COR["texto_3"])


class Avatar(tk.Canvas):
    """Círculo escuro com as iniciais de quem está logado."""

    def __init__(self, pai, fundo_pai, tamanho=32):
        t = px(tamanho)
        super().__init__(pai, width=t, height=t, bg=fundo_pai,
                         highlightthickness=0, bd=0)
        self.fundo_pai, self.t = fundo_pai, t

    def mostrar(self, nome):
        partes = nome.split()
        iniciais = (partes[0][0] + (partes[-1][0] if len(partes) > 1 else "")
                    if partes else "?").upper()
        self.delete("all")
        ret_arredondado(self, 0, 0, self.t, self.t, self.t // 2, COR["texto"],
                        self.fundo_pai)
        self.create_text(self.t / 2, self.t / 2, text=iniciais,
                         fill=COR["texto_invertido"], font=FONTE["rotulo"])


def marca_cancela(pai, fundo_pai, tamanho=36, cor=None, traco=None):
    """Símbolo do sistema: uma cancela (poste + braço listrado) num
    quadrado vermelho UNA, desenhada no Canvas (não é o logotipo da UNA)."""
    cor = cor or COR["marca"]
    traco = traco or COR["texto_sobre_marca"]
    t = px(tamanho)
    cv = tk.Canvas(pai, width=t, height=t, bg=fundo_pai, highlightthickness=0,
                   bd=0)
    ret_arredondado(cv, 0, 0, t, t, px(8), cor, fundo_pai)
    u = t / 36
    cv.create_rectangle(8 * u, 9 * u, 13 * u, 26 * u, fill=traco, width=0)    # poste
    cv.create_rectangle(6 * u, 25 * u, 15 * u, 28 * u, fill=traco, width=0)   # base
    cv.create_rectangle(13 * u, 11 * u, 30 * u, 17 * u, fill=traco, width=0)  # braço
    for x in (17, 24):   # listras do braço
        cv.create_rectangle(x * u, 12.5 * u, (x + 3) * u, 15.5 * u, fill=cor,
                            width=0)
    return cv


# ----------------------------------------------------------------------
# Cabeçalho de página
# ----------------------------------------------------------------------
class Cabecalho(tk.Frame):
    """
    Título da página + linha de apoio embaixo, e as ações da página à
    direita (.acoes). .subtitulo é o rótulo da linha de apoio; .linha
    recebe rótulos extras ao lado dele; .topo, ao lado do título.
    """

    def __init__(self, pai, titulo, subtitulo=""):
        fundo = COR["fundo"]
        super().__init__(pai, bg=fundo)
        textos = tk.Frame(self, bg=fundo)
        textos.pack(side="left", anchor="s")
        self.topo = tk.Frame(textos, bg=fundo)
        self.topo.pack(anchor="w")
        tk.Label(self.topo, text=titulo, font=FONTE["titulo_pagina"], bg=fundo,
                 fg=COR["texto"]).pack(side="left")
        self.linha = tk.Frame(textos, bg=fundo)
        self.linha.pack(anchor="w")
        self.subtitulo = tk.Label(self.linha, text=subtitulo, font=FONTE["corpo"],
                                  bg=fundo, fg=COR["texto_2"])
        self.subtitulo.pack(side="left")
        self.acoes = tk.Frame(self, bg=fundo)
        self.acoes.pack(side="right", anchor="s")

    def posicionar(self):
        self.pack(fill="x", padx=px(MARGEM), pady=(px(20), px(16)))
        return self


# ----------------------------------------------------------------------
# Tabelas
# ----------------------------------------------------------------------
def tabela(pai, colunas, situacao=None, mostrar=None, altura=None,
           selecao="browse", rolagem=True, compacta=False,
           largura_situacao=112):
    """
    Tabela (Treeview no estilo Guarita) dentro de um Frame branco.
    colunas: lista de (id, título, largura, âncora).
    situacao: título da 1ª coluna (bolinha + texto), ex.: "Situação",
    com `largura_situacao` px lógicos.
    mostrar: ids das colunas visíveis (as outras continuam nos values).
    Devolve (quadro, tabela).
    """
    quadro = tk.Frame(pai, bg=COR["superficie"])
    opcoes = {"height": altura} if altura else {}
    estilo = "Compacta.Tabela.Treeview" if compacta else "Tabela.Treeview"
    tab = ttk.Treeview(quadro, style=estilo,
                       show="tree headings" if situacao else "headings",
                       selectmode=selecao, columns=[c[0] for c in colunas],
                       **opcoes)
    larguras = {}                       # largura de projeto de cada coluna
    if situacao:
        tab.heading("#0", text=situacao, anchor="w")
        larguras["#0"] = px(largura_situacao)
        tab.column("#0", width=px(largura_situacao), minwidth=px(90),
                   stretch=False, anchor="w")
    for col, titulo, largura, ancora in colunas:
        tab.heading(col, text=titulo, anchor="w" if ancora == "w" else ancora)
        larguras[col] = px(largura)
        tab.column(col, width=px(largura), minwidth=px(40), stretch=False,
                   anchor=ancora)
    if mostrar:
        tab.configure(displaycolumns=mostrar)
    tab.bind("<Configure>", lambda e: _encaixar_colunas(tab, larguras),
             add="+")
    tab.tag_configure("zebra", background=COR["superficie_2"])
    tab.tag_configure("apagado", foreground=COR["texto_3"])
    # linhas em destaque (Movimento): fundo claro do estado, sem zebra
    tab.tag_configure("pendente", background=ESTADO["erro"][1])
    tab.tag_configure("excedido", background=ESTADO["alerta"][1])
    tab.pack(side="left", fill="both", expand=True)
    if rolagem:
        barra = ttk.Scrollbar(quadro, orient="vertical", command=tab.yview,
                              style="Fina.Vertical.TScrollbar")
        tab.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y", padx=(px(2), px(4)))
    return quadro, tab


def _encaixar_colunas(tab, larguras):
    """As colunas visíveis dividem a largura da tabela na proporção do
    projeto (o Treeview sozinho não encolhe as colunas): sobra espaço na tela
    grande, e na pequena elas encolhem até ENCOLHER_ATE do projeto, para o
    texto (ex.: o CPF) não ser cortado; abaixo disso a última fica cortada."""
    visiveis = list(tab["displaycolumns"])
    if visiveis in (["#all"], []):
        visiveis = list(tab["columns"])
    if tab["show"] and "tree" in str(tab["show"]):
        visiveis.insert(0, "#0")
    total = sum(larguras.get(c, 0) for c in visiveis)
    disponivel = tab.winfo_width() - px(2)
    if total <= 0 or disponivel <= 1:
        return
    escala = max(disponivel / total, ENCOLHER_ATE)
    for c in visiveis:
        minimo = int(tab.column(c, "minwidth"))
        tab.column(c, width=max(minimo, int(larguras.get(c, 0) * escala)))


def inserir_linha(tab, indice, values, iid=None, situacao=None, cor=None,
                  tags=(), zebra=True):
    """Linha com zebra (zebra=False para linha em destaque, que tem fundo
    próprio); `situacao` + `cor` = texto e bolinha da 1ª coluna."""
    tags = tuple(tags) + (("zebra",) if zebra and indice % 2 else ())
    opcoes = {"iid": iid} if iid is not None else {}
    if situacao is not None:
        opcoes["text"] = situacao
        if cor:
            opcoes["image"] = bolinha(tab, cor)
    return tab.insert("", "end", values=values, tags=tags, **opcoes)


def tabela_eventos(pai, larguras, altura, rolagem=True, compacta=False,
                   fundo=None):
    """Tabela do histórico (data e hora, usuário, ação, detalhe)."""
    colunas = [(col, titulo, largura, "w")
               for (col, titulo), largura in zip(COLUNAS_EVENTOS, larguras)]
    return tabela(pai, colunas, altura=altura, selecao="extended",
                  rolagem=rolagem, compacta=compacta)


def preencher_eventos(tab, eventos):
    tab.delete(*tab.get_children())
    for i, e in enumerate(eventos):
        inserir_linha(tab, i, (e["momento"], e["usuario"], e["acao"],
                               e["detalhe"]))


SETA_CRESCENTE, SETA_DECRESCENTE = chr(0x25B2), chr(0x25BC)


class OrdenacaoTabela:
    """
    Ordenar a tabela clicando no cabeçalho: 1º clique em crescente, 2º em
    decrescente (e assim por diante); a coluna em uso ganha a seta ▲ ou ▼.
    titulos: {coluna: título}; chaves: {coluna: função item -> valor de
    comparação} (datas e números comparados como datas e números, não como
    texto); desempate: função do critério de desempate (sempre crescente).
    ao_ordenar(): redesenha a tabela (a tela chama .ordenar(itens)).
    """

    def __init__(self, tab, titulos, chaves, ao_ordenar, coluna,
                 desempate=None):
        self.tab, self.titulos, self.chaves = tab, titulos, chaves
        self.ao_ordenar, self.desempate = ao_ordenar, desempate
        self.coluna, self.decrescente = coluna, False
        for col in titulos:
            tab.heading(col, command=lambda c=col: self.clicar(c))
        self._mostrar_setas()

    def clicar(self, coluna):
        if coluna == self.coluna:
            self.decrescente = not self.decrescente
        else:
            self.coluna, self.decrescente = coluna, False
        self._mostrar_setas()
        self.ao_ordenar()

    def _mostrar_setas(self):
        for col, titulo in self.titulos.items():
            if col == self.coluna:
                seta = SETA_DECRESCENTE if self.decrescente else SETA_CRESCENTE
                titulo = f"{titulo} {seta}"
            self.tab.heading(col, text=titulo)

    def ordenar(self, itens):
        """Lista nova, ordenada pela coluna escolhida (o sort do Python é
        estável: o desempate vale nos dois sentidos)."""
        itens = sorted(itens, key=self.desempate) if self.desempate else list(itens)
        return sorted(itens, key=self.chaves[self.coluna],
                      reverse=self.decrescente)


class Seletor(tk.Frame):
    """
    Navegação entre as seções de uma página (como as abas do Windows 11):
    a seção ativa fica em texto escuro com o traço vermelho UNA embaixo,
    o mesmo sinal do item ativo da barra lateral. Tab leva o foco; Enter
    ou Espaço escolhem. `comando(opcao)` é chamado na troca.
    """

    def __init__(self, pai, opcoes, comando, fundo_pai=None):
        self.fundo_pai = fundo_pai or COR["fundo"]
        super().__init__(pai, bg=self.fundo_pai)
        self.comando, self.ativa = comando, None
        self.itens = {}
        for opcao in opcoes:
            item = tk.Frame(self, bg=self.fundo_pai)
            item.pack(side="left", padx=(0, px(20)))
            rotulo = tk.Label(item, text=opcao, font=FONTE["corpo"],
                              bg=self.fundo_pai, fg=COR["texto_2"],
                              cursor="hand2", takefocus=1, padx=px(2),
                              pady=px(4), highlightthickness=px(2),
                              highlightcolor=COR["foco"],
                              highlightbackground=self.fundo_pai)
            rotulo.pack()
            traco = tk.Frame(item, height=px(3), bg=self.fundo_pai)
            traco.pack(fill="x")
            for evento in ("<Button-1>", "<Return>", "<space>"):
                rotulo.bind(evento, lambda e, o=opcao: self.selecionar(o))
            self.itens[opcao] = (rotulo, traco)
        linha = tk.Frame(self, bg=COR["borda"], height=1)
        linha.place(relx=0, rely=1, relwidth=1, y=-1)
        linha.lower()              # o traço da seção ativa fica por cima

    def definir_texto(self, opcao, texto):
        """Troca o texto mostrado de uma opção (ex.: "Veículos (2)")."""
        self.itens[opcao][0].config(text=texto)

    def selecionar(self, opcao):
        self.ativa = opcao
        for nome, (rotulo, traco) in self.itens.items():
            ativa = nome == opcao
            rotulo.config(font=FONTE["corpo_semi"] if ativa else FONTE["corpo"],
                          fg=COR["texto"] if ativa else COR["texto_2"])
            traco.config(bg=COR["marca"] if ativa else self.fundo_pai)
        self.comando(opcao)
        return "break"


class Alternador(tk.Canvas):
    """Interruptor liga/desliga com texto (ex.: "Mostrar removidos")."""

    def __init__(self, pai, texto, var, comando=None, fundo_pai=None,
                 textos=()):
        """`textos`: todos os textos que ele pode mostrar (definir_texto),
        para a largura caber o maior (ex.: "Aberto" e "Fechado")."""
        self.fundo_pai = fundo_pai or COR["superficie"]
        self.texto, self.var, self.comando = texto, var, comando
        self.fonte = tkfont.Font(root=pai, font=FONTE["corpo"])
        maior = max(self.fonte.measure(t) for t in (texto, *textos))
        super().__init__(pai, width=px(44) + maior,
                         height=px(ALTURA_CAMPO), bg=self.fundo_pai,
                         highlightthickness=0, bd=0, cursor="hand2",
                         takefocus=1)
        self.focado = False
        self.bind("<Configure>", lambda e: self._desenhar())
        self.bind("<Button-1>", lambda e: self.alternar())
        self.bind("<space>", lambda e: (self.alternar(), "break")[1])
        self.bind("<FocusIn>", lambda e: self._foco(True))
        self.bind("<FocusOut>", lambda e: self._foco(False))

    def cget(self, chave):
        return self.texto if chave == "text" else super().cget(chave)

    def definir_texto(self, texto):
        self.texto = texto
        self._desenhar()

    def alternar(self):
        self.var.set(not self.var.get())
        self._desenhar()
        if self.comando:
            self.comando()

    def _foco(self, sim):
        self.focado = sim
        self._desenhar()

    def _desenhar(self):
        self.delete("all")
        h = self.winfo_height()
        if h < 10:
            return
        ligado = bool(self.var.get())
        w_ch, h_ch = px(34), px(18)
        y0 = (h - h_ch) / 2
        cor = COR["primario"] if ligado else COR["superficie"]
        borda = COR["foco"] if self.focado else (None if ligado else COR["traco_campo"])
        ret_arredondado(self, 0, y0, w_ch, y0 + h_ch, h_ch // 2, cor,
                        self.fundo_pai, borda, px(2) if self.focado else 1)
        d = px(10)
        cx = w_ch - h_ch / 2 if ligado else h_ch / 2
        cor_bola = COR["superficie"] if ligado else COR["texto_2"]
        ret_arredondado(self, cx - d / 2, h / 2 - d / 2, cx + d / 2, h / 2 + d / 2,
                        d // 2, cor_bola, cor)
        self.create_text(w_ch + px(10), h / 2, text=self.texto, anchor="w",
                         font=FONTE["corpo"], fill=COR["texto"])


# ----------------------------------------------------------------------
# Diálogo (Corrigir registro, Novo usuário, Trocar senha, Exportar)
# ----------------------------------------------------------------------
class Dialogo:
    """
    Janela modal branca: título, subtítulo, conteúdo em .miolo e rodapé
    cinza-claro com os botões à direita (.adicionar_botao). Esc fecha;
    Enter confirma (se `confirmar` for informado).
    """

    def __init__(self, dono, titulo, subtitulo="", largura=520,
                 ao_usar=None):
        self.janela = tk.Toplevel(dono)
        self.janela.title(titulo)
        self.janela.configure(bg=COR["superficie"])
        self.janela.resizable(False, False)
        self.janela.transient(dono)
        pintar_barra_de_titulo(self.janela)
        if ao_usar is not None:   # conta como uso (sessão por inatividade)
            for evento in ("<KeyPress>", "<ButtonPress>"):
                self.janela.bind(evento, ao_usar, add="+")

        rodape = tk.Frame(self.janela, bg=COR["superficie_2"])
        rodape.pack(side="bottom", fill="x")
        tk.Frame(rodape, bg=COR["borda"], height=1).pack(fill="x")
        self.botoes = tk.Frame(rodape, bg=COR["superficie_2"])
        self.botoes.pack(side="right", padx=px(24), pady=px(14))

        corpo = tk.Frame(self.janela, bg=COR["superficie"])
        corpo.pack(fill="both", expand=True, padx=px(24), pady=(px(20), px(18)))
        tk.Label(corpo, text=titulo, font=FONTE["titulo_dialogo"],
                 bg=COR["superficie"], fg=COR["texto"]).pack(anchor="w")
        self.lbl_subtitulo = tk.Label(corpo, text=subtitulo, font=FONTE["corpo"],
                                      bg=COR["superficie"], fg=COR["texto_2"],
                                      justify="left", wraplength=px(largura))
        if subtitulo:
            self.lbl_subtitulo.pack(anchor="w", pady=(px(2), 0))
        self.miolo = tk.Frame(corpo, bg=COR["superficie"], width=px(largura))
        self.miolo.pack(fill="both", expand=True, pady=(px(16), 0))

    def adicionar_botao(self, texto, comando, variante="secundario", **kw):
        """Botões entram da direita para a esquerda: o principal primeiro."""
        b = Botao(self.botoes, texto, comando, variante,
                  fundo_pai=COR["superficie_2"], **kw)
        b.pack(side="right", padx=(px(8), 0))
        return b

    def abrir(self, confirmar=None, foco=None):
        """Liga Esc/Enter, centraliza sobre a janela principal e prende o foco."""
        self.janela.bind("<Escape>", lambda e: self.fechar())
        if confirmar is not None:
            self.janela.bind("<Return>", lambda e: confirmar())
            self.janela.bind("<KP_Enter>", lambda e: confirmar())
        self.janela.protocol("WM_DELETE_WINDOW", self.fechar)
        dono = self.janela.master
        if dono.winfo_viewable():
            self.janela.update_idletasks()
            x = dono.winfo_rootx() + (dono.winfo_width()
                                      - self.janela.winfo_reqwidth()) // 2
            y = dono.winfo_rooty() + (dono.winfo_height()
                                      - self.janela.winfo_reqheight()) // 3
            self.janela.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        if foco is not None:
            foco.focus_set()
        try:
            self.janela.grab_set()     # modal: a janela principal espera
        except tk.TclError:
            pass                       # janela ainda não visível (ex.: testes)

    def fechar(self):
        try:
            self.janela.grab_release()
        except tk.TclError:
            pass
        self.janela.destroy()

