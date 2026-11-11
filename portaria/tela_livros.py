"""
Páginas dos desafios extras da versão 3.2, todas no mesmo molde (PaginaLista):
cabeçalho com a contagem e o botão de criar, um cartão com pesquisa, filtro,
tabela, a linha de detalhe e as ações.

- Autorizações: visitantes autorizados e a emissão da autorização de entrada
  (uma página para imprimir, impressao.py).
- Encomendas: o que chegou e quem retirou.
- Chaves: com quem está cada chave, entrega e devolução.

Como no resto do sistema, a tela só organiza: quem confere as regras e as
permissões é o banco (dados_modulos.py).
"""

import tkinter as tk

from . import impressao, mensagens
from .componentes import (Aviso, Botao, Cabecalho, Campo, CampoTexto, Cartao,
                          Contador, Dialogo, EsperaDigitacao, campo_rotulado,
                          checkbutton, inserir_linha, plural, rotulo_campo,
                          tabela, titulo_cartao)
from .estilo import COR, ICONE, MARGEM, px
from .usuarios import eh_admin
from .validacao import (AUT_CANCELADA, AUT_FUTURA, AUT_VALIDA, AUT_VENCIDA,
                        FUNCIONARIO, MAXIMO_ANFITRIAO, MAXIMO_BUSCA,
                        MAXIMO_CARGO, MAXIMO_CHAVE, MAXIMO_DESCRICAO_ENCOMENDA,
                        MAXIMO_EMPRESA, MAXIMO_LOCAL, MAXIMO_MATRICULA,
                        MAXIMO_MOTIVO_VISITA, MAXIMO_NOME, MAXIMO_REMETENTE,
                        MAXIMO_SETOR, cpf_valido, normalizar, so_digitos,
                        validar_campos, validar_chave, validar_encomenda,
                        validar_funcionario, validar_quem_retira)

FORMATO_DIA = "%d/%m/%Y"


