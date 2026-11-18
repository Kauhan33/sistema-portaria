"""
Versão 3.6: encomenda e chave ligadas às pessoas do cadastro.

1) Encomendas: o destinatário é uma pessoa do cadastro (pelo CPF ou pelo
   nome de uma pessoa só); a retirada é de quem está na unidade e é o
   destinatário ou alguém da lista dele de quem pode retirar as encomendas
   (como "Quem pode retirar o carro", RN35).
2) Chaves: entregue e transferida a pessoas do cadastro que estão na
   unidade; quem está com chave não sai (devolver ou transferir antes).
3) As mensagens novas do CPF (faltam números / não existe / não é de uma
   pessoa cadastrada).
4) Uma autorização de entrada em vigor por CPF.
5) As sugestões de pessoas (autocompletar) nos campos de CPF e de nome.
6) Banco v17 (migração do v16 sem perder nada).
7) Dados de demonstração e anonimização (LGPD) das encomendas e chaves.

Banco (sem a tela, inclusive chamadas diretas) e tela (janela oculta).
"""

import os
import sqlite3
import tempfile
import tkinter as tk
import unittest
from datetime import date, datetime, timedelta
from unittest import mock

from portaria import dados, dados_modulos, tela_chave_saida, validacao, veiculos
from portaria.dados_modulos import (ANONIMO, AUTORIZADO_ENCOMENDA_ADICIONADO,
                                    AUTORIZADO_ENCOMENDA_REMOVIDO,
                                    AUTORIZADO_ENCOMENDA_VALIDADE,
                                    PESSOA_PRECISA_ESTAR, cpf_ficticio)
from portaria.senhas import gerar_hash
from portaria.sugestoes import (DESATIVADA, NA_UNIDADE, Sugestoes,
                                ligar_sugestoes, pessoa_pelo_nome)
from portaria.tela_chave_saida import DEVOLVER, JanelaChaveNaSaida, TRANSFERIR
from portaria.tela_livros import (DialogoEncomenda, DialogoQuemRetira,
                                  cpf_escolhido)
from portaria.tela_pessoas import (DialogoAutorizado, DialogoValidade,
                                   PESSOA_FORA, SECOES_FICHA)
from portaria.validacao import (CPF_INCOMPLETO, CPF_INEXISTENTE,
                                CPF_NAO_CADASTRADO, MAXIMO_NOME, mascarar_cpf,
                                mensagem_cpf)

from .test_aleatorio import Maquina
from .test_dados import registro, versao_do_arquivo
from .test_interface import BaseInterface, agora_menos
from .test_linguagem import BaseBanco as BaseBancoLinguagem
from .test_regras_no_banco import BaseRegras

HELENA, BRUNO, DAVI, EVA = ("52998224725", "11144477735", "39053344705",
                            "86288366757")
HOJE = date(2026, 10, 19)          # BaseRegras: segunda-feira, 10:00
NINGUEM_SE_CHAMA = ("Ninguém do cadastro se chama \"{}\".\nO destinatário "
                    "precisa ser uma pessoa cadastrada: digite pelo menos 3 "
                    "letras do nome ou do CPF e escolha nas sugestões.")
NAO_ESTA = ("{} não está na unidade.\nSó quem está dentro pode {}: registre "
            "a entrada antes.")
COM_A_CHAVE = ("{} está com a chave \"{}\".\nRegistre a devolução ou "
               "transfira a chave para outra pessoa antes da saída.")


# ======================================================================
# Banco
# ======================================================================
class BaseLivros(BaseRegras):
    """Helena e Bruno estão na unidade; Davi é do cadastro, mas saiu ontem;
    Eva não é do cadastro."""

    def setUp(self):
        super().setUp()
        self.helena = self.entrar(HELENA, "Helena Souza")
        self.bruno = self.entrar(BRUNO, "Bruno Almeida")
        self.banco.inserir(registro(cpf=DAVI, nome="Davi Prado",
                                    entrada="18/10/2026 08:00",
                                    saida="18/10/2026 09:00"), autor="paulo")

    def entrar(self, cpf, nome, entrada="19/10/2026 08:00"):
        return self.banco.inserir(registro(cpf=cpf, nome=nome,
                                           entrada=entrada), autor="paulo")

    def sair(self, *ids, saida="19/10/2026 09:30"):
        return self.banco.registrar_saidas(list(ids), saida, autor="paulo")

    def erro(self, funcao, *args, **kwargs):
        with self.assertRaises(dados.ErroDados) as e:
            funcao(*args, **kwargs)
        return str(e.exception)

    def ultimo(self):
        return self.banco.listar_eventos()[0]

    def depois(self, minutos=1):
        """O relógio anda (operações em minutos diferentes)."""
        self.AGORA = self.AGORA + timedelta(minutes=minutos)


# ----------------------------------------------------------------------
# 1) Encomenda só para quem é do cadastro
# ----------------------------------------------------------------------
class TestDestinatarioDoCadastro(BaseLivros):
    def nova(self, destinatario="Helena Souza", **extra):
        return self.banco.registrar_encomenda(destinatario, "Correios",
                                              "paulo", **extra)

    def test_pelo_cpf_grava_o_nome_e_o_cpf_do_cadastro(self):
        id_ = self.nova("Lena", cpf_destinatario=HELENA)
        e, = self.banco.listar_encomendas()
        self.assertEqual((e["id"], e["destinatario"], e["destinatario_cpf"]),
                         (id_, "Helena Souza", HELENA))
        self.assertEqual((self.ultimo()["acao"], self.ultimo()["detalhe"]),
                         ("Encomenda recebida",
                          f"#{id_} para Helena Souza, de Correios"))

    def test_cpf_com_pontuacao_vale(self):
        self.nova("Helena", cpf_destinatario="529.982.247-25")
        self.assertEqual(self.banco.listar_encomendas()[0]["destinatario_cpf"],
                         HELENA)

    def test_cpf_errado_ou_de_ninguem_e_recusado_com_a_mensagem_certa(self):
        for cpf, msg in (("5299822", CPF_INCOMPLETO),
                         ("12345678900", CPF_INEXISTENTE),
                         ("11111111111", CPF_INEXISTENTE),
                         (EVA, CPF_NAO_CADASTRADO)):
            with self.subTest(cpf=cpf):
                self.assertEqual(self.erro(self.nova, cpf_destinatario=cpf),
                                 msg)
        self.assertEqual(self.banco.listar_encomendas(), [])

    def test_nome_inteiro_sem_diferenca_de_acento_e_maiuscula(self):
        self.entrar(cpf_ficticio(123456789), "Otávio Mendes")
        for texto, nome in (("Helena Souza", "Helena Souza"),
                            ("HELENA SOUZA", "Helena Souza"),
                            ("  helena    souza ", "Helena Souza"),
                            ("otavio mendes", "Otávio Mendes"),
                            ("OTÁVIO MENDES", "Otávio Mendes")):
            with self.subTest(texto=texto):
                id_ = self.nova(texto)
                e = next(x for x in self.banco.listar_encomendas()
                         if x["id"] == id_)
                self.assertEqual(e["destinatario"], nome)

    def test_so_o_primeiro_nome_basta_se_for_unico(self):
        for texto in ("Helena", "helena", "HÉLENA"):
            with self.subTest(texto=texto):
                id_ = self.nova(texto)
                e = next(x for x in self.banco.listar_encomendas()
                         if x["id"] == id_)
                self.assertEqual((e["destinatario"], e["destinatario_cpf"]),
                                 ("Helena Souza", HELENA))

    def test_primeiro_nome_de_varias_pessoas_pede_o_nome_completo(self):
        self.entrar(cpf_ficticio(123456789), "Bruno Costa")
        self.assertEqual(self.erro(self.nova, "Bruno"),
                         "Há 2 pessoas com o nome \"Bruno\".\nDigite o nome "
                         "completo ou escolha nas sugestões.")
        # o nome completo desempata
        self.nova("Bruno Costa")
        self.assertEqual(self.banco.listar_encomendas()[0]["destinatario"],
                         "Bruno Costa")

    def test_mesmo_nome_completo_em_duas_pessoas(self):
        self.entrar(cpf_ficticio(123456789), "Helena Souza")
        self.assertEqual(self.erro(self.nova, "Helena Souza"),
                         "Há 2 pessoas com o nome \"Helena Souza\".\nDigite o "
                         "nome completo ou escolha nas sugestões.")
        # pelo CPF (escolhido nas sugestões) vai certo
        self.nova("Helena Souza", cpf_destinatario=cpf_ficticio(123456789))
        self.assertEqual(self.banco.listar_encomendas()[0]["destinatario_cpf"],
                         cpf_ficticio(123456789))

    def test_quem_nao_e_do_cadastro_e_recusado(self):
        for texto in ("Setor de Compras", "Souza", "Hel", "Helena Sousa",
                      "Eva Martins"):
            with self.subTest(texto=texto):
                self.assertEqual(self.erro(self.nova, texto),
                                 NINGUEM_SE_CHAMA.format(texto))
        self.assertEqual(self.banco.listar_encomendas(), [])
        self.assertNotIn("Encomenda recebida",
                         [e["acao"] for e in self.banco.listar_eventos()])

    def test_texto_so_com_numeros_e_tratado_como_cpf(self):
        for texto, esperado in (("52998224725", None),
                                ("529.982.247-25", None),
                                ("529 982 247 25", None),
                                ("529.982", CPF_INCOMPLETO),
                                ("123.456.789-00", CPF_INEXISTENTE),
                                ("862.883.667-57", CPF_NAO_CADASTRADO)):
            with self.subTest(texto=texto):
                if esperado:
                    self.assertEqual(self.erro(self.nova, texto), esperado)
                else:
                    id_ = self.nova(texto)
                    e = next(x for x in self.banco.listar_encomendas()
                             if x["id"] == id_)
                    self.assertEqual(e["destinatario"], "Helena Souza")

    def test_pessoa_de_fora_tambem_recebe_encomenda(self):
        """O destinatário é do cadastro; não precisa estar na unidade."""
        self.nova("Davi Prado")
        self.assertEqual(self.banco.listar_encomendas()[0]["destinatario_cpf"],
                         DAVI)

    def test_anonimizada_nao_e_destinataria(self):
        self.banco.anonimizar_pessoa(self.banco.buscar_pessoa(DAVI)["id"],
                                     "Pedido do titular", "ana")
        self.assertEqual(self.erro(self.nova, "Davi Prado"),
                         NINGUEM_SE_CHAMA.format("Davi Prado"))
        self.assertEqual(self.erro(self.nova, ANONIMO),
                         NINGUEM_SE_CHAMA.format(ANONIMO))
        self.assertEqual(self.erro(self.nova, cpf_destinatario=DAVI),
                         CPF_NAO_CADASTRADO)

    def test_sem_usuario_ativo_nada_e_gravado(self):
        for autor in (None, "ninguem"):
            with self.subTest(autor=autor):
                self.erro(self.banco.registrar_encomenda, "Helena Souza",
                          "Correios", autor)
        self.assertEqual(self.banco.listar_encomendas(), [])


# ----------------------------------------------------------------------
# 1) Retirada: na unidade, pelo destinatário ou por um autorizado
# ----------------------------------------------------------------------
class TestRetiradaDaEncomenda(BaseLivros):
    def setUp(self):
        super().setUp()
        self.encomenda = self.banco.registrar_encomenda("Helena Souza", "Correios",
                                                 "paulo")

    def pendente(self):
        return self.banco.listar_encomendas()[0]["retirada_em"] == ""

    def autorizar(self, cpf=BRUNO, nome="Bruno Almeida", valido_ate=None):
        return self.banco.adicionar_autorizado_encomenda(
            HELENA, cpf, nome, valido_ate, "ana")

    def test_destinatario_na_unidade_retira(self):
        self.assertEqual(self.banco.retirar_encomenda(self.encomenda, HELENA, "paulo"),
                         "Helena Souza")
        e, = self.banco.listar_encomendas()
        self.assertEqual((e["retirada_nome"], e["retirada_cpf"],
                          e["entregue_por"], e["retirada_em"]),
                         ("Helena Souza", HELENA, "paulo", "19/10/2026 10:00"))
        self.assertEqual((self.ultimo()["acao"], self.ultimo()["detalhe"]),
                         ("Encomenda retirada", f"#{self.encomenda} por Helena Souza"))

    def test_destinatario_fora_da_unidade_nao_retira(self):
        self.sair(self.helena)
        self.assertEqual(self.erro(self.banco.retirar_encomenda, self.encomenda,
                                   HELENA, "paulo"),
                         NAO_ESTA.format("Helena Souza", "retirar a encomenda"))
        self.assertTrue(self.pendente())

    def test_outra_pessoa_sem_autorizacao_nao_retira(self):
        self.assertEqual(
            self.erro(self.banco.retirar_encomenda, self.encomenda, BRUNO, "paulo"),
            "Bruno Almeida não pode retirar a encomenda de Helena Souza.\nSó "
            "Helena ou quem está na lista dele(a) de quem pode retirar as "
            "encomendas (Pessoas, na ficha).")
        self.assertTrue(self.pendente())

    def test_autorizado_na_unidade_retira_e_o_historico_diz(self):
        self.autorizar()
        self.assertEqual(self.banco.retirar_encomenda(self.encomenda, BRUNO, "paulo"),
                         "Bruno Almeida")
        e, = self.banco.listar_encomendas()
        self.assertEqual((e["retirada_nome"], e["retirada_cpf"]),
                         ("Bruno Almeida", BRUNO))
        self.assertEqual(self.ultimo()["detalhe"],
                         f"#{self.encomenda} por Bruno Almeida, autorizado por "
                         "Helena Souza")

    def test_autorizado_fora_da_unidade_nao_retira(self):
        self.autorizar(DAVI, "Davi Prado")
        self.assertEqual(self.erro(self.banco.retirar_encomenda, self.encomenda,
                                   DAVI, "paulo"),
                         NAO_ESTA.format("Davi Prado", "retirar a encomenda"))
        self.assertTrue(self.pendente())

    def test_validade_vale_ate_o_ultimo_dia_inclusive(self):
        self.autorizar(valido_ate=HOJE)
        self.AGORA = datetime(2026, 10, 19, 23, 59)        # o último minuto
        self.banco.retirar_encomenda(self.encomenda, BRUNO, "paulo")
        self.assertFalse(self.pendente())

    def test_autorizado_vencido_nao_vale(self):
        self.autorizar(valido_ate=HOJE)
        self.AGORA = datetime(2026, 10, 20, 0, 1)          # venceu ontem
        self.assertIn("não pode retirar a encomenda",
                      self.erro(self.banco.retirar_encomenda, self.encomenda, BRUNO,
                                "paulo"))
        self.assertTrue(self.pendente())

    def test_autorizado_removido_nao_vale(self):
        self.banco.remover_autorizado_encomenda(self.autorizar(), "paulo")
        self.assertIn("não pode retirar a encomenda",
                      self.erro(self.banco.retirar_encomenda, self.encomenda, BRUNO,
                                "paulo"))

    def test_autorizado_de_outra_pessoa_nao_vale(self):
        """Bruno pode retirar as do Davi, não as da Helena."""
        self.banco.adicionar_autorizado_encomenda(DAVI, BRUNO, "Bruno Almeida",
                                                  None, "ana")
        self.assertIn("não pode retirar a encomenda de Helena Souza",
                      self.erro(self.banco.retirar_encomenda, self.encomenda, BRUNO,
                                "paulo"))

    def test_cpf_obrigatorio_valido_e_do_cadastro(self):
        for cpf, msg in (("", CPF_INCOMPLETO), ("529982", CPF_INCOMPLETO),
                         ("12345678900", CPF_INEXISTENTE),
                         (EVA, CPF_NAO_CADASTRADO)):
            with self.subTest(cpf=cpf):
                self.assertEqual(self.erro(self.banco.retirar_encomenda,
                                           self.encomenda, cpf, "paulo"), msg)
        self.assertTrue(self.pendente())

    def test_nome_gravado_e_o_do_cadastro(self):
        """O cadastro foi corrigido: a retirada grava o nome de agora."""
        pessoa = self.banco.buscar_pessoa(HELENA)
        self.banco.atualizar_pessoa(pessoa["id"], "Helena Souza Lima",
                                    pessoa["celular"], "", pessoa["tipo"],
                                    autor="ana")
        self.assertEqual(self.banco.retirar_encomenda(self.encomenda, HELENA, "paulo"),
                         "Helena Souza Lima")
        self.assertEqual(self.banco.listar_encomendas()[0]["retirada_nome"],
                         "Helena Souza Lima")

    def test_nao_retira_duas_vezes_nem_a_que_nao_existe(self):
        self.banco.retirar_encomenda(self.encomenda, HELENA, "paulo")
        for id_ in (self.encomenda, 999):
            with self.subTest(id_=id_):
                self.assertEqual(self.erro(self.banco.retirar_encomenda, id_,
                                           HELENA, "ana"),
                                 "Esta encomenda já foi retirada ou não "
                                 "existe mais.")
        self.assertEqual(self.banco.listar_encomendas()[0]["entregue_por"],
                         "paulo")

    def test_sem_usuario_ativo_nao_retira(self):
        for autor in (None, "ninguem"):
            with self.subTest(autor=autor):
                self.erro(self.banco.retirar_encomenda, self.encomenda, HELENA, autor)
        self.assertTrue(self.pendente())

    def inserir_antiga(self, destinatario):
        """Encomenda gravada antes da 3.6 (sem o CPF do destinatário)."""
        con = sqlite3.connect(self.caminho)
        cursor = con.execute(
            "INSERT INTO encomendas (recebida_em, destinatario, setor, "
            "remetente, descricao, recebida_por) VALUES ('2026-10-18 10:00', "
            "?, '', 'Correios', '', 'paulo')", (destinatario,))
        con.commit()
        con.close()
        return cursor.lastrowid

    def test_encomenda_antiga_vale_pelo_primeiro_nome(self):
        antiga = self.inserir_antiga("HÉLENA Reis")
        e = next(x for x in self.banco.listar_encomendas() if x["id"] == antiga)
        self.assertEqual(e["destinatario_cpf"], "")
        self.assertEqual(self.banco.retirar_encomenda(antiga, HELENA, "paulo"),
                         "Helena Souza")
        e = next(x for x in self.banco.listar_encomendas() if x["id"] == antiga)
        self.assertEqual((e["retirada_nome"], e["retirada_cpf"]),
                         ("Helena Souza", HELENA))

    def test_encomenda_antiga_outro_primeiro_nome_nao_retira(self):
        antiga = self.inserir_antiga("Helena Reis")
        self.assertEqual(
            self.erro(self.banco.retirar_encomenda, antiga, BRUNO, "paulo"),
            "Bruno Almeida não pode retirar a encomenda de Helena Reis.\nEsta "
            "encomenda é de antes da 3.6: só quem tem o mesmo primeiro nome "
            "do destinatário a retira.")
        self.sair(self.helena)                     # e precisa estar dentro
        self.assertIn("não está na unidade",
                      self.erro(self.banco.retirar_encomenda, antiga, HELENA,
                                "paulo"))


