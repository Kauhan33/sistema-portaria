"""
Versão 3.6: as seções do Painel (Visão geral, Veículos, Entregas, Chaves,
Ocorrências e Funcionários). As consultas do banco com dados conhecidos
(casos vazios, limites do período, só leitura, sem CPF) e a tela (troca de
seção, só a seção na tela é relida, porteiro e administrador, tema escuro,
janela pequena e a Visão geral igual à de antes).
"""

import re
import sqlite3
import tkinter as tk
import unittest
from datetime import date, datetime, timedelta
from unittest import mock

from portaria import dados, estilo, graficos
from portaria.dados_modulos import cpf_ficticio
from portaria.tela_dashboard import (NUMEROS, SECOES, SECOES_DO_PAINEL,
                                     VISAO_GERAL, duracao)
from portaria.validacao import CATEGORIAS_OCORRENCIA, TIPOS_ACESSO

from .test_dados import registro
from .test_interface import BaseInterface
from .test_regras_no_banco import BaseRegras, senha_do_admin
from .test_tema import BaseTema

CARLA, BRUNO, DAVI, EVA = ("52998224725", "11144477735", "39053344705",
                           "86288366757")
CONSULTAS = ("painel_veiculos", "painel_entregas", "painel_chaves",
             "painel_ocorrencias", "painel_funcionarios")
CPF_NA_TELA = re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11}")


def gravar(caminho, sql, *params):
    """Grava direto na tabela (só as colunas de sempre): as consultas do
    Painel são só leitura, e os testes delas não dependem das regras de
    quem entrega chave ou retira encomenda (testadas em test_livros)."""
    con = sqlite3.connect(caminho)
    try:
        with con:
            return con.execute(sql, params).lastrowid
    finally:
        con.close()


def iso(texto):
    """'dd/mm/aaaa hh:mm' → 'AAAA-MM-DD HH:MM' ('' fica '')."""
    return (datetime.strptime(texto, "%d/%m/%Y %H:%M")
            .strftime("%Y-%m-%d %H:%M") if texto else "")


def nova_chave(caminho, nome, ativa=1):
    return gravar(caminho, "INSERT INTO chaves (nome, local, ativa, "
                  "criada_em, criada_por) VALUES (?, '', ?, "
                  "'2026-10-01 08:00', 'ana')", nome, ativa)


def emprestimo(caminho, chave, nome, retirada, devolvida="", cpf=""):
    gravar(caminho, "INSERT INTO emprestimos_chave (chave_id, nome, cpf, "
           "retirada_em, entregue_por, devolvida_em, recebida_por) VALUES "
           "(?, ?, ?, ?, 'paulo', ?, ?)", chave, nome, cpf, iso(retirada),
           iso(devolvida), "paulo" if devolvida else "")


def encomenda(caminho, destinatario, recebida, retirada="", quem="",
              cpf=""):
    gravar(caminho, "INSERT INTO encomendas (recebida_em, destinatario, "
           "remetente, recebida_por, retirada_em, retirada_nome, "
           "retirada_cpf, entregue_por) VALUES (?, ?, 'Correios', 'paulo', "
           "?, ?, ?, ?)", iso(recebida), destinatario, iso(retirada), quem,
           cpf, "paulo" if retirada else "")


class BasePainel(BaseRegras):
    """Banco com Ana e Bia (administradoras) e Paulo (porteiro); o relógio
    é self.AGORA (segunda, 19/10/2026 10:00), que cada teste pode mudar."""

    def em(self, momento):
        """Muda o relógio do banco (para gravar no passado)."""
        self.AGORA = momento

    def entrar(self, cpf, nome, entrada, placa="", tipo="Funcionário",
               saida="", **extra):
        return self.banco.inserir(registro(
            cpf=cpf, nome=nome, placa=placa, tipo=tipo, entrada=entrada,
            saida=saida, **extra))

    def eventos(self):
        return len(self.banco.listar_eventos())


