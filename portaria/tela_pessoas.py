"""
Aba Pessoas: todo mundo que já passou pela portaria, com nº de visitas,
última visita e quem está no campus. Permite corrigir os dados da pessoa
e começar uma nova entrada já preenchida.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from .consultas import filtrar
from .estilo import BORDA, FUNDO, botao, fonte_lbl
from .validacao import (TIPOS_ACESSO, formatar_celular, formatar_cpf,
                        formatar_placa, normalizar, validar_campos)

COLUNAS = [("nome", "Nome", 190, "w"), ("cpf", "CPF", 105, "center"),
           ("celular", "Celular", 115, "center"), ("placa", "Placa", 75, "center"),
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
        barra = tk.Frame(self.aba, bg=FUNDO)
        barra.pack(fill="x", padx=20, pady=(14, 4))
        tk.Label(barra, text="Buscar pessoa (nome, CPF, celular, placa ou tipo):",
                 bg=FUNDO, font=fonte_lbl).pack(side="left")
        self.busca = ttk.Entry(barra, font=("Segoe UI", 10))
        self.busca.pack(side="left", fill="x", expand=True, padx=8)
        self.busca.bind("<KeyRelease>", lambda e: self.atualizar())
        self.busca.bind("<Return>", lambda e: "break")

    def _montar_tabela(self):
        quadro = tk.Frame(self.aba, bg=FUNDO)
        quadro.pack(fill="both", expand=True, padx=20)
        self.tabela = ttk.Treeview(quadro, show="headings", selectmode="browse",
                                   columns=[c[0] for c in COLUNAS])
        for col, titulo, larg, anc in COLUNAS:
            self.tabela.heading(col, text=titulo)
            self.tabela.column(col, width=larg, anchor=anc)
        self.tabela.tag_configure("dentro", foreground="#0a8a50")
        self.tabela.tag_configure("bloqueado", foreground="#d9001b")
        rolagem = ttk.Scrollbar(quadro, orient="vertical",
                                command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=rolagem.set)
        self.tabela.pack(side="left", fill="both", expand=True)
        rolagem.pack(side="right", fill="y")
        self.tabela.bind("<<TreeviewSelect>>", self._ao_selecionar)
        self.tabela.bind("<Double-1>", lambda e: self.registrar_entrada())

        self.lbl_total = tk.Label(self.aba, text="", bg=FUNDO, fg="#444",
                                  font=("Segoe UI", 9), anchor="w")
        self.lbl_total.pack(fill="x", padx=20, pady=(4, 0))

    def _montar_formulario(self):
        caixa = tk.Frame(self.aba, bg="white", highlightbackground=BORDA,
                         highlightthickness=1)
        caixa.pack(fill="x", padx=20, pady=(6, 14))
        form = tk.Frame(caixa, bg="white")
        form.pack(fill="x", padx=16, pady=12)
        form.columnconfigure((0, 1, 2, 3), weight=1, uniform="p")

        self.lbl_titulo = tk.Label(form, text="Selecione uma pessoa na lista",
                                   bg="white", fg="#222",
                                   font=("Segoe UI", 11, "bold"))
        self.lbl_titulo.grid(row=0, column=0, columnspan=4, sticky="w",
                             pady=(0, 6))

        def rotulo(texto, coluna):
            tk.Label(form, text=texto, bg="white", fg="#333",
                     font=("Segoe UI", 9, "bold")
                     ).grid(row=1, column=coluna, sticky="w")

        rotulo("Nome completo", 0)
        self.nome = ttk.Entry(form, font=("Segoe UI", 10))
        self.nome.grid(row=2, column=0, columnspan=2, sticky="ew", padx=(0, 10))

        rotulo("Celular", 2)
        so_numeros = self.app.janela.register(
            lambda p: p == "" or (p.isascii() and p.isdigit() and len(p) <= 11))
        self.celular = ttk.Entry(form, font=("Segoe UI", 10), validate="key",
                                 validatecommand=(so_numeros, "%P"))
        self.celular.grid(row=2, column=2, sticky="ew", padx=(0, 10))

        rotulo("Placa", 3)
        self.var_placa = tk.StringVar()
        self.var_placa.trace_add("write", lambda *a: self.var_placa.set(
            self.var_placa.get().upper())
            if self.var_placa.get() != self.var_placa.get().upper() else None)
        ttk.Entry(form, font=("Segoe UI", 10), textvariable=self.var_placa
                  ).grid(row=2, column=3, sticky="ew")

        tk.Label(form, text="Tipo de acesso", bg="white", fg="#333",
                 font=("Segoe UI", 9, "bold")
                 ).grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.tipo = ttk.Combobox(form, values=TIPOS_ACESSO, state="readonly",
                                 font=("Segoe UI", 10))
        self.tipo.grid(row=4, column=0, sticky="ew", padx=(0, 10))

        botoes = tk.Frame(form, bg="white")
        botoes.grid(row=4, column=1, columnspan=3, sticky="e")
        botao(botoes, "Salvar alterações", "#1f6fd1", self.salvar)
        botao(botoes, "→ Registrar entrada", "#0a9a5a", self.registrar_entrada)

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

    def _ao_selecionar(self, event=None):
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
            messagebox.showwarning("Atenção", "Selecione uma pessoa na lista.")
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
            messagebox.showerror("Dados inválidos", msg)
            return
        ok, _ = self.app.tentar(self.app.banco.atualizar_pessoa, p["id"],
                                dados["nome"], dados["celular"], dados["placa"],
                                dados["tipo"], autor=self.app.usuario["login"])
        if not ok:
            return
        self.atualizar()
        self._ao_selecionar()
        messagebox.showinfo("Pessoas", "Dados atualizados com sucesso!")

    def registrar_entrada(self):
        if not self._exigir_selecao():
            return
        p = self.selecionada
        if p["dentro_desde"]:
            messagebox.showwarning(
                "Atenção", f"{p['nome']} já está no campus desde "
                           f"{p['dentro_desde']}.\nRegistre a saída na aba Cadastro.")
            return
        self.app.preencher_pessoa(p)
