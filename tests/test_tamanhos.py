"""
Tamanho máximo dos textos (RN33) na camada de validação: validacao.py,
usuarios.py e horarios.py recusam com "X: no máximo N caracteres". A
digitação e a colagem estão em test_componentes; o banco, em
test_regras_no_banco (TestTamanhoMaximoNoBanco).
"""

import unittest
from datetime import date, datetime

from portaria import dados, horarios, validacao
from portaria.horarios import Evento, Horario, hora
from portaria.usuarios import (REGEX_LOGIN, SENHA_MAXIMA, validar_novo_usuario,
                               validar_senha)

from .test_regras_no_banco import SEGUNDA, BaseRegras, autorizacao

AGORA = datetime(2026, 10, 16, 12, 0)


def registro(**mudancas):
    r = {"nome": "Ana Silva", "cpf": "52998224725", "celular": "31987654321",
         "placa": "", "tipo": "Visitante", "entrada": "16/10/2026 08:00",
         "saida": ""}
    r.update(mudancas)
    return r


class TestMaximosNumLugarSo(unittest.TestCase):
    def test_valores_pedidos(self):
        v = validacao
        self.assertEqual(
            (v.MAXIMO_NOME, v.MAXIMO_LOGIN, v.MAXIMO_SENHA,
             v.MAXIMO_JUSTIFICATIVA, v.MAXIMO_MOTIVO, v.MAXIMO_DESCRICAO,
             v.MAXIMO_BUSCA, v.MAXIMO_CPF_OU_PLACA, v.MAXIMO_DATA_HORA,
             v.MAXIMO_DATA, v.MAXIMO_HORA, v.MAXIMO_CPF, v.MAXIMO_CELULAR,
             v.MAXIMO_PLACA),
            (80, 20, 64, 200, 200, 80, 60, 14, 16, 10, 5, 11, 11, 7))
        self.assertEqual(SENHA_MAXIMA, v.MAXIMO_SENHA)
        self.assertTrue(REGEX_LOGIN.match("a" * 20))
        self.assertFalse(REGEX_LOGIN.match("a" * 21))

    def test_mensagem(self):
        self.assertEqual(validacao.checar_tamanho("Nome completo", "x" * 81, 80),
                         (False, "Nome completo: no máximo 80 caracteres."))
        self.assertEqual(validacao.checar_tamanho("Nome completo", "x" * 80, 80),
                         (True, ""))


class TestValidacao(unittest.TestCase):
    def test_nome_da_visita(self):
        longo = "Ana " + "Silva" * 16                  # 84 caracteres
        self.assertEqual(validacao.validar(registro(nome=longo), [], AGORA),
                         (False, "Nome completo: no máximo 80 caracteres."))
        self.assertTrue(validacao.validar(registro(nome=longo[:80]), [], AGORA)[0])
        self.assertFalse(validacao.validar_campos(registro(nome=longo))[0])

    def test_motivo_do_bloqueio(self):
        ok, msg = validacao.validar_bloqueio("cpf", "52998224725", "m" * 201, [])
        self.assertEqual(msg, "Motivo: no máximo 200 caracteres.")
        self.assertTrue(validacao.validar_bloqueio("cpf", "52998224725",
                                                   "m" * 200, [])[0])


class TestUsuarios(unittest.TestCase):
    def test_nome_e_login_do_novo_usuario(self):
        casos = [("N " + "x" * 79, "maria", "Nome completo: no máximo 80"),
                 ("Maria Souza", "m" * 21, "Usuário: no máximo 20")]
        for nome, login, esperado in casos:
            with self.subTest(nome=nome, login=login):
                ok, msg = validar_novo_usuario(nome, login, "segredo-forte",
                                               "segredo-forte", "porteiro",
                                               set())
                self.assertFalse(ok)
                self.assertIn(esperado, msg)

    def test_senha(self):
        longa = "s9" * 33                              # 66 caracteres
        self.assertEqual(validar_senha(longa, longa),
                         (False, "Senha: no máximo 64 caracteres."))
        self.assertTrue(validar_senha(longa[:64], longa[:64])[0])