class TestPeriodoEVazio(BasePainel):
    def test_periodo_fora_dos_limites_e_recusado(self):
        for consulta in CONSULTAS:
            for dias in (0, -1, 367, "7", 7.0, True, None):
                with self.subTest(consulta=consulta, dias=dias):
                    with self.assertRaises(dados.ErroDados) as erro:
                        getattr(self.banco, consulta)(dias)
                    self.assertIn("Período inválido", str(erro.exception))

    def test_limites_do_periodo(self):
        hoje = self.AGORA.date()
        for consulta in CONSULTAS:
            for dias in (1, 7, 30, 366):
                with self.subTest(consulta=consulta, dias=dias):
                    por_dia = getattr(self.banco, consulta)(dias)["por_dia"]
                    self.assertEqual(len(por_dia), dias)
                    self.assertEqual(por_dia[-1][0], hoje)
                    self.assertEqual(por_dia[0][0],
                                     hoje - timedelta(days=dias - 1))

    def test_banco_vazio(self):
        v = self.banco.painel_veiculos()
        self.assertEqual((v["no_estacionamento"], v["vagas"],
                          v["entradas_hoje"], v["saidas_hoje"],
                          v["entradas_periodo"], v["pendentes"],
                          v["dono_fora"], v["sem_o_dono"],
                          v["com_autorizado"]), (0,) * 9)
        self.assertIsNone(v["mais_antigo"])
        self.assertEqual(v["por_tipo"], [(t, 0, 0) for t in TIPOS_ACESSO])
        self.assertEqual(v["por_hora"], [0] * 24)
        e = self.banco.painel_entregas()
        self.assertEqual((e["aguardando"], e["recebidas_hoje"],
                          e["retiradas_periodo"], e["entregadores_hoje"]),
                         (0, 0, 0, 0))
        self.assertIsNone(e["mais_antiga"])
        self.assertIsNone(e["tempo_medio"])
        self.assertEqual(e["destinatarios"], [])
        c = self.banco.painel_chaves()
        self.assertEqual((c["cadastradas"], c["emprestadas"]), (0, 0))
        self.assertIsNone(c["mais_tempo_fora"])
        self.assertIsNone(c["tempo_medio_fora"])
        self.assertEqual(c["mais_usadas"], [])
        o = self.banco.painel_ocorrencias()
        self.assertEqual((o["abertas"], o["hoje"], o["no_periodo"]), (0, 0, 0))
        self.assertEqual(o["por_categoria"],
                         [(c, 0, 0) for c in CATEGORIAS_OCORRENCIA])
        f = self.banco.painel_funcionarios()
        self.assertEqual((f["cadastrados"], f["dentro"], f["vieram_hoje"],
                          f["sem_matricula"]), (0, 0, 0, 0))
        self.assertIsNone(f["ha_mais_tempo"])
        self.assertIsNone(f["permanencia_media"])
        self.assertEqual(f["por_setor"], [])
        for consulta in CONSULTAS:
            self.assertTrue(all(n == 0 for _, n in
                                getattr(self.banco, consulta)(30)["por_dia"]))

    def test_so_leitura(self):
        self.entrar(CARLA, "Carla Nogueira", "19/10/2026 08:00",
                    placa="BRA2E19")
        antes = self.eventos()
        for consulta in CONSULTAS:
            getattr(self.banco, consulta)(30)
        self.assertEqual(self.eventos(), antes)


class TestVeiculos(BasePainel):
    def setUp(self):
        super().setUp()
        self.banco.salvar_lotacao(2, False, autor="ana")
        # Carla chegou de carro hoje e saiu a pé; Bruno está a pé
        self.carla = self.entrar(CARLA, "Carla Nogueira", "19/10/2026 08:00",
                                 placa="BRA2E19")
        self.bruno = self.entrar(BRUNO, "Bruno Almeida", "19/10/2026 08:30")
        self.carro = self.banco.estadia_aberta(placa="BRA2E19")["id"]
        self.banco.registrar_saidas([self.carla], "19/10/2026 09:00",
                                    autor="paulo")
        # Davi deixou o carro na sexta e não saiu: veículo pendente
        self.entrar(DAVI, "Davi Prado", "16/10/2026 08:00", placa="ABC1D23")
        # Eva veio de carro ontem (domingo) e já foi embora com ele
        self.entrar(EVA, "Eva Martins", "18/10/2026 14:00", placa="QWE1234",
                    saida="18/10/2026 15:00", tipo="Visitante",
                    motivo="Reunião", anfitriao="Secretaria")

    def test_numeros_de_agora_e_de_hoje(self):
        v = self.banco.painel_veiculos(7)
        self.assertEqual(v["no_estacionamento"], 2)
        self.assertEqual(v["vagas"], 2)
        self.assertEqual(v["entradas_hoje"], 1)
        self.assertEqual(v["saidas_hoje"], 0)
        self.assertEqual(v["entradas_periodo"], 3)
        self.assertEqual(v["pendentes"], 1)              # o do Davi
        self.assertEqual(v["dono_fora"], 1)              # o da Carla
        self.assertEqual(v["mais_antigo"]["placa"], "ABC1D23")
        self.assertEqual(v["mais_antigo"]["nome"], "Davi Prado")
        self.assertEqual(v["mais_antigo"]["ha"], timedelta(days=3, hours=2))

    def test_um_dia_so_e_por_hora(self):
        v = self.banco.painel_veiculos(1)
        self.assertEqual(v["entradas_periodo"], 1)
        self.assertEqual(v["por_dia"], [(date(2026, 10, 19), 1)])
        self.assertEqual(v["por_hora"][8], 1)
        self.assertEqual(sum(v["por_hora"]), 1)
        v = self.banco.painel_veiculos(7)
        self.assertEqual(dict(v["por_dia"])[date(2026, 10, 18)], 1)
        self.assertEqual(v["por_hora"][14], 1)

    def test_por_tipo_no_periodo_e_agora(self):
        tipos = {t: (total, agora) for t, total, agora in
                 self.banco.painel_veiculos(7)["por_tipo"]}
        self.assertEqual(tipos["Funcionário"], (2, 2))
        self.assertEqual(tipos["Visitante"], (1, 0))
        self.assertEqual(tipos["Aluno"], (0, 0))
        # (o carro do Davi está lá agora mesmo fora do período de 1 dia)
        tipos = {t: (total, agora) for t, total, agora in
                 self.banco.painel_veiculos(1)["por_tipo"]}
        self.assertEqual(tipos["Funcionário"], (1, 2))

    def test_saida_com_autorizado_e_com_senha(self):
        self.banco.adicionar_autorizado(CARLA, BRUNO, "Bruno Almeida", None,
                                        autor="ana")
        self.banco.registrar_saidas([self.bruno], "19/10/2026 10:00",
                                    autor="paulo",
                                    com_veiculo={self.bruno: self.carro})
        v = self.banco.painel_veiculos(7)
        self.assertEqual((v["com_autorizado"], v["sem_o_dono"]), (1, 1))
        self.assertEqual((v["saidas_hoje"], v["no_estacionamento"]), (1, 1))
        davi = self.banco.estadia_aberta(placa="ABC1D23")["id"]
        self.assertTrue(self.banco.registrar_saida_veiculo(
            davi, "19/10/2026 10:00", autor="paulo",
            autorizacao=senha_do_admin()))
        v = self.banco.painel_veiculos(7)
        self.assertEqual((v["com_autorizado"], v["sem_o_dono"]), (1, 2))
        self.assertEqual((v["no_estacionamento"], v["pendentes"]), (0, 0))
        self.assertIsNone(v["mais_antigo"])

    def test_o_dono_saindo_com_o_carro_nao_conta(self):
        self.banco.salvar_lotacao(10, False, autor="ana")
        id_ = self.entrar(cpf_ficticio(123456789), "Gil Souza",
                          "19/10/2026 09:00", placa="RST4U56")
        carro = self.banco.estadia_aberta(placa="RST4U56")["id"]
        self.banco.registrar_saidas([id_], "19/10/2026 09:40", autor="paulo",
                                    com_veiculo={id_: carro})
        v = self.banco.painel_veiculos(7)
        self.assertEqual((v["com_autorizado"], v["sem_o_dono"]), (0, 0))
        self.assertEqual(v["saidas_hoje"], 1)


