"""
Versão 2.2 — V4: Relatório de exceções (Usuários › Exceções): cada tipo no
filtro certo, o período no horário local, o porteiro não vê, CSV com o
CPF mascarado e a exportação no histórico.
"""

import csv
import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime

from portaria import backup, dados, excecoes
from portaria.senhas import gerar_hash

from .test_dados import registro
from .test_interface import BaseInterface

HOJE = date.today()       # o histórico grava a hora local do computador


def evento(acao, detalhe, usuario="ana", nome="", cpf="",
           momento="21/10/2026 10:00:00"):
    return {"momento": momento, "usuario": usuario, "acao": acao,
            "detalhe": detalhe, "nome": nome, "cpf": cpf}


class TestLerExcecao(unittest.TestCase):
    def test_horario_retroativo_e_24h(self):
        casos = [("#1 Ana — Aluno: entrada às 23:30 fora do horário permitido "
                  "(06:30–22:30).", ["Horário"]),
                 ("#1 Ana — Entrada retroativa: 21/10/2026 05:00 é de mais de "
                  "3 h atrás. Aluno: entrada às 05:00 fora do horário "
                  "permitido (06:30–22:30).", ["Horário", "Retroativo"]),
                 ("#1 Ana — Visita de 30 h (o máximo é 24 h).",
                  ["Mais de 24 h"]),
                 ("#1 Ana — Campus fechado em 25/10/2026 (domingo).",
                  ["Horário"])]
        for regras, tipos in casos:
            with self.subTest(tipos=tipos):
                linha = excecoes.ler_excecao(evento(
                    dados.EXCECAO_AUTORIZADA,
                    regras + " Justificativa: Evento da reitoria. Operador: "
                    "paulo.silva. Senha do administrador conferida."))
                self.assertEqual(linha["tipos"], tipos)
                self.assertEqual(linha["justificativa"], "Evento da reitoria")
                self.assertEqual(linha["operava"], "paulo.silva")
                self.assertEqual(linha["autorizou"], "ana")

    def test_cada_acao_tem_o_seu_tipo_e_o_cpf_sai_mascarado(self):
        tipos = {dados.VEICULO_SEM_DONO: "Veículo sem o dono",
                 dados.VEICULO_COM_AUTORIZADO: "Veículo com autorizado",
                 dados.LOTACAO_LIBERADA: "Lotação com senha",
                 dados.SAIDA_AUTOMATICA_ENCERRAMENTO: "Saída automática",
                 dados.SAIDA_AUTOMATICA_ATUALIZACAO: "Saída automática",
                 dados.CODIGO_RECUPERACAO_USADO: "Código de recuperação"}
        for acao, tipo in tipos.items():
            linha = excecoes.ler_excecao(evento(acao, "x", nome="Ana Silva",
                                                cpf="52998224725"))
            self.assertEqual(linha["tipos"], [tipo])
            self.assertEqual(linha["pessoa"], "Ana Silva (***.982.247-**)")
            self.assertEqual(linha["operava"], "ana")       # sem "Operador:"
            self.assertEqual(linha["justificativa"], "—")
        self.assertEqual(set(tipos.values()) - set(excecoes.TIPOS), set())

    def test_filtrar(self):
        linhas = [excecoes.ler_excecao(evento(dados.VEICULO_SEM_DONO, "x")),
                  excecoes.ler_excecao(evento(dados.LOTACAO_LIBERADA, "x",
                                              usuario="bia"))]
        self.assertEqual(len(excecoes.filtrar(linhas)), 2)
        self.assertEqual(len(excecoes.filtrar(linhas, "Lotação com senha")), 1)
        self.assertEqual(len(excecoes.filtrar(linhas, autorizou="ana")), 1)
        self.assertEqual(excecoes.filtrar(linhas, "Horário"), [])
        self.assertEqual(excecoes.quem_autorizou(linhas), ["ana", "bia"])


