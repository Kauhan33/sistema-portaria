"""
Página Usuários (só administrador): as contas (criar porteiros e
administradores, ativar ou desativar, redefinir senha) e a atividade do
sistema (histórico de ações, com filtro). "Novo usuário" e "Redefinir
senha" abrem diálogos no estilo Guarita (as caixas de senha têm o mesmo
limite de 64 caracteres das outras).

Seção Exceções (V4): o relatório de tudo o que passou por cima de uma
regra num período (excecoes.py), com os filtros período (calendário), tipo
e quem autorizou, a pessoa com o CPF mascarado e "Exportar CSV" no padrão
do Painel (a exportação fica no histórico).
"""

import tkinter as tk
from datetime import datetime

from . import backup, excecoes, mensagens
from .componentes import (Aviso, Botao, Cabecalho, Campo, Cartao, Dialogo,
                          Seletor, campo_rotulado, inserir_linha, plural,
                          preencher_eventos, tabela, tabela_eventos,
                          titulo_cartao)
from .estilo import COR, ESPACO_CARTOES, FONTE, ICONE, MARGEM, px
from .validacao import MAXIMO_BUSCA, MAXIMO_LOGIN, MAXIMO_NOME
from .usuarios import (PERFIS, SENHA_MINIMA, gerar_hash, normalizar_login,
                       pode_desativar, validar_novo_usuario, validar_senha)

PERFIL_POR_NOME = {nome: chave for chave, nome in PERFIS.items()}
COLUNAS = [("login", "Usuário", 140, "w"), ("nome", "Nome", 260, "w"),
           ("perfil", "Perfil", 140, "w"), ("situacao", "Situação", 90, "w")]
COLUNAS_VISIVEIS = ("login", "nome", "perfil")
SECOES = ("Contas", "Exceções")
COLUNAS_EXCECOES = [("quando", "Quando", 124, "w"), ("tipo", "Tipo", 150, "w"),
                    ("pessoa", "Pessoa", 210, "w"),
                    ("autorizou", "Quem autorizou", 110, "w"),
                    ("operava", "Quem operava", 100, "w"),
                    ("justificativa", "Justificativa", 300, "w")]