class TestEntregas(BasePainel):
    def setUp(self):
        super().setUp()
        c = self.caminho
        encomenda(c, "Helena Souza", "16/10/2026 09:00", "16/10/2026 12:00",
                  "Helena Souza")
        encomenda(c, "helena souza", "19/10/2026 08:00")
        encomenda(c, "Rafael Lima", "19/10/2026 09:00", "19/10/2026 09:30",
                  "Rafael Lima")
        encomenda(c, "Biblioteca", "09/10/2026 09:00")      # fora dos 7 dias

    def test_numeros(self):
        e = self.banco.painel_entregas(7)
        self.assertEqual(e["aguardando"], 2)
        self.assertEqual(e["mais_antiga"]["destinatario"], "Biblioteca")
        self.assertEqual(e["mais_antiga"]["ha"], timedelta(days=10, hours=1))
        self.assertEqual((e["recebidas_hoje"], e["recebidas_periodo"]), (2, 3))
        self.assertEqual((e["retiradas_hoje"], e["retiradas_periodo"]), (1, 2))
        self.assertEqual(e["tempo_medio"], timedelta(minutes=105))  # 3h e 30min
        self.assertEqual(dict(e["por_dia"])[date(2026, 10, 16)], 1)
        self.assertEqual(e["por_dia"][-1], (date(2026, 10, 19), 2))

    def test_ranking_junta_maiusculas_e_conta_quem_aguarda(self):
        e = self.banco.painel_entregas(7)
        self.assertEqual(e["destinatarios"][0][1:], (2, 1))
        self.assertEqual(e["destinatarios"][0][0].lower(), "helena souza")
        self.assertEqual(e["destinatarios"][1], ("Rafael Lima", 1, 0))
        e = self.banco.painel_entregas(30)
        self.assertIn(("Biblioteca", 1, 1), e["destinatarios"])
        self.assertEqual(e["recebidas_periodo"], 4)

    def test_ranking_tem_limite(self):
        for n in range(10):
            encomenda(self.caminho, f"Destinatário {n:02d}", "19/10/2026 09:40")
        e = self.banco.painel_entregas(7)
        self.assertEqual(len(e["destinatarios"]), 6)
        contagens = [n for _, n, _ in e["destinatarios"]]
        self.assertEqual(contagens, sorted(contagens, reverse=True))

    def test_entregadores(self):
        visita = {"tipo": "Entregador", "motivo": "Entrega", "anfitriao":
                  "Portaria"}
        self.entrar(CARLA, "Carla Nogueira", "19/10/2026 09:50", **visita)
        self.entrar(BRUNO, "Bruno Almeida", "17/10/2026 09:00",
                    saida="17/10/2026 09:10", **visita)
        self.entrar(DAVI, "Davi Prado", "19/10/2026 09:00", tipo="Visitante",
                    motivo="Reunião", anfitriao="Diretoria")
        e = self.banco.painel_entregas(7)
        self.assertEqual((e["entregadores_hoje"], e["entregadores_periodo"],
                          e["entregadores_dentro"]), (1, 2, 1))
        self.assertEqual(self.banco.painel_entregas(1)["entregadores_periodo"],
                         1)


