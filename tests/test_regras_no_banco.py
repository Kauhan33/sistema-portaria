"""Regras de horário no banco: autorização de exceções (defesa em
profundidade), encerrar o dia e a configuração guardada no esquema v7."""

import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime

from portaria import dados, horarios
from portaria.horarios import Evento, Horario, RegraCategoria, hora

from .test_dados import (objetos_do_banco, rebaixar_para_v6, registro,
                         versao_do_arquivo)

SEGUNDA = date(2026, 10, 19)


def autorizacao(por="ana", justificativa="Evento da reitoria autorizado"):
    return {"autorizado_por": por, "justificativa": justificativa,
            "regras": ["Campus fechado em 25/10/2026 (domingo)."]}


class BaseRegras(unittest.TestCase):
    AGORA = datetime(2026, 10, 19, 10, 0)

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = os.path.join(self.pasta.name, "portaria.db")
        self.banco = dados.Banco(self.caminho, relogio=lambda: self.AGORA)
        self.banco.criar_usuario("Ana Admin", "ana", "admin", "h")
        self.banco.criar_usuario("Bia Admin", "bia", "admin", "h", autor="ana")
        self.banco.criar_usuario("Paulo Porteiro", "paulo", "porteiro", "h",
                                 autor="ana")

    def tearDown(self):
        self.pasta.cleanup()

    def excecoes(self):
        return [e for e in self.banco.listar_eventos()
                if e["acao"] == "Exceção autorizada"]


class TestVisitaAcimaDe24h(BaseRegras):
    LONGA = {"entrada": "16/10/2026 08:00", "saida": "17/10/2026 09:00"}

    def test_banco_recusa_sem_autorizacao(self):
        with self.assertRaises(dados.ErroDados) as erro:
            self.banco.inserir(registro(**self.LONGA), autor="paulo")
        self.assertIn("autorização de um administrador", str(erro.exception))
        self.assertEqual(self.banco.listar(), [])

    def test_saida_acima_de_24h_sem_autorizacao_nao_grava_nenhuma(self):
        curta = self.banco.inserir(registro(cpf="11144477735",
                                            entrada="19/10/2026 08:00"))
        longa = self.banco.inserir(registro(entrada="16/10/2026 08:00"))
        with self.assertRaises(dados.ErroDados):
            self.banco.registrar_saidas([curta, longa], "19/10/2026 09:00",
                                        autor="paulo")
        self.assertTrue(all(not r["saida"] for r in self.banco.listar()))

    def test_autorizacao_so_de_administrador_ativo_com_justificativa(self):
        self.banco.definir_ativo(2, False, autor="ana")          # bia desativada
        casos = [autorizacao(por="paulo"), autorizacao(por="bia"),
                 autorizacao(por="ninguem"), autorizacao(por=""),
                 autorizacao(justificativa="curta")]
        for caso in casos:
            with self.subTest(caso=caso):
                with self.assertRaises(dados.ErroDados):
                    self.banco.inserir(registro(**self.LONGA), autor="paulo",
                                       autorizacao=caso)
        self.assertEqual(self.banco.listar(), [])

    def test_com_autorizacao_grava_e_registra_quem_autorizou(self):
        id_ = self.banco.inserir(registro(**self.LONGA), autor="paulo",
                                 autorizacao=autorizacao())
        self.assertEqual(self.banco.buscar(id_)["saida"], "17/10/2026 09:00")
        evento = self.excecoes()[0]
        self.assertEqual(evento["usuario"], "ana")
        self.assertIn("domingo", evento["detalhe"])
        self.assertIn("Justificativa: Evento da reitoria", evento["detalhe"])
        self.assertIn("Operador: paulo", evento["detalhe"])
        self.assertIn("Exceção autorizada",
                      [e["acao"] for e in self.banco.eventos_do_registro(id_)])

    def test_saida_acima_de_24h_com_autorizacao(self):
        curta = self.banco.inserir(registro(cpf="11144477735",
                                            entrada="19/10/2026 08:00"))
        longa = self.banco.inserir(registro(entrada="16/10/2026 08:00"))
        gravados = self.banco.registrar_saidas([curta, longa], "19/10/2026 09:00",
                                               autor="paulo",
                                               autorizacao=autorizacao())
        self.assertEqual(gravados, [curta, longa])
        # a exceção fica só na visita que passou de 24 h
        self.assertEqual([e["detalhe"].split()[0] for e in self.excecoes()],
                         [f"#{longa}"])

    def test_correcao_que_passa_de_24h_precisa_de_autorizacao(self):
        id_ = self.banco.inserir(registro(entrada="19/10/2026 08:00",
                                          saida="19/10/2026 09:00"))
        novo = registro(entrada="16/10/2026 08:00", saida="19/10/2026 09:00")
        with self.assertRaises(dados.ErroDados):
            self.banco.editar(id_, novo, ["entrada"], autor="ana")
        self.banco.editar(id_, novo, ["entrada"], autor="ana",
                          autorizacao=autorizacao())
        self.assertEqual(self.banco.buscar(id_)["entrada"], "16/10/2026 08:00")
        self.assertEqual(len(self.excecoes()), 1)

    def test_corrigir_so_o_nome_de_visita_antiga_longa_nao_pede_autorizacao(self):
        con = sqlite3.connect(self.caminho)      # visita de antes da regra
        con.execute("INSERT INTO registros (nome, cpf, celular, tipo, entrada, "
                    "saida) VALUES ('Ana Silva', '52998224725', '31987654321', "
                    "'Aluno', '2026-10-10 08:00', '2026-10-12 08:00')")
        con.commit()
        con.close()
        antiga = self.banco.listar()[0]
        self.banco.editar(antiga["id"], dict(antiga, nome="Ana Silva Costa"),
                          ["nome"], autor="ana")
        self.assertEqual(self.banco.buscar(antiga["id"])["nome"], "Ana Silva Costa")


