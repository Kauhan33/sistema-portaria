"""
Campo Comando na tela de verdade (versão 2.4): F2/Ctrl+K, realce, Tab,
console, modo didático, máscara do porteiro, privacidade, os diálogos do
formulário e — a regra de ouro — a EXECUÇÃO: o mesmo comando e o mesmo
formulário, em dois bancos iguais, deixam o banco igual.
"""

import os
import sqlite3
import tempfile
import tkinter as tk
from datetime import timedelta
from unittest import mock

from portaria import dados, estilo
from portaria.interface import AppPortaria
from portaria.linguagem.interpretador import FALHOU, NAO_RODOU, PASSOU
from portaria.tela_comando import JanelaDidatica, desenhar_arvore
from portaria.tela_veiculo import A_PE

from .test_interface import (AGORA, VISITA_ANTIGA, BaseInterface,
                             criar_usuario, ha_uma_hora)

ANA, BETO, NOVO = "52998224725", "11144477735", "12345678909"


def fotografia(caminho):
    """O que importa no banco, sem os ids nem a hora real do relógio:
    visitas, estadias dos carros, pessoas, desativações e o histórico
    (quem fez o quê)."""
    con = sqlite3.connect(caminho)
    try:
        consultas = {
            "registros": "SELECT nome, cpf, celular, placa, tipo, entrada, "
                         "saida FROM registros ORDER BY id",
            "estadias": "SELECT placa, cpf, nome, entrada, saida FROM "
                        "estadias_veiculo ORDER BY id",
            "pessoas": "SELECT cpf, nome, celular, placa, tipo FROM pessoas "
                       "ORDER BY cpf",
            "desativacoes": "SELECT tipo, valor, motivo, ativo FROM bloqueios "
                            "ORDER BY id",
            "historico": "SELECT usuario, acao FROM auditoria ORDER BY id",
            "placas": "SELECT p.cpf, v.placa FROM placas_pessoa v JOIN "
                      "pessoas p ON p.id = v.pessoa_id ORDER BY p.cpf, v.placa",
        }
        return {nome: con.execute(sql).fetchall()
                for nome, sql in consultas.items()}
    finally:
        con.close()


class BaseComando(BaseInterface):
    entrar_como = "admin"

    def setUp(self):
        super().setUp()
        self.tela = self.app.tela_cadastro
        self.painel = self.tela.comando

    def comando(self, texto, app=None):
        """Digita no campo Comando e aperta Enter."""
        app = app or self.app
        linha = app.tela_cadastro.campo_saida_rapida
        linha.delete(0, tk.END)
        linha.insert(0, texto)
        return app.tela_cadastro.saida_rapida()

    def resposta(self, app=None):
        return (app or self.app).tela_cadastro.comando.texto_resposta

    def console(self):
        return self.painel.console.conteudo()


