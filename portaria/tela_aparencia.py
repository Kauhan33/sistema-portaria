"""
Página "Aparência" (3.5): cada usuário deixa o sistema do seu jeito.

- Barra lateral: grafite (a de sempre), vermelha ou branca;
- Botões principais: vermelhos (os de sempre), azuis ou brancos;
- Tema: claro, escuro ou seguir o Windows;
- Tamanho da letra: normal, grande ou maior.

Cada opção é um cartão com uma prévia desenhada (o porteiro vê o resultado
antes de escolher). Um clique (ou Espaço/Enter no cartão com o foco) grava
a escolha no usuário e a janela é remontada na hora, como na troca de tema;
vale nos próximos logins, em qualquer computador. A tela de login não muda:
ela é da portaria, não de um usuário.
"""

import tkinter as tk
import tkinter.font as tkfont

from . import estilo
from .componentes import Botao, Cabecalho, Cartao, ret_arredondado
from .estilo import COR, FONTE, MARGEM, RAIO_CONTROLE, px

ALTURA_OPCAO = 86
NOTA_LOGIN = ("As escolhas valem só para você, em qualquer computador da "
              "portaria. A tela de login continua com as cores de sempre.")


class OpcaoVisual(tk.Canvas):
    """Cartão de escolha: uma prévia desenhada e o nome embaixo. A opção
    escolhida tem o contorno escuro e o "visto"; Tab leva o foco e Espaço ou
    Enter escolhem. `previa(canvas, x0, y0, x1, y1)` desenha a prévia."""

    def __init__(self, pai, texto, previa, comando, escolhida=False):
        self.fundo_pai = COR["superficie"]
        super().__init__(pai, width=1, height=px(ALTURA_OPCAO),
                         bg=self.fundo_pai, highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=1)
        self.texto, self.previa, self.comando = texto, previa, comando
        self.escolhida, self.hover, self.focado = escolhida, False, False
        self.bind("<Configure>", lambda e: self._desenhar())
        self.bind("<Enter>", lambda e: self._mudar("hover", True))
        self.bind("<Leave>", lambda e: self._mudar("hover", False))
        self.bind("<FocusIn>", lambda e: self._mudar("focado", True))
        self.bind("<FocusOut>", lambda e: self._mudar("focado", False))
        self.bind("<ButtonRelease-1>", lambda e: self.invocar())
        for tecla in ("<space>", "<Return>", "<KP_Enter>"):
            self.bind(tecla, lambda e: (self.invocar(), "break")[1])

    def cget(self, chave):
        return self.texto if chave == "text" else super().cget(chave)

    def invocar(self):
        if not self.escolhida:
            self.comando()

    def _mudar(self, atributo, valor):
        setattr(self, atributo, valor)
        self._desenhar()

    def _desenhar(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20:
            return
        fundo = COR["hover"] if self.hover and not self.escolhida \
            else COR["superficie"]
        borda, esp = COR["borda_campo"], 1
        if self.escolhida:
            borda, esp = COR["texto"], px(2)
        if self.focado:
            borda, esp = COR["foco"], px(2)
        ret_arredondado(self, 0, 0, w, h, px(RAIO_CONTROLE), fundo,
                        self.fundo_pai, borda, esp)
        m = px(8)
        self.previa(self, m, m, w - m, h - px(30))
        fonte = FONTE["corpo_semi"] if self.escolhida else FONTE["corpo"]
        self.create_text(w / 2, h - px(15), text=self.texto, font=fonte,
                         fill=COR["texto"])
        if self.escolhida:             # o "visto" no canto
            r = px(9)
            cx, cy = w - px(14), px(14)
            self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=COR["texto"],
                             outline=COR["superficie"], width=px(2))
            self.create_line(cx - r * 0.45, cy, cx - r * 0.1, cy + r * 0.38,
                             cx + r * 0.5, cy - r * 0.35,
                             fill=COR["superficie"], width=max(2, px(2)),
                             capstyle="round", joinstyle="round")


# ----------------------------------------------------------------------
# Prévias (desenhadas com as cores que a opção teria, no tema em uso)
# ----------------------------------------------------------------------
def _cores(tema=None, lateral=None, botoes=None):
    """As cores de uma combinação, sem mexer na que está em uso."""
    tema = tema or estilo.TEMA["atual"]
    cores = dict(estilo.PALETAS[tema])
    cores.update(estilo.LATERAIS[tema][lateral or estilo.APARENCIA["lateral"]])
    escolha = estilo.BOTOES[tema][botoes or estilo.APARENCIA["botoes"]]
    cores.update({k: v for k, v in escolha.items() if not k.startswith("botao")})
    cores.update(botao=cores["primario"], botao_texto=cores["texto_invertido"],
                 botao_borda="")
    cores.update({k: v for k, v in escolha.items() if k.startswith("botao")})
    return cores


