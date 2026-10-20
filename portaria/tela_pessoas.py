"""
Página Pessoas: lista + ficha. À esquerda, todo mundo que já passou pela
portaria (busca no banco, banco.buscar_pessoas); à direita, a ficha da
pessoa escolhida: placa desenhada, número de visitas, faixa de bloqueio e
o formulário para corrigir o cadastro ou começar uma nova entrada.
"""

import tkinter as tk

from . import mensagens
from .componentes import (Aviso, Botao, Cabecalho, Campo, Cartao, Placa,
                          inserir_linha, plural, rotulo_campo, tabela,
                          titulo_cartao)
from .estilo import (COR, ESPACO_CARTOES, FONTE, ICONE, MARGEM, fonte_icone,
                     px)
from .validacao import (TIPOS_ACESSO, formatar_celular, formatar_placa,
                        normalizar, validar_campos)

COLUNAS = [("nome", "Nome", 190, "w"), ("cpf", "CPF", 118, "w"),
           ("celular", "Celular", 115, "w"), ("placa", "Placa", 80, "w"),
           ("tipo", "Tipo", 110, "w"), ("visitas", "Visitas", 64, "center"),
           ("ultima", "Última visita", 128, "w"),
           ("situacao", "Situação", 95, "w")]
# a ficha mostra o resto; os values continuam completos
COLUNAS_VISIVEIS = ("nome", "cpf", "visitas", "ultima")
LIMITE_BUSCA = 200
SEM_SELECAO = "Escolha uma pessoa na lista para ver a ficha."


