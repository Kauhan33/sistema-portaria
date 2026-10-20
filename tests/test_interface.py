"""Testa a tela de verdade: preenche campos e clica nos botões (janela oculta)."""

import json
import os
import tempfile
import tkinter as tk
import unittest
from datetime import datetime, timedelta
from unittest import mock

from portaria import dados
from portaria.interface import AppPortaria
from portaria.usuarios import LIMITE_TENTATIVAS, autenticar, gerar_hash
from portaria.validacao import FORMATO, converter_data

VISITA_ANTIGA = {"nome": "Beto Rocha", "cpf": "11144477735",
                 "celular": "31933334444", "placa": "QWE1234",
                 "tipo": "Professor", "entrada": "15/10/2026 07:00",
                 "saida": "15/10/2026 12:00"}


def ha_uma_hora():
    return (datetime.now() - timedelta(hours=1)).strftime(FORMATO)


def criar_usuario(banco, nome, login, perfil, senha):
    id_ = banco.criar_usuario(nome, login, perfil, gerar_hash(senha))
    return {"id": id_, "login": login, "nome": nome, "perfil": perfil}


class BaseInterface(unittest.TestCase):
    """
    Uma janela Tk (oculta) por classe de teste: criar e destruir um tk.Tk()
    custa caro. Cada teste monta o app numa janela Toplevel nova, filha dela.
    """
    entrar_como = "admin"      # "admin", "porteiro" ou None (abre no login)
    com_usuarios = True        # False = banco vazio (primeiro acesso)

    @classmethod
    def setUpClass(cls):
        try:
            cls.raiz = tk.Tk()
        except tk.TclError:
            raise unittest.SkipTest("sem tela disponível para o Tkinter")
        cls.raiz.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.raiz.destroy()

    def nova_janela(self):
        janela = tk.Toplevel(self.raiz)
        janela.withdraw()
        return janela

    def setUp(self):
        self.janela = self.nova_janela()
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho_db = os.path.join(self.pasta.name, "portaria.db")
        self.caminho_json = os.path.join(self.pasta.name, "registros_portaria.json")

        # caixas de mensagem e de diálogo viram "falsas" para o teste não travar
        self.msg = mock.MagicMock()
        self.msg.askyesno.return_value = True
        self.dialogo = mock.MagicMock()
        # todas as telas usam portaria.mensagens: um patch só cobre tudo
        patcher = mock.patch.multiple("portaria.mensagens", messagebox=self.msg,
                                      simpledialog=self.dialogo)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.banco = dados.Banco(self.caminho_db)
        if self.com_usuarios:
            self.admin = criar_usuario(self.banco, "Ana Admin", "ana.admin",
                                       "admin", "senha123")
            self.porteiro = criar_usuario(self.banco, "Paulo Porteiro", "paulo",
                                          "porteiro", "senha456")
        usuario = {"admin": getattr(self, "admin", None),
                   "porteiro": getattr(self, "porteiro", None)}.get(self.entrar_como)
        self.app = AppPortaria(self.caminho_db, self.janela,
                               json_antigo=self.caminho_json, usuario=usuario)

    def tearDown(self):
        # cancela os temporizadores (ex.: o aviso que some em 10 s) para não
        # dispararem no teste seguinte, que usa a mesma janela Tk
        for ident in self.raiz.tk.splitlist(self.raiz.tk.call("after", "info")):
            self.raiz.tk.call("after", "cancel", ident)
        self.app.janela.destroy()
        self.pasta.cleanup()

    def no_banco(self):
        return self.banco.listar()

    def acoes(self):
        return [(e["usuario"], e["acao"]) for e in self.banco.listar_eventos()]

    def preencher(self, nome="Ana Silva", cpf="52998224725",
                  celular="31987654321", placa="", tipo="Visitante"):
        self.app.nome.insert(0, nome)
        self.app.cpf.insert(0, cpf)
        self.app.celular.insert(0, celular)
        self.app.var_placa.set(placa)
        self.app.tipo.set(tipo)

    def cadastrar_um(self):
        self.preencher()
        self.app.cadastrar()
        return self.app.tabela.get_children()[0]

    def textos(self, widget):
        """Texto de todos os widgets dentro de `widget` que têm a opção text."""
        textos = []
        for filho in widget.winfo_children():
            if "text" in filho.keys():
                textos.append(str(filho.cget("text")))
            textos.extend(self.textos(filho))
        return textos


