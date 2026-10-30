"""
Revisão 2.5.1: os caminhos da linguagem que nenhum teste percorria
(achados pela medição de cobertura da suíte) e o defeito do "buscar" com
período num histórico grande.
"""
import tkinter as tk
from datetime import date, datetime, timedelta

from portaria.linguagem.executor import (MOSTRAR_NO_CONSOLE, quem_esta_dentro,
                                         situacao_do_veiculo)
from portaria.linguagem.semantico import AVISO
from portaria.validacao import FORMATO, formatar_cpf

from .test_interface import BaseInterface
from .test_linguagem import BETO, CARLA, DUDA, NOVO, BaseBanco


def checagem(analise, descricao):
    return next(c for c in analise.checagens if c.descricao == descricao)


class TestBuscarNoBanco(BaseBanco):
    def visita(self, dia, tipo="Aluno"):
        entrada = datetime.combine(dia, datetime.min.time()).replace(hour=9)
        self.banco.inserir({"nome": "Rui Lima", "cpf": NOVO,
                            "celular": "31987654321", "placa": "",
                            "tipo": tipo, "entrada": entrada.strftime(FORMATO),
                            "saida": (entrada + timedelta(hours=1))
                            .strftime(FORMATO)}, autor="ana")

    def test_periodo_e_tipo_vao_para_o_sql_antes_do_limite(self):
        """Defeito: com mais visitas recentes do que o limite, um período
        antigo voltava vazio (o limite cortava antes do filtro)."""
        for i in range(12):
            self.visita(date(2026, 10, 1) + timedelta(days=i))
        self.visita(date(2025, 1, 10), "Visitante")
        self.visita(date(2025, 1, 31))
        self.visita(date(2025, 2, 1))
        achados = self.banco.buscar_registros("rui", 5, desde=date(2025, 1, 1),
                                              ate=date(2025, 1, 31))
        self.assertEqual([r["entrada"][:10] for r in achados],
                         ["31/01/2025", "10/01/2025"])      # o dia final conta
        so_alunos = self.banco.buscar_registros(
            "rui", 5, desde=date(2025, 1, 1), ate=date(2025, 1, 31),
            tipo="Aluno")
        self.assertEqual(len(so_alunos), 1)
        # sem período, continua sendo "as mais recentes"
        self.assertEqual(len(self.banco.buscar_registros("rui", 5)), 5)


class TestCaminhosDoSemantico(BaseBanco):
    def test_periodos_do_buscar(self):
        dias = {}
        for palavra in ("hoje", "ontem", "semana", "mes"):
            d = self.analisar(f"buscar maria {palavra}").plano.dados
            dias[palavra] = (d["inicio"], d["fim"])
        hoje = self.agora.date()
        self.assertEqual(dias["hoje"], (hoje, hoje))
        self.assertEqual(dias["ontem"], (hoje - timedelta(days=1),) * 2)
        self.assertEqual(dias["semana"], (hoje - timedelta(days=6), hoje))
        self.assertEqual(dias["mes"], (hoje - timedelta(days=29), hoje))
        e = self.erro("buscar maria de 10/10/2026 ate 01/10/2026")
        self.assertIn("termina antes de começar", e.mensagem)

    def test_porteiro_busca_cpf_por_pedaco_recebe_aviso(self):
        a = self.analisar("buscar 52998", self.porteiro)
        self.assertEqual(checagem(a, "CPF só pelos 11 números").estado, AVISO)

    def test_situacao_pela_placa(self):
        a = self.analisar("situacao placa ABC1D23")
        self.assertEqual(a.plano.dados["estadia"]["cpf"], CARLA)
        r = situacao_do_veiculo(a.plano.dados, lambda m: m[-5:])
        self.assertIn("ABC1D23 está no estacionamento desde 08:14", r.texto)
        self.assertIn("o dono está no campus", r.texto)
        a = self.analisar("situacao placa NEY4829")
        r = situacao_do_veiculo(a.plano.dados, lambda m: m)
        self.assertIn("não está no estacionamento", r.texto)
        self.banco.desativar("placa", "NEY4829", "furto no estacionamento",
                             "ana")
        a = self.analisar("situacao placa NEY4829")
        r = situacao_do_veiculo(a.plano.dados, lambda m: m)
        self.assertEqual(r.nivel, AVISO)
        self.assertIn("furto no estacionamento", r.linhas[0])

    def test_desativar_quem_esta_no_campus_avisa(self):
        a = self.analisar(f'desativar {CARLA} motivo "agressão ao porteiro"')
        self.assertEqual(checagem(a, "Pessoa no campus agora").estado, AVISO)

    def test_saida_pela_placa_nao_aceita_opcoes(self):
        e = self.erro("saida placa ABC1D23 as 09:00")
        self.assertEqual(e.regra, "RN27")

    def test_saida_com_o_carro_que_pode_retirar(self):
        """RN35: Beto está a pé e pode retirar o carro de Carla."""
        self.banco.adicionar_autorizado(CARLA, BETO, "Beto Rocha", None, "ana")
        self.banco.inserir({"nome": "Beto Rocha", "cpf": BETO,
                            "celular": "31987651234", "placa": "",
                            "tipo": "Visitante", "entrada": "21/10/2026 09:00",
                            "saida": ""}, autor="ana")
        a = self.analisar(f"saida {BETO} placa ABC1D23")
        self.assertIsNone(a.erro)
        visita = a.plano.dados["registros"][0]["id"]
        self.assertIn(visita, a.plano.dados["levados"])
        # quem não está na lista não leva (RN32)
        self.banco.inserir({"nome": "Duda Martins", "cpf": DUDA,
                            "celular": "31987654321", "placa": "",
                            "tipo": "Professor", "entrada": "21/10/2026 09:50",
                            "saida": ""}, autor="ana")
        e = self.erro(f"saida {DUDA} placa ABC1D23")
        self.assertIn("não está autorizado(a)", e.mensagem)

    def test_cadastrar_cpf_desativado_pede_confirmacao(self):
        self.banco.desativar("cpf", NOVO, "fraude no cadastro", "ana")
        a = self.analisar(f'cadastrar {NOVO} visitante nome "Rui Lima" '
                          "cel 31987651234")
        self.assertEqual(checagem(a, "CPF ativo").estado, AVISO)
        self.assertIn("fraude no cadastro", a.plano.dados["confirmar"])


