"""
Diálogo "Autorização do administrador": aparece quando uma entrada, uma
saída ou uma correção foge das regras de horário (horarios.py). Lista as
regras violadas e pede uma justificativa (obrigatória, vai para o
histórico).

- Porteiro logado: um administrador vem até a guarita e digita o login e
  a senha dele (senha oculta). A conferência é a mesma do login
  (usuarios.entrar): a senha errada conta como tentativa e trava o login
  depois de várias. Só um administrador ativo autoriza.
- Administrador logado: só confirma, com a justificativa (sem senha).
- Lançamento num dia que JÁ FECHOU (RN24 c, so_com_senha): a senha é
  obrigatória para todos. O administrador logado redigita a própria senha
  (o login dele já vem preenchido; outro administrador pode trocar).

O diálogo só devolve a autorização; quem grava é a tela, passando-a ao
banco, que confere de novo e grava o evento "Exceção autorizada". A tela
abre o diálogo por app.perguntar (autorizar_excecao): se a sessão acabar
com ele aberto, a resposta é None e nada é gravado.
"""

import tkinter as tk

from .componentes import Aviso, Dialogo, campo_rotulado
from .estilo import COR, FONTE, ICONE, px
from .horarios import MINIMO_JUSTIFICATIVA, Excecoes
from .usuarios import eh_admin, entrar

TITULO = "Autorização do administrador"
SO_ADMIN = ("Somente um administrador pode autorizar a exceção.\n"
            "Peça para um administrador digitar o login e a senha dele.")


class JanelaAutorizacao(Dialogo):
    def __init__(self, app, regras, acao, dono=None, so_com_senha=False):
        """
        regras: textos das regras violadas; acao: o que precisa da
        autorização ("A entrada de Ana Silva"). `resultado` fica com a
        autorização ({"autorizado_por", "regras", "justificativa",
        "com_senha"}) quando o administrador confirma; continua None se
        cancelar. so_com_senha: até o administrador logado digita a senha.
        """
        self.app, self.regras = app, list(regras)
        self.resultado = None
        self.erro = ""                  # último erro mostrado na faixa
        admin_logado = eh_admin(app.usuario)
        self.pede_senha = so_com_senha or not admin_logado
        if so_com_senha:
            subtitulo = (f"{acao} lança um horário de um dia que já fechou. "
                         "Isso só passa com a senha de um administrador"
                         + (" (digite a sua)." if admin_logado else "."))
        elif self.pede_senha:
            subtitulo = (f"{acao} foge das regras de horário. Um administrador "
                         "precisa autorizar com o login e a senha dele.")
        else:
            subtitulo = (f"{acao} foge das regras de horário. Como você é "
                         "administrador, basta confirmar com a justificativa.")
        super().__init__(dono or app.janela, TITULO, subtitulo, largura=460,
                         ao_usar=app.registrar_uso)
        self._montar()
        self.adicionar_botao("Autorizar exceção" if self.pede_senha
                             else "Confirmar exceção", self.confirmar,
                             "primario", dica_tecla="Enter")
        self.adicionar_botao("Cancelar", self.fechar)
        foco = self.justificativa
        if self.pede_senha:
            foco = self.login
            if admin_logado:            # o login dele já vem preenchido
                self.login.insert(0, app.autor)
                foco = self.senha
        self.abrir(confirmar=self.confirmar, foco=foco)

    def _montar(self):
        regras = Aviso(self.miolo)
        regras.mostrar("alerta", "\n".join(f"• {r}" for r in self.regras),
                       icone=ICONE["relogio"])
        regras.pack(fill="x", pady=(0, px(14)))
        self.login = self.senha = None
        if self.pede_senha:
            linha = tk.Frame(self.miolo, bg=COR["superficie"])
            linha.pack(fill="x", pady=(0, px(12)))
            linha.columnconfigure((0, 1), weight=1, uniform="a")
            grupo, campo = campo_rotulado(linha, "Administrador", "login")
            grupo.grid(row=0, column=0, sticky="ew", padx=(0, px(12)))
            self.login = campo.entrada
            grupo, campo = campo_rotulado(linha, "Senha", senha=True)
            grupo.grid(row=0, column=1, sticky="ew")
            self.senha = campo.entrada
        grupo, campo = campo_rotulado(
            self.miolo, "Justificativa",
            f"obrigatória, mín. {MINIMO_JUSTIFICATIVA} caracteres; vai para o histórico")
        grupo.pack(fill="x")
        self.justificativa = campo.entrada
        self.faixa = Aviso(self.miolo)
        self.lbl_erro = self.faixa.lbl
        tk.Label(self.miolo, text="A exceção fica registrada com quem autorizou "
                                  "e quem estava operando.",
                 font=FONTE["dica"], bg=COR["superficie"], fg=COR["texto_3"]
                 ).pack(anchor="w", pady=(px(8), 0))

    def _erro(self, texto):
        self.erro = texto
        self.faixa.mostrar("erro", texto)
        self.faixa.pack(fill="x", pady=(px(12), 0))

    def confirmar(self):
        justificativa = " ".join(self.justificativa.get().split())
        if len(justificativa) < MINIMO_JUSTIFICATIVA:
            self._erro("Escreva a justificativa da exceção (pelo menos "
                       f"{MINIMO_JUSTIFICATIVA} caracteres).")
            self.justificativa.focus_set()
            return
        autorizado_por = self._conferir_admin()
        if autorizado_por is None:
            return
        self.resultado = {"autorizado_por": autorizado_por,
                          "regras": self.regras,
                          "justificativa": justificativa,
                          "com_senha": self.pede_senha}
        self.fechar()

    def _conferir_admin(self):
        """Login de quem autoriza, ou None (com o erro na faixa)."""
        if not self.pede_senha:
            return self.app.autor
        ok, resposta = self.app.tentar(entrar, self.app.banco, self.login.get(),
                                       self.senha.get(), self.app.relogio())
        if not ok:
            return None
        usuario, motivo = resposta
        self.senha.delete(0, tk.END)
        if usuario is None:
            self._erro(motivo)
            self.senha.focus_set()
            return None
        if not eh_admin(usuario):
            self._erro(SO_ADMIN)
            self.login.focus_set()
            return None
        return usuario["login"]

    def esperar(self):
        """Trava até o diálogo fechar (os testes trocam por um preenchimento)."""
        self.janela.wait_window()


def pedir_autorizacao(app, regras, acao, dono=None, so_com_senha=False):
    """Abre o diálogo e espera a resposta: a autorização ou None."""
    dialogo = JanelaAutorizacao(app, regras, acao, dono, so_com_senha)
    dialogo.esperar()
    if dialogo.janela.winfo_exists():
        dialogo.fechar()
    if dono is not None and dono.winfo_exists():
        try:
            dono.grab_set()          # a janela de onde veio volta a ser modal
        except tk.TclError:
            pass
    return dialogo.resultado


def autorizar_excecao(app, regras, acao, dono=None, so_com_senha=False):
    """Pela app.perguntar: se a sessão acabou com o diálogo aberto, None.
    `regras` pode ser uma lista de textos ou um horarios.Excecoes (que já
    diz se a autorização exige a senha)."""
    if isinstance(regras, Excecoes):
        so_com_senha = so_com_senha or regras.so_com_senha
        regras = regras.regras
    return app.perguntar(pedir_autorizacao, app, regras, acao, dono,
                         so_com_senha)
