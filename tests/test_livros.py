"""
As telas da versão 3.2: Funcionários, Autorizações (com a emissão), Encomendas
e Chaves; quem procura, crachá e autorização no Cadastro; recado de turno;
Painel por período; relatório; privacidade, histórico e dados de demonstração
em Configurações; tamanho da letra.
"""
import sqlite3
import tkinter as tk
from datetime import timedelta
from unittest import mock

from portaria import estilo, impressao
from portaria.validacao import AUT_CANCELADA, AUT_VALIDA

from .test_interface import AGORA, VISITA_ANTIGA, BaseInterface

ANA, BETO, CARLA = "52998224725", "11144477735", "39053344705"
HOJE = AGORA.strftime("%d/%m/%Y")


def primeira(pagina):
    pagina.tabela.selection_set(pagina.tabela.get_children()[0])
    pagina.app.janela.update()


class BasePagina(BaseInterface):
    PAGINA = ""

    def setUp(self):
        super().setUp()
        if self.PAGINA:
            self.app.ir_para(getattr(self.app, "aba_" + self.PAGINA))
            self.pagina = getattr(self.app, {"dash": "tela_dashboard"}.get(
                self.PAGINA, "tela_" + self.PAGINA))

    def evento(self):
        return self.banco.listar_eventos()[0]["acao"]


class TestChavesNaTela(BasePagina):
    PAGINA = "chaves"

    def setUp(self):
        super().setUp()
        self.lab = self.banco.cadastrar_chave("Laboratório 2", "Bloco B",
                                              "ana.admin")
        self.pagina.atualizar()
        primeira(self.pagina)

    def test_nova_chave(self):
        d = self.pagina.novo()
        self.assertFalse(d.salvar())                       # nome vazio
        self.assertIn("nome da chave", d.faixa.lbl.cget("text"))
        d.nome.insert(0, "Auditório")
        d.local.insert(0, "Bloco A")
        self.assertTrue(d.salvar())
        self.assertEqual(len(self.pagina.tabela.get_children()), 2)
        self.assertIn("2 chaves", self.pagina.lbl_total.cget("text"))

    def test_lista_longa_mostra_so_as_primeiras_e_avisa(self):
        for nome in ("Auditório", "Almoxarifado", "Biblioteca"):
            self.banco.cadastrar_chave(nome, "", "ana.admin")
        with mock.patch("portaria.tela_livros.LIMITE_LISTA", 2):
            self.pagina.atualizar()
            self.assertEqual(len(self.pagina.tabela.get_children()), 2)
            total = self.pagina.lbl_total.cget("text")
            self.assertIn("4 chaves", total)                # conta todas
            self.assertIn("mostrando os 2 primeiros", total)
            self.pagina.busca.insert(0, "lab")              # a pesquisa acha
            self.pagina.atualizar()
            self.assertEqual(len(self.pagina.tabela.get_children()), 1)
            self.assertNotIn("mostrando", self.pagina.lbl_total.cget("text"))

    def test_entregar_e_devolver(self):
        p = self.pagina
        self.assertEqual(p.btn_devolver.cget("state"), "disabled")
        d = p.entregar()
        d.cpf.insert(0, "12345678900")
        d.nome.insert(0, "Carla Nogueira")
        self.assertFalse(d.salvar())                       # CPF inválido
        d.cpf.delete(0, tk.END)
        self.assertTrue(d.salvar())
        linha = p.tabela.item(str(self.lab))
        self.assertEqual(linha["text"], "Emprestada")
        self.assertEqual(p.tabela.set(str(self.lab), "quem"), "Carla Nogueira")
        self.assertEqual(p.faixa.tipo, "sucesso")
        p.tabela.selection_set(str(self.lab))
        self.janela.update()
        self.assertEqual(p.btn_entregar.cget("state"), "disabled")
        p.devolver()
        self.assertEqual(p.tabela.item(str(self.lab))["text"], "Na portaria")
        self.assertEqual(self.evento(), "Chave devolvida")

    def test_cpf_de_quem_tem_cadastro_puxa_o_nome(self):
        self.banco.inserir(dict(VISITA_ANTIGA, placa=""), autor="ana.admin")
        d = self.pagina.entregar()
        d.cpf.insert(0, BETO)
        self.assertEqual(d.nome.get(), "Beto Rocha")
        d.fechar()

    def test_outra_estacao_entregou_antes(self):
        d = self.pagina.entregar()
        d.nome.insert(0, "Carla Nogueira")
        self.banco.entregar_chave(self.lab, "Beto Rocha", "paulo")
        d.salvar()
        self.msg.showerror.assert_called()
        self.assertEqual(self.pagina.tabela.set(str(self.lab), "quem"),
                         "Beto Rocha")

    def test_historico_e_remover(self):
        self.banco.entregar_chave(self.lab, "Carla Nogueira", "paulo")
        self.banco.devolver_chave(self.lab, "paulo")
        d = self.pagina.ver_historico()
        self.assertEqual(len(d.tabela.get_children()), 1)
        d.fechar()
        self.msg.askyesno.return_value = False
        self.pagina.remover()
        self.assertEqual(len(self.banco.listar_chaves()), 1)
        self.msg.askyesno.return_value = True
        primeira(self.pagina)
        self.pagina.remover()
        self.assertEqual(self.banco.listar_chaves(), [])

    def test_filtro_so_emprestadas(self):
        self.pagina.chk_filtro.invoke()
        self.assertEqual(self.pagina.tabela.get_children(), ())


