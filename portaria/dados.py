"""
Banco de dados SQLite: pessoas, registros de acesso (visitas), usuários,
histórico de ações (auditoria), tentativas de login, lista de bloqueio,
configuração dos horários de acesso e migração do antigo arquivo JSON.

Cada visita aponta para a pessoa (pessoa_id), mas guarda também uma cópia
dos dados daquele dia: se a pessoa trocar de celular, o histórico antigo
continua mostrando o que valia na data.

No banco as datas ficam em ISO ('2026-10-16 08:00'), que ordena e compara
certo em SQL; para o resto do sistema elas saem no formato da tela
('16/10/2026 08:00').

Permissões (`autor` = login de quem faz, conferido NO BANCO):
- operações sensíveis (excluir, corrigir, exportar, bloquear, desbloquear,
  criar, ativar ou desativar usuário e definir senha) EXIGEM um autor
  existente, ativo e com o perfil certo (RN02, RN11, RN12 e gestão de
  usuários). Sem autor, recusam: é o caso da sessão que expirou com uma
  caixa de confirmação aberta. A única exceção é o primeiro acesso:
  criar_usuario sem autor só funciona com a tabela de usuários vazia;
- nas escritas do dia a dia (entrada, saída, desfazer saída e corrigir
  pessoa), o autor informado precisa existir e estar ativo (usuário
  desativado com a sessão aberta não continua operando). Sem autor elas
  são chamadas internas (importação do JSON antigo, testes) e não vão
  para o histórico.

Veículos (v8): o carro tem uma ESTADIA própria (estadias_veiculo), com
entrada e saída independentes da visita. A visita com placa abre a estadia
(o responsável é a pessoa dela); a pessoa pode sair a pé e deixar o carro,
voltar a pé e depois sair com ele. Uma placa só tem uma estadia aberta por
vez (índice único). Apagar a visita de origem apaga a estadia (ON DELETE
CASCADE); corrigir a placa, o CPF ou a entrada de uma visita aberta corrige
a estadia aberta por ela.

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
import sqlite3
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta

from . import horarios
from .usuarios import (LOGIN_INEXISTENTE, SESSAO_ENCERRADA, TEMA_PADRAO, TEMAS,
                       pode_editar)
from .validacao import (FORMATO, TIPOS_ACESSO, formatar_placa, mascarar_cpf,
                        mascarar_cpfs_no_texto, so_digitos)

FORMATO_ISO = "%Y-%m-%d %H:%M"
FORMATO_ISO_SEGUNDOS = "%Y-%m-%d %H:%M:%S"
# 1: registros | 2: + usuarios e auditoria | 3: + pessoas
# 4: auditoria ligada ao registro (histórico de cada visita)
# 5: + bloqueios (lista de CPFs e placas com acesso negado)
# 6: uma visita aberta por CPF garantida no banco, índices de desempenho
#    e tentativas de login guardadas no banco
# 7: índice das saídas (o Movimento mostra também quem saiu hoje) e
#    configuração dos horários de acesso (funcionamento, feriados, eventos,
#    regras por categoria e parâmetros)
# 8: tolerância de cada categoria depois do fechamento, padrões novos das
#    regras de horário (ninguém entra depois de fechar, retroativo de 3 h)
#    e as estadias de veículo (o carro tem entrada e saída próprias)
# 9: tema (claro, escuro ou seguir o Windows) escolhido por cada usuário
VERSAO_ESQUEMA = 9
SEGUNDOS_ESPERA = 10          # espera pelo banco ocupado por outro computador
AUTOR_SISTEMA = "(sistema)"   # não é um login válido: ninguém se passa por ele

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

# Estadia de veículo com o tipo de acesso do responsável (da visita de
# origem ou, se ela foi apagada, do cadastro) e se ele está no campus
COLUNAS_ESTADIA = """e.id, e.placa, e.cpf, e.nome, e.entrada, e.saida,
    e.registro_id, COALESCE(r.tipo, p.tipo, ''),
    EXISTS (SELECT 1 FROM registros a WHERE a.cpf = e.cpf AND a.saida = '')"""
DE_ESTADIAS = """FROM estadias_veiculo e
    LEFT JOIN registros r ON r.id = e.registro_id
    LEFT JOIN pessoas p ON p.id = e.pessoa_id"""


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
            return "Este CPF ou placa já está bloqueado."
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


def _condicao_busca(texto, colunas):
    """
    WHERE da busca com o MESMO critério de consultas.filtrar: o texto (em
    minúsculas) contido no nome, tipo ou placa, ou os dígitos dele contidos
    no CPF ou celular. Devolve (sql, parametros); sql vazio = sem filtro.
    """
    texto = texto.strip().lower()
    if not texto:
        return "", []
    numeros = so_digitos(texto)
    partes = [f"instr(minusculo({c}), ?) > 0" for c in colunas["texto"]]
    params = [texto] * len(colunas["texto"])
    if numeros:
        partes += [f"instr({c}, ?) > 0" for c in colunas["digitos"]]
        params += [numeros] * len(colunas["digitos"])
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
            Banco._evento(con, AUTOR_SISTEMA, "Saída automática (atualização)",
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
# quem entrou primeiro com ela.
MIGRAR_ESTADIAS = f"""
INSERT INTO estadias_veiculo (placa, cpf, nome, pessoa_id, registro_id,
                              entrada, autor_entrada)
