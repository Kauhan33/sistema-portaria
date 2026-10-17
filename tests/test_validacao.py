import unittest
from datetime import datetime

from portaria.validacao import (celular_valido, checar_saida, cpf_valido,
                                formatar_celular,
                                formatar_cpf, formatar_placa, nome_valido,
                                normalizar, placa_valida, validar,
                                validar_campos)

AGORA = datetime(2026, 10, 16, 12, 0)
CPF_ANA = "52998224725"
CPF_BETO = "11144477735"


def registro(**mudancas):
    """Registro válido; cada teste troca só o campo que quer testar."""
    campos = dict(nome="Ana Silva", cpf=CPF_ANA, celular="31987654321",
                  placa="", tipo="Visitante", entrada="16/10/2026 08:00",
                  saida="")
    campos.update(mudancas)
    return normalizar(**campos)


def salvo(cpf, entrada, saida=""):
    return {"nome": "Ana Silva", "cpf": cpf, "celular": "31987654321",
            "placa": "", "tipo": "Aluno", "entrada": entrada, "saida": saida}


class TestCampos(unittest.TestCase):
    def test_cpf_valido(self):
        self.assertTrue(cpf_valido(CPF_ANA))
        self.assertTrue(cpf_valido(CPF_BETO))

    def test_cpf_invalido(self):
        for cpf in ["12345678900", "11111111111", "5299822472", "abcdefghijk", ""]:
            with self.subTest(cpf=cpf):
                self.assertFalse(cpf_valido(cpf))

    def test_celular(self):
        self.assertTrue(celular_valido("31987654321"))
        self.assertFalse(celular_valido("31887654321"))   # sem o 9
        self.assertFalse(celular_valido("20987654321"))   # DDD inexistente
        self.assertFalse(celular_valido("3198765432"))    # 10 dígitos

    def test_placa(self):
        self.assertTrue(placa_valida("ABC1234"))
        self.assertTrue(placa_valida("ABC1D23"))
        self.assertFalse(placa_valida("AB12345"))
        self.assertFalse(placa_valida("abc1234"))

    def test_nome(self):
        for nome in ["Ana Silva", "João da Costa", "Ana-Maria D'Ávila"]:
            with self.subTest(nome=nome):
                self.assertTrue(nome_valido(nome))
        for nome in ["Ana", "123 456", "Ana Silva2", "Ana @Silva"]:
            with self.subTest(nome=nome):
                self.assertFalse(nome_valido(nome))

    def test_formatadores(self):
        self.assertEqual(formatar_cpf(CPF_ANA), "529.982.247-25")
        self.assertEqual(formatar_celular("31987654321"), "(31) 98765-4321")
        self.assertEqual(formatar_placa("ABC1234"), "ABC-1234")
        self.assertEqual(formatar_placa("ABC1D23"), "ABC1D23")

    def test_normalizar_limpa_o_texto_digitado(self):
        r = normalizar("  Ana   Silva ", "529.982.247-25", "(31) 98765-4321",
                       " abc1d23 ", "Aluno", " 16/10/2026 08:00 ", " ")
        self.assertEqual(r["nome"], "Ana Silva")
        self.assertEqual(r["cpf"], CPF_ANA)
        self.assertEqual(r["celular"], "31987654321")
        self.assertEqual(r["placa"], "ABC1D23")
        self.assertEqual(r["entrada"], "16/10/2026 08:00")
        self.assertEqual(r["saida"], "")


