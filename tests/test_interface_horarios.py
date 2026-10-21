"""
Tela com as regras de horário: autorização do administrador, faixas de
saída pendente e de aviso antes de fechar, situação das visitas, encerrar
o dia, Painel e a página Configurações. Relógio do app sempre fixo.
"""

import tkinter as tk
import unittest
from datetime import date, datetime, timedelta

from portaria import horarios
from portaria.horarios import Evento, Horario, hora

from .test_interface import AGORA, BaseInterface

DOMINGO = datetime(2026, 10, 25, 10, 0)
ONTEM = (AGORA - timedelta(days=1)).replace(hour=8)


def tela(momento):
    return momento.strftime("%d/%m/%Y %H:%M")


def visita(nome="Beto Rocha", cpf="11144477735", tipo="Aluno", entrada=ONTEM,
           saida=None):
    return {"nome": nome, "cpf": cpf, "celular": "31933334444", "placa": "",
            "tipo": tipo, "entrada": tela(entrada),
            "saida": tela(saida) if saida else ""}


class BaseHorarios(BaseInterface):
    def responder(self, login=None, senha=None,
                  justificativa="Evento da reitoria autorizado"):
        """O "administrador" preenche o diálogo e clica em Autorizar."""
        def responder(dialogo):
            if login is not None:
                dialogo.login.insert(0, login)
                dialogo.senha.insert(0, senha)
            dialogo.justificativa.insert(0, justificativa)
            dialogo.confirmar()
        self.responder_autorizacao = responder

    def mudar_relogio(self, momento):
        self.agora = momento
        self.app.tela_cadastro.limpar()      # a Entrada volta a ser "agora"

    def cadastrar_no_domingo(self, tipo="Aluno"):
        self.mudar_relogio(DOMINGO)
        self.preencher(tipo=tipo)
        self.app.cadastrar()

    def excecoes(self):
        return [e for e in self.banco.listar_eventos()
                if e["acao"] == "Exceção autorizada"]

    def situacao_da_linha(self, id_):
        return self.app.tabela.item(str(id_))["text"]


