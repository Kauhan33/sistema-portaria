"""
Janela "Corrigir registro": corrige erro de digitação numa visita e mostra
o histórico daquele registro (quem cadastrou, deu saída, corrigiu e o quê).
"""

import tkinter as tk
from datetime import datetime

from . import mensagens
from .componentes import (Aviso, Campo, Dialogo, preencher_eventos,
                          rotulo_campo, tabela_eventos)
from .consultas import descrever_alteracoes
from .estilo import COR, FONTE, px
from .usuarios import pode_editar
from .validacao import (FORMATO_EXIBICAO, TIPOS_ACESSO,
                        checar_bloqueio_correcao, normalizar, validar)

SEM_HISTORICO = {"momento": "—", "usuario": "—", "acao": "Sem histórico",
                 "detalhe": "registro anterior ao histórico"}
DICA_DETALHE = "Clique numa linha para ver o detalhe completo."


class JanelaEdicao(Dialogo):
    def __init__(self, app, registro):
        self.app = app
        self.original = registro
        super().__init__(app.janela, f"Corrigir registro #{registro['id']}",
                         f"Entrada de {registro['nome']} em {registro['entrada']}."
                         " Toda correção fica no histórico.", largura=640,
                         ao_usar=app.registrar_uso)
        self._montar_campos()
        self._montar_historico()
        self.adicionar_botao("Salvar correção", self.salvar, "primario",
                             dica_tecla="Enter")
        self.adicionar_botao("Cancelar", self.fechar)
        self.abrir(confirmar=self.salvar, foco=self.nome)

    def _montar_campos(self):
        form = tk.Frame(self.miolo, bg=COR["superficie"])
        form.pack(fill="x")
        form.columnconfigure((0, 1, 2), weight=1, uniform="e")
        r = self.original

        def novo(texto, linha, coluna, valor, apoio="", juntas=1, **opcoes):
            frame, _ = rotulo_campo(form, texto, apoio)
            frame.grid(row=linha, column=coluna, sticky="w", pady=(0, px(4)))
            campo = Campo(form, **opcoes)
            campo.grid(row=linha + 1, column=coluna, columnspan=juntas,
                       sticky="ew", pady=(0, px(12)),
                       padx=(0, px(12)) if coluna + juntas < 3 else 0)
            campo.var.set(valor or "")      # valor do banco, sem passar pela digitação
            return campo

        # Q04: CPF, celular e placa com as mesmas restrições da Entrada e saída
        self.cpf = novo("CPF", 0, 0, r["cpf"], numeros=11).entrada
        self.nome = novo("Nome completo", 0, 1, r["nome"], juntas=2).entrada
        self.celular = novo("Celular", 2, 0, r["celular"], "só números",
                            numeros=11).entrada
        campo_placa = novo("Placa", 2, 1, r.get("placa", ""), "opcional",
                           placa=True)
        self.var_placa, self.caixa_placa = campo_placa.var, campo_placa.entrada
        self.tipo = novo("Tipo de acesso", 2, 2, r["tipo"],
                         opcoes=TIPOS_ACESSO).entrada
        self.entrada = novo("Entrada", 4, 0, r["entrada"], FORMATO_EXIBICAO).entrada
        self.saida = novo("Saída", 4, 1, r["saida"], "vazio = no campus").entrada
        self.cpf.config(font=FONTE["cpf"])

    def _montar_historico(self):
        tk.Label(self.miolo, text="Histórico deste registro", font=FONTE["rotulo"],
                 bg=COR["superficie"], fg=COR["texto"]
                 ).pack(anchor="w", pady=(px(6), px(6)))
        moldura = tk.Frame(self.miolo, bg=COR["superficie"],
                           highlightbackground=COR["borda"], highlightthickness=1)
        moldura.pack(fill="x")
        quadro, self.historico = tabela_eventos(
            moldura, (140, 80, 160, 260), altura=3, compacta=True)
        quadro.pack(fill="x")
        # detalhe completo da linha clicada (a coluna corta textos longos)
        self.faixa = Aviso(self.miolo)
        self.faixa.mostrar("neutro", DICA_DETALHE)
        self.faixa.pack(fill="x", pady=(px(10), 0))
        self.lbl_detalhe = self.faixa.lbl
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
            self.faixa.mostrar("info", f"{acao} por {usuario} em {momento}: "
                                       f"{detalhe}")

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
