"""Regras de horário (funções puras, relógio sempre fixo nos testes)."""

import unittest
from datetime import date, datetime, timedelta

from portaria import horarios as h
from portaria.horarios import (NO_CAMPUS, SAIDA_PENDENTE, SAIU, TEMPO_EXCEDIDO,
                               Evento, Horario, configuracao_padrao, hora)

SEGUNDA = date(2026, 10, 19)
SABADO = date(2026, 10, 24)
DOMINGO = date(2026, 10, 25)


def em(dia, texto):
    """datetime do dia às 'hh:mm'."""
    return datetime.combine(dia, hora(texto))


def tela(momento):
    return momento.strftime("%d/%m/%Y %H:%M")


def visita(tipo, entrada, saida=None):
    return {"tipo": tipo, "entrada": tela(entrada),
            "saida": tela(saida) if saida else ""}


class BaseRegras(unittest.TestCase):
    def setUp(self):
        self.config = configuracao_padrao()

    def permitido(self, tipo, momento):
        return h.entrada_permitida(self.config, tipo, momento)

    def excecoes(self, tipo, momento, agora=None):
        return h.excecoes_da_entrada(self.config, tipo, momento,
                                     agora or momento + timedelta(minutes=1)
                                     ).regras


class TestFuncionamento(BaseRegras):
    def janelas(self, dia):
        return [(j.abre, j.fecha) for j in h.janelas_do_dia(self.config, dia)]

    def test_padrao_semana_sabado_e_domingo(self):
        self.assertEqual(self.janelas(SEGUNDA),
                         [(em(SEGUNDA, "06:30"), em(SEGUNDA, "23:00"))])
        self.assertEqual(self.janelas(SABADO),
                         [(em(SABADO, "07:00"), em(SABADO, "14:00"))])
        self.assertEqual(self.janelas(DOMINGO), [])
        self.assertEqual(h.motivo_fechado(self.config, DOMINGO), "domingo")

    def test_feriado_fecha_o_campus(self):
        self.config.feriados[SEGUNDA] = "Dia do Professor"
        self.assertEqual(self.janelas(SEGUNDA), [])
        self.assertEqual(h.motivo_fechado(self.config, SEGUNDA),
                         "feriado: Dia do Professor")

    def test_evento_e_a_unica_janela_em_domingo_e_feriado(self):
        self.config.feriados[SEGUNDA] = "Feriado municipal"
        noite = Horario(hora("18:00"), hora("23:00"))
        for dia in (SEGUNDA, DOMINGO):
            self.config.eventos[dia] = Evento(dia, noite, "Formatura")
            janelas = h.janelas_do_dia(self.config, dia)
            self.assertEqual([(j.abre, j.fecha, j.origem) for j in janelas],
                             [(em(dia, "18:00"), em(dia, "23:00"),
                               "Evento: Formatura")])

    def test_evento_soma_ao_funcionamento_do_sabado(self):
        """Regra do coordenador: a formatura de sábado 18–23 não cancela
        a manhã 07–14; o campus abre nas duas janelas."""
        self.config.eventos[SABADO] = Evento(
            SABADO, Horario(hora("18:00"), hora("23:00")), "Formatura")
        self.assertEqual(self.janelas(SABADO),
                         [(em(SABADO, "07:00"), em(SABADO, "14:00")),
                          (em(SABADO, "18:00"), em(SABADO, "23:00"))])
        self.assertEqual(h.fechamento_do_dia(self.config, em(SABADO, "08:00")),
                         em(SABADO, "23:00"))         # fim da última janela

    def test_janelas_que_se_cruzam_viram_uma(self):
        self.config.eventos[SEGUNDA] = Evento(
            SEGUNDA, Horario(hora("20:00"), hora("23:45")), "Show")
        self.assertEqual(self.janelas(SEGUNDA),
                         [(em(SEGUNDA, "06:30"), em(SEGUNDA, "23:45"))])

    def test_aviso_antes_de_fechar_vale_para_cada_janela(self):
        self.config.eventos[SABADO] = Evento(
            SABADO, Horario(hora("18:00"), hora("23:00")), "Formatura")
        self.assertEqual(h.minutos_para_fechar(self.config, em(SABADO, "13:40")),
                         20)
        self.assertIsNone(h.minutos_para_fechar(self.config, em(SABADO, "15:00")))
        self.assertEqual(h.minutos_para_fechar(self.config, em(SABADO, "22:50")),
                         10)