# ----------------------------------------------------------------------
# O campo
# ----------------------------------------------------------------------
class TestCampoComando(BaseComando):
    def test_f2_e_ctrl_k_levam_ao_campo(self):
        """CT-62 | RF14 | positivo | F2 e Ctrl+K, de qualquer página, levam
        ao campo Comando (no lugar da Saída rápida)."""
        for tecla in ("<F2>", "<Control-k>", "<Control-K>"):
            self.assertTrue(self.janela.bind(tecla), tecla)
        self.app.ir_para(self.app.aba_pessoas)
        self.assertEqual(self.app.ir_para_saida_rapida(), "break")
        self.assertEqual(self.app.abas.select(), str(self.app.aba_cad))
        self.assertEqual(self.tela.lbl_saida_rapida.cget("text"),
                         "Comando (F2 · Ctrl+K)")

    def test_comando_ajuda_e_console(self):
        self.assertEqual(self.comando("ajuda"), "break")
        self.assertIn("comandos", self.resposta())
        self.assertTrue(self.painel.console_aberto)       # tem detalhes
        self.assertIn("entrada", self.console())
        self.assertEqual(self.painel.btn_console.cget("text"), "Console (1)")
        self.painel._esc()
        self.assertFalse(self.painel.console_aberto)
        self.painel.alternar_console()
        self.assertTrue(self.painel.console_aberto)

    def test_realce_por_token(self):
        """CT-63 | RF14 | positivo | o léxico roda a cada tecla e pinta
        cada token; o lexema com erro fica com a marca de erro."""
        linha = self.painel.linha
        linha.insert(0, "entrada 52998224725 visitante placa ABC1D23")
        for tag, trecho in (("COMANDO", "entrada"), ("NUMERO", ANA),
                            ("TIPO", "visitante"), ("PALAVRA_CHAVE", "placa"),
                            ("PLACA", "ABC1D23")):
            inicio, fim = linha.tag_ranges(tag)[:2]
            self.assertEqual(linha.get(inicio, fim), trecho)
        linha.delete(0, tk.END)
        linha.insert(0, "saida placa AB12345")
        inicio, fim = linha.tag_ranges("ERRO")
        self.assertEqual(linha.get(inicio, fim), "AB12345")
        self.assertTrue(linha.tag_cget("ERRO", "underline"))

    def test_uma_linha_com_maximo(self):
        """RN33: a linha de comando tem máximo de 200 caracteres (digitar
        e colar) e não quebra a linha."""
        campo = self.painel.campo
        self.assertEqual(campo.maximo, 200)
        campo.colar("ajuda\n" + "x" * 300)
        self.assertEqual(len(self.painel.linha.get()), 200)
        self.assertNotIn("\n", self.painel.linha.get())
        self.assertEqual(self.painel.linha.bind("<Up>")[:0], "")

    def test_tab_completa_comando_e_palavra(self):
        linha = self.painel.linha
        linha.insert(0, "entr")
        self.painel.completar()
        self.assertEqual(linha.get(), "entrada ")
        linha.escrever("entrda")
        self.painel.completar()                    # você quis dizer…?
        self.assertEqual(linha.get(), "entrada ")
        linha.escrever(f"entrada {ANA} visi")
        self.painel.completar()
        self.assertEqual(linha.get(), f"entrada {ANA} visitante ")
        linha.escrever("e")                        # entrada, editar, excluir
        self.painel.completar()
        self.painel.completar()
        self.assertEqual(linha.get(), "editar ")
        self.assertIn("Tab 2/3", self.resposta())

    def test_tab_troca_o_nome_pelo_cpf(self):
        """CT-63 | RF14 | positivo | parte do nome + Tab vira o CPF."""
        self.banco.inserir(dict(VISITA_ANTIGA))
        linha = self.painel.linha
        linha.insert(0, "situacao bet")
        self.painel.completar()
        self.assertEqual(linha.get(), "situacao 111.444.777-35 ")
        self.assertIn("Beto Rocha", self.resposta())
        self.comando(linha.get())
        self.assertIn("Beto Rocha está fora do campus", self.resposta())

    def test_erro_no_console_no_formato_do_compilador(self):
        """CT-57 | RF14 | negativo | o console mostra a linha, o ^ na
        coluna, a fase e a dica; nada é gravado."""
        self.comando("entrda 52998224725 aluno")
        linhas = self.console().splitlines()
        self.assertEqual(linhas[0], "› entrda 52998224725 aluno")
        self.assertEqual(linhas[1], "  ^^^^^^")
        self.assertTrue(linhas[2].startswith("[Sintático] coluna 1: "))
        self.assertIn("Você quis dizer entrada?", linhas[3])
        self.assertTrue(self.painel.console_aberto)
        self.assertIn("[Sintático]", self.resposta())
        self.assertEqual(self.painel.linha.get(), "entrda 52998224725 aluno")
        self.assertEqual(self.no_banco(), [])
        self.msg.showerror.assert_not_called()

    def test_console_guarda_as_ultimas(self):
        for _ in range(35):
            self.comando("pendentes")
        self.assertEqual(len(self.painel.console.entradas), 30)
        self.painel.console.limpar()
        self.assertEqual(self.console(), "")

    def test_tema_trocado_mantem_o_comando(self):
        self.painel.linha.insert(0, "dentro")
        self.comando("ajuda")
        self.painel.linha.escrever("dentro vis")
        self.painel.abrir_didatico()
        self.app.trocar_tema("escuro")
        painel = self.app.tela_cadastro.comando
        self.assertIsNot(painel, self.painel)
        self.assertEqual(painel.linha.get(), "dentro vis")
        self.assertEqual(len(painel.console.entradas), 1)
        self.assertTrue(painel.janela_didatica.existe())
        self.assertEqual(painel.janela_didatica.janela.cget("bg"),
                         estilo.PALETAS["escuro"]["superficie"])