class TestCadastroComoAdmin(BaseInterface):
    def test_cadastrar_salva_no_banco_e_limpa_o_formulario(self):
        self.preencher(placa="abc1d23")
        self.app.cadastrar()
        self.msg.showinfo.assert_called_with("Cadastro",
                                             "Registro cadastrado com sucesso!")
        salvos = self.no_banco()
        self.assertEqual(len(salvos), 1)
        self.assertEqual(salvos[0]["placa"], "ABC1D23")
        self.assertEqual(self.app.nome.get(), "")
        self.assertEqual(self.app.tabela.get_children(), (str(salvos[0]["id"]),))
        self.assertIn(("ana.admin", "Cadastro de entrada"), self.acoes())

    def test_cadastro_invalido_mostra_erro_e_nao_salva(self):
        self.preencher(nome="123 456")
        self.app.cadastrar()
        self.msg.showerror.assert_called_once()
        self.assertEqual(self.no_banco(), [])

    def test_registrar_saida_e_excluir(self):
        linha = self.cadastrar_um()
        self.app.tabela.selection_set(linha)
        self.app.registrar_saida()
        self.assertIsNotNone(converter_data(self.no_banco()[0]["saida"]))
        self.assertNotEqual(self.app.tabela.item(linha)["values"][-1], "— dentro —")

        self.app.tabela.selection_set(linha)
        self.app.excluir_selecionado()
        self.assertEqual(self.no_banco(), [])
        self.assertEqual(self.app.tabela.get_children(), ())
        exclusao = self.banco.listar_eventos()[0]
        self.assertEqual((exclusao["usuario"], exclusao["acao"]),
                         ("ana.admin", "Exclusão de registro"))
        self.assertIn("Ana Silva", exclusao["detalhe"])

    def test_admin_ve_botao_excluir_e_aba_usuarios(self):
        self.assertIsNotNone(self.app.btn_excluir)
        self.assertIsNotNone(self.app.aba_usuarios)
        self.assertIn("Administrador", self.app.lbl_usuario.cget("text"))

    def test_rotulo_mostra_formato_legivel(self):  # falha F4 da v1
        textos = self.textos(self.app.aba_cad)
        self.assertTrue(any("dd/mm/aaaa hh:mm" in t for t in textos))
        self.assertFalse(any("%d" in t for t in textos))

    def test_enter_cadastra_na_aba_cadastro(self):
        self.preencher()
        self.app.cadastrar(event=mock.Mock())          # como se fosse o Enter
        self.assertEqual(len(self.no_banco()), 1)

    def test_enter_fora_da_aba_cadastro_nao_cadastra(self):
        self.preencher()
        for aba in (self.app.aba_pessoas, self.app.aba_bloqueios,
                    self.app.aba_dash, self.app.aba_usuarios):
            with self.subTest(aba=str(aba)):
                self.app.abas.select(aba)
                self.app.cadastrar(event=mock.Mock())
                self.assertEqual(self.no_banco(), [])
        self.msg.showerror.assert_not_called()
        self.msg.showinfo.assert_not_called()


class TestDashboard(BaseInterface):
    def valor(self, chave):
        return self.app.cards[chave][0].cget("text")

    def apoio(self, chave):
        return self.app.cards[chave][1].cget("text")

    def test_sem_registros_mostra_zeros(self):
        self.assertEqual(self.valor("total"), "0")
        self.assertEqual(self.valor("dentro"), "0")
        self.assertEqual(self.valor("Aluno"), "0")
        self.assertEqual(self.valor("permanencia"), "—")
        self.assertEqual(self.apoio("permanencia"), "sem saídas registradas")

    def test_numeros_acompanham_os_registros(self):
        self.banco.inserir(dict(VISITA_ANTIGA))                  # 5 h, com placa
        self.banco.inserir({"nome": "Ana Silva", "cpf": "52998224725",
                            "celular": "31987654321", "placa": "",
                            "tipo": "Visitante", "entrada": ha_uma_hora(),
                            "saida": ""})
        self.app.registros = self.banco.listar()
        self.app.atualizar_tabela()
        self.assertEqual(self.valor("total"), "2")
        self.assertEqual(self.valor("dentro"), "1")
        self.assertEqual(self.apoio("dentro"), "1 já saíram")
        self.assertEqual(self.valor("veiculos"), "1")
        self.assertEqual(self.valor("permanencia"), "5h 00min")
        self.assertEqual(self.apoio("permanencia"), "1 saídas")
        self.assertEqual(self.valor("Visitante"), "1")
        self.assertEqual(self.apoio("Visitante"), "1 dentro agora")
        self.assertEqual(self.valor("Professor"), "1")
        self.assertEqual(self.apoio("Professor"), "0 dentro agora")


class TestPorteiro(BaseInterface):
    entrar_como = "porteiro"

    def test_porteiro_cadastra_e_registra_saida(self):
        linha = self.cadastrar_um()
        self.app.tabela.selection_set(linha)
        self.app.registrar_saida()
        self.assertTrue(self.no_banco()[0]["saida"])
        self.assertIn(("paulo", "Saída registrada"), self.acoes())

    def test_porteiro_nao_ve_botao_excluir_nem_aba_usuarios(self):  # RN02
        self.assertIsNone(self.app.btn_excluir)
        self.assertIsNone(self.app.aba_usuarios)
        self.assertIsNone(self.app.tela_usuarios)

    def test_porteiro_ve_a_aba_pessoas(self):
        self.assertIsNotNone(self.app.tela_pessoas)

    def test_porteiro_nao_consegue_excluir(self):  # RN02
        linha = self.cadastrar_um()
        self.app.tabela.selection_set(linha)
        self.app.excluir_selecionado()
        self.msg.showerror.assert_called_with(
            "Acesso negado", "Somente o administrador pode excluir registros.")
        self.assertEqual(len(self.no_banco()), 1)