class TestJanelaPorCategoria(BaseRegras):
    def test_aluno_entra_no_funcionamento_ate_30_min_antes_de_fechar(self):
        self.assertTrue(self.permitido("Aluno", em(SEGUNDA, "06:30")))
        self.assertTrue(self.permitido("Aluno", em(SEGUNDA, "22:30")))
        self.assertFalse(self.permitido("Aluno", em(SEGUNDA, "06:29")))
        self.assertFalse(self.permitido("Aluno", em(SEGUNDA, "22:31")))  # corte
        self.assertTrue(self.permitido("Aluno", em(SABADO, "13:30")))
        self.assertFalse(self.permitido("Aluno", em(SABADO, "13:31")))

    def test_professor_30_min_antes_de_abrir_ate_o_fechamento(self):
        self.assertTrue(self.permitido("Professor", em(SEGUNDA, "06:00")))
        self.assertFalse(self.permitido("Professor", em(SEGUNDA, "05:59")))
        self.assertTrue(self.permitido("Professor", em(SEGUNDA, "23:00")))
        self.assertFalse(self.permitido("Professor", em(SEGUNDA, "23:01")))

    def test_funcionario_uma_hora_antes_ate_o_fechamento(self):
        self.assertTrue(self.permitido("Funcionário", em(SEGUNDA, "05:30")))
        self.assertFalse(self.permitido("Funcionário", em(SEGUNDA, "05:29")))
        # era até 1 h depois de fechar; agora ninguém entra depois (RN23)
        self.assertTrue(self.permitido("Funcionário", em(SEGUNDA, "23:00")))
        self.assertFalse(self.permitido("Funcionário", em(SEGUNDA, "23:01")))
        self.assertFalse(self.permitido("Funcionário", em(SEGUNDA, "23:59")))

    def test_ninguem_entra_depois_de_fechar(self):
        for tipo in self.config.regras:
            with self.subTest(tipo=tipo):
                self.assertFalse(self.permitido(tipo, em(SEGUNDA, "23:01")))
                self.assertFalse(self.permitido(tipo, em(SABADO, "14:01")))

    def test_ate_positivo_salvo_antes_nao_passa_do_fechamento(self):
        # um banco antigo com "1 h depois de fechar" mudado pelo admin
        self.config.regras["Funcionário"] = h.RegraCategoria(
            True, 60, 90, permanencia_min=60)
        self.assertFalse(self.permitido("Funcionário", em(SEGUNDA, "23:30")))

    def test_janelas_fixas_valem_so_em_dia_aberto(self):
        casos = [("Visitante", "08:00", "18:00"), ("Entregador", "07:00", "17:00"),
                 ("Prestador de serviço", "07:00", "19:00")]
        for tipo, abre, fecha in casos:
            with self.subTest(tipo=tipo):
                self.assertTrue(self.permitido(tipo, em(SEGUNDA, abre)))
                self.assertTrue(self.permitido(tipo, em(SEGUNDA, fecha)))
                inicio = em(SEGUNDA, abre) - timedelta(minutes=1)
                fim = em(SEGUNDA, fecha) + timedelta(minutes=1)
                self.assertFalse(self.permitido(tipo, inicio))
                self.assertFalse(self.permitido(tipo, fim))
                self.assertFalse(self.permitido(tipo, em(DOMINGO, "10:00")))
        # no sábado a janela fixa vale, mas só até o campus fechar (14:00)
        self.assertTrue(self.permitido("Visitante", em(SABADO, "14:00")))
        self.assertFalse(self.permitido("Visitante", em(SABADO, "14:01")))
        self.assertFalse(self.permitido("Visitante", em(SABADO, "16:00")))

    def test_ninguem_entra_no_domingo_nem_no_feriado(self):
        self.config.feriados[SEGUNDA] = "Feriado"
        for tipo in self.config.regras:
            with self.subTest(tipo=tipo):
                self.assertFalse(self.permitido(tipo, em(DOMINGO, "10:00")))
                self.assertFalse(self.permitido(tipo, em(SEGUNDA, "10:00")))

    def test_evento_libera_domingo_e_feriado(self):
        self.config.feriados[SEGUNDA] = "Feriado"
        for dia in (SEGUNDA, DOMINGO):
            self.config.eventos[dia] = Evento(
                dia, Horario(hora("18:00"), hora("23:00")), "Show")
            self.assertTrue(self.permitido("Aluno", em(dia, "19:00")))
            self.assertFalse(self.permitido("Aluno", em(dia, "17:59")))
            self.assertTrue(self.permitido("Professor", em(dia, "17:30")))

    def test_evento_no_sabado_a_noite_soma_a_manha(self):
        self.config.eventos[SABADO] = Evento(
            SABADO, Horario(hora("18:00"), hora("23:00")), "Calourada")
        self.assertTrue(self.permitido("Aluno", em(SABADO, "20:00")))
        self.assertTrue(self.permitido("Aluno", em(SABADO, "08:00")))   # soma
        self.assertFalse(self.permitido("Professor", em(SABADO, "15:00")))
        self.assertFalse(self.permitido("Aluno", em(SABADO, "15:00")))  # entre
        self.assertTrue(self.permitido("Professor", em(SABADO, "17:30")))
        self.assertEqual(self.excecoes("Aluno", em(SABADO, "15:00")),
                         ["Aluno: entrada às 15:00 fora do horário permitido "
                          "(07:00–13:30, 18:00–22:30)."])

    def test_janela_fixa_so_dentro_do_campus_aberto(self):
        """QA2 A2: visitante 08:00 num domingo com evento 18–23 era
        aceito sem autorização."""
        self.config.eventos[DOMINGO] = Evento(
            DOMINGO, Horario(hora("18:00"), hora("23:00")), "Formatura")
        for tipo, momento in (("Visitante", "08:00"), ("Visitante", "10:00"),
                              ("Entregador", "07:00"),
                              ("Prestador de serviço", "07:30")):
            with self.subTest(tipo=tipo, momento=momento):
                self.assertFalse(self.permitido(tipo, em(DOMINGO, momento)))
        self.assertTrue(self.permitido("Prestador de serviço",
                                       em(DOMINGO, "18:30")))
        self.assertIn("a janela da categoria não cabe",
                      self.excecoes("Visitante", em(DOMINGO, "08:00"))[0])
        # dia útil com evento à noite: a janela fixa não começa antes da abertura
        self.config.funcionamento[0] = Horario(hora("09:00"), hora("17:00"))
        self.assertFalse(self.permitido("Visitante", em(SEGUNDA, "08:30")))
        self.assertTrue(self.permitido("Visitante", em(SEGUNDA, "09:00")))

    def test_tipo_sem_regra_nao_tem_restricao_de_horario(self):
        self.assertTrue(self.permitido("Outro", em(SEGUNDA, "03:00")))


