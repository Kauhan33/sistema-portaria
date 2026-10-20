"""
Aba Usuários (só administrador): criar porteiros e administradores, ativar
ou desativar, redefinir senha e ver o histórico de ações do sistema.
"""

import tkinter as tk

from . import mensagens
from .componentes import (botao, campo, cartao, combo, grupo_campo,
                          preencher_eventos, rotulo_secao, tabela,
                          tabela_eventos)
from .estilo import COR, FONTE
from .usuarios import (PERFIS, gerar_hash, normalizar_login, pode_desativar,
                       validar_novo_usuario, validar_senha)

PERFIL_POR_NOME = {nome: chave for chave, nome in PERFIS.items()}
COLUNAS = [("login", "Usuário", 110, "w"), ("nome", "Nome", 200, "w"),
           ("perfil", "Perfil", 110, "center"),
           ("situacao", "Situação", 90, "center")]


class AbaUsuarios:
    def __init__(self, aba, app):
        self.aba = aba
        self.app = app
        self.usuarios = []

        # Em cima: formulário + lista (altura fixa); embaixo o histórico
        # ocupa o espaço que sobrar.
        topo = tk.Frame(aba, bg=COR["fundo"])
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
        tk.Label(miolo, text="Novo usuário", bg=COR["superficie"],
                 fg=COR["texto"], font=FONTE["titulo_cartao"]
                 ).pack(anchor="w", pady=(0, 4))

        def novo_campo(texto, senha=False):
            grupo, caixa_texto = campo(miolo, texto, width=28,
                                       show="•" if senha else "")
            grupo.pack(fill="x")
            return caixa_texto

        self.nome = novo_campo("Nome completo")
        self.login = novo_campo("Usuário (ex.: maria.souza)")
        self.senha = novo_campo("Senha", senha=True)
        self.confirmacao = novo_campo("Confirmar senha", senha=True)
        grupo = grupo_campo(miolo, "Perfil")
        grupo.pack(fill="x")
        self.perfil = combo(grupo, PERFIL_POR_NOME)
        self.perfil.set(PERFIS["porteiro"])
        self.perfil.pack(fill="x")

        linha = tk.Frame(miolo, bg=COR["superficie"])
        linha.pack(fill="x", pady=(14, 0))
        botao(linha, "+ Criar usuário", COR["primario"], self.criar)

    def _montar_lista(self, topo):
        lado = tk.Frame(topo, bg=COR["fundo"])
        lado.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
        rotulo_secao(lado, "Usuários do sistema").pack(anchor="w", pady=(0, 4))
        quadro, self.tabela = tabela(lado, COLUNAS, altura=6, rolagem=False)
        quadro.pack(fill="both", expand=True)
        self.tabela.tag_configure("inativo", foreground=COR["desativado"])

        botoes = tk.Frame(lado, bg=COR["fundo"])
        botoes.pack(fill="x", pady=(8, 0))
        botao(botoes, "Ativar / desativar", COR["atencao"], self.alternar_ativo)
        botao(botoes, "Redefinir senha", COR["secundario"], self.redefinir_senha)

    def _montar_historico(self, aba):
        baixo = tk.Frame(aba, bg=COR["fundo"])
        baixo.pack(fill="both", expand=True, padx=20, pady=(6, 14))
        rotulo_secao(baixo, "Histórico de ações (mais recentes primeiro)"
                     ).pack(anchor="w", pady=(0, 4))
        quadro, self.historico = tabela_eventos(baixo, (140, 100, 160, 420),
                                                altura=4)
        quadro.pack(fill="both", expand=True)

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
            preencher_eventos(self.historico, eventos)

    def _autor(self):
        return self.app.usuario["login"]

    def _selecionado(self):
        selecao = self.tabela.selection()
        if not selecao:
            mensagens.aviso("Atenção", "Selecione um usuário na lista.")
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
            mensagens.erro("Dados inválidos", msg)
            return
        ok, _ = self.app.tentar(self.app.banco.criar_usuario, nome, login, perfil,
                                gerar_hash(senha), autor=self._autor())
        if not ok:
            return
        for campo in (self.nome, self.login, self.senha, self.confirmacao):
            campo.delete(0, tk.END)
        self.perfil.set(PERFIS["porteiro"])
        self.atualizar()
        mensagens.info("Usuários", f"Usuário {login} criado com sucesso!")

    def alternar_ativo(self):
        alvo = self._selecionado()
        if alvo is None:
            return
        if alvo["ativo"]:
            admins = sum(1 for u in self.usuarios
                         if u["perfil"] == "admin" and u["ativo"])
            ok, msg = pode_desativar(alvo, self.app.usuario, admins)
            if not ok:
                mensagens.erro("Não permitido", msg)
                return
            if not mensagens.confirmar(
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
        senha = mensagens.pedir_senha(
            "Redefinir senha", f"Nova senha para {alvo['login']}:",
            parent=self.aba)
        if senha is None:
            return
        confirmacao = mensagens.pedir_senha(
            "Redefinir senha", "Digite a nova senha de novo:", parent=self.aba)
        if confirmacao is None:
            return
        ok, msg = validar_senha(senha, confirmacao)
        if not ok:
            mensagens.erro("Dados inválidos", msg)
            return
        ok, _ = self.app.tentar(self.app.banco.definir_senha, alvo["id"],
                                gerar_hash(senha), autor=self._autor())
        if ok:
            self.atualizar()
            mensagens.info("Usuários",
                           f"Senha de {alvo['login']} redefinida.")