class PaginaLista:
    """O molde das páginas de lista. A página filha diz o que muda:
    TITULO, TITULO_CARTAO, NOVO (texto do botão de criar), COLUNAS,
    SITUACAO (título e largura da 1ª coluna), DICA e FILTRO (texto da caixa
    de seleção), e os métodos listar, linha, resumo, detalhe e acoes."""

    TITULO = TITULO_CARTAO = NOVO = DICA = FILTRO = ""
    COLUNAS = []
    SITUACAO = ("Situação", 110)

    def __init__(self, aba, app):
        self.aba, self.app = aba, app
        self.itens, self.dialogo, self.botoes = [], None, {}

        cab = Cabecalho(aba, self.TITULO).posicionar()
        self.lbl_total = cab.subtitulo
        self.btn_novo = None
        if self.pode_criar():
            self.btn_novo = Botao(cab.acoes, self.NOVO, self.novo, "primario",
                                  icone=ICONE["mais"], fundo_pai=COR["fundo"])
            self.btn_novo.pack()

        cartao = Cartao(aba, pad=0)
        cartao.pack(fill="both", expand=True, padx=px(MARGEM),
                    pady=(0, px(MARGEM)))
        m = cartao.miolo
        m.pack_configure(padx=px(1), pady=px(8))
        barra = tk.Frame(m, bg=COR["superficie"])
        barra.pack(fill="x", padx=px(19), pady=(px(6), px(10)))
        titulo_cartao(barra, self.TITULO_CARTAO).pack(side="left")
        campo = Campo(barra, largura=260, icone=ICONE["busca"],
                      dica_vazio="Pesquisar", maximo=MAXIMO_BUSCA)
        campo.pack(side="left", padx=(px(16), px(12)))
        self.busca = campo.entrada
        self.espera_busca = EsperaDigitacao(self.busca, self.atualizar)
        self.var_filtro = tk.BooleanVar(aba, False)
        self.chk_filtro = checkbutton(barra, self.FILTRO, self.var_filtro,
                                      self.atualizar)
        self.chk_filtro.pack(side="left")

        self.rodape = tk.Frame(m, bg=COR["superficie"])
        self.rodape.pack(side="bottom", fill="x", padx=px(19),
                         pady=(px(8), px(10)))
        self.acoes(self.rodape)
        self.faixa = Aviso(m)
        self.faixa.pack(side="bottom", fill="x", padx=px(19))
        self.faixa.mostrar("neutro", self.DICA)

        quadro, self.tabela = tabela(m, self.COLUNAS, situacao=self.SITUACAO[0],
                                     largura_situacao=self.SITUACAO[1],
                                     altura=8)
        quadro.pack(fill="both", expand=True, padx=px(12))
        self.tabela.bind("<<TreeviewSelect>>", lambda e: self._ao_selecionar())
        self.atualizar()

    # --- o que cada página diz -----------------------------------------
    def pode_criar(self):
        return True

    def acoes(self, rodape):
        """Monta os botões do pé com self.botao(...)."""

    def listar(self):
        raise NotImplementedError

    def linha(self, item):
        """(valores das colunas, texto da situação, cor da bolinha)."""
        raise NotImplementedError

    def resumo(self, itens):
        return plural(len(itens), "item", "itens")

    def detalhe(self, item):
        return ""

    def habilitados(self, item):
        """{nome do botão: pode usar com este item selecionado}."""
        return {}

    # --- peças ---------------------------------------------------------
    def botao(self, nome, texto, comando, variante="secundario", icone=None,
              lado="left"):
        b = Botao(self.rodape, texto, comando, variante,
                  icone=ICONE[icone] if icone else None)
        b.pack(side=lado, padx=(0, px(8)) if lado == "left" else 0)
        self.botoes[nome] = b
        return b

    def aviso(self, tipo, texto):
        self.faixa.mostrar(tipo, texto)

    def selecionado(self):
        selecao = self.tabela.selection()
        if not selecao:
            return None
        return next((i for i in self.itens if str(i["id"]) == selecao[0]), None)

    def atualizar(self):
        """Relê a lista do banco, com a pesquisa e o filtro da tela."""
        ok, itens = self.app.tentar(self.listar)
        if not ok:
            return
        self.itens = itens
        selecao = self.tabela.selection()
        self.tabela.delete(*self.tabela.get_children())
        for n, item in enumerate(itens):
            valores, situacao, cor = self.linha(item)
            inserir_linha(self.tabela, n, valores, iid=str(item["id"]),
                          situacao=situacao, cor=cor)
        if selecao and self.tabela.exists(selecao[0]):
            self.tabela.selection_set(selecao[0])
        self.lbl_total.config(text=self.resumo(itens))
        self._ao_selecionar()

    def _ao_selecionar(self):
        item = self.selecionado()
        usar = self.habilitados(item) if item else {}
        for nome, b in self.botoes.items():
            if nome in self.SEMPRE:
                continue
            b.definir_ativo(bool(item) and usar.get(nome, True))
        self.faixa.mostrar("neutro", self.detalhe(item) if item else self.DICA)

    SEMPRE = ()         # botões que não dependem de uma linha selecionada

    def executar(self, operacao, *args, sucesso="", **kwargs):
        """Roda no banco, relê a lista e mostra o aviso verde."""
        ok, _ = self.app.tentar(operacao, *args, **kwargs)
        self.atualizar()
        if ok and sucesso:
            self.aviso("sucesso", sucesso)
        return ok

    def cpf(self, cpf):
        return self.app.exibir_cpf(cpf) if cpf else "—"


class DialogoSimples(Dialogo):
    """Diálogo com campos empilhados, a faixa de erro e os botões."""

    def __init__(self, pagina, titulo, subtitulo, confirmar_texto, largura=440):
        self.pagina, self.app = pagina, pagina.app
        super().__init__(self.app.janela, titulo, subtitulo, largura=largura,
                         ao_usar=self.app.registrar_uso)
        self.miolo.columnconfigure((0, 1), weight=1, uniform="d")
        self.linha_atual = 0
        self.faixa = Aviso(self.miolo)
        self.adicionar_botao(confirmar_texto, self.salvar, "primario")
        self.adicionar_botao("Cancelar", self.fechar)

    def campo(self, texto, apoio="", juntas=2, coluna=0, **opcoes):
        grupo, c = campo_rotulado(self.miolo, texto, apoio, **opcoes)
        grupo.grid(row=self.linha_atual, column=coluna, columnspan=juntas,
                   sticky="ew", pady=(0, px(12)),
                   padx=(0, px(10)) if juntas == 1 and coluna == 0 else 0)
        if coluna + juntas >= 2:
            self.linha_atual += 1
        return c

    def texto_longo(self, texto, maximo, linhas=3):
        rotulo, _ = rotulo_campo(self.miolo, texto)
        rotulo.grid(row=self.linha_atual, column=0, columnspan=2, sticky="ew",
                    pady=(0, px(4)))
        caixa = CampoTexto(self.miolo, maximo, linhas=linhas)
        caixa.grid(row=self.linha_atual + 1, column=0, columnspan=2,
                   sticky="ew", pady=(0, px(12)))
        caixa.bind_enter(self.salvar)
        Contador(rotulo, caixa).pack(side="right")
        self.linha_atual += 2
        return caixa

    def erro(self, texto):
        self.faixa.mostrar("erro", texto)
        self.faixa.grid(row=self.linha_atual + 5, column=0, columnspan=2,
                        sticky="ew")
        return False

    def puxar_pessoa(self, var_cpf, destinos):
        """CPF completo de quem já tem cadastro preenche os campos vazios
        (`destinos`: {chave do cadastro: caixa})."""
        def ao_digitar(*_):
            cpf = so_digitos(var_cpf.get())
            if len(cpf) != 11 or not cpf_valido(cpf):
                return
            ok, pessoa = self.app.tentar(self.app.banco.buscar_pessoa, cpf)
            if ok and pessoa:
                for chave, caixa in destinos.items():
                    if not caixa.get().strip() and pessoa.get(chave):
                        caixa.insert(0, pessoa[chave])
        var_cpf.trace_add("write", ao_digitar)

    def salvar(self):
        raise NotImplementedError


