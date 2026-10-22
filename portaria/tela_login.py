"""
Tela de login, dividida em duas: à esquerda o painel vermelho UNA (o único
lugar onde o vermelho ocupa área grande) com a cancela e o relógio da
guarita; à direita o formulário. No primeiro uso (banco sem usuários) vira
"Primeiro acesso", que cria o administrador — não existe senha padrão.

O login passa por usuarios.entrar(): as tentativas erradas ficam no banco
e o bloqueio continua valendo mesmo fechando e abrindo o programa.

O formulário da direita muda conforme o momento (o painel fica):
- Entrar (o normal);
- Primeiro acesso: cria o administrador;
- Defina sua senha (RN39): quem entrou com a senha que o administrador
  passou (conta nova ou senha redefinida) escolhe a dele antes de
  qualquer outra tela;
- Esqueci a senha (RN38): usuário + código de recuperação + senha nova.

No primeiro acesso, depois de criar o administrador, aparecem os 8
códigos de recuperação dele (tela_recuperacao.py), uma vez só.
"""

import tkinter as tk
from datetime import datetime

from .componentes import (Aviso, Botao, Campo, data_por_extenso, link,
                          marca_cancela)
from .dados import ErroDados, log
from .tela_recuperacao import mostrar_codigos
from .estilo import COR, FONTE, px
from .usuarios import (SENHA_MINIMA, definir_senha_inicial, entrar,
                       gerar_codigos_recuperacao, gerar_hash, normalizar_login,
                       precisa_trocar_senha, recuperar_senha,
                       validar_novo_usuario)
from .validacao import MAXIMO_CODIGO, MAXIMO_LOGIN, MAXIMO_NOME

SEGUNDOS_RELOGIO = 15


