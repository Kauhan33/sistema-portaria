"""
Tela de login. No primeiro uso (banco sem usuários) vira a tela de
"Primeiro acesso", que cria o administrador — não existe senha padrão.
"""

import tkinter as tk
from tkinter import ttk

from .dados import ErroDados
from .estilo import VERMELHO, cartao
from .usuarios import (SENHA_MINIMA, autenticar, gerar_hash, normalizar_login,
                       validar_novo_usuario)


class TelaLogin:
    def __init__(self, pai, banco, tentativas, ao_entrar):
        """ao_entrar(usuario) é chamado quando o login dá certo."""
        self.banco = banco
        self.tentativas = tentativas
        self.ao_entrar = ao_entrar

        caixa, self.miolo = cartao(pai)
        caixa.place(relx=0.5, rely=0.45, anchor="center")

        try:
            self.primeiro_acesso = banco is not None and not banco.tem_usuarios()
        except ErroDados:
            banco = None
        if banco is None:
            self._titulo("Banco de dados indisponível",
                         "Feche o programa e verifique se a pasta permite gravar.")
            return

        if self.primeiro_acesso:
            self._titulo("Primeiro acesso",
                         "Crie o usuário administrador do sistema.")
            self.campo_nome = self._campo("Nome completo")
            self.campo_login = self._campo("Usuário (ex.: maria.souza)")
            self.campo_senha = self._campo(
                f"Senha (mínimo {SENHA_MINIMA} caracteres)", senha=True)
            self.campo_confirmacao = self._campo("Confirmar senha", senha=True)
            acao, texto = self.criar_administrador, "Criar administrador e entrar"
        else:
            self._titulo("Entrar", "Informe seu usuário e senha.")
            self.campo_login = self._campo("Usuário")
            self.campo_senha = self._campo("Senha", senha=True)
            acao, texto = self.entrar, "Entrar"

        self.lbl_erro = tk.Label(self.miolo, text="", bg="white", fg=VERMELHO,
                                 font=("Segoe UI", 9), wraplength=300,
                                 justify="left")
        self.lbl_erro.pack(anchor="w", pady=(4, 0))
        self.btn_acao = tk.Button(self.miolo, text=texto, command=acao,
                                  bg="#0a9a5a", fg="white",
                                  activebackground="#0a9a5a",
                                  activeforeground="white", relief="flat",
                                  cursor="hand2", font=("Segoe UI", 10, "bold"),
                                  pady=7)
        self.btn_acao.pack(fill="x", pady=(10, 0))

        # Enter em qualquer campo confirma
        for campo in self.miolo.winfo_children():
            if isinstance(campo, ttk.Entry):
                campo.bind("<Return>", lambda e: acao())
                campo.bind("<KP_Enter>", lambda e: acao())
        primeiro = self.campo_nome if self.primeiro_acesso else self.campo_login
        primeiro.focus_set()

    def _titulo(self, titulo, subtitulo):
        tk.Label(self.miolo, text=titulo, bg="white", fg="#222",
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(self.miolo, text=subtitulo, bg="white", fg="#666",
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 10))

    def _campo(self, rotulo, senha=False):
        tk.Label(self.miolo, text=rotulo, bg="white", fg="#333",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(6, 2))
        # RNF02: a senha aparece como •••• enquanto é digitada
        campo = ttk.Entry(self.miolo, font=("Segoe UI", 11), width=32,
                          show="•" if senha else "")
        campo.pack(fill="x")
        return campo

    def erro(self, texto):
        self.lbl_erro.config(text=texto)

    # --------------------------------------------------------------
    # Ações
    # --------------------------------------------------------------
    def entrar(self):
        restante = self.tentativas.segundos_restantes()
        if restante:
            self.erro(f"Muitas tentativas erradas. Aguarde {restante} s.")
            return
        login, senha = self.campo_login.get(), self.campo_senha.get()
        if not login.strip() or not senha:
            self.erro("Informe o usuário e a senha.")
            return
        try:
            usuario = autenticar(self.banco, login, senha)
            if usuario is None:
                self.banco.registrar_evento(normalizar_login(login)[:30],
                                            "Login recusado")
        except ErroDados as e:
            self.erro(str(e))
            return

        if usuario is None:
            self.tentativas.registrar_falha()
            self.campo_senha.delete(0, tk.END)
            restante = self.tentativas.segundos_restantes()
            self.erro("Usuário ou senha incorretos." + (
                f"\nMuitas tentativas erradas. Aguarde {restante} s."
                if restante else ""))
            return
        self.tentativas.registrar_sucesso()
        self.ao_entrar(usuario)

    def criar_administrador(self):
        nome = " ".join(self.campo_nome.get().split())
        login = normalizar_login(self.campo_login.get())
        senha = self.campo_senha.get()
        ok, msg = validar_novo_usuario(nome, login, senha,
                                       self.campo_confirmacao.get(), "admin",
                                       logins_existentes=set())
        if not ok:
            self.erro(msg)
            return
        try:
            self.banco.criar_usuario(nome, login, "admin", gerar_hash(senha))
            usuario = autenticar(self.banco, login, senha)
        except ErroDados as e:
            self.erro(str(e))
            return
        self.ao_entrar(usuario)
