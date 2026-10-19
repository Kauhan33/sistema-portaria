import json
import os
import sqlite3
import tempfile
import unittest

from portaria import dados


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
        self.banco.inserir(registro(nome="Segundo Cadastro", entrada="15/10/2026 10:00"))
        nomes = [r["nome"] for r in self.banco.listar()]
        self.assertEqual(nomes, ["Primeiro Cadastro", "Segundo Cadastro"])

    def test_registrar_saida(self):
        id_ = self.banco.inserir(registro())
        self.banco.registrar_saida(id_, "16/10/2026 11:15")
        self.assertEqual(self.banco.listar()[0]["saida"], "16/10/2026 11:15")

    def test_excluir_varios(self):
        ids = [self.banco.inserir(registro(cpf=c))
               for c in ("52998224725", "11144477735", "39053344705")]
        self.banco.excluir(ids[:2])
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
    def entrar(self, cpf, entrada="16/10/2026 08:00"):
        return self.banco.inserir(registro(cpf=cpf, entrada=entrada))

    def saidas(self):
        return {r["id"]: r["saida"] for r in self.banco.listar()}

    def test_saida_de_varios_de_uma_vez(self):
        a, b = self.entrar("52998224725"), self.entrar("11144477735")
        self.banco.registrar_saidas([a, b], "16/10/2026 09:00", autor="paulo")
        self.assertEqual(self.saidas(), {a: "16/10/2026 09:00",
                                         b: "16/10/2026 09:00"})
        self.assertEqual(len(self.banco.listar_eventos()), 2)

    def test_nao_sobrescreve_saida_ja_registrada(self):
        a = self.entrar("52998224725")
        self.banco.registrar_saida(a, "16/10/2026 09:00", autor="paulo")
        self.banco.registrar_saida(a, "16/10/2026 10:00", autor="paulo")
        self.assertEqual(self.saidas()[a], "16/10/2026 09:00")
        self.assertEqual(len(self.banco.listar_eventos()), 1)

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

    def test_nao_desfaz_se_ha_visita_encerrada_depois(self):
        a = self.entrar("52998224725")
        self.banco.registrar_saida(a, "16/10/2026 09:00")
        b = self.entrar("52998224725", entrada="16/10/2026 09:05")
        self.banco.registrar_saida(b, "16/10/2026 09:30")
        self.assertEqual(self.banco.desfazer_saidas([a]), 0)


class TestEdicao(BaseTemp):
    def corrigir(self, id_, **mudancas):
        antes = self.banco.buscar(id_)
        novo = {k: v for k, v in antes.items() if k != "id"}
        novo.update(mudancas)
        self.banco.editar(id_, novo, [f"{k} alterado" for k in mudancas],
                          autor="paulo")
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
            self.banco.editar(999, registro(), ["x"], autor="paulo")


class TestBloqueiosNoBanco(BaseTemp):
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
            self.banco.criar_usuario("Outra Ana", "ana", "porteiro", "h")
        with self.assertRaises(dados.ErroDados):
            self.banco.criar_usuario("Chefe Geral", "chefe", "chefe", "h")

    def test_ativar_desativar_e_trocar_senha(self):
        id_ = self.banco.criar_usuario("Ana Admin", "ana", "admin", "h1")
        self.banco.definir_ativo(id_, False)
        self.assertFalse(self.banco.buscar_usuario("ana")["ativo"])
        self.banco.definir_senha(id_, "h2")
        self.assertEqual(self.banco.buscar_usuario("ana")["senha"], "h2")


class TestAuditoria(BaseTemp):
    def acoes(self):
        return [(e["usuario"], e["acao"]) for e in self.banco.listar_eventos()]

    def test_operacoes_com_autor_ficam_no_historico(self):
        id_ = self.banco.inserir(registro(), autor="paulo")
        self.banco.registrar_saida(id_, "16/10/2026 09:00", autor="paulo")
        self.banco.excluir([id_], autor="ana")
        self.assertEqual(self.acoes(), [("ana", "Exclusão de registro"),
                                        ("paulo", "Saída registrada"),
                                        ("paulo", "Cadastro de entrada")])
        detalhe = self.banco.listar_eventos()[0]["detalhe"]
        self.assertIn("João Ávila", detalhe)
        self.assertIn("16/10/2026 08:00", detalhe)

    def test_sem_autor_nao_grava_historico(self):
        self.banco.inserir(registro())
        self.assertEqual(self.banco.listar_eventos(), [])

    def test_criar_usuario_registra_quem_criou(self):
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
        self.banco.excluir([id_])
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


if __name__ == "__main__":
    unittest.main()