class TestExcecoes(BaseRegras):
    def test_entrada_normal_nao_tem_excecao(self):
        self.assertEqual(self.excecoes("Aluno", em(SEGUNDA, "10:00")), [])

    def test_aluno_no_domingo_e_excecao_com_o_motivo(self):
        regras = self.excecoes("Aluno", em(DOMINGO, "10:00"))
        self.assertEqual(regras, ["Campus fechado em 25/10/2026 (domingo)."])

    def test_fora_da_janela_mostra_a_janela_certa(self):
        regras = self.excecoes("Visitante", em(SEGUNDA, "19:00"))
        self.assertEqual(regras, ["Visitante: entrada às 19:00 fora do horário "
                                  "permitido (08:00–18:00)."])

    def test_retroativa_antiga_e_excecao(self):
        entrada = em(SEGUNDA, "10:00")
        self.assertEqual(self.excecoes("Aluno", entrada,
                                       entrada + timedelta(hours=3)), [])
        regras = self.excecoes("Aluno", entrada,
                               entrada + timedelta(hours=3, minutes=1))
        self.assertEqual(len(regras), 1)
        self.assertIn("retroativa", regras[0])

    def test_limite_de_retroativo_configuravel(self):
        self.config.horas_retroativo = 2
        entrada = em(SEGUNDA, "10:00")
        self.assertTrue(self.excecoes("Aluno", entrada,
                                      entrada + timedelta(hours=2, minutes=30)))

    def test_visita_acima_de_24_h(self):
        entrada = em(SEGUNDA, "10:00")
        self.assertEqual(h.excecoes_da_duracao(entrada, entrada + timedelta(hours=24)),
                         [])
        self.assertEqual(h.excecoes_da_duracao(entrada,
                                               entrada + timedelta(hours=30)),
                         ["Visita de 30 h (o máximo é 24 h)."])

    def test_registro_com_saida_confere_entrada_e_duracao(self):
        r = visita("Aluno", em(DOMINGO, "10:00"),
                   em(DOMINGO, "10:00") + timedelta(hours=26))
        excecoes = h.excecoes_do_registro(self.config, r,
                                          em(DOMINGO, "10:00") + timedelta(days=2))
        # entrada retroativa, campus fechado, saída retroativa e 24 h
        self.assertEqual(len(excecoes.regras), 4)
        self.assertTrue(excecoes.so_com_senha)     # dias que já fecharam

    def test_correcao_so_confere_o_que_mudou(self):
        original = visita("Aluno", em(DOMINGO, "10:00"))     # já foi exceção
        agora = em(DOMINGO, "11:00")
        nome = dict(original, nome="Outro Nome")
        self.assertFalse(h.excecoes_da_correcao(self.config, original, nome,
                                                agora))
        tipo = dict(original, tipo="Visitante")
        self.assertEqual(len(h.excecoes_da_correcao(self.config, original, tipo,
                                                    agora).regras), 1)
        fevereiro = dict(original, entrada="10/02/2026 08:00")
        excecoes = h.excecoes_da_correcao(self.config, original, fevereiro, agora)
        self.assertTrue(any("retroativa" in r for r in excecoes.regras))
        self.assertTrue(excecoes.so_com_senha)
        saida = dict(fevereiro, saida="12/02/2026 08:00")
        regras = h.excecoes_da_correcao(self.config, fevereiro, saida, agora).regras
        self.assertTrue(any("24 h" in r for r in regras))
        self.assertTrue(any("Saída retroativa" in r for r in regras))