# ----------------------------------------------------------------------
# 1) Quem pode retirar as encomendas (como RN35)
# ----------------------------------------------------------------------
class TestAutorizadosDeEncomenda(BaseLivros):
    def adicionar(self, dono=HELENA, cpf=BRUNO, nome="Bruno Almeida",
                  valido_ate=None, autor="paulo"):
        return self.banco.adicionar_autorizado_encomenda(dono, cpf, nome,
                                                         valido_ate, autor)

    def test_porteiro_adiciona_com_a_pessoa_na_unidade(self):
        id_ = self.adicionar()
        a, = self.banco.listar_autorizados_encomenda(HELENA)
        self.assertEqual((a["id"], a["dono_cpf"], a["cpf"], a["nome"],
                          a["valido_ate"], a["dono_presente"], a["criado_por"],
                          a["ativo"]),
                         (id_, HELENA, BRUNO, "Bruno Almeida", None, True,
                          "paulo", True))
        ev = self.ultimo()
        self.assertEqual((ev["acao"], ev["detalhe"]),
                         (AUTORIZADO_ENCOMENDA_ADICIONADO,
                          f"Encomendas de Helena Souza: Bruno Almeida (CPF "
                          f"{mascarar_cpf(BRUNO)}) pode retirar, "
                          f"{veiculos.descrever_validade(None)}."))
        self.assertNotIn(BRUNO, ev["detalhe"])                 # LGPD

    def test_porteiro_com_a_pessoa_fora_nao_adiciona(self):
        self.assertEqual(self.erro(self.adicionar, dono=DAVI, cpf=BRUNO),
                         PESSOA_PRECISA_ESTAR)
        self.assertEqual(self.banco.listar_autorizados_encomenda(DAVI), [])

    def test_administrador_adiciona_a_qualquer_hora(self):
        self.adicionar(dono=DAVI, autor="ana")
        a, = self.banco.listar_autorizados_encomenda(DAVI)
        self.assertFalse(a["dono_presente"])

    def test_nao_pode_o_proprio_dono(self):
        self.assertEqual(self.erro(self.adicionar, cpf=HELENA,
                                   nome="Helena Souza"),
                         "A própria pessoa já retira as encomendas dela.")

    def test_validade_hoje_vale_e_ontem_nao(self):
        self.assertEqual(self.erro(self.adicionar,
                                   valido_ate=HOJE - timedelta(days=1)),
                         "A validade não pode ser antes de hoje.")
        self.adicionar(valido_ate=HOJE)
        self.assertEqual(self.banco.listar_autorizados_encomenda(HELENA)[0]
                         ["valido_ate"], HOJE)

    def test_nao_duplica_quem_esta_ativo(self):
        self.adicionar()
        self.assertEqual(self.erro(self.adicionar),
                         "Bruno Almeida já está na lista de quem pode retirar "
                         "as encomendas de Helena Souza.")
        # removido, pode voltar
        self.banco.remover_autorizado_encomenda(
            self.banco.listar_autorizados_encomenda(HELENA)[0]["id"], "paulo")
        self.adicionar()
        self.assertEqual(len(self.banco.listar_autorizados_encomenda(
            HELENA, incluir_removidos=True)), 2)

    def test_cpf_invalido_usa_as_mensagens_novas(self):
        for cpf, msg in (("", CPF_INCOMPLETO), ("1114447773", CPF_INCOMPLETO),
                         ("11144477700", CPF_INEXISTENTE),
                         ("11111111111", CPF_INEXISTENTE)):
            with self.subTest(cpf=cpf):
                self.assertEqual(self.erro(self.adicionar, cpf=cpf), msg)

    def test_nome_completo_e_tamanho(self):
        for nome, trecho in (("Bruno", "nome completo"),
                             ("Bruno 123", "nome completo"),
                             ("", "nome completo"),
                             ("Bruno " + "a" * MAXIMO_NOME, "no máximo")):
            with self.subTest(nome=nome):
                self.assertIn(trecho, self.erro(self.adicionar, nome=nome))
        self.assertEqual(self.banco.listar_autorizados_encomenda(HELENA), [])

    def test_dono_precisa_estar_cadastrado(self):
        self.assertEqual(self.erro(self.adicionar, dono=EVA, autor="ana"),
                         "A pessoa da ficha não está cadastrada.")

    def test_remover_e_logico_e_vai_ao_historico(self):
        id_ = self.adicionar()
        self.depois()
        self.banco.remover_autorizado_encomenda(id_, "paulo")
        self.assertEqual(self.banco.listar_autorizados_encomenda(HELENA), [])
        a, = self.banco.listar_autorizados_encomenda(HELENA,
                                                     incluir_removidos=True)
        self.assertEqual((a["ativo"], a["removido_por"], a["removido_em"]),
                         (False, "paulo", "19/10/2026 10:01"))
        self.assertEqual(self.ultimo()["acao"], AUTORIZADO_ENCOMENDA_REMOVIDO)
        self.assertEqual(self.erro(self.banco.remover_autorizado_encomenda,
                                   id_, "paulo"),
                         "Esta autorização já tinha sido removida.")

    def test_porteiro_remove_mesmo_com_a_pessoa_fora(self):
        id_ = self.adicionar()
        self.sair(self.helena)
        self.banco.remover_autorizado_encomenda(id_, "paulo")
        self.assertEqual(self.banco.listar_autorizados_encomenda(HELENA), [])

    def test_alterar_validade(self):
        id_ = self.adicionar()
        self.banco.alterar_validade_autorizado_encomenda(
            id_, date(2026, 12, 31), "paulo")
        self.assertEqual(self.banco.listar_autorizados_encomenda(HELENA)[0]
                         ["valido_ate"], date(2026, 12, 31))
        self.assertEqual((self.ultimo()["acao"], self.ultimo()["detalhe"]),
                         (AUTORIZADO_ENCOMENDA_VALIDADE,
                          f"Bruno Almeida: {veiculos.descrever_validade(None)}"
                          " → até 31/12/2026."))
        self.banco.alterar_validade_autorizado_encomenda(id_, None, "paulo")
        self.assertIsNone(self.banco.listar_autorizados_encomenda(HELENA)[0]
                          ["valido_ate"])
        self.assertEqual(self.erro(
            self.banco.alterar_validade_autorizado_encomenda, id_,
            HOJE - timedelta(days=1), "ana"),
            "A validade não pode ser antes de hoje.")

    def test_alterar_validade_porteiro_so_com_a_pessoa_na_unidade(self):
        id_ = self.adicionar()
        self.sair(self.helena)
        self.assertEqual(self.erro(
            self.banco.alterar_validade_autorizado_encomenda, id_, HOJE,
            "paulo"), PESSOA_PRECISA_ESTAR)
        self.banco.alterar_validade_autorizado_encomenda(id_, HOJE, "ana")
        self.assertEqual(self.banco.listar_autorizados_encomenda(HELENA)[0]
                         ["valido_ate"], HOJE)

    def test_alterar_validade_de_removido_e_recusado(self):
        id_ = self.adicionar()
        self.banco.remover_autorizado_encomenda(id_, "paulo")
        self.assertEqual(self.erro(
            self.banco.alterar_validade_autorizado_encomenda, id_, None,
            "ana"), "Esta autorização já tinha sido removida.")

    def test_sem_usuario_ativo_nada_muda(self):
        for autor in (None, "ninguem"):
            with self.subTest(autor=autor):
                self.erro(self.adicionar, autor=autor)
        self.assertEqual(self.banco.listar_autorizados_encomenda(HELENA), [])

    def test_autorizado_fora_do_cadastro_entra_na_lista_mas_nao_retira(self):
        """A lista aceita qualquer CPF válido (como a do carro); quem retira
        precisa ser do cadastro e estar na unidade."""
        self.adicionar(cpf=EVA, nome="Eva Martins")
        id_ = self.banco.registrar_encomenda("Helena", "Correios", "paulo")
        self.assertEqual(self.erro(self.banco.retirar_encomenda, id_, EVA,
                                   "paulo"), CPF_NAO_CADASTRADO)

    def test_lista_ativos_primeiro_e_mais_recentes_primeiro(self):
        a = self.adicionar()
        b = self.adicionar(cpf=DAVI, nome="Davi Prado")
        self.banco.remover_autorizado_encomenda(a, "paulo")
        c = self.adicionar(cpf=EVA, nome="Eva Martins")
        self.assertEqual([x["id"] for x in self.banco.listar_autorizados_encomenda(
            HELENA, incluir_removidos=True)], [c, b, a])

    def test_excluir_a_pessoa_desativa_a_lista_dela(self):
        cpf = cpf_ficticio(123456789)
        id_pessoa = self.banco.cadastrar_pessoa(cpf, "Gil Ramos",
                                                "31987654321", "",
                                                "Visitante", "ana")
        self.adicionar(dono=cpf, autor="ana")
        self.banco.excluir_pessoa(id_pessoa, "ana")
        a, = self.banco.listar_autorizados_encomenda(cpf,
                                                     incluir_removidos=True)
        self.assertEqual((a["ativo"], a["removido_por"]), (False, "ana"))

    def test_banco_recusa_o_proprio_dono_e_o_repetido_mesmo_sem_a_checagem(self):
        """Duas estações (ou um programa de fora): a tabela tem as travas."""
        self.adicionar()
        con = sqlite3.connect(self.caminho)
        for cpf in (HELENA, BRUNO):
            with self.subTest(cpf=cpf), \
                    self.assertRaises(sqlite3.IntegrityError):
                con.execute("INSERT INTO autorizados_encomenda (dono_cpf, cpf, "
                            "nome, criado_por, criado_em) VALUES (?, ?, "
                            "'X Y', 'ana', '2026-10-19 10:00')", (HELENA, cpf))
        con.close()


# ----------------------------------------------------------------------
# 2) Chave ligada à pessoa; transferência; a chave na saída
# ----------------------------------------------------------------------
class BaseChaves(BaseLivros):
    def setUp(self):
        super().setUp()
        self.lab = self.banco.cadastrar_chave("Laboratório 2", "Bloco B", "ana")
        self.aud = self.banco.cadastrar_chave("Auditório", "Bloco A", "ana")

    def com_quem(self, id_chave):
        c = next(c for c in self.banco.listar_chaves() if c["id"] == id_chave)
        return c["com_quem"] if c["emprestada"] else None


