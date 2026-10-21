"""Regras de horário no banco: autorização de exceções (defesa em
profundidade), encerrar o dia e a configuração guardada no esquema v7."""

import os
import sqlite3
import tempfile
import unittest
import unittest.mock
from datetime import date, datetime

from portaria import dados, horarios
from portaria.horarios import Evento, Horario, RegraCategoria, hora

from .test_dados import (objetos_do_banco, rebaixar_para_v6,
                         rebaixar_para_v7, registro, versao_do_arquivo)

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
        # o professor tem 30 min de tolerância depois do fechamento
        self.assertEqual(encerradas, [
            (aluno, "João Ávila", "19/10/2026 23:00"),
            (professor, "João Ávila", "19/10/2026 23:30")])
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
            self.assertEqual(versao_do_arquivo(caminho), dados.VERSAO_ESQUEMA)
            self.assertLessEqual({"funcionamento", "feriados", "eventos",
                                  "regras_categoria", "parametros",
                                  "idx_registros_saida"},
                                 objetos_do_banco(caminho))
            self.assertEqual(banco.ler_configuracao(),
                             horarios.configuracao_padrao())
            self.assertEqual(len(banco.listar()), 1)
            self.assertEqual(len(os.listdir(os.path.join(pasta, "backups"))), 1)


