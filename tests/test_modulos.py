"""
Os módulos da versão 3.2 no banco (dados_modulos.py, esquema v14): chaves,
encomendas, autorizações de entrada, funcionários, crachá, recados de turno,
privacidade (LGPD), histórico protegido e os dados de demonstração. Cada um
com o caminho certo, as recusas e a permissão conferida no banco.
"""
import os
import sqlite3
import unittest
from datetime import datetime, timedelta

from portaria import dados, validacao
from portaria.dados_modulos import ANONIMO, cpf_ficticio, hash_do_evento

from .test_dados import (objetos_do_banco, rebaixar_para_v13, registro,
                         versao_do_arquivo)
from .test_regras_no_banco import BaseRegras

ANA, BETO, CARLA = "52998224725", "11144477735", "39053344705"


def visita(**mudancas):
    r = registro(entrada="19/10/2026 09:00", placa="")
    r.update(mudancas)
    return r


class TestChaves(BaseRegras):
    def setUp(self):
        super().setUp()
        self.lab = self.banco.cadastrar_chave("Laboratório 2", "Bloco B", "ana")

    def chave(self):
        return self.banco.listar_chaves()[0]

    def test_cadastro_so_do_administrador(self):
        with self.assertRaises(dados.ErroDados):
            self.banco.cadastrar_chave("Auditório", "", "paulo")
        self.assertEqual(len(self.banco.listar_chaves()), 1)

    def test_nome_obrigatorio_com_limite_e_sem_repetir(self):
        for nome in ("", "   ", "x" * 41, "laboratório 2"):
            with self.subTest(nome=nome), self.assertRaises(dados.ErroDados):
                self.banco.cadastrar_chave(nome, "", "ana")

    def test_entregar_e_devolver(self):
        self.banco.entregar_chave(self.lab, "Carla Nogueira", "paulo", CARLA)
        c = self.chave()
        self.assertTrue(c["emprestada"])
        self.assertEqual((c["com_quem"], c["cpf"], c["entregue_por"]),
                         ("Carla Nogueira", CARLA, "paulo"))
        self.assertEqual(c["desde"], "19/10/2026 10:00")
        self.banco.devolver_chave(self.lab, "paulo")
        self.assertFalse(self.chave()["emprestada"])
        h = self.banco.historico_de_chaves()[0]
        self.assertEqual((h["chave"], h["nome"], h["recebida_por"]),
                         ("Laboratório 2", "Carla Nogueira", "paulo"))
        acoes = [e["acao"] for e in self.banco.listar_eventos()]
        self.assertIn("Chave entregue", acoes)
        self.assertIn("Chave devolvida", acoes)

    def test_chave_emprestada_nao_sai_de_novo(self):
        self.banco.entregar_chave(self.lab, "Carla Nogueira", "paulo")
        with self.assertRaises(dados.ErroDados) as erro:
            self.banco.entregar_chave(self.lab, "Beto Rocha", "paulo")
        self.assertIn("já está com Carla Nogueira", str(erro.exception))

    def test_o_banco_trava_duas_entregas_mesmo_sem_a_checagem(self):
        """Duas estações ao mesmo tempo: o índice único recusa a segunda."""
        self.banco.entregar_chave(self.lab, "Carla Nogueira", "paulo")
        con = sqlite3.connect(self.caminho)
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("INSERT INTO emprestimos_chave (chave_id, nome, "
                        "retirada_em, entregue_por) VALUES (?, 'X Y', "
                        "'2026-10-19 10:01', 'paulo')", (self.lab,))
        con.close()

    def test_quem_retira_precisa_de_nome_completo_e_cpf_valido_se_vier(self):
        for nome, cpf in (("", ""), ("Carla", ""), ("Carla 123", ""),
                          ("Carla Nogueira", "12345678900")):
            with self.subTest(nome=nome, cpf=cpf), \
                    self.assertRaises(dados.ErroDados):
                self.banco.entregar_chave(self.lab, nome, "paulo", cpf)
        self.assertFalse(self.chave()["emprestada"])

    def test_devolver_o_que_nao_esta_emprestado_e_recusado(self):
        with self.assertRaises(dados.ErroDados):
            self.banco.devolver_chave(self.lab, "paulo")

    def test_remover_so_admin_e_so_na_portaria(self):
        self.banco.entregar_chave(self.lab, "Carla Nogueira", "paulo")
        with self.assertRaises(dados.ErroDados):
            self.banco.desativar_chave(self.lab, "ana")       # emprestada
        self.banco.devolver_chave(self.lab, "paulo")
        with self.assertRaises(dados.ErroDados):
            self.banco.desativar_chave(self.lab, "paulo")     # porteiro
        self.banco.desativar_chave(self.lab, "ana")
        self.assertEqual(self.banco.listar_chaves(), [])
        self.assertEqual(len(self.banco.historico_de_chaves()), 1)  # fica
        with self.assertRaises(dados.ErroDados):
            self.banco.entregar_chave(self.lab, "Carla Nogueira", "paulo")

    def test_busca_e_so_emprestadas(self):
        self.banco.cadastrar_chave("Auditório", "Bloco A", "ana")
        self.banco.entregar_chave(self.lab, "Carla Nogueira", "paulo")
        self.assertEqual([c["nome"] for c in self.banco.listar_chaves()],
                         ["Laboratório 2", "Auditório"])     # emprestada 1º
        self.assertEqual(len(self.banco.listar_chaves(so_emprestadas=True)), 1)
        self.assertEqual(len(self.banco.listar_chaves("bloco a")), 1)
        self.assertEqual(len(self.banco.listar_chaves("carla")), 1)
        self.assertEqual(self.banco.listar_chaves("'; DROP TABLE chaves; --"), [])

    def test_sem_usuario_ativo_nada_e_gravado(self):
        for autor in (None, "ninguem"):
            with self.subTest(autor=autor), self.assertRaises(dados.ErroDados):
                self.banco.entregar_chave(self.lab, "Carla Nogueira", autor)


