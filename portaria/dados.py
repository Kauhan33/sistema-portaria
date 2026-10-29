"""
Banco de dados SQLite: pessoas, registros de acesso (visitas), usuários,
histórico de ações (auditoria), tentativas de login, desativações de
pessoas e veículos, configuração dos horários de acesso e migração do
antigo arquivo JSON.

Cada visita aponta para a pessoa (pessoa_id), mas guarda também uma cópia
dos dados daquele dia: se a pessoa trocar de celular, o histórico antigo
continua mostrando o que valia na data.

No banco as datas ficam em ISO ('2026-10-16 08:00'), que ordena e compara
certo em SQL; para o resto do sistema elas saem no formato da tela
('16/10/2026 08:00').

Permissões (`autor` = login de quem faz, conferido NO BANCO):
- operações sensíveis (excluir, corrigir, exportar, desativar e reativar
  pessoa ou veículo, excluir pessoa, criar, editar, ativar ou desativar
  usuário e definir senha) EXIGEM um autor existente, ativo e com o perfil
  certo (RN02, RN11, RN12, RN42 e gestão de usuários). Sem autor, recusam: é o caso da sessão que expirou com uma
  caixa de confirmação aberta. A única exceção é o primeiro acesso:
  criar_usuario sem autor só funciona com a tabela de usuários vazia;
- nas escritas do dia a dia (entrada, saída, desfazer saída, cadastrar e
  corrigir pessoa), o autor informado precisa existir e estar ativo (usuário
  desativado com a sessão aberta não continua operando). Sem autor elas
  são chamadas internas (importação do JSON antigo, testes) e não vão
  para o histórico.

Veículos (v8): o carro tem uma ESTADIA própria (estadias_veiculo), com
entrada e saída independentes da visita. A visita com placa abre a estadia
(o responsável é a pessoa dela); a pessoa pode sair a pé e deixar o carro,
voltar a pé (ou com outro carro) e depois sair com ele. Uma placa só tem
uma estadia aberta por vez (índice único). Excluir a visita de origem NÃO
tira do estacionamento o carro que ainda está lá (a estadia aberta só
perde a ligação com a visita); as encerradas vão junto (ON DELETE
CASCADE). Corrigir a placa, o CPF ou a entrada de uma visita aberta
corrige a estadia aberta por ela.

QUEM PODE RETIRAR O VEÍCULO (RN35, v11): a lista autorizados_veiculo
diz, por placa, quem leva o carro sem o dono e sem senha (ativo, na
validade, no campus a pé e não desativado: veiculos.pode_levar); o
carro sai junto com a saída dessa pessoa, com o evento "Veículo saiu com
autorizado". O porteiro só cadastra com o dono no campus (conferido aqui).

O VEÍCULO SÓ SAI COM O DONO (RN32): o dono é o responsável da estadia.
Uma estadia só é fechada junto com a saída do dono, na mesma transação
(registrar_saidas com o carro dele). Fechar a estadia sem o dono — só o
carro sai pela placa, outra pessoa sai com ele, ou a correção da visita
apaga/troca a placa ou o dono de um carro que ficou — exige
`autorizacao_veiculo` de um administrador ativo, dada COM a senha, e grava
o evento "Veículo saiu sem o dono" na mesma transação.

A SENHA DO ADMINISTRADOR É CONFERIDA AQUI (V0): a autorização que exige
senha leva {"autorizado_por": login, "senha": ...}; o Banco recalcula o
PBKDF2 (usuarios.conferir_autorizador, com o contador de senhas erradas da
estação, RN31) antes de gravar. A marca "com_senha" vinda de fora é
ignorada: só o Banco a põe, depois de conferir. A autorização de OUTRO
usuário (não o operador) também só vale com a senha dele. A senha nunca vai
para o histórico nem para o log.

Tamanho dos textos: os métodos que gravam recusam (ErroDados) texto acima
dos máximos de validacao.py (MAXIMO_*), sem mudar o esquema.

DESATIVAÇÃO (RN12, 2.3): desativar uma pessoa é desativar o CPF dela;
desativar um veículo, a placa. Fica na tabela `bloqueios` da v5 (uma
desativação = um bloqueio ativo; reativar = encerrá-lo, guardando quem e
quando): o esquema não mudou e os bloqueios antigos viraram desativações
sem migração. O banco confere de novo (validacao.checar_desativacao) na
entrada (inserir) e na correção (editar): desativado não entra.

Exceções de horário (horarios.py): a tela pede a autorização do
administrador e a passa em `autorizacao` ({"autorizado_por", "regras",
"justificativa"}). O banco confere de novo (defesa em profundidade): uma
visita com mais de 24 h só é gravada com a autorização de um
administrador ativo, e toda autorização vira um evento "Exceção
autorizada" no histórico daquela visita, na mesma transação.
"""

import json
import logging
import os
import re
import sqlite3
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta

from . import horarios, senhas, validacao, veiculos
from .usuarios import (LOGIN_INEXISTENTE, SESSAO_ENCERRADA, TEMA_PADRAO, TEMAS,
                       conferir_autorizador, pode_editar)
from .validacao import (FORMATO, MAXIMO_BUSCA, MAXIMO_CELULAR, MAXIMO_CPF,
                        MAXIMO_CODIGO, MAXIMO_DATA_HORA, MAXIMO_DESCRICAO,
                        MAXIMO_JUSTIFICATIVA, MAXIMO_LOGIN, MAXIMO_MOTIVO,
                        MAXIMO_NOME, MAXIMO_PLACA, MAXIMO_SENHA, TIPOS_ACESSO,
                        TIPOS_DESATIVACAO, checar_tamanho, formatar_placa,
                        mascarar_cpf,
                        mascarar_cpfs_no_texto, normalizar, so_digitos,
                        validar)

FORMATO_ISO = "%Y-%m-%d %H:%M"
FORMATO_ISO_SEGUNDOS = "%Y-%m-%d %H:%M:%S"
# 1: registros | 2: + usuarios e auditoria | 3: + pessoas
# 4: auditoria ligada ao registro (histórico de cada visita)
# 5: + bloqueios (CPFs e placas com acesso negado; na 2.3, as
#    desativações de pessoa e de veículo, na mesma tabela)
# 6: uma visita aberta por CPF garantida no banco, índices de desempenho
#    e tentativas de login guardadas no banco
# 7: índice das saídas (o Movimento mostra também quem saiu hoje) e
#    configuração dos horários de acesso (funcionamento, feriados, eventos,
#    regras por categoria e parâmetros)
# 8: tolerância de cada categoria depois do fechamento, padrões novos das
#    regras de horário (ninguém entra depois de fechar, retroativo de 3 h)
#    e as estadias de veículo (o carro tem entrada e saída próprias)
# 9: tema (claro, escuro ou seguir o Windows) escolhido por cada usuário
# 10: tabela meta com a versão do esquema, que um programa antigo não
#     conhece: se ele rebaixar o user_version, o programa novo percebe
# 11 (versão 2.2): troca de senha obrigatória (usuarios.trocar_senha),
#     códigos de recuperação do administrador, pessoas autorizadas a
#     retirar o veículo e a lotação do estacionamento (parametros vagas e
#     bloquear_lotado)
# (2.3: sem mudança de esquema — desativação, cadastro e exclusão de
#  pessoa usam as tabelas que já existiam)
VERSAO_ESQUEMA = 11
SEGUNDOS_ESPERA = 10          # espera pelo banco ocupado por outro computador
AUTOR_SISTEMA = "(sistema)"   # não é um login válido: ninguém se passa por ele
REGISTRO_MUDOU = ("Este registro foi alterado em outra estação enquanto a "
                  "correção estava aberta (por exemplo, recebeu a saída).\n"
                  "Nada foi gravado. Feche a janela e abra a correção de novo.")

log = logging.getLogger("portaria.dados")
log.addHandler(logging.NullHandler())   # sem log configurado, não imprime nada

# Tabelas da versão 5 (base de todas as migrações seguintes)
ESQUEMA_V5 = [
    """CREATE TABLE IF NOT EXISTS registros (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        nome     TEXT NOT NULL CHECK (nome <> ''),
        cpf      TEXT NOT NULL CHECK (length(cpf) = 11),
        celular  TEXT NOT NULL,
        placa    TEXT NOT NULL DEFAULT '',
        tipo     TEXT NOT NULL,
        entrada  TEXT NOT NULL,
        saida    TEXT NOT NULL DEFAULT '',
        pessoa_id INTEGER REFERENCES pessoas (id),
        CHECK (saida = '' OR saida >= entrada)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_registros_cpf ON registros (cpf)",
    """CREATE TABLE IF NOT EXISTS pessoas (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        cpf      TEXT NOT NULL UNIQUE CHECK (length(cpf) = 11),
        nome     TEXT NOT NULL CHECK (nome <> ''),
        celular  TEXT NOT NULL,
        placa    TEXT NOT NULL DEFAULT '',  -- último veículo usado
        tipo     TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS usuarios (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        login   TEXT NOT NULL UNIQUE,
        nome    TEXT NOT NULL,
        perfil  TEXT NOT NULL CHECK (perfil IN ('admin', 'porteiro')),
        senha   TEXT NOT NULL,              -- hash PBKDF2, nunca a senha
        ativo   INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1))
    )""",
    """CREATE TABLE IF NOT EXISTS auditoria (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        momento  TEXT NOT NULL,             -- ISO com segundos
        usuario  TEXT NOT NULL,             -- login de quem fez
        acao     TEXT NOT NULL,
        detalhe  TEXT NOT NULL DEFAULT '',
        registro_id INTEGER                 -- visita afetada, quando houver
    )""",
    """CREATE TABLE IF NOT EXISTS bloqueios (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo         TEXT NOT NULL CHECK (tipo IN ('cpf', 'placa')),
        valor        TEXT NOT NULL CHECK (valor <> ''),
        motivo       TEXT NOT NULL CHECK (motivo <> ''),
        criado_em    TEXT NOT NULL,         -- ISO
        criado_por   TEXT NOT NULL,
        ativo        INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
        removido_em  TEXT NOT NULL DEFAULT '',
        removido_por TEXT NOT NULL DEFAULT ''
    )""",
    # um mesmo CPF/placa só pode ter um bloqueio ativo por vez
    # (os removidos ficam guardados como histórico)
    """CREATE UNIQUE INDEX IF NOT EXISTS idx_bloqueio_ativo
        ON bloqueios (tipo, valor) WHERE ativo = 1""",
]

# Monta a tabela de pessoas a partir das visitas de um banco anterior à v3:
# dados da visita mais recente de cada CPF e o último veículo informado.
MIGRAR_PESSOAS = [
    """INSERT INTO pessoas (cpf, nome, celular, placa, tipo)
    SELECT r.cpf, r.nome, r.celular,
           COALESCE((SELECT r2.placa FROM registros r2
                     WHERE r2.cpf = r.cpf AND r2.placa <> ''
                     ORDER BY r2.id DESC LIMIT 1), ''),
           r.tipo
    FROM registros r
    WHERE r.id IN (SELECT MAX(id) FROM registros GROUP BY cpf)
    ON CONFLICT (cpf) DO NOTHING""",
    """UPDATE registros
    SET pessoa_id = (SELECT p.id FROM pessoas p WHERE p.cpf = registros.cpf)
    WHERE pessoa_id IS NULL""",
]

# Liga ao registro os eventos gravados antes da v4 (o detalhe começa
# com "#<id>" nas ações sobre visitas).
MIGRAR_AUDITORIA = """
UPDATE auditoria
SET registro_id = CAST(substr(detalhe, 2, instr(detalhe || ' ', ' ') - 2)
                       AS INTEGER)
WHERE registro_id IS NULL AND detalhe LIKE '#%'
  AND acao IN ('Cadastro de entrada', 'Saída registrada', 'Saída desfeita',
               'Exclusão de registro')
"""

# Visitas, última entrada e entrada em aberto de cada pessoa
SELECT_PESSOAS = """
SELECT p.id, p.cpf, p.nome, p.celular, p.placa, p.tipo,
       COUNT(r.id), MAX(r.entrada),
       MAX(CASE WHEN r.saida = '' THEN r.entrada END)
