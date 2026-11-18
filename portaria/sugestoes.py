"""
Preenchimento automático de CPF e nome (3.6).

A partir de 3 letras do nome ou 3 números do CPF, uma lista com até 3
pessoas do cadastro aparece logo abaixo do campo e vai ficando mais
precisa enquanto se digita (banco.sugerir_pessoas). As setas marcam uma
pessoa; Enter ou Tab escolhem a marcada; Esc fecha; o clique também
escolhe. Escolher preenche o formulário (o CPF e o nome, juntos).

Privacidade: o porteiro vê o CPF mascarado na lista (app.exibir_cpf); o
administrador, inteiro. Quem está na unidade aparece marcado.

A lista é uma janelinha sem borda (Toplevel) presa ao campo: fica por cima
do diálogo sem ser cortada por ele e nunca recebe o foco (o cursor continua
no campo).
"""

import tkinter as tk

from .base_dados import ErroDados
from .componentes import EsperaDigitacao
from .estilo import COR, FONTE, px
from .validacao import MAXIMO_SUGESTOES, sem_acento, so_digitos

ESPERA_SUGESTAO_MS = 150      # pausa na digitação antes de sugerir
NA_UNIDADE = "na unidade"
DESATIVADA = "desativada"


class Sugestoes:
    """
    A lista de sugestões de um campo. `buscar(texto)` devolve as pessoas
    (dicionários com nome, cpf, dentro e desativada); `escolher(pessoa)`
    preenche o formulário; `exibir_cpf(cpf)` formata o CPF de quem usa.
    Para os testes: `itens`, `marcado`, `aberta`, `atualizar()`,
    `escolher_item(n)` e `fechar()`.
    """

    def __init__(self, entrada, buscar, escolher, exibir_cpf,
                 espera=ESPERA_SUGESTAO_MS):
        self.entrada, self.buscar, self.ao_escolher = entrada, buscar, escolher
        self.exibir_cpf = exibir_cpf
        self.itens, self.marcado, self.janela = [], -1, None
        self._escolhido = None            # o texto que a escolha deixou
        self.espera = EsperaDigitacao(entrada, self.atualizar, espera)
        entrada.bind("<Down>", lambda e: self._mover(1), add="+")
        entrada.bind("<Up>", lambda e: self._mover(-1), add="+")
        for tecla in ("<Return>", "<KP_Enter>", "<Tab>"):
            entrada.bind(tecla, self._confirmar, add="+")
        entrada.bind("<Escape>", self._esc, add="+")
        entrada.bind("<FocusOut>", self._ao_perder_foco, add="+")
        entrada.bind("<Destroy>", lambda e: self.fechar(), add="+")
        entrada.winfo_toplevel().bind("<Configure>", self._posicionar, add="+")

    @property
    def aberta(self):
        return self.janela is not None

    # ------------------------------------------------------------------
    def atualizar(self):
        """Busca de novo com o texto do campo e mostra (ou fecha) a lista."""
        texto = self.entrada.get()
        if not self.entrada.winfo_exists():
            return
        if texto == self._escolhido:      # o texto que a própria escolha pôs
            self.fechar()
            return
        try:
            self.itens = list(self.buscar(texto))[:MAXIMO_SUGESTOES]
        except ErroDados:
            self.itens = []
        self.marcado = -1
        if self.itens:
            self._mostrar()
        else:
            self.fechar()

    def escolher_item(self, n):
        """Preenche o formulário com a pessoa `n` da lista."""
        if not 0 <= n < len(self.itens):
            return False
        pessoa = self.itens[n]
        self.fechar()
        self.espera.cancelar()
        self.ao_escolher(pessoa)
        self._escolhido = self.entrada.get()
        self.espera._visto = self._escolhido
        return True

    def fechar(self):
        if self.janela is not None:
            try:
                self.janela.destroy()
            except tk.TclError:
                pass
        self.janela, self.marcado = None, -1

    # ------------------------------------------------------------------
    def _mostrar(self):
        self.fechar()
        topo = self.entrada.winfo_toplevel()
        janela = self.janela = tk.Toplevel(topo)
        janela.withdraw()
        # (sem "transient": no Windows ele deixava a lista atrás do diálogo)
        janela.overrideredirect(True)
        janela.configure(bg=COR["borda_campo"])
        quadro = tk.Frame(janela, bg=COR["superficie"])
        quadro.pack(fill="both", expand=True, padx=1, pady=1)
        self.linhas = []
        for n, pessoa in enumerate(self.itens):
            self.linhas.append(self._linha(quadro, n, pessoa))
        janela.update_idletasks()
        self._posicionar()
        # por cima de tudo (até de um diálogo "sempre visível"): a lista é
        # passageira e fecha quando o campo perde o foco
        janela.attributes("-topmost", True)
        janela.deiconify()
        janela.lift()
        self.entrada.after_idle(self._devolver_foco)

    def _posicionar(self, event=None):
        """Logo abaixo do campo, pelo menos da largura dele (e larga o
        bastante para o nome e o CPF). Chamado de novo quando a janela do
        campo se move ou muda de tamanho (o diálogo que ainda se centraliza
        ao abrir)."""
        if self.janela is None:
            return
        # alinhada à borda do campo (o Campo é um quadro em volta da caixa)
        campo = self.entrada.master if type(
            self.entrada.master).__name__ == "Campo" else self.entrada
        try:
            campo.update_idletasks()
            largura = max(campo.winfo_width(), px(280),
                          self.janela.winfo_reqwidth())
            x = campo.winfo_rootx()
            y = campo.winfo_rooty() + campo.winfo_height() + px(2)
            self.janela.geometry(
                f"{largura}x{self.janela.winfo_reqheight()}+{x}+{y}")
        except tk.TclError:
            self.fechar()

    def _linha(self, pai, n, pessoa):
        linha = tk.Frame(pai, bg=COR["superficie"], cursor="hand2")
        linha.pack(fill="x")
        nome = tk.Label(linha, text=pessoa["nome"], font=FONTE["corpo"],
                        bg=COR["superficie"], fg=COR["texto"], anchor="w")
        nome.pack(side="top", fill="x", padx=px(10), pady=(px(6), 0))
        partes = [f"CPF {self.exibir_cpf(pessoa['cpf'])}"]
        if pessoa.get("tipo"):
            partes.append(pessoa["tipo"])
        apoio = tk.Frame(linha, bg=COR["superficie"])
        apoio.pack(side="top", fill="x", padx=px(10), pady=(0, px(6)))
        tk.Label(apoio, text="  ·  ".join(partes), font=FONTE["dica"],
                 bg=COR["superficie"], fg=COR["texto_2"]).pack(side="left")
        if pessoa.get("desativada"):
            marca, cor = DESATIVADA, COR["erro"]
        elif pessoa.get("dentro"):
            marca, cor = NA_UNIDADE, COR["sucesso"]
        else:
            marca = ""
        if marca:
            tk.Label(apoio, text=f"  ·  {marca}", font=FONTE["dica"],
                     bg=COR["superficie"], fg=cor).pack(side="left")
        for widget in (linha, nome, apoio, *apoio.winfo_children()):
            widget.bind("<Button-1>", lambda e, i=n: self.escolher_item(i))
            widget.bind("<Enter>", lambda e, i=n: self._marcar(i))
        return linha

    def _marcar(self, n):
        self.marcado = n
        for i, linha in enumerate(getattr(self, "linhas", [])):
            cor = COR["selecao"] if i == n else COR["superficie"]
            for widget in (linha, *linha.winfo_children()):
                widget.configure(bg=cor)
                for filho in widget.winfo_children():
                    filho.configure(bg=cor)

    def _mover(self, passo):
        if not self.aberta:
            return None
        n = self.marcado + passo
        self._marcar(max(0, min(len(self.itens) - 1, n)))
        return "break"

    def _confirmar(self, event=None):
        """Enter ou Tab com uma pessoa marcada: escolhe (e não deixa o
        Enter salvar o diálogo nem o Tab sair do campo)."""
        if self.aberta and self.marcado >= 0:
            self.escolher_item(self.marcado)
            return "break"
        self.fechar()
        return None

    def _esc(self, event=None):
        if self.aberta:
            self.fechar()
            return "break"
        return None

    def _ao_perder_foco(self, event=None):
        # o clique na lista tira o foco do campo: espera o clique chegar
        self.entrada.after(200, self._fechar_sem_foco)

    def _foco_na_lista(self):
        """O foco está na própria lista (o Windows ativa a janelinha ao
        mostrá-la ou no clique)."""
        try:
            foco = self.entrada.focus_get()
        except (tk.TclError, KeyError):
            return False
        return (foco is not None and self.janela is not None
                and str(foco).startswith(str(self.janela)))

    def _devolver_foco(self):
        """Se a lista pegou o foco ao aparecer, ele volta para o campo (a
        pessoa continua digitando)."""
        if self.aberta and self._foco_na_lista():
            try:
                self.entrada.focus_force()
            except tk.TclError:
                pass

    def _fechar_sem_foco(self):
        try:
            foco = self.entrada.focus_get()
        except (tk.TclError, KeyError):
            foco = None
        if foco is self.entrada or self._foco_na_lista():
            return
        self.fechar()


