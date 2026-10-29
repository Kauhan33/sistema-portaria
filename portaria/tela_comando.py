"""
Campo Comando (F2 ou Ctrl+K) da página Entrada e saída (versão 2.4).

No lugar da antiga "Saída rápida", no mesmo canto: o porteiro digita um
comando da linguagem da portaria (portaria/linguagem) e aperta Enter. Só
o CPF ou só a placa continuam dando a saída, como antes.

    [ Comando: entrada 529.982.247-25 aluno placa ABC1D23 ⏎ ] (●) Didático
    ✓ Registro cadastrado com sucesso! Entrada de Ana às 10:00.  Console (3)

- Realce: a cada tecla o analisador LÉXICO roda e pinta cada token (comando
  em negrito, CPF azul, placa com fundo, tipo verde, data e hora âmbar,
  texto cinza); o lexema com erro fica vermelho e sublinhado (E4).
- Tab completa o comando, a palavra-chave e o tipo; um pedaço do NOME vira
  o CPF da pessoa (mascarado para o porteiro: o campo guarda o CPF de
  verdade só na memória, em `apelidos`). Comando desconhecido recebe o
  "você quis dizer…?" e o Tab aplica a sugestão.
- A resposta aparece numa linha embaixo do campo; o console (recolhível)
  guarda as últimas respostas, com o erro no formato do compilador: a
  linha, o ^ na coluna, a fase entre colchetes e a dica.
- Modo didático (E2): uma janela por cima da tabela com a faixa das fases
  e as abas Tokens, Árvore, Símbolos e Checagens.

Privacidade (RN14): para o porteiro, toda resposta, o console e o modo
didático mostram o CPF mascarado. O texto dos comandos NÃO vai para o log
nem para o banco: o console e os apelidos ficam só na memória desta tela.
"""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from .componentes import (Alternador, Seletor, inserir_linha, link,
                          ret_arredondado, tabela)
from .estilo import (ALTURA_CAMPO, COR, CORES_TIPO, ESTADO, FONTE, ICONE,
                     MARGEM, fonte_icone, pintar_barra_de_titulo, px)
from .linguagem.erros import FASES, LEXICO
from .linguagem.executor import (AVISO, CANCELADO, ERRO, INFO, SUCESSO,
                                 Executor)
from .linguagem.interpretador import (FALHOU, NAO_RODOU, PASSOU, analisar,
                                      analisar_forma, marcar_execucao)
from .linguagem.lexico import (COMANDO, COMANDOS, CPF, DATA, ERRO as T_ERRO,
                               FIM, HORA, NUMERO, PALAVRA, PALAVRA_CHAVE,
                               PALAVRAS_CHAVE, PERIODO, PERIODOS, PLACA,
                               TEXTO, TIPO, TIPOS, mascarar_lexema,
                               reconhecer_placa, sem_acento, tokenizar)
from .linguagem.semantico import (AUTORIZACAO, AVISO as C_AVISO, ERRO as
                                  C_ERRO, OK as C_OK, PERGUNTA)
from .linguagem.sintatico import arvore_visual, sugerir_comando
from .usuarios import eh_admin
from .validacao import MAXIMO_COMANDO, formatar_cpf, mascarar_cpf

TITULO = "Comando (F2 · Ctrl+K)"
DICA_VAZIO = {"normal": "CPF, placa ou comando (ajuda)",
              "compacta": "Comando (F2): CPF, placa ou ajuda"}
LARGURA_CAMPO = 300
LARGURA_CONSOLE = 640
ENTRADAS_NO_CONSOLE = 30          # o console guarda as últimas respostas
OPCOES_DO_TAB = 6                 # nomes oferecidos pelo Tab
ICONE_NIVEL = {SUCESSO: "ok", INFO: "info", AVISO: "alerta", ERRO: "erro",
               CANCELADO: "info"}
COR_NIVEL = {SUCESSO: "sucesso", INFO: "info", AVISO: "alerta", ERRO: "erro",
             CANCELADO: "texto_2"}
# token -> (cor do texto, negrito?, fundo)
def cores_dos_tokens():
    """As cores do realce no tema em uso (paleta Guarita)."""
    return {
        COMANDO: {"foreground": COR["texto"], "font": FONTE["corpo_semi"]},
        PALAVRA_CHAVE: {"foreground": CORES_TIPO["Professor"]},
        TIPO: {"foreground": COR["sucesso"]},
        CPF: {"foreground": COR["info"]},
        NUMERO: {"foreground": COR["info"]},
        PLACA: {"foreground": ESTADO["info"][0],
                "background": ESTADO["info"][1]},
        DATA: {"foreground": COR["alerta"]},
        HORA: {"foreground": COR["alerta"]},
        PERIODO: {"foreground": COR["alerta"]},
        TEXTO: {"foreground": COR["texto_3"]},
        PALAVRA: {"foreground": COR["texto_2"]},
        T_ERRO: {"foreground": COR["erro"], "underline": True},
    }


def linhas_do_console(analise):
    """O erro como o console mostra: [(texto, tag)]. A linha digitada e o
    ^ ganham o mesmo recuo ("› " e "  "), para o ^ cair na coluna certa."""
    linhas = analise.linhas_do_erro()
    resultado = [("› " + linhas[0], "eco")]
    resto = linhas[1:]
    if analise.erro.coluna:
        resultado.append(("  " + resto[0], "marca"))
        resto = resto[1:]
    resultado.append((resto[0], "erro"))
    resultado += [(t, "dica") for t in resto[1:]]
    return resultado


def caber(texto, fonte, largura):
    """O texto cortado com "…" para caber em `largura` px."""
    medida = tkfont.Font(font=fonte)
    if medida.measure(texto) <= largura:
        return texto
    while texto and medida.measure(texto + "…") > largura:
        texto = texto[:-1]
    return texto + "…"


