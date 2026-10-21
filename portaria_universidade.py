"""
Portaria da Universidade - Controle de entrada e saída
UC – Teoria da Computação e Compiladores | Faculdade UNA

Apenas bibliotecas padrão do Python (tkinter, sqlite3, ctypes, csv, logging...).
Os registros são salvos automaticamente no banco SQLite 'portaria.db'.
Se existir o 'registros_portaria.json' da versão 1, ele é importado para o
banco na primeira execução e renomeado para '.migrado' (fica de backup).
Ao abrir: backup do dia na pasta 'backups' e erros técnicos em 'portaria.log'.

Atalhos: ENTER registra a entrada (página Entrada e saída); F2 leva à
saída rápida de qualquer página.

Organização do código (pasta portaria/):
    validacao.py       regras de CPF, celular, placa, nome, datas e as
                       verificações semânticas
    horarios.py        regras de horário de acesso (funcionamento, feriados,
                       eventos, categorias, exceções, situação da visita)
    dados.py           banco de dados SQLite e migração do JSON antigo
    consultas.py       busca e números do Painel (versão em Python)
    usuarios.py        senhas (hash), perfis, permissões, login e troca de senha
    backup.py          backup do banco e exportação para CSV
    estilo.py          tokens do design "Guarita": cores, fontes, ícones,
                       medidas, escala da tela (DPI) e estilos ttk
    componentes.py     peças de tela desenhadas: cartão, botões, campo,
                       faixa de aviso, placa Mercosul, tabela, diálogo
    mensagens.py       caixas de mensagem e "Salvar como"
    interface.py       janela, barra lateral, sessão e o contrato do app
    tela_login.py      login e primeiro acesso
    tela_cadastro.py   Entrada e saída (formulário, saída rápida, Movimento)
    tela_pessoas.py    Pessoas (lista e ficha)
    tela_bloqueios.py  Bloqueios (CPFs e placas barrados)
    tela_dashboard.py  Painel e exportação; graficos.py desenha as barras
    tela_usuarios.py   Usuários (só administrador)
    tela_configuracoes.py  Configurações dos horários (só administrador)
    tela_edicao.py     janela "Corrigir registro"
    tela_autorizacao.py  diálogo "Autorização do administrador"
    tela_veiculo.py    perguntas "Saiu com o veículo?" e "Saiu junto?"
    seletor_data.py    calendário e relógio dos campos de data e hora
    tela_senha.py      janela "Trocar minha senha"
Testes automatizados: python -m unittest
"""

import os
import sys

from portaria.dados import configurar_log
from portaria.estilo import ligar_nitidez
from portaria.interface import AppPortaria, ajustar_ao_monitor


def pasta_do_programa():
    # No .exe (PyInstaller) os dados ficam ao lado do executável
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BANCO = os.path.join(pasta_do_programa(), "portaria.db")
JSON_ANTIGO = os.path.join(pasta_do_programa(), "registros_portaria.json")
LOG = os.path.join(pasta_do_programa(), "portaria.log")   # erros técnicos

if __name__ == "__main__":
    configurar_log(LOG)    # detalhes técnicos dos erros (o usuário vê o simples)
    ligar_nitidez()        # texto nítido com escala de tela 125%/150% (DPI)
    app = AppPortaria(BANCO, json_antigo=JSON_ANTIGO)
    ajustar_ao_monitor(app.janela)
    app.executar()


# ==================================================================
# RELAÇÃO COM COMPILADORES (desafio final do exercício)
# ==================================================================
# 1) TOKEN (análise léxica)
#    Em portaria/tela_cadastro.py (AbaCadastro._montar_formulario), na linha:
#        self.var_cpf = tk.StringVar(self.aba)
#    Tokens: self (identificador), . (ponto), var_cpf (identificador),
#    = (operador de atribuição), tk (identificador), . (ponto),
#    StringVar (identificador), ( (abre parênteses), self . aba,
#    ) (fecha parênteses).
#    E na linha logo abaixo, com literais string e inteiro e argumento nomeado:
#        self.cpf = self._peca("cpf", "CPF", Campo(form, numeros=11, var=self.var_cpf))
#    Tokens: self . cpf, = , self . _peca, (, "cpf" e "CPF" (literais
#    string), ",", Campo, (, form, ",", numeros (identificador), = (sinal do
#    argumento nomeado), 11 (literal inteiro), ",", var, =, self . var_cpf,
#    ), ).
#    Outro, com literal string, em portaria/validacao.py:
#        FORMATO = "%d/%m/%Y %H:%M"            # usado pelo datetime
#    Tokens: FORMATO (identificador), = (operador de atribuição),
#    "%d/%m/%Y %H:%M" (literal string); o comentário (# ...) é descartado
#    pelo analisador léxico e não vira token.
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
#    Com as regras de horário, em horarios.excecoes_da_entrada() (chamada
#    por tela_cadastro.AbaCadastro.cadastrar, "VERIFICAÇÃO SEMÂNTICA 6"):
#    a entrada "Aluno, 25/10/2026 10:00" é sintaticamente válida (a data
#    existe, está no formato dd/mm/aaaa hh:mm, não está no futuro), mas não
#    faz sentido para um aluno num domingo, com o campus fechado. O mesmo
#    vale para um visitante às 19:00 (janela 08:00–18:00) ou uma visita de
#    30 h (horarios.excecoes_da_duracao). Como um compilador que recusa
#    "int x = 'texto';" mesmo com a sintaxe certa, o sistema não grava: pede
#    a autorização do administrador (tela_autorizacao.py), e o banco confere
#    de novo o limite de 24 h (dados.Banco._exigir_autorizacao_24h).
#    O mesmo vale para o lançamento retroativo (horarios.retroativo): a
#    entrada "20/10/2026 22:00" digitada às 23:10 é uma data bem escrita, mas
#    o dia dela já fechou; o significado depende do CONTEXTO (o relógio), não
#    da forma, e por isso só passa com a senha de um administrador. E a placa
#    "ABC1234" é válida (léxico e sintaxe), mas não faz sentido entrar de novo
#    se o carro já está no estacionamento (dados.Banco._abrir_estadia): é a
#    verificação de "símbolo já declarado", só que com carros.