def _janela(cv, x0, y0, x1, y1, c):
    """Uma janelinha do sistema: a barra lateral com o símbolo e três itens,
    e um cartão com um botão principal."""
    largura_lateral = (x1 - x0) * 0.34
    ret_arredondado(cv, x0, y0, x1, y1, px(5), c["fundo"], COR["superficie"],
                    c["borda"])
    xl = x0 + largura_lateral
    cv.create_rectangle(x0 + 1, y0 + 1, xl, y1 - 1, fill=c["lateral"], width=0)
    if c.get("lateral_contorno"):
        cv.create_line(xl, y0 + 1, xl, y1 - 1, fill=c["lateral_contorno"])
    s = px(7)
    cv.create_rectangle(x0 + px(5), y0 + px(5), x0 + px(5) + s,
                        y0 + px(5) + s, fill=c["lateral_simbolo"], width=0)
    for i in range(3):
        y = y0 + px(17) + i * px(7)
        ativo = i == 0
        if ativo:
            cv.create_rectangle(x0 + px(3), y - px(2), xl - px(3), y + px(3),
                                fill=c["lateral_ativo"], width=0)
        cv.create_line(x0 + px(6), y, xl - px(7), y, width=max(1, px(2)),
                       fill=c["lateral_destaque"] if ativo
                       else c["lateral_texto"])
    # o cartão com o botão principal
    cx0, cy0 = xl + px(6), y0 + px(6)
    cx1, cy1 = x1 - px(6), y1 - px(6)
    cv.create_rectangle(cx0, cy0, cx1, cy1, fill=c["superficie"],
                        outline=c["borda"])
    cv.create_line(cx0 + px(5), cy0 + px(7), cx1 - px(14), cy0 + px(7),
                   width=max(1, px(2)), fill=c["texto_3"])
    bx1 = cx0 + min(px(34), (cx1 - cx0) - px(8))
    cv.create_rectangle(cx0 + px(5), cy1 - px(11), bx1, cy1 - px(4),
                        fill=c["botao"], outline=c["botao_borda"] or c["botao"])


def previa_da_lateral(cor):
    return lambda cv, *caixa: _janela(cv, *caixa, _cores(lateral=cor))


def previa_dos_botoes(cor):
    def desenhar(cv, x0, y0, x1, y1):
        c = _cores(botoes=cor)
        ret_arredondado(cv, x0, y0, x1, y1, px(5), c["superficie_2"],
                        COR["superficie"], c["borda"])
        fonte = tkfont.Font(root=cv, font=FONTE["botao"])
        texto = "Salvar"
        bw = min(fonte.measure(texto) + px(26), x1 - x0 - px(8))
        bh = min(px(28), y1 - y0 - px(8))
        bx, by = (x0 + x1 - bw) / 2, (y0 + y1 - bh) / 2
        ret_arredondado(cv, bx, by, bx + bw, by + bh, px(6), c["botao"],
                        c["superficie_2"], c["botao_borda"] or None)
        cv.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=texto,
                       font=FONTE["botao"], fill=c["botao_texto"])
    return desenhar


def previa_do_tema(preferencia):
    def desenhar(cv, x0, y0, x1, y1):
        if preferencia in estilo.PALETAS:
            _janela(cv, x0, y0, x1, y1, _cores(tema=preferencia))
            return
        # seguir o Windows: metade clara, metade escura
        meio = (x0 + x1) / 2
        claro, escuro = _cores(tema="claro"), _cores(tema="escuro")
        ret_arredondado(cv, x0, y0, x1, y1, px(5), claro["fundo"],
                        COR["superficie"], claro["borda"])
        cv.create_rectangle(meio, y0 + 1, x1 - 1, y1 - 1, fill=escuro["fundo"],
                            width=0)
        for c, a, b in ((claro, x0, meio), (escuro, meio, x1)):
            cv.create_rectangle(a + px(6), y0 + px(8), b - px(6), y1 - px(8),
                                fill=c["superficie"], outline=c["borda"])
            cv.create_line(a + px(10), y0 + px(16), b - px(10), y0 + px(16),
                           width=max(1, px(2)), fill=c["texto_2"])
    return desenhar


def previa_da_letra(letra):
    def desenhar(cv, x0, y0, x1, y1):
        ret_arredondado(cv, x0, y0, x1, y1, px(5), COR["superficie_2"],
                        COR["superficie"], COR["borda"])
        base = FONTE["corpo"]
        tamanho = round(13 * estilo.ZOOMS[letra])
        cv.create_text((x0 + x1) / 2, (y0 + y1) / 2, text="Aa",
                       font=(base[0], tamanho), fill=COR["texto"])
    return desenhar