class TestEstadiasDeVeiculo(BaseRegras):
    """O carro tem estadia própria no banco (v8)."""

    def com_carro(self, **mudancas):
        return self.banco.inserir(registro(entrada="19/10/2026 08:00",
                                           **mudancas), autor="paulo")

    def test_visita_com_placa_abre_e_a_pe_nao(self):
        visita = self.com_carro()
        self.banco.inserir(registro(cpf="11144477735", entrada="19/10/2026 08:00"))
        estadias = self.banco.listar_estacionamento()
        self.assertEqual([(e["placa"], e["registro_id"], e["tipo"],
                           e["responsavel_dentro"]) for e in estadias],
                         [("ABC1D23", visita, "Funcionário", True)])
        self.assertEqual(self.banco.contadores()["veiculos"], 1)

    def test_placa_no_estacionamento_e_recusada_pelo_banco(self):
        self.com_carro()
        with self.assertRaises(dados.ErroDados) as erro:
            self.com_carro(cpf="11144477735", placa="ABC1D23")
        self.assertIn("já está no estacionamento", str(erro.exception))
        self.assertEqual(len(self.banco.listar()), 1)
        con = sqlite3.connect(self.caminho)        # e pelo índice único
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("INSERT INTO estadias_veiculo (placa, cpf, nome, "
                        "entrada) VALUES ('ABC1D23', '11144477735', 'X', "
                        "'2026-10-19 09:00')")
        con.close()

    def test_sair_a_pe_de_carro_e_desfazer(self):
        visita = self.com_carro()
        self.banco.registrar_saidas([visita], "19/10/2026 09:00", autor="paulo")
        self.assertIsNotNone(self.banco.estadia_aberta(cpf="52998224725"))
        volta = self.banco.inserir(registro(placa="", entrada="19/10/2026 09:30"))
        self.banco.registrar_saidas([volta], "19/10/2026 10:00", autor="paulo",
                                    com_veiculo={volta})
        self.assertIsNone(self.banco.estadia_aberta(placa="ABC1D23"))
        self.assertIn("Saída de veículo",
                      [e["acao"] for e in self.banco.eventos_do_registro(visita)])
        self.banco.desfazer_saidas([volta], autor="paulo", saida="19/10/2026 10:00")
        self.assertIsNotNone(self.banco.estadia_aberta(placa="ABC1D23"))

    def test_saida_so_do_carro_e_desfazer(self):
        self.com_carro()
        estadia = self.banco.estadia_aberta(placa="ABC1D23")
        self.assertTrue(self.banco.registrar_saida_veiculo(
            estadia["id"], "19/10/2026 09:00", autor="paulo"))
        self.assertFalse(self.banco.registrar_saida_veiculo(
            estadia["id"], "19/10/2026 09:00", autor="paulo"))
        self.assertEqual(self.banco.listar()[0]["saida"], "")
        self.assertEqual(self.banco.desfazer_saida_veiculos(
            [estadia["id"]], "19/10/2026 09:00", autor="paulo"), 1)
        self.assertIsNotNone(self.banco.estadia_aberta(placa="ABC1D23"))

    def test_corrigir_e_excluir_a_visita_acompanham_o_carro(self):
        visita = self.com_carro()
        original = self.banco.buscar(visita)
        self.banco.editar(visita, dict(original, placa="XYZ9A87"), ["placa"],
                          autor="ana")
        self.assertEqual(self.banco.estadia_aberta(cpf="52998224725")["placa"],
                         "XYZ9A87")
        self.banco.editar(visita, dict(original, placa=""), ["placa"], autor="ana")
        self.assertIsNone(self.banco.estadia_aberta(cpf="52998224725"))
        self.banco.editar(visita, original, ["placa"], autor="ana")
        self.assertIsNotNone(self.banco.estadia_aberta(placa="ABC1D23"))

    def test_excluir_a_visita_nao_tira_o_carro_que_esta_la(self):
        """QA1 M1 / QA2 M6: a pessoa saiu a pé e o carro ficou; excluir a
        visita de origem apagava o carro do estacionamento sem avisar."""
        visita = self.com_carro()
        self.banco.registrar_saidas([visita], "19/10/2026 09:00", autor="paulo")
        self.assertEqual(self.banco.excluir([visita], autor="ana"), ["ABC1D23"])
        carros = self.banco.listar_estacionamento()
        self.assertEqual([(e["placa"], e["registro_id"], e["tipo"])
                          for e in carros], [("ABC1D23", None, "Funcionário")])
        self.assertEqual(self.banco.contadores()["veiculos"], 1)
        acoes = [e["acao"] for e in self.banco.listar_eventos()[:2]]
        self.assertEqual(acoes, ["Exclusão de registro",
                                 "Veículo mantido no estacionamento"])
        # sai pela placa, como qualquer outro carro
        self.assertTrue(self.banco.registrar_saida_veiculo(
            carros[0]["id"], "19/10/2026 10:00", autor="paulo"))

    def test_excluir_visita_cujo_carro_ja_saiu_leva_a_estadia_junto(self):
        visita = self.com_carro()
        self.banco.registrar_saidas([visita], "19/10/2026 09:00", autor="paulo",
                                    com_veiculo={visita})
        self.assertEqual(self.banco.excluir([visita], autor="ana"), [])
        con = sqlite3.connect(self.caminho)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM estadias_veiculo"
                                     ).fetchone()[0], 0)
        con.close()

    def dois_carros(self):
        """Ana entra com GHI1J23, sai a pé, volta com KLM4N56."""
        primeira = self.com_carro(placa="GHI1J23")
        self.banco.registrar_saidas([primeira], "19/10/2026 09:00",
                                    autor="paulo")
        segunda = self.banco.inserir(registro(placa="KLM4N56",
                                              entrada="19/10/2026 09:30"),
                                     autor="paulo")
        return segunda

    def test_dois_carros_sai_o_da_propria_visita(self):
        """QA1 M3 / QA2 M1: fechava o mais antigo (o carro errado)."""
        segunda = self.dois_carros()
        self.banco.registrar_saidas([segunda], "19/10/2026 10:00",
                                    autor="paulo", com_veiculo={segunda})
        self.assertIsNone(self.banco.estadia_aberta(placa="KLM4N56"))
        self.assertIsNotNone(self.banco.estadia_aberta(placa="GHI1J23"))

    def test_dois_carros_sai_o_escolhido(self):
        segunda = self.dois_carros()
        antigo = self.banco.estadia_aberta(placa="GHI1J23")
        self.assertEqual([e["placa"] for e in
                          self.banco.estadias_abertas_do_cpf("52998224725")],
                         ["GHI1J23", "KLM4N56"])
        self.banco.registrar_saidas([segunda], "19/10/2026 10:00",
                                    autor="paulo",
                                    com_veiculo={segunda: antigo["id"]})
        self.assertIsNone(self.banco.estadia_aberta(placa="GHI1J23"))
        self.assertIsNotNone(self.banco.estadia_aberta(placa="KLM4N56"))

    def test_carro_de_outra_pessoa_e_recusado(self):
        segunda = self.dois_carros()
        outro = self.banco.inserir(registro(cpf="11144477735", placa="XYZ9A87",
                                            entrada="19/10/2026 09:40"))
        alheio = self.banco.estadia_aberta(placa="XYZ9A87")
        with self.assertRaises(dados.ErroDados):
            self.banco.registrar_saidas([segunda], "19/10/2026 10:00",
                                        autor="paulo",
                                        com_veiculo={segunda: alheio["id"]})
        self.assertEqual(self.banco.buscar(segunda)["saida"], "")
        self.assertEqual(self.banco.buscar(outro)["saida"], "")


