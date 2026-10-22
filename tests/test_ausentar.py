"""
Versão 2.2 — B4: "Ausentar" (cadeado ou Ctrl+L) trava a guarita na hora,
mantém o rascunho do formulário; a mesma senha destrava, outro usuário é
troca de turno; nenhuma janela fica acessível por cima da trava.
"""

from unittest import mock

from portaria import interface

from .test_interface import VISITA_ANTIGA, BaseInterface


class TestAusentar(BaseInterface):
    entrar_como = "porteiro"

    def rascunho(self):
        self.app.nome.insert(0, "Carla Nogueira")
        self.app.cpf.insert(0, "3905334")             # ainda digitando
        self.app.celular.insert(0, "31987654321")

    def destravar(self, login, senha):
        tela = self.app.tela_login
        tela.campo_login.delete(0, "end")
        tela.campo_login.insert(0, login)
        tela.campo_senha.insert(0, senha)
        tela.entrar()

    def test_travar_cobre_a_janela_com_o_login(self):
        self.rascunho()
        self.app.travar()
        self.assertIsNone(self.app.usuario)
        tela = self.app.tela_login
        self.assertEqual(tela.formulario, "travada")
        self.assertEqual(tela.campo_login.get(), "paulo")   # já preenchido
        textos = [w.cget("text") for w in tela.miolo.winfo_children()
                  if w.winfo_class() == "Label"]
        self.assertIn("Guarita travada por Paulo às 10:00", " ".join(textos))
        self.assertFalse(self.app.sessao.winfo_ismapped())
        self.assertEqual(self.janela.bind("<Control-l>"), "")
        self.assertIn(("paulo", interface.GUARITA_TRAVADA), self.acoes())

    def test_a_mesma_senha_destrava_e_devolve_o_rascunho_e_a_pagina(self):
        self.app.ir_para(self.app.aba_pessoas)
        self.rascunho()
        self.app.travar()
        self.destravar("paulo", "senha-errada")
        self.assertIsNone(self.app.usuario)                 # continua travada
        self.destravar("paulo", "senha456")
        self.assertEqual(self.app.usuario["login"], "paulo")
        self.assertEqual(self.app.nome.get(), "Carla Nogueira")
        self.assertEqual(self.app.cpf.get(), "3905334")
        self.assertEqual(self.app.celular.get(), "31987654321")
        self.assertEqual(self.app.abas.select(), str(self.app.aba_pessoas))
        self.assertIn(("paulo", interface.GUARITA_DESTRAVADA), self.acoes())

    def test_outro_usuario_e_troca_de_turno_e_descarta_o_rascunho(self):
        self.rascunho()
        self.app.travar()
        self.destravar("ana.admin", "senha123")
        self.assertEqual(self.app.usuario["login"], "ana.admin")
        self.assertEqual(self.app.nome.get(), "")
        self.assertEqual(self.app.cpf.get(), "")
        evento = next(e for e in self.banco.listar_eventos()
                      if e["acao"] == interface.TROCA_DE_TURNO)
        self.assertIn("travada por paulo", evento["detalhe"])

    def test_atalho_e_cadeado_travam(self):
        self.assertTrue(self.janela.bind("<Control-l>"))
        self.app.btn_travar.invocar()
        self.assertIsNone(self.app.usuario)
        self.assertEqual(self.app.travar(), "break")        # já travada

    def test_nenhuma_janela_fica_por_cima_da_trava(self):
        self.banco.inserir(dict(VISITA_ANTIGA, entrada="21/10/2026 08:00",
                                saida=""), autor="paulo")
        self.app.atualizar_tabela()
        self.app.tabela.selection_set(self.app.tabela.get_children()[0])
        self.app.editar_selecionado()
        corrigir = self.app.tela_cadastro.janela_edicao.janela
        senha = self.app.trocar_senha().janela
        self.app.travar()
        self.assertFalse(corrigir.winfo_exists())
        self.assertFalse(senha.winfo_exists())

    def test_caixa_aberta_na_hora_da_trava_nao_grava_nada(self):
        self.banco.inserir(dict(VISITA_ANTIGA, entrada="21/10/2026 08:00",
                                saida=""), autor="paulo")
        self.app.atualizar_tabela()

        def responde_e_trava(dialogo):
            dialogo.escolher(dialogo.opcoes[0][1])       # "Saiu de carro"...
            self.app.travar()                            # ...e a trava veio
        self.responder_veiculo = responde_e_trava
        self.app.tela_cadastro.campo_saida_rapida.insert(0, "11144477735")
        self.app.tela_cadastro.saida_rapida()
        self.assertTrue(all(not r["saida"] for r in self.no_banco()))
        self.assertIsNotNone(self.banco.estadia_aberta(placa="QWE1234"))
        self.assertIn(mock.call("Sessão encerrada",
                                "A sessão foi encerrada. Entre novamente."),
                      self.msg.showwarning.call_args_list)


if __name__ == "__main__":
    import unittest
    unittest.main()
