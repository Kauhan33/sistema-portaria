"""
As três fases de análise juntas (léxico -> sintático -> semântico).

analisar() devolve uma Analise com tudo o que o modo didático mostra: os
tokens, a árvore, as linhas da tabela de símbolos consultadas, as
checagens (com a RN de cada uma), em que fase parou e o erro. Se chegou
ao fim sem erro, `plano` diz o que o executor vai fazer. Nada é gravado
aqui (o semântico só consulta).

Privacidade (RN14): para o porteiro, `linha_exibida` e tudo o que passa
por mostrar() saem com o CPF mascarado, mesmo que ele tenha digitado o
número inteiro. O texto do comando não vai para o log nem para o banco.
"""

from dataclasses import dataclass, field

from ..usuarios import eh_admin
from ..validacao import mascarar_cpf
from .erros import (EXECUCAO, FASES, LEXICO, SEMANTICO, SINTATICO,
                    ErroDeAnalise, formatar_erro)
from .lexico import mascarar_lexema, mascarar_linha, tokenizar
from .semantico import AnalisadorSemantico
from .simbolos import TabelaDeSimbolos
from .sintatico import analisar_sintatico

# situação de cada fase na faixa do modo didático: ✓, ✗ ou —
PASSOU, FALHOU, NAO_RODOU = "passou", "falhou", "nao_rodou"


@dataclass
class Analise:
    linha: str
    privado: bool = True            # porteiro: CPF mascarado em tudo
    linha_exibida: str = ""
    tokens: list = field(default_factory=list)
    arvore: object = None
    simbolos: list = field(default_factory=list)
    checagens: list = field(default_factory=list)
    plano: object = None
    erro: ErroDeAnalise = None
    fases: dict = field(default_factory=lambda: dict.fromkeys(FASES,
                                                              NAO_RODOU))
    resposta: object = None         # executor.Resposta, depois de executar

    @property
    def parou_em(self):
        """A fase do erro (ou None se passou por todas as que rodaram)."""
        return self.erro.fase if self.erro else None

    def parar(self, erro):
        self.erro = erro
        self.fases[erro.fase] = FALHOU

    def mostrar(self, texto):
        """O texto como quem está logado pode ver (CPF mascarado para o
        porteiro; o tamanho não muda)."""
        return mascarar_lexema(texto) if self.privado else texto

    def linhas_do_erro(self):
        """O erro como o console mostra (linha, ^, fase e dica)."""
        if self.erro is None:
            return []
        return [self.mostrar(t) for t in formatar_erro(self.linha_exibida,
                                                       self.erro)]


def analisar_forma(texto, apelidos=None, privado=True):
    """Só léxico e sintático (sem o banco): o que o modo didático mostra
    enquanto se digita."""
    a = Analise(texto, privado)
    a.tokens, erros = tokenizar(texto, apelidos)
    a.linha_exibida = mascarar_linha(texto, a.tokens) if privado else texto
    if erros:
        a.parar(min(erros, key=lambda e: e.coluna or 0))
        return a
    a.fases[LEXICO] = PASSOU
    try:
        a.arvore = analisar_sintatico(a.tokens)
    except ErroDeAnalise as e:
        a.parar(e)
        return a
    a.fases[SINTATICO] = PASSOU
    return a


def analisar(texto, banco, usuario, agora, exibir_cpf=mascarar_cpf,
             apelidos=None):
    """As três fases. O semântico consulta o banco pela tabela de
    símbolos; a Analise volta com o plano (ou o erro)."""
    a = analisar_forma(texto, apelidos, privado=not eh_admin(usuario))
    if a.erro is not None:
        return a
    simbolos = TabelaDeSimbolos(banco, usuario, agora, exibir_cpf)
    semantico = AnalisadorSemantico(simbolos)
    try:
        a.plano = semantico.analisar(a.arvore)
        a.fases[SEMANTICO] = PASSOU
    except ErroDeAnalise as e:
        a.parar(e)
    finally:
        a.checagens = semantico.checagens
        a.simbolos = simbolos.linhas
    return a


def marcar_execucao(analise, resposta):
    """Depois do executor: a fase Execução passou (gravou ou respondeu) ou
    falhou (cancelada no diálogo ou recusada pelo banco)."""
    analise.resposta = resposta
    analise.fases[EXECUCAO] = (PASSOU if resposta.nivel in ("sucesso", "info")
                               else FALHOU)


__all__ = ["Analise", "analisar", "analisar_forma", "marcar_execucao",
           "PASSOU", "FALHOU", "NAO_RODOU", "mascarar_cpf"]