class TestAutorizacaoComoPorteiro(BaseHorarios):
    entrar_como = "porteiro"

    def test_entrada_normal_nao_pede_autorizacao(self):
        self.preencher(tipo="Aluno")
        self.app.cadastrar()
        self.assertEqual(self.autorizacoes, [])
        self.assertEqual(len(self.no_banco()), 1)

    def test_aluno_no_domingo_abre_a_autorizacao_com_a_regra(self):
        ocultas = []
        self.responder_autorizacao = lambda d: ocultas.append(d.senha.cget("show"))
        self.cadastrar_no_domingo()
        self.assertEqual(len(self.autorizacoes), 1)
        dialogo = self.autorizacoes[0]
        self.assertTrue(dialogo.pede_senha)
        self.assertEqual(dialogo.regras, ["Campus fechado em 25/10/2026 (domingo)."])
        self.assertEqual(ocultas, ["•"])                        # senha oculta
        self.assertEqual(self.no_banco(), [])                   # cancelou

    def test_senha_errada_nao_grava_e_conta_tentativa(self):
        self.responder("ana.admin", "senha-errada")
        self.cadastrar_no_domingo()
        self.assertEqual(self.no_banco(), [])
        self.assertIn("incorretos", self.autorizacoes[0].erro)
        self.assertEqual(self.banco.ler_tentativas_login("ana.admin")[0], 1)
        self.assertIn(("ana.admin", "Login recusado"), self.acoes())

    def test_porteiro_nao_autoriza_a_si_mesmo(self):
        self.responder("paulo", "senha456")
        self.cadastrar_no_domingo()
        self.assertEqual(self.no_banco(), [])
        self.assertIn("Somente um administrador",
                      self.autorizacoes[0].erro)

    def test_justificativa_vazia_e_recusada(self):
        self.responder("ana.admin", "senha123", justificativa="   ")
        self.cadastrar_no_domingo()
        self.assertEqual(self.no_banco(), [])
        self.assertIn("justificativa", self.autorizacoes[0].erro)

    def test_admin_certo_grava_com_o_historico_da_excecao(self):
        self.responder("ana.admin", "senha123")
        self.cadastrar_no_domingo()
        salvos = self.no_banco()
        self.assertEqual(len(salvos), 1)
        evento = self.excecoes()[0]
        self.assertEqual(evento["usuario"], "ana.admin")
        self.assertIn("domingo", evento["detalhe"])
        self.assertIn("Justificativa: Evento da reitoria", evento["detalhe"])
        self.assertIn("Operador: paulo", evento["detalhe"])
        self.assertIn("Exceção autorizada", [
            e["acao"] for e in self.banco.eventos_do_registro(salvos[0]["id"])])
        self.assertIn("exceção autorizada por ana.admin",
                      self.app.lbl_aviso.cget("text"))

    def test_sessao_expirada_durante_a_autorizacao_nao_grava(self):
        def expira_e_responde(dialogo):
            dialogo.login.insert(0, "ana.admin")
            dialogo.senha.insert(0, "senha123")
            dialogo.justificativa.insert(0, "Evento da reitoria autorizado")
            dialogo.confirmar()                 # autorização certa...
            self.assertIsNotNone(dialogo.resultado)
            self.app.sair(inatividade=True)     # ...mas a sessão acabou antes
        self.responder_autorizacao = expira_e_responde
        self.cadastrar_no_domingo()
        self.assertEqual(self.no_banco(), [])
        self.assertEqual(self.excecoes(), [])
        self.assertIsNone(self.app.usuario)
        self.msg.showwarning.assert_called()

    def test_saida_acima_de_24h_pede_autorizacao(self):
        id_ = self.banco.inserir(visita(entrada=AGORA - timedelta(hours=30)))
        self.app.atualizar_tabela()
        self.app.tabela.selection_set(str(id_))
        self.app.registrar_saida()                   # cancelou a autorização
        self.assertEqual(len(self.autorizacoes), 1)
        self.assertIn("Beto Rocha: Visita de 30 h", self.autorizacoes[0].regras[0])
        self.assertEqual(self.banco.buscar(id_)["saida"], "")
        self.responder("ana.admin", "senha123")
        self.app.registrar_saida_da_linha(str(id_))  # duplo clique
        self.assertEqual(self.banco.buscar(id_)["saida"], tela(AGORA))
        self.assertEqual(len(self.excecoes()), 1)

    def test_saida_rapida_tambem_pede_autorizacao(self):
        id_ = self.banco.inserir(visita(entrada=AGORA - timedelta(hours=30)))
        self.app.campo_saida_rapida.insert(0, "11144477735")
        self.app.saida_rapida()
        self.assertEqual(len(self.autorizacoes), 1)
        self.assertEqual(self.banco.buscar(id_)["saida"], "")