class TestChaves(BasePainel):
    def setUp(self):
        super().setUp()
        c = self.caminho
        self.lab = nova_chave(c, "Laboratório 2")
        self.aud = nova_chave(c, "Auditório")
        self.almox = nova_chave(c, "Almoxarifado")
        nova_chave(c, "Sala antiga", ativa=0)                # removida
        emprestimo(c, self.lab, "Carla Nogueira", "17/10/2026 08:00",
                   "17/10/2026 10:00")
        emprestimo(c, self.lab, "Bruno Almeida", "19/10/2026 08:00", cpf=BRUNO)
        emprestimo(c, self.aud, "Davi Prado", "19/10/2026 09:00",
                   "19/10/2026 09:30")

    def test_numeros(self):
        c = self.banco.painel_chaves(7)
        self.assertEqual((c["cadastradas"], c["emprestadas"]), (3, 1))
        self.assertEqual(c["mais_tempo_fora"],
                         {"chave": "Laboratório 2", "nome": "Bruno Almeida",
                          "ha": timedelta(hours=2)})
        self.assertEqual((c["emprestimos_hoje"], c["emprestimos_periodo"]),
                         (2, 3))
        self.assertEqual((c["devolucoes_hoje"], c["devolucoes_periodo"]),
                         (1, 2))
        self.assertEqual(c["tempo_medio_fora"], timedelta(minutes=75))
        self.assertEqual(c["mais_usadas"], [("Laboratório 2", 2, True),
                                            ("Auditório", 1, False)])
        self.assertEqual(c["por_dia"][-3:], [(date(2026, 10, 17), 1),
                                             (date(2026, 10, 18), 0),
                                             (date(2026, 10, 19), 2)])

    def test_periodo_de_um_dia(self):
        c = self.banco.painel_chaves(1)
        self.assertEqual(c["emprestimos_periodo"], 2)
        self.assertEqual(c["tempo_medio_fora"], timedelta(minutes=30))
        self.assertEqual(c["mais_usadas"], [("Auditório", 1, False),
                                            ("Laboratório 2", 1, True)])

    def test_chave_removida_sai_da_conta_de_cadastradas(self):
        gravar(self.caminho, "UPDATE chaves SET ativa = 0 WHERE id = ?",
               self.almox)
        self.assertEqual(self.banco.painel_chaves(7)["cadastradas"], 2)


class TestOcorrencias(BasePainel):
    def setUp(self):
        super().setUp()
        self.em(datetime(2026, 10, 15, 22, 0))
        self.banco.registrar_ocorrencia("Veículo", "Carro sobre a calçada.",
                                        "paulo")
        self.em(datetime(2026, 10, 18, 7, 0))
        a = self.banco.registrar_ocorrencia("Equipamento", "Cancela travada.",
                                            "paulo")
        self.em(datetime(2026, 10, 18, 9, 0))
        self.banco.resolver_ocorrencia(a, "ana")
        self.em(datetime(2026, 10, 19, 8, 0))
        self.banco.registrar_ocorrencia("Equipamento", "Catraca sem energia.",
                                        "paulo")
        self.banco.registrar_ocorrencia("Segurança", "Portão aberto à noite.",
                                        "paulo")
        self.em(datetime(2026, 10, 1, 8, 0))           # fora dos 7 dias
        self.banco.registrar_ocorrencia("Outra", "Lâmpada queimada.", "paulo")
        self.em(datetime(2026, 10, 19, 10, 0))

    def test_numeros(self):
        o = self.banco.painel_ocorrencias(7)
        self.assertEqual(o["abertas"], 4)
        self.assertEqual(o["mais_antiga"]["categoria"], "Outra")
        self.assertEqual(o["mais_antiga"]["ha"], timedelta(days=18, hours=2))
        self.assertEqual((o["hoje"], o["no_periodo"]), (2, 4))
        self.assertEqual(o["resolvidas_periodo"], 1)
        self.assertEqual(o["tempo_medio"], timedelta(hours=2))
        self.assertEqual(dict(o["por_dia"])[date(2026, 10, 15)], 1)

    def test_por_categoria_ordena_e_mostra_todas(self):
        o = self.banco.painel_ocorrencias(7)
        self.assertEqual(o["por_categoria"][0], ("Equipamento", 2, 1))
        # empate: a ordem da lista de categorias
        self.assertEqual(o["por_categoria"][1:3], [("Segurança", 1, 1),
                                                   ("Veículo", 1, 1)])
        self.assertEqual({c for c, _, _ in o["por_categoria"]},
                         set(CATEGORIAS_OCORRENCIA))
        o = self.banco.painel_ocorrencias(30)
        self.assertIn(("Outra", 1, 1), o["por_categoria"])


