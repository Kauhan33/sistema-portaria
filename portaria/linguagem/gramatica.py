"""
A gramática da linguagem (EBNF), num lugar só.

O texto EBNF abaixo é o MESMO de docs/GRAMATICA_DA_LINGUAGEM.md (um teste
confere): o comando `ajuda` mostra as regras daqui e o analisador
sintático (sintatico.py) tem uma função para cada uma.

Este módulo também lê o próprio EBNF (é um pequeno analisador de uma
linguagem de gramáticas) e calcula os conjuntos FIRST e FOLLOW, para
CONFERIR que a gramática é LL(1): em cada escolha (|, [ ] e { }), olhar
um token à frente basta para decidir o caminho. conflitos_ll1() devolve
a lista de conflitos (vazia = LL(1)); os testes e o Word usam.

Terminais: "entrada" (entre aspas) é a palavra da linguagem; PLACA, TIPO,
CPF... (maiúsculas) são os tipos de token do léxico (lexico.py).
"""

import re

EBNF = """\
linha      = comando FIM ;
comando    = entrada | saida | implicito | cadastrar | editar | excluir
           | desativar | reativar | situacao | dentro | buscar
           | pendentes | ajuda ;

entrada    = "entrada" cpf [ TIPO ] { opcao_ent } ;
opcao_ent  = "placa" PLACA
           | "sem" "carro"                 (* a pé, mesmo com placa cadastrada *)
           | "nome" TEXTO
           | "cel" NUMERO
           | "as" HORA                     (* hoje, em outro horário *)
           | "em" DATA HORA ;              (* lançamento retroativo, RN24 *)

saida      = "saida" alvo { opcao_sai } ;
opcao_sai  = "placa" PLACA                 (* com qual carro, RN40 *)
           | "sem" "carro"                 (* sai a pé, o carro fica *)
           | "as" HORA ;
implicito  = cpf | PLACA ;                 (* = saida *)

cadastrar  = "cadastrar" cpf TIPO "nome" TEXTO "cel" NUMERO [ "placa" PLACA ] ;
editar     = "editar" cpf campo { campo } ;
campo      = "nome" TEXTO | "cel" NUMERO | "placa" PLACA | "tipo" TIPO ;
excluir    = "excluir" cpf ;

desativar  = "desativar" alvo "motivo" TEXTO ;
reativar   = "reativar" alvo ;
situacao   = "situacao" alvo ;
dentro     = "dentro" [ TIPO ] ;
buscar     = "buscar" termo [ TIPO ] [ periodo ] ;
termo      = TEXTO | PALAVRA | cpf | PLACA ;
periodo    = PERIODO | "de" DATA [ "ate" DATA ] ;
pendentes  = "pendentes" ;
ajuda      = "ajuda" [ COMANDO ] ;

alvo       = cpf | "placa" PLACA ;
cpf        = CPF | NUMERO ;
"""

# Exemplo de cada comando (o `ajuda` mostra; os testes rodam todos)
EXEMPLOS = {
    "entrada": 'entrada 529.982.247-25 aluno placa ABC1D23',
    "saida": "saida 52998224725 · saida placa ABC1D23 · "
             "saida 52998224725 sem carro",
    "cadastrar": 'cadastrar 111.444.777-35 visitante nome "Bruno Almeida" '
                 'cel 31987651234',
    "editar": "editar 11144477735 cel 31999990000 tipo professor",
    "excluir": "excluir 11144477735",
    "desativar": 'desativar 11144477735 motivo "agressão ao porteiro"',
    "reativar": "reativar 11144477735 · reativar placa ABC1D23",
    "situacao": "situacao 52998224725 · situacao placa ABC1D23",
    "dentro": "dentro · dentro visitante",
    "buscar": "buscar maria visitante semana · "
              "buscar ABC1D23 de 01/10/2026 ate 15/10/2026",
    "pendentes": "pendentes",
    "ajuda": "ajuda · ajuda entrada",
}
FAZ = {
    "entrada": "Registra a entrada (Criar visita)",
    "saida": "Registra a saída da pessoa ou do carro",
    "cadastrar": "Nova pessoa, sem entrada (RN41)",
    "editar": "Muda nome, celular, placa ou tipo do cadastro",
    "excluir": "Exclui o cadastro de quem nunca teve visita (RN42, admin)",
    "desativar": "Pessoa ou veículo desativado não entra (RN12, admin)",
    "reativar": "Encerra a desativação (RN12, admin)",
    "situacao": "Ficha resumida: dentro ou fora, carro, desativado",
    "dentro": "Quem está no campus agora (pode filtrar por tipo)",
    "buscar": "Procura no histórico",
    "pendentes": "Saídas pendentes, tempo excedido e carros com o dono fora",
    "ajuda": "Mostra a gramática (esta tabela)",
}
SO_ADMIN = ("excluir", "desativar", "reativar")


