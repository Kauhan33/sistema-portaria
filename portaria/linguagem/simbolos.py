"""
Tabela de SÍMBOLOS do analisador semântico.

Num compilador, a tabela de símbolos diz o que cada nome significa
(variável x: int, declarada na linha 3). Aqui os "nomes" de um comando
são CPFs, placas, o usuário logado e o dia de hoje, e o significado está
no banco:

    pessoas      CPF -> nome, tipo, dentro ou fora do campus, visitas
    veículos     placa -> estadia aberta, responsável, dono no campus
    desativações CPF ou placa -> desativado(a), motivo (RN12)
    usuário      o login e o perfil de quem está logado (RN02)
    o dia        os horários de hoje e da categoria (horarios.py)

A tabela SÓ CONSULTA (os mesmos métodos de leitura do Banco que as telas
usam). Cada consulta vira uma linha em `linhas`, que o modo didático mostra
na aba Símbolos; o CPF dessas linhas sai como a tela mostra para quem está
logado (`exibir_cpf`: mascarado para o porteiro, RN14).
"""

from dataclasses import dataclass
from datetime import datetime

from .. import horarios
from ..usuarios import PERFIS
from ..validacao import FORMATO, formatar_placa, mascarar_cpf
from ..veiculos import texto_lotacao


@dataclass
class Simbolo:
    categoria: str        # "Pessoa", "Veículo", "Desativação", "Usuário"...
    chave: str            # "CPF ***.982.247-**", "Placa ABC1D23"
    descricao: str        # "Ana Silva · Visitante · no campus desde 08:00"