class TestLogin(BaseInterface):
    entrar_como = None

    def tentar_login(self, login, senha):
        tela = self.app.tela_login
        tela.campo_login.delete(0, tk.END)
        tela.campo_login.insert(0, login)
        tela.campo_senha.delete(0, tk.END)
        tela.campo_senha.insert(0, senha)
        tela.entrar()

    def test_abre_na_tela_de_login_com_senha_oculta(self):  # RNF02
        self.assertIsNone(self.app.usuario)
        self.assertFalse(self.app.tela_login.primeiro_acesso)
        self.assertEqual(self.app.tela_login.campo_senha.cget("show"), "•")
        self.assertFalse(self.app.sessao.winfo_ismapped())

    def test_login_certo_entra_no_sistema(self):
        self.tentar_login(" Ana.Admin ", "senha123")
        self.assertEqual(self.app.usuario["login"], "ana.admin")
        self.assertTrue(hasattr(self.app, "aba_cad"))
        self.assertIn(("ana.admin", "Entrou no sistema"), self.acoes())

    def test_senha_errada_nao_entra(self):
        self.tentar_login("ana.admin", "errada")
        self.assertIsNone(self.app.usuario)
        self.assertIn("incorretos", self.app.tela_login.lbl_erro.cget("text"))
        self.assertEqual(self.app.tela_login.campo_senha.get(), "")
        self.assertIn(("ana.admin", "Login recusado"), self.acoes())

    def test_enter_em_qualquer_campo_confirma(self):  # Q13
        tela = self.app.tela_login
        self.assertEqual(tela.campos, [tela.campo_login, tela.campo_senha])
        # vale mesmo com cada campo dentro do seu próprio Frame
        for caixa in tela.campos:
            self.assertIsNot(caixa.master, tela.miolo)
            self.assertTrue(caixa.bind("<Return>"))
            self.assertTrue(caixa.bind("<KP_Enter>"))

    def test_usuario_desativado_nao_entra(self):
        self.banco.definir_ativo(self.porteiro["id"], False)
        self.tentar_login("paulo", "senha456")
        self.assertIsNone(self.app.usuario)

    def test_bloqueio_depois_de_muitas_tentativas(self):
        agora = [500.0]
        self.app.tentativas.relogio = lambda: agora[0]
        for _ in range(LIMITE_TENTATIVAS):
            self.tentar_login("ana.admin", "errada")
        self.tentar_login("ana.admin", "senha123")      # certa, mas bloqueado
        self.assertIsNone(self.app.usuario)
        self.assertIn("Aguarde", self.app.tela_login.lbl_erro.cget("text"))
        agora[0] += 31
        self.tentar_login("ana.admin", "senha123")
        self.assertEqual(self.app.usuario["login"], "ana.admin")

    def test_sair_volta_para_o_login(self):
        self.tentar_login("paulo", "senha456")
        self.app.sair()
        self.assertIsNone(self.app.usuario)
        self.assertEqual(self.janela.bind("<Return>"), "")
        self.assertEqual(self.janela.bind("<F2>"), "")
        self.assertIn(("paulo", "Saiu do sistema"), self.acoes())
        self.tentar_login("ana.admin", "senha123")      # outro usuário entra
        self.assertEqual(self.app.usuario["perfil"], "admin")


class TestPrimeiroAcesso(BaseInterface):
    entrar_como = None
    com_usuarios = False

    def preencher_admin(self, senha="segredo1", confirmacao="segredo1"):
        tela = self.app.tela_login
        tela.campo_nome.insert(0, "Carla Dias")
        tela.campo_login.insert(0, "carla")
        tela.campo_senha.insert(0, senha)
        tela.campo_confirmacao.insert(0, confirmacao)
        tela.criar_administrador()

    def test_banco_vazio_pede_para_criar_o_administrador(self):
        tela = self.app.tela_login
        self.assertTrue(tela.primeiro_acesso)
        self.assertEqual(tela.campos, [tela.campo_nome, tela.campo_login,
                                       tela.campo_senha, tela.campo_confirmacao])
        self.assertTrue(all(c.bind("<Return>") for c in tela.campos))

    def test_senha_curta_e_recusada(self):
        self.preencher_admin(senha="123", confirmacao="123")
        self.assertIn("pelo menos", self.app.tela_login.lbl_erro.cget("text"))
        self.assertFalse(self.banco.tem_usuarios())

    def test_cria_administrador_e_entra(self):
        self.preencher_admin()
        self.assertEqual(self.app.usuario["perfil"], "admin")
        self.assertIsNotNone(autenticar(self.banco, "carla", "segredo1"))

    def test_importa_o_json_da_v1_mesmo_antes_do_login(self):
        self.app.janela.destroy()
        with open(self.caminho_json, "w", encoding="utf-8") as f:
            json.dump([{"nome": "Ana Silva", "cpf": "52998224725",
                        "celular": "31987654321", "placa": "", "tipo": "Aluno",
                        "entrada": "15/10/2026 08:00", "saida": ""}], f)
        self.janela = self.nova_janela()
        self.app = AppPortaria(self.caminho_db, self.janela,
                               json_antigo=self.caminho_json)
        self.assertIn("1 registro(s)", self.msg.showinfo.call_args[0][1])
        self.preencher_admin()
        self.assertEqual(len(self.app.tabela.get_children()), 1)


