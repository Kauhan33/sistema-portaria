"""
Banco de dados SQLite: pessoas, registros de acesso (visitas), usuários,
histórico de ações (auditoria) e migração do antigo arquivo JSON.

Cada visita aponta para a pessoa (pessoa_id), mas guarda também uma cópia
dos dados daquele dia: se a pessoa trocar de celular, o histórico antigo
continua mostrando o que valia na data.

No banco as datas ficam em ISO ('2026-10-16 08:00'), que ordena e compara
certo em SQL; para o resto do sistema elas saem no formato da tela
('16/10/2026 08:00').
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from .validacao import FORMATO

FORMATO_ISO = "%Y-%m-%d %H:%M"
# 1: registros | 2: + usuarios e auditoria | 3: + pessoas
# 4: auditoria ligada ao registro (histórico de cada visita)
VERSAO_ESQUEMA = 4

ESQUEMA = """
CREATE TABLE IF NOT EXISTS registros (
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
);
CREATE INDEX IF NOT EXISTS idx_registros_cpf ON registros (cpf);

CREATE TABLE IF NOT EXISTS pessoas (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    cpf      TEXT NOT NULL UNIQUE CHECK (length(cpf) = 11),
    nome     TEXT NOT NULL CHECK (nome <> ''),
    celular  TEXT NOT NULL,
    placa    TEXT NOT NULL DEFAULT '',  -- último veículo usado
    tipo     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usuarios (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    login   TEXT NOT NULL UNIQUE,
    nome    TEXT NOT NULL,
    perfil  TEXT NOT NULL CHECK (perfil IN ('admin', 'porteiro')),
    senha   TEXT NOT NULL,              -- hash PBKDF2, nunca a senha
    ativo   INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS auditoria (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    momento  TEXT NOT NULL,             -- ISO com segundos
    usuario  TEXT NOT NULL,             -- login de quem fez
    acao     TEXT NOT NULL,
    detalhe  TEXT NOT NULL DEFAULT '',
    registro_id INTEGER                 -- visita afetada, quando houver
);
"""


class ErroDados(Exception):
    """Falha ao ler ou gravar os registros."""


def para_iso(texto):
    return datetime.strptime(texto, FORMATO).strftime(FORMATO_ISO) if texto else ""


def de_iso(texto):
    return datetime.strptime(texto, FORMATO_ISO).strftime(FORMATO) if texto else ""


# Monta a tabela de pessoas a partir das visitas de um banco anterior à v3:
# dados da visita mais recente de cada CPF e o último veículo informado.
MIGRAR_PESSOAS = """
INSERT INTO pessoas (cpf, nome, celular, placa, tipo)
SELECT r.cpf, r.nome, r.celular,
       COALESCE((SELECT r2.placa FROM registros r2
                 WHERE r2.cpf = r.cpf AND r2.placa <> ''
                 ORDER BY r2.id DESC LIMIT 1), ''),
       r.tipo
FROM registros r
WHERE r.id IN (SELECT MAX(id) FROM registros GROUP BY cpf)
ON CONFLICT (cpf) DO NOTHING;

UPDATE registros
SET pessoa_id = (SELECT p.id FROM pessoas p WHERE p.cpf = registros.cpf)
WHERE pessoa_id IS NULL;
"""

# Liga ao registro os eventos gravados antes da v4 (o detalhe começa
# com "#<id>" nas ações sobre visitas).
MIGRAR_AUDITORIA = """
UPDATE auditoria
SET registro_id = CAST(substr(detalhe, 2, instr(detalhe || ' ', ' ') - 2)
                       AS INTEGER)
WHERE registro_id IS NULL AND detalhe LIKE '#%'
  AND acao IN ('Cadastro de entrada', 'Saída registrada', 'Saída desfeita',
               'Exclusão de registro');
"""

# Visitas, última entrada e entrada em aberto de cada pessoa
SELECT_PESSOAS = """
SELECT p.id, p.cpf, p.nome, p.celular, p.placa, p.tipo,
       COUNT(r.id), MAX(r.entrada),
       MAX(CASE WHEN r.saida = '' THEN r.entrada END)
FROM pessoas p LEFT JOIN registros r ON r.pessoa_id = p.id
"""


class Banco:
    def __init__(self, caminho):
        self.caminho = caminho
        with self._conexao() as con:
            versao = con.execute("PRAGMA user_version").fetchone()[0]
            con.executescript(ESQUEMA)
            colunas = {c[1] for c in con.execute("PRAGMA table_info(registros)")}
            if "pessoa_id" not in colunas:   # banco das versões 1 e 2
                con.execute("ALTER TABLE registros ADD COLUMN pessoa_id "
                            "INTEGER REFERENCES pessoas (id)")
            if versao < 3:
                con.executescript(MIGRAR_PESSOAS)
            colunas = {c[1] for c in con.execute("PRAGMA table_info(auditoria)")}
            if "registro_id" not in colunas:   # banco das versões 2 e 3
                con.execute("ALTER TABLE auditoria ADD COLUMN registro_id INTEGER")
            if versao < 4:
                con.executescript(MIGRAR_AUDITORIA)
            con.execute("CREATE INDEX IF NOT EXISTS idx_registros_pessoa "
                        "ON registros (pessoa_id)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_auditoria_registro "
                        "ON auditoria (registro_id)")
            con.execute(f"PRAGMA user_version = {VERSAO_ESQUEMA}")

    @contextmanager
    def _conexao(self):
        """Uma transação: confirma no fim, desfaz se der erro, sempre fecha."""
        try:
            con = sqlite3.connect(self.caminho)
        except sqlite3.Error as e:
            raise ErroDados(f"Não foi possível abrir o banco de dados.\n{e}") from e
        try:
            yield con
            con.commit()
        except sqlite3.Error as e:
            con.rollback()
            raise ErroDados(f"Erro no banco de dados.\n{e}") from e
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    # --------------------------------------------------------------
    # Operações
    # --------------------------------------------------------------
    def listar(self):
        """Todos os registros, na ordem em que foram cadastrados."""
        with self._conexao() as con:
            linhas = con.execute(
                "SELECT id, nome, cpf, celular, placa, tipo, entrada, saida "
                "FROM registros ORDER BY id").fetchall()
        return [{"id": i, "nome": nome, "cpf": cpf, "celular": cel,
                 "placa": placa, "tipo": tipo, "entrada": de_iso(entrada),
                 "saida": de_iso(saida)}
                for i, nome, cpf, cel, placa, tipo, entrada, saida in linhas]

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
        Grava a visita e atualiza o cadastro da pessoa com os dados dela.
        A visita vai primeiro: se ela for recusada, a pessoa nem é tocada.
        """
        cursor = con.execute(
            "INSERT INTO registros (nome, cpf, celular, placa, tipo, entrada, saida) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (r["nome"], r["cpf"], r["celular"], r.get("placa", ""), r["tipo"],
             para_iso(r["entrada"]), para_iso(r.get("saida", ""))))
        id_registro = cursor.lastrowid
        # Pessoa nova é criada; pessoa conhecida fica com os dados mais
        # recentes (a placa só muda se veio de carro desta vez).
        con.execute(
            "INSERT INTO pessoas (cpf, nome, celular, placa, tipo) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (cpf) DO UPDATE SET nome = excluded.nome, "
            "celular = excluded.celular, tipo = excluded.tipo, "
            "placa = CASE WHEN excluded.placa <> '' THEN excluded.placa "
            "ELSE pessoas.placa END",
            (r["cpf"], r["nome"], r["celular"], r.get("placa", ""), r["tipo"]))
        con.execute("UPDATE registros SET pessoa_id = "
                    "(SELECT id FROM pessoas WHERE cpf = ?) WHERE id = ?",
                    (r["cpf"], id_registro))
        return id_registro

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
        """Apaga os registros; o histórico guarda o que foi apagado."""
        with self._conexao() as con:
            for i in ids:
                linha = con.execute(
                    "SELECT nome, cpf, entrada, saida FROM registros WHERE id = ?",
                    (i,)).fetchone()
                if linha is None:
                    continue
                con.execute("DELETE FROM registros WHERE id = ?", (i,))
                nome, cpf, entrada, saida = linha
                self._evento(con, autor, "Exclusão de registro",
                             f"#{i} {nome}, CPF {cpf}, entrada {de_iso(entrada)}, "
                             f"saída {de_iso(saida) or '—'}", i)

    def buscar(self, id_registro):
        """Um registro pelo id (datas no formato da tela), ou None."""
        return next((r for r in self.listar() if r["id"] == id_registro), None)

    def editar(self, id_registro, novo, alteracoes, autor=None):
        """
        Corrige um registro e grava no histórico o que mudou (`alteracoes`,
        já descritas). Mantém o cadastro da pessoa coerente:
        - se esta é a visita mais recente da pessoa, ela recebe os dados novos;
        - se o CPF mudou, a visita passa para a pessoa certa e a pessoa do
          CPF errado é removida se ficar sem nenhuma visita.
        """
        with self._conexao() as con:
            linha = con.execute("SELECT pessoa_id, nome FROM registros "
                                "WHERE id = ?", (id_registro,)).fetchone()
            if linha is None:
                raise ErroDados("Este registro não existe mais.")
            pessoa_antiga = linha[0]
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
            mais_recente = con.execute(
                "SELECT id FROM registros WHERE pessoa_id = ? "
                "ORDER BY entrada DESC, id DESC LIMIT 1", (pessoa,)).fetchone()[0]
            if mais_recente == id_registro:
                con.execute(
                    "UPDATE pessoas SET nome = ?, celular = ?, tipo = ?, "
                    "placa = CASE WHEN ? <> '' THEN ? ELSE placa END WHERE id = ?",
                    (novo["nome"], novo["celular"], novo["tipo"], novo["placa"],
                     novo["placa"], pessoa))
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
        with self._conexao() as con:
            cursor = con.execute(
                "INSERT INTO usuarios (login, nome, perfil, senha) VALUES (?, ?, ?, ?)",
                (login, nome, perfil, senha_hash))
            self._evento(con, autor or login, "Usuário criado", f"{login} ({perfil})")
            return cursor.lastrowid

    def definir_ativo(self, id_usuario, ativo, autor=None):
        with self._conexao() as con:
            con.execute("UPDATE usuarios SET ativo = ? WHERE id = ?",
                        (int(ativo), id_usuario))
            self._evento(con, autor, "Usuário ativado" if ativo else "Usuário desativado",
                         self._login_de(con, id_usuario))

    def definir_senha(self, id_usuario, senha_hash, autor=None):
        with self._conexao() as con:
            con.execute("UPDATE usuarios SET senha = ? WHERE id = ?",
                        (senha_hash, id_usuario))
            self._evento(con, autor, "Senha redefinida",
                         self._login_de(con, id_usuario))

    @staticmethod
    def _login_de(con, id_usuario):
        linha = con.execute("SELECT login FROM usuarios WHERE id = ?",
                            (id_usuario,)).fetchone()
        return linha[0] if linha else f"#{id_usuario}"

    # --------------------------------------------------------------
    # Histórico de ações (auditoria)
    # --------------------------------------------------------------
    def registrar_evento(self, autor, acao, detalhe=""):
        with self._conexao() as con:
            self._evento(con, autor, acao, detalhe)

    @staticmethod
    def _formatar_evento(linha):
        momento, usuario, acao, detalhe = linha
        return {"momento": datetime.strptime(momento, "%Y-%m-%d %H:%M:%S")
                .strftime("%d/%m/%Y %H:%M:%S"),
                "usuario": usuario, "acao": acao, "detalhe": detalhe}

    @staticmethod
    def _evento(con, autor, acao, detalhe="", registro_id=None):
        """Grava no histórico dentro da mesma transação da operação."""
        if autor:
            con.execute("INSERT INTO auditoria (momento, usuario, acao, detalhe, "
                        "registro_id) VALUES (?, ?, ?, ?, ?)",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), autor,
                         acao, detalhe, registro_id))

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
        raise ErroDados(f"Não foi possível ler o arquivo de registros.\n{e}")