SELECT r.placa, r.cpf, r.nome, r.pessoa_id, r.id, r.entrada, '{AUTOR_SISTEMA}'
FROM registros r
WHERE r.saida = '' AND r.placa <> ''
  AND r.id = (SELECT r2.id FROM registros r2
              WHERE r2.saida = '' AND r2.placa = r.placa
              ORDER BY r2.entrada, r2.id LIMIT 1)
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
    if "tolerancia_min" not in colunas:
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


# (versão alcançada, função) em ordem; uma migração nova entra no fim
MIGRACOES = [(5, _passo_v5), (6, _passo_v6), (7, _passo_v7), (8, _passo_v8),
             (9, _passo_v9)]


class Banco:
    def __init__(self, caminho, wal=True, relogio=None):
        """
        Abre (e atualiza, se preciso) o banco. `wal=False` para banco em
        pasta de rede, onde o modo WAL do SQLite não funciona.
        `avisos` guarda mensagens da atualização para mostrar ao administrador.
        `relogio`: função que devolve o agora (a tela passa o dela, para as
        regras de horário e a RN11 usarem o mesmo relógio nos testes).
        """
        self.caminho = caminho
        self.relogio = relogio or datetime.now
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
            if versao > VERSAO_ESQUEMA:
                raise ErroDados(
                    "Este banco de dados foi criado por uma versão mais nova "
                    "do programa.\nAtualize o programa para abrir este banco "
                    "(nada foi alterado nele).",
                    detalhe=f"user_version {versao} > {VERSAO_ESQUEMA}")
            if 0 < versao < VERSAO_ESQUEMA:
                self._backup_antes_de_migrar(versao)
            for alvo, passo in MIGRACOES:
                if versao >= alvo:
                    continue
                con.execute("BEGIN IMMEDIATE")
                try:
                    passo(self, con, versao)
                    con.execute(f"PRAGMA user_version = {int(alvo)}")
                    con.execute("COMMIT")
                except BaseException:
                    con.execute("ROLLBACK")
                    raise
                versao = alvo
            if wal:
                con.execute("PRAGMA journal_mode = WAL")
        except sqlite3.Error as e:
            raise _erro(e) from e
        finally:
            con.close()

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
    def _exigir(con, autor, so_admin=True, para="fazer esta operação"):
        """
        Operação sensível: `autor` é obrigatório e precisa existir, estar
        ativo e (com so_admin) ser administrador. Devolve o usuário (dict).
        """
        if autor is None:
            raise ErroDados(SESSAO_ENCERRADA)
        linha = con.execute("SELECT id, perfil, ativo FROM usuarios "
                            "WHERE login = ?", (autor,)).fetchone()
        if linha is None or not linha[2]:
            raise ErroDados("Usuário não autorizado ou desativado.\n"
                            "Saia e entre de novo no sistema.")
        if so_admin and linha[1] != "admin":
            raise ErroDados(f"Somente o administrador pode {para}.")
        return {"id": linha[0], "login": autor, "perfil": linha[1]}

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
        cls._evento(con, autorizacao["autorizado_por"], "Exceção autorizada",
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

    def buscar_registros(self, texto, limite=200):
        """
        Busca no histórico inteiro com o mesmo critério de consultas.filtrar
        (nome, tipo, placa; CPF e celular pelos dígitos), da visita mais
        recente para a mais antiga, no máximo `limite`. Texto vazio = as
        mais recentes.
        """
        condicao, params = _condicao_busca(
            texto, {"texto": ("nome", "tipo", "placa"),
                    "digitos": ("cpf", "celular")})
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
        """Números da barra lateral: pessoas cadastradas, quem está no
        campus e bloqueios ativos (três contagens com índice: rápido)."""
        with self._conexao() as con:
            pessoas, = con.execute("SELECT COUNT(*) FROM pessoas").fetchone()
            no_campus, = con.execute("SELECT COUNT(*) FROM registros "
                                     "WHERE saida = ''").fetchone()
            bloqueios, = con.execute("SELECT COUNT(*) FROM bloqueios "
                                     "WHERE ativo = 1").fetchone()
            veiculos, = con.execute("SELECT COUNT(*) FROM estadias_veiculo "
                                    "WHERE saida = ''").fetchone()
        return {"pessoas": pessoas, "no_campus": no_campus,
                "bloqueios": bloqueios, "veiculos": veiculos}

    def inserir(self, registro, autor=None, autorizacao=None):
        """
        Grava um registro (datas no formato da tela) e devolve o id. Com
        `autorizacao`, a visita é uma exceção de horário autorizada.
        """
        with self._conexao() as con:
            self._conferir_autor(con, autor)
            self._conferir_autorizacao(con, autorizacao)
            self._exigir_autorizacao_24h(
                _duracao_iso(para_iso(registro["entrada"]),
                             para_iso(registro.get("saida", ""))),
                autorizacao, registro["nome"])
            id_ = self._inserir(con, registro)
            self._evento(con, autor, "Cadastro de entrada",
                         f"#{id_} {registro['nome']} ({registro['tipo']})", id_)
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
                         com_veiculo=()):
        """
        Saída de uma ou várias visitas na mesma transação; só das abertas.
        Devolve os ids que de fato receberam a saída (outra estação pode ter
        dado a saída ou excluído a visita antes). Visita que passaria de
        24 h precisa da `autorizacao` (senão nada é gravado), e é a ela que
        a "Exceção autorizada" fica ligada. As visitas em `com_veiculo`
        saem com o carro: a estadia aberta do responsável fecha junto.
        """
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
                con.execute("UPDATE registros SET saida = ? WHERE id = ?",
                            (saida_iso, i))
                gravados.append(i)
                self._evento(con, autor, "Saída registrada", f"#{i}", i)
                if acima_de_24h:
                    self._registrar_excecao(con, autorizacao, autor, i, nome)
                if i in com_veiculo:
                    self._fechar_estadia_do_responsavel(con, i, saida_iso, autor)
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
        """Apaga os registros (RN02: só administrador); o histórico guarda o
        que foi apagado, com o CPF mascarado."""
        with self._conexao() as con:
            self._exigir(con, autor, para="excluir registros")
            for i in ids:
                linha = con.execute(
                    "SELECT nome, cpf, entrada, saida FROM registros WHERE id = ?",
                    (i,)).fetchone()
                if linha is None:
                    continue
                con.execute("DELETE FROM registros WHERE id = ?", (i,))
                nome, cpf, entrada, saida = linha
                self._evento(con, autor, "Exclusão de registro",
                             f"#{i} {nome}, CPF {mascarar_cpf(cpf)}, entrada "
                             f"{de_iso(entrada)}, saída {de_iso(saida) or '—'}", i)

    def buscar(self, id_registro):
        """Um registro pelo id (datas no formato da tela), ou None."""
        with self._conexao() as con:
            linha = con.execute(f"SELECT {COLUNAS_REGISTRO} FROM registros "
                                "WHERE id = ?", (id_registro,)).fetchone()
        return _registro(linha) if linha else None

    def editar(self, id_registro, novo, alteracoes, autor, autorizacao=None):
        """
        Corrige um registro e grava no histórico o que mudou (`alteracoes`,
        já descritas). Porteiro só corrige visitas com entrada (a original e
        a nova) nas últimas 24 h (RN11). Mantém o cadastro da pessoa coerente:
        - se esta é a visita mais recente da pessoa, ela recebe os dados novos;
        - se o CPF mudou, a visita passa para a pessoa certa e a pessoa do
          CPF errado é removida se ficar sem nenhuma visita.
        Exceção de horário: com `autorizacao` (obrigatória se as datas
        mudarem e a visita passar de 24 h), grava a "Exceção autorizada".
        """
        with self._conexao() as con:
            usuario = self._exigir(con, autor, so_admin=False)
            self._conferir_autorizacao(con, autorizacao)
            linha = con.execute("SELECT pessoa_id, nome, entrada, saida, placa "
                                "FROM registros WHERE id = ?",
                                (id_registro,)).fetchone()
            if linha is None:
                raise ErroDados("Este registro não existe mais.")
            pessoa_antiga = linha[0]
            agora = self.relogio()
            for entrada in (de_iso(linha[2]), novo["entrada"]):
                ok, msg = pode_editar(usuario, {"entrada": entrada}, agora)
                if not ok:
                    raise ErroDados(msg)
            datas = (para_iso(novo["entrada"]), para_iso(novo["saida"]))
            if datas != (linha[2], linha[3]):       # só se as datas mudaram
                self._exigir_autorizacao_24h(_duracao_iso(*datas), autorizacao,
                                             novo["nome"])
            con.execute(
                "UPDATE registros SET nome = ?, cpf = ?, celular = ?, placa = ?, "
                "tipo = ?, entrada = ?, saida = ? WHERE id = ?",
                (novo["nome"], novo["cpf"], novo["celular"], novo["placa"],
                 novo["tipo"], para_iso(novo["entrada"]), para_iso(novo["saida"]),
                 id_registro))
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
                con.execute("UPDATE registros SET saida = ? WHERE id = ? "
                            "AND saida = ''", (saida, r["id"]))
                self._evento(con, autor, "Saída automática (encerramento)",
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
        """Estadia aberta pela placa ou pelo CPF do responsável, ou None."""
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
    def _fechar_estadia_do_responsavel(cls, con, id_registro, saida, autor):
        """Saída "de carro": fecha a estadia aberta do responsável da visita."""
        cpf, nome = con.execute("SELECT cpf, nome FROM registros WHERE id = ?",
                                (id_registro,)).fetchone()
        estadia = cls._estadia_aberta(con, "cpf", cpf)
        if estadia is None:
            return
        con.execute("UPDATE estadias_veiculo SET saida = ?, autor_saida = ?, "
                    "registro_saida_id = ? WHERE id = ? AND saida = ''",
                    (saida, autor or AUTOR_SISTEMA, id_registro, estadia["id"]))
        cls._evento(con, autor, "Saída de veículo",
                    f"Placa {formatar_placa(estadia['placa'])} saiu com "
                    f"{nome} (#{id_registro}).", estadia["registro_id"])

    def registrar_saida_veiculo(self, id_estadia, saida, autor=None):
        """Só o carro sai (saída pela placa). False se ele já tinha saído."""
        saida_iso = para_iso(saida)
        with self._conexao() as con:
            self._conferir_autor(con, autor)
            linha = con.execute("SELECT placa, nome, registro_id "
                                "FROM estadias_veiculo WHERE id = ? AND "
                                "saida = ''", (id_estadia,)).fetchone()
            if linha is None:
                return False
            placa, nome, registro_id = linha
            con.execute("UPDATE estadias_veiculo SET saida = ?, autor_saida = ? "
                        "WHERE id = ?", (saida_iso, autor or AUTOR_SISTEMA,
                                         id_estadia))
            self._evento(con, autor, "Saída de veículo",
                         f"Placa {formatar_placa(placa)} saiu (responsável: "
                         f"{nome}).", registro_id)
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
            parametros["minutos_aviso"], parametros["horas_retroativo"])

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

    def adicionar_feriado(self, dia, descricao, autor):
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
    # Lista de bloqueio
    # --------------------------------------------------------------
    def listar_bloqueios(self, incluir_removidos=False):
        """Bloqueios (ativos primeiro, mais recentes primeiro) com o nome da
        pessoa quando o CPF já é conhecido."""
        filtro = "" if incluir_removidos else "WHERE b.ativo = 1"
        with self._conexao() as con:
            linhas = con.execute(
                "SELECT b.id, b.tipo, b.valor, b.motivo, b.criado_em, "
                "b.criado_por, b.ativo, b.removido_em, b.removido_por, "
                "COALESCE(p.nome, '') FROM bloqueios b "
                "LEFT JOIN pessoas p ON b.tipo = 'cpf' AND p.cpf = b.valor "
                f"{filtro} ORDER BY b.ativo DESC, b.id DESC").fetchall()
        return [{"id": i, "tipo": tipo, "valor": valor, "motivo": motivo,
                 "criado_em": de_iso(criado), "criado_por": por,
                 "ativo": bool(ativo), "removido_em": de_iso(removido),
                 "removido_por": removido_por, "nome": nome}
                for (i, tipo, valor, motivo, criado, por, ativo, removido,
                     removido_por, nome) in linhas]

    def bloquear(self, tipo, valor, motivo, autor):
        agora = datetime.now().strftime(FORMATO_ISO)
        with self._conexao() as con:
            self._exigir(con, autor, para="bloquear CPF ou placa")
            cursor = con.execute(
                "INSERT INTO bloqueios (tipo, valor, motivo, criado_em, criado_por) "
                "VALUES (?, ?, ?, ?, ?)", (tipo, valor, motivo.strip(), agora, autor))
            self._evento(con, autor, "Bloqueio criado",
                         f"{tipo.upper()} {valor} — {motivo.strip()}")
            return cursor.lastrowid

    def desbloquear(self, id_bloqueio, autor):
        agora = datetime.now().strftime(FORMATO_ISO)
        with self._conexao() as con:
            self._exigir(con, autor, para="remover bloqueios")
            linha = con.execute("SELECT tipo, valor FROM bloqueios "
                                "WHERE id = ? AND ativo = 1",
                                (id_bloqueio,)).fetchone()
            if linha is None:
                raise ErroDados("Este bloqueio não está mais ativo.")
            con.execute("UPDATE bloqueios SET ativo = 0, removido_em = ?, "
                        "removido_por = ? WHERE id = ?",
                        (agora, autor, id_bloqueio))
            self._evento(con, autor, "Bloqueio removido",
                         f"{linha[0].upper()} {linha[1]}")

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

    def buscar_pessoas(self, texto, limite=200):
        """
        Aba Pessoas sem carregar todo mundo: mesmo critério de
        consultas.filtrar (nome, tipo, placa; CPF e celular pelos dígitos),
        em ordem alfabética, no máximo `limite`. Passando do limite, quem
        está no campus entra primeiro (a lista abre ordenada pela situação).
        """
        condicao, params = _condicao_busca(
            texto, {"texto": ("nome", "tipo", "placa"),
                    "digitos": ("cpf", "celular")})
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

    def atualizar_pessoa(self, id_pessoa, nome, celular, placa, tipo, autor=None):
        """Corrige o cadastro da pessoa (as visitas antigas não mudam)."""
        with self._conexao() as con:
            self._conferir_autor(con, autor)
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
                                "tema FROM usuarios WHERE login = ?",
                                (login,)).fetchone()
        if linha is None:
            return None
        i, login, nome, perfil, senha, ativo, tema = linha
        return {"id": i, "login": login, "nome": nome, "perfil": perfil,
                "senha": senha, "ativo": bool(ativo), "tema": tema}

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

    def criar_usuario(self, nome, login, perfil, senha_hash, autor=None):
        """
        Com autor: só administrador. Sem autor = primeiro acesso, aceito só
        com a tabela de usuários vazia. A condição fica no próprio INSERT:
        duas estações no "Primeiro acesso" não criam dois usuários.
        """
        with self._conexao() as con:
            if autor is None:
                cursor = con.execute(
                    "INSERT INTO usuarios (login, nome, perfil, senha) "
                    "SELECT ?, ?, ?, ? WHERE NOT EXISTS (SELECT 1 FROM usuarios)",
                    (login, nome, perfil, senha_hash))
                if not cursor.rowcount:
                    raise ErroDados("O primeiro usuário já foi criado (talvez "
                                    "em outro computador).\nEntre com um "
                                    "usuário existente.")
            else:
                self._exigir(con, autor, para="criar usuários")
                cursor = con.execute(
                    "INSERT INTO usuarios (login, nome, perfil, senha) "
                    "VALUES (?, ?, ?, ?)", (login, nome, perfil, senha_hash))
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
        (usuarios.trocar_senha)."""
        with self._conexao() as con:
            quem = self._exigir(con, autor, so_admin=False)
            propria = quem["id"] == id_usuario
            if not propria and quem["perfil"] != "admin":
                raise ErroDados("Somente o administrador pode redefinir a "
                                "senha de outro usuário.")
            con.execute("UPDATE usuarios SET senha = ? WHERE id = ?",
                        (senha_hash, id_usuario))
            login = self._login_de(con, id_usuario)
            if not propria:
                con.execute("DELETE FROM tentativas_login WHERE chave = ?",
                            (login,))
            self._evento(con, autor, "Senha alterada" if propria
                         else "Senha redefinida", login)

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
        """
        if not os.path.exists(caminho_json):
            return ""
        registros, aviso = ler_json(caminho_json)
        if aviso:
            return aviso

        # Um registro que viola as regras da tabela é recusado sozinho;
        # os demais continuam na mesma transação.
        ignorados = 0
        with self._conexao() as con:
            for r in registros:
                try:
                    self._inserir(con, r)
                except (KeyError, TypeError, ValueError, sqlite3.IntegrityError):
                    ignorados += 1

        os.replace(caminho_json, caminho_json + ".migrado")
        aviso = (f"{len(registros) - ignorados} registro(s) do arquivo antigo "
                 "foram importados para o banco de dados.")
        if ignorados:
            aviso += (f"\n{ignorados} registro(s) com dados inválidos não foram "
                      "importados; eles continuam no arquivo\n"
                      f"{os.path.basename(caminho_json)}.migrado.")
        return aviso


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