class TestPermanenciaESituacao(BaseRegras):
    def situacao(self, tipo, entrada, agora, saida=None):
        return h.situacao(self.config, visita(tipo, entrada, saida), agora)

    def test_permanencia_maxima_por_categoria(self):
        entrada = em(SEGUNDA, "10:00")
        esperado = {"Aluno": em(SEGUNDA, "23:00"),
                    "Professor": em(SEGUNDA, "23:00"),
                    "Funcionário": em(SEGUNDA, "22:00"),
                    "Visitante": em(SEGUNDA, "14:00"),
                    "Entregador": em(SEGUNDA, "11:00"),
                    "Prestador de serviço": em(SEGUNDA, "20:00")}
        for tipo, limite in esperado.items():
            with self.subTest(tipo=tipo):
                self.assertEqual(h.limite_permanencia(self.config, tipo, entrada),
                                 limite)

    def test_ninguem_passa_de_24_h(self):
        self.config.regras["Funcionário"] = h.RegraCategoria(
            True, 60, 0, permanencia_min=40 * 60, tolerancia_min=30)
        entrada = em(SEGUNDA, "10:00")
        self.assertEqual(h.limite_permanencia(self.config, "Funcionário", entrada),
                         entrada + timedelta(hours=24))
        # a saída pendente não depende da permanência: fechamento + 30 min
        self.assertEqual(h.prazo_saida(self.config, "Funcionário", entrada),
                         em(SEGUNDA, "23:30"))

    def test_ok_excedido_e_pendente(self):
        entrada = em(SEGUNDA, "10:00")
        self.assertEqual(self.situacao("Visitante", entrada, em(SEGUNDA, "14:00")),
                         NO_CAMPUS)
        self.assertEqual(self.situacao("Visitante", entrada, em(SEGUNDA, "14:01")),
                         TEMPO_EXCEDIDO)
        self.assertEqual(self.situacao("Visitante", entrada, em(SEGUNDA, "23:00")),
                         TEMPO_EXCEDIDO)
        self.assertEqual(self.situacao("Visitante", entrada, em(SEGUNDA, "23:01")),
                         SAIDA_PENDENTE)
        self.assertEqual(self.situacao("Visitante", entrada, em(SEGUNDA, "23:01"),
                                       saida=em(SEGUNDA, "12:00")), SAIU)

    def test_aluno_fica_pendente_no_fechamento(self):
        entrada = em(SEGUNDA, "08:00")
        self.assertEqual(self.situacao("Aluno", entrada, em(SEGUNDA, "23:00")),
                         NO_CAMPUS)
        self.assertEqual(self.situacao("Aluno", entrada, em(SEGUNDA, "23:01")),
                         SAIDA_PENDENTE)

    def test_professor_e_funcionario_tem_30_min_de_tolerancia(self):
        entrada = em(SEGUNDA, "18:00")
        for tipo in ("Professor", "Funcionário"):
            with self.subTest(tipo=tipo):
                self.assertEqual(h.prazo_saida(self.config, tipo, entrada),
                                 em(SEGUNDA, "23:30"))
                self.assertNotEqual(self.situacao(tipo, entrada,
                                                  em(SEGUNDA, "23:30")),
                                    SAIDA_PENDENTE)
                self.assertEqual(self.situacao(tipo, entrada,
                                               em(SEGUNDA, "23:31")),
                                 SAIDA_PENDENTE)
        # na tolerância o professor já passou da permanência (até fechar)
        self.assertEqual(self.situacao("Professor", entrada, em(SEGUNDA, "23:10")),
                         TEMPO_EXCEDIDO)

    def test_as_outras_categorias_ficam_pendentes_no_fechamento(self):
        # o caso do aluno: visitante que entrou 22:55 tinha prazo até 02:55
        entrada = em(SEGUNDA, "22:55")
        for tipo in ("Aluno", "Visitante", "Entregador", "Prestador de serviço"):
            with self.subTest(tipo=tipo):
                self.assertEqual(h.prazo_saida(self.config, tipo, entrada),
                                 em(SEGUNDA, "23:00"))
                self.assertEqual(self.situacao(tipo, entrada,
                                               em(SEGUNDA, "23:01")),
                                 SAIDA_PENDENTE)

    def test_tolerancia_configuravel_por_categoria(self):
        self.config.regras["Aluno"] = h.RegraCategoria(
            True, 0, -30, ate_fechamento=True, tolerancia_min=15)
        self.assertEqual(h.prazo_saida(self.config, "Aluno", em(SEGUNDA, "08:00")),
                         em(SEGUNDA, "23:15"))

    def test_entrada_depois_do_prazo_ja_nasce_pendente(self):
        # só com autorização; o dia dela acabou: o prazo é a própria entrada
        aluno = em(SEGUNDA, "23:10")
        self.assertEqual(h.prazo_saida(self.config, "Aluno", aluno), aluno)
        self.assertEqual(self.situacao("Aluno", aluno, em(SEGUNDA, "23:11")),
                         SAIDA_PENDENTE)
        # o professor ainda está na tolerância do dia
        self.assertEqual(h.prazo_saida(self.config, "Professor", aluno),
                         em(SEGUNDA, "23:30"))

    def test_pendente_no_fechamento_do_evento(self):
        self.config.eventos[SABADO] = Evento(
            SABADO, Horario(hora("18:00"), hora("23:00")), "Calourada")
        entrada = em(SABADO, "19:00")
        self.assertEqual(h.prazo_saida(self.config, "Aluno", entrada),
                         em(SABADO, "23:00"))

    def test_entrada_com_campus_fechado_tem_prazo_no_fim_do_dia(self):
        entrada = em(DOMINGO, "10:00")
        self.assertEqual(h.prazo_saida(self.config, "Aluno", entrada),
                         em(DOMINGO + timedelta(days=1), "00:00"))
        self.assertGreater(h.prazo_saida(self.config, "Visitante", entrada),
                           entrada)

    def test_contar_situacoes(self):
        agora = em(SEGUNDA, "15:00")
        registros = [visita("Aluno", em(SEGUNDA, "08:00")),
                     visita("Visitante", em(SEGUNDA, "09:00")),
                     visita("Aluno", em(SEGUNDA - timedelta(days=1), "08:00")),
                     visita("Aluno", em(SEGUNDA, "08:00"), em(SEGUNDA, "09:00"))]
        self.assertEqual(h.contar_situacoes(self.config, registros, agora),
                         {NO_CAMPUS: 1, TEMPO_EXCEDIDO: 1, SAIDA_PENDENTE: 1})