class TelaLogin:
    def __init__(self, pai, banco, ao_entrar, relogio=None, aviso=""):
        """
        ao_entrar(usuario) é chamado quando o login dá certo.
        relogio: função que devolve o datetime de agora (testes).
        aviso: faixa informativa ao abrir (ex.: sessão encerrada).
        """
        self.banco = banco
        self.ao_entrar = ao_entrar
        self.relogio = relogio or datetime.now
        self.campos = []                 # caixas de texto, na ordem da tela
        self.primeiro_acesso = False
        self.formulario = None           # "entrar", "primeiro_acesso"...
        self._usuario_pendente = None    # RN39: entrou, falta a senha dele
        self._timer = None

        self._montar_painel(pai)
        lado = tk.Frame(pai, bg=COR["superficie"])
        lado.pack(side="left", fill="both", expand=True)
        self.miolo = tk.Frame(lado, bg=COR["superficie"])
        self.miolo.place(relx=0.5, rely=0.5, anchor="center", width=px(360))

        try:
            self.primeiro_acesso = banco is not None and not banco.tem_usuarios()
        except ErroDados:
            banco = None
        if banco is None:
            self._titulo("Banco de dados indisponível",
                         "Feche o programa e confira se a pasta permite gravar. "
                         "Se continuar, avise o administrador.")
            return

        if self.primeiro_acesso:
            self.mostrar_primeiro_acesso()
        else:
            self.mostrar_entrar(aviso)

    # --------------------------------------------------------------
    # Formulários (o painel da esquerda continua)
    # --------------------------------------------------------------
    def _novo_formulario(self, nome, titulo, subtitulo):
        """Apaga o formulário anterior e começa outro."""
        for w in self.miolo.winfo_children():
            w.destroy()
        self.campos = []
        self.formulario = nome
        self._titulo(titulo, subtitulo)

    def _fechar_formulario(self, texto, acao, dica="", ligacao=None):
        """Faixa de erro (escondida), o botão principal, a dica de baixo
        (com um link opcional: (texto, comando)) e o Enter em qualquer
        campo (cada campo fica no seu Frame)."""
        self.faixa = Aviso(self.miolo)
        self.lbl_erro = self.faixa.lbl
        self.btn_acao = Botao(self.miolo, texto, acao, "primario", altura=40,
                              dica_tecla="Enter")
        self.btn_acao.pack(fill="x")
        self.link = None
        if dica or ligacao:
            rodape = tk.Frame(self.miolo, bg=COR["superficie"])
            rodape.pack(fill="x", pady=(px(16), 0))
            if ligacao:
                self.link = link(rodape, *ligacao)
                self.link.pack(side="left", padx=(0, px(10)))
            if dica:
                tk.Label(rodape, text=dica, font=FONTE["dica"],
                         bg=COR["superficie"], fg=COR["texto_3"],
                         justify="left", wraplength=px(260 if ligacao else 360)
                         ).pack(side="left", anchor="w")
        for caixa_texto in self.campos:
            caixa_texto.bind("<Return>", lambda e: (acao(), "break")[1])
            caixa_texto.bind("<KP_Enter>", lambda e: (acao(), "break")[1])
        self.campos[0].focus_set()

    def mostrar_primeiro_acesso(self):
        self._novo_formulario("primeiro_acesso", "Primeiro acesso",
                              "Crie o usuário administrador do sistema. "
                              "Ele cadastra os porteiros depois.")
        self.campo_nome = self._campo("Nome completo", maximo=MAXIMO_NOME)
        self.campo_login = self._campo("Usuário", "ex.: maria.souza",
                                       maximo=MAXIMO_LOGIN)
        self.campo_senha = self._campo(
            "Senha", f"mínimo {SENHA_MINIMA} caracteres", senha=True)
        self.campo_confirmacao = self._campo("Confirmar senha", senha=True)
        self._fechar_formulario("Criar administrador e entrar",
                                self.criar_administrador)

    def mostrar_entrar(self, aviso=""):
        self._novo_formulario("entrar", "Entrar",
                              "Use o usuário e a senha que o administrador "
                              "cadastrou para você.")
        self.campo_login = self._campo("Usuário", maximo=MAXIMO_LOGIN)
        self.campo_senha = self._campo("Senha", senha=True)
        self._fechar_formulario("Entrar", self.entrar,
                                "ou peça ao administrador para redefinir.",
                                ("Esqueci a senha", self.mostrar_esqueci))
        if aviso:
            self._mostrar("info", aviso)

    def mostrar_esqueci(self):
        """RN38: troca a senha com um código de recuperação."""
        login = self.campo_login.get() if self.formulario == "entrar" else ""
        self._novo_formulario(
            "esqueci", "Esqueci a senha",
            "Use um dos códigos de recuperação que o sistema mostrou ao "
            "criar o administrador. Cada código vale uma vez.")
        self.campo_login = self._campo("Usuário", maximo=MAXIMO_LOGIN)
        self.campo_login.insert(0, login)
        self.campo_codigo = self._campo("Código de recuperação", "ex.: K7QM-2F9X",
                                        maximo=MAXIMO_CODIGO)
        self.campo_nova = self._campo(
            "Nova senha", f"mínimo {SENHA_MINIMA} caracteres", senha=True)
        self.campo_confirmacao = self._campo("Confirmar a nova senha",
                                             senha=True)
        self._fechar_formulario("Trocar a senha", self.recuperar,
                                "Sem código? Peça a outro administrador.",
                                ("Voltar", self.mostrar_entrar))
        if login:
            self.campo_codigo.focus_set()

    def mostrar_definir_senha(self, usuario):
        """RN39: "Defina sua senha" antes de qualquer tela."""
        self._usuario_pendente = usuario
        primeiro = usuario["nome"].split()[0] if usuario["nome"] else ""
        self._novo_formulario(
            "definir_senha", "Defina sua senha",
            f"Olá, {primeiro}. Você entrou com a senha que o administrador "
            "passou. Escolha uma senha só sua para continuar.")
        self.campo_nova = self._campo(
            "Nova senha", f"mínimo {SENHA_MINIMA} caracteres", senha=True)
        self.campo_confirmacao = self._campo("Confirmar a nova senha",
                                             senha=True)
        self._fechar_formulario("Salvar senha e entrar", self.definir_senha,
                                "Não use o login nem sequências. A senha "
                                "provisória deixa de valer.")

    # --------------------------------------------------------------
    # Montagem
    # --------------------------------------------------------------
    def _montar_painel(self, pai):
        marca = COR["painel_login"]
        branco = COR["texto_sobre_marca"]
        painel = tk.Frame(pai, bg=marca, width=px(470))
        painel.pack(side="left", fill="y")
        painel.pack_propagate(False)
        dentro = tk.Frame(painel, bg=marca)
        dentro.pack(fill="both", expand=True, padx=px(48), pady=px(48))
        marca_cancela(dentro, marca, tamanho=56, cor=branco,
                      traco=marca).pack(anchor="w")
        tk.Label(dentro, text="Portaria", font=FONTE["titulo_grande"], bg=marca,
                 fg=branco).pack(anchor="w", pady=(px(20), 0))
        tk.Label(dentro, text="Controle de entrada e saída\ndo campus da "
                              "universidade", font=FONTE["corpo_grande"],
                 bg=marca, fg=branco, justify="left").pack(anchor="w",
                                                           pady=(px(4), 0))
        relogio = tk.Frame(dentro, bg=marca)
        relogio.pack(side="bottom", anchor="w")
        self.lbl_hora = tk.Label(relogio, font=FONTE["relogio"], bg=marca,
                                 fg=branco)
        self.lbl_hora.pack(anchor="w")
        self.lbl_data = tk.Label(relogio, font=FONTE["corpo_grande"], bg=marca,
                                 fg=branco)
        self.lbl_data.pack(anchor="w")
        self._atualizar_relogio()
        painel.bind("<Destroy>", self._parar_relogio)

    def _atualizar_relogio(self):
        agora = self.relogio()
        self.lbl_hora.config(text=agora.strftime("%H:%M"))
        self.lbl_data.config(text=data_por_extenso(agora))
        self._timer = self.lbl_hora.after(SEGUNDOS_RELOGIO * 1000,
                                          self._atualizar_relogio)

    def _parar_relogio(self, event=None):
        if self._timer:
            try:
                self.lbl_hora.after_cancel(self._timer)
            except tk.TclError:
                pass
            self._timer = None

    def _titulo(self, titulo, subtitulo):
        fundo = COR["superficie"]
        tk.Label(self.miolo, text=titulo, font=FONTE["titulo_pagina"], bg=fundo,
                 fg=COR["texto"]).pack(anchor="w")
        tk.Label(self.miolo, text=subtitulo, font=FONTE["corpo"], bg=fundo,
                 fg=COR["texto_2"], wraplength=px(360), justify="left"
                 ).pack(anchor="w", pady=(px(4), px(24)))

    def _campo(self, texto, apoio="", senha=False, maximo=None):
        # RNF02: a senha aparece como •••• enquanto é digitada
        fundo = COR["superficie"]
        linha = tk.Frame(self.miolo, bg=fundo)
        linha.pack(anchor="w", pady=(0, px(4)))
        tk.Label(linha, text=texto, font=FONTE["rotulo"], bg=fundo,
                 fg=COR["texto"]).pack(side="left")
        if apoio:
            tk.Label(linha, text=apoio, font=FONTE["dica"], bg=fundo,
                     fg=COR["texto_3"]).pack(side="left", padx=(px(8), 0))
        campo = Campo(self.miolo, senha=senha, maximo=maximo)
        campo.pack(fill="x", pady=(0, px(16)))
        self.campos.append(campo.entrada)
        return campo.entrada

    def _mostrar(self, tipo, texto):
        self.faixa.mostrar(tipo, texto)
        if not self.faixa.winfo_manager():
            self.faixa.pack(fill="x", pady=(0, px(16)), before=self.btn_acao)

    def erro(self, texto):
        self._mostrar("erro", texto)

    # --------------------------------------------------------------
    # Ações
    # --------------------------------------------------------------
    def entrar(self):
        try:
            usuario, motivo = entrar(self.banco, self.campo_login.get(),
                                     self.campo_senha.get(), agora=self.relogio())
        except ErroDados as e:
            self.erro(str(e))
            return
        if usuario is None:
            if self.campo_login.get().strip():
                self.campo_senha.delete(0, tk.END)
            self.erro(motivo)
            return
        if precisa_trocar_senha(usuario):
            self.mostrar_definir_senha(usuario)
            return
        self.ao_entrar(usuario)

    def recuperar(self):
        """RN38: código certo troca a senha (e é queimado); errado conta
        como tentativa no bloqueio progressivo do login."""
        login = self.campo_login.get()
        try:
            ok, msg = recuperar_senha(self.banco, login,
                                      self.campo_codigo.get(),
                                      self.campo_nova.get(),
                                      self.campo_confirmacao.get(),
                                      agora=self.relogio())
        except ErroDados as e:
            self.erro(str(e))
            return
        if not ok:
            for caixa in (self.campo_codigo, self.campo_nova,
                          self.campo_confirmacao):
                caixa.delete(0, tk.END)
            self.campo_codigo.focus_set()
            self.erro(msg)
            return
        self.mostrar_entrar()
        self.campo_login.insert(0, normalizar_login(login))
        self.campo_senha.focus_set()
        self._mostrar("sucesso", msg)

    def definir_senha(self):
        """RN39: grava a senha escolhida e entra."""
        usuario = self._usuario_pendente
        try:
            ok, msg = definir_senha_inicial(self.banco, usuario["login"],
                                            self.campo_nova.get(),
                                            self.campo_confirmacao.get())
        except ErroDados as e:
            self.erro(str(e))
            return
        if not ok:
            for caixa in (self.campo_nova, self.campo_confirmacao):
                caixa.delete(0, tk.END)
            self.campo_nova.focus_set()
            self.erro(msg)
            return
        self._usuario_pendente = None
        self.ao_entrar(dict(usuario, trocar_senha=False))

    def criar_administrador(self):
        nome = " ".join(self.campo_nome.get().split())
        login = normalizar_login(self.campo_login.get())
        senha = self.campo_senha.get()
        ok, msg = validar_novo_usuario(nome, login, senha,
                                       self.campo_confirmacao.get(), "admin",
                                       logins_existentes=set())
        if not ok:
            self.erro(msg)
            return
        try:
            self.banco.criar_usuario(nome, login, "admin", gerar_hash(senha))
            usuario, motivo = entrar(self.banco, login, senha,
                                     agora=self.relogio())
        except ErroDados as e:
            self.erro(str(e))
            return
        if usuario is None:
            self.erro(motivo)
            return
        self._mostrar_codigos_novos(usuario)
        self.ao_entrar(usuario)

    def _mostrar_codigos_novos(self, usuario):
        """RN38: os 8 códigos de recuperação do administrador recém-criado,
        mostrados uma vez (com "Guardei em lugar seguro")."""
        try:
            codigos = gerar_codigos_recuperacao(self.banco, usuario)
        except ErroDados as e:          # sem os códigos ainda dá para entrar
            log.error("Códigos de recuperação não gerados: %s",
                      e.detalhe or e)
            return
        mostrar_codigos(self.miolo.winfo_toplevel(), codigos,
                        usuario["login"], self.relogio)