class DialogoQuemRetira(DialogoSimples):
    """Quem está levando (a chave ou a encomenda): nome e, se quiser, CPF."""

    def __init__(self, pagina, titulo, subtitulo, confirmar_texto, ao_confirmar):
        super().__init__(pagina, titulo, subtitulo, confirmar_texto)
        self.ao_confirmar = ao_confirmar
        c = self.campo("CPF", "opcional", numeros=11)
        self.cpf = c.entrada
        self.nome = self.campo("Nome completo *", maximo=MAXIMO_NOME).entrada
        self.puxar_pessoa(c.var, {"nome": self.nome})
        self.abrir(confirmar=self.salvar, foco=self.cpf)

    def salvar(self):
        nome, cpf = " ".join(self.nome.get().split()), self.cpf.get().strip()
        ok, msg = validar_quem_retira(nome, cpf)
        if not ok:
            return self.erro(msg)
        self.fechar()
        self.ao_confirmar(nome, cpf)
        return True


# ----------------------------------------------------------------------
# Chaves
# ----------------------------------------------------------------------
class DialogoChave(DialogoSimples):
    def __init__(self, pagina):
        super().__init__(pagina, "Nova chave",
                         "Cadastre cada chave que fica na portaria.",
                         "Cadastrar")
        self.nome = self.campo("Nome da chave *", "ex.: Laboratório 2",
                               maximo=MAXIMO_CHAVE).entrada
        self.local = self.campo("Local", "opcional", maximo=MAXIMO_LOCAL).entrada
        self.abrir(confirmar=self.salvar, foco=self.nome)

    def salvar(self):
        nome = " ".join(self.nome.get().split())
        local = " ".join(self.local.get().split())
        ok, msg = validar_chave(nome, local)
        if not ok:
            return self.erro(msg)
        ok, _ = self.app.tentar(self.app.banco.cadastrar_chave, nome, local,
                                self.app.autor)
        if not ok:
            return False
        self.fechar()
        self.pagina.atualizar()
        self.pagina.aviso("sucesso", f"Chave \"{nome}\" cadastrada.")
        return True


class DialogoHistoricoChaves(Dialogo):
    """As últimas entregas e devoluções (só leitura)."""

    COLUNAS = [("chave", "Chave", 150, "w"), ("nome", "Com quem", 170, "w"),
               ("retirada", "Retirada", 124, "w"),
               ("devolucao", "Devolução", 124, "w"),
               ("por", "Entregue por", 100, "w")]

    def __init__(self, pagina):
        app = pagina.app
        super().__init__(app.janela, "Histórico das chaves",
                         "As 200 entregas mais recentes.", largura=700,
                         ao_usar=app.registrar_uso)
        quadro, self.tabela = tabela(self.miolo, self.COLUNAS, altura=10)
        quadro.pack(fill="both", expand=True)
        ok, historico = app.tentar(app.banco.historico_de_chaves)
        for n, h in enumerate(historico if ok else []):
            inserir_linha(self.tabela, n, (
                h["chave"], h["nome"], h["retirada_em"],
                h["devolvida_em"] or "com a pessoa", h["entregue_por"]))
        self.adicionar_botao("Fechar", self.fechar)
        self.abrir()