class TestRespostasLongas(BaseBanco):
    def test_console_mostra_ate_o_limite_e_quantos_faltam(self):
        registros = [{"nome": f"Pessoa {i}", "cpf": NOVO, "tipo": "Aluno",
                      "placa": "", "saida": "",
                      "entrada": f"21/10/2026 {8 + i // 60:02d}:{i % 60:02d}"}
                     for i in range(MOSTRAR_NO_CONSOLE + 3)]
        r = quem_esta_dentro(registros, None, formatar_cpf, lambda m: m[-5:])
        self.assertEqual(len(r.linhas), MOSTRAR_NO_CONSOLE + 1)
        self.assertEqual(r.linhas[-1], "… e mais 3")


class TestBuscarPelaTela(BaseInterface):
    entrar_como = "admin"

    def comando(self, texto):
        linha = self.app.tela_cadastro.campo_saida_rapida
        linha.delete(0, tk.END)
        linha.insert(0, texto)
        self.app.tela_cadastro.saida_rapida()
        return self.app.tela_cadastro.comando.texto_resposta

    def test_buscar_periodo_antigo_com_historico_grande(self):
        """O defeito pela tela: 210 visitas recentes de Ana e 3 em
        janeiro/2025; "buscar ana de 01/01/2025 ate 31/01/2025" achava 0."""
        inicio = datetime(2026, 3, 1, 9, 0)
        dias = [inicio + timedelta(days=i) for i in range(210)]
        dias += [datetime(2025, 1, d, 9, 0) for d in (5, 15, 25)]
        for e in dias:
            self.banco.inserir({"nome": "Ana Souza", "cpf": "52998224725",
                                "celular": "31987654321", "placa": "",
                                "tipo": "Visitante", "entrada": e.strftime(FORMATO),
                                "saida": (e + timedelta(hours=2)).strftime(FORMATO)},
                               autor="ana.admin")
        texto = self.comando("buscar ana de 01/01/2025 ate 31/01/2025")
        self.assertIn("3 visitas encontradas", texto)

    def test_desativar_quem_esta_no_campus_pelo_comando(self):
        self.banco.inserir({"nome": "Ana Souza", "cpf": "52998224725",
                            "celular": "31987654321", "placa": "",
                            "tipo": "Visitante",
                            "entrada": (self.app.relogio() - timedelta(hours=1))
                            .strftime(FORMATO), "saida": ""},
                           autor="ana.admin")
        self.app.atualizar_tabela()
        texto = self.comando('desativar 52998224725 motivo "agressão ao '
                             'porteiro"')
        self.assertIn("No campus agora: Ana Souza", texto)


if __name__ == "__main__":
    import unittest
    unittest.main()
