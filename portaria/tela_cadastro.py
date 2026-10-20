"""
Aba Cadastro: registrar a entrada de uma pessoa (com preenchimento
automático pelo CPF e alerta de bloqueio), dar saída (botão, duplo clique
ou saída rápida por CPF/placa), desfazer a saída, corrigir e excluir
registros, e a tabela com a busca.

Fala com a janela principal só pelo contrato público do app (ver
interface.py): app.banco, app.usuario, app.autor, app.registros,
app.tentar(), app.gravar(), app.recarregar_registros() e
app.atualizar_tabela().
"""

import tkinter as tk
from datetime import datetime
from tkinter import ttk

from . import mensagens
from .componentes import (barra_busca, botao, botao_link, botao_pequeno,
                          combo, dica, entrada, entrada_numeros, entrada_placa,
                          rotulo_secao, tabela)
from .consultas import encontrar_dentro, filtrar
from .estilo import COR, FONTE
from .tela_edicao import JanelaEdicao
from .usuarios import pode_editar, pode_excluir
from .validacao import (FORMATO, FORMATO_EXIBICAO, PLACA_OBRIGATORIA,
                        TIPOS_ACESSO, checar_bloqueio, checar_saida,
                        cpf_valido, formatar_celular, formatar_cpf,
                        formatar_placa, normalizar, placa_valida, so_digitos,
                        validar)

DICA_CPF = "Digite o CPF primeiro: quem já veio tem os dados preenchidos sozinhos."
DICA_PLACA = "ABC1234 ou ABC1D23 (deixe vazio se a pé)"
SEGUNDOS_PARA_DESFAZER = 10
COLUNAS = [("Nome", "Nome", 170, "w"), ("CPF", "CPF", 105, "center"),
           ("Celular", "Celular", 115, "center"),
           ("Placa", "Placa", 75, "center"),
           ("Tipo", "Tipo de acesso", 120, "w"),
           ("Entrada", "Entrada", 130, "center"),
           ("Saida", "Saída", 130, "center")]


def agora():
    return datetime.now().strftime(FORMATO)


