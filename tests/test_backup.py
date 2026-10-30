import csv
import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime

from portaria import backup, dados


def registro(**mudancas):
    r = {"nome": "João Ávila", "cpf": "52998224725", "celular": "31987654321",
         "placa": "QWE1234", "tipo": "Funcionário",
         "entrada": "16/10/2026 08:00", "saida": "16/10/2026 17:30"}
    r.update(mudancas)
    return r


class BaseBackup(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho_db = os.path.join(self.pasta.name, "portaria.db")
        self.pasta_backup = os.path.join(self.pasta.name, "backups")
        self.banco = dados.Banco(self.caminho_db)
        self.banco.criar_usuario("Ana Admin", "ana", "admin", "h")
        self.banco.criar_usuario("Paulo Porteiro", "paulo", "porteiro", "h",
                                 autor="ana", trocar_senha=False)

    def tearDown(self):
        self.pasta.cleanup()


class TestBackup(BaseBackup):
    def contar(self, caminho):
        con = sqlite3.connect(caminho)
        n = con.execute("SELECT COUNT(*) FROM registros").fetchone()[0]
        con.close()
        return n

    def test_backup_manual_e_uma_copia_que_abre(self):
        self.banco.inserir(registro())
        self.banco.inserir(registro(cpf="11144477735", saida=""))
        destino = backup.fazer_backup(self.caminho_db, self.pasta_backup,
                                      agora=datetime(2026, 10, 20, 9, 30, 5))
        self.assertEqual(os.path.basename(destino),
                         "portaria-manual-20261020-093005.db")
        self.assertEqual(self.contar(destino), 2)
        self.assertEqual(len(dados.Banco(destino).listar()), 2)
        self.assertEqual(backup.verificar_banco(destino), (True, ""))

    def test_backup_diario_so_um_por_dia(self):
        hoje = date(2026, 10, 20)
        primeiro = backup.backup_diario(self.caminho_db, self.pasta_backup, hoje=hoje)
        self.assertTrue(primeiro.endswith("portaria-2026-10-20.db"))
        self.banco.inserir(registro())
        self.assertIsNone(backup.backup_diario(self.caminho_db, self.pasta_backup,
                                               hoje=hoje))
        self.assertEqual(self.contar(primeiro), 0)   # não foi sobrescrito

    def test_backup_diario_guarda_so_os_mais_recentes(self):
        manual = backup.fazer_backup(self.caminho_db, self.pasta_backup)
        for dia in range(15, 21):
            backup.backup_diario(self.caminho_db, self.pasta_backup, manter=3,
                                 hoje=date(2026, 10, dia))
        nomes = [os.path.basename(c) for c in backup.backups_diarios(self.pasta_backup)]
        self.assertEqual(nomes, ["portaria-2026-10-18.db", "portaria-2026-10-19.db",
                                 "portaria-2026-10-20.db"])
        self.assertTrue(os.path.exists(manual))      # manual fica fora da rotação

    def test_banco_danificado_nao_vira_backup(self):
        danificado = os.path.join(self.pasta.name, "danificado.db")
        with open(danificado, "wb") as f:
            f.write(b"isto nao e um banco SQLite" * 200)
        with self.assertRaises(dados.ErroDados) as erro:
            backup.backup_diario(danificado, self.pasta_backup)
        self.assertIn("Backup não realizado", str(erro.exception))
        self.assertEqual(backup.backups_diarios(self.pasta_backup), [])
        self.assertFalse(backup.verificar_banco(danificado)[0])

    def test_pasta_de_backup_impossivel_vira_erro_amigavel(self):  # B4
        with open(self.pasta_backup, "w") as f:     # "backups" é um arquivo
            f.write("não é pasta")
        with self.assertRaises(dados.ErroDados) as erro:
            backup.backup_diario(self.caminho_db, hoje=date(2026, 10, 20))
        self.assertIn("Backup não realizado", str(erro.exception))

    def test_pasta_padrao_ao_lado_do_banco(self):
        self.assertEqual(backup.pasta_padrao(self.caminho_db), self.pasta_backup)
        self.assertTrue(backup.backup_diario(self.caminho_db)
                        .startswith(self.pasta_backup))


class TestExportarCsv(BaseBackup):
    def setUp(self):
        super().setUp()
        self.csv = os.path.join(self.pasta.name, "relatorio.csv")
        self.banco.inserir(registro(entrada="14/10/2026 23:59",
                                    saida="15/10/2026 00:10"))       # fora
        self.banco.inserir(registro(entrada="15/10/2026 07:00",
                                    saida="15/10/2026 08:00"))
        self.banco.inserir(registro(nome="Ana Silva", cpf="11144477735",
                                    celular="11998765432", placa="",
                                    tipo="Visitante", entrada="16/10/2026 23:59",
                                    saida=""))
        self.banco.inserir(registro(entrada="17/10/2026 00:00",
                                    saida="17/10/2026 01:00"))       # fora

    def ler(self):
        with open(self.csv, "rb") as f:
            bruto = f.read()
        with open(self.csv, encoding="utf-8-sig", newline="") as f:
            return bruto, list(csv.reader(f, delimiter=";"))

    def test_exporta_o_periodo_formatado_para_o_excel(self):
        n = backup.exportar_csv(self.banco, self.csv, date(2026, 10, 15),
                                date(2026, 10, 16), autor="ana")
        self.assertEqual(n, 2)
        bruto, linhas = self.ler()
        self.assertTrue(bruto.startswith(b"\xef\xbb\xbf"))           # BOM
        self.assertIn("Saída".encode("utf-8"), bruto)
        self.assertEqual(linhas, [
            backup.CABECALHO_CSV,
            ["João Ávila", "529.982.247-25", "(31) 98765-4321", "QWE-1234",
             "Funcionário", "15/10/2026 07:00", "15/10/2026 08:00"],
            ["Ana Silva", "111.444.777-35", "(11) 99876-5432", "", "Visitante",
             "16/10/2026 23:59", ""]])

    def test_exportacao_fica_no_historico(self):
        backup.exportar_csv(self.banco, self.csv, date(2026, 10, 15),
                            date(2026, 10, 16), autor="ana")
        evento = self.banco.listar_eventos()[0]
        self.assertEqual((evento["usuario"], evento["acao"]),
                         ("ana", "Exportação de registros"))
        self.assertIn("2 registro(s) de 15/10/2026 a 16/10/2026", evento["detalhe"])

    def test_falha_ao_gravar_nao_fica_no_historico(self):  # B6
        sem_pasta = os.path.join(self.pasta.name, "nao-existe", "relatorio.csv")
        with self.assertRaises(dados.ErroDados):
            backup.exportar_csv(self.banco, sem_pasta, date(2026, 10, 15),
                                date(2026, 10, 16), autor="ana")
        acoes = [e["acao"] for e in self.banco.listar_eventos()]
        self.assertNotIn("Exportação de registros", acoes)

    def test_porteiro_nao_exporta_e_nada_e_gravado(self):
        with self.assertRaises(dados.ErroDados):
            backup.exportar_csv(self.banco, self.csv, date(2026, 10, 1),
                                date(2026, 10, 31), autor="paulo")
        self.assertFalse(os.path.exists(self.csv))

    def test_texto_que_parece_formula_nao_vira_formula(self):
        with self.banco._conexao() as con:     # dado vindo de fora (ex.: JSON)
            con.execute("UPDATE registros SET nome = '=HYPERLINK(1)'")
        backup.exportar_csv(self.banco, self.csv, date(2026, 10, 15),
                            date(2026, 10, 15), autor="ana")
        self.assertEqual(self.ler()[1][1][0], "'=HYPERLINK(1)")

    def test_periodo_invertido(self):
        with self.assertRaises(dados.ErroDados):
            backup.exportar_csv(self.banco, self.csv, date(2026, 10, 16),
                                date(2026, 10, 15), autor="ana")


if __name__ == "__main__":
    unittest.main()


class TestCelulaDoCsv(unittest.TestCase):
    def test_textos_que_o_excel_leria_como_formula(self):
        """CSV injection (OWASP): =, +, -, @, TAB e CR no começo."""
        for perigoso in ("=1+1", "+5", "-2", "@SUM(A1)", "\t=1", "\r=1"):
            self.assertEqual(backup._celula(perigoso), "'" + perigoso)
        for normal in ("Ana Souza", "52998224725", "", 0, "a=b"):
            self.assertEqual(backup._celula(normal), str(normal))