class TestCorridaEntreEstacoes(BaseRegras):
    """Duas estações no mesmo banco: a segunda nunca apaga nem sobrescreve
    o que a primeira gravou (condição no próprio UPDATE)."""

    AGORA = datetime(2026, 10, 19, 10, 0)

    def outra_estacao(self):
        return dados.Banco(self.caminho, relogio=lambda: self.AGORA)

    def no_meio(self, alvo, acao):
        """Roda `acao` (a outra estação) logo depois da 1ª chamada de
        dados.<alvo>, ou seja, entre a leitura e a gravação desta."""
        original = getattr(dados, alvo) if hasattr(dados, alvo) else None
        modulo = dados if original else horarios
        original = original or getattr(horarios, alvo)
        feito = []

        def com_gancho(*args, **kwargs):
            if not feito:
                feito.append(True)
                acao()
            return original(*args, **kwargs)
        patcher = unittest.mock.patch.object(modulo, alvo, com_gancho)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_correcao_com_linha_desatualizada_e_recusada(self):
        """QA2 A1: a correção do nome reabria a visita que a outra estação
        tinha fechado."""
        id_ = self.banco.inserir(registro(entrada="19/10/2026 08:00"))
        aberto_na_tela = self.banco.buscar(id_)
        self.outra_estacao().registrar_saidas([id_], "19/10/2026 09:00",
                                              autor="paulo")
        novo = dict(aberto_na_tela, nome="João Ávila Souza")
        with self.assertRaises(dados.ErroDados) as erro:
            self.banco.editar(id_, novo, ["Nome"], autor="ana",
                              original=aberto_na_tela)
        self.assertIn("outra estação", str(erro.exception))
        self.assertEqual(self.banco.buscar(id_)["saida"], "19/10/2026 09:00")
        self.assertEqual(self.banco.buscar(id_)["nome"], "João Ávila")
        # com a linha em dia, a correção passa
        atual = self.banco.buscar(id_)
        self.banco.editar(id_, dict(atual, nome="João Ávila Souza"), ["Nome"],
                          autor="ana", original=atual)
        self.assertEqual(self.banco.buscar(id_)["saida"], "19/10/2026 09:00")

    def test_duas_saidas_ao_mesmo_tempo_a_segunda_nao_sobrescreve(self):
        """QA2 B1: a estação 1 gravava 09:05 por cima das 09:00."""
        id_ = self.banco.inserir(registro(entrada="19/10/2026 08:00"))
        self.no_meio("_duracao_iso", lambda: self.outra_estacao()
                     .registrar_saidas([id_], "19/10/2026 09:00", autor="paulo"))
        gravados = self.banco.registrar_saidas([id_], "19/10/2026 09:05",
                                               autor="ana")
        self.assertEqual(gravados, [])
        self.assertEqual(self.banco.buscar(id_)["saida"], "19/10/2026 09:00")
        saidas = [e for e in self.banco.eventos_do_registro(id_)
                  if e["acao"] == "Saída registrada"]
        self.assertEqual(len(saidas), 1)

    def test_encerrar_o_dia_nao_registra_saida_falsa(self):
        """QA2 B2: a saída real (00:20) de outra estação no meio do
        Encerrar o dia virava 'Saída automática ... 23:00' no histórico."""
        self.AGORA = datetime(2026, 10, 20, 0, 30)
        id_ = self.banco.inserir(registro(tipo="Aluno",
                                          entrada="19/10/2026 08:00"))
        self.no_meio("prazo_saida", lambda: self.outra_estacao()
                     .registrar_saidas([id_], "20/10/2026 00:20", autor="paulo"))
        self.assertEqual(self.banco.encerrar_pendentes(self.AGORA, autor="ana"),
                         [])
        self.assertEqual(self.banco.buscar(id_)["saida"], "20/10/2026 00:20")
        self.assertNotIn("Saída automática (encerramento)",
                         [e["acao"] for e in self.banco.eventos_do_registro(id_)])


