"""
Portaria da Universidade - Controle de entrada e saída
UC – Teoria da Computação e Compiladores | Faculdade UNA

Apenas bibliotecas padrão do Python (tkinter, sqlite3, datetime, json, os, re).
Os registros são salvos automaticamente no banco SQLite 'portaria.db'.
Se existir o 'registros_portaria.json' da versão 1, ele é importado para o
banco na primeira execução e renomeado para '.migrado' (fica de backup).

Atalho: pressione ENTER para cadastrar (na aba Cadastro).
A aba Dashboard mostra estatísticas dos dados coletados.

Organização do código (pasta portaria/):
    validacao.py       regras de CPF, celular, placa, nome, datas e as
                       verificações semânticas
    dados.py           banco de dados SQLite e migração do JSON antigo
    consultas.py       busca na tabela e números do dashboard
    usuarios.py        senhas (hash), perfis, permissões e bloqueio de login
    estilo.py          cores e fontes com nome (tokens) e o tema ttk
    componentes.py     peças de tela: campos, tabelas, botões, cartões
    mensagens.py       caixas de mensagem (erro, aviso, confirmação)
    interface.py       janela principal, sessão, abas e o contrato do app
    tela_login.py      login e primeiro acesso
    tela_cadastro.py   aba Cadastro (entrada, saída, busca e tabela)
    tela_pessoas.py    aba Pessoas
    tela_bloqueios.py  aba Bloqueios (lista de CPFs e placas barrados)
    tela_dashboard.py  aba Dashboard; graficos.py desenha as barras
    tela_usuarios.py   aba Usuários (só administrador)
    tela_edicao.py     janela "Corrigir registro"
Testes automatizados: python -m unittest
"""

import os
import sys

from portaria.interface import AppPortaria


def pasta_do_programa():
    # No .exe (PyInstaller) os dados ficam ao lado do executável
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BANCO = os.path.join(pasta_do_programa(), "portaria.db")
JSON_ANTIGO = os.path.join(pasta_do_programa(), "registros_portaria.json")

if __name__ == "__main__":
    AppPortaria(BANCO, json_antigo=JSON_ANTIGO).executar()


# ==================================================================
# RELAÇÃO COM COMPILADORES (desafio final do exercício)
# ==================================================================
# 1) TOKEN (análise léxica)
#    Em portaria/tela_cadastro.py (AbaCadastro._montar_formulario), na linha:
#        self.cpf = entrada_numeros(form, 11, textvariable=self.var_cpf)
#    Tokens: self (identificador), . (ponto), cpf (identificador),
#    = (operador de atribuição), entrada_numeros (identificador),
#    ( (abre parênteses), form (identificador), , (vírgula),
#    11 (literal inteiro), textvariable (identificador), = (sinal do
#    argumento nomeado), self . var_cpf, ) (fecha parênteses).
#    Outro, com literal string, em portaria/estilo.py:
#        FAMILIA = "Segoe UI"
#    Tokens: FAMILIA (identificador), = (operador), "Segoe UI" (literal string).
#
# 2) VARIÁVEL DA TABELA DE SÍMBOLOS
#    Símbolo: BANCO | Tipo: str | Valor: caminho do portaria.db | Escopo: global
#    (também, em validacao.py: FORMATO -> str, TIPOS_ACESSO -> list,
#     DDDS_VALIDOS -> set, REGEX_PLACA -> re.Pattern;
#     em estilo.py: COR -> dict, FONTE -> dict;
#     em interface.py: self.registros -> list, atributo da AppPortaria)
#
# 3) VERIFICAÇÃO SEMÂNTICA
#    Em validacao.validar(): o código está sintaticamente correto, mas só faz
#    sentido se:  saida_dt < entrada_dt  for falso (saída não anterior à
#    entrada); a entrada não estiver no futuro; o CPF passar nos dígitos
#    verificadores; o celular tiver o 9 após o DDD; o nome tiver só letras;
#    e o mesmo CPF não estiver no campus duas vezes ao mesmo tempo
#    (entrada aberta ou períodos que se cruzam).
#    Em validacao.checar_bloqueio(): o registro pode estar perfeito, mas a
#    entrada não faz sentido se o CPF ou a placa estiverem bloqueados (RN12).
#    Outro exemplo, em tela_cadastro.AbaCadastro.excluir_selecionado(): a
#    chamada self.app.gravar(self.app.banco.excluir, ...) é válida, mas só
#    faz sentido se usuarios.pode_excluir(self.app.usuario) for verdadeiro
#    (RN02).