class TestEncomendas(BaseRegras):
    def nova(self, **mudancas):
        dados_ = {"destinatario": "Helena Souza", "remetente": "Correios",
                  "autor": "paulo", "setor": "Secretaria",
                  "descricao": "Envelope"}
        dados_.update(mudancas)
        return self.banco.registrar_encomenda(**dados_)

    def test_registrar_e_retirar(self):
        id_ = self.nova()
        e = self.banco.listar_encomendas()[0]
        self.assertEqual((e["destinatario"], e["remetente"], e["recebida_por"],
                          e["recebida_em"], e["retirada_em"]),
                         ("Helena Souza", "Correios", "paulo",
                          "19/10/2026 10:00", ""))
        self.banco.retirar_encomenda(id_, "Helena Souza", "paulo", ANA)
        e = self.banco.listar_encomendas()[0]
        self.assertEqual((e["retirada_nome"], e["retirada_cpf"],
                          e["entregue_por"]), ("Helena Souza", ANA, "paulo"))
        self.assertEqual(self.banco.listar_encomendas(so_pendentes=True), [])

    def test_campos_obrigatorios_e_limites(self):
        for mudanca in ({"destinatario": ""}, {"remetente": "  "},
                        {"destinatario": "x" * 81}, {"descricao": "x" * 201},
                        {"setor": "x" * 61}):
            with self.subTest(mudanca=mudanca), \
                    self.assertRaises(dados.ErroDados):
                self.nova(**mudanca)
        self.assertEqual(self.banco.listar_encomendas(), [])

    def test_nao_se_retira_duas_vezes(self):
        id_ = self.nova()
        self.banco.retirar_encomenda(id_, "Helena Souza", "paulo")
        with self.assertRaises(dados.ErroDados):
            self.banco.retirar_encomenda(id_, "Outra Pessoa", "ana")
        self.assertEqual(self.banco.listar_encomendas()[0]["retirada_nome"],
                         "Helena Souza")

    def test_excluir_so_administrador(self):
        id_ = self.nova()
        with self.assertRaises(dados.ErroDados):
            self.banco.excluir_encomenda(id_, "paulo")
        self.banco.excluir_encomenda(id_, "ana")
        self.assertEqual(self.banco.listar_encomendas(), [])
        self.assertEqual(self.banco.listar_eventos()[0]["acao"],
                         "Encomenda excluída")

    def test_pendentes_primeiro_e_busca(self):
        a = self.nova()
        self.nova(destinatario="Rafael Lima", remetente="Kalunga")
        self.banco.retirar_encomenda(a, "Helena Souza", "paulo")
        self.assertEqual([e["destinatario"] for e in
                          self.banco.listar_encomendas()],
                         ["Rafael Lima", "Helena Souza"])
        self.assertEqual(len(self.banco.listar_encomendas("kalunga")), 1)

    def test_cpf_na_descricao_vai_mascarado(self):
        self.nova(descricao="Documento do CPF 529.982.247-25")
        self.assertNotIn("529.982.247-25",
                         self.banco.listar_encomendas()[0]["descricao"])


