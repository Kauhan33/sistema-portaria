"""
Janela "Corrigir registro": corrige erro de digitação numa visita e mostra
o histórico daquele registro (quem cadastrou, deu saída, corrigiu e o quê).
"""

import tkinter as tk
from datetime import datetime

from . import mensagens
from .componentes import (botao, campo, cartao, combo, entrada_placa,
                          grupo_campo, preencher_eventos, tabela_eventos)
from .consultas import descrever_alteracoes
from .estilo import COR, FONTE
from .usuarios import pode_editar
from .validacao import (FORMATO_EXIBICAO, TIPOS_ACESSO,
                        checar_bloqueio_correcao, normalizar, validar)

SEM_HISTORICO = {"momento": "—", "usuario": "—", "acao": "Sem histórico",
                 "detalhe": "registro anterior ao histórico"}


class JanelaEdicao:
    def __init__(self, app, registro):
        self.app = app
        self.original = registro

        self.janela = tk.Toplevel(app.janela)
        self.janela.title(f"Corrigir registro #{registro['id']}")
        self.janela.configure(bg=COR["fundo"])
        self.janela.resizable(False, False)
        self.janela.transient(app.janela)

        caixa, miolo = cartao(self.janela)
        caixa.pack(fill="both", expand=True, padx=16, pady=16)
        tk.Label(miolo, text="Corrigir registro", bg=COR["superficie"],
                 fg=COR["texto"], font=FONTE["titulo_dialogo"]
                 ).pack(anchor="w")
        tk.Label(miolo, text=f"Entrada de {registro['nome']} em "
                             f"{registro['entrada']}. Toda correção fica "
                             "registrada no histórico abaixo.",
                 bg=COR["superficie"], fg=COR["texto_3"], font=FONTE["legenda"]
                 ).pack(anchor="w", pady=(0, 8))

        self._montar_campos(miolo)

        linha = tk.Frame(miolo, bg=COR["superficie"])
        linha.pack(fill="x", pady=(12, 0))
        botao(linha, "Salvar correção", COR["primario"], self.salvar)
        botao(linha, "Cancelar", COR["neutro"], self.fechar)

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
        form = tk.Frame(miolo, bg=COR["superficie"])
        form.pack(fill="x")
        form.columnconfigure((0, 1), weight=1, uniform="e")
        r = self.original

        def posicionar(grupo, linha, coluna):
            grupo.grid(row=linha, column=coluna, sticky="ew",
                       padx=(0, 10) if coluna == 0 else 0)

        def novo_campo(texto, linha, coluna, valor):
            grupo, caixa = campo(form, texto, width=30)
            posicionar(grupo, linha, coluna)
            if valor:
                caixa.insert(0, valor)
            return caixa

        self.cpf = novo_campo("CPF (somente números)", 0, 0, r["cpf"])
        self.nome = novo_campo("Nome completo", 0, 1, r["nome"])
        self.celular = novo_campo("Celular com DDD", 1, 0, r["celular"])
        grupo = grupo_campo(form, "Placa do veículo")
        posicionar(grupo, 1, 1)
        # Q04: aqui a placa ainda aceita qualquer tecla (como antes)
        caixa_placa, self.var_placa = entrada_placa(
            grupo, tk.StringVar(value=r.get("placa", "")), restringir=False,
            width=30)
        caixa_placa.pack(fill="x")

        grupo = grupo_campo(form, "Tipo de acesso")
        posicionar(grupo, 2, 0)
        self.tipo = combo(grupo, TIPOS_ACESSO)
        self.tipo.set(r["tipo"])
        self.tipo.pack(fill="x")

        self.entrada = novo_campo(f"Entrada ({FORMATO_EXIBICAO})", 3, 0,
                                  r["entrada"])
        self.saida = novo_campo(
            f"Saída ({FORMATO_EXIBICAO}) — vazio = no campus", 3, 1, r["saida"])

    def _montar_historico(self, miolo):
        tk.Label(miolo, text="Histórico deste registro", bg=COR["superficie"],
                 fg=COR["texto"], font=FONTE["rotulo_secao"]
                 ).pack(anchor="w", pady=(14, 4))
        quadro, self.historico = tabela_eventos(
            miolo, (130, 80, 130, 320), altura=5, rolagem=False,
            fundo=COR["superficie"])
        quadro.pack(fill="x")
        # detalhe completo da linha clicada (a coluna corta textos longos)
        self.lbl_detalhe = tk.Label(
            miolo, text="Clique numa linha para ver o detalhe completo.",
            bg=COR["superficie"], fg=COR["texto_3"], font=FONTE["legenda"],
            wraplength=640, justify="left")
        self.lbl_detalhe.pack(anchor="w", pady=(4, 0))
        self.historico.bind("<<TreeviewSelect>>", self.mostrar_detalhe)
        ok, eventos = self.app.tentar(self.app.banco.eventos_do_registro,
                                      self.original["id"])
        if not ok:
            return
        preencher_eventos(self.historico, eventos or [SEM_HISTORICO])

    def mostrar_detalhe(self, event=None):
        selecao = self.historico.selection()
        if selecao:
            valores = self.historico.item(selecao[0])["values"]
            momento, usuario, acao, detalhe = valores
            self.lbl_detalhe.config(text=f"{acao} por {usuario} em {momento}: "
                                         f"{detalhe}", fg=COR["texto"])

    # --------------------------------------------------------------
    # Ações
    # --------------------------------------------------------------
    def salvar(self):
        novo = normalizar(self.nome.get(), self.cpf.get(), self.celular.get(),
                          self.var_placa.get(), self.tipo.get(),
                          self.entrada.get(), self.saida.get())
        alteracoes = descrever_alteracoes(self.original, novo)
        if not alteracoes:
            mensagens.info("Corrigir registro", "Nada foi alterado.",
                           parent=self.janela)
            return
        # o porteiro também não pode mover o registro para outro dia
        ok, msg = pode_editar(self.app.usuario, novo, datetime.now())
        if ok:
            ok, anteriores = self.app.tentar(self.app.banco.listar_por_cpf,
                                             novo["cpf"])
            if not ok:
                return
            outros = [r for r in anteriores if r["id"] != self.original["id"]]
            ok, msg = validar(novo, outros)
        if not ok:
            mensagens.erro("Dados inválidos", msg, parent=self.janela)
            return
        ok, ativos = self.app.tentar(self.app.banco.listar_bloqueios)
        if not ok:
            return
        ok, msg = checar_bloqueio_correcao(self.original, novo, ativos)
        if not ok:
            mensagens.erro("Acesso negado", msg, parent=self.janela)
            return
        if not self.app.gravar(self.app.banco.editar, self.original["id"],
                               novo, alteracoes):
            return
        self.app.atualizar_tabela()
        self.app.avisar(f"Registro de {novo['nome'].split()[0]} corrigido "
                        f"({len(alteracoes)} alteração(ões)).")
        self.fechar()

    def fechar(self):
        try:
            self.janela.grab_release()
        except tk.TclError:
            pass
        self.janela.destroy()
