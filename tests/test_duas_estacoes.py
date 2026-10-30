"""
Duas (ou mais) estações no mesmo banco ao mesmo tempo (revisão 2.5.1):
threads de verdade, cada uma com o seu Banco aberto no mesmo arquivo,
como dois computadores numa pasta compartilhada. O banco tem de decidir
sozinho: uma operação ganha, a outra recebe ErroDados (a mensagem para o
usuário) ou nada a fazer — nunca um erro do SQLite, nunca dado duplicado.
"""
import os
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime

from portaria import dados
from portaria.senhas import gerar_hash

from .test_aleatorio import cpf

AGORA = datetime(2026, 10, 21, 10, 0)


def visita(c, placa="", nome="Ana Souza", entrada="21/10/2026 09:00"):
    return {"nome": nome, "cpf": c, "celular": "31987654321", "placa": placa,
            "tipo": "Aluno", "entrada": entrada, "saida": ""}


class TestDuasEstacoes(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.caminho = os.path.join(self.pasta.name, "portaria.db")
        b = dados.Banco(self.caminho, relogio=lambda: AGORA)
        b.criar_usuario("Ana Admin", "ana", "admin", gerar_hash("senha-da-ana-1"))
        b.criar_usuario("Paulo Porteiro", "paulo", "porteiro",
                        gerar_hash("senha-do-paulo1"), autor="ana",
                        trocar_senha=False)

    def estacao(self):
        return dados.Banco(self.caminho, relogio=lambda: AGORA)

    def ao_mesmo_tempo(self, *tarefas):
        """Roda as tarefas em threads soltas juntas (barreira); devolve
        [("ok", resultado) | ("recusada", mensagem) | ("ERRO", exceção)]."""
        largada = threading.Barrier(len(tarefas))
        resultados = [None] * len(tarefas)

        def rodar(i, tarefa):
            largada.wait()
            try:
                resultados[i] = ("ok", tarefa())
            except dados.ErroDados as e:
                resultados[i] = ("recusada", str(e))
            except Exception as e:                      # noqa: BLE001
                resultados[i] = ("ERRO", repr(e))
        threads = [threading.Thread(target=rodar, args=(i, t))
                   for i, t in enumerate(tarefas)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(60)
        self.assertNotIn("ERRO", [r[0] for r in resultados], resultados)
        return resultados

    def contar(self, consulta, params=()):
        con = sqlite3.connect(self.caminho)
        try:
            return con.execute(consulta, params).fetchone()[0]
        finally:
            con.close()

    def test_mesma_pessoa_entrando_nas_duas(self):
        c = cpf(529_982_247)
        for _ in range(5):
            r = self.ao_mesmo_tempo(
                lambda: self.estacao().inserir(visita(c), autor="paulo"),
                lambda: self.estacao().inserir(visita(c), autor="ana"))
            self.assertEqual(sorted(x[0] for x in r), ["ok", "recusada"], r)
            self.assertEqual(self.contar("SELECT COUNT(*) FROM registros WHERE "
                                         "cpf = ? AND saida = ''", (c,)), 1)
            self.estacao().registrar_saidas(
                [self.contar("SELECT id FROM registros WHERE saida = ''")],
                "21/10/2026 09:30", autor="ana")
            # a próxima rodada entra depois da última saída
            con = sqlite3.connect(self.caminho)
            con.execute("DELETE FROM registros")
            con.commit()
            con.close()

    def test_mesma_saida_nas_duas(self):
        i = self.estacao().inserir(visita(cpf(111_444_777)), autor="paulo")
        r = self.ao_mesmo_tempo(
            lambda: self.estacao().registrar_saidas([i], "21/10/2026 09:40",
                                                   autor="paulo"),
            lambda: self.estacao().registrar_saidas([i], "21/10/2026 09:41",
                                                   autor="ana"))
        gravadas = [x[1] for x in r if x[0] == "ok"]
        self.assertEqual(sorted(len(g) for g in gravadas), [0, 1], r)
        self.assertEqual(self.contar("SELECT COUNT(*) FROM auditoria WHERE "
                                     "acao = 'Saída registrada'"), 1)

    def test_mesmo_carro_entrando_com_duas_pessoas(self):
        r = self.ao_mesmo_tempo(
            lambda: self.estacao().inserir(visita(cpf(111_444_777), "ABC1D23"),
                                           autor="paulo"),
            lambda: self.estacao().inserir(
                visita(cpf(390_533_447), "ABC1D23", "Beto Rocha"), autor="ana"))
        self.assertEqual(sorted(x[0] for x in r), ["ok", "recusada"], r)
        self.assertEqual(self.contar("SELECT COUNT(*) FROM estadias_veiculo "
                                     "WHERE saida = ''"), 1)

    def test_muitas_entradas_juntas_nenhuma_se_perde(self):
        """8 estações, 15 entradas cada, sem pausa: todas gravadas (o
        busy_timeout espera a vez; ninguém vê "banco ocupado")."""
        def estacao(n):
            def tarefa():
                b = self.estacao()
                for k in range(15):
                    b.inserir(visita(cpf(200_000_000 + n * 1000 + k),
                                     nome="Gil Ramos"), autor="paulo")
            return tarefa
        r = self.ao_mesmo_tempo(*(estacao(n) for n in range(8)))
        self.assertEqual([x[0] for x in r], ["ok"] * 8, r)
        self.assertEqual(self.contar("SELECT COUNT(*) FROM registros"), 120)
        self.assertEqual(self.contar("SELECT COUNT(*) FROM pessoas"), 120)

    def test_correcao_com_a_visita_mudada_pela_outra(self):
        b1, b2 = self.estacao(), self.estacao()
        i = b1.inserir(visita(cpf(111_444_777)), autor="paulo")
        lida = b1.buscar(i)                         # a correção abriu aqui
        b2.registrar_saidas([i], "21/10/2026 09:50", autor="ana")
        with self.assertRaises(dados.ErroDados) as erro:
            b1.editar(i, dict(lida, nome="Ana Souza Lima"), ["nome"], "ana",
                      original=lida)
        self.assertEqual(str(erro.exception), dados.REGISTRO_MUDOU)
        self.assertEqual(b1.buscar(i)["saida"], "21/10/2026 09:50")

    def test_cadastro_com_placas_ao_mesmo_tempo(self):
        c = cpf(390_533_447)
        r = self.ao_mesmo_tempo(
            lambda: self.estacao().cadastrar_pessoa(
                c, "Carla Lima", "31987654321", ["ABC1D23", "NEY4829"],
                "Aluno", "paulo"),
            lambda: self.estacao().cadastrar_pessoa(
                c, "Carla Lima", "31987654321", ["QWE1E34"], "Aluno", "ana"))
        self.assertEqual(sorted(x[0] for x in r), ["ok", "recusada"], r)
        self.assertEqual(self.contar("SELECT COUNT(*) FROM pessoas"), 1)
        placas = self.contar("SELECT COUNT(*) FROM placas_pessoa")
        self.assertIn(placas, (1, 2))           # as de uma só das estações


if __name__ == "__main__":
    unittest.main()