class TestFuncionarios(BasePainel):
    def setUp(self):
        super().setUp()
        # três funcionários (Carla e Bruno com setor), uma visitante
        self.entrar(CARLA, "Carla Nogueira", "19/10/2026 07:00")
        self.entrar(CARLA, "Carla Nogueira", "18/10/2026 08:00",
                    saida="18/10/2026 12:00")
        self.entrar(CARLA, "Carla Nogueira", "18/10/2026 13:00",
                    saida="18/10/2026 17:00")
        self.entrar(BRUNO, "Bruno Almeida", "19/10/2026 08:00",
                    saida="19/10/2026 09:00")
        self.entrar(DAVI, "Davi Prado", "10/10/2026 08:00",
                    saida="10/10/2026 09:00")
        self.entrar(EVA, "Eva Martins", "19/10/2026 09:00", tipo="Visitante",
                    motivo="Reunião", anfitriao="Secretaria")
        for cpf, mat, setor in ((CARLA, "F-1", "Manutenção"),
                                (BRUNO, "F-2", "manutenção")):
            pessoa = self.banco.buscar_pessoa(cpf)
            self.banco.salvar_funcionario(pessoa["id"], mat, setor, "", "ana")

    def test_numeros(self):
        f = self.banco.painel_funcionarios(7)
        self.assertEqual((f["cadastrados"], f["sem_matricula"]), (3, 1))
        self.assertEqual((f["dentro"], f["vieram_hoje"]), (1, 2))
        self.assertEqual(f["ha_mais_tempo"],
                         {"nome": "Carla Nogueira", "ha": timedelta(hours=3)})
        self.assertEqual(f["saidas_periodo"], 3)
        self.assertEqual(f["permanencia_media"], timedelta(minutes=180))
        # duas visitas da Carla no mesmo dia contam uma presença
        self.assertEqual(f["por_dia"][-2:], [(date(2026, 10, 18), 1),
                                             (date(2026, 10, 19), 2)])
        self.assertEqual(self.banco.painel_funcionarios(30)["saidas_periodo"],
                         4)

    def test_por_setor(self):
        f = self.banco.painel_funcionarios(7)
        setor, n, dentro = f["por_setor"][0]
        self.assertEqual((setor.lower(), n, dentro), ("manutenção", 2, 1))
        self.assertEqual(f["por_setor"][1], ("Sem setor", 1, 0))

    def test_anonimizado_sai_dos_cadastrados(self):
        davi = self.banco.buscar_pessoa(DAVI)
        self.banco.anonimizar_pessoa(davi["id"], "Pedido do titular", "ana")
        f = self.banco.painel_funcionarios(30)
        self.assertEqual(f["cadastrados"], 2)
        self.assertNotIn(("Sem setor", 1, 0), f["por_setor"])


class TestNadaDeCpf(BasePainel):
    def test_nenhuma_consulta_devolve_cpf(self):
        self.entrar(CARLA, "Carla Nogueira", "19/10/2026 08:00",
                    placa="BRA2E19")
        lab = nova_chave(self.caminho, "Laboratório 2")
        emprestimo(self.caminho, lab, "Bruno Almeida", "19/10/2026 08:00",
                   cpf=BRUNO)
        encomenda(self.caminho, "Davi Prado", "19/10/2026 08:00",
                  "19/10/2026 09:00", "Davi Prado", cpf=DAVI)
        gravar(self.caminho, "INSERT INTO ocorrencias (momento, categoria, "
               "texto, cpf, autor) VALUES ('2026-10-19 09:00', 'Segurança', "
               "'Pessoa sem crachá.', ?, 'paulo')", EVA)
        for consulta in CONSULTAS:
            texto = repr(getattr(self.banco, consulta)(30))
            for cpf in (CARLA, BRUNO, DAVI, EVA):
                self.assertNotIn(cpf, texto, consulta)


# ----------------------------------------------------------------------
# A tela
# ----------------------------------------------------------------------
class BaseTelaPainel(BaseInterface):
    def setUp(self):
        super().setUp()
        self.app.ir_para(self.app.aba_dash)
        self.painel = self.app.tela_dashboard

    def demonstracao(self):
        self.app.banco.preencher_demonstracao("ana.admin")
        self.painel.atualizar()

    def textos(self, widget):
        """Todo o texto de `widget` (rótulos e o que os Canvas desenham)."""
        achados = []
        for filho in widget.winfo_children():
            if isinstance(filho, tk.Label):
                achados.append(str(filho.cget("text")))
            elif isinstance(filho, tk.Canvas):
                achados += [str(filho.itemcget(i, "text"))
                            for i in filho.find_all()
                            if filho.type(i) == "text"]
            achados += self.textos(filho)
        return achados


