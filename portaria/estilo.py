"""
Cores, fontes, ícones e medidas do sistema, num lugar só (tokens com nome).

Sistema de design "Guarita" (docs/design/PROPOSTA_DESIGN.md): a tela é
calma (neutros, um só botão escuro por tela) e só "grita" quando importa,
como uma cancela: verde = pode entrar, âmbar = atenção, vermelho = bloqueado.
O vermelho da UNA é identidade (símbolo, item ativo do menu, login).

As telas nunca escrevem "#d9001b" nem ("Segoe UI", 10): usam COR["marca"],
FONTE["corpo"], ICONE["busca"], px(24) etc. Para mudar o visual, muda-se
este arquivo (e componentes.py, que monta as peças com estes valores).

Nitidez (DPI): com a escala do Windows em 125%, o programa precisa avisar
que sabe lidar com a escala (ligar_nitidez), senão o Windows estica a
janela como uma imagem e o texto fica borrado. Com o aviso ligado, tudo o
que é medido em pixels passa por px(); as fontes (em pontos) o Tk já ajusta.
"""

import ctypes
import tkinter.font as tkfont
from tkinter import ttk

# ----------------------------------------------------------------------
# Escala da tela (DPI)
# ----------------------------------------------------------------------
ESCALA = 1.0          # 1.25 com a escala de 125% do Windows


def ligar_nitidez():
    """
    Avisa o Windows que o programa desenha na escala certa (texto nítido).
    Chame ANTES de criar a janela. Devolve a escala (ex.: 1.25). Fora do
    Windows, ou nos testes (que não chamam), a escala fica 1.
    """
    global ESCALA
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        ESCALA = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
    except (AttributeError, OSError):
        ESCALA = 1.0
    return ESCALA


def px(n):
    """Medida em pixels "lógicos" (de 100%) → pixels reais da tela."""
    return max(1, round(n * ESCALA))


# ----------------------------------------------------------------------
# Cores
# ----------------------------------------------------------------------
COR = {
    # marca (vermelho UNA: só identidade)
    "marca": "#D9001B",            # símbolo, traço do item ativo, painel do login
    "marca_escura": "#B80017",
    # neutros
    "fundo": "#F3F4F6",            # fundo da janela
    "lateral": "#EEF0F3",          # barra lateral
    "superficie": "#FFFFFF",       # cartões, campos, tabelas
    "superficie_2": "#F8F9FB",     # cabeçalho de tabela, linha zebrada, rodapé de diálogo
    "borda": "#E1E4EA",            # contorno de cartão (decorativo)
    "borda_campo": "#C5CBD5",      # contorno do campo
    "traco_campo": "#8C95A6",      # linha de baixo do campo (contraste 3:1)
    "texto": "#1B2330",            # texto principal (15,8:1)
    "texto_2": "#475467",          # secundário, cabeçalho de tabela (7,7:1)
    "texto_3": "#5B6578",          # dicas, legendas, desativados (5,9:1)
    "selecao": "#E3E9F4",          # linha selecionada
    "hover": "#E8EBF0",            # fundo ao passar o mouse
    "barra": "#AEB7C6",            # barras do gráfico, bolinha "saiu"
    # ação principal (um botão por tela)
    "primario": "#1B2330",
    "primario_hover": "#2E3A4D",
    "primario_press": "#10161F",
    "foco": "#1F5FBF",             # anel de foco do teclado, links
    "texto_invertido": "#FFFFFF",  # texto sobre o primário ou a marca
    # estados: cor do texto (o conjunto completo fica em ESTADO)
    "sucesso": "#0B6B3A",
    "alerta": "#8A4600",
    "erro": "#B00017",
    "info": "#1D4E9E",
    # placa Mercosul
    "placa_azul": "#0B3C9C",
    "placa_verde": "#009B3A",
}

# Estados de aviso: (texto, fundo, borda). Contraste texto/fundo ≥ 5,9:1.
# A cor nunca é o único sinal: todo estado tem ícone e texto.
ESTADO = {
    "sucesso": ("#0B6B3A", "#E8F5EE", "#B5DEC5"),
    "alerta": ("#8A4600", "#FFF4E0", "#F2D29B"),
    "erro": ("#B00017", "#FDECEE", "#F3BAC2"),
    "info": ("#1D4E9E", "#EAF1FC", "#BCD0F0"),
    "neutro": ("#475467", "#F3F4F6", "#E1E4EA"),
}