class TestChavesDoPorteiro(BasePagina):
    PAGINA = "chaves"
    entrar_como = "porteiro"

    def test_porteiro_entrega_mas_nao_cadastra_nem_remove(self):
        self.assertIsNone(self.pagina.btn_novo)
        self.assertIsNone(self.pagina.btn_remover)
        chave = self.banco.cadastrar_chave("Auditório", "", "ana.admin")
        self.pagina.atualizar()
        primeira(self.pagina)
        d = self.pagina.entregar()
        d.nome.insert(0, "Carla Nogueira")
        d.cpf.insert(0, CARLA)
        self.assertTrue(d.salvar())
        self.assertIn("***", self.pagina.faixa.lbl.cget("text") + "***")
        self.pagina.tabela.selection_set(str(chave))
        self.janela.update()
        self.assertNotIn(CARLA, self.pagina.faixa.lbl.cget("text"))


class TestEncomendasNaTela(BasePagina):
    PAGINA = "encomendas"

    def nova(self):
        d = self.pagina.novo()
        d.destinatario.insert(0, "Helena Souza")
        d.remetente.insert(0, "Correios")
        d.descricao.insert(0, "Envelope registrado")
        self.assertTrue(d.salvar())
        primeira(self.pagina)

    def test_validacao_no_dialogo(self):
        d = self.pagina.novo()
        self.assertFalse(d.salvar())
        self.assertIn("destinatário", d.faixa.lbl.cget("text"))
        d.fechar()
        self.assertEqual(self.banco.listar_encomendas(), [])

    def test_registrar_retirar_e_filtrar(self):
        self.nova()
        p = self.pagina
        linha = p.tabela.get_children()[0]
        self.assertEqual(p.tabela.item(linha)["text"], "Aguardando retirada")
        self.assertIn("1 aguardando", p.lbl_total.cget("text"))
        d = p.retirar()
        d.nome.insert(0, "Helena Souza")
        self.assertTrue(d.salvar())
        self.assertEqual(p.tabela.item(linha)["text"], "Retirada")
        p.tabela.selection_set(linha)
        self.janela.update()
        self.assertEqual(p.btn_retirar.cget("state"), "disabled")
        self.assertIn("Retirada em", p.faixa.lbl.cget("text"))
        p.chk_filtro.invoke()
        self.assertEqual(p.tabela.get_children(), ())

    def test_excluir_pede_confirmacao(self):
        self.nova()
        self.msg.askyesno.return_value = False
        self.pagina.excluir()
        self.assertEqual(len(self.banco.listar_encomendas()), 1)
        self.msg.askyesno.return_value = True
        self.pagina.excluir()
        self.assertEqual(self.banco.listar_encomendas(), [])

    def test_pesquisa(self):
        self.nova()
        self.pagina.busca.insert(0, "kalunga")
        self.pagina.atualizar()
        self.assertEqual(self.pagina.tabela.get_children(), ())