class TestEncerrarODia(BaseRegras):
    AGORA = datetime(2026, 10, 20, 9, 0)        # terça de manhã

    def test_encerra_so_as_pendentes_no_prazo_de_cada_uma(self):
        aluno = self.banco.inserir(registro(tipo="Aluno",
                                            entrada="19/10/2026 08:00"))
        professor = self.banco.inserir(registro(
            cpf="11144477735", tipo="Professor", entrada="19/10/2026 19:00"))
        hoje = self.banco.inserir(registro(cpf="39053344705", tipo="Aluno",
                                           entrada="20/10/2026 08:00"))
        encerradas = self.banco.encerrar_pendentes(self.AGORA, autor="ana")
        self.assertEqual(encerradas, [
            (aluno, "João Ávila", "19/10/2026 23:00"),
            (professor, "João Ávila", "20/10/2026 00:00")])
        self.assertEqual(self.banco.buscar(hoje)["saida"], "")
        acoes = [e["acao"] for e in self.banco.eventos_do_registro(aluno)]
        self.assertEqual(acoes, ["Saída automática (encerramento)"])
        self.assertEqual(self.banco.listar_eventos()[0]["usuario"], "ana")

    def test_porteiro_nao_encerra_o_dia(self):
        self.banco.inserir(registro(tipo="Aluno", entrada="19/10/2026 08:00"))
        with self.assertRaises(dados.ErroDados):
            self.banco.encerrar_pendentes(self.AGORA, autor="paulo")
        self.assertEqual(self.banco.listar()[0]["saida"], "")

    def test_listar_abertas(self):
        self.banco.inserir(registro(entrada="19/10/2026 08:00",
                                    saida="19/10/2026 09:00"))
        aberta = self.banco.inserir(registro(entrada="20/10/2026 08:00"))
        self.assertEqual([r["id"] for r in self.banco.listar_abertas()], [aberta])


