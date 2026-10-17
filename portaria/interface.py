"""
Interface gráfica (Tkinter): janela principal, sessão do usuário, aba
Cadastro e aba Dashboard. O login fica em tela_login.py, a aba Pessoas em
tela_pessoas.py e a aba Usuários (só administrador) em tela_usuarios.py.

As regras ficam em validacao.py e usuarios.py, o banco de dados em dados.py
e os números em consultas.py — aqui só se monta a tela e se reage aos botões.
"""

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from . import dados
from .consultas import encontrar_dentro, filtrar, formatar_duracao, resumo
from .estilo import FUNDO, VERMELHO, botao, fonte_dica, fonte_lbl
from .tela_login import TelaLogin
from .tela_pessoas import AbaPessoas
from .tela_usuarios import AbaUsuarios
from .usuarios import (PERFIS, ControleTentativas, pode_excluir,
                       pode_gerenciar_usuarios)
from .validacao import (FORMATO, FORMATO_EXIBICAO, PLACA_OBRIGATORIA,
                        TIPOS_ACESSO, checar_saida, cpf_valido,
                        formatar_celular, formatar_cpf, formatar_placa,
                        normalizar, so_digitos, validar)

CORES_TIPO = {"Aluno": "#1f6fd1", "Professor": "#7a3fd1",
              "Funcionário": "#0a9a5a", "Visitante": "#e08a00",
              "Entregador": "#d9001b", "Prestador de serviço": "#5a6b7b"}
PLURAL_TIPO = {"Aluno": "Alunos", "Professor": "Professores",
               "Funcionário": "Funcionários", "Visitante": "Visitantes",
               "Entregador": "Entregadores",
               "Prestador de serviço": "Prestadores"}


DICA_CPF = "Digite o CPF primeiro: quem já veio tem os dados preenchidos sozinhos."
SEGUNDOS_PARA_DESFAZER = 10
TECLAS_DA_SESSAO = ("<Return>", "<KP_Enter>", "<F2>")


