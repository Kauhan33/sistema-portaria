"""
Janela principal (Tkinter): cabeçalho, sessão do usuário (login e saída) e
as abas. Cada aba mora no seu módulo: tela_cadastro.py, tela_pessoas.py,
tela_bloqueios.py, tela_dashboard.py e tela_usuarios.py (só administrador);
o login fica em tela_login.py e a janela "Corrigir registro" em
tela_edicao.py.

As regras ficam em validacao.py e usuarios.py, o banco de dados em dados.py
e os números em consultas.py — as telas só montam widgets e reagem aos
botões.

CONTRATO DO APP — o que as telas podem usar da AppPortaria:
    app.janela                   janela principal (Tk)
    app.banco                    banco de dados (dados.Banco)
    app.usuario                  quem está logado (dicionário)
    app.autor                    login de quem está logado (para o histórico)
    app.registros                lista de visitas carregada do banco
    app.tentar(operacao, ...)    roda no banco; (True, resultado) ou avisa
                                 o erro e devolve (False, None)
    app.gravar(operacao, ...)    grava em nome do usuário e recarrega a lista
    app.recarregar_registros()   relê a lista de visitas do banco
    app.atualizar_tabela()       redesenha a tabela do Cadastro e o Dashboard
    app.avisar(texto, desfazer=None)  aviso que some sozinho no Cadastro
    app.preencher_pessoa(pessoa) abre o Cadastro com a pessoa preenchida
Nenhuma tela mexe em atributo com "_" do app.

Convenção das abas: class AbaX com __init__(self, aba, app) e atualizar().
"""

import tkinter as tk
from tkinter import ttk

from . import dados, mensagens
from .componentes import botao_pequeno
from .estilo import COR, FONTE, aplicar_tema
from .tela_bloqueios import AbaBloqueios
from .tela_cadastro import AbaCadastro
from .tela_dashboard import AbaDashboard
from .tela_login import TelaLogin
from .tela_pessoas import AbaPessoas
from .tela_usuarios import AbaUsuarios
from .usuarios import PERFIS, ControleTentativas, pode_gerenciar_usuarios

TECLAS_DA_SESSAO = ("<Return>", "<KP_Enter>", "<F2>")

# Nomes da aba Cadastro que continuam valendo como app.<nome> (os testes e
# a versão anterior usavam assim): app.cpf é o mesmo que
# app.tela_cadastro.cpf.
NOMES_DO_CADASTRO = {
    "nome", "cpf", "var_cpf", "celular", "var_placa", "tipo", "entrada",
    "saida", "tabela", "busca", "lbl_pessoa", "lbl_dica_placa", "lbl_aviso",
    "btn_desfazer", "btn_excluir", "campo_saida_rapida", "lbl_status",
    "janela_edicao", "cadastrar", "limpar", "registrar_saida",
    "registrar_saida_da_linha", "saida_rapida", "desfazer_saida",
    "editar_selecionado", "excluir_selecionado",
}