class TestAutorizacoesNaTela(BasePagina):
    PAGINA = "autorizacoes"

    def criar(self, cpf=ANA, nome="Ana Silva"):
        d = self.pagina.novo()
        d.cpf.insert(0, cpf)
        d.nome.insert(0, nome)
        d.empresa.insert(0, "Alfa Ltda")
        d.anfitriao.insert(0, "Diretoria")
        d.motivo.insert(0, "Reunião sobre o contrato")
        self.assertTrue(d.salvar())
        return self.banco.listar_autorizacoes()[0]["id"]

    def test_o_dialogo_abre_com_hoje_e_recusa_o_que_falta(self):
        d = self.pagina.novo()
        self.assertEqual((d.de.get(), d.ate.get()), (HOJE, HOJE))
        self.assertFalse(d.salvar())
        self.msg.showerror.assert_called()
        d.fechar()
        self.assertEqual(self.banco.listar_autorizacoes(), [])

    def test_criar_aparece_valida_e_selecionada(self):
        id_ = self.criar()
        p = self.pagina
        self.assertEqual(p.tabela.item(str(id_))["text"], AUT_VALIDA)
        self.assertEqual(p.tabela.selection(), (str(id_),))
        self.assertIn("1 válida hoje", p.lbl_total.cget("text"))
        self.assertIn("Reunião sobre o contrato", p.faixa.lbl.cget("text") +
                      p.detalhe(p.selecionado()))

    def test_emitir_abre_a_pagina_para_imprimir(self):
        id_ = self.criar()
        caminho = self.pagina.emitir()
        self.addCleanup(impressao.apagar_temporarios)
        self.navegador.open.assert_called_once()
        with open(caminho, encoding="utf-8") as f:
            pagina = f.read()
        self.assertIn(f"Autorização de entrada nº {id_:03d}", pagina)
        self.assertIn("Ana Silva", pagina)
        self.assertIn("529.982.247-25", pagina)             # admin vê o CPF
        self.assertIn("Diretoria", pagina)
        self.assertEqual(self.banco.buscar_autorizacao(id_)["emissoes"], 1)
        self.assertEqual(self.evento(), "Autorização de entrada emitida")

    def test_o_que_foi_digitado_nao_vira_marcacao_na_pagina(self):
        d = self.pagina.novo()
        d.cpf.insert(0, ANA)
        d.nome.insert(0, "Ana Silva")
        d.anfitriao.insert(0, "<script>alert(1)</script>")
        d.motivo.insert(0, "<b>negrito</b>")
        self.assertTrue(d.salvar())
        caminho = self.pagina.emitir()
        self.addCleanup(impressao.apagar_temporarios)
        with open(caminho, encoding="utf-8") as f:
            pagina = f.read()
        self.assertNotIn("<script>alert", pagina)
        self.assertIn("&lt;script&gt;", pagina)

    def test_cancelar_e_botoes(self):
        id_ = self.criar()
        self.pagina.cancelar()
        self.assertEqual(self.pagina.tabela.item(str(id_))["text"],
                         AUT_CANCELADA)
        self.pagina.tabela.selection_set(str(id_))
        self.janela.update()
        for botao in (self.pagina.btn_emitir, self.pagina.btn_entrada,
                      self.pagina.btn_cancelar):
            self.assertEqual(botao.cget("state"), "disabled")
        self.assertIsNone(self.pagina.emitir())

    def test_registrar_entrada_leva_ao_cadastro_com_os_dados(self):
        id_ = self.criar()
        self.pagina.registrar_entrada()
        app = self.app
        self.assertEqual(app.abas.select(), str(app.aba_cad))
        self.assertEqual((app.nome.get(), app.empresa.get(), app.motivo.get(),
                          app.anfitriao.get()),
                         ("Ana Silva", "Alfa Ltda", "Reunião sobre o contrato",
                          "Diretoria"))
        self.assertIn(f"autorização nº {id_:03d}", app.lbl_pessoa.cget("text"))
        app.celular.insert(0, "31987654321")
        app.tipo.set("Visitante")
        app.cadastrar()
        self.assertEqual(len(self.no_banco()), 1)
        self.assertEqual(self.banco.buscar_autorizacao(id_)["usos"], 1)

    def test_faixa_da_autorizacao_cabe_numa_linha_na_tela_pequena(self):
        """O nome longo de quem autorizou vira reticências: a faixa não
        quebra em duas linhas e não empurra o Cadastrar para fora (1366x768
        de notebook = 1093x536 px lógicos)."""
        d = self.pagina.novo()
        d.cpf.insert(0, ANA)
        d.nome.insert(0, "Ana Silva")
        d.anfitriao.insert(0, "Coordenação de Engenharia de Computação e "
                              "Sistemas")
        d.motivo.insert(0, "Reunião sobre o contrato")
        self.assertTrue(d.salvar())
        app = self.app
        self.janela.deiconify()
        self.janela.geometry("1093x536")
        app.ir_para(app.aba_cad)
        app.cpf.insert(0, ANA)
        self.janela.update()
        texto = app.lbl_pessoa.cget("text")
        self.assertIn("Entrada autorizada por Coordenação de Engenhar…", texto)
        self.assertLessEqual(len(texto), 75)
        self.assertEqual(app.anfitriao.get(), "Coordenação de Engenharia de "
                                              "Computação e Sistemas")
        tela = app.tela_cadastro
        base = self.janela.winfo_rooty() + 536
        for botao in (tela.btn_cadastrar, tela.btn_limpar, tela.btn_cancelar):
            self.assertTrue(botao.winfo_ismapped())
            self.assertLessEqual(botao.winfo_rooty() + botao.winfo_height(),
                                 base)

    def test_trocar_o_cpf_limpa_o_que_veio_da_autorizacao(self):
        self.criar()
        app = self.app
        app.ir_para(app.aba_cad)
        app.cpf.insert(0, ANA)
        self.assertEqual(app.nome.get(), "Ana Silva")
        app.cpf.delete(0, tk.END)
        self.assertEqual((app.nome.get(), app.motivo.get(),
                          app.anfitriao.get()), ("", "", ""))

    def test_pessoa_desativada_continua_barrada_mesmo_autorizada(self):
        self.criar()
        self.banco.desativar("cpf", ANA, "Motivo válido", "ana.admin")
        app = self.app
        app.ir_para(app.aba_cad)
        app.cpf.insert(0, ANA)
        self.assertEqual(app.tela_cadastro.aviso_pessoa.tipo, "erro")
        self.assertIn("desativada", app.lbl_pessoa.cget("text"))