FORMATO_DIA = "%d/%m/%Y"


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
        self.seletor = Seletor(aba, SECOES, self.mostrar_secao)
        self.seletor.pack(fill="x", padx=px(MARGEM), pady=(0, px(12)))
        self.secoes = {nome: tk.Frame(aba, bg=COR["fundo"]) for nome in SECOES}
        self.excecoes = []          # linhas do relatório (excecoes.ler_excecao)
        self._montar_contas()
        self._montar_atividade()
        self._montar_excecoes()
        self.seletor.selecionar(SECOES[0])
        self.atualizar()

    def mostrar_secao(self, nome):
        for secao, frame in self.secoes.items():
            if secao == nome:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()
        if nome == SECOES[1] and getattr(self, "desde", None) is not None:
            self.atualizar_excecoes()

    # --------------------------------------------------------------
    # Montagem
    # --------------------------------------------------------------
    def _montar_contas(self):
        cartao = Cartao(self.secoes["Contas"], pad=0)
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
        cartao = Cartao(self.secoes["Contas"], pad=0)
        cartao.pack(fill="both", expand=True, padx=px(MARGEM),
                    pady=(0, px(MARGEM)))
        m = cartao.miolo
        m.pack_configure(padx=px(1), pady=px(8))
        barra = tk.Frame(m, bg=COR["superficie"])
        barra.pack(fill="x", padx=px(19), pady=(px(6), px(12)))
        titulo_cartao(barra, "Atividade").pack(side="left")
        campo = Campo(barra, largura=300, icone=ICONE["busca"],
                      dica_vazio="Filtrar por usuário, ação ou detalhe",
                      maximo=MAXIMO_BUSCA)
        campo.pack(side="left", padx=(px(16), 0))
        self.busca = campo.entrada
        self.busca.bind("<KeyRelease>", lambda e: self._mostrar_eventos())
        quadro, self.historico = tabela_eventos(m, (150, 110, 190, 420), altura=6)
        quadro.pack(fill="both", expand=True, padx=px(12))

    def _montar_excecoes(self):
        """V4: filtros, tabela e "Exportar CSV"."""
        cartao = Cartao(self.secoes["Exceções"], pad=0)
        cartao.pack(fill="both", expand=True, padx=px(MARGEM),
                    pady=(0, px(MARGEM)))
        m = cartao.miolo
        m.pack_configure(padx=px(1), pady=px(8))
        barra = tk.Frame(m, bg=COR["superficie"])
        barra.pack(fill="x", padx=px(19), pady=(px(6), px(10)))
        titulo_cartao(barra, "Exceções do período").pack(side="left")
        Botao(barra, "Exportar CSV", self.exportar_excecoes, "secundario",
              icone=ICONE["baixar"]).pack(side="right")
        filtros = tk.Frame(m, bg=COR["superficie"])
        filtros.pack(fill="x", padx=px(19), pady=(0, px(10)))
        filtros.columnconfigure((0, 1), weight=2, uniform="d")
        filtros.columnconfigure((2, 3), weight=3, uniform="o")
        hoje = self.app.relogio().date()

        def grupo(coluna, texto, **opcoes):
            g, campo = campo_rotulado(filtros, texto, **opcoes)
            g.grid(row=0, column=coluna, sticky="ew",
                   padx=(0, px(12) if coluna < 3 else 0))
            return campo.entrada

        self.desde = grupo(0, "De", seletor="data", relogio=self.app.relogio,
                           ao_escolher=self.atualizar_excecoes)
        self.ate = grupo(1, "Até", seletor="data", relogio=self.app.relogio,
                         ao_escolher=self.atualizar_excecoes)
        self.tipo_excecao = grupo(2, "Tipo",
                                  opcoes=(excecoes.TODOS, *excecoes.TIPOS))
        self.autorizou = grupo(3, "Quem autorizou", opcoes=(excecoes.TODOS,))
        for caixa, valor in ((self.desde, hoje.replace(day=1)),
                             (self.ate, hoje)):
            caixa.insert(0, valor.strftime(FORMATO_DIA))
            caixa.bind("<Return>", lambda e: (self.atualizar_excecoes(),
                                              "break")[1])
        for combo in (self.tipo_excecao, self.autorizou):
            combo.set(excecoes.TODOS)
            combo.bind("<<ComboboxSelected>>",
                       lambda e: self.mostrar_excecoes())
        self.faixa_excecoes = Aviso(m)
        rodape = tk.Frame(m, bg=COR["superficie"])
        rodape.pack(side="bottom", fill="x", padx=px(19), pady=(px(8), px(2)))
        self.lbl_excecoes = tk.Label(rodape, text="", font=FONTE["dica"],
                                     bg=COR["superficie"], fg=COR["texto_3"])
        self.lbl_excecoes.pack(side="left")
        quadro, self.tabela_excecoes = tabela(m, COLUNAS_EXCECOES)
        quadro.pack(fill="both", expand=True, padx=px(12))
        self.quadro_excecoes = quadro

    def _periodo(self):
        """(desde, ate) dos campos, ou None com o erro na faixa."""
        try:
            desde = datetime.strptime(self.desde.get().strip(),
                                      FORMATO_DIA).date()
            ate = datetime.strptime(self.ate.get().strip(), FORMATO_DIA).date()
        except ValueError:
            self._erro_excecoes("Data inválida. Use o formato dd/mm/aaaa.")
            return None
        if ate < desde:
            self._erro_excecoes("A data final não pode ser anterior à inicial.")
            return None
        self.faixa_excecoes.pack_forget()
        return desde, ate

    def _erro_excecoes(self, texto):
        self.faixa_excecoes.mostrar("erro", texto)
        self.faixa_excecoes.pack(fill="x", padx=px(19), pady=(0, px(10)),
                                 before=self.quadro_excecoes)

    def atualizar_excecoes(self):
        """Relê do banco as exceções do período (os outros filtros valem
        na hora, sem reler)."""
        periodo = self._periodo()
        if periodo is None:
            return
        ok, eventos = self.app.tentar(self.app.banco.listar_excecoes,
                                      *periodo, autor=self.app.autor)
        if not ok:
            return
        self.excecoes = [excecoes.ler_excecao(e) for e in eventos]
        quem = self.autorizou.get()
        opcoes = (excecoes.TODOS, *excecoes.quem_autorizou(self.excecoes))
        self.autorizou.configure(values=opcoes)
        if quem not in opcoes:
            self.autorizou.set(excecoes.TODOS)
        self.mostrar_excecoes()

    def mostrar_excecoes(self):
        linhas = excecoes.filtrar(self.excecoes, self.tipo_excecao.get(),
                                  self.autorizou.get())
        tab = self.tabela_excecoes
        tab.delete(*tab.get_children())
        for i, l in enumerate(linhas):
            inserir_linha(tab, i, (l["quando"], ", ".join(l["tipos"]),
                                   l["pessoa"], l["autorizou"], l["operava"],
                                   l["justificativa"]))
        self.lbl_excecoes.config(
            text=plural(len(linhas), "exceção", "exceções") + " no período"
            + ("" if len(linhas) == len(self.excecoes)
               else f" (de {len(self.excecoes)}, com os filtros)"))
        return linhas

    def exportar_excecoes(self):
        """CSV do que a tabela mostra (período e filtros), como no Painel."""
        periodo = self._periodo()
        if periodo is None:
            return
        desde, ate = periodo
        caminho = self.app.perguntar(
            mensagens.salvar_como, "Exportar exceções",
            f"excecoes-{desde:%Y-%m-%d}-a-{ate:%Y-%m-%d}.csv")
        if not caminho:
            return
        ok, quantas = self.app.tentar(
            backup.exportar_excecoes_csv, self.app.banco, caminho, desde, ate,
            self.app.autor, self.tipo_excecao.get(), self.autorizou.get())
        if ok:
            mensagens.info("Exportar exceções",
                           f"{plural(quantas, 'exceção exportada', 'exceções exportadas')}"
                           f" para:\n{caminho}")

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
        if self.seletor.ativa == SECOES[1]:
            self.atualizar_excecoes()

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
        """Abre o diálogo "Redefinir senha" do usuário selecionado; devolve
        o diálogo (ou None, sem seleção)."""
        alvo = self._selecionado()
        if alvo is None:
            return None
        self.dialogo = DialogoRedefinirSenha(self, alvo)
        return self.dialogo


