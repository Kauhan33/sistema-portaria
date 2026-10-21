import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta
from unittest import mock

from portaria import dados
from portaria.consultas import filtrar, resumo
from portaria.validacao import FORMATO


def registro(**mudancas):
    r = {"nome": "João Ávila", "cpf": "52998224725", "celular": "31987654321",
         "placa": "ABC1D23", "tipo": "Funcionário",
         "entrada": "16/10/2026 08:00", "saida": ""}
    r.update(mudancas)
    return r


class BaseTemp(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho_db = os.path.join(self.pasta.name, "portaria.db")
        self.caminho_json = os.path.join(self.pasta.name, "registros_portaria.json")
        self.banco = dados.Banco(self.caminho_db)

    def tearDown(self):
        self.pasta.cleanup()   # falha se alguma conexão ficou aberta

    def criar_equipe(self):
        """ana e bia (administradoras) e paulo (porteiro): as operações
        com autor conferem o perfil dele no banco. A ana é o primeiro
        acesso (sem autor); ela cria as outras."""
        self.banco.criar_usuario("Ana Admin", "ana", "admin", "hash-falso")
        for nome, login, perfil in [("Bia Admin", "bia", "admin"),
                                    ("Paulo Porteiro", "paulo", "porteiro")]:
            self.banco.criar_usuario(nome, login, perfil, "hash-falso",
                                     autor="ana")

    def escrever_json(self, conteudo):
        with open(self.caminho_json, "w", encoding="utf-8") as f:
            f.write(conteudo if isinstance(conteudo, str)
                    else json.dumps(conteudo, ensure_ascii=False))


class TestBanco(BaseTemp):
    def test_banco_novo_comeca_vazio_com_versao_do_esquema(self):
        self.assertEqual(self.banco.listar(), [])
        con = sqlite3.connect(self.caminho_db)
        versao = con.execute("PRAGMA user_version").fetchone()[0]
        con.close()
        self.assertEqual(versao, dados.VERSAO_ESQUEMA)

    def test_inserir_e_listar_mantem_acentos_e_formato_da_tela(self):
        id_ = self.banco.inserir(registro())
        self.assertEqual(self.banco.listar(), [dict(registro(), id=id_)])

    def test_datas_ficam_em_iso_no_banco(self):
        self.banco.inserir(registro(saida="16/10/2026 09:30"))
        con = sqlite3.connect(self.caminho_db)
        linha = con.execute("SELECT entrada, saida FROM registros").fetchone()
        con.close()
        self.assertEqual(linha, ("2026-10-16 08:00", "2026-10-16 09:30"))

    def test_lista_na_ordem_de_cadastro(self):
        self.banco.inserir(registro(nome="Primeiro Cadastro", entrada="16/10/2026 10:00"))
        self.banco.inserir(registro(nome="Segundo Cadastro", cpf="11144477735",
                                    entrada="15/10/2026 10:00"))
        nomes = [r["nome"] for r in self.banco.listar()]
        self.assertEqual(nomes, ["Primeiro Cadastro", "Segundo Cadastro"])

    def test_registrar_saida(self):
        id_ = self.banco.inserir(registro())
        self.banco.registrar_saida(id_, "16/10/2026 11:15")
        self.assertEqual(self.banco.listar()[0]["saida"], "16/10/2026 11:15")

    def test_excluir_varios(self):
        self.criar_equipe()
        ids = [self.banco.inserir(registro(cpf=c))
               for c in ("52998224725", "11144477735", "39053344705")]
        self.banco.excluir(ids[:2], autor="ana")
        self.assertEqual([r["id"] for r in self.banco.listar()], [ids[2]])

    def test_banco_recusa_saida_antes_da_entrada(self):
        # regra RN04 garantida também pelo próprio banco (CHECK)
        with self.assertRaises(dados.ErroDados):
            self.banco.inserir(registro(saida="16/10/2026 07:00"))
        self.assertEqual(self.banco.listar(), [])

    def test_banco_recusa_cpf_incompleto(self):
        with self.assertRaises(dados.ErroDados):
            self.banco.inserir(registro(cpf="123"))

    def test_dados_continuam_ao_reabrir(self):
        self.banco.inserir(registro())
        self.assertEqual(len(dados.Banco(self.caminho_db).listar()), 1)


class TestSaidas(BaseTemp):
    def setUp(self):
        super().setUp()
        self.criar_equipe()

    def entrar(self, cpf, entrada="16/10/2026 08:00"):
        return self.banco.inserir(registro(cpf=cpf, entrada=entrada))

    def saidas(self):
        return {r["id"]: r["saida"] for r in self.banco.listar()}

    def eventos_de_saida(self):
        return sum(1 for e in self.banco.listar_eventos()
                   if e["acao"] == "Saída registrada")

    def test_saida_de_varios_de_uma_vez(self):
        a, b = self.entrar("52998224725"), self.entrar("11144477735")
        self.banco.registrar_saidas([a, b], "16/10/2026 09:00", autor="paulo")
        self.assertEqual(self.saidas(), {a: "16/10/2026 09:00",
                                         b: "16/10/2026 09:00"})
        self.assertEqual(self.eventos_de_saida(), 2)

    def test_nao_sobrescreve_saida_ja_registrada(self):
        a = self.entrar("52998224725")
        self.banco.registrar_saida(a, "16/10/2026 09:00", autor="paulo")
        self.banco.registrar_saida(a, "16/10/2026 10:00", autor="paulo")
        self.assertEqual(self.saidas()[a], "16/10/2026 09:00")
        self.assertEqual(self.eventos_de_saida(), 1)

    def test_desfazer_saida(self):
        a = self.entrar("52998224725")
        self.banco.registrar_saida(a, "16/10/2026 09:00")
        self.assertEqual(self.banco.desfazer_saidas([a], autor="paulo"), 1)
        self.assertEqual(self.saidas()[a], "")
        self.assertEqual(self.banco.listar_eventos()[0]["acao"], "Saída desfeita")

    def test_nao_desfaz_se_a_pessoa_ja_entrou_de_novo(self):
        a = self.entrar("52998224725")
        self.banco.registrar_saida(a, "16/10/2026 09:00")
        self.entrar("52998224725", entrada="16/10/2026 09:05")
        self.assertEqual(self.banco.desfazer_saidas([a]), 0)
        self.assertEqual(self.saidas()[a], "16/10/2026 09:00")

    def test_saida_devolve_so_os_ids_que_gravou(self):  # B3
        a, b = self.entrar("52998224725"), self.entrar("11144477735")
        self.banco.registrar_saida(a, "16/10/2026 09:00", autor="bia")  # outra estação
        self.banco.excluir([b], autor="bia")
        c = self.entrar("39053344705")
        self.assertEqual(self.banco.registrar_saidas([a, b, c], "16/10/2026 10:00",
                                                     autor="paulo"), [c])
        self.assertFalse(self.banco.registrar_saida(a, "16/10/2026 10:30"))
        self.assertEqual(self.saidas()[a], "16/10/2026 09:00")

    def test_desfazer_so_a_saida_com_o_horario_gravado(self):  # B3
        a = self.entrar("52998224725")
        self.banco.registrar_saida(a, "16/10/2026 09:00", autor="bia")
        self.assertEqual(self.banco.desfazer_saidas(
            [a], autor="paulo", saida="16/10/2026 10:00"), 0)
        self.assertEqual(self.saidas()[a], "16/10/2026 09:00")
        self.assertEqual(self.banco.desfazer_saidas(
            [a], autor="bia", saida="16/10/2026 09:00"), 1)

    def test_nao_desfaz_se_ha_visita_encerrada_depois(self):
        a = self.entrar("52998224725")
        self.banco.registrar_saida(a, "16/10/2026 09:00")
        b = self.entrar("52998224725", entrada="16/10/2026 09:05")
        self.banco.registrar_saida(b, "16/10/2026 09:30")
        self.assertEqual(self.banco.desfazer_saidas([a]), 0)


class TestEdicao(BaseTemp):
    def setUp(self):
        super().setUp()
        self.criar_equipe()

    def corrigir(self, id_, **mudancas):
        antes = self.banco.buscar(id_)
        novo = {k: v for k, v in antes.items() if k != "id"}
        novo.update(mudancas)
        self.banco.editar(id_, novo, [f"{k} alterado" for k in mudancas],
                          autor="ana")
        return self.banco.buscar(id_)

    def test_corrige_e_guarda_no_historico_do_registro(self):
        id_ = self.banco.inserir(registro(), autor="paulo")
        depois = self.corrigir(id_, nome="João Ávila Neto", celular="31911112222")
        self.assertEqual((depois["nome"], depois["celular"]),
                         ("João Ávila Neto", "31911112222"))
        eventos = self.banco.eventos_do_registro(id_)
        self.assertEqual([e["acao"] for e in eventos],
                         ["Cadastro de entrada", "Registro corrigido"])
        self.assertIn("nome alterado; celular alterado", eventos[1]["detalhe"])
        self.assertEqual(self.banco.eventos_do_registro(999), [])

    def test_visita_mais_recente_atualiza_a_pessoa(self):
        self.banco.inserir(registro(entrada="15/10/2026 08:00",
                                    saida="15/10/2026 09:00"))
        recente = self.banco.inserir(registro())
        self.corrigir(recente, celular="31911112222")
        self.assertEqual(self.banco.buscar_pessoa("52998224725")["celular"],
                         "31911112222")

    def test_visita_antiga_nao_mexe_na_pessoa(self):
        antiga = self.banco.inserir(registro(entrada="15/10/2026 08:00",
                                             saida="15/10/2026 09:00"))
        self.banco.inserir(registro())
        self.corrigir(antiga, celular="31911112222")
        self.assertEqual(self.banco.buscar_pessoa("52998224725")["celular"],
                         "31987654321")

    def test_cpf_digitado_errado_passa_para_a_pessoa_certa(self):
        self.banco.inserir(registro(cpf="11144477735", entrada="15/10/2026 08:00",
                                    saida="15/10/2026 09:00"))
        errado = self.banco.inserir(registro(cpf="52998224725"))
        self.corrigir(errado, cpf="11144477735")
        self.assertIsNone(self.banco.buscar_pessoa("52998224725"))  # fantasma
        self.assertEqual(self.banco.buscar_pessoa("11144477735")["visitas"], 2)

    def test_cpf_trocado_nao_remove_pessoa_com_outras_visitas(self):
        self.banco.inserir(registro(entrada="15/10/2026 08:00",
                                    saida="15/10/2026 09:00"))
        id_ = self.banco.inserir(registro())
        self.corrigir(id_, cpf="39053344705")
        self.assertEqual(self.banco.buscar_pessoa("52998224725")["visitas"], 1)
        self.assertEqual(self.banco.buscar_pessoa("39053344705")["visitas"], 1)

    def test_correcao_invalida_nao_muda_nada(self):
        id_ = self.banco.inserir(registro())
        with self.assertRaises(dados.ErroDados):
            self.corrigir(id_, saida="16/10/2026 07:00")   # saída < entrada
        self.assertEqual(self.banco.buscar(id_)["saida"], "")
        self.assertEqual(self.banco.eventos_do_registro(id_), [])

    def test_registro_que_nao_existe(self):
        with self.assertRaises(dados.ErroDados):
            self.banco.editar(999, registro(), ["x"], autor="ana")


class TestBloqueiosNoBanco(BaseTemp):
    def setUp(self):
        super().setUp()
        self.criar_equipe()

    def test_bloquear_listar_e_remover(self):
        self.banco.inserir(registro())                      # pessoa conhecida
        id_ = self.banco.bloquear("cpf", "52998224725", " Furto ", "ana")
        b = self.banco.listar_bloqueios()[0]
        self.assertEqual((b["id"], b["tipo"], b["valor"], b["motivo"], b["nome"],
                          b["criado_por"], b["ativo"]),
                         (id_, "cpf", "52998224725", "Furto", "João Ávila",
                          "ana", True))
        self.banco.desbloquear(id_, "bia")
        self.assertEqual(self.banco.listar_bloqueios(), [])
        removido = self.banco.listar_bloqueios(incluir_removidos=True)[0]
        self.assertEqual((removido["ativo"], removido["removido_por"]),
                         (False, "bia"))
        self.assertEqual([e["acao"] for e in self.banco.listar_eventos()][:2],
                         ["Bloqueio removido", "Bloqueio criado"])

    def test_nao_bloqueia_duas_vezes_mas_pode_bloquear_de_novo(self):
        id_ = self.banco.bloquear("placa", "ABC1D23", "Motivo um", "ana")
        with self.assertRaises(dados.ErroDados):
            self.banco.bloquear("placa", "ABC1D23", "Motivo dois", "ana")
        self.banco.desbloquear(id_, "ana")
        self.banco.bloquear("placa", "ABC1D23", "Motivo três", "ana")
        self.assertEqual(len(self.banco.listar_bloqueios(True)), 2)

    def test_remover_bloqueio_ja_removido(self):
        id_ = self.banco.bloquear("cpf", "52998224725", "Motivo um", "ana")
        self.banco.desbloquear(id_, "ana")
        with self.assertRaises(dados.ErroDados):
            self.banco.desbloquear(id_, "ana")


class TestUsuariosNoBanco(BaseTemp):
    def test_criar_listar_e_buscar(self):
        self.assertFalse(self.banco.tem_usuarios())
        id_ = self.banco.criar_usuario("Ana Admin", "ana", "admin", "hash-falso")
        self.assertTrue(self.banco.tem_usuarios())
        self.assertEqual(self.banco.listar_usuarios(),
                         [{"id": id_, "login": "ana", "nome": "Ana Admin",
                           "perfil": "admin", "ativo": True}])
        self.assertEqual(self.banco.buscar_usuario("ana")["senha"], "hash-falso")
        self.assertIsNone(self.banco.buscar_usuario("ninguem"))

    def test_login_repetido_e_perfil_invalido_sao_recusados(self):
        self.banco.criar_usuario("Ana Admin", "ana", "admin", "h")
        with self.assertRaises(dados.ErroDados):
            self.banco.criar_usuario("Outra Ana", "ana", "porteiro", "h",
                                     autor="ana")
        with self.assertRaises(dados.ErroDados):
            self.banco.criar_usuario("Chefe Geral", "chefe", "chefe", "h",
                                     autor="ana")

    def test_ativar_desativar_e_trocar_senha(self):
        id_ = self.banco.criar_usuario("Ana Admin", "ana", "admin", "h1")
        self.banco.definir_senha(id_, "h2", autor="ana")
        self.banco.definir_ativo(id_, False, autor="ana")
        self.assertFalse(self.banco.buscar_usuario("ana")["ativo"])
        self.assertEqual(self.banco.buscar_usuario("ana")["senha"], "h2")


class TestAuditoria(BaseTemp):
    def acoes(self):
        return [(e["usuario"], e["acao"]) for e in self.banco.listar_eventos()]

    def test_operacoes_com_autor_ficam_no_historico(self):
        self.criar_equipe()
        id_ = self.banco.inserir(registro(), autor="paulo")
        self.banco.registrar_saida(id_, "16/10/2026 09:00", autor="paulo")
        self.banco.excluir([id_], autor="ana")
        self.assertEqual(self.acoes()[:3], [("ana", "Exclusão de registro"),
                                            ("paulo", "Saída registrada"),
                                            ("paulo", "Cadastro de entrada")])
        detalhe = self.banco.listar_eventos()[0]["detalhe"]
        self.assertIn("João Ávila", detalhe)
        self.assertIn("16/10/2026 08:00", detalhe)

    def test_sem_autor_nao_grava_historico(self):
        self.banco.inserir(registro())
        self.assertEqual(self.banco.listar_eventos(), [])

    def test_criar_usuario_registra_quem_criou(self):
        self.banco.criar_usuario("Ana Admin", "ana", "admin", "h")
        self.banco.criar_usuario("Paulo Porteiro", "paulo", "porteiro", "h",
                                 autor="ana")
        evento = self.banco.listar_eventos()[0]
        self.assertEqual((evento["usuario"], evento["acao"], evento["detalhe"]),
                         ("ana", "Usuário criado", "paulo (porteiro)"))

    def test_data_do_evento_no_formato_da_tela(self):
        self.banco.registrar_evento("ana", "Entrou no sistema")
        momento = self.banco.listar_eventos()[0]["momento"]
        self.assertRegex(momento, r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}$")


class TestPessoas(BaseTemp):
    def setUp(self):
        super().setUp()
        self.criar_equipe()

    def test_primeira_visita_cria_a_pessoa(self):
        self.banco.inserir(registro())
        p = self.banco.buscar_pessoa("52998224725")
        self.assertEqual((p["nome"], p["celular"], p["placa"], p["tipo"]),
                         ("João Ávila", "31987654321", "ABC1D23", "Funcionário"))
        self.assertEqual(p["visitas"], 1)
        self.assertEqual(p["ultima_visita"], "16/10/2026 08:00")
        self.assertEqual(p["dentro_desde"], "16/10/2026 08:00")

    def test_cpf_desconhecido(self):
        self.assertIsNone(self.banco.buscar_pessoa("11144477735"))

    def test_nova_visita_atualiza_dados_e_guarda_ultimo_veiculo(self):
        self.banco.inserir(registro(saida="16/10/2026 09:00"))
        self.banco.inserir(registro(celular="31911112222", placa="",
                                    entrada="17/10/2026 08:00",
                                    saida="17/10/2026 10:00"))
        p = self.banco.buscar_pessoa("52998224725")
        self.assertEqual(p["celular"], "31911112222")   # dado mais recente
        self.assertEqual(p["placa"], "ABC1D23")         # veio a pé: mantém o carro
        self.assertEqual(p["visitas"], 2)
        self.assertEqual(p["ultima_visita"], "17/10/2026 08:00")
        self.assertEqual(p["dentro_desde"], "")

    def test_visita_guarda_os_dados_daquele_dia(self):
        self.banco.inserir(registro(saida="16/10/2026 09:00"))
        self.banco.inserir(registro(celular="31911112222",
                                    entrada="17/10/2026 08:00"))
        celulares = [r["celular"] for r in self.banco.listar()]
        self.assertEqual(celulares, ["31987654321", "31911112222"])

    def test_listar_pessoas_em_ordem_alfabetica(self):
        self.banco.inserir(registro(nome="Zeca Lima", cpf="11144477735"))
        self.banco.inserir(registro(nome="ana Souza", cpf="39053344705",
                                    saida="16/10/2026 09:00"))
        pessoas = self.banco.listar_pessoas()
        self.assertEqual([p["nome"] for p in pessoas], ["ana Souza", "Zeca Lima"])
        self.assertEqual([bool(p["dentro_desde"]) for p in pessoas], [False, True])

    def test_corrigir_dados_nao_muda_as_visitas(self):
        self.banco.inserir(registro())
        id_ = self.banco.buscar_pessoa("52998224725")["id"]
        self.banco.atualizar_pessoa(id_, "João Ávila Neto", "31933334444", "",
                                    "Professor", autor="ana")
        p = self.banco.buscar_pessoa("52998224725")
        self.assertEqual((p["nome"], p["celular"], p["placa"], p["tipo"]),
                         ("João Ávila Neto", "31933334444", "", "Professor"))
        self.assertEqual(self.banco.listar()[0]["nome"], "João Ávila")
        self.assertEqual(self.banco.listar_eventos()[0]["acao"],
                         "Dados de pessoa alterados")

    def test_excluir_visita_mantem_a_pessoa(self):
        id_ = self.banco.inserir(registro())
        self.banco.excluir([id_], autor="ana")
        p = self.banco.buscar_pessoa("52998224725")
        self.assertEqual((p["visitas"], p["ultima_visita"]), (0, ""))

    def test_visita_recusada_nao_cria_pessoa(self):
        with self.assertRaises(dados.ErroDados):
            self.banco.inserir(registro(saida="16/10/2026 07:00"))
        self.assertEqual(self.banco.listar_pessoas(), [])

    def test_visita_recusada_na_importacao_nao_cria_pessoa(self):
        # Na importação a transação continua depois de um registro ruim,
        # então a pessoa não pode ter sido gravada antes da visita.
        self.escrever_json([registro(),
                            registro(cpf="11144477735",
                                     saida="16/10/2026 07:00")])  # saída < entrada
        self.banco.importar_json(self.caminho_json)
        self.assertEqual([p["cpf"] for p in self.banco.listar_pessoas()],
                         ["52998224725"])

    def test_importar_json_cria_as_pessoas(self):
        self.escrever_json([registro(entrada="15/10/2026 08:00",
                                     saida="15/10/2026 09:00"),
                            registro(entrada="16/10/2026 08:00")])
        self.banco.importar_json(self.caminho_json)
        self.assertEqual(self.banco.buscar_pessoa("52998224725")["visitas"], 2)


class TestAtualizacaoDoEsquema(unittest.TestCase):
    def abrir_banco_antigo(self, pasta, versao, visitas):
        """Cria um portaria.db como as versões 1/2 deixavam (sem pessoas)."""
        caminho = os.path.join(pasta, "portaria.db")
        con = sqlite3.connect(caminho)
        con.executescript("""
            CREATE TABLE registros (
                id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
                cpf TEXT NOT NULL, celular TEXT NOT NULL,
                placa TEXT NOT NULL DEFAULT '', tipo TEXT NOT NULL,
                entrada TEXT NOT NULL, saida TEXT NOT NULL DEFAULT '');""")
        con.executemany("INSERT INTO registros (nome, cpf, celular, placa, tipo, "
                        "entrada, saida) VALUES (?, ?, ?, ?, ?, ?, ?)", visitas)
        con.execute(f"PRAGMA user_version = {versao}")
        con.commit()
        con.close()
        return dados.Banco(caminho), caminho

    def test_banco_da_versao_1_ganha_as_tabelas_novas_sem_perder_dados(self):
        with tempfile.TemporaryDirectory() as pasta:
            banco, caminho = self.abrir_banco_antigo(pasta, 1, [
                ("Ana Silva", "52998224725", "31987654321", "", "Aluno",
                 "2026-10-16 08:00", "")])
            self.assertEqual([r["nome"] for r in banco.listar()], ["Ana Silva"])
            self.assertFalse(banco.tem_usuarios())
            self.assertEqual(banco.buscar_pessoa("52998224725")["visitas"], 1)
            con = sqlite3.connect(caminho)
            versao = con.execute("PRAGMA user_version").fetchone()[0]
            con.close()
            self.assertEqual(versao, dados.VERSAO_ESQUEMA)

    def test_pessoas_montadas_a_partir_das_visitas_antigas(self):
        with tempfile.TemporaryDirectory() as pasta:
            banco, caminho = self.abrir_banco_antigo(pasta, 2, [
                ("Ana Silva", "52998224725", "31987654321", "ABC1D23", "Visitante",
                 "2026-10-14 08:00", "2026-10-14 09:00"),
                ("Ana Silva Costa", "52998224725", "31911112222", "", "Aluno",
                 "2026-10-15 08:00", ""),
                ("Beto Rocha", "11144477735", "31933334444", "", "Professor",
                 "2026-10-15 07:00", "2026-10-15 12:00")])
            ana = banco.buscar_pessoa("52998224725")
            self.assertEqual((ana["nome"], ana["celular"], ana["placa"], ana["tipo"]),
                             ("Ana Silva Costa", "31911112222", "ABC1D23", "Aluno"))
            self.assertEqual(ana["visitas"], 2)
            self.assertEqual(ana["dentro_desde"], "15/10/2026 08:00")
            self.assertEqual(len(banco.listar_pessoas()), 2)
            con = sqlite3.connect(caminho)
            sem_pessoa = con.execute("SELECT COUNT(*) FROM registros "
                                     "WHERE pessoa_id IS NULL").fetchone()[0]
            con.close()
            self.assertEqual(sem_pessoa, 0)

    def test_historico_antigo_e_ligado_ao_registro_na_v4(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "portaria.db")
            banco = dados.Banco(caminho)
            banco.criar_usuario("Paulo Porteiro", "paulo", "porteiro", "h")
            id_ = banco.inserir(registro(), autor="paulo")
            banco.registrar_saida(id_, "16/10/2026 09:00", autor="paulo")
            banco.registrar_evento("paulo", "Entrou no sistema")
            con = sqlite3.connect(caminho)      # volta o banco para a v3
            con.executescript("""
                DROP INDEX idx_auditoria_registro;
                ALTER TABLE auditoria DROP COLUMN registro_id;
                PRAGMA user_version = 3;""")
            con.close()

            banco = dados.Banco(caminho)
            self.assertEqual([e["acao"] for e in banco.eventos_do_registro(id_)],
                             ["Cadastro de entrada", "Saída registrada"])

    def test_reabrir_banco_novo_nao_duplica_nada(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "portaria.db")
            dados.Banco(caminho).inserir(registro())
            banco = dados.Banco(caminho)
            self.assertEqual(len(banco.listar_pessoas()), 1)
            self.assertEqual(len(banco.listar()), 1)


class TestMigracao(BaseTemp):
    def test_sem_json_nao_faz_nada(self):
        self.assertEqual(self.banco.importar_json(self.caminho_json), "")

    def test_importa_tudo_e_guarda_o_json_como_migrado(self):
        antigos = [registro(), registro(cpf="11144477735", saida="16/10/2026 09:00")]
        self.escrever_json(antigos)
        aviso = self.banco.importar_json(self.caminho_json)
        self.assertIn("2 registro(s)", aviso)
        self.assertEqual([{k: v for k, v in r.items() if k != "id"}
                          for r in self.banco.listar()], antigos)
        self.assertFalse(os.path.exists(self.caminho_json))
        self.assertTrue(os.path.exists(self.caminho_json + ".migrado"))

    def test_migracao_nao_se_repete(self):
        self.escrever_json([registro()])
        self.banco.importar_json(self.caminho_json)
        self.assertEqual(self.banco.importar_json(self.caminho_json), "")
        self.assertEqual(len(self.banco.listar()), 1)

    def test_registros_invalidos_sao_ignorados_e_avisados(self):
        self.escrever_json([
            registro(),
            registro(entrada="ontem"),                       # data ilegível
            {"nome": "Sem CPF"},                             # faltam campos
            registro(cpf="11144477735", saida="16/10/2026 07:00"),  # saída < entrada
            "texto solto",
        ])
        aviso = self.banco.importar_json(self.caminho_json)
        self.assertEqual(len(self.banco.listar()), 1)
        self.assertIn("4 registro(s) com dados inválidos", aviso)
        self.assertTrue(os.path.exists(self.caminho_json + ".migrado"))

    def test_json_danificado_e_guardado_e_nada_importado(self):
        self.escrever_json('[{"nome": "Ana"')   # cortado no meio
        aviso = self.banco.importar_json(self.caminho_json)
        self.assertIn("danificado", aviso)
        self.assertEqual(self.banco.listar(), [])
        copias = [n for n in os.listdir(self.pasta.name) if "danificado" in n]
        self.assertEqual(len(copias), 1)

    def test_json_que_nao_e_lista_conta_como_danificado(self):
        self.escrever_json({"nome": "Ana"})
        self.assertIn("danificado", self.banco.importar_json(self.caminho_json))


def agora_menos(**delta):
    return (datetime.now() - timedelta(**delta)).strftime(FORMATO)


def rebaixar_para_v7(caminho):
    """Deixa um banco como a versão 7 deixava: sem a tolerância e com os
    padrões antigos das regras de horário."""
    con = sqlite3.connect(caminho)
    con.executescript("""
        ALTER TABLE regras_categoria DROP COLUMN tolerancia_min;
        UPDATE regras_categoria SET fecha_depois = 60 WHERE tipo = 'Funcionário';
        UPDATE regras_categoria SET permanencia_min = 60 WHERE tipo = 'Professor';
        UPDATE parametros SET valor = 12 WHERE chave = 'horas_retroativo';
        PRAGMA user_version = 7;""")
    con.close()


def rebaixar_para_v6(caminho):
    """Deixa um banco como a versão 6 deixava (sem o que a v7 criou)."""
    rebaixar_para_v7(caminho)
    con = sqlite3.connect(caminho)
    con.executescript("""
        DROP INDEX idx_registros_saida;
        DROP TABLE funcionamento;
        DROP TABLE feriados;
        DROP TABLE eventos;
        DROP TABLE regras_categoria;
        DROP TABLE parametros;
        PRAGMA user_version = 6;""")
    con.close()


def rebaixar_para_v5(caminho):
    """Deixa um banco como a versão 5 deixava (sem o que a v6 e a v7 criaram)."""
    rebaixar_para_v6(caminho)
    con = sqlite3.connect(caminho)
    con.executescript("""
        DROP INDEX idx_um_aberto_por_cpf;
        DROP INDEX idx_registros_entrada;
        DROP INDEX idx_pessoas_nome;
        DROP INDEX idx_auditoria_momento;
        DROP TABLE tentativas_login;
        PRAGMA user_version = 5;""")
    con.close()


def objetos_do_banco(caminho):
    con = sqlite3.connect(caminho)
    nomes = {n for (n,) in con.execute("SELECT name FROM sqlite_master")}
    con.close()
    return nomes


def versao_do_arquivo(caminho):
    con = sqlite3.connect(caminho)
    versao = con.execute("PRAGMA user_version").fetchone()[0]
    con.close()
    return versao


class TestIntegridade(BaseTemp):
    def test_segunda_visita_aberta_do_mesmo_cpf_e_recusada_pelo_banco(self):
        # duas estações: a segunda tinha a lista antiga e não viu a entrada
        outra_estacao = dados.Banco(self.caminho_db)
        self.banco.inserir(registro())
        with self.assertRaises(dados.ErroDados) as erro:
            outra_estacao.inserir(registro(entrada="16/10/2026 09:00"))
        self.assertIn("entrada sem saída", str(erro.exception))
        self.assertEqual(len(self.banco.listar()), 1)

    def test_visita_encerrada_do_mesmo_cpf_continua_aceita(self):
        self.banco.inserir(registro(entrada="15/10/2026 08:00",
                                    saida="15/10/2026 09:00"))
        self.banco.inserir(registro())
        self.assertEqual(len(self.banco.listar()), 2)

    def test_erro_tecnico_vira_mensagem_amigavel(self):
        self.banco.inserir(registro())
        with self.assertRaises(dados.ErroDados) as erro:
            self.banco.inserir(registro(entrada="16/10/2026 09:00"))
        mensagem = str(erro.exception)
        for tecnico in ("constraint", "UNIQUE", "registros", "sqlite"):
            self.assertNotIn(tecnico, mensagem)
        self.assertIn("UNIQUE constraint failed", erro.exception.detalhe)

    def test_login_repetido_tem_mensagem_propria(self):
        self.banco.criar_usuario("Ana Admin", "ana", "admin", "h")
        with self.assertRaises(dados.ErroDados) as erro:
            self.banco.criar_usuario("Outra Ana", "ana", "porteiro", "h",
                                     autor="ana")
        self.assertEqual(str(erro.exception), "Já existe um usuário com esse login.")

    def test_erro_vai_para_o_log_sem_ir_para_a_tela(self):
        self.banco.inserir(registro())
        with self.assertLogs("portaria.dados", level="ERROR") as registro_log:
            with self.assertRaises(dados.ErroDados):
                self.banco.inserir(registro(entrada="16/10/2026 09:00"))
        self.assertIn("UNIQUE constraint failed", registro_log.output[0])

    def test_chaves_estrangeiras_valem(self):
        with self.banco._conexao() as con:
            self.assertEqual(con.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(con.execute("PRAGMA busy_timeout").fetchone()[0],
                             dados.SEGUNDOS_ESPERA * 1000)
        with self.assertRaises(dados.ErroDados):
            with self.banco._conexao() as con:
                con.execute("INSERT INTO registros (nome, cpf, celular, tipo, "
                            "entrada, pessoa_id) VALUES ('A B', '52998224725', "
                            "'31987654321', 'Aluno', '2026-10-16 08:00', 99999)")

    def test_modo_wal_ligado(self):
        con = sqlite3.connect(self.caminho_db)
        modo = con.execute("PRAGMA journal_mode").fetchone()[0]
        con.close()
        self.assertEqual(modo, "wal")

    def test_banco_de_versao_mais_nova_e_recusado_sem_alterar_nada(self):
        con = sqlite3.connect(self.caminho_db)
        con.execute("PRAGMA journal_mode = DELETE")
        con.execute("PRAGMA user_version = 99")
        con.close()
        with open(self.caminho_db, "rb") as f:
            antes = hashlib.sha256(f.read()).hexdigest()
        with self.assertRaises(dados.ErroDados) as erro:
            dados.Banco(self.caminho_db)
        self.assertIn("versão mais nova", str(erro.exception))
        with open(self.caminho_db, "rb") as f:
            self.assertEqual(hashlib.sha256(f.read()).hexdigest(), antes)
        self.assertEqual(versao_do_arquivo(self.caminho_db), 99)

    def test_visita_retroativa_nao_sobrescreve_a_pessoa(self):
        self.banco.inserir(registro())                       # visita de hoje
        self.banco.inserir(registro(nome="João Velho", celular="31911112222",
                                    tipo="Visitante", placa="XYZ9A87",
                                    entrada="10/10/2026 08:00",
                                    saida="10/10/2026 09:00"))
        p = self.banco.buscar_pessoa("52998224725")
        self.assertEqual((p["nome"], p["celular"], p["tipo"], p["placa"]),
                         ("João Ávila", "31987654321", "Funcionário", "ABC1D23"))
        self.assertEqual(p["visitas"], 2)

    def test_visita_retroativa_de_pessoa_nova_cria_a_pessoa(self):
        self.banco.inserir(registro(entrada="10/10/2026 08:00",
                                    saida="10/10/2026 09:00"))
        self.assertEqual(self.banco.buscar_pessoa("52998224725")["nome"],
                         "João Ávila")

    def test_de_iso_por_fatiamento_igual_ao_strptime(self):
        for iso in ("2026-10-16 08:05", "2026-01-31 23:59", "1999-12-01 00:00"):
            esperado = datetime.strptime(iso, dados.FORMATO_ISO).strftime(FORMATO)
            self.assertEqual(dados.de_iso(iso), esperado)
        self.assertEqual(dados.de_iso(""), "")


class TestMigracaoV6(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = os.path.join(self.pasta.name, "portaria.db")

    def tearDown(self):
        self.pasta.cleanup()

    def test_v5_vira_v6_com_indices_e_backup_antes(self):
        dados.Banco(self.caminho).inserir(registro())
        rebaixar_para_v5(self.caminho)
        banco = dados.Banco(self.caminho)
        self.assertEqual(versao_do_arquivo(self.caminho), dados.VERSAO_ESQUEMA)
        self.assertLessEqual({"idx_um_aberto_por_cpf", "idx_registros_entrada",
                              "idx_auditoria_momento", "tentativas_login"},
                             objetos_do_banco(self.caminho))
        backups = os.listdir(os.path.join(self.pasta.name, "backups"))
        self.assertEqual(len(backups), 1)
        self.assertIn(f"antes-v{dados.VERSAO_ESQUEMA}-de-v5", backups[0])
        self.assertEqual(len(banco.listar()), 1)
        self.assertEqual(banco.avisos, [])

    def test_sem_conseguir_o_backup_nao_migra_e_explica(self):  # B4
        dados.Banco(self.caminho).inserir(registro())
        rebaixar_para_v5(self.caminho)
        # um arquivo chamado "backups" impede criar a pasta (como uma pasta
        # sem permissão de gravação)
        with open(os.path.join(self.pasta.name, "backups"), "w") as f:
            f.write("não é pasta")
        with self.assertRaises(dados.ErroDados) as erro:
            dados.Banco(self.caminho)
        self.assertIn("cópia de segurança", str(erro.exception))
        self.assertIn("Nada foi alterado", str(erro.exception))
        self.assertEqual(versao_do_arquivo(self.caminho), 5)

    def test_erro_no_meio_da_migracao_desfaz_o_passo_inteiro(self):
        dados.Banco(self.caminho)
        rebaixar_para_v5(self.caminho)

        def passo_que_falha(banco, con, versao):
            dados._passo_v6(banco, con, versao)    # cria índices e tabela...
            raise RuntimeError("falta de energia simulada")   # ...e cai

        with mock.patch.object(dados, "MIGRACOES",
                               [(5, dados._passo_v5), (6, passo_que_falha)]):
            with self.assertRaises(RuntimeError):
                dados.Banco(self.caminho)
        self.assertEqual(versao_do_arquivo(self.caminho), 5)
        objetos = objetos_do_banco(self.caminho)
        self.assertNotIn("idx_um_aberto_por_cpf", objetos)
        self.assertNotIn("tentativas_login", objetos)
        dados.Banco(self.caminho)                   # na próxima vez, migra
        self.assertEqual(versao_do_arquivo(self.caminho), dados.VERSAO_ESQUEMA)

    def test_banco_com_visitas_abertas_duplicadas_abre_e_corrige(self):
        dados.Banco(self.caminho)
        rebaixar_para_v5(self.caminho)
        con = sqlite3.connect(self.caminho)
        con.executemany(
            "INSERT INTO registros (nome, cpf, celular, tipo, entrada, saida) "
            "VALUES (?, ?, '31987654321', 'Aluno', ?, '')",
            [("Ana Silva", "52998224725", "2026-10-16 08:00"),
             ("Ana Silva", "52998224725", "2026-10-16 10:00"),
             ("Ana Silva", "52998224725", "2026-10-16 11:30"),
             ("Beto Rocha", "11144477735", "2026-10-16 09:00")])
        con.commit()
        con.close()

        banco = dados.Banco(self.caminho)
        saidas = {r["entrada"]: r["saida"] for r in banco.listar()
                  if r["cpf"] == "52998224725"}
        self.assertEqual(saidas, {"16/10/2026 08:00": "16/10/2026 10:00",
                                  "16/10/2026 10:00": "16/10/2026 11:30",
                                  "16/10/2026 11:30": ""})
        self.assertEqual(len(banco.avisos), 1)
        self.assertIn("2 visita(s)", banco.avisos[0])
        eventos = [e for e in banco.listar_eventos()
                   if e["acao"] == "Saída automática (atualização)"]
        self.assertEqual(len(eventos), 2)
        self.assertEqual(eventos[0]["usuario"], dados.AUTOR_SISTEMA)
        self.assertIn("idx_um_aberto_por_cpf", objetos_do_banco(self.caminho))


class TestMigracaoV7(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = os.path.join(self.pasta.name, "portaria.db")

    def tearDown(self):
        self.pasta.cleanup()

    def test_v6_vira_v7_com_indice_das_saidas_e_backup_antes(self):
        dados.Banco(self.caminho).inserir(registro())
        rebaixar_para_v6(self.caminho)
        self.assertNotIn("idx_registros_saida", objetos_do_banco(self.caminho))
        banco = dados.Banco(self.caminho)
        self.assertEqual(versao_do_arquivo(self.caminho), dados.VERSAO_ESQUEMA)
        self.assertIn("idx_registros_saida", objetos_do_banco(self.caminho))
        backups = os.listdir(os.path.join(self.pasta.name, "backups"))
        self.assertEqual(len(backups), 1)
        self.assertIn(f"antes-v{dados.VERSAO_ESQUEMA}-de-v6", backups[0])
        self.assertEqual(len(banco.listar()), 1)


class TestConsultasNoBanco(BaseTemp):
    """As consultas novas no SQL dão o mesmo resultado das antigas em Python."""

    HOJE = date(2026, 10, 16)

    def setUp(self):
        super().setUp()
        cpfs = ["52998224725", "11144477735", "39053344705", "16899535009",
                "86288366757", "71428793860"]
        self.banco.inserir(registro(cpf=cpfs[0], entrada="15/10/2026 07:00",
                                    saida="15/10/2026 08:30"))   # ontem, saiu
        self.banco.inserir(registro(nome="Beto Rocha", cpf=cpfs[1], placa="",
                                    tipo="Professor",
                                    entrada="14/10/2026 22:00"))  # dentro há dias
        self.banco.inserir(registro(nome="JOSÉ ÉRICO", cpf=cpfs[2], placa="QWE1234",
                                    celular="11998765432", tipo="Visitante",
                                    entrada="16/10/2026 09:00",
                                    saida="16/10/2026 09:47"))    # hoje, saiu
        self.banco.inserir(registro(cpf=cpfs[0], entrada="16/10/2026 10:00"))
        self.banco.inserir(registro(nome="Duda Reis", cpf=cpfs[3], tipo="Outro",
                                    entrada="09/10/2026 10:00",
                                    saida="09/10/2026 10:01"))    # há 7 dias
        self.banco.inserir(registro(nome="Eva Lima", cpf=cpfs[4], tipo="Aluno",
                                    entrada="17/10/2026 08:00",
                                    saida="17/10/2026 18:59"))    # amanhã
        self.banco.inserir(registro(nome="Fábio Melo", cpf=cpfs[5], tipo="Aluno",
                                    entrada="16/10/2026 00:00",
                                    saida="16/10/2026 00:00"))

    def test_movimento_e_hoje_mais_quem_esta_dentro(self):
        movimento = self.banco.listar_movimento(self.HOJE)
        self.assertEqual([(r["nome"], r["entrada"]) for r in movimento], [
            ("João Ávila", "16/10/2026 10:00"),
            ("JOSÉ ÉRICO", "16/10/2026 09:00"),
            ("Fábio Melo", "16/10/2026 00:00"),
            ("Beto Rocha", "14/10/2026 22:00")])

    def test_movimento_inclui_quem_saiu_hoje_com_entrada_em_outro_dia(self):
        # bug: entrada de outro dia (ex.: corrigida para fevereiro) e saída
        # registrada hoje sumia do Movimento (só aparecia na busca)
        id_ = self.banco.inserir(registro(
            nome="Gil Prestes", cpf="12345678909", tipo="Prestador de serviço",
            entrada="15/10/2026 22:00", saida="16/10/2026 06:00"))
        self.banco.inserir(registro(
            nome="Hugo Neves", cpf="98765432100", entrada="14/10/2026 07:00",
            saida="15/10/2026 06:00"))                  # saiu ontem: não
        movimento = self.banco.listar_movimento(self.HOJE)
        self.assertEqual([r["id"] for r in movimento].count(id_), 1)
        self.assertNotIn("Hugo Neves", [r["nome"] for r in movimento])

    def test_movimento_usa_indice_em_todas_as_partes(self):
        con = sqlite3.connect(self.caminho_db)
        plano = " ".join(str(linha[3]) for linha in con.execute(
            "EXPLAIN QUERY PLAN SELECT id FROM registros "
            "WHERE saida >= '2026-10-16 00:00' AND saida < '2026-10-17 00:00' "
            "AND +entrada < '2026-10-16 00:00'"))
        con.close()
        self.assertIn("idx_registros_saida", plano)
        self.assertNotIn("SCAN registros", plano)

    def test_buscar_registros_igual_ao_filtrar(self):
        todos = self.banco.listar()
        mais_recentes_primeiro = sorted(
            todos, key=lambda r: (dados.para_iso(r["entrada"]), r["id"]),
            reverse=True)
        for texto in ["", "  ", "ana", "JOÃO", "josé", "érico", "529.982",
                      "119987", "qwe", "aluno", "outro", "x", "16/10", "9"]:
            with self.subTest(texto=texto):
                self.assertEqual(self.banco.buscar_registros(texto),
                                 filtrar(mais_recentes_primeiro, texto))

    def test_buscar_registros_respeita_o_limite(self):
        self.assertEqual(len(self.banco.buscar_registros("", limite=3)), 3)

    def test_resumo_no_sql_igual_ao_resumo_em_python(self):
        todos = self.banco.listar()
        for hoje in (self.HOJE, date(2026, 10, 17), date(2026, 10, 1),
                     datetime(2026, 10, 16, 15, 0)):
            with self.subTest(hoje=hoje):
                dia = hoje.date() if isinstance(hoje, datetime) else hoje
                self.assertEqual(self.banco.resumo_painel(hoje),
                                 resumo(todos, dia))

    def test_resumo_de_banco_vazio(self):
        vazio = dados.Banco(os.path.join(self.pasta.name, "vazio.db"))
        self.assertEqual(vazio.resumo_painel(self.HOJE), resumo([], self.HOJE))

    def test_buscar_um_e_listar_por_cpf(self):
        primeiro = self.banco.listar()[0]
        self.assertEqual(self.banco.buscar(primeiro["id"]), primeiro)
        self.assertIsNone(self.banco.buscar(9999))
        self.assertEqual([r["entrada"] for r in
                          self.banco.listar_por_cpf("52998224725")],
                         ["15/10/2026 07:00", "16/10/2026 10:00"])

    def test_buscar_pessoas_igual_ao_filtrar(self):
        pessoas = self.banco.listar_pessoas()
        for texto in ["", "o", "JOSÉ", "beto", "111.444", "aluno", "zz"]:
            with self.subTest(texto=texto):
                self.assertEqual(self.banco.buscar_pessoas(texto),
                                 filtrar(pessoas, texto))


    def test_contadores_da_barra_lateral(self):
        self.criar_equipe()
        self.banco.bloquear("placa", "ABC1234", "Motivo válido", "ana")
        id_ = self.banco.bloquear("cpf", "11144477735", "Motivo válido", "ana")
        self.banco.desbloquear(id_, "ana")                     # removido não conta
        self.assertEqual(self.banco.contadores(),
                         {"pessoas": 6, "no_campus": 2, "bloqueios": 1})


class TestPermissoesNoBanco(BaseTemp):
    """S04: a camada de dados confere o perfil de quem faz (quando informado)."""

    def setUp(self):
        super().setUp()
        self.criar_equipe()
        self.ids = {u["login"]: u["id"] for u in self.banco.listar_usuarios()}

    def test_porteiro_nao_exclui_registro(self):  # RN02
        id_ = self.banco.inserir(registro())
        with self.assertRaises(dados.ErroDados) as erro:
            self.banco.excluir([id_], autor="paulo")
        self.assertIn("Somente o administrador", str(erro.exception))
        self.assertEqual(len(self.banco.listar()), 1)
        self.banco.excluir([id_], autor="ana")
        self.assertEqual(self.banco.listar(), [])

    def test_porteiro_nao_mexe_na_lista_de_bloqueio(self):  # RN12
        with self.assertRaises(dados.ErroDados):
            self.banco.bloquear("cpf", "52998224725", "Motivo qualquer", "paulo")
        id_ = self.banco.bloquear("cpf", "52998224725", "Motivo qualquer", "ana")
        with self.assertRaises(dados.ErroDados):
            self.banco.desbloquear(id_, "paulo")
        self.assertEqual(len(self.banco.listar_bloqueios()), 1)

    def test_porteiro_nao_gerencia_usuarios(self):
        with self.assertRaises(dados.ErroDados):
            self.banco.criar_usuario("Novo Admin", "novo", "admin", "h",
                                     autor="paulo")
        with self.assertRaises(dados.ErroDados):
            self.banco.definir_ativo(self.ids["ana"], False, autor="paulo")
        with self.assertRaises(dados.ErroDados):
            self.banco.definir_senha(self.ids["ana"], "outro-hash", autor="paulo")
        self.assertIsNone(self.banco.buscar_usuario("novo"))
        ana = self.banco.buscar_usuario("ana")
        self.assertEqual((ana["ativo"], ana["senha"]), (True, "hash-falso"))

    def test_cada_um_troca_a_propria_senha_e_admin_redefine(self):
        self.banco.definir_senha(self.ids["paulo"], "h-paulo", autor="paulo")
        self.banco.definir_senha(self.ids["paulo"], "h-admin", autor="ana")
        self.assertEqual(self.banco.buscar_usuario("paulo")["senha"], "h-admin")
        acoes = [(e["usuario"], e["acao"]) for e in self.banco.listar_eventos()]
        self.assertEqual(acoes[:2], [("ana", "Senha redefinida"),
                                     ("paulo", "Senha alterada")])

    def test_porteiro_corrige_so_registro_recente(self):  # RN11
        recente = self.banco.inserir(registro(entrada=agora_menos(hours=1)))
        antigo = self.banco.inserir(registro(cpf="11144477735",
                                             entrada=agora_menos(hours=30)))
        novo = dict(self.banco.buscar(recente), nome="João Ávila Neto")
        self.banco.editar(recente, novo, ["Nome"], autor="paulo")
        for id_, mudanca in [(antigo, {"nome": "Beto Rocha"}),
                             (recente, {"entrada": agora_menos(hours=30)})]:
            with self.subTest(id_=id_), self.assertRaises(dados.ErroDados) as e:
                self.banco.editar(id_, dict(self.banco.buscar(id_), **mudanca),
                                  ["x"], autor="paulo")
            self.assertIn("24 horas", str(e.exception))
        self.banco.editar(antigo, dict(self.banco.buscar(antigo), nome="Beto Rocha"),
                          ["Nome"], autor="ana")
        self.assertEqual(self.banco.buscar(antigo)["nome"], "Beto Rocha")

    def test_autor_desativado_ou_inexistente_e_recusado(self):
        self.banco.definir_ativo(self.ids["bia"], False, autor="ana")
        id_ = self.banco.inserir(registro())
        for autor in ("bia", "fantasma"):
            with self.subTest(autor=autor), self.assertRaises(dados.ErroDados):
                self.banco.excluir([id_], autor=autor)
        self.assertEqual(len(self.banco.listar()), 1)

    def test_operacao_sensivel_sem_autor_e_recusada(self):  # N01
        # a sessão que expirou com a caixa aberta chega aqui com autor=None
        id_ = self.banco.inserir(registro())
        bloqueio = self.banco.bloquear("placa", "ABC1234", "Motivo válido", "ana")
        antes = len(self.banco.listar_eventos())
        operacoes = [
            ("excluir", lambda: self.banco.excluir([id_], None)),
            ("editar", lambda: self.banco.editar(
                id_, dict(self.banco.buscar(id_), nome="Outro Nome"), ["x"], None)),
            ("exportar", lambda: self.banco.registros_do_periodo(
                date(2026, 10, 1), date(2026, 10, 31), None)),
            ("bloquear", lambda: self.banco.bloquear(
                "cpf", "11144477735", "Motivo válido", None)),
            ("desbloquear", lambda: self.banco.desbloquear(bloqueio, None)),
            ("desativar", lambda: self.banco.definir_ativo(
                self.ids["paulo"], False, None)),
            ("senha", lambda: self.banco.definir_senha(
                self.ids["paulo"], "outro-hash", None)),
            ("criar", lambda: self.banco.criar_usuario(      # N03: já há
                "Novo Admin", "novo", "admin", "h")),         # usuários
        ]
        for nome, operacao in operacoes:
            with self.subTest(nome), self.assertRaises(dados.ErroDados):
                operacao()
        self.assertEqual(self.banco.buscar(id_)["nome"], "João Ávila")
        self.assertEqual(len(self.banco.listar_bloqueios()), 1)
        self.assertIsNone(self.banco.buscar_usuario("novo"))
        paulo = self.banco.buscar_usuario("paulo")
        self.assertEqual((paulo["ativo"], paulo["senha"]), (True, "hash-falso"))
        self.assertEqual(len(self.banco.listar_eventos()), antes)

    def test_mensagem_de_sessao_encerrada(self):
        id_ = self.banco.inserir(registro())
        with self.assertRaises(dados.ErroDados) as erro:
            self.banco.excluir([id_], None)
        self.assertEqual(str(erro.exception),
                         "A sessão foi encerrada. Entre novamente.")

    def test_usuario_desativado_nao_continua_operando(self):  # B5
        self.banco.definir_ativo(self.ids["paulo"], False, autor="ana")
        id_ = self.banco.inserir(registro(), autor="ana")
        pessoa = self.banco.buscar_pessoa("52998224725")["id"]
        operacoes = [
            ("inserir", lambda: self.banco.inserir(
                registro(cpf="11144477735"), autor="paulo")),
            ("saida", lambda: self.banco.registrar_saidas(
                [id_], "16/10/2026 09:00", autor="paulo")),
            ("pessoa", lambda: self.banco.atualizar_pessoa(
                pessoa, "Outro Nome", "31987654321", "", "Aluno", autor="paulo")),
            ("inexistente", lambda: self.banco.inserir(
                registro(cpf="39053344705"), autor="fantasma")),
        ]
        for nome, operacao in operacoes:
            with self.subTest(nome), self.assertRaises(dados.ErroDados):
                operacao()
        self.assertEqual(len(self.banco.listar()), 1)
        self.assertEqual(self.banco.buscar(id_)["saida"], "")
        self.banco.registrar_saida(id_, "16/10/2026 09:00", autor="ana")
        with self.assertRaises(dados.ErroDados):
            self.banco.desfazer_saidas([id_], autor="paulo")
        self.assertEqual(self.banco.buscar(id_)["saida"], "16/10/2026 09:00")

    def test_primeiro_acesso_so_com_a_tabela_vazia(self):  # N03
        vazio = dados.Banco(os.path.join(self.pasta.name, "outro.db"))
        vazio.criar_usuario("Ana Admin", "ana", "admin", "h")
        with self.assertRaises(dados.ErroDados) as erro:
            vazio.criar_usuario("Intruso Silva", "intruso", "admin", "h")
        self.assertIn("primeiro usuário já foi criado", str(erro.exception))
        self.assertEqual([u["login"] for u in vazio.listar_usuarios()], ["ana"])

    def test_admin_redefine_senha_e_libera_o_login_travado(self):  # B7
        self.banco.gravar_tentativas_login("paulo", 0, 3,
                                           datetime.now() + timedelta(minutes=5))
        self.banco.gravar_tentativas_login("bia", 2, 0, None)
        self.banco.definir_senha(self.ids["paulo"], "h-nova", autor="ana")
        self.assertEqual(self.banco.ler_tentativas_login("paulo"), (0, 0, None))
        # trocar a própria senha não zera a contagem de quem errou
        self.banco.definir_senha(self.ids["bia"], "h-bia", autor="bia")
        self.assertEqual(self.banco.ler_tentativas_login("bia")[0], 2)

    def test_porteiro_nao_exporta_registros(self):
        with self.assertRaises(dados.ErroDados):
            self.banco.registros_do_periodo(date(2026, 10, 1), date(2026, 10, 31),
                                            autor="paulo")


class TestPrivacidadeNoHistorico(BaseTemp):
    """S08/S11: o histórico não guarda CPF completo nem texto de senha."""

    def setUp(self):
        super().setUp()
        self.criar_equipe()

    def detalhes(self):
        return " | ".join(e["detalhe"] for e in self.banco.listar_eventos())

    def test_exclusao_grava_cpf_mascarado(self):
        id_ = self.banco.inserir(registro(), autor="paulo")
        self.banco.excluir([id_], autor="ana")
        detalhe = self.banco.listar_eventos()[0]["detalhe"]
        self.assertIn("***.982.247-**", detalhe)
        self.assertNotIn("52998224725", detalhe)
        self.assertNotIn("529.982.247-25", detalhe)

    def test_cpf_em_qualquer_detalhe_e_mascarado(self):
        # como a tela registra a "Entrada recusada (bloqueio)" e a correção
        self.banco.registrar_evento("paulo", "Entrada recusada (bloqueio)",
                                    "Ana Silva, CPF 529.982.247-25, placa ABC1D23")
        self.banco.bloquear("cpf", "11144477735", "Ameaçou alguém", "ana")
        id_ = self.banco.inserir(registro(), autor="paulo")
        novo = dict(self.banco.buscar(id_), cpf="39053344705")
        self.banco.editar(id_, novo, ["CPF: 529.982.247-25 → 390.533.447-05"],
                          autor="ana")
        detalhes = self.detalhes()
        for cpf in ("52998224725", "529.982.247-25", "11144477735",
                    "39053344705", "390.533.447-05"):
            self.assertNotIn(cpf, detalhes)
        self.assertIn("***.982.247-** → ***.533.447-**", detalhes)
        self.assertIn("CPF ***.444.777-**", detalhes)

    def test_login_recusado_de_login_inexistente_nao_grava_o_texto(self):  # S11
        self.banco.registrar_evento("minhasenha#2026", "Login recusado")
        self.banco.registrar_evento("ana", "Login recusado")
        usuarios = [e["usuario"] for e in self.banco.listar_eventos()]
        self.assertEqual(usuarios[:2], ["ana", "(login inexistente)"])
        con = sqlite3.connect(self.caminho_db)
        tudo = str(con.execute("SELECT * FROM auditoria").fetchall())
        con.close()
        self.assertNotIn("minhasenha", tudo)


if __name__ == "__main__":
    unittest.main()