class TestSecoesNaTela(BaseTelaPainel):
    def test_seletor_comeca_na_visao_geral_e_monta_as_outras_ao_abrir(self):
        p = self.painel
        self.assertEqual(tuple(p.seletor.itens), SECOES)
        self.assertEqual(p.secao, VISAO_GERAL)
        self.assertEqual(p.paginas, {})
        visiveis = [n for n, f in p.secoes.items() if f.winfo_manager()]
        self.assertEqual(visiveis, [VISAO_GERAL])
        for nome in SECOES[1:]:
            p.seletor.selecionar(nome)
            self.assertIsInstance(p.paginas[nome], SECOES_DO_PAINEL[nome])
            visiveis = [n for n, f in p.secoes.items() if f.winfo_manager()]
            self.assertEqual(visiveis, [nome])
            self.assertEqual(p.lbl_subtitulo.cget("text"),
                             p.paginas[nome].SUBTITULO)
        pagina = p.paginas["Chaves"]
        p.seletor.selecionar("Chaves")
        self.assertIs(p.paginas["Chaves"], pagina)        # não remonta

    def test_so_a_secao_na_tela_e_relida(self):
        p, banco = self.painel, self.app.banco
        espioes = {nome: mock.patch.object(banco, nome, wraps=getattr(banco, nome))
                   for nome in CONSULTAS + ("resumo_painel",)}
        chamadas = {nome: e.start() for nome, e in espioes.items()}
        for e in espioes.values():
            self.addCleanup(e.stop)
        p.seletor.selecionar("Veículos")
        self.assertEqual(chamadas["painel_veiculos"].call_count, 1)
        self.app.atualizar_tabela()                 # um registro mudou
        self.app.ir_para(self.app.aba_dash)         # voltou à página
        self.assertEqual(chamadas["painel_veiculos"].call_count, 3)
        self.assertEqual(chamadas["resumo_painel"].call_count, 0)
        for nome in CONSULTAS[1:]:
            self.assertEqual(chamadas[nome].call_count, 0, nome)
        p.seletor.selecionar(VISAO_GERAL)
        self.assertEqual(chamadas["resumo_painel"].call_count, 1)
        self.assertEqual(chamadas["painel_veiculos"].call_count, 3)

    def test_periodo_e_visao(self):
        self.demonstracao()
        p, banco = self.painel, self.app.banco
        p.seletor.selecionar("Veículos")
        pagina = p.paginas["Veículos"]
        self.assertEqual(len(pagina.colunas), 7)
        self.assertEqual(pagina.lbl_ranking.cget("text"), "entradas em 7 dias")
        with mock.patch.object(banco, "painel_veiculos",
                               wraps=banco.painel_veiculos) as consulta:
            pagina.seletor_visao.selecionar("Por hora")
            consulta.assert_not_called()          # só a visão: não relê
            self.assertEqual(len(pagina.colunas), 24)
            self.assertEqual(pagina.nome_destaque, f"{pagina.destaque:02d}h")
            pagina.seletor_periodo.selecionar("30 dias")
            consulta.assert_called_once_with(30)
        self.assertEqual(pagina.lbl_ranking.cget("text"), "entradas em 30 dias")
        pagina.seletor_visao.selecionar("Por dia")
        self.assertEqual(len(pagina.colunas), 30)
        self.assertEqual(pagina.nome_destaque, "Hoje")
        self.assertIn("30 dias", pagina.cards["autorizado"][1].cget("text"))

    def test_cada_secao_com_a_demonstracao(self):
        """A tela mostra o que o banco calcula (os números da demonstração
        vêm da própria consulta: a demonstração pode crescer)."""
        self.demonstracao()
        self.janela.deiconify()
        self.janela.geometry("1280x800")
        banco, p = self.app.banco, self.painel
        v, e = banco.painel_veiculos(7), banco.painel_entregas(7)
        c, o = banco.painel_chaves(7), banco.painel_ocorrencias(7)
        f = banco.painel_funcionarios(7)
        esperado = {
            "Veículos": {"agora": v["no_estacionamento"],
                         "hoje": v["entradas_hoje"]},
            "Entregas": {"aguardando": e["aguardando"],
                         "recebidas": e["recebidas_hoje"]},
            "Chaves": {"emprestadas": c["emprestadas"]},
            "Ocorrências": {"abertas": o["abertas"], "hoje": o["hoje"],
                            "periodo": o["no_periodo"]},
            "Funcionários": {"dentro": f["dentro"],
                             "cadastrados": f["cadastrados"]},
        }
        for nome in SECOES[1:]:
            with self.subTest(secao=nome):
                p.seletor.selecionar(nome)
                self.janela.update()
                pagina = p.paginas[nome]
                for chave, valor in esperado[nome].items():
                    self.assertGreater(valor, 0, chave)
                    self.assertEqual(pagina.cards[chave][0].cget("text"),
                                     str(valor))
                for chave, (valor, apoio) in pagina.cards.items():
                    self.assertTrue(valor.cget("text"), chave)
                    self.assertTrue(apoio.cget("text"), chave)
                self.assertTrue(pagina.ranking)
                self.assertTrue(pagina.cv_ranking.find_all())
                self.assertTrue(pagina.cv_colunas.find_all())
        nome, n, fora = c["mais_usadas"][0]
        self.assertEqual(p.paginas["Chaves"].ranking[0],
                         (nome, n, "emprestada" if fora else ""))
        self.assertEqual(p.paginas["Chaves"].cards["emprestadas"][1]
                         .cget("text"), f"de {c['cadastradas']} chaves")
        self.assertEqual(p.paginas["Ocorrências"].ranking[0][:2],
                         o["por_categoria"][0][:2])

    def test_graficos_vazios_avisam(self):
        self.janela.deiconify()
        self.janela.geometry("1280x800")
        p = self.painel
        for nome in SECOES[1:]:
            with self.subTest(secao=nome):
                p.seletor.selecionar(nome)
                self.janela.update()
                pagina = p.paginas[nome]
                textos = self.textos(pagina.cv_colunas.master)
                self.assertIn(pagina.AVISO, textos)
                if nome != "Ocorrências":       # (as categorias aparecem)
                    self.assertIn(pagina.AVISO_RANKING or pagina.AVISO,
                                  self.textos(pagina.cv_ranking.master))

    def test_vagas_e_alertas_mudam_a_cor(self):
        self.demonstracao()
        carros = self.app.banco.painel_veiculos(7)["no_estacionamento"]
        self.assertGreater(carros, 0)
        self.app.banco.salvar_lotacao(carros, False, autor="ana.admin")
        p = self.painel
        p.seletor.selecionar("Veículos")
        valor, apoio = p.paginas["Veículos"].cards["agora"]
        self.assertEqual(apoio.cget("text"), f"de {carros} vagas  ·  lotado")
        self.assertEqual(str(valor.cget("fg")).upper(), estilo.COR["erro"].upper())
        p.seletor.selecionar("Ocorrências")
        valor, _ = p.paginas["Ocorrências"].cards["abertas"]
        self.assertEqual(str(valor.cget("fg")).upper(),
                         estilo.COR["alerta"].upper())
        for o in self.app.banco.listar_ocorrencias(so_abertas=True):
            self.app.banco.resolver_ocorrencia(o["id"], "ana.admin")
        p.atualizar()
        self.assertEqual(valor.cget("text"), "0")
        self.assertEqual(str(valor.cget("fg")).upper(),
                         estilo.COR["sucesso"].upper())

    def test_erro_do_banco_avisa_e_nao_quebra(self):
        p = self.painel
        p.seletor.selecionar("Chaves")
        with mock.patch.object(self.app.banco, "painel_chaves",
                               side_effect=dados.ErroDados("Banco ocupado.")):
            p.atualizar()
        self.msg.showerror.assert_called()
        self.assertEqual(p.paginas["Chaves"].cards["emprestadas"][0]
                         .cget("text"), "0")

    def test_sem_cpf_na_tela_do_administrador(self):
        self.demonstracao()
        for nome in SECOES:
            self.painel.seletor.selecionar(nome)
        self.janela.deiconify()
        self.janela.update()
        for texto in self.textos(self.app.aba_dash):
            self.assertIsNone(CPF_NA_TELA.search(texto), texto)