class TestAutorizacoes(BaseRegras):
    def criar(self, **mudancas):
        campos = {"cpf": ANA, "nome": "Ana Silva", "empresa": "Alfa Ltda",
                  "motivo": "Reunião", "anfitriao": "Diretoria",
                  "valida_de": "19/10/2026", "valida_ate": "21/10/2026",
                  "autor": "paulo"}
        campos.update(mudancas)
        return self.banco.criar_autorizacao(**campos)

    def test_criar_e_situacoes(self):
        valida = self.criar()
        futura = self.criar(cpf=BETO, nome="Beto Rocha",
                            valida_de="20/10/2026")
        situacoes = {a["id"]: a["situacao"]
                     for a in self.banco.listar_autorizacoes()}
        self.assertEqual(situacoes, {valida: validacao.AUT_VALIDA,
                                     futura: validacao.AUT_FUTURA})
        self.banco.cancelar_autorizacao(valida, "ana")
        self.assertEqual(self.banco.buscar_autorizacao(valida)["situacao"],
                         validacao.AUT_CANCELADA)
        self.AGORA = datetime(2026, 10, 25, 10, 0)
        self.addCleanup(setattr, type(self), "AGORA", BaseRegras.AGORA)
        self.assertEqual(self.banco.buscar_autorizacao(futura)["situacao"],
                         validacao.AUT_VENCIDA)

    def test_validacao(self):
        casos = ({"cpf": "12345678900"}, {"cpf": ""}, {"nome": "Ana"},
                 {"motivo": ""}, {"anfitriao": "  "},
                 {"valida_de": "21/10/2026", "valida_ate": "20/10/2026"},
                 {"valida_de": "01/10/2026", "valida_ate": "10/10/2026"},
                 {"valida_ate": "31/12/2027"}, {"valida_de": "31/02/2026"},
                 {"valida_ate": "amanhã"}, {"motivo": "x" * 201})
        for mudanca in casos:
            with self.subTest(mudanca=mudanca), \
                    self.assertRaises(dados.ErroDados):
                self.criar(**mudanca)
        self.assertEqual(self.banco.listar_autorizacoes(), [])

    def test_autorizacao_valida_do_dia(self):
        self.assertIsNone(self.banco.autorizacao_valida(ANA))
        id_ = self.criar()
        self.assertEqual(self.banco.autorizacao_valida(ANA)["id"], id_)
        self.assertIsNone(self.banco.autorizacao_valida(BETO))
        self.banco.cancelar_autorizacao(id_, "paulo")
        self.assertIsNone(self.banco.autorizacao_valida(ANA))

    def test_entrada_conta_como_uso(self):
        id_ = self.criar()
        self.banco.inserir(visita(), autor="paulo")
        a = self.banco.buscar_autorizacao(id_)
        self.assertEqual((a["usos"], a["ultimo_uso"]), (1, "19/10/2026 09:00"))
        self.assertIn("Entrada com autorização",
                      [e["acao"] for e in self.banco.listar_eventos()])
        self.banco.inserir(visita(cpf=BETO, nome="Beto Rocha"), autor="paulo")
        self.assertEqual(self.banco.buscar_autorizacao(id_)["usos"], 1)

    def test_cancelar_duas_vezes_e_recusado(self):
        id_ = self.criar()
        self.banco.cancelar_autorizacao(id_, "paulo")
        with self.assertRaises(dados.ErroDados):
            self.banco.cancelar_autorizacao(id_, "ana")

    def test_emissao_fica_no_historico(self):
        id_ = self.criar()
        self.banco.registrar_emissao(id_, "paulo")
        self.assertEqual(self.banco.buscar_autorizacao(id_)["emissoes"], 1)
        self.assertEqual(self.banco.listar_eventos()[0]["acao"],
                         "Autorização de entrada emitida")
        with self.assertRaises(dados.ErroDados):
            self.banco.registrar_emissao(9999, "paulo")

    def test_porteiro_so_acha_o_cpf_inteiro(self):
        self.criar()
        self.assertEqual(len(self.banco.listar_autorizacoes(ANA)), 1)
        self.assertEqual(len(self.banco.listar_autorizacoes("5299")), 1)
        self.assertEqual(self.banco.listar_autorizacoes(
            "5299", so_cpf_completo=True), [])
        self.assertEqual(len(self.banco.listar_autorizacoes(
            ANA, so_cpf_completo=True)), 1)
        self.assertEqual(len(self.banco.listar_autorizacoes("diretoria")), 1)
        self.assertEqual(len(self.banco.listar_autorizacoes(so_validas=True)), 1)