class TestAbaUsuarios(BaseInterface):
    def setUp(self):
        super().setUp()
        self.aba = self.app.tela_usuarios

    def linha_de(self, login):
        return next(i for i in self.aba.tabela.get_children()
                    if self.aba.tabela.item(i)["values"][0] == login)

    def test_lista_os_usuarios(self):
        logins = [self.aba.tabela.item(i)["values"][0]
                  for i in self.aba.tabela.get_children()]
        self.assertEqual(logins, ["ana.admin", "paulo"])

    def test_criar_porteiro(self):
        self.aba.nome.insert(0, "Maria Souza")
        self.aba.login.insert(0, "Maria.Souza")
        self.aba.senha.insert(0, "segredo1")
        self.aba.confirmacao.insert(0, "segredo1")
        self.aba.criar()
        novo = autenticar(self.banco, "maria.souza", "segredo1")
        self.assertEqual(novo["perfil"], "porteiro")
        self.linha_de("maria.souza")      # aparece na lista
        self.assertEqual(self.aba.senha.get(), "")
        self.assertIn(("ana.admin", "Usuário criado"), self.acoes())

    def test_login_repetido_e_recusado(self):
        self.aba.nome.insert(0, "Outro Paulo")
        self.aba.login.insert(0, "paulo")
        self.aba.senha.insert(0, "segredo1")
        self.aba.confirmacao.insert(0, "segredo1")
        self.aba.criar()
        self.assertIn("Já existe", self.msg.showerror.call_args[0][1])

    def test_admin_nao_desativa_a_si_mesmo(self):
        self.aba.tabela.selection_set(self.linha_de("ana.admin"))
        self.aba.alternar_ativo()
        self.assertIn("próprio", self.msg.showerror.call_args[0][1])

    def test_desativar_e_reativar_porteiro(self):
        self.aba.tabela.selection_set(self.linha_de("paulo"))
        self.aba.alternar_ativo()
        self.assertIsNone(autenticar(self.banco, "paulo", "senha456"))
        self.assertEqual(self.aba.tabela.item(self.linha_de("paulo"))["values"][3],
                         "Desativado")
        self.aba.tabela.selection_set(self.linha_de("paulo"))
        self.aba.alternar_ativo()
        self.assertIsNotNone(autenticar(self.banco, "paulo", "senha456"))

    def test_redefinir_senha(self):
        self.dialogo.askstring.side_effect = ["novasenha", "novasenha"]
        self.aba.tabela.selection_set(self.linha_de("paulo"))
        self.aba.redefinir_senha()
        self.assertIsNone(autenticar(self.banco, "paulo", "senha456"))
        self.assertIsNotNone(autenticar(self.banco, "paulo", "novasenha"))
        self.assertIn(("ana.admin", "Senha redefinida"), self.acoes())

    def test_historico_mostra_as_acoes(self):
        self.cadastrar_um()
        self.aba.atualizar()
        acoes = [self.aba.historico.item(i)["values"][2]
                 for i in self.aba.historico.get_children()]
        self.assertEqual(acoes[0], "Cadastro de entrada")


class TestPreenchimentoAutomatico(BaseInterface):
    entrar_como = "porteiro"

    def setUp(self):
        super().setUp()
        self.banco.inserir(dict(VISITA_ANTIGA))

    def digitar_cpf(self, cpf):
        self.app.cpf.delete(0, tk.END)
        self.app.cpf.insert(0, cpf)

    def campos(self):
        a = self.app
        return (a.nome.get(), a.celular.get(), a.var_placa.get(), a.tipo.get())

    def dica(self):
        return self.app.lbl_pessoa.cget("text")

    def test_cpf_de_quem_ja_veio_preenche_os_dados(self):
        self.digitar_cpf("11144477735")
        self.assertEqual(self.campos(),
                         ("Beto Rocha", "31933334444", "QWE1234", "Professor"))
        self.assertIn("Já cadastrado: 1 visita(s)", self.dica())

    def test_basta_o_cpf_para_cadastrar_a_entrada(self):
        self.digitar_cpf("11144477735")
        self.app.cadastrar()
        self.assertEqual(len(self.no_banco()), 2)
        self.assertEqual(self.banco.buscar_pessoa("11144477735")["visitas"], 2)

    def test_cpf_novo_nao_preenche_nada(self):
        self.digitar_cpf("52998224725")
        self.assertEqual(self.campos(), ("", "", "", ""))
        self.assertIn("Pessoa nova", self.dica())

    def test_cpf_invalido_avisa_na_hora(self):
        self.digitar_cpf("12345678900")
        self.assertIn("CPF inválido", self.dica())

    def test_nao_apaga_o_que_ja_foi_digitado(self):
        self.app.nome.insert(0, "Roberto Rocha")
        self.digitar_cpf("11144477735")
        self.assertEqual(self.app.nome.get(), "Roberto Rocha")
        self.assertEqual(self.app.celular.get(), "31933334444")

    def test_trocar_o_cpf_desfaz_so_o_que_foi_preenchido_sozinho(self):
        self.digitar_cpf("11144477735")
        self.app.celular.delete(0, tk.END)
        self.app.celular.insert(0, "31900001111")      # porteiro corrigiu
        self.app.cpf.delete(10, tk.END)                 # apagou um dígito
        self.assertEqual(self.campos(), ("", "31900001111", "", ""))

    def test_avisa_quando_a_pessoa_ja_esta_no_campus(self):
        self.banco.inserir(dict(VISITA_ANTIGA, entrada=ha_uma_hora(), saida=""))
        self.digitar_cpf("11144477735")
        self.assertIn("está no campus desde", self.dica())

    def test_limpar_volta_ao_inicio(self):
        self.digitar_cpf("11144477735")
        self.app.limpar()
        self.assertEqual(self.campos(), ("", "", "", ""))
        self.assertIn("Digite o CPF primeiro", self.dica())


