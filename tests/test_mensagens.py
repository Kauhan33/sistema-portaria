"""Testa a porta única das caixas de mensagem (sem abrir janela nenhuma)."""

import unittest
from unittest import mock

from portaria import mensagens


class TestMensagens(unittest.TestCase):
    def setUp(self):
        self.caixa = mock.MagicMock()
        patcher = mock.patch.multiple(mensagens, messagebox=self.caixa)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_cada_funcao_usa_a_caixa_certa(self):
        mensagens.erro("T", "e")
        mensagens.aviso("T", "a")
        mensagens.info("T", "i")
        self.caixa.showerror.assert_called_once_with("T", "e")
        self.caixa.showwarning.assert_called_once_with("T", "a")
        self.caixa.showinfo.assert_called_once_with("T", "i")

    def test_confirmar_devolve_a_resposta(self):
        self.caixa.askyesno.return_value = False
        self.assertFalse(mensagens.confirmar("T", "Excluir?"))

    def test_parent_so_e_repassado_quando_informado(self):
        dono = object()
        mensagens.erro("T", "e", parent=dono)
        self.caixa.showerror.assert_called_once_with("T", "e", parent=dono)


if __name__ == "__main__":
    unittest.main()