class TestFuncionarios(BaseRegras):
    def setUp(self):
        super().setUp()
        self.banco.cadastrar_pessoa(ANA, "Ana Silva", "31987654321", "",
                                    "Funcionário", "ana")
        self.banco.cadastrar_pessoa(BETO, "Beto Rocha", "31987654321", "",
                                    "Aluno", "ana")
        self.ana = self.banco.buscar_pessoa(ANA)["id"]
        self.beto = self.banco.buscar_pessoa(BETO)["id"]

    def test_salvar_e_listar(self):
        self.banco.salvar_funcionario(self.ana, "F-0012", "Secretaria",
                                      "Assistente", "paulo")
        f = self.banco.listar_funcionarios()
        self.assertEqual(len(f), 1)                    # só quem é Funcionário
        self.assertEqual((f[0]["matricula"], f[0]["setor"], f[0]["cargo"]),
                         ("F-0012", "Secretaria", "Assistente"))
        self.assertEqual(self.banco.buscar_pessoa(ANA)["setor"], "Secretaria")
        self.assertEqual(self.banco.listar_eventos()[0]["acao"],
                         "Dados de funcionário alterados")
        self.assertEqual(len(self.banco.listar_funcionarios("secret")), 1)
        self.assertEqual(self.banco.listar_funcionarios("zzz"), [])

    def test_quem_nao_e_funcionario_e_recusado(self):
        with self.assertRaises(dados.ErroDados):
            self.banco.salvar_funcionario(self.beto, "F-1", "", "", "ana")

    def test_matricula_nao_se_repete_e_tem_formato(self):
        self.banco.cadastrar_pessoa(CARLA, "Carla Nogueira", "31987654321", "",
                                    "Funcionário", "ana")
        carla = self.banco.buscar_pessoa(CARLA)["id"]
        self.banco.salvar_funcionario(self.ana, "F-0012", "", "", "ana")
        for matricula in ("F-0012", "F 12!", "x" * 21):
            with self.subTest(matricula=matricula), \
                    self.assertRaises(dados.ErroDados):
                self.banco.salvar_funcionario(carla, matricula, "", "", "ana")
        self.banco.salvar_funcionario(carla, "", "", "", "ana")   # vazia pode

    def test_ponto_de_hoje(self):
        self.assertEqual(self.banco.listar_funcionarios()[0]["dentro_desde"], "")
        id_ = self.banco.inserir(visita(tipo="Funcionário", nome="Ana Silva"),
                                 autor="paulo")
        f = self.banco.listar_funcionarios()[0]
        self.assertEqual((f["entrada_hoje"], f["dentro_desde"]),
                         ("19/10/2026 09:00", "19/10/2026 09:00"))
        self.banco.registrar_saidas([id_], "19/10/2026 09:50", autor="paulo")
        f = self.banco.listar_funcionarios()[0]
        self.assertEqual((f["saida_hoje"], f["dentro_desde"]),
                         ("19/10/2026 09:50", ""))