class AbaCadastro:
    def __init__(self, aba, app):
        self.aba = aba
        self.app = app
        self.janela_edicao = None     # janela "Corrigir registro" aberta
        self._auto = None   # o que foi preenchido sozinho, para poder desfazer
        self._timer_aviso = None
        self._para_desfazer = None

        self._montar_formulario()
        self._montar_botoes()
        self._montar_saida_rapida()
        self._montar_tabela()

    # --------------------------------------------------------------
    # Montagem
    # --------------------------------------------------------------
    def _montar_formulario(self):
        form = tk.Frame(self.aba, bg=COR["fundo"])
        form.pack(fill="x", padx=20, pady=14)
        form.columnconfigure((0, 1, 2), weight=1, uniform="col")

        def rotulo(texto, linha, coluna, **kw):
            rotulo_secao(form, texto).grid(row=linha, column=coluna,
                                           sticky="w", **kw)

        def nova_dica(texto, linha, coluna, cor=COR["texto_3"]):
            rotulo_dica = dica(form, texto, cor=cor)
            rotulo_dica.grid(row=linha, column=coluna, sticky="w")
            return rotulo_dica

        # Linha 0-2: CPF primeiro (é por ele que a pessoa é reconhecida)
        # e nome nas outras duas colunas
        rotulo("CPF (somente números): *", 0, 0)
        self.var_cpf = tk.StringVar()
        self.cpf = entrada_numeros(form, 11, textvariable=self.var_cpf)
        self.cpf.grid(row=1, column=0, sticky="ew", padx=(0, 10))

        rotulo("Nome completo: *", 0, 1)
        self.nome = entrada(form)
        self.nome.grid(row=1, column=1, columnspan=2, sticky="ew")

        self.lbl_pessoa = tk.Label(form, text=DICA_CPF, bg=COR["fundo"],
                                   fg=COR["texto_3"], font=FONTE["aviso"],
                                   anchor="w")
        self.lbl_pessoa.grid(row=2, column=0, columnspan=3, sticky="w",
                             pady=(2, 6))

        # Linha 3-5: celular, placa e tipo
        rotulo("Celular com DDD (somente números): *", 3, 0)
        self.celular = entrada_numeros(form, 11)
        self.celular.grid(row=4, column=0, sticky="ew", padx=(0, 10))

        # Placa: letras/números, máximo 7, sempre maiúscula
        rotulo("Placa do veículo:" + (" *" if PLACA_OBRIGATORIA else ""), 3, 1)
        caixa_placa, self.var_placa = entrada_placa(form)
        caixa_placa.grid(row=4, column=1, sticky="ew", padx=(0, 10))

        rotulo("Tipo de acesso: *", 3, 2)
        self.tipo = combo(form, TIPOS_ACESSO)
        self.tipo.grid(row=4, column=2, sticky="ew")

        nova_dica("Ex.: 31912345678 (DDD + 9 + 8 dígitos)", 5, 0)
        self.lbl_dica_placa = nova_dica(DICA_PLACA, 5, 1)

        # Linha 6-8: entrada e saída
        rotulo(f"Entrada ({FORMATO_EXIBICAO}): *", 6, 0, pady=(8, 0))
        self.entrada = self._campo_data(form, 7, 0)
        rotulo(f"Saída ({FORMATO_EXIBICAO}):", 6, 1, pady=(8, 0))
        self.saida = self._campo_data(form, 7, 1)

        nova_dica("Saída em branco = pessoa ainda no campus.", 8, 1)
        nova_dica("* campos obrigatórios", 8, 0, cor=COR["erro"])

        # Liga o preenchimento automático e os alertas de bloqueio só
        # depois de tudo montado
        self.var_cpf.trace_add("write", self._ao_digitar_cpf)
        self.var_placa.trace_add("write", self._ao_digitar_placa)

    @staticmethod
    def _campo_data(form, linha, coluna):
        """Campo de data/hora com o botão 'Agora' ao lado."""
        caixa = tk.Frame(form, bg=COR["fundo"])
        caixa.grid(row=linha, column=coluna, sticky="ew", padx=(0, 10))
        campo = entrada(caixa)
        campo.pack(side="left", fill="x", expand=True)
        ttk.Button(caixa, text="Agora", width=7,
                   command=lambda: (campo.delete(0, tk.END),
                                    campo.insert(0, agora()))
                   ).pack(side="left", padx=(6, 0))
        return campo

    def _montar_botoes(self):
        botoes = tk.Frame(self.aba, bg=COR["fundo"])
        botoes.pack(fill="x", padx=20)
        botao(botoes, "+ Cadastrar (Enter)", COR["primario"], self.cadastrar)
        botao(botoes, "Limpar", COR["secundario"], self.limpar)
        botao(botoes, "Registrar saída", COR["atencao"], self.registrar_saida)
        botao(botoes, "✎ Corrigir", COR["neutro"], self.editar_selecionado)
        self.btn_excluir = None
        if pode_excluir(self.app.usuario):  # RN02: o porteiro nem vê o botão
            self.btn_excluir = botao(botoes, "✕ Excluir selecionado",
                                     COR["perigo"], self.excluir_selecionado,
                                     lado="right")

    def _montar_saida_rapida(self):
        """Saída rápida: CPF ou placa + Enter (F2 leva o cursor para cá)."""
        barra = tk.Frame(self.aba, bg=COR["fundo"])
        barra.pack(fill="x", padx=20, pady=(12, 0))
        rotulo_secao(barra, "Saída rápida (F2) — CPF ou placa:").pack(side="left")
        self.campo_saida_rapida = entrada(barra, width=18)
        self.campo_saida_rapida.pack(side="left", padx=8)
        self.campo_saida_rapida.bind("<Return>", self.saida_rapida)
        self.campo_saida_rapida.bind("<KP_Enter>", self.saida_rapida)
        botao_pequeno(barra, "Registrar", self.saida_rapida, COR["atencao"],
                      padx=10, pady=2).pack(side="left")
        self.lbl_aviso = tk.Label(barra, text="", bg=COR["fundo"],
                                  fg=COR["sucesso"], font=FONTE["aviso"])
        self.lbl_aviso.pack(side="left", padx=(16, 0))
        self.btn_desfazer = botao_link(barra, "Desfazer", self.desfazer_saida)

    def _montar_tabela(self):
        barra, self.busca = barra_busca(
            self.aba, "Buscar (nome, CPF, celular, placa ou tipo):")
        barra.pack(fill="x", padx=20, pady=(8, 4))
        self.busca.bind("<KeyRelease>", lambda e: self.atualizar_tabela())

        quadro, self.tabela = tabela(self.aba, COLUNAS, selecao="extended")
        quadro.pack(fill="both", expand=True, padx=20, pady=(0, 6))
        self.tabela.bind("<Double-1>", self._ao_duplo_clique)

        self.lbl_status = tk.Label(self.aba, text="", bg=COR["fundo"],
                                   fg=COR["texto_status"], font=FONTE["legenda"],
                                   anchor="w")
        self.lbl_status.pack(fill="x", padx=20, pady=(0, 8))

    # --------------------------------------------------------------
    # Tabela
    # --------------------------------------------------------------
    def atualizar_tabela(self):
        """Mostra app.registros filtrados pela busca e o total no rodapé."""
        registros = self.app.registros
        self.tabela.delete(*self.tabela.get_children())
        for r in filtrar(registros, self.busca.get()):
            self.tabela.insert("", "end", iid=str(r["id"]), values=(
                r["nome"],
                formatar_cpf(r.get("cpf", "")),
                formatar_celular(r.get("celular", "")),
                formatar_placa(r.get("placa", "")) or "—",
                r["tipo"],
                r["entrada"],
                r["saida"] or "— dentro —"))
        total_dentro = sum(1 for r in registros if not r["saida"])
        self.lbl_status.config(text=f"Registros: {len(registros)}   |   "
                                    f"Pessoas dentro agora: {total_dentro}")

    def _registro(self, iid):
        """Registro da tabela pela linha selecionada (iid = id no banco)."""
        return next(r for r in self.app.registros if r["id"] == int(iid))

    def _esta_visivel(self):
        # a aba fica dentro do Notebook de abas (self.aba.master)
        return self.aba.master.select() == str(self.aba)

    # --------------------------------------------------------------
    # Cadastrar e limpar
    # --------------------------------------------------------------
    def cadastrar(self, event=None):
        if event is not None and not self._esta_visivel():
            return  # Enter só cadastra na aba Cadastro
        registro = normalizar(self.nome.get(), self.cpf.get(),
                              self.celular.get(), self.var_placa.get(),
                              self.tipo.get(), self.entrada.get(),
                              self.saida.get())
        # RN12: bloqueio primeiro, para não preencher a ficha à toa
        ok, ativos = self.app.tentar(self.app.banco.listar_bloqueios)
        if not ok:
            return
        ok, msg = checar_bloqueio(registro, ativos)
        if not ok:
            self._registrar_recusa(registro)
            mensagens.erro("Acesso negado", msg)
            return
        ok, msg = validar(registro, self.app.registros)
        if not ok:
            mensagens.erro("Dados inválidos", msg)
            return
        if not self.app.gravar(self.app.banco.inserir, registro):
            return
        self.app.atualizar_tabela()
        self.limpar()
        mensagens.info("Cadastro", "Registro cadastrado com sucesso!")

    def _registrar_recusa(self, registro):
        detalhe = f"{registro['nome'] or '?'}, CPF {formatar_cpf(registro['cpf'])}"
        if registro["placa"]:
            detalhe += f", placa {registro['placa']}"
        self.app.tentar(self.app.banco.registrar_evento, self.app.autor,
                        "Entrada recusada (bloqueio)", detalhe)

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

    def preencher_pessoa(self, pessoa):
        """Começa uma nova entrada para a pessoa (usado pela aba Pessoas)."""
        self.limpar()
        self.var_cpf.set(pessoa["cpf"])
        self.tipo.focus()

    # --------------------------------------------------------------
    # Preenchimento automático pelo CPF e alertas de bloqueio
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

    def _dica_pessoa(self, texto, cor=COR["texto_3"]):
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
            self._dica_pessoa("CPF inválido — confira os números.", COR["erro"])
            return
        ok, pessoa = self.app.tentar(self.app.banco.buscar_pessoa, cpf)
        if not ok:
            return
        if pessoa is None:
            self._dica_pessoa("Pessoa nova — preencha os dados abaixo.",
                              COR["info"])
        else:
            self._preencher_automatico(pessoa)
        bloqueio = self._bloqueio_ativo("cpf", cpf)
        if bloqueio:
            self._dica_pessoa(f"CPF BLOQUEADO — {bloqueio['motivo']}. "
                              "A entrada será recusada.", COR["erro"])

    def _bloqueio_ativo(self, tipo, valor):
        ok, ativos = self.app.tentar(self.app.banco.listar_bloqueios)
        return next((b for b in (ativos or [])
                     if b["tipo"] == tipo and b["valor"] == valor), None)

    def _ao_digitar_placa(self, *args):
        """Placa completa e bloqueada: troca a dica por um alerta vermelho."""
        placa = self.var_placa.get().strip().upper()
        bloqueio = (self._bloqueio_ativo("placa", placa)
                    if placa_valida(placa) else None)
        if bloqueio:
            self.lbl_dica_placa.config(
                text=f"PLACA BLOQUEADA — {bloqueio['motivo']}", fg=COR["erro"],
                font=FONTE["dica_forte"])
        else:
            self.lbl_dica_placa.config(text=DICA_PLACA, fg=COR["texto_3"],
                                       font=FONTE["dica"])

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
                              COR["alerta"])
        else:
            self._dica_pessoa(f"✓ Já cadastrado: {pessoa['visitas']} visita(s), "
                              f"última em {pessoa['ultima_visita'] or '—'}.",
                              COR["sucesso"])

    def _desfazer_preenchimento(self):
        """CPF trocado: apaga o que foi preenchido sozinho e não foi mexido."""
        campos = self._campos_pessoa()
        for chave, valor in self._auto["campos"].items():
            if campos[chave].get() == valor:
                self._escrever(campos[chave], "")
        self._auto = None

    # --------------------------------------------------------------
    # Corrigir e excluir o registro selecionado
    # --------------------------------------------------------------
    def editar_selecionado(self):
        """Abre a janela para corrigir o registro selecionado (RN11)."""
        selecionado = self.tabela.selection()
        if not selecionado:
            mensagens.aviso("Atenção", "Selecione um registro na tabela.")
            return
        if len(selecionado) > 1:
            mensagens.aviso("Atenção", "Selecione um registro só para corrigir.")
            return
        registro = self._registro(selecionado[0])
        ok, msg = pode_editar(self.app.usuario, registro, datetime.now())
        if not ok:
            mensagens.erro("Acesso negado", msg)
            return
        self.janela_edicao = JanelaEdicao(self.app, registro)

    def excluir_selecionado(self):
        if not pode_excluir(self.app.usuario):  # RN02
            mensagens.erro("Acesso negado",
                           "Somente o administrador pode excluir registros.")
            return
        selecionado = self.tabela.selection()
        if not selecionado:
            mensagens.aviso("Atenção", "Selecione um registro na tabela.")
            return
        if not mensagens.confirmar("Confirmar", "Excluir o registro selecionado?"):
            return
        self.app.gravar(self.app.banco.excluir, [int(i) for i in selecionado])
        self.app.atualizar_tabela()

    # --------------------------------------------------------------
    # Saída: botão, duplo clique e saída rápida por CPF ou placa
    # --------------------------------------------------------------
    def registrar_saida(self):
        """Botão: saída (data/hora atual) das linhas selecionadas."""
        selecionado = self.tabela.selection()
        if not selecionado:
            mensagens.aviso("Atenção", "Selecione um registro na tabela.")
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
            mensagens.aviso("Saída rápida", "Digite o CPF ou a placa.")
            return "break"
        encontrados = encontrar_dentro(self.app.registros, texto)
        if not encontrados:
            mensagens.erro("Saída rápida",
                           f"Ninguém no campus com o CPF ou a placa “{texto}”.")
            return "break"
        if len(encontrados) > 1:
            nomes = "\n".join(f"• {r['nome']}" for r in encontrados)
            if not mensagens.confirmar(
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
            mensagens.info("Aviso", "\n".join(recusas))
            return False
        ids = [r["id"] for r in prontos]
        if not self.app.gravar(self.app.banco.registrar_saidas, ids,
                               momento.strftime(FORMATO)):
            return False
        self.app.atualizar_tabela()
        primeiros = [r["nome"].split()[0] for r in prontos]
        nomes = primeiros[-1]
        if len(primeiros) > 1:
            nomes = ", ".join(primeiros[:-1]) + " e " + nomes
        texto = f"✓ Saída de {nomes} registrada às {momento:%H:%M}."
        if recusas:
            texto += f"  ({len(recusas)} já tinha(m) saída.)"
        self.avisar(texto, desfazer=ids)
        return True

    def desfazer_saida(self):
        ids = self._para_desfazer
        if not ids:
            return
        ok, desfeitas = self.app.tentar(self.app.banco.desfazer_saidas, ids,
                                        autor=self.app.autor)
        if not ok:
            return
        self.app.recarregar_registros()
        self.app.atualizar_tabela()
        if desfeitas < len(ids):
            mensagens.aviso("Desfazer", "Não foi possível desfazer a saída de "
                                        "quem já tem outra entrada depois desta.")
        self.avisar("↺ Saída desfeita — a pessoa voltou a constar no campus."
                    if desfeitas else "")

    # --------------------------------------------------------------
    # Aviso que some sozinho (com o botão Desfazer, se for o caso)
    # --------------------------------------------------------------
    def avisar(self, texto, desfazer=None):
        """Mensagem que some sozinha; com `desfazer`, mostra o botão Desfazer."""
        if self._timer_aviso:
            self.aba.after_cancel(self._timer_aviso)
        self.lbl_aviso.config(text=texto)
        self._para_desfazer = desfazer
        if desfazer:
            self.btn_desfazer.pack(side="left", padx=(8, 0))
        else:
            self.btn_desfazer.pack_forget()
        self._timer_aviso = self.aba.after(SEGUNDOS_PARA_DESFAZER * 1000,
                                           self._esconder_aviso)

    def _esconder_aviso(self):
        self._timer_aviso = None
        self._para_desfazer = None
        self.lbl_aviso.config(text="")
        self.btn_desfazer.pack_forget()