class TestVisaoGeralIgual(BaseTelaPainel):
    def test_numeros_graficos_e_botoes_de_antes(self):
        p = self.painel
        self.assertEqual(list(p.cards), [c for c, _ in NUMEROS])
        self.assertIs(self.app.cards, p.cards)
        self.assertIn("Exportar CSV", self.botoes(self.app.aba_dash))
        self.assertIn("Relatório", self.botoes(self.app.aba_dash))
        self.assertEqual(len(p.dados["tipos"]), len(TIPOS_ACESSO))
        self.assertEqual(len(p.dados["dias"]), 7)
        self.assertEqual(p.seletor_periodo.ativa, "7 dias")
        self.assertEqual(p.seletor_visao.ativa, "Por dia")

    def test_volta_a_visao_geral_com_os_numeros_novos(self):
        p = self.painel
        p.seletor.selecionar("Entregas")
        self.app.banco.inserir({"nome": "Ana Silva", "cpf": CARLA,
                                "celular": "31987654321", "placa": "",
                                "tipo": "Aluno",
                                "entrada": "21/10/2026 09:00", "saida": ""})
        self.app.atualizar_tabela()
        self.assertEqual(self.app.cards["dentro"][0].cget("text"), "0")
        p.seletor.selecionar(VISAO_GERAL)
        self.assertEqual(self.app.cards["dentro"][0].cget("text"), "1")
        self.assertIn("1 registro desde o início", p.lbl_subtitulo.cget("text"))

    def test_faixa_do_administrador_fica_acima_das_secoes(self):
        p = self.painel
        self.assertTrue(p.faixa_admin.winfo_manager())
        filhos = p.aba.pack_slaves()
        self.assertLess(filhos.index(p.faixa_admin), filhos.index(p.seletor))
        p.seletor.selecionar("Funcionários")
        self.assertTrue(p.faixa_admin.winfo_manager())


class TestSecoesDoPorteiro(BaseTelaPainel):
    entrar_como = "porteiro"

    def test_porteiro_ve_as_secoes_sem_cpf_e_sem_exportar(self):
        self.app.banco.preencher_demonstracao("ana.admin")
        p = self.painel
        self.assertIsNone(p.btn_exportar)
        for nome in SECOES:
            with self.subTest(secao=nome):
                p.seletor.selecionar(nome)
                self.assertFalse(p.faixa_admin.winfo_manager())
        self.janela.deiconify()
        self.janela.update()
        for texto in self.textos(self.app.aba_dash):
            self.assertIsNone(CPF_NA_TELA.search(texto), texto)
        dentro = self.app.banco.painel_funcionarios(7)["dentro"]
        self.assertEqual(p.paginas["Funcionários"].cards["dentro"][0]
                         .cget("text"), str(dentro))


class TestSecoesNoEscuro(BaseTema):
    def test_todas_as_secoes_no_escuro_sem_fundo_claro(self):
        self.app.trocar_tema("escuro")
        self.app.banco.preencher_demonstracao("ana.admin")
        self.app.ir_para(self.app.aba_dash)
        for nome in SECOES:
            with self.subTest(secao=nome):
                self.app.tela_dashboard.seletor.selecionar(nome)
                self.app.janela.update_idletasks()
                self.assert_sem_fundo_claro(self.app.aba_dash)
                for cv in self.canvases(self.app.aba_dash):
                    self.assertLess(estilo.luminancia(cv.cget("bg")), 0.3)

    def canvases(self, widget):
        for filho in widget.winfo_children():
            if isinstance(filho, tk.Canvas):
                yield filho
            yield from self.canvases(filho)