class TestCrachaEAnfitriao(BaseRegras):
    def test_visita_guarda_quem_procura_e_o_cracha(self):
        id_ = self.banco.inserir(visita(anfitriao="Coordenação", cracha="7"),
                                 autor="paulo")
        r = self.banco.buscar(id_)
        self.assertEqual((r["anfitriao"], r["cracha"]), ("Coordenação", "7"))
        self.assertEqual(self.banco.crachas_em_uso(), ["7"])

    def test_cracha_nao_fica_com_duas_pessoas(self):
        self.banco.inserir(visita(cracha="7"), autor="paulo")
        with self.assertRaises(dados.ErroDados) as erro:
            self.banco.inserir(visita(cpf=BETO, nome="Beto Rocha", cracha="7"),
                               autor="paulo")
        self.assertIn("O crachá 7 está com", str(erro.exception))
        self.assertEqual(len(self.banco.listar()), 1)

    def test_cracha_volta_a_ficar_livre_na_saida(self):
        id_ = self.banco.inserir(visita(cracha="7"), autor="paulo")
        self.banco.registrar_saidas([id_], "19/10/2026 09:30", autor="paulo")
        self.assertEqual(self.banco.crachas_em_uso(), [])
        self.banco.inserir(visita(cpf=BETO, nome="Beto Rocha", cracha="7",
                                  entrada="19/10/2026 09:40"), autor="paulo")

    def test_desfazer_a_saida_nao_rouba_o_cracha_de_quem_pegou_depois(self):
        id_ = self.banco.inserir(visita(cracha="7"), autor="paulo")
        self.banco.registrar_saidas([id_], "19/10/2026 09:30", autor="paulo")
        self.banco.inserir(visita(cpf=BETO, nome="Beto Rocha", cracha="7",
                                  entrada="19/10/2026 09:40"), autor="paulo")
        self.banco.desfazer_saidas([id_], autor="paulo")
        self.assertEqual(self.banco.buscar(id_)["cracha"], "")
        self.assertEqual(self.banco.crachas_em_uso(), ["7"])

    def test_cracha_invalido_e_limite_de_quem_procura(self):
        for mudanca in ({"cracha": "abc"}, {"cracha": "1000"},
                        {"anfitriao": "x" * 61}):
            r = validacao.normalizar("Ana Silva", ANA, "31987654321", "",
                                     "Aluno", "19/10/2026 09:00", "",
                                     **{"anfitriao": "", "cracha": "",
                                        **mudanca})
            with self.subTest(mudanca=mudanca):
                self.assertFalse(validacao.validar_campos(r)[0])
        self.assertEqual(validacao.normalizar(
            "Ana Silva", ANA, "31987654321", "", "Aluno", "19/10/2026 09:00",
            "", cracha=" 007 ")["cracha"], "7")

    def test_corrigir_mantem_ou_troca_o_cracha(self):
        id_ = self.banco.inserir(visita(cracha="7"), autor="ana")
        outra = self.banco.inserir(visita(cpf=BETO, nome="Beto Rocha",
                                          cracha="8"), autor="ana")
        original = self.banco.buscar(id_)
        novo = dict(original, nome="João Avila")
        novo.pop("cracha")                              # sem a chave: fica
        self.banco.editar(id_, novo, ["Nome"], "ana", original=original)
        self.assertEqual(self.banco.buscar(id_)["cracha"], "7")
        with self.assertRaises(dados.ErroDados):        # o 8 está com o Beto
            self.banco.editar(id_, dict(self.banco.buscar(id_), cracha="8"),
                              ["Crachá"], "ana")
        del outra


class TestRecados(BaseRegras):
    def test_deixar_listar_e_marcar_como_lido(self):
        id_ = self.banco.deixar_recado("O portão lateral fica fechado.", "paulo")
        r = self.banco.listar_recados(so_nao_lidos=True)[0]
        self.assertEqual((r["id"], r["autor"], r["lido_em"]), (id_, "paulo", ""))
        self.banco.marcar_recado_lido(id_, "ana")
        self.assertEqual(self.banco.listar_recados(so_nao_lidos=True), [])
        self.assertEqual(self.banco.listar_recados()[0]["lido_por"], "ana")
        with self.assertRaises(dados.ErroDados):
            self.banco.marcar_recado_lido(id_, "paulo")

    def test_recado_vazio_curto_ou_longo_e_recusado(self):
        for texto in ("", "oi", "x" * 501):
            with self.subTest(texto=texto), self.assertRaises(dados.ErroDados):
                self.banco.deixar_recado(texto, "paulo")

    def test_cpf_no_recado_vai_mascarado(self):
        self.banco.deixar_recado("Liberar o CPF 529.982.247-25 amanhã.", "paulo")
        self.assertNotIn("529.982.247-25",
                         self.banco.listar_recados()[0]["texto"])


class TestLetra(BaseRegras):
    def test_cada_usuario_tem_a_sua(self):
        self.assertEqual(self.banco.letra_do_usuario("paulo"), "normal")
        self.banco.definir_letra("grande", "paulo")
        self.assertEqual(self.banco.letra_do_usuario("paulo"), "grande")
        self.assertEqual(self.banco.letra_do_usuario("ana"), "normal")
        with self.assertRaises(dados.ErroDados):
            self.banco.definir_letra("gigante", "paulo")