class TestAutorizacoesDoPorteiro(BasePagina):
    PAGINA = "autorizacoes"
    entrar_como = "porteiro"

    def test_cpf_mascarado_na_lista_e_na_pagina_impressa(self):
        # (o banco do app usa o relógio fixo dos testes)
        id_ = self.app.banco.criar_autorizacao(
            ANA, "Ana Silva", "", "Reunião", "Diretoria", HOJE, HOJE, "paulo")
        self.pagina.atualizar()
        self.assertEqual(self.pagina.tabela.set(str(id_), "cpf"),
                         "***.982.247-**")
        primeira(self.pagina)
        caminho = self.pagina.emitir()
        self.addCleanup(impressao.apagar_temporarios)
        with open(caminho, encoding="utf-8") as f:
            self.assertNotIn("529.982.247-25", f.read())


class TestFuncionariosNaTela(BasePagina):
    PAGINA = "funcionarios"

    def novo(self, **mudancas):
        campos = {"cpf": ANA, "celular": "31987654321", "nome": "Ana Silva",
                  "empresa": "UNA", "matricula": "F-0012",
                  "setor": "Secretaria", "cargo": "Assistente"}
        campos.update(mudancas)
        d = self.pagina.novo()
        for nome, valor in campos.items():
            getattr(d, nome).insert(0, valor)
        return d

    def test_novo_funcionario(self):
        self.assertTrue(self.novo().salvar())
        p = self.pagina
        linha = p.tabela.get_children()[0]
        self.assertEqual(p.tabela.item(linha)["text"], "Não veio")
        self.assertEqual((p.tabela.set(linha, "matricula"),
                          p.tabela.set(linha, "setor")),
                         ("F-0012", "Secretaria"))
        pessoa = self.banco.buscar_pessoa(ANA)
        self.assertEqual((pessoa["tipo"], pessoa["empresa"]),
                         ("Funcionário", "UNA"))

    def test_validacao_e_cpf_que_ja_existe(self):
        for mudanca, trecho in (({"cpf": "12345678900"}, "CPF"),
                                ({"nome": "Ana"}, "nome"),
                                ({"empresa": ""}, "empresa"),
                                ({"matricula": "F 12!"}, "Matrícula")):
            with self.subTest(mudanca=mudanca):
                d = self.novo(**{k: "" for k in mudanca})
                for campo, valor in mudanca.items():
                    getattr(d, campo).delete(0, tk.END)
                    getattr(d, campo).insert(0, valor)
                self.assertFalse(d.salvar())
                self.assertIn(trecho.lower(), d.faixa.lbl.cget("text").lower())
                d.fechar()
        self.banco.inserir(dict(VISITA_ANTIGA, placa=""), autor="ana.admin")
        d = self.novo(cpf=BETO)
        self.assertFalse(d.salvar())
        self.assertIn("já é de Beto Rocha", d.faixa.lbl.cget("text"))
        d.fechar()

    def test_editar_dados_e_ponto_de_hoje(self):
        self.novo().salvar()
        primeira(self.pagina)
        d = self.pagina.editar_dados()
        d.cargo.delete(0, tk.END)
        d.cargo.insert(0, "Coordenadora")
        self.assertTrue(d.salvar())
        linha = self.pagina.tabela.get_children()[0]
        self.assertEqual(self.pagina.tabela.set(linha, "cargo"), "Coordenadora")
        # registrar entrada: abre o Cadastro com a pessoa
        primeira(self.pagina)
        self.pagina.registrar_entrada()
        app = self.app
        self.assertEqual(app.abas.select(), str(app.aba_cad))
        self.assertEqual(app.nome.get(), "Ana Silva")
        app.motivo.insert(0, "Expediente")
        app.cadastrar()
        app.ir_para(app.aba_funcionarios)
        self.assertEqual(self.pagina.tabela.item(linha)["text"], "Dentro")
        self.assertEqual(self.pagina.tabela.set(linha, "entrada"),
                         AGORA.strftime("%H:%M"))
        primeira(self.pagina)
        self.assertEqual(self.pagina.btn_entrada.cget("state"), "disabled")
        self.pagina.chk_filtro.invoke()
        self.assertEqual(len(self.pagina.tabela.get_children()), 1)