FROM pessoas p LEFT JOIN registros r ON r.pessoa_id = p.id
"""

COLUNAS_REGISTRO = "id, nome, cpf, celular, placa, tipo, entrada, saida"
# Tamanho máximo dos textos da visita, conferido antes de gravar
TAMANHOS_DA_VISITA = (("Nome completo", "nome", MAXIMO_NOME),
                      ("CPF", "cpf", MAXIMO_CPF),
                      ("Celular", "celular", MAXIMO_CELULAR),
                      ("Placa", "placa", MAXIMO_PLACA),
                      ("Entrada", "entrada", MAXIMO_DATA_HORA),
                      ("Saída", "saida", MAXIMO_DATA_HORA))
# Ações do histórico (auditoria) que passaram por cima de uma regra: o
# Relatório de exceções (Usuários › Exceções) filtra por elas
EXCECAO_AUTORIZADA = "Exceção autorizada"        # horário, retroativo, 24 h
SAIDA_AUTOMATICA_ENCERRAMENTO = "Saída automática (encerramento)"
SAIDA_AUTOMATICA_ATUALIZACAO = "Saída automática (atualização)"
VEICULO_SEM_DONO = "Veículo saiu sem o dono"     # evento e regra (RN32)
# RN35: pessoas autorizadas a retirar o veículo
VEICULO_COM_AUTORIZADO = "Veículo saiu com autorizado"
AUTORIZADO_ADICIONADO = "Autorizado a retirar veículo"
AUTORIZADO_REMOVIDO = "Autorização de retirada removida"
# RN37: lotação do estacionamento
LOTACAO_LIBERADA = "Estacionamento lotado liberado"           # com a senha
LOTACAO_CONFIRMADA = "Entrada com estacionamento lotado"      # só o aviso
# RN40: dois carros da mesma pessoa
CARRO_JA_SAIU = "Saída de veículo corrigida (já tinha saído)"
OUTRO_CARRO_LIBERADO = "Terceiro carro da mesma pessoa liberado"
# RN38: códigos de recuperação do administrador (o código nunca vai ao
# histórico, só quantos restam)
CODIGOS_GERADOS = "Códigos de recuperação gerados"
# RN12 (2.3): desativação de pessoa (CPF) e de veículo (placa)
DESATIVADA = {"cpf": "Pessoa desativada", "placa": "Veículo desativado"}
REATIVADA = {"cpf": "Pessoa reativada", "placa": "Veículo reativado"}
ENTRADA_RECUSADA = "Entrada recusada (desativação)"
# 2.3: cadastro de pessoa sem entrada e exclusão (só sem visitas)
PESSOA_CADASTRADA = "Pessoa cadastrada"
PESSOA_EXCLUIDA = "Pessoa excluída"
CODIGO_RECUPERACAO_USADO = "Senha redefinida com código de recuperação"
RECUPERACAO_RECUSADA = "Recuperação de senha recusada"
# todas as exceções, na ordem do filtro "Tipo" do relatório
ACOES_DE_EXCECAO = (EXCECAO_AUTORIZADA, VEICULO_SEM_DONO,
                    VEICULO_COM_AUTORIZADO, LOTACAO_LIBERADA,
                    CARRO_JA_SAIU, OUTRO_CARRO_LIBERADO,
                    SAIDA_AUTOMATICA_ENCERRAMENTO,
                    SAIDA_AUTOMATICA_ATUALIZACAO, CODIGO_RECUPERACAO_USADO)
TROCA_DE_SENHA_PENDENTE = ("Defina a sua senha antes de continuar: saia e "
                           "entre de novo para trocá-la.")
AUTORIZACAO_SEM_SENHA = ("A autorização de outro usuário só vale com a senha "
                         "dele.\nNada foi gravado.")
# Busca (visitas e pessoas): texto no nome, tipo e placa; dígitos no CPF
# e no celular
COLUNAS_BUSCA = {"texto": ("nome", "tipo", "placa"),
                 "digitos": ("cpf", "celular")}

# Estadia de veículo com o tipo de acesso do responsável (da visita de
# origem ou, se ela foi apagada, do cadastro) e se ele está no campus
COLUNAS_ESTADIA = """e.id, e.placa, e.cpf, e.nome, e.entrada, e.saida,
    e.registro_id, COALESCE(r.tipo, p.tipo, ''),
    EXISTS (SELECT 1 FROM registros a WHERE a.cpf = e.cpf AND a.saida = '')"""
DE_ESTADIAS = """FROM estadias_veiculo e
    LEFT JOIN registros r ON r.id = e.registro_id
    LEFT JOIN pessoas p ON p.id = e.pessoa_id"""


# Linha da lista de quem pode retirar o veículo (RN35)
COLUNAS_AUTORIZADO = ("id, placa, dono_cpf, cpf, nome, valido_ate, "
                      "dono_presente, criado_por, criado_em, ativo, "
                      "removido_em, removido_por")
COLUNAS_AUTORIZADO_A = ", ".join(f"a.{c.strip()}"
                                 for c in COLUNAS_AUTORIZADO.split(","))


def _autorizado(linha):
    (i, placa, dono_cpf, cpf, nome, valido_ate, presente, criado_por,
     criado_em, ativo, removido_em, removido_por) = linha
    return {"id": i, "placa": placa, "dono_cpf": dono_cpf, "cpf": cpf,
            "nome": nome, "valido_ate": veiculos.dia_do_banco(valido_ate),
            "dono_presente": bool(presente), "criado_por": criado_por,
            "criado_em": de_iso(criado_em), "ativo": bool(ativo),
            "removido_em": de_iso(removido_em), "removido_por": removido_por}


class ErroDados(Exception):
    """
    Falha ao ler ou gravar os registros. A mensagem (str) é para o usuário;
    o erro técnico do SQLite, quando houver, fica em `detalhe` e no log.
    """

    def __init__(self, mensagem, detalhe=""):
        super().__init__(mensagem)
        self.detalhe = detalhe


def configurar_log(caminho, nivel=logging.WARNING):
    """
    Grava os erros técnicos do banco num arquivo (com rotação, até 3 x 1 MB).
    O log não leva dados pessoais: só a mensagem de erro do SQLite.
    """
    from logging.handlers import RotatingFileHandler
    handler = RotatingFileHandler(caminho, maxBytes=1_000_000, backupCount=3,
                                  encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(handler)
    log.setLevel(nivel)
    return handler


def mensagem_amigavel(erro):
    """Traduz um erro do SQLite numa mensagem sem SQL nem nomes de tabelas."""
    texto = str(erro).lower()
    if isinstance(erro, sqlite3.IntegrityError):
        if "registros.cpf" in texto:
            return ("Este CPF já possui uma entrada sem saída.\n"
                    "Registre a saída antes de uma nova entrada.")
        if "usuarios.login" in texto:
            return "Já existe um usuário com esse login."
        if "estadias_veiculo.placa" in texto:
            return ("Este veículo já está no estacionamento.\n"
                    "Registre a saída dele pela placa antes de uma nova "
                    "entrada com ele.")
        if "bloqueios.tipo" in texto:
            return "Esta pessoa ou veículo já está desativado."
        if "foreign key" in texto:
            return ("O registro aponta para um cadastro que não existe mais.\n"
                    "Atualize a tela e tente de novo.")
        return ("O banco de dados recusou os dados (valor inválido ou "
                "repetido).\nConfira os campos e tente de novo.")
    if "locked" in texto or "busy" in texto:
        return ("O banco de dados está em uso por outro computador ou "
                "programa.\nTente de novo em alguns segundos.")
    if "malformed" in texto or "not a database" in texto or "corrupt" in texto:
        return ("O arquivo do banco de dados está danificado.\n"
                "Avise o administrador: é preciso restaurar o último backup.")
    if "readonly" in texto or "read-only" in texto:
        return ("Sem permissão para gravar no banco de dados.\n"
                "Avise o administrador.")
    if "disk" in texto or "full" in texto:
        return "Não foi possível gravar: disco cheio ou com defeito."
    if "unable to open" in texto:
        return ("Não foi possível abrir o banco de dados.\n"
                "Confira se a pasta existe e se há permissão de gravação.")
    return ("Erro no banco de dados.\n"
            "Tente de novo; se continuar, avise o administrador.")


def _erro(erro):
    """ErroDados amigável a partir de um erro do SQLite (detalhe vai ao log)."""
    log.error("Erro do SQLite: %s: %s", type(erro).__name__, erro)
    return ErroDados(mensagem_amigavel(erro), detalhe=str(erro))


def para_iso(texto):
    """Formato da tela → ISO. Usa strptime de propósito: também valida."""
    return datetime.strptime(texto, FORMATO).strftime(FORMATO_ISO) if texto else ""


def de_iso(texto):
    """ISO → formato da tela, fatiando o texto (19x mais rápido que strptime;
    roda em toda linha das listagens)."""
    if not texto:
        return ""
    if len(texto) != 16:
        return datetime.strptime(texto, FORMATO_ISO).strftime(FORMATO)
    return f"{texto[8:10]}/{texto[5:7]}/{texto[:4]} {texto[11:16]}"


def _dia_iso(dia):
    """date/datetime → 'AAAA-MM-DD 00:00' (início do dia, para comparar em SQL)."""
    if isinstance(dia, datetime):
        dia = dia.date()
    return f"{dia:%Y-%m-%d} 00:00"


def _exigir_tamanho(rotulo, texto, maximo):
    """Defesa em profundidade: texto acima do máximo não é gravado."""
    ok, msg = checar_tamanho(rotulo, texto or "", maximo)
    if not ok:
        raise ErroDados(msg)


def _exigir_tamanhos_da_visita(registro):
    for rotulo, chave, maximo in TAMANHOS_DA_VISITA:
        _exigir_tamanho(rotulo, registro.get(chave, ""), maximo)


def _registro(linha):
    i, nome, cpf, cel, placa, tipo, entrada, saida = linha
    return {"id": i, "nome": nome, "cpf": cpf, "celular": cel,
            "placa": placa, "tipo": tipo, "entrada": de_iso(entrada),
            "saida": de_iso(saida)}


def _estadia(linha):
    i, placa, cpf, nome, entrada, saida, registro_id, tipo, dentro = linha
    return {"id": i, "placa": placa, "cpf": cpf, "nome": nome,
            "entrada": de_iso(entrada), "saida": de_iso(saida),
            "registro_id": registro_id, "tipo": tipo,
            "responsavel_dentro": bool(dentro)}


def _condicao_busca(texto, tabela, colunas, so_cpf_completo=False):
    """
    WHERE da busca com o MESMO critério de consultas.filtrar: o texto (em
    minúsculas) contido no nome, tipo ou placa, ou os dígitos dele contidos
    no CPF ou celular. Devolve (sql, parametros); sql vazio = sem filtro.

    so_cpf_completo (porteiro, que vê o CPF mascarado): o CPF só é achado
    pelos 11 dígitos exatos. Com pedaços, a busca respondia sobre os
    dígitos escondidos e o CPF inteiro saía em umas 20 buscas (QA2 M2).
    11 dígitos num campo de 11 dígitos é o mesmo que igualdade: `cpf = ?`
    usa o índice.
    """
    texto = texto.strip().lower()[:MAXIMO_BUSCA]
    if not texto:
        return "", []
    numeros = so_digitos(texto)
    if len(numeros) == 11 and re.fullmatch(r"[\d.\-\s]+", texto):
        # CPF ou celular completo: nome, tipo e placa não têm 11 dígitos
        # seguidos. Pelo índice do CPF (com OR o SQLite varria a tabela
        # inteira pela ordem da entrada: 0,25 s com 100 mil visitas)
        partes = " UNION ".join(f"SELECT id FROM {tabela} WHERE {c} = ?"
                                for c in colunas["digitos"])
        return f"id IN ({partes})", [numeros] * len(colunas["digitos"])
    partes = [f"instr(minusculo({c}), ?) > 0" for c in colunas["texto"]]
    params = [texto] * len(colunas["texto"])
    if numeros:
        for c in colunas["digitos"]:
            if c.endswith("cpf") and (len(numeros) == 11 or so_cpf_completo):
                if len(numeros) == 11:
                    partes.append(f"{c} = ?")
                    params.append(numeros)
                continue
            partes.append(f"instr({c}, ?) > 0")
            params.append(numeros)
    return "(" + " OR ".join(partes) + ")", params


def _minusculo(texto):
    return texto.lower() if texto is not None else None


def copiar_banco(origem, destino):
    """
    Cópia consistente do banco (mesmo em uso) com a API de backup do SQLite.
    Grava num arquivo temporário e só então renomeia: nunca fica um backup
    pela metade com o nome final.
    """
    temporario = destino + ".tmp"
    try:
        if os.path.exists(temporario):
            os.remove(temporario)
        with closing(sqlite3.connect(origem, timeout=SEGUNDOS_ESPERA)) as src, \
                closing(sqlite3.connect(temporario)) as dst:
            src.backup(dst)
        os.replace(temporario, destino)
    except sqlite3.Error as e:
        _apagar_se_existe(temporario)
        raise _erro(e) from e
    except OSError as e:
        _apagar_se_existe(temporario)
        log.error("Erro ao gravar a cópia do banco: %s", e)
        raise ErroDados("Não foi possível gravar a cópia de segurança do "
                        "banco.\nConfira a permissão e o espaço livre na "
                        "pasta backups.", detalhe=str(e)) from e
    return destino


def _apagar_se_existe(caminho):
    try:
        if os.path.exists(caminho):
            os.remove(caminho)
    except OSError as e:
        log.warning("Não foi possível apagar %s: %s", caminho, e)


# ------------------------------------------------------------------
# Migrações: cada passo roda numa transação só (tudo ou nada) e grava a
# nova versão na mesma transação. Não usar executescript aqui: ele faz
# COMMIT antes de rodar e quebraria a atomicidade.
# ------------------------------------------------------------------
def _passo_v5(banco, con, versao):
    """Do banco vazio (ou das versões 1 a 4) até a v5."""
    for sql in ESQUEMA_V5:
        con.execute(sql)
    colunas = {c[1] for c in con.execute("PRAGMA table_info(registros)")}
    if "pessoa_id" not in colunas:   # banco das versões 1 e 2
        con.execute("ALTER TABLE registros ADD COLUMN pessoa_id "
                    "INTEGER REFERENCES pessoas (id)")
    if versao < 3:
        for sql in MIGRAR_PESSOAS:
            con.execute(sql)
    colunas = {c[1] for c in con.execute("PRAGMA table_info(auditoria)")}
    if "registro_id" not in colunas:   # banco das versões 2 e 3
        con.execute("ALTER TABLE auditoria ADD COLUMN registro_id INTEGER")
    if versao < 4:
        con.execute(MIGRAR_AUDITORIA)
    con.execute("CREATE INDEX IF NOT EXISTS idx_registros_pessoa "
                "ON registros (pessoa_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_auditoria_registro "
                "ON auditoria (registro_id)")


def _passo_v6(banco, con, versao):
    """
    Integridade e desempenho:
    - visitas que apontam para pessoa inexistente são religadas pelo CPF
      (as chaves estrangeiras passam a valer em toda conexão);
    - CPF com mais de uma visita aberta (só acontecia com duas estações ao
      mesmo tempo): as mais antigas recebem como saída o horário da entrada
      seguinte, com um evento no histórico de cada uma e um aviso para o
      administrador conferir. Nada é apagado. Só então o índice único
      "uma visita aberta por CPF" é criado;
    - índices para "hoje + quem está dentro", busca e auditoria;
    - tabela das tentativas de login.
    """
    con.execute("UPDATE registros SET pessoa_id = "
                "(SELECT p.id FROM pessoas p WHERE p.cpf = registros.cpf) "
                "WHERE pessoa_id IS NOT NULL "
                "AND pessoa_id NOT IN (SELECT id FROM pessoas)")
    duplicados = con.execute("SELECT cpf FROM registros WHERE saida = '' "
                             "GROUP BY cpf HAVING COUNT(*) > 1").fetchall()
    fechadas = 0
    for (cpf,) in duplicados:
        abertas = con.execute("SELECT id, nome, entrada FROM registros "
                              "WHERE cpf = ? AND saida = '' "
                              "ORDER BY entrada, id", (cpf,)).fetchall()
        for (id_, nome, _), (_, _, seguinte) in zip(abertas, abertas[1:]):
            con.execute("UPDATE registros SET saida = ? WHERE id = ?",
                        (seguinte, id_))
            Banco._evento(con, AUTOR_SISTEMA, SAIDA_AUTOMATICA_ATUALIZACAO,
                          f"#{id_} {nome}: havia outra entrada sem saída do "
                          f"mesmo CPF; saída marcada em {de_iso(seguinte)}, "
                          "horário da entrada seguinte. Confira e corrija "
                          "se preciso.", id_)
            fechadas += 1
    if fechadas:
        banco.avisos.append(
            f"{fechadas} visita(s) estavam abertas em duplicidade (mesmo CPF "
            "dentro duas vezes) e receberam saída automática.\n"
            "Confira no histórico: ação \"Saída automática (atualização)\".")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_um_aberto_por_cpf "
                "ON registros (cpf) WHERE saida = ''")
    con.execute("CREATE INDEX IF NOT EXISTS idx_registros_entrada "
                "ON registros (entrada)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_pessoas_nome "
                "ON pessoas (nome COLLATE NOCASE)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_auditoria_momento "
                "ON auditoria (momento)")
    con.execute("""CREATE TABLE IF NOT EXISTS tentativas_login (
        chave         TEXT PRIMARY KEY,     -- login existente ou '*'
        falhas        INTEGER NOT NULL DEFAULT 0,
        bloqueios     INTEGER NOT NULL DEFAULT 0,
        bloqueado_ate TEXT NOT NULL DEFAULT ''
    )""")
    con.execute("PRAGMA analysis_limit = 1000")   # estatística por amostra: rápido
    con.execute("ANALYZE")


ESQUEMA_V7 = [
    # horário do campus por dia da semana (0 = segunda); vazio = fechado
    """CREATE TABLE IF NOT EXISTS funcionamento (
        dia    INTEGER PRIMARY KEY CHECK (dia BETWEEN 0 AND 6),
        abre   TEXT NOT NULL DEFAULT '',     -- 'HH:MM'
        fecha  TEXT NOT NULL DEFAULT '',
        CHECK ((abre = '' AND fecha = '') OR (abre <> '' AND fecha > abre))
    )""",
    """CREATE TABLE IF NOT EXISTS feriados (
        data      TEXT PRIMARY KEY,          -- 'AAAA-MM-DD'
        descricao TEXT NOT NULL CHECK (descricao <> '')
    )""",
    # evento: horário especial que soma ao funcionamento da data
    """CREATE TABLE IF NOT EXISTS eventos (
        data      TEXT PRIMARY KEY,
        abre      TEXT NOT NULL,
        fecha     TEXT NOT NULL,
        descricao TEXT NOT NULL CHECK (descricao <> ''),
        CHECK (fecha > abre)
    )""",
    """CREATE TABLE IF NOT EXISTS regras_categoria (
        tipo            TEXT PRIMARY KEY,
        relativa        INTEGER NOT NULL CHECK (relativa IN (0, 1)),
        abre_antes      INTEGER NOT NULL DEFAULT 0,
        fecha_depois    INTEGER NOT NULL DEFAULT 0,
        janela_abre     TEXT NOT NULL DEFAULT '',
        janela_fecha    TEXT NOT NULL DEFAULT '',
        ate_fechamento  INTEGER NOT NULL DEFAULT 0 CHECK (ate_fechamento IN (0, 1)),
        permanencia_min INTEGER NOT NULL CHECK (permanencia_min >= 0),
        CHECK (relativa = 1 OR janela_fecha > janela_abre)
    )""",
    # minutos_aviso (antes de fechar) e horas_retroativo
    """CREATE TABLE IF NOT EXISTS parametros (
        chave TEXT PRIMARY KEY,
        valor INTEGER NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_registros_saida ON registros (saida)",
]


def _passo_v7(banco, con, versao):
    """
    - índice das saídas: o Movimento passa a mostrar também quem SAIU hoje
      (ex.: entrada corrigida para outro dia e saída registrada agora), sem
      varrer a tabela inteira;
    - tabelas da configuração dos horários de acesso, já com os horários
      padrão (horarios.configuracao_padrao), que o administrador muda na
      página Configurações.
    """
    for sql in ESQUEMA_V7:
        con.execute(sql)
    padrao = horarios.configuracao_padrao()
    for dia, horario in padrao.funcionamento.items():
        con.execute("INSERT INTO funcionamento (dia, abre, fecha) VALUES "
                    "(?, ?, ?) ON CONFLICT (dia) DO NOTHING",
                    (dia, *_horario_iso(horario)))
    for tipo, regra in padrao.regras.items():     # a tolerância vem na v8
        con.execute("INSERT INTO regras_categoria " + _COLUNAS_REGRA_V7 +
                    " ON CONFLICT (tipo) DO NOTHING",
                    (tipo, *_regra_iso(regra)[:-1]))
    for chave, valor in _parametros(padrao).items():
        con.execute("INSERT INTO parametros (chave, valor) VALUES (?, ?) "
                    "ON CONFLICT (chave) DO NOTHING", (chave, valor))
    con.execute("ANALYZE")


_COLUNAS_REGRA_V7 = ("(tipo, relativa, abre_antes, fecha_depois, janela_abre, "
                     "janela_fecha, ate_fechamento, permanencia_min) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?)")
_COLUNAS_REGRA = ("(tipo, relativa, abre_antes, fecha_depois, janela_abre, "
                  "janela_fecha, ate_fechamento, permanencia_min, "
                  "tolerancia_min) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)")

# Padrões da v7 que mudaram na v8: só o que AINDA está no padrão antigo é
# trocado (o que o administrador já tinha mudado fica como ele deixou).
# (tabela, coluna, valor novo, condição que identifica o padrão antigo)
PADROES_ANTIGOS_V8 = [
    ("regras_categoria", "fecha_depois", 0,
     "tipo = 'Funcionário' AND relativa = 1 AND fecha_depois = 60",
     "Funcionário: entrada até o fechamento (era até 1 h depois)"),
    ("regras_categoria", "permanencia_min", 0,
     "tipo = 'Professor' AND ate_fechamento = 1 AND permanencia_min = 60",
     "Professor: permanência até o fechamento (a hora extra virou a "
     "tolerância de 30 min)"),
    ("parametros", "valor", horarios.HORAS_RETROATIVO_PADRAO,
     "chave = 'horas_retroativo' AND valor = 12",
     f"Lançamento retroativo sem autorização: até "
     f"{horarios.HORAS_RETROATIVO_PADRAO} h (era 12 h)"),
]


def _parametros(config):
    return {"minutos_aviso": config.minutos_aviso,
            "horas_retroativo": config.horas_retroativo}


def _horario_iso(horario):
    """Horario (ou None = fechado) -> ('HH:MM', 'HH:MM') para o banco."""
    if horario is None:
        return "", ""
    return (horario.abre.strftime(horarios.FORMATO_HORA),
            horario.fecha.strftime(horarios.FORMATO_HORA))


def _regra_iso(regra):
    """RegraCategoria -> valores das colunas (sem o tipo)."""
    return (int(regra.relativa), regra.abre_antes, regra.fecha_depois,
            *_horario_iso(regra.janela), int(regra.ate_fechamento),
            regra.permanencia_min, regra.tolerancia_min)


def _horario_do_banco(abre, fecha):
    if not abre:
        return None
    return horarios.Horario(horarios.hora(abre), horarios.hora(fecha))


def _descrever_evento(evento):
    return (f"{evento.data:{horarios.FORMATO_DATA}} {evento.horario} — "
            f"{evento.descricao}")


def _duracao_iso(entrada, saida):
    """Exceções do limite de 24 h, com as datas ISO do banco."""
    if not saida:
        return []
    return horarios.excecoes_da_duracao(datetime.strptime(entrada, FORMATO_ISO),
                                        datetime.strptime(saida, FORMATO_ISO))


ESQUEMA_V8 = [
    """CREATE TABLE IF NOT EXISTS estadias_veiculo (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        placa       TEXT NOT NULL CHECK (placa <> ''),
        cpf         TEXT NOT NULL CHECK (length(cpf) = 11),  -- responsável
        nome        TEXT NOT NULL,          -- nome do responsável na entrada
        pessoa_id   INTEGER REFERENCES pessoas (id),
        registro_id INTEGER REFERENCES registros (id) ON DELETE CASCADE,
        entrada     TEXT NOT NULL,          -- ISO
        saida       TEXT NOT NULL DEFAULT '',
        -- visita com que o carro saiu (para o Desfazer da saída)
        registro_saida_id INTEGER REFERENCES registros (id) ON DELETE SET NULL,
        autor_entrada TEXT NOT NULL DEFAULT '',
        autor_saida   TEXT NOT NULL DEFAULT '',
        CHECK (saida = '' OR saida >= entrada)
    )""",
    # o mesmo carro não "entra" duas vezes: uma estadia aberta por placa
    """CREATE UNIQUE INDEX IF NOT EXISTS idx_uma_estadia_aberta_por_placa
        ON estadias_veiculo (placa) WHERE saida = ''""",
    """CREATE INDEX IF NOT EXISTS idx_estadias_abertas_cpf
        ON estadias_veiculo (cpf) WHERE saida = ''""",
    """CREATE INDEX IF NOT EXISTS idx_estadias_registro
        ON estadias_veiculo (registro_id)""",
    """CREATE INDEX IF NOT EXISTS idx_estadias_registro_saida
        ON estadias_veiculo (registro_saida_id)""",
]

