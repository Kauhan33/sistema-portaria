"""
Cores, fontes, ícones e medidas do sistema, num lugar só (tokens com nome).

Sistema de design "Guarita" (docs/design/PROPOSTA_DESIGN.md): a tela é
calma (neutros, um só botão escuro por tela) e só "grita" quando importa,
como uma cancela: verde = pode entrar, âmbar = atenção, vermelho = bloqueado.
O vermelho da UNA é identidade (símbolo, item ativo do menu, login).

As telas nunca escrevem "#d9001b" nem ("Segoe UI", 10): usam COR["marca"],
FONTE["corpo"], ICONE["busca"], px(24) etc. Para mudar o visual, muda-se
este arquivo (e componentes.py, que monta as peças com estes valores).

Dois temas, claro e escuro ("Guarita à noite"), com os mesmos nomes de
token: usar_tema("escuro") troca o conteúdo de COR, ESTADO e CORES_TIPO
e aplicar_tema(janela) refaz os estilos ttk. Cada usuário escolhe o seu
(claro, escuro ou seguir o Windows) no menu da conta; ver interface.py.

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
# Cores: dois temas (claro e escuro), com os MESMOS nomes de token
# ----------------------------------------------------------------------
# As telas leem COR["texto"], ESTADO["erro"], CORES_TIPO["Aluno"]: estes três
# dicionários são sempre os mesmos objetos e usar_tema() troca o conteúdo
# deles. Por isso nenhum módulo guarda uma cor numa constante: ela ficaria
# com o tema de quando o módulo foi importado.
PALETAS = {
    "claro": {
        # marca (vermelho UNA: só identidade)
        "marca": "#D9001B",            # símbolo, traço do item ativo
        "marca_escura": "#B80017",     # botão "marca" com o mouse em cima
        "marca_press": "#9A0013",
        "painel_login": "#D9001B",     # painel vermelho do login
        "texto_sobre_marca": "#FFFFFF",
        # neutros
        "fundo": "#F3F4F6",            # fundo da janela
        "lateral": "#EEF0F3",          # barra lateral
        "superficie": "#FFFFFF",       # cartões, campos, tabelas
        "superficie_2": "#F8F9FB",     # cabeçalho de tabela, zebra, rodapé de diálogo
        "borda": "#E1E4EA",            # contorno de cartão (decorativo)
        "borda_campo": "#C5CBD5",      # contorno do campo
        "traco_campo": "#8C95A6",      # linha de baixo do campo (contraste 3:1)
        "texto": "#1B2330",            # texto principal
        "texto_2": "#475467",          # secundário, cabeçalho de tabela
        "texto_3": "#5B6578",          # dicas, legendas, desativados
        "selecao": "#E3E9F4",          # linha selecionada
        "hover": "#E8EBF0",            # fundo ao passar o mouse
        "press": "#DDE1E8",            # botão fantasma pressionado
        "barra": "#858E9F",            # barras do gráfico, bolinha "saiu" (3:1)
        "rolagem": "#CDD3DC",          # barra de rolagem
        # ação principal (um botão por tela)
        "primario": "#1B2330",
        "primario_hover": "#2E3A4D",
        "primario_press": "#10161F",
        "texto_invertido": "#FFFFFF",  # texto sobre o primário
        "dica_invertida": "#AEB7C6",   # "Enter" dentro do botão primário
        "foco": "#1F5FBF",             # anel de foco do teclado, links
        # estados: cor do texto (o conjunto completo fica em ESTADO)
        "sucesso": "#0B6B3A",
        "alerta": "#8A4600",
        "erro": "#B00017",
        "erro_press": "#F9D9DE",       # botão "perigo" pressionado
        "info": "#1D4E9E",
        # placa Mercosul: é um objeto de verdade, branca nos dois temas
        "placa_fundo": "#FFFFFF",
        "placa_texto": "#1B2330",
        "placa_erro": "#B00017",
        "placa_azul": "#0B3C9C",
        "placa_verde": "#009B3A",
    },
    # "Guarita à noite": ardósia azulada (nem preto puro, nem o claro
    # invertido). As superfícies sobem de tom em vez de ganhar sombra; o
    # primário vira claro (o botão principal continua sendo o ponto de maior
    # contraste da tela) e os estados viram texto claro sobre fundo tingido.
    "escuro": {
        "marca": "#E01A32",            # um pouco mais viva: aparece no escuro
        "marca_escura": "#C8001C",
        "marca_press": "#B0001A",
        "painel_login": "#A8001A",     # vermelho mais fundo: não ofusca à noite
        "texto_sobre_marca": "#FFFFFF",
        "fundo": "#13171D",
        "lateral": "#0F1217",
        "superficie": "#1B2028",
        "superficie_2": "#222833",
        "borda": "#2D3440",
        "borda_campo": "#3E4756",
        "traco_campo": "#7A8599",
        "texto": "#E9EDF3",
        "texto_2": "#B6BFCC",
        "texto_3": "#A0AABA",
        "selecao": "#263A5C",
        "hover": "#262D38",
        "press": "#2F3744",
        "barra": "#6F7A8C",
        "rolagem": "#4A5465",
        "primario": "#E9EDF3",
        "primario_hover": "#D2D9E3",
        "primario_press": "#B9C2CF",
        "texto_invertido": "#13171D",
        "dica_invertida": "#4E5868",
        "foco": "#7DB1FF",
        "sucesso": "#5FD08F",
        "alerta": "#F2B45A",
        "erro": "#FF8A93",
        "erro_press": "#4A1E24",
        "info": "#8DB8FF",
        "placa_fundo": "#FFFFFF",
        "placa_texto": "#1B2330",
        "placa_erro": "#B00017",
        "placa_azul": "#0B3C9C",
        "placa_verde": "#009B3A",
    },
}

# Estados de aviso: (texto, fundo, borda). A cor nunca é o único sinal:
# todo estado tem ícone e texto.
ESTADOS = {
    "claro": {
        "sucesso": ("#0B6B3A", "#E8F5EE", "#B5DEC5"),
        "alerta": ("#8A4600", "#FFF4E0", "#F2D29B"),
        "erro": ("#B00017", "#FDECEE", "#F3BAC2"),
        "info": ("#1D4E9E", "#EAF1FC", "#BCD0F0"),
        "neutro": ("#475467", "#F3F4F6", "#E1E4EA"),
    },
    "escuro": {
        "sucesso": ("#5FD08F", "#12291E", "#245A3C"),
        "alerta": ("#F2B45A", "#2E2210", "#644817"),
        "erro": ("#FF8A93", "#33161A", "#6A2C34"),
        "info": ("#8DB8FF", "#14233D", "#2B4878"),
        "neutro": ("#B6BFCC", "#222833", "#2D3440"),
    },
}

# cor do ponto ao lado de cada tipo de acesso (≥ 4,5:1 na superfície)
TIPOS_POR_TEMA = {
    "claro": {"Aluno": "#1D4E9E", "Professor": "#6B3FA0",
              "Funcionário": "#0B6B3A", "Visitante": "#8A4600",
              "Entregador": "#B00017", "Prestador de serviço": "#475467"},
    "escuro": {"Aluno": "#8DB8FF", "Professor": "#C3A2F0",
               "Funcionário": "#5FD08F", "Visitante": "#F2B45A",
               "Entregador": "#FF8A93", "Prestador de serviço": "#B6BFCC"},
}

COR, ESTADO, CORES_TIPO = {}, {}, {}
TEMA = {"atual": None}            # "claro" ou "escuro": o que está na tela

# Preferência de cada usuário (coluna usuarios.tema) -> texto do menu
PREFERENCIAS_TEMA = {"claro": "Claro", "escuro": "Escuro",
                     "sistema": "Seguir o Windows"}
PREFERENCIA_PADRAO = "sistema"
CHAVE_TEMA_WINDOWS = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
# SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
SWP_REDESENHAR_MOLDURA = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020


def usar_tema(nome):
    """Troca as cores de COR, ESTADO e CORES_TIPO para o tema "claro" ou
    "escuro". Devolve True se mudou. As telas já montadas não mudam
    sozinhas: quem troca o tema remonta a janela (AppPortaria)."""
    if nome == TEMA["atual"]:
        return False
    for destino, origem in ((COR, PALETAS), (ESTADO, ESTADOS),
                            (CORES_TIPO, TIPOS_POR_TEMA)):
        destino.clear()
        destino.update(origem[nome])
    TEMA["atual"] = nome
    return True


def windows_usa_tema_escuro():
    """Lê no registro se o Windows está no modo escuro para os aplicativos
    (AppsUseLightTheme = 0). Fora do Windows, ou sem a chave: claro."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_TEMA_WINDOWS) as k:
            valor, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
    except (ImportError, OSError):
        return False
    return valor == 0