class TestSecoesNaTelaPequena(BaseTelaPainel):
    """O notebook 1366x768 a 125% (nos testes a escala é 1: 1093x536)."""

    def setUp(self):
        super().setUp()
        self.demonstracao()
        self.janela.deiconify()
        self.janela.geometry("1093x536")

    def dentro_do_canvas(self, cv):
        w, h = cv.winfo_width(), cv.winfo_height()
        for item in cv.find_all():
            x0, y0, x1, y1 = cv.bbox(item)
            self.assertGreaterEqual(x0, -1, cv.itemcget(item, "text")
                                    if cv.type(item) == "text" else item)
            self.assertLessEqual(x1, w + 1)
            self.assertGreaterEqual(y0, -1)
            self.assertLessEqual(y1, h + 1)

    def test_numeros_e_graficos_cabem(self):
        p = self.painel
        for nome in SECOES[1:]:
            with self.subTest(secao=nome):
                p.seletor.selecionar(nome)
                self.janela.update()
                pagina = p.paginas[nome]
                for valor, apoio in pagina.cards.values():
                    largura = valor.master.winfo_width()
                    for rotulo in valor.master.winfo_children():
                        texto = rotulo.cget("text")
                        medida = int(rotulo.tk.call(
                            "font", "measure", rotulo.cget("font"), texto))
                        self.assertLessEqual(medida, largura, texto)
                self.dentro_do_canvas(pagina.cv_ranking)
                self.assertGreater(pagina.cv_colunas.winfo_height(), 40)
                # nem a página passa da janela
                self.assertLessEqual(
                    pagina.cv_colunas.winfo_rooty()
                    + pagina.cv_colunas.winfo_height(),
                    self.janela.winfo_rooty() + self.janela.winfo_height())

    def test_nome_comprido_e_cortado(self):
        nome = "Coordenação do Curso de Engenharia de Produção"
        for _ in range(5):                  # o primeiro do ranking
            encomenda(self.caminho_db, nome, "21/10/2026 09:00")
        p = self.painel
        p.seletor.selecionar("Entregas")
        self.janela.update()
        cv = p.paginas["Entregas"].cv_ranking
        textos = [cv.itemcget(i, "text") for i in cv.find_all()
                  if cv.type(i) == "text"]
        cortado = next(t for t in textos if t.startswith("Coordenação"))
        self.assertTrue(cortado.endswith("…"))
        self.dentro_do_canvas(cv)


class TestDesenhos(BaseInterface):
    def canvas(self, largura, altura):
        """Canvas numa janela só dele, do tamanho pedido."""
        janela = tk.Toplevel(self.raiz)
        self.addCleanup(janela.destroy)
        cv = tk.Canvas(janela, width=largura, height=altura,
                       highlightthickness=0)
        cv.pack()
        janela.update()
        return cv

    def test_duracao_de_relance(self):
        self.assertEqual(duracao(None), "—")
        self.assertEqual(duracao(timedelta(minutes=45)), "45min")
        self.assertEqual(duracao(timedelta(hours=3, minutes=10)), "3h 10min")
        self.assertEqual(duracao(timedelta(days=2, hours=4, minutes=59)),
                         "2d 4h")

    def test_cortar_texto(self):
        cv = self.canvas(10, 10)
        fonte = estilo.FONTE["grafico"]
        self.assertEqual(graficos.cortar_texto(cv, "Auditório", fonte, 500),
                         "Auditório")
        cortado = graficos.cortar_texto(cv, "Coordenação de Engenharia",
                                        fonte, 60)
        self.assertTrue(cortado.endswith("…"))
        self.assertLessEqual(int(cv.tk.call("font", "measure", fonte,
                                            cortado)), 60)
        self.assertEqual(graficos.cortar_texto(cv, "Auditório", fonte, 1), "")

    def test_ranking_nas_duas_alturas(self):
        itens = [("Coordenação de Engenharia", 4, "2 aguardando"),
                 ("Rafael Lima", 1, ""), ("Sem nada", 0, "")]
        for altura in (300, 60):
            with self.subTest(altura=altura):
                cv = self.canvas(320, altura)
                graficos.desenhar_ranking(cv, itens, "vazio")
                textos = [cv.itemcget(i, "text") for i in cv.find_all()
                          if cv.type(i) == "text"]
                self.assertIn("2 aguardando", textos)
                self.assertNotIn("vazio", textos)
                for item in cv.find_all():
                    x0, y0, x1, y1 = cv.bbox(item)
                    self.assertGreaterEqual(x0, -1)
                    self.assertLessEqual(x1, 321)
                    self.assertLessEqual(y1, altura + 1)

    def test_sem_dados_mostra_o_aviso(self):
        cv = self.canvas(300, 100)
        for desenhar in (graficos.desenhar_ranking, graficos.desenhar_colunas):
            for itens in ([], [("A", 0, "")]):
                desenhar(cv, [i[:2] for i in itens]
                         if desenhar is graficos.desenhar_colunas else itens,
                         aviso="Nenhuma chave")
                textos = [cv.itemcget(i, "text") for i in cv.find_all()]
                self.assertEqual(textos, ["Nenhuma chave"])


if __name__ == "__main__":
    unittest.main()
