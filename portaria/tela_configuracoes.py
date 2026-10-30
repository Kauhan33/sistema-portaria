"""
Página Configurações (só administrador): os horários de acesso do campus
(regras em horarios.py, guardadas no banco pela dados.py).

Três seções, escolhidas no seletor do topo:
- Funcionamento: horário de cada dia da semana, minutos do aviso antes de
  fechar, o limite do lançamento retroativo (3 h) e o estacionamento
  (RN37: vagas, 0 = sem controle, e "Bloquear quando lotado");
- Categorias: janela de entrada, permanência máxima e tolerância depois do
  fechamento de cada tipo de acesso;
- Feriados e eventos: datas com o campus fechado e datas com horário
  especial (o evento SOMA ao funcionamento do dia: num sábado normal com
  formatura à noite o campus abre nas duas janelas). Adicionar, Editar
  (RN44: a linha escolhida volta para os campos e o botão vira "Salvar")
  e Remover.

Tudo o que é digitado passa pelas funções horarios.ler_* (fecha depois de
abre, hh:mm válido, números nos limites) antes de ir ao banco, que confere
o perfil de administrador e registra cada mudança no histórico.

O resultado de Salvar (erro ou "Salvo") aparece NO LUGAR da nota de ajuda
da seção, junto do botão: a altura da página não muda, então no notebook
(1366x670) o botão e a mensagem continuam visíveis. Reler a página
(abri-la de novo) traz a nota de volta.
"""

import tkinter as tk
from datetime import date

from . import horarios, mensagens
from .componentes import (Alternador, Aviso, Botao, Cabecalho, Campo, Cartao,
                          Seletor, campo_rotulado, inserir_linha, rotulo_campo,
                          tabela, titulo_cartao)
from .estilo import COR, CORES_TIPO, ESPACO_CARTOES, FONTE, ICONE, MARGEM, px
from .horarios import DIAS_SEMANA, FORMATO_DATA
from .validacao import MAXIMO_DESCRICAO, MAXIMO_HORA, TIPOS_ACESSO
from .veiculos import MAXIMO_VAGAS, ler_vagas

SECOES = ("Funcionamento", "Categorias", "Feriados e eventos", "Atalhos")
# Configurações › Atalhos (2.5.3): as teclas do programa, inclusive a do
# modo didático, que não tem mais botão na tela
ATALHOS = (
    ("F2 ou Ctrl+K", "Vai ao campo Comando, de qualquer página"),
    ("Enter", "Registrar entrada (na Entrada e saída) ou executar o comando"),
    ("Tab", "No campo Comando: completa o comando, a palavra, o tipo ou o nome"),
    ("Esc", "No campo Comando: limpa a linha; fecha o console"),
    ("Ctrl+L", "Travar a guarita (Ausentar)"),
    ("Ctrl+Shift+D", "Abre e fecha o modo didático do campo Comando: as fases "
                     "da análise (léxico, sintático, semântico e execução), "
                     "os tokens, a árvore, os símbolos e as checagens. É da "
                     "apresentação de Compiladores; o porteiro não precisa"),
)
JANELAS = {"Do funcionamento": True, "Horário fixo": False}
PERMANENCIAS = {"Até fechar +": True, "No máximo": False}
JANELA_FIXA_PADRAO = ("08:00", "18:00")
DICA_CATEGORIAS = ("Do funcionamento: De = min antes de abrir; Até = 0 (até "
                   "fechar) ou negativo (min antes de fechar). Horário fixo: "
                   "hh:mm, só com o campus aberto. Ninguém entra depois de fechar. "
                   "Tolerância = min depois do fechamento até a saída pendente.")
LARGURA_HORA_RELOGIO = 104    # hh:mm com o ícone do relógio
ABERTO = {True: "Aberto", False: "Fechado"}
NOTA_FUNCIONAMENTO = (
    "Retroativo além do limite, saída com o campus fechado e visita acima "
    f"de {horarios.LIMITE_VISITA_HORAS} h pedem autorização (dia já "
    "fechado: só com a senha).")
