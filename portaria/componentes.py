"""
Peças de tela reutilizáveis: rótulos, campos, tabelas, botões e cartões.

As telas dizem O QUE montar (ex.: campo("Nome completo")); o COMO (fonte,
cor, validação de digitação) fica aqui, num lugar só. As funções criam o
widget mas não o posicionam: grid ou pack continua sendo decisão da tela
(exceto botao(), que já se coloca na fila de botões).
"""

import tkinter as tk
from tkinter import ttk

from .estilo import COR, FONTE

TAMANHO_PLACA = 7
COLUNAS_EVENTOS = [("momento", "Data e hora"), ("usuario", "Usuário"),
                   ("acao", "Ação"), ("detalhe", "Detalhe")]


# ------------------------------------------------------------------
# Textos
# ------------------------------------------------------------------
def rotulo(pai, texto, fundo=COR["superficie"]):
    """Rótulo de campo dentro de um cartão branco."""
    return tk.Label(pai, text=texto, bg=fundo, fg=COR["texto_2"],
                    font=FONTE["rotulo"])


def rotulo_secao(pai, texto, fundo=COR["fundo"]):
    """Rótulo em negrito sobre o fundo da aba ("Buscar...", "Lista de...")."""
    return tk.Label(pai, text=texto, bg=fundo, font=FONTE["rotulo_secao"])


def dica(pai, texto, fundo=COR["fundo"], cor=COR["texto_3"]):
    """Texto pequeno de ajuda embaixo de um campo."""
    return tk.Label(pai, text=texto, bg=fundo, fg=cor, font=FONTE["dica"])


# ------------------------------------------------------------------
# Campos
# ------------------------------------------------------------------
def entrada(pai, **opcoes):
    """Caixa de texto padrão (ttk.Entry com a fonte do corpo)."""
    opcoes.setdefault("font", FONTE["corpo"])
    return ttk.Entry(pai, **opcoes)


def entrada_numeros(pai, limite, **opcoes):
    """Caixa que só aceita dígitos, no máximo `limite` (CPF, celular)."""
    def aceita(texto):
        return texto == "" or (texto.isascii() and texto.isdigit()
                               and len(texto) <= limite)
    return entrada(pai, validate="key",
                   validatecommand=(pai.register(aceita), "%P"), **opcoes)


def entrada_placa(pai, var=None, restringir=True, **opcoes):
    """
    Caixa da placa: o texto vira maiúsculo enquanto se digita. Com
    `restringir`, só aceita letras e números, até 7. Devolve (entry, var).
    """
    var = var if var is not None else tk.StringVar()

    def maiuscula(*_):
        texto = var.get()
        if texto != texto.upper():
            var.set(texto.upper())

    def aceita(texto):
        return texto == "" or (texto.isascii() and texto.isalnum()
                               and len(texto) <= TAMANHO_PLACA)

    var.trace_add("write", maiuscula)
    if restringir:
        opcoes.update(validate="key",
                      validatecommand=(pai.register(aceita), "%P"))
    return entrada(pai, textvariable=var, **opcoes), var


def combo(pai, valores, **opcoes):
    """Lista de escolha (só se escolhe, não se digita)."""
    opcoes.setdefault("font", FONTE["corpo"])
    return ttk.Combobox(pai, values=list(valores), state="readonly", **opcoes)


def grupo_campo(pai, texto, pagina=False, espaco=(6, 2)):
    """
    Frame com o rótulo em cima; o campo vai dentro dele, com pack.
    pagina=True: sobre o fundo da aba (Cadastro); senão, dentro de cartão.
    espaco: folga em cima e embaixo do rótulo.
    """
    fundo = COR["fundo"] if pagina else COR["superficie"]
    grupo = tk.Frame(pai, bg=fundo)
    criar_rotulo = rotulo_secao if pagina else rotulo
    criar_rotulo(grupo, texto, fundo).pack(anchor="w", pady=espaco)
    return grupo


def campo(pai, texto, pagina=False, espaco=(6, 2), **opcoes):
    """Rótulo + caixa de texto. Devolve (grupo, entry); a tela posiciona o grupo."""
    grupo = grupo_campo(pai, texto, pagina, espaco)
    caixa = entrada(grupo, **opcoes)
    caixa.pack(fill="x")
    return grupo, caixa