def resolver_tema(preferencia):
    """Preferência do usuário -> tema a usar ("claro" ou "escuro")."""
    if preferencia in PALETAS:
        return preferencia
    return "escuro" if windows_usa_tema_escuro() else "claro"


def pintar_barra_de_titulo(janela):
    """Barra de título do Windows escura no tema escuro (Windows 10 20H1+ e
    11: atributo DWMWA_USE_IMMERSIVE_DARK_MODE). Fora do Windows, ou se ele
    recusar, nada acontece: a barra fica como o Windows quiser."""
    escuro = ctypes.c_int(1 if TEMA["atual"] == "escuro" else 0)
    try:
        janela.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(janela.winfo_id())
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(escuro),
            ctypes.sizeof(escuro))
        # a barra só é redesenhada quando a moldura "muda"
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                                          SWP_REDESENHAR_MOLDURA)
    except (AttributeError, OSError):
        pass


def luminancia(cor):
    """Luminância relativa (WCAG 2.x) de uma cor "#RRGGBB"."""
    canais = [int(cor[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
               for c in canais)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(cor1, cor2):
    """Razão de contraste WCAG entre duas cores (de 1 a 21)."""
    clara, escura = sorted((luminancia(cor1), luminancia(cor2)), reverse=True)
    return (clara + 0.05) / (escura + 0.05)


# WCAG AA: texto comum 4,5:1; elementos gráficos (barras, bolinhas,
# contorno do campo, anel de foco) 3:1
TEXTO_AA, GRAFICO_AA = 4.5, 3.0


def pares_de_contraste():
    """(o quê, cor da frente, cor do fundo, mínimo) de todos os pares de
    texto/fundo e gráfico/fundo do tema em uso. O teste confere cada um nos
    dois temas e a tabela da documentação sai desta mesma lista."""
    c = COR
    pares = []
    for fundo in ("fundo", "lateral", "superficie", "superficie_2", "hover"):
        for texto in ("texto", "texto_2", "texto_3"):
            pares.append((f"{texto} / {fundo}", c[texto], c[fundo], TEXTO_AA))
    pares += [
        ("texto / selecao", c["texto"], c["selecao"], TEXTO_AA),
        ("texto_3 / selecao (linha apagada selecionada)", c["texto_3"],
         c["selecao"], TEXTO_AA),
        ("foco (link) / superficie", c["foco"], c["superficie"], TEXTO_AA),
        ("foco (link) / fundo", c["foco"], c["fundo"], TEXTO_AA),
    ]
    for fundo in ("primario", "primario_hover", "primario_press"):
        pares.append((f"texto_invertido / {fundo}", c["texto_invertido"],
                      c[fundo], TEXTO_AA))
    pares += [
        ("dica_invertida / primario", c["dica_invertida"], c["primario"],
         TEXTO_AA),
        ("dica_invertida / primario_hover", c["dica_invertida"],
         c["primario_hover"], TEXTO_AA),
        ("texto_3 / hover (botão desativado)", c["texto_3"], c["hover"],
         TEXTO_AA),
    ]
    for fundo in ("marca", "marca_escura", "marca_press", "painel_login"):
        pares.append((f"texto_sobre_marca / {fundo}", c["texto_sobre_marca"],
                      c[fundo], TEXTO_AA))
    for nome, (texto, fundo, _) in ESTADO.items():
        pares.append((f"estado {nome}: texto / fundo", texto, fundo, TEXTO_AA))
        pares.append((f"texto / fundo do estado {nome} (linha em destaque)",
                      c["texto"], fundo, TEXTO_AA))
    for nome in ("sucesso", "alerta", "erro", "info"):
        for fundo in ("superficie", "fundo"):
            pares.append((f"{nome} / {fundo}", c[nome], c[fundo], TEXTO_AA))
    for tipo, cor in CORES_TIPO.items():
        for fundo in ("superficie", "superficie_2", "selecao"):
            pares.append((f"tipo {tipo} / {fundo}", cor, c[fundo], TEXTO_AA))
    pares += [
        ("placa: caracteres / placa", c["placa_texto"], c["placa_fundo"],
         TEXTO_AA),
        ("placa bloqueada / placa", c["placa_erro"], c["placa_fundo"], TEXTO_AA),
        ("placa: BRASIL / faixa azul", c["placa_fundo"], c["placa_azul"],
         TEXTO_AA),
        ("traco_campo / superficie (linha do campo)", c["traco_campo"],
         c["superficie"], GRAFICO_AA),
        ("foco / superficie (anel de foco)", c["foco"], c["superficie"],
         GRAFICO_AA),
        ("barra / superficie (gráfico, bolinha Saiu)", c["barra"],
         c["superficie"], GRAFICO_AA),
        ("barra / superficie_2 (bolinha na zebra)", c["barra"],
         c["superficie_2"], GRAFICO_AA),
        ("marca / superficie (barra de hoje)", c["marca"], c["superficie"],
         GRAFICO_AA),
        ("texto_2 / superficie_2 (barra horizontal)", c["texto_2"],
         c["superficie_2"], GRAFICO_AA),
    ]
    return pares


usar_tema("claro")

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
    "config": chr(0xE713), "escudo": chr(0xEA18), "calendario": chr(0xE787),
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
    """Estilos dos widgets ttk da janela (tema clam, redesenhado) e as cores
    padrão dos widgets tk, com as cores do tema em uso (usar_tema). Chamar
    de novo depois de trocar o tema: os widgets ttk mudam na hora."""
    s = ttk.Style(janela)
    s.theme_use("clam")
    sup, sup2 = COR["superficie"], COR["superficie_2"]
    _cores_padrao_tk(janela)

    # Lista de escolha sem borda própria: a moldura é o Campo desenhado
    s.configure("Liso.TCombobox", fieldbackground=sup, background=sup,
                foreground=COR["texto"], bordercolor=sup, lightcolor=sup,
                darkcolor=sup, arrowcolor=COR["texto_2"], arrowsize=px(12),
                padding=(px(6), px(4)), relief="flat")
    s.map("Liso.TCombobox",
          fieldbackground=[("readonly", sup)],
          selectbackground=[("readonly", sup)],
          selectforeground=[("readonly", COR["texto"])],
          foreground=[("disabled", COR["texto_3"]), ("readonly", COR["texto"])],
          background=[("active", sup), ("pressed", sup)],
          bordercolor=[("focus", sup)], lightcolor=[("focus", sup)])
    janela.option_add("*TCombobox*Listbox.font", FONTE["corpo"])
    janela.option_add("*TCombobox*Listbox.selectBackground", COR["selecao"])
    janela.option_add("*TCombobox*Listbox.selectForeground", COR["texto"])
    janela.option_add("*TCombobox*Listbox.background", sup)
    janela.option_add("*TCombobox*Listbox.foreground", COR["texto"])

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
    s.configure("Compacta.Tabela.Treeview", rowheight=px(27))

    # Barra de rolagem fina, sem setas
    s.layout("Fina.Vertical.TScrollbar", [
        ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    s.configure("Fina.Vertical.TScrollbar", troughcolor=sup,
                background=COR["rolagem"], bordercolor=sup,
                lightcolor=COR["rolagem"], darkcolor=COR["rolagem"],
                arrowsize=px(8), gripcount=0,
                relief="flat")
    s.map("Fina.Vertical.TScrollbar", background=[("active", COR["barra"])])

    # Páginas: um Notebook com as abas escondidas (a navegação é a barra
    # lateral; app.abas.select(...) continua valendo)
    s.layout("Paginas.TNotebook.Tab", [])
    s.layout("Paginas.TNotebook", [("Notebook.client", {"sticky": "nswe"})])
    # (sem as cores de borda o clam desenha um contorno bege em volta)
    s.configure("Paginas.TNotebook", background=COR["fundo"], borderwidth=0,
                tabmargins=0, bordercolor=COR["fundo"],
                lightcolor=COR["fundo"], darkcolor=COR["fundo"])
    return s


def _cores_padrao_tk(janela):
    """Cores padrão dos widgets tk que não dizem a sua (menu da conta, a
    lista do Combobox): sem isto eles
    ficariam claros no tema escuro."""
    padroes = {
        "*Background": COR["superficie"], "*Foreground": COR["texto"],
        "*activeBackground": COR["selecao"], "*activeForeground": COR["texto"],
        "*selectBackground": COR["selecao"], "*selectForeground": COR["texto"],
        "*insertBackground": COR["texto"], "*highlightBackground": COR["superficie"],
        "*highlightColor": COR["foco"], "*troughColor": COR["superficie_2"],
        "*disabledForeground": COR["texto_3"],
    }
    for padrao, cor in padroes.items():
        janela.option_add(padrao, cor)
