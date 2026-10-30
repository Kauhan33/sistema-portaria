"""
Fuzz das funções que recebem o texto digitado ou colado (revisão 2.5.1):
validação da visita, datas, horas, placas, desativação, regras de horário,
validade de quem pode retirar, vagas, senha e login. Com qualquer texto
(acentos, emoji, controle, números enormes, SQL, só espaços), elas
respondem "pode" ou "não pode" com mensagem: nunca levantam exceção.
"""
import random
import string
import unittest
from datetime import date, datetime

from portaria import horarios, usuarios, validacao, veiculos

VOLTAS = 3000
PEDACOS = ["", " ", "  ", "0", "00", "29", "02", "2028", "2025", "1900", "9999",
           "/", ":", "-", ".", "24:00", "23:59", "00:00", "29/02/2025",
           "29/02/2028", "31/04/2026", "21/10/2026 15:20", "21/10/26",
           "52998224725", "529.982.247-25", "11111111111", "ABC1D23",
           "ABC-1234", "abc1d23", "Ana", "Souza", "d'Ávila", "Zé", "\U0001F600",
           "\u0000", "\t", "\n", "=1+1", "' OR 1=1 --", "%", "_", "\\", "é",
           "Ç", "１２３", "9" * 30, "-5", "1e9", "NaN", "inf"]


def texto(r):
    if r.random() < 0.3:
        return "".join(r.choice(string.printable + "áéíóúçãõÁÉ ")
                       for _ in range(r.randint(0, 25)))
    return "".join(r.choice(PEDACOS) for _ in range(r.randint(0, 4)))


class TestEntradasEstranhas(unittest.TestCase):
    def setUp(self):
        self.r = random.Random(33)
        self.config = horarios.configuracao_padrao()
        self.agora = datetime(2026, 10, 21, 15, 20)

    def sem_excecao(self, nome, funcao, *args):
        try:
            return funcao(*args)
        except Exception as e:                          # noqa: BLE001
            self.fail(f"{nome}{args!r}: {type(e).__name__}: {e}")

    def test_visita(self):
        for _ in range(VOLTAS):
            r = self.sem_excecao("normalizar", validacao.normalizar,
                                 texto(self.r), texto(self.r), texto(self.r),
                                 texto(self.r),
                                 self.r.choice(validacao.TIPOS_ACESSO + [""]),
                                 texto(self.r), texto(self.r))
            ok, msg = self.sem_excecao("validar_campos", validacao.validar_campos, r)
            self.assertTrue(ok or msg)
            ok, msg = self.sem_excecao("validar", validacao.validar, r, [],
                                       self.agora)
            self.assertTrue(ok or msg)
            self.sem_excecao("checar_saida", validacao.checar_saida, r, self.agora)

    def test_campos_soltos(self):
        for _ in range(VOLTAS):
            t = texto(self.r)
            for nome, f in (("converter_data", validacao.converter_data),
                            ("cpf_valido", validacao.cpf_valido),
                            ("celular_valido", validacao.celular_valido),
                            ("nome_valido", validacao.nome_valido),
                            ("placa_valida", validacao.placa_valida),
                            ("placa_antiga", validacao.placa_antiga),
                            ("mascarar_cpfs_no_texto",
                             validacao.mascarar_cpfs_no_texto),
                            ("normalizar_placa", validacao.normalizar_placa)):
                self.sem_excecao(nome, f, t)
            ok, msg, _ = self.sem_excecao("validar_placas",
                                          validacao.validar_placas, [t, t])
            self.assertTrue(ok or msg)
            for tipo in ("cpf", "placa"):
                ok, msg = self.sem_excecao("validar_desativacao",
                                           validacao.validar_desativacao,
                                           tipo, t, texto(self.r), [])
                self.assertTrue(ok or msg)

    def assert_le(self, nome, f, *args):
        """As leituras do horário devolvem o valor ou levantam ValueError
        (a mensagem da tela); nunca outra exceção."""
        try:
            f(*args)
        except ValueError as e:
            self.assertTrue(str(e), nome)
        except Exception as e:                          # noqa: BLE001
            self.fail(f"{nome}{args!r}: {type(e).__name__}: {e}")

    def test_configuracoes_e_regras(self):
        for _ in range(VOLTAS):
            t, u = texto(self.r), texto(self.r)
            self.assert_le("ler_hora", horarios.ler_hora, t, "Abre")
            self.assert_le("ler_horario", horarios.ler_horario, t, u, "Segunda")
            self.assert_le("ler_minutos", horarios.ler_minutos, t, "Minutos")
            self.assert_le("ler_parametros", horarios.ler_parametros, t, u)
            self.assert_le("ler_data", horarios.ler_data, t)
            self.assert_le("ler_justificativa", horarios.ler_justificativa, t)
            self.assert_le("ler_feriado", horarios.ler_feriado, t, u,
                           self.config)
            self.assert_le("ler_evento", horarios.ler_evento, t, u,
                           texto(self.r), texto(self.r), self.config)
            self.assert_le("ler_regra", horarios.ler_regra,
                           "Aluno", self.r.random() < 0.5, t, u,
                           self.r.random() < 0.5, texto(self.r), texto(self.r))
            self.assert_le("ler_vagas", veiculos.ler_vagas, t)
            self.assert_le("ler_validade", veiculos.ler_validade, t)
            ok_ou_erro = self.sem_excecao(
                "validar_nova_validade", veiculos.validar_nova_validade, t,
                date(2026, 10, 21))
            self.assertIsNotNone(ok_ou_erro)
            self.sem_excecao("validar_autorizado", veiculos.validar_autorizado,
                             {"cpf": "52998224725", "placa": "ABC1D23",
                              "nome": "Ana Souza"}, t, u, texto(self.r),
                             date(2026, 10, 21))

    def test_contas(self):
        for _ in range(VOLTAS):
            t, u = texto(self.r), texto(self.r)
            self.sem_excecao("normalizar_login", usuarios.normalizar_login, t)
            ok, msg = self.sem_excecao("validar_senha", usuarios.validar_senha,
                                       t, self.r.choice([t, u]), u)
            self.assertTrue(ok or msg)
            ok, msg = self.sem_excecao(
                "validar_novo_usuario", usuarios.validar_novo_usuario, t, u,
                texto(self.r), texto(self.r),
                self.r.choice(["admin", "porteiro", t]), [])
            self.assertTrue(ok or msg)


if __name__ == "__main__":
    unittest.main()
