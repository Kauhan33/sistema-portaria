"""
Códigos de recuperação do administrador (RN38), na tela:

- JanelaCodigos: mostra os 8 códigos UMA vez (no primeiro acesso, logo
  depois de criar o administrador, e ao gerar novos). "Imprimir" abre uma
  página HTML no navegador (o arquivo temporário é apagado depois). Para
  continuar é preciso marcar "Guardei os códigos em lugar seguro".
- JanelaNovosCodigos: menu da conta → "Gerar novos códigos de
  recuperação"; pede a senha atual e invalida os códigos antigos.

O "Esqueci a senha" (login + código + nova senha) fica no formulário da
tela de login (tela_login.py); a regra está em usuarios.recuperar_senha.
"""

import atexit
import html
import os
import tempfile
import tkinter as tk
import webbrowser
from datetime import datetime

from . import mensagens
from .componentes import Alternador, Aviso, Dialogo, campo_rotulado
from .estilo import COR, FONTE, ICONE, px
from .usuarios import gerar_novos_codigos

TITULO = "Códigos de recuperação"
SEGUNDOS_ATE_APAGAR = 120        # o navegador já leu a página
_temporarios = []                # páginas de impressão ainda não apagadas


def pagina_de_impressao(codigos, login, momento):
    """HTML simples (imprime numa folha) com os códigos e como usá-los."""
    linhas = "\n".join(f"<li>{html.escape(c)}</li>" for c in codigos)
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>{TITULO} — Portaria</title>
<style>
body {{ font-family: "Segoe UI", sans-serif; margin: 40px; color: #1f2328; }}
h1 {{ font-size: 20px; margin-bottom: 4px; }}
p {{ font-size: 13px; color: #4b5563; max-width: 520px; }}
ol {{ columns: 2; font: 600 20px "Bahnschrift", monospace;
      letter-spacing: 2px; padding-left: 28px; }}
li {{ margin: 6px 0; }}
</style></head>
<body onload="window.print()">
<h1>{TITULO} — Portaria da Universidade</h1>
<p>Administrador: <b>{html.escape(login)}</b> · gerados em
{momento:%d/%m/%Y %H:%M}</p>
<ol>
{linhas}
</ol>
<p>Cada código vale <b>uma vez</b>. Se esquecer a senha, na tela de login
use "Esqueci a senha": usuário, um código e a senha nova. Guarde esta folha
em lugar seguro (não junto do computador da portaria).</p>
</body></html>"""


def imprimir_codigos(codigos, login, momento=None, dono=None):
    """Grava a página num arquivo temporário e abre no navegador (que
    imprime). O arquivo é apagado SEGUNDOS_ATE_APAGAR depois (ou ao fechar
    o programa). Devolve o caminho."""
    momento = momento or datetime.now()
    arquivo = tempfile.NamedTemporaryFile(
        "w", suffix=".html", prefix="portaria-codigos-", delete=False,
        encoding="utf-8")
    with arquivo:
        arquivo.write(pagina_de_impressao(codigos, login, momento))
    _temporarios.append(arquivo.name)
    webbrowser.open(f"file:///{arquivo.name.replace(os.sep, '/')}")
    if dono is not None:
        dono.after(SEGUNDOS_ATE_APAGAR * 1000, apagar_temporarios)
    return arquivo.name


def apagar_temporarios():
    """Apaga as páginas de impressão que ainda existem."""
    while _temporarios:
        caminho = _temporarios.pop()
        try:
            os.remove(caminho)
        except OSError:
            pass


atexit.register(apagar_temporarios)


class JanelaCodigos(Dialogo):
    def __init__(self, dono, codigos, login, relogio=None, ao_usar=None):
        """Mostra os códigos; `confirmado` fica True quando a pessoa marca
        "Guardei" e clica em Continuar."""
        self.codigos, self.login = list(codigos), login
        self.relogio = relogio or datetime.now
        self.confirmado = False
        super().__init__(dono, TITULO,
                         "Guarde estes códigos: com um deles você troca a "
                         "senha se esquecê-la. Cada um vale uma vez e eles "
                         "não aparecem de novo.", largura=430, ao_usar=ao_usar)
        grade = tk.Frame(self.miolo, bg=COR["superficie_2"],
                         highlightthickness=1,
                         highlightbackground=COR["borda"])
        grade.pack(fill="x")
        grade.columnconfigure((0, 1), weight=1, uniform="c")
        self.rotulos = []
        for i, codigo in enumerate(self.codigos):
            rotulo = tk.Label(grade, text=f"{i + 1}.  {codigo}",
                              font=FONTE["numero"], bg=COR["superficie_2"],
                              fg=COR["texto"], anchor="w")
            rotulo.grid(row=i // 2, column=i % 2, sticky="w",
                        padx=px(18), pady=px(4))
            self.rotulos.append(rotulo)
        self.guardei = tk.BooleanVar(self.janela, value=False)
        self.alternador = Alternador(self.miolo,
                                     "Guardei os códigos em lugar seguro",
                                     self.guardei, comando=self._ao_marcar)
        self.alternador.pack(anchor="w", pady=(px(14), 0))
        self.faixa = Aviso(self.miolo)
        self.btn_continuar = self.adicionar_botao("Continuar", self.continuar,
                                                  "primario")
        self.btn_continuar.definir_ativo(False)
        self.adicionar_botao("Imprimir", self.imprimir,
                             icone=ICONE["baixar"])
        self.abrir(confirmar=self.continuar)
        # fechar pelo X ou Esc também exige o "Guardei"
        self.janela.protocol("WM_DELETE_WINDOW", self.continuar)
        self.janela.bind("<Escape>", lambda e: self.continuar())

    def _ao_marcar(self):
        self.btn_continuar.definir_ativo(self.guardei.get())
        if self.guardei.get():
            self.faixa.pack_forget()

    def imprimir(self):
        imprimir_codigos(self.codigos, self.login, self.relogio(), self.janela)

    def continuar(self):
        if not self.guardei.get():
            self.faixa.mostrar("alerta", "Marque \"Guardei os códigos em "
                                         "lugar seguro\" para continuar.")
            self.faixa.pack(fill="x", pady=(px(12), 0))
            return
        self.confirmado = True
        self.fechar()

    def esperar(self):
        """Trava até fechar (os testes trocam por uma resposta)."""
        self.janela.wait_window()


def mostrar_codigos(dono, codigos, login, relogio=None, ao_usar=None):
    janela = JanelaCodigos(dono, codigos, login, relogio, ao_usar)
    janela.esperar()
    if janela.janela.winfo_exists():
        janela.fechar()
    return janela.confirmado


class JanelaNovosCodigos(Dialogo):
    """Menu da conta → "Gerar novos códigos de recuperação" (só
    administrador): confirma com a senha atual e mostra os novos."""

    def __init__(self, app):
        self.app = app
        super().__init__(app.janela, "Gerar novos códigos",
                         "Os códigos de recuperação antigos deixam de valer. "
                         "Confirme com a sua senha atual.", largura=360,
                         ao_usar=app.registrar_uso)
        grupo, campo = campo_rotulado(self.miolo, "Senha atual", senha=True)
        grupo.pack(fill="x")
        self.senha = campo.entrada
        self.faixa = Aviso(self.miolo)
        self.adicionar_botao("Gerar códigos", self.gerar, "primario")
        self.adicionar_botao("Cancelar", self.fechar)
        self.abrir(confirmar=self.gerar, foco=self.senha)

    def gerar(self):
        ok, resposta = self.app.tentar(gerar_novos_codigos, self.app.banco,
                                       self.app.usuario, self.senha.get())
        self.senha.delete(0, tk.END)
        if not ok:
            return
        codigos, motivo = resposta
        if codigos is None:
            self.faixa.mostrar("erro", motivo)
            self.faixa.pack(fill="x", pady=(px(12), 0))
            return
        self.fechar()
        self.app.perguntar(mostrar_codigos, self.app.janela, codigos,
                           self.app.autor, self.app.relogio,
                           self.app.registrar_uso)
        mensagens.info(TITULO, "Códigos novos gerados. Os antigos não valem "
                               "mais.")
