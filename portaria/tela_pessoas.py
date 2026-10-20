"""
Aba Pessoas: todo mundo que já passou pela portaria, com nº de visitas,
última visita e quem está no campus. Permite corrigir os dados da pessoa
e começar uma nova entrada já preenchida.
"""

import tkinter as tk

from . import mensagens
from .componentes import (barra_busca, botao, cartao, combo, entrada,
                          entrada_numeros, entrada_placa, rotulo, tabela)
from .consultas import filtrar
from .estilo import COR, FONTE
from .validacao import (TIPOS_ACESSO, formatar_celular, formatar_cpf,
                        formatar_placa, normalizar, validar_campos)

COLUNAS = [("nome", "Nome", 190, "w"), ("cpf", "CPF", 105, "center"),
           ("celular", "Celular", 115, "center"),
           ("placa", "Placa", 75, "center"),
           ("tipo", "Tipo", 110, "w"), ("visitas", "Visitas", 60, "center"),
           ("ultima", "Última visita", 125, "center"),
           ("situacao", "Situação", 95, "center")]


class AbaPessoas:
    def __init__(self, aba, app):
        self.aba = aba
        self.app = app
        self.pessoas = []
        self.selecionada = None

        self._montar_busca()
        self._montar_tabela()
        self._montar_formulario()
        self.atualizar()

    # --------------------------------------------------------------
    # Montagem
    # --------------------------------------------------------------
    def _montar_busca(self):
        barra, self.busca = barra_busca(
            self.aba, "Buscar pessoa (nome, CPF, celular, placa ou tipo):")
        barra.pack(fill="x", padx=20, pady=(14, 4))
        self.busca.bind("<KeyRelease>", lambda e: self.atualizar())

    def _montar_tabela(self):
        quadro, self.tabela = tabela(self.aba, COLUNAS)
        quadro.pack(fill="both", expand=True, padx=20)
        self.tabela.tag_configure("dentro", foreground=COR["sucesso"])
        self.tabela.tag_configure("bloqueado", foreground=COR["erro"])
        self.tabela.bind("<<TreeviewSelect>>", self.ao_selecionar)
        self.tabela.bind("<Double-1>", lambda e: self.registrar_entrada())

        self.lbl_total = tk.Label(self.aba, text="", bg=COR["fundo"],
                                  fg=COR["texto_status"], font=FONTE["legenda"],
                                  anchor="w")
        self.lbl_total.pack(fill="x", padx=20, pady=(4, 0))

    def _montar_formulario(self):
        caixa, form = cartao(self.aba, faixa=False, padx=16, pady=12)
        caixa.pack(fill="x", padx=20, pady=(6, 14))
        form.columnconfigure((0, 1, 2, 3), weight=1, uniform="p")

        self.lbl_titulo = tk.Label(form, text="Selecione uma pessoa na lista",
                                   bg=COR["superficie"], fg=COR["texto"],
                                   font=FONTE["titulo_secao"])
        self.lbl_titulo.grid(row=0, column=0, columnspan=4, sticky="w",
                             pady=(0, 6))

        for coluna, texto in [(0, "Nome completo"), (2, "Celular"), (3, "Placa")]:
            rotulo(form, texto).grid(row=1, column=coluna, sticky="w")
        self.nome = entrada(form)
        self.nome.grid(row=2, column=0, columnspan=2, sticky="ew", padx=(0, 10))
        self.celular = entrada_numeros(form, 11)
        self.celular.grid(row=2, column=2, sticky="ew", padx=(0, 10))
        # Q04: aqui a placa ainda aceita qualquer tecla (como antes)
        caixa_placa, self.var_placa = entrada_placa(form, restringir=False)
        caixa_placa.grid(row=2, column=3, sticky="ew")

        rotulo(form, "Tipo de acesso").grid(row=3, column=0, sticky="w",
                                            pady=(8, 0))
        self.tipo = combo(form, TIPOS_ACESSO)
        self.tipo.grid(row=4, column=0, sticky="ew", padx=(0, 10))

        botoes = tk.Frame(form, bg=COR["superficie"])
        botoes.grid(row=4, column=1, columnspan=3, sticky="e")
        botao(botoes, "Salvar alterações", COR["secundario"], self.salvar)
        botao(botoes, "→ Registrar entrada", COR["primario"],
              self.registrar_entrada)

    # --------------------------------------------------------------
    # Dados
    # --------------------------------------------------------------
    def atualizar(self):
        ok, pessoas = self.app.tentar(self.app.banco.listar_pessoas)
        if not ok:
            return
        self.pessoas = pessoas
        ok, bloqueios = self.app.tentar(self.app.banco.listar_bloqueios)
        bloqueados = {b["valor"] for b in (bloqueios or []) if b["tipo"] == "cpf"}
        selecao = self.tabela.selection()
        self.tabela.delete(*self.tabela.get_children())
        for p in filtrar(pessoas, self.busca.get()):
            situacao = "No campus" if p["dentro_desde"] else "—"
            tags = ("dentro",) if p["dentro_desde"] else ()
            if p["cpf"] in bloqueados:
                situacao = ("No campus · " if p["dentro_desde"] else "") + "BLOQUEADO"
                tags = ("bloqueado",)
            self.tabela.insert("", "end", iid=str(p["id"]), values=(
                p["nome"], formatar_cpf(p["cpf"]), formatar_celular(p["celular"]),
                formatar_placa(p["placa"]) or "—", p["tipo"], p["visitas"],
                p["ultima_visita"] or "—", situacao), tags=tags)
        if selecao and self.tabela.exists(selecao[0]):
            self.tabela.selection_set(selecao[0])
        dentro = sum(1 for p in pessoas if p["dentro_desde"])
        self.lbl_total.config(text=f"Pessoas cadastradas: {len(pessoas)}   |   "
                                   f"No campus agora: {dentro}")

    def ao_selecionar(self, event=None):
        selecao = self.tabela.selection()
        if not selecao:
            return
        p = next(p for p in self.pessoas if p["id"] == int(selecao[0]))
        self.selecionada = p
        self.lbl_titulo.config(text=f"Dados de {p['nome']}  ·  CPF "
                                    f"{formatar_cpf(p['cpf'])}")
        for campo, valor in [(self.nome, p["nome"]), (self.celular, p["celular"])]:
            campo.delete(0, tk.END)
            campo.insert(0, valor)
        self.var_placa.set(p["placa"])
        self.tipo.set(p["tipo"])

    def _exigir_selecao(self):
        if self.selecionada is None:
            mensagens.aviso("Atenção", "Selecione uma pessoa na lista.")
            return False
        return True

    # --------------------------------------------------------------
    # Ações
    # --------------------------------------------------------------
    def salvar(self):
        if not self._exigir_selecao():
            return
        p = self.selecionada
        dados = normalizar(self.nome.get(), p["cpf"], self.celular.get(),
                           self.var_placa.get(), self.tipo.get(), "", "")
        ok, msg = validar_campos(dados)
        if not ok:
            mensagens.erro("Dados inválidos", msg)
            return
        ok, _ = self.app.tentar(self.app.banco.atualizar_pessoa, p["id"],
                                dados["nome"], dados["celular"], dados["placa"],
                                dados["tipo"], autor=self.app.autor)
        if not ok:
            return
        self.atualizar()
        self.ao_selecionar()
        mensagens.info("Pessoas", "Dados atualizados com sucesso!")

    def registrar_entrada(self):
        if not self._exigir_selecao():
            return
        p = self.selecionada
        if p["dentro_desde"]:
            mensagens.aviso(
                "Atenção", f"{p['nome']} já está no campus desde "
                           f"{p['dentro_desde']}.\nRegistre a saída na aba Cadastro.")
            return
        self.app.preencher_pessoa(p)