class TestAutorizacaoComoAdmin(BaseHorarios):
    entrar_como = "admin"

    def test_admin_logado_so_confirma_com_justificativa(self):
        self.responder()
        self.cadastrar_no_domingo()
        dialogo = self.autorizacoes[0]
        self.assertFalse(dialogo.pede_senha)
        self.assertIsNone(dialogo.senha)
        self.assertEqual(len(self.no_banco()), 1)
        self.assertEqual(self.excecoes()[0]["usuario"], "ana.admin")

    def test_admin_tambem_precisa_de_justificativa(self):
        self.responder(justificativa="")
        self.cadastrar_no_domingo()
        self.assertEqual(self.no_banco(), [])

    def test_evento_no_domingo_libera_sem_autorizacao(self):
        self.banco.adicionar_evento(Evento(DOMINGO.date(), Horario(
            hora("08:00"), hora("18:00")), "Vestibular"), "ana.admin")
        self.cadastrar_no_domingo()
        self.assertEqual(self.autorizacoes, [])
        self.assertEqual(len(self.no_banco()), 1)

    def test_corrigir_entrada_para_fevereiro_e_dar_saida(self):
        # o caso do aluno: cadastrou agora, corrigiu a entrada para fevereiro
        # e registrou a saída. As duas exceções pedem confirmação, e a
        # visita continua no Movimento (saiu hoje).
        self.responder()
        self.preencher(tipo="Prestador de serviço")
        self.app.cadastrar()
        id_ = self.no_banco()[0]["id"]
        self.app.tabela.selection_set(str(id_))
        self.app.editar_selecionado()
        janela = self.app.janela_edicao
        janela.entrada.delete(0, tk.END)
        janela.entrada.insert(0, "10/02/2026 08:00")
        janela.salvar()
        self.assertEqual(self.banco.buscar(id_)["entrada"], "10/02/2026 08:00")
        self.assertIn("retroativa", " ".join(self.autorizacoes[0].regras))
        self.app.tabela.selection_set(str(id_))
        self.app.registrar_saida()
        self.assertEqual(self.banco.buscar(id_)["saida"], tela(AGORA))
        self.assertEqual(len(self.autorizacoes), 2)
        self.assertEqual(len(self.excecoes()), 2)
        self.assertIn(str(id_), self.app.tabela.get_children())

    def test_correcao_cancelada_nao_grava(self):
        id_ = self.banco.inserir(visita(entrada=AGORA - timedelta(hours=1)))
        self.app.atualizar_tabela()
        self.app.tabela.selection_set(str(id_))
        self.app.editar_selecionado()
        janela = self.app.janela_edicao
        janela.entrada.delete(0, tk.END)
        janela.entrada.insert(0, "10/02/2026 08:00")
        janela.salvar()                       # autorização cancelada
        self.assertEqual(len(self.autorizacoes), 1)
        self.assertEqual(self.banco.buscar(id_)["entrada"],
                         tela(AGORA - timedelta(hours=1)))


class TestSituacaoEFaixas(BaseHorarios):
    entrar_como = "porteiro"

    def test_saida_pendente_em_destaque_e_na_faixa(self):
        id_ = self.banco.inserir(visita(entrada=ONTEM))
        self.app.atualizar_tabela()
        self.assertEqual(self.situacao_da_linha(id_), horarios.SAIDA_PENDENTE)
        self.assertIn("pendente", self.app.tabela.item(str(id_))["tags"])
        faixa = self.app.tela_cadastro.faixa_pendentes
        self.assertTrue(faixa.winfo_manager())
        self.assertIn("1 saída pendente", faixa.lbl.cget("text"))
        self.assertIsNone(faixa.acao)                    # porteiro não encerra

    def test_tempo_excedido(self):
        id_ = self.banco.inserir(visita(tipo="Visitante",
                                        entrada=AGORA - timedelta(hours=5)))
        outro = self.banco.inserir(visita(nome="Ana Silva", cpf="52998224725",
                                          tipo="Visitante",
                                          entrada=AGORA - timedelta(hours=1)))
        self.app.atualizar_tabela()
        self.assertEqual(self.situacao_da_linha(id_), horarios.TEMPO_EXCEDIDO)
        self.assertEqual(self.situacao_da_linha(outro), horarios.NO_CAMPUS)
        self.assertFalse(self.app.tela_cadastro.faixa_pendentes.winfo_manager())

    def test_aviso_de_fechamento_so_nos_ultimos_minutos(self):
        self.banco.inserir(visita(entrada=AGORA))
        self.app.atualizar_tabela()
        faixa = self.app.tela_cadastro.faixa_fechamento
        self.assertFalse(faixa.winfo_manager())
        self.agora = AGORA.replace(hour=22, minute=40)
        self.app.tela_cadastro.atualizar_alertas()
        self.assertTrue(faixa.winfo_manager())
        self.assertEqual(faixa.lbl.cget("text"),
                         "Campus fecha às 23:00 (em 20 min)  ·  1 no campus")
        self.msg.showinfo.assert_not_called()         # sem caixa de diálogo
        self.agora = AGORA.replace(hour=23, minute=1)
        self.app.tela_cadastro.atualizar_alertas()
        self.assertFalse(faixa.winfo_manager())
        self.assertTrue(self.app.tela_cadastro.faixa_pendentes.winfo_manager())

    def test_faixas_se_atualizam_sozinhas_com_o_tempo(self):
        self.banco.inserir(visita(entrada=AGORA))
        self.app.atualizar_tabela()
        self.agora = AGORA.replace(hour=22, minute=45)
        self.app.registrar_uso()
        self.app._vigiar_inatividade()               # o temporizador de 30 s
        self.assertTrue(self.app.tela_cadastro.faixa_fechamento.winfo_manager())

    def test_porteiro_nao_encerra_o_dia(self):
        id_ = self.banco.inserir(visita(entrada=ONTEM))
        self.app.tela_cadastro.encerrar_dia()
        self.msg.showerror.assert_called_once()
        self.assertEqual(self.banco.buscar(id_)["saida"], "")