# ----------------------------------------------------------------------
# O campo: uma linha de Text (cores por trecho) que fala como um Entry
# ----------------------------------------------------------------------
class LinhaComando(tk.Text):
    """
    O Tk Entry não colore trechos; o Text colore (tags), mas tem várias
    linhas. Esta é um Text de uma linha só, com a mesma interface do
    Entry que as telas e os testes usam: get(), insert(0, "..."),
    delete(0, tk.END), icursor(). Enter, Tab e as setas de linha não
    entram no texto; o máximo (MAXIMO_COMANDO) vale para digitar e colar
    (o que passar é cortado, como nos outros campos, RN33).
    """

    def __init__(self, pai, maximo=MAXIMO_COMANDO, ao_mudar=None):
        super().__init__(pai, height=1, wrap="none", undo=True, relief="flat",
                         bd=0, highlightthickness=0, padx=0, pady=0,
                         font=FONTE["corpo"], bg=COR["superficie"],
                         fg=COR["texto"], insertbackground=COR["texto"],
                         selectbackground=COR["selecao"],
                         selectforeground=COR["texto"],
                         inactiveselectbackground=COR["selecao"],
                         exportselection=False)
        self.maximo, self.ao_mudar = maximo, ao_mudar
        for tag, opcoes in cores_dos_tokens().items():
            self.tag_configure(tag, **opcoes)
        self.tag_raise("sel")
        self.bind("<<Modified>>", self._modificado)
        self.bind("<<Paste>>", self._colar)
        self.bind("<KeyPress>", self._tecla)
        # o que um Text faria e uma linha de comando não faz
        for tecla in ("<Up>", "<Down>", "<Prior>", "<Next>", "<Control-o>",
                      "<Control-t>", "<Control-k>", "<Control-K>",
                      "<Control-i>", "<Shift-Return>", "<Control-Return>"):
            self.bind(tecla, lambda e: "break")

    # --- a interface do Entry ----------------------------------------
    @staticmethod
    def _indice(indice):
        if isinstance(indice, int):
            return f"1.{indice}"
        return "end-1c" if indice in (tk.END, "end") else indice

    def get(self, inicio=None, fim=None):
        if inicio is None:
            return tk.Text.get(self, "1.0", "end-1c")
        return tk.Text.get(self, self._indice(inicio),
                           self._indice(fim) if fim is not None else None)

    def insert(self, indice, texto, *tags):
        texto = " ".join(str(texto).replace("\t", " ").splitlines())
        cabe = max(self.maximo - len(self.get()), 0)
        if texto[:cabe]:
            tk.Text.insert(self, self._indice(indice), texto[:cabe], *tags)
        self._avisar()

    def delete(self, inicio, fim=None):
        tk.Text.delete(self, self._indice(inicio),
                       self._indice(fim) if fim is not None else None)
        self._avisar()

    def icursor(self, indice):
        self.mark_set("insert", self._indice(indice))

    def selection_present(self):
        return bool(self.tag_ranges("sel"))

    def escrever(self, texto):
        """Troca todo o texto (e põe o cursor no fim)."""
        tk.Text.delete(self, "1.0", "end")
        self.insert(0, texto)
        self.mark_set("insert", "end-1c")

    # --- digitação e colagem -----------------------------------------
    def _tecla(self, event):
        controle = event.state & 0x4
        if event.char and event.char >= " " and not controle:
            if len(self.get()) >= self.maximo and not self.selection_present():
                return "break"          # no máximo: a tecla não entra
        return None

    def _colar(self, event=None):
        try:
            texto = self.clipboard_get()
        except tk.TclError:
            return "break"
        if self.selection_present():
            tk.Text.delete(self, "sel.first", "sel.last")
        self.insert("insert", texto)
        return "break"

    def _modificado(self, event=None):
        if self.edit_modified():
            self.edit_modified(False)
            self._avisar()

    def _avisar(self):
        if self.ao_mudar is not None:
            self.ao_mudar()

    # --- realce ------------------------------------------------------
    def realcar(self, tokens):
        """Pinta cada token pela cor do tipo dele (o léxico a cada tecla)."""
        for tag in cores_dos_tokens():
            self.tag_remove(tag, "1.0", "end")
        for t in tokens:
            if t.tipo != FIM and t.lexema:
                self.tag_add(t.tipo, f"1.{t.coluna - 1}", f"1.{t.fim - 1}")