# ------------------------------------------------------------------
# Leitura do EBNF: regra -> expressão
# ------------------------------------------------------------------
# Expressões: ("alt", [seq, ...]), ("seq", [item, ...]), ("opt", expr),
# ("rep", expr), ("t", '"placa"' | "PLACA") e ("nt", "alvo").
_PEDACOS = re.compile(r'\(\*.*?\*\)|"[^"]*"|[A-Za-z_]+|[=;|\[\]{}()]',
                      re.DOTALL)


def ler_ebnf(texto=EBNF):
    """{nome da regra: expressão}, na ordem do texto."""
    pedacos = [p for p in _PEDACOS.findall(texto) if not p.startswith("(*")]
    regras, i = {}, 0

    def alternativa():
        nonlocal i
        opcoes = [sequencia()]
        while i < len(pedacos) and pedacos[i] == "|":
            i += 1
            opcoes.append(sequencia())
        return opcoes[0] if len(opcoes) == 1 else ("alt", opcoes)

    def sequencia():
        nonlocal i
        itens = []
        while i < len(pedacos) and pedacos[i] not in "|;)]}":
            itens.append(fator())
        return itens[0] if len(itens) == 1 else ("seq", itens)

    def fator():
        nonlocal i
        p = pedacos[i]
        i += 1
        if p in "[{(":
            dentro = alternativa()
            i += 1                                   # ] } )
            return {"[": ("opt", dentro), "{": ("rep", dentro),
                    "(": dentro}[p]
        if p.startswith('"') or p.isupper():
            return ("t", p)
        return ("nt", p)

    while i < len(pedacos):
        nome = pedacos[i]
        i += 2                                       # nome =
        regras[nome] = alternativa()
        i += 1                                       # ;
    return regras


def regras_de(nome, regras=None):
    """As linhas do EBNF da regra `nome` (para o `ajuda entrada`)."""
    linhas = EBNF.splitlines()
    for i, linha in enumerate(linhas):
        if linha.startswith(nome + " ") or linha.startswith(nome + "="):
            fim = i
            while not linhas[fim].split("(*")[0].rstrip().endswith(";"):
                fim += 1
            return linhas[i:fim + 1]
    return []


# ------------------------------------------------------------------
# FIRST, FOLLOW e a conferência LL(1)
# ------------------------------------------------------------------
VAZIO = "ε"


def _first_expr(expr, first):
    """FIRST de uma expressão (com VAZIO se ela pode não consumir nada)."""
    tipo = expr[0]
    if tipo == "t":
        return {expr[1]}
    if tipo == "nt":
        return set(first[expr[1]])
    if tipo in ("opt", "rep"):
        return _first_expr(expr[1], first) | {VAZIO}
    if tipo == "alt":
        return set().union(*(_first_expr(e, first) for e in expr[1]))
    resultado = set()                                 # seq
    for item in expr[1]:
        f = _first_expr(item, first)
        resultado |= f - {VAZIO}
        if VAZIO not in f:
            return resultado
    return resultado | {VAZIO}


