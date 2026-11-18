"""
A chave da portaria na saída (3.6).

Quem vai sair e está com uma chave da portaria não sai com ela: antes da
saída, a pergunta "Carla está com a chave Laboratório 2" →
[Registrar devolução] a chave volta para a portaria; [Transferir para
outra pessoa] a chave passa para alguém que está na unidade (CPF e nome,
com as sugestões); Cancelar: nada é registrado e a pessoa continua dentro.
Uma pergunta por chave. O banco confere de novo (registrar_saidas recusa a
saída de quem ainda está com chave).

A pergunta abre por app.perguntar: se a sessão acabar com ela aberta, a
resposta é None e nada é gravado. Os testes trocam `esperar` por uma
resposta (como nas perguntas do carro, tela_veiculo.py).
"""

import tkinter as tk
from types import SimpleNamespace

from .componentes import Dialogo
from .estilo import COR, FONTE, px

DEVOLVER, TRANSFERIR = "devolver", "transferir"


class JanelaChaveNaSaida(Dialogo):
    """A pergunta de uma chave: `resultado` fica DEVOLVER, TRANSFERIR ou
    None (cancelou)."""

    def __init__(self, app, registro, chave):
        self.app, self.resultado = app, None
        primeiro = registro["nome"].split()[0]
        super().__init__(
            app.janela, f"{primeiro} está com a chave \"{chave['nome']}\"",
            "A chave da portaria não sai da unidade com a pessoa.",
            largura=520, ao_usar=app.registrar_uso)
        texto = (f"{registro['nome']} está com a chave \"{chave['nome']}\" "
                    f"desde {chave['desde']}. Antes da saída, registre a "
                    "devolução ou transfira a chave para outra pessoa que "
                    "está na unidade.")
        tk.Label(self.miolo, text=texto, font=FONTE["corpo"],
                 bg=COR["superficie"], fg=COR["texto"], justify="left",
                 wraplength=px(460)).pack(anchor="w", pady=(0, px(4)))
        self.adicionar_botao("Registrar devolução",
                             lambda: self.escolher(DEVOLVER), "primario")
        self.adicionar_botao("Transferir para outra pessoa",
                             lambda: self.escolher(TRANSFERIR), "secundario")
        self.adicionar_botao("Cancelar", self.fechar)
        self.abrir(confirmar=lambda: self.escolher(DEVOLVER))

    def escolher(self, valor):
        self.resultado = valor
        self.fechar()

    def esperar(self):
        """Trava até o diálogo fechar (os testes trocam por uma resposta)."""
        self.janela.wait_window()


def _perguntar(app, registro, chave):
    dialogo = JanelaChaveNaSaida(app, registro, chave)
    dialogo.esperar()
    if dialogo.janela.winfo_exists():
        dialogo.fechar()
    return dialogo.resultado


def esperar_transferencia(dialogo):
    """Trava até o diálogo da transferência fechar (os testes trocam)."""
    dialogo.janela.wait_window()


def _para_quem(app, registro, chave, saindo):
    """Transfere a chave para quem o porteiro escolher (uma pessoa na
    unidade que não está saindo junto). Devolve (nome, CPF) de quem recebeu,
    ou None (cancelou). Se o banco recusar, o diálogo continua aberto."""
    from .tela_livros import DialogoQuemRetira     # (evita import circular)
    escolha = {}

    def transferir(nome, cpf):
        ok, _ = app.tentar(app.banco.transferir_chave, chave["id"], cpf,
                           app.autor)
        if ok:
            escolha.update(nome=nome, cpf=cpf)
        return ok

    dialogo = DialogoQuemRetira(
        SimpleNamespace(app=app), "Transferir chave",
        f"{registro['nome']} vai sair. Para quem vai a chave "
        f"\"{chave['nome']}\"?", "Transferir", transferir,
        excluir=lambda: saindo,
        recusa="{nome} também está saindo.\nEscolha quem fica na unidade.")
    esperar_transferencia(dialogo)
    if dialogo.janela.winfo_exists():
        dialogo.fechar()
    return (escolha["nome"], escolha["cpf"]) if escolha else None


def resolver_chaves(app, registros):
    """Antes da saída de `registros`: cada chave que está com alguém deles
    é devolvida ou transferida. True = pode seguir com a saída; False =
    cancelou (o que já foi devolvido ou transferido fica gravado)."""
    saindo = tuple(r["cpf"] for r in registros)
    for registro in registros:
        ok, chaves = app.tentar(app.banco.chaves_da_pessoa, registro["cpf"])
        if not ok:
            return False
        for chave in chaves:
            resposta = app.perguntar(_perguntar, app, registro, chave)
            if resposta == DEVOLVER:
                ok, _ = app.tentar(app.banco.devolver_chave, chave["id"],
                                   app.autor)
            elif resposta == TRANSFERIR:
                # (a transferência é gravada no próprio diálogo)
                if app.perguntar(_para_quem, app, registro, chave,
                                 saindo) is None:
                    return False
            else:
                return False
            if not ok:
                return False
    return True