class TestEntregarChave(BaseChaves):
    def test_entrega_com_o_nome_do_cadastro(self):
        self.assertEqual(self.banco.entregar_chave(self.lab, "529.982.247-25",
                                                   "paulo"), "Helena Souza")
        c = self.banco.listar_chaves()[0]
        self.assertEqual((c["com_quem"], c["cpf"], c["entregue_por"]),
                         ("Helena Souza", HELENA, "paulo"))
        self.assertEqual((self.ultimo()["acao"], self.ultimo()["detalhe"]),
                         ("Chave entregue", "Laboratório 2 para Helena Souza"))

    def test_so_quem_esta_na_unidade(self):
        self.assertEqual(self.erro(self.banco.entregar_chave, self.lab, DAVI,
                                   "paulo"),
                         NAO_ESTA.format("Davi Prado", "receber a chave"))
        self.assertIsNone(self.com_quem(self.lab))

    def test_cpf_obrigatorio_valido_e_do_cadastro(self):
        for cpf, msg in (("", CPF_INCOMPLETO), (None, CPF_INCOMPLETO),
                         ("12345678900", CPF_INEXISTENTE),
                         (EVA, CPF_NAO_CADASTRADO)):
            with self.subTest(cpf=cpf):
                self.assertEqual(self.erro(self.banco.entregar_chave, self.lab,
                                           cpf, "paulo"), msg)
        self.assertIsNone(self.com_quem(self.lab))

    def test_anonimizada_nao_recebe(self):
        self.banco.anonimizar_pessoa(self.banco.buscar_pessoa(DAVI)["id"],
                                     "Pedido do titular", "ana")
        self.assertEqual(self.erro(self.banco.entregar_chave, self.lab, DAVI,
                                   "paulo"), CPF_NAO_CADASTRADO)

    def test_chaves_da_pessoa(self):
        self.banco.entregar_chave(self.lab, HELENA, "paulo")
        self.banco.entregar_chave(self.aud, HELENA, "paulo")
        self.assertEqual([c["nome"] for c in self.banco.chaves_da_pessoa(HELENA)],
                         ["Auditório", "Laboratório 2"])      # por nome
        self.assertEqual(self.banco.chaves_da_pessoa("529.982.247-25")[0]
                         ["desde"], "19/10/2026 10:00")
        self.assertEqual(self.banco.chaves_da_pessoa(BRUNO), [])
        self.assertEqual(self.banco.chaves_da_pessoa(""), [])
        self.assertEqual(self.banco.chaves_da_pessoa(None), [])
        self.banco.devolver_chave(self.lab, "paulo")
        self.assertEqual([c["nome"] for c in self.banco.chaves_da_pessoa(HELENA)],
                         ["Auditório"])


class TestTransferirChave(BaseChaves):
    def setUp(self):
        super().setUp()
        self.banco.entregar_chave(self.lab, HELENA, "paulo")
        self.depois(5)

    def test_transfere_para_outra_pessoa_na_unidade(self):
        self.assertEqual(self.banco.transferir_chave(self.lab, BRUNO, "ana"),
                         "Bruno Almeida")
        self.assertEqual(self.com_quem(self.lab), "Bruno Almeida")
        self.assertEqual(self.banco.chaves_da_pessoa(HELENA), [])
        self.assertEqual([c["nome"] for c in self.banco.chaves_da_pessoa(BRUNO)],
                         ["Laboratório 2"])
        novo, antigo = self.banco.historico_de_chaves()
        self.assertEqual((novo["nome"], novo["retirada_em"], novo["entregue_por"],
                          novo["devolvida_em"], novo["transferida_para"]),
                         ("Bruno Almeida", "19/10/2026 10:05", "ana", "", ""))
        self.assertEqual((antigo["nome"], antigo["devolvida_em"],
                          antigo["recebida_por"], antigo["transferida_para"]),
                         ("Helena Souza", "19/10/2026 10:05", "ana",
                          "Bruno Almeida"))
        self.assertEqual((self.ultimo()["acao"], self.ultimo()["detalhe"]),
                         ("Chave transferida",
                          "Laboratório 2: de Helena Souza para Bruno Almeida"))

    def test_devolucao_comum_nao_tem_transferida_para(self):
        self.banco.devolver_chave(self.lab, "paulo")
        self.assertEqual(self.banco.historico_de_chaves()[0]
                         ["transferida_para"], "")

    def test_nao_transfere_para_quem_ja_esta_com_ela(self):
        self.assertEqual(self.erro(self.banco.transferir_chave, self.lab,
                                   HELENA, "paulo"),
                         "A chave \"Laboratório 2\" já está com Helena Souza.")
        self.assertEqual(len(self.banco.historico_de_chaves()), 1)

    def test_quem_recebe_precisa_estar_na_unidade_e_no_cadastro(self):
        for cpf, msg in ((DAVI, NAO_ESTA.format("Davi Prado",
                                                "receber a chave")),
                         (EVA, CPF_NAO_CADASTRADO),
                         ("", CPF_INCOMPLETO),
                         ("12345678900", CPF_INEXISTENTE)):
            with self.subTest(cpf=cpf):
                self.assertEqual(self.erro(self.banco.transferir_chave,
                                           self.lab, cpf, "paulo"), msg)
        self.assertEqual(self.com_quem(self.lab), "Helena Souza")
        self.assertEqual(len(self.banco.historico_de_chaves()), 1)

    def test_so_chave_emprestada(self):
        msg = "Esta chave não está emprestada (foi devolvida ou removida)."
        for id_chave in (self.aud, 999):
            with self.subTest(id_chave=id_chave):
                self.assertEqual(self.erro(self.banco.transferir_chave,
                                           id_chave, BRUNO, "paulo"), msg)
        self.banco.devolver_chave(self.lab, "paulo")
        self.assertEqual(self.erro(self.banco.transferir_chave, self.lab,
                                   BRUNO, "paulo"), msg)

    def test_sem_usuario_ativo_nao_transfere(self):
        for autor in (None, "ninguem"):
            with self.subTest(autor=autor):
                self.erro(self.banco.transferir_chave, self.lab, BRUNO, autor)
        self.assertEqual(self.com_quem(self.lab), "Helena Souza")

    def test_transferir_de_novo_encadeia_o_historico(self):
        carla = cpf_ficticio(390533447)
        self.entrar(carla, "Carla Nogueira")
        self.banco.transferir_chave(self.lab, BRUNO, "paulo")
        self.depois(5)
        self.banco.transferir_chave(self.lab, carla, "paulo")
        self.assertEqual([(h["nome"], h["transferida_para"])
                          for h in self.banco.historico_de_chaves()],
                         [("Carla Nogueira", ""),
                          ("Bruno Almeida", "Carla Nogueira"),
                          ("Helena Souza", "Bruno Almeida")])

    def test_o_banco_trava_duas_pessoas_com_a_mesma_chave(self):
        con = sqlite3.connect(self.caminho)
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("INSERT INTO emprestimos_chave (chave_id, nome, cpf, "
                        "retirada_em, entregue_por) VALUES (?, 'Bruno Almeida',"
                        " ?, '2026-10-19 10:06', 'paulo')", (self.lab, BRUNO))
        con.close()


class TestChaveNaSaidaNoBanco(BaseChaves):
    def setUp(self):
        super().setUp()
        self.banco.entregar_chave(self.lab, HELENA, "paulo")

    def aberta(self, id_):
        return self.banco.buscar(id_)["saida"] == ""

    def test_saida_de_quem_esta_com_chave_e_recusada(self):
        self.assertEqual(self.erro(self.sair, self.helena),
                         COM_A_CHAVE.format("Helena Souza", "Laboratório 2"))
        self.assertTrue(self.aberta(self.helena))

    def test_com_duas_chaves_a_mensagem_lista_as_duas(self):
        self.banco.entregar_chave(self.aud, HELENA, "paulo")
        self.assertEqual(self.erro(self.sair, self.helena),
                         "Helena Souza está com as chaves \"Auditório\", "
                         "\"Laboratório 2\".\nRegistre a devolução ou "
                         "transfira a chave para outra pessoa antes da saída.")

    def test_saida_de_varias_e_uma_transacao(self):
        """Bruno e Helena saem juntos; Helena tem a chave: nenhuma grava."""
        self.erro(self.sair, self.bruno, self.helena)
        self.assertTrue(self.aberta(self.bruno))
        self.assertTrue(self.aberta(self.helena))
        self.assertNotIn("Saída", [e["acao"] for e in
                                   self.banco.listar_eventos()][:1])

    def test_depois_de_devolver_sai(self):
        self.banco.devolver_chave(self.lab, "paulo")
        self.sair(self.helena)
        self.assertFalse(self.aberta(self.helena))

    def test_depois_de_transferir_sai_e_quem_recebeu_nao(self):
        self.banco.transferir_chave(self.lab, BRUNO, "paulo")
        self.sair(self.helena)
        self.assertFalse(self.aberta(self.helena))
        self.assertEqual(self.erro(self.sair, self.bruno),
                         COM_A_CHAVE.format("Bruno Almeida", "Laboratório 2"))

    def test_correcao_nao_fecha_a_visita_de_quem_tem_chave(self):
        original = self.banco.buscar(self.helena)
        msg = self.erro(self.banco.editar, self.helena,
                        dict(original, saida="19/10/2026 09:50"), ["saida"],
                        "ana", original=original)
        self.assertEqual(msg, COM_A_CHAVE.format("Helena Souza",
                                                 "Laboratório 2"))
        self.assertTrue(self.aberta(self.helena))

    def test_correcao_nao_troca_o_cpf_da_visita_de_quem_tem_chave(self):
        original = self.banco.buscar(self.helena)
        self.assertIn("está com a chave", self.erro(
            self.banco.editar, self.helena,
            dict(original, cpf=EVA, nome="Eva Martins"), ["cpf", "nome"],
            "ana", original=original))
        self.assertEqual(self.banco.buscar(self.helena)["cpf"], HELENA)

    def test_correcao_de_outro_campo_continua_valendo(self):
        original = self.banco.buscar(self.helena)
        self.banco.editar(self.helena, dict(original, celular="31911112222"),
                          ["celular"], "ana", original=original)
        self.assertEqual(self.banco.buscar(self.helena)["celular"],
                         "31911112222")

    def test_excluir_a_visita_aberta_de_quem_tem_chave_e_recusado(self):
        self.assertIn("está com a chave",
                      self.erro(self.banco.excluir, [self.helena], "ana"))
        self.assertTrue(self.aberta(self.helena))
        self.banco.devolver_chave(self.lab, "paulo")
        self.banco.excluir([self.helena], "ana")
        self.assertIsNone(self.banco.buscar(self.helena))

    def test_encerrar_o_dia_nao_deixa_a_chave_com_quem_saiu(self):
        """Corrigido (achado do QA): "Encerrar o dia" (encerrar_pendentes)
        fechava a visita de quem estava com a chave. Agora pula essa visita
        (continua pendente até a devolução ou a transferência) e encerra as
        outras."""
        encerradas = self.banco.encerrar_pendentes(
            datetime(2026, 10, 20, 10, 0), "ana")
        self.assertTrue(self.aberta(self.helena))
        self.assertEqual(self.banco.chaves_da_pessoa(HELENA)[0]["nome"],
                         "Laboratório 2")
        self.assertEqual([e[0] for e in encerradas], [self.bruno])
        self.assertFalse(self.aberta(self.bruno))

    def test_encerrar_o_dia_depois_de_devolver_encerra(self):
        self.banco.devolver_chave(self.lab, "paulo")
        encerradas = self.banco.encerrar_pendentes(
            datetime(2026, 10, 20, 10, 0), "ana")
        self.assertEqual(sorted(e[0] for e in encerradas),
                         sorted([self.helena, self.bruno]))



class TestChaveComQuemEstaDentroAleatorio(unittest.TestCase):
    """Sequências aleatórias (como test_aleatorio, com o "Encerrar o dia"):
    ninguém fora da unidade fica com chave e o nome de quem está com ela é
    sempre de uma pessoa do cadastro."""

    def test_invariante_da_chave(self):
        class SemEncerrar(Maquina):
            OPERACOES = dict(Maquina.OPERACOES)
            OPERACOES.update(chave_entregar=8, chave_transferir=6,
                             chave_nova=2)

            def _dentro(self):
                """Quase sempre alguém que está na unidade."""
                abertas = [r["cpf"] for r in self.banco.listar_abertas()]
                if abertas and self.r.random() < 0.8:
                    return self.r.choice(abertas)
                return self._cpf_qualquer()

            def op_chave_entregar(self):
                self.banco.entregar_chave(self._chave(), self._dentro(),
                                          self.autor())

            def op_chave_transferir(self):
                emprestadas = self.sql("SELECT chave_id FROM "
                                       "emprestimos_chave WHERE "
                                       "devolvida_em = ''")
                chave = (self.r.choice(emprestadas)[0] if emprestadas
                         else self._chave())
                self.banco.transferir_chave(chave, self._dentro(),
                                            self.autor())

        feitas = {}
        for semente in (11, 12, 13):
            with self.subTest(semente=semente), \
                    tempfile.TemporaryDirectory() as pasta:
                m = SemEncerrar(semente, pasta)
                for i in range(300):
                    nome = m.passo()
                    fora = m.sql(
                        "SELECT e.cpf FROM emprestimos_chave e WHERE "
                        "e.devolvida_em = '' AND NOT EXISTS (SELECT 1 FROM "
                        "registros r WHERE r.cpf = e.cpf AND r.saida = '')")
                    self.assertEqual(fora, [], f"passo {i} ({nome})")
                    m.conferir(self, f"semente {semente}, passo {i} ({nome})")
                for op in ("chave_entregar", "chave_transferir"):
                    feitas[op] = feitas.get(op, 0) + m.feitas.get(op, 0)
                del m
        # a sequência exercitou de fato a entrega e a transferência
        self.assertGreater(feitas["chave_entregar"], 0)
        self.assertGreater(feitas["chave_transferir"], 0)


# ----------------------------------------------------------------------
# 3) As mensagens do CPF
# ----------------------------------------------------------------------
class TestMensagensDeCpf(unittest.TestCase):
    def test_mensagem_cpf(self):
        for cpf, msg in (("", CPF_INCOMPLETO), (None, CPF_INCOMPLETO),
                         ("5", CPF_INCOMPLETO),
                         ("5299822472", CPF_INCOMPLETO),         # 10
                         ("529982247251", CPF_INCOMPLETO),       # 12
                         ("5299822472a", CPF_INCOMPLETO),
                         ("529.982.247", CPF_INCOMPLETO),
                         ("52998224726", CPF_INEXISTENTE),       # dígito errado
                         ("12345678900", CPF_INEXISTENTE),
                         ("00000000000", CPF_INEXISTENTE),
                         ("52998224725", ""), (BRUNO, "")):
            with self.subTest(cpf=cpf):
                self.assertEqual(mensagem_cpf(cpf), msg)

    def test_textos_exatos(self):
        self.assertEqual(CPF_INCOMPLETO, "CPF inválido.\nDigite os 11 números "
                                         "(somente números).")
        self.assertEqual(CPF_INEXISTENTE, "CPF inválido.\nDigite um CPF "
                                          "existente.")
        self.assertEqual(CPF_NAO_CADASTRADO, "CPF inválido.\nDigite um CPF "
                                             "existente (de uma pessoa "
                                             "cadastrada).")

    def test_validar_quem_retira_cpf_e_nome_obrigatorios(self):
        v = validacao.validar_quem_retira
        self.assertEqual(v("Helena Souza", HELENA), (True, ""))
        for nome, cpf, msg in (
                ("Helena Souza", "", "O CPF é obrigatório."),
                ("", "", "O CPF é obrigatório."),
                ("Helena Souza", "529", CPF_INCOMPLETO),
                ("Helena Souza", "12345678900", CPF_INEXISTENTE),
                ("", HELENA, "Informe o nome de quem está retirando."),
                ("Helena", HELENA, "Informe o nome completo (nome e "
                                   "sobrenome, só letras).")):
            with self.subTest(nome=nome, cpf=cpf):
                self.assertEqual(v(nome, cpf), (False, msg))

    def test_os_formularios_usam_a_mensagem_certa(self):
        base = {"nome": "Helena Souza", "cpf": "", "celular": "31987654321",
                "placa": "", "tipo": "Visitante", "empresa": "",
                "motivo": "Reunião", "entrada": "19/10/2026 08:00",
                "saida": ""}
        for cpf, msg in (("5299822472", CPF_INCOMPLETO),
                         ("52998224726", CPF_INEXISTENTE)):
            with self.subTest(cpf=cpf):
                self.assertEqual(validacao.validar_campos(dict(base, cpf=cpf)),
                                 (False, msg))
                self.assertEqual(validacao.validar_ocorrencia(
                    validacao.CATEGORIAS_OCORRENCIA[0], "Texto da ocorrência", cpf, "")[1], msg)
                self.assertEqual(validacao.validar_desativacao(
                    "cpf", cpf, "Motivo qualquer", [])[1], msg)
                self.assertEqual(veiculos.conferir_autorizado(
                    "BRA2E19", BRUNO, cpf, "Davi Prado", None, HOJE)[1], msg)
                self.assertEqual(veiculos.conferir_autorizado_encomenda(
                    BRUNO, cpf, "Davi Prado", None, HOJE)[1], msg)

    def test_sem_acento_e_primeiro_nome(self):
        self.assertEqual(validacao.sem_acento("Ótávio ÇÃO"), "otavio cao")
        self.assertEqual(validacao.sem_acento(None), "")
        self.assertEqual(validacao.primeiro_nome("  Hélena  Souza"), "helena")
        self.assertEqual(validacao.primeiro_nome(""), "")


