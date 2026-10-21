"""
Página "Entrada e saída" (antiga aba Cadastro): registrar a entrada de uma
pessoa (com preenchimento automático pelo CPF, faixa de situação e alerta
de bloqueio), dar saída (saída rápida F2 por CPF ou placa, botão ou duplo
clique), desfazer a saída, corrigir e excluir registros.

A tabela "Movimento" mostra o dia: as entradas e saídas de hoje e todo
mundo que ainda está no campus (app.registros = banco.listar_movimento).
Com texto na busca, ela procura no histórico inteiro (banco.buscar_registros).

Regras de horário (horarios.py): entrada fora do horário da categoria,
retroativa antiga ou visita acima de 24 h é uma EXCEÇÃO e pede a
autorização do administrador (tela_autorizacao.py). A situação de cada
visita aberta é calculada com o relógio do app: "Tempo excedido" (âmbar)
e "Saída pendente" (vermelho, depois do fechamento do dia da entrada).
Faixas no topo da página avisam as saídas pendentes (o administrador
encerra o dia) e quando o campus está perto de fechar.

Fala com a janela principal só pelo contrato público do app (ver
interface.py).
"""

import tkinter as tk
from datetime import datetime

from . import horarios, mensagens
from .componentes import (Aviso, Botao, Cabecalho, Campo, Cartao, Placa, link,
                          data_por_extenso, inserir_linha, plural,
                          rotulo_campo, tabela, titulo_cartao)
from .consultas import encontrar_dentro
from .estilo import (COR, CORES_TIPO, ESPACO_CARTOES, FONTE, ICONE, MARGEM,
                     fonte_icone, px)
from .tela_autorizacao import autorizar_excecao
from .tela_edicao import JanelaEdicao
from .usuarios import eh_admin, pode_editar, pode_excluir
from .validacao import (FORMATO, FORMATO_EXIBICAO, PLACA_OBRIGATORIA,
                        TIPOS_ACESSO, checar_bloqueio, checar_saida,
                        cpf_valido, formatar_celular, formatar_cpf,
                        formatar_placa, normalizar, placa_valida, so_digitos,
                        validar)

DICA_CPF = "Digite o CPF primeiro: quem já veio tem os dados preenchidos."
DICA_PLACA = "obrigatória" if PLACA_OBRIGATORIA else "opcional"
SEGUNDOS_PARA_DESFAZER = 10
SAIDA_JA_FEITA = ("Essa visita já tinha saída ou foi excluída em outra "
                  "estação. A tabela foi atualizada.")
LIMITE_BUSCA = 200
COLUNAS = [("Nome", "Nome", 170, "w"), ("CPF", "CPF", 118, "w"),
           ("Celular", "Celular", 112, "w"), ("Placa", "Placa", 86, "w"),
           ("Tipo", "Tipo de acesso", 150, "w"),
           ("Entrada", "Entrada", 128, "w"), ("Saida", "Saída", 128, "w")]
# o celular continua nos values (mesma linha de antes), mas não aparece
COLUNAS_VISIVEIS = ("Nome", "CPF", "Placa", "Tipo", "Entrada", "Saida")

# Abaixo desta altura da página (px lógicos) o layout fica compacto: num
# notebook 1366x768 a 125% a página tem uns 540 (670 px reais).
ALTURA_CONFORTAVEL = 740
# Posição (linha, coluna, colunas ocupadas) de cada campo, com o rótulo na
# linha de cima: (layout normal, layout compacto)
GRADE = {
    "cpf": ((0, 0, 1), (0, 0, 1)),
    "nome": ((0, 1, 2), (0, 1, 2)),
    "celular": ((3, 0, 1), (0, 3, 1)),
    "placa": ((3, 1, 1), (3, 0, 1)),
    "tipo": ((3, 2, 1), (3, 1, 1)),
    "entrada": ((5, 0, 1), (3, 2, 1)),
    "saida": ((5, 1, 1), (3, 3, 1)),
}
# Espaços (px lógicos) de cada densidade
ESPACOS = {
    "normal": {"topo": (20, 16), "cartao": 18, "titulo": 10,
               "movimento": (ESPACO_CARTOES, MARGEM), "miolo_mov": 8,
               "barra": (6, 12), "rodape": (8, 2)},
    "compacta": {"topo": (8, 8), "cartao": 12, "titulo": 6,
                 "movimento": (8, 12), "miolo_mov": 4,
                 "barra": (2, 6), "rodape": (4, 0)},
}


# Situação da visita -> (cor da bolinha, marca da linha em destaque)
APARENCIA = {horarios.NO_CAMPUS: (COR["sucesso"], None),
             horarios.TEMPO_EXCEDIDO: (COR["alerta"], "excedido"),
             horarios.SAIDA_PENDENTE: (COR["erro"], "pendente"),
             horarios.SAIU: (COR["barra"], None)}
LARGURA_SITUACAO = 132         # cabe "Saída pendente" com a bolinha
MOSTRAR_NO_ENCERRAMENTO = 8    # nomes listados na confirmação


def _px(par):
    """(antes, depois) em px lógicos -> px reais."""
    return tuple(px(n) for n in par)