class CampoComando(tk.Frame):
    """O contorno no estilo dos outros campos (componentes.Campo), com a
    LinhaComando dentro, o ícone de executar e a dica com o campo vazio."""

    def __init__(self, pai, fundo_pai, largura, acao, ao_mudar):
        self.fundo_pai = fundo_pai
        super().__init__(pai, bg=fundo_pai, height=px(ALTURA_CAMPO),
                         width=px(largura))
        self.pack_propagate(False)
        self.focado = False
        self.cv = tk.Canvas(self, bg=fundo_pai, highlightthickness=0, bd=0)
        self.cv.place(x=0, y=0, relwidth=1, relheight=1)
        self.ao_mudar = ao_mudar
        self.entrada = LinhaComando(self, ao_mudar=self._mudou)
        self.entrada.place(x=px(10), rely=0.5, anchor="w", relwidth=1,
                           width=-px(46))
        self.lbl_icone = tk.Label(self, text=ICONE["seta"],
                                  font=fonte_icone(11), bg=COR["superficie"],
                                  fg=COR["texto_2"], cursor="hand2")
        self.lbl_icone.place(relx=1, rely=0.5, anchor="e", x=-px(10))
        self.lbl_icone.bind("<Button-1>", lambda e: acao())
        self.lbl_vazio = tk.Label(self, text="", font=FONTE["corpo"],
                                  bg=COR["superficie"], fg=COR["texto_3"],
                                  anchor="w", cursor="xterm")
        self.lbl_vazio.bind("<Button-1>", lambda e: self.entrada.focus_set())
        self.entrada.bind("<FocusIn>", lambda e: self._foco(True), add="+")
        self.entrada.bind("<FocusOut>", lambda e: self._foco(False), add="+")
        self.cv.bind("<Configure>", lambda e: self._desenhar())
        self._mostrar_vazio()

    @property
    def maximo(self):
        """O tamanho máximo (como componentes.Campo.maximo, RN33)."""
        return self.entrada.maximo

    def colar(self, texto):
        """Cola no cursor só o que cabe (como componentes.Campo.colar)."""
        if self.entrada.selection_present():
            tk.Text.delete(self.entrada, "sel.first", "sel.last")
        self.entrada.insert("insert", texto)

    def _mudou(self):
        self._mostrar_vazio()
        self.ao_mudar()

    def _mostrar_vazio(self):
        if self.entrada.get():
            self.lbl_vazio.place_forget()
        else:
            self.lbl_vazio.place(x=px(10) + 1, rely=0.5, anchor="w")

    def _foco(self, sim):
        self.focado = sim
        self._desenhar()

    def _desenhar(self):
        cv = self.cv
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 10:
            return
        r = px(4)
        ret_arredondado(cv, 0, 0, w, h, r, COR["superficie"], self.fundo_pai,
                        COR["borda_campo"])
        cor, esp = (COR["foco"], px(2)) if self.focado else (COR["traco_campo"], 1)
        cv.create_rectangle(r, h - esp, w - r, h, fill=cor, width=0)


# ----------------------------------------------------------------------
# Console: as últimas respostas (recolhível, por cima da página)
# ----------------------------------------------------------------------
class Console(tk.Frame):
    def __init__(self, pagina, ao_fechar):
        super().__init__(pagina, bg=COR["borda_campo"])
        interno = tk.Frame(self, bg=COR["superficie"])
        interno.pack(fill="both", expand=True, padx=1, pady=1)
        topo = tk.Frame(interno, bg=COR["superficie"])
        topo.pack(fill="x", padx=px(12), pady=(px(8), px(4)))
        tk.Label(topo, text="Console", font=FONTE["rotulo"],
                 bg=COR["superficie"], fg=COR["texto"]).pack(side="left")
        tk.Label(topo, text="  últimas respostas · só nesta tela, não fica "
                            "gravado", font=FONTE["dica"],
                 bg=COR["superficie"], fg=COR["texto_3"]).pack(side="left")
        link(topo, "Fechar (Esc)", ao_fechar, fundo=COR["superficie"]
             ).pack(side="right")
        link(topo, "Limpar", self.limpar, fundo=COR["superficie"]
             ).pack(side="right", padx=(0, px(12)))
        corpo = tk.Frame(interno, bg=COR["superficie"])
        corpo.pack(fill="both", expand=True, padx=(px(12), px(4)),
                   pady=(0, px(8)))
        self.texto = tk.Text(corpo, height=9, wrap="none", relief="flat",
                             bd=0, highlightthickness=0, font=FONTE["mono"],
                             bg=COR["superficie"], fg=COR["texto"],
                             selectbackground=COR["selecao"],
                             selectforeground=COR["texto"], padx=0, pady=0,
                             cursor="arrow")
        barra = ttk.Scrollbar(corpo, orient="vertical",
                              command=self.texto.yview,
                              style="Fina.Vertical.TScrollbar")
        self.texto.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.texto.pack(side="left", fill="both", expand=True)
        cores = {"eco": COR["texto_2"], "marca": COR["erro"],
                 "erro": COR["erro"], "sucesso": COR["sucesso"],
                 "aviso": COR["alerta"], "info": COR["info"],
                 "cancelado": COR["texto_2"], "dica": COR["texto_3"],
                 "detalhe": COR["texto"]}
        for tag, cor in cores.items():
            self.texto.tag_configure(tag, foreground=cor, lmargin1=px(2),
                                     lmargin2=px(18), wrap="word")
        for tag in ("eco", "marca"):          # o ^ só cai certo sem quebra
            self.texto.tag_configure(tag, wrap="none", lmargin2=px(2))
        self.texto.tag_configure("eco", font=FONTE["mono_semi"])
        self.texto.configure(state="disabled")
        self.entradas = []                    # [(texto, tag), ...] por comando

    def adicionar(self, linhas):
        """Mais uma resposta: [(texto, tag)]. Guarda só as últimas."""
        self.entradas.append(linhas)
        del self.entradas[:-ENTRADAS_NO_CONSOLE]
        self._redesenhar()

    def limpar(self):
        self.entradas = []
        self._redesenhar()

    def _redesenhar(self):
        t = self.texto
        t.configure(state="normal")
        t.delete("1.0", "end")
        for i, linhas in enumerate(self.entradas):
            if i:
                t.insert("end", "\n")
            for texto, tag in linhas:
                t.insert("end", texto + "\n", tag)
        t.configure(state="disabled")
        t.see("end")

    def conteudo(self):
        return self.texto.get("1.0", "end-1c")


