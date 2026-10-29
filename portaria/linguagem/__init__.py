"""
Linguagem de comandos da portaria (versão 2.4): o campo Comando (F2 ou
Ctrl+K) da página Entrada e saída.

Um comando passa pelas fases de um compilador, cada uma num módulo:

    lexico.py      texto -> tokens (com a coluna de cada um)
    sintatico.py   tokens -> árvore (descida recursiva, gramática LL(1))
    semantico.py   árvore + tabela de símbolos (simbolos.py) -> checagens
    executor.py    grava pelos MESMOS caminhos do formulário

A gramática (EBNF) fica em gramatica.py, que também confere que ela é
LL(1) e gera o texto do comando `ajuda`. erros.py formata os erros de
todas as fases do mesmo jeito: a linha, o ^ na coluna, a fase e a dica.

Regra de ouro (docs/GRAMATICA_DA_LINGUAGEM.md): o comando é só outra porta
de entrada. Ele monta o mesmo registro que o formulário monta e passa
pelas mesmas funções (validacao, horarios, Banco e as RN01 a RN45).
analisar() junta as três primeiras fases; nada aqui grava no banco.
"""

from .erros import (EXECUCAO, FASES, LEXICO, SEMANTICO, SINTATICO,
                    ErroDeAnalise, formatar_erro)
from .lexico import analisar_lexico, tokenizar
from .sintatico import analisar_sintatico

__all__ = ["EXECUCAO", "FASES", "LEXICO", "SEMANTICO", "SINTATICO",
           "ErroDeAnalise", "formatar_erro", "analisar_lexico", "tokenizar",
           "analisar_sintatico"]