class AppPortaria:
    def __init__(self, caminho_banco, janela=None, json_antigo=None,
                 usuario=None):
        """
        json_antigo: arquivo da v1; se existir, é importado para o banco.
        usuario: entra direto com esse usuário (usado nos testes); sem ele,
        a janela abre na tela de login.
        """
        self.caminho_banco = caminho_banco
        self.json_antigo = json_antigo
        self.banco = None
        self.usuario = None                       # quem está logado
        self.tentativas = ControleTentativas()
        self.corpo = None                         # login ou abas principais
        self.registros = []                       # cópia do banco para a tela
        self.tela_cadastro = self.tela_dashboard = None

        self.janela = janela or tk.Tk()
        self._montar_janela()
        self._carregar()
        if usuario:
            self.entrar(usuario)
        else:
            self.mostrar_login()

    def executar(self):
        self.janela.mainloop()

    def __getattr__(self, nome):
        # Só é chamado quando o app não tem o atributo: app.cpf, app.cadastrar
        # etc. são repassados para a aba Cadastro (ver NOMES_DO_CADASTRO).
        cadastro = self.__dict__.get("tela_cadastro")
        if cadastro is not None and nome in NOMES_DO_CADASTRO:
            return getattr(cadastro, nome)
        raise AttributeError(f"AppPortaria não tem o atributo '{nome}'")

    @property
    def cards(self):
        """Cards do Dashboard: chave -> (rótulo do valor, rótulo de apoio)."""
        return self.tela_dashboard.cards if self.tela_dashboard else {}

    # --------------------------------------------------------------
    # Banco de dados (parte do contrato usado pelas telas)
    # --------------------------------------------------------------
    def _carregar(self):
        try:
            self.banco = dados.Banco(self.caminho_banco)
            aviso = (self.banco.importar_json(self.json_antigo)
                     if self.json_antigo else "")
        except dados.ErroDados as e:
            self.banco = None
            mensagens.erro("Erro", str(e))
            return
        if aviso:
            mensagens.info("Banco de dados", aviso)

    @property
    def autor(self):
        """Login de quem está logado; vai para o histórico de cada ação."""
        return self.usuario["login"] if self.usuario else None

    def tentar(self, operacao, *args, **kwargs):
        """Executa no banco; devolve (True, resultado) ou avisa e (False, None)."""
        try:
            return True, operacao(*args, **kwargs)
        except dados.ErroDados as e:
            mensagens.erro("Erro", str(e))
            return False, None

    def gravar(self, operacao, *args):
        """Grava em nome do usuário logado e recarrega a lista; False se falhar."""
        ok, _ = self.tentar(operacao, *args, autor=self.autor)
        if ok:
            self.recarregar_registros()
        return ok

    def recarregar_registros(self):
        """Relê as visitas do banco; se falhar, mantém a lista que já estava."""
        ok, registros = self.tentar(self.banco.listar)
        if ok:
            self.registros = registros
        return ok

    def atualizar_tabela(self):
        """Os registros mudaram: redesenha a tabela do Cadastro e o Dashboard."""
        self.tela_cadastro.atualizar_tabela()
        self.tela_dashboard.atualizar()

    def avisar(self, texto, desfazer=None):
        self.tela_cadastro.avisar(texto, desfazer)

    def preencher_pessoa(self, pessoa):
        """Começa uma nova entrada para a pessoa (usado pela aba Pessoas)."""
        self.abas.select(self.aba_cad)
        self.tela_cadastro.preencher_pessoa(pessoa)

    # --------------------------------------------------------------
    # Sessão: login e saída
    # --------------------------------------------------------------
    def _trocar_corpo(self):
        if self.corpo is not None:
            self.corpo.destroy()
        self.corpo = tk.Frame(self.janela, bg=COR["fundo"])
        self.corpo.pack(fill="both", expand=True)

    def mostrar_login(self):
        self._trocar_corpo()
        self.tela_login = TelaLogin(self.corpo, self.banco, self.tentativas,
                                    self.entrar)

    def entrar(self, usuario):
        self.usuario = usuario
        self.tentar(self.banco.registrar_evento, usuario["login"],
                    "Entrou no sistema")
        self.lbl_usuario.config(
            text=f"👤 {usuario['nome']}  ·  {PERFIS[usuario['perfil']]}")
        self.sessao.place(relx=1.0, rely=0.5, anchor="e", x=-20)
        self._trocar_corpo()
        self._montar_principal()

    def sair(self):
        if self.usuario:
            self.tentar(self.banco.registrar_evento, self.autor,
                        "Saiu do sistema")
        self.usuario = None
        for tecla in TECLAS_DA_SESSAO:
            self.janela.unbind(tecla)
        self.sessao.place_forget()
        self.mostrar_login()

    # --------------------------------------------------------------
    # Montagem da janela e das abas
    # --------------------------------------------------------------
    def _montar_janela(self):
        janela = self.janela
        janela.title("Portaria da Universidade")
        janela.geometry("1020x720")
        janela.minsize(900, 620)
        janela.configure(bg=COR["fundo"])
        aplicar_tema(janela)

        # Cabeçalho
        topo = tk.Frame(janela, bg=COR["marca"])
        topo.pack(fill="x")
        tk.Label(topo, text="🏛  Portaria da Universidade", bg=COR["marca"],
                 fg=COR["texto_invertido"], font=FONTE["titulo_pagina"]
                 ).pack(anchor="w", padx=20, pady=(12, 0))
        tk.Label(topo, text="Controle de entrada e saída de pessoas no campus",
                 bg=COR["marca"], fg=COR["marca_tinta"], font=FONTE["corpo"]
                 ).pack(anchor="w", padx=20, pady=(0, 12))

        # Quem está logado + Sair (aparece só depois do login)
        self.sessao = tk.Frame(topo, bg=COR["marca"])
        self.lbl_usuario = tk.Label(self.sessao, bg=COR["marca"],
                                    fg=COR["texto_invertido"],
                                    font=FONTE["corpo_semi"])
        self.lbl_usuario.pack(side="left", padx=(0, 12))
        botao_pequeno(self.sessao, "Sair", self.sair, COR["superficie"],
                      cor_texto=COR["marca"], cor_ativa=COR["marca_tinta"],
                      padx=12, pady=3).pack(side="left")

    def _nova_aba(self, titulo):
        aba = tk.Frame(self.abas, bg=COR["fundo"])
        self.abas.add(aba, text=f"  {titulo}  ")
        return aba

    def _montar_principal(self):
        """Abas que aparecem depois do login."""
        self.abas = ttk.Notebook(self.corpo)
        self.abas.pack(fill="both", expand=True)
        self.aba_cad = self._nova_aba("📋 Cadastro")
        self.aba_pessoas = self._nova_aba("👥 Pessoas")
        self.aba_bloqueios = self._nova_aba("🚫 Bloqueios")
        self.aba_dash = self._nova_aba("📊 Dashboard")
        self.aba_usuarios = self.tela_usuarios = None
        self.tela_cadastro = AbaCadastro(self.aba_cad, self)
        self.tela_dashboard = AbaDashboard(self.aba_dash, self)
        self.tela_pessoas = AbaPessoas(self.aba_pessoas, self)
        self.tela_bloqueios = AbaBloqueios(self.aba_bloqueios, self)
        if pode_gerenciar_usuarios(self.usuario):
            self.aba_usuarios = self._nova_aba("👤 Usuários")
            self.tela_usuarios = AbaUsuarios(self.aba_usuarios, self)

        # abrir uma destas abas relê os dados dela
        self._telas_que_recarregam = {
            str(aba): tela for aba, tela in [
                (self.aba_pessoas, self.tela_pessoas),
                (self.aba_bloqueios, self.tela_bloqueios),
                (self.aba_usuarios, self.tela_usuarios)] if aba is not None}
        self.abas.bind("<<NotebookTabChanged>>", self.ao_trocar_aba)

        # Tecla ENTER cadastra (só na aba Cadastro; a busca ignora o Enter)
        self.janela.bind("<Return>", self.tela_cadastro.cadastrar)
        self.janela.bind("<KP_Enter>", self.tela_cadastro.cadastrar)
        self.janela.bind(
            "<F2>", lambda e: self.tela_cadastro.campo_saida_rapida.focus_set())

        self.recarregar_registros()
        self.tela_cadastro.limpar()
        self.atualizar_tabela()

    def ao_trocar_aba(self, event=None):
        tela = self._telas_que_recarregam.get(self.abas.select())
        if tela is not None:
            tela.atualizar()
