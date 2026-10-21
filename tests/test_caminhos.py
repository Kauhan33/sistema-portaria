import os
import tempfile
import unittest
from unittest import mock

from portaria import caminhos


class TestPastaDeDados(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.programa = os.path.join(self.temp.name, "Portaria")
        os.makedirs(self.programa)

    def tearDown(self):
        self.temp.cleanup()

    def escrever_ini(self, texto):
        with open(os.path.join(self.programa, caminhos.ARQUIVO_INSTALACAO), "w",
                  encoding="utf-8") as f:
            f.write(texto)

    def test_portatil_sem_ini_fica_ao_lado_do_programa(self):
        self.assertEqual(caminhos.pasta_de_dados(self.programa), self.programa)

    def test_instalado_usa_a_pasta_do_ini_e_cria(self):
        dados = os.path.join(self.temp.name, "ProgramData", "Portaria")
        self.escrever_ini(f"[Portaria]\ndados={dados}\n")
        self.assertEqual(caminhos.pasta_de_dados(self.programa), dados)
        self.assertTrue(os.path.isdir(dados))

    def test_variavel_de_ambiente_no_ini(self):
        with mock.patch.dict(os.environ, {"PASTA_TESTE": self.temp.name}):
            self.escrever_ini("[Portaria]\ndados=%PASTA_TESTE%\\dados\n")
            self.assertEqual(caminhos.pasta_de_dados(self.programa),
                             os.path.join(self.temp.name, "dados"))

    def test_ini_estragado_ou_sem_a_chave_volta_ao_portatil(self):
        for texto in ["isto não é ini", "[Portaria]\n", "[Outra]\ndados=C:\\x\n"]:
            with self.subTest(texto=texto):
                self.escrever_ini(texto)
                self.assertEqual(caminhos.pasta_de_dados(self.programa),
                                 self.programa)

    def test_pasta_do_ini_sem_permissao_usa_a_do_usuario(self):
        self.escrever_ini("[Portaria]\ndados=Z:\\sem\\permissao\n")
        reserva = os.path.join(self.temp.name, "local")
        criar = os.makedirs

        def makedirs_falso(caminho, exist_ok=False):
            if caminho.startswith("Z:"):
                raise PermissionError(caminho)
            return criar(caminho, exist_ok=exist_ok)

        with mock.patch.dict(os.environ, {"LOCALAPPDATA": reserva}), \
                mock.patch("portaria.caminhos.os.makedirs", makedirs_falso):
            self.assertEqual(caminhos.pasta_de_dados(self.programa),
                             os.path.join(reserva, "Portaria"))


if __name__ == "__main__":
    unittest.main()