# ----------------------------------------------------------------------
# A saída rápida de antes continua (só o CPF ou só a placa)
# ----------------------------------------------------------------------
class TestSaidaRapidaContinua(BaseComando):
    entrar_como = "porteiro"

    def setUp(self):
        super().setUp()
        self.banco.inserir(dict(VISITA_ANTIGA, entrada=ha_uma_hora(),
                                saida=""), autor="paulo")
        self.app.atualizar_tabela()

    def test_so_o_cpf_da_a_saida(self):
        """CT-62 | RF02 | positivo | só o CPF = saida (a Saída rápida)."""
        self.responder_veiculo = A_PE
        self.comando("111.444.777-35")
        self.assertTrue(self.no_banco()[0]["saida"])
        self.assertIn("Saída de Beto registrada", self.resposta())
        self.assertIn("a pé", self.resposta())
        self.assertEqual(self.painel.linha.get(), "")       # limpa no sucesso

    def test_so_a_placa_tira_o_carro(self):
        self.comando("qwe-1234")
        self.assertEqual(self.perguntas_veiculo,
                         ["Beto saiu junto com o carro?"])
        self.assertIsNone(self.banco.estadia_aberta(placa="QWE1234"))


# ----------------------------------------------------------------------
# Privacidade e permissões
# ----------------------------------------------------------------------
class TestPrivacidade(BaseComando):
    entrar_como = "porteiro"

    def test_porteiro_ve_o_cpf_mascarado(self):
        """CT-64 | RN14 | positivo | para o porteiro, a resposta, o console
        e o modo didático mostram o CPF mascarado, mesmo digitado inteiro."""
        self.banco.inserir(dict(VISITA_ANTIGA, entrada=ha_uma_hora(),
                                saida=""), autor="paulo")
        self.comando("dentro")
        self.comando(f"situacao {BETO}")
        self.comando(f"entrada {BETO}")                    # RN05: erro
        didatica = self.painel.abrir_didatico()
        textos = [self.console(), self.resposta(),
                  didatica.lbl_linha.cget("text"),
                  didatica.lbl_mensagem.cget("text")]
        for aba, (_, tab) in didatica.paineis.items():
            if aba != "Árvore":
                didatica.seletor.selecionar(aba)
                textos += [str(tab.item(i, "values"))
                           for i in tab.get_children()]
        didatica.seletor.selecionar("Árvore")
        cv = didatica.arvore
        textos += [cv.itemcget(i, "text") for i in cv.find_all()
                   if cv.type(i) == "text"]
        tudo = "\n".join(textos)
        self.assertNotIn(BETO, tudo)
        self.assertNotIn("111.444.777-35", tudo)
        self.assertIn("***.444.777-**", tudo)

    def test_tab_do_porteiro_escreve_o_cpf_mascarado(self):
        self.banco.inserir(dict(VISITA_ANTIGA))
        self.painel.linha.insert(0, "situacao bet")
        self.painel.completar()
        self.assertEqual(self.painel.linha.get(), "situacao ***.444.777-** ")
        self.comando(self.painel.linha.get())      # o campo sabe o CPF
        self.assertIn("Beto Rocha está fora do campus", self.resposta())

    def test_comando_de_admin_recusado_para_o_porteiro(self):
        """CT-59 | RN02 | negativo | o porteiro não desativa: para no
        semântico e o banco não muda."""
        self.comando('desativar placa QWE1234 motivo "teste de motivo"')
        self.assertIn("[Semântico]", self.resposta())
        self.assertIn("só o administrador", self.resposta())
        self.assertEqual(self.banco.listar_desativacoes(), [])

    def test_o_texto_do_comando_nao_e_gravado(self):
        """CT-64 | RNF05 | positivo | o texto digitado não vai para o log
        nem para o banco (só os eventos normais)."""
        marcador = "zqxmarcadorzqx"
        with mock.patch.object(dados.log, "handle") as log:
            self.comando(f'buscar "{marcador}"')
            self.comando(f"{marcador} 1")
            self.comando(f'desativar placa QWE1234 motivo "{marcador}"')
        self.assertFalse(any(marcador in str(c) for c in log.call_args_list))
        self.app.banco = None                     # nenhuma conexão aberta
        with open(self.caminho_db, "rb") as f:
            self.assertNotIn(marcador.encode(), f.read())
        for e in self.banco.listar_eventos():
            self.assertNotIn(marcador, e["detalhe"])


