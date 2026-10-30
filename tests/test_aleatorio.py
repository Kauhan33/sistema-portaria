"""
Teste por sequências aleatórias (revisão 2.5.1): milhares de operações do
Banco em ordem aleatória — entradas, saídas, desfazer, correções,
exclusões, carros, desativações, cadastro de pessoas com várias placas,
quem pode retirar e "Encerrar o dia" — e, depois de cada uma, as regras
que nunca podem quebrar (invariantes):

- um CPF tem no máximo uma visita aberta (RN05);
- uma placa tem no máximo uma estadia aberta (RN25);
- a visita aponta para a pessoa do próprio CPF;
- a placa principal da pessoa está entre os carros dela (RN47);
- a estadia aberta de uma visita tem a placa da visita;
- o histórico (auditoria) só cresce;
- os contadores da barra lateral batem com a contagem direta;
- nenhuma chave estrangeira quebrada e o banco íntegro.

Uma operação recusada tem de ser ErroDados (a mensagem para o usuário);
qualquer outra exceção é defeito. As sementes são fixas (o resultado se
repete); PORTARIA_PASSOS=5000 roda uma versão longa.
"""
import os
import random
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta

from portaria import dados
from portaria.senhas import gerar_hash
from portaria.validacao import FORMATO, TIPOS_ACESSO

PASSOS = int(os.environ.get("PORTARIA_PASSOS", "250"))
SEMENTES = (1, 2, 3)
INICIO = datetime(2026, 10, 19, 7, 30)          # segunda-feira


def cpf(base):
    d = [int(c) for c in f"{base:09d}"]
    for n in (10, 11):
        s = sum(v * (n - i) for i, v in enumerate(d)) % 11
        d.append(0 if s < 2 else 11 - s)
    return "".join(map(str, d))


CPFS = [cpf(123_456_000 + i * 7) for i in range(14)]
NOMES = ["Ana Souza", "Beto Rocha", "Carla Lima", "Duda Martins",
         "Edu Prado", "Fabi Costa", "Gil Ramos"]
PLACAS = ["ABC1D23", "NEY4829", "QWE1E34", "BRA2E19", "MBC7712", "KLM3B21",
          "RST4A56", "JKL4M56", "XYZ9A88"]