# Cada visita aberta com placa vira uma estadia aberta. Se a mesma placa
# está em mais de uma visita aberta (caronas, antes da v8), o responsável é
# quem entrou primeiro com ela. Pode rodar de novo (banco rebaixado por um
# programa antigo, QA2 B3): placa já no estacionamento ou visita que já
# tem estadia não ganham outra.
MIGRAR_ESTADIAS = f"""
INSERT INTO estadias_veiculo (placa, cpf, nome, pessoa_id, registro_id,
                              entrada, autor_entrada)
SELECT r.placa, r.cpf, r.nome, r.pessoa_id, r.id, r.entrada, '{AUTOR_SISTEMA}'
FROM registros r
WHERE r.saida = '' AND r.placa <> ''
  AND r.id = (SELECT r2.id FROM registros r2
              WHERE r2.saida = '' AND r2.placa = r.placa
              ORDER BY r2.entrada, r2.id LIMIT 1)
  AND NOT EXISTS (SELECT 1 FROM estadias_veiculo e
                  WHERE (e.saida = '' AND e.placa = r.placa)
                     OR e.registro_id = r.id)
"""


def _passo_v8(banco, con, versao):
    """
    Regras de horário revistas pelo aluno:
    - coluna da tolerância depois do fechamento (30 min para professor e
      funcionário: só eles ficam um pouco além do fechamento sem virar
      "Saída pendente");
    - padrões novos (PADROES_ANTIGOS_V8), trocados só onde o valor ainda
      era o padrão antigo. O que mudou vai num aviso para o administrador;
    - estadias de veículo, já com os carros de quem está no campus.
    """
    for sql in ESQUEMA_V8:
        con.execute(sql)
    con.execute(MIGRAR_ESTADIAS)
    colunas = {c[1] for c in con.execute("PRAGMA table_info(regras_categoria)")}
    if "tolerancia_min" in colunas:
        return          # já era v8 (rebaixado por um programa antigo)
    con.execute("ALTER TABLE regras_categoria ADD COLUMN tolerancia_min "
                "INTEGER NOT NULL DEFAULT 0 CHECK (tolerancia_min >= 0)")
    padrao = horarios.configuracao_padrao()
    for tipo, regra in padrao.regras.items():
        if regra.tolerancia_min:
            con.execute("UPDATE regras_categoria SET tolerancia_min = ? "
                        "WHERE tipo = ?", (regra.tolerancia_min, tipo))
    mudancas = []
    for tabela, coluna, valor, condicao, descricao in PADROES_ANTIGOS_V8:
        cursor = con.execute(f"UPDATE {tabela} SET {coluna} = ? "
                             f"WHERE {condicao}", (valor,))
        if cursor.rowcount:
            mudancas.append(descricao)
    if versao >= 7 and mudancas:
        banco.avisos.append(
            "Regras de horário atualizadas para os novos padrões:\n• "
            + "\n• ".join(mudancas)
            + "\nProfessor e funcionário têm 30 min de tolerância depois do "
              "fechamento. Confira em Configurações.")


def _passo_v9(banco, con, versao):
    """Coluna do tema de cada usuário. Usuário novo começa em "seguir o
    Windows"; quem já existia começa em "claro", que é como o programa
    sempre abriu: nada muda para ele até escolher outro tema no menu da
    conta."""
    colunas = {c[1] for c in con.execute("PRAGMA table_info(usuarios)")}
    if "tema" in colunas:
        return
    lista = ", ".join(f"'{t}'" for t in TEMAS)
    con.execute(f"ALTER TABLE usuarios ADD COLUMN tema TEXT NOT NULL "
                f"DEFAULT '{TEMA_PADRAO}' CHECK (tema IN ({lista}))")
    if versao > 0:
        con.execute("UPDATE usuarios SET tema = 'claro'")


def _passo_v10(banco, con, versao):
    """Tabela meta: guarda a versão do esquema num lugar que os programas
    antigos não conhecem (eles só olham o PRAGMA user_version). O programa
    das versões 5 e 6 regravava o user_version sem conferir; com a meta, o
    programa novo percebe o rebaixamento (ver Banco._migrar)."""
    con.execute("""CREATE TABLE IF NOT EXISTS meta (
        chave TEXT PRIMARY KEY,
        valor INTEGER NOT NULL
    )""")


ESQUEMA_V11 = [
    # RN38: só o hash de cada código; usado_em = quando foi queimado
    """CREATE TABLE IF NOT EXISTS codigos_recuperacao (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL REFERENCES usuarios (id),
        hash       TEXT NOT NULL CHECK (hash <> ''),
        usado_em   TEXT NOT NULL DEFAULT ''
    )""",
    """CREATE INDEX IF NOT EXISTS idx_codigos_usuario
        ON codigos_recuperacao (usuario_id)""",
    # RN35: quem pode retirar o carro de uma placa sem o dono (remoção
    # lógica, como nos bloqueios); valido_ate 'AAAA-MM-DD' ou '' (até
    # alguém remover); dono_presente: o dono estava no campus no cadastro
    f"""CREATE TABLE IF NOT EXISTS autorizados_veiculo (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        placa         TEXT NOT NULL CHECK (length(placa) = {MAXIMO_PLACA}),
        dono_cpf      TEXT NOT NULL CHECK (length(dono_cpf) = 11),
        cpf           TEXT NOT NULL CHECK (length(cpf) = 11 AND cpf <> dono_cpf),
        nome          TEXT NOT NULL CHECK (nome <> '' AND length(nome) <= {MAXIMO_NOME}),
        valido_ate    TEXT NOT NULL DEFAULT '',
        dono_presente INTEGER NOT NULL DEFAULT 0 CHECK (dono_presente IN (0, 1)),
        criado_por    TEXT NOT NULL,
        criado_em     TEXT NOT NULL,
        ativo         INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
        removido_em   TEXT NOT NULL DEFAULT '',
        removido_por  TEXT NOT NULL DEFAULT ''
    )""",
    """CREATE INDEX IF NOT EXISTS idx_autorizados_placa
        ON autorizados_veiculo (placa)""",
    # a mesma pessoa não fica duas vezes ativa na lista da mesma placa
    """CREATE UNIQUE INDEX IF NOT EXISTS idx_autorizado_ativo
        ON autorizados_veiculo (placa, cpf) WHERE ativo = 1""",
]
# RN37: 0 vagas = sem controle de lotação; bloquear_lotado 0 = só avisa
PARAMETROS_V11 = {"vagas": 0, "bloquear_lotado": 0}


def _passo_v11(banco, con, versao):
    """
    Versão 2.2 (uma migração só):
    - usuarios.trocar_senha (RN39): quem já existia não precisa trocar;
    - codigos_recuperacao (RN38) e autorizados_veiculo (RN35);
    - parâmetros da lotação do estacionamento (RN37), sem controle.
    """
    colunas = {c[1] for c in con.execute("PRAGMA table_info(usuarios)")}
    if "trocar_senha" not in colunas:
        con.execute("ALTER TABLE usuarios ADD COLUMN trocar_senha INTEGER "
                    "NOT NULL DEFAULT 0 CHECK (trocar_senha IN (0, 1))")
    for sql in ESQUEMA_V11:
        con.execute(sql)
    for chave, valor in PARAMETROS_V11.items():
        con.execute("INSERT INTO parametros (chave, valor) VALUES (?, ?) "
                    "ON CONFLICT (chave) DO NOTHING", (chave, valor))


# (versão alcançada, função) em ordem; uma migração nova entra no fim.
# Cada passo pode rodar de novo sem estragar nada (banco rebaixado).
MIGRACOES = [(5, _passo_v5), (6, _passo_v6), (7, _passo_v7), (8, _passo_v8),
             (9, _passo_v9), (10, _passo_v10), (11, _passo_v11)]

VERSAO_MAIS_NOVA = ("Este banco de dados foi criado por uma versão mais nova "
                    "do programa.\nAtualize o programa para abrir este banco "
                    "(nada foi alterado nele).")
REBAIXADO = ("Este banco foi aberto por uma versão ANTIGA do programa, que "
             "rebaixou a versão dele (v{gravada} → v{versao}). O banco foi "
             "atualizado de novo, com uma cópia em backups antes.\nConfira "
             "os registros feitos na versão antiga e não use mais o "
             "programa antigo neste banco.")


def _versao_gravada(con):
    """Versão do esquema guardada na tabela meta (0 se ainda não existe)."""
    existe = con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                         "AND name = 'meta'").fetchone()
    if existe is None:
        return 0
    linha = con.execute("SELECT valor FROM meta WHERE chave = "
                        "'versao_esquema'").fetchone()
    return linha[0] if linha else 0