class TestDataAbsurda(BaseRegras):
    def test_ano_9999_no_banco_nao_derruba_a_situacao(self):
        """QA2 M3: uma visita de 31/12/9999 derrubava o login."""
        r = {"tipo": "Aluno", "entrada": "31/12/9999 23:00", "saida": ""}
        self.assertEqual(h.situacao(self.config, r, em(SEGUNDA, "10:00")),
                         NO_CAMPUS)
        self.assertEqual(h.contar_situacoes(self.config, [r],
                                            em(SEGUNDA, "10:00"))[NO_CAMPUS], 1)


class TestAvisoDeFechamento(BaseRegras):
    def test_aviso_nos_ultimos_30_minutos(self):
        self.assertIsNone(h.minutos_para_fechar(self.config, em(SEGUNDA, "22:29")))
        self.assertEqual(h.minutos_para_fechar(self.config, em(SEGUNDA, "22:30")), 30)
        self.assertEqual(h.minutos_para_fechar(self.config, em(SEGUNDA, "22:59")), 1)
        self.assertIsNone(h.minutos_para_fechar(self.config, em(SEGUNDA, "23:00")))
        self.assertIsNone(h.minutos_para_fechar(self.config, em(DOMINGO, "22:45")))

    def test_minutos_configuraveis(self):
        self.config.minutos_aviso = 60
        self.assertEqual(h.minutos_para_fechar(self.config, em(SABADO, "13:00")), 60)