class TestValidar(unittest.TestCase):
    """Casos de teste do cadastro: cada um diz a entrada e o resultado esperado."""

    def assertRecusa(self, reg, trecho, registros=()):
        ok, msg = validar(reg, list(registros), AGORA)
        self.assertFalse(ok, "deveria recusar")
        self.assertIn(trecho, msg)

    def test_cadastro_completo_e_aceito(self):
        self.assertEqual(validar(registro(), [], AGORA), (True, ""))

    def test_cadastro_com_saida_e_aceito(self):
        ok, _ = validar(registro(saida="16/10/2026 09:30"), [], AGORA)
        self.assertTrue(ok)

    def test_campos_obrigatorios_vazios(self):
        self.assertRecusa(registro(nome=""), "nome")
        self.assertRecusa(registro(cpf=""), "CPF é obrigatório")
        self.assertRecusa(registro(celular=""), "celular é obrigatório")
        self.assertRecusa(registro(tipo=""), "tipo de acesso")

    def test_nome_sem_sobrenome(self):
        self.assertRecusa(registro(nome="Ana"), "nome completo")

    def test_nome_com_numeros(self):  # falha F1 da v1
        self.assertRecusa(registro(nome="123 456"), "apenas letras")

    def test_cpf_com_digito_errado(self):
        self.assertRecusa(registro(cpf="12345678900"), "CPF inválido")

    def test_placa_invalida(self):
        self.assertRecusa(registro(placa="AB12"), "Placa inválida")

    def test_data_em_formato_errado(self):
        self.assertRecusa(registro(entrada="2026-10-16 08:00"), "dd/mm/aaaa hh:mm")
        self.assertRecusa(registro(saida="amanhã"), "dd/mm/aaaa hh:mm")

    def test_entrada_no_futuro(self):  # falha F2 da v1
        self.assertRecusa(registro(entrada="16/10/2030 08:00"), "futuro")

    def test_saida_no_futuro(self):
        self.assertRecusa(registro(saida="16/10/2026 23:00"), "futuro")

    def test_saida_antes_da_entrada(self):
        self.assertRecusa(registro(saida="16/10/2026 07:00"), "anterior à entrada")

    def test_segunda_entrada_aberta_do_mesmo_cpf(self):
        dentro = [salvo(CPF_ANA, "16/10/2026 08:00")]
        self.assertRecusa(registro(entrada="16/10/2026 09:00"), "sem saída", dentro)

    def test_visita_retroativa_com_pessoa_dentro(self):  # falha F3 da v1
        dentro = [salvo(CPF_ANA, "16/10/2026 08:00")]
        reg = registro(entrada="16/10/2026 09:00", saida="16/10/2026 10:00")
        self.assertRecusa(reg, "sem saída", dentro)

    def test_periodos_que_se_cruzam(self):
        antes = [salvo(CPF_ANA, "16/10/2026 08:00", "16/10/2026 10:00")]
        reg = registro(entrada="16/10/2026 09:00", saida="16/10/2026 11:00")
        self.assertRecusa(reg, "nesse período", antes)

    def test_nova_entrada_depois_da_saida_e_aceita(self):
        antes = [salvo(CPF_ANA, "16/10/2026 08:00", "16/10/2026 10:00")]
        ok, _ = validar(registro(entrada="16/10/2026 10:00"), antes, AGORA)
        self.assertTrue(ok)

    def test_validar_campos_da_pessoa_ignora_datas(self):
        reg = registro(entrada="", saida="")
        self.assertEqual(validar_campos(reg), (True, ""))
        self.assertFalse(validar_campos(registro(nome="123 456", entrada=""))[0])

    def test_outro_cpf_dentro_nao_atrapalha(self):
        dentro = [salvo(CPF_BETO, "16/10/2026 08:00")]
        ok, _ = validar(registro(), dentro, AGORA)
        self.assertTrue(ok)


class TestChecarSaida(unittest.TestCase):
    def test_saida_de_quem_esta_dentro(self):
        self.assertEqual(checar_saida(salvo(CPF_ANA, "16/10/2026 08:00"), AGORA),
                         (True, ""))

    def test_quem_ja_saiu(self):
        ok, msg = checar_saida(salvo(CPF_ANA, "16/10/2026 08:00",
                                     "16/10/2026 09:00"), AGORA)
        self.assertFalse(ok)
        self.assertIn("já tem a saída", msg)

    def test_entrada_depois_de_agora(self):
        ok, msg = checar_saida(salvo(CPF_ANA, "16/10/2026 13:00"), AGORA)
        self.assertFalse(ok)
        self.assertIn("anterior à entrada", msg)


if __name__ == "__main__":
    unittest.main()