# cor do ponto ao lado de cada tipo de acesso (≥ 4,5:1 no branco)
CORES_TIPO = {"Aluno": "#1D4E9E", "Professor": "#6B3FA0",
              "Funcionário": "#0B6B3A", "Visitante": "#8A4600",
              "Entregador": "#B00017", "Prestador de serviço": "#475467"}

# ----------------------------------------------------------------------
# Ícones: Segoe Fluent Icons (Windows 11) / Segoe MDL2 Assets (Windows 10).
# Sempre pelo código (chr(0xE...)): o caractere colado no arquivo some
# em alguns editores, porque é de uso privado.
# ----------------------------------------------------------------------
ICONE = {
    "entrada": chr(0xE8AB), "pessoas": chr(0xE716), "bloqueio": chr(0xE733),
    "painel": chr(0xE9F9), "usuarios": chr(0xE7EF), "sair": chr(0xE7E8),
    "busca": chr(0xE721), "mais": chr(0xE710), "lixo": chr(0xE74D),
    "editar": chr(0xE70F), "relogio": chr(0xE823), "desfazer": chr(0xE7A7),
    "ok": chr(0xE73E), "alerta": chr(0xE7BA), "erro": chr(0xE783),
    "info": chr(0xE946), "seta": chr(0xE72A), "cadeado": chr(0xE72E),
    "pessoa": chr(0xE77B), "carro": chr(0xE804), "baixar": chr(0xE896),
    "chave": chr(0xE8D7), "mais_opcoes": chr(0xE712),
    "config": chr(0xE713), "escudo": chr(0xEA18),
}

# ----------------------------------------------------------------------
# Fontes do Windows (nada para instalar). carregar_fontes() troca as
# famílias pelas melhores disponíveis (Segoe UI Variable no Windows 11).
# ----------------------------------------------------------------------
FAMILIAS = {
    "display": "Segoe UI Semibold",   # títulos de página
    "texto": "Segoe UI",              # corpo
    "semi": "Segoe UI Semibold",      # rótulos, botões, avisos
    "numero": "Bahnschrift",          # relógio, números do Painel
    "numero_semi": "Bahnschrift",
    "placa": "Bahnschrift",           # placa Mercosul (parente da fonte das placas)
    "icone": "Segoe MDL2 Assets",
}

PREFERIDAS = {
    "display": ("Segoe UI Variable Display Semib", "Segoe UI Semibold"),
    "texto": ("Segoe UI Variable Text", "Segoe UI"),
    "semi": ("Segoe UI Variable Text Semibold", "Segoe UI Semibold"),
    "numero": ("Bahnschrift",),
    "numero_semi": ("Bahnschrift SemiBold", "Bahnschrift"),
    "placa": ("Bahnschrift SemiBold SemiConden", "Bahnschrift SemiBold",
              "Bahnschrift"),
    "icone": ("Segoe Fluent Icons", "Segoe MDL2 Assets"),
}


def _montar_fontes():
    f = FAMILIAS
    return {
        # escala tipográfica (pt): 9 · 10 · 12 · 16 · 18 · 28
        "titulo_grande": (f["display"], 28),     # "Portaria" no login
        "titulo_pagina": (f["display"], 18),     # "Entrada e saída", "Pessoas"
        "titulo_dialogo": (f["display"], 16),    # "Corrigir registro #12"
        "titulo_cartao": (f["semi"], 12),        # "Nova entrada", "Movimento"
        "marca": (f["semi"], 13),                # "Portaria" na barra lateral
        "corpo": (f["texto"], 10),               # campos, tabelas, texto
        "corpo_grande": (f["texto"], 12),        # texto do painel do login
        "corpo_semi": (f["semi"], 10),           # avisos, item ativo do menu
        "rotulo": (f["semi"], 9),                # rótulo de campo, cabeçalho de tabela
        "dica": (f["texto"], 9),                 # dicas, legendas, apoio
        "link": (f["semi"], 9, "underline"),     # "Desfazer", "Registrar saída"
        "botao": (f["semi"], 10),
        "numero": (f["numero_semi"], 20),        # histórico da pessoa
        "kpi": (f["numero_semi"], 26),           # números do Painel
        "kpi_destaque": (f["numero_semi"], 34),  # "No campus agora"
        "relogio": (f["numero"], 54),            # relógio do login
        "cpf": (f["numero"], 12),                # CPF na ficha da pessoa
        "placa": (f["placa"], 22),
        "placa_pequena": (f["numero_semi"], 7),  # "BRASIL" na placa
        "grafico": (f["texto"], 9),              # legendas dos gráficos
        "grafico_valor": (f["numero_semi"], 10),  # valores nos gráficos
    }


FONTE = _montar_fontes()


