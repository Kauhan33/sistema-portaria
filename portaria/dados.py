"""
Banco de dados SQLite: pessoas, registros de acesso (visitas), usuários,
histórico de ações (auditoria), tentativas de login, lista de bloqueio e
migração do antigo arquivo JSON.

Cada visita aponta para a pessoa (pessoa_id), mas guarda também uma cópia
dos dados daquele dia: se a pessoa trocar de celular, o histórico antigo
continua mostrando o que valia na data.

No banco as datas ficam em ISO ('2026-10-16 08:00'), que ordena e compara
certo em SQL; para o resto do sistema elas saem no formato da tela
('16/10/2026 08:00').

Permissões: quando `autor` (login de quem faz) é informado, as operações
sensíveis conferem o perfil dele NO BANCO e recusam com ErroDados se não
puder (RN02, RN11, RN12 e gestão de usuários). `autor=None` continua aceito
para chamadas internas e testes, sem checagem e sem histórico. É uma
limitação conhecida: quem chama o Banco direto pode omitir o autor.
"""

import json
import logging
import os
import sqlite3
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta

from .usuarios import LOGIN_INEXISTENTE, pode_editar
from .validacao import (FORMATO, TIPOS_ACESSO, mascarar_cpf,
                        mascarar_cpfs_no_texto, so_digitos)

FORMATO_ISO = "%Y-%m-%d %H:%M"
FORMATO_ISO_SEGUNDOS = "%Y-%m-%d %H:%M:%S"
# 1: registros | 2: + usuarios e auditoria | 3: + pessoas
# 4: auditoria ligada ao registro (histórico de cada visita)
# 5: + bloqueios (lista de CPFs e placas com acesso negado)
# 6: uma visita aberta por CPF garantida no banco, índices de desempenho
#    e tentativas de login guardadas no banco
VERSAO_ESQUEMA = 6
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
    if os.path.exists(temporario):
        os.remove(temporario)
    try:
        with closing(sqlite3.connect(origem, timeout=SEGUNDOS_ESPERA)) as src, \
                closing(sqlite3.connect(temporario)) as dst:
            src.backup(dst)
        os.replace(temporario, destino)
    except sqlite3.Error as e:
        if os.path.exists(temporario):
            os.remove(temporario)
        raise _erro(e) from e
    return destino


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


# (versão alcançada, função) em ordem; uma migração nova entra no fim
MIGRACOES = [(5, _passo_v5), (6, _passo_v6)]


