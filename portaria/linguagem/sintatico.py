"""
Análise SINTÁTICA: os tokens viram uma árvore (descida recursiva).

Cada regra da gramática (gramatica.EBNF) tem um método _<regra>() que
consome os tokens dela e devolve o nó da árvore (dataclasses abaixo, ex.:
ComandoEntrada(comando, cpf, tipo, opcoes)). Para escolher o caminho
basta olhar o token atual (um à frente): a gramática é LL(1), porque cada
comando começa com uma palavra diferente e cada opção também (os
conjuntos FIRST são disjuntos; gramatica.conflitos_ll1 confere).

O sintático NÃO consulta o banco: "entrada 12345678900 aluno" é uma
frase bem escrita (o CPF inválido é problema do semântico). Ele recusa a
ordem errada ("visitante entrada ..."), o que falta ("saida placa" e o
fim da linha) e o que sobra, com a coluna e uma dica. Comando
desconhecido recebe o "você quis dizer…?" (difflib), como na Lanchonete.
"""

import difflib
from dataclasses import dataclass, field, fields

from .erros import SINTATICO, ErroDeAnalise
from .gramatica import EXEMPLOS
from .lexico import (COMANDO, COMANDOS, CPF, DATA, FIM, HORA, NUMERO,
                     PALAVRA, PALAVRA_CHAVE, PERIODO, PLACA, TEXTO, TIPO,
                     Token)


# ------------------------------------------------------------------
# A árvore
# ------------------------------------------------------------------
@dataclass
class Opcao:
    """Uma opção: a palavra ("placa", "sem", "as"...) e os valores."""
    palavra: Token
    valores: list = field(default_factory=list)

    @property
    def nome(self):
        return "sem carro" if self.palavra.valor == "sem" else self.palavra.valor

    @property
    def valor(self):
        """O token do valor (o último: "em DATA HORA" tem dois)."""
        return self.valores[-1] if self.valores else None


@dataclass
class Alvo:
    """De quem é o comando: um CPF, ou "placa" PLACA."""
    valor: Token
    palavra: Token = None

    @property
    def eh_placa(self):
        return self.valor.tipo == PLACA


@dataclass
class Periodo:
    """hoje | ontem | semana | mes, ou "de" DATA [ "ate" DATA ]."""
    palavra: Token
    inicio: Token = None
    ate: Token = None
    fim: Token = None


@dataclass
class Comando:
    comando: Token                    # a palavra do comando


@dataclass
class ComandoEntrada(Comando):
    cpf: Token = None
    tipo: Token = None
    opcoes: list = field(default_factory=list)


@dataclass
class ComandoSaida(Comando):
    alvo: Alvo = None
    opcoes: list = field(default_factory=list)


@dataclass
class ComandoImplicito(Comando):
    """Só o CPF ou só a placa: é uma saída (a Saída rápida de antes)."""
    alvo: Alvo = None


@dataclass
class ComandoCadastrar(Comando):
    cpf: Token = None
    tipo: Token = None
    opcoes: list = field(default_factory=list)   # nome, cel e [placa]


@dataclass
class ComandoEditar(Comando):
    cpf: Token = None
    campos: list = field(default_factory=list)


@dataclass
class ComandoExcluir(Comando):
    cpf: Token = None


@dataclass
class ComandoDesativar(Comando):
    alvo: Alvo = None
    motivo: Opcao = None


@dataclass
class ComandoReativar(Comando):
    alvo: Alvo = None


@dataclass
class ComandoSituacao(Comando):
    alvo: Alvo = None


@dataclass
class ComandoDentro(Comando):
    tipo: Token = None


@dataclass
class ComandoBuscar(Comando):
    termo: Token = None
    tipo: Token = None
    periodo: Periodo = None


@dataclass
class ComandoPendentes(Comando):
    pass


@dataclass
class ComandoAjuda(Comando):
    sobre: Token = None


# ------------------------------------------------------------------
# Mensagens
# ------------------------------------------------------------------
OPCOES_ENTRADA = ("placa", "sem", "nome", "cel", "as", "em")
OPCOES_SAIDA = ("placa", "sem", "as")
CAMPOS = ("nome", "cel", "placa", "tipo")
LISTA_COMANDOS = "entrada, saida, buscar…"