class TestCrachaNoCadastro(BaseInterface):
    def preencher_tudo(self, cpf=ANA, nome="Ana Silva", cracha="7",
                       anfitriao="Coordenação"):
        self.preencher(nome=nome, cpf=cpf)
        self.app.cracha.insert(0, cracha)
        self.app.anfitriao.insert(0, anfitriao)

    def test_cadastro_guarda_o_cracha_e_quem_procura(self):
        self.preencher_tudo()
        self.app.cadastrar()
        r = self.no_banco()[0]
        self.assertEqual((r["cracha"], r["anfitriao"]), ("7", "Coordenação"))
        self.assertIn("Crachá 7.", self.app.lbl_pessoa.cget("text"))
        self.assertEqual((self.app.cracha.get(), self.app.anfitriao.get()),
                         ("", ""))

    def test_cracha_em_uso_e_recusado(self):
        self.preencher_tudo()
        self.app.cadastrar()
        self.preencher_tudo(cpf=BETO, nome="Beto Rocha")
        self.app.cadastrar()
        self.assertEqual(len(self.no_banco()), 1)
        self.assertIn("O crachá 7 está com",
                      self.msg.showerror.call_args[0][1])

    def test_cracha_so_aceita_numeros_e_tres_digitos(self):
        self.app.cracha.insert(0, "12ab345")
        self.assertEqual(self.app.cracha.get(), "")
        self.app.cracha.insert(0, "123")
        self.app.cracha.insert(tk.END, "4")
        self.assertEqual(self.app.cracha.get(), "123")

    def test_filtro_dentro_mostra_o_cracha_e_a_saida_pede_de_volta(self):
        self.preencher_tudo()
        self.app.cadastrar()
        tela = self.app.tela_cadastro
        self.app.ir_para(self.app.aba_controle)
        tela.filtro.set("Dentro")
        tela.atualizar_tabela()
        self.assertIn("Cracha", tela.tabela["displaycolumns"])
        self.assertNotIn("Saida", tela.tabela["displaycolumns"])
        linha = tela.tabela.get_children()[0]
        self.assertEqual(tela.tabela.set(linha, "Cracha"), "7")
        tela.tabela.selection_set(linha)
        tela.btn_saida.invoke()
        self.assertIn("Recolha o crachá 7", tela.lbl_aviso.cget("text"))
        tela.filtro.set("Todos")
        tela.atualizar_tabela()
        self.assertIn("Saida", tela.tabela["displaycolumns"])


