"""
Janela principal (Tkinter): moldura com a barra lateral, sessão do usuário
(login, saída, troca de senha e saída automática por inatividade) e as
páginas. Cada página mora no seu módulo: tela_cadastro.py ("Entrada e
saída"), tela_pessoas.py, tela_bloqueios.py, tela_dashboard.py ("Painel")
e tela_usuarios.py (só administrador); o login fica em tela_login.py, a
janela "Corrigir registro" em tela_edicao.py e "Trocar minha senha" em
tela_senha.py.

As regras ficam em validacao.py e usuarios.py, o banco de dados em dados.py
e os números em consultas.py — as telas só montam widgets e reagem aos
botões.

CONTRATO DO APP — o que as telas podem usar da AppPortaria:
    app.janela                   janela principal (Tk)
    app.banco                    banco de dados (dados.Banco)
    app.usuario                  quem está logado (dicionário)
    app.autor                    login de quem está logado (para o histórico)
    app.registros                visitas do movimento: as de hoje e todas as
                                 que ainda não têm saída (banco.listar_movimento)
    app.tentar(operacao, ...)    roda no banco; (True, resultado) ou avisa
                                 o erro e devolve (False, None). Sem sessão
                                 (usuário saiu ou expirou), nem roda
    app.gravar(operacao, ...)    grava em nome do usuário e recarrega a lista
    app.perguntar(caixa, ...)    abre uma caixa que trava a tela (Sim/Não,
                                 senha, "Salvar como") e devolve a resposta,
                                 ou None se a sessão acabou com ela aberta
    app.recarregar_registros()   relê o movimento do banco
    app.atualizar_tabela()       relê o movimento e redesenha a Entrada e
                                 saída, o Painel e os contadores do menu
    app.avisar(texto, desfazer=None)  aviso que some sozinho no Movimento
    app.preencher_pessoa(pessoa) abre a Entrada e saída com a pessoa preenchida
    app.ir_para(pagina)          mostra uma página (ex.: app.aba_bloqueios)
    app.exibir_cpf(cpf)          CPF como a tabela mostra: completo para o
                                 administrador, mascarado para o porteiro
    app.registrar_uso()          conta como uso (sessão por inatividade)
Nenhuma tela mexe em atributo com "_" do app.

Convenção das páginas: class AbaX com __init__(self, aba, app) e atualizar().
A Entrada e saída é montada no login; as outras páginas na primeira vez que
são abertas ou usadas (app.tela_pessoas etc. — ver PAGINAS_SOB_DEMANDA).
"""

import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

from . import backup, dados, mensagens
from .componentes import Avatar, BotaoIcone, ItemMenu, marca_cancela
from .estilo import (COR, FONTE, ICONE, LARGURA_LATERAL, aplicar_tema,
                     carregar_fontes, px)
from .tela_bloqueios import AbaBloqueios
from .tela_cadastro import AbaCadastro
from .tela_dashboard import AbaDashboard
from .tela_login import TelaLogin
from .tela_pessoas import AbaPessoas
from .tela_senha import JanelaSenha
from .tela_usuarios import AbaUsuarios
from .usuarios import (MINUTOS_INATIVIDADE, PERFIS, SESSAO_ENCERRADA, eh_admin,
                       pode_gerenciar_usuarios)
from .validacao import formatar_cpf, mascarar_cpf

TECLAS_DA_SESSAO = ("<Return>", "<KP_Enter>", "<F2>")
EVENTOS_DE_USO = ("<KeyPress>", "<ButtonPress>", "<Motion>", "<MouseWheel>")
SEGUNDOS_ENTRE_CONFERENCIAS = 30      # de quanto em quanto tempo olha a inatividade
AVISO_INATIVIDADE = (f"Sua sessão foi encerrada depois de {MINUTOS_INATIVIDADE} "
                     "minutos sem uso. Entre de novo para continuar.")

