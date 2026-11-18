"""
Consultas dos painéis da 3.6 (abas do Painel: Veículos, Entregas, Chaves,
Ocorrências e Funcionários). Só leitura: cada consulta abre uma conexão,
calcula no SQL e devolve dicionários prontos para a tela. Nada aqui devolve
CPF: os painéis mostram nomes.

O período é dos últimos `dias` dias, de hoje (relógio do banco) para trás;
"agora" e "hoje" vêm do mesmo relógio.
"""

from datetime import datetime, timedelta

from . import horarios, validacao
from .base_dados import FORMATO_ISO, ErroDados

MAXIMO_DIAS = 366
TAMANHO_RANKING = 6         # linhas dos rankings (mais usadas, por setor...)
SEM_SETOR = "Sem setor"
OUTROS = "Outros"
PERIODO_INVALIDO = f"Período inválido: escolha de 1 a {MAXIMO_DIAS} dias."


def _dia(d):
    return d.strftime("%Y-%m-%d")


def _momento(texto):
    """'AAAA-MM-DD HH:MM' do banco → datetime (None se vazio ou estranho)."""
    try:
        return datetime.strptime((texto or "")[:16], FORMATO_ISO)
    except ValueError:
        return None


def _ha(agora, texto):
    """Quanto tempo desde o momento gravado (nunca negativo)."""
    momento = _momento(texto)
    if momento is None:
        return None
    return max(agora - momento, timedelta(0))


def _media(minutos):
    """AVG do SQL (minutos, ou None sem linhas) → timedelta ou None."""
    return None if minutos is None else timedelta(minutes=round(minutos))


def _minutos_entre(inicio, fim):
    """Expressão SQL: minutos entre duas colunas ISO."""
    return f"(julianday({fim}) - julianday({inicio})) * 1440"