class TestLeituraDaConfiguracao(unittest.TestCase):
    def test_horas_validas_e_invalidas(self):
        self.assertEqual(h.ler_hora("07:30", "x"), (hora("07:30"), ""))
        for texto in ("7:30", "24:00", "07:60", "0730", "aa:bb", ""):
            with self.subTest(texto=texto):
                self.assertIsNone(h.ler_hora(texto, "x")[0])

    def test_fechamento_depois_da_abertura(self):
        valor, erro = h.ler_horario("18:00", "08:00", "Sábado")
        self.assertIsNone(valor)
        self.assertIn("depois da abertura", erro)
        self.assertIsNone(h.ler_horario("08:00", "08:00", "x")[0])

    def test_funcionamento_da_semana(self):
        linhas = [(True, "06:30", "23:00")] * 5 + [(True, "07:00", "14:00"),
                                                     (False, "", "")]
        funcionamento, erro = h.ler_funcionamento(linhas)
        self.assertEqual(erro, "")
        self.assertEqual(funcionamento, configuracao_padrao().funcionamento)
        linhas[2] = (True, "23:00", "06:30")
        _, erro = h.ler_funcionamento(linhas)
        self.assertIn("Quarta-feira", erro)

    def test_regra_relativa_e_fixa(self):
        regra, erro = h.ler_regra("Aluno", True, "0", "-30", True, "0")
        self.assertEqual((regra, erro), (configuracao_padrao().regras["Aluno"], ""))
        regra, erro = h.ler_regra("Visitante", False, "08:00", "18:00", False, "240")
        self.assertEqual((regra, erro),
                         (configuracao_padrao().regras["Visitante"], ""))
        self.assertIsNone(h.ler_regra("Visitante", False, "18:00", "08:00",
                                      False, "240")[0])
        self.assertIsNone(h.ler_regra("Aluno", True, "x", "0", True, "0")[0])
        self.assertIsNone(h.ler_regra("Visitante", False, "08:00", "18:00",
                                      False, "0")[0])      # permanência zero
        regra, erro = h.ler_regra("Professor", True, "30", "0", True, "0", "30")
        self.assertEqual((regra, erro),
                         (configuracao_padrao().regras["Professor"], ""))
        valor, erro = h.ler_regra("Funcionário", True, "60", "60", False, "720")
        self.assertIsNone(valor)                # depois de fechar, não
        self.assertIn("Ninguém entra depois de fechar", erro)
        self.assertIsNone(h.ler_regra("Aluno", True, "0", "-30", True, "0",
                                      "-5")[0])                # tolerância

    def test_parametros(self):
        self.assertEqual(h.ler_parametros("45", "6"), ((45, 6), ""))
        self.assertEqual(h.ler_parametros("0", "12"), ((0, 12), ""))
        self.assertIn("horas", h.ler_parametros("30", "0")[1])
        self.assertIn("minutos", h.ler_parametros("abc", "12")[1])
        self.assertIsNone(h.ler_parametros("500", "12")[0])

    def test_feriado_e_evento(self):
        config = configuracao_padrao()
        (dia, nome), erro = h.ler_feriado("25/12/2026", "Natal", config)
        self.assertEqual((dia, nome, erro), (date(2026, 12, 25), "Natal", ""))
        config.feriados[dia] = nome
        self.assertIn("já é feriado", h.ler_feriado("25/12/2026", "Natal", config)[1])
        self.assertIn("inválida", h.ler_feriado("31/02/2026", "Natal", config)[1])
        evento, erro = h.ler_evento("25/10/2026", "18:00", "23:00", "Show", config)
        self.assertEqual(erro, "")
        self.assertEqual(evento.horario, Horario(hora("18:00"), hora("23:00")))
        self.assertIsNone(h.ler_evento("25/10/2026", "23:00", "18:00", "Show",
                                       config)[0])
        self.assertIsNone(h.ler_evento("25/10/2026", "18:00", "23:00", "", config)[0])

    def test_descrever_regra(self):
        regras = configuracao_padrao().regras
        self.assertEqual(h.descrever_regra("Aluno", regras["Aluno"]),
                         "Aluno: entrada desde a abertura até 30 min antes de "
                         "fechar; fica até o fechamento")
        self.assertEqual(h.descrever_regra("Professor", regras["Professor"]),
                         "Professor: entrada desde 30 min antes de abrir até o "
                         "fechamento; fica até o fechamento; tolerância de "
                         "30 min depois de fechar")
        self.assertEqual(h.descrever_regra("Visitante", regras["Visitante"]),
                         "Visitante: entrada das 08:00 às 18:00; fica no "
                         "máximo 4 h")