def agora():
    return datetime.now().strftime(FORMATO)


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
        self.dados_dash = {"tipos": [], "dias": []}  # dados prontos dos gráficos
        self.cards = {}                           # nome -> (label valor, label apoio)

        self.janela = janela or tk.Tk()
        self._montar_janela()
        self._carregar()
        if usuario:
            self.entrar(usuario)
        else:
            self.mostrar_login()

    def executar(self):
        self.janela.mainloop()

    # --------------------------------------------------------------
    # Banco de dados
    # --------------------------------------------------------------
    def _carregar(self):
        try:
            self.banco = dados.Banco(self.caminho_banco)
            aviso = (self.banco.importar_json(self.json_antigo)
                     if self.json_antigo else "")
        except dados.ErroDados as e:
            self.banco = None
            messagebox.showerror("Erro", str(e))
            return
        if aviso:
            messagebox.showinfo("Banco de dados", aviso)

    def tentar(self, operacao, *args, **kwargs):
        """Executa no banco; devolve (True, resultado) ou avisa e (False, None)."""
        try:
            return True, operacao(*args, **kwargs)
        except dados.ErroDados as e:
            messagebox.showerror("Erro", str(e))
            return False, None

    def _gravar(self, operacao, *args):
        """Grava em nome do usuário logado e recarrega a lista; False se falhar."""
        ok, _ = self.tentar(operacao, *args, autor=self.usuario["login"])
        if ok:
            recarregou, registros = self.tentar(self.banco.listar)
            if recarregou:
                self.registros = registros
        return ok

    # --------------------------------------------------------------
    # Sessão: login e saída
    # --------------------------------------------------------------
    def _trocar_corpo(self):
        if self.corpo is not None:
            self.corpo.destroy()
        self.corpo = tk.Frame(self.janela, bg=FUNDO)
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
            self.tentar(self.banco.registrar_evento, self.usuario["login"],
                        "Saiu do sistema")
        self.usuario = None
        for tecla in TECLAS_DA_SESSAO:
            self.janela.unbind(tecla)
        self.sessao.place_forget()
        self.mostrar_login()

    def _registro(self, iid):
        """Registro da tabela pela linha selecionada (iid = id no banco)."""
        return next(r for r in self.registros if r["id"] == int(iid))

    # --------------------------------------------------------------
    # Ações dos botões
    # --------------------------------------------------------------
    def cadastrar(self, event=None):
        if event is not None and self.abas.select() != str(self.aba_cad):
            return  # Enter só cadastra na aba Cadastro
        registro = normalizar(self.nome.get(), self.cpf.get(),
                              self.celular.get(), self.var_placa.get(),
                              self.tipo.get(), self.entrada.get(),
                              self.saida.get())
        ok, msg = validar(registro, self.registros)
        if not ok:
            messagebox.showerror("Dados inválidos", msg)
            return
        if not self._gravar(self.banco.inserir, registro):
            return
        self.atualizar_tabela(self.busca.get())
        self.limpar()
        messagebox.showinfo("Cadastro", "Registro cadastrado com sucesso!")

    def limpar(self):
        self._auto = None
        self.nome.delete(0, tk.END)
        self.var_cpf.set("")
        self.celular.delete(0, tk.END)
        self.var_placa.set("")
        self.tipo.set("")
        self.entrada.delete(0, tk.END)
        self.entrada.insert(0, agora())
        self.saida.delete(0, tk.END)
        self.cpf.focus()

    # --------------------------------------------------------------
    # Preenchimento automático pelo CPF
    # --------------------------------------------------------------
    def _campos_pessoa(self):
        return {"nome": self.nome, "celular": self.celular,
                "placa": self.var_placa, "tipo": self.tipo}

    @staticmethod
    def _escrever(campo, valor):
        if hasattr(campo, "set"):          # Combobox e StringVar
            campo.set(valor)
        else:                              # Entry
            campo.delete(0, tk.END)
            campo.insert(0, valor)

    def _dica_pessoa(self, texto, cor="#666"):
        self.lbl_pessoa.config(text=texto, fg=cor)

    def _ao_digitar_cpf(self, *args):
        """Ao completar o CPF, busca a pessoa e preenche os campos vazios."""
        cpf = so_digitos(self.var_cpf.get())
        if self._auto and self._auto["cpf"] != cpf:
            self._desfazer_preenchimento()
        if len(cpf) < 11:
            self._dica_pessoa(DICA_CPF)
            return
        if self._auto:
            return
        if not cpf_valido(cpf):
            self._dica_pessoa("CPF inválido — confira os números.", VERMELHO)
            return
        ok, pessoa = self.tentar(self.banco.buscar_pessoa, cpf)
        if not ok:
            return
        if pessoa is None:
            self._dica_pessoa("Pessoa nova — preencha os dados abaixo.", "#1f6fd1")
            return
        self._preencher_automatico(pessoa)

    def _preencher_automatico(self, pessoa):
        preenchidos = {}
        for chave, campo in self._campos_pessoa().items():
            if not campo.get().strip() and pessoa[chave]:
                self._escrever(campo, pessoa[chave])
                preenchidos[chave] = campo.get()
        self._auto = {"cpf": pessoa["cpf"], "campos": preenchidos}
        if pessoa["dentro_desde"]:
            primeiro_nome = pessoa["nome"].split()[0]
            self._dica_pessoa(f"⚠ {primeiro_nome} está no campus desde "
                              f"{pessoa['dentro_desde']} — registre a saída antes.",
                              "#c46a00")
        else:
            self._dica_pessoa(f"✓ Já cadastrado: {pessoa['visitas']} visita(s), "
                              f"última em {pessoa['ultima_visita'] or '—'}.",
                              "#0a8a50")

    def _desfazer_preenchimento(self):
        """CPF trocado: apaga o que foi preenchido sozinho e não foi mexido."""
        campos = self._campos_pessoa()
        for chave, valor in self._auto["campos"].items():
            if campos[chave].get() == valor:
                self._escrever(campos[chave], "")
        self._auto = None

    def preencher_pessoa(self, pessoa):
        """Começa uma nova entrada para a pessoa (usado pela aba Pessoas)."""
        self.limpar()
        self.var_cpf.set(pessoa["cpf"])
        self.abas.select(self.aba_cad)
        self.tipo.focus()

    def excluir_selecionado(self):
        if not pode_excluir(self.usuario):  # RN02
            messagebox.showerror("Acesso negado",
                                 "Somente o administrador pode excluir registros.")
            return
        selecionado = self.tabela.selection()
        if not selecionado:
            messagebox.showwarning("Atenção", "Selecione um registro na tabela.")
            return
        if not messagebox.askyesno("Confirmar", "Excluir o registro selecionado?"):
            return
        self._gravar(self.banco.excluir, [int(i) for i in selecionado])
        self.atualizar_tabela(self.busca.get())

    # --------------------------------------------------------------
    # Saída: botão, duplo clique e saída rápida por CPF ou placa
    # --------------------------------------------------------------
    def registrar_saida(self):
        """Botão: saída (data/hora atual) das linhas selecionadas."""
        selecionado = self.tabela.selection()
        if not selecionado:
            messagebox.showwarning("Atenção", "Selecione um registro na tabela.")
            return
        self._dar_saida([self._registro(i) for i in selecionado])

    def _ao_duplo_clique(self, event):
        linha = self.tabela.identify_row(event.y)
        if linha:
            self.registrar_saida_da_linha(linha)
        return "break"

    def registrar_saida_da_linha(self, linha):
        self._dar_saida([self._registro(linha)])

    def saida_rapida(self, event=None):
        """Campo Saída rápida: CPF ou placa exatos + Enter."""
        texto = self.campo_saida_rapida.get().strip()
        if not texto:
            messagebox.showwarning("Saída rápida", "Digite o CPF ou a placa.")
            return "break"
        encontrados = encontrar_dentro(self.registros, texto)
        if not encontrados:
            messagebox.showerror("Saída rápida",
                                 f"Ninguém no campus com o CPF ou a placa "
                                 f"“{texto}”.")
            return "break"
        if len(encontrados) > 1:
            nomes = "\n".join(f"• {r['nome']}" for r in encontrados)
            if not messagebox.askyesno(
                    "Saída rápida",
                    f"{len(encontrados)} pessoas estão no campus com essa placa:"
                    f"\n{nomes}\n\nRegistrar a saída de todas?"):
                return "break"
        if self._dar_saida(encontrados):
            self.campo_saida_rapida.delete(0, tk.END)
        return "break"

    def _dar_saida(self, registros):
        """Registra a saída agora; avisa sem travar a tela e oferece desfazer."""
        momento = datetime.now()
        prontos, recusas = [], []
        for r in registros:
            ok, msg = checar_saida(r, momento)
            if ok:
                prontos.append(r)
            else:
                recusas.append(msg)
        if not prontos:
            messagebox.showinfo("Aviso", "\n".join(recusas))
            return False
        ids = [r["id"] for r in prontos]
        if not self._gravar(self.banco.registrar_saidas, ids,
                            momento.strftime(FORMATO)):
            return False
        self.atualizar_tabela(self.busca.get())
        primeiros = [r["nome"].split()[0] for r in prontos]
        nomes = primeiros[-1]
        if len(primeiros) > 1:
            nomes = ", ".join(primeiros[:-1]) + " e " + nomes
        texto = f"✓ Saída de {nomes} registrada às {momento:%H:%M}."
        if recusas:
            texto += f"  ({len(recusas)} já tinha(m) saída.)"
        self._avisar(texto, desfazer=ids)
        return True

    def _avisar(self, texto, desfazer=None):
        """Mensagem que some sozinha; com `desfazer`, mostra o botão Desfazer."""
        if self._timer_aviso:
            self.janela.after_cancel(self._timer_aviso)
        self.lbl_aviso.config(text=texto)
        self._para_desfazer = desfazer
        if desfazer:
            self.btn_desfazer.pack(side="left", padx=(8, 0))
        else:
            self.btn_desfazer.pack_forget()
        self._timer_aviso = self.janela.after(SEGUNDOS_PARA_DESFAZER * 1000,
                                              self._esconder_aviso)

    def _esconder_aviso(self):
        self._timer_aviso = None
        self._para_desfazer = None
        self.lbl_aviso.config(text="")
        self.btn_desfazer.pack_forget()

    def desfazer_saida(self):
        ids = self._para_desfazer
        if not ids:
            return
        ok, desfeitas = self.tentar(self.banco.desfazer_saidas, ids,
                                    autor=self.usuario["login"])
        if not ok:
            return
        self.registros = self.tentar(self.banco.listar)[1] or self.registros
        self.atualizar_tabela(self.busca.get())
        if desfeitas < len(ids):
            messagebox.showwarning(
                "Desfazer", "Não foi possível desfazer a saída de quem já tem "
                            "outra entrada depois desta.")
        self._avisar("↺ Saída desfeita — a pessoa voltou a constar no campus."
                     if desfeitas else "")

    def atualizar_tabela(self, filtro=""):
        for item in self.tabela.get_children():
            self.tabela.delete(item)
        for r in filtrar(self.registros, filtro):
            self.tabela.insert("", "end", iid=str(r["id"]), values=(
                r["nome"],
                formatar_cpf(r.get("cpf", "")),
                formatar_celular(r.get("celular", "")),
                formatar_placa(r.get("placa", "")) or "—",
                r["tipo"],
                r["entrada"],
                r["saida"] or "— dentro —"))
        total_dentro = sum(1 for r in self.registros if not r["saida"])
        self.lbl_status.config(text=f"Registros: {len(self.registros)}   |   "
                                    f"Pessoas dentro agora: {total_dentro}")
        self.atualizar_dashboard()

    # --------------------------------------------------------------
    # Janela e aba Cadastro
    # --------------------------------------------------------------
    def _montar_janela(self):
        janela = self.janela
        janela.title("Portaria da Universidade")
        janela.geometry("1020x720")
        janela.minsize(900, 620)
        janela.configure(bg=FUNDO)

        estilo = ttk.Style()
        estilo.theme_use("clam")
        estilo.configure("Treeview", rowheight=26, font=("Segoe UI", 10))
        estilo.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        estilo.configure("TNotebook", background=FUNDO, borderwidth=0)
        estilo.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"),
                         padding=[18, 7])

        # Cabeçalho
        topo = tk.Frame(janela, bg=VERMELHO)
        topo.pack(fill="x")
        tk.Label(topo, text="🏛  Portaria da Universidade", bg=VERMELHO,
                 fg="white", font=("Segoe UI", 18, "bold")
                 ).pack(anchor="w", padx=20, pady=(12, 0))
        tk.Label(topo, text="Controle de entrada e saída de pessoas no campus",
                 bg=VERMELHO, fg="#ffd9de", font=("Segoe UI", 10)
                 ).pack(anchor="w", padx=20, pady=(0, 12))

        # Quem está logado + Sair (aparece só depois do login)
        self.sessao = tk.Frame(topo, bg=VERMELHO)
        self.lbl_usuario = tk.Label(self.sessao, bg=VERMELHO, fg="white",
                                    font=("Segoe UI", 10, "bold"))
        self.lbl_usuario.pack(side="left", padx=(0, 12))
        tk.Button(self.sessao, text="Sair", command=self.sair, bg="white",
                  fg=VERMELHO, activebackground="#ffd9de",
                  activeforeground=VERMELHO, relief="flat", cursor="hand2",
                  font=("Segoe UI", 9, "bold"), padx=12, pady=3
                  ).pack(side="left")

    def _montar_principal(self):
        """Abas que aparecem depois do login."""
        self.abas = ttk.Notebook(self.corpo)
        self.abas.pack(fill="both", expand=True)
        self.aba_cad = tk.Frame(self.abas, bg=FUNDO)
        self.aba_dash = tk.Frame(self.abas, bg=FUNDO)
        self.aba_pessoas = tk.Frame(self.abas, bg=FUNDO)
        self.abas.add(self.aba_cad, text="  📋 Cadastro  ")
        self.abas.add(self.aba_pessoas, text="  👥 Pessoas  ")
        self.abas.add(self.aba_dash, text="  📊 Dashboard  ")
        self.cards = {}
        self.aba_usuarios = self.tela_usuarios = None
        self._montar_cadastro()
        self._montar_dashboard()
        self.tela_pessoas = AbaPessoas(self.aba_pessoas, self)
        self.abas.bind("<<NotebookTabChanged>>", self._ao_trocar_aba)

        if pode_gerenciar_usuarios(self.usuario):
            self.aba_usuarios = tk.Frame(self.abas, bg=FUNDO)
            self.abas.add(self.aba_usuarios, text="  👤 Usuários  ")
            self.tela_usuarios = AbaUsuarios(self.aba_usuarios, self)

        # Tecla ENTER cadastra (exceto na caixa de busca)
        self.janela.bind("<Return>", self.cadastrar)
        self.janela.bind("<KP_Enter>", self.cadastrar)
        self.busca.bind("<Return>", lambda e: "break")
        self.janela.bind("<F2>", lambda e: self.campo_saida_rapida.focus_set())

        self.registros = self.tentar(self.banco.listar)[1] or []
        self.limpar()
        self.atualizar_tabela()

    def _ao_trocar_aba(self, event=None):
        aba = self.abas.select()
        if aba == str(self.aba_pessoas):
            self.tela_pessoas.atualizar()
        elif self.aba_usuarios is not None and aba == str(self.aba_usuarios):
            self.tela_usuarios.atualizar()

    def _so_numeros(self, limite):
        """Validação de digitação: só números, com limite de tamanho."""
        return (self.janela.register(
            lambda p: p == "" or (p.isascii() and p.isdigit() and len(p) <= limite)),
            "%P")

    def _montar_cadastro(self):
        form = tk.Frame(self.aba_cad, bg=FUNDO)
        form.pack(fill="x", padx=20, pady=14)
        form.columnconfigure((0, 1, 2), weight=1, uniform="col")

        def rotulo(texto, linha, coluna, **kw):
            tk.Label(form, text=texto, bg=FUNDO, font=fonte_lbl
                     ).grid(row=linha, column=coluna, sticky="w", **kw)

        def dica(texto, linha, coluna, cor="#666"):
            tk.Label(form, text=texto, bg=FUNDO, fg=cor, font=fonte_dica
                     ).grid(row=linha, column=coluna, sticky="w")

        # Linha 0-2: CPF primeiro (é por ele que a pessoa é reconhecida)
        # e nome nas outras duas colunas
        rotulo("CPF (somente números): *", 0, 0)
        self._auto = None   # o que foi preenchido sozinho, para poder desfazer
        self.var_cpf = tk.StringVar()
        self.cpf = ttk.Entry(form, font=("Segoe UI", 10), validate="key",
                             textvariable=self.var_cpf,
                             validatecommand=self._so_numeros(11))
        self.cpf.grid(row=1, column=0, sticky="ew", padx=(0, 10))

        rotulo("Nome completo: *", 0, 1)
        self.nome = ttk.Entry(form, font=("Segoe UI", 10))
        self.nome.grid(row=1, column=1, columnspan=2, sticky="ew")

        self.lbl_pessoa = tk.Label(form, text=DICA_CPF, bg=FUNDO, fg="#666",
                                   font=("Segoe UI", 9, "bold"), anchor="w")
        self.lbl_pessoa.grid(row=2, column=0, columnspan=3, sticky="w",
                             pady=(2, 6))

        # Linha 3-5: celular, placa e tipo
        rotulo("Celular com DDD (somente números): *", 3, 0)
        self.celular = ttk.Entry(form, font=("Segoe UI", 10), validate="key",
                                 validatecommand=self._so_numeros(11))
        self.celular.grid(row=4, column=0, sticky="ew", padx=(0, 10))

        # Placa: letras/números, máximo 7, sempre maiúscula
        rotulo("Placa do veículo:" + (" *" if PLACA_OBRIGATORIA else ""), 3, 1)
        self.var_placa = tk.StringVar()
        self.var_placa.trace_add("write", self._placa_maiuscula)
        placa_ok = self.janela.register(
            lambda p: p == "" or (p.isascii() and p.isalnum() and len(p) <= 7))
        ttk.Entry(form, font=("Segoe UI", 10), textvariable=self.var_placa,
                  validate="key", validatecommand=(placa_ok, "%P")
                  ).grid(row=4, column=1, sticky="ew", padx=(0, 10))

        rotulo("Tipo de acesso: *", 3, 2)
        self.tipo = ttk.Combobox(form, values=TIPOS_ACESSO, state="readonly",
                                 font=("Segoe UI", 10))
        self.tipo.grid(row=4, column=2, sticky="ew")

        dica("Ex.: 31912345678 (DDD + 9 + 8 dígitos)", 5, 0)
        dica("ABC1234 ou ABC1D23 (deixe vazio se a pé)", 5, 1)

        # Linha 6-8: entrada e saída
        rotulo(f"Entrada ({FORMATO_EXIBICAO}): *", 6, 0, pady=(8, 0))
        self.entrada = self._campo_data(form, 7, 0)
        rotulo(f"Saída ({FORMATO_EXIBICAO}):", 6, 1, pady=(8, 0))
        self.saida = self._campo_data(form, 7, 1)

        dica("Saída em branco = pessoa ainda no campus.", 8, 1)
        dica("* campos obrigatórios", 8, 0, cor=VERMELHO)

        # Liga o preenchimento automático só depois de tudo montado
        self.var_cpf.trace_add("write", self._ao_digitar_cpf)

        # Botões
        botoes = tk.Frame(self.aba_cad, bg=FUNDO)
        botoes.pack(fill="x", padx=20)
        botao(botoes, "+ Cadastrar (Enter)", "#0a9a5a", self.cadastrar)
        botao(botoes, "Limpar", "#1f6fd1", self.limpar)
        botao(botoes, "Registrar saída", "#e08a00", self.registrar_saida)
        self.btn_excluir = None
        if pode_excluir(self.usuario):  # RN02: o porteiro nem vê o botão
            self.btn_excluir = botao(botoes, "✕ Excluir selecionado", "#e03131",
                                     self.excluir_selecionado, lado="right")

        # Saída rápida: CPF ou placa + Enter (F2 leva o cursor para cá)
        barra_saida = tk.Frame(self.aba_cad, bg=FUNDO)
        barra_saida.pack(fill="x", padx=20, pady=(12, 0))
        tk.Label(barra_saida, text="Saída rápida (F2) — CPF ou placa:",
                 bg=FUNDO, font=fonte_lbl).pack(side="left")
        self.campo_saida_rapida = ttk.Entry(barra_saida, font=("Segoe UI", 10),
                                            width=18)
        self.campo_saida_rapida.pack(side="left", padx=8)
        self.campo_saida_rapida.bind("<Return>", self.saida_rapida)
        self.campo_saida_rapida.bind("<KP_Enter>", self.saida_rapida)
        tk.Button(barra_saida, text="Registrar", command=self.saida_rapida,
                  bg="#e08a00", fg="white", activebackground="#e08a00",
                  activeforeground="white", relief="flat", cursor="hand2",
                  font=("Segoe UI", 9, "bold"), padx=10, pady=2
                  ).pack(side="left")
        self.lbl_aviso = tk.Label(barra_saida, text="", bg=FUNDO, fg="#0a8a50",
                                  font=("Segoe UI", 9, "bold"))
        self.lbl_aviso.pack(side="left", padx=(16, 0))
        self.btn_desfazer = tk.Button(barra_saida, text="Desfazer",
                                      command=self.desfazer_saida, bg=FUNDO,
                                      fg="#1f6fd1", activebackground=FUNDO,
                                      relief="flat", cursor="hand2",
                                      font=("Segoe UI", 9, "bold underline"))
        self._timer_aviso = None
        self._para_desfazer = None

        # Busca
        barra_busca = tk.Frame(self.aba_cad, bg=FUNDO)
        barra_busca.pack(fill="x", padx=20, pady=(8, 4))
        tk.Label(barra_busca, text="Buscar (nome, CPF, celular, placa ou tipo):",
                 bg=FUNDO, font=fonte_lbl).pack(side="left")
        self.busca = ttk.Entry(barra_busca, font=("Segoe UI", 10))
        self.busca.pack(side="left", fill="x", expand=True, padx=8)
        self.busca.bind("<KeyRelease>",
                        lambda e: self.atualizar_tabela(self.busca.get()))

        # Tabela
        quadro = tk.Frame(self.aba_cad, bg=FUNDO)
        quadro.pack(fill="both", expand=True, padx=20, pady=(0, 6))
        self.tabela = ttk.Treeview(
            quadro, show="headings", selectmode="extended",
            columns=("Nome", "CPF", "Celular", "Placa", "Tipo", "Entrada",
                     "Saida"))
        for col, titulo, larg, anc in [
                ("Nome", "Nome", 170, "w"), ("CPF", "CPF", 105, "center"),
                ("Celular", "Celular", 115, "center"),
                ("Placa", "Placa", 75, "center"),
                ("Tipo", "Tipo de acesso", 120, "w"),
                ("Entrada", "Entrada", 130, "center"),
                ("Saida", "Saída", 130, "center")]:
            self.tabela.heading(col, text=titulo)
            self.tabela.column(col, width=larg, anchor=anc)
        rolagem = ttk.Scrollbar(quadro, orient="vertical",
                                command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=rolagem.set)
        self.tabela.pack(side="left", fill="both", expand=True)
        rolagem.pack(side="right", fill="y")
        self.tabela.bind("<Double-1>", self._ao_duplo_clique)

        self.lbl_status = tk.Label(self.aba_cad, text="", bg=FUNDO, fg="#444",
                                   font=("Segoe UI", 9), anchor="w")
        self.lbl_status.pack(fill="x", padx=20, pady=(0, 8))

    def _placa_maiuscula(self, *args):
        texto = self.var_placa.get()
        if texto != texto.upper():
            self.var_placa.set(texto.upper())

    def _campo_data(self, form, linha, coluna):
        """Campo de data/hora com o botão 'Agora' ao lado."""
        caixa = tk.Frame(form, bg=FUNDO)
        caixa.grid(row=linha, column=coluna, sticky="ew", padx=(0, 10))
        campo = ttk.Entry(caixa, font=("Segoe UI", 10))
        campo.pack(side="left", fill="x", expand=True)
        ttk.Button(caixa, text="Agora", width=7,
                   command=lambda: (campo.delete(0, tk.END),
                                    campo.insert(0, agora()))
                   ).pack(side="left", padx=(6, 0))
        return campo

    # --------------------------------------------------------------
    # Aba Dashboard
    # --------------------------------------------------------------
    def _criar_card(self, pai, linha, coluna, chave, titulo, cor):
        caixa = tk.Frame(pai, bg="white", highlightbackground="#dde1ea",
                         highlightthickness=1)
        caixa.grid(row=linha, column=coluna, sticky="nsew", padx=5, pady=5)
        tk.Frame(caixa, bg=cor, height=4).pack(fill="x")
        tk.Label(caixa, text=titulo, bg="white", fg="#555",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12,
                                                    pady=(8, 0))
        valor = tk.Label(caixa, text="0", bg="white", fg="#222",
                         font=("Segoe UI", 20, "bold"))
        valor.pack(anchor="w", padx=12)
        apoio = tk.Label(caixa, text="", bg="white", fg="#777",
                         font=("Segoe UI", 8))
        apoio.pack(anchor="w", padx=12, pady=(0, 8))
        self.cards[chave] = (valor, apoio)

    def _montar_dashboard(self):
        aba = self.aba_dash

        # Linha 1: um card por tipo de acesso
        linha_tipos = tk.Frame(aba, bg=FUNDO)
        linha_tipos.pack(fill="x", padx=15, pady=(14, 0))
        linha_tipos.columnconfigure(tuple(range(len(TIPOS_ACESSO))), weight=1,
                                    uniform="ct")
        for i, t in enumerate(TIPOS_ACESSO):
            self._criar_card(linha_tipos, 0, i, t, PLURAL_TIPO[t], CORES_TIPO[t])

        # Linha 2: resumo geral
        linha_resumo = tk.Frame(aba, bg=FUNDO)
        linha_resumo.pack(fill="x", padx=15)
        linha_resumo.columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="cr")
        for i, (chave, titulo, cor) in enumerate([
                ("total", "TOTAL DE REGISTROS", "#222222"),
                ("dentro", "DENTRO AGORA", "#0a9a5a"),
                ("hoje", "ENTRADAS HOJE", "#1f6fd1"),
                ("veiculos", "COM VEÍCULO", "#e08a00"),
                ("permanencia", "PERMANÊNCIA MÉDIA", "#7a3fd1")]):
            self._criar_card(linha_resumo, 0, i, chave, titulo, cor)

        # Gráficos
        area = tk.Frame(aba, bg=FUNDO)
        area.pack(fill="both", expand=True, padx=15, pady=(6, 14))
        area.columnconfigure(0, weight=1, uniform="g")
        area.columnconfigure(1, weight=1, uniform="g")
        area.rowconfigure(0, weight=1)
        self.cv_tipos = tk.Canvas(area, bg="white", height=260,
                                  highlightbackground="#dde1ea",
                                  highlightthickness=1)
        self.cv_tipos.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.cv_dias = tk.Canvas(area, bg="white", height=260,
                                 highlightbackground="#dde1ea",
                                 highlightthickness=1)
        self.cv_dias.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.cv_tipos.bind("<Configure>", self.redesenhar_graficos)
        self.cv_dias.bind("<Configure>", self.redesenhar_graficos)

    @staticmethod
    def desenhar_barras_horizontais(cv, titulo, itens):
        """itens: lista de (rótulo, valor, texto à direita, cor)."""
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        cv.create_text(14, 18, text=titulo, anchor="w", fill="#222",
                       font=("Segoe UI", 11, "bold"))
        if not itens or max(v for _, v, _, _ in itens) == 0:
            cv.create_text(w / 2, h / 2, text="Sem dados ainda", fill="#888",
                           font=("Segoe UI", 10))
            return
        maximo = max(v for _, v, _, _ in itens)
        esq, dir_, topo = 130, 190, 42
        area = max(w - esq - dir_, 10)
        passo = (h - topo - 10) / len(itens)
        for i, (rotulo_, valor_, extra, cor) in enumerate(itens):
            y = topo + i * passo
            comp = area * valor_ / maximo
            cv.create_text(esq - 8, y + passo / 2, text=rotulo_, anchor="e",
                           fill="#333", font=("Segoe UI", 9))
            cv.create_rectangle(esq, y + passo * 0.2, esq + max(comp, 2),
                                y + passo * 0.8, fill=cor, outline="")
            cv.create_text(esq + comp + 8, y + passo / 2, text=extra, anchor="w",
                           fill="#444", font=("Segoe UI", 9, "bold"))

    @staticmethod
    def desenhar_barras_verticais(cv, titulo, itens, cor):
        """itens: lista de (rótulo, valor)."""
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        cv.create_text(14, 18, text=titulo, anchor="w", fill="#222",
                       font=("Segoe UI", 11, "bold"))
        if not itens or max(v for _, v in itens) == 0:
            cv.create_text(w / 2, h / 2, text="Sem dados ainda", fill="#888",
                           font=("Segoe UI", 10))
            return
        maximo = max(v for _, v in itens)
        esq, topo, base = 20, 56, h - 30
        larg = max((w - 2 * esq) / len(itens), 10)
        cv.create_line(esq, base, w - esq, base, fill="#ccc")
        for i, (rotulo_, valor_) in enumerate(itens):
            x0 = esq + i * larg + larg * 0.2
            x1 = esq + (i + 1) * larg - larg * 0.2
            altura = (base - topo) * valor_ / maximo
            cv.create_rectangle(x0, base - altura, x1, base, fill=cor,
                                outline="")
            cv.create_text((x0 + x1) / 2, base - altura - 9, text=str(valor_),
                           fill="#444", font=("Segoe UI", 9, "bold"))
            cv.create_text((x0 + x1) / 2, base + 14, text=rotulo_, fill="#555",
                           font=("Segoe UI", 8))

    def redesenhar_graficos(self, event=None):
        self.desenhar_barras_horizontais(self.cv_tipos,
                                         "Pessoas por tipo de acesso",
                                         self.dados_dash["tipos"])
        self.desenhar_barras_verticais(self.cv_dias, "Entradas nos últimos 7 dias",
                                       self.dados_dash["dias"], "#1f6fd1")

    def atualizar_dashboard(self):
        hoje = datetime.now().date()
        r = resumo(self.registros, hoje)
        por_tipo = r["por_tipo"]

        for t in TIPOS_ACESSO:
            total_t, dentro_t = por_tipo[t]
            self.cards[t][0].config(text=str(total_t))
            self.cards[t][1].config(text=f"{dentro_t} dentro agora")

        self.cards["total"][0].config(text=str(r["total"]))
        self.cards["total"][1].config(text="desde o início")
        self.cards["dentro"][0].config(text=str(r["dentro"]))
        self.cards["dentro"][1].config(text=f"{r['total'] - r['dentro']} já saíram")
        self.cards["hoje"][0].config(text=str(r["entradas_hoje"]))
        self.cards["hoje"][1].config(text=hoje.strftime("%d/%m/%Y"))
        self.cards["veiculos"][0].config(text=str(r["com_veiculo"]))
        self.cards["veiculos"][1].config(text="registros com placa")
        if r["permanencia_media"] is not None:
            self.cards["permanencia"][0].config(
                text=formatar_duracao(r["permanencia_media"]))
            self.cards["permanencia"][1].config(text=f"{r['saidas']} saídas")
        else:
            self.cards["permanencia"][0].config(text="—")
            self.cards["permanencia"][1].config(text="sem saídas registradas")

        total = r["total"]
        self.dados_dash["tipos"] = [
            (PLURAL_TIPO.get(t, t), por_tipo[t][0],
             f"{por_tipo[t][0]} ({por_tipo[t][0] * 100 // total if total else 0}%)"
             f" · {por_tipo[t][1]} dentro",
             CORES_TIPO.get(t, "#888"))
            for t in TIPOS_ACESSO]
        self.dados_dash["dias"] = [(d.strftime("%d/%m"), n)
                                   for d, n in r["por_dia"].items()]
        self.redesenhar_graficos()