# Nomes da Entrada e saída que continuam valendo como app.<nome> (os testes
# e a versão anterior usavam assim): app.cpf é o mesmo que
# app.tela_cadastro.cpf.
NOMES_DO_CADASTRO = {
    "nome", "cpf", "var_cpf", "celular", "var_placa", "tipo", "entrada",
    "saida", "tabela", "busca", "lbl_pessoa", "lbl_dica_placa",
    "lbl_placa_status", "lbl_aviso", "btn_desfazer", "btn_excluir",
    "campo_saida_rapida", "lbl_status", "janela_edicao", "cadastrar", "limpar",
    "registrar_saida", "registrar_saida_da_linha", "saida_rapida",
    "desfazer_saida", "editar_selecionado", "excluir_selecionado",
}


# Páginas montadas só na primeira vez que são abertas (ou usadas): o login
# fica rápido e a janela só tem os widgets de que alguém precisou.
# nome do atributo -> (página onde ela mora, classe)
PAGINAS_SOB_DEMANDA = {
    "tela_pessoas": ("aba_pessoas", AbaPessoas),
    "tela_bloqueios": ("aba_bloqueios", AbaBloqueios),
    "tela_dashboard": ("aba_dash", AbaDashboard),
    "tela_usuarios": ("aba_usuarios", AbaUsuarios),
}


def ajustar_ao_monitor(janela):
    """Tela pequena (ex.: notebook 1366x768 a 125%): abre maximizada."""
    if (janela.winfo_screenwidth() < px(1200)
            or janela.winfo_screenheight() < px(800)):
        try:
            janela.state("zoomed")
        except tk.TclError:
            pass


