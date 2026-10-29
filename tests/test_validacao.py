import unittest
from datetime import datetime

from portaria import validacao
from portaria.validacao import (celular_valido, checar_desativacao,
                                checar_desativacao_correcao,
                                checar_saida, cpf_valido,
                                normalizar_desativacao, validar_desativacao,
                                formatar_celular,
                                formatar_cpf, formatar_placa, mascarar_cpf,
                                mascarar_cpfs_no_texto, nome_valido,
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

    def test_placa_antiga_ou_mercosul(self):
        for placa in ("NEY4829", "ney4829", "NEY48", "ABC1234"):
            with self.subTest(placa=placa):
                self.assertTrue(validacao.placa_antiga(placa))
        for placa in ("BRA2E19", "BRA2", "NEY4", "", None, "AB12345",
                      "NEY48291"):
            with self.subTest(placa=placa):
                self.assertFalse(validacao.placa_antiga(placa))

    def test_normalizar_limpa_o_texto_digitado(self):
        r = normalizar("  Ana   Silva ", "529.982.247-25", "(31) 98765-4321",
                       " abc1d23 ", "Aluno", " 16/10/2026 08:00 ", " ")
        self.assertEqual(r["nome"], "Ana Silva")
        self.assertEqual(r["cpf"], CPF_ANA)
        self.assertEqual(r["celular"], "31987654321")
        self.assertEqual(r["placa"], "ABC1D23")
        self.assertEqual(r["entrada"], "16/10/2026 08:00")
        self.assertEqual(r["saida"], "")

    def test_normalizar_completa_a_hora_de_um_digito(self):
        """QA2 B4: '9:5' era gravado certo, mas o aviso dizia 'às 6 9:5'
        e a correção via mudança onde não havia."""
        r = normalizar("Ana Silva", CPF_ANA, "31987654321", "", "Aluno",
                       "16/10/2026 9:5", "16/10/2026 10:7")
        self.assertEqual(r["entrada"], "16/10/2026 09:05")
        self.assertEqual(r["saida"], "16/10/2026 10:07")


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

    def test_ano_absurdo_e_recusado(self):
        """QA2 B5: '0026' passava e virava 'dia já encerrado'."""
        self.assertRecusa(registro(entrada="21/10/0026 10:00"), "Confira o ano")
        self.assertRecusa(registro(entrada="01/01/0001 00:00"), "Confira o ano")

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


def desativacao(tipo, valor, motivo="Agrediu o porteiro"):
    return {"tipo": tipo, "valor": valor, "motivo": motivo,
            "criado_em": "10/10/2026 08:00", "criado_por": "ana"}


class TestDesativacao(unittest.TestCase):
    def test_normalizar(self):
        self.assertEqual(normalizar_desativacao("cpf", "529.982.247-25"), CPF_ANA)
        self.assertEqual(normalizar_desativacao("placa", " abc-1234 "), "ABC1234")

    def test_validar_desativacao(self):
        ativos = [desativacao("cpf", CPF_BETO)]
        self.assertEqual(validar_desativacao("cpf", CPF_ANA, "Furto na biblioteca",
                                          ativos), (True, ""))
        self.assertEqual(validar_desativacao("placa", "ABC1D23", "Estacionou na "
                                          "vaga de ambulância", ativos), (True, ""))
        casos = {
            "tipo vazio": (("", CPF_ANA, "Motivo qualquer"), "pessoa (CPF)"),
            "cpf inválido": (("cpf", "12345678900", "Motivo qualquer"), "CPF inválido"),
            "placa inválida": (("placa", "AB12", "Motivo qualquer"), "Placa inválida"),
            "sem motivo": (("cpf", CPF_ANA, "  ab "), "motivo"),
            "já desativada": (("cpf", CPF_BETO, "Motivo qualquer"),
                              "Esta pessoa já está desativada"),
        }
        for caso, (args, trecho) in casos.items():
            with self.subTest(caso):
                ok, msg = validar_desativacao(*args, ativos)
                self.assertFalse(ok)
                self.assertIn(trecho, msg)

    def test_entrada_de_pessoa_desativada_e_recusada(self):  # RN12
        ok, msg = checar_desativacao(registro(), [desativacao("cpf", CPF_ANA)])
        self.assertFalse(ok)
        self.assertIn("Acesso negado", msg)
        self.assertIn("Motivo: Agrediu o porteiro", msg)
        self.assertIn("Pessoa desativada: CPF 529.982.247-25", msg)
        self.assertIn("Só um administrador pode reativar", msg)

    def test_entrada_com_veiculo_desativado_e_recusada(self):
        ok, msg = checar_desativacao(registro(placa="abc1d23"),
                                  [desativacao("placa", "ABC1D23")])
        self.assertFalse(ok)
        self.assertIn("Veículo desativado: Placa ABC1D23", msg)

    def test_correcao_nao_pode_colocar_desativado_no_campus(self):  # S01
        ativos = [desativacao("cpf", CPF_ANA), desativacao("placa", "ABC1D23")]
        livre = registro(cpf=CPF_BETO)
        trocou_cpf = registro()
        trocou_placa = registro(cpf=CPF_BETO, placa="ABC1D23")
        self.assertFalse(checar_desativacao_correcao(livre, trocou_cpf, ativos)[0])
        self.assertFalse(checar_desativacao_correcao(livre, trocou_placa, ativos)[0])
        encerrada = registro(saida="16/10/2026 09:00")
        reaberta = registro(saida="")
        self.assertFalse(checar_desativacao_correcao(encerrada, reaberta, ativos)[0])

    def test_correcao_de_nome_de_quem_foi_desativado_depois(self):
        ativos = [desativacao("cpf", CPF_ANA)]
        for saida in ["16/10/2026 09:00", ""]:          # encerrada ou aberta
            with self.subTest(saida=saida):
                antes = registro(saida=saida)
                depois = registro(nome="Ana Silva Costa", saida=saida)
                self.assertEqual(checar_desativacao_correcao(antes, depois, ativos),
                                 (True, ""))

    def test_sem_desativacao_ou_a_pe(self):
        ativos = [desativacao("cpf", CPF_BETO), desativacao("placa", "ABC1D23")]
        self.assertEqual(checar_desativacao(registro(), ativos), (True, ""))
        self.assertEqual(checar_desativacao(registro(placa=""), []), (True, ""))


class TestMascararCpf(unittest.TestCase):  # S08 (LGPD)
    def test_mostra_so_o_meio(self):
        self.assertEqual(mascarar_cpf(CPF_ANA), "***.982.247-**")
        self.assertEqual(mascarar_cpf("529.982.247-25"), "***.982.247-**")
        self.assertEqual(mascarar_cpf(""), "")
        self.assertEqual(mascarar_cpf("123"), "***")

    def test_mascara_cpfs_num_texto_sem_mexer_no_celular(self):
        texto = ("#3 Ana Silva, CPF 52998224725, celular 31987654321; "
                 "CPF: 529.982.247-25 → 111.444.777-35")
        self.assertEqual(mascarar_cpfs_no_texto(texto),
                         "#3 Ana Silva, CPF ***.982.247-**, celular 31987654321; "
                         "CPF: ***.982.247-** → ***.444.777-**")
        self.assertEqual(mascarar_cpfs_no_texto(""), "")


if __name__ == "__main__":
    unittest.main()