class TestPrivacidade(BaseRegras):
    def setUp(self):
        super().setUp()
        self.visita = self.banco.inserir(
            visita(entrada="19/10/2026 08:00", saida="19/10/2026 09:00",
                   empresa="Alfa", motivo="Reunião", placa="ABC1D23"),
            autor="paulo")
        self.pessoa = self.banco.buscar_pessoa(ANA)["id"]

    def anonimizar(self, autor="ana"):
        self.banco.anonimizar_pessoa(self.pessoa, "Pedido do titular por "
                                                  "e-mail", autor)

    def test_anonimizar_troca_os_dados_e_mantem_a_visita(self):
        self.anonimizar()
        self.assertIsNone(self.banco.buscar_pessoa(ANA))
        r = self.banco.buscar(self.visita)
        self.assertEqual((r["nome"], r["celular"], r["placa"], r["empresa"],
                          r["motivo"]), (ANONIMO, "", "", "", ""))
        self.assertTrue(validacao.anonimizado(r["cpf"]))
        self.assertEqual(validacao.formatar_cpf(r["cpf"]), "anonimizado")
        self.assertEqual(validacao.mascarar_cpf(r["cpf"]), "anonimizado")
        self.assertEqual(len(self.banco.listar()), 1)       # a contagem fica
        evento = self.banco.listar_eventos()[0]
        self.assertEqual(evento["acao"], "Pessoa anonimizada")
        self.assertNotIn("João", evento["detalhe"])
        con = sqlite3.connect(self.caminho)
        sobra = con.execute("SELECT COUNT(*) FROM placas_pessoa").fetchone()[0]
        con.close()
        self.assertEqual(sobra, 0)

    def test_so_administrador_e_com_justificativa(self):
        with self.assertRaises(dados.ErroDados):
            self.anonimizar("paulo")
        with self.assertRaises(dados.ErroDados):
            self.banco.anonimizar_pessoa(self.pessoa, "curta", "ana")
        self.assertIsNotNone(self.banco.buscar_pessoa(ANA))

    def test_quem_esta_dentro_ou_desativado_nao_e_anonimizado(self):
        self.banco.inserir(visita(entrada="19/10/2026 09:30"), autor="paulo")
        with self.assertRaises(dados.ErroDados) as erro:
            self.anonimizar()
        self.assertIn("está dentro", str(erro.exception))
        self.banco.registrar_saidas(
            [r["id"] for r in self.banco.listar() if not r["saida"]],
            "19/10/2026 09:40", autor="paulo")
        self.banco.desativar("cpf", ANA, "Motivo válido", "ana")
        with self.assertRaises(dados.ErroDados) as erro:
            self.anonimizar()
        self.assertIn("desativada", str(erro.exception))

    def test_anonimizar_duas_vezes_e_recusado(self):
        self.anonimizar()
        with self.assertRaises(dados.ErroDados):
            self.anonimizar()

    def test_o_mesmo_cpf_pode_voltar_como_pessoa_nova(self):
        self.anonimizar()
        self.banco.inserir(visita(entrada="19/10/2026 09:30"), autor="paulo")
        nova = self.banco.buscar_pessoa(ANA)
        self.assertEqual(nova["visitas"], 1)
        self.assertNotEqual(nova["id"], self.pessoa)

    def test_prazo_de_guarda(self):
        self.banco.inserir(visita(cpf=BETO, nome="Beto Rocha",
                                  entrada="19/10/2026 09:30"), autor="paulo")
        self.assertEqual(self.banco.contar_fora_do_prazo(12), 0)
        self.AGORA = datetime(2027, 12, 1, 10, 0)
        self.addCleanup(setattr, type(self), "AGORA", BaseRegras.AGORA)
        # Ana saiu há mais de 12 meses; Beto continua dentro: fica
        self.assertEqual(self.banco.contar_fora_do_prazo(12), 1)
        with self.assertRaises(dados.ErroDados):
            self.banco.aplicar_retencao(12, "paulo")
        self.assertEqual(self.banco.aplicar_retencao(12, "ana"), 1)
        self.assertIsNone(self.banco.buscar_pessoa(ANA))
        self.assertIsNotNone(self.banco.buscar_pessoa(BETO))
        self.assertEqual(self.banco.aplicar_retencao(12, "ana"), 0)

    def test_prazo_invalido(self):
        for meses in (-1, 121, "12", 1.5, True):
            with self.subTest(meses=meses), self.assertRaises(dados.ErroDados):
                self.banco.contar_fora_do_prazo(meses)
        with self.assertRaises(dados.ErroDados):
            self.banco.aplicar_retencao(0, "ana")