# ----------------------------------------------------------------------
# O painel: título, campo, interruptor, resposta e console
# ----------------------------------------------------------------------
class PainelComando:
    """Monta o campo Comando no cabeçalho (`pai` = Cabecalho.acoes) e liga
    a análise e a execução. `tela` é a AbaCadastro (a porta do executor)."""

    def __init__(self, pai, tela):
        self.tela, self.app = tela, tela.app
        fundo = COR["fundo"]
        self.apelidos = {}              # CPF mascarado -> CPF (Tab, porteiro)
        self._tab = None                # opções do Tab em uso
        self.ultima = None              # a última Analise (modo didático)
        self.janela_didatica = None
        self.var_didatico = tk.BooleanVar(pai, False)

        self.lbl_titulo = tk.Label(pai, text=TITULO, font=FONTE["rotulo"],
                                   bg=fundo, fg=COR["texto_2"])
        self.lbl_titulo.pack(anchor="w", pady=(0, px(4)))
        self.linha_campo = tk.Frame(pai, bg=fundo)
        self.linha_campo.pack(anchor="w")
        self.campo = CampoComando(self.linha_campo, fundo, LARGURA_CAMPO,
                                  self.executar, self._ao_mudar)
        self.campo.pack(side="left")
        self.linha = self.campo.entrada
        self.alternador = Alternador(self.linha_campo, "Didático",
                                     self.var_didatico,
                                     self.alternar_didatico, fundo_pai=fundo)
        self.alternador.pack(side="left", padx=(px(12), 0))
        for tecla in ("<Return>", "<KP_Enter>"):
            self.linha.bind(tecla, self.executar)
        self.linha.bind("<Tab>", self.completar)
        self.linha.bind("<Escape>", self._esc)

        # a resposta numa linha, embaixo do campo, e o link do console
        self.linha_resposta = tk.Frame(pai, bg=fundo, height=px(20))
        self.linha_resposta.pack(fill="x", pady=(px(3), 0))
        self.linha_resposta.pack_propagate(False)
        self.lbl_icone = tk.Label(self.linha_resposta, text="",
                                  font=fonte_icone(9), bg=fundo)
        self.lbl_icone.pack(side="left", padx=(0, px(5)))
        self.lbl_resposta = tk.Label(self.linha_resposta, text="",
                                     font=FONTE["dica"], bg=fundo,
                                     fg=COR["texto_2"], anchor="w")
        self.lbl_resposta.pack(side="left", fill="x", expand=True)
        self.btn_console = link(self.linha_resposta, "Console",
                                self.alternar_console, fundo=fundo)
        self.btn_console.pack(side="right")
        self.console = Console(tela.aba, self.fechar_console)
        self.console_aberto = False

    # --- texto e realce ----------------------------------------------
    def _ao_mudar(self):
        texto = self.linha.get()
        tokens, _ = tokenizar(texto, self.apelidos)
        self.linha.realcar(tokens)
        if self._tab is not None and texto != self._tab["texto"]:
            self._tab = None
        if self.janela_didatica is not None and self.janela_didatica.existe():
            self.janela_didatica.mostrar(self._forma(texto), digitando=True)

    def _forma(self, texto):
        return analisar_forma(texto, self.apelidos,
                              privado=not eh_admin(self.app.usuario))

    # --- executar ------------------------------------------------------
    def executar(self, event=None):
        """Enter: as fases do compilador e, sem erro, a execução."""
        if self.app.usuario is None:
            return "break"
        texto = self.linha.get().strip()
        if not texto:
            self.responder(INFO, "Digite o CPF ou a placa (saída) ou um "
                                 "comando; \"ajuda\" mostra todos.")
            return "break"
        self.app.recarregar_registros()       # outra estação pode ter mudado
        analise = analisar(texto, self.app.banco, self.app.usuario,
                           self.app.relogio(), self.app.exibir_cpf,
                           self.apelidos)
        self.ultima = analise
        eco = ("› " + analise.linha_exibida, "eco")
        if analise.erro is not None:
            recusa = getattr(analise.erro, "recusa", None)
            if recusa is not None:        # RN12: vai ao histórico, como o
                self.tela.registrar_recusa(recusa)       # formulário faz
            self.console.adicionar(linhas_do_console(analise))
            self.responder(ERRO, analise.mostrar(analise.erro.titulo()))
            self.abrir_console()
        else:
            dialogo = next((c for c in analise.checagens
                            if c.estado in (PERGUNTA, AUTORIZACAO)), None)
            if dialogo is not None:      # o diálogo do formulário vai abrir
                self.responder(INFO, f"{dialogo.descricao} ({dialogo.regra}):"
                                     " responda no diálogo.")
                self.linha_resposta.update_idletasks()
            resposta = Executor(self.app, self.tela).executar(analise.plano)
            if self.app.usuario is None or not self.linha.winfo_exists():
                return "break"     # a sessão acabou com um diálogo aberto
            marcar_execucao(analise, resposta)
            self.console.adicionar(
                [eco, (analise.mostrar(resposta.texto), resposta.nivel)]
                + [("  " + analise.mostrar(t), "detalhe")
                   for t in resposta.linhas])
            self.responder(resposta.nivel, analise.mostrar(resposta.texto),
                           detalhes=bool(resposta.linhas))
            if resposta.linhas:
                self.abrir_console()
            if resposta.nivel == SUCESSO:
                self.limpar()
        if self.janela_didatica is not None and self.janela_didatica.existe():
            self.janela_didatica.mostrar(analise)
        return "break"

    def limpar(self):
        self.linha.delete(0, tk.END)
        self.apelidos.clear()

    def responder(self, nivel, texto, detalhes=False):
        """A linha de resposta embaixo do campo."""
        cor = COR[COR_NIVEL[nivel]]
        self.texto_resposta = texto
        self.lbl_icone.config(text=ICONE[ICONE_NIVEL[nivel]], fg=cor)
        largura = max(self.linha_resposta.winfo_width()
                      - self.btn_console.winfo_reqwidth() - px(24), px(120))
        if self.linha_resposta.winfo_width() <= 1:
            largura = px(LARGURA_CAMPO + 80)
        self.lbl_resposta.config(text=caber(texto, FONTE["dica"], largura),
                                 fg=cor)
        n = len(self.console.entradas)
        self.btn_console.config(text=f"Console ({n})" if n else "Console")

    # --- console -------------------------------------------------------
    def alternar_console(self):
        if self.console_aberto:
            self.fechar_console()
        else:
            self.abrir_console()

    def abrir_console(self):
        aba = self.tela.aba
        aba.update_idletasks()
        y = (self.linha_resposta.winfo_rooty() - aba.winfo_rooty()
             + self.linha_resposta.winfo_height() + px(4))
        largura = min(px(LARGURA_CONSOLE), aba.winfo_width() - px(2 * MARGEM))
        self.console.place(in_=aba, relx=1, x=-px(MARGEM), y=max(y, 0),
                           anchor="ne", width=max(largura, px(320)))
        self.console.lift()
        self.console_aberto = True

    def fechar_console(self):
        self.console.place_forget()
        self.console_aberto = False

    def _esc(self, event=None):
        if self._tab is not None:
            self._tab = None
        self.fechar_console()
        return "break"

    # --- Tab: autocompletar ---------------------------------------------
    def completar(self, event=None):
        """Tab: completa a palavra do cursor (comando, palavra-chave, tipo,
        período) ou troca o pedaço de um nome pelo CPF da pessoa. Repetir o
        Tab passa para a próxima opção."""
        texto = self.linha.get()
        if self._tab is not None and texto == self._tab["texto"]:
            return self._proxima_opcao()
        cursor = len(self.linha.get("1.0", "insert"))
        inicio = texto.rfind(" ", 0, cursor) + 1
        palavra = texto[inicio:cursor]
        primeira = not texto[:inicio].strip()
        opcoes = self._opcoes(palavra, primeira)
        if not opcoes:
            self.responder(INFO, "Tab: nada para completar aqui.")
            return "break"
        self._tab = {"inicio": inicio, "fim": cursor, "opcoes": opcoes,
                     "i": -1, "texto": None}
        return self._proxima_opcao()

    def _proxima_opcao(self):
        tab = self._tab
        tab["i"] = (tab["i"] + 1) % len(tab["opcoes"])
        rotulo, novo = tab["opcoes"][tab["i"]]
        texto = self.linha.get()
        antes, depois = texto[:tab["inicio"]], texto[tab["fim"]:]
        if not depois.startswith(" "):
            novo += " "
        tab["texto"] = antes + novo + depois   # antes de escrever: o
        self.linha.escrever(tab["texto"])      # _ao_mudar não desfaz o Tab
        self.linha.icursor(len(antes) + len(novo))
        tab["fim"] = len(antes) + len(novo)
        if len(tab["opcoes"]) > 1:
            self.responder(INFO, f"Tab {tab['i'] + 1}/{len(tab['opcoes'])}: "
                                 f"{rotulo} · Tab de novo: a próxima")
        elif rotulo:
            self.responder(INFO, f"Tab: {rotulo}")
        return "break"

    def _opcoes(self, palavra, primeira):
        """[(rótulo, texto que entra)] para a palavra do cursor."""
        chave = sem_acento(palavra)
        if primeira:
            achados = [c for c in COMANDOS if c.startswith(chave)]
            if not achados and chave:
                sugestao = sugerir_comando(chave)
                achados = [sugestao] if sugestao else []
            if achados:
                return [("", c) for c in achados]
        elif chave:
            palavras = list(PALAVRAS_CHAVE) + list(TIPOS) + list(PERIODOS)
            achados = [p for p in palavras if p.startswith(chave)
                       and p != chave]
            if achados:
                return [("", p) for p in achados]
        if len(chave) >= 2 and chave.isalpha():
            return self._nomes(palavra)
        return []

    def _nomes(self, pedaco):
        """Pessoas com o pedaço no nome: o Tab troca pelo CPF (mascarado
        para o porteiro; o CPF de verdade fica em `apelidos`)."""
        ok, pessoas = self.app.tentar(self.app.banco.buscar_pessoas, pedaco,
                                      OPCOES_DO_TAB)
        if not ok:
            return []
        admin = eh_admin(self.app.usuario)
        opcoes = []
        for p in pessoas:
            if pedaco.lower() not in p["nome"].lower():
                continue                       # (achou pelo tipo ou placa)
            onde = " (no campus)" if p["dentro_desde"] else ""
            if admin:
                texto = formatar_cpf(p["cpf"])
            else:
                texto = mascarar_cpf(p["cpf"])
                self.apelidos[texto] = p["cpf"]
            opcoes.append((p["nome"] + onde, texto))
        return opcoes

    # --- modo didático ---------------------------------------------------
    def alternar_didatico(self):
        if self.var_didatico.get():
            self.abrir_didatico()
        elif self.janela_didatica is not None:
            self.janela_didatica.fechar()

    def abrir_didatico(self):
        if self.janela_didatica is None or not self.janela_didatica.existe():
            self.janela_didatica = JanelaDidatica(self)
        self.var_didatico.set(True)
        self.alternador._desenhar()
        analise = self.ultima or self._forma(self.linha.get())
        self.janela_didatica.mostrar(analise)
        self.linha.focus_set()
        return self.janela_didatica

    def ao_fechar_didatico(self):
        self.var_didatico.set(False)
        self.alternador._desenhar()

    # --- trocar o tema / travar: o que estava aqui volta ----------------
    def ler(self):
        return {"texto": self.linha.get(), "apelidos": dict(self.apelidos),
                "console": list(self.console.entradas),
                "didatico": self.var_didatico.get()}

    def restaurar(self, estado):
        if not estado:
            return
        self.apelidos.update(estado["apelidos"])
        self.linha.escrever(estado["texto"])
        self.console.entradas = list(estado["console"])
        self.console._redesenhar()
        if estado["didatico"]:
            self.abrir_didatico()