class Banco:
    def __init__(self, caminho, wal=True, relogio=None, estacao=None):
        """
        Abre (e atualiza, se preciso) o banco. `wal=False` para banco em
        pasta de rede, onde o modo WAL do SQLite não funciona.
        `avisos` guarda mensagens da atualização para mostrar ao administrador.
        `relogio`: função que devolve o agora (a tela passa o dela, para as
        regras de horário e a RN11 usarem o mesmo relógio nos testes).
        `estacao`: nome deste computador no contador de senhas erradas da
        autorização (o mesmo do diálogo: senhas.estacao_atual).
        """
        self.caminho = caminho
        self.relogio = relogio or datetime.now
        self.estacao = estacao or senhas.estacao_atual()
        self.avisos = []
        self._migrar(wal)

    # --------------------------------------------------------------
    # Abertura e migração
    # --------------------------------------------------------------
    def _migrar(self, wal):
        try:
            con = sqlite3.connect(self.caminho, timeout=SEGUNDOS_ESPERA,
                                  isolation_level=None)
        except sqlite3.Error as e:
            raise _erro(e) from e
        try:
            versao = con.execute("PRAGMA user_version").fetchone()[0]
            gravada = _versao_gravada(con)
            if max(versao, gravada) > VERSAO_ESQUEMA:
                raise ErroDados(VERSAO_MAIS_NOVA, detalhe=(
                    f"user_version {versao}, meta {gravada} > {VERSAO_ESQUEMA}"))
            if gravada > versao:
                # um programa antigo (v5/v6) regravou o user_version: os
                # passos rodam de novo (todos podem repetir) e o admin sabe
                log.warning("Banco rebaixado: meta v%s, user_version v%s",
                            gravada, versao)
                self.avisos.append(REBAIXADO.format(gravada=gravada,
                                                    versao=versao))
            if 0 < versao < VERSAO_ESQUEMA:
                self._backup_antes_de_migrar(versao)
            for alvo, passo in MIGRACOES:
                if versao >= alvo:
                    continue
                self._passo(con, alvo, passo, versao)
                versao = alvo
            if gravada != VERSAO_ESQUEMA:
                con.execute("INSERT INTO meta (chave, valor) VALUES "
                            "('versao_esquema', ?) ON CONFLICT (chave) "
                            "DO UPDATE SET valor = excluded.valor",
                            (VERSAO_ESQUEMA,))
            if wal:
                con.execute("PRAGMA journal_mode = WAL")
        except sqlite3.Error as e:
            raise _erro(e) from e
        finally:
            con.close()

    def _passo(self, con, alvo, passo, versao):
        """Um passo da migração numa transação; se falhar, nada muda e a
        mensagem diz que foi a atualização (não um erro de cadastro)."""
        con.execute("BEGIN IMMEDIATE")
        try:
            passo(self, con, versao)
            con.execute(f"PRAGMA user_version = {int(alvo)}")
            con.execute("COMMIT")
        except sqlite3.IntegrityError as e:
            con.execute("ROLLBACK")
            log.error("Migração para a v%s recusada: %s", alvo, e)
            raise ErroDados(
                f"Não foi possível atualizar o banco de dados para a versão "
                f"{alvo} (os dados atuais não passaram nas regras novas).\n"
                "Nada foi alterado nele; há uma cópia na pasta backups. "
                "Avise o administrador.", detalhe=str(e)) from e
        except BaseException:
            con.execute("ROLLBACK")
            raise

    def _backup_antes_de_migrar(self, versao):
        """Cópia do banco antigo antes de mudar o esquema (pasta backups).
        Sem a cópia, a atualização não acontece: o banco fica como estava."""
        pasta = os.path.join(os.path.dirname(os.path.abspath(self.caminho)),
                             "backups")
        nome = (f"portaria-antes-v{VERSAO_ESQUEMA}-de-v{versao}-"
                f"{datetime.now():%Y%m%d-%H%M%S}.db")
        try:
            os.makedirs(pasta, exist_ok=True)
            copiar_banco(self.caminho, os.path.join(pasta, nome))
        except (OSError, ErroDados) as e:
            log.error("Backup antes da atualização não realizado: %s",
                      getattr(e, "detalhe", "") or e)
            raise ErroDados(
                "Este banco de dados precisa ser atualizado para esta versão "
                "do programa, mas antes é preciso fazer uma cópia de "
                "segurança dele (pasta backups, ao lado do banco), e isso "
                "não foi possível.\nNada foi alterado no banco. Confira se a "
                "pasta pode ser criada e se há espaço no disco; depois abra "
                "o programa de novo.", detalhe=str(e)) from e

    @contextmanager
    def _conexao(self):
        """Uma transação: confirma no fim, desfaz se der erro, sempre fecha."""
        try:
            con = sqlite3.connect(self.caminho, timeout=SEGUNDOS_ESPERA)
            con.execute("PRAGMA foreign_keys = ON")
            con.execute(f"PRAGMA busy_timeout = {SEGUNDOS_ESPERA * 1000}")
            con.execute("PRAGMA synchronous = NORMAL")
            con.create_function("minusculo", 1, _minusculo, deterministic=True)
        except sqlite3.Error as e:
            raise _erro(e) from e
        try:
            yield con
            con.commit()
        except sqlite3.Error as e:
            con.rollback()
            raise _erro(e) from e
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    def verificar_integridade(self):
        """(ok, mensagem) com PRAGMA quick_check (rápido: ~70 ms com 1 ano)."""
        with self._conexao() as con:
            linhas = [linha[0] for linha in con.execute("PRAGMA quick_check")]
        if linhas == ["ok"]:
            return True, ""
        log.error("quick_check: %s", "; ".join(linhas[:10]))
        return False, ("O banco de dados apresenta defeitos.\n"
                       "Avise o administrador: é preciso restaurar o último backup.")

    # --------------------------------------------------------------
    # Permissões (conferidas no banco)
    # --------------------------------------------------------------
    @staticmethod
    def _exigir(con, autor, so_admin=True, para="fazer esta operação",
                troca=False):
        """
        Operação sensível: `autor` é obrigatório e precisa existir, estar
        ativo e (com so_admin) ser administrador. Devolve o usuário (dict).
        RN39: quem ainda precisa definir a própria senha (criado ou com a
        senha redefinida pelo administrador) não faz nada além disso
        (troca=True é só a troca da própria senha).
        """
        if autor is None:
            raise ErroDados(SESSAO_ENCERRADA)
        linha = con.execute("SELECT id, perfil, ativo, trocar_senha "
                            "FROM usuarios WHERE login = ?",
                            (autor,)).fetchone()
        if linha is None or not linha[2]:
            raise ErroDados("Usuário não autorizado ou desativado.\n"
                            "Saia e entre de novo no sistema.")
        if linha[3] and not troca:
            raise ErroDados(TROCA_DE_SENHA_PENDENTE)
        if so_admin and linha[1] != "admin":
            raise ErroDados(f"Somente o administrador pode {para}.")
        return {"id": linha[0], "login": autor, "perfil": linha[1]}

    def _autorizacao_conferida(self, autorizacao, autor):
        """
        V0: a autorização como o Banco a aceita. Devolve uma CÓPIA sem a
        senha, com "com_senha" = True só se a senha foi recalculada AQUI
        (a marca que veio de fora é descartada). Senha errada conta no
        contador da estação (RN31) e recusa; com a estação travada, nem a
        senha certa passa. Sem senha, só vale a autorização dada pelo
        próprio operador (o administrador logado): a de outro usuário
        precisa da senha dele. Roda ANTES da transação da operação, para o
        contador ficar gravado mesmo quando ela é recusada.
        """
        if autorizacao is None:
            return None
        copia = {k: v for k, v in autorizacao.items()
                 if k not in ("senha", "com_senha")}
        login = copia.get("autorizado_por") or ""
        senha = autorizacao.get("senha")
        if senha is None:
            if autor is not None and login and login != autor:
                raise ErroDados(AUTORIZACAO_SEM_SENHA)
            return copia
        _exigir_tamanho("Senha", senha, MAXIMO_SENHA)
        usuario, motivo = conferir_autorizador(
            self, login, senha, self.estacao, autor or AUTOR_SISTEMA,
            self.relogio())
        if usuario is None:
            raise ErroDados(f"{motivo}\nNada foi gravado.")
        copia["autorizado_por"] = usuario["login"]
        copia["com_senha"] = True
        return copia

    @classmethod
    def _conferir_autorizacao(cls, con, autorizacao):
        """
        Exceção de horário: quem autoriza precisa ser administrador ativo
        e a justificativa é obrigatória. Sem autorização, não faz nada.
        """
        if autorizacao is None:
            return
        if not autorizacao.get("autorizado_por"):
            raise ErroDados("Falta o administrador que autorizou a exceção.")
        cls._exigir(con, autorizacao["autorizado_por"],
                    para="autorizar exceções de horário")
        justificativa = autorizacao.get("justificativa", "").strip()
        if len(justificativa) < horarios.MINIMO_JUSTIFICATIVA:
            raise ErroDados("A exceção precisa de uma justificativa (pelo "
                            f"menos {horarios.MINIMO_JUSTIFICATIVA} caracteres).")
        _exigir_tamanho("Justificativa", justificativa, MAXIMO_JUSTIFICATIVA)

    @classmethod
    def _conferir_autorizacao_veiculo(cls, con, autorizacao, placa):
        """RN32: o carro sai sem o dono só com a autorização de um
        administrador ativo dada com a SENHA dele (até o administrador
        logado redigita a senha), conferida em _autorizacao_conferida."""
        if autorizacao is None:
            raise ErroDados(
                f"O veículo {formatar_placa(placa)} só sai com o dono.\n"
                "Para liberar sem ele, um administrador precisa digitar a "
                "senha.")
        cls._conferir_autorizacao(con, autorizacao)
        if not autorizacao.get("com_senha"):
            raise ErroDados("A saída do veículo sem o dono precisa da senha "
                            "do administrador.")

    @classmethod
    def _registrar_veiculo_sem_dono(cls, con, autorizacao, autor, o_que,
                                    registro_id):
        """Evento "Veículo saiu sem o dono": quem autorizou (usuário do
        evento), o que aconteceu, o porquê e quem operava."""
        cls._evento(con, autorizacao["autorizado_por"], VEICULO_SEM_DONO,
                    f"{o_que} Justificativa: "
                    f"{autorizacao['justificativa'].strip()}. Operador: "
                    f"{autor or AUTOR_SISTEMA}. Senha do administrador "
                    "conferida.", registro_id)

    @staticmethod
    def _exigir_autorizacao_24h(acima_de_24h, autorizacao, nome):
        """Defesa em profundidade: visita acima de 24 h só com autorização."""
        if acima_de_24h and autorizacao is None:
            raise ErroDados(f"{nome}: {acima_de_24h[0]}\nIsso só pode ser "
                            "gravado com a autorização de um administrador.")

    @classmethod
    def _registrar_excecao(cls, con, autorizacao, autor, id_, nome):
        """Evento "Exceção autorizada" no histórico da visita: quem
        autorizou (usuário do evento), quem operava, as regras e o porquê."""
        regras = " ".join(autorizacao.get("regras", []))
        senha = (" Senha do administrador conferida."
                 if autorizacao.get("com_senha") else "")
        cls._evento(con, autorizacao["autorizado_por"], EXCECAO_AUTORIZADA,
                    f"#{id_} {nome} — {regras} Justificativa: "
                    f"{autorizacao['justificativa'].strip()}. "
                    f"Operador: {autor or AUTOR_SISTEMA}.{senha}", id_)

    @classmethod
    def _conferir_autor(cls, con, autor):
        """Escrita do dia a dia: o autor, quando informado, precisa existir
        e estar ativo. Sem autor é chamada interna (não vai ao histórico)."""
        if autor is not None:
            cls._exigir(con, autor, so_admin=False)

    # --------------------------------------------------------------
    # Registros (visitas)
    # --------------------------------------------------------------
    def listar(self):
        """Todos os registros, na ordem em que foram cadastrados."""
        with self._conexao() as con:
            linhas = con.execute(f"SELECT {COLUNAS_REGISTRO} FROM registros "
                                 "ORDER BY id").fetchall()
        return [_registro(linha) for linha in linhas]

    def listar_movimento(self, hoje):
        """
        Tabela principal: o movimento do dia `hoje` (date) — visitas com
        entrada hoje, todas as ainda abertas (quem está no campus) e as que
        tiveram SAÍDA hoje mesmo com a entrada em outro dia (ex.: entrada
        corrigida para fevereiro e saída registrada agora) —, da entrada mais
        recente para a mais antiga. Custo constante, não cresce com o
        histórico: cada parte usa um índice (entrada, aberta, saída).
        """
        inicio = _dia_iso(hoje)
        fim = _dia_iso((hoje.date() if isinstance(hoje, datetime) else hoje)
                       + timedelta(days=1))
        # UNION ALL usa um índice por parte; com OR viraria varredura da
        # tabela. As três partes não se repetem: a 2ª e a 3ª só pegam
        # entradas de outros dias. O '+' impede o índice de entrada nelas.
        with self._conexao() as con:
            linhas = con.execute(
                f"SELECT * FROM (SELECT {COLUNAS_REGISTRO} FROM registros "
                "WHERE entrada >= ? AND entrada < ? "
                f"UNION ALL SELECT {COLUNAS_REGISTRO} FROM registros "
                "WHERE saida = '' AND (+entrada < ? OR +entrada >= ?) "
                f"UNION ALL SELECT {COLUNAS_REGISTRO} FROM registros "
                "WHERE saida >= ? AND saida < ? AND +entrada < ?) "
                "ORDER BY entrada DESC, id DESC",
                (inicio, fim, inicio, fim, inicio, fim, inicio)).fetchall()
        return [_registro(linha) for linha in linhas]

    def buscar_registros(self, texto, limite=200, so_cpf_completo=False):
        """
        Busca no histórico inteiro com o mesmo critério de consultas.filtrar
        (nome, tipo, placa; CPF e celular pelos dígitos), da visita mais
        recente para a mais antiga, no máximo `limite`. Texto vazio = as
        mais recentes. so_cpf_completo: ver _condicao_busca (porteiro).
        """
        condicao, params = _condicao_busca(
            texto, "registros", COLUNAS_BUSCA, so_cpf_completo)
        where = f"WHERE {condicao}" if condicao else ""
        with self._conexao() as con:
            linhas = con.execute(
                f"SELECT {COLUNAS_REGISTRO} FROM registros {where} "
                "ORDER BY entrada DESC, id DESC LIMIT ?",
                (*params, int(limite))).fetchall()
        return [_registro(linha) for linha in linhas]

    def listar_por_cpf(self, cpf):
        """Todas as visitas de um CPF (para a checagem de sobreposição de
        validacao.validar quando a tela só tem o movimento do dia)."""
        with self._conexao() as con:
            linhas = con.execute(f"SELECT {COLUNAS_REGISTRO} FROM registros "
                                 "WHERE cpf = ? ORDER BY entrada, id",
                                 (cpf,)).fetchall()
        return [_registro(linha) for linha in linhas]

    def resumo_painel(self, hoje):
        """
        Números do dashboard calculados no SQL, no MESMO formato de
        consultas.resumo(registros, hoje): total, dentro, entradas_hoje,
        com_veiculo, por_tipo {tipo: [total, dentro]}, por_dia (7 dias),
        permanencia_media (timedelta ou None) e saidas.
        """
        if isinstance(hoje, datetime):
            hoje = hoje.date()
        por_tipo = {t: [0, 0] for t in TIPOS_ACESSO}
        por_dia = {hoje - timedelta(days=i): 0 for i in range(6, -1, -1)}
        total = dentro = com_veiculo = saidas = minutos = 0
        with self._conexao() as con:
            for tipo, qtd, abertos, veiculos, fechados, soma in con.execute(
                    "SELECT tipo, COUNT(*), SUM(saida = ''), SUM(placa <> ''), "
                    "SUM(saida <> ''), SUM(CASE WHEN saida <> '' THEN "
                    "CAST(round((julianday(saida) - julianday(entrada)) * 1440)"
                    " AS INTEGER) END) "
                    "FROM registros GROUP BY tipo ORDER BY MIN(id)"):
                por_tipo.setdefault(tipo, [0, 0])
                por_tipo[tipo][0] += qtd
                por_tipo[tipo][1] += abertos
                total += qtd
                dentro += abertos
                com_veiculo += veiculos
                saidas += fechados
                minutos += soma or 0
            for dia, qtd in con.execute(
                    "SELECT substr(entrada, 1, 10), COUNT(*) FROM registros "
                    "WHERE entrada >= ? AND entrada < ? GROUP BY 1",
                    (_dia_iso(hoje - timedelta(days=6)),
                     _dia_iso(hoje + timedelta(days=1)))):
                por_dia[date.fromisoformat(dia)] = qtd
        return {
            "total": total,
            "dentro": dentro,
            "entradas_hoje": por_dia[hoje],
            "com_veiculo": com_veiculo,
            "por_tipo": por_tipo,
            "por_dia": por_dia,
            "permanencia_media": (timedelta(minutes=minutos) / saidas
                                  if saidas else None),
            "saidas": saidas,
        }

    def contadores(self):
        """Números da barra lateral e das subabas de Pessoas: pessoas
        cadastradas, quem está no campus, pessoas (CPFs) e veículos
        (placas) desativados e carros no estacionamento (contagens com
        índice: rápido)."""
        with self._conexao() as con:
            pessoas, = con.execute("SELECT COUNT(*) FROM pessoas").fetchone()
            no_campus, = con.execute("SELECT COUNT(*) FROM registros "
                                     "WHERE saida = ''").fetchone()
            desativadas = dict(con.execute(
                "SELECT tipo, COUNT(*) FROM bloqueios WHERE ativo = 1 "
                "GROUP BY tipo").fetchall())
            veiculos, = con.execute("SELECT COUNT(*) FROM estadias_veiculo "
                                    "WHERE saida = ''").fetchone()
        return {"pessoas": pessoas, "no_campus": no_campus,
                "desativadas": desativadas.get("cpf", 0),
                "veiculos_desativados": desativadas.get("placa", 0),
                "veiculos": veiculos}

    def inserir(self, registro, autor=None, autorizacao=None,
                lotado_confirmado=False, autorizacao_lotacao=None,
                carro_ja_saiu=None, autorizacao_ja_saiu=None,
                autorizacao_carros=None):
        """
        Grava um registro (datas no formato da tela) e devolve o id. Com
        `autorizacao`, a visita é uma exceção de horário autorizada.
        RN37: a entrada de carro com o estacionamento lotado só passa com
        `lotado_confirmado` (o porteiro viu o aviso) ou, com "Bloquear
        quando lotado", com `autorizacao_lotacao` de um administrador dada
        com a senha (conferida aqui).
        RN40: `carro_ja_saiu` (id da estadia de um carro desta pessoa que
        ficou como no estacionamento, mas já tinha saído) é fechada na mesma
        transação, só com `autorizacao_ja_saiu` (senha do administrador).
        Com MAXIMO_CARROS_POR_PESSOA carros dela abertos, outro só entra com
        `autorizacao_carros` (senha do administrador).
        """
        autorizacao = self._autorizacao_conferida(autorizacao, autor)
        autorizacao_lotacao = self._autorizacao_conferida(autorizacao_lotacao,
                                                          autor)
        autorizacao_ja_saiu = self._autorizacao_conferida(autorizacao_ja_saiu,
                                                          autor)
        autorizacao_carros = self._autorizacao_conferida(autorizacao_carros,
                                                         autor)
        with self._conexao() as con:
            self._conferir_autor(con, autor)
            self._conferir_desativacao(con, registro)
            self._conferir_autorizacao(con, autorizacao)
            self._exigir_autorizacao_24h(
                _duracao_iso(para_iso(registro["entrada"]),
                             para_iso(registro.get("saida", ""))),
                autorizacao, registro["nome"])
            id_ = self._inserir(con, registro)
            self._evento(con, autor, "Cadastro de entrada",
                         f"#{id_} {registro['nome']} ({registro['tipo']})", id_)
            if carro_ja_saiu is not None:
                self._corrigir_carro_que_ja_saiu(con, carro_ja_saiu, registro,
                                                 id_, autor,
                                                 autorizacao_ja_saiu)
            if registro.get("placa") and not registro.get("saida"):
                self._conferir_carros_da_pessoa(con, registro, id_, autor,
                                                autorizacao_carros)
                self._conferir_lotacao(con, registro, id_, autor,
                                       lotado_confirmado, autorizacao_lotacao)
            if registro.get("placa"):
                self._abrir_estadia(con, registro, id_, autor)
            if autorizacao:
                self._registrar_excecao(con, autorizacao, autor, id_,
                                        registro["nome"])
            return id_

    @staticmethod
    def _inserir(con, r):
        """
        Grava a visita e cria a pessoa, se for nova. Os dados da pessoa só
        são atualizados se esta for a visita MAIS RECENTE dela: lançar uma
        visita antiga (retroativa) não troca o nome/celular atuais.
        A visita vai primeiro: se ela for recusada, a pessoa nem é tocada.
        """
        _exigir_tamanhos_da_visita(r)
        cursor = con.execute(
            "INSERT INTO registros (nome, cpf, celular, placa, tipo, entrada, saida) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (r["nome"], r["cpf"], r["celular"], r.get("placa", ""), r["tipo"],
             para_iso(r["entrada"]), para_iso(r.get("saida", ""))))
        id_registro = cursor.lastrowid
        con.execute("INSERT INTO pessoas (cpf, nome, celular, placa, tipo) "
                    "VALUES (?, ?, ?, ?, ?) ON CONFLICT (cpf) DO NOTHING",
                    (r["cpf"], r["nome"], r["celular"], r.get("placa", ""),
                     r["tipo"]))
        pessoa = con.execute("SELECT id FROM pessoas WHERE cpf = ?",
                             (r["cpf"],)).fetchone()[0]
        con.execute("UPDATE registros SET pessoa_id = ? WHERE id = ?",
                    (pessoa, id_registro))
        Banco._atualizar_pessoa_se_recente(con, pessoa, id_registro, r)
        return id_registro

    @staticmethod
    def _atualizar_pessoa_se_recente(con, pessoa, id_registro, r):
        """A pessoa fica com os dados da visita mais recente (a placa só muda
        se veio de carro desta vez)."""
        mais_recente = con.execute(
            "SELECT id FROM registros WHERE pessoa_id = ? "
            "ORDER BY entrada DESC, id DESC LIMIT 1", (pessoa,)).fetchone()[0]
        if mais_recente == id_registro:
            placa = r.get("placa", "")
            con.execute(
                "UPDATE pessoas SET nome = ?, celular = ?, tipo = ?, "
                "placa = CASE WHEN ? <> '' THEN ? ELSE placa END WHERE id = ?",
                (r["nome"], r["celular"], r["tipo"], placa, placa, pessoa))

    def registrar_saida(self, id_registro, saida, autor=None, autorizacao=None):
        """Saída de uma visita; False se ela já tinha saída ou não existe."""
        return bool(self.registrar_saidas([id_registro], saida, autor,
                                          autorizacao))

    def registrar_saidas(self, ids, saida, autor=None, autorizacao=None,
                         com_veiculo=(), autorizacao_veiculo=None):
        """
        Saída de uma ou várias visitas na mesma transação; só das abertas.
        Devolve os ids que de fato receberam a saída (outra estação pode ter
        dado a saída ou excluído a visita antes). Visita que passaria de
        24 h precisa da `autorizacao` (senão nada é gravado), e é a ela que
        a "Exceção autorizada" fica ligada.

        `com_veiculo`: as visitas que saem com o carro. Um dicionário
        {id da visita: id da estadia} diz QUAL carro (a pessoa pode ter dois
        no estacionamento); num conjunto de ids, sai o carro com que ela
        entrou nesta visita ou, sem ele, o mais antigo dela.

        RN32: o carro de OUTRO dono (a estadia escolhida não é da pessoa
        que sai) só sai com `autorizacao_veiculo` (administrador, com a
        senha); a exceção fica no histórico como "Veículo saiu sem o dono".
        O carro só fecha se a visita de quem sai com ele recebeu a saída
        nesta mesma transação.

        Duas estações dando a saída da mesma visita: o UPDATE só grava se a
        visita ainda estiver aberta, então a segunda não sobrescreve a
        primeira (nem duplica o evento no histórico).
        """
        autorizacao = self._autorizacao_conferida(autorizacao, autor)
        autorizacao_veiculo = self._autorizacao_conferida(autorizacao_veiculo,
                                                          autor)
        escolhas = (com_veiculo if isinstance(com_veiculo, dict)
                    else dict.fromkeys(com_veiculo))
        gravados = []
        saida_iso = para_iso(saida)
        with self._conexao() as con:
            self._conferir_autor(con, autor)
            self._conferir_autorizacao(con, autorizacao)
            for i in ids:
                linha = con.execute("SELECT nome, entrada FROM registros "
                                    "WHERE id = ? AND saida = ''", (i,)).fetchone()
                if linha is None:
                    continue
                nome, entrada = linha
                acima_de_24h = _duracao_iso(entrada, saida_iso)
                self._exigir_autorizacao_24h(acima_de_24h, autorizacao, nome)
                cursor = con.execute("UPDATE registros SET saida = ? "
                                     "WHERE id = ? AND saida = ''", (saida_iso, i))
                if not cursor.rowcount:      # outra estação chegou antes
                    continue
                gravados.append(i)
                self._evento(con, autor, "Saída registrada", f"#{i}", i)
                if acima_de_24h:
                    self._registrar_excecao(con, autorizacao, autor, i, nome)
                if i in escolhas:
                    self._sair_de_carro(con, i, saida_iso, autor, escolhas[i],
                                        autorizacao_veiculo)
        return gravados

    def desfazer_saidas(self, ids, autor=None, saida=None):
        """
        Volta as visitas para "dentro" (botão Desfazer). Só desfaz se a pessoa
        não tiver outra visita aberta ou terminada depois desta entrada —
        senão ficaria no campus duas vezes. Com `saida` (formato da tela), só
        desfaz a saída com esse horário: a que esta estação gravou, nunca
        uma lançada ou corrigida por outra. Devolve quantas foram desfeitas.
        """
        desfeitas = 0
        so_esta = "AND saida = ? " if saida else ""
        with self._conexao() as con:
            self._conferir_autor(con, autor)
            for i in ids:
                linha = con.execute("SELECT saida FROM registros WHERE id = ?",
                                    (i,)).fetchone()
                saida_antiga = linha[0] if linha else ""
                cursor = con.execute(
                    "UPDATE registros SET saida = '' WHERE id = ? AND saida <> '' "
                    + so_esta +
                    "AND NOT EXISTS (SELECT 1 FROM registros o "
                    "  WHERE o.cpf = registros.cpf AND o.id <> registros.id "
                    "  AND (o.saida = '' OR o.saida > registros.entrada))",
                    (i, para_iso(saida)) if saida else (i,))
                if cursor.rowcount:
                    desfeitas += 1
                    self._evento(con, autor, "Saída desfeita", f"#{i}", i)
                    self._reabrir_estadias(con, "registro_saida_id = ?", i,
                                           saida_antiga, autor)
        return desfeitas

    def excluir(self, ids, autor):
        """
        Apaga os registros (RN02: só administrador); o histórico guarda o
        que foi apagado, com o CPF mascarado.

        O carro que a visita trouxe e que AINDA ESTÁ no estacionamento não
        some com ela: ele está fisicamente lá (RN25). A estadia aberta só
        perde a ligação com a visita (o responsável continua pelo CPF e pelo
        cadastro) e o histórico registra "Veículo mantido no
        estacionamento"; o carro sai pela placa, como qualquer outro. As
        estadias já encerradas daquela visita vão junto com ela. Devolve as
        placas que continuaram no estacionamento.
        """
        mantidas = []
        with self._conexao() as con:
            self._exigir(con, autor, para="excluir registros")
            for i in ids:
                linha = con.execute(
                    "SELECT nome, cpf, entrada, saida FROM registros WHERE id = ?",
                    (i,)).fetchone()
                if linha is None:
                    continue
                nome, cpf, entrada, saida = linha
                placas = [p for (p,) in con.execute(
                    "SELECT placa FROM estadias_veiculo WHERE registro_id = ? "
                    "AND saida = ''", (i,))]
                con.execute("UPDATE estadias_veiculo SET registro_id = NULL "
                            "WHERE registro_id = ? AND saida = ''", (i,))
                con.execute("DELETE FROM registros WHERE id = ?", (i,))
                for placa in placas:
                    self._evento(con, autor, "Veículo mantido no estacionamento",
                                 f"Placa {formatar_placa(placa)}: a visita #{i} "
                                 f"de {nome} foi excluída e o carro continua no "
                                 "estacionamento (sai pela placa).")
                self._evento(con, autor, "Exclusão de registro",
                             f"#{i} {nome}, CPF {mascarar_cpf(cpf)}, entrada "
                             f"{de_iso(entrada)}, saída {de_iso(saida) or '—'}", i)
                mantidas += placas
        return mantidas

    def buscar(self, id_registro):
        """Um registro pelo id (datas no formato da tela), ou None."""
        with self._conexao() as con:
            linha = con.execute(f"SELECT {COLUNAS_REGISTRO} FROM registros "
                                "WHERE id = ?", (id_registro,)).fetchone()
        return _registro(linha) if linha else None

    def editar(self, id_registro, novo, alteracoes, autor, autorizacao=None,
               original=None, autorizacao_veiculo=None):
        """
        Corrige um registro e grava no histórico o que mudou (`alteracoes`,
        já descritas). Porteiro só corrige visitas com entrada (a original e
        a nova) nas últimas 24 h (RN11). Mantém o cadastro da pessoa coerente:
        - se esta é a visita mais recente da pessoa, ela recebe os dados novos;
        - se o CPF mudou, a visita passa para a pessoa certa e a pessoa do
          CPF errado é removida se ficar sem nenhuma visita.
        Exceção de horário: com `autorizacao` (obrigatória se as datas
        mudarem e a visita passar de 24 h), grava a "Exceção autorizada".

        `original`: o registro como a tela o leu ao abrir a correção. Se
        outra estação mudou a visita nesse meio-tempo (ex.: deu a saída), a
        correção é RECUSADA sem gravar nada (trava otimista: a condição vai
        no próprio UPDATE). Antes, salvar só o nome reabria a visita e
        apagava a saída dada pela outra estação.

        RN32: a correção que tiraria um carro do estacionamento sem o dono
        ou passaria o carro a outro dono (ver _correcao_mexe_no_carro) só
        grava com `autorizacao_veiculo` (administrador, com a senha).
        """
        _exigir_tamanhos_da_visita(novo)
        autorizacao = self._autorizacao_conferida(autorizacao, autor)
        autorizacao_veiculo = self._autorizacao_conferida(autorizacao_veiculo,
                                                          autor)
        with self._conexao() as con:
            usuario = self._exigir(con, autor, so_admin=False)
            self._conferir_autorizacao(con, autorizacao)
            linha = con.execute("SELECT pessoa_id, nome, entrada, saida, placa, "
                                "cpf FROM registros WHERE id = ?",
                                (id_registro,)).fetchone()
            if linha is None:
                raise ErroDados("Este registro não existe mais.")
            self._conferir_desativacao(con, novo, original={
                "cpf": linha[5], "placa": linha[4], "saida": linha[3]})
            pessoa_antiga = linha[0]
            sem_o_dono = self._correcao_mexe_no_carro(
                con, id_registro, {"cpf": linha[5], "saida": linha[3]}, novo)
            if sem_o_dono:
                self._conferir_autorizacao_veiculo(con, autorizacao_veiculo,
                                                   sem_o_dono[0][1])
            agora = self.relogio()
            for entrada in (de_iso(linha[2]), novo["entrada"]):
                ok, msg = pode_editar(usuario, {"entrada": entrada}, agora)
                if not ok:
                    raise ErroDados(msg)
            datas = (para_iso(novo["entrada"]), para_iso(novo["saida"]))
            if datas != (linha[2], linha[3]):       # só se as datas mudaram
                self._exigir_autorizacao_24h(_duracao_iso(*datas), autorizacao,
                                             novo["nome"])
            condicao, como_estava = "", ()
            if original is not None:
                condicao = (" AND nome = ? AND cpf = ? AND celular = ? AND "
                            "placa = ? AND tipo = ? AND entrada = ? AND saida = ?")
                como_estava = (original["nome"], original["cpf"],
                               original["celular"], original.get("placa", ""),
                               original["tipo"], para_iso(original["entrada"]),
                               para_iso(original["saida"]))
            cursor = con.execute(
                "UPDATE registros SET nome = ?, cpf = ?, celular = ?, placa = ?, "
                "tipo = ?, entrada = ?, saida = ? WHERE id = ?" + condicao,
                (novo["nome"], novo["cpf"], novo["celular"], novo["placa"],
                 novo["tipo"], para_iso(novo["entrada"]), para_iso(novo["saida"]),
                 id_registro, *como_estava))
            if not cursor.rowcount:
                raise ErroDados(REGISTRO_MUDOU)
            # Pessoa do CPF (novo): cria se ainda não existe
            con.execute("INSERT INTO pessoas (cpf, nome, celular, placa, tipo) "
                        "VALUES (?, ?, ?, ?, ?) ON CONFLICT (cpf) DO NOTHING",
                        (novo["cpf"], novo["nome"], novo["celular"],
                         novo["placa"], novo["tipo"]))
            pessoa = con.execute("SELECT id FROM pessoas WHERE cpf = ?",
                                 (novo["cpf"],)).fetchone()[0]
            con.execute("UPDATE registros SET pessoa_id = ? WHERE id = ?",
                        (pessoa, id_registro))
            self._atualizar_pessoa_se_recente(con, pessoa, id_registro, novo)
            self._sincronizar_estadia(con, id_registro, novo, linha[4],
                                      pessoa, autor)
            if pessoa_antiga is not None and pessoa_antiga != pessoa:
                con.execute("DELETE FROM pessoas WHERE id = ? AND NOT EXISTS "
                            "(SELECT 1 FROM registros WHERE pessoa_id = ?)",
                            (pessoa_antiga, pessoa_antiga))
            self._evento(con, autor, "Registro corrigido",
                         f"#{id_registro} {linha[1]} — " + "; ".join(alteracoes),
                         id_registro)
            if autorizacao:
                self._registrar_excecao(con, autorizacao, autor, id_registro,
                                        novo["nome"])
            for texto, _ in sem_o_dono:
                self._registrar_veiculo_sem_dono(
                    con, autorizacao_veiculo, autor,
                    f"Correção da visita #{id_registro}: {texto}", id_registro)

    def veiculo_sem_dono_na_correcao(self, id_registro, novo):
        """Textos do que a correção faria com um carro sem o dono (a tela
        pede a senha do administrador antes de salvar); [] = nada."""
        with self._conexao() as con:
            linha = con.execute("SELECT cpf, saida FROM registros WHERE id = ?",
                                (id_registro,)).fetchone()
            if linha is None:
                return []
            antes = {"cpf": linha[0], "saida": linha[1]}
            return [texto for texto, _ in self._correcao_mexe_no_carro(
                con, id_registro, antes, novo)]

    @classmethod
    def _correcao_mexe_no_carro(cls, con, id_registro, antes, novo):
        """
        [(texto, placa)] do que a correção faria com carros no
        estacionamento sem o dono (RN32):
        - a visita já saiu e o carro dela ficou: apagar ou trocar a placa
          tiraria o carro sem o dono; trocar o CPF passaria o carro a outro
          dono, que poderia sair com ele;
        - a visita fica aberta e o CPF muda para o de alguém com carro no
          estacionamento: essa pessoa passaria a constar no campus e
          poderia sair com o carro.
        Corrigir a placa ou o CPF de quem AINDA está no campus com o carro
        é erro de digitação da própria visita: não pede nada.
        """
        achados = []
        estadia = cls._estadia_aberta(con, "registro_id", id_registro)
        if estadia is not None and antes["saida"]:
            placa = formatar_placa(estadia["placa"])
            if not novo["placa"]:
                achados.append(f"a placa {placa} seria apagada e o carro "
                               "sairia do estacionamento sem o dono.")
            elif novo["placa"] != estadia["placa"]:
                achados.append(f"a placa {placa} seria trocada por "
                               f"{formatar_placa(novo['placa'])} e o carro "
                               "sairia do estacionamento sem o dono.")
            if novo["cpf"] != antes["cpf"]:
                achados.append(f"o carro {placa}, que ficou no "
                               "estacionamento, passaria para outro dono.")
            achados = [(texto, estadia["placa"]) for texto in achados]
        if novo["cpf"] != antes["cpf"] and not novo["saida"]:
            for (placa,) in con.execute(
                    "SELECT placa FROM estadias_veiculo WHERE saida = '' AND "
                    "cpf = ? AND registro_id IS NOT ?", (novo["cpf"], id_registro)):
                achados.append((f"{novo['nome']} passaria a constar no campus "
                                f"como dono do carro {formatar_placa(placa)}, "
                                "que está no estacionamento, e poderia sair "
                                "com ele.", placa))
        return achados

    def eventos_do_registro(self, id_registro):
        """Histórico de uma visita, do mais antigo para o mais recente."""
        with self._conexao() as con:
            linhas = con.execute("SELECT momento, usuario, acao, detalhe "
                                 "FROM auditoria WHERE registro_id = ? "
                                 "ORDER BY id", (id_registro,)).fetchall()
        return [self._formatar_evento(linha) for linha in linhas]

    def registros_do_periodo(self, desde, ate, autor):
        """
        Visitas com entrada entre os dias `desde` e `ate` (date, inclusive),
        em ordem de entrada, para a exportação (backup.exportar_csv). Leva
        CPF e celular completos: só administrador. O evento "Exportação de
        registros" é gravado por exportar_csv depois que o arquivo existe.
        """
        with self._conexao() as con:
            self._exigir(con, autor, para="exportar registros")
            linhas = con.execute(
                f"SELECT {COLUNAS_REGISTRO} FROM registros "
                "WHERE entrada >= ? AND entrada < ? ORDER BY entrada, id",
                (_dia_iso(desde), _dia_iso(ate + timedelta(days=1)))).fetchall()
        return [_registro(linha) for linha in linhas]

    def listar_abertas(self):
        """Visitas sem saída (quem está no campus), da entrada mais recente
        para a mais antiga: base do Painel (tempo excedido, pendentes)."""
        with self._conexao() as con:
            linhas = con.execute(f"SELECT {COLUNAS_REGISTRO} FROM registros "
                                 "WHERE saida = '' "
                                 "ORDER BY entrada DESC, id DESC").fetchall()
        return [_registro(linha) for linha in linhas]

    def encerrar_pendentes(self, agora, autor):
        """
        "Encerrar o dia" (só administrador): cada visita com SAÍDA PENDENTE
        no momento `agora` recebe a saída no prazo dela (horarios.prazo_saida:
        o fechamento do dia da entrada), com o evento "Saída automática
        (encerramento)". Tudo numa transação. Devolve [(id, nome, saída)].
        """
        encerradas = []
        with self._conexao() as con:
            self._exigir(con, autor, para="encerrar o dia")
            config = self._ler_configuracao(con)
            abertas = con.execute(f"SELECT {COLUNAS_REGISTRO} FROM registros "
                                  "WHERE saida = '' ORDER BY entrada, id")
            for r in [_registro(linha) for linha in abertas.fetchall()]:
                if horarios.situacao(config, r, agora) != horarios.SAIDA_PENDENTE:
                    continue
                prazo = horarios.prazo_saida(
                    config, r["tipo"], datetime.strptime(r["entrada"], FORMATO))
                saida = prazo.strftime(FORMATO_ISO)
                cursor = con.execute("UPDATE registros SET saida = ? WHERE "
                                     "id = ? AND saida = ''", (saida, r["id"]))
                if not cursor.rowcount:   # a saída real veio de outra estação
                    continue
                self._evento(con, autor, SAIDA_AUTOMATICA_ENCERRAMENTO,
                             f"#{r['id']} {r['nome']}: saída marcada em "
                             f"{de_iso(saida)}, prazo de saída do dia da "
                             "entrada.", r["id"])
                encerradas.append((r["id"], r["nome"], de_iso(saida)))
        return encerradas

    # --------------------------------------------------------------
    # Estadias de veículo (o carro no estacionamento)
    # --------------------------------------------------------------
    @staticmethod
    def _estadia_aberta(con, coluna, valor):
        """Estadia aberta pela placa, pelo CPF do responsável (a mais
        antiga), pelo id ou pela visita que a abriu, ou None."""
        linha = con.execute(f"SELECT {COLUNAS_ESTADIA} {DE_ESTADIAS} "
                            f"WHERE e.saida = '' AND e.{coluna} = ? "
                            "ORDER BY e.entrada LIMIT 1", (valor,)).fetchone()
        return _estadia(linha) if linha else None

    def estadia_aberta(self, placa=None, cpf=None):
        """O carro com essa placa (ou do responsável com esse CPF) que está
        no estacionamento agora, ou None."""
        with self._conexao() as con:
            if placa:
                return self._estadia_aberta(con, "placa", placa)
            return self._estadia_aberta(con, "cpf", cpf)

    def estadias_abertas_do_cpf(self, cpf):
        """Os carros desse responsável no estacionamento (pode haver mais
        de um: saiu a pé e voltou com outro), do mais antigo ao mais novo."""
        with self._conexao() as con:
            linhas = con.execute(f"SELECT {COLUNAS_ESTADIA} {DE_ESTADIAS} "
                                 "WHERE e.saida = '' AND e.cpf = ? "
                                 "ORDER BY e.entrada, e.id", (cpf,)).fetchall()
        return [_estadia(linha) for linha in linhas]

    def listar_estacionamento(self):
        """Veículos no estacionamento (estadias abertas), do mais recente
        para o mais antigo, com o tipo de acesso do responsável e se ele
        está no campus."""
        with self._conexao() as con:
            linhas = con.execute(f"SELECT {COLUNAS_ESTADIA} {DE_ESTADIAS} "
                                 "WHERE e.saida = '' "
                                 "ORDER BY e.entrada DESC, e.id DESC").fetchall()
        return [_estadia(linha) for linha in linhas]

    @classmethod
    def _abrir_estadia(cls, con, r, id_registro, autor):
        """A visita chegou com o carro: abre a estadia dele (fechada junto,
        se a visita já veio com saída). Placa já no estacionamento: recusa."""
        aberta = cls._estadia_aberta(con, "placa", r["placa"])
        if aberta is not None and not r.get("saida"):
            raise ErroDados(
                f"O veículo {formatar_placa(r['placa'])} já está no "
                f"estacionamento desde {aberta['entrada']} (responsável: "
                f"{aberta['nome']}).\nRegistre a saída dele pela placa ou "
                "deixe a placa vazia (entrada a pé).")
        saida = para_iso(r.get("saida", ""))
        con.execute(
            "INSERT INTO estadias_veiculo (placa, cpf, nome, pessoa_id, "
            "registro_id, entrada, saida, registro_saida_id, autor_entrada, "
            "autor_saida) SELECT ?, ?, ?, pessoa_id, id, entrada, saida, "
            "CASE WHEN saida <> '' THEN id END, ?, ? FROM registros "
            "WHERE id = ?",
            (r["placa"], r["cpf"], r["nome"], autor or AUTOR_SISTEMA,
             (autor or AUTOR_SISTEMA) if saida else "", id_registro))

    @classmethod
    def _conferir_lotacao(cls, con, registro, id_registro, autor, confirmado,
                          autorizacao):
        """RN37 conferida no banco: com o estacionamento lotado, a entrada
        de carro precisa da confirmação do aviso ou, com "Bloquear quando
        lotado", da senha de um administrador. Grava o evento."""
        config = cls._ler_configuracao(con)
        ocupadas = cls._ocupadas(con)
        if not veiculos.esta_lotado(ocupadas, config.vagas):
            return
        regra = veiculos.regra_lotado(ocupadas, config.vagas)
        placa = formatar_placa(registro["placa"])
        if config.bloquear_lotado:
            if autorizacao is None or not autorizacao.get("com_senha"):
                raise ErroDados(f"{regra}.\nA entrada do carro {placa} só "
                                "passa com a senha de um administrador.")
            cls._conferir_autorizacao(con, autorizacao)
            cls._evento(con, autorizacao["autorizado_por"], LOTACAO_LIBERADA,
                        f"#{id_registro} {registro['nome']}: entrada do carro "
                        f"{placa} com o {regra[0].lower()}{regra[1:]}. "
                        f"Justificativa: {autorizacao['justificativa']}. "
                        f"Operador: {autor or AUTOR_SISTEMA}. Senha do "
                        "administrador conferida.", id_registro)
            return
        if not confirmado:
            raise ErroDados(f"{regra}.\nConfirme a entrada do carro {placa} "
                            "mesmo assim.")
        cls._evento(con, autor, LOTACAO_CONFIRMADA,
                    f"#{id_registro} {registro['nome']}: carro {placa} entrou "
                    f"com o {regra[0].lower()}{regra[1:]} (aviso confirmado).",
                    id_registro)

    @classmethod
    def _corrigir_carro_que_ja_saiu(cls, con, id_estadia, registro, id_,
                                    autor, autorizacao):
        """RN40 "O BRA2E19 já saiu": a guarita esqueceu de registrar a
        saída do carro. Fecha a estadia (do MESMO CPF) com a senha do
        administrador; vai ao relatório de exceções."""
        estadia = cls._estadia_aberta(con, "id", id_estadia)
        if estadia is None:
            raise ErroDados("Esse carro já não está no estacionamento.\n"
                            "Atualize a tela e tente de novo.")
        if estadia["cpf"] != registro["cpf"]:
            raise ErroDados("Só o carro da própria pessoa pode ser marcado "
                            "como já saído na entrada dela.")
        cls._conferir_autorizacao_veiculo(con, autorizacao, estadia["placa"])
        entrada = con.execute("SELECT entrada FROM estadias_veiculo WHERE "
                              "id = ?", (id_estadia,)).fetchone()[0]
        saida = max(para_iso(registro["entrada"]), entrada)
        con.execute("UPDATE estadias_veiculo SET saida = ?, autor_saida = ? "
                    "WHERE id = ? AND saida = ''",
                    (saida, autor or AUTOR_SISTEMA, id_estadia))
        placa = formatar_placa(estadia["placa"])
        cls._evento(con, autorizacao["autorizado_por"], CARRO_JA_SAIU,
                    f"Placa {placa} de {estadia['nome']} (no estacionamento "
                    f"desde {estadia['entrada']}) já tinha saído sem registro; "
                    f"saída corrigida na entrada #{id_}. Justificativa: "
                    f"{autorizacao['justificativa']}. Operador: "
                    f"{autor or AUTOR_SISTEMA}. Senha do administrador "
                    "conferida.", estadia["registro_id"])

    @classmethod
    def _conferir_carros_da_pessoa(cls, con, registro, id_, autor,
                                   autorizacao):
        """RN40 conferida no banco: com MAXIMO_CARROS_POR_PESSOA carros da
        pessoa no estacionamento, mais um só com a senha do
        administrador."""
        abertos = [p for (p,) in con.execute(
            "SELECT placa FROM estadias_veiculo WHERE saida = '' AND cpf = ? "
            "ORDER BY entrada, id", (registro["cpf"],))]
        if not veiculos.precisa_senha_para_outro_carro(len(abertos)):
            return
        placas = ", ".join(formatar_placa(p) for p in abertos)
        if autorizacao is None or not autorizacao.get("com_senha"):
            raise ErroDados(
                f"{registro['nome']} já tem {len(abertos)} carros no "
                f"estacionamento ({placas}).\nOutro carro só entra com a "
                "senha de um administrador.")
        cls._conferir_autorizacao(con, autorizacao)
        cls._evento(con, autorizacao["autorizado_por"], OUTRO_CARRO_LIBERADO,
                    f"#{id_} {registro['nome']}: entrou com o carro "
                    f"{formatar_placa(registro['placa'])} tendo {placas} no "
                    f"estacionamento. Justificativa: "
                    f"{autorizacao['justificativa']}. Operador: "
                    f"{autor or AUTOR_SISTEMA}. Senha do administrador "
                    "conferida.", id_)

    @staticmethod
    def _ocupadas(con):
        return con.execute("SELECT COUNT(*) FROM estadias_veiculo "
                           "WHERE saida = ''").fetchone()[0]

    def ocupacao_estacionamento(self):
        """RN37: (carros no estacionamento, vagas, bloquear_lotado)."""
        with self._conexao() as con:
            config = self._ler_configuracao(con)
            return self._ocupadas(con), config.vagas, config.bloquear_lotado

    @staticmethod
    def _carro_do_dono(con, id_registro, cpf):
        """O carro de quem sai: o que entrou com esta visita ou, sem ele, o
        mais antigo dessa pessoa (saiu a pé e voltou). Sempre do mesmo CPF."""
        linha = con.execute(f"SELECT {COLUNAS_ESTADIA} {DE_ESTADIAS} "
                            "WHERE e.saida = '' AND e.cpf = ? "
                            "ORDER BY e.registro_id IS NOT ? , e.entrada, e.id "
                            "LIMIT 1", (cpf, id_registro)).fetchone()
        return _estadia(linha) if linha else None

    @classmethod
    def _sair_de_carro(cls, con, id_registro, saida, autor, id_estadia=None,
                       autorizacao=None):
        """Saída "de carro" de quem acabou de receber a saída nesta
        transação: fecha a estadia `id_estadia` ou, sem ela, o carro dessa
        pessoa. Se o carro escolhido é de OUTRO dono, só com a autorização
        de veículo (RN32), registrada como "Veículo saiu sem o dono"."""
        cpf, nome = con.execute("SELECT cpf, nome FROM registros WHERE id = ?",
                                (id_registro,)).fetchone()
        if id_estadia is None:
            estadia = cls._carro_do_dono(con, id_registro, cpf)
        else:
            estadia = cls._estadia_aberta(con, "id", id_estadia)
        if estadia is None:
            return
        sem_o_dono = estadia["cpf"] != cpf
        autorizado = None
        if sem_o_dono and autorizacao is None:          # RN35
            autorizado = cls._autorizado_a_levar(con, estadia["placa"], cpf,
                                                 id_registro, saida)
        if sem_o_dono and autorizado is None:
            cls._conferir_autorizacao_veiculo(con, autorizacao, estadia["placa"])
        con.execute("UPDATE estadias_veiculo SET saida = ?, autor_saida = ?, "
                    "registro_saida_id = ? WHERE id = ? AND saida = ''",
                    (saida, autor or AUTOR_SISTEMA, id_registro, estadia["id"]))
        placa = formatar_placa(estadia["placa"])
        cls._evento(con, autor, "Saída de veículo",
                    f"Placa {placa} saiu com {nome} (#{id_registro}).",
                    estadia["registro_id"])
        if autorizado is not None:
            cls._evento(con, autorizado["criado_por"], VEICULO_COM_AUTORIZADO,
                        f"Placa {placa} levada por {nome} (CPF {cpf}, "
                        f"#{id_registro}), autorizado por "
                        f"{autorizado['criado_por']} em "
                        f"{autorizado['criado_em'][:10]}; dono: "
                        f"{estadia['nome']} (CPF {estadia['cpf']}). Operador: "
                        f"{autor or AUTOR_SISTEMA}.", id_registro)
        elif sem_o_dono:
            cls._registrar_veiculo_sem_dono(
                con, autorizacao, autor,
                f"Placa {placa} saiu com {nome} (#{id_registro}); o dono é "
                f"{estadia['nome']} (CPF {estadia['cpf']}).",
                estadia["registro_id"])

    @classmethod
    def _autorizado_a_levar(cls, con, placa, cpf, id_registro, saida):
        """RN35: a linha da lista que deixa `cpf` (a visita `id_registro`,
        que acabou de receber a saída) levar o carro `placa` sem o dono e
        sem senha, ou None (aí vale a RN32)."""
        dia = datetime.strptime(saida, FORMATO_ISO).date()
        visita_a_pe = con.execute("SELECT placa = '' FROM registros "
                                  "WHERE id = ?", (id_registro,)).fetchone()[0]
        desativada = con.execute("SELECT 1 FROM bloqueios WHERE tipo = 'cpf' "
                                 "AND valor = ? AND ativo = 1",
                                 (cpf,)).fetchone() is not None
        for linha in con.execute(f"SELECT {COLUNAS_AUTORIZADO} FROM "
                                 "autorizados_veiculo WHERE placa = ? AND "
                                 "cpf = ? AND ativo = 1", (placa, cpf)):
            autorizado = _autorizado(linha)
            ok, _ = veiculos.pode_levar(autorizado, dia, bool(visita_a_pe),
                                        desativada)
            if ok:
                return autorizado
        return None

    def registrar_saida_veiculo(self, id_estadia, saida, autor=None,
                                autorizacao=None):
        """
        Só o carro sai (saída pela placa ou pela lista de veículos): o dono
        não sai nesta operação, então é sempre "Veículo saiu sem o dono" e
        precisa da `autorizacao` de um administrador com a senha (RN32).
        Quando o dono sai junto, a tela usa registrar_saidas com o carro.
        False se o carro já tinha saído (nada a autorizar).
        """
        saida_iso = para_iso(saida)
        autorizacao = self._autorizacao_conferida(autorizacao, autor)
        with self._conexao() as con:
            self._conferir_autor(con, autor)
            estadia = self._estadia_aberta(con, "id", id_estadia)
            if estadia is None:
                return False
            self._conferir_autorizacao_veiculo(con, autorizacao,
                                               estadia["placa"])
            con.execute("UPDATE estadias_veiculo SET saida = ?, autor_saida = ? "
                        "WHERE id = ?", (saida_iso, autor or AUTOR_SISTEMA,
                                         id_estadia))
            placa = formatar_placa(estadia["placa"])
            self._evento(con, autor, "Saída de veículo",
                         f"Placa {placa} saiu (responsável: {estadia['nome']}).",
                         estadia["registro_id"])
            onde = ("continua no campus" if estadia["responsavel_dentro"]
                    else "está fora do campus")
            self._registrar_veiculo_sem_dono(
                con, autorizacao, autor,
                f"Placa {placa} saiu sem o dono, {estadia['nome']} (CPF "
                f"{estadia['cpf']}), que {onde}.", estadia["registro_id"])
            return True

    def desfazer_saida_veiculos(self, ids, saida, autor=None):
        """Desfaz a saída só do carro (botão Desfazer). Devolve quantas."""
        with self._conexao() as con:
            self._conferir_autor(con, autor)
            return sum(self._reabrir_estadias(con, "id = ?", i, para_iso(saida),
                                              autor) for i in ids)

    @classmethod
    def _reabrir_estadias(cls, con, condicao, valor, saida, autor):
        """Volta para o estacionamento as estadias da condição que saíram
        em `saida`, se a placa não tiver entrado de novo nesse meio-tempo."""
        reabertas = 0
        for id_, placa, registro_id in con.execute(
                "SELECT id, placa, registro_id FROM estadias_veiculo "
                f"WHERE {condicao} AND saida = ?", (valor, saida)).fetchall():
            cursor = con.execute(
                "UPDATE estadias_veiculo SET saida = '', autor_saida = '', "
                "registro_saida_id = NULL WHERE id = ? AND NOT EXISTS (SELECT 1 "
                "FROM estadias_veiculo o WHERE o.placa = ? AND o.saida = '')",
                (id_, placa))
            if cursor.rowcount:
                reabertas += 1
                cls._evento(con, autor, "Saída de veículo desfeita",
                            f"Placa {formatar_placa(placa)}", registro_id)
        return reabertas

    @classmethod
    def _sincronizar_estadia(cls, con, id_registro, novo, placa_da_visita,
                             pessoa, autor):
        """
        Correção de uma visita mantém o carro dela coerente:
        - estadia aberta por ela e placa apagada: era erro de digitação,
          a estadia sai (fica no histórico);
        - estadia aberta e placa ou entrada mudaram: corrige a estadia;
        - visita aberta que ganhou placa: abre a estadia.
        Estadia já fechada só acompanha o responsável (CPF digitado errado).
        """
        # o responsável acompanha a visita, mesmo nas estadias já fechadas
        con.execute("UPDATE estadias_veiculo SET cpf = ?, nome = ?, "
                    "pessoa_id = ? WHERE registro_id = ?",
                    (novo["cpf"], novo["nome"], pessoa, id_registro))
        linha = con.execute("SELECT id, placa, saida FROM estadias_veiculo "
                            "WHERE registro_id = ? ORDER BY id DESC LIMIT 1",
                            (id_registro,)).fetchone()
        placa = novo["placa"]
        if linha is None:
            # só se a placa foi digitada agora (visita antiga, de carona,
            # pode ter placa sem estadia)
            if placa and placa != placa_da_visita and not novo["saida"]:
                cls._conferir_carros_da_pessoa(con, novo, id_registro, autor,
                                               None)
                cls._abrir_estadia(con, novo, id_registro, autor)
            return
        id_estadia, placa_antiga, saida = linha
        if saida:
            return
        if not placa:
            con.execute("DELETE FROM estadias_veiculo WHERE id = ?", (id_estadia,))
            cls._evento(con, autor, "Estadia de veículo removida",
                        f"Placa {formatar_placa(placa_antiga)} apagada na "
                        "correção da visita.", id_registro)
            return
        if placa != placa_antiga:
            aberta = cls._estadia_aberta(con, "placa", placa)
            if aberta is not None:
                raise ErroDados(f"O veículo {formatar_placa(placa)} já está no "
                                f"estacionamento desde {aberta['entrada']}.")
        con.execute("UPDATE estadias_veiculo SET placa = ?, entrada = ? "
                    "WHERE id = ?", (placa, para_iso(novo["entrada"]), id_estadia))

    # --------------------------------------------------------------
    # Quem pode retirar o veículo (RN35)
    # --------------------------------------------------------------
    def listar_autorizados(self, placa, incluir_removidos=False):
        """Lista da placa: ativos primeiro, mais recentes primeiro."""
        filtro = "" if incluir_removidos else " AND ativo = 1"
        with self._conexao() as con:
            linhas = con.execute(f"SELECT {COLUNAS_AUTORIZADO} FROM "
                                 f"autorizados_veiculo WHERE placa = ?{filtro} "
                                 "ORDER BY ativo DESC, id DESC",
                                 (placa,)).fetchall()
        return [_autorizado(linha) for linha in linhas]

    def adicionar_autorizado(self, dono_cpf, cpf, nome, valido_ate, autor):
        """
        Põe `cpf`/`nome` na lista de quem pode retirar o carro de `dono_cpf`
        (a placa cadastrada dele), com validade opcional (date ou None).
        RN35: o porteiro só cadastra com o dono no campus agora; o
        administrador, a qualquer hora. O histórico grava quem cadastrou e
        se o dono estava presente. Devolve o id.
        """
        nome = " ".join((nome or "").split())
        _exigir_tamanho("Nome completo", nome, MAXIMO_NOME)
        _exigir_tamanho("CPF", cpf, MAXIMO_CPF)
        with self._conexao() as con:
            usuario = self._exigir(con, autor, so_admin=False)
            dono = con.execute("SELECT placa, nome FROM pessoas WHERE cpf = ?",
                               (dono_cpf,)).fetchone()
            if dono is None:
                raise ErroDados("O dono do veículo não está cadastrado.")
            placa, nome_dono = dono
            presente = con.execute("SELECT 1 FROM registros WHERE cpf = ? "
                                   "AND saida = ''",
                                   (dono_cpf,)).fetchone() is not None
            ok, msg = veiculos.pode_cadastrar_autorizado(
                usuario["perfil"] == "admin", presente)
            if not ok:
                raise ErroDados(msg)
            agora = self.relogio()
            ok, msg = veiculos.conferir_autorizado(placa, dono_cpf, cpf, nome,
                                                   valido_ate, agora.date())
            if not ok:
                raise ErroDados(msg)
            if con.execute("SELECT 1 FROM autorizados_veiculo WHERE placa = ? "
                           "AND cpf = ? AND ativo = 1",
                           (placa, cpf)).fetchone():
                raise ErroDados(f"{nome} já está na lista de quem pode "
                                f"retirar o carro {formatar_placa(placa)}.")
            cursor = con.execute(
                "INSERT INTO autorizados_veiculo (placa, dono_cpf, cpf, nome, "
                "valido_ate, dono_presente, criado_por, criado_em) VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?)",
                (placa, dono_cpf, cpf, nome, veiculos.dia_iso(valido_ate),
                 int(presente), autor, agora.strftime(FORMATO_ISO)))
            self._evento(con, autor, AUTORIZADO_ADICIONADO,
                         f"Placa {formatar_placa(placa)} de {nome_dono}: "
                         f"{nome} (CPF {cpf}) pode retirar, "
                         f"{veiculos.descrever_validade(valido_ate)}; dono "
                         + ("presente no campus." if presente
                            else "fora do campus (cadastro do administrador)."))
            return cursor.lastrowid

    def remover_autorizado(self, id_autorizado, autor):
        """Remoção lógica (fica guardado quem removeu e quando). Qualquer
        usuário remove: remover só diminui a permissão."""
        with self._conexao() as con:
            self._exigir(con, autor, so_admin=False)
            linha = con.execute("SELECT placa, nome, cpf FROM "
                                "autorizados_veiculo WHERE id = ? AND "
                                "ativo = 1", (id_autorizado,)).fetchone()
            if linha is None:
                raise ErroDados("Esta autorização já tinha sido removida.")
            con.execute("UPDATE autorizados_veiculo SET ativo = 0, "
                        "removido_em = ?, removido_por = ? WHERE id = ?",
                        (self.relogio().strftime(FORMATO_ISO), autor,
                         id_autorizado))
            self._evento(con, autor, AUTORIZADO_REMOVIDO,
                         f"Placa {formatar_placa(linha[0])}: {linha[1]} (CPF "
                         f"{linha[2]}) não pode mais retirar o carro.")

    def contar_autorizados(self, dia):
        """{placa: quantos podem retirar o carro no dia} (aba Veículos)."""
        with self._conexao() as con:
            return dict(con.execute(
                "SELECT placa, COUNT(*) FROM autorizados_veiculo WHERE "
                "ativo = 1 AND (valido_ate = '' OR valido_ate >= ?) "
                "GROUP BY placa", (dia.isoformat(),)).fetchall())

    def veiculos_que_pode_levar(self, cpf, dia):
        """Carros no estacionamento que `cpf` pode levar sem o dono (RN35),
        cada um com o "autorizado" (a linha da lista). Vazio se a pessoa
        está desativada. Sem os carros dela mesma."""
        with self._conexao() as con:
            if con.execute("SELECT 1 FROM bloqueios WHERE tipo = 'cpf' AND "
                           "valor = ? AND ativo = 1", (cpf,)).fetchone():
                return []
            estadias = [_estadia(linha) for linha in con.execute(
                f"SELECT {COLUNAS_ESTADIA} {DE_ESTADIAS} WHERE e.saida = '' "
                "AND e.cpf <> ? ORDER BY e.entrada, e.id", (cpf,))]
            levaveis = []
            for estadia in estadias:
                for linha in con.execute(
                        f"SELECT {COLUNAS_AUTORIZADO} FROM autorizados_veiculo "
                        "WHERE placa = ? AND cpf = ? AND ativo = 1",
                        (estadia["placa"], cpf)):
                    autorizado = _autorizado(linha)
                    if veiculos.autorizacao_vale(autorizado, dia):
                        levaveis.append(dict(estadia, autorizado=autorizado))
                        break
        return levaveis

    def autorizados_no_campus(self, placa, dia):
        """RN35: quem da lista da placa está no campus a pé agora (pode
        levar o carro), com a visita aberta; sem as pessoas desativadas."""
        with self._conexao() as con:
            linhas = con.execute(
                f"SELECT {COLUNAS_AUTORIZADO_A}, r.id FROM autorizados_veiculo a "
                "JOIN registros r ON r.cpf = a.cpf AND r.saida = '' "
                "AND r.placa = '' WHERE a.placa = ? AND a.ativo = 1 "
                "AND NOT EXISTS (SELECT 1 FROM bloqueios b WHERE b.tipo = 'cpf' "
                "AND b.valor = a.cpf AND b.ativo = 1) ORDER BY a.nome",
                (placa,)).fetchall()
        no_campus = []
        for linha in linhas:
            autorizado = _autorizado(linha[:-1])
            if veiculos.autorizacao_vale(autorizado, dia):
                no_campus.append(dict(autorizado, registro_id=linha[-1]))
        return no_campus

    # --------------------------------------------------------------
    # Configuração dos horários de acesso (página Configurações)
    # --------------------------------------------------------------
    def ler_configuracao(self):
        """A configuração em vigor (horarios.Configuracao)."""
        with self._conexao() as con:
            return self._ler_configuracao(con)

    @staticmethod
    def _ler_configuracao(con):
        padrao = horarios.configuracao_padrao()
        funcionamento = dict(padrao.funcionamento)
        for dia, abre, fecha in con.execute("SELECT dia, abre, fecha "
                                            "FROM funcionamento"):
            funcionamento[dia] = _horario_do_banco(abre, fecha)
        regras = dict(padrao.regras)
        for (tipo, relativa, antes, depois, j_abre, j_fecha, ate_fechamento,
             minutos, tolerancia) in con.execute(
                "SELECT tipo, relativa, abre_antes, fecha_depois, janela_abre, "
                "janela_fecha, ate_fechamento, permanencia_min, tolerancia_min "
                "FROM regras_categoria"):
            regras[tipo] = horarios.RegraCategoria(
                bool(relativa), antes, depois, _horario_do_banco(j_abre, j_fecha),
                bool(ate_fechamento), minutos, tolerancia)
        feriados = {date.fromisoformat(dia): descricao for dia, descricao
                    in con.execute("SELECT data, descricao FROM feriados")}
        eventos = {}
        for dia, abre, fecha, descricao in con.execute(
                "SELECT data, abre, fecha, descricao FROM eventos"):
            eventos[date.fromisoformat(dia)] = horarios.Evento(
                date.fromisoformat(dia), _horario_do_banco(abre, fecha),
                descricao)
        parametros = _parametros(padrao)
        parametros.update(con.execute("SELECT chave, valor FROM parametros"))
        return horarios.Configuracao(
            funcionamento, regras, feriados, eventos,
            parametros["minutos_aviso"], parametros["horas_retroativo"],
            parametros.get("vagas", 0),
            bool(parametros.get("bloquear_lotado", 0)))

    def salvar_funcionamento(self, funcionamento, autor):
        """{dia: Horario ou None}; grava e registra só os dias que mudaram.
        Devolve quantos mudaram."""
        with self._conexao() as con:
            self._exigir(con, autor, para="alterar as configurações")
            antes = self._ler_configuracao(con).funcionamento
            mudancas = []
            for dia, horario in sorted(funcionamento.items()):
                if horario == antes.get(dia):
                    continue
                con.execute("UPDATE funcionamento SET abre = ?, fecha = ? "
                            "WHERE dia = ?", (*_horario_iso(horario), dia))
                mudancas.append(
                    f"{horarios.DIAS_SEMANA[dia]}: "
                    f"{horarios.descrever_horario(antes.get(dia))} → "
                    f"{horarios.descrever_horario(horario)}")
            self._evento_de_configuracao(con, autor, "Funcionamento", mudancas)
            return len(mudancas)

    def salvar_regras(self, regras, autor):
        """{tipo: RegraCategoria}; grava e registra só as que mudaram."""
        with self._conexao() as con:
            self._exigir(con, autor, para="alterar as configurações")
            antes = self._ler_configuracao(con).regras
            mudancas = []
            for tipo, regra in regras.items():
                if regra == antes.get(tipo):
                    continue
                con.execute("INSERT OR REPLACE INTO regras_categoria "
                            + _COLUNAS_REGRA, (tipo, *_regra_iso(regra)))
                mudancas.append(horarios.descrever_regra(tipo, regra))
            self._evento_de_configuracao(con, autor, "Regras por categoria",
                                         mudancas)
            return len(mudancas)

    def salvar_parametros(self, minutos_aviso, horas_retroativo, autor):
        """Minutos do aviso antes de fechar e limite da entrada retroativa."""
        novos = {"minutos_aviso": minutos_aviso,
                 "horas_retroativo": horas_retroativo}
        rotulos = {"minutos_aviso": ("Aviso antes de fechar", "min"),
                   "horas_retroativo": ("Lançamento retroativo", "h")}
        with self._conexao() as con:
            self._exigir(con, autor, para="alterar as configurações")
            antes = _parametros(self._ler_configuracao(con))
            mudancas = []
            for chave, valor in novos.items():
                if valor == antes[chave]:
                    continue
                con.execute("INSERT OR REPLACE INTO parametros (chave, valor) "
                            "VALUES (?, ?)", (chave, int(valor)))
                rotulo, unidade = rotulos[chave]
                mudancas.append(f"{rotulo}: {antes[chave]} → {valor} {unidade}")
            self._evento_de_configuracao(con, autor, "Avisos e limites",
                                         mudancas)
            return len(mudancas)

    def salvar_lotacao(self, vagas, bloquear, autor):
        """RN37: vagas do estacionamento (0 = sem controle, até 4 dígitos)
        e se a entrada com ele lotado pede a senha do administrador."""
        if (not isinstance(vagas, int) or isinstance(vagas, bool)
                or not 0 <= vagas <= veiculos.MAXIMO_VAGAS):
            raise ErroDados(f"Vagas do estacionamento: de 0 a "
                            f"{veiculos.MAXIMO_VAGAS}.")
        novos = {"vagas": vagas, "bloquear_lotado": int(bool(bloquear))}
        sim_nao = {0: "não", 1: "sim"}
        with self._conexao() as con:
            self._exigir(con, autor, para="alterar as configurações")
            config = self._ler_configuracao(con)
            antes = {"vagas": config.vagas,
                     "bloquear_lotado": int(config.bloquear_lotado)}
            mudancas = []
            for chave, valor in novos.items():
                if valor == antes[chave]:
                    continue
                con.execute("INSERT OR REPLACE INTO parametros (chave, valor) "
                            "VALUES (?, ?)", (chave, valor))
                if chave == "vagas":
                    mudancas.append(f"Vagas: {antes[chave]} → {valor}")
                else:
                    mudancas.append(f"Bloquear quando lotado: "
                                    f"{sim_nao[antes[chave]]} → {sim_nao[valor]}")
            self._evento_de_configuracao(con, autor, "Estacionamento", mudancas)
            return len(mudancas)

    def adicionar_feriado(self, dia, descricao, autor):
        _exigir_tamanho("Descrição", descricao.strip(), MAXIMO_DESCRICAO)
        with self._conexao() as con:
            self._exigir(con, autor, para="alterar as configurações")
            con.execute("INSERT INTO feriados (data, descricao) VALUES (?, ?)",
                        (dia.isoformat(), descricao.strip()))
            self._evento_de_configuracao(
                con, autor, "Feriado adicionado",
                [f"{dia:{horarios.FORMATO_DATA}} — {descricao.strip()}"])

    def remover_feriado(self, dia, autor):
        with self._conexao() as con:
            self._exigir(con, autor, para="alterar as configurações")
            linha = con.execute("SELECT descricao FROM feriados WHERE data = ?",
                                (dia.isoformat(),)).fetchone()
            if linha is None:
                raise ErroDados("Este feriado já foi removido.")
            con.execute("DELETE FROM feriados WHERE data = ?", (dia.isoformat(),))
            self._evento_de_configuracao(
                con, autor, "Feriado removido",
                [f"{dia:{horarios.FORMATO_DATA}} — {linha[0]}"])

    def adicionar_evento(self, evento, autor):
        _exigir_tamanho("Descrição", evento.descricao, MAXIMO_DESCRICAO)
        with self._conexao() as con:
            self._exigir(con, autor, para="alterar as configurações")
            con.execute("INSERT INTO eventos (data, abre, fecha, descricao) "
                        "VALUES (?, ?, ?, ?)",
                        (evento.data.isoformat(), *_horario_iso(evento.horario),
                         evento.descricao))
            self._evento_de_configuracao(con, autor, "Evento adicionado",
                                         [_descrever_evento(evento)])

    def remover_evento(self, dia, autor):
        with self._conexao() as con:
            self._exigir(con, autor, para="alterar as configurações")
            evento = self._ler_configuracao(con).eventos.get(dia)
            if evento is None:
                raise ErroDados("Este evento já foi removido.")
            con.execute("DELETE FROM eventos WHERE data = ?", (dia.isoformat(),))
            self._evento_de_configuracao(con, autor, "Evento removido",
                                         [_descrever_evento(evento)])

    @classmethod
    def _evento_de_configuracao(cls, con, autor, assunto, mudancas):
        if mudancas:
            cls._evento(con, autor, "Configuração alterada",
                        f"{assunto}: " + "; ".join(mudancas))

    # --------------------------------------------------------------
    # Desativação de pessoa (CPF) e de veículo (placa) — RN12
    # --------------------------------------------------------------
    def listar_desativacoes(self, incluir_reativadas=False, tipo=None):
        """
        Desativações (as em vigor primeiro, mais recentes primeiro), só de
        um `tipo` ("cpf" ou "placa") se informado. Cada uma traz o nome e o
        id da pessoa: a dona do CPF (CPF sem cadastro: nome "" e pessoa_id
        None, aparece como "(sem cadastro)") ou, na placa, quem tem aquela
        placa cadastrada.
        """
        condicoes = ([] if incluir_reativadas else ["b.ativo = 1"]) + (
            ["b.tipo = ?"] if tipo else [])
        filtro = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""
        with self._conexao() as con:
            linhas = con.execute(
                "SELECT b.id, b.tipo, b.valor, b.motivo, b.criado_em, "
                "b.criado_por, b.ativo, b.removido_em, b.removido_por, "
                "COALESCE(p.nome, ''), p.id FROM bloqueios b "
                "LEFT JOIN pessoas p ON p.id = (SELECT q.id FROM pessoas q "
                "WHERE (b.tipo = 'cpf' AND q.cpf = b.valor) OR "
                "(b.tipo = 'placa' AND q.placa = b.valor) "
                "ORDER BY q.id LIMIT 1) "
                f"{filtro} ORDER BY b.ativo DESC, b.id DESC",
                (tipo,) if tipo else ()).fetchall()
        return [{"id": i, "tipo": tipo_, "valor": valor, "motivo": motivo,
                 "criado_em": de_iso(criado), "criado_por": por,
                 "ativo": bool(ativo), "reativado_em": de_iso(removido),
                 "reativado_por": removido_por, "nome": nome,
                 "pessoa_id": pessoa_id}
                for (i, tipo_, valor, motivo, criado, por, ativo, removido,
                     removido_por, nome, pessoa_id) in linhas]

    @staticmethod
    def _desativacoes_que_pegam(con, cpf, placa):
        """As desativações em vigor do CPF ou da placa (para conferir)."""
        linhas = con.execute(
            "SELECT tipo, valor, motivo, criado_em, criado_por FROM bloqueios "
            "WHERE ativo = 1 AND ((tipo = 'cpf' AND valor = ?) OR "
            "(tipo = 'placa' AND valor = ?))", (cpf or "", placa or "")
        ).fetchall()
        return [{"tipo": t, "valor": v, "motivo": m, "criado_em": de_iso(c),
                 "criado_por": por} for t, v, m, c, por in linhas]

    @classmethod
    def _conferir_desativacao(cls, con, registro, original=None):
        """RN12 no banco: a pessoa (CPF) ou o veículo (placa) desativado
        não entra; na correção (`original`), só se a mudança o põe no
        campus (validacao.checar_desativacao_correcao)."""
        ativas = cls._desativacoes_que_pegam(con, registro.get("cpf"),
                                             registro.get("placa"))
        if not ativas:
            return
        ok, msg = (validacao.checar_desativacao_correcao(original, registro,
                                                         ativas)
                   if original is not None
                   else validacao.checar_desativacao(registro, ativas))
        if not ok:
            raise ErroDados(msg)

    def desativar(self, tipo, valor, motivo, autor):
        """
        Desativa a pessoa (tipo "cpf") ou o veículo ("placa"): a entrada
        passa a ser recusada. Só o administrador (RN12); o banco confere
        de novo o CPF/placa, o motivo e se já não está desativado.
        Devolve o id.
        """
        motivo = " ".join((motivo or "").split())
        _exigir_tamanho("CPF ou placa", valor or "",
                        MAXIMO_CPF if tipo == "cpf" else MAXIMO_PLACA)
        _exigir_tamanho("Motivo", motivo, MAXIMO_MOTIVO)
        with self._conexao() as con:
            self._exigir(con, autor, para="desativar pessoas ou veículos")
            ativas = self._desativacoes_que_pegam(
                con, valor if tipo == "cpf" else "",
                valor if tipo == "placa" else "")
            ok, msg = validacao.validar_desativacao(tipo, valor, motivo, ativas)
            if not ok:
                raise ErroDados(msg)
            nome = con.execute(
                "SELECT nome FROM pessoas WHERE "
                + ("cpf = ?" if tipo == "cpf" else "placa = ?")
                + " ORDER BY id LIMIT 1", (valor,)).fetchone()
            cursor = con.execute(
                "INSERT INTO bloqueios (tipo, valor, motivo, criado_em, criado_por) "
                "VALUES (?, ?, ?, ?, ?)",
                (tipo, valor, motivo, self.relogio().strftime(FORMATO_ISO),
                 autor))
            quem = f" ({nome[0]})" if nome else (
                " (sem cadastro)" if tipo == "cpf" else "")
            self._evento(con, autor, DESATIVADA[tipo],
                         f"{TIPOS_DESATIVACAO[tipo]} "
                         f"{validacao.formatar_desativacao(tipo, valor)}"
                         f"{quem} — {motivo}")
            return cursor.lastrowid

    def reativar(self, id_desativacao, autor):
        """Reativa (a entrada volta a ser permitida). Só o administrador;
        a desativação fica guardada com quem reativou e quando."""
        with self._conexao() as con:
            self._exigir(con, autor, para="reativar pessoas ou veículos")
            linha = con.execute("SELECT tipo, valor FROM bloqueios "
                                "WHERE id = ? AND ativo = 1",
                                (id_desativacao,)).fetchone()
            if linha is None:
                raise ErroDados("Esta desativação não está mais em vigor "
                                "(já foi reativada).")
            tipo, valor = linha
            con.execute("UPDATE bloqueios SET ativo = 0, removido_em = ?, "
                        "removido_por = ? WHERE id = ?",
                        (self.relogio().strftime(FORMATO_ISO), autor,
                         id_desativacao))
            self._evento(con, autor, REATIVADA[tipo],
                         f"{TIPOS_DESATIVACAO[tipo]} "
                         f"{validacao.formatar_desativacao(tipo, valor)}")

    # --------------------------------------------------------------
    # Pessoas
    # --------------------------------------------------------------
    @staticmethod
    def _pessoa(linha):
        i, cpf, nome, cel, placa, tipo, visitas, ultima, aberta = linha
        return {"id": i, "cpf": cpf, "nome": nome, "celular": cel,
                "placa": placa, "tipo": tipo, "visitas": visitas,
                "ultima_visita": de_iso(ultima or ""),
                "dentro_desde": de_iso(aberta or "")}

    def listar_pessoas(self):
        """Pessoas em ordem alfabética, com nº de visitas e se estão no campus."""
        with self._conexao() as con:
            linhas = con.execute(SELECT_PESSOAS + " GROUP BY p.id "
                                 "ORDER BY p.nome COLLATE NOCASE").fetchall()
        return [self._pessoa(linha) for linha in linhas]

    def buscar_pessoas(self, texto, limite=200, so_cpf_completo=False,
                       so_ativas=False):
        """
        Aba Pessoas sem carregar todo mundo: mesmo critério de
        consultas.filtrar (nome, tipo, placa; CPF e celular pelos dígitos),
        em ordem alfabética, no máximo `limite`. Passando do limite, quem
        está no campus entra primeiro (a lista abre ordenada pela situação).
        so_cpf_completo: ver _condicao_busca (porteiro).
        so_ativas: sem as pessoas desativadas (subaba Ativas, 2.3).
        """
        condicao, params = _condicao_busca(
            texto, "pessoas", COLUNAS_BUSCA, so_cpf_completo)
        if so_ativas:
            condicao = " AND ".join(c for c in (condicao, (
                "NOT EXISTS (SELECT 1 FROM bloqueios b WHERE b.tipo = 'cpf' "
                "AND b.valor = pessoas.cpf AND b.ativo = 1)")) if c)
        where = f"WHERE {condicao}" if condicao else ""
        with self._conexao() as con:
            linhas = con.execute(
                SELECT_PESSOAS + " WHERE p.id IN (SELECT id FROM pessoas "
                f"{where} ORDER BY NOT EXISTS (SELECT 1 FROM registros d "
                "WHERE d.pessoa_id = pessoas.id AND d.saida = ''), "
                "nome COLLATE NOCASE LIMIT ?) "
                "GROUP BY p.id ORDER BY p.nome COLLATE NOCASE",
                (*params, int(limite))).fetchall()
        return [self._pessoa(linha) for linha in linhas]

    def visitas_da_pessoa(self, id_pessoa, limite=200):
        """Visitas da pessoa (ficha da página Pessoas), da mais recente
        para a mais antiga, com os dados preenchidos em cada uma."""
        with self._conexao() as con:
            linhas = con.execute(f"SELECT {COLUNAS_REGISTRO} FROM registros "
                                 "WHERE pessoa_id = ? "
                                 "ORDER BY entrada DESC, id DESC LIMIT ?",
                                 (id_pessoa, int(limite))).fetchall()
        return [_registro(linha) for linha in linhas]

    def buscar_pessoa(self, cpf):
        """Pessoa já cadastrada com esse CPF, ou None."""
        with self._conexao() as con:
            linha = con.execute(SELECT_PESSOAS + " WHERE p.cpf = ? GROUP BY p.id",
                                (cpf,)).fetchone()
        return self._pessoa(linha) if linha else None

    def cadastrar_pessoa(self, cpf, nome, celular, placa, tipo, autor):
        """
        "Nova pessoa" (2.3): cadastra SEM registrar entrada. Mesma
        validação e mesmos limites da entrada (validacao.validar_campos,
        conferida de novo aqui); CPF já cadastrado é recusado. Qualquer
        usuário ativo cadastra (o porteiro já cadastra na entrada). CPF
        desativado pode ser cadastrado: continua desativado. Devolve o id.
        """
        dados = {"nome": " ".join((nome or "").split()), "cpf": cpf or "",
                 "celular": celular or "", "placa": (placa or "").upper(),
                 "tipo": tipo}
        _exigir_tamanho("CPF", dados["cpf"], MAXIMO_CPF)
        _exigir_tamanhos_da_visita(dados)
        ok, msg = validacao.validar_campos(dados)
        if not ok:
            raise ErroDados(msg)
        with self._conexao() as con:
            self._exigir(con, autor, so_admin=False)
            existente = con.execute("SELECT nome FROM pessoas WHERE cpf = ?",
                                    (dados["cpf"],)).fetchone()
            if existente:
                raise ErroDados(f"Este CPF já está cadastrado "
                                f"({existente[0]}).")
            cursor = con.execute(
                "INSERT INTO pessoas (cpf, nome, celular, placa, tipo) "
                "VALUES (?, ?, ?, ?, ?)",
                (dados["cpf"], dados["nome"], dados["celular"], dados["placa"],
                 dados["tipo"]))
            self._evento(con, autor, PESSOA_CADASTRADA,
                         f"{dados['nome']} (pessoa #{cursor.lastrowid}), sem "
                         "entrada")
            return cursor.lastrowid

    def atualizar_pessoa(self, id_pessoa, nome, celular, placa, tipo, autor=None):
        """Corrige o cadastro da pessoa (as visitas antigas não mudam). O
        banco confere de novo os campos (validacao.validar_campos)."""
        _exigir_tamanhos_da_visita({"nome": nome, "celular": celular,
                                    "placa": placa})
        with self._conexao() as con:
            self._conferir_autor(con, autor)
            linha = con.execute("SELECT cpf FROM pessoas WHERE id = ?",
                                (id_pessoa,)).fetchone()
            if linha is None:
                raise ErroDados("Esta pessoa não está mais cadastrada.")
            ok, msg = validacao.validar_campos(
                {"nome": nome, "cpf": linha[0], "celular": celular,
                 "placa": placa, "tipo": tipo})
            if not ok:
                raise ErroDados(msg)
            con.execute("UPDATE pessoas SET nome = ?, celular = ?, placa = ?, "
                        "tipo = ? WHERE id = ?",
                        (nome, celular, placa, tipo, id_pessoa))
            self._evento(con, autor, "Dados de pessoa alterados",
                         f"{nome} (pessoa #{id_pessoa})")

    # --------------------------------------------------------------
    # Usuários
    # --------------------------------------------------------------
    def tem_usuarios(self):
        with self._conexao() as con:
            return con.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone() is not None

    def listar_usuarios(self):
        with self._conexao() as con:
            linhas = con.execute("SELECT id, login, nome, perfil, ativo "
                                 "FROM usuarios ORDER BY login").fetchall()
        return [{"id": i, "login": login, "nome": nome, "perfil": perfil,
                 "ativo": bool(ativo)}
                for i, login, nome, perfil, ativo in linhas]

    def buscar_usuario(self, login):
        """Usuário com o hash da senha (só para conferir o login), ou None."""
        with self._conexao() as con:
            linha = con.execute("SELECT id, login, nome, perfil, senha, ativo, "
                                "tema, trocar_senha FROM usuarios "
                                "WHERE login = ?", (login,)).fetchone()
        if linha is None:
            return None
        i, login, nome, perfil, senha, ativo, tema, trocar = linha
        return {"id": i, "login": login, "nome": nome, "perfil": perfil,
                "senha": senha, "ativo": bool(ativo), "tema": tema,
                "trocar_senha": bool(trocar)}

    def definir_tema(self, tema, autor):
        """Cada usuário escolhe o PRÓPRIO tema (vale nos próximos logins).
        Não vai para o histórico: é preferência de tela, não ação na
        portaria."""
        if tema not in TEMAS:
            raise ErroDados("Tema desconhecido.", detalhe=repr(tema))
        with self._conexao() as con:
            self._exigir(con, autor, so_admin=False)
            con.execute("UPDATE usuarios SET tema = ? WHERE login = ?",
                        (tema, autor))

    def criar_usuario(self, nome, login, perfil, senha_hash, autor=None,
                      trocar_senha=None):
        """
        Com autor: só administrador. Sem autor = primeiro acesso, aceito só
        com a tabela de usuários vazia. A condição fica no próprio INSERT:
        duas estações no "Primeiro acesso" não criam dois usuários.
        RN39: quem o administrador cria define a própria senha no primeiro
        login (trocar_senha; o padrão é "criado por alguém"); o
        administrador do primeiro acesso escolheu a dele e não troca.
        """
        if trocar_senha is None:
            trocar_senha = autor is not None
        _exigir_tamanho("Nome completo", nome, MAXIMO_NOME)
        _exigir_tamanho("Usuário", login, MAXIMO_LOGIN)
        with self._conexao() as con:
            if autor is None:
                cursor = con.execute(
                    "INSERT INTO usuarios (login, nome, perfil, senha, "
                    "trocar_senha) SELECT ?, ?, ?, ?, ? WHERE NOT EXISTS "
                    "(SELECT 1 FROM usuarios)",
                    (login, nome, perfil, senha_hash, int(trocar_senha)))
                if not cursor.rowcount:
                    raise ErroDados("O primeiro usuário já foi criado (talvez "
                                    "em outro computador).\nEntre com um "
                                    "usuário existente.")
            else:
                self._exigir(con, autor, para="criar usuários")
                cursor = con.execute(
                    "INSERT INTO usuarios (login, nome, perfil, senha, "
                    "trocar_senha) VALUES (?, ?, ?, ?, ?)",
                    (login, nome, perfil, senha_hash, int(trocar_senha)))
            self._evento(con, autor or login, "Usuário criado", f"{login} ({perfil})")
            return cursor.lastrowid

    def definir_ativo(self, id_usuario, ativo, autor):
        with self._conexao() as con:
            self._exigir(con, autor, para="ativar ou desativar usuários")
            con.execute("UPDATE usuarios SET ativo = ? WHERE id = ?",
                        (int(ativo), id_usuario))
            self._evento(con, autor, "Usuário ativado" if ativo else "Usuário desativado",
                         self._login_de(con, id_usuario))

    def definir_senha(self, id_usuario, senha_hash, autor):
        """Administrador redefine a senha de qualquer um, e isso libera o
        login travado por tentativas erradas; os demais só trocam a própria
        (usuarios.trocar_senha). RN39: a senha redefinida pelo
        administrador é provisória (o usuário define a dele no próximo
        login); trocar a própria tira a pendência."""
        with self._conexao() as con:
            quem = self._exigir(con, autor, so_admin=False, troca=True)
            propria = quem["id"] == id_usuario
            if not propria:       # com a troca pendente, só a própria senha
                quem = self._exigir(con, autor, para="redefinir a senha de "
                                    "outro usuário")
            con.execute("UPDATE usuarios SET senha = ?, trocar_senha = ? "
                        "WHERE id = ?",
                        (senha_hash, 0 if propria else 1, id_usuario))
            login = self._login_de(con, id_usuario)
            if not propria:
                con.execute("DELETE FROM tentativas_login WHERE chave = ?",
                            (login,))
            self._evento(con, autor, "Senha alterada" if propria
                         else "Senha redefinida", login)

    # --------------------------------------------------------------
    # Códigos de recuperação do administrador (RN38)
    # --------------------------------------------------------------
    def salvar_codigos_recuperacao(self, id_usuario, hashes, autor):
        """
        Troca os códigos do administrador `id_usuario` pelos novos (só os
        hashes chegam aqui): os antigos, usados ou não, deixam de valer. Só
        o próprio administrador gera os dele (no primeiro acesso, logo
        depois de criado, ou pelo menu da conta, com a senha atual).
        """
        if not hashes or any(not h for h in hashes):
            raise ErroDados("Códigos de recuperação inválidos.")
        with self._conexao() as con:
            quem = self._exigir(con, autor, para="gerar códigos de "
                                "recuperação")
            if quem["id"] != id_usuario:
                raise ErroDados("Cada administrador gera só os próprios "
                                "códigos de recuperação.")
            con.execute("DELETE FROM codigos_recuperacao WHERE usuario_id = ?",
                        (id_usuario,))
            con.executemany("INSERT INTO codigos_recuperacao (usuario_id, "
                            "hash) VALUES (?, ?)",
                            [(id_usuario, h) for h in hashes])
            self._evento(con, autor, CODIGOS_GERADOS,
                         f"{len(hashes)} códigos novos; os anteriores "
                         "deixaram de valer.")

    def codigos_restantes(self, login):
        """Quantos códigos de recuperação o usuário ainda pode usar."""
        with self._conexao() as con:
            return con.execute(
                "SELECT COUNT(*) FROM codigos_recuperacao c JOIN usuarios u "
                "ON u.id = c.usuario_id WHERE u.login = ? AND c.usado_em = ''",
                (login,)).fetchone()[0]

    def usar_codigo_recuperacao(self, login, codigo, senha_hash):
        """
        "Esqueci a senha": se `codigo` (já normalizado, sem o hífen) é um
        dos códigos ainda não usados do usuário ativo, ele é QUEIMADO, a
        senha vira `senha_hash` (escolhida por ele: sem troca pendente) e o
        login travado é liberado, tudo numa transação. O histórico registra
        o uso sem o código. Devolve True; código errado devolve False (quem
        chama conta a tentativa errada no bloqueio progressivo).
        """
        _exigir_tamanho("Código de recuperação", codigo, MAXIMO_CODIGO)
        with self._conexao() as con:
            usuario = con.execute("SELECT id FROM usuarios WHERE login = ? "
                                  "AND ativo = 1", (login,)).fetchone()
            linhas = [] if usuario is None else con.execute(
                "SELECT id, hash FROM codigos_recuperacao WHERE usuario_id = ? "
                "AND usado_em = '' ORDER BY id", (usuario[0],)).fetchall()
            achado = next((i for i, h in linhas
                           if senhas.conferir_senha(codigo, h)), None)
            if achado is None:
                return False
            agora = self.relogio().strftime(FORMATO_ISO_SEGUNDOS)
            cursor = con.execute("UPDATE codigos_recuperacao SET usado_em = ? "
                                 "WHERE id = ? AND usado_em = ''",
                                 (agora, achado))
            if not cursor.rowcount:      # outra estação usou antes
                return False
            con.execute("UPDATE usuarios SET senha = ?, trocar_senha = 0 "
                        "WHERE id = ?", (senha_hash, usuario[0]))
            con.execute("DELETE FROM tentativas_login WHERE chave = ?",
                        (login,))
            restam = len(linhas) - 1
            self._evento(con, login, CODIGO_RECUPERACAO_USADO,
                         f"Um código de recuperação foi usado e queimado; "
                         f"restam {restam}.")
            return True

    def atualizar_hash_senha(self, id_usuario, senha_hash):
        """Troca o hash pelo padrão atual (mesma senha) no login. Interno:
        não é ação de ninguém, não vai para o histórico."""
        with self._conexao() as con:
            con.execute("UPDATE usuarios SET senha = ? WHERE id = ?",
                        (senha_hash, id_usuario))

    @staticmethod
    def _login_de(con, id_usuario):
        linha = con.execute("SELECT login FROM usuarios WHERE id = ?",
                            (id_usuario,)).fetchone()
        return linha[0] if linha else f"#{id_usuario}"

    # --------------------------------------------------------------
    # Tentativas de login (sobrevivem a fechar e abrir o programa)
    # --------------------------------------------------------------
    def ler_tentativas_login(self, chave):
        """(falhas, bloqueios, bloqueado_ate: datetime ou None) da chave."""
        with self._conexao() as con:
            linha = con.execute("SELECT falhas, bloqueios, bloqueado_ate "
                                "FROM tentativas_login WHERE chave = ?",
                                (chave,)).fetchone()
        if linha is None:
            return 0, 0, None
        falhas, bloqueios, ate = linha
        return (falhas, bloqueios,
                datetime.strptime(ate, FORMATO_ISO_SEGUNDOS) if ate else None)

    def gravar_tentativas_login(self, chave, falhas, bloqueios, bloqueado_ate):
        ate = bloqueado_ate.strftime(FORMATO_ISO_SEGUNDOS) if bloqueado_ate else ""
        with self._conexao() as con:
            con.execute("INSERT INTO tentativas_login (chave, falhas, bloqueios, "
                        "bloqueado_ate) VALUES (?, ?, ?, ?) ON CONFLICT (chave) "
                        "DO UPDATE SET falhas = excluded.falhas, "
                        "bloqueios = excluded.bloqueios, "
                        "bloqueado_ate = excluded.bloqueado_ate",
                        (chave, falhas, bloqueios, ate))

    # --------------------------------------------------------------
    # Histórico de ações (auditoria)
    # --------------------------------------------------------------
    def registrar_evento(self, autor, acao, detalhe=""):
        with self._conexao() as con:
            if acao == "Login recusado" and autor is not None:
                # S11: o texto do campo Usuário só é gravado se for um login
                # que existe (senão pode ser uma senha digitada no lugar)
                existe = con.execute("SELECT 1 FROM usuarios WHERE login = ?",
                                     (autor,)).fetchone()
                if existe is None:
                    autor = LOGIN_INEXISTENTE
            self._evento(con, autor, acao, detalhe)

    @staticmethod
    def _formatar_evento(linha):
        momento, usuario, acao, detalhe = linha
        return {"momento": datetime.strptime(momento, FORMATO_ISO_SEGUNDOS)
                .strftime("%d/%m/%Y %H:%M:%S"),
                "usuario": usuario, "acao": acao, "detalhe": detalhe}

    @staticmethod
    def _evento(con, autor, acao, detalhe="", registro_id=None):
        """Grava no histórico dentro da mesma transação da operação.
        CPFs no detalhe são mascarados (LGPD): ***.982.247-**."""
        if autor:
            con.execute("INSERT INTO auditoria (momento, usuario, acao, detalhe, "
                        "registro_id) VALUES (?, ?, ?, ?, ?)",
                        (datetime.now().strftime(FORMATO_ISO_SEGUNDOS), autor,
                         acao, mascarar_cpfs_no_texto(detalhe), registro_id))

    def listar_excecoes(self, desde, ate, autor):
        """
        V4: os eventos de exceção (ACOES_DE_EXCECAO) com o momento entre os
        dias `desde` e `ate` (date, inclusive; hora local, como o
        histórico grava), do mais recente para o mais antigo, com o nome e
        o CPF da visita ligada (se ela ainda existe). Só administrador.
        """
        marcas = ", ".join("?" for _ in ACOES_DE_EXCECAO)
        with self._conexao() as con:
            self._exigir(con, autor, para="ver o relatório de exceções")
            linhas = con.execute(
                "SELECT a.momento, a.usuario, a.acao, a.detalhe, "
                "COALESCE(r.nome, ''), COALESCE(r.cpf, '') FROM auditoria a "
                "LEFT JOIN registros r ON r.id = a.registro_id "
                f"WHERE a.acao IN ({marcas}) AND a.momento >= ? "
                "AND a.momento < ? ORDER BY a.momento DESC, a.id DESC",
                (*ACOES_DE_EXCECAO, f"{desde:%Y-%m-%d} 00:00:00",
                 f"{ate + timedelta(days=1):%Y-%m-%d} 00:00:00")).fetchall()
        eventos = []
        for momento, usuario, acao, detalhe, nome, cpf in linhas:
            evento = self._formatar_evento((momento, usuario, acao, detalhe))
            evento.update(nome=nome, cpf=cpf)
            eventos.append(evento)
        return eventos

    def listar_eventos(self, limite=200):
        """Últimos eventos, do mais recente para o mais antigo."""
        with self._conexao() as con:
            linhas = con.execute("SELECT momento, usuario, acao, detalhe "
                                 "FROM auditoria ORDER BY id DESC LIMIT ?",
                                 (limite,)).fetchall()
        return [self._formatar_evento(linha) for linha in linhas]

    # --------------------------------------------------------------
    # Migração do JSON da versão 1
    # --------------------------------------------------------------
    def importar_json(self, caminho_json):
        """
        Copia os registros do JSON antigo para o banco, numa só transação, e
        renomeia o JSON para '.migrado' (fica de backup). Devolve um aviso
        para mostrar ao usuário, ou '' se não havia o que migrar.

        Cada registro passa pelas MESMAS regras do cadastro (QA2 M3):
        validacao.validar (nome, CPF, celular, placa, tipo, datas que
        existem, não estão no futuro e são de 2000 em diante, sem cruzar
        outra visita do CPF) e o limite de 24 h, que aqui não tem quem
        autorize. O que não passa é ignorado e contado no aviso, com os
        motivos. Visita aberta com placa abre a estadia do carro. O
        histórico ganha "Importação do arquivo antigo" com as quantidades
        (sem dados pessoais), feita por "(sistema)".
        """
        if not os.path.exists(caminho_json):
            return ""
        registros, aviso = ler_json(caminho_json)
        if aviso:
            return aviso

        # Um registro recusado não impede os outros (mesma transação)
        agora = self.relogio()
        motivos = {}
        with self._conexao() as con:
            for bruto in registros:
                motivo = self._importar_registro(con, bruto, agora)
                if motivo:
                    motivos[motivo] = motivos.get(motivo, 0) + 1
            ignorados = sum(motivos.values())
            resumo = "; ".join(f"{m} ({n})" for m, n in sorted(
                motivos.items(), key=lambda par: -par[1]))
            self._evento(con, AUTOR_SISTEMA, "Importação do arquivo antigo",
                         f"{len(registros) - ignorados} registro(s) importado(s)"
                         f" de {os.path.basename(caminho_json)}; {ignorados} "
                         "ignorado(s)" + (f": {resumo}" if resumo else "."))

        os.replace(caminho_json, caminho_json + ".migrado")
        aviso = (f"{len(registros) - ignorados} registro(s) do arquivo antigo "
                 "foram importados para o banco de dados.")
        if ignorados:
            aviso += (f"\n{ignorados} registro(s) com dados inválidos não foram "
                      "importados; eles continuam no arquivo\n"
                      f"{os.path.basename(caminho_json)}.migrado.\n"
                      f"Motivos: {resumo}.")
        return aviso

    def _importar_registro(self, con, bruto, agora):
        """Grava um registro do JSON antigo se ele passar nas regras do
        cadastro. Devolve '' ou o motivo da recusa (sem dados pessoais)."""
        if not isinstance(bruto, dict):
            return "formato desconhecido"
        campos = ("nome", "cpf", "celular", "placa", "tipo", "entrada", "saida")
        r = normalizar(*(str(bruto.get(c) or "") for c in campos))
        anteriores = [_registro(linha) for linha in con.execute(
            f"SELECT {COLUNAS_REGISTRO} FROM registros WHERE cpf = ?",
            (r["cpf"],))]
        ok, msg = validar(r, anteriores, agora)
        if not ok:
            return msg.splitlines()[0].split(" (")[0].rstrip(".")
        if _duracao_iso(para_iso(r["entrada"]), para_iso(r["saida"])):
            return f"visita de mais de {horarios.LIMITE_VISITA_HORAS} h"
        try:
            id_ = self._inserir(con, r)
        except sqlite3.IntegrityError:
            return "recusado pelo banco"
        if r["placa"] and not r["saida"] and \
                self._estadia_aberta(con, "placa", r["placa"]) is None:
            self._abrir_estadia(con, r, id_, AUTOR_SISTEMA)
        return ""


def ler_json(caminho):
    """
    Devolve (registros, aviso) do arquivo JSON da versão 1. Arquivo danificado
    é renomeado para não se perder; o aviso diz para onde foi.
    """
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            registros = json.load(f)
        if not isinstance(registros, list):
            raise ValueError("o arquivo não contém uma lista")
        return registros, ""
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        base, ext = os.path.splitext(caminho)
        copia = f"{base}.danificado-{datetime.now():%Y%m%d-%H%M%S}{ext}"
        os.replace(caminho, copia)
        return [], ("O arquivo de registros antigo estava danificado e foi "
                    f"guardado como\n{os.path.basename(copia)}.\n"
                    "Nenhum registro foi importado dele.")
    except OSError as e:
        log.error("Erro ao ler o JSON antigo: %s", e)
        raise ErroDados("Não foi possível ler o arquivo de registros antigo.",
                        detalhe=str(e)) from e