def calcular_first(regras):
    """{regra: FIRST}, até não mudar mais (ponto fixo)."""
    first = {nome: set() for nome in regras}
    mudou = True
    while mudou:
        mudou = False
        for nome, expr in regras.items():
            novo = _first_expr(expr, first)
            if novo != first[nome]:
                first[nome] = novo
                mudou = True
    return first


def _first_seq(itens, first):
    return _first_expr(("seq", itens), first) if itens else {VAZIO}


def _visitar(expr, depois, first, acao):
    """Chama acao(expr, depois) em cada pedaço, com `depois` = o que pode
    vir logo em seguida a ele (o FOLLOW local)."""
    acao(expr, depois)
    tipo = expr[0]
    if tipo == "seq":
        itens = expr[1]
        for k, item in enumerate(itens):
            resto = _first_seq(itens[k + 1:], first)
            seguinte = (resto - {VAZIO}) | (depois if VAZIO in resto else set())
            _visitar(item, seguinte, first, acao)
    elif tipo == "alt":
        for e in expr[1]:
            _visitar(e, depois, first, acao)
    elif tipo == "opt":
        _visitar(expr[1], depois, first, acao)
    elif tipo == "rep":       # depois de uma repetição pode vir outra
        _visitar(expr[1], depois | (_first_expr(expr[1], first) - {VAZIO}),
                 first, acao)


def calcular_follow(regras, first, inicial="linha"):
    follow = {nome: set() for nome in regras}
    follow[inicial].add("FIM")
    mudou = True
    while mudou:
        mudou = False

        def acao(expr, depois):
            nonlocal mudou
            if expr[0] == "nt" and not depois <= follow[expr[1]]:
                follow[expr[1]] |= depois
                mudou = True
        for nome, expr in regras.items():
            _visitar(expr, follow[nome], first, acao)
    return follow


def conflitos_ll1(texto=EBNF):
    """
    Conflitos LL(1) da gramática (lista vazia = é LL(1)):
    - numa escolha (a | b), os FIRST das alternativas se cruzam;
    - num opcional ou repetição ([a], {a}), o FIRST de `a` cruza com o que
      pode vir depois dele (aí não daria para saber se entra ou pula).
    """
    regras = ler_ebnf(texto)
    first = calcular_first(regras)
    follow = calcular_follow(regras, first)
    conflitos = []

    def acao(expr, depois):
        if expr[0] == "alt":
            vistos = set()
            for alternativa in expr[1]:
                f = _first_expr(alternativa, first) - {VAZIO}
                if f & vistos:
                    conflitos.append(f"escolha com {sorted(f & vistos)} em "
                                     "mais de uma alternativa")
                vistos |= f
        elif expr[0] in ("opt", "rep"):
            f = _first_expr(expr[1], first) - {VAZIO}
            if f & depois:
                conflitos.append(f"{'[ ]' if expr[0] == 'opt' else '{ }'} "
                                 f"com {sorted(f & depois)} também depois")
    for nome, expr in regras.items():
        antes = len(conflitos)
        _visitar(expr, follow[nome], first, acao)
        conflitos[antes:] = [f"{nome}: {c}" for c in conflitos[antes:]]
    return conflitos


def tabela_first(texto=EBNF):
    """[(regra, alternativa em texto, FIRST)] das regras com escolha: a
    tabela "por que é LL(1)" do Word."""
    regras = ler_ebnf(texto)
    first = calcular_first(regras)
    linhas = []
    for nome, expr in regras.items():
        if expr[0] != "alt":
            continue
        for alternativa in expr[1]:
            linhas.append((nome, _escrever(alternativa),
                           sorted(_first_expr(alternativa, first) - {VAZIO})))
    return linhas


def _escrever(expr):
    tipo = expr[0]
    if tipo in ("t", "nt"):
        return expr[1]
    if tipo == "seq":
        return " ".join(_escrever(e) for e in expr[1])
    if tipo == "alt":
        return " | ".join(_escrever(e) for e in expr[1])
    return ("[ " if tipo == "opt" else "{ ") + _escrever(expr[1]) + \
        (" ]" if tipo == "opt" else " }")