class TestCpfDaOcorrenciaNoBanco(BaseLivros):
    def test_cpf_da_ocorrencia_e_de_uma_pessoa_cadastrada(self):
        """O aluno decidiu: na ocorrência, "CPF existente" = cadastrado."""
        self.assertEqual(self.erro(self.banco.registrar_ocorrencia, validacao.CATEGORIAS_OCORRENCIA[0],
                                   "Pessoa sem crachá na portaria", "paulo",
                                   cpf=EVA), CPF_NAO_CADASTRADO)
        self.assertEqual(self.erro(self.banco.registrar_ocorrencia, validacao.CATEGORIAS_OCORRENCIA[0],
                                   "Pessoa sem crachá na portaria", "paulo",
                                   cpf="12345678900"), CPF_INEXISTENTE)
        self.banco.registrar_ocorrencia(validacao.CATEGORIAS_OCORRENCIA[0], "Pessoa sem crachá na "
                                        "portaria", "paulo", cpf=DAVI)
        self.banco.registrar_ocorrencia(validacao.CATEGORIAS_OCORRENCIA[0], "Sem CPF nenhum aqui",
                                        "paulo")
        self.assertEqual(len(self.banco.listar_ocorrencias()), 2)


class TestCpfNaLinguagem(BaseBancoLinguagem):
    def test_digitos_que_nao_conferem_pedem_um_cpf_existente(self):
        e = self.erro("entrada 12345678900 aluno")
        self.assertEqual(e.regra, "RN06")
        self.assertTrue(e.mensagem.endswith(
            "os dígitos verificadores não conferem: digite um CPF "
            "existente."), e.mensagem)


# ----------------------------------------------------------------------
# 4) Uma autorização de entrada em vigor por CPF
# ----------------------------------------------------------------------
class TestAutorizacaoUnicaPorCpf(BaseRegras):
    def criar(self, cpf=HELENA, nome="Ana Silva", de="19/10/2026",
              ate="21/10/2026"):
        return self.banco.criar_autorizacao(cpf, nome, "", "Reunião",
                                            "Diretoria", de, ate, "paulo")

    def recusa(self, **campos):
        with self.assertRaises(dados.ErroDados) as e:
            self.criar(**campos)
        return str(e.exception)

    def test_segunda_em_vigor_e_recusada_com_o_numero_da_primeira(self):
        id_ = self.criar()
        self.assertEqual(self.recusa(de="25/10/2026", ate="26/10/2026"),
                         f"Este CPF já tem a autorização nº {id_} (Ana Silva, "
                         "de 19/10/2026 a 21/10/2026).\nPara mudar o período, "
                         "cancele a anterior e crie outra.")
        self.assertEqual(len(self.banco.listar_autorizacoes()), 1)

    def test_a_futura_tambem_conta(self):
        self.criar(de="25/10/2026", ate="26/10/2026")
        self.assertIn("já tem a autorização", self.recusa())

    def test_vence_hoje_ainda_conta_e_amanha_nao(self):
        self.criar(de="19/10/2026", ate="19/10/2026")
        self.assertIn("já tem a autorização", self.recusa())
        self.AGORA = datetime(2026, 10, 20, 8, 0)
        self.criar(de="20/10/2026", ate="20/10/2026")
        self.assertEqual(len(self.banco.listar_autorizacoes()), 2)

    def test_cancelada_nao_conta(self):
        id_ = self.criar()
        self.banco.cancelar_autorizacao(id_, "paulo")
        self.criar(de="20/10/2026", ate="22/10/2026")
        self.assertEqual(len(self.banco.listar_autorizacoes()), 2)

    def test_outro_cpf_nao_conta(self):
        self.criar()
        self.criar(cpf=BRUNO, nome="Bruno Almeida")
        self.assertEqual(len(self.banco.listar_autorizacoes()), 2)


# ----------------------------------------------------------------------
# 5) Sugestões no banco
# ----------------------------------------------------------------------
class TestSugerirPessoas(BaseLivros):
    def setUp(self):
        super().setUp()
        self.ana_helena = cpf_ficticio(100000001)
        self.michele = cpf_ficticio(100000002)
        self.otavio = cpf_ficticio(100000003)
        for cpf, nome in ((self.ana_helena, "Ana Helena Dias"),
                          (self.michele, "Michele Rocha"),
                          (self.otavio, "Otávio Mendes")):
            self.banco.cadastrar_pessoa(cpf, nome, "31987654321", "",
                                        "Visitante", "ana")

    def nomes(self, texto, **extra):
        return [p["nome"] for p in self.banco.sugerir_pessoas(texto, **extra)]

    def test_menos_de_3_nao_sugere(self):
        for texto in ("", "  ", "H", "He", "52", "5", "  he  ", "5.2"):
            with self.subTest(texto=texto):
                self.assertEqual(self.banco.sugerir_pessoas(texto), [])
        self.assertEqual(self.nomes("Hel"), ["Helena Souza", "Ana Helena Dias",
                                             "Michele Rocha"])

    def test_ordem_comeca_depois_palavra_depois_o_resto(self):
        self.assertEqual(self.nomes("hel"), ["Helena Souza", "Ana Helena Dias",
                                             "Michele Rocha"])

    def test_refina_enquanto_digita(self):
        self.assertEqual(len(self.nomes("Hel")), 3)
        self.assertEqual(self.nomes("Hele"), ["Helena Souza",       # miCHELE
                                              "Ana Helena Dias",
                                              "Michele Rocha"])
        self.assertEqual(self.nomes("Helen"), ["Helena Souza",
                                               "Ana Helena Dias"])
        self.assertEqual(self.nomes("Helena S"), ["Helena Souza"])
        self.assertEqual(self.nomes("Helena Sx"), [])

    def test_sem_diferenca_de_acento_e_maiuscula(self):
        for texto in ("ota", "OTA", "Otá", "otávio m", "OTAVIO MENDES"):
            with self.subTest(texto=texto):
                self.assertEqual(self.nomes(texto), ["Otávio Mendes"])

    def test_pelo_comeco_do_cpf(self):
        self.assertEqual(self.nomes("529"), ["Helena Souza"])
        self.assertEqual(self.nomes("529.982"), ["Helena Souza"])
        self.assertEqual(self.nomes("529 982 247-25"), ["Helena Souza"])
        self.assertEqual(self.nomes("111"), ["Bruno Almeida"])
        self.assertEqual(self.nomes("998"), [])          # meio do CPF não
        self.assertEqual(self.nomes("5291"), [])

    def test_no_maximo_3_e_limite(self):
        for n in range(5):
            self.banco.cadastrar_pessoa(cpf_ficticio(200000000 + n),
                                        f"Silva {'abcde'[n]}lves", "31987654321",
                                        "", "Visitante", "ana")
        self.assertEqual(len(self.banco.sugerir_pessoas("silva")), 3)
        self.assertEqual(len(self.banco.sugerir_pessoas("silva", limite=10)), 5)
        self.assertEqual(validacao.MAXIMO_SUGESTOES, 3)
        self.assertEqual(validacao.MINIMO_SUGESTAO, 3)

    def test_quem_esta_dentro_vem_antes(self):
        maria = cpf_ficticio(300000001)
        self.banco.cadastrar_pessoa(cpf_ficticio(300000002), "Marcos Dias",
                                    "31987654321", "", "Visitante", "ana")
        self.entrar(maria, "Maria Lopes")
        self.assertEqual(self.nomes("mar"), ["Maria Lopes", "Marcos Dias"])

    def test_campos_de_cada_sugestao(self):
        p, = self.banco.sugerir_pessoas("Helena S")
        self.assertEqual(p, {"nome": "Helena Souza", "cpf": HELENA,
                             "tipo": "Funcionário", "dentro": True,
                             "desativada": False})
        self.banco.desativar("cpf", self.otavio, "Motivo de teste", "ana")
        p, = self.banco.sugerir_pessoas("Otávio")
        self.assertEqual((p["dentro"], p["desativada"]), (False, True))

    def test_so_dentro(self):
        self.assertEqual(self.nomes("hel", so_dentro=True), ["Helena Souza"])
        self.assertEqual(self.nomes("Davi", so_dentro=True), [])
        self.assertEqual(self.nomes("Davi"), ["Davi Prado"])

    def test_excluir(self):
        self.assertEqual(self.nomes("Helena", excluir=(HELENA,)),
                         ["Ana Helena Dias"])
        self.assertEqual(self.nomes("Helena", excluir=(HELENA, "", None)),
                         ["Ana Helena Dias"])
        self.assertEqual(self.nomes("529", excluir=[HELENA]), [])

    def test_sem_as_anonimizadas(self):
        self.banco.anonimizar_pessoa(self.banco.buscar_pessoa(DAVI)["id"],
                                     "Pedido do titular", "ana")
        self.assertEqual(self.nomes("Davi"), [])
        self.assertEqual(self.nomes("Pessoa anon"), [])
        self.assertEqual(self.nomes("390"), [])

    def test_texto_estranho_nao_quebra_nem_acha_tudo(self):
        for texto in ("'; DROP TABLE pessoas; --", "%%%", "___", "a%b",
                      "x" * 500, "\x00\x00\x00", "hel1"):
            with self.subTest(texto=texto[:20]):
                self.assertEqual(self.banco.sugerir_pessoas(texto), [])
        self.assertEqual(len(self.banco.listar_pessoas()), 6)


# ----------------------------------------------------------------------
# 6) Migração v16 -> v17
# ----------------------------------------------------------------------
class TestMigracaoV17(unittest.TestCase):
    """O banco da 3.5 (v16): encomendas sem o CPF do destinatário,
    empréstimos sem "transferida_para" e sem a lista de encomendas."""

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.caminho = os.path.join(self.pasta.name, "portaria.db")
        self.relogio = lambda: datetime(2026, 10, 19, 10)      # noqa: E731
        banco = dados.Banco(self.caminho, relogio=self.relogio)
        banco.criar_usuario("Ana Admin", "ana", "admin", gerar_hash("senha123"))
        banco.inserir(registro(cpf=HELENA, nome="Helena Souza",
                               entrada="19/10/2026 08:00"), autor="ana")
        banco.inserir(registro(cpf=BRUNO, nome="Bruno Almeida",
                               entrada="19/10/2026 08:00"), autor="ana")
        self.encomenda = banco.registrar_encomenda("Helena Souza", "Correios",
                                                   "ana", setor="Bloco B")
        self.lab = banco.cadastrar_chave("Laboratório 2", "", "ana")
        banco.entregar_chave(self.lab, HELENA, "ana")
        self.eventos = len(banco.listar_eventos())
        del banco
        con = sqlite3.connect(self.caminho)          # como a 3.5 deixava
        con.execute("DROP INDEX idx_encomendas_destinatario")
        con.execute("DROP INDEX idx_emprestimos_cpf")
        con.execute("ALTER TABLE encomendas DROP COLUMN destinatario_cpf")
        con.execute("ALTER TABLE emprestimos_chave DROP COLUMN "
                    "transferida_para")
        con.execute("DROP TABLE autorizados_encomenda")
        con.execute("PRAGMA user_version = 16")
        con.execute("UPDATE meta SET valor = '16' WHERE chave = "
                    "'versao_esquema'")
        con.commit()
        con.close()

    def colunas(self, tabela):
        con = sqlite3.connect(self.caminho)
        nomes = {c[1] for c in con.execute(f"PRAGMA table_info({tabela})")}
        con.close()
        return nomes

    def test_versao_17(self):
        self.assertEqual(dados.VERSAO_ESQUEMA, 17)
        self.assertIn((17, dados_modulos.passo_v17), dados.MIGRACOES)

    def test_banco_da_3_5_ganha_as_colunas_e_a_tabela(self):
        self.assertEqual(versao_do_arquivo(self.caminho), 16)
        self.assertNotIn("destinatario_cpf", self.colunas("encomendas"))
        banco = dados.Banco(self.caminho, relogio=self.relogio)
        self.assertEqual(versao_do_arquivo(self.caminho), 17)
        self.assertIn("destinatario_cpf", self.colunas("encomendas"))
        self.assertIn("transferida_para", self.colunas("emprestimos_chave"))
        self.assertLessEqual({"dono_cpf", "cpf", "nome", "valido_ate", "ativo"},
                             self.colunas("autorizados_encomenda"))
        # nada se perde
        e, = banco.listar_encomendas()
        self.assertEqual((e["id"], e["destinatario"], e["setor"],
                          e["destinatario_cpf"]),
                         (self.encomenda, "Helena Souza", "Bloco B", ""))
        h, = banco.historico_de_chaves()
        self.assertEqual((h["nome"], h["cpf"], h["transferida_para"]),
                         ("Helena Souza", HELENA, ""))
        self.assertEqual(len(banco.listar()), 2)
        self.assertGreaterEqual(len(banco.listar_eventos()), self.eventos)
        self.assertTrue(banco.verificar_historico()["integro"])
        self.assertEqual(banco.listar_autorizados_encomenda(HELENA), [])
        del banco

    def test_depois_da_migracao_tudo_funciona(self):
        banco = dados.Banco(self.caminho, relogio=self.relogio)
        # a encomenda antiga vale pelo primeiro nome
        self.assertIn("antes da 3.6", self._erro(
            banco.retirar_encomenda, self.encomenda, BRUNO, "ana"))
        banco.retirar_encomenda(self.encomenda, HELENA, "ana")
        # o empréstimo antigo pode ser transferido; a lista nova funciona
        banco.transferir_chave(self.lab, BRUNO, "ana")
        self.assertEqual(banco.historico_de_chaves()[1]["transferida_para"],
                         "Bruno Almeida")
        banco.adicionar_autorizado_encomenda(HELENA, BRUNO, "Bruno Almeida",
                                             None, "ana")
        id_ = banco.registrar_encomenda("Helena", "Kalunga", "ana")
        banco.retirar_encomenda(id_, BRUNO, "ana")
        self.assertTrue(banco.verificar_historico()["integro"])
        del banco

    def _erro(self, funcao, *args):
        with self.assertRaises(dados.ErroDados) as e:
            funcao(*args)
        return str(e.exception)

    def test_faz_o_backup_de_v16(self):
        banco = dados.Banco(self.caminho, relogio=self.relogio)
        del banco
        backups = os.listdir(os.path.join(self.pasta.name, "backups"))
        self.assertTrue(any("-de-v16-" in f for f in backups), backups)

    def test_migrar_duas_vezes_e_passo_idempotente(self):
        dados.Banco(self.caminho, relogio=self.relogio)
        banco = dados.Banco(self.caminho, relogio=self.relogio)
        banco.adicionar_autorizado_encomenda(HELENA, BRUNO, "Bruno Almeida",
                                             None, "ana")
        con = sqlite3.connect(self.caminho)
        dados_modulos.passo_v17(banco, con, 16)           # de novo: nada muda
        con.commit()
        con.close()
        self.assertEqual(len(banco.listar_autorizados_encomenda(HELENA)), 1)
        self.assertEqual(versao_do_arquivo(self.caminho), 17)
        del banco


