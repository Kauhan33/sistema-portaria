"""Senhas (hash e bloqueio progressivo) e códigos de recuperação: funções
puras de senhas.py, sem banco nem tela."""

import unittest
from datetime import datetime, timedelta

from portaria import senhas


class TestHash(unittest.TestCase):
    def test_confere_so_a_senha_certa(self):
        guardado = senhas.gerar_hash("segredo-forte")
        self.assertTrue(senhas.conferir_senha("segredo-forte", guardado))
        self.assertFalse(senhas.conferir_senha("segredo-fraco", guardado))
        self.assertFalse(senhas.conferir_senha("segredo-forte", "h"))
        self.assertFalse(senhas.conferir_senha("x", None))

    def test_hash_nao_contem_a_senha(self):
        self.assertNotIn("segredo-forte", senhas.gerar_hash("segredo-forte"))


class TestContarFalha(unittest.TestCase):
    AGORA = datetime(2026, 10, 21, 10, 0)

    def test_quatro_falhas_nao_travam(self):
        estado = (0, 0)
        for i in range(1, senhas.LIMITE_TENTATIVAS):
            falhas, bloqueios, ate, segundos = senhas.contar_falha(
                *estado, self.AGORA)
            self.assertEqual((falhas, ate, segundos), (i, None, None))
            estado = (falhas, bloqueios)

    def test_quinta_trava_e_o_tempo_dobra(self):
        falhas, bloqueios, ate, segundos = senhas.contar_falha(
            senhas.LIMITE_TENTATIVAS - 1, 0, self.AGORA)
        self.assertEqual((falhas, bloqueios, segundos), (0, 1, 30))
        self.assertEqual(ate, self.AGORA + timedelta(seconds=30))
        *_, segundos = senhas.contar_falha(senhas.LIMITE_TENTATIVAS - 1, 1,
                                           self.AGORA)
        self.assertEqual(segundos, 60)
        *_, segundos = senhas.contar_falha(senhas.LIMITE_TENTATIVAS - 1, 20,
                                           self.AGORA)
        self.assertEqual(segundos, senhas.SEGUNDOS_BLOQUEIO_MAXIMO)


if __name__ == "__main__":
    unittest.main()