class TestMigracaoV7ParaV8(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = os.path.join(self.pasta.name, "portaria.db")
        dados.Banco(self.caminho).inserir(registro())
        rebaixar_para_v7(self.caminho)

    def tearDown(self):
        self.pasta.cleanup()

    def test_padroes_antigos_viram_os_novos_e_ganham_tolerancia(self):
        banco = dados.Banco(self.caminho)
        self.assertEqual(versao_do_arquivo(self.caminho), dados.VERSAO_ESQUEMA)
        self.assertEqual(banco.ler_configuracao(), horarios.configuracao_padrao())
        self.assertIn("Funcionário: entrada até o fechamento", banco.avisos[0])
        self.assertIn(f"antes-v{dados.VERSAO_ESQUEMA}-de-v7",
                      os.listdir(os.path.join(self.pasta.name, "backups"))[0])

    def test_carros_de_quem_esta_no_campus_viram_estadias(self):
        con = sqlite3.connect(self.caminho)       # carona: mesma placa, depois
        con.execute("INSERT INTO registros (nome, cpf, celular, placa, tipo, "
                    "entrada) VALUES ('Beto Rocha', '11144477735', '31911112222',"
                    " 'ABC1D23', 'Aluno', '2026-10-16 09:00')")
        con.execute("INSERT INTO registros (nome, cpf, celular, placa, tipo, "
                    "entrada, saida) VALUES ('Duda Reis', '39053344705', '3191',"
                    " 'QWE1234', 'Aluno', '2026-10-15 09:00', '2026-10-15 10:00')")
        con.commit()
        con.close()
        estadias = dados.Banco(self.caminho).listar_estacionamento()
        self.assertEqual([(e["placa"], e["nome"], e["entrada"]) for e in estadias],
                         [("ABC1D23", "João Ávila", "16/10/2026 08:00")])

    @unittest.skipUnless(os.environ.get("PORTARIA_BANCO_V7"),
                         "defina PORTARIA_BANCO_V7 com a CÓPIA de um banco v7 real")
    def test_copia_de_um_banco_v7_real(self):
        """Roda com uma cópia (nunca o original) de um banco v7 em uso."""
        import shutil
        destino = os.path.join(self.pasta.name, "copia.db")
        shutil.copyfile(os.environ["PORTARIA_BANCO_V7"], destino)
        con = sqlite3.connect(destino)
        abertas_com_placa = con.execute(
            "SELECT COUNT(DISTINCT placa) FROM registros "
            "WHERE saida = '' AND placa <> ''").fetchone()[0]
        visitas = con.execute("SELECT COUNT(*) FROM registros").fetchone()[0]
        con.close()
        banco = dados.Banco(destino)
        self.assertEqual(versao_do_arquivo(destino), dados.VERSAO_ESQUEMA)
        self.assertEqual(len(banco.listar()), visitas)
        self.assertEqual(len(banco.listar_estacionamento()), abertas_com_placa)
        self.assertEqual(banco.verificar_integridade(), (True, ""))
        banco.ler_configuracao()

    def test_o_que_o_admin_mudou_continua_como_ele_deixou(self):
        con = sqlite3.connect(self.caminho)
        con.executescript("""
            UPDATE regras_categoria SET fecha_depois = -15 WHERE tipo = 'Funcionário';
            UPDATE regras_categoria SET permanencia_min = 90 WHERE tipo = 'Professor';
            UPDATE parametros SET valor = 6 WHERE chave = 'horas_retroativo';""")
        con.close()
        config = dados.Banco(self.caminho).ler_configuracao()
        self.assertEqual(config.regras["Funcionário"].fecha_depois, -15)
        self.assertEqual(config.regras["Professor"].permanencia_min, 90)
        self.assertEqual(config.horas_retroativo, 6)
        self.assertEqual(config.regras["Professor"].tolerancia_min, 30)
        self.assertEqual(config.regras["Aluno"].tolerancia_min, 0)


if __name__ == "__main__":
    unittest.main()