def fonte_icone(tamanho=12):
    return (FAMILIAS["icone"], tamanho)


def carregar_fontes(raiz):
    """Escolhe as melhores famílias instaladas (chame com a janela criada)."""
    instaladas = set(tkfont.families(raiz))
    for papel, opcoes in PREFERIDAS.items():
        FAMILIAS[papel] = next((f for f in opcoes if f in instaladas),
                               FAMILIAS[papel])
    FONTE.update(_montar_fontes())


# ----------------------------------------------------------------------
# Medidas (px lógicos; sempre passam por px() na hora de usar)
# ----------------------------------------------------------------------
MARGEM = 24              # margem da página
ESPACO_CARTOES = 16      # distância entre cartões
ALTURA_CAMPO = 36        # campo e botão (45 px reais a 125%: alvo ≥ 44)
ALTURA_LINHA = 34        # linha da tabela
LARGURA_LATERAL = 232    # barra lateral


# ----------------------------------------------------------------------
# Estilos ttk (tabela, lista de escolha, barra de rolagem, páginas)
# ----------------------------------------------------------------------
def aplicar_tema(janela):
    """Estilos dos widgets ttk da janela (tema clam, redesenhado)."""
    s = ttk.Style(janela)
    s.theme_use("clam")
    sup, sup2 = COR["superficie"], COR["superficie_2"]

    # Lista de escolha sem borda própria: a moldura é o Campo desenhado
    s.configure("Liso.TCombobox", fieldbackground=sup, background=sup,
                foreground=COR["texto"], bordercolor=sup, lightcolor=sup,
                darkcolor=sup, arrowcolor=COR["texto_2"], arrowsize=px(12),
                padding=(px(6), px(4)), relief="flat")
    s.map("Liso.TCombobox",
          fieldbackground=[("readonly", sup)],
          selectbackground=[("readonly", sup)],
          selectforeground=[("readonly", COR["texto"])],
          background=[("active", sup), ("pressed", sup)],
          bordercolor=[("focus", sup)], lightcolor=[("focus", sup)])
    janela.option_add("*TCombobox*Listbox.font", FONTE["corpo"])
    janela.option_add("*TCombobox*Listbox.selectBackground", COR["selecao"])
    janela.option_add("*TCombobox*Listbox.selectForeground", COR["texto"])

    # Tabela: sem bordas, cabeçalho claro, linhas altas, seleção suave
    s.configure("Tabela.Treeview", background=sup, fieldbackground=sup,
                foreground=COR["texto"], bordercolor=sup, lightcolor=sup,
                darkcolor=sup, rowheight=px(ALTURA_LINHA), font=FONTE["corpo"],
                borderwidth=0, relief="flat")
    s.map("Tabela.Treeview", background=[("selected", COR["selecao"])],
          foreground=[("selected", COR["texto"])])
    s.configure("Tabela.Treeview.Heading", background=sup2,
                foreground=COR["texto_2"], font=FONTE["rotulo"], relief="flat",
                borderwidth=0, bordercolor=COR["borda"], lightcolor=sup2,
                darkcolor=COR["borda"], padding=(px(10), px(8)))
    s.map("Tabela.Treeview.Heading", background=[("active", COR["hover"])])
    # sem o triângulo de árvore e sem o retângulo pontilhado de foco
    s.layout("Tabela.Treeview.Item", [
        ("Treeitem.padding", {"sticky": "nswe", "children": [
            ("Treeitem.image", {"side": "left", "sticky": ""}),
            ("Treeitem.text", {"side": "left", "sticky": ""})]})])
    s.layout("Tabela.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    # versão compacta (histórico dentro de diálogos)
    s.configure("Compacta.Tabela.Treeview", rowheight=px(30))

    # Barra de rolagem fina, sem setas
    s.layout("Fina.Vertical.TScrollbar", [
        ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    s.configure("Fina.Vertical.TScrollbar", troughcolor=sup,
                background="#CDD3DC", bordercolor=sup, lightcolor="#CDD3DC",
                darkcolor="#CDD3DC", arrowsize=px(8), gripcount=0,
                relief="flat")
    s.map("Fina.Vertical.TScrollbar", background=[("active", COR["barra"])])

    # Páginas: um Notebook com as abas escondidas (a navegação é a barra
    # lateral; app.abas.select(...) continua valendo)
    s.layout("Paginas.TNotebook.Tab", [])
    s.layout("Paginas.TNotebook", [("Notebook.client", {"sticky": "nswe"})])
    s.configure("Paginas.TNotebook", background=COR["fundo"], borderwidth=0,
                tabmargins=0)
    return s