def descrever(token):
    """Como o token aparece na mensagem de erro. Número longo não é
    repetido (pode ser um CPF: a mensagem não o expõe)."""
    lx = token.lexema
    if token.tipo == FIM:
        return "o fim da linha"
    if token.tipo == NUMERO:
        return (f"um número de {len(lx)} dígitos" if len(lx) >= 9
                else f'o número "{lx}"')
    return {COMANDO: f'o comando "{lx}"', PALAVRA_CHAVE: f'a palavra "{lx}"',
            TIPO: f'o tipo "{lx}"', CPF: "um CPF", PLACA: f'a placa "{lx}"',
            DATA: f'a data "{lx}"', HORA: f'a hora "{lx}"',
            PERIODO: f'o período "{lx}"', TEXTO: "um texto entre aspas",
            PALAVRA: f'a palavra "{lx}"'}.get(token.tipo, f'"{lx}"')


def exemplo(comando):
    """O primeiro exemplo do comando (gramatica.EXEMPLOS)."""
    return EXEMPLOS[comando].split(" · ")[0]


def sugerir_comando(palavra):
    """O comando mais parecido (difflib), ou ''."""
    parecidos = difflib.get_close_matches(palavra, COMANDOS, n=1, cutoff=0.6)
    return parecidos[0] if parecidos else ""


