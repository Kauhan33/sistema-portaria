"""
Aba Bloqueios: CPFs e placas com acesso negado (RN12). Todos veem a lista;
só o administrador cria ou remove bloqueios. Remover não apaga: o bloqueio
fica guardado com quem removeu e quando.
"""

import tkinter as tk
from tkinter import ttk

from . import mensagens
from .consultas import encontrar_dentro
from .estilo import COR, FONTE, botao
from .usuarios import pode_gerenciar_bloqueios
from .validacao import (BLOQUEADO, COM_ARTIGO, COM_DE, TIPOS_BLOQUEIO,
                        formatar_bloqueio, normalizar_bloqueio,
                        validar_bloqueio)

TIPO_POR_NOME = {nome: chave for chave, nome in TIPOS_BLOQUEIO.items()}
COLUNAS = [("tipo", "Tipo", 60, "center"), ("valor", "CPF / Placa", 120, "center"),
           ("nome", "Pessoa", 150, "w"), ("motivo", "Motivo", 220, "w"),
           ("criado", "Bloqueado em", 125, "center"), ("por", "Por", 90, "w"),
           ("situacao", "Situação", 210, "w")]


class AbaBloqueios:
    def __init__(self, aba, app):
        self.aba = aba
        self.app = app
        self.bloqueios = []
        self.admin = pode_gerenciar_bloqueios(app.usuario)
        self.form = None

        if self.admin:
            self._montar_formulario()
        else:
            tk.Label(aba, text="CPFs e placas desta lista não podem entrar. "
                               "Só um administrador cria ou remove bloqueios.",
                     bg=COR["fundo"], fg=COR["erro"], font=FONTE["rotulo_secao"]
                     ).pack(anchor="w", padx=20, pady=(14, 0))
        self._montar_lista()
        self.atualizar()

    # --------------------------------------------------------------
    # Montagem
    # --------------------------------------------------------------
    def _montar_formulario(self):
        caixa = tk.Frame(self.aba, bg=COR["superficie"], highlightbackground=COR["borda"],
                         highlightthickness=1)
        caixa.pack(fill="x", padx=20, pady=(14, 0))
        tk.Frame(caixa, bg=COR["marca"], height=4).pack(fill="x")
        self.form = form = tk.Frame(caixa, bg=COR["superficie"])
        form.pack(fill="x", padx=16, pady=(10, 14))
        form.columnconfigure(2, weight=1)

        tk.Label(form, text="Novo bloqueio", bg=COR["superficie"], fg=COR["texto"],
                 font=FONTE["titulo_secao"]
                 ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
        for coluna, texto in enumerate(["Tipo", "CPF ou placa", "Motivo"]):
            tk.Label(form, text=texto, bg=COR["superficie"], fg=COR["texto_2"],
                     font=FONTE["rotulo"]
                     ).grid(row=1, column=coluna, sticky="w")
        self.tipo = ttk.Combobox(form, values=list(TIPO_POR_NOME), width=8,
                                 state="readonly", font=FONTE["corpo"])
        self.tipo.set("CPF")
        self.tipo.grid(row=2, column=0, sticky="w", padx=(0, 10))
        self.valor = ttk.Entry(form, font=FONTE["corpo"], width=18)
        self.valor.grid(row=2, column=1, sticky="w", padx=(0, 10))
        self.motivo = ttk.Entry(form, font=FONTE["corpo"])
        self.motivo.grid(row=2, column=2, sticky="ew", padx=(0, 10))
        botoes = tk.Frame(form, bg=COR["superficie"])
        botoes.grid(row=2, column=3, sticky="e")
        botao(botoes, "Bloquear", COR["erro"], self.bloquear)
        self.motivo.bind("<Return>", lambda e: (self.bloquear(), "break")[1])

    def _montar_lista(self):
        barra = tk.Frame(self.aba, bg=COR["fundo"])
        barra.pack(fill="x", padx=20, pady=(12, 4))
        tk.Label(barra, text="Lista de bloqueio", bg=COR["fundo"],
                 font=FONTE["rotulo_secao"]).pack(side="left")
        self.ver_removidos = tk.BooleanVar(value=False)
        ttk.Checkbutton(barra, text="Mostrar bloqueios removidos",
                        variable=self.ver_removidos,
                        command=self.atualizar).pack(side="right")

        quadro = tk.Frame(self.aba, bg=COR["fundo"])
        quadro.pack(fill="both", expand=True, padx=20)
        self.tabela = ttk.Treeview(quadro, show="headings", selectmode="browse",
                                   columns=[c[0] for c in COLUNAS])
        for col, titulo, larg, anc in COLUNAS:
            self.tabela.heading(col, text=titulo)
            self.tabela.column(col, width=larg, anchor=anc)
        self.tabela.tag_configure("removido", foreground=COR["desativado"])
        rolagem = ttk.Scrollbar(quadro, orient="vertical",
                                command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=rolagem.set)
        self.tabela.pack(side="left", fill="both", expand=True)
        rolagem.pack(side="right", fill="y")

        rodape = tk.Frame(self.aba, bg=COR["fundo"])
        rodape.pack(fill="x", padx=20, pady=(6, 14))
        self.lbl_total = tk.Label(rodape, text="", bg=COR["fundo"], fg=COR["texto_status"],
                                  font=FONTE["legenda"])
        self.lbl_total.pack(side="left")
        if self.admin:
            botao(rodape, "Remover bloqueio", COR["neutro"], self.remover, lado="right")

    # --------------------------------------------------------------
    # Dados
    # --------------------------------------------------------------
    def atualizar(self):
        ok, bloqueios = self.app.tentar(self.app.banco.listar_bloqueios,
                                        self.ver_removidos.get())
        if not ok:
            return
        self.bloqueios = bloqueios
        self.tabela.delete(*self.tabela.get_children())
        for b in bloqueios:
            situacao = ("Ativo" if b["ativo"] else
                        f"Removido {b['removido_em']} ({b['removido_por']})")
            self.tabela.insert("", "end", iid=str(b["id"]), values=(
                TIPOS_BLOQUEIO[b["tipo"]], formatar_bloqueio(b["tipo"], b["valor"]),
                b["nome"] or "—", b["motivo"], b["criado_em"], b["criado_por"],
                situacao), tags=() if b["ativo"] else ("removido",))
        ativos = sum(1 for b in bloqueios if b["ativo"])
        self.lbl_total.config(text=f"Bloqueios ativos: {ativos}")

    # --------------------------------------------------------------
    # Ações (só administrador)
    # --------------------------------------------------------------
    def _exigir_admin(self):
        if not self.admin:
            mensagens.erro("Acesso negado", "Somente o administrador "
                                            "gerencia a lista de bloqueio.")
        return self.admin

    def bloquear(self):
        if not self._exigir_admin():
            return
        tipo = TIPO_POR_NOME.get(self.tipo.get(), "")
        valor = normalizar_bloqueio(tipo, self.valor.get())
        motivo = " ".join(self.motivo.get().split())
        ok, ativos = self.app.tentar(self.app.banco.listar_bloqueios)
        if not ok:
            return
        ok, msg = validar_bloqueio(tipo, valor, motivo, ativos)
        if not ok:
            mensagens.erro("Dados inválidos", msg)
            return
        rotulo = formatar_bloqueio(tipo, valor)
        if not mensagens.confirmar(
                "Confirmar bloqueio", f"Bloquear {COM_ARTIGO[tipo]} {rotulo}?\n"
                f"Motivo: {motivo}\n\n"
                "A entrada será recusada até um administrador remover o bloqueio."):
            return
        ok, _ = self.app.tentar(self.app.banco.bloquear, tipo, valor, motivo,
                                self.app.usuario["login"])
        if not ok:
            return
        self.valor.delete(0, tk.END)
        self.motivo.delete(0, tk.END)
        self.atualizar()
        dentro = encontrar_dentro(self.app.registros, valor)
        if dentro:
            nomes = ", ".join(r["nome"] for r in dentro)
            mensagens.info("Atenção", f"{TIPOS_BLOQUEIO[tipo]} {rotulo} "
                                      f"{BLOQUEADO[tipo]}.\n\nNo campus "
                                      f"agora: {nomes}.\nO bloqueio vale "
                                      "para as próximas entradas.")

    def remover(self):
        if not self._exigir_admin():
            return
        selecao = self.tabela.selection()
        if not selecao:
            mensagens.aviso("Atenção", "Selecione um bloqueio na lista.")
            return
        b = next(b for b in self.bloqueios if b["id"] == int(selecao[0]))
        if not b["ativo"]:
            mensagens.info("Aviso", "Este bloqueio já foi removido.")
            return
        rotulo = formatar_bloqueio(b["tipo"], b["valor"])
        if not mensagens.confirmar("Remover bloqueio",
                                   f"Remover o bloqueio {COM_DE[b['tipo']]} "
                                   f"{rotulo}?\n"
                                   "A entrada volta a ser permitida."):
            return
        self.app.tentar(self.app.banco.desbloquear, b["id"],
                        self.app.usuario["login"])
        self.atualizar()