class TestAnonimizadoNaoVolta(BaseRegras):
    """Achado pelas sequências aleatórias da 3.2: depois de anonimizar,
    nenhuma operação devolve dados pessoais à pessoa ou às visitas dela."""

    def setUp(self):
        super().setUp()
        self.id_visita = self.banco.inserir(
            visita(entrada="19/10/2026 08:00", saida="19/10/2026 09:00",
                   tipo="Funcionário"), autor="paulo")
        self.pessoa = self.banco.buscar_pessoa(ANA)["id"]
        self.banco.anonimizar_pessoa(self.pessoa, "Pedido do titular por "
                                     "e-mail", "ana")

    def test_desfazer_a_saida_nao_reabre_a_visita(self):
        self.assertEqual(self.banco.desfazer_saidas([self.id_visita],
                                                    autor="paulo"), 0)
        self.assertNotEqual(self.banco.buscar(self.id_visita)["saida"], "")

    def test_corrigir_a_visita_e_recusado(self):
        original = self.banco.buscar(self.id_visita)
        novo = dict(original, nome="Maria Souza", cpf=ANA)
        with self.assertRaisesRegex(dados.ErroDados, "anonimizada"):
            self.banco.editar(self.id_visita, novo, ["nome"], "ana",
                              original=original)
        self.assertEqual(self.banco.buscar(self.id_visita)["nome"],
                         "Pessoa anonimizada")

    def test_nao_vira_funcionario_de_novo(self):
        with self.assertRaisesRegex(dados.ErroDados, "não existe mais"):
            self.banco.salvar_funcionario(self.pessoa, "F-1", "Secretaria",
                                          "Técnica", "ana")

    def test_o_cadastro_nao_e_mais_alteravel(self):
        with self.assertRaisesRegex(dados.ErroDados, "não está mais cadastrada"):
            self.banco.atualizar_pessoa(self.pessoa, "Maria Souza",
                                        "31999990000", "", "Visitante",
                                        autor="ana")


class TestHistoricoProtegido(BaseRegras):
    def setUp(self):
        super().setUp()
        self.banco.inserir(visita(), autor="paulo")
        self.banco.registrar_ocorrencia("Outra", "Texto suficiente", "paulo")

    def sql(self, comando):
        con = sqlite3.connect(self.caminho)
        con.execute(comando)
        con.commit()
        con.close()

    def test_historico_integro(self):
        estado = self.banco.verificar_historico()
        self.assertTrue(estado["integro"])
        self.assertIsNone(estado["primeiro_alterado"])
        self.assertEqual(estado["total"], len(self.banco.listar_eventos()))

    def test_evento_alterado_por_fora_e_achado(self):
        self.sql("UPDATE auditoria SET detalhe = 'outra coisa' WHERE id = 2")
        estado = self.banco.verificar_historico()
        self.assertFalse(estado["integro"])
        self.assertEqual(estado["primeiro_alterado"], 2)

    def test_evento_apagado_do_meio_e_achado(self):
        self.sql("DELETE FROM auditoria WHERE id = 2")
        estado = self.banco.verificar_historico()
        self.assertFalse(estado["integro"])
        self.assertEqual(estado["primeiro_alterado"], 3)

    def test_trocar_o_autor_tambem_quebra(self):
        self.sql("UPDATE auditoria SET usuario = 'outro' WHERE id = 3")
        self.assertEqual(self.banco.verificar_historico()["primeiro_alterado"], 3)

    def test_eventos_novos_continuam_a_corrente(self):
        for i in range(5):
            self.banco.registrar_ocorrencia("Outra", f"Texto número {i}", "ana")
        self.assertTrue(self.banco.verificar_historico()["integro"])

    def test_o_elo_depende_do_anterior(self):
        a = hash_do_evento("", "m", "u", "a", "d", None)
        self.assertNotEqual(a, hash_do_evento(a, "m", "u", "a", "d", None))
        self.assertNotEqual(a, hash_do_evento("", "m", "u", "a", "d", 1))
        self.assertEqual(len(a), 64)