class TestEncerrarODia(BaseHorarios):
    entrar_como = "admin"

    def test_encerrar_o_dia_pela_faixa(self):
        pendente = self.banco.inserir(visita(entrada=ONTEM))
        hoje = self.banco.inserir(visita(nome="Ana Silva", cpf="52998224725",
                                         entrada=AGORA))
        self.app.atualizar_tabela()
        faixa = self.app.tela_cadastro.faixa_pendentes
        self.assertEqual(faixa.acao.cget("text"), "Encerrar o dia")
        faixa.comando()                               # clique no link
        pergunta = self.msg.askyesno.call_args[0][1]
        self.assertIn("Beto Rocha: entrada 20/10/2026 08:00, saída "
                      "20/10/2026 23:00", pergunta)
        self.assertEqual(self.banco.buscar(pendente)["saida"], "20/10/2026 23:00")
        self.assertEqual(self.banco.buscar(hoje)["saida"], "")
        self.assertIn(("ana.admin", "Saída automática (encerramento)"),
                      self.acoes())
        self.assertFalse(faixa.winfo_manager())
        self.assertIn("1 saída automática", self.app.lbl_aviso.cget("text"))

    def test_nao_encerra_sem_confirmar(self):
        pendente = self.banco.inserir(visita(entrada=ONTEM))
        self.msg.askyesno.return_value = False
        self.app.atualizar_tabela()
        self.app.tela_cadastro.encerrar_dia()
        self.assertEqual(self.banco.buscar(pendente)["saida"], "")


class TestPainelComHorarios(BaseHorarios):
    def test_tempo_excedido_e_pendentes_no_painel(self):
        self.banco.inserir(visita(tipo="Visitante",
                                  entrada=AGORA - timedelta(hours=5)))
        self.banco.inserir(visita(nome="Ana Silva", cpf="52998224725",
                                  entrada=ONTEM))
        self.app.ir_para(self.app.aba_dash)
        valor, apoio = self.app.cards["excedido"]
        self.assertEqual(valor.cget("text"), "1")
        self.assertEqual(apoio.cget("text"), "+ 1 saída pendente")


