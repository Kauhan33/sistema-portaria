"""
Página Ocorrências (desafio extra do A3, RN49): o livro da portaria. Qualquer
usuário registra e resolve; só o administrador exclui (RN02). A ocorrência pode
citar um CPF e uma placa, conferidos como no Cadastro; o CPF aparece mascarado
para o porteiro (RN14), inclusive se foi digitado no meio da descrição.
"""

import tkinter as tk

from . import mensagens
from .componentes import (Aviso, Botao, Cabecalho, Campo, CampoTexto, Cartao,
                          Contador, Dialogo, EsperaDigitacao, campo_rotulado,
                          checkbutton, inserir_linha, plural, rotulo_campo,
                          tabela, titulo_cartao)
from .estilo import COR, FONTE, ICONE, MARGEM, px
from .usuarios import pode_excluir
from .validacao import (CATEGORIAS_OCORRENCIA, MAXIMO_BUSCA, MAXIMO_OCORRENCIA,
                        MAXIMO_RECADO, formatar_placa, validar_ocorrencia,
                        validar_recado)

TODAS = "Todas as categorias"
FILTROS = [TODAS] + CATEGORIAS_OCORRENCIA
COLUNAS = [("numero", "Nº", 52, "center"), ("momento", "Quando", 124, "w"),
           ("categoria", "Categoria", 150, "w"),
           ("texto", "Descrição", 320, "w"), ("cpf", "CPF", 118, "w"),
           ("placa", "Placa", 84, "w"), ("autor", "Registrou", 100, "w")]
ABERTA, RESOLVIDA = "Aberta", "Resolvida"
DICA = "Selecione uma ocorrência para ler a descrição inteira."


class DialogoOcorrencia(Dialogo):
    """Nova ocorrência: categoria, descrição e, se houver, CPF e placa."""

    def __init__(self, pagina):
        self.pagina = pagina
        app = pagina.app
        super().__init__(app.janela, "Nova ocorrência",
                         "Fica no livro da portaria, com o seu usuário e a "
                         "hora de agora.", largura=480,
                         ao_usar=app.registrar_uso)
        form = self.miolo
        form.columnconfigure((0, 1), weight=1, uniform="o")
        grupo, c = campo_rotulado(form, "Categoria *",
                                  opcoes=CATEGORIAS_OCORRENCIA)
        grupo.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, px(12)))
        self.categoria = c.entrada
        linha, _ = rotulo_campo(form, "Descrição *")
        linha.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, px(4)))
        self.texto = CampoTexto(form, MAXIMO_OCORRENCIA, linhas=4)
        self.texto.grid(row=2, column=0, columnspan=2, sticky="ew",
                        pady=(0, px(12)))
        self.texto.bind_enter(self.salvar)
        Contador(linha, self.texto).pack(side="right")
        grupo, c = campo_rotulado(form, "CPF", "opcional", numeros=11)
        grupo.grid(row=3, column=0, sticky="ew", padx=(0, px(10)),
                   pady=(0, px(12)))
        self.cpf = c.entrada
        grupo, c = campo_rotulado(form, "Placa", "opcional", placa=True)
        grupo.grid(row=3, column=1, sticky="ew", pady=(0, px(12)))
        self.placa = c.entrada
        self.faixa = Aviso(form)
        self.adicionar_botao("Registrar", self.salvar, "primario")
        self.adicionar_botao("Cancelar", self.fechar)
        self.abrir(confirmar=self.salvar, foco=self.categoria)

    def salvar(self):
        """Grava; devolve True se gravou."""
        app = self.pagina.app
        ok, msg = validar_ocorrencia(self.categoria.get(), self.texto.get(),
                                     self.cpf.get().strip(),
                                     self.placa.get().strip())
        if not ok:
            self.faixa.mostrar("erro", msg)
            self.faixa.grid(row=4, column=0, columnspan=2, sticky="ew")
            return False
        ok, _ = app.tentar(app.banco.registrar_ocorrencia, self.categoria.get(),
                           self.texto.get(), app.autor, cpf=self.cpf.get(),
                           placa=self.placa.get())
        if not ok:
            return False
        self.fechar()
        self.pagina.atualizar()
        self.pagina.aviso("sucesso", "Ocorrência registrada.")
        return True