class TestHorarios(unittest.TestCase):
    def test_justificativa(self):
        self.assertEqual(horarios.ler_justificativa("  Evento   da reitoria "),
                         ("Evento da reitoria", ""))
        self.assertIn("pelo menos", horarios.ler_justificativa("curta")[1])
        self.assertEqual(horarios.ler_justificativa("j" * 201),
                         (None, "Justificativa: no máximo 200 caracteres."))
        self.assertEqual(horarios.ler_justificativa("j" * 200)[1], "")

    def test_descricao_de_feriado_e_evento(self):
        config = horarios.configuracao_padrao()
        self.assertEqual(horarios.ler_feriado("25/12/2026", "d" * 81, config),
                         (None, "Descrição: no máximo 80 caracteres."))
        self.assertEqual(horarios.ler_feriado("25/12/2026", "d" * 80, config),
                         ((date(2026, 12, 25), "d" * 80), ""))
        evento, erro = horarios.ler_evento("24/12/2026", "18:00", "22:00",
                                           "d" * 81, config)
        self.assertEqual(erro, "Descrição: no máximo 80 caracteres.")


class TestTamanhoMaximoNoBanco(BaseRegras):
    """Defesa em profundidade: texto acima do máximo não é gravado, mesmo
    que a tela deixe passar."""

    def recusa(self, operacao, *args, **kwargs):
        with self.assertRaises(dados.ErroDados) as erro:
            operacao(*args, **kwargs)
        self.assertIn("no máximo", str(erro.exception))

    def test_visita_com_nome_longo(self):
        self.recusa(self.banco.inserir,
                    registro(nome="Ana " + "x" * 77, entrada="19/10/2026 08:00"))
        self.assertEqual(self.banco.listar(), [])
        self.banco.inserir(registro(nome="Ana " + "x" * 76,
                                    entrada="19/10/2026 08:00"))   # 80: passa

    def test_correcao_e_cadastro_da_pessoa(self):
        id_ = self.banco.inserir(registro(entrada="19/10/2026 08:00"))
        atual = self.banco.buscar(id_)
        self.recusa(self.banco.editar, id_, dict(atual, nome="A " + "b" * 79),
                    ["Nome"], autor="ana")
        self.recusa(self.banco.editar, id_, dict(atual, celular="3" * 12),
                    ["Celular"], autor="ana")
        pessoa = self.banco.buscar_pessoa("52998224725")
        self.recusa(self.banco.atualizar_pessoa, pessoa["id"], "A " + "b" * 79,
                    "31987654321", "", "Aluno", autor="ana")
        self.recusa(self.banco.atualizar_pessoa, pessoa["id"], "Ana Silva",
                    "31987654321", "ABC1D234", "Aluno", autor="ana")

    def test_bloqueio_feriado_evento_e_usuario(self):
        self.recusa(self.banco.bloquear, "cpf", "52998224725", "m" * 201, "ana")
        self.recusa(self.banco.bloquear, "placa", "ABC1D234", "Motivo ok",
                    "ana")
        self.recusa(self.banco.adicionar_feriado, SEGUNDA, "d" * 81, "ana")
        self.recusa(self.banco.adicionar_evento,
                    Evento(SEGUNDA, Horario(hora("18:00"), hora("22:00")),
                           "d" * 81), "ana")
        self.recusa(self.banco.criar_usuario, "A " + "b" * 79, "maria", "porteiro",
                    "h", autor="ana")
        self.recusa(self.banco.criar_usuario, "Maria Souza", "m" * 21,
                    "porteiro", "h", autor="ana")
        self.banco.bloquear("cpf", "52998224725", "m" * 200, "ana")   # 200: passa

    def test_justificativa_da_excecao(self):
        longa = autorizacao(justificativa="j" * 201)
        self.recusa(self.banco.inserir,
                    registro(entrada="16/10/2026 08:00",
                             saida="17/10/2026 09:00"), autor="paulo",
                    autorizacao=longa)


if __name__ == "__main__":
    unittest.main()
