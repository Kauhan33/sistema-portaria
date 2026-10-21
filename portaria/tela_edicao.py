"""
Janela "Corrigir registro": corrige erro de digitação numa visita e mostra
o histórico daquele registro (quem cadastrou, deu saída, corrigiu e o quê).

Privacidade: o porteiro vê o CPF mascarado (***.982.247-**) e somente
leitura. Para corrigir um CPF digitado errado ele clica no lápis do campo
e digita o número inteiro de novo (com o documento em mãos).
"""

import tkinter as tk

from . import horarios, mensagens
from .componentes import (Aviso, Campo, Dialogo, preencher_eventos,
                          rotulo_campo, tabela_eventos)
from .consultas import descrever_alteracoes
from .estilo import COR, FONTE, ICONE, px
from .tela_autorizacao import autorizar_excecao
from .usuarios import eh_admin, pode_editar
from .validacao import (FORMATO_EXIBICAO, TIPOS_ACESSO,
                        checar_bloqueio_correcao, mascarar_cpf, normalizar,
                        validar)

SEM_HISTORICO = {"momento": "—", "usuario": "—", "acao": "Sem histórico",
                 "detalhe": "registro anterior ao histórico"}
DICA_DETALHE = "Clique numa linha para ver o detalhe completo."


class JanelaEdicao(Dialogo):
    def __init__(self, app, registro):
        self.app = app
        self.original = registro
        self.cpf_oculto = not eh_admin(app.usuario)   # porteiro: mascarado
        super().__init__(app.janela, f"Corrigir registro #{registro['id']}",
                         f"Entrada de {registro['nome']} em {registro['entrada']}."
                         " Toda correção fica no histórico.", largura=780,
                         ao_usar=app.registrar_uso)
        self._montar_campos()
        self._montar_historico()
        self.adicionar_botao("Salvar correção", self.salvar, "primario",
                             dica_tecla="Enter")
        self.adicionar_botao("Cancelar", self.fechar)
        self.abrir(confirmar=self.salvar, foco=self.nome)

    def _montar_campos(self):
        form = tk.Frame(self.miolo, bg=COR["superficie"])
        form.pack(fill="x")
        form.columnconfigure((0, 1, 2, 3), weight=1, uniform="e")
        r = self.original

        def novo(texto, linha, coluna, valor, apoio="", juntas=1, **opcoes):
            espaco = (0, px(12)) if coluna + juntas < 4 else 0
            frame, _ = rotulo_campo(form, texto, apoio)
            frame.grid(row=linha, column=coluna, sticky="w", pady=(0, px(4)),
                       padx=espaco)
            campo = Campo(form, **opcoes)
            campo.grid(row=linha + 1, column=coluna, columnspan=juntas,
                       sticky="ew", pady=(0, px(12)), padx=espaco)
            campo.var.set(valor or "")      # valor do banco, sem passar pela digitação
            return campo

        # Q04: CPF, celular e placa com as mesmas restrições da Entrada e
        # saída. Duas linhas de 4 colunas: cabe num notebook 1366x768 a 125%
        if self.cpf_oculto:
            self.cpf = novo("CPF", 0, 0, mascarar_cpf(r["cpf"]), "lápis = trocar",
                            numeros=11, icone=ICONE["editar"],
                            acao_icone=self.liberar_cpf).entrada
            self.cpf.config(state="readonly", fg=COR["texto_2"],
                            readonlybackground=COR["superficie"])
        else:
            self.cpf = novo("CPF", 0, 0, r["cpf"], numeros=11).entrada
        self.nome = novo("Nome completo", 0, 1, r["nome"], juntas=2).entrada
        self.celular = novo("Celular", 0, 3, r["celular"], "só números",
                            numeros=11).entrada
        campo_placa = novo("Placa", 2, 0, r.get("placa", ""), "opcional",
                           placa=True)
        self.var_placa, self.caixa_placa = campo_placa.var, campo_placa.entrada
        self.tipo = novo("Tipo de acesso", 2, 1, r["tipo"],
                         opcoes=TIPOS_ACESSO).entrada
        self.entrada = novo("Entrada", 2, 2, r["entrada"], FORMATO_EXIBICAO,
                            seletor="data_hora", relogio=self.app.relogio).entrada
        self.saida = novo("Saída", 2, 3, r["saida"], "vazio = no campus",
                          seletor="data_hora", relogio=self.app.relogio).entrada
        self.cpf.config(font=FONTE["cpf"])

    def _montar_historico(self):
        tk.Label(self.miolo, text="Histórico deste registro", font=FONTE["rotulo"],
                 bg=COR["superficie"], fg=COR["texto"]
                 ).pack(anchor="w", pady=(px(6), px(6)))
        moldura = tk.Frame(self.miolo, bg=COR["superficie"],
                           highlightbackground=COR["borda"], highlightthickness=1)
        moldura.pack(fill="x")
        quadro, self.historico = tabela_eventos(
            moldura, (140, 80, 160, 260), altura=2, compacta=True)
        quadro.pack(fill="x")
        # detalhe completo da linha clicada (a coluna corta textos longos)
        self.faixa = Aviso(self.miolo)
        self.faixa.mostrar("neutro", DICA_DETALHE)
        self.faixa.pack(fill="x", pady=(px(10), 0))
        self.lbl_detalhe = self.faixa.lbl
        self.historico.bind("<<TreeviewSelect>>", self.mostrar_detalhe)
        ok, eventos = self.app.tentar(self.app.banco.eventos_do_registro,
                                      self.original["id"])
        if not ok:
            return
        preencher_eventos(self.historico, eventos or [SEM_HISTORICO])

    def mostrar_detalhe(self, event=None):
        selecao = self.historico.selection()
        if selecao:
            valores = self.historico.item(selecao[0])["values"]
            momento, usuario, acao, detalhe = valores
            self.faixa.mostrar("info", f"{acao} por {usuario} em {momento}: "
                                       f"{detalhe}")

    # --------------------------------------------------------------
    # Ações
    # --------------------------------------------------------------
    def liberar_cpf(self):
        """Lápis do campo CPF (porteiro): apaga o CPF mascarado e deixa
        digitar o número certo."""
        if not self.cpf_oculto:
            return
        self.cpf_oculto = False
        self.cpf.config(state="normal", fg=COR["texto"])
        self.cpf.delete(0, tk.END)
        # o Tk desliga a validação quando recebe um texto que não passaria
        # nela (a máscara): religa a regra "só dígitos"
        self.cpf.config(validate="key")
        self.cpf.focus_set()

    def salvar(self):
        cpf = self.original["cpf"] if self.cpf_oculto else self.cpf.get()
        novo = normalizar(self.nome.get(), cpf, self.celular.get(),
                          self.var_placa.get(), self.tipo.get(),
                          self.entrada.get(), self.saida.get())
        alteracoes = descrever_alteracoes(self.original, novo)
        if not alteracoes:
            mensagens.info("Corrigir registro", "Nada foi alterado.",
                           parent=self.janela)
            return
        # o porteiro também não pode mover o registro para outro dia
        agora = self.app.relogio()
        ok, msg = pode_editar(self.app.usuario, novo, agora)
        if ok:
            ok, anteriores = self.app.tentar(self.app.banco.listar_por_cpf,
                                             novo["cpf"])
            if not ok:
                return
            outros = [r for r in anteriores if r["id"] != self.original["id"]]
            ok, msg = validar(novo, outros, agora)
        if not ok:
            mensagens.erro("Dados inválidos", msg, parent=self.janela)
            return
        ok, ativos = self.app.tentar(self.app.banco.listar_bloqueios)
        if not ok:
            return
        ok, msg = checar_bloqueio_correcao(self.original, novo, ativos)
        if not ok:
            mensagens.erro("Acesso negado", msg, parent=self.janela)
            return
        autorizacao, ok = self._autorizar(novo, agora)
        if not ok:
            return
        # `original`: se outra estação mudou a visita depois que esta janela
        # abriu (ex.: deu a saída), o banco recusa em vez de desfazer aquilo
        if not self.app.gravar(self.app.banco.editar, self.original["id"],
                               novo, alteracoes, autorizacao=autorizacao,
                               original=self.original):
            return
        self.app.atualizar_tabela()
        self.app.avisar(f"Registro de {novo['nome'].split()[0]} corrigido "
                        f"({len(alteracoes)} alteração(ões)).")
        self.fechar()

    def _autorizar(self, novo, agora):
        """Correção que vira exceção de horário (entrada movida para fora
        do horário, retroativa antiga, mais de 24 h) pede a autorização.
        Devolve (autorização ou None, pode seguir?)."""
        ok, config = self.app.tentar(self.app.banco.ler_configuracao)
        if not ok:
            return None, False
        regras = horarios.excecoes_da_correcao(config, self.original, novo, agora)
        if not regras:
            return None, True
        autorizacao = autorizar_excecao(
            self.app, regras, f"A correção do registro de {novo['nome']}",
            dono=self.janela)
        return autorizacao, autorizacao is not None
