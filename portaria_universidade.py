"""
Portaria da Universidade - Controle de entrada e saída
UC – Teoria da Computação e Compiladores | Faculdade UNA

Apenas bibliotecas padrão do Python (tkinter, sqlite3, ctypes, csv, logging...).
Os registros são salvos automaticamente no banco SQLite 'portaria.db'.
Se existir o 'registros_portaria.json' da versão 1, ele é importado para o
banco na primeira execução e renomeado para '.migrado' (fica de backup).
Ao abrir: backup do dia na pasta 'backups' e erros técnicos em 'portaria.log'.

Atalhos: ENTER registra a entrada (página Entrada e saída); F2 ou Ctrl+K
levam ao campo Comando (a linguagem da portaria, versão 2.4; só o CPF ou
só a placa continuam dando a saída, como a antiga Saída rápida).

Organização do código (pasta portaria/):
    validacao.py       regras de CPF, celular, placa, nome, datas e as
                       verificações semânticas
    horarios.py        regras de horário de acesso (funcionamento, feriados,
                       eventos, categorias, exceções, situação da visita)
    dados.py           banco de dados SQLite e migração do JSON antigo
    consultas.py       busca e números do Painel (versão em Python)
    usuarios.py        perfis, permissões, login e troca de senha
    senhas.py          hash das senhas (PBKDF2) e códigos de recuperação
    veiculos.py        quem pode retirar o carro e lotação (funções puras)
    backup.py          backup do banco e exportação para CSV
    linguagem/         a linguagem de comandos (2.4): lexico.py (tokens),
                       gramatica.py (EBNF e conferência LL(1)),
                       sintatico.py (árvore), simbolos.py (tabela de
                       símbolos), semantico.py (checagens com as RN),
                       executor.py (grava pelos caminhos do formulário)
    estilo.py          tokens do design "Guarita": cores, fontes, ícones,
                       medidas, escala da tela (DPI) e estilos ttk
    componentes.py     peças de tela desenhadas: cartão, botões, campo,
                       faixa de aviso, placa, tabela, diálogo
    mensagens.py       caixas de mensagem e "Salvar como"
    interface.py       janela, barra lateral, sessão e o contrato do app
    tela_login.py      login, primeiro acesso e recuperação da senha
    tela_cadastro.py   Entrada e saída (formulário, Movimento)
    tela_comando.py    campo Comando, console e modo didático (2.4)
    tela_pessoas.py    Pessoas (lista, ficha, desativação, Nova pessoa)
    tela_dashboard.py  Painel e exportação; graficos.py desenha as barras
    tela_usuarios.py   Usuários e exceções (só administrador)
    tela_configuracoes.py  Configurações dos horários (só administrador)
    tela_edicao.py     janela "Corrigir registro"
    tela_autorizacao.py  diálogo "Autorização do administrador"
    tela_veiculo.py    perguntas do carro ("Saiu com o veículo?"...)
    seletor_data.py    calendário e relógio dos campos de data e hora
    tela_senha.py      janela "Trocar minha senha"
Testes automatizados: python -m unittest
"""

import os

from portaria.caminhos import pasta_de_dados
from portaria.dados import configurar_log
from portaria.estilo import ligar_nitidez
from portaria.interface import AppPortaria, ajustar_ao_monitor

# Instalado: C:\ProgramData\Portaria; portátil ou pelo código: ao lado do
# programa (veja portaria/caminhos.py)
DADOS = pasta_de_dados()
BANCO = os.path.join(DADOS, "portaria.db")
JSON_ANTIGO = os.path.join(DADOS, "registros_portaria.json")
LOG = os.path.join(DADOS, "portaria.log")   # erros técnicos

if __name__ == "__main__":
    configurar_log(LOG)    # detalhes técnicos dos erros (o usuário vê o simples)
    ligar_nitidez()        # texto nítido com escala de tela 125%/150% (DPI)
    app = AppPortaria(BANCO, json_antigo=JSON_ANTIGO)
    ajustar_ao_monitor(app.janela)
    app.executar()