class AbaChaves(PaginaLista):
    TITULO, TITULO_CARTAO, NOVO = "Chaves", "Chaves da portaria", "Nova chave"
    FILTRO = "Só emprestadas"
    DICA = "Selecione uma chave para entregar ou registrar a devolução."
    SITUACAO = ("Situação", 120)
    COLUNAS = [("nome", "Chave", 190, "w"), ("local", "Local", 190, "w"),
               ("quem", "Com quem", 190, "w"), ("desde", "Desde", 130, "w")]
    NA_PORTARIA, EMPRESTADA = "Na portaria", "Emprestada"
    SEMPRE = ("historico",)

    def pode_criar(self):                 # o cadastro das chaves é do admin
        return eh_admin(self.app.usuario)

    def acoes(self, rodape):
        self.btn_entregar = self.botao("entregar", "Entregar chave",
                                       self.entregar, "primario")
        self.btn_devolver = self.botao("devolver", "Registrar devolução",
                                       self.devolver, icone="ok")
        self.btn_historico = self.botao("historico", "Ver histórico",
                                        self.ver_historico, "fantasma")
        self.btn_remover = None
        if eh_admin(self.app.usuario):
            self.btn_remover = self.botao("remover", "Remover", self.remover,
                                          "perigo", icone="lixo", lado="right")

    def listar(self):
        return self.app.banco.listar_chaves(self.busca.get(),
                                            self.var_filtro.get())

    def linha(self, c):
        emprestada = c["emprestada"]
        return ((c["nome"], c["local"] or "—", c["com_quem"] or "—",
                 c["desde"] or "—"),
                self.EMPRESTADA if emprestada else self.NA_PORTARIA,
                COR["alerta"] if emprestada else COR["sucesso"])

    def resumo(self, itens):
        fora = sum(1 for c in itens if c["emprestada"])
        return (plural(len(itens), "chave", "chaves") + "  ·  "
                + plural(fora, "emprestada", "emprestadas"))

    def detalhe(self, c):
        if not c["emprestada"]:
            return f"{c['nome']}: na portaria."
        return (f"{c['nome']}: com {c['com_quem']} (CPF {self.cpf(c['cpf'])}) "
                f"desde {c['desde']}, entregue por {c['entregue_por']}.")

    def habilitados(self, c):
        return {"entregar": not c["emprestada"], "devolver": c["emprestada"],
                "remover": not c["emprestada"]}

    def novo(self):
        self.dialogo = DialogoChave(self)
        return self.dialogo

    def entregar(self):
        c = self.selecionado()
        if c is None or c["emprestada"]:
            return None
        self.dialogo = DialogoQuemRetira(
            self, "Entregar chave", f"Quem está levando a chave \"{c['nome']}\"?",
            "Entregar",
            lambda nome, cpf: self.executar(
                self.app.banco.entregar_chave, c["id"], nome, self.app.autor,
                cpf, sucesso=f"Chave \"{c['nome']}\" entregue a {nome}."))
        return self.dialogo

    def devolver(self):
        c = self.selecionado()
        if c is not None:
            self.executar(self.app.banco.devolver_chave, c["id"],
                          self.app.autor,
                          sucesso=f"Chave \"{c['nome']}\" devolvida.")

    def ver_historico(self):
        self.dialogo = DialogoHistoricoChaves(self)
        return self.dialogo

    def remover(self):
        c = self.selecionado()
        if c is None or self.btn_remover is None:
            return
        if self.app.perguntar(
                mensagens.confirmar, "Remover chave",
                f"Remover a chave \"{c['nome']}\" da lista?\nO histórico das "
                "entregas continua guardado."):
            self.executar(self.app.banco.desativar_chave, c["id"],
                          self.app.autor,
                          sucesso=f"Chave \"{c['nome']}\" removida.")