class TestRecadoDeTurno(BaseInterface):
    def test_recado_aparece_no_controle_ate_ser_lido(self):
        app = self.app
        tela = app.tela_cadastro
        self.assertIsNone(tela.recado)
        app.ir_para(app.aba_ocorrencias)
        d = app.tela_ocorrencias.novo_recado()
        self.assertFalse(d.salvar())                       # vazio
        d.texto.insert(0, "O portão lateral fica fechado até amanhã.")
        self.assertTrue(d.salvar())
        self.janela.deiconify()
        app.ir_para(app.aba_controle)
        self.janela.update()
        self.assertTrue(tela.faixa_recado.winfo_ismapped())
        self.assertIn("portão lateral", tela.faixa_recado.lbl.cget("text"))
        tela.marcar_recado_lido()
        self.janela.update()
        self.assertFalse(tela.faixa_recado.winfo_ismapped())
        self.assertEqual(self.banco.listar_recados()[0]["lido_por"],
                         "ana.admin")

    def test_o_mais_antigo_primeiro(self):
        self.banco.deixar_recado("Primeiro recado do dia", "paulo")
        self.banco.deixar_recado("Segundo recado do dia", "paulo")
        tela = self.app.tela_cadastro
        tela.atualizar_alertas()
        self.assertIn("Primeiro", tela.faixa_recado.lbl.cget("text"))
        tela.marcar_recado_lido()
        self.assertIn("Segundo", tela.faixa_recado.lbl.cget("text"))


class TestPainelERelatorio(BasePagina):
    PAGINA = "dash"

    def setUp(self):
        BaseInterface.setUp(self)
        for dias, cpf in ((0, ANA), (0, BETO), (3, CARLA)):
            entrada = AGORA - timedelta(days=dias, hours=1)
            self.banco.inserir(dict(
                VISITA_ANTIGA, cpf=cpf, placa="",
                entrada=entrada.strftime("%d/%m/%Y %H:%M"),
                saida=(entrada + timedelta(minutes=20)).strftime(
                    "%d/%m/%Y %H:%M")), autor="ana.admin")
        self.app.ir_para(self.app.aba_dash)
        self.painel = self.app.tela_dashboard

    def test_por_dia_em_7_e_30_dias(self):
        p = self.painel
        self.assertEqual(len(p.dados["dias"]), 7)
        self.assertEqual(p.dados["dias"][-1][1], 2)            # hoje
        self.assertEqual(sum(n for _, n in p.dados["dias"]), 3)
        p.seletor_periodo.selecionar("30 dias")
        self.assertEqual(len(p.dados["dias"]), 30)
        self.assertEqual(sum(n for _, n in p.dados["dias"]), 3)

    def test_por_hora_destaca_o_pico(self):
        p = self.painel
        p.seletor_visao.selecionar("Por hora")
        self.assertEqual(len(p.dados["dias"]), 24)
        hora = (AGORA - timedelta(hours=1)).hour
        self.assertEqual(p.destaque, hora)
        self.assertEqual(p.nome_destaque, f"{hora:02d}h")
        self.assertEqual(p.dados["dias"][hora][1], 3)
        self.assertIn("pico", p.lbl_apoio_dias.cget("text"))
        p.seletor_visao.selecionar("Por dia")
        self.assertIsNone(p.destaque)

    def test_grafico_desenha_nos_dois_modos_sem_erro(self):
        self.janela.deiconify()
        self.janela.update()
        p = self.painel
        for visao in ("Por hora", "Por dia"):
            for periodo in ("30 dias", "7 dias"):
                p.seletor_visao.selecionar(visao)
                p.seletor_periodo.selecionar(periodo)
                self.janela.update()
                self.assertTrue(p.cv_dias.find_all())

    def test_relatorio_para_imprimir(self):
        d = self.painel.abrir_relatorio()
        d.periodo(AGORA.date() - timedelta(days=6), AGORA.date())
        caminho = d.confirmar()
        self.addCleanup(impressao.apagar_temporarios)
        self.navegador.open.assert_called_once()
        with open(caminho, encoding="utf-8") as f:
            pagina = f.read()
        self.assertIn("Relatório de movimento", pagina)
        self.assertIn("Beto Rocha", pagina)
        self.assertIn("<b>3</b>visitas", pagina)
        self.assertEqual(self.evento(), "Relatório emitido")

    def test_relatorio_recusa_data_invalida(self):
        d = self.painel.abrir_relatorio()
        d.desde.delete(0, tk.END)
        d.desde.insert(0, "99/99/2026")
        self.assertIsNone(d.confirmar())
        self.navegador.open.assert_not_called()
        d.fechar()


