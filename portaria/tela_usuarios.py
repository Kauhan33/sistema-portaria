"""
Aba Usuários (só administrador): criar porteiros e administradores, ativar
ou desativar, redefinir senha e ver o histórico de ações do sistema.
"""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .estilo import FUNDO, botao, cartao, fonte_lbl
from .usuarios import (PERFIS, gerar_hash, normalizar_login, pode_desativar,
                       validar_novo_usuario, validar_senha)

PERFIL_POR_NOME = {nome: chave for chave, nome in PERFIS.items()}


class AbaUsuarios:
    def __init__(self, aba, app):
        self.aba = aba
        self.app = app
        self.usuarios = []

        # Em cima: formulário + lista (altura fixa); embaixo o histórico
        # ocupa o espaço que sobrar.
        topo = tk.Frame(aba, bg=FUNDO)
        topo.pack(fill="x", padx=20, pady=(14, 6))
        topo.columnconfigure(1, weight=1)

        self._montar_formulario(topo)
        self._montar_lista(topo)
        self._montar_historico(aba)
        self.atualizar()

    # --------------------------------------------------------------
    # Montagem
    # --------------------------------------------------------------
    def _montar_formulario(self, topo):
        caixa, miolo = cartao(topo)
        caixa.grid(row=0, column=0, sticky="ns")
        tk.Label(miolo, text="Novo usuário", bg="white", fg="#222",
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 4))

        def campo(rotulo, senha=False):
            tk.Label(miolo, text=rotulo, bg="white", fg="#333",
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(6, 2))
            entrada = ttk.Entry(miolo, font=("Segoe UI", 10), width=28,
                                show="•" if senha else "")
            entrada.pack(fill="x")
            return entrada

        self.nome = campo("Nome completo")
        self.login = campo("Usuário (ex.: maria.souza)")
        self.senha = campo("Senha", senha=True)
        self.confirmacao = campo("Confirmar senha", senha=True)
        tk.Label(miolo, text="Perfil", bg="white", fg="#333",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(6, 2))
        self.perfil = ttk.Combobox(miolo, values=list(PERFIL_POR_NOME),
                                   state="readonly", font=("Segoe UI", 10))
        self.perfil.set(PERFIS["porteiro"])
        self.perfil.pack(fill="x")

        linha = tk.Frame(miolo, bg="white")
        linha.pack(fill="x", pady=(14, 0))
        botao(linha, "+ Criar usuário", "#0a9a5a", self.criar)

    def _montar_lista(self, topo):
        lado = tk.Frame(topo, bg=FUNDO)
        lado.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
        tk.Label(lado, text="Usuários do sistema", bg=FUNDO,
                 font=fonte_lbl).pack(anchor="w", pady=(0, 4))
        self.tabela = ttk.Treeview(lado, show="headings", selectmode="browse",
                                   columns=("login", "nome", "perfil", "situacao"),
                                   height=6)
        for col, titulo, larg in [("login", "Usuário", 110),
                                  ("nome", "Nome", 200),
                                  ("perfil", "Perfil", 110),
                                  ("situacao", "Situação", 90)]:
            self.tabela.heading(col, text=titulo)
            self.tabela.column(col, width=larg,
                               anchor="w" if col in ("login", "nome") else "center")
        self.tabela.pack(fill="both", expand=True)
        self.tabela.tag_configure("inativo", foreground="#999")

        botoes = tk.Frame(lado, bg=FUNDO)
        botoes.pack(fill="x", pady=(8, 0))
        botao(botoes, "Ativar / desativar", "#e08a00", self.alternar_ativo)
        botao(botoes, "Redefinir senha", "#1f6fd1", self.redefinir_senha)

    def _montar_historico(self, aba):
        baixo = tk.Frame(aba, bg=FUNDO)
        baixo.pack(fill="both", expand=True, padx=20, pady=(6, 14))
        tk.Label(baixo, text="Histórico de ações (mais recentes primeiro)",
                 bg=FUNDO, font=fonte_lbl).pack(anchor="w", pady=(0, 4))
        quadro = tk.Frame(baixo, bg=FUNDO)
        quadro.pack(fill="both", expand=True)
        self.historico = ttk.Treeview(quadro, show="headings", height=4,
                                      columns=("momento", "usuario", "acao",
                                               "detalhe"))
        for col, titulo, larg in [("momento", "Data e hora", 140),
                                  ("usuario", "Usuário", 100),
                                  ("acao", "Ação", 160),
                                  ("detalhe", "Detalhe", 420)]:
            self.historico.heading(col, text=titulo)
            self.historico.column(col, width=larg, anchor="w")
        rolagem = ttk.Scrollbar(quadro, orient="vertical",
                                command=self.historico.yview)
        self.historico.configure(yscrollcommand=rolagem.set)
        self.historico.pack(side="left", fill="both", expand=True)
        rolagem.pack(side="right", fill="y")

    # --------------------------------------------------------------
    # Dados
    # --------------------------------------------------------------
    def atualizar(self):
        ok, usuarios = self.app.tentar(self.app.banco.listar_usuarios)
        if ok:
            self.usuarios = usuarios
            self.tabela.delete(*self.tabela.get_children())
            for u in usuarios:
                self.tabela.insert("", "end", iid=str(u["id"]), values=(
                    u["login"], u["nome"], PERFIS[u["perfil"]],
                    "Ativo" if u["ativo"] else "Desativado"),
                    tags=() if u["ativo"] else ("inativo",))
        ok, eventos = self.app.tentar(self.app.banco.listar_eventos)
        if ok:
            self.historico.delete(*self.historico.get_children())
            for e in eventos:
                self.historico.insert("", "end", values=(
                    e["momento"], e["usuario"], e["acao"], e["detalhe"]))

    def _autor(self):
        return self.app.usuario["login"]

    def _selecionado(self):
        selecao = self.tabela.selection()
        if not selecao:
            messagebox.showwarning("Atenção", "Selecione um usuário na lista.")
            return None
        return next(u for u in self.usuarios if u["id"] == int(selecao[0]))

    # --------------------------------------------------------------
    # Ações
    # --------------------------------------------------------------
    def criar(self):
        nome = " ".join(self.nome.get().split())
        login = normalizar_login(self.login.get())
        senha = self.senha.get()
        perfil = PERFIL_POR_NOME.get(self.perfil.get(), "")
        ok, msg = validar_novo_usuario(nome, login, senha, self.confirmacao.get(),
                                       perfil, {u["login"] for u in self.usuarios})
        if not ok:
            messagebox.showerror("Dados inválidos", msg)
            return
        ok, _ = self.app.tentar(self.app.banco.criar_usuario, nome, login, perfil,
                                gerar_hash(senha), autor=self._autor())
        if not ok:
            return
        for campo in (self.nome, self.login, self.senha, self.confirmacao):
            campo.delete(0, tk.END)
        self.perfil.set(PERFIS["porteiro"])
        self.atualizar()
        messagebox.showinfo("Usuários", f"Usuário {login} criado com sucesso!")

    def alternar_ativo(self):
        alvo = self._selecionado()
        if alvo is None:
            return
        if alvo["ativo"]:
            admins = sum(1 for u in self.usuarios
                         if u["perfil"] == "admin" and u["ativo"])
            ok, msg = pode_desativar(alvo, self.app.usuario, admins)
            if not ok:
                messagebox.showerror("Não permitido", msg)
                return
            if not messagebox.askyesno(
                    "Confirmar", f"Desativar o usuário {alvo['login']}?\n"
                                 "Ele não conseguirá mais entrar no sistema."):
                return
        self.app.tentar(self.app.banco.definir_ativo, alvo["id"],
                        not alvo["ativo"], autor=self._autor())
        self.atualizar()

    def redefinir_senha(self):
        alvo = self._selecionado()
        if alvo is None:
            return
        senha = simpledialog.askstring(
            "Redefinir senha", f"Nova senha para {alvo['login']}:",
            show="•", parent=self.aba)
        if senha is None:
            return
        confirmacao = simpledialog.askstring(
            "Redefinir senha", "Digite a nova senha de novo:",
            show="•", parent=self.aba)
        if confirmacao is None:
            return
        ok, msg = validar_senha(senha, confirmacao)
        if not ok:
            messagebox.showerror("Dados inválidos", msg)
            return
        ok, _ = self.app.tentar(self.app.banco.definir_senha, alvo["id"],
                                gerar_hash(senha), autor=self._autor())
        if ok:
            self.atualizar()
            messagebox.showinfo("Usuários",
                                f"Senha de {alvo['login']} redefinida.")