# ----------------------------------------------------------------------
# Encomendas
# ----------------------------------------------------------------------
class DialogoEncomenda(DialogoSimples):
    def __init__(self, pagina):
        super().__init__(pagina, "Nova encomenda",
                         "O que chegou na portaria e para quem.", "Registrar",
                         largura=480)
        self.destinatario = self.campo("Destinatário *", "pessoa ou setor",
                                       juntas=1, maximo=MAXIMO_NOME).entrada
        self.setor = self.campo("Setor ou bloco", "opcional", juntas=1,
                                coluna=1, maximo=MAXIMO_LOCAL).entrada
        self.remetente = self.campo("Remetente *", "quem mandou ou a "
                                    "transportadora",
                                    maximo=MAXIMO_REMETENTE).entrada
        self.descricao = self.texto_longo("Descrição",
                                          MAXIMO_DESCRICAO_ENCOMENDA, linhas=2)
        self.abrir(confirmar=self.salvar, foco=self.destinatario)

    def salvar(self):
        campos = [" ".join(c.get().split()) for c in
                  (self.destinatario, self.remetente, self.setor,
                   self.descricao)]
        ok, msg = validar_encomenda(*campos)
        if not ok:
            return self.erro(msg)
        destinatario, remetente, setor, descricao = campos
        ok, _ = self.app.tentar(self.app.banco.registrar_encomenda,
                                destinatario, remetente, self.app.autor,
                                setor=setor, descricao=descricao)
        if not ok:
            return False
        self.fechar()
        self.pagina.atualizar()
        self.pagina.aviso("sucesso", f"Encomenda para {destinatario} "
                                     "registrada.")
        return True


class AbaEncomendas(PaginaLista):
    TITULO, TITULO_CARTAO = "Encomendas", "Encomendas recebidas"
    NOVO, FILTRO = "Nova encomenda", "Só aguardando retirada"
    DICA = "Selecione uma encomenda para registrar a retirada."
    SITUACAO = ("Situação", 150)
    COLUNAS = [("numero", "Nº", 50, "center"),
               ("recebida", "Recebida em", 124, "w"),
               ("destinatario", "Destinatário", 180, "w"),
               ("setor", "Setor", 110, "w"), ("remetente", "Remetente", 140, "w"),
               ("retirada", "Retirada por", 150, "w")]
    AGUARDANDO, RETIRADA = "Aguardando retirada", "Retirada"

    def acoes(self, rodape):
        self.btn_retirar = self.botao("retirar", "Registrar retirada",
                                      self.retirar, "primario")
        self.btn_excluir = None
        if eh_admin(self.app.usuario):
            self.btn_excluir = self.botao("excluir", "Excluir", self.excluir,
                                          "perigo", icone="lixo", lado="right")

    def listar(self):
        return self.app.banco.listar_encomendas(self.busca.get(),
                                                self.var_filtro.get())

    def linha(self, e):
        aguardando = not e["retirada_em"]
        return ((e["id"], e["recebida_em"], e["destinatario"],
                 e["setor"] or "—", e["remetente"], e["retirada_nome"] or "—"),
                self.AGUARDANDO if aguardando else self.RETIRADA,
                COR["alerta"] if aguardando else COR["sucesso"])

    def resumo(self, itens):
        aguardando = sum(1 for e in itens if not e["retirada_em"])
        return (plural(len(itens), "encomenda", "encomendas") + "  ·  "
                + plural(aguardando, "aguardando retirada",
                         "aguardando retirada"))

    def detalhe(self, e):
        texto = (f"Nº {e['id']}: {e['descricao'] or 'sem descrição'}. Recebida "
                 f"por {e['recebida_por']}.")
        if e["retirada_em"]:
            texto += (f"\nRetirada em {e['retirada_em']} por "
                      f"{e['retirada_nome']} (CPF {self.cpf(e['retirada_cpf'])})"
                      f", entregue por {e['entregue_por']}.")
        return texto

    def habilitados(self, e):
        return {"retirar": not e["retirada_em"]}

    def novo(self):
        self.dialogo = DialogoEncomenda(self)
        return self.dialogo

    def retirar(self):
        e = self.selecionado()
        if e is None or e["retirada_em"]:
            return None
        self.dialogo = DialogoQuemRetira(
            self, "Registrar retirada",
            f"Quem está retirando a encomenda de {e['destinatario']}?",
            "Registrar retirada",
            lambda nome, cpf: self.executar(
                self.app.banco.retirar_encomenda, e["id"], nome,
                self.app.autor, cpf,
                sucesso=f"Encomenda nº {e['id']} retirada por {nome}."))
        return self.dialogo

    def excluir(self):
        e = self.selecionado()
        if e is None or self.btn_excluir is None:
            return
        if self.app.perguntar(
                mensagens.confirmar, "Excluir encomenda",
                f"Excluir a encomenda nº {e['id']} (para {e['destinatario']})?"
                "\nA exclusão não pode ser desfeita e fica no histórico."):
            self.executar(self.app.banco.excluir_encomenda, e["id"],
                          self.app.autor,
                          sucesso=f"Encomenda nº {e['id']} excluída.")


