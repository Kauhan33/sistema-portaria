"""
Página Bloqueios: CPFs e placas com acesso negado (RN12). Todos veem a
lista; só o administrador cria ou remove bloqueios. Remover não apaga: o
bloqueio fica guardado com quem removeu e quando ("Mostrar removidos").
"""

import tkinter as tk

from . import mensagens
from .componentes import (Alternador, Aviso, Botao, Cabecalho, Campo, Cartao,
                          Contador, inserir_linha, plural, rotulo_campo, tabela,
                          titulo_cartao)
from .consultas import encontrar_dentro
from .estilo import COR, ESPACO_CARTOES, ICONE, MARGEM, px
from .usuarios import pode_gerenciar_bloqueios
from .validacao import (BLOQUEADO, COM_ARTIGO, COM_DE, MAXIMO_CPF_OU_PLACA,
                        MAXIMO_MOTIVO, TIPOS_BLOQUEIO,
                        formatar_bloqueio, normalizar_bloqueio,
                        validar_bloqueio)

TIPO_POR_NOME = {nome: chave for chave, nome in TIPOS_BLOQUEIO.items()}
COLUNAS = [("tipo", "Tipo", 64, "w"),
           ("valor", "CPF ou placa", 124, "w"), ("nome", "Pessoa", 150, "w"),
           ("motivo", "Motivo", 230, "w"),
           ("criado", "Bloqueado em", 128, "w"), ("por", "Por", 90, "w"),
           ("situacao", "Removido em", 190, "w")]
SEM_REMOVIDOS = tuple(c[0] for c in COLUNAS[:-1])
AVISO_PORTEIRO = ("CPFs e placas desta lista não podem entrar. Só um "
                  "administrador cria ou remove bloqueios.")