class TestExcecoesNoBanco(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = os.path.join(self.pasta.name, "portaria.db")
        self.banco = dados.Banco(self.caminho)
        self.banco.criar_usuario("Ana Admin", "ana", "admin",
                                 gerar_hash("senha-da-ana"))
        self.banco.criar_usuario("Paulo Porteiro", "paulo", "porteiro", "h",
                                 autor="ana", trocar_senha=False)

    def tearDown(self):
        self.pasta.cleanup()

    def test_cada_tipo_de_excecao_aparece(self):
        hoje = HOJE.strftime("%d/%m/%Y")
        self.banco.inserir(registro(entrada=f"{hoje} 00:01",
                                    saida=f"{hoje} 00:02", placa=""),
                           autor="paulo",
                           autorizacao={"autorizado_por": "ana",
                                        "senha": "senha-da-ana",
                                        "regras": ["Campus fechado."],
                                        "justificativa": "Plantão da obra"})
        self.banco.registrar_evento("paulo", "Saiu do sistema")   # não é exceção
        linhas = [excecoes.ler_excecao(e)
                  for e in self.banco.listar_excecoes(HOJE, HOJE, autor="ana")]
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]["pessoa"], "João Ávila (***.982.247-**)")
        self.assertEqual(linhas[0]["operava"], "paulo")
        self.assertEqual(linhas[0]["justificativa"], "Plantão da obra")

    def test_periodo_na_hora_local_com_os_limites(self):
        con = sqlite3.connect(self.caminho)
        for momento in ("2026-10-19 23:59:59", "2026-10-20 00:00:00",
                        "2026-10-20 23:59:59", "2026-10-21 00:00:00"):
            con.execute("INSERT INTO auditoria (momento, usuario, acao, "
                        "detalhe) VALUES (?, 'ana', ?, 'x')",
                        (momento, dados.VEICULO_SEM_DONO))
        con.commit()
        con.close()
        dia = date(2026, 10, 20)
        momentos = [e["momento"] for e in
                    self.banco.listar_excecoes(dia, dia, autor="ana")]
        self.assertEqual(momentos, ["20/10/2026 23:59:59",
                                    "20/10/2026 00:00:00"])

    def test_porteiro_nao_ve_o_relatorio(self):
        for autor in ("paulo", None):
            with self.assertRaises(dados.ErroDados):
                self.banco.listar_excecoes(HOJE, HOJE, autor=autor)

    def test_csv_com_cpf_mascarado_e_no_historico(self):
        self.banco.inserir(registro(entrada="16/10/2026 08:00",
                                    saida="17/10/2026 09:00", placa=""),
                           autor="ana",
                           autorizacao={"autorizado_por": "ana",
                                        "regras": ["Visita de 25 h (o máximo "
                                                   "é 24 h)."],
                                        "justificativa": "Plantão da obra"})
        caminho = os.path.join(self.pasta.name, "excecoes.csv")
        quantas = backup.exportar_excecoes_csv(self.banco, caminho, HOJE, HOJE,
                                               "ana")
        self.assertEqual(quantas, 1)
        with open(caminho, encoding="utf-8-sig") as f:
            texto = f.read()
        linhas = list(csv.reader(texto.splitlines(), delimiter=";"))
        self.assertEqual(linhas[0], backup.CABECALHO_EXCECOES)
        self.assertEqual(linhas[1][1], "Mais de 24 h")
        self.assertIn("***.982.247-**", linhas[1][2])
        self.assertNotIn("52998224725", texto)
        self.assertIn("Exportação de exceções",
                      [e["acao"] for e in self.banco.listar_eventos()])
        with self.assertRaises(dados.ErroDados):
            backup.exportar_excecoes_csv(self.banco, caminho, HOJE, HOJE,
                                         "paulo")


class TestAbaExcecoes(BaseInterface):
    def setUp(self):
        super().setUp()
        hoje = HOJE.strftime("%d/%m/%Y")
        self.banco.inserir(registro(entrada=f"{hoje} 00:01",
                                    saida=f"{hoje} 00:02", placa=""),
                           autor="ana.admin",
                           autorizacao={"autorizado_por": "ana.admin",
                                        "regras": ["Campus fechado."],
                                        "justificativa": "Plantão da obra"})
        self.banco.registrar_evento("ana.admin", dados.CODIGO_RECUPERACAO_USADO,
                                    "restam 7")
        self.aba = self.app.tela_usuarios
        self.aba.seletor.selecionar("Exceções")
        for caixa in (self.aba.desde, self.aba.ate):
            caixa.delete(0, "end")
            caixa.insert(0, hoje)
        self.aba.atualizar_excecoes()

    def linhas(self):
        tab = self.aba.tabela_excecoes
        return [tab.item(i)["values"] for i in tab.get_children()]

    def test_mostra_as_excecoes_com_o_cpf_mascarado(self):
        linhas = self.linhas()
        self.assertEqual(len(linhas), 2)
        horario = next(l for l in linhas if l[1] == "Horário")
        self.assertEqual(horario[2], "João Ávila (***.982.247-**)")
        self.assertEqual(horario[5], "Plantão da obra")
        self.assertIn("2 exceções", self.aba.lbl_excecoes.cget("text"))

    def test_filtros_de_tipo_e_quem_autorizou(self):
        self.aba.tipo_excecao.set("Código de recuperação")
        self.aba.mostrar_excecoes()
        self.assertEqual([l[1] for l in self.linhas()],
                         ["Código de recuperação"])
        self.assertIn("(de 2, com os filtros)", self.aba.lbl_excecoes.cget("text"))
        self.aba.tipo_excecao.set("Todos")
        self.assertIn("ana.admin", self.aba.autorizou.cget("values"))
        self.aba.autorizou.set("ninguem")
        self.assertEqual(self.aba.mostrar_excecoes(), [])

    def test_data_invalida_avisa(self):
        self.aba.ate.delete(0, "end")
        self.aba.ate.insert(0, "31/02/2026")
        self.aba.atualizar_excecoes()
        self.assertIn("Data inválida", self.aba.faixa_excecoes.lbl.cget("text"))

    def test_exportar_csv(self):
        caminho = os.path.join(self.pasta.name, "excecoes.csv")
        self.arquivo.asksaveasfilename.return_value = caminho
        self.aba.tipo_excecao.set("Horário")
        self.aba.exportar_excecoes()
        with open(caminho, encoding="utf-8-sig") as f:
            self.assertEqual(len(list(csv.reader(f, delimiter=";"))), 2)
        self.assertIn(("ana.admin", "Exportação de exceções"), self.acoes())


class TestPorteiroSemExcecoes(BaseInterface):
    entrar_como = "porteiro"

    def test_porteiro_nao_abre_a_aba(self):
        self.assertIsNone(self.app.aba_usuarios)
        self.assertIsNone(self.app.tela_usuarios)


if __name__ == "__main__":
    unittest.main()
