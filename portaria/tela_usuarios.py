"""
Página Usuários (só administrador): as contas (criar porteiros e
administradores, ativar ou desativar, redefinir senha) e a atividade do
sistema (histórico de ações, com filtro). "Novo usuário" abre um diálogo.
"""

import tkinter as tk

from . import mensagens
from .componentes import (Aviso, Botao, Cabecalho, Campo, Cartao, Dialogo,
                          campo_rotulado, inserir_linha, plural,
                          preencher_eventos, tabela, tabela_eventos,
                          titulo_cartao)
from .estilo import COR, ESPACO_CARTOES, ICONE, MARGEM, px
from .usuarios import (PERFIS, SENHA_MINIMA, gerar_hash, normalizar_login,
                       pode_desativar, validar_novo_usuario, validar_senha)

PERFIL_POR_NOME = {nome: chave for chave, nome in PERFIS.items()}
COLUNAS = [("login", "Usuário", 140, "w"), ("nome", "Nome", 260, "w"),
           ("perfil", "Perfil", 140, "w"), ("situacao", "Situação", 90, "w")]
COLUNAS_VISIVEIS = ("login", "nome", "perfil")


class AbaUsuarios:
    def __init__(self, aba, app):
        self.aba = aba
        self.app = app
        self.usuarios = []
        self.eventos = []
        self.dialogo = None

        cab = Cabecalho(aba, "Usuários").posicionar()
        self.lbl_total = cab.subtitulo
        Botao(cab.acoes, "Novo usuário", self.novo_usuario, "primario",
              icone=ICONE["mais"], fundo_pai=COR["fundo"]).pack()
        self._montar_contas()
        self._montar_atividade()
        self.atualizar()

    # --------------------------------------------------------------
    # Montagem
    # --------------------------------------------------------------
    def _montar_contas(self):
        cartao = Cartao(self.aba, pad=0)
        cartao.pack(fill="x", padx=px(MARGEM), pady=(0, px(ESPACO_CARTOES)))
        m = cartao.miolo
        m.pack_configure(padx=px(1), pady=px(8))
        barra = tk.Frame(m, bg=COR["superficie"])
        barra.pack(fill="x", padx=px(19), pady=(px(6), px(12)))
        titulo_cartao(barra, "Contas").pack(side="left")
        self.btn_ativo = Botao(barra, "Desativar", self.alternar_ativo, "perigo",
                               largura=120)
        self.btn_ativo.pack(side="right")
        Botao(barra, "Redefinir senha", self.redefinir_senha, "secundario",
              icone=ICONE["chave"]).pack(side="right", padx=(0, px(8)))
        quadro, self.tabela = tabela(m, COLUNAS, situacao="Situação",
                                     mostrar=COLUNAS_VISIVEIS, altura=4,
                                     rolagem=True)
        quadro.pack(fill="x", padx=px(12))
        self.tabela.bind("<<TreeviewSelect>>", lambda e: self._ao_selecionar())

    def _montar_atividade(self):
        cartao = Cartao(self.aba, pad=0)
        cartao.pack(fill="both", expand=True, padx=px(MARGEM),
                    pady=(0, px(MARGEM)))
        m = cartao.miolo
        m.pack_configure(padx=px(1), pady=px(8))
        barra = tk.Frame(m, bg=COR["superficie"])
        barra.pack(fill="x", padx=px(19), pady=(px(6), px(12)))
        titulo_cartao(barra, "Atividade").pack(side="left")
        campo = Campo(barra, largura=300, icone=ICONE["busca"],
                      dica_vazio="Filtrar por usuário, ação ou detalhe")
        campo.pack(side="left", padx=(px(16), 0))
        self.busca = campo.entrada
        self.busca.bind("<KeyRelease>", lambda e: self._mostrar_eventos())
        quadro, self.historico = tabela_eventos(m, (150, 110, 190, 420), altura=6)
        quadro.pack(fill="both", expand=True, padx=px(12))

    # --------------------------------------------------------------
    # Dados
    # --------------------------------------------------------------
    def atualizar(self):
        ok, usuarios = self.app.tentar(self.app.banco.listar_usuarios)
        if ok:
            self.usuarios = usuarios
            selecao = self.tabela.selection()
            self.tabela.delete(*self.tabela.get_children())
            for i, u in enumerate(usuarios):
                situacao = "Ativo" if u["ativo"] else "Desativado"
                inserir_linha(self.tabela, i, (
                    u["login"], u["nome"], PERFIS[u["perfil"]], situacao),
                    iid=str(u["id"]), situacao=situacao,
                    cor=COR["sucesso"] if u["ativo"] else COR["barra"],
                    tags=() if u["ativo"] else ("apagado",))
            if selecao and self.tabela.exists(selecao[0]):
                self.tabela.selection_set(selecao[0])
            ativos = sum(1 for u in usuarios if u["ativo"])
            inativas = len(usuarios) - ativos
            self.lbl_total.config(text=plural(ativos, "conta ativa", "contas ativas")
                                  + (f"  ·  {plural(inativas, 'desativada', 'desativadas')}"
                                     if inativas else ""))
        ok, eventos = self.app.tentar(self.app.banco.listar_eventos)
        if ok:
            self.eventos = eventos
            self._mostrar_eventos()
        self._ao_selecionar()

    def _mostrar_eventos(self):
        texto = self.busca.get().strip().lower()
        preencher_eventos(self.historico, [
            e for e in self.eventos
            if not texto or texto in f"{e['usuario']} {e['acao']} "
                                     f"{e['detalhe']}".lower()])

    def _ao_selecionar(self):
        """O botão diz o que vai fazer com a conta selecionada."""
        selecao = self.tabela.selection()
        alvo = next((u for u in self.usuarios
                     if selecao and str(u["id"]) == selecao[0]), None)
        if alvo is not None and not alvo["ativo"]:
            self.btn_ativo.definir_texto("Ativar", "secundario")
        else:
            self.btn_ativo.definir_texto("Desativar", "perigo")

    def _selecionado(self):
        selecao = self.tabela.selection()
        if not selecao:
            mensagens.aviso("Atenção", "Selecione um usuário na lista.")
            return None
        return next(u for u in self.usuarios if u["id"] == int(selecao[0]))

    # --------------------------------------------------------------
    # Ações
    # --------------------------------------------------------------
    def novo_usuario(self):
        """Abre o diálogo "Novo usuário"; devolve o diálogo."""
        self.dialogo = DialogoUsuario(self)
        return self.dialogo

    def alternar_ativo(self):
        alvo = self._selecionado()
        if alvo is None:
            return
        if alvo["ativo"]:
            admins = sum(1 for u in self.usuarios
                         if u["perfil"] == "admin" and u["ativo"])
            ok, msg = pode_desativar(alvo, self.app.usuario, admins)
            if not ok:
                mensagens.erro("Não permitido", msg)
                return
            if not self.app.perguntar(
                    mensagens.confirmar,
                    "Desativar usuário", f"Desativar o usuário {alvo['login']}?\n"
                                         "Ele não conseguirá mais entrar no sistema."):
                return
        self.app.tentar(self.app.banco.definir_ativo, alvo["id"],
                        not alvo["ativo"], autor=self.app.autor)
        self.atualizar()

    def redefinir_senha(self):
        alvo = self._selecionado()
        if alvo is None:
            return
        senha = self.app.perguntar(
            mensagens.pedir_senha, "Redefinir senha",
            f"Nova senha para {alvo['login']}:", parent=self.aba)
        if senha is None:
            return
        confirmacao = self.app.perguntar(
            mensagens.pedir_senha, "Redefinir senha",
            "Digite a nova senha de novo:", parent=self.aba)
        if confirmacao is None:
            return
        ok, msg = validar_senha(senha, confirmacao)
        if not ok:
            mensagens.erro("Dados inválidos", msg)
            return
        ok, _ = self.app.tentar(self.app.banco.definir_senha, alvo["id"],
                                gerar_hash(senha), autor=self.app.autor)
        if ok:
            self.atualizar()
            mensagens.info("Usuários",
                           f"Senha de {alvo['login']} redefinida. Se o login "
                           "estava travado por tentativas erradas, já foi "
                           "liberado.")


