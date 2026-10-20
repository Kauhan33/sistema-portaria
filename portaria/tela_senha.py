"""
Janela "Trocar minha senha" (menu do usuário, no rodapé da barra lateral).
Qualquer perfil troca a PRÓPRIA senha informando a atual; a regra fica em
usuarios.trocar_senha (senha mínima, senhas fáceis recusadas, histórico).
"""

import tkinter as tk

from . import mensagens
from .componentes import Aviso, Dialogo, campo_rotulado
from .estilo import px
from .usuarios import SENHA_MINIMA, trocar_senha


class JanelaSenha(Dialogo):
    def __init__(self, app):
        self.app = app
        super().__init__(app.janela, "Trocar minha senha",
                         "Informe a senha atual e escolha uma nova, com pelo "
                         f"menos {SENHA_MINIMA} caracteres.", largura=360,
                         ao_usar=app.registrar_uso)
        self.atual = self._campo("Senha atual")
        self.nova = self._campo("Nova senha")
        self.confirmacao = self._campo("Confirmar a nova senha")
        self.faixa = Aviso(self.miolo)
        self.lbl_erro = self.faixa.lbl
        self.adicionar_botao("Salvar nova senha", self.salvar, "primario")
        self.adicionar_botao("Cancelar", self.fechar)
        self.abrir(confirmar=self.salvar, foco=self.atual)

    def _campo(self, texto):
        grupo, campo = campo_rotulado(self.miolo, texto, senha=True)
        grupo.pack(fill="x", pady=(0, px(14)))
        return campo.entrada

    def salvar(self):
        ok, resultado = self.app.tentar(
            trocar_senha, self.app.banco, self.app.usuario, self.atual.get(),
            self.nova.get(), self.confirmacao.get())
        if not ok:
            return
        trocou, msg = resultado
        if not trocou:
            self.faixa.mostrar("erro", msg)
            self.faixa.pack(fill="x", pady=(px(2), 0))
            for caixa in (self.nova, self.confirmacao):
                caixa.delete(0, tk.END)
            return
        self.fechar()
        mensagens.info("Trocar minha senha", msg)

