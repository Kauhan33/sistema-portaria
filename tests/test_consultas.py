import unittest
from datetime import date, timedelta

from portaria.consultas import (encontrar_dentro, filtrar, formatar_duracao,
                                resumo)

REGISTROS = [
    {"nome": "Ana Silva", "cpf": "52998224725", "celular": "31987654321",
     "placa": "ABC1D23", "tipo": "Visitante",
     "entrada": "16/10/2026 08:10", "saida": "16/10/2026 09:40"},
    {"nome": "Carlos Souza", "cpf": "11144477735", "celular": "31991234567",
     "placa": "", "tipo": "Aluno", "entrada": "16/10/2026 18:20", "saida": ""},
    {"nome": "Mariana Lima", "cpf": "39053344705", "celular": "11998765432",
     "placa": "QWE1234", "tipo": "Professor",
     "entrada": "15/10/2026 07:30", "saida": "15/10/2026 12:00"},
]


class TestFiltrar(unittest.TestCase):
    def nomes(self, texto):
        return [r["nome"] for r in filtrar(REGISTROS, texto)]

    def test_busca_vazia_traz_tudo(self):
        self.assertEqual(len(filtrar(REGISTROS, "")), 3)

    def test_busca_por_nome_sem_diferenciar_maiusculas(self):
        self.assertEqual(self.nomes("ana"), ["Ana Silva", "Mariana Lima"])

    def test_busca_por_cpf_formatado(self):
        self.assertEqual(self.nomes("111.444"), ["Carlos Souza"])

    def test_busca_por_placa_e_tipo(self):
        self.assertEqual(self.nomes("qwe"), ["Mariana Lima"])
        self.assertEqual(self.nomes("visitante"), ["Ana Silva"])


class TestResumo(unittest.TestCase):
    def setUp(self):
        self.r = resumo(REGISTROS, date(2026, 10, 16))

    def test_totais(self):
        self.assertEqual(self.r["total"], 3)
        self.assertEqual(self.r["dentro"], 1)
        self.assertEqual(self.r["entradas_hoje"], 2)
        self.assertEqual(self.r["com_veiculo"], 2)
        self.assertEqual(self.r["por_tipo"]["Aluno"], [1, 1])
        self.assertEqual(self.r["por_tipo"]["Entregador"], [0, 0])

    def test_ultimos_7_dias(self):
        dias = self.r["por_dia"]
        self.assertEqual(len(dias), 7)
        self.assertEqual(dias[date(2026, 10, 16)], 2)
        self.assertEqual(dias[date(2026, 10, 15)], 1)

    def test_permanencia_media(self):
        # 1h30 e 4h30 -> média de 3h
        self.assertEqual(self.r["permanencia_media"], timedelta(hours=3))
        self.assertEqual(self.r["saidas"], 2)

    def test_sem_registros(self):
        vazio = resumo([], date(2026, 10, 16))
        self.assertEqual(vazio["total"], 0)
        self.assertIsNone(vazio["permanencia_media"])

    def test_formatar_duracao(self):
        self.assertEqual(formatar_duracao(timedelta(minutes=45)), "45min")
        self.assertEqual(formatar_duracao(timedelta(hours=3, minutes=5)), "3h 05min")


class TestEncontrarDentro(unittest.TestCase):
    """Saída rápida: só quem está no campus, só correspondência exata."""

    DENTRO = REGISTROS + [
        {"nome": "Duda Reis", "cpf": "52998224725", "celular": "31900000000",
         "placa": "QWE1234", "tipo": "Aluno",
         "entrada": "16/10/2026 19:00", "saida": ""},
    ]

    def nomes(self, texto):
        return [r["nome"] for r in encontrar_dentro(self.DENTRO, texto)]

    def test_por_cpf_com_ou_sem_pontuacao(self):
        self.assertEqual(self.nomes("11144477735"), ["Carlos Souza"])
        self.assertEqual(self.nomes(" 111.444.777-35 "), ["Carlos Souza"])

    def test_por_placa_com_hifen_ou_minuscula(self):
        # Mariana usou QWE1234 numa visita encerrada: não entra na conta
        self.assertEqual(self.nomes("qwe-1234"), ["Duda Reis"])

    def test_quem_ja_saiu_nao_aparece(self):
        self.assertEqual(self.nomes("52998224725"), ["Duda Reis"])  # Ana já saiu
        self.assertEqual(self.nomes("ABC1D23"), [])                  # placa da Ana

    def test_cpf_incompleto_ou_vazio_nao_acha_ninguem(self):
        for texto in ["1114447773", "111", "", "   "]:
            with self.subTest(texto=texto):
                self.assertEqual(self.nomes(texto), [])


if __name__ == "__main__":
    unittest.main()