class TestDemonstracao(BaseRegras):
    def test_so_administrador(self):
        with self.assertRaises(dados.ErroDados):
            self.banco.preencher_demonstracao("paulo")
        self.assertEqual(self.banco.listar(), [])

    def test_enche_o_banco_com_dados_coerentes(self):
        feito = self.banco.preencher_demonstracao("ana")
        self.assertEqual(feito["pessoas"], 12)
        self.assertGreater(feito["visitas"], 20)
        self.assertEqual((feito["chaves"], feito["encomendas"],
                          feito["autorizações"], feito["ocorrências"]),
                         (4, 3, 2, 3))
        pessoas = self.banco.listar_pessoas()
        self.assertEqual(len(pessoas), 12)
        self.assertTrue(all(validacao.cpf_valido(p["cpf"]) for p in pessoas))
        dentro = [r for r in self.banco.listar() if not r["saida"]]
        self.assertGreater(len(dentro), 3)
        self.assertEqual(len({r["cpf"] for r in dentro}), len(dentro))
        self.assertEqual(len(self.banco.listar_chaves(so_emprestadas=True)), 1)
        self.assertEqual(len(self.banco.listar_recados()), 1)
        con = sqlite3.connect(self.caminho)
        self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0],
                         "ok")
        futuro = con.execute("SELECT COUNT(*) FROM registros WHERE entrada > ?",
                             (self.AGORA.strftime("%Y-%m-%d %H:%M"),)
                             ).fetchone()[0]
        con.close()
        self.assertEqual(futuro, 0)
        self.assertTrue(self.banco.verificar_historico()["integro"])
        self.assertEqual(self.banco.listar_eventos()[0]["acao"],
                         "Dados de demonstração inseridos")

    def test_carro_de_quem_esta_dentro_fica_no_estacionamento(self):
        self.banco.preencher_demonstracao("ana")
        placas = {r["placa"] for r in self.banco.listar()
                  if not r["saida"] and r["placa"]}
        self.assertTrue(placas)
        for placa in placas:
            self.assertIsNotNone(self.banco.estadia_aberta(placa=placa), placa)

    def test_rodar_de_novo_nao_duplica(self):
        self.banco.preencher_demonstracao("ana")
        antes = len(self.banco.listar())
        feito = self.banco.preencher_demonstracao("ana")
        self.assertEqual((feito["pessoas"], feito["visitas"], feito["chaves"]),
                         (0, 0, 0))
        self.assertEqual(len(self.banco.listar()), antes)

    def test_cpf_ficticio_e_valido(self):
        for base in (1, 123456789, 987654321):
            self.assertTrue(validacao.cpf_valido(cpf_ficticio(base)), base)


class TestMigracaoV14(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.caminho = os.path.join(self.pasta.name, "portaria.db")

    def test_banco_da_3_1_ganha_os_modulos_sem_perder_nada(self):
        from portaria.senhas import gerar_hash
        banco = dados.Banco(self.caminho)
        banco.criar_usuario("Ana Admin", "ana", "admin", gerar_hash("senha123"))
        banco.inserir(registro(), autor="ana")
        banco.registrar_ocorrencia("Outra", "Texto suficiente", "ana")
        eventos = len(banco.listar_eventos())
        del banco
        rebaixar_para_v13(self.caminho)
        self.assertEqual(versao_do_arquivo(self.caminho), 13)
        self.assertNotIn("chaves", objetos_do_banco(self.caminho))

        banco = dados.Banco(self.caminho)
        self.assertEqual(versao_do_arquivo(self.caminho), dados.VERSAO_ESQUEMA)
        objetos = objetos_do_banco(self.caminho)
        for nome in ("chaves", "emprestimos_chave", "encomendas",
                     "autorizacoes_entrada", "recados_turno",
                     "idx_cracha_em_uso", "idx_chave_emprestada"):
            self.assertIn(nome, objetos)
        self.assertEqual(len(banco.listar()), 1)
        self.assertEqual(banco.listar()[0]["cracha"], "")
        self.assertEqual(len(banco.listar_eventos()), eventos)
        # o histórico antigo ganhou a corrente na migração
        self.assertTrue(banco.verificar_historico()["integro"])
        self.assertEqual(banco.letra_do_usuario("ana"), "normal")
        self.assertTrue(any("antes-v14-de-v13" in f for f in
                            os.listdir(os.path.join(self.pasta.name,
                                                    "backups"))))

    def test_migrar_duas_vezes_nao_estraga(self):
        dados.Banco(self.caminho)
        rebaixar_para_v13(self.caminho)
        dados.Banco(self.caminho)
        con = sqlite3.connect(self.caminho)
        con.execute("PRAGMA user_version = 13")
        con.execute("UPDATE meta SET valor = 13 WHERE chave = 'versao_esquema'")
        con.commit()
        con.close()
        dados.Banco(self.caminho)                       # roda o passo de novo
        self.assertEqual(versao_do_arquivo(self.caminho), dados.VERSAO_ESQUEMA)


if __name__ == "__main__":
    unittest.main()