class TestAbaPessoas(BaseInterface):
    def setUp(self):
        super().setUp()
        self.banco.inserir(dict(VISITA_ANTIGA))
        self.banco.inserir({"nome": "Ana Silva", "cpf": "52998224725",
                            "celular": "31987654321", "placa": "",
                            "tipo": "Visitante", "entrada": ha_uma_hora(),
                            "saida": ""})
        self.aba = self.app.tela_pessoas
        self.aba.atualizar()
        self.beto = self.banco.buscar_pessoa("11144477735")["id"]
        self.ana = self.banco.buscar_pessoa("52998224725")["id"]

    def selecionar(self, id_pessoa):
        self.aba.tabela.selection_set(str(id_pessoa))
        self.aba.ao_selecionar()

    def valores(self, id_pessoa):
        return self.aba.tabela.item(str(id_pessoa))["values"]

    def test_lista_pessoas_com_visitas_e_situacao(self):
        self.assertEqual(self.aba.tabela.get_children(),
                         (str(self.ana), str(self.beto)))   # ordem alfabética
        self.assertEqual(self.valores(self.ana)[-1], "No campus")
        self.assertEqual(self.valores(self.beto)[5:], [1, "15/10/2026 07:00", "—"])
        self.assertIn("No campus agora: 1", self.aba.lbl_total.cget("text"))

    def test_busca(self):
        self.aba.busca.insert(0, "beto")
        self.aba.atualizar()
        self.assertEqual(self.aba.tabela.get_children(), (str(self.beto),))

    def test_selecionar_preenche_o_formulario(self):
        self.selecionar(self.beto)
        self.assertEqual(self.aba.nome.get(), "Beto Rocha")
        self.assertEqual(self.aba.var_placa.get(), "QWE1234")
        self.assertIn("111.444.777-35", self.aba.lbl_titulo.cget("text"))

    def test_salvar_alteracoes(self):
        self.selecionar(self.beto)
        self.aba.celular.delete(0, tk.END)
        self.aba.celular.insert(0, "31955556666")
        self.aba.salvar()
        self.assertEqual(self.banco.buscar_pessoa("11144477735")["celular"],
                         "31955556666")
        self.assertIn(("ana.admin", "Dados de pessoa alterados"), self.acoes())

    def test_salvar_dados_invalidos_e_recusado(self):
        self.selecionar(self.beto)
        self.aba.nome.delete(0, tk.END)
        self.aba.nome.insert(0, "Beto")
        self.aba.salvar()
        self.assertIn("nome completo", self.msg.showerror.call_args[0][1])
        self.assertEqual(self.banco.buscar_pessoa("11144477735")["nome"],
                         "Beto Rocha")

    def test_registrar_entrada_abre_o_cadastro_preenchido(self):
        self.selecionar(self.beto)
        self.aba.registrar_entrada()
        self.assertEqual(self.app.abas.select(), str(self.app.aba_cad))
        self.assertEqual(self.app.cpf.get(), "11144477735")
        self.assertEqual(self.app.nome.get(), "Beto Rocha")

    def test_quem_esta_no_campus_nao_ganha_outra_entrada(self):
        self.selecionar(self.ana)
        self.aba.registrar_entrada()
        self.assertIn("já está no campus", self.msg.showwarning.call_args[0][1])
        self.assertEqual(self.app.cpf.get(), "")

    def test_acao_sem_selecao_avisa(self):
        self.aba.salvar()
        self.assertIn("Selecione", self.msg.showwarning.call_args[0][1])