# ----------------------------------------------------------------------
# 7) Demonstração e anonimização
# ----------------------------------------------------------------------
class TestDemonstracao(BaseRegras):
    def test_encomendas_de_pessoas_do_cadastro_e_a_chave_com_quem_esta_dentro(self):
        self.banco.preencher_demonstracao("ana")
        encomendas = self.banco.listar_encomendas()
        self.assertEqual(len(encomendas), 3)
        for e in encomendas:
            with self.subTest(destinatario=e["destinatario"]):
                pessoa = self.banco.buscar_pessoa(e["destinatario_cpf"])
                self.assertIsNotNone(pessoa)
                self.assertEqual(pessoa["nome"], e["destinatario"])
        lab = next(c for c in self.banco.listar_chaves()
                   if c["nome"] == "Laboratório 2")
        self.assertEqual((lab["com_quem"], lab["cpf"]),
                         ("Carla Nogueira", cpf_ficticio(390533447)))
        self.assertEqual(self.banco.buscar_pessoa(lab["cpf"])["nome"],
                         "Carla Nogueira")
        abertas = [r for r in self.banco.listar_abertas()
                   if r["cpf"] == lab["cpf"]]
        self.assertEqual(len(abertas), 1, "Carla precisa estar na unidade")
        # a regra da 3.6 vale também para os dados de demonstração
        with self.assertRaises(dados.ErroDados):
            self.banco.registrar_saidas([abertas[0]["id"]], "19/10/2026 10:00",
                                        autor="ana")

    def test_encomenda_da_demonstracao_e_retirada_pela_destinataria(self):
        self.banco.preencher_demonstracao("ana")
        dentro = {r["cpf"] for r in self.banco.listar_abertas()}
        e = next((e for e in self.banco.listar_encomendas()
                  if e["destinatario_cpf"] in dentro), None)
        if e is None:
            self.skipTest("nenhuma destinatária da demonstração está dentro")
        self.banco.retirar_encomenda(e["id"], e["destinatario_cpf"], "ana")


class TestAnonimizacaoDosLivros(BaseLivros):
    """Helena: destinatária, quem retirou, quem levou chave (devolvida e
    transferida), dona e autorizada de listas de encomendas. Depois de
    anonimizada, nada disso guarda o nome nem o CPF dela."""

    def setUp(self):
        super().setUp()
        b = self.banco
        lab = b.cadastrar_chave("Laboratório 2", "", "ana")
        aud = b.cadastrar_chave("Auditório", "", "ana")
        self.retirada = b.registrar_encomenda("Helena Souza", "Correios",
                                              "paulo")
        b.retirar_encomenda(self.retirada, HELENA, "paulo")
        self.pendente = b.registrar_encomenda("Helena", "Kalunga", "paulo")
        self.do_bruno = b.registrar_encomenda("Bruno Almeida", "Amazon",
                                              "paulo")
        b.adicionar_autorizado_encomenda(HELENA, BRUNO, "Bruno Almeida", None,
                                         "paulo")
        b.adicionar_autorizado_encomenda(BRUNO, HELENA, "Helena Souza", None,
                                         "paulo")
        b.retirar_encomenda(self.do_bruno, HELENA, "paulo")   # autorizada
        b.entregar_chave(lab, HELENA, "paulo")
        self.depois()
        b.transferir_chave(lab, BRUNO, "paulo")               # de Helena
        self.depois()
        b.entregar_chave(aud, BRUNO, "paulo")
        self.depois()
        b.transferir_chave(aud, HELENA, "paulo")              # para Helena
        self.depois()
        b.devolver_chave(aud, "paulo")
        self.depois()
        self.sair(self.helena, saida="19/10/2026 10:06")
        self.id_helena = b.buscar_pessoa(HELENA)["id"]

    def texto_das_tabelas(self):
        con = sqlite3.connect(self.caminho)
        try:
            partes = []
            for tabela in ("encomendas", "emprestimos_chave",
                           "autorizados_encomenda"):
                for linha in con.execute(f"SELECT * FROM {tabela}"):
                    partes.append(" | ".join(map(str, linha)))
            return "\n".join(partes)
        finally:
            con.close()

    def test_nada_guarda_o_nome_nem_o_cpf(self):
        self.assertIn("Helena Souza", self.texto_das_tabelas())
        self.banco.anonimizar_pessoa(self.id_helena, "Pedido da titular", "ana")
        texto = self.texto_das_tabelas()
        self.assertNotIn("Helena", texto)
        self.assertNotIn(HELENA, texto)

    def test_encomendas(self):
        self.banco.anonimizar_pessoa(self.id_helena, "Pedido da titular", "ana")
        por_id = {e["id"]: e for e in self.banco.listar_encomendas()}
        for id_ in (self.retirada, self.pendente):
            self.assertEqual(por_id[id_]["destinatario"], ANONIMO)
            self.assertTrue(por_id[id_]["destinatario_cpf"].startswith("X"))
        self.assertEqual(por_id[self.retirada]["retirada_nome"], ANONIMO)
        # a do Bruno continua dele; só quem retirou é anonimizado
        bruno = por_id[self.do_bruno]
        self.assertEqual((bruno["destinatario"], bruno["destinatario_cpf"],
                          bruno["retirada_nome"]),
                         ("Bruno Almeida", BRUNO, ANONIMO))

    def test_chaves(self):
        self.banco.anonimizar_pessoa(self.id_helena, "Pedido da titular", "ana")
        historico = [(h["chave"], h["nome"], h["transferida_para"])
                     for h in self.banco.historico_de_chaves()]
        self.assertEqual(sorted(historico), sorted([
            ("Auditório", ANONIMO, ""),
            ("Auditório", "Bruno Almeida", ANONIMO),
            ("Laboratório 2", "Bruno Almeida", ""),
            ("Laboratório 2", ANONIMO, "Bruno Almeida")]))

    def test_listas_de_quem_pode_retirar(self):
        self.banco.anonimizar_pessoa(self.id_helena, "Pedido da titular", "ana")
        do_bruno, = self.banco.listar_autorizados_encomenda(
            BRUNO, incluir_removidos=True)
        self.assertEqual((do_bruno["nome"], do_bruno["ativo"],
                          do_bruno["removido_por"]),
                         (ANONIMO, False, "(anonimização)"))
        self.assertTrue(do_bruno["cpf"].startswith("X"))
        self.assertEqual(self.banco.listar_autorizados_encomenda(
            HELENA, incluir_removidos=True), [])         # dono virou código
        con = sqlite3.connect(self.caminho)
        linhas = con.execute("SELECT nome, ativo, dono_cpf FROM "
                             "autorizados_encomenda WHERE cpf = ?",
                             (BRUNO,)).fetchall()
        con.close()
        self.assertEqual(len(linhas), 1)
        nome, ativo, dono = linhas[0]
        self.assertEqual((nome, ativo), ("Bruno Almeida", 0))
        self.assertTrue(dono.startswith("X"))

    def test_dados_dos_outros_nao_mudam(self):
        antes = self.banco.listar_chaves()
        self.banco.anonimizar_pessoa(self.id_helena, "Pedido da titular", "ana")
        self.assertEqual(self.banco.listar_chaves(), antes)
        self.assertEqual(self.banco.buscar_pessoa(BRUNO)["nome"],
                         "Bruno Almeida")

    def test_anonimizada_some_das_sugestoes_e_nao_recebe_mais(self):
        self.banco.anonimizar_pessoa(self.id_helena, "Pedido da titular", "ana")
        self.assertEqual(self.banco.sugerir_pessoas("Helena"), [])
        self.assertEqual(self.banco.sugerir_pessoas("529"), [])
        with self.assertRaises(dados.ErroDados):
            self.banco.registrar_encomenda("Helena Souza", "Correios", "paulo")

    def test_transferencias_no_mesmo_minuto_nao_apagam_o_nome_de_outro(self):
        """Corrigido (achado do QA): _anonimizar_livros achava "quem recebeu
        a chave transferida" pelo horário, que tem só minutos. A chave passa
        de Bruno para Davi e de Davi para Eva no mesmo minuto; anonimizar a
        Eva só muda o "transferida_para" do empréstimo do Davi (agora pelo
        id do empréstimo seguinte)."""
        b = self.banco
        sala = b.cadastrar_chave("Sala 3", "", "ana")
        eva = cpf_ficticio(123456789)
        self.entrar(DAVI, "Davi Prado", entrada="19/10/2026 10:00")
        self.entrar(eva, "Eva Martins", entrada="19/10/2026 10:00")
        b.entregar_chave(sala, BRUNO, "paulo")
        self.depois()
        b.transferir_chave(sala, DAVI, "paulo")            # mesmo minuto:
        b.transferir_chave(sala, eva, "paulo")             # Davi -> Eva
        self.depois()
        b.devolver_chave(sala, "paulo")
        self.depois()
        id_eva = [r for r in b.listar_abertas() if r["cpf"] == eva][0]["id"]
        self.sair(id_eva, saida="19/10/2026 10:14")
        b.anonimizar_pessoa(b.buscar_pessoa(eva)["id"],
                            "Pedido da titular (LGPD)", "ana")
        historico = [(h["nome"], h["transferida_para"])
                     for h in b.historico_de_chaves() if h["chave"] == "Sala 3"]
        self.assertIn(("Bruno Almeida", "Davi Prado"), historico)
        self.assertIn(("Davi Prado", "Pessoa anonimizada"), historico)


# ======================================================================
# Tela
# ======================================================================
class BaseTela36(BaseInterface):
    """A tela (janela oculta). Helena e Bruno estão na unidade; Davi é do
    cadastro, mas saiu."""

    def setUp(self):
        super().setUp()
        # o banco do app, com o relógio fixo dos testes (o self.banco da
        # BaseInterface usa o relógio de verdade: validade e horários)
        self.banco = self.app.banco
        self.helena = self.dentro(HELENA, "Helena Souza")
        self.bruno = self.dentro(BRUNO, "Bruno Almeida")
        self.banco.inserir(registro(cpf=DAVI, nome="Davi Prado",
                                    entrada="20/10/2026 08:00",
                                    saida="20/10/2026 09:00"),
                           autor="ana.admin")
        self.app.atualizar_tabela()
        # a pergunta da chave na saída e o diálogo da transferência não
        # travam o teste: cada teste diz a resposta (None = Cancelar)
        self.perguntas_chave = []
        self.respostas_chave = []

        def esperar(dialogo):
            self.perguntas_chave.append(dialogo.janela.title())
            resposta = self.respostas_chave.pop(0) if self.respostas_chave \
                else None
            if resposta is not None:
                dialogo.escolher(resposta)

        patcher = mock.patch.object(JanelaChaveNaSaida, "esperar", esperar)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.transferir_para = None          # CPF digitado; None = Cancelar
        self.dialogos_transferencia = []

        def esperar_transferencia(dialogo):
            self.dialogos_transferencia.append(dialogo.janela.title())
            if self.transferir_para is not None:
                dialogo.cpf.insert(0, self.transferir_para)
                dialogo.salvar()

        patcher = mock.patch.object(tela_chave_saida, "esperar_transferencia",
                                    esperar_transferencia)
        patcher.start()
        self.addCleanup(patcher.stop)

    def dentro(self, cpf, nome, minutos=60):
        return self.banco.inserir(registro(cpf=cpf, nome=nome,
                                           entrada=agora_menos(minutos)),
                                  autor="ana.admin")

    def pagina(self, nome):
        self.app.ir_para(getattr(self.app, "aba_" + nome))
        return getattr(self.app, "tela_" + nome)

    def selecionar(self, pagina, iid):
        pagina.atualizar()
        pagina.tabela.selection_set(str(iid))
        self.janela.update()

    def aberta(self, id_):
        return self.banco.buscar(id_)["saida"] == ""