# ----------------------------------------------------------------------
# Autorizações de entrada (visitantes autorizados)
# ----------------------------------------------------------------------
class DialogoAutorizacao(DialogoSimples):
    def __init__(self, pagina):
        super().__init__(pagina, "Nova autorização de entrada",
                         "Quem um setor avisou que vai receber. Na chegada, o "
                         "Cadastro mostra a autorização pelo CPF.",
                         "Autorizar", largura=520)
        hoje = self.app.relogio().date()
        c = self.campo("CPF *", "só números", juntas=1, numeros=11)
        self.cpf = c.entrada
        self.nome = self.campo("Nome completo *", juntas=1, coluna=1,
                               maximo=MAXIMO_NOME).entrada
        self.empresa = self.campo("Empresa", "opcional", juntas=1,
                                  maximo=MAXIMO_EMPRESA).entrada
        self.anfitriao = self.campo("Autorizado por *", "pessoa ou setor",
                                    juntas=1, coluna=1,
                                    maximo=MAXIMO_ANFITRIAO).entrada
        self.de = self.campo("Válida de *", "dd/mm/aaaa", juntas=1,
                             seletor="data", relogio=self.app.relogio).entrada
        self.ate = self.campo("Até *", "dd/mm/aaaa", juntas=1, coluna=1,
                              seletor="data", relogio=self.app.relogio).entrada
        for caixa in (self.de, self.ate):
            caixa.insert(0, hoje.strftime(FORMATO_DIA))
        self.motivo = self.texto_longo("Motivo *", MAXIMO_MOTIVO_VISITA,
                                       linhas=2)
        self.puxar_pessoa(c.var, {"nome": self.nome, "empresa": self.empresa})
        self.abrir(confirmar=self.salvar, foco=self.cpf)

    def salvar(self):
        nome = " ".join(self.nome.get().split())
        ok, id_ = self.app.tentar(
            self.app.banco.criar_autorizacao, self.cpf.get(), nome,
            self.empresa.get(), self.motivo.get(), self.anfitriao.get(),
            self.de.get(), self.ate.get(), self.app.autor)
        if not ok:
            return False
        self.fechar()
        self.pagina.atualizar()
        self.pagina.tabela.selection_set(str(id_))
        self.pagina.aviso("sucesso", f"Autorização nº {id_:03d} criada para "
                                     f"{nome}. Use Emitir para imprimir.")
        return True