class AppPortaria:
    def __init__(self, caminho_banco, janela=None, json_antigo=None,
                 usuario=None, relogio=None):
        """
        json_antigo: arquivo da v1; se existir, é importado para o banco.
        usuario: entra direto com esse usuário (usado nos testes); sem ele,
        a janela abre na tela de login.
        relogio: função que devolve o datetime de agora (os testes trocam
        para simular o tempo passando: login bloqueado, inatividade).
        """
        self.caminho_banco = caminho_banco
        self.json_antigo = json_antigo
        self.relogio = relogio or datetime.now
        self.banco = None
        self.usuario = None                       # quem está logado
        self._sessao = 0                          # muda a cada entrar/sair
        self.corpo = None                        # login ou páginas
        self.registros = []                       # movimento mostrado na tela
        self.tela_cadastro = None                 # as outras: sob demanda
        self.janela_senha = None
        self.itens_menu = {}
        self.avisos_admin = []      # migração do banco e backup: só o admin vê
        self.ultimo_uso = self.relogio()
        self._timer_inatividade = None

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
        # etc. são repassados para a Entrada e saída (ver NOMES_DO_CADASTRO).
        # app.tela_pessoas etc. ainda não montadas são montadas agora.
        if nome in PAGINAS_SOB_DEMANDA and "abas" in self.__dict__:
            return self._montar_pagina(nome)
        cadastro = self.__dict__.get("tela_cadastro")
        if cadastro is not None and nome in NOMES_DO_CADASTRO:
            return getattr(cadastro, nome)
        raise AttributeError(f"AppPortaria não tem o atributo '{nome}'")

    @property
    def cards(self):
        """Números do Painel: chave -> (rótulo do valor, rótulo de apoio)."""
        return self.tela_dashboard.cards if self.usuario else {}

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
        self.avisos_admin = list(self.banco.avisos)
        try:   # uma cópia por dia, guardando as 30 mais recentes
            backup.backup_diario(self.caminho_banco)
        except (dados.ErroDados, OSError) as e:
            dados.log.error("Backup diário não realizado: %s",
                            getattr(e, "detalhe", "") or e)
            self.avisos_admin.append("O backup diário do banco não foi feito "
                                     f"hoje.\n{e}")

    def mostrar_avisos(self):
        """Avisos da atualização do banco e do backup, uma vez, ao
        administrador que entrar."""
        if self.avisos_admin and eh_admin(self.usuario):
            mensagens.aviso("Avisos do sistema", "\n\n".join(self.avisos_admin))
            self.avisos_admin = []

    def _erro_inesperado(self, tipo, erro, rastro):
        """Erro de programação numa ação da tela: o detalhe vai para o log
        (portaria.log), o usuário vê uma mensagem simples."""
        dados.log.error("Erro inesperado na tela", exc_info=(tipo, erro, rastro))
        mensagens.erro("Erro inesperado",
                       "Algo deu errado nesta ação e ela não foi concluída.\n"
                       "Tente de novo; se continuar, avise o administrador.")

    @property
    def autor(self):
        """Login de quem está logado; vai para o histórico de cada ação."""
        return self.usuario["login"] if self.usuario else None

    def tentar(self, operacao, *args, **kwargs):
        """Executa no banco; devolve (True, resultado) ou avisa e (False, None).
        Sem ninguém logado (a sessão acabou) não executa nada."""
        if self.usuario is None:
            self._avisar_sessao_encerrada()
            return False, None
        try:
            return True, operacao(*args, **kwargs)
        except dados.ErroDados as e:
            if e.detalhe:      # o técnico vai para o log, não para a tela
                dados.log.warning("%s | detalhe: %s", str(e).splitlines()[0],
                                  e.detalhe)
            mensagens.erro("Erro", str(e))
            return False, None

    def perguntar(self, caixa, *args, **kwargs):
        """
        Abre uma caixa que trava a tela (mensagens.confirmar, pedir_senha,
        salvar_como) e devolve a resposta. O tempo de inatividade continua
        correndo com ela aberta: se a sessão acabou (ou mudou) enquanto
        isso, avisa e devolve None, e quem chamou não faz nada.
        """
        sessao = self._sessao
        resposta = caixa(*args, **kwargs)
        if self._sessao != sessao or self.usuario is None:
            self._avisar_sessao_encerrada()
            return None
        return resposta

    @staticmethod
    def _avisar_sessao_encerrada():
        mensagens.aviso("Sessão encerrada", SESSAO_ENCERRADA)

    def gravar(self, operacao, *args):
        """Grava em nome do usuário logado e recarrega a lista; False se falhar."""
        ok, _ = self.tentar(operacao, *args, autor=self.autor)
        if ok:
            self.recarregar_registros()
        return ok

    def recarregar_registros(self):
        """Relê o movimento (hoje + quem está no campus); se falhar, mantém
        a lista que já estava."""
        ok, registros = self.tentar(self.banco.listar_movimento,
                                    self.relogio().date())
        if ok:
            self.registros = registros
        return ok

    def atualizar_tabela(self):
        """Os registros mudaram: relê e redesenha o que depende deles."""
        self.recarregar_registros()
        self.tela_cadastro.atualizar_tabela()
        if "tela_dashboard" in self.__dict__:       # só se já foi montado
            self.tela_dashboard.atualizar()
        self.atualizar_contadores()

    def atualizar_contadores(self):
        """Números ao lado de Pessoas e Bloqueios na barra lateral."""
        ok, n = self.tentar(self.banco.contadores)
        if not ok or not self.itens_menu:
            return
        self.itens_menu[str(self.aba_pessoas)].definir_contador(
            str(n["pessoas"]) if n["pessoas"] else "")
        self.itens_menu[str(self.aba_bloqueios)].definir_contador(
            str(n["bloqueios"]) if n["bloqueios"] else "")

    def avisar(self, texto, desfazer=None):
        self.tela_cadastro.avisar(texto, desfazer)

    def preencher_pessoa(self, pessoa):
        """Começa uma nova entrada para a pessoa (usado pela página Pessoas)."""
        self.ir_para(self.aba_cad)
        self.tela_cadastro.preencher_pessoa(pessoa)

    def exibir_cpf(self, cpf):
        """Privacidade: nas tabelas o porteiro vê o CPF mascarado."""
        return formatar_cpf(cpf) if eh_admin(self.usuario) else mascarar_cpf(cpf)

    # --------------------------------------------------------------
    # Sessão: login, saída, troca de senha e inatividade
    # --------------------------------------------------------------
    def _trocar_corpo(self):
        if self.corpo is not None:
            self.corpo.destroy()
        self.corpo = tk.Frame(self.janela, bg=COR["fundo"])
        self.corpo.pack(side="left", fill="both", expand=True)

    def mostrar_login(self, aviso=""):
        self._trocar_corpo()
        self.tela_login = TelaLogin(self.corpo, self.banco, self.entrar,
                                    relogio=lambda: self.relogio(), aviso=aviso)

    def entrar(self, usuario):
        self.usuario = usuario
        self._sessao += 1
        self.tentar(self.banco.registrar_evento, usuario["login"],
                    "Entrou no sistema")
        self.avatar.mostrar(usuario["nome"])
        self.lbl_usuario.config(text=usuario["nome"])
        self.lbl_perfil.config(text=PERFIS[usuario["perfil"]])
        self._trocar_corpo()
        self.lateral.pack(side="left", fill="y", before=self.corpo)
        self._montar_principal()
        self.registrar_uso()
        self._vigiar_inatividade()
        self.mostrar_avisos()

    def sair(self, inatividade=False):
        if self.usuario:
            self.tentar(self.banco.registrar_evento, self.autor,
                        "Sessão encerrada por inatividade" if inatividade
                        else "Saiu do sistema")
        self.usuario = None
        self._sessao += 1
        if self._timer_inatividade:
            self.janela.after_cancel(self._timer_inatividade)
            self._timer_inatividade = None
        self._fechar_janelas_da_sessao()
        for tecla in TECLAS_DA_SESSAO:
            self.janela.unbind(tecla)
        self.itens_menu = {}
        self.lateral.pack_forget()
        self.mostrar_login(AVISO_INATIVIDADE if inatividade else "")

    def _fechar_janelas_da_sessao(self):
        """Fecha as janelas próprias abertas (Corrigir, Trocar senha, Novo
        usuário, Exportar, Redefinir senha...), em qualquer nível. As caixas
        nativas do Windows não fecham por aqui: quem as abriu usa
        app.perguntar e confere a sessão quando elas voltam."""
        pendentes = list(self.janela.winfo_children())
        while pendentes:
            w = pendentes.pop()
            if isinstance(w, tk.Toplevel):
                w.destroy()
            else:
                pendentes.extend(w.winfo_children())

    def trocar_senha(self):
        """Menu do usuário → "Trocar minha senha"."""
        self.janela_senha = JanelaSenha(self)
        return self.janela_senha

    def registrar_uso(self, event=None):
        self.ultimo_uso = self.relogio()

    def conferir_inatividade(self):
        """Sem teclado/mouse por MINUTOS_INATIVIDADE: volta ao login.
        Devolve True se encerrou a sessão."""
        if self.usuario is None:
            return False
        if self.relogio() - self.ultimo_uso >= timedelta(minutes=MINUTOS_INATIVIDADE):
            self.sair(inatividade=True)
            return True
        return False

    def _ao_fechar(self, event):
        """Janela fechada: para de vigiar a inatividade."""
        if event.widget is self.janela and self._timer_inatividade:
            try:
                self.janela.after_cancel(self._timer_inatividade)
            except tk.TclError:
                pass
            self._timer_inatividade = None

    def _vigiar_inatividade(self):
        self._timer_inatividade = None
        if not self.conferir_inatividade() and self.usuario:
            self._timer_inatividade = self.janela.after(
                SEGUNDOS_ENTRE_CONFERENCIAS * 1000, self._vigiar_inatividade)

    # --------------------------------------------------------------
    # Montagem da janela, da barra lateral e das páginas
    # --------------------------------------------------------------
    def _montar_janela(self):
        janela = self.janela
        janela.title("Portaria da Universidade")
        janela.geometry(f"{px(1180)}x{px(760)}")
        janela.minsize(px(1000), px(640))
        janela.configure(bg=COR["fundo"])
        janela.report_callback_exception = self._erro_inesperado
        carregar_fontes(janela)
        aplicar_tema(janela)
        # qualquer tecla ou mouse dentro da janela conta como uso
        for evento in EVENTOS_DE_USO:
            janela.bind(evento, self.registrar_uso, add="+")
        janela.bind("<Destroy>", self._ao_fechar, add="+")
        self._montar_lateral()

    def _montar_lateral(self):
        """Barra lateral: marca, menu das páginas e quem está logado.
        Só aparece depois do login (pack em entrar, pack_forget em sair)."""
        fundo = COR["lateral"]
        self.lateral = tk.Frame(self.janela, bg=fundo, width=px(LARGURA_LATERAL))
        self.lateral.pack_propagate(False)
        tk.Frame(self.lateral, bg=COR["borda"], width=1).pack(side="right",
                                                              fill="y")
        marca = tk.Frame(self.lateral, bg=fundo)
        marca.pack(fill="x", padx=px(16), pady=(px(20), px(24)))
        marca_cancela(marca, fundo).pack(side="left")
        textos = tk.Frame(marca, bg=fundo)
        textos.pack(side="left", padx=(px(12), 0))
        tk.Label(textos, text="Portaria", font=FONTE["marca"], bg=fundo,
                 fg=COR["texto"]).pack(anchor="w")
        tk.Label(textos, text="Universidade", font=FONTE["dica"], bg=fundo,
                 fg=COR["texto_3"]).pack(anchor="w")

        self.menu = tk.Frame(self.lateral, bg=fundo)
        self.menu.pack(fill="x", padx=px(10))

        # Rodapé: quem está logado, menu do usuário e sair
        self.sessao = tk.Frame(self.lateral, bg=fundo)
        self.sessao.pack(side="bottom", fill="x", padx=(px(16), px(10)),
                         pady=px(14))
        tk.Frame(self.lateral, bg=COR["borda"], height=1).pack(
            side="bottom", fill="x", padx=px(16))
        self.avatar = Avatar(self.sessao, fundo)
        self.avatar.pack(side="left")
        quem = tk.Frame(self.sessao, bg=fundo)
        quem.pack(side="left", padx=(px(10), 0), fill="x", expand=True)
        self.lbl_usuario = tk.Label(quem, font=FONTE["corpo_semi"], bg=fundo,
                                    fg=COR["texto"], anchor="w")
        self.lbl_usuario.pack(anchor="w", fill="x")
        self.lbl_perfil = tk.Label(quem, font=FONTE["dica"], bg=fundo,
                                   fg=COR["texto_3"], anchor="w")
        self.lbl_perfil.pack(anchor="w")
        self.btn_sair = BotaoIcone(self.sessao, ICONE["sair"], self.sair, fundo,
                                   descricao="Sair")
        self.btn_sair.pack(side="right")
        self.btn_opcoes = BotaoIcone(self.sessao, ICONE["mais_opcoes"],
                                     self.abrir_menu_usuario, fundo,
                                     descricao="Opções da conta")
        self.btn_opcoes.pack(side="right")

        self.menu_usuario = tk.Menu(self.janela, tearoff=0, font=FONTE["corpo"],
                                    activebackground=COR["selecao"],
                                    activeforeground=COR["texto"])
        self.menu_usuario.add_command(label="Trocar minha senha",
                                      command=self.trocar_senha)
        self.menu_usuario.add_separator()
        self.menu_usuario.add_command(label="Sair", command=self.sair)
        for w in (self.avatar, quem, self.lbl_usuario, self.lbl_perfil):
            w.bind("<Button-1>", lambda e: self.abrir_menu_usuario())
            w.config(cursor="hand2")

    def abrir_menu_usuario(self):
        x = self.btn_opcoes.winfo_rootx()
        y = self.btn_opcoes.winfo_rooty() - px(70)
        try:
            self.menu_usuario.tk_popup(x, y)
        finally:
            self.menu_usuario.grab_release()

    def _nova_pagina(self, titulo, icone):
        aba = tk.Frame(self.abas, bg=COR["fundo"])
        self.abas.add(aba, text=titulo)
        item = ItemMenu(self.menu, titulo, ICONE[icone],
                        lambda: self.ir_para(aba))
        item.pack(fill="x")
        self.itens_menu[str(aba)] = item
        return aba

    def _montar_principal(self):
        """Páginas que aparecem depois do login (Notebook sem as abas: quem
        navega é a barra lateral)."""
        for item in self.menu.winfo_children():
            item.destroy()
        self.itens_menu = {}
        self.abas = ttk.Notebook(self.corpo, style="Paginas.TNotebook")
        self.abas.pack(fill="both", expand=True)
        self.aba_cad = self._nova_pagina("Entrada e saída", "entrada")
        self.aba_pessoas = self._nova_pagina("Pessoas", "pessoas")
        self.aba_bloqueios = self._nova_pagina("Bloqueios", "bloqueio")
        self.aba_dash = self._nova_pagina("Painel", "painel")
        self.aba_usuarios = None
        if pode_gerenciar_usuarios(self.usuario):
            self.aba_usuarios = self._nova_pagina("Usuários", "usuarios")
        for nome in PAGINAS_SOB_DEMANDA:       # as da sessão anterior saem
            self.__dict__.pop(nome, None)
        # a Entrada e saída é a página inicial: montada já
        self.tela_cadastro = AbaCadastro(self.aba_cad, self)

        # página -> nome da tela (abrir a página monta ou relê a tela)
        self._paginas = {str(getattr(self, aba)): nome for nome, (aba, _)
                         in PAGINAS_SOB_DEMANDA.items()
                         if getattr(self, aba) is not None}
        self._paginas[str(self.aba_cad)] = "tela_cadastro"

        # Enter registra a entrada (só na Entrada e saída; a busca ignora)
        self.janela.bind("<Return>", self.tela_cadastro.cadastrar)
        self.janela.bind("<KP_Enter>", self.tela_cadastro.cadastrar)
        self.janela.bind("<F2>", self.ir_para_saida_rapida)

        self.tela_cadastro.limpar()
        self.atualizar_tabela()
        self.ao_trocar_aba()

    def _montar_pagina(self, nome):
        """Monta a página na primeira vez (a montagem já lê os dados)."""
        nome_aba, classe = PAGINAS_SOB_DEMANDA[nome]
        aba = self.__dict__.get(nome_aba)
        tela = classe(aba, self) if aba is not None else None   # Usuários: só admin
        setattr(self, nome, tela)
        return tela

    def ir_para(self, aba):
        """Mostra a página e acende o item do menu (e relê os dados dela)."""
        self.abas.select(aba)
        self.ao_trocar_aba()

    def ir_para_saida_rapida(self, event=None):
        """F2: de qualquer página, leva o cursor à saída rápida."""
        if self.abas.select() != str(self.aba_cad):
            self.ir_para(self.aba_cad)
        self.tela_cadastro.campo_saida_rapida.focus_set()
        return "break"

    def ao_trocar_aba(self, event=None):
        atual = self.abas.select()
        for aba, item in self.itens_menu.items():
            item.definir_ativo(aba == atual)
        nome = self._paginas.get(atual)
        if nome in self.__dict__:
            self.__dict__[nome].atualizar()        # já montada: relê
        elif nome is not None:
            getattr(self, nome)                    # monta (e lê) agora