# ----------------------------------------------------------------------
# 5) O componente de sugestões
# ----------------------------------------------------------------------
class TestComponenteSugestoes(BaseTela36):
    def setUp(self):
        super().setUp()
        self.banco.cadastrar_pessoa(cpf_ficticio(100000001), "Ana Helena Dias",
                                    "31987654321", "", "Visitante",
                                    "ana.admin")
        self.banco.cadastrar_pessoa(cpf_ficticio(100000002), "Michele Rocha",
                                    "31987654321", "", "Visitante",
                                    "ana.admin")
        # um formulário só com os dois campos, numa janela à parte
        self.quadro = tk.Toplevel(self.raiz)
        self.quadro.geometry("300x80+40+40")
        self.addCleanup(self.quadro.destroy)
        self.cpf = tk.Entry(self.quadro)
        self.nome = tk.Entry(self.quadro)
        self.cpf.pack()
        self.nome.pack()
        self.escolhidas = []
        self.sug = ligar_sugestoes(self.app, {"cpf": self.cpf,
                                              "nome": self.nome},
                                   ao_escolher=self.escolhidas.append)

    def digitar(self, campo, texto):
        caixa = getattr(self, campo)
        caixa.delete(0, tk.END)
        caixa.insert(0, texto)
        self.sug[campo].atualizar()
        return self.sug[campo]

    def nomes(self, s):
        return [p["nome"] for p in s.itens]

    def tecla(self, s, tecla):
        """A tecla no campo, com o foco nele (como o porteiro digitando)."""
        self.quadro.deiconify()
        self.quadro.update()
        s.entrada.focus_force()
        self.quadro.update()
        s.entrada.event_generate(tecla)
        self.quadro.update()

    def test_liga_os_dois_campos(self):
        self.assertEqual(set(self.sug), {"cpf", "nome"})
        self.assertIsInstance(self.sug["cpf"], Sugestoes)

    def test_2_caracteres_nao_sugere_3_sugere(self):
        s = self.digitar("nome", "He")
        self.assertFalse(s.aberta)
        self.assertEqual(s.itens, [])
        s = self.digitar("nome", "Hel")
        self.assertTrue(s.aberta)
        self.assertEqual(self.nomes(s), ["Helena Souza", "Ana Helena Dias",
                                         "Michele Rocha"])
        s = self.digitar("cpf", "52")
        self.assertFalse(s.aberta)
        s = self.digitar("cpf", "529")
        self.assertEqual(self.nomes(s), ["Helena Souza"])

    def test_refina_e_fecha_sem_ninguem(self):
        s = self.digitar("nome", "Hel")
        self.assertEqual(len(s.itens), 3)
        self.digitar("nome", "Helena S")
        self.assertEqual(self.nomes(s), ["Helena Souza"])
        self.digitar("nome", "Helena Sx")
        self.assertFalse(s.aberta)
        self.assertEqual(s.itens, [])

    def test_no_maximo_3_mesmo_se_o_banco_mandar_mais(self):
        with mock.patch.object(self.banco.__class__, "sugerir_pessoas",
                               return_value=[{"nome": f"P {n}", "cpf": HELENA,
                                              "tipo": "", "dentro": False,
                                              "desativada": False}
                                             for n in range(6)]):
            s = self.digitar("nome", "qualquer")
        self.assertEqual(len(s.itens), 3)

    def test_escolher_preenche_cpf_e_nome(self):
        s = self.digitar("nome", "Helena S")
        self.assertTrue(s.escolher_item(0))
        self.assertEqual((self.cpf.get(), self.nome.get()),
                         (HELENA, "Helena Souza"))
        self.assertFalse(s.aberta)
        self.assertEqual(self.escolhidas[0]["cpf"], HELENA)
        # a mesma escolha não reabre a lista
        s.atualizar()
        self.assertFalse(s.aberta)
        self.assertFalse(s.escolher_item(5))           # fora da lista

    def test_escolher_pelo_cpf_tambem_preenche_o_nome(self):
        s = self.digitar("cpf", "111")
        s.escolher_item(0)
        self.assertEqual((self.cpf.get(), self.nome.get()),
                         (BRUNO, "Bruno Almeida"))

    def test_setas_marcam_e_enter_escolhe(self):
        s = self.digitar("nome", "Hel")
        self.assertEqual(s.marcado, -1)
        self.tecla(s, "<Down>")
        self.assertEqual(s.marcado, 0)
        self.tecla(s, "<Down>")
        self.tecla(s, "<Down>")
        self.tecla(s, "<Down>")                       # não passa do último
        self.assertEqual(s.marcado, 2)
        self.tecla(s, "<Up>")
        self.assertEqual(s.marcado, 1)
        self.tecla(s, "<Return>")
        self.assertEqual(self.nome.get(), "Ana Helena Dias")
        self.assertFalse(s.aberta)

    def test_tab_escolhe_a_marcada(self):
        s = self.digitar("nome", "Hel")
        self.tecla(s, "<Down>")
        self.tecla(s, "<Tab>")
        self.assertEqual(self.nome.get(), "Helena Souza")
        self.assertEqual(self.cpf.get(), HELENA)
        self.janela.withdraw()

    def test_enter_sem_marcar_so_fecha(self):
        s = self.digitar("nome", "Hel")
        self.assertIsNone(s._confirmar())
        self.assertFalse(s.aberta)
        self.assertEqual(self.nome.get(), "Hel")
        self.assertEqual(self.cpf.get(), "")

    def test_esc_fecha_sem_escolher(self):
        s = self.digitar("nome", "Hel")
        self.tecla(s, "<Escape>")
        self.assertFalse(s.aberta)
        self.assertEqual((self.nome.get(), self.cpf.get()), ("Hel", ""))
        self.assertIsNone(s._esc())           # fechada: o Esc segue adiante
        self.janela.withdraw()

    def test_admin_ve_o_cpf_inteiro_e_quem_esta_na_unidade(self):
        s = self.digitar("nome", "Hel")
        textos = self.textos(s.janela)
        self.assertIn("CPF 529.982.247-25  ·  Funcionário", textos)
        self.assertIn(f"  ·  {NA_UNIDADE}", textos)

    def test_desativada_aparece_marcada(self):
        self.banco.desativar("cpf", cpf_ficticio(100000002), "Motivo de teste",
                             "ana.admin")
        s = self.digitar("nome", "Michele")
        self.assertIn(f"  ·  {DESATIVADA}", self.textos(s.janela))

    def test_clique_na_linha_escolhe(self):
        s = self.digitar("nome", "Helena S")
        self.quadro.update()
        s.janela.update()
        nome = s.linhas[0].winfo_children()[0]      # o rótulo com o nome
        nome.event_generate("<Button-1>", x=5, y=5)
        self.quadro.update()
        self.assertEqual(self.cpf.get(), HELENA)

    def test_so_dentro_e_excluir(self):
        dentro = ligar_sugestoes(self.app, {"nome": self.nome}, so_dentro=True,
                                 excluir=lambda: (BRUNO,))["nome"]
        self.nome.insert(0, "Hel")
        dentro.atualizar()
        self.assertEqual(self.nomes(dentro), ["Helena Souza"])
        self.nome.delete(0, tk.END)
        self.nome.insert(0, "Bru")
        dentro.atualizar()
        self.assertEqual(dentro.itens, [])

    def test_pessoa_pelo_nome(self):
        self.assertEqual(pessoa_pelo_nome(self.app, "helena souza")["cpf"],
                         HELENA)
        self.assertEqual(pessoa_pelo_nome(self.app, "Helena Souza",
                                          so_dentro=True)["cpf"], HELENA)
        self.assertIsNone(pessoa_pelo_nome(self.app, "Davi Prado",
                                           so_dentro=True))
        self.assertEqual(pessoa_pelo_nome(self.app, "Davi Prado")["cpf"], DAVI)
        for nome in ("Helena", "He", "", None, "52998224725",
                     "Ninguém Daqui"):
            with self.subTest(nome=nome):
                self.assertIsNone(pessoa_pelo_nome(self.app, nome))
        self.banco.cadastrar_pessoa(cpf_ficticio(100000003), "Helena Souza",
                                    "31987654321", "", "Visitante",
                                    "ana.admin")
        self.assertIsNone(pessoa_pelo_nome(self.app, "Helena Souza"))  # 2


class TestSugestoesDoPorteiro(TestComponenteSugestoes):
    entrar_como = "porteiro"

    def test_admin_ve_o_cpf_inteiro_e_quem_esta_na_unidade(self):
        self.skipTest("só vale para o administrador")

    def test_porteiro_ve_o_cpf_mascarado(self):
        """O porteiro vê o CPF mascarado na lista (privacidade)."""
        s = self.digitar("nome", "Hel")
        textos = " ".join(self.textos(s.janela))
        self.assertIn("CPF ***.982.247-**", textos)
        self.assertNotIn("529.982.247-25", textos)
        self.assertNotIn(HELENA, textos)

    def test_desativada_aparece_marcada(self):
        self.skipTest("só o administrador desativa")


class TestSugestoesNasTelas(BaseTela36):
    """Cada campo de CPF/nome da lista do aluno tem as sugestões."""

    def test_campos_ligados(self):
        app = self.app
        casos = []
        d = self.pagina("ocorrencias").nova()
        casos.append(("Nova ocorrência", d, {"cpf"}))
        d2 = self.pagina("autorizacoes").novo()
        casos.append(("Nova autorização", d2, {"cpf", "nome"}))
        d3 = self.pagina("funcionarios").novo()
        casos.append(("Novo funcionário", d3, {"cpf", "nome"}))
        pessoas = self.pagina("pessoas")
        d4 = pessoas.nova_pessoa()
        casos.append(("Nova pessoa", d4, {"cpf", "nome"}))
        d5 = self.pagina("encomendas").novo()
        casos.append(("Nova encomenda", d5, {"nome"}))
        cad = app.tela_cadastro
        for nome, d, campos in casos:
            with self.subTest(dialogo=nome):
                self.assertEqual(set(d.sugestoes), campos)
                d.fechar()
        self.assertEqual(set(cad.sugestoes), {"cpf", "nome"})
        self.assertEqual(set(cad.sugestoes_destinatario), {"nome"})
        config = self.pagina("configuracoes")
        self.assertEqual(set(config.sugestoes_anonimizar), {"cpf"})

    def test_quem_retira_so_mostra_quem_esta_dentro(self):
        lab = self.banco.cadastrar_chave("Laboratório 2", "", "ana.admin")
        chaves = self.pagina("chaves")
        self.selecionar(chaves, lab)
        d = chaves.entregar()
        d.nome.insert(0, "Dav")
        d.sugestoes["nome"].atualizar()
        self.assertEqual(d.sugestoes["nome"].itens, [])     # Davi saiu
        d.nome.delete(0, tk.END)
        d.nome.insert(0, "Hel")
        d.sugestoes["nome"].atualizar()
        self.assertEqual([p["nome"] for p in d.sugestoes["nome"].itens],
                         ["Helena Souza"])
        d.fechar()

    def test_cadastro_escolher_preenche_o_cadastro(self):
        cad = self.app.tela_cadastro
        self.app.nome.insert(0, "Dav")
        s = cad.sugestoes["nome"]
        s.atualizar()
        self.assertEqual([p["nome"] for p in s.itens], ["Davi Prado"])
        s.escolher_item(0)
        self.assertEqual((self.app.nome.get(), self.app.cpf.get()),
                         ("Davi Prado", DAVI))
        self.assertEqual(self.app.celular.get(), "31987654321")  # puxou o resto
        self.app.cadastrar()
        visitas = [r for r in self.no_banco() if r["cpf"] == DAVI]
        self.assertEqual(len(visitas), 2)
        self.assertEqual(sum(1 for r in visitas if not r["saida"]), 1)

    def test_dialogo_autorizado_nao_sugere_o_proprio_dono(self):
        pessoas = self.pagina("pessoas")
        pessoas.atualizar()
        pessoas.tabela.selection_set(str(self.banco.buscar_pessoa(HELENA)["id"]))
        pessoas.ao_selecionar()
        d = pessoas.adicionar_autorizado_encomenda()
        d.nome.insert(0, "Hel")
        d.sugestoes["nome"].atualizar()
        self.assertEqual(d.sugestoes["nome"].itens, [])
        d.fechar()


# ----------------------------------------------------------------------
# 1) Encomendas na tela
# ----------------------------------------------------------------------
class TestEncomendaNaTela(BaseTela36):
    def nova(self, texto, escolher=None, remetente="Correios"):
        d = self.pagina("encomendas").novo()
        self.assertIsInstance(d, DialogoEncomenda)
        d.destinatario.insert(0, texto)
        if escolher is not None:
            d.sugestoes["nome"].atualizar()
            d.sugestoes["nome"].escolher_item(escolher)
        d.remetente.insert(0, remetente)
        return d

    def test_escolher_nas_sugestoes_grava_o_cpf(self):
        d = self.nova("Hel", escolher=0)
        self.assertEqual(d.destinatario.get(), "Helena Souza")
        self.assertEqual(d.escolhido["cpf"], HELENA)
        self.assertEqual(cpf_escolhido(d.escolhido, d.destinatario.get()),
                         HELENA)
        self.assertTrue(d.salvar())
        e, = self.banco.listar_encomendas()
        self.assertEqual((e["destinatario"], e["destinatario_cpf"]),
                         ("Helena Souza", HELENA))
        self.assertEqual(self.app.tela_encomendas.faixa.lbl.cget("text"),
                         "Encomenda nº 001 para Helena Souza registrada.")

    def test_escolher_e_depois_trocar_o_texto_perde_a_escolha(self):
        d = self.nova("Hel", escolher=0)
        d.destinatario.delete(0, tk.END)
        d.destinatario.insert(0, "Bruno Almeida")
        self.assertTrue(d.salvar())
        self.assertEqual(self.banco.listar_encomendas()[0]["destinatario_cpf"],
                         BRUNO)

    def test_nome_de_ninguem_avisa_e_o_dialogo_fica(self):
        d = self.nova("Setor de Compras")
        self.assertFalse(d.salvar())
        titulo, texto = self.msg.showerror.call_args[0][:2]
        self.assertEqual(texto, NINGUEM_SE_CHAMA.format("Setor de Compras"))
        self.assertTrue(d.janela.winfo_exists())
        self.assertEqual(self.banco.listar_encomendas(), [])
        d.fechar()

    def test_enter_com_a_lista_aberta_escolhe_e_nao_registra(self):
        d = self.nova("Hel")
        s = d.sugestoes["nome"]
        s.atualizar()
        self.janela.deiconify()
        d.destinatario.focus_force()
        self.janela.update()
        d.destinatario.event_generate("<Down>")
        d.destinatario.event_generate("<Return>")
        self.janela.update()
        self.assertEqual(d.destinatario.get(), "Helena Souza")
        self.assertEqual(self.banco.listar_encomendas(), [])  # não salvou
        self.assertTrue(d.janela.winfo_exists())
        d.fechar()
        self.janela.withdraw()

    def test_esc_com_a_lista_aberta_fecha_so_a_lista(self):
        d = self.nova("Hel")
        d.sugestoes["nome"].atualizar()
        self.janela.deiconify()
        d.destinatario.focus_force()
        self.janela.update()
        d.destinatario.event_generate("<Escape>")
        self.janela.update()
        self.assertFalse(d.sugestoes["nome"].aberta)
        self.assertTrue(d.janela.winfo_exists())
        d.fechar()
        self.janela.withdraw()

    def test_cpf_escolhido(self):
        p = {"nome": "Hélena Souza", "cpf": HELENA}
        self.assertEqual(cpf_escolhido(p, "helena  souza"), HELENA)
        self.assertEqual(cpf_escolhido(p, "Helena"), "")
        self.assertEqual(cpf_escolhido(None, "Helena Souza"), "")

    def retirar(self, cpf="", nome=""):
        id_ = self.banco.registrar_encomenda("Helena Souza", "Correios",
                                             "ana.admin")
        pagina = self.pagina("encomendas")
        self.selecionar(pagina, id_)
        d = pagina.retirar()
        self.assertIsInstance(d, DialogoQuemRetira)
        if cpf:
            d.cpf.insert(0, cpf)
        if nome:
            d.nome.delete(0, tk.END)
            d.nome.insert(0, nome)
        return id_, d

    def test_retirada_pelo_cpf_puxa_o_nome(self):
        id_, d = self.retirar(HELENA)
        self.assertEqual(d.nome.get(), "Helena Souza")
        self.assertTrue(d.salvar())
        e, = self.banco.listar_encomendas()
        self.assertEqual((e["retirada_nome"], e["retirada_cpf"]),
                         ("Helena Souza", HELENA))
        self.assertEqual(self.app.tela_encomendas.faixa.lbl.cget("text"),
                         f"Encomenda nº {id_} retirada por Helena Souza.")

    def test_retirada_pelo_nome_inteiro_acha_o_cpf(self):
        _, d = self.retirar(nome="helena souza")
        self.assertTrue(d.salvar())
        self.assertEqual(self.banco.listar_encomendas()[0]["retirada_cpf"],
                         HELENA)

    def test_retirada_recusas_no_dialogo(self):
        for cpf, nome, msg in (
                ("", "", "O CPF é obrigatório."),
                ("", "Davi Prado", "Escolha a pessoa nas sugestões (comece a "
                                   "digitar o nome ou o CPF): o CPF é "
                                   "obrigatório."),
                ("", "Helena", "Escolha a pessoa nas sugestões (comece a "
                               "digitar o nome ou o CPF): o CPF é "
                               "obrigatório."),
                ("52998224726", "Helena Souza", CPF_INEXISTENTE),
                ("529982", "Helena Souza", CPF_INCOMPLETO),
                (EVA, "Eva Martins", CPF_NAO_CADASTRADO),
                (HELENA, "Bruno Almeida", "Este CPF é de Helena Souza, não de "
                                          "Bruno Almeida.\nConfira o CPF ou o "
                                          "nome.")):
            with self.subTest(cpf=cpf, nome=nome):
                _, d = self.retirar(cpf, nome)
                self.assertFalse(d.salvar())
                self.assertEqual(d.faixa.lbl.cget("text"), msg)
                d.fechar()
        self.assertTrue(all(not e["retirada_em"]
                            for e in self.banco.listar_encomendas()))

    def test_retirada_por_quem_nao_pode_avisa_e_nao_grava(self):
        _, d = self.retirar(BRUNO)
        d.salvar()
        texto = self.msg.showerror.call_args[0][1]
        self.assertIn("Bruno Almeida não pode retirar a encomenda de Helena "
                      "Souza", texto)
        self.assertEqual(self.banco.listar_encomendas()[0]["retirada_em"], "")