# ------------------------------------------------------------------
# O analisador (uma função por regra da EBNF)
# ------------------------------------------------------------------
class AnalisadorSintatico:
    def __init__(self, tokens):
        self.tokens, self.i = tokens, 0
        # o que poderia vir no lugar do token que sobrou no fim
        self.esperado = "o fim da linha"

    # --- utilitários ----------------------------------------------
    @property
    def atual(self):
        return self.tokens[self.i]

    def _avancar(self):
        token = self.atual
        if token.tipo != FIM:
            self.i += 1
        return token

    def _eh(self, *palavras):
        """O token atual é uma das palavras da linguagem?"""
        t = self.atual
        return t.tipo in (COMANDO, PALAVRA_CHAVE) and t.valor in palavras

    def _erro(self, mensagem, dica="", sugestao="", token=None):
        t = token or self.atual
        return ErroDeAnalise(SINTATICO, mensagem, t.coluna,
                             max(1, len(t.lexema)), dica, sugestao,
                             fim_da_linha=t.tipo == FIM)

    def _esperar(self, tipo, depois, dica=""):
        """Consome um token do `tipo` que vem depois da palavra `depois`."""
        if self.atual.tipo == tipo:
            return self._avancar()
        nomes = {PLACA: "a PLACA", TEXTO: "um TEXTO entre aspas",
                 NUMERO: "um NÚMERO", HORA: "uma HORA (hh:mm)",
                 DATA: "uma DATA (dd/mm/aaaa)", TIPO: "o TIPO de acesso"}
        if self.atual.tipo == FIM:
            raise self._erro(f'esperado {nomes[tipo]} depois de "{depois}", '
                             "mas o comando acabou.", dica)
        raise self._erro(f'esperado {nomes[tipo]} depois de "{depois}"; '
                         f"encontrado {descrever(self.atual)}.", dica)

    def _palavra(self, palavra, dica=""):
        """Consome a palavra da linguagem `palavra` (ex.: "motivo")."""
        if self._eh(palavra):
            return self._avancar()
        if self.atual.tipo == FIM:
            raise self._erro(f'esperado "{palavra}", mas o comando acabou.',
                             dica)
        antes = ("antes do texto" if self.atual.tipo == TEXTO
                 else f"no lugar de {descrever(self.atual)}")
        raise self._erro(f'esperado "{palavra}" {antes}.', dica)

    # --- linha e comando ------------------------------------------
    def linha(self):
        """linha = comando FIM ;"""
        arvore = self._comando()
        if self.atual.tipo != FIM:
            raise self._erro(f"sobrou {descrever(self.atual)} depois do "
                             f"comando; esperado {self.esperado}.")
        return arvore

    def _comando(self):
        """comando = entrada | saida | implicito | ... | ajuda ;
        A escolha é pelo primeiro token (FIRST de cada alternativa)."""
        t = self.atual
        if t.tipo == COMANDO:
            return getattr(self, "_" + t.valor)()
        if t.tipo in (CPF, NUMERO, PLACA):         # FIRST(implicito)
            return self._implicito()
        if t.tipo == FIM:
            raise self._erro("a linha está vazia.",
                             "digite só o CPF ou a placa para dar a saída, "
                             'ou um comando (ex.: "ajuda").')
        if t.tipo == PALAVRA:
            sugestao = sugerir_comando(t.valor)
            raise self._erro(f'comando desconhecido "{t.lexema}".',
                             "" if sugestao else
                             f"comandos: {', '.join(COMANDOS)}.",
                             sugestao=sugestao)
        depois = next((x for x in self.tokens[self.i:] if x.tipo == COMANDO),
                      None)
        dica = ("o comando vem primeiro: " + exemplo(depois.valor)
                if depois else 'o comando vem primeiro (ex.: "ajuda").')
        raise self._erro(f"esperado um comando ({LISTA_COMANDOS}), "
                         f"encontrado {descrever(t)}.", dica)

    # --- os comandos ----------------------------------------------
    def _entrada(self):
        """entrada = "entrada" cpf [ TIPO ] { opcao_ent } ;"""
        comando = self._avancar()
        cpf = self._cpf("entrada")
        tipo = self._avancar() if self.atual.tipo == TIPO else None
        opcoes = []
        while self._eh(*OPCOES_ENTRADA):
            opcoes.append(self._opcao_ent())
        self.esperado = ("uma opção (placa, sem carro, nome, cel, as, em) "
                         "ou o fim da linha" + ("" if tipo or opcoes else
                                                ", ou o tipo"))
        return ComandoEntrada(comando, cpf, tipo, opcoes)

    def _opcao_ent(self):
        """opcao_ent = "placa" PLACA | "sem" "carro" | "nome" TEXTO
                     | "cel" NUMERO | "as" HORA | "em" DATA HORA ;"""
        palavra = self.atual.valor
        if palavra == "nome":
            p = self._avancar()
            return Opcao(p, [self._esperar(TEXTO, "nome",
                                           'o nome vai entre aspas: nome '
                                           '"Bruno Almeida".')])
        if palavra == "cel":
            p = self._avancar()
            return Opcao(p, [self._esperar(NUMERO, "cel",
                                           "só os números, com o DDD "
                                           "(ex.: cel 31987651234).")])
        if palavra == "em":
            p = self._avancar()
            data = self._esperar(DATA, "em", "ex.: em 18/10/2026 08:00.")
            return Opcao(p, [data, self._esperar(HORA, data.lexema,
                                                 "ex.: em 18/10/2026 08:00.")])
        return self._opcao_comum()

    def _opcao_comum(self):
        """As opções que entrada e saída têm iguais: "placa" PLACA,
        "sem" "carro" e "as" HORA."""
        palavra = self._avancar()
        if palavra.valor == "placa":
            return Opcao(palavra, [self._esperar(PLACA, "placa",
                                                 "ex.: placa ABC1D23.")])
        if palavra.valor == "sem":
            return Opcao(palavra, [self._palavra("carro",
                                                 'a pé se escreve "sem '
                                                 'carro".')])
        return Opcao(palavra, [self._esperar(HORA, "as", "ex.: as 14:05.")])

    def _saida(self):
        """saida = "saida" alvo { opcao_sai } ;"""
        comando = self._avancar()
        alvo = self._alvo("saida")
        opcoes = []
        while self._eh(*OPCOES_SAIDA):
            opcoes.append(self._opcao_sai())
        self.esperado = "uma opção (placa, sem carro, as) ou o fim da linha"
        return ComandoSaida(comando, alvo, opcoes)

    def _opcao_sai(self):
        """opcao_sai = "placa" PLACA | "sem" "carro" | "as" HORA ;"""
        return self._opcao_comum()

    def _implicito(self):
        """implicito = cpf | PLACA ;   (* = saida *)"""
        valor = self._avancar()
        self.esperado = ('o fim da linha (só o CPF ou só a placa dão a '
                         'saída; para mais, use "saida ...")')
        return ComandoImplicito(None, Alvo(valor))

    def _cadastrar(self):
        """cadastrar = "cadastrar" cpf TIPO "nome" TEXTO "cel" NUMERO
                       [ "placa" PLACA ] ;"""
        comando = self._avancar()
        ex = "Ex.: " + exemplo("cadastrar")
        cpf = self._cpf("cadastrar")
        tipo = self._esperar(TIPO, "o CPF", ex)
        opcoes = [Opcao(self._palavra("nome", ex),
                        [self._esperar(TEXTO, "nome", ex)]),
                  Opcao(self._palavra("cel", ex),
                        [self._esperar(NUMERO, "cel", ex)])]
        if self._eh("placa"):
            p = self._avancar()
            opcoes.append(Opcao(p, [self._esperar(PLACA, "placa")]))
        self.esperado = '"placa" ou o fim da linha'
        return ComandoCadastrar(comando, cpf, tipo, opcoes)

    def _editar(self):
        """editar = "editar" cpf campo { campo } ;"""
        comando = self._avancar()
        cpf = self._cpf("editar")
        campos = [self._campo()]
        while self._eh(*CAMPOS):
            campos.append(self._campo())
        self.esperado = "o que muda (nome, cel, placa, tipo) ou o fim da linha"
        return ComandoEditar(comando, cpf, campos)

    def _campo(self):
        """campo = "nome" TEXTO | "cel" NUMERO | "placa" PLACA
                 | "tipo" TIPO ;"""
        if not self._eh(*CAMPOS):
            raise self._erro("esperado o que muda (nome, cel, placa ou "
                             f"tipo); encontrado {descrever(self.atual)}.",
                             "Ex.: " + exemplo("editar"))
        palavra = self._avancar()
        tipo = {"nome": TEXTO, "cel": NUMERO, "placa": PLACA,
                "tipo": TIPO}[palavra.valor]
        dica = ('o nome vai entre aspas: nome "Bruno Almeida".'
                if tipo == TEXTO else "")
        return Opcao(palavra, [self._esperar(tipo, palavra.lexema, dica)])

    def _excluir(self):
        """excluir = "excluir" cpf ;"""
        comando = self._avancar()
        return ComandoExcluir(comando, self._cpf("excluir"))

    def _desativar(self):
        """desativar = "desativar" alvo "motivo" TEXTO ;"""
        comando = self._avancar()
        alvo = self._alvo("desativar")
        ex = "Ex.: " + exemplo("desativar")
        palavra = self._palavra("motivo", ex)
        motivo = Opcao(palavra, [self._esperar(TEXTO, "motivo", ex)])
        return ComandoDesativar(comando, alvo, motivo)

    def _reativar(self):
        """reativar = "reativar" alvo ;"""
        comando = self._avancar()
        return ComandoReativar(comando, self._alvo("reativar"))

    def _situacao(self):
        """situacao = "situacao" alvo ;"""
        comando = self._avancar()
        return ComandoSituacao(comando, self._alvo("situacao"))

    def _dentro(self):
        """dentro = "dentro" [ TIPO ] ;"""
        comando = self._avancar()
        tipo = self._avancar() if self.atual.tipo == TIPO else None
        self.esperado = "o fim da linha" + ("" if tipo else " ou o tipo")
        return ComandoDentro(comando, tipo)

    def _buscar(self):
        """buscar = "buscar" termo [ TIPO ] [ periodo ] ;"""
        comando = self._avancar()
        termo = self._termo()
        tipo = self._avancar() if self.atual.tipo == TIPO else None
        periodo = None
        if self.atual.tipo == PERIODO or self._eh("de"):   # FIRST(periodo)
            periodo = self._periodo()
        self.esperado = ("o tipo, o período (hoje, ontem, semana, mes, "
                         "de DATA) ou o fim da linha")
        return ComandoBuscar(comando, termo, tipo, periodo)

    def _termo(self):
        """termo = TEXTO | PALAVRA | cpf | PLACA ;"""
        if self.atual.tipo in (TEXTO, PALAVRA, CPF, NUMERO, PLACA):
            return self._avancar()
        if self.atual.tipo == FIM:
            raise self._erro('esperado o que buscar depois de "buscar", '
                             "mas o comando acabou.",
                             "Ex.: " + exemplo("buscar"))
        raise self._erro("esperado o que buscar (nome, CPF, placa ou texto "
                         f"entre aspas); encontrado {descrever(self.atual)}.",
                         'para buscar essa palavra, ponha entre aspas: '
                         f'buscar "{self.atual.lexema}".')

    def _periodo(self):
        """periodo = PERIODO | "de" DATA [ "ate" DATA ] ;"""
        if self.atual.tipo == PERIODO:
            return Periodo(self._avancar())
        palavra = self._avancar()                       # "de"
        inicio = self._esperar(DATA, "de", "ex.: de 01/10/2026 ate "
                                           "15/10/2026.")
        if self._eh("ate"):
            ate = self._avancar()
            return Periodo(palavra, inicio, ate,
                           self._esperar(DATA, "ate", "ex.: ate 15/10/2026."))
        return Periodo(palavra, inicio)

    def _pendentes(self):
        """pendentes = "pendentes" ;"""
        return ComandoPendentes(self._avancar())

    def _ajuda(self):
        """ajuda = "ajuda" [ COMANDO ] ;"""
        comando = self._avancar()
        sobre = self._avancar() if self.atual.tipo == COMANDO else None
        self.esperado = "o fim da linha" + ("" if sobre else
                                            " ou o nome de um comando")
        return ComandoAjuda(comando, sobre)

    # --- alvo e cpf -----------------------------------------------
    def _alvo(self, depois):
        """alvo = cpf | "placa" PLACA ;"""
        if self._eh("placa"):
            palavra = self._avancar()
            return Alvo(self._esperar(PLACA, "placa", "ex.: placa ABC1D23."),
                        palavra)
        if self.atual.tipo in (CPF, NUMERO):
            return Alvo(self._avancar())
        dica = ""
        if self.atual.tipo == PLACA:
            dica = f"para a placa, escreva: {depois} placa {self.atual.lexema}"
        elif depois in EXEMPLOS:
            dica = "Ex.: " + exemplo(depois)
        if self.atual.tipo == FIM:
            raise self._erro(f'esperado o CPF ou "placa PLACA" depois de '
                             f'"{depois}", mas o comando acabou.', dica)
        raise self._erro(f'depois de "{depois}" vem o CPF ou "placa PLACA"; '
                         f"encontrado {descrever(self.atual)}.", dica)

    def _cpf(self, depois):
        """cpf = CPF | NUMERO ;"""
        if self.atual.tipo in (CPF, NUMERO):
            return self._avancar()
        dica = "Ex.: " + exemplo(depois)
        if self.atual.tipo == FIM:
            raise self._erro(f'esperado o CPF depois de "{depois}", mas o '
                             "comando acabou.", dica)
        raise self._erro(f'depois de "{depois}" vem o CPF; encontrado '
                         f"{descrever(self.atual)}.", dica)