class TestPainelDoPorteiro(BasePagina):
    PAGINA = "dash"
    entrar_como = "porteiro"

    def test_porteiro_nao_tem_relatorio(self):
        self.assertIsNone(self.pagina.btn_relatorio)
        self.assertIsNone(self.pagina.abrir_relatorio())
        self.msg.showerror.assert_called()


class TestDadosEPrivacidade(BasePagina):
    PAGINA = "configuracoes"

    def setUp(self):
        super().setUp()
        self.pagina.seletor.selecionar("Dados e privacidade")

    def test_cabe_na_tela_pequena_com_os_tres_avisos(self):
        cfg = self.pagina
        self.janela.deiconify()
        self.janela.geometry("1093x536")
        cfg.preencher_demonstracao()
        cfg.conferir_historico()
        cfg.anonimizar()                          # CPF vazio: aviso de erro
        self.janela.update()
        base = self.janela.winfo_rooty() + 536
        direita = self.janela.winfo_rootx() + 1093
        for peca in (cfg.faixa_demonstracao, cfg.faixa_historico,
                     cfg.faixa_privacidade, cfg.btn_prazo, cfg.btn_anonimizar,
                     cfg.btn_demonstracao, cfg.btn_historico):
            self.assertTrue(peca.winfo_ismapped(), peca)
            self.assertLessEqual(peca.winfo_rooty() + peca.winfo_height(),
                                 base, peca)
            self.assertLessEqual(peca.winfo_rootx() + peca.winfo_width(),
                                 direita, peca)

    def test_dados_de_demonstracao(self):
        cfg = self.pagina
        self.msg.askyesno.return_value = False
        self.assertIsNone(cfg.preencher_demonstracao())
        self.assertEqual(self.no_banco(), [])
        self.msg.askyesno.return_value = True
        feito = cfg.preencher_demonstracao()
        self.assertEqual(feito["pessoas"], 12)
        self.assertEqual(cfg.faixa_demonstracao.tipo, "sucesso")
        self.assertTrue(self.app.registros)                 # o Controle já vê
        cfg.preencher_demonstracao()
        self.assertEqual(cfg.faixa_demonstracao.tipo, "info")

    def test_todas_as_paginas_abrem_com_os_dados_de_demonstracao(self):
        self.pagina.preencher_demonstracao()
        self.janela.deiconify()
        for aba in self.app.itens_menu:
            self.app.ir_para(aba)
            self.janela.update()
        self.assertEqual(len(self.app.tela_chaves.tabela.get_children()), 4)
        self.assertEqual(len(self.app.tela_encomendas.tabela.get_children()), 3)
        self.assertEqual(len(self.app.tela_autorizacoes.tabela.get_children()),
                         2)
        self.assertEqual(len(self.app.tela_funcionarios.tabela.get_children()),
                         2)

    def test_conferir_o_historico(self):
        cfg = self.pagina
        self.assertTrue(cfg.conferir_historico()["integro"])
        self.assertEqual(cfg.faixa_historico.tipo, "sucesso")
        con = sqlite3.connect(self.caminho_db)
        con.execute("UPDATE auditoria SET detalhe = 'x' WHERE id = 1")
        con.commit()
        con.close()
        cfg.conferir_historico()
        self.assertEqual(cfg.faixa_historico.tipo, "erro")
        self.assertIn("ação nº 1", cfg.faixa_historico.lbl.cget("text"))

    def test_anonimizar_pela_tela(self):
        cfg = self.pagina
        self.banco.inserir(dict(VISITA_ANTIGA, placa=""), autor="ana.admin")
        for cpf, justificativa, trecho in (
                ("123", "Pedido do titular por e-mail", "CPF inválido"),
                (BETO, "curta", "justificativa"),
                (ANA, "Pedido do titular por e-mail", "Não há pessoa")):
            for caixa, valor in ((cfg.cpf_anonimizar, cpf),
                                 (cfg.justificativa_anonimizar, justificativa)):
                caixa.delete(0, tk.END)
                caixa.insert(0, valor)
            cfg.anonimizar()
            self.assertIn(trecho.lower(),
                          cfg.faixa_privacidade.lbl.cget("text").lower())
        cfg.cpf_anonimizar.delete(0, tk.END)
        cfg.cpf_anonimizar.insert(0, BETO)
        self.msg.askyesno.return_value = False
        cfg.anonimizar()
        self.assertIsNotNone(self.banco.buscar_pessoa(BETO))
        self.msg.askyesno.return_value = True
        self.assertTrue(cfg.anonimizar())
        self.assertIsNone(self.banco.buscar_pessoa(BETO))
        self.assertEqual(cfg.cpf_anonimizar.get(), "")
        # some das listas; a visita fica, sem os dados
        self.app.ir_para(self.app.aba_pessoas)
        self.assertEqual(self.app.tela_pessoas.tabela.get_children(), ())
        self.assertEqual(self.no_banco()[0]["nome"], "Pessoa anonimizada")

    def test_prazo_de_guarda_pela_tela(self):
        cfg = self.pagina
        self.banco.inserir(dict(VISITA_ANTIGA, placa=""), autor="ana.admin")
        cfg.aplicar_prazo()                 # 12 meses: a visita é de 6 dias
        self.assertEqual(cfg.faixa_privacidade.tipo, "info")
        cfg.meses_guarda.delete(0, tk.END)
        cfg.aplicar_prazo()                 # vazio
        self.msg.showerror.assert_called()
        self.agora = AGORA + timedelta(days=500)
        cfg.meses_guarda.insert(0, "12")
        self.assertEqual(cfg.aplicar_prazo(), 1)
        self.assertEqual(cfg.faixa_privacidade.tipo, "sucesso")
        self.assertIsNone(self.banco.buscar_pessoa(BETO))