class Maquina:
    """O banco, o relógio e as operações sorteadas."""

    def __init__(self, semente, pasta):
        self.r = random.Random(semente)
        self.agora = INICIO
        self.caminho = os.path.join(pasta, "portaria.db")
        self.banco = dados.Banco(self.caminho, relogio=lambda: self.agora)
        self.banco.criar_usuario("Ana Admin", "ana", "admin",
                                 gerar_hash("senha-da-ana-1"))
        self.banco.criar_usuario("Paulo Porteiro", "paulo", "porteiro",
                                 gerar_hash("senha-do-paulo1"), autor="ana",
                                 trocar_senha=False)
        self.eventos = 0
        self.feitas = {}
        self.recusadas = {}

    # --- auxiliares --------------------------------------------------
    def quando(self, minutos_atras=0):
        return (self.agora - timedelta(minutes=minutos_atras)).strftime(FORMATO)

    def sql(self, consulta, params=()):
        con = sqlite3.connect(self.caminho)
        try:
            return con.execute(consulta, params).fetchall()
        finally:
            con.close()

    def autor(self):
        return self.r.choice(["ana", "paulo"])

    # --- operações ---------------------------------------------------
    def op_entrada(self):
        c = self.r.choice(CPFS)
        pessoa = self.banco.buscar_pessoa(c)
        placa = self.r.choice(["", "", self.r.choice(PLACAS)]
                              + (pessoa["placas"] if pessoa else []))
        nome = pessoa["nome"] if pessoa and self.r.random() < 0.8 \
            else self.r.choice(NOMES)
        r = {"nome": nome, "cpf": c, "celular": "31987654321", "placa": placa,
             "tipo": self.r.choice(TIPOS_ACESSO),
             "entrada": self.quando(self.r.choice([0, 0, 5, 30])), "saida": ""}
        self.banco.inserir(r, autor=self.autor(), lotado_confirmado=True)

    def op_saida(self):
        abertas = self.banco.listar_abertas()
        if not abertas:
            return
        v = self.r.choice(abertas)
        estadias = self.banco.estadias_abertas_do_cpf(v["cpf"])
        com = {}
        if estadias and self.r.random() < 0.7:
            com = {v["id"]: self.r.choice(estadias)["id"]}
        self.banco.registrar_saidas([v["id"]], self.quando(), autor=self.autor(),
                                    com_veiculo=com)

    def op_desfazer(self):
        fechadas = self.sql("SELECT id FROM registros WHERE saida <> ''")
        if fechadas:
            self.banco.desfazer_saidas([self.r.choice(fechadas)[0]],
                                       autor=self.autor())

    def op_excluir(self):
        ids = self.sql("SELECT id FROM registros")
        if ids:
            self.banco.excluir([self.r.choice(ids)[0]], "ana")

    def op_corrigir(self):
        ids = self.sql("SELECT id FROM registros")
        if not ids:
            return
        i = self.r.choice(ids)[0]
        original = self.banco.buscar(i)
        novo = dict(original)
        mudanca = self.r.choice(["nome", "placa", "saida", "cpf", "tipo"])
        if mudanca == "nome":
            novo["nome"] = self.r.choice(NOMES)
        elif mudanca == "placa":
            novo["placa"] = self.r.choice([""] + PLACAS)
        elif mudanca == "saida":
            novo["saida"] = "" if original["saida"] else self.quando()
        elif mudanca == "cpf":
            novo["cpf"] = self.r.choice(CPFS)
        else:
            novo["tipo"] = self.r.choice(TIPOS_ACESSO)
        self.banco.editar(i, novo, [f"{mudanca} corrigido"], "ana",
                          original=original)

    def op_saida_do_carro(self):
        estadias = self.banco.listar_estacionamento()
        if estadias:
            e = self.r.choice(estadias)
            self.banco.registrar_saida_veiculo(e["id"], self.quando(),
                                               autor=self.autor())

    def op_desativar(self):
        tipo = self.r.choice(["cpf", "placa"])
        valor = self.r.choice(CPFS if tipo == "cpf" else PLACAS)
        self.banco.desativar(tipo, valor, "Motivo do teste aleatório", "ana")

    def op_reativar(self):
        ativas = self.banco.listar_desativacoes()
        if ativas:
            self.banco.reativar(self.r.choice(ativas)["id"], "ana")

    def op_cadastrar(self):
        placas = self.r.sample(PLACAS, self.r.randint(0, 3))
        self.banco.cadastrar_pessoa(self.r.choice(CPFS), self.r.choice(NOMES),
                                    "31999998888", placas,
                                    self.r.choice(TIPOS_ACESSO), self.autor())

    def op_editar_pessoa(self):
        pessoas = self.banco.listar_pessoas()
        if not pessoas:
            return
        p = self.r.choice(pessoas)
        placas = list(p["placas"])
        if placas and self.r.random() < 0.5:
            placas.remove(self.r.choice(placas))
        if self.r.random() < 0.6:
            placas.append(self.r.choice(PLACAS))
        self.r.shuffle(placas)
        self.banco.atualizar_pessoa(p["id"], p["nome"], p["celular"], placas,
                                    p["tipo"], autor=self.autor())

    def op_excluir_pessoa(self):
        pessoas = self.banco.listar_pessoas()
        if pessoas:
            self.banco.excluir_pessoa(self.r.choice(pessoas)["id"], "ana")

    def op_autorizado(self):
        pessoas = self.banco.listar_pessoas()
        donos = [p for p in pessoas if p["placas"]]
        if not donos:
            return
        dono = self.r.choice(donos)
        outro = self.r.choice([c for c in CPFS if c != dono["cpf"]])
        self.banco.adicionar_autorizado(
            dono["cpf"], outro, "Fulano de Tal", None, "ana",
            placa=self.r.choice(dono["placas"]))

    def op_remover_autorizado(self):
        ids = self.sql("SELECT id FROM autorizados_veiculo WHERE ativo = 1")
        if ids:
            self.banco.remover_autorizado(self.r.choice(ids)[0], self.autor())

    def op_encerrar(self):
        self.banco.encerrar_pendentes(self.agora, "ana")

    OPERACOES = {
        "entrada": 9, "saida": 6, "desfazer": 2, "excluir": 1, "corrigir": 3,
        "saida_do_carro": 2, "desativar": 1, "reativar": 1, "cadastrar": 2,
        "editar_pessoa": 2, "excluir_pessoa": 1, "autorizado": 1,
        "remover_autorizado": 1, "encerrar": 1,
    }

    def passo(self):
        self.agora += timedelta(minutes=self.r.randint(1, 40))
        nome = self.r.choices(list(self.OPERACOES),
                              weights=self.OPERACOES.values())[0]
        try:
            getattr(self, "op_" + nome)()
            self.feitas[nome] = self.feitas.get(nome, 0) + 1
        except dados.ErroDados:
            self.recusadas[nome] = self.recusadas.get(nome, 0) + 1
        return nome

    # --- invariantes -------------------------------------------------
    def conferir(self, teste, nome, completo=False):
        s = self.sql
        teste.assertEqual(s("SELECT cpf FROM registros WHERE saida = '' "
                            "GROUP BY cpf HAVING COUNT(*) > 1"), [],
                          f"{nome}: duas visitas abertas do mesmo CPF")
        teste.assertEqual(s("SELECT placa FROM estadias_veiculo WHERE saida = '' "
                            "GROUP BY placa HAVING COUNT(*) > 1"), [],
                          f"{nome}: a mesma placa duas vezes no estacionamento")
        teste.assertEqual(s("SELECT r.id FROM registros r JOIN pessoas p ON "
                            "p.id = r.pessoa_id WHERE p.cpf <> r.cpf"), [],
                          f"{nome}: visita ligada à pessoa de outro CPF")
        teste.assertEqual(s("SELECT id FROM registros WHERE pessoa_id IS NULL"),
                          [], f"{nome}: visita sem pessoa")
        teste.assertEqual(s("SELECT p.id, p.placa FROM pessoas p WHERE "
                            "p.placa <> '' AND NOT EXISTS (SELECT 1 FROM "
                            "placas_pessoa v WHERE v.pessoa_id = p.id AND "
                            "v.placa = p.placa)"), [],
                          f"{nome}: placa principal fora dos carros da pessoa")
        teste.assertEqual(s("SELECT e.id FROM estadias_veiculo e JOIN registros "
                            "r ON r.id = e.registro_id WHERE e.saida = '' AND "
                            "r.placa <> e.placa"), [],
                          f"{nome}: estadia aberta com placa diferente da visita")
        teste.assertEqual(s("SELECT * FROM registros WHERE saida <> '' AND "
                            "saida < entrada"), [], f"{nome}: saída antes da entrada")
        eventos = s("SELECT COUNT(*) FROM auditoria")[0][0]
        teste.assertGreaterEqual(eventos, self.eventos,
                                 f"{nome}: o histórico perdeu eventos")
        self.eventos = eventos
        n = self.banco.contadores()
        teste.assertEqual(n["pessoas"], s("SELECT COUNT(*) FROM pessoas")[0][0])
        teste.assertEqual(n["no_campus"],
                          s("SELECT COUNT(*) FROM registros WHERE saida = ''")[0][0],
                          f"{nome}: contador do campus")
        teste.assertEqual(s("PRAGMA foreign_key_check"), [],
                          f"{nome}: chave estrangeira quebrada")
        if completo:
            teste.assertEqual(s("PRAGMA integrity_check"), [("ok",)])
            # as leituras da tela não quebram
            hoje = self.agora.date()
            self.banco.listar_movimento(hoje)
            self.banco.resumo_painel(hoje)
            self.banco.buscar_pessoas("")
            self.banco.buscar_registros("a")
            for p in self.banco.listar_pessoas():
                teste.assertEqual(len(p["placas"]), len(set(p["placas"])))
                if p["placa"]:
                    teste.assertEqual(p["placas"][0], p["placa"])