class DialogoRecado(Dialogo):
    """Recado para o próximo turno: aparece no Controle de acesso de quem
    entrar depois, até alguém marcar como lido."""

    def __init__(self, pagina):
        self.pagina = pagina
        app = pagina.app
        super().__init__(app.janela, "Recado para o próximo turno",
                         "Fica à vista no Controle de acesso até alguém "
                         "marcar como lido.", largura=480,
                         ao_usar=app.registrar_uso)
        linha, _ = rotulo_campo(self.miolo, "Recado *")
        linha.pack(fill="x", pady=(0, px(4)))
        self.texto = CampoTexto(self.miolo, MAXIMO_RECADO, linhas=4)
        self.texto.pack(fill="x", pady=(0, px(12)))
        self.texto.bind_enter(self.salvar)
        Contador(linha, self.texto).pack(side="right")
        self.faixa = Aviso(self.miolo)
        self.adicionar_botao("Deixar recado", self.salvar, "primario")
        self.adicionar_botao("Cancelar", self.fechar)
        self.abrir(confirmar=self.salvar, foco=self.texto)

    def salvar(self):
        app = self.pagina.app
        texto = " ".join(self.texto.get().split())
        ok, msg = validar_recado(texto)
        if not ok:
            self.faixa.mostrar("erro", msg)
            self.faixa.pack(fill="x")
            return False
        ok, _ = app.tentar(app.banco.deixar_recado, texto, app.autor)
        if not ok:
            return False
        self.fechar()
        app.tela_cadastro.atualizar_alertas()
        self.pagina.aviso("sucesso", "Recado deixado para o próximo turno.")
        return True