# ----------------------------------------------------------------------
# Modo didático
# ----------------------------------------------------------------------
class TestModoDidatico(BaseComando):
    def test_mostra_onde_parou_com_o_mesmo_erro(self):
        """CT-65 | RF32 | positivo | a faixa das fases mostra onde o comando
        parou e a mensagem é a mesma do console; as quatro abas enchem."""
        self.banco.inserir(dict(VISITA_ANTIGA, entrada=ha_uma_hora(),
                                saida=""), autor="paulo")
        didatica = self.painel.abrir_didatico()
        self.assertTrue(self.painel.var_didatico.get())
        self.comando(f"entrada {BETO} visitante")
        a = didatica.analise
        self.assertEqual(list(a.fases.values()),
                         [PASSOU, PASSOU, FALHOU, NAO_RODOU])
        self.assertEqual(didatica.lbl_mensagem.cget("text")[:60],
                         a.erro.titulo()[:60])
        self.assertIn(a.erro.titulo()[:40], self.console())
        tokens = didatica.paineis["Tokens"][1]
        self.assertEqual(len(tokens.get_children()), 4)    # 3 + FIM
        for aba in ("Símbolos", "Checagens"):
            didatica.seletor.selecionar(aba)
            self.assertTrue(didatica.paineis[aba][1].get_children(), aba)
        checagens = didatica.paineis["Checagens"][1]
        ultima = checagens.get_children()[-1]
        self.assertEqual(checagens.item(ultima, "text"), "Parou aqui")
        self.assertIn("RN05", checagens.item(ultima, "values"))
        didatica.seletor.selecionar("Árvore")
        self.assertTrue(didatica.arvore.find_all())

    def test_erro_lexico_e_digitacao(self):
        didatica = self.painel.abrir_didatico()
        self.painel.linha.insert(0, "saida placa AB12345")   # enquanto digita
        self.assertEqual(didatica.analise.fases["Léxico"], FALHOU)
        didatica.seletor.selecionar("Árvore")
        self.assertIn("parou na fase Léxico",
                      didatica.lbl_vazio.cget("text"))
        didatica.seletor.selecionar("Checagens")
        self.assertIn("não rodou", didatica.lbl_vazio.cget("text"))
        self.painel.linha.escrever("dentro visitante")
        self.assertEqual(didatica.analise.fases["Sintático"], PASSOU)
        self.assertEqual(didatica.analise.fases["Semântico"], NAO_RODOU)
        self.comando("dentro visitante")
        self.assertEqual(didatica.analise.fases["Execução"], PASSOU)

    def test_so_pelo_atalho_do_teclado(self):
        """2.5.3 (pedido do aluno): o interruptor "Didático" não aparece;
        Ctrl+Shift+D (de qualquer página) leva à Entrada e saída e abre o
        modo; de novo, fecha. O atalho está em Configurações › Atalhos."""
        self.assertEqual(self.painel.alternador.winfo_manager(), "")
        self.assertIn("<Control-Key-D>", self.app.janela.bind())
        self.app.ir_para(self.app.aba_pessoas)
        self.app.alternar_modo_didatico()
        self.assertEqual(self.app.abas.select(), str(self.app.aba_cad))
        self.assertTrue(self.painel.var_didatico.get())
        self.assertTrue(self.painel.janela_didatica.existe())
        self.app.alternar_modo_didatico()
        self.assertFalse(self.painel.var_didatico.get())
        self.assertFalse(self.painel.janela_didatica.existe())
        config = self.app.tela_configuracoes
        config.seletor.selecionar("Atalhos")
        self.assertIn("modo didático",
                      config.lbl_atalhos["Ctrl+Shift+D"].cget("text"))

    def test_fechar_desliga_o_interruptor(self):
        didatica = self.painel.abrir_didatico()
        self.assertIsInstance(didatica, JanelaDidatica)
        didatica.fechar()
        self.assertFalse(self.painel.var_didatico.get())
        self.assertFalse(didatica.existe())

    def test_no_com_erro_fica_vermelho(self):
        from portaria.linguagem.lexico import analisar_lexico
        from portaria.linguagem.sintatico import (analisar_sintatico,
                                                  arvore_visual)
        texto = "entrada 111.444.777-35 visitante placa QWE1E34"
        raiz = arvore_visual(analisar_sintatico(analisar_lexico(texto)))
        cv = tk.Canvas(self.janela, width=600, height=300)
        desenhar_arvore(cv, raiz, marcar=(34, 47))
        vermelhos = [i for i in cv.find_all() if cv.type(i) == "text"
                     and cv.itemcget(i, "fill") == estilo.ESTADO["erro"][0]]
        textos = {cv.itemcget(i, "text") for i in vermelhos}
        self.assertEqual(textos, {"opção placa", "placa", "QWE1E34"})