class Banco:
    def __init__(self, caminho, wal=True):
        """
        Abre (e atualiza, se preciso) o banco. `wal=False` para banco em
        pasta de rede, onde o modo WAL do SQLite não funciona.
        `avisos` guarda mensagens da atualização para mostrar ao administrador.
        """
        self.caminho = caminho
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
        """Cópia do banco antigo antes de mudar o esquema (pasta backups)."""
        pasta = os.path.join(os.path.dirname(os.path.abspath(self.caminho)),
                             "backups")
        os.makedirs(pasta, exist_ok=True)
        nome = (f"portaria-antes-v{VERSAO_ESQUEMA}-de-v{versao}-"
                f"{datetime.now():%Y%m%d-%H%M%S}.db")
        copiar_banco(self.caminho, os.path.join(pasta, nome))

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
    # Permissões (conferidas no banco quando o autor é informado)
    # --------------------------------------------------------------
    @staticmethod
    def _exigir(con, autor, so_admin=True, para="fazer esta operação"):
        """
        Confere o perfil de `autor` no banco. Devolve o usuário (dict) ou
        None quando autor=None (chamada interna: sem checagem).
        """
        if autor is None:
            return None
        linha = con.execute("SELECT id, perfil, ativo FROM usuarios "
                            "WHERE login = ?", (autor,)).fetchone()
        if linha is None or not linha[2]:
            raise ErroDados("Usuário não autorizado ou desativado.\n"
                            "Saia e entre de novo no sistema.")
        if so_admin and linha[1] != "admin":
            raise ErroDados(f"Somente o administrador pode {para}.")
        return {"id": linha[0], "login": autor, "perfil": linha[1]}

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
        Tabela principal: visitas com entrada no dia `hoje` (date) mais todas
        as ainda abertas (quem está no campus), da entrada mais recente para
        a mais antiga. Custo constante, não cresce com o histórico.
        """
        inicio = _dia_iso(hoje)
        fim = _dia_iso((hoje.date() if isinstance(hoje, datetime) else hoje)
                       + timedelta(days=1))
        # UNION ALL usa os dois índices; com OR viraria varredura da tabela.
        # O '+' impede o índice de entrada na parte das abertas (seria pior).
        with self._conexao() as con:
            linhas = con.execute(
                f"SELECT * FROM (SELECT {COLUNAS_REGISTRO} FROM registros "
                "WHERE entrada >= ? AND entrada < ? "
                f"UNION ALL SELECT {COLUNAS_REGISTRO} FROM registros "
                "WHERE saida = '' AND (+entrada < ? OR +entrada >= ?)) "
                "ORDER BY entrada DESC, id DESC",
                (inicio, fim, inicio, fim)).fetchall()
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
        return {"pessoas": pessoas, "no_campus": no_campus,
                "bloqueios": bloqueios}

    def inserir(self, registro, autor=None):
        """Grava um registro (datas no formato da tela) e devolve o id."""
        with self._conexao() as con:
            id_ = self._inserir(con, registro)
            self._evento(con, autor, "Cadastro de entrada",
                         f"#{id_} {registro['nome']} ({registro['tipo']})", id_)
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

    def registrar_saida(self, id_registro, saida, autor=None):
        self.registrar_saidas([id_registro], saida, autor)

    def registrar_saidas(self, ids, saida, autor=None):
        """Saída de uma ou várias visitas na mesma transação; só das abertas."""
        with self._conexao() as con:
            for i in ids:
                cursor = con.execute("UPDATE registros SET saida = ? "
                                     "WHERE id = ? AND saida = ''",
                                     (para_iso(saida), i))
                if cursor.rowcount:
                    self._evento(con, autor, "Saída registrada", f"#{i}", i)

    def desfazer_saidas(self, ids, autor=None):
        """
        Volta as visitas para "dentro" (botão Desfazer). Só desfaz se a pessoa
        não tiver outra visita aberta ou terminada depois desta entrada —
        senão ficaria no campus duas vezes. Devolve quantas foram desfeitas.
        """
        desfeitas = 0
        with self._conexao() as con:
            for i in ids:
                cursor = con.execute(
                    "UPDATE registros SET saida = '' WHERE id = ? AND saida <> '' "
                    "AND NOT EXISTS (SELECT 1 FROM registros o "
                    "  WHERE o.cpf = registros.cpf AND o.id <> registros.id "
                    "  AND (o.saida = '' OR o.saida > registros.entrada))", (i,))
                if cursor.rowcount:
                    desfeitas += 1
                    self._evento(con, autor, "Saída desfeita", f"#{i}", i)
        return desfeitas

    def excluir(self, ids, autor=None):
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

    def editar(self, id_registro, novo, alteracoes, autor=None):
        """
        Corrige um registro e grava no histórico o que mudou (`alteracoes`,
        já descritas). Porteiro só corrige visitas com entrada (a original e
        a nova) nas últimas 24 h (RN11). Mantém o cadastro da pessoa coerente:
        - se esta é a visita mais recente da pessoa, ela recebe os dados novos;
        - se o CPF mudou, a visita passa para a pessoa certa e a pessoa do
          CPF errado é removida se ficar sem nenhuma visita.
        """
        with self._conexao() as con:
            usuario = self._exigir(con, autor, so_admin=False)
            linha = con.execute("SELECT pessoa_id, nome, entrada FROM registros "
                                "WHERE id = ?", (id_registro,)).fetchone()
            if linha is None:
                raise ErroDados("Este registro não existe mais.")
            pessoa_antiga = linha[0]
            if usuario is not None:
                agora = datetime.now()
                for entrada in (de_iso(linha[2]), novo["entrada"]):
                    ok, msg = pode_editar(usuario, {"entrada": entrada}, agora)
                    if not ok:
                        raise ErroDados(msg)
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
            if pessoa_antiga is not None and pessoa_antiga != pessoa:
                con.execute("DELETE FROM pessoas WHERE id = ? AND NOT EXISTS "
                            "(SELECT 1 FROM registros WHERE pessoa_id = ?)",
                            (pessoa_antiga, pessoa_antiga))
            self._evento(con, autor, "Registro corrigido",
                         f"#{id_registro} {linha[1]} — " + "; ".join(alteracoes),
                         id_registro)

    def eventos_do_registro(self, id_registro):
        """Histórico de uma visita, do mais antigo para o mais recente."""
        with self._conexao() as con:
            linhas = con.execute("SELECT momento, usuario, acao, detalhe "
                                 "FROM auditoria WHERE registro_id = ? "
                                 "ORDER BY id", (id_registro,)).fetchall()
        return [self._formatar_evento(linha) for linha in linhas]

    def registros_do_periodo(self, desde, ate, autor=None):
        """
        Visitas com entrada entre os dias `desde` e `ate` (date, inclusive),
        em ordem de entrada, para a exportação (backup.exportar_csv). Leva
        CPF e celular completos: só administrador, e fica no histórico.
        """
        with self._conexao() as con:
            self._exigir(con, autor, para="exportar registros")
            linhas = con.execute(
                f"SELECT {COLUNAS_REGISTRO} FROM registros "
                "WHERE entrada >= ? AND entrada < ? ORDER BY entrada, id",
                (_dia_iso(desde), _dia_iso(ate + timedelta(days=1)))).fetchall()
            self._evento(con, autor, "Exportação de registros",
                         f"{len(linhas)} registro(s) de {desde:%d/%m/%Y} "
                         f"a {ate:%d/%m/%Y}")
        return [_registro(linha) for linha in linhas]

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
        em ordem alfabética, no máximo `limite`.
        """
        condicao, params = _condicao_busca(
            texto, {"texto": ("nome", "tipo", "placa"),
                    "digitos": ("cpf", "celular")})
        where = f"WHERE {condicao}" if condicao else ""
        with self._conexao() as con:
            linhas = con.execute(
                SELECT_PESSOAS + " WHERE p.id IN (SELECT id FROM pessoas "
                f"{where} ORDER BY nome COLLATE NOCASE LIMIT ?) "
                "GROUP BY p.id ORDER BY p.nome COLLATE NOCASE",
                (*params, int(limite))).fetchall()
        return [self._pessoa(linha) for linha in linhas]

    def buscar_pessoa(self, cpf):
        """Pessoa já cadastrada com esse CPF, ou None."""
        with self._conexao() as con:
            linha = con.execute(SELECT_PESSOAS + " WHERE p.cpf = ? GROUP BY p.id",
                                (cpf,)).fetchone()
        return self._pessoa(linha) if linha else None

    def atualizar_pessoa(self, id_pessoa, nome, celular, placa, tipo, autor=None):
        """Corrige o cadastro da pessoa (as visitas antigas não mudam)."""
        with self._conexao() as con:
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
            linha = con.execute("SELECT id, login, nome, perfil, senha, ativo "
                                "FROM usuarios WHERE login = ?", (login,)).fetchone()
        if linha is None:
            return None
        i, login, nome, perfil, senha, ativo = linha
        return {"id": i, "login": login, "nome": nome, "perfil": perfil,
                "senha": senha, "ativo": bool(ativo)}

    def criar_usuario(self, nome, login, perfil, senha_hash, autor=None):
        """Sem autor = primeiro acesso (cria o primeiro administrador)."""
        with self._conexao() as con:
            self._exigir(con, autor, para="criar usuários")
            cursor = con.execute(
                "INSERT INTO usuarios (login, nome, perfil, senha) VALUES (?, ?, ?, ?)",
                (login, nome, perfil, senha_hash))
            self._evento(con, autor or login, "Usuário criado", f"{login} ({perfil})")
            return cursor.lastrowid

    def definir_ativo(self, id_usuario, ativo, autor=None):
        with self._conexao() as con:
            self._exigir(con, autor, para="ativar ou desativar usuários")
            con.execute("UPDATE usuarios SET ativo = ? WHERE id = ?",
                        (int(ativo), id_usuario))
            self._evento(con, autor, "Usuário ativado" if ativo else "Usuário desativado",
                         self._login_de(con, id_usuario))

    def definir_senha(self, id_usuario, senha_hash, autor=None):
        """Administrador redefine a senha de qualquer um; os demais só a
        própria (troca de senha: usuarios.trocar_senha)."""
        with self._conexao() as con:
            quem = self._exigir(con, autor, so_admin=False)
            propria = quem is not None and quem["id"] == id_usuario
            if quem is not None and not propria and quem["perfil"] != "admin":
                raise ErroDados("Somente o administrador pode redefinir a "
                                "senha de outro usuário.")
            con.execute("UPDATE usuarios SET senha = ? WHERE id = ?",
                        (senha_hash, id_usuario))
            self._evento(con, autor, "Senha alterada" if propria
                         else "Senha redefinida", self._login_de(con, id_usuario))

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