class AbaOcorrencias:
    def __init__(self, aba, app):
        self.aba = aba
        self.app = app
        self.ocorrencias = []
        self.dialogo = None

        cab = Cabecalho(aba, "Ocorrências").posicionar()
        self.lbl_total = cab.subtitulo
        self.btn_nova = Botao(cab.acoes, "Nova ocorrência", self.nova,
                              "primario", icone=ICONE["mais"],
                              fundo_pai=COR["fundo"])
        self.btn_nova.pack(side="right")
        self.btn_recado = Botao(cab.acoes, "Recado de turno", self.novo_recado,
                                "secundario", fundo_pai=COR["fundo"])
        self.btn_recado.pack(side="right", padx=(0, px(8)))

        cartao = Cartao(aba, pad=0)
        cartao.pack(fill="both", expand=True, padx=px(MARGEM),
                    pady=(0, px(MARGEM)))
        m = cartao.miolo
        m.pack_configure(padx=px(1), pady=px(8))
        barra = tk.Frame(m, bg=COR["superficie"])
        barra.pack(fill="x", padx=px(19), pady=(px(6), px(10)))
        titulo_cartao(barra, "Livro da portaria").pack(side="left")
        campo = Campo(barra, largura=240, icone=ICONE["busca"],
                      dica_vazio="Pesquisar", maximo=MAXIMO_BUSCA)
        campo.pack(side="left", padx=(px(16), px(10)))
        self.busca = campo.entrada
        self.espera_busca = EsperaDigitacao(self.busca, self.atualizar)
        campo = Campo(barra, opcoes=FILTROS, largura=190)
        campo.pack(side="left", padx=(0, px(10)))
        self.filtro = campo.entrada
        self.filtro.set(TODAS)
        self.filtro.bind("<<ComboboxSelected>>", lambda e: self.atualizar())
        self.var_abertas = tk.BooleanVar(aba, False)
        self.chk_abertas = checkbutton(barra, "Só abertas", self.var_abertas,
                                       self.atualizar)
        self.chk_abertas.pack(side="left")

        rodape = tk.Frame(m, bg=COR["superficie"])
        rodape.pack(side="bottom", fill="x", padx=px(19), pady=(px(8), px(10)))
        self.btn_resolver = Botao(rodape, "Marcar como resolvida", self.resolver,
                                  "secundario", icone=ICONE["ok"])
        self.btn_resolver.pack(side="left")
        self.btn_excluir = None
        if pode_excluir(app.usuario):       # RN02: o porteiro nem vê o botão
            self.btn_excluir = Botao(rodape, "Excluir", self.excluir, "perigo",
                                     icone=ICONE["lixo"])
            self.btn_excluir.pack(side="left", padx=(px(8), 0))
        self.faixa = Aviso(m)
        self.faixa.pack(side="bottom", fill="x", padx=px(19))
        self.faixa.mostrar("neutro", DICA)

        quadro, self.tabela = tabela(m, COLUNAS, situacao="Situação",
                                     largura_situacao=100, altura=8)
        quadro.pack(fill="both", expand=True, padx=px(12))
        self.tabela.bind("<<TreeviewSelect>>", lambda e: self._ao_selecionar())
        self.atualizar()

    def aviso(self, tipo, texto):
        self.faixa.mostrar(tipo, texto)

    def atualizar(self):
        """Relê o livro do banco, com a pesquisa e os filtros da tela."""
        filtro = self.filtro.get()
        ok, ocorrencias = self.app.tentar(
            self.app.banco.listar_ocorrencias, texto=self.busca.get(),
            categoria=None if filtro == TODAS else filtro,
            so_abertas=self.var_abertas.get())
        if not ok:
            return
        self.ocorrencias = ocorrencias
        selecao = self.tabela.selection()
        self.tabela.delete(*self.tabela.get_children())
        for i, o in enumerate(ocorrencias):
            aberta = not o["resolvida_em"]
            inserir_linha(self.tabela, i, (
                o["id"], o["momento"], o["categoria"], o["texto"],
                self.app.exibir_cpf(o["cpf"]) if o["cpf"] else "—",
                formatar_placa(o["placa"]) if o["placa"] else "—", o["autor"]),
                iid=str(o["id"]), situacao=ABERTA if aberta else RESOLVIDA,
                cor=COR["alerta"] if aberta else COR["sucesso"])
        if selecao and self.tabela.exists(selecao[0]):
            self.tabela.selection_set(selecao[0])
        abertas = sum(1 for o in ocorrencias if not o["resolvida_em"])
        self.lbl_total.config(text=plural(len(ocorrencias), "ocorrência",
                                          "ocorrências")
                              + f"  ·  {plural(abertas, 'aberta', 'abertas')}")
        self._ao_selecionar()

    def _selecionada(self):
        selecao = self.tabela.selection()
        if not selecao:
            return None
        return next((o for o in self.ocorrencias if str(o["id"]) == selecao[0]),
                    None)

    def _ao_selecionar(self):
        o = self._selecionada()
        self.btn_resolver.definir_ativo(bool(o) and not o["resolvida_em"])
        if self.btn_excluir is not None:
            self.btn_excluir.definir_ativo(bool(o))
        if o is None:
            self.faixa.mostrar("neutro", DICA)
            return
        texto = f"Nº {o['id']}: {o['texto']}"
        if o["resolvida_em"]:
            texto += (f"\nResolvida em {o['resolvida_em']} por "
                      f"{o['resolvida_por']}.")
        self.faixa.mostrar("neutro", texto)

    def nova(self):
        self.dialogo = DialogoOcorrencia(self)
        return self.dialogo

    def novo_recado(self):
        self.dialogo = DialogoRecado(self)
        return self.dialogo

    def resolver(self):
        o = self._selecionada()
        if o is None:
            return
        ok, _ = self.app.tentar(self.app.banco.resolver_ocorrencia, o["id"],
                                self.app.autor)
        self.atualizar()
        if ok:
            self.aviso("sucesso", f"Ocorrência nº {o['id']} marcada como "
                                  "resolvida.")

    def excluir(self):
        o = self._selecionada()
        if o is None or self.btn_excluir is None:
            return
        if not self.app.perguntar(
                mensagens.confirmar, "Excluir ocorrência",
                f"Excluir a ocorrência nº {o['id']} ({o['categoria']})?\n"
                "A exclusão não pode ser desfeita e fica no histórico."):
            return
        ok, _ = self.app.tentar(self.app.banco.excluir_ocorrencia, o["id"],
                                self.app.autor)
        self.atualizar()
        if ok:
            self.aviso("sucesso", f"Ocorrência nº {o['id']} excluída.")