LARGURA_NUMERO = 72           # minutos ou hh:mm na tabela de categorias
LARGURA_VAGAS = 76            # 4 dígitos
TEXTO_BLOQUEAR = "Bloquear quando lotado"
COLUNAS_FERIADOS = [("data", "Data", 96, "w"), ("dia", "Dia", 56, "w"),
                    ("descricao", "Descrição", 200, "w")]
COLUNAS_EVENTOS = [("data", "Data", 96, "w"), ("horario", "Horário", 104, "w"),
                   ("descricao", "Descrição", 220, "w")]


def _texto(campo, valor):
    """Escreve num Entry mesmo desativado."""
    estado = campo.cget("state")
    campo.config(state="normal")
    campo.delete(0, tk.END)
    campo.insert(0, valor)
    campo.config(state=estado)


def _hhmm(momento):
    return momento.strftime(horarios.FORMATO_HORA)


class AbaConfiguracoes:
    def __init__(self, aba, app):
        self.aba = aba
        self.app = app
        self.config = None
        self.dias = []          # 7 x (var aberto, campo abre, campo fecha)
        self.alternadores = []  # "Aberto" ou "Fechado" de cada dia
        self.categorias = {}    # tipo -> campos da linha

        cab = Cabecalho(aba, "Configurações",
                        "Horários de acesso do campus  ·  só o administrador "
                        "altera, e toda mudança fica no histórico").posicionar()
        self.seletor = Seletor(aba, SECOES, self.mostrar_secao)
        self.seletor.pack(fill="x", padx=px(MARGEM), pady=(0, px(12)))
        self.secoes = {nome: tk.Frame(aba, bg=COR["fundo"]) for nome in SECOES}
        self._montar_funcionamento(self.secoes["Funcionamento"])
        self._montar_categorias(self.secoes["Categorias"])
        self._montar_calendario(self.secoes["Feriados e eventos"])
        self._montar_atalhos(self.secoes["Atalhos"])
        self.seletor.selecionar(SECOES[0])
        self.atualizar()

    def mostrar_secao(self, nome):
        for secao, frame in self.secoes.items():
            if secao == nome:
                frame.pack(fill="both", expand=True, padx=px(MARGEM),
                           pady=(0, px(MARGEM)))
            else:
                frame.pack_forget()

    # --------------------------------------------------------------
    # Funcionamento + avisos e limites
    # --------------------------------------------------------------
    def _montar_funcionamento(self, secao):
        secao.columnconfigure(0, weight=3, uniform="f")
        secao.columnconfigure(1, weight=2, uniform="f")
        cartao = Cartao(secao, pad=16)
        cartao.grid(row=0, column=0, sticky="nsew", padx=(0, px(ESPACO_CARTOES)))
        m = cartao.miolo
        cab = tk.Frame(m, bg=COR["superficie"])
        cab.pack(fill="x", pady=(0, px(8)))
        titulo_cartao(cab, "Horário de funcionamento").pack(side="left")
        # no topo: nenhuma mensagem empurra o botão para fora da tela
        self.btn_salvar_funcionamento = Botao(
            cab, "Salvar funcionamento", self.salvar_funcionamento, "primario")
        self.btn_salvar_funcionamento.pack(side="right")
        grade = tk.Frame(m, bg=COR["superficie"])
        grade.pack(fill="x")
        for coluna, texto in enumerate(("Dia", "", "Abre", "Fecha")):
            tk.Label(grade, text=texto, font=FONTE["rotulo"], bg=COR["superficie"],
                     fg=COR["texto_2"]).grid(row=0, column=coluna, sticky="w",
                                             pady=(0, px(2)))
        grade.columnconfigure(0, weight=1)
        for dia, nome in enumerate(DIAS_SEMANA):
            linha = dia + 1
            tk.Label(grade, text=nome, font=FONTE["corpo"], bg=COR["superficie"],
                     fg=COR["texto"]).grid(row=linha, column=0, sticky="w")
            aberto = tk.BooleanVar(self.aba, value=True)
            abre = Campo(grade, largura=LARGURA_HORA_RELOGIO, seletor="hora")
            fecha = Campo(grade, largura=LARGURA_HORA_RELOGIO, seletor="hora")
            for campo in (abre, fecha):      # dia fechado: campo apagado, liso
                campo.entrada.config(disabledbackground=COR["superficie"],
                                     disabledforeground=COR["texto_3"])
            alternador = Alternador(
                grade, ABERTO[True], aberto, textos=tuple(ABERTO.values()),
                comando=lambda d=dia: self._ao_alternar_dia(d))
            alternador.grid(row=linha, column=1, sticky="w", padx=(0, px(16)))
            abre.grid(row=linha, column=2, pady=1, padx=(0, px(8)))
            fecha.grid(row=linha, column=3, pady=1)
            self.dias.append((aberto, abre.entrada, fecha.entrada))
            self.alternadores.append(alternador)

        lado = Cartao(secao, pad=16)
        lado.grid(row=0, column=1, sticky="nsew")
        m = lado.miolo
        titulo_cartao(m, "Avisos e limites").pack(anchor="w", pady=(0, px(6)))
        grupo, campo = campo_rotulado(m, "Aviso antes de fechar",
                                      "minutos (0 = sem aviso)", numeros=3)
        grupo.pack(fill="x", pady=(0, px(12)))
        self.minutos_aviso = campo.entrada
        grupo, campo = campo_rotulado(m, "Lançamento retroativo",
                                      "horas sem autorização", numeros=2)
        grupo.pack(fill="x", pady=(0, px(12)))
        self.horas_retroativo = campo.entrada
        # RN37: lotação do estacionamento (o campo e o interruptor numa
        # linha só: cabe no notebook 1366x670)
        linha, _ = rotulo_campo(m, "Vagas do estacionamento",
                                "0 = sem controle")
        linha.pack(fill="x", pady=(0, px(4)))
        linha = tk.Frame(m, bg=COR["superficie"])
        linha.pack(fill="x", pady=(0, px(12)))
        campo = Campo(linha, largura=LARGURA_VAGAS,
                      numeros=len(str(MAXIMO_VAGAS)))
        campo.pack(side="left", padx=(0, px(12)))
        self.vagas = campo.entrada
        self.var_bloquear_lotado = tk.BooleanVar(self.aba, value=False)
        self.alternador_lotado = Alternador(linha, TEXTO_BLOQUEAR,
                                            self.var_bloquear_lotado)
        self.alternador_lotado.pack(side="left")
        # a nota de ajuda dá lugar ao resultado de Salvar (respiro menor:
        # com a lotação, o cartão continua cabendo no notebook)
        self.faixa_funcionamento = self._nota(m, NOTA_FUNCIONAMENTO)
        self.faixa_funcionamento.definir_respiro(6)

    def _ao_alternar_dia(self, dia):
        aberto, abre, fecha = self.dias[dia]
        self.alternadores[dia].definir_texto(ABERTO[bool(aberto.get())])
        estado = "normal" if aberto.get() else "disabled"
        for campo in (abre, fecha):
            campo.config(state=estado)

    def _preencher_funcionamento(self):
        for dia, (aberto, abre, fecha) in enumerate(self.dias):
            horario = self.config.funcionamento.get(dia)
            aberto.set(horario is not None)
            abre.config(state="normal")
            fecha.config(state="normal")
            _texto(abre, horario.abre.strftime("%H:%M") if horario else "")
            _texto(fecha, horario.fecha.strftime("%H:%M") if horario else "")
            self._ao_alternar_dia(dia)
        _texto(self.minutos_aviso, str(self.config.minutos_aviso))
        _texto(self.horas_retroativo, str(self.config.horas_retroativo))
        _texto(self.vagas, str(self.config.vagas))
        self.var_bloquear_lotado.set(self.config.bloquear_lotado)
        self.alternador_lotado.definir_texto(TEXTO_BLOQUEAR)

    def salvar_funcionamento(self):
        linhas = [(aberto.get(), abre.get(), fecha.get())
                  for aberto, abre, fecha in self.dias]
        funcionamento, erro = horarios.ler_funcionamento(linhas)
        if not erro:
            parametros, erro = horarios.ler_parametros(
                self.minutos_aviso.get(), self.horas_retroativo.get())
        if not erro:
            vagas, erro = ler_vagas(self.vagas.get())
        if erro:
            self._resultado(self.faixa_funcionamento, "erro", erro)
            return
        ok, dias = self.app.tentar(self.app.banco.salvar_funcionamento,
                                   funcionamento, autor=self.app.autor)
        if not ok:
            return
        ok, outros = self.app.tentar(self.app.banco.salvar_parametros,
                                     *parametros, autor=self.app.autor)
        if not ok:
            return
        ok, lotacao = self.app.tentar(self.app.banco.salvar_lotacao, vagas,
                                      self.var_bloquear_lotado.get(),
                                      autor=self.app.autor)
        if not ok:
            return
        self._salvo(self.faixa_funcionamento, dias + outros + lotacao)

    # --------------------------------------------------------------
    # Regras por categoria
    # --------------------------------------------------------------
    def _montar_categorias(self, secao):
        cartao = Cartao(secao, pad=16)
        cartao.pack(fill="both", expand=True)
        m = cartao.miolo
        cab = tk.Frame(m, bg=COR["superficie"])
        cab.pack(fill="x")
        titulo_cartao(cab, "Regras por categoria").pack(side="left")
        Botao(cab, "Salvar regras", self.salvar_regras, "primario"
              ).pack(side="right")
        # a dica dá lugar ao resultado de Salvar (logo abaixo do botão)
        self.faixa_categorias = self._nota(m, DICA_CATEGORIAS)
        self.faixa_categorias.pack_configure(pady=(px(8), px(8)))
        self.faixa_categorias.definir_respiro(6)
        grade = tk.Frame(m, bg=COR["superficie"])
        grade.pack(fill="x")
        self.grade_categorias = grade
        titulos = ("Categoria", "Janela de entrada", "De", "Até", "Permanência",
                   "Minutos", "Tolerância")
        for coluna, texto in enumerate(titulos):
            tk.Label(grade, text=texto, font=FONTE["rotulo"], bg=COR["superficie"],
                     fg=COR["texto_2"]).grid(row=0, column=coluna, sticky="w",
                                             pady=(0, px(2)))
        grade.columnconfigure((1, 4), weight=1)
        for linha, tipo in enumerate(TIPOS_ACESSO, start=1):
            self.categorias[tipo] = self._linha_categoria(grade, linha, tipo)

    def _linha_categoria(self, grade, linha, tipo):
        nome = tk.Frame(grade, bg=COR["superficie"])
        nome.grid(row=linha, column=0, sticky="w", padx=(0, px(12)))
        tk.Label(nome, text=chr(0x25CF), font=FONTE["dica"], bg=COR["superficie"],
                 fg=CORES_TIPO.get(tipo, COR["texto_2"])).pack(side="left")
        tk.Label(nome, text=tipo, font=FONTE["corpo"], bg=COR["superficie"],
                 fg=COR["texto"]).pack(side="left", padx=(px(4), 0))
        campos = {"janela": Campo(grade, opcoes=JANELAS),
                  "de": Campo(grade, largura=LARGURA_NUMERO,
                              maximo=MAXIMO_HORA),
                  "ate": Campo(grade, largura=LARGURA_NUMERO,
                               maximo=MAXIMO_HORA),
                  "permanencia": Campo(grade, opcoes=PERMANENCIAS),
                  "minutos": Campo(grade, largura=LARGURA_NUMERO, numeros=4),
                  "tolerancia": Campo(grade, largura=LARGURA_NUMERO, numeros=3)}
        for coluna, campo in enumerate(campos.values(), start=1):
            campo.grid(row=linha, column=coluna, sticky="ew", pady=1,
                       padx=(0, px(8) if coluna < len(campos) else 0))
        linha_campos = {chave: campo.entrada for chave, campo in campos.items()}
        linha_campos["memoria"] = {}       # o que cada janela tinha (trocar e voltar)
        linha_campos["janela"].bind("<<ComboboxSelected>>",
                                    lambda e, t=tipo: self._ao_trocar_janela(t))
        return linha_campos

    def _ao_trocar_janela(self, tipo):
        """Troca De/Até para o formato da janela escolhida (minutos ou hh:mm)."""
        c = self.categorias[tipo]
        relativa = JANELAS[c["janela"].get()]
        anterior = c.get("relativa_mostrada", not relativa)
        if anterior == relativa:
            return
        c["memoria"][anterior] = (c["de"].get(), c["ate"].get())
        de, ate = c["memoria"].get(relativa, ("0", "0") if relativa
                                   else JANELA_FIXA_PADRAO)
        _texto(c["de"], de)
        _texto(c["ate"], ate)
        c["relativa_mostrada"] = relativa

    def _preencher_categorias(self):
        nome_janela = {v: k for k, v in JANELAS.items()}
        nome_permanencia = {v: k for k, v in PERMANENCIAS.items()}
        for tipo, c in self.categorias.items():
            regra = self.config.regras[tipo]
            c["memoria"] = {}
            c["relativa_mostrada"] = regra.relativa
            c["janela"].set(nome_janela[regra.relativa])
            if regra.relativa:
                de, ate = str(regra.abre_antes), str(regra.fecha_depois)
            else:
                de, ate = _hhmm(regra.janela.abre), _hhmm(regra.janela.fecha)
            _texto(c["de"], de)
            _texto(c["ate"], ate)
            c["permanencia"].set(nome_permanencia[regra.ate_fechamento])
            _texto(c["minutos"], str(regra.permanencia_min))
            _texto(c["tolerancia"], str(regra.tolerancia_min))

    def salvar_regras(self):
        regras = {}
        for tipo, c in self.categorias.items():
            regra, erro = horarios.ler_regra(
                tipo, JANELAS[c["janela"].get()], c["de"].get(), c["ate"].get(),
                PERMANENCIAS[c["permanencia"].get()], c["minutos"].get(),
                c["tolerancia"].get())
            if erro:
                self._resultado(self.faixa_categorias, "erro", erro)
                return
            regras[tipo] = regra
        ok, mudaram = self.app.tentar(self.app.banco.salvar_regras, regras,
                                      autor=self.app.autor)
        if ok:
            self._salvo(self.faixa_categorias, mudaram)

    # --------------------------------------------------------------
    # Feriados e eventos
    # --------------------------------------------------------------
    def _montar_atalhos(self, secao):
        """Só leitura: as teclas do programa (a do modo didático é a única
        forma de abri-lo)."""
        cartao = Cartao(secao, pad=20)
        cartao.pack(fill="both", expand=True)
        m = cartao.miolo
        titulo_cartao(m, "Atalhos do teclado").pack(anchor="w")
        fundo = COR["superficie"]
        grade = tk.Frame(m, bg=fundo)
        grade.pack(fill="x", pady=(px(12), 0))
        grade.columnconfigure(1, weight=1)
        self.lbl_atalhos = {}
        for i, (teclas, faz) in enumerate(ATALHOS):
            tk.Label(grade, text=teclas, font=FONTE["rotulo"], bg=fundo,
                     fg=COR["texto"], anchor="nw").grid(
                row=i, column=0, sticky="nw", padx=(0, px(24)), pady=px(6))
            rotulo = tk.Label(grade, text=faz, font=FONTE["corpo"], bg=fundo,
                              fg=COR["texto_2"], anchor="w", justify="left",
                              wraplength=px(640))
            rotulo.grid(row=i, column=1, sticky="w", pady=px(6))
            self.lbl_atalhos[teclas] = rotulo

    def _montar_calendario(self, secao):
        secao.columnconfigure(0, weight=2, uniform="c")
        secao.columnconfigure(1, weight=3, uniform="c")
        secao.rowconfigure(0, weight=1)
        self.editando = {"feriado": None, "evento": None}
        m = self._cartao_lista(secao, 0, "Feriados", "campus fechado o dia todo",
                               self.remover_feriado, self.editar_feriado)
        linha = tk.Frame(m, bg=COR["superficie"])
        linha.pack(fill="x")
        linha.columnconfigure(1, weight=1)
        self.data_feriado = self._campo(linha, 0, 0, "Data", "dd/mm/aaaa", 136,
                                        seletor="data")
        self.nome_feriado = self._campo(linha, 0, 1, "Descrição", "ex.: Natal",
                                        maximo=MAXIMO_DESCRICAO)
        acoes = tk.Frame(linha, bg=COR["superficie"])
        acoes.grid(row=2, column=0, columnspan=2, sticky="e", pady=(px(10), 0))
        self.btn_cancelar_feriado = Botao(acoes, "Cancelar",
                                          lambda: self.cancelar_edicao("feriado"),
                                          "fantasma")
        self.btn_feriado = Botao(acoes, "Adicionar", self.adicionar_feriado,
                                 "secundario", icone=ICONE["mais"])
        self.btn_feriado.pack(side="right")
        self.faixa_feriados = Aviso(m)
        quadro, self.tabela_feriados = tabela(m, COLUNAS_FERIADOS, altura=5)
        quadro.pack(fill="both", expand=True, pady=(px(12), 0))
        self.faixa_feriados.antes_de = quadro

        m = self._cartao_lista(secao, 1, "Eventos",
                               "abre também nesse horário (soma ao do dia)",
                               self.remover_evento, self.editar_evento)
        linha = tk.Frame(m, bg=COR["superficie"])
        linha.pack(fill="x")
        linha.columnconfigure(3, weight=1)
        self.data_evento = self._campo(linha, 0, 0, "Data", "dd/mm/aaaa", 136,
                                       seletor="data")
        self.abre_evento = self._campo(linha, 0, 1, "Abre", "hh:mm",
                                       LARGURA_HORA_RELOGIO, seletor="hora")
        self.fecha_evento = self._campo(linha, 0, 2, "Fecha", "hh:mm",
                                        LARGURA_HORA_RELOGIO, seletor="hora")
        self.nome_evento = self._campo(linha, 2, 0, "Descrição", "ex.: Formatura",
                                       juntas=4, maximo=MAXIMO_DESCRICAO)
        # na linha da data: ao lado da descrição, era cortado no notebook
        acoes = tk.Frame(linha, bg=COR["superficie"])
        acoes.grid(row=1, column=3, sticky="e")
        self.btn_cancelar_evento = Botao(acoes, "Cancelar",
                                         lambda: self.cancelar_edicao("evento"),
                                         "fantasma")
        self.btn_evento = Botao(acoes, "Adicionar", self.adicionar_evento,
                                "secundario", icone=ICONE["mais"])
        self.btn_evento.pack(side="right")
        self.faixa_eventos = Aviso(m)
        quadro, self.tabela_eventos = tabela(m, COLUNAS_EVENTOS, altura=5)
        quadro.pack(fill="both", expand=True, pady=(px(12), 0))
        self.faixa_eventos.antes_de = quadro

    def _cartao_lista(self, secao, coluna, titulo, apoio, remover, editar):
        cartao = Cartao(secao, pad=16)
        cartao.grid(row=0, column=coluna, sticky="nsew",
                    padx=(0, px(ESPACO_CARTOES)) if coluna == 0 else 0)
        m = cartao.miolo
        cab = tk.Frame(m, bg=COR["superficie"])
        cab.pack(fill="x", pady=(0, px(10)))
        textos = tk.Frame(cab, bg=COR["superficie"])
        textos.pack(side="left")
        titulo_cartao(textos, titulo).pack(anchor="w")
        tk.Label(textos, text=apoio, font=FONTE["dica"], bg=COR["superficie"],
                 fg=COR["texto_3"]).pack(anchor="w")
        # Editar e Remover embaixo da lista (no notebook o cartão dos
        # feriados é estreito para o título e dois botões)
        acoes = tk.Frame(m, bg=COR["superficie"])
        acoes.pack(side="bottom", fill="x", pady=(px(10), 0))
        Botao(acoes, "Remover", remover, "secundario", icone=ICONE["lixo"]
              ).pack(side="right")
        Botao(acoes, "Editar", editar, "secundario", icone=ICONE["editar"]
              ).pack(side="right", padx=(0, px(8)))
        return m

    def _campo(self, grade, linha, coluna, texto, dica, largura=None, juntas=1,
               seletor=None, maximo=None):
        """Rótulo em cima e campo embaixo (o formato fica dentro do campo);
        com `seletor`, o calendário ou o relógio abre no clique."""
        rotulo, _ = rotulo_campo(grade, texto)
        rotulo.grid(row=linha, column=coluna, sticky="w",
                    pady=(px(10) if linha else 0, px(4)))
        campo = Campo(grade, largura=largura, dica_vazio=dica, seletor=seletor,
                      relogio=self.app.relogio, maximo=maximo)
        campo.grid(row=linha + 1, column=coluna, columnspan=juntas, sticky="ew",
                   padx=(0, px(8)))
        return campo.entrada

    def _preencher_calendario(self):
        hoje = self.app.relogio().date()
        self.tabela_feriados.delete(*self.tabela_feriados.get_children())
        for i, (dia, nome) in enumerate(sorted(self.config.feriados.items())):
            inserir_linha(self.tabela_feriados, i,
                          (f"{dia:{FORMATO_DATA}}", DIAS_SEMANA[dia.weekday()][:3], nome),
                          iid=dia.isoformat(),
                          tags=("apagado",) if dia < hoje else ())
        self.tabela_eventos.delete(*self.tabela_eventos.get_children())
        for i, evento in enumerate(sorted(self.config.eventos.values(),
                                          key=lambda e: e.data)):
            inserir_linha(self.tabela_eventos, i,
                          (f"{evento.data:{FORMATO_DATA}}", str(evento.horario),
                           evento.descricao), iid=evento.data.isoformat(),
                          tags=("apagado",) if evento.data < hoje else ())

    def adicionar_feriado(self):
        """Adicionar (ou, editando, Salvar a alteração do feriado)."""
        editando = self.editando["feriado"]
        valor, erro = horarios.ler_feriado(self.data_feriado.get(),
                                           self.nome_feriado.get(), self.config,
                                           editando=editando)
        if erro:
            self._resultado(self.faixa_feriados, "erro", erro)
            return
        if editando is not None:
            ok, mudou = self.app.tentar(self.app.banco.editar_feriado,
                                        editando, *valor, autor=self.app.autor)
            texto = f"Feriado de {valor[0]:{FORMATO_DATA}} alterado."
        else:
            ok, mudou = self.app.tentar(self.app.banco.adicionar_feriado,
                                        *valor, autor=self.app.autor)
            mudou = 1
            texto = f"Feriado de {valor[0]:{FORMATO_DATA}} adicionado."
        if ok:
            self.cancelar_edicao("feriado")
            self._salvo(self.faixa_feriados, mudou,
                        texto if mudou else "Nada mudou.")

    def adicionar_evento(self):
        """Adicionar (ou, editando, Salvar a alteração do evento)."""
        editando = self.editando["evento"]
        evento, erro = horarios.ler_evento(
            self.data_evento.get(), self.abre_evento.get(),
            self.fecha_evento.get(), self.nome_evento.get(), self.config,
            editando=editando)
        if erro:
            self._resultado(self.faixa_eventos, "erro", erro)
            return
        if editando is not None:
            ok, mudou = self.app.tentar(self.app.banco.editar_evento, editando,
                                        evento, autor=self.app.autor)
            texto = f"Evento de {evento.data:{FORMATO_DATA}} alterado."
        else:
            ok, mudou = self.app.tentar(self.app.banco.adicionar_evento, evento,
                                        autor=self.app.autor)
            mudou = 1
            texto = f"Evento de {evento.data:{FORMATO_DATA}} adicionado."
        if ok:
            self.cancelar_edicao("evento")
            self._salvo(self.faixa_eventos, mudou,
                        texto if mudou else "Nada mudou.")

    # --- editar (RN44): a linha volta para os campos -----------------
    def _campos(self, nome):
        if nome == "feriado":
            return (self.data_feriado, self.nome_feriado)
        return (self.data_evento, self.abre_evento, self.fecha_evento,
                self.nome_evento)

    def _botoes_de(self, nome):
        if nome == "feriado":
            return self.btn_feriado, self.btn_cancelar_feriado
        return self.btn_evento, self.btn_cancelar_evento

    def _editar(self, nome, tab, valores):
        selecao = tab.selection()
        if not selecao:
            mensagens.aviso("Atenção", f"Selecione um {nome} na lista.")
            return False
        dia = date.fromisoformat(selecao[0])
        for campo, valor in zip(self._campos(nome), valores(dia)):
            _texto(campo, valor)
        self.editando[nome] = dia
        salvar, cancelar = self._botoes_de(nome)
        salvar.icone = None
        salvar.definir_texto("Salvar alteração", "primario")
        cancelar.pack(side="right", padx=(0, px(8)), before=salvar)
        return True

    def editar_feriado(self):
        """Feriados › Editar: a data e a descrição voltam para os campos."""
        return self._editar("feriado", self.tabela_feriados, lambda dia: (
            f"{dia:{FORMATO_DATA}}", self.config.feriados[dia]))

    def editar_evento(self):
        """Eventos › Editar: data, horário e descrição voltam aos campos."""
        def valores(dia):
            evento = self.config.eventos[dia]
            return (f"{dia:{FORMATO_DATA}}", _hhmm(evento.horario.abre),
                    _hhmm(evento.horario.fecha), evento.descricao)
        return self._editar("evento", self.tabela_eventos, valores)

    def cancelar_edicao(self, nome):
        """Limpa os campos e o botão volta a ser "Adicionar"."""
        for campo in self._campos(nome):
            _texto(campo, "")
        self.editando[nome] = None
        salvar, cancelar = self._botoes_de(nome)
        salvar.icone = ICONE["mais"]
        salvar.definir_texto("Adicionar", "secundario")
        cancelar.pack_forget()

    def remover_feriado(self):
        self._remover(self.tabela_feriados, "feriado",
                      self.app.banco.remover_feriado, self.faixa_feriados)

    def remover_evento(self):
        self._remover(self.tabela_eventos, "evento",
                      self.app.banco.remover_evento, self.faixa_eventos)

    def _remover(self, tab, nome, operacao, faixa):
        selecao = tab.selection()
        if not selecao:
            mensagens.aviso("Atenção", f"Selecione um {nome} na lista.")
            return
        dia = date.fromisoformat(selecao[0])
        if not self.app.perguntar(mensagens.confirmar, f"Remover {nome}",
                                  f"Remover o {nome} de {dia:{FORMATO_DATA}}?\n"
                                  "A remoção fica no histórico."):
            return
        ok, _ = self.app.tentar(operacao, dia, autor=self.app.autor)
        if ok:
            if self.editando.get(nome) == dia:
                self.cancelar_edicao(nome)
            self._salvo(faixa, 1, f"{nome.capitalize()} de "
                                  f"{dia:{FORMATO_DATA}} removido.")

    # --------------------------------------------------------------
    # Dados e mensagens
    # --------------------------------------------------------------
    def atualizar(self):
        """Página aberta: relê a configuração do banco (descarta o que
        foi digitado e não foi salvo)."""
        ok, config = self.app.tentar(self.app.banco.ler_configuracao)
        if not ok:
            return
        self.config = config
        self._limpar_resultados()
        self._preencher_funcionamento()
        self._preencher_categorias()
        self._preencher_calendario()

    @staticmethod
    def _nota(pai, texto):
        """Faixa neutra de ajuda que também mostra o resultado de Salvar."""
        faixa = Aviso(pai)
        faixa.nota = texto
        faixa.mostrar("neutro", texto)
        faixa.pack(fill="x")
        return faixa

    def _limpar_resultados(self):
        """Ao reler a página, as notas voltam e as mensagens antigas somem."""
        for faixa in (self.faixa_funcionamento, self.faixa_categorias,
                      self.faixa_feriados, self.faixa_eventos):
            nota = getattr(faixa, "nota", None)
            if nota:
                faixa.mostrar("neutro", nota)
            else:
                faixa.pack_forget()

    @staticmethod
    def _resultado(faixa, tipo, texto):
        """Mensagem perto de onde se digitou: no lugar da nota de ajuda ou
        antes da lista."""
        faixa.mostrar(tipo, texto)
        if not faixa.winfo_manager():
            antes = getattr(faixa, "antes_de", None)
            faixa.pack(fill="x", pady=(px(10), 0),
                       **({"before": antes} if antes else {}))

    def _salvo(self, faixa, mudancas, texto=None):
        """Relê tudo, avisa na seção e atualiza o Movimento (as situações
        dependem dos horários)."""
        self.atualizar()
        self.app.atualizar_tabela()
        if texto is None:
            texto = ("Nada mudou." if not mudancas else
                     f"Salvo: {mudancas} alteração(ões), registradas no histórico.")
        self._resultado(faixa, "sucesso", texto)