class AbaCadastro:
    def __init__(self, aba, app):
        self.aba = aba
        self.app = app
        self.janela_edicao = None     # janela "Corrigir registro" aberta
        self.mostrados = {}           # id -> registro das linhas da tabela
        self._auto = None   # o que foi preenchido sozinho, para poder desfazer
        self._timer_aviso = None
        self._para_desfazer = None          # ids da última saída gravada aqui
        self._saida_para_desfazer = None    # e o horário dela
        self.pecas, self.apoios = {}, {}    # rótulo e campo do formulário
        self.compacta = None                # densidade em uso
        self.config = None                  # horários em vigor (horarios.py)

        self._montar_cabecalho()
        self._montar_alertas()
        self._montar_formulario()
        self._montar_movimento()
        self._aplicar_densidade(False)
        self.aba.bind("<Configure>", self._ao_redimensionar)

    # --------------------------------------------------------------
    # Montagem
    # --------------------------------------------------------------
    def _montar_cabecalho(self):
        """Título, data e quantos estão no campus; à direita a saída rápida
        (a ação mais usada da guarita: F2 leva o cursor até ela)."""
        cab = Cabecalho(self.aba, "Entrada e saída").posicionar()
        self.cabecalho = cab
        self.lbl_no_campus = tk.Label(cab.linha, font=FONTE["corpo_semi"],
                                      bg=COR["fundo"], fg=COR["sucesso"])
        self.lbl_no_campus.pack(side="left")

        tk.Label(cab.acoes, text="Saída rápida (F2)", font=FONTE["rotulo"],
                 bg=COR["fundo"], fg=COR["texto_2"]).pack(anchor="w",
                                                          pady=(0, px(4)))
        linha = tk.Frame(cab.acoes, bg=COR["fundo"])
        linha.pack()
        campo = Campo(linha, fundo_pai=COR["fundo"], largura=230,
                      icone=ICONE["busca"], acao_icone=self.saida_rapida,
                      dica_vazio="CPF ou placa")
        campo.pack(side="left")
        self.campo_saida_rapida = campo.entrada
        self.campo_saida_rapida.bind("<Return>", self.saida_rapida)
        self.campo_saida_rapida.bind("<KP_Enter>", self.saida_rapida)
        Botao(linha, "Registrar saída", self.saida_rapida, "secundario",
              fundo_pai=COR["fundo"], dica_tecla="Enter"
              ).pack(side="left", padx=(px(8), 0))

    def _montar_alertas(self):
        """Faixas que só aparecem quando importam (sem caixa de diálogo):
        saídas pendentes e o campus perto de fechar."""
        self.alertas = tk.Frame(self.aba, bg=COR["fundo"])
        self.alertas.pack(fill="x", padx=px(MARGEM))
        self.faixa_pendentes = Aviso(self.alertas, fundo_pai=COR["fundo"])
        self.faixa_fechamento = Aviso(self.alertas, fundo_pai=COR["fundo"])

    def _montar_formulario(self):
        """Cartão "Nova entrada". As peças são criadas aqui e posicionadas
        por _aplicar_densidade (normal ou compacta, conforme a altura)."""
        self.cartao_form = Cartao(self.aba, pad=ESPACOS["normal"]["cartao"])
        self.cartao_form.pack(fill="x", padx=px(MARGEM))
        m = self.cartao_form.miolo
        self.cab_form = tk.Frame(m, bg=COR["superficie"])
        self.cab_form.pack(fill="x")
        self.titulo_form = titulo_cartao(self.cab_form, "Nova entrada")
        corpo = tk.Frame(m, bg=COR["superficie"])
        corpo.pack(fill="x")
        self.ficha = tk.Frame(corpo, bg=COR["superficie"], width=px(214))
        self.divisor_ficha = tk.Frame(corpo, bg=COR["borda"], width=1)
        self.form = form = tk.Frame(corpo, bg=COR["superficie"])
        form.pack(side="left", fill="x", expand=True)

        # CPF primeiro: é por ele que a pessoa é reconhecida
        self.var_cpf = tk.StringVar(self.aba)
        self.cpf = self._peca("cpf", "CPF", Campo(form, numeros=11, var=self.var_cpf))
        self.nome = self._peca("nome", "Nome completo", Campo(form))
        self.celular = self._peca("celular", "Celular com DDD",
                                  Campo(form, numeros=11), "só números")
        campo_placa = Campo(form, placa=True)
        self.var_placa = campo_placa.var
        self._peca("placa", "Placa", campo_placa, DICA_PLACA)
        self.lbl_dica_placa = self.apoios["placa"]
        self.tipo = self._peca("tipo", "Tipo de acesso",
                               Campo(form, opcoes=TIPOS_ACESSO))
        self.entrada = self._peca("entrada", "Entrada", self._campo_data(form),
                                  FORMATO_EXIBICAO)
        self.saida = self._peca("saida", "Saída", self._campo_data(form),
                                "vazio = no campus")

        # Faixa de situação da pessoa (neutra, nova, já veio, no campus,
        # bloqueada), o botão principal e o "Limpar": filhos do cartão para
        # poderem ir para a grade do formulário ou para a linha do título
        self.aviso_pessoa = Aviso(m)
        self.lbl_pessoa = self.aviso_pessoa.lbl
        self.btn_cadastrar = Botao(m, "Registrar entrada", self.cadastrar,
                                   "primario", dica_tecla="Enter")
        self.btn_limpar = Botao(m, "Limpar formulário", self.limpar, "fantasma",
                                altura=30)

        self._montar_ficha()
        # Liga o preenchimento automático e os alertas só depois de tudo montado
        self.var_cpf.trace_add("write", self._ao_digitar_cpf)
        self.var_placa.trace_add("write", self._ao_digitar_placa)

    def _peca(self, chave, texto, campo, apoio=""):
        """Rótulo + campo do formulário (posicionados depois, pela GRADE)."""
        rotulo, self.apoios[chave] = rotulo_campo(self.form, texto, apoio)
        self.pecas[chave] = (rotulo, campo)
        return campo.entrada

    # --------------------------------------------------------------
    # Densidade: normal ou compacta (tela baixa)
    # --------------------------------------------------------------
    def _ao_redimensionar(self, event):
        if event.widget is self.aba:
            self._aplicar_densidade(event.height < px(ALTURA_CONFORTAVEL))

    def _aplicar_densidade(self, compacta):
        """
        Normal: formulário em 3 colunas com a ficha da pessoa à direita.
        Compacta (página baixa, ex.: notebook 1366x768 a 125%): 4 colunas,
        sem a ficha, a faixa de situação no lugar do título do cartão,
        espaços menores e linhas da tabela mais baixas, para o Movimento
        continuar mostrando umas 4 linhas.
        """
        if compacta == self.compacta:
            return
        self.compacta = compacta
        e = ESPACOS["compacta" if compacta else "normal"]
        self.cabecalho.pack_configure(pady=_px(e["topo"]))
        self.cartao_form.miolo.pack_configure(padx=px(e["cartao"]),
                                              pady=px(e["cartao"]))
        self.cab_form.pack_configure(pady=(0, px(e["titulo"])))
        self._posicionar_formulario(compacta)
        self.cartao_mov.pack_configure(pady=_px(e["movimento"]))
        self.cartao_mov.miolo.pack_configure(pady=px(e["miolo_mov"]))
        self.barra_mov.pack_configure(pady=_px(e["barra"]))
        self.rodape_mov.pack_configure(pady=_px(e["rodape"]))
        self.tabela.configure(style="Compacta.Tabela.Treeview" if compacta
                              else "Tabela.Treeview")

    def _posicionar_formulario(self, compacta):
        for w in (self.titulo_form, self.btn_limpar, self.btn_cadastrar,
                  self.aviso_pessoa, self.ficha, self.divisor_ficha):
            w.pack_forget()
            w.grid_forget()
        colunas = 4 if compacta else 3
        self.form.columnconfigure((0, 1, 2), weight=1, uniform="f")
        self.form.columnconfigure(3, weight=1 if compacta else 0,
                                  uniform="f" if compacta else "")
        # espaço antes da 2ª linha de campos (compacta) ou da linha da
        # Entrada/Saída (normal: a 2ª linha já vem depois da faixa)
        self.form.grid_rowconfigure(3, pad=px(12) if compacta else 0)
        self.form.grid_rowconfigure(5, pad=0 if compacta else px(14))
        for chave, (rotulo, campo) in self.pecas.items():
            linha, coluna, juntas = GRADE[chave][1 if compacta else 0]
            rotulo.grid(row=linha, column=coluna, sticky="w", pady=(0, px(4)))
            campo.grid(row=linha + 1, column=coluna, columnspan=juntas,
                       sticky="ew",
                       padx=(0, px(12) if coluna + juntas < colunas else 0))
        if compacta:
            self.btn_limpar.definir_texto("Limpar")
            self.btn_cadastrar.pack(in_=self.cab_form, side="right")
            self.btn_limpar.pack(in_=self.cab_form, side="right",
                                 padx=(0, px(8)))
            self.aviso_pessoa.pack(in_=self.cab_form, side="left", fill="x",
                                   expand=True, padx=(0, px(16)))
            return
        self.titulo_form.pack(side="left")
        self.btn_limpar.definir_texto("Limpar formulário")
        self.btn_limpar.pack(in_=self.cab_form, side="right")
        self.aviso_pessoa.grid(in_=self.form, row=2, column=0, columnspan=3,
                               sticky="ew", pady=(px(10), px(14)))
        self.btn_cadastrar.grid(in_=self.form, row=6, column=2, sticky="ew")
        self.ficha.pack(side="right", fill="y", before=self.form)
        self.divisor_ficha.pack(side="right", fill="y", padx=px(20),
                                before=self.form)

    def _campo_data(self, form):
        """Campo de data/hora; o relógio dentro dele põe a hora de agora."""
        def preencher_agora():
            campo.entrada.delete(0, tk.END)
            campo.entrada.insert(0, self._agora_texto())

        campo = Campo(form, icone=ICONE["relogio"], acao_icone=preencher_agora)
        return campo

    def _montar_ficha(self):
        """Coluna da direita: a placa desenhada e o histórico da pessoa."""
        f, fundo = self.ficha, COR["superficie"]
        f.pack_propagate(False)
        tk.Label(f, text="Veículo", font=FONTE["rotulo"], bg=fundo,
                 fg=COR["texto"]).pack(anchor="w", pady=(0, px(6)))
        self.desenho_placa = Placa(f, fundo, largura=200)
        self.desenho_placa.pack(anchor="w")
        self.lbl_placa_status = tk.Label(f, text="", font=FONTE["rotulo"],
                                         bg=fundo, fg=COR["erro"],
                                         wraplength=px(200), justify="left")
        self.lbl_placa_status.pack(anchor="w")
        tk.Frame(f, bg=COR["borda"], height=1).pack(fill="x", pady=px(14))
        tk.Label(f, text="Histórico da pessoa", font=FONTE["rotulo"], bg=fundo,
                 fg=COR["texto"]).pack(anchor="w")
        numeros = tk.Frame(f, bg=fundo)
        numeros.pack(anchor="w", fill="x", pady=(px(6), 0))
        self.lbl_visitas = self._numero(numeros, "visitas")
        self.lbl_ultima = self._numero(numeros, "última vinda")
        self.chip_tipo = tk.Frame(f, bg=fundo)
        self.lbl_ponto_tipo = tk.Label(self.chip_tipo, text=chr(0x25CF),
                                       font=FONTE["dica"], bg=fundo)
        self.lbl_ponto_tipo.pack(side="left")
        self.lbl_tipo = tk.Label(self.chip_tipo, font=FONTE["corpo_semi"],
                                 bg=fundo, fg=COR["texto"])
        self.lbl_tipo.pack(side="left", padx=(px(4), 0))

    @staticmethod
    def _numero(pai, legenda):
        bloco = tk.Frame(pai, bg=COR["superficie"])
        bloco.pack(side="left", padx=(0, px(28)))
        valor = tk.Label(bloco, text="—", font=FONTE["numero"],
                         bg=COR["superficie"], fg=COR["texto"])
        valor.pack(anchor="w")
        tk.Label(bloco, text=legenda, font=FONTE["dica"], bg=COR["superficie"],
                 fg=COR["texto_3"]).pack(anchor="w")
        return valor

    def _montar_movimento(self):
        self.cartao_mov = Cartao(self.aba, pad=0)
        self.cartao_mov.pack(fill="both", expand=True, padx=px(MARGEM))
        m = self.cartao_mov.miolo
        m.pack_configure(padx=px(1))
        self.barra_mov = barra = tk.Frame(m, bg=COR["superficie"])
        barra.pack(fill="x", padx=px(19))
        titulo_cartao(barra, "Movimento").pack(side="left")
        campo_busca = Campo(barra, largura=300, icone=ICONE["busca"],
                            dica_vazio="Buscar no histórico: nome, CPF, placa…")
        campo_busca.pack(side="left", padx=(px(16), 0))
        self.busca = campo_busca.entrada
        self.busca.bind("<KeyRelease>", lambda e: self.atualizar_tabela())
        self.busca.bind("<Return>", lambda e: "break")   # Enter na busca não cadastra
        self.busca.bind("<KP_Enter>", lambda e: "break")

        self.btn_excluir = None
        if pode_excluir(self.app.usuario):  # RN02: o porteiro nem vê o botão
            self.btn_excluir = Botao(barra, "Excluir", self.excluir_selecionado,
                                     "perigo", icone=ICONE["lixo"])
            self.btn_excluir.pack(side="right")
        Botao(barra, "Corrigir", self.editar_selecionado, "secundario",
              icone=ICONE["editar"]).pack(side="right", padx=(0, px(8)))
        Botao(barra, "Registrar saída", self.registrar_saida, "secundario",
              icone=ICONE["seta"]).pack(side="right", padx=(0, px(8)))

        self.rodape_mov = rodape = tk.Frame(m, bg=COR["superficie"])
        rodape.pack(side="bottom", fill="x", padx=px(19))
        self.lbl_status = tk.Label(rodape, text="", font=FONTE["dica"],
                                   bg=COR["superficie"], fg=COR["texto_3"])
        self.lbl_status.pack(side="left")
        # aviso que some sozinho (com o Desfazer da saída)
        aviso = tk.Frame(rodape, bg=COR["superficie"])
        aviso.pack(side="right")
        self.lbl_aviso_icone = tk.Label(aviso, text="", font=fonte_icone(10),
                                        bg=COR["superficie"], fg=COR["sucesso"])
        self.lbl_aviso_icone.pack(side="left", padx=(0, px(6)))
        self.lbl_aviso = tk.Label(aviso, text="", font=FONTE["corpo_semi"],
                                  bg=COR["superficie"], fg=COR["sucesso"])
        self.lbl_aviso.pack(side="left")
        self.btn_desfazer = link(aviso, "Desfazer", self.desfazer_saida)

        quadro, self.tabela = tabela(m, COLUNAS, situacao="Situação",
                                     mostrar=COLUNAS_VISIVEIS,
                                     selecao="extended",
                                     largura_situacao=LARGURA_SITUACAO)
        quadro.pack(fill="both", expand=True, padx=px(12))
        self.tabela.bind("<Double-1>", self._ao_duplo_clique)
        # Enter com o foco na tabela não cadastra (o formulário está vazio)
        self.tabela.bind("<Return>", lambda e: "break")
        self.tabela.bind("<KP_Enter>", lambda e: "break")

    # --------------------------------------------------------------
    # Tabela
    # --------------------------------------------------------------
    def atualizar(self):
        """Página aberta: relê o movimento do banco."""
        self.app.recarregar_registros()
        self.atualizar_tabela()

    def _agora_texto(self):
        return self.app.relogio().strftime(FORMATO)

    def _situacao_da_visita(self, registro, agora):
        if self.config is None:          # sem a configuração: só dentro/saiu
            return horarios.SAIU if registro["saida"] else horarios.NO_CAMPUS
        return horarios.situacao(self.config, registro, agora)

    def atualizar_tabela(self):
        """Sem busca: o movimento (hoje + no campus). Com busca: o histórico."""
        ok, config = self.app.tentar(self.app.banco.ler_configuracao)
        if ok:
            self.config = config
        agora = self.app.relogio()
        texto = self.busca.get().strip()
        if texto:
            ok, registros = self.app.tentar(self.app.banco.buscar_registros,
                                            texto, LIMITE_BUSCA)
            if not ok:
                return
        else:
            registros = self.app.registros
        selecao = self.tabela.selection()
        self.tabela.delete(*self.tabela.get_children())
        self.mostrados = {}
        for i, r in enumerate(registros):
            self.mostrados[r["id"]] = r
            situacao = self._situacao_da_visita(r, agora)
            cor, destaque = APARENCIA[situacao]
            inserir_linha(self.tabela, i, (
                r["nome"],
                self.app.exibir_cpf(r.get("cpf", "")),
                formatar_celular(r.get("celular", "")),
                formatar_placa(r.get("placa", "")) or "—",
                r["tipo"],
                r["entrada"],
                r["saida"] or "—"), iid=str(r["id"]),
                situacao=situacao, cor=cor,
                tags=(destaque,) if destaque else (), zebra=not destaque)
        manter = [i for i in selecao if self.tabela.exists(i)]
        if manter:
            self.tabela.selection_set(manter)

        dentro = sum(1 for r in self.app.registros if not r["saida"])
        hoje = self.app.relogio().strftime("%d/%m/%Y")
        entradas_hoje = sum(1 for r in self.app.registros
                            if r["entrada"].startswith(hoje))
        if texto:
            status = plural(len(registros), "registro encontrado",
                            "registros encontrados") + " no histórico"
            if len(registros) >= LIMITE_BUSCA:
                status += f" (os {LIMITE_BUSCA} mais recentes)"
        else:
            status = (f"{plural(entradas_hoje, 'entrada', 'entradas')} hoje"
                      f"  ·  {dentro} no campus  ·  duplo clique registra a saída")
        self.lbl_status.config(text=status)
        self.cabecalho.subtitulo.config(
            text=data_por_extenso(self.app.relogio()) + "  ·  ")
        self.lbl_no_campus.config(
            text="Ninguém no campus agora" if not dentro else
            plural(dentro, "pessoa", "pessoas") + " no campus agora")
        self.atualizar_alertas()

    # --------------------------------------------------------------
    # Faixas: saídas pendentes e aviso antes de fechar
    # --------------------------------------------------------------
    def atualizar_alertas(self):
        """Recalcula as faixas com o relógio (também a cada 30 s, pelo app):
        não depende de alguém estar usando a tela na hora de fechar."""
        if self.config is None:
            return
        agora = self.app.relogio()
        contagem = horarios.contar_situacoes(self.config, self.app.registros,
                                             agora)
        pendentes = contagem[horarios.SAIDA_PENDENTE]
        if pendentes:
            admin = eh_admin(self.app.usuario)
            texto = (plural(pendentes, "saída pendente", "saídas pendentes")
                     + ": ficaram no campus depois do fechamento do dia da "
                       "entrada. Registre a saída de cada uma"
                     + (" ou encerre o dia." if admin
                        else " ou peça a um administrador para encerrar o dia."))
            self.faixa_pendentes.mostrar(
                "erro", texto, icone=ICONE["alerta"],
                acao="Encerrar o dia" if admin else None,
                comando=self.encerrar_dia)
        self._exibir(self.faixa_pendentes, pendentes > 0)

        minutos = horarios.minutos_para_fechar(self.config, agora)
        if minutos is not None:
            fecha = horarios.expediente(self.config, agora.date()).fecha
            dentro = sum(contagem.values())
            texto = (f"O campus fecha às {fecha:%H:%M} (em {minutos} min). "
                     + ("Ninguém no campus agora." if not dentro else
                        f"Ainda há {plural(dentro, 'pessoa', 'pessoas')} "
                        "no campus."))
            self.faixa_fechamento.mostrar("info", texto, icone=ICONE["relogio"])
        self._exibir(self.faixa_fechamento, minutos is not None)

    def _exibir(self, faixa, visivel):
        if visivel and not faixa.winfo_ismapped():
            faixa.pack(fill="x", pady=(0, px(8)))
        elif not visivel:
            faixa.pack_forget()

    def encerrar_dia(self):
        """Só administrador: saída automática de todas as saídas pendentes,
        no prazo de cada uma (o fechamento do dia da entrada)."""
        if not eh_admin(self.app.usuario):
            mensagens.erro("Acesso negado",
                           "Somente o administrador pode encerrar o dia.")
            return
        self.app.recarregar_registros()
        agora = self.app.relogio()
        pendentes = [r for r in self.app.registros
                     if self._situacao_da_visita(r, agora)
                     == horarios.SAIDA_PENDENTE]
        if not pendentes:
            mensagens.info("Encerrar o dia", "Não há saídas pendentes.")
            self.app.atualizar_tabela()
            return
        if not self.app.perguntar(mensagens.confirmar, "Encerrar o dia",
                                  self._texto_encerramento(pendentes)):
            return
        ok, encerradas = self.app.tentar(self.app.banco.encerrar_pendentes,
                                         agora, autor=self.app.autor)
        if not ok:
            return
        self.app.atualizar_tabela()
        self.avisar(plural(len(encerradas), "saída automática registrada",
                           "saídas automáticas registradas")
                    + " no encerramento do dia.")

    def _texto_encerramento(self, pendentes):
        linhas = []
        for r in pendentes[:MOSTRAR_NO_ENCERRAMENTO]:
            prazo = horarios.prazo_saida(self.config, r["tipo"],
                                         datetime.strptime(r["entrada"], FORMATO))
            linhas.append(f"• {r['nome']}: entrada {r['entrada']}, "
                          f"saída {prazo:{FORMATO}}")
        if len(pendentes) > MOSTRAR_NO_ENCERRAMENTO:
            linhas.append(f"• e mais {len(pendentes) - MOSTRAR_NO_ENCERRAMENTO}")
        return ("Dar saída automática a "
                + plural(len(pendentes), "visita pendente", "visitas pendentes")
                + ", no horário de fechamento do dia de cada entrada?\n\n"
                + "\n".join(linhas)
                + "\n\nCada uma fica no histórico como "
                  "\"Saída automática (encerramento)\".")

    def _registro(self, iid):
        """Registro da linha da tabela (iid = id no banco). Se a linha já
        saiu do movimento (ex.: deu saída e a entrada foi ontem), relê."""
        registro = self.mostrados.get(int(iid))
        if registro is None:
            ok, registro = self.app.tentar(self.app.banco.buscar, int(iid))
        return registro

    def _esta_visivel(self):
        # a página fica dentro do Notebook de páginas (self.aba.master)
        return self.aba.master.select() == str(self.aba)

    # --------------------------------------------------------------
    # Registrar a entrada e limpar
    # --------------------------------------------------------------
    def cadastrar(self, event=None):
        if event is not None and not self._esta_visivel():
            return  # Enter só registra na página Entrada e saída
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
        # a sobreposição é conferida com TODAS as visitas desse CPF no banco
        # (a tabela só tem o movimento do dia)
        ok, anteriores = self.app.tentar(self.app.banco.listar_por_cpf,
                                         registro["cpf"])
        if not ok:
            return
        agora = self.app.relogio()
        ok, msg = validar(registro, anteriores, agora)
        if not ok:
            mensagens.erro("Dados inválidos", msg)
            return
        # VERIFICAÇÃO SEMÂNTICA 6: a entrada faz sentido para a categoria
        # naquele dia e horário? Se não, é exceção: só com autorização
        ok, config = self.app.tentar(self.app.banco.ler_configuracao)
        if not ok:
            return
        autorizacao = None
        regras = horarios.excecoes_do_registro(config, registro, agora)
        if regras:
            autorizacao = autorizar_excecao(self.app, regras,
                                            f"A entrada de {registro['nome']}")
            if autorizacao is None:
                return
        if not self.app.gravar(self.app.banco.inserir, registro,
                               autorizacao=autorizacao):
            return
        self.app.atualizar_tabela()
        self.limpar()
        hora = registro["entrada"][-5:]
        self.avisar(f"Entrada de {registro['nome'].split()[0]} registrada "
                    f"às {hora}" + self._com_autorizacao(autorizacao))

    @staticmethod
    def _com_autorizacao(autorizacao):
        if autorizacao is None:
            return "."
        return f" (exceção autorizada por {autorizacao['autorizado_por']})."

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
        self.entrada.insert(0, self._agora_texto())
        self.saida.delete(0, tk.END)
        self.cpf.focus()

    def preencher_pessoa(self, pessoa):
        """Começa uma nova entrada para a pessoa (usado pela página Pessoas)."""
        self.limpar()
        self.var_cpf.set(pessoa["cpf"])
        self.tipo.focus()

    # --------------------------------------------------------------
    # Preenchimento automático pelo CPF, faixa de situação e bloqueios
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

    def _situacao(self, tipo, texto, acao=None, comando=None):
        self.aviso_pessoa.mostrar(tipo, texto, acao=acao, comando=comando)

    def _ao_digitar_cpf(self, *args):
        """Ao completar o CPF, busca a pessoa e preenche os campos vazios."""
        cpf = so_digitos(self.var_cpf.get())
        if self._auto and self._auto["cpf"] != cpf:
            self._desfazer_preenchimento()
        if len(cpf) < 11:
            self._situacao("neutro", DICA_CPF)
            self._mostrar_ficha(None)
            return
        if self._auto:
            return
        if not cpf_valido(cpf):
            self._situacao("erro", "CPF inválido: confira os números.")
            return
        ok, pessoa = self.app.tentar(self.app.banco.buscar_pessoa, cpf)
        if not ok:
            return
        if pessoa is not None:
            self._preencher_automatico(pessoa)
        self._mostrar_situacao(cpf, pessoa)

    def _mostrar_situacao(self, cpf, pessoa):
        """Faixa e ficha conforme a pessoa: nova, já veio, no campus ou
        bloqueada (o bloqueio tem a palavra final)."""
        self._mostrar_ficha(pessoa)
        if pessoa is None:
            self._situacao("info", "Pessoa nova: preencha os dados abaixo.")
        elif pessoa["dentro_desde"]:
            self._situacao(
                "alerta", f"{pessoa['nome'].split()[0]} está no campus desde "
                          f"{self._quando(pessoa['dentro_desde'])}. "
                          "Registre a saída antes.",
                "Registrar saída", lambda: self._saida_de(cpf))
        else:
            self._situacao("sucesso", "Já cadastrado. Confira os dados e "
                                      "registre a entrada.")
        bloqueio = self._bloqueio_ativo("cpf", cpf)
        if bloqueio:
            self._situacao("erro", f"CPF bloqueado: {bloqueio['motivo']}. "
                                   "A entrada será recusada.",
                           "Ver bloqueio",
                           lambda: self.app.ir_para(self.app.aba_bloqueios))

    def _quando(self, momento):
        """'18:14' se foi hoje; senão a data e a hora."""
        hoje = self.app.relogio().strftime("%d/%m/%Y")
        return momento[-5:] if momento.startswith(hoje) else momento

    def _mostrar_ficha(self, pessoa):
        if pessoa is None:
            self.lbl_visitas.config(text="—")
            self.lbl_ultima.config(text="—")
            self.chip_tipo.pack_forget()
            return
        self.lbl_visitas.config(text=str(pessoa["visitas"]))
        self.lbl_ultima.config(text=(pessoa["ultima_visita"] or "—")[:5])
        if pessoa["tipo"]:
            self.lbl_ponto_tipo.config(fg=CORES_TIPO.get(pessoa["tipo"],
                                                         COR["texto_2"]))
            self.lbl_tipo.config(text=pessoa["tipo"])
            self.chip_tipo.pack(anchor="w", pady=(px(12), 0))

    def _saida_de(self, cpf):
        """Link "Registrar saída" da faixa: dá saída na visita aberta."""
        self.app.recarregar_registros()
        abertos = [r for r in self.app.registros
                   if r["cpf"] == cpf and not r["saida"]]
        if abertos and self._dar_saida(abertos):
            ok, pessoa = self.app.tentar(self.app.banco.buscar_pessoa, cpf)
            if ok:
                self._mostrar_situacao(cpf, pessoa)

    def _bloqueio_ativo(self, tipo, valor):
        ok, ativos = self.app.tentar(self.app.banco.listar_bloqueios)
        return next((b for b in (ativos or [])
                     if b["tipo"] == tipo and b["valor"] == valor), None)

    def _ao_digitar_placa(self, *args):
        """Placa desenhada acompanha a digitação; bloqueada fica vermelha."""
        placa = self.var_placa.get().strip().upper()
        bloqueio = (self._bloqueio_ativo("placa", placa)
                    if placa_valida(placa) else None)
        self.desenho_placa.mostrar(placa, bloqueada=bloqueio is not None)
        if bloqueio:
            self.lbl_dica_placa.config(text="bloqueada", fg=COR["erro"],
                                       font=FONTE["rotulo"])
            self.lbl_placa_status.config(
                text=f"Placa bloqueada: {bloqueio['motivo']}")
            self.lbl_placa_status.pack_configure(pady=(px(6), 0))
        else:
            self.lbl_dica_placa.config(text=DICA_PLACA, fg=COR["texto_3"],
                                       font=FONTE["dica"])
            self.lbl_placa_status.config(text="")
            self.lbl_placa_status.pack_configure(pady=0)

    def _preencher_automatico(self, pessoa):
        preenchidos = {}
        for chave, campo in self._campos_pessoa().items():
            if not campo.get().strip() and pessoa[chave]:
                self._escrever(campo, pessoa[chave])
                preenchidos[chave] = campo.get()
        self._auto = {"cpf": pessoa["cpf"], "campos": preenchidos}

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
        ok, msg = pode_editar(self.app.usuario, registro, self.app.relogio())
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
        if not self.app.perguntar(
                mensagens.confirmar,
                "Excluir registro",
                "Excluir " + plural(len(selecionado), "registro selecionado",
                                    "registros selecionados") + "?\n"
                "A exclusão fica registrada no histórico."):
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
        registro = self._registro(linha)
        if registro:
            self._dar_saida([registro])

    def saida_rapida(self, event=None):
        """Campo Saída rápida: CPF ou placa exatos + Enter."""
        texto = self.campo_saida_rapida.get().strip()
        if not texto:
            mensagens.aviso("Saída rápida", "Digite o CPF ou a placa.")
            return "break"
        self.app.recarregar_registros()        # outra estação pode ter mudado
        encontrados = encontrar_dentro(self.app.registros, texto)
        if not encontrados:
            mensagens.erro("Saída rápida",
                           f"Ninguém no campus com o CPF ou a placa “{texto}”.")
            return "break"
        if len(encontrados) > 1:
            nomes = "\n".join(f"• {r['nome']}" for r in encontrados)
            if not self.app.perguntar(
                    mensagens.confirmar,
                    "Saída rápida",
                    f"{len(encontrados)} pessoas estão no campus com essa placa:"
                    f"\n{nomes}\n\nRegistrar a saída de todas?"):
                return "break"
        if self._dar_saida(encontrados):
            self.campo_saida_rapida.delete(0, tk.END)
        return "break"

    def _dar_saida(self, registros):
        """Registra a saída agora; avisa sem travar a tela e oferece desfazer.
        Visita que passaria de 24 h é exceção: pede a autorização antes."""
        momento = self.app.relogio().replace(second=0, microsecond=0)
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
        regras = [f"{r['nome']}: {regra}" for r in prontos
                  for regra in horarios.excecoes_da_duracao(
                      datetime.strptime(r["entrada"], FORMATO), momento)]
        autorizacao = None
        if regras:
            autorizacao = autorizar_excecao(self.app, regras, "Esta saída")
            if autorizacao is None:
                return False
        saida = momento.strftime(FORMATO)
        ok, gravados = self.app.tentar(
            self.app.banco.registrar_saidas, [r["id"] for r in prontos], saida,
            autor=self.app.autor, autorizacao=autorizacao)
        if not ok:
            return False
        # a linha pode estar desatualizada: só conta o que o banco gravou
        self.app.atualizar_tabela()
        if not gravados:
            mensagens.aviso("Saída", SAIDA_JA_FEITA)
            return False
        gravadas = sorted((r for r in prontos if r["id"] in gravados),
                          key=lambda r: r["id"])
        primeiros = [r["nome"].split()[0] for r in gravadas]
        nomes = primeiros[-1]
        if len(primeiros) > 1:
            nomes = ", ".join(primeiros[:-1]) + " e " + nomes
        texto = (f"Saída de {nomes} registrada às {momento:%H:%M}"
                 + self._com_autorizacao(autorizacao))
        nao_gravadas = len(recusas) + len(prontos) - len(gravadas)
        if nao_gravadas:
            texto += (f" ({nao_gravadas} já tinha(m) saída ou foi(ram) "
                      "excluída(s) em outra estação.)")
        self._saida_para_desfazer = saida
        self.avisar(texto, desfazer=gravados)
        return True

    def desfazer_saida(self):
        """Desfaz só as saídas que esta tela gravou, com o horário gravado
        (nunca a saída dada ou corrigida por outra estação)."""
        ids = self._para_desfazer
        if not ids:
            return
        ok, desfeitas = self.app.tentar(self.app.banco.desfazer_saidas, ids,
                                        autor=self.app.autor,
                                        saida=self._saida_para_desfazer)
        if not ok:
            return
        self.app.atualizar_tabela()
        if desfeitas < len(ids):
            mensagens.aviso("Desfazer", "Não foi possível desfazer a saída de "
                                        "quem já tem outra entrada depois desta.")
        if desfeitas:
            self.avisar("Saída desfeita: a pessoa voltou a constar no campus.",
                        icone=ICONE["desfazer"])
        else:
            self.avisar("")

    # --------------------------------------------------------------
    # Aviso que some sozinho (com o Desfazer, se for o caso)
    # --------------------------------------------------------------
    def avisar(self, texto, desfazer=None, icone=None):
        """Mensagem no rodapé do Movimento que some sozinha; com `desfazer`
        (ids), mostra o link Desfazer."""
        if self._timer_aviso:
            self.aba.after_cancel(self._timer_aviso)
        self.lbl_aviso.config(text=texto)
        self.lbl_aviso_icone.config(text=(icone or ICONE["ok"]) if texto else "")
        self._para_desfazer = desfazer
        if desfazer:
            self.btn_desfazer.pack(side="left", padx=(px(10), 0))
        else:
            self.btn_desfazer.pack_forget()
        self._timer_aviso = self.aba.after(SEGUNDOS_PARA_DESFAZER * 1000,
                                           self._esconder_aviso)

    def _esconder_aviso(self):
        self._timer_aviso = None
        self._para_desfazer = None
        self.lbl_aviso.config(text="")
        self.lbl_aviso_icone.config(text="")
        self.btn_desfazer.pack_forget()