class TestSaidaRapida(BaseInterface):
    entrar_como = "porteiro"

    def setUp(self):
        super().setUp()
        entrada = ha_uma_hora()
        pessoas = [("Beto Rocha", "11144477735", "QWE1234"),
                   ("Ana Silva", "52998224725", "QWE1234"),     # mesma carona
                   ("Duda Reis", "39053344705", "")]
        self.ids = {}
        for nome, cpf, placa in pessoas:
            self.ids[nome.split()[0]] = self.banco.inserir(
                {"nome": nome, "cpf": cpf, "celular": "31987654321",
                 "placa": placa, "tipo": "Visitante", "entrada": entrada,
                 "saida": ""})
        self.app.registros = self.banco.listar()
        self.app.atualizar_tabela()

    def saida(self, nome):
        return next(r["saida"] for r in self.no_banco()
                    if r["id"] == self.ids[nome])

    def digitar(self, texto):
        self.app.campo_saida_rapida.delete(0, tk.END)
        self.app.campo_saida_rapida.insert(0, texto)
        return self.app.saida_rapida()

    def aviso(self):
        return self.app.lbl_aviso.cget("text")

    def desfazer_visivel(self):
        return self.app.btn_desfazer.winfo_manager() != ""   # está no layout

    def test_saida_pelo_cpf_formatado(self):
        resultado = self.digitar("111.444.777-35")
        self.assertEqual(resultado, "break")       # Enter não cadastra nada
        self.assertTrue(self.saida("Beto"))
        self.assertEqual(self.saida("Ana"), "")
        self.assertEqual(self.app.campo_saida_rapida.get(), "")
        self.assertIn("Saída de Beto registrada", self.aviso())
        self.assertTrue(self.desfazer_visivel())
        self.msg.showinfo.assert_not_called()      # não trava com caixinha
        self.assertIn(("paulo", "Saída registrada"), self.acoes())

    def test_placa_de_duas_pessoas_pergunta_antes(self):
        self.msg.askyesno.return_value = False
        self.digitar("qwe-1234")
        self.assertIn("Beto Rocha", self.msg.askyesno.call_args[0][1])
        self.assertEqual((self.saida("Beto"), self.saida("Ana")), ("", ""))
        self.msg.askyesno.return_value = True
        self.digitar("qwe-1234")
        self.assertTrue(self.saida("Beto") and self.saida("Ana"))
        self.assertIn("Beto e Ana", self.aviso())

    def test_cpf_ou_placa_sem_ninguem_dentro(self):
        for texto in ["12345678909", "111444777", "ZZZ9999"]:
            with self.subTest(texto=texto):
                self.digitar(texto)
                self.assertIn("Ninguém no campus", self.msg.showerror.call_args[0][1])
        self.assertTrue(all(not r["saida"] for r in self.no_banco()))

    def test_quem_ja_saiu_nao_e_encontrado_de_novo(self):
        self.digitar("39053344705")
        self.digitar("39053344705")
        self.assertIn("Ninguém no campus", self.msg.showerror.call_args[0][1])

    def test_campo_vazio_avisa(self):
        self.digitar("  ")
        self.assertIn("Digite o CPF", self.msg.showwarning.call_args[0][1])

    def test_duplo_clique_na_linha(self):
        self.assertTrue(self.app.tabela.bind("<Double-1>"))
        self.app.registrar_saida_da_linha(str(self.ids["Duda"]))
        self.assertTrue(self.saida("Duda"))
        self.assertIn("Saída de Duda", self.aviso())

    def test_duplo_clique_em_quem_ja_saiu(self):
        self.app.registrar_saida_da_linha(str(self.ids["Duda"]))
        self.app.registrar_saida_da_linha(str(self.ids["Duda"]))
        self.assertIn("já tem a saída", self.msg.showinfo.call_args[0][1])

    def test_botao_com_varias_linhas_selecionadas(self):
        self.app.tabela.selection_set([str(self.ids["Beto"]), str(self.ids["Duda"])])
        self.app.registrar_saida()
        self.assertTrue(self.saida("Beto") and self.saida("Duda"))
        self.assertEqual(self.saida("Ana"), "")

    def test_desfazer_volta_a_pessoa_para_dentro(self):
        self.digitar("11144477735")
        self.app.desfazer_saida()
        self.assertEqual(self.saida("Beto"), "")
        self.assertIn("Saída desfeita", self.aviso())
        self.assertFalse(self.desfazer_visivel())
        self.assertIn(("paulo", "Saída desfeita"), self.acoes())
        linha = self.app.tabela.item(str(self.ids["Beto"]))["values"]
        self.assertEqual(linha[-1], "— dentro —")

    def test_f2_vai_para_a_saida_rapida(self):
        self.assertTrue(self.janela.bind("<F2>"))