# ----------------------------------------------------------------------
# 1) Pessoas › ficha › Encomendas
# ----------------------------------------------------------------------
class TestFichaEncomendas(BaseTela36):
    entrar_como = "porteiro"

    def ficha(self, cpf=HELENA):
        pessoas = self.pagina("pessoas")
        pessoas.atualizar()
        pessoas.tabela.selection_set(str(self.banco.buscar_pessoa(cpf)["id"]))
        pessoas.ao_selecionar()
        pessoas.seletor_ficha.selecionar("Encomendas")
        return pessoas

    def titulo_da_secao(self, pessoas):
        return pessoas.seletor_ficha.itens["Encomendas"][0].cget("text")

    def test_a_secao_existe(self):
        self.assertEqual(SECOES_FICHA, ("Visitas", "Veículo", "Encomendas"))
        pessoas = self.ficha()
        self.assertEqual(self.titulo_da_secao(pessoas), "Encomendas")
        self.assertEqual(pessoas.lbl_aguardando.cget("text"),
                         "Nenhuma encomenda aguardando retirada.")

    def test_aguardando_retirada(self):
        for remetente in ("Correios", "Kalunga"):
            self.banco.registrar_encomenda("Helena Souza", remetente, "paulo")
        self.banco.registrar_encomenda("Bruno Almeida", "Amazon", "paulo")
        pessoas = self.ficha()
        self.assertEqual(pessoas.lbl_aguardando.cget("text"),       # recentes
                         "Aguardando retirada: 2 encomendas (nº 002, 001).")
        self.banco.retirar_encomenda(1, HELENA, "paulo")
        pessoas = self.ficha()
        self.assertEqual(pessoas.lbl_aguardando.cget("text"),
                         "Aguardando retirada: 1 encomenda (nº 002).")

    def test_porteiro_adiciona_com_a_pessoa_na_unidade(self):
        pessoas = self.ficha()
        self.assertTrue(pessoas.btn_adicionar_encomenda.ativo)
        self.assertFalse(pessoas.btn_validade_encomenda.ativo)   # lista vazia
        self.assertFalse(pessoas.btn_remover_encomenda.ativo)
        d = pessoas.adicionar_autorizado_encomenda()
        self.assertIsInstance(d, DialogoAutorizado)
        self.assertTrue(d.encomenda)
        self.assertEqual(d.janela.title(), "Quem pode retirar as encomendas")
        d.cpf.insert(0, BRUNO)
        self.assertEqual(d.nome.get(), "Bruno Almeida")          # já veio
        self.assertTrue(d.salvar())
        self.assertFalse(d.janela.winfo_exists())
        tabela = pessoas.tabela_autorizados_encomenda
        linha, = tabela.get_children()
        self.assertEqual(tabela.item(linha)["values"][:3],
                         ["Bruno Almeida", "***.444.777-**", "sem prazo"])
        self.assertEqual(self.titulo_da_secao(pessoas), "Encomendas (1)")
        self.assertTrue(pessoas.btn_validade_encomenda.ativo)
        self.assertTrue(pessoas.btn_remover_encomenda.ativo)
        self.assertIn(("paulo", AUTORIZADO_ENCOMENDA_ADICIONADO), self.acoes())

    def test_porteiro_com_a_pessoa_fora_nao_adiciona(self):
        pessoas = self.ficha(DAVI)
        self.assertFalse(pessoas.btn_adicionar_encomenda.ativo)
        self.assertEqual(pessoas.lbl_pessoa_fora.cget("text"), PESSOA_FORA)
        self.assertEqual(pessoas.lbl_pessoa_fora.winfo_manager(), "pack")
        self.assertIsNone(pessoas.adicionar_autorizado_encomenda())
        self.msg.showwarning.assert_called()

    def test_dados_invalidos_ficam_no_dialogo(self):
        pessoas = self.ficha()
        for cpf, nome, validade, msg in (
                (HELENA, "Helena Souza", "",
                 "A própria pessoa já retira as encomendas dela."),
                ("11144477700", "Bruno Almeida", "", CPF_INEXISTENTE),
                ("1114", "Bruno Almeida", "", CPF_INCOMPLETO),
                (BRUNO, "Bruno", "", "Informe o nome completo de quem vai "
                                     "retirar (só letras)."),
                (BRUNO, "Bruno Almeida", "01/01/2020",
                 "A validade não pode ser antes de hoje.")):
            with self.subTest(cpf=cpf, validade=validade):
                d = pessoas.adicionar_autorizado_encomenda()
                d.cpf.insert(0, cpf)
                d.nome.delete(0, tk.END)
                d.nome.insert(0, nome)
                d.validade.insert(0, validade)
                self.assertFalse(d.salvar())
                self.assertEqual(d.faixa.lbl.cget("text"), msg)
                d.fechar()
        self.assertEqual(self.banco.listar_autorizados_encomenda(HELENA), [])

    def test_validade_pela_ficha(self):
        id_ = self.banco.adicionar_autorizado_encomenda(
            HELENA, BRUNO, "Bruno Almeida", None, "paulo")
        pessoas = self.ficha()
        self.assertIsNone(pessoas.editar_validade_encomenda())   # sem seleção
        pessoas.tabela_autorizados_encomenda.selection_set(str(id_))
        d = pessoas.editar_validade_encomenda()
        self.assertIsInstance(d, DialogoValidade)
        self.assertTrue(d.encomenda)
        d.validade.insert(0, "01/01/2020")
        self.assertFalse(d.salvar())
        self.assertIn("antes de hoje", d.faixa.lbl.cget("text"))
        d.validade.delete(0, tk.END)
        d.validade.insert(0, "31/12/2030")
        self.assertTrue(d.salvar())
        self.assertEqual(self.banco.listar_autorizados_encomenda(HELENA)[0]
                         ["valido_ate"], date(2030, 12, 31))
        linha = pessoas.tabela_autorizados_encomenda.item(str(id_))
        self.assertEqual(linha["values"][2], "31/12/2030")
        self.assertIn(("paulo", AUTORIZADO_ENCOMENDA_VALIDADE), self.acoes())

    def test_vencido_aparece_como_venceu(self):
        self.banco.adicionar_autorizado_encomenda(
            HELENA, BRUNO, "Bruno Almeida", self.agora.date(), "paulo")
        self.agora += timedelta(days=1)
        pessoas = self.ficha()
        tabela = pessoas.tabela_autorizados_encomenda
        linha, = tabela.get_children()
        self.assertEqual(tabela.item(linha)["values"][2], "venceu")

    def test_remover_pede_confirmacao(self):
        id_ = self.banco.adicionar_autorizado_encomenda(
            HELENA, BRUNO, "Bruno Almeida", None, "paulo")
        pessoas = self.ficha()
        pessoas.tabela_autorizados_encomenda.selection_set(str(id_))
        self.msg.askyesno.return_value = False
        pessoas.remover_autorizado_encomenda()
        self.assertEqual(len(self.banco.listar_autorizados_encomenda(HELENA)), 1)
        self.msg.askyesno.return_value = True
        pessoas.remover_autorizado_encomenda()
        self.assertEqual(self.banco.listar_autorizados_encomenda(HELENA), [])
        self.assertEqual(pessoas.tabela_autorizados_encomenda.get_children(), ())
        self.assertIn(("paulo", AUTORIZADO_ENCOMENDA_REMOVIDO), self.acoes())

    def test_porteiro_com_a_pessoa_fora_nao_muda_a_validade(self):
        id_ = self.banco.adicionar_autorizado_encomenda(
            DAVI, BRUNO, "Bruno Almeida", None, "ana.admin")
        pessoas = self.ficha(DAVI)
        self.assertFalse(pessoas.btn_validade_encomenda.ativo)
        self.assertTrue(pessoas.btn_remover_encomenda.ativo)     # remover pode
        pessoas.tabela_autorizados_encomenda.selection_set(str(id_))
        self.assertIsNone(pessoas.editar_validade_encomenda())


class TestFichaEncomendasDoAdministrador(BaseTela36):
    def test_administrador_adiciona_com_a_pessoa_fora(self):
        pessoas = self.pagina("pessoas")
        pessoas.atualizar()
        pessoas.tabela.selection_set(str(self.banco.buscar_pessoa(DAVI)["id"]))
        pessoas.ao_selecionar()
        self.assertTrue(pessoas.btn_adicionar_encomenda.ativo)
        d = pessoas.adicionar_autorizado_encomenda()
        d.cpf.insert(0, BRUNO)
        d.validade.insert(0, "31/12/2026")
        self.assertTrue(d.salvar())
        a, = self.banco.listar_autorizados_encomenda(DAVI)
        self.assertEqual((a["valido_ate"], a["dono_presente"]),
                         (date(2026, 12, 31), False))
        linha = pessoas.tabela_autorizados_encomenda.item(str(a["id"]))
        self.assertEqual(linha["values"][1], "111.444.777-35")   # admin: inteiro


# ----------------------------------------------------------------------
# 2) Chaves na tela: entregar, transferir, histórico
# ----------------------------------------------------------------------
class TestChavesNaTela36(BaseTela36):
    def setUp(self):
        super().setUp()
        self.lab = self.banco.cadastrar_chave("Laboratório 2", "Bloco B",
                                              "ana.admin")
        self.chaves = self.pagina("chaves")
        self.selecionar(self.chaves, self.lab)

    def test_transferir_so_com_a_chave_emprestada(self):
        p = self.chaves
        self.assertFalse(p.btn_transferir.ativo)
        self.assertIsNone(p.transferir())
        self.banco.entregar_chave(self.lab, HELENA, "ana.admin")
        self.selecionar(p, self.lab)
        self.assertTrue(p.btn_transferir.ativo)
        self.assertFalse(p.btn_entregar.ativo)

    def test_entregar_pela_tela_exige_quem_esta_dentro(self):
        d = self.chaves.entregar()
        d.cpf.insert(0, DAVI)
        self.assertEqual(d.nome.get(), "Davi Prado")
        d.salvar()
        self.assertIn("Davi Prado não está na unidade",
                      self.msg.showerror.call_args[0][1])
        # o diálogo continua aberto para corrigir (achado do QA)
        self.assertTrue(d.janela.winfo_exists())
        d.cpf.delete(0, "end")
        d.nome.delete(0, "end")
        d.cpf.insert(0, HELENA)
        self.assertTrue(d.salvar())
        self.assertFalse(d.janela.winfo_exists())
        self.assertEqual(self.banco.listar_chaves()[0]["com_quem"],
                         "Helena Souza")

    def test_transferir_para_quem_ja_esta_com_a_chave_e_recusado_no_dialogo(
            self):
        self.banco.entregar_chave(self.lab, HELENA, "ana.admin")
        self.selecionar(self.chaves, self.lab)
        d = self.chaves.transferir()
        d.cpf.insert(0, HELENA)
        self.assertFalse(d.salvar())
        self.assertEqual(d.faixa.lbl.cget("text"),
                         "A chave \"Laboratório 2\" já está com Helena "
                         "Souza.\nEscolha outra pessoa.")
        self.assertTrue(d.janela.winfo_exists())
        d.fechar()
        self.assertEqual(self.banco.listar_chaves()[0]["com_quem"],
                         "Helena Souza")

    def test_transferir_pela_tela(self):
        self.banco.entregar_chave(self.lab, HELENA, "ana.admin")
        self.selecionar(self.chaves, self.lab)
        d = self.chaves.transferir()
        self.assertEqual(d.janela.title(), "Transferir chave")
        d.nome.insert(0, "Hel")                    # quem está com ela não
        d.sugestoes["nome"].atualizar()            # aparece nas sugestões
        self.assertEqual(d.sugestoes["nome"].itens, [])
        d.nome.delete(0, tk.END)
        d.cpf.insert(0, BRUNO)
        self.assertTrue(d.salvar())
        self.assertEqual(self.chaves.tabela.set(str(self.lab), "quem"),
                         "Bruno Almeida")
        self.assertEqual(self.chaves.faixa.lbl.cget("text"),
                         "Chave \"Laboratório 2\" transferida de Helena Souza "
                         "para Bruno Almeida.")
        self.assertIn(("ana.admin", "Chave transferida"), self.acoes())

    def test_historico_mostra_para_quem_foi(self):
        self.banco.entregar_chave(self.lab, HELENA, "ana.admin")
        self.agora += timedelta(minutes=5)
        self.banco.transferir_chave(self.lab, BRUNO, "ana.admin")
        d = self.chaves.ver_historico()
        linhas = [d.tabela.item(i)["values"] for i in d.tabela.get_children()]
        self.assertEqual(linhas[0][1], "Bruno Almeida")
        self.assertEqual(linhas[0][3], "com a pessoa")
        self.assertEqual(linhas[1][1], "Helena Souza")
        self.assertEqual(linhas[1][3], "21/10/2026 10:05 → Bruno Almeida")
        d.fechar()

    def test_dialogos_cabem_no_notebook(self):
        self.banco.entregar_chave(self.lab, HELENA, "ana.admin")
        self.selecionar(self.chaves, self.lab)
        for d in (self.chaves.transferir(), self.chaves.ver_historico()):
            with self.subTest(dialogo=d.janela.title()):
                d.janela.update()
                self.assertLessEqual(d.janela.winfo_reqheight(), 536 - 30)
                self.assertLessEqual(d.janela.winfo_reqwidth(), 1093)
                d.fechar()