class TestTamanhoDaLetra(BaseInterface):
    def setUp(self):
        super().setUp()
        self.addCleanup(estilo.usar_letra, "normal")

    def test_letra_maior_aumenta_e_volta(self):
        normal = estilo.FONTE["corpo"][1]
        campo = estilo.px(36)
        self.app.cpf.insert(0, ANA)
        self.app.trocar_letra("maior")
        self.assertGreater(estilo.FONTE["corpo"][1], normal)
        self.assertGreater(estilo.px(36), campo)
        self.assertEqual(self.banco.letra_do_usuario("ana.admin"), "maior")
        self.assertEqual(self.app.var_letra.get(), "maior")
        self.assertEqual(self.app.cpf.get(), ANA)           # o formulário fica
        self.assertEqual(self.app.tela_cadastro.btn_cadastrar.cget("text"),
                         "Cadastrar")
        self.app.trocar_letra("normal")
        self.assertEqual(estilo.FONTE["corpo"][1], normal)
        self.assertEqual(estilo.px(36), campo)

    def test_e_de_cada_usuario_e_o_login_fica_normal(self):
        self.app.trocar_letra("grande")
        self.app.sair()
        self.assertEqual(estilo.ZOOM, 1.0)
        self.app.entrar(self.porteiro)
        self.assertEqual(estilo.ZOOM, 1.0)
        self.app.sair()
        self.app.entrar(self.admin)
        self.assertEqual(estilo.ZOOM, estilo.ZOOMS["grande"])
        self.assertEqual(self.app.var_letra.get(), "grande")

    def test_todas_as_paginas_abrem_com_a_letra_maior(self):
        self.app.trocar_letra("maior")
        self.janela.deiconify()
        for aba in self.app.itens_menu:
            self.app.ir_para(aba)
            self.janela.update()


class TestCodigoDaPessoa(BaseInterface):
    def test_ficha_mostra_o_codigo_do_cadastro(self):
        self.banco.inserir(dict(VISITA_ANTIGA, placa=""), autor="ana.admin")
        pessoa = self.banco.buscar_pessoa(BETO)
        self.app.ir_para(self.app.aba_pessoas)
        self.app.tela_pessoas.abrir_ficha(pessoa)
        self.assertEqual(self.app.tela_pessoas.lbl_codigo.cget("text"),
                         f"Código P{pessoa['id']:03d}")


class TestMenuCabeNaTelaPequena(BaseInterface):
    def test_o_menu_com_onze_paginas_cabe_em_536_px(self):
        self.janela.deiconify()
        self.janela.geometry("1093x536")
        self.janela.update()
        app = self.app
        self.assertEqual(len(app.itens_menu), 11)
        base = self.janela.winfo_rooty() + 536
        for item in app.itens_menu.values():
            self.assertTrue(item.winfo_ismapped())
        ultimo = list(app.itens_menu.values())[-1]
        topo_do_rodape = app.sessao.winfo_rooty()
        self.assertLessEqual(ultimo.winfo_rooty() + ultimo.winfo_height(),
                             topo_do_rodape)
        self.assertLessEqual(app.sessao.winfo_rooty() + app.sessao.winfo_height(),
                             base)