class TestConfiguracaoNoBanco(BaseRegras):
    def test_banco_novo_comeca_com_os_horarios_padrao(self):
        self.assertEqual(self.banco.ler_configuracao(),
                         horarios.configuracao_padrao())

    def test_funcionamento_persiste_e_vai_para_o_historico(self):
        config = self.banco.ler_configuracao()
        config.funcionamento[5] = Horario(hora("08:00"), hora("13:00"))
        config.funcionamento[6] = Horario(hora("09:00"), hora("12:00"))
        self.assertEqual(self.banco.salvar_funcionamento(config.funcionamento,
                                                         autor="ana"), 2)
        relido = dados.Banco(self.caminho).ler_configuracao()
        self.assertEqual(relido.funcionamento[5], config.funcionamento[5])
        self.assertEqual(relido.funcionamento[6], config.funcionamento[6])
        evento = self.banco.listar_eventos()[0]
        self.assertEqual((evento["usuario"], evento["acao"]),
                         ("ana", "Configuração alterada"))
        self.assertIn("Sábado: 07:00–14:00 → 08:00–13:00", evento["detalhe"])
        self.assertIn("Domingo: fechado → 09:00–12:00", evento["detalhe"])
        # sem mudança: nada no histórico
        total = len(self.banco.listar_eventos())
        self.assertEqual(self.banco.salvar_funcionamento(relido.funcionamento,
                                                         autor="ana"), 0)
        self.assertEqual(len(self.banco.listar_eventos()), total)

    def test_regras_e_parametros_persistem(self):
        regras = {"Visitante": RegraCategoria(
            False, janela=Horario(hora("09:00"), hora("17:00")),
            permanencia_min=120)}
        self.assertEqual(self.banco.salvar_regras(regras, autor="ana"), 1)
        self.banco.salvar_parametros(45, 6, autor="ana")
        config = dados.Banco(self.caminho).ler_configuracao()
        self.assertEqual(config.regras["Visitante"], regras["Visitante"])
        self.assertEqual(config.regras["Aluno"],
                         horarios.configuracao_padrao().regras["Aluno"])
        self.assertEqual((config.minutos_aviso, config.horas_retroativo), (45, 6))
        detalhes = [e["detalhe"] for e in self.banco.listar_eventos()[:2]]
        self.assertIn("Aviso antes de fechar: 30 → 45 min", detalhes[0])
        self.assertIn("Visitante: entrada das 09:00 às 17:00", detalhes[1])

    def test_feriados_e_eventos(self):
        natal = date(2026, 12, 25)
        show = Evento(date(2026, 10, 25), Horario(hora("18:00"), hora("23:00")),
                      "Show de calouros")
        self.banco.adicionar_feriado(natal, "Natal", autor="ana")
        self.banco.adicionar_evento(show, autor="ana")
        config = self.banco.ler_configuracao()
        self.assertEqual(config.feriados, {natal: "Natal"})
        self.assertEqual(config.eventos, {show.data: show})
        with self.assertRaises(dados.ErroDados):          # repetido
            self.banco.adicionar_feriado(natal, "Natal", autor="ana")
        self.banco.remover_feriado(natal, autor="ana")
        self.banco.remover_evento(show.data, autor="ana")
        config = self.banco.ler_configuracao()
        self.assertEqual((config.feriados, config.eventos), ({}, {}))
        with self.assertRaises(dados.ErroDados):
            self.banco.remover_evento(show.data, autor="ana")
        acoes = [e["detalhe"].split(":")[0] for e in self.banco.listar_eventos()
                 if e["acao"] == "Configuração alterada"]
        self.assertEqual(acoes, ["Evento removido", "Feriado removido",
                                 "Evento adicionado", "Feriado adicionado"])

    def test_porteiro_nao_altera_configuracoes(self):
        config = self.banco.ler_configuracao()
        operacoes = [
            lambda: self.banco.salvar_funcionamento(config.funcionamento, "paulo"),
            lambda: self.banco.salvar_regras(config.regras, "paulo"),
            lambda: self.banco.salvar_parametros(10, 10, "paulo"),
            lambda: self.banco.adicionar_feriado(SEGUNDA, "Feriado", "paulo"),
            lambda: self.banco.salvar_parametros(10, 10, None)]   # sessão expirou
        for operacao in operacoes:
            with self.assertRaises(dados.ErroDados):
                operacao()
        self.assertEqual(self.banco.ler_configuracao(),
                         horarios.configuracao_padrao())

    def test_horario_invalido_e_recusado_pela_tabela(self):
        con = sqlite3.connect(self.caminho)
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("UPDATE funcionamento SET abre = '23:00', "
                        "fecha = '06:00' WHERE dia = 0")
        con.close()


class TestMigracaoV6ParaV7(unittest.TestCase):
    def test_v6_ganha_a_configuracao_padrao_sem_perder_visitas(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "portaria.db")
            dados.Banco(caminho).inserir(registro())
            rebaixar_para_v6(caminho)
            self.assertNotIn("funcionamento", objetos_do_banco(caminho))
            banco = dados.Banco(caminho)
            self.assertEqual(versao_do_arquivo(caminho), 7)
            self.assertLessEqual({"funcionamento", "feriados", "eventos",
                                  "regras_categoria", "parametros",
                                  "idx_registros_saida"},
                                 objetos_do_banco(caminho))
            self.assertEqual(banco.ler_configuracao(),
                             horarios.configuracao_padrao())
            self.assertEqual(len(banco.listar()), 1)
            self.assertEqual(len(os.listdir(os.path.join(pasta, "backups"))), 1)


if __name__ == "__main__":
    unittest.main()