class TabelaDeSimbolos:
    def __init__(self, banco, usuario, agora, exibir_cpf=mascarar_cpf):
        self.banco, self.usuario, self.agora = banco, usuario, agora
        self.exibir_cpf = exibir_cpf
        self.linhas = []
        self._cache = {}

    # --- registro do que foi consultado -----------------------------
    def _anotar(self, categoria, chave, descricao):
        simbolo = Simbolo(categoria, chave, descricao)
        if simbolo not in self.linhas:
            self.linhas.append(simbolo)

    def _uma_vez(self, chave, leitura):
        """Lê do banco uma vez por análise (a mesma consulta não repete)."""
        if chave not in self._cache:
            self._cache[chave] = leitura()
        return self._cache[chave]

    def quando(self, momento):
        """'18:14' se foi hoje; senão 'dd/mm/aaaa hh:mm' (como a tela)."""
        if not momento:
            return ""
        hoje = self.agora.strftime("%d/%m/%Y")
        return momento[-5:] if momento.startswith(hoje) else momento

    # --- usuário ----------------------------------------------------
    def usuario_logado(self):
        u = self.usuario or {}
        self._anotar("Usuário", u.get("login", "?"),
                     PERFIS.get(u.get("perfil"), "?"))
        return u

    # --- pessoas ----------------------------------------------------
    def pessoa(self, cpf):
        """O cadastro da pessoa (banco.buscar_pessoa) ou None."""
        p = self._uma_vez(("pessoa", cpf),
                          lambda: self.banco.buscar_pessoa(cpf))
        chave = "CPF " + self.exibir_cpf(cpf)
        if p is None:
            self._anotar("Pessoa", chave, "não cadastrada")
        else:
            onde = (f"no campus desde {self.quando(p['dentro_desde'])}"
                    if p["dentro_desde"] else "fora do campus")
            placa = f" · placa {formatar_placa(p['placa'])}" if p["placa"] \
                else ""
            self._anotar("Pessoa", chave,
                         f"{p['nome']} · {p['tipo']} · {onde}{placa}")
        return p

    def visitas(self, cpf):
        """Todas as visitas do CPF (banco.listar_por_cpf), para validar."""
        return self._uma_vez(("visitas", cpf),
                             lambda: self.banco.listar_por_cpf(cpf))

    def visitas_abertas(self, cpf):
        abertas = [r for r in self.visitas(cpf) if not r["saida"]]
        for r in abertas:
            self._anotar("Visita", f"#{r['id']}",
                         f"{r['nome']} · entrada {self.quando(r['entrada'])} · "
                         "sem saída")
        return abertas

    def ultima_saida(self, cpf):
        """A saída mais recente do CPF ('' se nunca saiu)."""
        saidas = [r["saida"] for r in self.visitas(cpf) if r["saida"]]
        return max(saidas, key=lambda s: datetime.strptime(s, FORMATO),
                   default="")

    # --- desativações -------------------------------------------------
    def desativacoes(self):
        return self._uma_vez("desativacoes", self.banco.listar_desativacoes)

    def desativacao(self, tipo, valor):
        """A desativação em vigor do CPF ou da placa, ou None."""
        d = next((d for d in self.desativacoes()
                  if d["tipo"] == tipo and d["valor"] == valor), None)
        chave = ("CPF " + self.exibir_cpf(valor) if tipo == "cpf"
                 else "Placa " + formatar_placa(valor))
        self._anotar("Desativação", chave,
                     "não está desativado(a)" if d is None else
                     f"DESATIVADO(A) desde {d['criado_em'][:10]}: "
                     f"{d['motivo']}")
        return d

    # --- veículos -----------------------------------------------------
    def _anotar_estadia(self, e):
        dono = "dono no campus" if e.get("responsavel_dentro") else \
            "dono fora do campus"
        self._anotar("Veículo", "Placa " + formatar_placa(e["placa"]),
                     f"no estacionamento desde {self.quando(e['entrada'])} · "
                     f"{e['nome']} · {dono}")

    def estadia_da_placa(self, placa):
        e = self._uma_vez(("placa", placa),
                          lambda: self.banco.estadia_aberta(placa=placa))
        if e is None:
            self._anotar("Veículo", "Placa " + formatar_placa(placa),
                         "não está no estacionamento")
        else:
            self._anotar_estadia(e)
        return e

    def estacionamento(self):
        """Os carros no estacionamento (banco.listar_estacionamento)."""
        return self._uma_vez("estacionamento",
                             self.banco.listar_estacionamento)

    def estadias_do_cpf(self, cpf):
        """Os carros desse responsável no estacionamento (com a marca de
        "dono no campus", como na lista Veículos)."""
        estadias = [e for e in self.estacionamento() if e["cpf"] == cpf]
        estadias.sort(key=lambda e: (datetime.strptime(e["entrada"], FORMATO),
                                     e["id"]))
        for e in estadias:
            self._anotar_estadia(e)
        return estadias

    def levaveis(self, cpf):
        """Carros de outro dono que o CPF pode levar (RN35)."""
        carros = self._uma_vez(("levaveis", cpf),
                               lambda: self.banco.veiculos_que_pode_levar(
                                   cpf, self.agora.date()))
        for e in carros:
            self._anotar("Autorizado", "Placa " + formatar_placa(e["placa"]),
                         "pode ser retirado por "
                         f"{self.exibir_cpf(cpf)} (RN35)")
        return carros

    def ocupacao(self):
        ocupadas, vagas, bloquear = self._uma_vez(
            "ocupacao", self.banco.ocupacao_estacionamento)
        texto = texto_lotacao(ocupadas, vagas) or "sem controle de vagas"
        self._anotar("Estacionamento", "Vagas",
                     texto + (" · bloqueia quando lotado" if bloquear else ""))
        return ocupadas, vagas, bloquear

    # --- o dia ----------------------------------------------------------
    def configuracao(self, tipo=None):
        """Os horários em vigor; anota o funcionamento de hoje e a janela
        da categoria `tipo`."""
        config = self._uma_vez("config", self.banco.ler_configuracao)
        hoje = self.agora.date()
        janelas = horarios.janelas_do_dia(config, hoje)
        dia = horarios.DIAS_SEMANA[hoje.weekday()].lower()
        aberto = (horarios.descrever_janelas(janelas) if janelas else
                  "fechado (" + horarios.motivo_fechado(config, hoje) + ")")
        self._anotar("Hoje", f"{hoje:%d/%m/%Y}", f"{dia}, {aberto}")
        if tipo:
            entrada = horarios.janelas_entrada(config, tipo, hoje)
            self._anotar("Categoria", tipo,
                         "entra " + horarios.descrever_janelas(entrada)
                         if entrada else "não entra hoje")
        return config