def ligar_sugestoes(app, entradas, preencher=None, so_dentro=False,
                    excluir=None, ao_escolher=None):
    """
    Liga as sugestões aos campos de CPF e de nome de um formulário.
    `entradas`: {"cpf": caixa, "nome": caixa} (só as que existem).
    Escolher uma pessoa em qualquer um dos dois preenche os dois.
    `preencher(pessoa)` troca o preenchimento padrão; `ao_escolher(pessoa)`
    roda depois dele. `so_dentro`: só quem está na unidade; `excluir()`:
    CPFs que não entram na lista. Devolve {campo: Sugestoes}.
    """
    def buscar(texto):
        return app.banco.sugerir_pessoas(
            texto, so_dentro=so_dentro, excluir=tuple(excluir() if excluir
                                                      else ()))

    def preencher_padrao(pessoa):
        for campo, caixa in entradas.items():
            valor = pessoa.get(campo, "")
            if caixa is not None and valor:
                caixa.delete(0, "end")
                caixa.insert(0, valor)

    def escolher(pessoa):
        (preencher or preencher_padrao)(pessoa)
        if ao_escolher is not None:
            ao_escolher(pessoa)
        app.registrar_uso()

    return {campo: Sugestoes(caixa, buscar, escolher, app.exibir_cpf)
            for campo, caixa in entradas.items() if caixa is not None}


def pessoa_pelo_nome(app, nome, so_dentro=False):
    """A pessoa do cadastro com exatamente esse nome (sem diferença de
    acento e maiúscula), se for uma só; senão None. Para quem digitou o
    nome inteiro sem escolher na lista."""
    alvo = sem_acento(" ".join((nome or "").split()))
    if len(alvo) < 3 or so_digitos(alvo) == alvo:
        return None
    try:
        pessoas = app.banco.sugerir_pessoas(nome, limite=20,
                                            so_dentro=so_dentro)
    except ErroDados:
        return None
    iguais = [p for p in pessoas if sem_acento(p["nome"]) == alvo]
    return iguais[0] if len(iguais) == 1 else None
