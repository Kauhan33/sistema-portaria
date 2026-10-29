"""
Análise LÉXICA: o texto digitado vira uma lista de tokens.

Cada token tem o tipo (COMANDO, CPF, PLACA...), o lexema (o pedaço como
foi digitado), a coluna onde começa (1 = primeiro caractere) e o valor já
na forma do sistema ("Saída" -> "saida", "529.982.247-25" -> "52998224725",
"visitantes" -> "Visitante", "01/10/2026" -> date). A linguagem aceita
maiúsculas e minúsculas, com ou sem acento, e os tipos no plural.

Os tokens (docs/GRAMATICA_DA_LINGUAGEM.md, seção 2):

    COMANDO        entrada, saida, cadastrar ... (COMANDOS)
    PALAVRA_CHAVE  placa, nome, cel, tipo, motivo, sem, carro, as, em, de, ate
    TIPO           aluno, professor ... e os plurais (TIPOS)
    PERIODO        hoje, ontem, semana, mes
    CPF            529.982.247-25 (com a pontuação; sem ela é um NUMERO)
    NUMERO         52998224725, 31987651234
    PLACA          ABC1234, ABC-1234, ABC1D23 (autômato finito, abaixo)
    DATA           01/10/2026 (e a data precisa existir)
    HORA           14:05
    TEXTO          "Bruno Almeida" (entre aspas)
    PALAVRA        letras que não são nenhuma das anteriores (busca)
    FIM            o fim da linha

Ponto didático: um CPF sem pontuação e um celular são o MESMO token, um
NUMERO de 11 dígitos. Quem decide o que ele é é o analisador sintático,
pela posição (depois de "entrada" é CPF, depois de "cel" é celular).

tokenizar() é tolerante (não para no primeiro erro): o campo usa para
colorir a linha a cada tecla. analisar_lexico() para no primeiro erro,
como a fase léxica de um compilador.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

from ..validacao import MAXIMO_COMANDO, TIPOS_ACESSO
from .erros import LEXICO, ErroDeAnalise

# ------------------------------------------------------------------
# Tipos de token
# ------------------------------------------------------------------
COMANDO, PALAVRA_CHAVE, TIPO, PERIODO = ("COMANDO", "PALAVRA_CHAVE", "TIPO",
                                         "PERIODO")
CPF, NUMERO, PLACA, DATA, HORA = "CPF", "NUMERO", "PLACA", "DATA", "HORA"
TEXTO, PALAVRA, FIM, ERRO = "TEXTO", "PALAVRA", "FIM", "ERRO"
TIPOS_DE_TOKEN = (COMANDO, PALAVRA_CHAVE, TIPO, PERIODO, CPF, NUMERO, PLACA,
                  DATA, HORA, TEXTO, PALAVRA, FIM)

# ------------------------------------------------------------------
# Tabela de palavras (sem acento e em minúsculas)
# ------------------------------------------------------------------
COMANDOS = ("entrada", "saida", "cadastrar", "editar", "excluir", "desativar",
            "reativar", "situacao", "dentro", "buscar", "pendentes", "ajuda")
PALAVRAS_CHAVE = ("placa", "nome", "cel", "tipo", "motivo", "sem", "carro",
                  "as", "em", "de", "ate")
PERIODOS = ("hoje", "ontem", "semana", "mes")
# palavra (singular) -> o tipo de acesso como está em validacao.TIPOS_ACESSO
TIPOS = {"aluno": "Aluno", "professor": "Professor",
         "funcionario": "Funcionário", "visitante": "Visitante",
         "entregador": "Entregador", "prestador": "Prestador de serviço"}
PLURAIS = {"alunos": "aluno", "professores": "professor",
           "funcionarios": "funcionario", "visitantes": "visitante",
           "entregadores": "entregador", "prestadores": "prestador"}
# o nome curto de cada tipo de acesso (para escrever um comando de exemplo)
PALAVRA_DO_TIPO = {tipo: palavra for palavra, tipo in TIPOS.items()}
assert sorted(TIPOS.values()) == sorted(TIPOS_ACESSO)   # uma lista só

# ------------------------------------------------------------------
# Padrões
# ------------------------------------------------------------------
REGEX_CPF = re.compile(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$")
# CPF mascarado que o autocompletar escreve para o porteiro (RN14): só vale
# se veio do Tab (o campo guarda o CPF de verdade, ver `apelidos`)
REGEX_CPF_MASCARADO = re.compile(r"^\*{3}\.\d{3}\.\d{3}-\*{2}$")
REGEX_NUMERO = re.compile(r"^\d+$")
REGEX_DATA = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
REGEX_HORA = re.compile(r"^(\d{2}):(\d{2})$")
REGEX_PALAVRA = re.compile(r"^[^\W\d_]+(?:['-][^\W\d_]+)*$")
# caracteres que podem aparecer num lexema fora das aspas
_PERMITIDOS = set(".-/:*'")
DICA_SIMBOLOS = ("Use palavras, números, CPF, placa, data (dd/mm/aaaa), "
                 "hora (hh:mm) ou um texto entre aspas.")
DICA_PLACA = "formatos ABC1234 (antiga) ou ABC1D23 (Mercosul)."

# ------------------------------------------------------------------
# Autômato finito determinístico da PLACA (antiga e Mercosul)
# ------------------------------------------------------------------
# L = letra A-Z, D = dígito, H = hífen. Antiga: LLL[-]DDDD; Mercosul:
# LLL[-]DLDD. O 5º caractere (estado q5) aceita letra ou dígito: é o único
# ponto em que os dois modelos diferem. q8 é o estado final (aceita).
TRANSICOES_PLACA = {
    ("q0", "L"): "q1", ("q1", "L"): "q2", ("q2", "L"): "q3",
    ("q3", "H"): "q4", ("q3", "D"): "q5", ("q4", "D"): "q5",
    ("q5", "L"): "q6", ("q5", "D"): "q6",
    ("q6", "D"): "q7", ("q7", "D"): "q8",
}
INICIAL_PLACA, FINAIS_PLACA = "q0", {"q8"}


def classe_do_caractere(c):
    """'L' (letra A-Z), 'D' (dígito), 'H' (hífen) ou None."""
    if "A" <= c <= "Z":
        return "L"
    if "0" <= c <= "9":
        return "D"
    return "H" if c == "-" else None


def reconhecer_placa(texto):
    """Roda o autômato da placa. Devolve (aceitou, estados visitados): o
    caminho é o que o modo didático e o Word mostram."""
    estado, caminho = INICIAL_PLACA, [INICIAL_PLACA]
    for c in texto.upper():
        estado = TRANSICOES_PLACA.get((estado, classe_do_caractere(c)))
        if estado is None:
            return False, caminho
        caminho.append(estado)
    return estado in FINAIS_PLACA, caminho


# ------------------------------------------------------------------
# Token
# ------------------------------------------------------------------
@dataclass(frozen=True)
class Token:
    tipo: str
    lexema: str
    coluna: int                 # 1 = primeiro caractere da linha
    valor: object = field(default=None, compare=False)
    linha: int = 1

    @property
    def fim(self):
        """Coluna logo depois do token."""
        return self.coluna + len(self.lexema)

    @property
    def terminal(self):
        """Como o token aparece na gramática: palavras da linguagem entre
        aspas ('"placa"'), o resto pelo tipo ('PLACA')."""
        if self.tipo in (COMANDO, PALAVRA_CHAVE):
            return f'"{self.valor}"'
        return self.tipo


def sem_acento(texto):
    """'Saída' -> 'saida' (a comparação das palavras da linguagem)."""
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto
                   if unicodedata.category(c) != "Mn").lower()


def _erro(mensagem, coluna, tamanho=1, dica=""):
    return ErroDeAnalise(LEXICO, mensagem, coluna, tamanho, dica)


def _palavra(lexema, coluna):
    """Uma palavra: comando, palavra-chave, tipo, período ou PALAVRA."""
    chave = sem_acento(lexema)
    if chave in COMANDOS:
        return Token(COMANDO, lexema, coluna, chave)
    if chave in PALAVRAS_CHAVE:
        return Token(PALAVRA_CHAVE, lexema, coluna, chave)
    singular = PLURAIS.get(chave, chave)
    if singular in TIPOS:
        return Token(TIPO, lexema, coluna, TIPOS[singular])
    if chave in PERIODOS:
        return Token(PERIODO, lexema, coluna, chave)
    return Token(PALAVRA, lexema, coluna, chave)


def _data(lexema, coluna):
    m = REGEX_DATA.match(lexema)
    if not m:
        return _erro(f'"{lexema}" não é uma data.', coluna, len(lexema),
                     "escreva dd/mm/aaaa, com dois números no dia e no mês "
                     "(ex.: 01/10/2026).")
    dia, mes, ano = (int(g) for g in m.groups())
    problemas = []
    if not 1 <= dia <= 31:
        problemas.append(f"o dia {dia}")
    if not 1 <= mes <= 12:
        problemas.append(f"o mês {mes}")
    if problemas:
        existe = "não existe" if len(problemas) == 1 else "não existem"
        return _erro(f'"{lexema}" parece uma data, mas '
                     + " e ".join(problemas) + f" {existe}.",
                     coluna, len(lexema))
    try:
        return Token(DATA, lexema, coluna, date(ano, mes, dia))
    except ValueError:
        return _erro(f'"{lexema}" parece uma data, mas esse dia não existe '
                     "no calendário.", coluna, len(lexema))


def _hora(lexema, coluna):
    m = REGEX_HORA.match(lexema)
    if not m:
        return _erro(f'"{lexema}" não é uma hora.', coluna, len(lexema),
                     "escreva hh:mm, com dois números (ex.: 09:05).")
    horas, minutos = int(m.group(1)), int(m.group(2))
    if horas > 23 or minutos > 59:
        return _erro(f'"{lexema}" parece uma hora, mas ela não existe '
                     "(de 00:00 a 23:59).", coluna, len(lexema))
    return Token(HORA, lexema, coluna, (horas, minutos))


def classificar(lexema, coluna, apelidos=None):
    """O token de um lexema (fora das aspas) ou o ErroDeAnalise léxico."""
    for i, c in enumerate(lexema):
        if not (c.isalnum() or c in _PERMITIDOS):
            return _erro(f'o símbolo "{c}" não pertence à linguagem.',
                         coluna + i, 1, DICA_SIMBOLOS)
    if REGEX_CPF_MASCARADO.match(lexema):
        cpf = (apelidos or {}).get(lexema)
        if cpf is None:
            return _erro(f'o CPF mascarado "{lexema}" só vale quando é '
                         "escolhido pelo Tab.", coluna, len(lexema),
                         "digite o CPF inteiro ou escreva parte do nome e "
                         "aperte Tab.")
        return Token(CPF, lexema, coluna, cpf)
    if REGEX_CPF.match(lexema):
        return Token(CPF, lexema, coluna, re.sub(r"\D", "", lexema))
    if REGEX_NUMERO.match(lexema):
        return Token(NUMERO, lexema, coluna, lexema)
    if "/" in lexema:
        return _data(lexema, coluna)
    if ":" in lexema:
        return _hora(lexema, coluna)
    if lexema.isascii():
        aceitou, _ = reconhecer_placa(lexema)
        if aceitou:
            return Token(PLACA, lexema, coluna,
                         lexema.replace("-", "").upper())
    if REGEX_PALAVRA.match(lexema):
        return _palavra(lexema, coluna)
    tem_letra = any(c.isalpha() for c in lexema)
    tem_digito = any(c.isdigit() for c in lexema)
    if tem_letra and tem_digito:
        return _erro(f'"{lexema}" não é uma placa.', coluna, len(lexema),
                     DICA_PLACA[0].upper() + DICA_PLACA[1:])
    if tem_digito:
        return _erro(f'"{lexema}" não é um CPF nem um número.', coluna,
                     len(lexema), "escreva o CPF como 529.982.247-25 ou só "
                                  "os 11 números.")
    return _erro(f'"{lexema}" não pertence à linguagem.', coluna,
                 len(lexema), DICA_SIMBOLOS)


def tokenizar(texto, apelidos=None):
    """
    (tokens, erros) sem parar no primeiro erro: um lexema com erro vira um
    token ERRO e a análise continua (o realce do campo pinta cada um). A
    lista termina sempre com o token FIM. `apelidos`: CPF mascarado ->
    CPF de verdade (o que o autocompletar escreveu para o porteiro).
    """
    tokens, erros, i = [], [], 0
    n = len(texto)
    if n > MAXIMO_COMANDO:
        erros.append(_erro(f"o comando passa de {MAXIMO_COMANDO} caracteres.",
                           MAXIMO_COMANDO + 1, n - MAXIMO_COMANDO))
    while i < n:
        c = texto[i]
        if c.isspace():
            i += 1
            continue
        coluna = i + 1
        if c == '"':                                  # TEXTO
            fecha = texto.find('"', i + 1)
            if fecha < 0:
                erros.append(_erro("texto sem aspas de fechamento.", coluna,
                                   1, 'feche o texto com " (aspas).'))
                tokens.append(Token(ERRO, texto[i:], coluna))
                break
            lexema = texto[i:fecha + 1]
            tokens.append(Token(TEXTO, lexema, coluna,
                                " ".join(lexema[1:-1].split())))
            i = fecha + 1
            continue
        j = i
        while j < n and not texto[j].isspace() and texto[j] != '"':
            j += 1
        lexema = texto[i:j]
        resultado = classificar(lexema, coluna, apelidos)
        if isinstance(resultado, ErroDeAnalise):
            erros.append(resultado)
            tokens.append(Token(ERRO, lexema, coluna, resultado))
        else:
            tokens.append(resultado)
        i = j
    tokens.append(Token(FIM, "", n + 1))
    return tokens, erros


def analisar_lexico(texto, apelidos=None):
    """A fase léxica: os tokens, ou ErroDeAnalise no primeiro erro."""
    tokens, erros = tokenizar(texto, apelidos)
    if erros:
        raise min(erros, key=lambda e: e.coluna or 0)
    return tokens


# ------------------------------------------------------------------
# Privacidade: a linha mostrada ao porteiro (RN14)
# ------------------------------------------------------------------
# CPF formatado ou 11 dígitos: os 3 primeiros e os 2 últimos números viram
# "*" (o tamanho não muda, então o ^ do erro continua na coluna certa)
_CPF_NA_LINHA = re.compile(r"(?<!\d)(\d{3})(\.?\d{3}\.?\d{3}-?)(\d{2})(?!\d)")


def mascarar_lexema(lexema):
    """'529.982.247-25' -> '***.982.247-**'; '52998224725' -> '***982247**'."""
    return _CPF_NA_LINHA.sub(lambda m: "***" + m.group(2) + "**", lexema)


def eh_celular(tokens, i):
    """O NUMERO da posição i vem depois de "cel" (é celular, não CPF)?"""
    return (i > 0 and tokens[i - 1].tipo == PALAVRA_CHAVE
            and tokens[i - 1].valor == "cel")


def mascarar_linha(texto, tokens=None):
    """A linha com os CPFs mascarados, do mesmo tamanho (o celular, que
    vem depois de "cel", fica como está)."""
    if tokens is None:
        tokens, _ = tokenizar(texto)
    letras = list(texto)
    for i, t in enumerate(tokens):
        if t.tipo == FIM or eh_celular(tokens, i):
            continue
        novo = mascarar_lexema(t.lexema)
        letras[t.coluna - 1:t.fim - 1] = novo
    return "".join(letras)