def barra_busca(pai, texto):
    """Linha "rótulo + caixa de busca" sobre o fundo; devolve (barra, entry)."""
    barra = tk.Frame(pai, bg=COR["fundo"])
    rotulo_secao(barra, texto).pack(side="left")
    busca = entrada(barra)
    busca.pack(side="left", fill="x", expand=True, padx=8)
    busca.bind("<Return>", lambda e: "break")     # Enter na busca não cadastra
    return barra, busca


# ------------------------------------------------------------------
# Tabelas
# ------------------------------------------------------------------
def tabela(pai, colunas, altura=None, selecao="browse", rolagem=True,
           fundo=COR["fundo"]):
    """
    Tabela (Treeview) dentro de um Frame, com barra de rolagem.
    colunas: lista de (id, título, largura, âncora). Devolve (quadro, tabela).
    """
    quadro = tk.Frame(pai, bg=fundo)
    opcoes = {"height": altura} if altura else {}
    tab = ttk.Treeview(quadro, show="headings", selectmode=selecao,
                       columns=[c[0] for c in colunas], **opcoes)
    for col, titulo, largura, ancora in colunas:
        tab.heading(col, text=titulo)
        tab.column(col, width=largura, anchor=ancora)
    tab.pack(side="left", fill="both", expand=True)
    if rolagem:
        barra = ttk.Scrollbar(quadro, orient="vertical", command=tab.yview)
        tab.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
    return quadro, tab


def tabela_eventos(pai, larguras, altura, rolagem=True, fundo=COR["fundo"]):
    """Tabela do histórico (data e hora, usuário, ação, detalhe)."""
    colunas = [(col, titulo, largura, "w")
               for (col, titulo), largura in zip(COLUNAS_EVENTOS, larguras)]
    return tabela(pai, colunas, altura, selecao="extended", rolagem=rolagem,
                  fundo=fundo)


def preencher_eventos(tab, eventos):
    tab.delete(*tab.get_children())
    for e in eventos:
        tab.insert("", "end", values=(e["momento"], e["usuario"], e["acao"],
                                      e["detalhe"]))


# ------------------------------------------------------------------
# Botões e cartões
# ------------------------------------------------------------------
def novo_botao(pai, texto, comando, cor, cor_texto=COR["texto_invertido"],
               cor_ativa=None, fonte=FONTE["botao"], **opcoes):
    """Botão chapado colorido, sem posicionar (opcoes: padx, pady...)."""
    return tk.Button(pai, text=texto, command=comando, bg=cor, fg=cor_texto,
                     activebackground=cor_ativa or cor,
                     activeforeground=cor_texto, relief="flat",
                     cursor="hand2", font=fonte, **opcoes)


def botao(pai, texto, cor, comando, lado="left"):
    """Botão padrão, já colocado na fila de botões (da esquerda ou direita)."""
    b = novo_botao(pai, texto, comando, cor, padx=14, pady=6)
    b.pack(side=lado, padx=(0, 8))
    return b


def botao_pequeno(pai, texto, comando, cor, **opcoes):
    return novo_botao(pai, texto, comando, cor, fonte=FONTE["botao_pequeno"],
                      **opcoes)


def botao_link(pai, texto, comando, fundo=COR["fundo"]):
    """Botão que parece link (texto sublinhado, sem fundo próprio)."""
    return tk.Button(pai, text=texto, command=comando, bg=fundo,
                     fg=COR["foco"], activebackground=fundo, relief="flat",
                     cursor="hand2", font=FONTE["link"])


def cartao(pai, faixa=True, padx=24, pady=(16, 20)):
    """
    Caixa branca com borda (e faixa vermelha no topo, se `faixa`).
    Devolve (caixa, miolo): a tela posiciona a caixa e monta no miolo.
    """
    caixa = tk.Frame(pai, bg=COR["superficie"], highlightbackground=COR["borda"],
                     highlightthickness=1)
    if faixa:
        tk.Frame(caixa, bg=COR["marca"], height=4).pack(fill="x")
    miolo = tk.Frame(caixa, bg=COR["superficie"])
    miolo.pack(fill="both", expand=True, padx=padx, pady=pady)
    return caixa, miolo