class TestConfiguracoes(BaseHorarios):
    entrar_como = "admin"

    def setUp(self):
        super().setUp()
        self.app.ir_para(self.app.aba_configuracoes)
        self.tela = self.app.tela_configuracoes

    def test_so_admin_tem_a_pagina(self):
        textos = [i.cget("text") for i in self.app.itens_menu.values()]
        self.assertEqual(textos[-2:], ["Usuários", "Configurações"])

    def test_mostra_a_configuracao_em_vigor(self):
        aberto, abre, fecha = self.tela.dias[5]
        self.assertEqual((aberto.get(), abre.get(), fecha.get()),
                         (True, "07:00", "14:00"))
        self.assertFalse(self.tela.dias[6][0].get())        # domingo fechado
        self.assertEqual(self.tela.dias[6][1].cget("state"), "disabled")
        aluno = self.tela.categorias["Aluno"]
        self.assertEqual((aluno["janela"].get(), aluno["de"].get(),
                          aluno["ate"].get(), aluno["minutos"].get()),
                         ("Do funcionamento", "0", "-30", "0"))
        self.assertEqual(self.tela.categorias["Visitante"]["de"].get(), "08:00")

    def test_salvar_funcionamento_valida_e_registra(self):
        _, abre, fecha = self.tela.dias[5]
        abre.delete(0, tk.END)
        abre.insert(0, "15:00")                       # depois do fechamento
        self.tela.salvar_funcionamento()
        self.assertIn("Sábado", self.tela.faixa_funcionamento.lbl.cget("text"))
        self.assertEqual(self.banco.ler_configuracao(),
                         horarios.configuracao_padrao())
        abre.delete(0, tk.END)
        abre.insert(0, "08:00")
        self.tela.dias[6][0].set(True)               # abre o domingo
        self.tela._ao_alternar_dia(6)
        for campo, valor in zip(self.tela.dias[6][1:], ("09:00", "12:00")):
            campo.insert(0, valor)
        self.tela.minutos_aviso.delete(0, tk.END)
        self.tela.minutos_aviso.insert(0, "45")
        self.tela.salvar_funcionamento()
        config = self.banco.ler_configuracao()
        self.assertEqual(config.funcionamento[5], Horario(hora("08:00"), hora("14:00")))
        self.assertEqual(config.funcionamento[6], Horario(hora("09:00"), hora("12:00")))
        self.assertEqual(config.minutos_aviso, 45)
        self.assertIn("3 alteração", self.tela.faixa_funcionamento.lbl.cget("text"))
        self.assertIn(("ana.admin", "Configuração alterada"), self.acoes())

    def test_salvar_regras_valida_e_troca_a_janela(self):
        visitante = self.tela.categorias["Visitante"]
        visitante["ate"].delete(0, tk.END)
        visitante["ate"].insert(0, "25:00")
        self.tela.salvar_regras()
        self.assertIn("horário inválido",
                      self.tela.faixa_categorias.lbl.cget("text"))
        # trocar para "Do funcionamento" passa De/Até para minutos
        visitante["janela"].set("Do funcionamento")
        self.tela._ao_trocar_janela("Visitante")
        self.assertEqual((visitante["de"].get(), visitante["ate"].get()), ("0", "0"))
        self.tela.salvar_regras()
        regra = self.banco.ler_configuracao().regras["Visitante"]
        self.assertTrue(regra.relativa)
        self.assertEqual(regra.permanencia_min, 240)

    def test_feriados_e_eventos(self):
        self.tela.seletor.selecionar("Feriados e eventos")
        self.tela.data_feriado.insert(0, "25/12/2026")
        self.tela.nome_feriado.insert(0, "Natal")
        self.tela.adicionar_feriado()
        self.assertEqual(self.banco.ler_configuracao().feriados,
                         {date(2026, 12, 25): "Natal"})
        self.assertEqual(self.tela.tabela_feriados.get_children(), ("2026-12-25",))
        self.tela.data_evento.insert(0, "25/10/2026")
        self.tela.abre_evento.insert(0, "18:00")
        self.tela.fecha_evento.insert(0, "17:00")
        self.tela.nome_evento.insert(0, "Show")
        self.tela.adicionar_evento()
        self.assertIn("depois da abertura", self.tela.faixa_eventos.lbl.cget("text"))
        self.tela.fecha_evento.delete(0, tk.END)
        self.tela.fecha_evento.insert(0, "23:00")
        self.tela.adicionar_evento()
        self.assertIn(date(2026, 10, 25), self.banco.ler_configuracao().eventos)
        self.tela.tabela_feriados.selection_set("2026-12-25")
        self.tela.remover_feriado()
        self.assertEqual(self.banco.ler_configuracao().feriados, {})


class TestConfiguracoesPorteiro(BaseHorarios):
    entrar_como = "porteiro"

    def test_porteiro_nao_tem_a_pagina(self):
        self.assertIsNone(self.app.aba_configuracoes)
        self.assertIsNone(self.app.tela_configuracoes)


if __name__ == "__main__":
    unittest.main()