class TestSequenciasAleatorias(unittest.TestCase):
    def test_invariantes_em_sequencias_aleatorias(self):
        for semente in SEMENTES:
            with self.subTest(semente=semente), \
                    tempfile.TemporaryDirectory() as pasta:
                m = Maquina(semente, pasta)
                for i in range(PASSOS):
                    nome = m.passo()
                    m.conferir(self, f"semente {semente}, passo {i} ({nome})",
                               completo=(i % 50 == 49))
                m.conferir(self, f"semente {semente}, fim", completo=True)
                # a sequência exercitou de fato as operações
                self.assertGreater(m.feitas.get("entrada", 0), 10)
                self.assertGreater(m.feitas.get("saida", 0), 5)


if __name__ == "__main__":
    unittest.main()


class TestCasosAchados(unittest.TestCase):
    """Os defeitos que as sequências aleatórias acharam, um teste fixo
    para cada (não voltam sem o teste perceber)."""

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.m = Maquina(0, self.pasta.name)
        self.banco = self.m.banco

    def visita(self, placa):
        return self.banco.inserir(
            {"nome": "Gil Ramos", "cpf": CPFS[0], "celular": "31987654321",
             "placa": placa, "tipo": "Aluno",
             "entrada": self.m.quando(30), "saida": ""}, autor="paulo")

    def corrigir_placa(self, i, placa):
        original = self.banco.buscar(i)
        self.banco.editar(i, dict(original, placa=placa), ["placa"], "ana",
                          original=original)

    def test_desfazer_saida_depois_de_corrigir_a_placa(self):
        """Semente 21: sai com o BRA2E19, a placa da visita é corrigida
        para RST4A56 e a saída é desfeita. Antes, o BRA2E19 voltava ao
        estacionamento ligado a uma visita que diz RST4A56."""
        i = self.visita("BRA2E19")
        estadia = self.banco.estadia_aberta(placa="BRA2E19")["id"]
        saida = self.m.quando()
        self.banco.registrar_saidas([i], saida, autor="paulo",
                                    com_veiculo={i: estadia})
        self.corrigir_placa(i, "RST4A56")
        self.assertEqual(self.banco.desfazer_saidas([i], autor="paulo"), 1)
        self.assertIsNone(self.banco.estadia_aberta(placa="BRA2E19"))
        self.assertEqual(self.banco.estadia_aberta(placa="RST4A56")["id"],
                         estadia)
        self.m.conferir(self, "desfazer depois da correção", completo=True)

    def test_desfazer_saida_depois_de_apagar_a_placa(self):
        """A visita ficou sem placa (veio a pé): nenhum carro volta."""
        i = self.visita("BRA2E19")
        estadia = self.banco.estadia_aberta(placa="BRA2E19")["id"]
        self.banco.registrar_saidas([i], self.m.quando(), autor="paulo",
                                    com_veiculo={i: estadia})
        self.corrigir_placa(i, "")
        self.assertEqual(self.banco.desfazer_saidas([i], autor="paulo"), 1)
        self.assertEqual(self.banco.listar_estacionamento(), [])
        self.m.conferir(self, "desfazer depois de apagar a placa",
                        completo=True)
