"""
Desempenho com o histórico grande (revisão 2.5.1). Medir tempo em teste
falha à toa em computador lento; aqui se confere o PLANO da consulta
(EXPLAIN QUERY PLAN): ela usa o índice certo e não varre a tabela.

Medido num banco de 2 anos (146 mil visitas, 20 mil pessoas, 292 mil
eventos): a lista de Pessoas caiu de 0,3 s para 12 ms com a troca abaixo.
"""
import os
import sqlite3
import tempfile
import unittest
from unittest import mock
from datetime import date

from portaria import dados


class TestPlanoDasConsultas(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.caminho = os.path.join(self.pasta.name, "portaria.db")
        self.banco = dados.Banco(self.caminho)

    def plano(self, sql, params=()):
        con = sqlite3.connect(self.caminho)
        con.create_function("minusculo", 1, lambda t: t.lower() if t else t)
        try:
            return " | ".join(linha[-1] for linha in con.execute(
                "EXPLAIN QUERY PLAN " + sql, params))
        finally:
            con.close()

    def test_pessoas_no_campus_primeiro_usa_o_indice_de_visita_aberta(self):
        """A ordem "no campus primeiro" da lista de Pessoas: pelo
        pessoa_id, o SQLite varria as visitas abertas para cada pessoa
        (0,3 s com 20 mil pessoas); pelo CPF usa o índice parcial de
        "uma visita aberta por CPF" (RN05)."""
        sql = ("SELECT id FROM pessoas ORDER BY NOT EXISTS (SELECT 1 FROM "
               "registros d WHERE d.cpf = pessoas.cpf AND d.saida = ''), "
               "nome COLLATE NOCASE LIMIT 200")
        self.assertIn("idx_um_aberto_por_cpf", self.plano(sql))
        # e é essa a consulta que buscar_pessoas usa
        with open(dados.__file__, encoding="utf-8") as f:
            self.assertIn("WHERE d.cpf = pessoas.cpf AND d.saida = ''", f.read())

    def test_buscar_com_periodo_usa_o_indice_da_entrada(self):
        """O "buscar ... de DATA ate DATA" filtra no SQL (antes do limite)
        e o período usa o índice da entrada."""
        comandos = []
        conectar = sqlite3.connect

        def conectar_espiando(*args, **kwargs):
            con = conectar(*args, **kwargs)
            con.set_trace_callback(comandos.append)    # o SQL com os valores
            return con
        with mock.patch("portaria.dados.sqlite3.connect", conectar_espiando):
            self.banco.buscar_registros("", 200, desde=date(2025, 1, 1),
                                        ate=date(2025, 1, 31))
        sql = next(c for c in comandos if "FROM registros" in c)
        self.assertIn("entrada >= '2025-01-01 00:00'", sql)
        self.assertIn("entrada < '2025-02-01 00:00'", sql)
        self.assertIn("idx_registros_entrada", self.plano(sql))


if __name__ == "__main__":
    unittest.main()