# ----------------------------------------------------------------------
# 2) A chave na saída (devolver / transferir / cancelar)
# ----------------------------------------------------------------------
class TestChaveNaSaidaNaTela(BaseTela36):
    def setUp(self):
        super().setUp()
        self.lab = self.banco.cadastrar_chave("Laboratório 2", "Bloco B",
                                              "ana.admin")
        self.banco.entregar_chave(self.lab, HELENA, "ana.admin")
        self.app.atualizar_tabela()
        self.cad = self.app.tela_cadastro

    def saida_da_helena(self):
        self.cad.dar_saida([self.banco.buscar(self.helena)])

    def com_quem(self):
        c = self.banco.listar_chaves()[0]
        return c["com_quem"] if c["emprestada"] else None

    def test_pergunta_uma_vez_por_chave(self):
        self.respostas_chave = [DEVOLVER]
        self.saida_da_helena()
        self.assertEqual(self.perguntas_chave,
                         ["Helena está com a chave \"Laboratório 2\""])

    def test_devolver_e_sair(self):
        self.respostas_chave = [DEVOLVER]
        self.assertIsNot(self.cad.dar_saida([self.banco.buscar(self.helena)]),
                         False)
        self.assertIsNone(self.com_quem())
        self.assertFalse(self.aberta(self.helena))
        self.assertIn(("ana.admin", "Chave devolvida"), self.acoes())

    def test_transferir_e_sair(self):
        self.respostas_chave = [TRANSFERIR]
        self.transferir_para = BRUNO
        self.saida_da_helena()
        self.assertEqual(self.dialogos_transferencia, ["Transferir chave"])
        self.assertEqual(self.com_quem(), "Bruno Almeida")
        self.assertFalse(self.aberta(self.helena))
        self.assertTrue(self.aberta(self.bruno))
        self.assertIn(("ana.admin", "Chave transferida"), self.acoes())

    def test_cancelar_a_pergunta_nao_grava_nada(self):
        self.respostas_chave = [None]
        self.assertFalse(self.cad.dar_saida([self.banco.buscar(self.helena)]))
        self.assertEqual(self.com_quem(), "Helena Souza")
        self.assertTrue(self.aberta(self.helena))

    def test_cancelar_a_transferencia_nao_grava_nada(self):
        self.respostas_chave = [TRANSFERIR]
        self.transferir_para = None
        self.assertFalse(self.cad.dar_saida([self.banco.buscar(self.helena)]))
        self.assertEqual(self.com_quem(), "Helena Souza")
        self.assertTrue(self.aberta(self.helena))

    def test_transferir_para_quem_esta_fora_avisa_e_nao_sai(self):
        self.respostas_chave = [TRANSFERIR]
        self.transferir_para = DAVI
        self.assertFalse(self.cad.dar_saida([self.banco.buscar(self.helena)]))
        self.assertIn("Davi Prado não está na unidade",
                      self.msg.showerror.call_args[0][1])
        self.assertEqual(self.com_quem(), "Helena Souza")
        self.assertTrue(self.aberta(self.helena))

    def test_duas_chaves_duas_perguntas(self):
        aud = self.banco.cadastrar_chave("Auditório", "", "ana.admin")
        self.banco.entregar_chave(aud, HELENA, "ana.admin")
        self.respostas_chave = [DEVOLVER, TRANSFERIR]
        self.transferir_para = BRUNO
        self.saida_da_helena()
        self.assertEqual(self.perguntas_chave,
                         ["Helena está com a chave \"Auditório\"",
                          "Helena está com a chave \"Laboratório 2\""])
        self.assertEqual(self.banco.chaves_da_pessoa(HELENA), [])
        self.assertEqual([c["nome"] for c in self.banco.chaves_da_pessoa(BRUNO)],
                         ["Laboratório 2"])
        self.assertFalse(self.aberta(self.helena))

    def test_quem_nao_tem_chave_nao_e_perguntado(self):
        self.cad.dar_saida([self.banco.buscar(self.bruno)])
        self.assertEqual(self.perguntas_chave, [])
        self.assertFalse(self.aberta(self.bruno))

    def test_botao_registrar_saida_tambem_pergunta(self):
        self.respostas_chave = [DEVOLVER]
        self.app.tabela.selection_set(str(self.helena))
        self.cad.registrar_saida()
        self.assertEqual(len(self.perguntas_chave), 1)
        self.assertFalse(self.aberta(self.helena))

    def test_saida_rapida_pelo_cpf_tambem_pergunta(self):
        self.respostas_chave = [None]
        self.cad.campo_saida_rapida.insert(0, HELENA)
        self.cad.saida_rapida()
        self.assertEqual(len(self.perguntas_chave), 1)
        self.assertTrue(self.aberta(self.helena))

    def test_duas_pessoas_cancelar_nao_grava_nenhuma(self):
        self.respostas_chave = [None]
        self.assertFalse(self.cad.dar_saida([self.banco.buscar(self.helena),
                                             self.banco.buscar(self.bruno)]))
        self.assertTrue(self.aberta(self.helena))
        self.assertTrue(self.aberta(self.bruno))

    def test_dialogo_da_pergunta_tem_os_tres_botoes(self):
        def olhar(dialogo):
            self.botoes_vistos = self.botoes(dialogo.janela)
            self.titulo_visto = dialogo.janela.title()

        with mock.patch.object(JanelaChaveNaSaida, "esperar", olhar):
            self.saida_da_helena()
        self.assertEqual(self.botoes_vistos,
                         ["Registrar devolução", "Transferir para outra pessoa",
                          "Cancelar"])
        self.assertTrue(self.aberta(self.helena))           # fechou = cancelar

    def test_transferir_para_quem_tambem_esta_saindo_e_recusado(self):
        """Corrigido (achado do QA): na saída de várias pessoas, o CPF
        digitado de quem também está saindo era aceito na transferência.
        Agora o diálogo recusa (com a mensagem) e nada é transferido."""
        self.respostas_chave = [TRANSFERIR]
        self.transferir_para = BRUNO
        recusas = []
        original = DialogoQuemRetira.erro

        def erro(dialogo, texto):
            recusas.append(texto)
            return original(dialogo, texto)

        with mock.patch.object(DialogoQuemRetira, "erro", erro):
            self.assertFalse(self.cad.dar_saida(
                [self.banco.buscar(self.bruno),
                 self.banco.buscar(self.helena)]))
        self.assertEqual(recusas, ["Bruno Almeida também está saindo.\n"
                                   "Escolha quem fica na unidade."])
        self.assertEqual(self.com_quem(), "Helena Souza")
        self.assertTrue(self.aberta(self.bruno))
        self.assertTrue(self.aberta(self.helena))

    def test_transferencia_recusada_pelo_banco_deixa_o_dialogo_aberto(self):
        """Achado do QA: o diálogo fechava antes de o banco conferir. Agora,
        com o CPF de quem está fora, o erro aparece e o diálogo continua
        aberto para o porteiro corrigir."""
        self.respostas_chave = [TRANSFERIR]
        self.transferir_para = DAVI
        abertos = []
        original = tela_chave_saida.esperar_transferencia

        def esperar(dialogo):
            original(dialogo)
            abertos.append(dialogo.janela.winfo_exists())

        with mock.patch.object(tela_chave_saida, "esperar_transferencia",
                               esperar):
            self.assertFalse(self.cad.dar_saida(
                [self.banco.buscar(self.helena)]))
        self.assertEqual(abertos, [True])
        self.assertIn("Davi Prado não está na unidade",
                      self.msg.showerror.call_args[0][1])
        self.assertEqual(self.com_quem(), "Helena Souza")

    def test_corrigir_o_cpf_no_mesmo_dialogo_transfere(self):
        """Depois da recusa, o porteiro troca o CPF e a transferência sai."""
        self.respostas_chave = [TRANSFERIR]

        def esperar(dialogo):
            dialogo.cpf.insert(0, DAVI)
            dialogo.salvar()
            self.assertTrue(dialogo.janela.winfo_exists())
            dialogo.cpf.delete(0, "end")
            dialogo.nome.delete(0, "end")
            dialogo.cpf.insert(0, BRUNO)
            self.assertTrue(dialogo.salvar())
            self.assertFalse(dialogo.janela.winfo_exists())

        with mock.patch.object(tela_chave_saida, "esperar_transferencia",
                               esperar):
            self.assertIsNot(self.cad.dar_saida(
                [self.banco.buscar(self.helena)]), False)
        self.assertEqual(self.com_quem(), "Bruno Almeida")
        self.assertFalse(self.aberta(self.helena))


# ----------------------------------------------------------------------
# 3) As mensagens de CPF nas telas; 4) a autorização repetida na tela
# ----------------------------------------------------------------------
class TestMensagensNasTelas(BaseTela36):
    def test_cadastro_avisa_cpf_que_nao_existe_na_hora(self):
        self.app.cpf.insert(0, "52998224726")
        self.assertIn("CPF inválido. Digite um CPF existente.",
                      self.app.lbl_pessoa.cget("text"))

    def test_cadastrar_com_cpf_incompleto(self):
        self.preencher(cpf="5299822472")
        self.app.cadastrar()
        self.assertEqual(self.msg.showerror.call_args[0][1], CPF_INCOMPLETO)

    def test_nova_pessoa(self):
        d = self.pagina("pessoas").nova_pessoa()
        d.cpf.insert(0, "52998224726")
        self.assertIn("CPF inválido. Digite um CPF existente.",
                      d.faixa.lbl.cget("text"))
        d.fechar()

    def test_ocorrencia_com_cpf_de_quem_nao_e_do_cadastro(self):
        pagina = self.pagina("ocorrencias")
        d = pagina.nova()
        d.categoria.set(validacao.CATEGORIAS_OCORRENCIA[0])
        d.texto.insert("1.0", "Pessoa sem crachá na portaria")
        d.cpf.insert(0, EVA)
        self.assertFalse(d.salvar())
        self.assertEqual(d.faixa.lbl.cget("text"), CPF_NAO_CADASTRADO)
        d.cpf.delete(0, tk.END)
        d.cpf.insert(0, "12345678900")
        self.assertFalse(d.salvar())
        self.assertEqual(d.faixa.lbl.cget("text"), CPF_INEXISTENTE)
        d.cpf.delete(0, tk.END)
        d.cpf.insert(0, DAVI)
        self.assertTrue(d.salvar())
        self.assertEqual(self.banco.listar_ocorrencias()[0]["cpf"], DAVI)

    def test_anonimizar_em_configuracoes(self):
        config = self.pagina("configuracoes")
        config.cpf_anonimizar.insert(0, "52998224726")
        config.justificativa_anonimizar.insert(0, "Pedido do titular")
        config.anonimizar()
        self.assertIn("CPF inválido. Digite um CPF existente.",
                      config.faixa_privacidade.lbl.cget("text"))

    def test_autorizacao_repetida_avisa_e_o_dialogo_fica(self):
        pagina = self.pagina("autorizacoes")
        for vez in (1, 2):
            d = pagina.novo()
            d.cpf.insert(0, EVA)
            d.nome.insert(0, "Eva Martins")
            d.anfitriao.insert(0, "Diretoria")
            d.motivo.insert(0, "Reunião sobre o contrato")
            ok = d.salvar()
            if vez == 1:
                self.assertTrue(ok)
        self.assertFalse(ok)
        self.assertIn("Este CPF já tem a autorização nº 1 (Eva Martins",
                      self.msg.showerror.call_args[0][1])
        self.assertTrue(d.janela.winfo_exists())
        self.assertEqual(len(self.banco.listar_autorizacoes()), 1)
        d.fechar()


class TestCadastroEntregadorComSugestoes(BaseTela36):
    def test_destinatario_escolhido_vai_com_o_cpf(self):
        cad = self.app.tela_cadastro
        self.app.tipo.set("Entregador")
        cad.destinatario.insert(0, "Hel")
        cad.sugestoes_destinatario["nome"].atualizar()
        cad.sugestoes_destinatario["nome"].escolher_item(0)
        self.assertEqual(cad._destinatario_escolhido["cpf"], HELENA)
        cad.remetente.insert(0, "Correios")
        self.assertEqual(cad.registrar_encomenda(), 1)
        e, = self.banco.listar_encomendas()
        self.assertEqual((e["destinatario"], e["destinatario_cpf"]),
                         ("Helena Souza", HELENA))
        self.assertEqual(cad.lbl_pessoa.cget("text"),
                         "Encomenda nº 001 para Helena Souza registrada.")
        self.assertIsNone(cad._destinatario_escolhido)      # limpou

    def test_destinatario_que_nao_e_do_cadastro_avisa(self):
        cad = self.app.tela_cadastro
        self.app.tipo.set("Entregador")
        cad.destinatario.insert(0, "Setor de Compras")
        cad.remetente.insert(0, "Correios")
        self.assertIsNone(cad.registrar_encomenda())
        self.assertEqual(self.msg.showerror.call_args[0][1],
                         NINGUEM_SE_CHAMA.format("Setor de Compras"))
        self.assertEqual(cad.destinatario.get(), "Setor de Compras")  # fica
        self.assertEqual(self.banco.listar_encomendas(), [])


if __name__ == "__main__":
    unittest.main()


# ----------------------------------------------------------------------
# Correções do QA da 3.6: encerrar o dia na tela; excluir pessoa com
# encomenda aguardando retirada
# ----------------------------------------------------------------------
class TestEncerrarODiaComChaveNaTela(BaseTela36):
    def test_pergunta_e_aviso_falam_de_quem_esta_com_a_chave(self):
        lab = self.banco.cadastrar_chave("Laboratório 2", "", "ana.admin")
        self.banco.entregar_chave(lab, HELENA, "ana.admin")
        ctrl = self.app.tela_cadastro
        pendentes = [self.banco.buscar(self.helena),
                     self.banco.buscar(self.bruno)]
        texto = ctrl._texto_encerramento(pendentes)
        self.assertIn("Quem está com uma chave da portaria não recebe a saída "
                      "automática", texto)
        self.assertIn("Helena Souza (chave \"Laboratório 2\")", texto)
        self.assertNotIn("Bruno Almeida (chave", texto)

    def test_sem_chave_a_pergunta_nao_fala_de_chave(self):
        ctrl = self.app.tela_cadastro
        texto = ctrl._texto_encerramento([self.banco.buscar(self.bruno)])
        self.assertNotIn("chave", texto)


class TestExcluirPessoaComEncomenda(BaseLivros):
    """Achado do QA: excluir o cadastro deixava a encomenda pendente com o
    CPF de quem já não é do cadastro (ninguém conseguiria retirá-la)."""

    def setUp(self):
        super().setUp()
        self.eva = cpf_ficticio(987654321)
        self.id_eva = self.banco.cadastrar_pessoa(
            self.eva, "Eva Martins", "31987654321", "", "Funcionário", "ana")
        self.encomenda = self.banco.registrar_encomenda(
            "Eva Martins", "Correios", "paulo")

    def test_com_encomenda_aguardando_a_exclusao_e_recusada(self):
        self.assertEqual(
            self.erro(self.banco.excluir_pessoa, self.id_eva, "ana"),
            "Eva Martins tem 1 encomenda aguardando retirada.\nRegistre a "
            "retirada ou exclua a encomenda (Encomendas) antes de excluir o "
            "cadastro.")
        self.assertIsNotNone(self.banco.buscar_pessoa(self.eva))

    def test_depois_de_excluir_a_encomenda_exclui(self):
        self.banco.excluir_encomenda(self.encomenda, "ana")
        self.banco.excluir_pessoa(self.id_eva, "ana")
        self.assertIsNone(self.banco.buscar_pessoa(self.eva))