class DialogoUsuario(Dialogo):
    """Diálogo "Novo usuário": nome, login, senha (2x) e perfil."""

    def __init__(self, aba):
        self.aba = aba
        app = aba.app
        super().__init__(app.janela, "Novo usuário",
                         "O usuário entra com o login e a senha daqui. Peça "
                         "para ele trocar a senha no primeiro acesso.",
                         largura=440, ao_usar=app.registrar_uso)
        form = self.miolo
        form.columnconfigure((0, 1), weight=1, uniform="u")

        def campo(texto, linha, coluna, juntas=1, apoio="", **opcoes):
            grupo, c = campo_rotulado(form, texto, apoio, **opcoes)
            grupo.grid(row=linha, column=coluna, columnspan=juntas, sticky="ew",
                       pady=(0, px(14)),
                       padx=(0, px(10)) if coluna == 0 and juntas == 1 else 0)
            return c.entrada

        self.nome = campo("Nome completo", 0, 0, juntas=2)
        self.login = campo("Usuário", 1, 0, juntas=2, apoio="ex.: maria.souza")
        self.senha = campo("Senha", 2, 0, apoio=f"mín. {SENHA_MINIMA}", senha=True)
        self.confirmacao = campo("Confirmar senha", 2, 1, senha=True)
        self.perfil = campo("Perfil", 3, 0, opcoes=PERFIL_POR_NOME)
        self.perfil.set(PERFIS["porteiro"])
        self.faixa = Aviso(form)
        self.lbl_erro = self.faixa.lbl
        self.adicionar_botao("Criar usuário", self.criar, "primario")
        self.adicionar_botao("Cancelar", self.fechar)
        self.abrir(confirmar=self.criar, foco=self.nome)

    def criar(self):
        app = self.aba.app
        nome = " ".join(self.nome.get().split())
        login = normalizar_login(self.login.get())
        senha = self.senha.get()
        perfil = PERFIL_POR_NOME.get(self.perfil.get(), "")
        ok, msg = validar_novo_usuario(nome, login, senha, self.confirmacao.get(),
                                       perfil,
                                       {u["login"] for u in self.aba.usuarios})
        if not ok:
            self.faixa.mostrar("erro", msg)
            self.faixa.grid(row=4, column=0, columnspan=2, sticky="ew")
            return
        ok, _ = app.tentar(app.banco.criar_usuario, nome, login, perfil,
                           gerar_hash(senha), autor=app.autor)
        if not ok:
            return
        self.fechar()
        self.aba.atualizar()
        mensagens.info("Usuários", f"Usuário {login} criado. "
                                   "Ele já pode entrar no sistema.")