def analisar_sintatico(tokens):
    """A fase sintática: a árvore do comando ou ErroDeAnalise."""
    return AnalisadorSintatico(tokens).linha()


# ------------------------------------------------------------------
# A árvore para desenhar (modo didático e Word)
# ------------------------------------------------------------------
@dataclass
class NoVisual:
    rotulo: str                # "ComandoEntrada", "alvo", "529.982.247-25"
    legenda: str = ""          # o tipo do token ("CPF") ou o campo
    filhos: list = field(default_factory=list)
    inicio: int = 0            # colunas que o nó cobre na linha
    fim: int = 0
    folha: bool = False


def _no_token(token, campo=""):
    return NoVisual(token.lexema, token.tipo, [], token.coluna, token.fim,
                    folha=True)


def _no(valor, campo):
    """O nó de um campo da árvore (Token, Opcao, Alvo, Periodo, lista)."""
    if isinstance(valor, Token):
        if campo in ("comando",):
            return _no_token(valor)
        no = NoVisual(campo, "", [_no_token(valor)], valor.coluna, valor.fim)
        return no
    if isinstance(valor, Opcao):
        filhos = [_no_token(valor.palavra)] + [_no_token(v)
                                               for v in valor.valores]
        return NoVisual(f"opção {valor.nome}", "", filhos, filhos[0].inicio,
                        filhos[-1].fim)
    if isinstance(valor, Alvo):
        filhos = ([_no_token(valor.palavra)] if valor.palavra else []) + [
            _no_token(valor.valor)]
        return NoVisual("alvo", "", filhos, filhos[0].inicio, filhos[-1].fim)
    if isinstance(valor, Periodo):
        tokens = [t for t in (valor.palavra, valor.inicio, valor.ate,
                              valor.fim) if t is not None]
        filhos = [_no_token(t) for t in tokens]
        return NoVisual("período", "", filhos, filhos[0].inicio,
                        filhos[-1].fim)
    return None


def arvore_visual(comando):
    """A árvore em NoVisual: a raiz é a classe (ex.: ComandoEntrada), os
    filhos são os campos na ordem da regra."""
    filhos = []
    for f in fields(comando):
        valor = getattr(comando, f.name)
        itens = valor if isinstance(valor, list) else [valor]
        for item in itens:
            if item is None:
                continue
            no = _no(item, f.name)
            if no is not None:
                filhos.append(no)
    inicio = min((n.inicio for n in filhos), default=1)
    fim = max((n.fim for n in filhos), default=1)
    return NoVisual(type(comando).__name__, "", filhos, inicio, fim)