# ==================================================================
# RELAÇÃO COM COMPILADORES (desafio final do exercício)
# ==================================================================
# Desde a versão 2.4 o sistema TEM um compilador de verdade: a linguagem
# de comandos do campo Comando (F2 ou Ctrl+K), em portaria/linguagem/. A
# gramática está em docs/GRAMATICA_DA_LINGUAGEM.md (EBNF, LL(1)) e o modo
# didático mostra as fases na tela. As linhas citadas abaixo são conferidas
# por um teste (tests/test_linguagem.py, TestComentarioDeCompiladores).
#
# 1) TOKEN (análise léxica)
#    O token é um objeto com tipo, lexema, coluna e valor, em
#    portaria/linguagem/lexico.py, linha 128:
#        class Token:
#    e o analisador léxico cria um token PLACA (depois que o autômato
#    finito da placa, TRANSICOES_PLACA, aceita o lexema) em
#    portaria/linguagem/lexico.py, linha 236:
#        return Token(PLACA, lexema, coluna,
#    Para o comando "saida placa ABC1D23" os tokens são:
#        COMANDO "saida" (coluna 1), PALAVRA_CHAVE "placa" (coluna 7),
#        PLACA "ABC1D23" (coluna 13) e FIM (coluna 20).
#    "52998224725" é um NUMERO: o léxico não sabe se é CPF ou celular;
#    quem decide é o sintático, pela posição (depois de "entrada" é CPF,
#    depois de "cel" é celular). Erro léxico: "AB12345 não é uma placa",
#    com o ^ na coluna. (No próprio Python, a linha acima tem os tokens
#    return (palavra reservada), Token (identificador), "(" , PLACA, ",",
#    lexema, ",", coluna, "," ...: o mesmo tipo de análise.)
#
# 2) VARIÁVEL DA TABELA DE SÍMBOLOS
#    A tabela de símbolos do semântico (portaria/linguagem/simbolos.py)
#    diz o que cada "nome" do comando significa no banco. O símbolo da
#    pessoa é registrado em
#    portaria/linguagem/simbolos.py, linha 83:
#        self._anotar("Pessoa", chave,
#    Exemplo (aba Símbolos do modo didático):
#        Categoria: Pessoa | Símbolo: CPF 529.982.247-25 |
#        Valor: Ana Silva · Visitante · no campus desde 08:00
#    O usuário logado também é um símbolo (Usuário: paulo · Porteiro),
#    como a placa (Veículo: no estacionamento desde 08:20) e o dia (Hoje:
#    quarta-feira, 06:30–23:00). No Python deste arquivo: Símbolo BANCO |
#    Tipo: str | Valor: caminho do portaria.db | Escopo: global.
#
# 3) VERIFICAÇÃO SEMÂNTICA
#    "entrada 39053344705" é léxica e sintaticamente correta, mas não faz
#    sentido se a pessoa já está no campus (RN05). O semântico recusa em
#    portaria/linguagem/semantico.py, linha 239:
#        self._exigir(False, "Não está no campus", "RN05",
#    e, com o registro montado como o formulário monta, chama a MESMA
#    validação do formulário (regra de ouro: nada de regra duplicada) em
#    portaria/linguagem/semantico.py, linha 260:
#        ok, msg = validar(registro, self.s.visitas(cpf), self.agora)
#    Outras checagens com a regra de cada uma: CPF com os dígitos
#    verificadores (RN06), pessoa ou placa desativada (RN12), opção dada
#    duas vezes ("variável declarada duas vezes"), tipo diferente do
#    cadastro (um AVISO, como uma conversão de tipo), comando de
#    administrador digitado pelo porteiro (RN02), horário da categoria e
#    lançamento retroativo (RN17, RN24: abrem a autorização do
#    administrador). No formulário, as mesmas regras estão em
#    validacao.validar() (VERIFICAÇÃO SEMÂNTICA 1 a 5) e em
#    horarios.excecoes_do_registro() (VERIFICAÇÃO SEMÂNTICA 6); o banco
#    confere de novo (dados.Banco.inserir).