class CasosCorrigir:
    """Testes da janela Corrigir que valem para porteiro e administrador."""

    def setUp(self):
        super().setUp()
        self.hoje = self.banco.inserir(dict(VISITA_ANTIGA, entrada=ha_uma_hora(),
                                            saida=""), autor="paulo")
        self.antigo = self.banco.inserir(dict(VISITA_ANTIGA, nome="Ana Silva",
                                              cpf="52998224725"))
        self.app.registros = self.banco.listar()
        self.app.atualizar_tabela()

    def abrir(self, id_):
        self.app.tabela.selection_set(str(id_))
        self.app.editar_selecionado()
        janela = getattr(self.app, "janela_edicao", None)
        if janela:
            janela.janela.withdraw()
        return janela

    def trocar(self, campo, valor):
        campo.delete(0, tk.END)
        campo.insert(0, valor)

    def test_corrige_registro_de_hoje(self):
        edicao = self.abrir(self.hoje)
        self.assertEqual(edicao.nome.get(), "Beto Rocha")
        self.trocar(edicao.nome, "Roberto Rocha")
        edicao.salvar()
        self.assertEqual(self.banco.buscar(self.hoje)["nome"], "Roberto Rocha")
        self.assertFalse(edicao.janela.winfo_exists())
        self.assertIn("corrigido", self.app.lbl_aviso.cget("text"))
        evento = self.banco.eventos_do_registro(self.hoje)[-1]
        self.assertEqual((evento["usuario"], evento["acao"]),
                         (self.app.usuario["login"], "Registro corrigido"))
        self.assertIn("Nome: Beto Rocha → Roberto Rocha", evento["detalhe"])
        linha = self.app.tabela.item(str(self.hoje))["values"]
        self.assertEqual(linha[0], "Roberto Rocha")

    def test_janela_mostra_o_historico_do_registro(self):
        edicao = self.abrir(self.hoje)
        acoes = [edicao.historico.item(i)["values"][2]
                 for i in edicao.historico.get_children()]
        self.assertEqual(acoes, ["Cadastro de entrada"])
        edicao.historico.selection_set(edicao.historico.get_children()[0])
        edicao.mostrar_detalhe()
        self.assertIn("Cadastro de entrada por paulo",
                      edicao.lbl_detalhe.cget("text"))

    def test_sem_alteracao_avisa(self):
        edicao = self.abrir(self.hoje)
        edicao.salvar()
        self.assertEqual(self.msg.showinfo.call_args[0][1], "Nada foi alterado.")

    def test_correcao_passa_pelas_mesmas_validacoes(self):
        edicao = self.abrir(self.hoje)
        self.trocar(edicao.nome, "Beto 123")
        edicao.salvar()
        self.assertIn("apenas letras", self.msg.showerror.call_args[0][1])
        self.assertEqual(self.banco.buscar(self.hoje)["nome"], "Beto Rocha")

    def test_nao_pode_colocar_saida_antes_da_entrada(self):
        edicao = self.abrir(self.hoje)
        self.trocar(edicao.saida, "01/01/2026 00:00")
        edicao.salvar()
        self.assertIn("anterior à entrada", self.msg.showerror.call_args[0][1])

    def test_nao_burla_o_bloqueio_pela_correcao(self):  # S01 da revisão
        self.banco.bloquear("cpf", "39053344705", "Ameaçou um aluno", "ana.admin")
        edicao = self.abrir(self.hoje)
        self.trocar(edicao.cpf, "39053344705")
        edicao.salvar()
        titulo, msg = self.msg.showerror.call_args[0]
        self.assertEqual(titulo, "Acesso negado")
        self.assertIn("Ameaçou um aluno", msg)
        self.assertEqual(self.banco.buscar(self.hoje)["cpf"], "11144477735")

    def test_selecionar_varios_avisa(self):
        self.app.tabela.selection_set([str(self.hoje), str(self.antigo)])
        self.app.editar_selecionado()
        self.assertIn("um registro só", self.msg.showwarning.call_args[0][1])


class TestCorrigirComoPorteiro(CasosCorrigir, BaseInterface):
    entrar_como = "porteiro"

    def test_porteiro_nao_corrige_registro_antigo(self):  # RN11
        self.assertIsNone(self.abrir(self.antigo))
        self.assertIn("últimas 24 horas",
                      self.msg.showerror.call_args[0][1])

    def test_porteiro_nao_move_registro_para_outro_dia(self):
        edicao = self.abrir(self.hoje)
        self.trocar(edicao.entrada, "10/10/2026 08:00")
        edicao.salvar()
        self.assertIn("últimas 24 horas", self.msg.showerror.call_args[0][1])
        self.assertTrue(edicao.janela.winfo_exists())


class TestCorrigirComoAdmin(CasosCorrigir, BaseInterface):
    entrar_como = "admin"

    def test_admin_corrige_registro_antigo_e_cpf(self):
        edicao = self.abrir(self.antigo)
        self.trocar(edicao.cpf, "39053344705")
        edicao.salvar()
        self.assertEqual(self.banco.buscar(self.antigo)["cpf"], "39053344705")
        self.assertIsNone(self.banco.buscar_pessoa("52998224725"))


class TestBloqueioNoCadastro(BaseInterface):
    entrar_como = "porteiro"

    def setUp(self):
        super().setUp()
        self.banco.inserir(dict(VISITA_ANTIGA))
        self.banco.bloquear("cpf", "11144477735", "Ameaçou um aluno", "ana.admin")
        self.banco.bloquear("placa", "XYZ9A87", "Veículo furtado", "ana.admin")

    def test_alerta_ao_digitar_cpf_bloqueado(self):
        self.app.cpf.insert(0, "11144477735")
        dica = self.app.lbl_pessoa.cget("text")
        self.assertIn("CPF BLOQUEADO — Ameaçou um aluno", dica)
        self.assertEqual(self.app.nome.get(), "Beto Rocha")   # ainda preenche

    def test_alerta_ao_digitar_placa_bloqueada(self):
        self.app.var_placa.set("xyz9a87")
        self.assertIn("PLACA BLOQUEADA — Veículo furtado",
                      self.app.lbl_dica_placa.cget("text"))
        self.app.var_placa.set("XYZ9A8")                       # apagou um
        self.assertIn("ABC1234 ou ABC1D23", self.app.lbl_dica_placa.cget("text"))

    def test_cadastro_de_cpf_bloqueado_e_recusado_e_registrado(self):  # RN12
        self.app.cpf.insert(0, "11144477735")
        self.app.cadastrar()
        titulo, msg = self.msg.showerror.call_args[0]
        self.assertEqual(titulo, "Acesso negado")
        self.assertIn("Ameaçou um aluno", msg)
        self.assertEqual(len(self.no_banco()), 1)             # só a visita antiga
        self.assertIn(("paulo", "Entrada recusada (bloqueio)"), self.acoes())

    def test_bloqueio_vem_antes_das_outras_validacoes(self):
        self.app.var_placa.set("XYZ9A87")                      # só a placa
        self.app.cadastrar()
        self.assertEqual(self.msg.showerror.call_args[0][0], "Acesso negado")

    def test_pessoa_bloqueada_aparece_na_aba_pessoas(self):
        self.app.tela_pessoas.atualizar()
        id_ = str(self.banco.buscar_pessoa("11144477735")["id"])
        self.assertEqual(self.app.tela_pessoas.tabela.item(id_)["values"][-1],
                         "BLOQUEADO")

    def test_porteiro_ve_a_lista_mas_nao_gerencia(self):
        aba = self.app.tela_bloqueios
        self.app.abas.select(self.app.aba_bloqueios)
        self.app.ao_trocar_aba()                 # abrir a aba recarrega
        self.assertIsNone(aba.form)
        self.assertEqual(len(aba.tabela.get_children()), 2)
        aba.bloquear()
        self.assertIn("Somente o administrador", self.msg.showerror.call_args[0][1])