# ----------------------------------------------------------------------
# Os diálogos do formulário
# ----------------------------------------------------------------------
class TestComandoAbreOsDialogos(BaseComando):
    def test_vai_entrar_de_carro(self):
        """CT-66 | RN34 | positivo | quem tem placa no cadastro e não disse
        "placa" nem "sem carro": o comando abre a mesma pergunta."""
        self.banco.inserir(dict(VISITA_ANTIGA))
        self.comando(f"entrada {BETO}")
        self.assertEqual(self.perguntas_veiculo, ["Beto vai entrar de carro?"])
        self.assertEqual(self.no_banco()[-1]["placa"], "QWE1234")
        self.assertIn("Registro cadastrado com sucesso!", self.resposta())

    def test_com_qual_carro(self):
        """RN40: Beto saiu a pé (o QWE1234 ficou) e voltou com o XYZ9A87:
        "saida CPF" abre a mesma pergunta do formulário."""
        primeira = self.banco.inserir(dict(VISITA_ANTIGA,
                                           entrada="21/10/2026 08:00",
                                           saida=""))
        self.banco.registrar_saidas([primeira], "21/10/2026 08:30")
        self.banco.inserir(dict(VISITA_ANTIGA, placa="XYZ9A87",
                                entrada="21/10/2026 09:00", saida=""))
        self.responder_veiculo = A_PE
        self.comando(BETO)
        self.assertEqual(self.perguntas_veiculo,
                         ["Com qual carro Beto está saindo?"])
        self.assertIn("os carros", self.resposta())

    def test_autorizacao_do_administrador(self):
        """CT-66 | RN24 | positivo | lançamento de um dia que já fechou: o
        comando abre a autorização do administrador e, com a senha, grava a
        exceção como o formulário."""
        texto = (f'entrada {ANA} visitante nome "Ana Silva" '
                 "cel 31987654321 em 18/10/2026 09:00")
        self.comando(texto)                               # cancela
        self.assertEqual(len(self.autorizacoes), 1)
        self.assertEqual(self.no_banco(), [])
        self.assertIn("Nada foi gravado", self.resposta())
        self.autorizar_com_senha()
        self.comando(texto)
        self.assertEqual(self.no_banco()[0]["entrada"], "18/10/2026 09:00")
        self.assertIn(("ana.admin", "Exceção autorizada"), self.acoes())

    def test_tipo_diferente_pergunta_antes(self):
        """CT-60 | RF14 | positivo | aviso de tipo: "Registrar como
        Prestador?" (Não = nada gravado)."""
        self.banco.inserir(dict(VISITA_ANTIGA))
        self.msg.askyesno.return_value = False
        self.comando(f"entrada {BETO} prestador sem carro")
        titulo = self.msg.askyesno.call_args[0][0]
        self.assertEqual(titulo, "Tipo diferente do cadastro")
        self.assertEqual(len(self.no_banco()), 1)
        self.msg.askyesno.return_value = True
        self.comando(f"entrada {BETO} prestador sem carro")
        self.assertEqual(self.no_banco()[-1]["tipo"], "Prestador de serviço")

    def test_desativado_vai_ao_historico(self):
        """RN12: a entrada recusada pelo comando vai ao histórico, como a
        do formulário."""
        self.banco.inserir(dict(VISITA_ANTIGA))
        self.banco.desativar("cpf", BETO, "agressão ao porteiro", "ana.admin")
        self.comando(f"entrada {BETO} sem carro")
        self.assertIn("RN12", self.resposta())
        self.assertIn(("ana.admin", dados.ENTRADA_RECUSADA), self.acoes())