class DialogoRedefinirSenha(Dialogo):
    """Nova senha (2x) para outro usuário: o administrador a passa para
    ele, que é obrigado a trocá-la no próximo login (RN39). Libera o login
    travado. A senha não pode ser igual ao login dele."""

    def __init__(self, aba, alvo):
        self.aba, self.alvo = aba, alvo
        app = aba.app
        super().__init__(app.janela, "Redefinir senha",
                         f"Senha provisória para {alvo['login']}, com pelo "
                         f"menos {SENHA_MINIMA} caracteres. No próximo login "
                         "ele escolhe uma senha só dele.", largura=360,
                         ao_usar=app.registrar_uso)
        self.senha = self._campo("Nova senha")
        self.confirmacao = self._campo("Confirmar a nova senha")
        self.faixa = Aviso(self.miolo)
        self.adicionar_botao("Redefinir senha", self.salvar, "primario")
        self.adicionar_botao("Cancelar", self.fechar)
        self.abrir(confirmar=self.salvar, foco=self.senha)

    def _campo(self, texto):
        grupo, campo = campo_rotulado(self.miolo, texto, senha=True)
        grupo.pack(fill="x", pady=(0, px(14)))
        return campo.entrada

    def salvar(self):
        app = self.aba.app
        senha = self.senha.get()
        ok, msg = validar_senha(senha, self.confirmacao.get(),
                                self.alvo["login"])
        if not ok:
            self.faixa.mostrar("erro", msg)
            self.faixa.pack(fill="x", pady=(px(2), 0))
            return
        ok, _ = app.tentar(app.banco.definir_senha, self.alvo["id"],
                           gerar_hash(senha), autor=app.autor)
        if not ok:
            return
        self.fechar()
        self.aba.atualizar()
        mensagens.info("Usuários",
                       f"Senha de {self.alvo['login']} redefinida. No "
                       "próximo login ele define uma senha nova. Se o login "
                       "estava travado por tentativas erradas, já foi "
                       "liberado.")


class DialogoUsuario(Dialogo):
    """Diálogo "Novo usuário": nome, login, senha (2x) e perfil."""

    def __init__(self, aba):
        self.aba = aba
        app = aba.app
        super().__init__(app.janela, "Novo usuário",
                         "A senha daqui é provisória: no primeiro login o "
                         "usuário escolhe uma senha só dele.",
                         largura=440, ao_usar=app.registrar_uso)
        form = self.miolo
        form.columnconfigure((0, 1), weight=1, uniform="u")

        def campo(texto, linha, coluna, juntas=1, apoio="", **opcoes):
            grupo, c = campo_rotulado(form, texto, apoio, **opcoes)
            grupo.grid(row=linha, column=coluna, columnspan=juntas, sticky="ew",
                       pady=(0, px(14)),
                       padx=(0, px(10)) if coluna == 0 and juntas == 1 else 0)
            return c.entrada

        self.nome = campo("Nome completo", 0, 0, juntas=2, maximo=MAXIMO_NOME)
        self.login = campo("Usuário", 1, 0, juntas=2, apoio="ex.: maria.souza",
                           maximo=MAXIMO_LOGIN)
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
        mensagens.info("Usuários", f"Usuário {login} criado. Ele já pode "
                                   "entrar e vai definir a senha dele no "
                                   "primeiro login.")
