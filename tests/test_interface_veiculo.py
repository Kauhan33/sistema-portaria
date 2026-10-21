"""
Tela, rodada 5: o veículo só sai com o dono (RN32), com o administrador
logado (que também redigita a senha) e na correção do registro. Os casos
do porteiro estão em test_interface.TestEstadiaDeVeiculo.
"""

from portaria import validacao

from .test_interface import AGORA, BaseInterface, ha_uma_hora

ANA = "52998224725"


# ----------------------------------------------------------------------
# RN32 com o administrador logado e na correção
# ----------------------------------------------------------------------
class TestVeiculoComAdminLogado(BaseInterface):
    entrar_como = "admin"

    def setUp(self):
        super().setUp()
        self.banco.inserir({"nome": "Ana Silva", "cpf": ANA,
                            "celular": "31987654321", "placa": "ABC1234",
                            "tipo": "Professor", "entrada": ha_uma_hora(),
                            "saida": ""}, autor="paulo")
        self.visita = self.no_banco()[0]["id"]
        self.banco.registrar_saidas([self.visita], AGORA.strftime(
            validacao.FORMATO), autor="paulo")          # saiu a pé
        self.app.atualizar_tabela()
        self.tela = self.app.tela_cadastro

    def estadia(self):
        return self.banco.estadia_aberta(placa="ABC1234")

    def test_admin_logado_tambem_redigita_a_propria_senha(self):
        self.responder_veiculo = "principal"
        vistos = []

        def redigita(dialogo):
            vistos.append((dialogo.pede_senha, dialogo.login.get(),
                           dialogo.lbl_subtitulo.cget("text")))
            dialogo.senha.insert(0, "senha123")
            dialogo.justificativa.insert(0, "Retirada pedida pelo dono")
            dialogo.confirmar()
        self.responder_autorizacao = redigita
        self.tela.campo_saida_rapida.insert(0, "ABC1234")
        self.tela.saida_rapida()
        pede_senha, login, subtitulo = vistos[0]
        self.assertTrue(pede_senha)
        self.assertEqual(login, "ana.admin")          # já vem preenchido
        self.assertIn("digite a sua", subtitulo)
        self.assertIsNone(self.estadia())
        self.assertIn(("ana.admin", "Veículo saiu sem o dono"), self.acoes())

    def test_admin_sem_digitar_a_senha_nao_libera(self):
        self.responder_veiculo = "principal"

        def so_justifica(dialogo):
            dialogo.justificativa.insert(0, "Retirada pedida pelo dono")
            dialogo.confirmar()
        self.responder_autorizacao = so_justifica
        self.tela.campo_saida_rapida.insert(0, "ABC1234")
        self.tela.saida_rapida()
        self.assertTrue(self.autorizacoes[0].erro)
        self.assertIsNotNone(self.estadia())

    def abrir_correcao(self):
        self.app.tabela.selection_set(str(self.visita))
        self.app.editar_selecionado()
        janela = self.app.janela_edicao
        janela.janela.withdraw()
        return janela

    def test_correcao_que_apaga_a_placa_do_carro_que_ficou_pede_a_senha(self):
        edicao = self.abrir_correcao()
        edicao.var_placa.set("")
        edicao.salvar()                               # cancelou a senha
        self.assertEqual(self.banco.buscar(self.visita)["placa"], "ABC1234")
        self.assertIsNotNone(self.estadia())
        self.assertTrue(self.autorizacoes[0].veiculo)
        self.assertIn("Veículo saiu sem o dono: a placa ABC-1234 seria apagada",
                      self.autorizacoes[0].regras[0])
        self.autorizar_com_senha()
        edicao.salvar()
        self.assertEqual(self.banco.buscar(self.visita)["placa"], "")
        self.assertIsNone(self.estadia())
        self.assertIn(("ana.admin", "Veículo saiu sem o dono"), self.acoes())
