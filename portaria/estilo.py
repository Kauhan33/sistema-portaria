"""
Cores e fontes do sistema, num lugar só (tokens com nome).

As telas nunca escrevem "#d9001b" nem ("Segoe UI", 10): usam COR["marca"],
FONTE["corpo"] etc. Os nomes seguem o sistema de design "Guarita"
(docs/design/PROPOSTA_DESIGN.md); os valores ainda são os da tela atual.
Para mudar o visual, muda-se este arquivo (e componentes.py, que monta
as peças com estes valores).
"""

from tkinter import ttk

COR = {
    # marca
    "marca": "#d9001b",            # vermelho UNA: cabeçalho, faixa dos cartões
    "marca_tinta": "#ffd9de",      # texto claro sobre a marca
    # neutros
    "fundo": "#f4f6fa",            # fundo da janela
    "superficie": "white",         # cartões, gráficos
    "borda": "#dde1ea",            # contorno de cartão
    "texto": "#222",               # títulos
    "texto_2": "#333",             # rótulos dos campos, nomes nos gráficos
    "texto_status": "#444",        # linhas de status, valores nos gráficos
    "texto_rotulo": "#555",        # título dos cards, dias no gráfico
    "texto_3": "#666",             # dicas e subtítulos
    "texto_apoio": "#777",         # linha de apoio dos cards
    "texto_vazio": "#888",         # "Sem dados ainda"
    "desativado": "#999",          # linhas removidas ou inativas
    "linha_grafico": "#ccc",       # eixo do gráfico
    "texto_invertido": "white",    # texto sobre botão colorido ou sobre a marca
    # botões (nesta versão cada tipo de ação ainda tem a sua cor)
    "primario": "#0a9a5a",         # cadastrar, criar, salvar, entrar
    "secundario": "#1f6fd1",       # limpar, salvar alterações, redefinir senha
    "atencao": "#e08a00",          # registrar saída, ativar/desativar
    "neutro": "#5a6b7b",           # corrigir, cancelar, remover bloqueio
    "perigo": "#e03131",           # excluir
    # estados (cor do texto de avisos e dicas)
    "sucesso": "#0a8a50",
    "alerta": "#c46a00",
    "info": "#1f6fd1",
    "erro": "#d9001b",
    "foco": "#1f6fd1",             # link ("Desfazer")
}

# cor de cada tipo de acesso e de cada card de resumo no Dashboard
CORES_TIPO = {"Aluno": "#1f6fd1", "Professor": "#7a3fd1",
              "Funcionário": "#0a9a5a", "Visitante": "#e08a00",
              "Entregador": "#d9001b", "Prestador de serviço": "#5a6b7b"}
CORES_RESUMO = {"total": "#222222", "dentro": "#0a9a5a", "hoje": "#1f6fd1",
                "veiculos": "#e08a00", "permanencia": "#7a3fd1"}
COR_GRAFICO_DIAS = "#1f6fd1"

FAMILIA = "Segoe UI"
FONTE = {
    "titulo_pagina": (FAMILIA, 18, "bold"),    # cabeçalho da janela
    "titulo_login": (FAMILIA, 16, "bold"),
    "titulo_dialogo": (FAMILIA, 14, "bold"),   # janela Corrigir
    "titulo_cartao": (FAMILIA, 12, "bold"),
    "titulo_secao": (FAMILIA, 11, "bold"),     # títulos menores e dos gráficos
    "rotulo_secao": (FAMILIA, 10, "bold"),     # "Buscar...", "Lista de bloqueio"
    "corpo": (FAMILIA, 10),                    # campos e tabelas
    "corpo_semi": (FAMILIA, 10, "bold"),       # usuário logado
    "corpo_grande": (FAMILIA, 11),             # campos do login
    "rotulo": (FAMILIA, 9, "bold"),            # rótulo de campo, título de card
    "legenda": (FAMILIA, 9),                   # status, subtítulos
    "aviso": (FAMILIA, 9, "bold"),             # dica do CPF, aviso da saída
    "link": (FAMILIA, 9, "bold underline"),
    "dica": (FAMILIA, 8),
    "dica_forte": (FAMILIA, 8, "bold"),        # alerta de placa bloqueada
    "botao": (FAMILIA, 10, "bold"),
    "botao_pequeno": (FAMILIA, 9, "bold"),
    "kpi": (FAMILIA, 20, "bold"),              # números do Dashboard
    "aba": (FAMILIA, 10, "bold"),
    "cabecalho_tabela": (FAMILIA, 10, "bold"),
}


def aplicar_tema(janela):
    """Estilo dos widgets ttk (tabelas e abas) da janela principal."""
    estilo = ttk.Style(janela)
    estilo.theme_use("clam")
    estilo.configure("Treeview", rowheight=26, font=FONTE["corpo"])
    estilo.configure("Treeview.Heading", font=FONTE["cabecalho_tabela"])
    estilo.configure("TNotebook", background=COR["fundo"], borderwidth=0)
    estilo.configure("TNotebook.Tab", font=FONTE["aba"], padding=[18, 7])