# ----------------------------------------------------------------------
# Regra de ouro: o comando grava o MESMO que o formulário
# ----------------------------------------------------------------------
class TestExecucaoIgualAoFormulario(BaseComando):
    """Dois bancos com o mesmo começo: num, o formulário; no outro, o
    comando. No fim, as visitas, os carros, as pessoas, as desativações e
    o histórico (quem fez o quê) são iguais."""

    def outro_app(self):
        pasta = tempfile.TemporaryDirectory()
        caminho = os.path.join(pasta.name, "portaria.db")
        banco = dados.Banco(caminho)
        admin = criar_usuario(banco, "Ana Admin", "ana.admin", "admin",
                              "senha123")
        criar_usuario(banco, "Paulo Porteiro", "paulo", "porteiro",
                      "senha456", "ana.admin")
        app = AppPortaria(caminho, self.nova_janela(), usuario=admin,
                          relogio=lambda: self.agora)
        self.addCleanup(pasta.cleanup)
        self.addCleanup(app.janela.destroy)
        return app, banco, caminho

    def comparar(self):
        self.assertEqual(fotografia(self.caminho_db),
                         fotografia(self.caminho2))

    def preparar(self, *visitas):
        self.app2, self.banco2, self.caminho2 = self.outro_app()
        for banco in (self.banco, self.banco2):
            for v in visitas:
                banco.inserir(dict(v), autor="paulo")
        for app in (self.app, self.app2):
            app.atualizar_tabela()

    def test_entrada_de_pessoa_nova(self):
        """CT-67 | RF01 | positivo | a mesma entrada pelo formulário e pelo
        comando grava o mesmo registro, o mesmo carro e o mesmo histórico."""
        self.preparar()
        self.preencher(placa="ABC1D23")
        self.app.cadastrar()
        self.comando('entrada 529.982.247-25 visitante nome "Ana Silva" '
                     "cel 31987654321 placa ABC1D23", self.app2)
        self.assertIn("Registro cadastrado com sucesso!",
                      self.resposta(self.app2))
        self.comparar()

    def test_entrada_com_a_pergunta_do_carro(self):
        self.preparar(VISITA_ANTIGA)
        self.app.var_cpf.set(BETO)                  # preenche pelo CPF
        self.app.cadastrar()
        self.comando(f"entrada {BETO}", self.app2)
        self.assertEqual(self.perguntas_veiculo,
                         ["Beto vai entrar de carro?"] * 2)
        self.comparar()

    def test_saida_a_pe(self):
        """CT-67 | RF02 | positivo | "saida CPF sem carro" = a saída pelo
        botão respondendo "Saiu a pé" (o carro fica)."""
        self.preparar(dict(VISITA_ANTIGA, entrada=ha_uma_hora(), saida=""))
        self.responder_veiculo = A_PE
        self.app.tabela.selection_set(self.app.tabela.get_children()[0])
        self.app.registrar_saida()
        self.comando(f"saida {BETO} sem carro", self.app2)
        self.assertEqual(len(self.perguntas_veiculo), 1)  # o comando já disse
        self.assertIn("o carro QWE-1234 fica", self.resposta(self.app2))
        self.comparar()

    def test_retroativo_com_autorizacao(self):
        self.preparar()
        self.autorizar_com_senha()
        self.preencher()
        self.app.entrada.delete(0, tk.END)
        self.app.entrada.insert(0, "18/10/2026 09:00")
        self.app.cadastrar()
        self.comando(f'entrada {ANA} visitante nome "Ana Silva" '
                     "cel 31987654321 em 18/10/2026 09:00", self.app2)
        self.assertEqual(len(self.autorizacoes), 2)
        self.comparar()

    def test_crud_da_pessoa(self):
        """CT-68 | RF27 | positivo | cadastrar, editar, desativar, reativar
        e excluir pela linguagem = pelos diálogos da página Pessoas."""
        self.preparar()
        pessoas = self.app.tela_pessoas
        d = pessoas.nova_pessoa()
        d.cpf.insert(0, NOVO)
        d.nome.insert(0, "Rui Lima")
        d.celular.insert(0, "31987651234")
        d.tipo.set("Visitante")
        self.assertTrue(d.salvar())
        d = pessoas.editar()
        d.celular.delete(0, tk.END)
        d.celular.insert(0, "31999990000")
        d.tipo.set("Professor")
        self.assertTrue(d.salvar())
        d = pessoas.desativar_selecionada()
        d.motivo.insert(0, "agressão ao porteiro")
        self.assertTrue(d.salvar())
        pessoas.reativar(self.banco.listar_desativacoes()[0])
        pessoas.abrir_ficha(self.banco.buscar_pessoa(NOVO))
        self.assertTrue(pessoas.excluir_selecionada())
        for texto in (f'cadastrar {NOVO} visitante nome "Rui Lima" '
                      "cel 31987651234",
                      f"editar {NOVO} cel 31999990000 tipo professor",
                      f'desativar {NOVO} motivo "agressão ao porteiro"',
                      f"reativar {NOVO}", f"excluir {NOVO}"):
            self.comando(texto, self.app2)
            self.assertNotIn("[", self.resposta(self.app2), texto)
        self.comparar()

    def test_varias_placas_igual_ao_formulario(self):
        """CT-71 | RN47 | positivo | cadastrar com dois carros e depois
        trocar um deles: pelo comando = pelo diálogo de Pessoas; o
        situacao mostra os carros do cadastro."""
        self.preparar()
        pessoas = self.app.tela_pessoas
        d = pessoas.nova_pessoa()
        d.cpf.insert(0, NOVO)
        d.nome.insert(0, "Rui Lima")
        d.celular.insert(0, "31987651234")
        d.tipo.set("Visitante")
        for placa in ("ABC1D23", "NEY4829"):
            d.caixa_placa.insert(0, placa)
            d.adicionar_placa()
        self.assertTrue(d.salvar())
        d = pessoas.editar()
        d.tirar_placa("NEY4829")
        d.caixa_placa.insert(0, "QWE1E34")
        self.assertTrue(d.salvar())
        for texto in (f'cadastrar {NOVO} visitante nome "Rui Lima" '
                      "cel 31987651234 placa ABC1D23 placa NEY4829",
                      f"editar {NOVO} sem placa NEY4829 placa QWE1E34"):
            self.comando(texto, self.app2)
            self.assertNotIn("[", self.resposta(self.app2), texto)
        self.comparar()
        self.assertEqual(self.banco2.buscar_pessoa(NOVO)["placas"],
                         ["ABC1D23", "QWE1E34"])
        self.comando(f"situacao {NOVO}", self.app2)
        self.assertIn("2 carros no cadastro: ABC1D23, QWE1E34",
                      self.app2.tela_cadastro.comando.console.conteudo())

    def test_cadastrar_atualiza_a_pagina_pessoas(self):
        pessoas = self.app.tela_pessoas
        self.comando(f'cadastrar {NOVO} visitante nome "Rui Lima" '
                     "cel 31987651234")
        self.assertIn("Pessoa cadastrada: Rui Lima", self.resposta())
        nomes = [pessoas.tabela.item(i, "values")[0]
                 for i in pessoas.tabela.get_children()]
        self.assertTrue(any("Rui Lima" in str(n) for n in nomes), nomes)