class AbaAutorizacoes(PaginaLista):
    TITULO, TITULO_CARTAO = "Autorizações", "Visitantes autorizados"
    NOVO, FILTRO = "Nova autorização", "Só válidas hoje"
    DICA = "Selecione uma autorização para emitir, registrar a entrada ou cancelar."
    SITUACAO = ("Situação", 110)
    COLUNAS = [("numero", "Nº", 50, "center"), ("nome", "Nome", 170, "w"),
               ("cpf", "CPF", 118, "w"), ("empresa", "Empresa", 130, "w"),
               ("anfitriao", "Autorizado por", 130, "w"),
               ("periodo", "Válida", 150, "w"), ("usos", "Entradas", 70, "center")]
    CORES = {AUT_VALIDA: "sucesso", AUT_FUTURA: "info", AUT_VENCIDA: "barra",
             AUT_CANCELADA: "erro"}

    def acoes(self, rodape):
        self.btn_emitir = self.botao("emitir", "Emitir autorização",
                                     self.emitir, "primario")
        self.btn_entrada = self.botao("entrada", "Registrar entrada",
                                      self.registrar_entrada)
        self.btn_cancelar = self.botao("cancelar", "Cancelar autorização",
                                       self.cancelar, "perigo", lado="right")

    def listar(self):
        return self.app.banco.listar_autorizacoes(
            self.busca.get(), self.var_filtro.get(),
            so_cpf_completo=not eh_admin(self.app.usuario))

    def linha(self, a):
        periodo = (a["valida_de"] if a["valida_de"] == a["valida_ate"]
                   else f"{a['valida_de'][:5]} a {a['valida_ate']}")
        return ((f"{a['id']:03d}", a["nome"], self.cpf(a["cpf"]),
                 a["empresa"] or "—", a["anfitriao"], periodo, a["usos"]),
                a["situacao"], COR[self.CORES[a["situacao"]]])

    def resumo(self, itens):
        validas = sum(1 for a in itens if a["situacao"] == AUT_VALIDA)
        return (plural(len(itens), "autorização", "autorizações") + "  ·  "
                + plural(validas, "válida hoje", "válidas hoje"))

    def detalhe(self, a):
        texto = (f"Nº {a['id']:03d}: {a['motivo']}. Criada por "
                 f"{a['criada_por']} em {a['criada_em']}.")
        if a["cancelada_em"]:
            texto += (f"\nCancelada em {a['cancelada_em']} por "
                      f"{a['cancelada_por']}.")
        elif a["ultimo_uso"]:
            texto += f"\nÚltima entrada: {a['ultimo_uso']}."
        return texto

    def habilitados(self, a):
        ativa = a["situacao"] in (AUT_VALIDA, AUT_FUTURA)
        return {"emitir": ativa, "cancelar": ativa,
                "entrada": a["situacao"] == AUT_VALIDA}

    def novo(self):
        self.dialogo = DialogoAutorizacao(self)
        return self.dialogo

    def emitir(self):
        """Desafio extra: emissão da autorização de entrada (para imprimir)."""
        a = self.selecionado()
        if a is None or a["situacao"] not in (AUT_VALIDA, AUT_FUTURA):
            return None
        ok, _ = self.app.tentar(self.app.banco.registrar_emissao, a["id"],
                                self.app.autor)
        if not ok:
            self.atualizar()
            return None
        pagina = impressao.autorizacao_html(
            a, self.cpf(a["cpf"]), self.app.usuario["nome"], self.app.relogio())
        caminho = impressao.abrir(pagina, "autorizacao", self.app.janela)
        self.atualizar()
        self.aviso("sucesso", f"Autorização nº {a['id']:03d} aberta no "
                              "navegador para imprimir.")
        return caminho

    def registrar_entrada(self):
        """Abre o Cadastro com a pessoa da autorização (o CPF traz o resto)."""
        a = self.selecionado()
        if a is not None and a["situacao"] == AUT_VALIDA:
            self.app.preencher_pessoa({"cpf": a["cpf"]})

    def cancelar(self):
        a = self.selecionado()
        if a is None:
            return
        if self.app.perguntar(
                mensagens.confirmar, "Cancelar autorização",
                f"Cancelar a autorização nº {a['id']:03d} de {a['nome']}?\n"
                "Ela deixa de valer na hora e continua na lista."):
            self.executar(self.app.banco.cancelar_autorizacao, a["id"],
                          self.app.autor,
                          sucesso=f"Autorização nº {a['id']:03d} cancelada.")


# ----------------------------------------------------------------------
# Funcionários
# ----------------------------------------------------------------------
class DialogoFuncionario(DialogoSimples):
    """Novo funcionário (cadastra a pessoa, do tipo Funcionário, com a
    matrícula, o setor e o cargo) ou os dados de um que já existe."""

    def __init__(self, pagina, funcionario=None):
        self.funcionario = f = funcionario
        super().__init__(
            pagina, "Dados do funcionário" if f else "Novo funcionário",
            f"{f['nome']}: matrícula, setor e cargo." if f else
            "Cadastra a pessoa como Funcionário. A entrada não é registrada.",
            "Salvar" if f else "Cadastrar", largura=480)
        self.cpf = self.nome = self.celular = self.empresa = None
        if f is None:
            self.cpf = self.campo("CPF *", "só números", juntas=1,
                                  numeros=11).entrada
            self.celular = self.campo("Telefone *", "com DDD", juntas=1,
                                      coluna=1, numeros=11).entrada
            self.nome = self.campo("Nome completo *",
                                   maximo=MAXIMO_NOME).entrada
            self.empresa = self.campo("Empresa *", "ex.: a própria universidade",
                                      maximo=MAXIMO_EMPRESA).entrada
        self.matricula = self.campo("Matrícula", "opcional", juntas=1,
                                    maximo=MAXIMO_MATRICULA).entrada
        self.setor = self.campo("Setor", "opcional", juntas=1, coluna=1,
                                maximo=MAXIMO_SETOR).entrada
        self.cargo = self.campo("Cargo", "opcional", maximo=MAXIMO_CARGO).entrada
        if f is not None:
            for caixa, chave in ((self.matricula, "matricula"),
                                 (self.setor, "setor"), (self.cargo, "cargo")):
                caixa.insert(0, f[chave])
        self.abrir(confirmar=self.salvar,
                   foco=self.cpf if f is None else self.matricula)

    def salvar(self):
        app = self.app
        extras = [" ".join(c.get().split()) for c in
                  (self.matricula, self.setor, self.cargo)]
        ok, msg = validar_funcionario(*extras)
        if not ok:
            return self.erro(msg)
        if self.funcionario is not None:
            id_pessoa, nome = self.funcionario["id"], self.funcionario["nome"]
        else:
            pessoa = normalizar(self.nome.get(), self.cpf.get(),
                                self.celular.get(), "", FUNCIONARIO, "", "",
                                empresa=self.empresa.get())
            ok, msg = validar_campos(pessoa)
            if not ok:
                return self.erro(msg)
            ok, existente = app.tentar(app.banco.buscar_pessoa, pessoa["cpf"])
            if not ok:
                return False
            if existente:
                return self.erro(f"Este CPF já é de {existente['nome']} "
                                 f"({existente['tipo']}). Para torná-lo "
                                 "funcionário, edite o cadastro em Pessoas.")
            ok, _ = app.tentar(app.banco.cadastrar_pessoa, pessoa["cpf"],
                               pessoa["nome"], pessoa["celular"], [],
                               FUNCIONARIO, app.autor,
                               empresa=pessoa["empresa"])
            if not ok:
                return False
            ok, criada = app.tentar(app.banco.buscar_pessoa, pessoa["cpf"])
            if not ok or not criada:
                return False
            id_pessoa, nome = criada["id"], criada["nome"]
            app.atualizar_contadores()
        ok, _ = app.tentar(app.banco.salvar_funcionario, id_pessoa, *extras,
                           app.autor)
        self.fechar()
        self.pagina.atualizar()
        if ok:
            self.pagina.aviso("sucesso", f"Dados de {nome} salvos.")
        return ok