class TestAbaBloqueios(BaseInterface):
    def setUp(self):
        super().setUp()
        self.aba = self.app.tela_bloqueios

    def preencher(self, tipo, valor, motivo):
        self.aba.tipo.set(tipo)
        self.aba.valor.delete(0, tk.END)
        self.aba.valor.insert(0, valor)
        self.aba.motivo.delete(0, tk.END)
        self.aba.motivo.insert(0, motivo)
        self.aba.bloquear()

    def test_admin_bloqueia_cpf(self):
        self.preencher("CPF", "111.444.777-35", "Ameaçou um aluno")
        self.assertIn("Bloquear o CPF 111.444.777-35",
                      self.msg.askyesno.call_args[0][1])
        b = self.banco.listar_bloqueios()[0]
        self.assertEqual((b["valor"], b["criado_por"]), ("11144477735", "ana.admin"))
        self.assertEqual(len(self.aba.tabela.get_children()), 1)
        self.assertEqual(self.aba.valor.get(), "")

    def test_cancelar_a_confirmacao_nao_bloqueia(self):
        self.msg.askyesno.return_value = False
        self.preencher("Placa", "abc-1234", "Estacionou em local proibido")
        self.assertEqual(self.banco.listar_bloqueios(), [])

    def test_dados_invalidos(self):
        self.preencher("CPF", "111.444.777-35", "ab")
        self.assertIn("motivo", self.msg.showerror.call_args[0][1])
        self.preencher("Placa", "AB1", "Motivo válido")
        self.assertIn("Placa inválida", self.msg.showerror.call_args[0][1])

    def test_bloqueio_repetido(self):
        self.preencher("Placa", "ABC1234", "Motivo válido")
        self.preencher("Placa", "abc-1234", "Outro motivo")
        self.assertIn("Esta placa já está bloqueada", self.msg.showerror.call_args[0][1])

    def test_avisa_se_a_pessoa_bloqueada_esta_no_campus(self):
        self.banco.inserir(dict(VISITA_ANTIGA, entrada=ha_uma_hora(), saida=""))
        self.app.registros = self.banco.listar()
        self.preencher("CPF", "11144477735", "Ameaçou um aluno")
        self.assertIn("No campus agora: Beto Rocha",
                      self.msg.showinfo.call_args[0][1])

    def test_remover_bloqueio_e_ver_removidos(self):
        self.preencher("CPF", "11144477735", "Ameaçou um aluno")
        id_ = self.aba.tabela.get_children()[0]
        self.aba.tabela.selection_set(id_)
        self.aba.remover()
        self.assertEqual(self.aba.tabela.get_children(), ())
        self.aba.ver_removidos.set(True)
        self.aba.atualizar()
        situacao = self.aba.tabela.item(id_)["values"][-1]
        self.assertTrue(situacao.startswith("Removido"))
        self.assertIn(("ana.admin", "Bloqueio removido"), self.acoes())

    def test_depois_de_remover_a_entrada_volta_a_ser_aceita(self):
        self.preencher("CPF", "52998224725", "Motivo válido")
        self.aba.tabela.selection_set(self.aba.tabela.get_children()[0])
        self.aba.remover()
        self.app.cpf.insert(0, "52998224725")
        self.app.nome.insert(0, "Ana Silva")
        self.app.celular.insert(0, "31987654321")
        self.app.tipo.set("Visitante")
        self.app.cadastrar()
        self.assertEqual(len(self.no_banco()), 1)


class TestContratoDoApp(BaseInterface):
    def test_nomes_antigos_apontam_para_a_aba_cadastro(self):
        cadastro = self.app.tela_cadastro
        self.assertIs(self.app.cpf, cadastro.cpf)
        self.assertIs(self.app.tabela, cadastro.tabela)
        self.assertEqual(self.app.cadastrar, cadastro.cadastrar)
        self.assertIs(self.app.cards, self.app.tela_dashboard.cards)
        with self.assertRaises(AttributeError):
            self.app.nao_existe

    def test_telas_nao_usam_nada_privado_do_app(self):  # Q10
        pasta = os.path.dirname(dados.__file__)
        for arquivo in os.listdir(pasta):
            if arquivo.startswith("tela_"):
                with self.subTest(arquivo=arquivo):
                    with open(os.path.join(pasta, arquivo), encoding="utf-8") as f:
                        self.assertNotRegex(f.read(), r"app\._")


if __name__ == "__main__":
    unittest.main()