class AbaAparencia:
    """A página: quatro escolhas em dois pares de colunas e "Restaurar o
    padrão". Monta de novo a cada troca (a janela é remontada)."""

    def __init__(self, aba, app):
        self.aba, self.app = aba, app
        self.opcoes = {}           # (grupo, valor) -> OpcaoVisual
        cab = Cabecalho(aba, "Aparência",
                        "Deixe o sistema do seu jeito: cores, tema e "
                        "tamanho da letra").posicionar()
        self.btn_padrao = Botao(cab.acoes, "Restaurar o padrão",
                                self.restaurar_padrao, "secundario",
                                fundo_pai=COR["fundo"])
        self.btn_padrao.pack(side="right")
        cartao = Cartao(aba, pad=20)
        cartao.pack(fill="x", padx=px(MARGEM))
        m = cartao.miolo
        m.columnconfigure((0, 1), weight=1, uniform="ap")
        usuario = app.usuario or {}
        lateral, botoes = estilo.APARENCIA["lateral"], estilo.APARENCIA["botoes"]
        self._grupo(m, 0, 0, "lateral", "Barra lateral",
                    "A cor do menu à esquerda.",
                    estilo.NOMES_DA_LATERAL, lateral, previa_da_lateral,
                    lambda v: app.trocar_aparencia(lateral=v))
        self._grupo(m, 0, 1, "botoes", "Botões principais",
                    "O botão de cada tela (Cadastrar, Salvar...).",
                    estilo.NOMES_DOS_BOTOES, botoes, previa_dos_botoes,
                    lambda v: app.trocar_aparencia(botoes=v))
        self._grupo(m, 2, 0, "tema", "Tema", "Claro, escuro ou o do Windows.",
                    {"claro": "Claro", "escuro": "Escuro",
                     "sistema": "Do Windows"},
                    usuario.get("tema", "sistema"), previa_do_tema,
                    app.trocar_tema)
        self._grupo(m, 2, 1, "letra", "Tamanho da letra",
                    "Aumenta o texto e as telas juntos.",
                    estilo.NOMES_DA_LETRA, usuario.get("letra", "normal"),
                    previa_da_letra, app.trocar_letra)
        self.lbl_nota = tk.Label(aba, text=NOTA_LOGIN, font=FONTE["dica"],
                                 bg=COR["fundo"], fg=COR["texto_3"],
                                 anchor="w", justify="left")
        self.lbl_nota.pack(fill="x", padx=px(MARGEM), pady=(px(10), 0))

    def _grupo(self, pai, linha, coluna, grupo, titulo, apoio, nomes, atual,
               previa, ao_escolher):
        caixa = tk.Frame(pai, bg=COR["superficie"])
        caixa.grid(row=linha, column=coluna, sticky="new",
                   padx=(0, px(14)) if coluna == 0 else (px(14), 0),
                   pady=(0, px(18)) if linha == 0 else 0)
        tk.Label(caixa, text=titulo, font=FONTE["titulo_cartao"],
                 bg=COR["superficie"], fg=COR["texto"]).pack(anchor="w")
        tk.Label(caixa, text=apoio, font=FONTE["dica"], bg=COR["superficie"],
                 fg=COR["texto_3"]).pack(anchor="w", pady=(0, px(8)))
        linha_opcoes = tk.Frame(caixa, bg=COR["superficie"])
        linha_opcoes.pack(fill="x")
        linha_opcoes.columnconfigure(tuple(range(len(nomes))), weight=1,
                                     uniform=grupo)
        for i, (valor, nome) in enumerate(nomes.items()):
            opcao = OpcaoVisual(linha_opcoes, nome, previa(valor),
                                lambda v=valor: ao_escolher(v),
                                escolhida=valor == atual)
            opcao.grid(row=0, column=i, sticky="ew",
                       padx=(0 if i == 0 else px(8), 0))
            self.opcoes[(grupo, valor)] = opcao

    def escolhida(self, grupo):
        """O valor escolhido de um grupo ("lateral", "botoes", "tema",
        "letra")."""
        return next(v for (g, v), o in self.opcoes.items()
                    if g == grupo and o.escolhida)

    def restaurar_padrao(self):
        """Grafite, vermelho, seguir o Windows e letra normal."""
        self.app.restaurar_aparencia()

    def atualizar(self):
        """Marca de novo o que está escolhido (uma troca que não muda as
        cores, como "Claro" com o Windows no claro, não remonta a janela)."""
        usuario = self.app.usuario or {}
        atuais = {"lateral": estilo.APARENCIA["lateral"],
                  "botoes": estilo.APARENCIA["botoes"],
                  "tema": usuario.get("tema", estilo.PREFERENCIA_PADRAO),
                  "letra": usuario.get("letra", "normal")}
        for (grupo, valor), opcao in self.opcoes.items():
            escolhida = atuais[grupo] == valor
            if opcao.escolhida != escolhida:
                opcao.escolhida = escolhida
                opcao._desenhar()