class AbaFuncionarios(PaginaLista):
    """Desafio extra: controle de funcionários. Quem é do tipo Funcionário,
    com a matrícula, o setor, o cargo e o ponto de hoje."""

    TITULO, TITULO_CARTAO = "Funcionários", "Quadro de funcionários"
    NOVO, FILTRO = "Novo funcionário", "Só quem está dentro"
    DICA = "Selecione um funcionário para registrar a entrada ou ver os dados."
    SITUACAO = ("Hoje", 120)
    COLUNAS = [("nome", "Nome", 180, "w"), ("matricula", "Matrícula", 90, "w"),
               ("setor", "Setor", 130, "w"), ("cargo", "Cargo", 130, "w"),
               ("entrada", "Entrada", 80, "w"), ("saida", "Saída", 80, "w")]
    DENTRO, SAIU, NAO_VEIO = "Dentro", "Saiu", "Não veio"

    def acoes(self, rodape):
        self.btn_entrada = self.botao("entrada", "Registrar entrada",
                                      self.registrar_entrada, "primario")
        self.btn_dados = self.botao("dados", "Dados do funcionário",
                                    self.editar_dados, icone="editar")

    def listar(self):
        funcionarios = self.app.banco.listar_funcionarios(self.busca.get())
        if self.var_filtro.get():
            funcionarios = [f for f in funcionarios if f["dentro_desde"]]
        return funcionarios

    def situacao(self, f):
        if f["dentro_desde"]:
            return self.DENTRO
        return self.SAIU if f["entrada_hoje"] else self.NAO_VEIO

    def linha(self, f):
        situacao = self.situacao(f)
        return ((f["nome"], f["matricula"] or "—", f["setor"] or "—",
                 f["cargo"] or "—", f["entrada_hoje"][-5:] or "—",
                 f["saida_hoje"][-5:] or "—"), situacao,
                COR["sucesso"] if situacao == self.DENTRO else COR["barra"])

    def resumo(self, itens):
        dentro = sum(1 for f in itens if f["dentro_desde"])
        return (plural(len(itens), "funcionário", "funcionários") + "  ·  "
                + plural(dentro, "dentro agora", "dentro agora"))

    def detalhe(self, f):
        texto = f"{f['nome']}  ·  CPF {self.cpf(f['cpf'])}"
        if f["dentro_desde"]:
            texto += f"\nDentro desde {f['dentro_desde']}."
        return texto

    def habilitados(self, f):
        return {"entrada": not f["dentro_desde"]}

    def novo(self):
        self.dialogo = DialogoFuncionario(self)
        return self.dialogo

    def editar_dados(self):
        f = self.selecionado()
        if f is None:
            return None
        self.dialogo = DialogoFuncionario(self, f)
        return self.dialogo

    def registrar_entrada(self):
        f = self.selecionado()
        if f is not None and not f["dentro_desde"]:
            self.app.preencher_pessoa({"cpf": f["cpf"]})