class TestLancamentoRetroativo(BaseRegras):
    """RN24: (a) até 3 h com o dia aberto: normal; (b) mais de 3 h:
    autorização; (c) dia que já fechou: só com senha."""

    def retro(self, momento, agora):
        return h.retroativo(self.config, "Entrada", momento, agora)

    def test_a_ate_3_h_com_o_dia_aberto_e_normal(self):
        self.assertFalse(self.retro(em(SEGUNDA, "12:00"), em(SEGUNDA, "15:00")))

    def test_ate_5_min_no_passado_e_agora(self):
        self.assertFalse(self.retro(em(SEGUNDA, "22:58"), em(SEGUNDA, "23:03")))
        self.assertTrue(self.retro(em(SEGUNDA, "22:57"), em(SEGUNDA, "23:03")))

    def test_b_mais_de_3_h_pede_autorizacao_sem_senha(self):
        excecoes = self.retro(em(SEGUNDA, "11:59"), em(SEGUNDA, "15:00"))
        self.assertEqual(excecoes.regras, ["Entrada retroativa: 19/10/2026 11:59 "
                                           "é de mais de 3 h atrás."])
        self.assertFalse(excecoes.so_com_senha)

    def test_c_depois_do_fechamento_so_com_senha(self):
        casos = [(em(SEGUNDA, "22:00"), em(SEGUNDA, "23:10")),     # 1 h 10
                 (em(SEGUNDA, "22:30"),
                  em(SEGUNDA + timedelta(days=1), "00:10")),
                 (em(SEGUNDA, "20:00"), em(SEGUNDA + timedelta(days=1), "08:00"))]
        for momento, agora in casos:
            with self.subTest(agora=agora):
                excecoes = self.retro(momento, agora)
                self.assertTrue(excecoes.so_com_senha)
                self.assertIn("fechou às 23:00 de 19/10/2026",
                              excecoes.regras[0])

    def test_dia_sem_expediente_fecha_a_meia_noite(self):
        self.assertFalse(self.retro(em(DOMINGO, "10:00"), em(DOMINGO, "12:00")))
        excecoes = self.retro(em(DOMINGO, "10:00"),
                              em(DOMINGO + timedelta(days=1), "07:00"))
        self.assertTrue(excecoes.so_com_senha)
        self.assertIn("meia-noite de 25/10/2026", excecoes.regras[0])

    def saida(self, tipo, momento, agora):
        return h.retroativo(self.config, "Saída", momento, agora, tipo)

    def test_b_saida_com_o_campus_fechado_e_excecao_mesmo_recente(self):
        """QA1 M4: 00:30 lançando a saída de 00:10 passava sem nada."""
        terca = SEGUNDA + timedelta(days=1)
        casos = [(em(terca, "00:10"), em(terca, "00:30")),     # madrugada
                 (em(terca, "02:00"), em(terca, "05:50")),
                 (em(DOMINGO, "10:00"), em(DOMINGO, "10:30"))]  # domingo
        for momento, agora in casos:
            with self.subTest(momento=momento):
                excecoes = self.saida("Aluno", momento, agora)
                self.assertFalse(excecoes.so_com_senha)
                self.assertIn("campus fechado", excecoes.regras[-1])
        # sábado com evento: entre as janelas (14:00–18:00) também é fechado
        self.config.eventos[SABADO] = Evento(
            SABADO, Horario(hora("18:00"), hora("23:00")), "Formatura")
        excecoes = self.saida("Aluno", em(SABADO, "15:00"), em(SABADO, "15:30"))
        self.assertIn("aberto 07:00–14:00, 18:00–23:00", excecoes.regras[0])
        self.assertFalse(self.saida("Aluno", em(SABADO, "19:00"),
                                    em(SABADO, "19:30")))

    def test_c_usa_o_prazo_da_categoria(self):
        """QA1 M6: a saída real às 23:00 da funcionária (tolerância até
        23:30), lançada às 23:10, não pede a senha."""
        self.assertFalse(self.saida("Funcionário", em(SEGUNDA, "23:00"),
                                    em(SEGUNDA, "23:10")))
        self.assertFalse(self.saida("Funcionário", em(SEGUNDA, "23:20"),
                                    em(SEGUNDA, "23:28")))      # na tolerância
        senha = self.saida("Funcionário", em(SEGUNDA, "23:00"),
                           em(SEGUNDA, "23:40"))
        self.assertTrue(senha.so_com_senha)
        self.assertIn("tolerância da categoria até 23:30", senha.regras[0])
        self.assertTrue(self.saida("Aluno", em(SEGUNDA, "23:00"),
                                   em(SEGUNDA, "23:10")).so_com_senha)

    def test_os_segundos_do_relogio_nao_contam(self):
        """QA2 B6: 13:00:30 (a tela mostra 13:00) ainda é 3 h exatas."""
        agora = em(SEGUNDA, "13:00").replace(second=30)
        self.assertFalse(self.retro(em(SEGUNDA, "10:00"), agora))

    def test_saida_digitada_no_cadastro_tambem_conta(self):
        r = visita("Aluno", em(SEGUNDA, "21:00"), em(SEGUNDA, "22:00"))
        excecoes = h.excecoes_do_registro(self.config, r, em(SEGUNDA, "23:10"))
        self.assertEqual(len(excecoes.regras), 2)          # entrada e saída
        self.assertTrue(excecoes.regras[1].startswith("Saída retroativa"))
        self.assertTrue(excecoes.so_com_senha)