# ----------------------------------------------------------------------
# Modo didático
# ----------------------------------------------------------------------
ABAS = ("Tokens", "Árvore", "Símbolos", "Checagens")
SIMBOLO_FASE = {PASSOU: "✓", FALHOU: "✗", NAO_RODOU: "—"}
ESTADO_FASE = {PASSOU: "sucesso", FALHOU: "erro", NAO_RODOU: "neutro"}
CHECAGEM = {C_OK: ("Passou", "sucesso"), C_ERRO: ("Parou aqui", "erro"),
            C_AVISO: ("Aviso", "alerta"), PERGUNTA: ("Pergunta", "info"),
            AUTORIZACAO: ("Autorização", "alerta")}
LARGURA_DIDATICA, ALTURA_DIDATICA = 720, 520
MENSAGEM_MAXIMA = 190           # caracteres da mensagem (2 linhas)


class JanelaDidatica:
    """A análise do comando, fase a fase. Janela por cima da tabela (no
    notebook 1366x670 ela cabe sobre o Movimento), sem travar a tela: o
    porteiro continua digitando no campo e ela acompanha."""

    def __init__(self, painel):
        self.painel, app = painel, painel.app
        self.privado = not eh_admin(app.usuario)
        j = self.janela = tk.Toplevel(app.janela)
        j.title("Modo didático — análise do comando")
        j.configure(bg=COR["superficie"])
        j.transient(app.janela)
        pintar_barra_de_titulo(j)
        j.protocol("WM_DELETE_WINDOW", self.fechar)
        j.bind("<Escape>", lambda e: self.fechar())
        fundo = COR["superficie"]
        corpo = tk.Frame(j, bg=fundo)
        corpo.pack(fill="both", expand=True, padx=px(18), pady=(px(8),
                                                               px(10)))
        topo = tk.Frame(corpo, bg=fundo)
        topo.pack(fill="x")
        tk.Label(topo, text="Análise do comando", font=FONTE["titulo_cartao"],
                 bg=fundo, fg=COR["texto"]).pack(side="left")
        self.lbl_estado = tk.Label(topo, text="", font=FONTE["dica"],
                                   bg=fundo, fg=COR["texto_3"])
        self.lbl_estado.pack(side="right")
        self.lbl_linha = tk.Label(corpo, text="", font=FONTE["mono_semi"],
                                  bg=COR["superficie_2"], fg=COR["texto"],
                                  anchor="w", padx=px(10), pady=px(4))
        self.lbl_linha.pack(fill="x", pady=(px(6), px(6)))
        self.fases = tk.Canvas(corpo, bg=fundo, height=px(28),
                               highlightthickness=0, bd=0)
        self.fases.pack(fill="x")
        self.fases.bind("<Configure>", lambda e: self._desenhar_fases())
        # a mensagem (o mesmo erro do console, ou a resposta): até 2 linhas
        mensagem = tk.Frame(corpo, bg=fundo)
        mensagem.pack(fill="x", pady=(px(6), px(2)))
        self.lbl_icone = tk.Label(mensagem, text="", font=fonte_icone(10),
                                  bg=fundo)
        self.lbl_icone.pack(side="left", anchor="n", pady=(px(2), 0))
        self.lbl_mensagem = tk.Label(mensagem, text="", font=FONTE["dica"],
                                     bg=fundo, anchor="w", justify="left",
                                     wraplength=px(LARGURA_DIDATICA - 70))
        self.lbl_mensagem.pack(side="left", fill="x", padx=(px(6), 0))
        self.seletor = Seletor(corpo, ABAS, self.mostrar_aba, fundo_pai=fundo)
        self.seletor.compactar()
        self.seletor.pack(fill="x", pady=(0, px(4)))
        self.area = tk.Frame(corpo, bg=fundo)
        self.area.pack(fill="both", expand=True)
        self.lbl_vazio = tk.Label(self.area, text="", font=FONTE["corpo"],
                                  bg=fundo, fg=COR["texto_3"],
                                  justify="left", wraplength=px(600))
        self.paineis = {
            "Tokens": tabela(self.area, [
                ("n", "#", 30, "w"), ("lexema", "Lexema", 140, "w"),
                ("token", "Token", 120, "w"), ("valor", "Valor", 280, "w"),
                ("coluna", "Coluna", 60, "w")], altura=6, compacta=True),
            "Símbolos": tabela(self.area, [
                ("categoria", "Categoria", 100, "w"),
                ("chave", "Símbolo", 150, "w"),
                ("descricao", "O que a tabela diz", 380, "w")], altura=6,
                compacta=True),
            "Checagens": tabela(self.area, [
                ("checagem", "Checagem (na ordem)", 220, "w"),
                ("regra", "Regra", 100, "w"),
                ("detalhe", "Detalhe", 210, "w")], situacao="Resultado",
                largura_situacao=100, altura=6, compacta=True),
        }
        self.paineis["Tokens"][1].tag_configure("erro",
                                                foreground=COR["erro"])
        self.quadro_arvore = tk.Frame(self.area, bg=fundo)
        self.arvore = tk.Canvas(self.quadro_arvore, bg=fundo,
                                highlightthickness=0, bd=0)
        rolagem = ttk.Scrollbar(self.quadro_arvore, orient="horizontal",
                                command=self.arvore.xview,
                                style="Fina.Horizontal.TScrollbar")
        self.arvore.configure(xscrollcommand=rolagem.set)
        rolagem.pack(side="bottom", fill="x")
        self.arvore.pack(fill="both", expand=True)
        self.paineis["Árvore"] = (self.quadro_arvore, self.arvore)
        self.analise = None
        self.aba = ABAS[0]
        self._posicionar()
        self.seletor.selecionar(ABAS[0])

    def existe(self):
        try:
            return bool(self.janela.winfo_exists())
        except tk.TclError:
            return False

    def fechar(self):
        if self.existe():
            self.janela.destroy()
        self.painel.ao_fechar_didatico()

    def _posicionar(self):
        """À direita da janela principal, logo abaixo do campo Comando (por
        cima do formulário e da tabela): no notebook 1366x670 ela ocupa a
        altura que sobra embaixo do cabeçalho."""
        dono = self.painel.app.janela
        largura = min(px(LARGURA_DIDATICA), max(dono.winfo_width() - px(40),
                                                px(560)))
        if not dono.winfo_viewable():
            self.janela.geometry(f"{largura}x{px(ALTURA_DIDATICA)}")
            return
        resposta = self.painel.linha_resposta
        topo = resposta.winfo_rooty() + resposta.winfo_height() + px(6)
        baixo = dono.winfo_rooty() + dono.winfo_height() - px(12)
        altura = min(px(ALTURA_DIDATICA), max(baixo - topo, px(360)))
        x = dono.winfo_rootx() + dono.winfo_width() - largura - px(16)
        y = max(min(topo, baixo - altura), 0)
        self.janela.geometry(f"{largura}x{altura}+{max(x, 0)}+{y}")

    # --- o que mostrar -----------------------------------------------------
    def mostrar(self, analise, digitando=False):
        self.analise = analise
        self.lbl_linha.config(text=analise.linha_exibida or " ")
        self.lbl_estado.config(text="enquanto digita: léxico e sintático"
                               if digitando else "depois do Enter")
        self._desenhar_fases()
        if analise.erro is not None:
            self._mensagem(ERRO, analise.mostrar(analise.erro.titulo()))
        elif analise.resposta is not None:
            self._mensagem(analise.resposta.nivel,
                           analise.mostrar(analise.resposta.texto))
        elif digitando and analise.arvore is not None:
            self._mensagem(INFO, "Léxico e sintático passaram. Enter roda o "
                                 "semântico e a execução.")
        else:
            self._mensagem(CANCELADO, "Digite um comando no campo.")
        self.mostrar_aba(self.aba)

    def _mensagem(self, nivel, texto):
        """A mesma mensagem do console (no máximo 2 linhas)."""
        if len(texto) > MENSAGEM_MAXIMA:
            texto = texto[:MENSAGEM_MAXIMA - 1].rstrip() + "…"
        cor = COR[COR_NIVEL[nivel]]
        self.lbl_icone.config(text=ICONE[ICONE_NIVEL[nivel]], fg=cor)
        self.lbl_mensagem.config(text=texto, fg=cor)

    def _desenhar_fases(self):
        """Léxico ✓ → Sintático ✓ → Semântico ✗ → Execução —"""
        cv = self.fases
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 50 or self.analise is None:
            return
        seta = px(26)
        largura = (w - seta * 3) / 4
        x = 0
        for i, fase in enumerate(FASES):
            situacao = self.analise.fases[fase]
            texto_cor, fundo, borda = ESTADO[ESTADO_FASE[situacao]]
            ret_arredondado(cv, x, 1, x + largura, h - 1, px(6), fundo,
                            COR["superficie"], borda)
            cv.create_text(x + largura / 2, h / 2,
                           text=f"{fase}  {SIMBOLO_FASE[situacao]}",
                           font=FONTE["corpo_semi"], fill=texto_cor)
            x += largura
            if i < 3:
                cv.create_text(x + seta / 2, h / 2, text="→",
                               font=FONTE["corpo_semi"], fill=COR["texto_3"])
                x += seta

    def mostrar_aba(self, aba):
        self.aba = aba
        for quadro, _ in self.paineis.values():
            quadro.pack_forget()
        self.lbl_vazio.place_forget()
        quadro, tab = self.paineis[aba]
        quadro.pack(fill="both", expand=True)
        if self.analise is None:
            return
        {"Tokens": self._tokens, "Árvore": self._arvore,
         "Símbolos": self._simbolos, "Checagens": self._checagens}[aba](tab)

    def _vazio(self, texto):
        self.lbl_vazio.config(text=texto)
        self.lbl_vazio.place(relx=0.5, rely=0.45, anchor="center")
        self.lbl_vazio.lift()

    def _parou_antes(self, fase):
        a = self.analise
        if a.fases[fase] != NAO_RODOU:
            return False
        if a.erro is not None:
            self._vazio(f"O comando parou na fase {a.erro.fase}: a fase "
                        f"{fase} não rodou.")
        else:
            self._vazio(f"A fase {fase} roda quando você aperta Enter.")
        return True

    def _mostrar(self, texto):
        return mascarar_lexema(texto) if self.privado else texto

    def _tokens(self, tab):
        tab.delete(*tab.get_children())
        for i, t in enumerate(self.analise.tokens, 1):
            lexema = self._mostrar(t.lexema) if t.tipo != FIM else "(fim)"
            inserir_linha(tab, i - 1, (i, lexema, t.tipo,
                                       self._valor(t), t.coluna),
                          tags=("erro",) if t.tipo == T_ERRO else ())

    def _valor(self, t):
        if t.tipo == T_ERRO:
            return getattr(t.valor, "mensagem", "")
        if t.tipo == PLACA:
            aceitou, caminho = reconhecer_placa(t.lexema)
            return f"{t.valor}  ·  " + "→".join(caminho) + (
                " ✓" if aceitou else "")
        if t.tipo == CPF:
            return self._mostrar(formatar_cpf(t.valor))
        if t.tipo == DATA:
            return f"{t.valor:%d/%m/%Y}"
        if t.tipo == HORA:
            return "{:02d}:{:02d}".format(*t.valor)
        if t.tipo == NUMERO:
            return f"{len(t.lexema)} dígitos" + (
                " (CPF ou celular: o sintático decide)"
                if len(t.lexema) == 11 else "")
        return "" if t.valor is None else self._mostrar(str(t.valor))

    def _simbolos(self, tab):
        tab.delete(*tab.get_children())
        if self._parou_antes(FASES[2]):
            return
        for i, s in enumerate(self.analise.simbolos):
            inserir_linha(tab, i, (s.categoria, self._mostrar(s.chave),
                                   self._mostrar(s.descricao)))

    def _checagens(self, tab):
        tab.delete(*tab.get_children())
        if self._parou_antes(FASES[2]):
            return
        for i, c in enumerate(self.analise.checagens):
            texto, cor = CHECAGEM[c.estado]
            inserir_linha(tab, i, (c.descricao, c.regra,
                                   self._mostrar(c.detalhe)),
                          situacao=texto, cor=COR[cor])
        if not self.analise.checagens:
            self._vazio("Este comando não tem checagens com o banco.")

    def _arvore(self, cv):
        cv.delete("all")
        a = self.analise
        if a.arvore is None:
            self._vazio(f"A árvore não foi montada: o comando parou na fase "
                        f"{a.erro.fase if a.erro else LEXICO}."
                        if a.erro else "Digite um comando.")
            return
        erro = a.erro
        marcar = None
        if erro is not None and erro.coluna and erro.fase != LEXICO:
            marcar = (erro.coluna, erro.coluna + erro.tamanho)
        desenhar_arvore(cv, arvore_visual(a.arvore), marcar, self._mostrar)