class PainelMixin:
    """As consultas das abas do Painel (3.6)."""

    def _periodo(self, dias):
        """(agora, textos do período) dos últimos `dias` dias até hoje:
        {"hoje", "inicio", "fim"} ('AAAA-MM-DD'; fim = amanhã, exclusivo)
        e a lista dos dias (date), do mais antigo a hoje."""
        if (isinstance(dias, bool) or not isinstance(dias, int)
                or not 1 <= dias <= MAXIMO_DIAS):
            raise ErroDados(PERIODO_INVALIDO)
        agora = self.relogio().replace(second=0, microsecond=0)
        hoje = agora.date()
        inicio = hoje - timedelta(days=dias - 1)
        limites = {"hoje": _dia(hoje), "inicio": _dia(inicio),
                   "fim": _dia(hoje + timedelta(days=1))}
        return agora, limites, [inicio + timedelta(days=n) for n in range(dias)]

    @staticmethod
    def _contar(con, sql, *params):
        return con.execute(sql, params).fetchone()[0] or 0

    @staticmethod
    def _por_dia(con, tabela, coluna, p, dias):
        """[(dia, quantos)] do período, com zero nos dias sem nada."""
        contagem = dict(con.execute(
            f"SELECT substr({coluna}, 1, 10), COUNT(*) FROM {tabela} "
            f"WHERE {coluna} >= ? AND {coluna} < ? GROUP BY 1",
            (p["inicio"], p["fim"])))
        return [(d, contagem.get(_dia(d), 0)) for d in dias]

    # --------------------------------------------------------------
    # Veículos
    # --------------------------------------------------------------
    def painel_veiculos(self, dias=7):
        """
        Estacionamento: carros agora (e as vagas, 0 = sem controle),
        entradas e saídas de hoje, entradas no período (por dia, por hora e
        por tipo de acesso do responsável), o carro que está lá há mais
        tempo e as saídas do período sem o dono: com outra pessoa ou só o
        carro (RN35: com autorizado; o resto, com a senha do administrador,
        RN32). Os pendentes (RN25) e os de dono fora do campus seguem as
        regras de horários.
        """
        from .dados import VEICULO_COM_AUTORIZADO    # (dados importa este)
        agora, p, lista_dias = self._periodo(dias)
        no_periodo = "e.entrada >= :inicio AND e.entrada < :fim"
        with self._conexao() as con:
            no_estacionamento = self._contar(
                con, "SELECT COUNT(*) FROM estadias_veiculo WHERE saida = ''")
            linha = con.execute("SELECT valor FROM parametros WHERE "
                                "chave = 'vagas'").fetchone()
            vagas = linha[0] if linha else 0
            entradas_hoje, saidas_hoje, entradas_periodo = con.execute(
                "SELECT SUM(entrada >= :hoje AND entrada < :fim), "
                "SUM(saida >= :hoje AND saida < :fim), "
                "SUM(entrada >= :inicio AND entrada < :fim) "
                "FROM estadias_veiculo WHERE entrada >= :inicio "
                "OR saida >= :hoje", p).fetchone()
            antigo = con.execute(
                "SELECT placa, nome, entrada FROM estadias_veiculo "
                "WHERE saida = '' ORDER BY entrada, id LIMIT 1").fetchone()
            sem_o_dono, com_autorizado = con.execute(
                "SELECT COUNT(*), SUM(EXISTS (SELECT 1 FROM auditoria a "
                "WHERE a.registro_id = e.registro_saida_id AND a.acao = "
                ":acao)) FROM estadias_veiculo e LEFT JOIN registros r "
                "ON r.id = e.registro_saida_id WHERE e.saida >= :inicio "
                "AND e.saida < :fim AND (r.id IS NULL OR r.cpf <> e.cpf)",
                dict(p, acao=VEICULO_COM_AUTORIZADO)).fetchone()
            por_tipo = con.execute(
                f"SELECT COALESCE(r.tipo, ''), SUM({no_periodo}), "
                "SUM(e.saida = '') FROM estadias_veiculo e LEFT JOIN "
                "registros r ON r.id = e.registro_id "
                f"WHERE ({no_periodo}) OR e.saida = '' GROUP BY 1",
                p).fetchall()
            por_dia = self._por_dia(con, "estadias_veiculo", "entrada", p,
                                    lista_dias)
            por_hora = [0] * 24
            for hora, n in con.execute(
                    "SELECT substr(entrada, 12, 2), COUNT(*) FROM "
                    "estadias_veiculo WHERE entrada >= ? AND entrada < ? "
                    "GROUP BY 1", (p["inicio"], p["fim"])):
                if hora.isdecimal() and int(hora) < 24:
                    por_hora[int(hora)] = n
        config = self.ler_configuracao()
        situacoes = [horarios.situacao_veiculo(config, e, agora)
                     for e in self.listar_estacionamento()]
        contagem = {t: [0, 0] for t in validacao.TIPOS_ACESSO}
        for tipo, total, abertos in por_tipo:
            par = contagem.setdefault(tipo or OUTROS, [0, 0])
            par[0] += total or 0
            par[1] += abertos or 0
        return {
            "no_estacionamento": no_estacionamento,
            "vagas": vagas,
            "entradas_hoje": entradas_hoje or 0,
            "saidas_hoje": saidas_hoje or 0,
            "entradas_periodo": entradas_periodo or 0,
            "pendentes": situacoes.count(horarios.VEICULO_PENDENTE),
            "dono_fora": situacoes.count(horarios.DONO_FORA),
            "mais_antigo": None if antigo is None else {
                "placa": validacao.formatar_placa(antigo[0]),
                "nome": antigo[1], "ha": _ha(agora, antigo[2])},
            "sem_o_dono": sem_o_dono or 0,
            "com_autorizado": com_autorizado or 0,
            "por_tipo": [(t, total, dentro)
                         for t, (total, dentro) in contagem.items()],
            "por_dia": por_dia,
            "por_hora": por_hora,
        }

    # --------------------------------------------------------------
    # Entregas (encomendas e entregadores)
    # --------------------------------------------------------------
    def painel_entregas(self, dias=7):
        """
        Encomendas aguardando retirada (e a mais antiga delas), recebidas e
        retiradas hoje, recebidas no período (por dia e os destinatários
        que mais recebem), o tempo médio até a retirada (das retiradas no
        período) e os entregadores (visitas do tipo Entregador).
        """
        agora, p, lista_dias = self._periodo(dias)
        with self._conexao() as con:
            aguardando = self._contar(con, "SELECT COUNT(*) FROM encomendas "
                                           "WHERE retirada_em = ''")
            antiga = con.execute(
                "SELECT destinatario, recebida_em FROM encomendas WHERE "
                "retirada_em = '' ORDER BY recebida_em, id LIMIT 1").fetchone()
            recebidas_hoje, recebidas_periodo = con.execute(
                "SELECT SUM(recebida_em >= :hoje), COUNT(*) FROM encomendas "
                "WHERE recebida_em >= :inicio AND recebida_em < :fim",
                p).fetchone()
            retiradas_hoje, retiradas_periodo, media = con.execute(
                "SELECT SUM(retirada_em >= :hoje), COUNT(*), AVG("
                + _minutos_entre("recebida_em", "retirada_em") + ") FROM "
                "encomendas WHERE retirada_em >= :inicio AND retirada_em < :fim",
                p).fetchone()
            entregadores_hoje, entregadores_periodo = con.execute(
                "SELECT SUM(entrada >= :hoje), COUNT(*) FROM registros "
                "WHERE tipo = :tipo AND entrada >= :inicio AND entrada < :fim",
                dict(p, tipo="Entregador")).fetchone()
            entregadores_dentro = self._contar(
                con, "SELECT COUNT(*) FROM registros WHERE saida = '' AND "
                     "tipo = ?", "Entregador")
            ranking = con.execute(
                "SELECT MIN(destinatario), COUNT(*), SUM(retirada_em = '') "
                "FROM encomendas WHERE recebida_em >= ? AND recebida_em < ? "
                "GROUP BY minusculo(destinatario) "
                "ORDER BY 2 DESC, minusculo(MIN(destinatario)) LIMIT ?",
                (p["inicio"], p["fim"], TAMANHO_RANKING)).fetchall()
            por_dia = self._por_dia(con, "encomendas", "recebida_em", p,
                                    lista_dias)
        return {
            "aguardando": aguardando,
            "mais_antiga": None if antiga is None else {
                "destinatario": antiga[0], "ha": _ha(agora, antiga[1])},
            "recebidas_hoje": recebidas_hoje or 0,
            "recebidas_periodo": recebidas_periodo or 0,
            "retiradas_hoje": retiradas_hoje or 0,
            "retiradas_periodo": retiradas_periodo or 0,
            "tempo_medio": _media(media),
            "entregadores_hoje": entregadores_hoje or 0,
            "entregadores_periodo": entregadores_periodo or 0,
            "entregadores_dentro": entregadores_dentro,
            "destinatarios": [(nome, n, aguardam)
                              for nome, n, aguardam in ranking],
            "por_dia": por_dia,
        }

    # --------------------------------------------------------------
    # Chaves
    # --------------------------------------------------------------
    def painel_chaves(self, dias=7):
        """
        Chaves cadastradas e emprestadas agora (e a que está fora há mais
        tempo, com quem), empréstimos e devoluções de hoje, empréstimos no
        período (por dia e as chaves mais usadas) e o tempo médio fora (das
        devolvidas no período).
        """
        agora, p, lista_dias = self._periodo(dias)
        with self._conexao() as con:
            cadastradas = self._contar(con, "SELECT COUNT(*) FROM chaves "
                                            "WHERE ativa = 1")
            emprestadas = self._contar(
                con, "SELECT COUNT(*) FROM emprestimos_chave e JOIN chaves c "
                     "ON c.id = e.chave_id WHERE e.devolvida_em = '' "
                     "AND c.ativa = 1")
            fora = con.execute(
                "SELECT c.nome, e.nome, e.retirada_em FROM emprestimos_chave e "
                "JOIN chaves c ON c.id = e.chave_id WHERE e.devolvida_em = '' "
                "ORDER BY e.retirada_em, e.id LIMIT 1").fetchone()
            emprestimos_hoje, emprestimos_periodo = con.execute(
                "SELECT SUM(retirada_em >= :hoje), COUNT(*) FROM "
                "emprestimos_chave WHERE retirada_em >= :inicio "
                "AND retirada_em < :fim", p).fetchone()
            devolucoes_hoje, devolucoes_periodo, media = con.execute(
                "SELECT SUM(devolvida_em >= :hoje), COUNT(*), AVG("
                + _minutos_entre("retirada_em", "devolvida_em") + ") FROM "
                "emprestimos_chave WHERE devolvida_em >= :inicio "
                "AND devolvida_em < :fim", p).fetchone()
            mais_usadas = con.execute(
                "SELECT c.nome, COUNT(*), EXISTS (SELECT 1 FROM "
                "emprestimos_chave x WHERE x.chave_id = c.id AND "
                "x.devolvida_em = '') FROM emprestimos_chave e JOIN chaves c "
                "ON c.id = e.chave_id WHERE e.retirada_em >= ? AND "
                "e.retirada_em < ? GROUP BY c.id "
                "ORDER BY 2 DESC, minusculo(c.nome) LIMIT ?",
                (p["inicio"], p["fim"], TAMANHO_RANKING)).fetchall()
            por_dia = self._por_dia(con, "emprestimos_chave", "retirada_em",
                                    p, lista_dias)
        return {
            "cadastradas": cadastradas,
            "emprestadas": emprestadas,
            "mais_tempo_fora": None if fora is None else {
                "chave": fora[0], "nome": fora[1], "ha": _ha(agora, fora[2])},
            "emprestimos_hoje": emprestimos_hoje or 0,
            "emprestimos_periodo": emprestimos_periodo or 0,
            "devolucoes_hoje": devolucoes_hoje or 0,
            "devolucoes_periodo": devolucoes_periodo or 0,
            "tempo_medio_fora": _media(media),
            "mais_usadas": [(nome, n, bool(fora_agora))
                            for nome, n, fora_agora in mais_usadas],
            "por_dia": por_dia,
        }

    # --------------------------------------------------------------
    # Ocorrências
    # --------------------------------------------------------------
    def painel_ocorrencias(self, dias=7):
        """
        Ocorrências abertas (e a mais antiga delas), registradas hoje e no
        período (por dia e por categoria, todas as categorias, com as
        abertas de cada uma) e o tempo médio até resolver (das resolvidas
        no período).
        """
        agora, p, lista_dias = self._periodo(dias)
        with self._conexao() as con:
            abertas = self._contar(con, "SELECT COUNT(*) FROM ocorrencias "
                                        "WHERE resolvida_em = ''")
            antiga = con.execute(
                "SELECT categoria, momento FROM ocorrencias WHERE "
                "resolvida_em = '' ORDER BY momento, id LIMIT 1").fetchone()
            registradas_hoje, no_periodo = con.execute(
                "SELECT SUM(momento >= :hoje), COUNT(*) FROM ocorrencias "
                "WHERE momento >= :inicio AND momento < :fim", p).fetchone()
            resolvidas, media = con.execute(
                "SELECT COUNT(*), AVG(" + _minutos_entre("momento",
                                                         "resolvida_em")
                + ") FROM ocorrencias WHERE resolvida_em >= :inicio "
                "AND resolvida_em < :fim", p).fetchone()
            categorias = con.execute(
                "SELECT categoria, COUNT(*), SUM(resolvida_em = '') FROM "
                "ocorrencias WHERE momento >= ? AND momento < ? GROUP BY 1",
                (p["inicio"], p["fim"])).fetchall()
            por_dia = self._por_dia(con, "ocorrencias", "momento", p,
                                    lista_dias)
        contagem = {c: [0, 0] for c in validacao.CATEGORIAS_OCORRENCIA}
        for categoria, n, abertas_dela in categorias:
            contagem[categoria] = [n, abertas_dela or 0]
        ordem = list(contagem)
        por_categoria = sorted(((c, n, a) for c, (n, a) in contagem.items()),
                               key=lambda item: (-item[1], ordem.index(item[0])))
        return {
            "abertas": abertas,
            "mais_antiga": None if antiga is None else {
                "categoria": antiga[0], "ha": _ha(agora, antiga[1])},
            "hoje": registradas_hoje or 0,
            "no_periodo": no_periodo or 0,
            "resolvidas_periodo": resolvidas or 0,
            "tempo_medio": _media(media),
            "por_categoria": por_categoria,
            "por_dia": por_dia,
        }

    # --------------------------------------------------------------
    # Funcionários
    # --------------------------------------------------------------
    def painel_funcionarios(self, dias=7):
        """
        Quem tem o tipo Funcionário no cadastro (sem os anonimizados):
        quantos são (e quantos sem matrícula), quantos estão dentro agora e
        quem está há mais tempo, quantos vieram hoje, quantos vieram em cada
        dia do período, a permanência média (das saídas no período) e os
        setores com mais funcionários.
        """
        agora, p, lista_dias = self._periodo(dias)
        tipo = validacao.FUNCIONARIO
        deles = ("registros r JOIN pessoas p ON p.id = r.pessoa_id "
                 "AND p.tipo = ?")
        with self._conexao() as con:
            cadastrados, sem_matricula = con.execute(
                "SELECT COUNT(*), SUM(matricula = '') FROM pessoas WHERE "
                "tipo = ? AND cpf NOT LIKE 'X%'", (tipo,)).fetchone()
            dentro = self._contar(
                con, f"SELECT COUNT(DISTINCT p.id) FROM {deles} "
                     "WHERE r.saida = ''", tipo)
            vieram_hoje = self._contar(
                con, f"SELECT COUNT(DISTINCT p.id) FROM {deles} WHERE "
                     "r.entrada >= ? AND r.entrada < ?",
                tipo, p["hoje"], p["fim"])
            antigo = con.execute(
                f"SELECT p.nome, r.entrada FROM {deles} WHERE r.saida = '' "
                "ORDER BY r.entrada, r.id LIMIT 1", (tipo,)).fetchone()
            saidas, media = con.execute(
                "SELECT COUNT(*), AVG(" + _minutos_entre("r.entrada",
                                                         "r.saida")
                + f") FROM {deles} WHERE r.saida >= ? AND r.saida < ?",
                (tipo, p["inicio"], p["fim"])).fetchone()
            setores = con.execute(
                "SELECT MIN(p.setor), COUNT(*), SUM(EXISTS (SELECT 1 FROM "
                "registros r WHERE r.pessoa_id = p.id AND r.saida = '')) "
                "FROM pessoas p WHERE p.tipo = ? AND p.cpf NOT LIKE 'X%' "
                "GROUP BY minusculo(p.setor) "
                "ORDER BY 2 DESC, minusculo(MIN(p.setor)) LIMIT ?",
                (tipo, TAMANHO_RANKING)).fetchall()
            contagem = dict(con.execute(
                "SELECT substr(r.entrada, 1, 10), COUNT(DISTINCT p.id) FROM "
                f"{deles} WHERE r.entrada >= ? AND r.entrada < ? GROUP BY 1",
                (tipo, p["inicio"], p["fim"])))
        return {
            "cadastrados": cadastrados,
            "sem_matricula": sem_matricula or 0,
            "dentro": dentro,
            "vieram_hoje": vieram_hoje,
            "ha_mais_tempo": None if antigo is None else {
                "nome": antigo[0], "ha": _ha(agora, antigo[1])},
            "saidas_periodo": saidas or 0,
            "permanencia_media": _media(media),
            "por_setor": [(setor or SEM_SETOR, n, dentro_agora or 0)
                          for setor, n, dentro_agora in setores],
            "por_dia": [(d, contagem.get(_dia(d), 0)) for d in lista_dias],
        }
