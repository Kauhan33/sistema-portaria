"""
Janela "Corrigir registro": corrige erro de digitação numa visita e mostra
o histórico daquele registro (quem cadastrou, deu saída, corrigiu e o quê).
"""

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from .consultas import descrever_alteracoes
from .estilo import FUNDO, botao, cartao
from .usuarios import pode_editar
from .validacao import (FORMATO_EXIBICAO, TIPOS_ACESSO,
                        checar_bloqueio_correcao, normalizar, validar)


class JanelaEdicao:
    def __init__(self, app, registro):
        self.app = app
        self.original = registro

        self.janela = tk.Toplevel(app.janela)
        self.janela.title(f"Corrigir registro #{registro['id']}")
        self.janela.configure(bg=FUNDO)
        self.janela.resizable(False, False)
        self.janela.transient(app.janela)

        caixa, miolo = cartao(self.janela)
        caixa.pack(fill="both", expand=True, padx=16, pady=16)
        tk.Label(miolo, text="Corrigir registro", bg="white", fg="#222",
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(miolo, text=f"Entrada de {registro['nome']} em "
                             f"{registro['entrada']}. Toda correção fica "
                             "registrada no histórico abaixo.",
                 bg="white", fg="#666", font=("Segoe UI", 9)
                 ).pack(anchor="w", pady=(0, 8))

        self._montar_campos(miolo)

        linha = tk.Frame(miolo, bg="white")
        linha.pack(fill="x", pady=(12, 0))
        botao(linha, "Salvar correção", "#0a9a5a", self.salvar)
        botao(linha, "Cancelar", "#5a6b7b", self.fechar)

        self._montar_historico(miolo)

        self.janela.bind("<Return>", lambda e: self.salvar())
        self.janela.bind("<KP_Enter>", lambda e: self.salvar())
        self.janela.bind("<Escape>", lambda e: self.fechar())
        self.janela.protocol("WM_DELETE_WINDOW", self.fechar)
        self.nome.focus_set()
        try:
            self.janela.grab_set()     # modal: a janela principal espera
        except tk.TclError:
            pass                       # janela ainda não visível (ex.: testes)

    def _montar_campos(self, miolo):
        form = tk.Frame(miolo, bg="white")
        form.pack(fill="x")
        form.columnconfigure((0, 1), weight=1, uniform="e")
        r = self.original

        def campo(rotulo, linha, coluna, valor, **kw):
            tk.Label(form, text=rotulo, bg="white", fg="#333",
                     font=("Segoe UI", 9, "bold")
                     ).grid(row=linha, column=coluna, sticky="w", pady=(6, 2))
            entrada = ttk.Entry(form, font=("Segoe UI", 10), width=30, **kw)
            entrada.grid(row=linha + 1, column=coluna, sticky="ew",
                         padx=(0, 10) if coluna == 0 else 0)
            if valor:
                entrada.insert(0, valor)
            return entrada

        self.cpf = campo("CPF (somente números)", 0, 0, r["cpf"])
        self.nome = campo("Nome completo", 0, 1, r["nome"])
        self.celular = campo("Celular com DDD", 2, 0, r["celular"])
        self.var_placa = tk.StringVar(value=r.get("placa", ""))
        self.var_placa.trace_add("write", lambda *a: self.var_placa.set(
            self.var_placa.get().upper())
            if self.var_placa.get() != self.var_placa.get().upper() else None)
        campo("Placa do veículo", 2, 1, "", textvariable=self.var_placa)

        tk.Label(form, text="Tipo de acesso", bg="white", fg="#333",
                 font=("Segoe UI", 9, "bold")
                 ).grid(row=4, column=0, sticky="w", pady=(6, 2))
        self.tipo = ttk.Combobox(form, values=TIPOS_ACESSO, state="readonly",
                                 font=("Segoe UI", 10))
        self.tipo.set(r["tipo"])
        self.tipo.grid(row=5, column=0, sticky="ew", padx=(0, 10))

        self.entrada = campo(f"Entrada ({FORMATO_EXIBICAO})", 6, 0, r["entrada"])
        self.saida = campo(f"Saída ({FORMATO_EXIBICAO}) — vazio = no campus",
                           6, 1, r["saida"])

    def _montar_historico(self, miolo):
        tk.Label(miolo, text="Histórico deste registro", bg="white", fg="#222",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(14, 4))
        self.historico = ttk.Treeview(miolo, show="headings", height=5,
                                      columns=("momento", "usuario", "acao",
                                               "detalhe"))
        for col, titulo, larg in [("momento", "Data e hora", 130),
                                  ("usuario", "Usuário", 80),
                                  ("acao", "Ação", 130),
                                  ("detalhe", "Detalhe", 320)]:
            self.historico.heading(col, text=titulo)
            self.historico.column(col, width=larg, anchor="w")
        self.historico.pack(fill="x")
        # detalhe completo da linha clicada (a coluna corta textos longos)
        self.lbl_detalhe = tk.Label(miolo, text="Clique numa linha para ver "
                                    "o detalhe completo.", bg="white", fg="#666",
                                    font=("Segoe UI", 9), wraplength=640,
                                    justify="left")
        self.lbl_detalhe.pack(anchor="w", pady=(4, 0))
        self.historico.bind("<<TreeviewSelect>>", self._mostrar_detalhe)
        ok, eventos = self.app.tentar(self.app.banco.eventos_do_registro,
                                      self.original["id"])
        for e in eventos if ok else []:
            self.historico.insert("", "end", values=(
                e["momento"], e["usuario"], e["acao"], e["detalhe"]))
        if ok and not eventos:
            self.historico.insert("", "end", values=(
                "—", "—", "Sem histórico", "registro anterior ao histórico"))

    def _mostrar_detalhe(self, event=None):
        selecao = self.historico.selection()
        if selecao:
            valores = self.historico.item(selecao[0])["values"]
            momento, usuario, acao, detalhe = valores
            self.lbl_detalhe.config(text=f"{acao} por {usuario} em {momento}: "
                                         f"{detalhe}", fg="#222")

    # --------------------------------------------------------------
    # Ações
    # --------------------------------------------------------------
    def salvar(self):
        novo = normalizar(self.nome.get(), self.cpf.get(), self.celular.get(),
                          self.var_placa.get(), self.tipo.get(),
                          self.entrada.get(), self.saida.get())
        alteracoes = descrever_alteracoes(self.original, novo)
        if not alteracoes:
            messagebox.showinfo("Corrigir registro", "Nada foi alterado.",
                                parent=self.janela)
            return
        # o porteiro também não pode mover o registro para outro dia
        ok, msg = pode_editar(self.app.usuario, novo, datetime.now())
        if ok:
            outros = [r for r in self.app.registros
                      if r["id"] != self.original["id"]]
            ok, msg = validar(novo, outros)
        if not ok:
            messagebox.showerror("Dados inválidos", msg, parent=self.janela)
            return
        ok, ativos = self.app.tentar(self.app.banco.listar_bloqueios)
        if not ok:
            return
        ok, msg = checar_bloqueio_correcao(self.original, novo, ativos)
        if not ok:
            messagebox.showerror("Acesso negado", msg, parent=self.janela)
            return
        ok, _ = self.app.tentar(self.app.banco.editar, self.original["id"], novo,
                                alteracoes, autor=self.app.usuario["login"])
        if not ok:
            return
        self.app.registros = self.app.tentar(self.app.banco.listar)[1] \
            or self.app.registros
        self.app.atualizar_tabela(self.app.busca.get())
        self.app._avisar(f"✓ Registro de {novo['nome'].split()[0]} corrigido "
                         f"({len(alteracoes)} alteração(ões)).")
        self.fechar()

    def fechar(self):
        try:
            self.janela.grab_release()
        except tk.TclError:
            pass
        self.janela.destroy()