# ----------------------------------------------------------------------
# A árvore no Canvas (nós arredondados no estilo Guarita)
# ----------------------------------------------------------------------
def desenhar_arvore(cv, raiz, marcar=None, mostrar=lambda t: t):
    """Desenha a árvore: as folhas lado a lado na ordem da linha e cada
    nó centrado sobre os filhos. `marcar` = (coluna inicial, final) do
    erro: o nó mais alto que fica inteiro dentro dela fica vermelho."""
    fonte, fonte_legenda = FONTE["corpo_semi"], FONTE["dica"]
    medida = tkfont.Font(font=fonte)
    nivel, espaco, margem = px(54), px(12), px(16)
    altura_no = px(24)
    posicoes = {}
    proximo = [margem]

    def largura(no):
        texto = mostrar(no.rotulo)
        return medida.measure(texto) + px(20)

    def dentro(no):
        return (marcar is not None and no.inicio and marcar[0] <= no.inicio
                and no.fim <= marcar[1])

    def colocar(no, prof):
        if not no.filhos:
            w = largura(no)
            posicoes[id(no)] = (proximo[0] + w / 2, prof, w)
            proximo[0] += w + espaco
            return
        for f in no.filhos:
            colocar(f, prof + 1)
        xs = [posicoes[id(f)][0] for f in no.filhos]
        w = largura(no)
        centro = (min(xs) + max(xs)) / 2
        posicoes[id(no)] = (centro, prof, w)

    colocar(raiz, 0)
    # o nó não pode passar da margem esquerda (rótulo largo em cima); se a
    # árvore é mais estreita que o Canvas, fica no meio
    menor = min(x - w / 2 for x, _, w in posicoes.values())
    maior = max(x + w / 2 for x, _, w in posicoes.values())
    sobra = cv.winfo_width() - (maior - menor) - 2 * margem
    deslocar = max(0, margem - menor) + max(0, sobra / 2)

    def y_de(prof):
        return px(10) + prof * nivel

    def desenhar(no, vermelho):
        x, prof, w = posicoes[id(no)]
        x += deslocar
        y = y_de(prof)
        erro = vermelho or dentro(no)
        for f in no.filhos:
            fx = posicoes[id(f)][0] + deslocar
            cv.create_line(x, y + altura_no, fx, y_de(prof + 1),
                           fill=COR["borda_campo"], width=px(1))
        for f in no.filhos:
            desenhar(f, erro)
        if erro:
            texto, fundo, borda = ESTADO["erro"]
        elif prof == 0:
            texto, fundo, borda = (COR["texto_invertido"], COR["primario"],
                                   COR["primario"])
        elif no.folha:
            texto, fundo, borda = (COR["texto"], COR["superficie"],
                                   COR["traco_campo"])
        else:
            texto, fundo, borda = (COR["texto"], COR["superficie_2"],
                                   COR["borda_campo"])
        ret_arredondado(cv, x - w / 2, y, x + w / 2, y + altura_no, px(8),
                        fundo, COR["superficie"], borda)
        cv.create_text(x, y + altura_no / 2, text=mostrar(no.rotulo),
                       font=fonte, fill=texto)
        if no.folha and no.legenda:
            cv.create_text(x, y + altura_no + px(9), text=no.legenda,
                           font=fonte_legenda, fill=COR["texto_3"])

    desenhar(raiz, False)
    fim = max(x + w / 2 for x, _, w in posicoes.values()) + deslocar + margem
    profundidade = max(p for _, p, _ in posicoes.values())
    cv.configure(scrollregion=(0, 0, fim, y_de(profundidade) + px(50)))
    return posicoes
