"""
Banco de dados dos módulos da versão 3.2 (esquema v14): chaves, encomendas,
autorizações de entrada (visitantes autorizados), dados dos funcionários,
crachá e quem a visita procura, recados de turno, privacidade (LGPD),
histórico protegido contra alteração e os dados de demonstração.

É um "mixin" da classe Banco (dados.py): os métodos daqui usam a mesma
conexão, as mesmas permissões (_exigir) e o mesmo histórico (_evento). Como
em todo o sistema, a tela nunca é a única trava: cada método confere de novo
quem pode e se os dados valem.
"""

import hashlib
import random
from datetime import date, datetime, timedelta

from . import validacao
from .dados import (FORMATO_ISO, FORMATO_ISO_SEGUNDOS, ErroDados, de_iso,
                    para_iso)
from .validacao import (FORMATO, MAXIMO_BUSCA, mascarar_cpfs_no_texto,
                        so_digitos)

FORMATO_DIA_ISO = "%Y-%m-%d"
FORMATO_DIA = "%d/%m/%Y"
ANONIMO = "Pessoa anonimizada"
TAMANHOS_DE_LETRA = ("normal", "grande", "maior")

ESQUEMA_V14 = [
    # chaves da portaria: o cadastro e quem está com cada uma
    """CREATE TABLE IF NOT EXISTS chaves (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        nome       TEXT NOT NULL CHECK (nome <> ''),
        local      TEXT NOT NULL DEFAULT '',
        ativa      INTEGER NOT NULL DEFAULT 1 CHECK (ativa IN (0, 1)),
        criada_em  TEXT NOT NULL,
        criada_por TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS emprestimos_chave (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        chave_id     INTEGER NOT NULL REFERENCES chaves (id),
        nome         TEXT NOT NULL CHECK (nome <> ''),
        cpf          TEXT NOT NULL DEFAULT '',
        retirada_em  TEXT NOT NULL,
        entregue_por TEXT NOT NULL,
        devolvida_em TEXT NOT NULL DEFAULT '',
        recebida_por TEXT NOT NULL DEFAULT '',
        CHECK (devolvida_em = '' OR devolvida_em >= retirada_em)
    )""",
    # uma chave só fica com uma pessoa por vez
    """CREATE UNIQUE INDEX IF NOT EXISTS idx_chave_emprestada
        ON emprestimos_chave (chave_id) WHERE devolvida_em = ''""",
    """CREATE TABLE IF NOT EXISTS encomendas (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        recebida_em  TEXT NOT NULL,
        destinatario TEXT NOT NULL CHECK (destinatario <> ''),
        setor        TEXT NOT NULL DEFAULT '',
        remetente    TEXT NOT NULL CHECK (remetente <> ''),
        descricao    TEXT NOT NULL DEFAULT '',
        recebida_por TEXT NOT NULL,
        retirada_em  TEXT NOT NULL DEFAULT '',
        retirada_nome TEXT NOT NULL DEFAULT '',
        retirada_cpf TEXT NOT NULL DEFAULT '',
        entregue_por TEXT NOT NULL DEFAULT ''
    )""",
    "CREATE INDEX IF NOT EXISTS idx_encomendas_data ON encomendas (recebida_em)",
    # visitantes autorizados: quem pode entrar, por quem e em que dias
    """CREATE TABLE IF NOT EXISTS autorizacoes_entrada (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        cpf           TEXT NOT NULL CHECK (length(cpf) = 11),
        nome          TEXT NOT NULL CHECK (nome <> ''),
        empresa       TEXT NOT NULL DEFAULT '',
        motivo        TEXT NOT NULL CHECK (motivo <> ''),
        anfitriao     TEXT NOT NULL CHECK (anfitriao <> ''),
        valida_de     TEXT NOT NULL,        -- dia ISO
        valida_ate    TEXT NOT NULL,
        criada_em     TEXT NOT NULL,
        criada_por    TEXT NOT NULL,
        cancelada_em  TEXT NOT NULL DEFAULT '',
        cancelada_por TEXT NOT NULL DEFAULT '',
        usos          INTEGER NOT NULL DEFAULT 0,
        ultimo_uso    TEXT NOT NULL DEFAULT '',
        emissoes      INTEGER NOT NULL DEFAULT 0,
        CHECK (valida_ate >= valida_de)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_autorizacoes_cpf ON autorizacoes_entrada (cpf)",
    """CREATE TABLE IF NOT EXISTS recados_turno (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        momento  TEXT NOT NULL,
        autor    TEXT NOT NULL,
        texto    TEXT NOT NULL CHECK (texto <> ''),
        lido_em  TEXT NOT NULL DEFAULT '',
        lido_por TEXT NOT NULL DEFAULT ''
    )""",
    # o crachá só fica com uma visita aberta por vez
    """CREATE UNIQUE INDEX IF NOT EXISTS idx_cracha_em_uso
        ON registros (cracha) WHERE saida = '' AND cracha <> ''""",
]
COLUNAS_V14 = (("registros", "anfitriao", "TEXT NOT NULL DEFAULT ''"),
               ("registros", "cracha", "TEXT NOT NULL DEFAULT ''"),
               ("pessoas", "matricula", "TEXT NOT NULL DEFAULT ''"),
               ("pessoas", "setor", "TEXT NOT NULL DEFAULT ''"),
               ("pessoas", "cargo", "TEXT NOT NULL DEFAULT ''"),
               ("auditoria", "hash", "TEXT NOT NULL DEFAULT ''"),
               ("usuarios", "letra", "TEXT NOT NULL DEFAULT 'normal'"))


def hash_do_evento(anterior, momento, usuario, acao, detalhe, registro_id):
    """Elo da corrente do histórico: o SHA-256 do evento junto com o elo do
    evento anterior. Mudar ou apagar um evento antigo quebra todos os elos
    seguintes (verificar_historico acha o primeiro quebrado)."""
    texto = "\x1f".join((anterior, momento, usuario, acao, detalhe,
                         "" if registro_id is None else str(registro_id)))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def encadear_historico(con):
    """Calcula (de novo) a corrente inteira do histórico. Só na migração:
    depois dela, cada evento novo já nasce com o seu elo."""
    anterior = ""
    for i, momento, usuario, acao, detalhe, registro in con.execute(
            "SELECT id, momento, usuario, acao, detalhe, registro_id "
            "FROM auditoria ORDER BY id").fetchall():
        anterior = hash_do_evento(anterior, momento, usuario, acao, detalhe,
                                  registro)
        con.execute("UPDATE auditoria SET hash = ? WHERE id = ?", (anterior, i))


def passo_v14(banco, con, versao):
    """
    Versão 3.2: chaves, encomendas, autorizações de entrada, recados de
    turno; quem a visita procura e o crachá; matrícula, setor e cargo do
    funcionário; o elo (hash) de cada evento do histórico; o tamanho da
    letra de cada usuário.
    """
    for tabela, coluna, tipo in COLUNAS_V14:
        existentes = {c[1] for c in con.execute(f"PRAGMA table_info({tabela})")}
        if coluna not in existentes:
            con.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
    for sql in ESQUEMA_V14:
        con.execute(sql)
    encadear_historico(con)


def cpf_ficticio(base):
    """CPF válido (dígitos verificadores certos) a partir de 9 dígitos."""
    d = [int(c) for c in f"{base:09d}"]
    for n in (10, 11):
        s = sum(v * (n - i) for i, v in enumerate(d)) % 11
        d.append(0 if s < 2 else 11 - s)
    return "".join(map(str, d))


def _dia_da_tela(texto, rotulo):
    try:
        return datetime.strptime((texto or "").strip(), FORMATO_DIA).date()
    except ValueError:
        raise ErroDados(f"{rotulo}: use o formato dd/mm/aaaa.") from None


def _dia_para_tela(iso):
    return datetime.strptime(iso, FORMATO_DIA_ISO).strftime(FORMATO_DIA)


def _limpo(texto):
    return " ".join((texto or "").split())


def _contem(colunas):
    """Trecho WHERE: o texto (minúsculo) aparece em alguma das colunas."""
    juntas = " || ' ' || ".join(colunas)
    return f"instr(minusculo({juntas}), ?) > 0"


class ModulosMixin:
    """Os módulos da 3.2 (ver o texto no alto do arquivo)."""

    def _agora_iso(self):
        return self.relogio().strftime(FORMATO_ISO)

    @staticmethod
    def _recusar(ok_msg):
        ok, msg = ok_msg
        if not ok:
            raise ErroDados(msg)

    # --------------------------------------------------------------
    # Chaves entregues e devolvidas
    # --------------------------------------------------------------
    def cadastrar_chave(self, nome, local, autor):
        """Chave nova (só administrador). O nome não se repete entre as
        chaves ativas. Devolve o id."""
        nome, local = _limpo(nome), _limpo(local)
        self._recusar(validacao.validar_chave(nome, local))
        with self._conexao() as con:
            self._exigir(con, autor, para="cadastrar chaves")
            if con.execute("SELECT 1 FROM chaves WHERE ativa = 1 AND "
                           "minusculo(nome) = ?", (nome.lower(),)).fetchone():
                raise ErroDados(f"Já existe a chave \"{nome}\".")
            cursor = con.execute(
                "INSERT INTO chaves (nome, local, criada_em, criada_por) "
                "VALUES (?, ?, ?, ?)", (nome, local, self._agora_iso(), autor))
            self._evento(con, autor, "Chave cadastrada",
                         f"#{cursor.lastrowid} {nome}"
                         + (f" ({local})" if local else ""))
            return cursor.lastrowid

    def desativar_chave(self, id_chave, autor):
        """Tira a chave da lista (só administrador; o histórico dela fica).
        Chave emprestada não pode: primeiro a devolução."""
        with self._conexao() as con:
            self._exigir(con, autor, para="remover chaves")
            linha = con.execute("SELECT nome, ativa FROM chaves WHERE id = ?",
                                (id_chave,)).fetchone()
            if linha is None or not linha[1]:
                raise ErroDados("Esta chave não existe mais.")
            if con.execute("SELECT 1 FROM emprestimos_chave WHERE chave_id = ? "
                           "AND devolvida_em = ''", (id_chave,)).fetchone():
                raise ErroDados(f"A chave \"{linha[0]}\" está emprestada.\n"
                                "Registre a devolução antes de remover.")
            con.execute("UPDATE chaves SET ativa = 0 WHERE id = ?", (id_chave,))
            self._evento(con, autor, "Chave removida", f"#{id_chave} {linha[0]}")

    def listar_chaves(self, texto="", so_emprestadas=False):
        """As chaves ativas, com quem está cada uma (emprestadas primeiro)."""
        partes, params = ["c.ativa = 1"], []
        texto = (texto or "").strip().lower()[:MAXIMO_BUSCA]
        if texto:
            partes.append(_contem(("c.nome", "c.local", "COALESCE(e.nome, '')")))
            params.append(texto)
        if so_emprestadas:
            partes.append("e.id IS NOT NULL")
        with self._conexao() as con:
            linhas = con.execute(
                "SELECT c.id, c.nome, c.local, e.id, e.nome, e.cpf, "
                "e.retirada_em, e.entregue_por FROM chaves c "
                "LEFT JOIN emprestimos_chave e ON e.chave_id = c.id "
                "AND e.devolvida_em = '' "
                f"WHERE {' AND '.join(partes)} "
                "ORDER BY (e.id IS NULL), minusculo(c.nome)", params).fetchall()
        return [{"id": i, "nome": nome, "local": local,
                 "emprestada": emprestimo is not None,
                 "com_quem": quem or "", "cpf": cpf or "",
                 "desde": de_iso(desde or ""), "entregue_por": por or ""}
                for i, nome, local, emprestimo, quem, cpf, desde, por in linhas]

    def entregar_chave(self, id_chave, nome, autor, cpf=""):
        """Empresta a chave (qualquer usuário ativo). A chave precisa estar
        na portaria; o CPF é opcional, mas, se vier, tem de ser válido."""
        nome, cpf = _limpo(nome), so_digitos(cpf or "")
        self._recusar(validacao.validar_quem_retira(nome, cpf))
        with self._conexao() as con:
            self._exigir(con, autor, so_admin=False)
            linha = con.execute("SELECT nome, ativa FROM chaves WHERE id = ?",
                                (id_chave,)).fetchone()
            if linha is None or not linha[1]:
                raise ErroDados("Esta chave não existe mais.")
            com = con.execute("SELECT nome FROM emprestimos_chave WHERE "
                              "chave_id = ? AND devolvida_em = ''",
                              (id_chave,)).fetchone()
            if com:
                raise ErroDados(f"A chave \"{linha[0]}\" já está com {com[0]}.\n"
                                "Registre a devolução antes de entregar de novo.")
            con.execute("INSERT INTO emprestimos_chave (chave_id, nome, cpf, "
                        "retirada_em, entregue_por) VALUES (?, ?, ?, ?, ?)",
                        (id_chave, nome, cpf, self._agora_iso(), autor))
            self._evento(con, autor, "Chave entregue", f"{linha[0]} para {nome}")

    def devolver_chave(self, id_chave, autor):
        """Registra a devolução (qualquer usuário ativo)."""
        with self._conexao() as con:
            self._exigir(con, autor, so_admin=False)
            linha = con.execute(
                "SELECT e.id, e.nome, c.nome FROM emprestimos_chave e "
                "JOIN chaves c ON c.id = e.chave_id WHERE e.chave_id = ? "
                "AND e.devolvida_em = ''", (id_chave,)).fetchone()
            if linha is None:
                raise ErroDados("Esta chave já foi devolvida (ou não está "
                                "emprestada).")
            con.execute("UPDATE emprestimos_chave SET devolvida_em = ?, "
                        "recebida_por = ? WHERE id = ?",
                        (self._agora_iso(), autor, linha[0]))
            self._evento(con, autor, "Chave devolvida",
                         f"{linha[2]} por {linha[1]}")

    def historico_de_chaves(self, texto="", limite=200):
        """Empréstimos, do mais recente para o mais antigo."""
        texto = (texto or "").strip().lower()[:MAXIMO_BUSCA]
        where = ("WHERE " + _contem(("c.nome", "e.nome")) + " ") if texto else ""
        with self._conexao() as con:
            linhas = con.execute(
                "SELECT c.nome, e.nome, e.cpf, e.retirada_em, e.entregue_por, "
                "e.devolvida_em, e.recebida_por FROM emprestimos_chave e "
                f"JOIN chaves c ON c.id = e.chave_id {where}"
                "ORDER BY e.retirada_em DESC, e.id DESC LIMIT ?",
                ((texto,) if texto else ()) + (int(limite),)).fetchall()
        return [{"chave": c, "nome": n, "cpf": cpf, "retirada_em": de_iso(r),
                 "entregue_por": por, "devolvida_em": de_iso(d),
                 "recebida_por": rec}
                for c, n, cpf, r, por, d, rec in linhas]

    # --------------------------------------------------------------
    # Encomendas
    # --------------------------------------------------------------
    def registrar_encomenda(self, destinatario, remetente, autor, setor="",
                            descricao=""):
        """Encomenda que chegou na portaria (qualquer usuário ativo)."""
        destinatario, remetente = _limpo(destinatario), _limpo(remetente)
        setor, descricao = _limpo(setor), _limpo(descricao)
        self._recusar(validacao.validar_encomenda(destinatario, remetente,
                                                  setor, descricao))
        descricao = mascarar_cpfs_no_texto(descricao)
        with self._conexao() as con:
            self._exigir(con, autor, so_admin=False)
            cursor = con.execute(
                "INSERT INTO encomendas (recebida_em, destinatario, setor, "
                "remetente, descricao, recebida_por) VALUES (?, ?, ?, ?, ?, ?)",
                (self._agora_iso(), destinatario, setor, remetente, descricao,
                 autor))
            self._evento(con, autor, "Encomenda recebida",
                         f"#{cursor.lastrowid} para {destinatario}, de "
                         f"{remetente}")
            return cursor.lastrowid

    def listar_encomendas(self, texto="", so_pendentes=False, limite=200):
        partes, params = [], []
        texto = (texto or "").strip().lower()[:MAXIMO_BUSCA]
        if texto:
            partes.append(_contem(("destinatario", "setor", "remetente",
                                   "descricao", "retirada_nome")))
            params.append(texto)
        if so_pendentes:
            partes.append("retirada_em = ''")
        where = f"WHERE {' AND '.join(partes)} " if partes else ""
        with self._conexao() as con:
            linhas = con.execute(
                "SELECT id, recebida_em, destinatario, setor, remetente, "
                "descricao, recebida_por, retirada_em, retirada_nome, "
                f"retirada_cpf, entregue_por FROM encomendas {where}"
                "ORDER BY (retirada_em <> ''), recebida_em DESC, id DESC "
                "LIMIT ?", (*params, int(limite))).fetchall()
        return [{"id": i, "recebida_em": de_iso(rec), "destinatario": dest,
                 "setor": setor, "remetente": rem, "descricao": desc,
                 "recebida_por": por, "retirada_em": de_iso(ret),
                 "retirada_nome": nome, "retirada_cpf": cpf,
                 "entregue_por": ent}
                for i, rec, dest, setor, rem, desc, por, ret, nome, cpf, ent
                in linhas]

    def retirar_encomenda(self, id_encomenda, nome, autor, cpf=""):
        """Entrega a encomenda a quem veio buscar (qualquer usuário ativo)."""
        nome, cpf = _limpo(nome), so_digitos(cpf or "")
        self._recusar(validacao.validar_quem_retira(nome, cpf))
        with self._conexao() as con:
            self._exigir(con, autor, so_admin=False)
            cursor = con.execute(
                "UPDATE encomendas SET retirada_em = ?, retirada_nome = ?, "
                "retirada_cpf = ?, entregue_por = ? WHERE id = ? "
                "AND retirada_em = ''",
                (self._agora_iso(), nome, cpf, autor, id_encomenda))
            if not cursor.rowcount:
                raise ErroDados("Esta encomenda já foi retirada ou não "
                                "existe mais.")
            self._evento(con, autor, "Encomenda retirada",
                         f"#{id_encomenda} por {nome}")

    def excluir_encomenda(self, id_encomenda, autor):
        """Só o administrador (lançamento feito por engano)."""
        with self._conexao() as con:
            self._exigir(con, autor, para="excluir encomendas")
            linha = con.execute("SELECT destinatario, remetente FROM encomendas "
                                "WHERE id = ?", (id_encomenda,)).fetchone()
            if linha is None:
                raise ErroDados("Esta encomenda não existe mais.")
            con.execute("DELETE FROM encomendas WHERE id = ?", (id_encomenda,))
            self._evento(con, autor, "Encomenda excluída",
                         f"#{id_encomenda} para {linha[0]}, de {linha[1]}")

    # --------------------------------------------------------------
    # Visitantes autorizados e emissão da autorização de entrada
    # --------------------------------------------------------------
    def criar_autorizacao(self, cpf, nome, empresa, motivo, anfitriao,
                          valida_de, valida_ate, autor):
        """Autoriza a entrada de alguém num período (qualquer usuário ativo
        registra o que o setor pediu). Datas como na tela (dd/mm/aaaa).
        Devolve o id (o número da autorização)."""
        cpf, nome, empresa = so_digitos(cpf or ""), _limpo(nome), _limpo(empresa)
        motivo = mascarar_cpfs_no_texto(_limpo(motivo))
        anfitriao = _limpo(anfitriao)
        de = _dia_da_tela(valida_de, "Válida de")
        ate = _dia_da_tela(valida_ate, "Válida até")
        self._recusar(validacao.validar_autorizacao(
            cpf, nome, empresa, motivo, anfitriao, de, ate,
            self.relogio().date()))
        with self._conexao() as con:
            self._exigir(con, autor, so_admin=False)
            cursor = con.execute(
                "INSERT INTO autorizacoes_entrada (cpf, nome, empresa, motivo, "
                "anfitriao, valida_de, valida_ate, criada_em, criada_por) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (cpf, nome, empresa, motivo, anfitriao,
                 de.strftime(FORMATO_DIA_ISO), ate.strftime(FORMATO_DIA_ISO),
                 self._agora_iso(), autor))
            self._evento(con, autor, "Autorização de entrada criada",
                         f"nº {cursor.lastrowid}: {nome}, por {anfitriao}, de "
                         f"{de.strftime(FORMATO_DIA)} a "
                         f"{ate.strftime(FORMATO_DIA)}")
            return cursor.lastrowid

    @staticmethod
    def _autorizacao(linha, hoje):
        (i, cpf, nome, empresa, motivo, anfitriao, de, ate, criada, por,
         cancelada, cancelada_por, usos, ultimo, emissoes) = linha
        if cancelada:
            situacao = validacao.AUT_CANCELADA
        elif ate < hoje:
            situacao = validacao.AUT_VENCIDA
        elif de > hoje:
            situacao = validacao.AUT_FUTURA
        else:
            situacao = validacao.AUT_VALIDA
        return {"id": i, "cpf": cpf, "nome": nome, "empresa": empresa,
                "motivo": motivo, "anfitriao": anfitriao,
                "valida_de": _dia_para_tela(de), "valida_ate": _dia_para_tela(ate),
                "criada_em": de_iso(criada), "criada_por": por,
                "cancelada_em": de_iso(cancelada), "cancelada_por": cancelada_por,
                "usos": usos, "ultimo_uso": de_iso(ultimo), "emissoes": emissoes,
                "situacao": situacao}

    COLUNAS_AUTORIZACAO = ("id, cpf, nome, empresa, motivo, anfitriao, "
                           "valida_de, valida_ate, criada_em, criada_por, "
                           "cancelada_em, cancelada_por, usos, ultimo_uso, "
                           "emissoes")

    def listar_autorizacoes(self, texto="", so_validas=False, limite=200,
                            so_cpf_completo=False):
        """Da mais nova para a mais antiga. so_cpf_completo (porteiro): o
        CPF só é achado pelos 11 dígitos, como nas outras buscas (RN30)."""
        hoje = self.relogio().date().strftime(FORMATO_DIA_ISO)
        partes, params = [], []
        texto = (texto or "").strip().lower()[:MAXIMO_BUSCA]
        if texto:
            numeros = so_digitos(texto)
            achar = [_contem(("nome", "empresa", "anfitriao", "motivo"))]
            params.append(texto)
            if len(numeros) == 11 or (numeros and not so_cpf_completo):
                achar.append("cpf = ?" if len(numeros) == 11
                             else "instr(cpf, ?) > 0")
                params.append(numeros)
            partes.append("(" + " OR ".join(achar) + ")")
        if so_validas:
            partes.append("cancelada_em = '' AND valida_de <= ? AND "
                          "valida_ate >= ?")
            params += [hoje, hoje]
        where = f"WHERE {' AND '.join(partes)} " if partes else ""
        with self._conexao() as con:
            linhas = con.execute(
                f"SELECT {self.COLUNAS_AUTORIZACAO} FROM autorizacoes_entrada "
                f"{where}ORDER BY id DESC LIMIT ?",
                (*params, int(limite))).fetchall()
        return [self._autorizacao(linha, hoje) for linha in linhas]

    def buscar_autorizacao(self, id_autorizacao):
        hoje = self.relogio().date().strftime(FORMATO_DIA_ISO)
        with self._conexao() as con:
            linha = con.execute(
                f"SELECT {self.COLUNAS_AUTORIZACAO} FROM autorizacoes_entrada "
                "WHERE id = ?", (id_autorizacao,)).fetchone()
        return self._autorizacao(linha, hoje) if linha else None

    def autorizacao_valida(self, cpf, dia=None):
        """A autorização que vale para este CPF no dia (hoje), ou None."""
        dia = (dia or self.relogio().date()).strftime(FORMATO_DIA_ISO)
        with self._conexao() as con:
            linha = self._autorizacao_do_dia(con, so_digitos(cpf or ""), dia)
        return self._autorizacao(linha, dia) if linha else None

    def _autorizacao_do_dia(self, con, cpf, dia_iso):
        return con.execute(
            f"SELECT {self.COLUNAS_AUTORIZACAO} FROM autorizacoes_entrada "
            "WHERE cpf = ? AND cancelada_em = '' AND valida_de <= ? "
            "AND valida_ate >= ? ORDER BY id DESC LIMIT 1",
            (cpf, dia_iso, dia_iso)).fetchone()

    def _usar_autorizacao(self, con, registro, id_visita, autor):
        """A entrada de quem tem autorização válida no dia conta como uso
        (chamado por Banco.inserir, na mesma transação)."""
        entrada = para_iso(registro["entrada"])
        linha = self._autorizacao_do_dia(con, registro["cpf"], entrada[:10])
        if linha is None:
            return
        con.execute("UPDATE autorizacoes_entrada SET usos = usos + 1, "
                    "ultimo_uso = ? WHERE id = ?", (entrada, linha[0]))
        self._evento(con, autor, "Entrada com autorização",
                     f"autorização nº {linha[0]}, por {linha[5]}", id_visita)

    def cancelar_autorizacao(self, id_autorizacao, autor):
        with self._conexao() as con:
            self._exigir(con, autor, so_admin=False)
            cursor = con.execute(
                "UPDATE autorizacoes_entrada SET cancelada_em = ?, "
                "cancelada_por = ? WHERE id = ? AND cancelada_em = ''",
                (self._agora_iso(), autor, id_autorizacao))
            if not cursor.rowcount:
                raise ErroDados("Esta autorização já foi cancelada ou não "
                                "existe mais.")
            self._evento(con, autor, "Autorização de entrada cancelada",
                         f"nº {id_autorizacao}")

    def registrar_emissao(self, id_autorizacao, autor):
        """A autorização foi emitida (impressa): fica no histórico."""
        with self._conexao() as con:
            self._exigir(con, autor, so_admin=False)
            cursor = con.execute("UPDATE autorizacoes_entrada SET emissoes = "
                                 "emissoes + 1 WHERE id = ?", (id_autorizacao,))
            if not cursor.rowcount:
                raise ErroDados("Esta autorização não existe mais.")
            self._evento(con, autor, "Autorização de entrada emitida",
                         f"nº {id_autorizacao}")

    # --------------------------------------------------------------
    # Funcionários (matrícula, setor e cargo de quem é do tipo Funcionário)
    # --------------------------------------------------------------
    def salvar_funcionario(self, id_pessoa, matricula, setor, cargo, autor):
        matricula, setor, cargo = _limpo(matricula), _limpo(setor), _limpo(cargo)
        self._recusar(validacao.validar_funcionario(matricula, setor, cargo))
        with self._conexao() as con:
            self._exigir(con, autor, so_admin=False)
            linha = con.execute("SELECT nome, tipo, matricula, setor, cargo "
                                "FROM pessoas WHERE id = ?",
                                (id_pessoa,)).fetchone()
            if linha is None:
                raise ErroDados("Esta pessoa não existe mais.")
            if linha[1] != validacao.FUNCIONARIO:
                raise ErroDados(f"{linha[0]} não é do tipo Funcionário.")
            if matricula and con.execute(
                    "SELECT 1 FROM pessoas WHERE matricula = ? AND id <> ?",
                    (matricula, id_pessoa)).fetchone():
                raise ErroDados(f"A matrícula {matricula} já é de outro "
                                "funcionário.")
            con.execute("UPDATE pessoas SET matricula = ?, setor = ?, cargo = ? "
                        "WHERE id = ?", (matricula, setor, cargo, id_pessoa))
            mudou = [f"{rotulo}: {antes or '—'} → {depois or '—'}"
                     for rotulo, antes, depois in (
                         ("Matrícula", linha[2], matricula),
                         ("Setor", linha[3], setor), ("Cargo", linha[4], cargo))
                     if antes != depois]
            if mudou:
                self._evento(con, autor, "Dados de funcionário alterados",
                             f"{linha[0]}: " + "; ".join(mudou))

    def listar_funcionarios(self, texto=""):
        """Quem é do tipo Funcionário, com a matrícula, o setor, o cargo e
        o ponto de hoje (entrada, saída e se está dentro)."""
        hoje = self.relogio().date().strftime(FORMATO_DIA_ISO)
        texto = (texto or "").strip().lower()[:MAXIMO_BUSCA]
        filtro = (" AND " + _contem(("p.nome", "p.matricula", "p.setor",
                                     "p.cargo"))) if texto else ""
        with self._conexao() as con:
            linhas = con.execute(
                "SELECT p.id, p.cpf, p.nome, p.matricula, p.setor, p.cargo, "
                "(SELECT MIN(r.entrada) FROM registros r WHERE r.pessoa_id = "
                " p.id AND substr(r.entrada, 1, 10) = ?), "
                "(SELECT MAX(r.saida) FROM registros r WHERE r.pessoa_id = p.id "
                " AND substr(r.entrada, 1, 10) = ? AND r.saida <> ''), "
                "(SELECT r.entrada FROM registros r WHERE r.pessoa_id = p.id "
                " AND r.saida = '' LIMIT 1) "
                f"FROM pessoas p WHERE p.tipo = ?{filtro} "
                "ORDER BY minusculo(p.nome)",
                (hoje, hoje, validacao.FUNCIONARIO)
                + ((texto,) if texto else ())).fetchall()
        return [{"id": i, "cpf": cpf, "nome": nome, "matricula": mat,
                 "setor": setor, "cargo": cargo,
                 "entrada_hoje": de_iso(entrada or ""),
                 "saida_hoje": de_iso(saida or ""),
                 "dentro_desde": de_iso(dentro or "")}
                for i, cpf, nome, mat, setor, cargo, entrada, saida, dentro
                in linhas]

    # --------------------------------------------------------------
    # Crachá (uma visita aberta por crachá)
    # --------------------------------------------------------------
    @staticmethod
    def _conferir_cracha(con, registro, id_visita=None):
        cracha = registro.get("cracha") or ""
        if not cracha or registro.get("saida"):
            return
        linha = con.execute("SELECT nome FROM registros WHERE cracha = ? AND "
                            "saida = '' AND id IS NOT ?",
                            (cracha, id_visita)).fetchone()
        if linha:
            raise ErroDados(f"O crachá {cracha} está com {linha[0]}.\n"
                            "Escolha outro crachá.")

    def crachas_em_uso(self):
        with self._conexao() as con:
            return [c for c, in con.execute(
                "SELECT cracha FROM registros WHERE saida = '' AND cracha <> '' "
                "ORDER BY CAST(cracha AS INTEGER)")]

    # --------------------------------------------------------------
    # Recados de turno
    # --------------------------------------------------------------
    def deixar_recado(self, texto, autor):
        texto = mascarar_cpfs_no_texto(_limpo(texto))
        self._recusar(validacao.validar_recado(texto))
        with self._conexao() as con:
            self._exigir(con, autor, so_admin=False)
            cursor = con.execute("INSERT INTO recados_turno (momento, autor, "
                                 "texto) VALUES (?, ?, ?)",
                                 (self._agora_iso(), autor, texto))
            self._evento(con, autor, "Recado de turno deixado",
                         f"#{cursor.lastrowid} {texto[:80]}")
            return cursor.lastrowid

    def listar_recados(self, so_nao_lidos=False, limite=50):
        where = "WHERE lido_em = '' " if so_nao_lidos else ""
        with self._conexao() as con:
            linhas = con.execute(
                "SELECT id, momento, autor, texto, lido_em, lido_por FROM "
                f"recados_turno {where}ORDER BY id DESC LIMIT ?",
                (int(limite),)).fetchall()
        return [{"id": i, "momento": de_iso(m), "autor": a, "texto": t,
                 "lido_em": de_iso(em), "lido_por": por}
                for i, m, a, t, em, por in linhas]

    def marcar_recado_lido(self, id_recado, autor):
        with self._conexao() as con:
            self._exigir(con, autor, so_admin=False)
            cursor = con.execute("UPDATE recados_turno SET lido_em = ?, "
                                 "lido_por = ? WHERE id = ? AND lido_em = ''",
                                 (self._agora_iso(), autor, id_recado))
            if not cursor.rowcount:
                raise ErroDados("Este recado já foi marcado como lido.")
            self._evento(con, autor, "Recado de turno lido", f"#{id_recado}")

    # --------------------------------------------------------------
    # Tamanho da letra (preferência de cada usuário, como o tema)
    # --------------------------------------------------------------
    def definir_letra(self, letra, autor):
        if letra not in TAMANHOS_DE_LETRA:
            raise ErroDados("Tamanho de letra desconhecido.", detalhe=repr(letra))
        with self._conexao() as con:
            self._exigir(con, autor, so_admin=False)
            con.execute("UPDATE usuarios SET letra = ? WHERE login = ?",
                        (letra, autor))

    def letra_do_usuario(self, login):
        with self._conexao() as con:
            linha = con.execute("SELECT letra FROM usuarios WHERE login = ?",
                                (login,)).fetchone()
        return linha[0] if linha and linha[0] in TAMANHOS_DE_LETRA else "normal"

    # --------------------------------------------------------------
    # Privacidade (LGPD): anonimizar e prazo de guarda
    # --------------------------------------------------------------
    def _anonimizar(self, con, id_pessoa):
        """Troca os dados pessoais da pessoa e das visitas dela por textos
        neutros. As visitas ficam (os números do Painel não mudam). O CPF
        vira um código que nunca é um CPF de verdade."""
        codigo = f"X{id_pessoa:010d}"
        con.execute("UPDATE pessoas SET nome = ?, cpf = ?, celular = '', "
                    "placa = '', empresa = '', matricula = '', setor = '', "
                    "cargo = '' WHERE id = ?", (ANONIMO, codigo, id_pessoa))
        con.execute("UPDATE registros SET nome = ?, cpf = ?, celular = '', "
                    "placa = '', empresa = '', motivo = '', anfitriao = '' "
                    "WHERE pessoa_id = ?", (ANONIMO, codigo, id_pessoa))
        con.execute("DELETE FROM placas_pessoa WHERE pessoa_id = ?",
                    (id_pessoa,))

    @staticmethod
    def _impede_anonimizar(con, id_pessoa):
        """Motivo para não anonimizar agora, ou ''."""
        linha = con.execute("SELECT nome, cpf FROM pessoas WHERE id = ?",
                            (id_pessoa,)).fetchone()
        if linha is None:
            return "Esta pessoa não existe mais."
        if linha[1].startswith("X"):
            return "Esta pessoa já foi anonimizada."
        if con.execute("SELECT 1 FROM registros WHERE pessoa_id = ? AND "
                       "saida = ''", (id_pessoa,)).fetchone():
            return (f"{linha[0]} está dentro agora.\nRegistre a saída antes "
                    "de anonimizar.")
        if con.execute("SELECT 1 FROM bloqueios WHERE tipo = 'cpf' AND "
                       "valor = ? AND ativo = 1", (linha[1],)).fetchone():
            return (f"{linha[0]} está desativada: o motivo precisa do CPF.\n"
                    "Reative antes de anonimizar.")
        if con.execute("SELECT 1 FROM estadias_veiculo e JOIN registros r ON "
                       "r.id = e.registro_id WHERE r.pessoa_id = ? AND "
                       "e.saida = ''", (id_pessoa,)).fetchone():
            return (f"{linha[0]} tem um carro no estacionamento.\nRegistre a "
                    "saída do carro antes de anonimizar.")
        return ""

    def anonimizar_pessoa(self, id_pessoa, justificativa, autor):
        """A pedido do titular (só administrador, com justificativa)."""
        justificativa = _limpo(justificativa)
        self._recusar(validacao.validar_justificativa_simples(justificativa))
        with self._conexao() as con:
            self._exigir(con, autor, para="anonimizar pessoas")
            motivo = self._impede_anonimizar(con, id_pessoa)
            if motivo:
                raise ErroDados(motivo)
            self._anonimizar(con, id_pessoa)
            self._evento(con, autor, "Pessoa anonimizada",
                         f"pessoa #{id_pessoa}. Justificativa: {justificativa}")

    def _fora_do_prazo(self, con, meses):
        limite = (self.relogio() - timedelta(days=30 * meses)).strftime(
            FORMATO_ISO)
        return [i for i, in con.execute(
            "SELECT p.id FROM pessoas p WHERE p.cpf NOT LIKE 'X%' AND "
            "COALESCE((SELECT MAX(CASE WHEN r.saida = '' THEN '9999' "
            " ELSE r.saida END) FROM registros r WHERE r.pessoa_id = p.id), "
            " '0') < ? AND NOT EXISTS (SELECT 1 FROM bloqueios b WHERE "
            " b.tipo = 'cpf' AND b.valor = p.cpf AND b.ativo = 1) AND EXISTS "
            "(SELECT 1 FROM registros r WHERE r.pessoa_id = p.id)", (limite,))]

    def contar_fora_do_prazo(self, meses):
        """Quantas pessoas a retenção anonimizaria agora."""
        self._recusar(validacao.validar_meses_de_guarda(meses))
        if not meses:
            return 0
        with self._conexao() as con:
            return len(self._fora_do_prazo(con, meses))

    def aplicar_retencao(self, meses, autor):
        """Anonimiza quem não vem há mais de `meses` meses (só
        administrador). Quem está desativado fica: o motivo precisa do CPF.
        Devolve quantas pessoas foram anonimizadas."""
        self._recusar(validacao.validar_meses_de_guarda(meses))
        if not meses:
            raise ErroDados("Informe o prazo de guarda em meses (de 1 a 120).")
        with self._conexao() as con:
            self._exigir(con, autor, para="aplicar o prazo de guarda")
            pessoas = self._fora_do_prazo(con, meses)
            for id_pessoa in pessoas:
                self._anonimizar(con, id_pessoa)
            self._evento(con, autor, "Prazo de guarda aplicado",
                         f"{len(pessoas)} pessoa(s) sem visita há mais de "
                         f"{meses} meses anonimizada(s)")
            return len(pessoas)

    # --------------------------------------------------------------
    # Painel: entradas por dia e por hora de um período
    # --------------------------------------------------------------
    def entradas_por_dia(self, hoje, dias):
        """[(dia, entradas)] dos últimos `dias` dias, do mais antigo a hoje."""
        inicio = hoje - timedelta(days=dias - 1)
        with self._conexao() as con:
            contagem = dict(con.execute(
                "SELECT substr(entrada, 1, 10), COUNT(*) FROM registros "
                "WHERE entrada >= ? AND entrada < ? GROUP BY 1",
                (inicio.strftime(FORMATO_DIA_ISO),
                 (hoje + timedelta(days=1)).strftime(FORMATO_DIA_ISO))))
        return [(inicio + timedelta(days=n),
                 contagem.get((inicio + timedelta(days=n)).strftime(
                     FORMATO_DIA_ISO), 0)) for n in range(dias)]

    def entradas_por_hora(self, hoje, dias):
        """24 números: quantas entradas em cada hora do dia, somando os
        últimos `dias` dias (o horário de pico é a maior)."""
        inicio = hoje - timedelta(days=dias - 1)
        horas = [0] * 24
        with self._conexao() as con:
            for hora, n in con.execute(
                    "SELECT substr(entrada, 12, 2), COUNT(*) FROM registros "
                    "WHERE entrada >= ? AND entrada < ? GROUP BY 1",
                    (inicio.strftime(FORMATO_DIA_ISO),
                     (hoje + timedelta(days=1)).strftime(FORMATO_DIA_ISO))):
                if hora.isdecimal() and int(hora) < 24:
                    horas[int(hora)] = n
        return horas

    # --------------------------------------------------------------
    # Histórico protegido contra alteração
    # --------------------------------------------------------------
    def verificar_historico(self):
        """Refaz a corrente do histórico e compara com a gravada. Devolve
        {"total", "integro", "primeiro_alterado" (id ou None)}."""
        anterior, total = "", 0
        with self._conexao() as con:
            for i, momento, usuario, acao, detalhe, registro, gravado in \
                    con.execute("SELECT id, momento, usuario, acao, detalhe, "
                                "registro_id, hash FROM auditoria ORDER BY id"):
                total += 1
                anterior = hash_do_evento(anterior, momento, usuario, acao,
                                          detalhe, registro)
                if anterior != gravado:
                    return {"total": total, "integro": False,
                            "primeiro_alterado": i}
        return {"total": total, "integro": True, "primeiro_alterado": None}

    # --------------------------------------------------------------
    # Dados de demonstração (fictícios), só para apresentar o sistema
    # --------------------------------------------------------------
    PESSOAS_DE_DEMONSTRACAO = (
        # (base do CPF, nome, tipo, empresa, placa, motivo)
        (390533447, "Carla Nogueira", "Professor", "UNA", "BRA2E19",
         "Aula de Compiladores"),
        (111444777, "Bruno Almeida", "Professor", "UNA", "", "Banca de TCC"),
        (168995350, "Diego Ramos", "Aluno", "UNA", "QWE1D23", "Aula"),
        (529982247, "Mariana Costa", "Aluno", "UNA", "", "Biblioteca"),
        (714287938, "Rafael Lima", "Funcionário", "UNA", "RST4A56",
         "Expediente"),
        (284759163, "Helena Souza", "Funcionário", "UNA", "", "Expediente"),
        (453178287, "Lucas Pereira", "Prestador de serviço", "NetFibra", "",
         "Reparo na rede do bloco B"),
        (862883667, "Hélio Prado", "Prestador de serviço", "Clima Frio Ltda",
         "JKL4M56", "Manutenção do ar-condicionado"),
        (635241789, "Júlia Martins", "Visitante", "Beta Consultoria", "",
         "Visita técnica ao laboratório"),
        (741852963, "Otávio Reis", "Visitante", "Alfa Ltda", "NEY4829",
         "Reunião com a coordenação"),
        (456123789, "Lara Duarte", "Entregador", "Rápido Entregas", "",
         "Entrega de material de escritório"),
        (987654321, "Fábio Melo", "Aluno", "UNA", "", "Prova"),
    )

    def preencher_demonstracao(self, autor):
        """
        Enche o banco com dados FICTÍCIOS para apresentar o sistema (só
        administrador): pessoas, visitas dos últimos dias, quem está dentro
        agora, carros, chaves, encomendas, autorizações, ocorrências e um
        recado. Tudo numa transação; quem já existe (pelo CPF) é pulado.
        Devolve um resumo {o quê: quantos}.
        """
        r = random.Random(32)
        agora = self.relogio().replace(second=0, microsecond=0)
        feito = {"pessoas": 0, "visitas": 0, "chaves": 0, "encomendas": 0,
                 "autorizações": 0, "ocorrências": 0}
        with self._conexao() as con:
            self._exigir(con, autor, para="inserir os dados de demonstração")
            novas = []
            for base, nome, tipo, empresa, placa, motivo in \
                    self.PESSOAS_DE_DEMONSTRACAO:
                cpf = cpf_ficticio(base)
                if con.execute("SELECT 1 FROM pessoas WHERE cpf = ?",
                               (cpf,)).fetchone():
                    continue
                if placa and con.execute(
                        "SELECT 1 FROM estadias_veiculo WHERE placa = ? AND "
                        "saida = ''", (placa,)).fetchone():
                    placa = ""
                novas.append({"nome": nome, "cpf": cpf, "tipo": tipo,
                              "celular": f"319{r.randint(10000000, 99999999)}",
                              "empresa": empresa, "placa": placa,
                              "motivo": motivo})
            feito["pessoas"] = len(novas)
            # visitas encerradas dos 6 dias anteriores (uma por dia e pessoa,
            # nem todo dia) e a de hoje, que fica aberta para 2 em cada 3
            for n, p in enumerate(novas):
                for dias in range(6, 0, -1):
                    dia = agora - timedelta(days=dias)
                    if dia.weekday() == 6 or r.random() < 0.45:
                        continue
                    entrada = dia.replace(hour=r.randint(7, 10),
                                          minute=r.choice((0, 10, 20, 35, 50)))
                    saida = entrada + timedelta(hours=r.randint(1, 5),
                                                minutes=r.choice((0, 15, 40)))
                    self._visita_de_demonstracao(con, p, entrada, saida, autor)
                    feito["visitas"] += 1
                minutos = 20 + 25 * n
                entrada = max(agora - timedelta(minutes=minutos),
                              agora.replace(hour=0, minute=0))
                saida = None
                if n % 3 == 2 and entrada + timedelta(minutes=10) <= agora:
                    saida = entrada + timedelta(minutes=10)
                self._visita_de_demonstracao(con, p, entrada, saida, autor)
                feito["visitas"] += 1
            agora_iso = agora.strftime(FORMATO_ISO)
            for nome, local in (("Laboratório 2", "Bloco B, 1º andar"),
                                ("Auditório", "Bloco A"),
                                ("Sala dos professores", "Bloco A, térreo"),
                                ("Almoxarifado", "Bloco C")):
                if con.execute("SELECT 1 FROM chaves WHERE ativa = 1 AND "
                               "nome = ?", (nome,)).fetchone():
                    continue
                cursor = con.execute(
                    "INSERT INTO chaves (nome, local, criada_em, criada_por) "
                    "VALUES (?, ?, ?, ?)", (nome, local, agora_iso, autor))
                feito["chaves"] += 1
                if nome == "Laboratório 2":
                    con.execute(
                        "INSERT INTO emprestimos_chave (chave_id, nome, cpf, "
                        "retirada_em, entregue_por) VALUES (?, ?, ?, ?, ?)",
                        (cursor.lastrowid, "Carla Nogueira",
                         cpf_ficticio(390533447), agora_iso, autor))
            if feito["pessoas"]:
                for destinatario, setor, remetente, descricao in (
                        ("Helena Souza", "Secretaria", "Correios",
                         "Envelope registrado"),
                        ("Coordenação de Engenharia", "Bloco B", "Mercado Livre",
                         "Caixa média"),
                        ("Rafael Lima", "Manutenção", "Kalunga",
                         "Material de escritório")):
                    con.execute(
                        "INSERT INTO encomendas (recebida_em, destinatario, "
                        "setor, remetente, descricao, recebida_por) VALUES "
                        "(?, ?, ?, ?, ?, ?)", (agora_iso, destinatario, setor,
                                               remetente, descricao, autor))
                    feito["encomendas"] += 1
                hoje = agora.date()
                for base, nome, empresa, motivo, anfitriao, dias in (
                        (135792468, "Paula Viana", "Gama Engenharia",
                         "Vistoria do elevador", "Manutenção", 2),
                        (246813579, "Sérgio Antunes", "Delta Seguros",
                         "Reunião sobre o contrato", "Diretoria", 0)):
                    con.execute(
                        "INSERT INTO autorizacoes_entrada (cpf, nome, empresa, "
                        "motivo, anfitriao, valida_de, valida_ate, criada_em, "
                        "criada_por) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (cpf_ficticio(base), nome, empresa, motivo, anfitriao,
                         hoje.strftime(FORMATO_DIA_ISO),
                         (hoje + timedelta(days=dias)).strftime(FORMATO_DIA_ISO),
                         agora_iso, autor))
                    feito["autorizações"] += 1
                for categoria, texto in (
                        ("Veículo", "Carro estacionado sobre a calçada do "
                                    "bloco A; dono avisado pelo telefone."),
                        ("Equipamento", "Cancela da entrada 2 demorando para "
                                        "abrir; chamado aberto na manutenção."),
                        ("Achados e perdidos", "Mochila preta encontrada na "
                                               "recepção, guardada na portaria.")):
                    con.execute(
                        "INSERT INTO ocorrencias (momento, categoria, texto, "
                        "autor) VALUES (?, ?, ?, ?)",
                        (agora_iso, categoria, texto, autor))
                    feito["ocorrências"] += 1
                con.execute("INSERT INTO recados_turno (momento, autor, texto) "
                            "VALUES (?, ?, ?)",
                            (agora_iso, autor, "O portão lateral fica fechado "
                                               "até a manutenção liberar."))
            resumo = ", ".join(f"{n} {o}" for o, n in feito.items())
            self._evento(con, autor, "Dados de demonstração inseridos", resumo)
        return feito

    def _visita_de_demonstracao(self, con, pessoa, entrada, saida, autor):
        """Uma visita fictícia, pelo mesmo caminho das de verdade (_inserir
        cria a pessoa e guarda a placa; a aberta com placa abre a estadia)."""
        registro = dict(pessoa, entrada=entrada.strftime(FORMATO),
                        saida=saida.strftime(FORMATO) if saida else "")
        if saida:
            registro["placa"] = ""      # (o carro de ontem não fica no pátio)
        id_ = self._inserir(con, registro)
        if registro["placa"]:
            self._abrir_estadia(con, registro, id_, autor)
        return id_


def dia_para_tela(dia):
    """date -> 'dd/mm/aaaa' (para preencher os campos das telas)."""
    return dia.strftime(FORMATO_DIA) if isinstance(dia, date) else ""