class TestSituacaoDoCarro(unittest.TestCase):
    """RN32: carro com o dono fora fica "Dono fora do campus"."""

    AGORA = datetime(2026, 10, 16, 12, 0)

    def estadia(self, dentro):
        return {"entrada": "16/10/2026 08:00", "tipo": "Professor",
                "responsavel_dentro": dentro}

    def test_dono_fora_e_dono_dentro(self):
        config = h.configuracao_padrao()
        self.assertEqual(h.situacao_veiculo(config, self.estadia(False),
                                                   self.AGORA),
                         h.DONO_FORA)
        self.assertEqual(h.situacao_veiculo(config, self.estadia(True),
                                                   self.AGORA),
                         h.NO_ESTACIONAMENTO)

    def test_pendente_vale_mais_que_dono_fora(self):
        config = h.configuracao_padrao()
        tarde = datetime(2026, 10, 17, 9, 0)
        self.assertEqual(h.situacao_veiculo(config, self.estadia(False),
                                                   tarde),
                         h.VEICULO_PENDENTE)


if __name__ == "__main__":
    unittest.main()


class TestEditarFeriadoEEvento(unittest.TestCase):  # RN44 (2.3)
    def test_a_propria_data_pode_ficar_e_outra_repetida_nao(self):
        from datetime import date as _date
        from portaria import horarios as h
        config = h.configuracao_padrao()
        config.feriados[_date(2026, 12, 25)] = "Natal"
        config.feriados[_date(2026, 11, 2)] = "Finados"
        valor, erro = h.ler_feriado("25/12/2026", "Natal de novo", config,
                                    editando=_date(2026, 12, 25))
        self.assertEqual((valor, erro), ((_date(2026, 12, 25), "Natal de novo"),
                                         ""))
        _, erro = h.ler_feriado("02/11/2026", "Natal", config,
                                editando=_date(2026, 12, 25))
        self.assertIn("já é feriado", erro)
        _, erro = h.ler_feriado("25/12/2026", "Natal", config)
        self.assertIn("já é feriado", erro)
        evento, _ = h.ler_evento("25/10/2026", "18:00", "23:00", "Show",
                                 config)
        config.eventos[evento.data] = evento
        novo, erro = h.ler_evento("25/10/2026", "19:00", "23:30", "Show",
                                  config, editando=evento.data)
        self.assertEqual(erro, "")
        self.assertEqual(novo.descricao, "Show")
        _, erro = h.ler_evento("25/10/2026", "19:00", "23:30", "Show", config)
        self.assertIn("Já há um evento", erro)