class AbaPessoas:
    def __init__(self, aba, app):
        self.aba = aba
        self.app = app
        self.pessoas = []
        self.bloqueados = {}          # cpf -> motivo do bloqueio ativo
        self.selecionada = None

        cab = Cabecalho(aba, "Pessoas").posicionar()
        self.lbl_total = cab.subtitulo
        corpo = tk.Frame(aba, bg=COR["fundo"])
        corpo.pack(fill="both", expand=True, padx=px(MARGEM),
                   pady=(0, px(MARGEM)))
        self._montar_ficha(corpo)
        self._montar_lista(corpo)
        self.atualizar()

    # --------------------------------------------------------------
    # Montagem
    # --------------------------------------------------------------
    def _montar_lista(self, corpo):
        cartao = Cartao(corpo, pad=0)
        cartao.pack(side="left", fill="both", expand=True,
                    padx=(0, px(ESPACO_CARTOES)))
        m = cartao.miolo
        m.pack_configure(padx=px(1), pady=px(8))
        barra = tk.Frame(m, bg=COR["superficie"])
        barra.pack(fill="x", padx=px(19), pady=(px(6), px(12)))
        campo = Campo(barra, icone=ICONE["busca"],
                      dica_vazio="Buscar por nome, CPF, celular, placa ou tipo")
        campo.pack(fill="x")
        self.busca = campo.entrada
        self.busca.bind("<KeyRelease>", lambda e: self.atualizar())
        self.busca.bind("<Return>", lambda e: "break")

        rodape = tk.Frame(m, bg=COR["superficie"])
        rodape.pack(side="bottom", fill="x", padx=px(19), pady=(px(8), px(2)))
        self.lbl_status = tk.Label(rodape, text="", font=FONTE["dica"],
                                   bg=COR["superficie"], fg=COR["texto_3"])
        self.lbl_status.pack(side="left")

        quadro, self.tabela = tabela(m, COLUNAS, situacao="Situação",
                                     mostrar=COLUNAS_VISIVEIS)
        quadro.pack(fill="both", expand=True, padx=px(12))
        self.tabela.bind("<<TreeviewSelect>>", self.ao_selecionar)
        self.tabela.bind("<Double-1>", lambda e: self.registrar_entrada())

    def _montar_ficha(self, corpo):
        cartao = Cartao(corpo, pad=20)
        cartao.config(width=px(372))
        cartao.pack_propagate(False)
        cartao.pack(side="right", fill="y")
        fundo = COR["superficie"]

        # estado vazio (nada escolhido)
        self.vazio = tk.Frame(cartao.miolo, bg=fundo)
        self.vazio.place(relx=0.5, rely=0.4, anchor="center")
        tk.Label(self.vazio, text=ICONE["pessoa"], font=fonte_icone(28),
                 bg=fundo, fg=COR["texto_3"]).pack()
        tk.Label(self.vazio, text=SEM_SELECAO, font=FONTE["corpo"], bg=fundo,
                 fg=COR["texto_2"], wraplength=px(240)).pack(pady=(px(10), 0))

        self.conteudo = tk.Frame(cartao.miolo, bg=fundo)
        c = self.conteudo
        self.lbl_titulo = titulo_cartao(c, "")
        self.lbl_titulo.pack(anchor="w")
        self.lbl_cpf = tk.Label(c, font=FONTE["cpf"], bg=fundo,
                                fg=COR["texto_2"])
        self.lbl_cpf.pack(anchor="w")

        linha = tk.Frame(c, bg=fundo)
        linha.pack(fill="x", pady=(px(12), 0))
        self.desenho_placa = Placa(linha, fundo, largura=170)
        self.desenho_placa.pack(side="left")
        numeros = tk.Frame(linha, bg=fundo)
        numeros.pack(side="left", padx=(px(18), 0))
        self.lbl_visitas = self._numero(numeros, "visitas")
        self.lbl_ultima = self._numero(numeros, "última vinda")

        self.faixa = Aviso(c)
        self.separador = tk.Frame(c, bg=COR["borda"], height=1)
        self.separador.pack(fill="x", pady=px(14))

        form = tk.Frame(c, bg=fundo)
        form.pack(fill="x")
        form.columnconfigure((0, 1), weight=1, uniform="p")

        def grupo(texto, linha_, coluna, campo, juntas=1, apoio=""):
            frame, _ = rotulo_campo(form, texto, apoio)
            frame.grid(row=linha_, column=coluna, columnspan=juntas, sticky="w",
                       pady=(0, px(4)))
            campo.grid(row=linha_ + 1, column=coluna, columnspan=juntas,
                       sticky="ew", pady=(0, px(12)),
                       padx=(0, px(10)) if coluna == 0 and juntas == 1 else 0)
            return campo

        self.campo_nome = grupo("Nome completo", 0, 0, Campo(form), juntas=2)
        self.nome = self.campo_nome.entrada
        # Q04: as mesmas restrições de digitação da Entrada e saída
        self.celular = grupo("Celular", 2, 0, Campo(form, numeros=11)).entrada
        campo_placa = grupo("Placa", 2, 1, Campo(form, placa=True),
                            apoio="opcional")
        self.var_placa, self.caixa_placa = campo_placa.var, campo_placa.entrada
        self.var_placa.trace_add("write", lambda *a: self._mostrar_placa())
        self.tipo = grupo("Tipo de acesso", 4, 0, Campo(form, opcoes=TIPOS_ACESSO),
                          juntas=2).entrada

        botoes = tk.Frame(c, bg=fundo)
        botoes.pack(fill="x", pady=(px(4), 0))
        Botao(botoes, "Registrar entrada", self.registrar_entrada,
              "primario").pack(side="left")
        Botao(botoes, "Salvar alterações", self.salvar,
              "secundario").pack(side="left", padx=(px(8), 0))

    @staticmethod
    def _numero(pai, legenda):
        bloco = tk.Frame(pai, bg=COR["superficie"])
        bloco.pack(anchor="w")
        valor = tk.Label(bloco, text="—", font=FONTE["numero"],
                         bg=COR["superficie"], fg=COR["texto"])
        valor.pack(anchor="w")
        tk.Label(bloco, text=legenda, font=FONTE["dica"], bg=COR["superficie"],
                 fg=COR["texto_3"]).pack(anchor="w")
        return valor

    # --------------------------------------------------------------
    # Dados
    # --------------------------------------------------------------
    def atualizar(self):
        ok, pessoas = self.app.tentar(self.app.banco.buscar_pessoas,
                                      self.busca.get(), LIMITE_BUSCA)
        if not ok:
            return
        self.pessoas = pessoas
        ok, bloqueios = self.app.tentar(self.app.banco.listar_bloqueios)
        self.bloqueados = {b["valor"]: b["motivo"] for b in (bloqueios or [])
                           if b["tipo"] == "cpf"}
        selecao = self.tabela.selection()
        self.tabela.delete(*self.tabela.get_children())
        for i, p in enumerate(pessoas):
            bloqueado = p["cpf"] in self.bloqueados
            if bloqueado:
                situacao = ("No campus · " if p["dentro_desde"] else "") + "Bloqueado"
                texto, cor = "Bloqueado", COR["erro"]
            elif p["dentro_desde"]:
                situacao = texto = "No campus"
                cor = COR["sucesso"]
            else:
                situacao, texto, cor = "—", "Fora", COR["barra"]
            inserir_linha(self.tabela, i, (
                p["nome"], self.app.exibir_cpf(p["cpf"]),
                formatar_celular(p["celular"]), formatar_placa(p["placa"]) or "—",
                p["tipo"], p["visitas"], p["ultima_visita"] or "—", situacao),
                iid=str(p["id"]), situacao=texto, cor=cor)
        if selecao and self.tabela.exists(selecao[0]):
            self.tabela.selection_set(selecao[0])

        ok, n = self.app.tentar(self.app.banco.contadores)
        if ok:
            self.lbl_total.config(
                text=plural(n["pessoas"], "pessoa cadastrada",
                            "pessoas cadastradas")
                + f"  ·  {n['no_campus']} no campus agora")
        status = plural(len(pessoas), "pessoa na lista", "pessoas na lista")
        if len(pessoas) >= LIMITE_BUSCA:
            status += f" (as {LIMITE_BUSCA} primeiras: refine a busca)"
        self.lbl_status.config(text=status + "  ·  duplo clique começa uma "
                                             "nova entrada")

    def ao_selecionar(self, event=None):
        selecao = self.tabela.selection()
        if not selecao:
            return
        p = next(p for p in self.pessoas if p["id"] == int(selecao[0]))
        self.selecionada = p
        self.vazio.place_forget()
        self.conteudo.pack(fill="both", expand=True)
        self.lbl_titulo.config(text=p["nome"])
        self.lbl_cpf.config(text="CPF " + self.app.exibir_cpf(p["cpf"]))
        self.lbl_visitas.config(text=str(p["visitas"]))
        self.lbl_ultima.config(text=(p["ultima_visita"] or "—")[:5])
        self.nome.delete(0, tk.END)
        self.nome.insert(0, p["nome"])
        self.celular.delete(0, tk.END)
        self.celular.insert(0, p["celular"])
        self.var_placa.set(p["placa"])
        self.tipo.set(p["tipo"])
        motivo = self.bloqueados.get(p["cpf"])
        if motivo:
            self._faixa("erro", f"CPF bloqueado: {motivo}")
        elif p["dentro_desde"]:
            self._faixa("sucesso", f"No campus desde {p['dentro_desde']}.")
        else:
            self.faixa.pack_forget()
        self._mostrar_placa()

    def _faixa(self, tipo, texto):
        self.faixa.mostrar(tipo, texto)
        self.faixa.pack(fill="x", pady=(px(14), 0), before=self.separador)

    def _mostrar_placa(self):
        self.desenho_placa.mostrar(self.var_placa.get().strip())

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
        self._faixa("sucesso", "Alterações salvas.")

    def registrar_entrada(self):
        if not self._exigir_selecao():
            return
        p = self.selecionada
        if p["dentro_desde"]:
            mensagens.aviso(
                "Atenção", f"{p['nome']} já está no campus desde "
                           f"{p['dentro_desde']}.\nRegistre a saída na página "
                           "Entrada e saída.")
            return
        self.app.preencher_pessoa(p)