class AbaBloqueios:
    def __init__(self, aba, app):
        self.aba = aba
        self.app = app
        self.bloqueios = []
        self.admin = pode_gerenciar_bloqueios(app.usuario)
        self.form = None
        self.btn_remover = None

        cab = Cabecalho(aba, "Bloqueios").posicionar()
        self.lbl_total = cab.subtitulo
        if self.admin:
            Botao(cab.acoes, "Novo bloqueio", self.alternar_formulario, "perigo",
                  icone=ICONE["mais"], fundo_pai=COR["fundo"]).pack()
            self._montar_formulario()
        else:
            faixa = Aviso(aba, fundo_pai=COR["fundo"])
            faixa.mostrar("info", AVISO_PORTEIRO)
            faixa.pack(fill="x", padx=px(MARGEM), pady=(0, px(ESPACO_CARTOES)))
        self._montar_lista()
        self.atualizar()

    # --------------------------------------------------------------
    # Montagem
    # --------------------------------------------------------------
    def _montar_formulario(self):
        """Cartão "Novo bloqueio" (fica fechado até o botão do cabeçalho)."""
        self.form = Cartao(self.aba, pad=18)
        m = self.form.miolo
        titulo_cartao(m, "Novo bloqueio").pack(anchor="w", pady=(0, px(10)))
        linha = tk.Frame(m, bg=COR["superficie"])
        linha.pack(fill="x")
        linha.columnconfigure(2, weight=1)
        for coluna, (texto, apoio) in enumerate([
                ("Tipo", ""), ("CPF ou placa", ""),
                ("Motivo", "aparece para o porteiro na hora da entrada")]):
            frame, _ = rotulo_campo(linha, texto, apoio)
            frame.grid(row=0, column=coluna, sticky="w", pady=(0, px(4)))
        self.tipo = Campo(linha, opcoes=TIPO_POR_NOME, largura=110).entrada
        self.tipo.master.grid(row=1, column=0, padx=(0, px(10)))
        self.tipo.set("CPF")
        self.valor = Campo(linha, largura=170,
                           maximo=MAXIMO_CPF_OU_PLACA).entrada
        self.valor.master.grid(row=1, column=1, padx=(0, px(10)))
        campo_motivo = Campo(linha, maximo=MAXIMO_MOTIVO)
        self.motivo = campo_motivo.entrada
        self.motivo.master.grid(row=1, column=2, sticky="ew", padx=(0, px(10)))
        # "123/200" discreto acima do campo, à direita do rótulo
        self.contador_motivo = Contador(linha, campo_motivo)
        self.contador_motivo.grid(row=0, column=2, sticky="e",
                                  padx=(0, px(10)), pady=(0, px(4)))
        self.motivo.bind("<Return>", lambda e: (self.bloquear(), "break")[1])
        botoes = tk.Frame(linha, bg=COR["superficie"])
        botoes.grid(row=1, column=3)
        Botao(botoes, "Cancelar", self.alternar_formulario, "fantasma"
              ).pack(side="left", padx=(0, px(8)))
        Botao(botoes, "Bloquear", self.bloquear, "primario").pack(side="left")

    def alternar_formulario(self):
        """Abre ou fecha o cartão de novo bloqueio."""
        if self.form.winfo_manager():
            self.form.pack_forget()
        else:
            self.form.pack(fill="x", padx=px(MARGEM),
                           pady=(0, px(ESPACO_CARTOES)), before=self.cartao_lista)
            self.valor.focus_set()

    def _montar_lista(self):
        self.cartao_lista = Cartao(self.aba, pad=0)
        self.cartao_lista.pack(fill="both", expand=True, padx=px(MARGEM),
                               pady=(0, px(MARGEM)))
        m = self.cartao_lista.miolo
        m.pack_configure(padx=px(1), pady=px(8))
        barra = tk.Frame(m, bg=COR["superficie"])
        barra.pack(fill="x", padx=px(19), pady=(px(6), px(12)))
        titulo_cartao(barra, "Lista de bloqueio").pack(side="left")
        self.ver_removidos = tk.BooleanVar(self.aba, value=False)
        Alternador(barra, "Mostrar removidos", self.ver_removidos,
                   self.atualizar).pack(side="left", padx=(px(20), 0))
        if self.admin:
            self.btn_remover = Botao(barra, "Remover bloqueio", self.remover,
                                     "secundario")
            self.btn_remover.pack(side="right")

        quadro, self.tabela = tabela(m, COLUNAS, situacao="Situação",
                                     mostrar=SEM_REMOVIDOS)
        quadro.pack(fill="both", expand=True, padx=px(12))
        self.tabela.bind("<<TreeviewSelect>>", lambda e: self._ao_selecionar())

    # --------------------------------------------------------------
    # Dados
    # --------------------------------------------------------------
    def atualizar(self):
        removidos = self.ver_removidos.get()
        ok, bloqueios = self.app.tentar(self.app.banco.listar_bloqueios,
                                        removidos)
        if not ok:
            return
        self.bloqueios = bloqueios
        self.tabela.configure(displaycolumns=[c[0] for c in COLUNAS]
                              if removidos else SEM_REMOVIDOS)
        self.tabela.delete(*self.tabela.get_children())
        for i, b in enumerate(bloqueios):
            valor = (self.app.exibir_cpf(b["valor"]) if b["tipo"] == "cpf"
                     else formatar_bloqueio(b["tipo"], b["valor"]))
            remocao = ("" if b["ativo"] else
                       f"{b['removido_em']} por {b['removido_por']}")
            inserir_linha(self.tabela, i, (
                TIPOS_BLOQUEIO[b["tipo"]], valor, b["nome"] or "—", b["motivo"],
                b["criado_em"], b["criado_por"], remocao), iid=str(b["id"]),
                situacao="Ativo" if b["ativo"] else "Removido",
                cor=COR["erro"] if b["ativo"] else COR["barra"],
                tags=() if b["ativo"] else ("apagado",))
        ativos = sum(1 for b in bloqueios if b["ativo"])
        self.lbl_total.config(text=plural(ativos, "bloqueio ativo",
                                          "bloqueios ativos")
                              if ativos else "Nenhum bloqueio ativo")
        self._ao_selecionar()

    def _ao_selecionar(self):
        """Remover só fica ativo com um bloqueio ativo selecionado."""
        if self.btn_remover is None:
            return
        selecao = self.tabela.selection()
        ativo = bool(selecao) and any(
            b["ativo"] for b in self.bloqueios if str(b["id"]) == selecao[0])
        self.btn_remover.definir_ativo(ativo)

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
        if not self.app.perguntar(
                mensagens.confirmar,
                "Confirmar bloqueio", f"Bloquear {COM_ARTIGO[tipo]} {rotulo}?\n"
                f"Motivo: {motivo}\n\n"
                "A entrada será recusada até um administrador remover o bloqueio."):
            return
        ok, _ = self.app.tentar(self.app.banco.bloquear, tipo, valor, motivo,
                                self.app.autor)
        if not ok:
            return
        self.valor.delete(0, tk.END)
        self.motivo.delete(0, tk.END)
        if self.form.winfo_manager():
            self.form.pack_forget()
        self.atualizar()
        self.app.atualizar_contadores()
        self.app.recarregar_registros()        # quem está no campus agora
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
        if not self.app.perguntar(
                mensagens.confirmar, "Remover bloqueio",
                f"Remover o bloqueio {COM_DE[b['tipo']]} {rotulo}?\n"
                "A entrada volta a ser permitida."):
            return
        self.app.tentar(self.app.banco.desbloquear, b["id"], self.app.autor)
        self.atualizar()
        self.app.atualizar_contadores()

