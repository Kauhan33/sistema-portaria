"""
Página Painel, em seções (3.6), escolhidas no Seletor do alto:

- Visão geral: cinco números do movimento (no campus agora, entradas de
  hoje, permanência média, veículos no estacionamento agora — com os
  pendentes depois do fechamento, ou o total de visitas com veículo, no
  apoio — e tempo excedido — as visitas abertas acima da permanência
  máxima da categoria, com as saídas pendentes no apoio) e dois gráficos
  (pessoas por tipo de acesso e entradas nos últimos 7 dias);
- Veículos, Entregas, Chaves, Ocorrências e Funcionários: a fileira de
  números de cada assunto, um ranking e a contagem por dia do período
  (7 ou 30 dias).

Os números vêm do banco (resumo_painel e as consultas de dados_painel.py,
calculadas no SQL); o desenho fica em graficos.py. Só a seção que está na
tela é relida: as outras, quando forem abertas. Os painéis mostram nomes,
nunca CPF.
O administrador exporta os registros de um período para planilha (CSV).
RN38: com só 1 administrador ativo, a faixa "Só existe 1 administrador
ativo. Crie um segundo." aparece para o administrador (se ele perder a
senha e os códigos de recuperação, ninguém mais entra como administrador).
"""

import tkinter as tk
from datetime import datetime, timedelta
from tkinter import font as tkfont

from . import backup, horarios, impressao, mensagens
from .componentes import (Aviso, Botao, Cabecalho, Cartao, Dialogo, Seletor,
                          campo_rotulado, plural, titulo_cartao)
from .consultas import formatar_duracao
from .estilo import COR, ESPACO_CARTOES, FONTE, ICONE, MARGEM, px
from .graficos import (cortar_texto, desenhar_barras_horizontais,
                       desenhar_barras_verticais, desenhar_colunas,
                       desenhar_ranking)
from .usuarios import eh_admin, precisa_de_outro_admin
from .validacao import TIPOS_ACESSO

PLURAL_TIPO = {"Aluno": "Alunos", "Professor": "Professores",
               "Funcionário": "Funcionários", "Visitante": "Visitantes",
               "Entregador": "Entregadores",
               "Prestador de serviço": "Prestadores"}
VISAO_GERAL = "Visão geral"
SECOES = (VISAO_GERAL, "Veículos", "Entregas", "Chaves", "Ocorrências",
          "Funcionários")
# (chave, rótulo); o primeiro é o destaque
NUMEROS = [("dentro", "Dentro agora"), ("hoje", "Entradas hoje"),
           ("permanencia", "Permanência média"),
           ("estacionamento", "No estacionamento"),
           ("excedido", "Tempo excedido")]
ALTURA_GRAFICO = 230
# o gráfico da direita: por dia ou por hora, em 7 ou 30 dias
VISOES = ("Por dia", "Por hora")
PERIODOS = {"7 dias": 7, "30 dias": 30}
MAXIMO_NO_RELATORIO = 3000      # visitas numa página para imprimir
FORMATO_DIA = "%d/%m/%Y"
SO_UM_ADMIN = "Só existe 1 administrador ativo. Crie um segundo."


def duracao(td):
    """Tempo de relance: "45min", "3h 10min" ou, de um dia para cima,
    "2d 4h"; "—" sem valor."""
    if td is None:
        return "—"
    if td.days:
        return f"{td.days}d {td.seconds // 3600}h"
    return formatar_duracao(td)


class LinhaNumeros(tk.Frame):
    """Fileira de cartões de número (o primeiro é o destaque, em letra
    maior). `cortar_apoio`: o rótulo e o apoio compridos (um nome, a letra
    "Maior") terminam em "…" em vez de alargar o cartão."""

    def __init__(self, pai, numeros, cor_destaque=None, cortar_apoio=False):
        super().__init__(pai, bg=COR["fundo"])
        self.cards = {}                  # chave -> (valor, apoio)
        self.fonte_do_numero = {}        # só os que saíram da letra normal
        self.cores = {}                  # cor normal de cada número
        self.apoios = {}                 # texto inteiro do apoio
        self.rotulos = {}                # chave -> (Label, texto inteiro)
        self.destaque = numeros[0][0]
        self.cortar_apoio = cortar_apoio
        self.columnconfigure(tuple(range(len(numeros))), weight=1,
                             uniform="numeros")
        for coluna, (chave, rotulo) in enumerate(numeros):
            cartao = Cartao(self, pad=14)
            cartao.grid(row=0, column=coluna, sticky="nsew",
                        padx=px(ESPACO_CARTOES // 2))
            m = cartao.miolo
            nome = tk.Label(m, text=rotulo, font=FONTE["corpo_semi"],
                            bg=COR["superficie"], fg=COR["texto_2"])
            nome.pack(anchor="w")
            self.rotulos[chave] = (nome, rotulo)
            destaque = coluna == 0
            self.cores[chave] = ((cor_destaque or COR["sucesso"]) if destaque
                                 else COR["texto"])
            valor = tk.Label(m, text="0", bg=COR["superficie"],
                             font=FONTE["kpi_destaque" if destaque else "kpi"],
                             fg=self.cores[chave])
            valor.pack(anchor="w", pady=(px(2), 0))
            apoio = tk.Label(m, text="", font=FONTE["dica"], bg=COR["superficie"],
                             fg=COR["texto_3"])
            apoio.pack(anchor="w", side="bottom")
            self.cards[chave] = (valor, apoio)
            m.bind("<Configure>", lambda e, c=chave: self.caber(c), add="+")

    def mostrar(self, chave, valor, apoio, cor=None, cor_apoio=None):
        """Escreve o número e o apoio (com a cor de alerta, se vier)."""
        rotulo_valor, rotulo_apoio = self.cards[chave]
        rotulo_valor.config(text=str(valor), fg=cor or self.cores[chave])
        rotulo_apoio.config(text=apoio, fg=cor_apoio or COR["texto_3"])
        self.apoios[chave] = apoio
        self.caber(chave)

    def caber(self, chave):
        """Número comprido ("3h 10min") em cartão estreito (janela pequena):
        usa a maior letra que cabe, em vez de cortar o texto."""
        valor, apoio = self.cards[chave]
        largura = valor.master.winfo_width()
        if largura <= 1:
            return
        normal = FONTE["kpi_destaque" if chave == self.destaque else "kpi"]
        escolhida = normal
        for fonte in (normal, FONTE["numero"], FONTE["corpo_semi"]):
            escolhida = fonte
            if tkfont.Font(font=fonte).measure(valor.cget("text")) <= largura:
                break
        if self.fonte_do_numero.get(chave, normal) != escolhida:
            self.fonte_do_numero[chave] = escolhida
            valor.config(font=escolhida)
        if not self.cortar_apoio:
            return
        nome, rotulo = self.rotulos[chave]
        for widget, inteiro, fonte in ((nome, rotulo, FONTE["corpo_semi"]),
                                       (apoio, self.apoios.get(chave),
                                        FONTE["dica"])):
            if inteiro is not None:
                texto = cortar_texto(widget, inteiro, fonte, largura)
                if widget.cget("text") != texto:
                    widget.config(text=texto)


def cartao_grafico(area, coluna, titulo):
    """Cartão de gráfico na coluna `coluna` da área: devolve (cabeçalho,
    Canvas). O título fica no cabeçalho, fora do Canvas."""
    cartao = Cartao(area, pad=18)
    cartao.grid(row=0, column=coluna, sticky="nsew",
                padx=px(ESPACO_CARTOES // 2))
    cab = tk.Frame(cartao.miolo, bg=COR["superficie"])
    cab.pack(fill="x", pady=(0, px(12)))
    titulo_cartao(cab, titulo).pack(side="left")
    cv = tk.Canvas(cartao.miolo, bg=COR["superficie"], height=px(ALTURA_GRAFICO),
                   highlightthickness=0, bd=0)
    cv.pack(fill="both", expand=True)
    return cab, cv


def area_dos_graficos(pai):
    """Os dois cartões de gráfico lado a lado, embaixo dos números."""
    area = tk.Frame(pai, bg=COR["fundo"])
    area.pack(fill="both", expand=True, padx=px(MARGEM - ESPACO_CARTOES // 2),
              pady=(px(ESPACO_CARTOES), px(MARGEM)))
    area.columnconfigure((0, 1), weight=1, uniform="g")
    area.rowconfigure(0, weight=1)
    return area


class ComPeriodo:
    """O período (7 ou 30 dias) no cabeçalho de um cartão de gráfico, com
    o nome abreviado quando falta largura."""

    def _montar_periodo(self, cab, ao_trocar, visoes=()):
        """Os Seletores do cabeçalho: a visão (por dia ou por hora), se
        houver, e o período, à direita. Nenhum chama `ao_trocar` aqui."""
        self.seletor_visao = None
        self._montando = True
        if visoes:
            self.seletor_visao = Seletor(cab, visoes, lambda o: ao_trocar(),
                                         fundo_pai=COR["superficie"])
            self.seletor_visao.compactar()
            self.seletor_visao.pack(side="left", padx=(px(16), 0))
            self.seletor_visao.selecionar(visoes[0])
        self.seletor_periodo = Seletor(cab, tuple(PERIODOS), lambda o: ao_trocar(),
                                       fundo_pai=COR["superficie"])
        self.seletor_periodo.compactar()
        self.seletor_periodo.pack(side="right")
        self.seletor_periodo.selecionar("7 dias")
        self._montando = False
        self._cab_entradas, self._largura_do_cab = cab, None
        cab.bind("<Configure>", self._ajustar_periodo, add="+")

    @property
    def dias(self):
        return PERIODOS[self.seletor_periodo.ativa]

    def _ajustar_periodo(self, event=None):
        """Cartão estreito (janela pequena): "7 dias / 30 dias" vira
        "7d / 30d", em vez de sair cortado."""
        cab = self._cab_entradas
        if self._largura_do_cab is None:        # medida com os nomes inteiros
            cab.update_idletasks()
            self._largura_do_cab = px(8) + sum(
                w.winfo_reqwidth() for w in cab.winfo_children()
                if w.winfo_manager()) + px(16)
        curto = cab.winfo_width() < self._largura_do_cab
        if curto != getattr(self, "periodo_curto", None):
            self.periodo_curto = curto
            for nome in PERIODOS:
                self.seletor_periodo.definir_texto(
                    nome, nome.replace(" dias", "d") if curto else nome)


class AbaDashboard(ComPeriodo):
    def __init__(self, aba, app):
        self.aba = aba
        self.app = app
        self.com_veiculo = 0                       # visitas com placa (total)
        self.dados = {"tipos": [], "dias": []}     # dados prontos dos gráficos
        self.destaque, self.nome_destaque = None, "Hoje"
        self.btn_exportar = self.btn_relatorio = None
        self.dialogo = None
        self.paginas = {}          # seção -> SecaoPainel (montada ao abrir)
        self._pronto = False

        cab = Cabecalho(aba, "Painel").posicionar()
        self.lbl_subtitulo = cab.subtitulo
        if eh_admin(app.usuario):       # exportação: só administrador
            self.btn_exportar = Botao(cab.acoes, "Exportar CSV",
                                      self.abrir_exportacao, "secundario",
                                      icone=ICONE["baixar"],
                                      fundo_pai=COR["fundo"])
            self.btn_exportar.pack(side="right")
            self.btn_relatorio = Botao(cab.acoes, "Relatório",
                                       self.abrir_relatorio, "secundario",
                                       icone=ICONE["imprimir"],
                                       fundo_pai=COR["fundo"])
            self.btn_relatorio.pack(side="right", padx=(0, px(8)))
        self.faixa_admin = Aviso(aba, fundo_pai=COR["fundo"])
        # (compacto: a linha das seções não tira altura dos gráficos no
        # notebook 1366x670)
        self.seletor = Seletor(aba, SECOES, self.mostrar_secao)
        self.seletor.compactar()
        self.seletor.pack(fill="x", padx=px(MARGEM), pady=(0, px(10)))
        self.secoes = {nome: tk.Frame(aba, bg=COR["fundo"]) for nome in SECOES}
        self._montar_numeros()
        self._montar_graficos()
        self.seletor.selecionar(VISAO_GERAL)
        self._pronto = True
        self.atualizar()

    @property
    def secao(self):
        """A seção que está na tela."""
        return self.seletor.ativa

    def mostrar_secao(self, nome):
        """Troca a seção (montada na primeira vez) e relê só ela."""
        for secao, frame in self.secoes.items():
            if secao == nome:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()
        if nome != VISAO_GERAL and nome not in self.paginas:
            self.paginas[nome] = SECOES_DO_PAINEL[nome](self.secoes[nome],
                                                        self.app)
        if self._pronto:
            self.atualizar()

    # --------------------------------------------------------------
    # Montagem da Visão geral
    # --------------------------------------------------------------
    def _montar_numeros(self):
        self.linha_numeros = LinhaNumeros(self.secoes[VISAO_GERAL], NUMEROS)
        self.linha_numeros.pack(fill="x", padx=px(MARGEM - ESPACO_CARTOES // 2))
        self.cards = self.linha_numeros.cards
        self.fonte_do_numero = self.linha_numeros.fonte_do_numero

    def _caber(self, chave):
        self.linha_numeros.caber(chave)

    def _montar_graficos(self):
        area = area_dos_graficos(self.secoes[VISAO_GERAL])
        cab, self.cv_tipos = cartao_grafico(area, 0, "Pessoas por tipo de acesso")
        tk.Label(cab, text="todas as visitas", font=FONTE["dica"],
                 bg=COR["superficie"], fg=COR["texto_3"]).pack(side="right")
        cab, self.cv_dias = cartao_grafico(area, 1, "Entradas")
        # por dia ou por hora (o horário de pico), em 7 ou 30 dias; o apoio
        # ("pico às 08h") não vai na linha do título, que já tem as escolhas
        self.lbl_apoio_dias = tk.Label(cab, text="hoje em destaque",
                                       font=FONTE["dica"], bg=COR["superficie"],
                                       fg=COR["texto_3"])
        self._montar_periodo(cab, self._ao_trocar_visao, VISOES)
        for cv in (self.cv_tipos, self.cv_dias):
            cv.bind("<Configure>", self.redesenhar_graficos)

    # --------------------------------------------------------------
    # Dados
    # --------------------------------------------------------------
    def atualizar(self):
        """Relê só a seção que está na tela (as outras são lidas quando
        forem abertas) e a faixa do administrador."""
        if self.secao == VISAO_GERAL:
            self._atualizar_visao_geral()
            return
        pagina = self.paginas[self.secao]
        self.lbl_subtitulo.config(text=pagina.SUBTITULO)
        pagina.atualizar()
        self._mostrar_faixa_admin()

    def _atualizar_visao_geral(self):
        """Relê os números do banco (calculados no SQL)."""
        hoje = self.app.relogio().date()
        ok, r = self.app.tentar(self.app.banco.resumo_painel, hoje)
        if not ok:
            return
        por_tipo = r["por_tipo"]
        self.lbl_subtitulo.config(
            text=f"{plural(r['total'], 'registro', 'registros')} desde o início"
                 f"  ·  {plural(r['saidas'], 'visita encerrada', 'visitas encerradas')}")
        self._mostrar("dentro", r["dentro"], "ainda sem saída")
        self._mostrar("hoje", r["entradas_hoje"], hoje.strftime(FORMATO_DIA))
        if r["permanencia_media"] is not None:
            self._mostrar("permanencia", formatar_duracao(r["permanencia_media"]),
                          f"em {plural(r['saidas'], 'visita', 'visitas')}")
        else:
            self._mostrar("permanencia", "—", "sem saídas registradas")
        self.com_veiculo = r["com_veiculo"]
        self._mostrar_horarios()
        self._mostrar_faixa_admin()

        self.dados["tipos"] = [
            (PLURAL_TIPO.get(t, t), por_tipo[t][0], f"{por_tipo[t][1]} dentro")
            for t in TIPOS_ACESSO]
        self._ler_entradas()
        self.redesenhar_graficos()

    def _ao_trocar_visao(self):
        if not self._montando:
            self._ler_entradas()
            self.redesenhar_graficos()

    def _ler_entradas(self):
        """O gráfico da direita: entradas por dia (hoje em destaque) ou por
        hora (o pico em destaque), nos últimos 7 ou 30 dias."""
        hoje = self.app.relogio().date()
        dias = self.dias
        if self.seletor_visao.ativa == VISOES[1]:
            ok, horas = self.app.tentar(self.app.banco.entradas_por_hora, hoje,
                                        dias)
            if not ok:
                return
            pico = max(range(24), key=lambda h: horas[h])
            self.dados["dias"] = [(f"{h:02d}h" if h % 3 == 0 else "", n)
                                  for h, n in enumerate(horas)]
            self.destaque, self.nome_destaque = pico, f"{pico:02d}h"
            self.lbl_apoio_dias.config(
                text=f"pico às {pico:02d}h" if horas[pico] else "sem entradas")
            return
        ok, por_dia = self.app.tentar(self.app.banco.entradas_por_dia, hoje,
                                      dias)
        if not ok:
            return
        self.dados["dias"] = [
            (d.strftime("%d/%m") if dias <= 7 or n % 5 == 0 else "", total)
            for n, (d, total) in enumerate(por_dia)]
        self.destaque, self.nome_destaque = None, "Hoje"
        self.lbl_apoio_dias.config(text="hoje em destaque")

    def _mostrar_horarios(self):
        """Tempo excedido e saídas pendentes, com o relógio do app."""
        ok, config = self.app.tentar(self.app.banco.ler_configuracao)
        if not ok:
            return
        ok, abertas = self.app.tentar(self.app.banco.listar_abertas)
        if not ok:
            return
        agora = self.app.relogio()
        contagem = horarios.contar_situacoes(config, abertas, agora)
        excedidos = contagem[horarios.TEMPO_EXCEDIDO]
        pendentes = contagem[horarios.SAIDA_PENDENTE]
        self._mostrar("excedido", excedidos,
                      "+ " + plural(pendentes, "saída pendente", "saídas pendentes")
                      if pendentes else "acima do permitido")
        self.cards["excedido"][0].config(
            fg=COR["alerta"] if excedidos else COR["texto"])
        self.cards["excedido"][1].config(
            fg=COR["erro"] if pendentes else COR["texto_3"])
        ok, veiculos = self.app.tentar(self.app.banco.listar_estacionamento)
        if not ok:
            return
        carros = sum(1 for e in veiculos if horarios.situacao_veiculo(
            config, e, agora) == horarios.VEICULO_PENDENTE)
        self._mostrar("estacionamento", len(veiculos),
                      plural(carros, "veículo pendente", "veículos pendentes")
                      if carros else plural(self.com_veiculo, "visita com veículo",
                                            "visitas com veículo"))
        self.cards["estacionamento"][1].config(
            fg=COR["erro"] if carros else COR["texto_3"])

    def _mostrar_faixa_admin(self):
        """RN38: só para o administrador, com 1 administrador ativo."""
        mostrar = False
        if eh_admin(self.app.usuario):
            ok, contas = self.app.tentar(self.app.banco.listar_usuarios)
            mostrar = ok and precisa_de_outro_admin(contas)
        if mostrar:
            self.faixa_admin.mostrar(
                "alerta", SO_UM_ADMIN, icone=ICONE["escudo"],
                acao="Ir para Usuários",
                comando=lambda: self.app.ir_para(self.app.aba_usuarios))
            self.faixa_admin.pack(fill="x", padx=px(MARGEM),
                                  pady=(0, px(ESPACO_CARTOES)),
                                  before=self.seletor)
        else:
            self.faixa_admin.pack_forget()

    def _mostrar(self, chave, valor, apoio):
        self.linha_numeros.mostrar(chave, valor, apoio)

    def redesenhar_graficos(self, event=None):
        desenhar_barras_horizontais(self.cv_tipos, self.dados["tipos"])
        desenhar_barras_verticais(self.cv_dias, self.dados["dias"],
                                  self.destaque, self.nome_destaque)

    # --------------------------------------------------------------
    # Exportar CSV (só administrador)
    # --------------------------------------------------------------
    def abrir_exportacao(self):
        if not eh_admin(self.app.usuario):
            mensagens.erro("Acesso negado",
                           "Somente o administrador exporta os registros.")
            return None
        self.dialogo = DialogoExportar(self.app)
        return self.dialogo

    def abrir_relatorio(self):
        """Relatório do período, numa página para imprimir (só administrador:
        leva os CPFs completos, como a exportação)."""
        if not eh_admin(self.app.usuario):
            mensagens.erro("Acesso negado",
                           "Somente o administrador emite o relatório.")
            return None
        self.dialogo = DialogoRelatorio(self.app)
        return self.dialogo


class DialogoExportar(Dialogo):
    """Escolha do período (com atalhos) e do arquivo para exportar."""

    def __init__(self, app):
        self.app = app
        super().__init__(app.janela, self.TITULO, self.SUBTITULO, largura=420,
                         ao_usar=app.registrar_uso)
        hoje = app.relogio().date()
        atalhos = tk.Frame(self.miolo, bg=COR["superficie"])
        atalhos.pack(fill="x", pady=(0, px(14)))
        for texto, inicio in [("Hoje", hoje),
                              ("Últimos 7 dias", hoje - timedelta(days=6)),
                              ("Este mês", hoje.replace(day=1))]:
            Botao(atalhos, texto, lambda i=inicio: self.periodo(i, hoje),
                  "secundario", altura=30).pack(side="left", padx=(0, px(8)))
        datas = tk.Frame(self.miolo, bg=COR["superficie"])
        datas.pack(fill="x")
        datas.columnconfigure((0, 1), weight=1, uniform="d")
        grupo, campo = campo_rotulado(datas, "De", "dd/mm/aaaa", seletor="data",
                                      relogio=app.relogio)
        grupo.grid(row=0, column=0, sticky="ew", padx=(0, px(12)))
        self.desde = campo.entrada
        grupo, campo = campo_rotulado(datas, "Até", "dd/mm/aaaa", seletor="data",
                                      relogio=app.relogio)
        grupo.grid(row=0, column=1, sticky="ew")
        self.ate = campo.entrada
        self.faixa = Aviso(self.miolo)
        self.faixa.mostrar("alerta", self.AVISO)
        self.faixa.pack(fill="x", pady=(px(16), 0))
        self.lbl_erro = self.faixa.lbl
        self.periodo(hoje.replace(day=1), hoje)
        self.adicionar_botao(self.BOTAO, self.confirmar, "primario")
        self.adicionar_botao("Cancelar", self.fechar)
        self.abrir(confirmar=self.confirmar, foco=self.desde)

    TITULO = "Exportar registros"
    SUBTITULO = ("As visitas com entrada no período vão para uma planilha "
                 "(CSV) que abre no Excel.")
    AVISO = ("O arquivo leva CPF e celular completos: guarde-o com o mesmo "
             "cuidado do sistema.")
    BOTAO = "Escolher arquivo e exportar"

    def confirmar(self):
        return self.exportar()

    def periodo_escolhido(self):
        """(desde, ate) ou None, com o erro já na faixa."""
        desde, ate = self._data(self.desde), self._data(self.ate)
        if desde is None or ate is None:
            self.faixa.mostrar("erro", "Data inválida. Use o formato dd/mm/aaaa.")
            return None
        if ate < desde:
            self.faixa.mostrar("erro", "A data final não pode ser anterior à "
                                       "inicial.")
            return None
        return desde, ate

    def periodo(self, desde, ate):
        for caixa, dia in ((self.desde, desde), (self.ate, ate)):
            caixa.delete(0, tk.END)
            caixa.insert(0, dia.strftime(FORMATO_DIA))

    def _data(self, caixa):
        try:
            return datetime.strptime(caixa.get().strip(), FORMATO_DIA).date()
        except ValueError:
            return None

    def exportar(self):
        desde, ate = self._data(self.desde), self._data(self.ate)
        if desde is None or ate is None:
            self.faixa.mostrar("erro", "Data inválida. Use o formato dd/mm/aaaa.")
            return
        if ate < desde:
            self.faixa.mostrar("erro", "A data final não pode ser anterior à "
                                       "inicial.")
            return
        caminho = self.app.perguntar(
            mensagens.salvar_como, "Exportar registros",
            f"portaria-{desde:%Y-%m-%d}-a-{ate:%Y-%m-%d}.csv", parent=self.janela)
        if not caminho:
            return
        ok, quantos = self.app.tentar(backup.exportar_csv, self.app.banco,
                                      caminho, desde, ate, self.app.autor)
        if not ok:
            return
        self.fechar()
        mensagens.info("Exportar registros",
                       f"{plural(quantos, 'registro exportado', 'registros exportados')}"
                       f" para:\n{caminho}")


class DialogoRelatorio(DialogoExportar):
    """O mesmo período da exportação, mas o resultado é uma página para
    imprimir (ou salvar em PDF) aberta no navegador."""

    TITULO = "Relatório para imprimir"
    SUBTITULO = ("As visitas com entrada no período, com o resumo, numa "
                 "página que o navegador imprime ou salva em PDF.")
    AVISO = ("O relatório leva os CPFs completos: guarde ou descarte o papel "
             "com cuidado.")
    BOTAO = "Abrir relatório"

    def confirmar(self):
        periodo = self.periodo_escolhido()
        if periodo is None:
            return None
        desde, ate = periodo
        app = self.app
        ok, registros = app.tentar(app.banco.registros_do_periodo, desde, ate,
                                   app.autor)
        if not ok:
            return None
        if len(registros) > MAXIMO_NO_RELATORIO:
            self.faixa.mostrar(
                "erro", f"São {len(registros)} visitas: é demais para "
                        "imprimir. Escolha um período menor ou use Exportar "
                        "CSV.")
            return None
        pagina = impressao.relatorio_html(registros, desde, ate, app.exibir_cpf,
                                          app.usuario["nome"], app.relogio())
        caminho = impressao.abrir(pagina, "relatorio", app.janela)
        app.tentar(app.banco.registrar_evento, app.autor, "Relatório emitido",
                   f"{desde:%d/%m/%Y} a {ate:%d/%m/%Y}: "
                   f"{plural(len(registros), 'visita', 'visitas')}")
        self.fechar()
        return caminho


# ----------------------------------------------------------------------
# Seções do Painel (3.6)
# ----------------------------------------------------------------------
class SecaoPainel(ComPeriodo):
    """
    Uma seção do Painel: a fileira de números e dois cartões — à esquerda
    um ranking (o nome em cima de cada barra: cabe nome comprido), à
    direita a contagem por dia do período (7 ou 30 dias, hoje em
    destaque). Cada subclasse diz a consulta do banco e o que mostrar.
    """
    SUBTITULO = ""
    NUMEROS = []
    COR_DESTAQUE = "sucesso"
    CONSULTA = ""                    # método do banco: consulta(dias)
    RANKING = ""                     # título do cartão da esquerda
    APOIO_RANKING = "últimos {dias} dias"
    COLUNAS = ""                     # título do cartão da direita
    VISOES = ()                      # ("Por dia", "Por hora"), se houver
    AVISO = ""                       # gráfico sem dados
    AVISO_RANKING = None             # (None: o mesmo AVISO)

    def __init__(self, pai, app):
        self.app = app
        self.resultado = None        # o da última consulta
        self._periodo_lido = None
        self.ranking, self.colunas = [], []
        self.destaque, self.nome_destaque = None, "Hoje"
        self.numeros = LinhaNumeros(pai, self.NUMEROS,
                                    cor_destaque=COR[self.COR_DESTAQUE],
                                    cortar_apoio=True)
        self.numeros.pack(fill="x", padx=px(MARGEM - ESPACO_CARTOES // 2))
        self.cards = self.numeros.cards
        area = area_dos_graficos(pai)
        cab, self.cv_ranking = cartao_grafico(area, 0, self.RANKING)
        self.lbl_ranking = tk.Label(cab, text="", font=FONTE["dica"],
                                    bg=COR["superficie"], fg=COR["texto_3"])
        self.lbl_ranking.pack(side="right")
        cab, self.cv_colunas = cartao_grafico(area, 1, self.COLUNAS)
        self._montar_periodo(cab, self._ao_trocar, self.VISOES)
        for cv in (self.cv_ranking, self.cv_colunas):
            cv.bind("<Configure>", self.redesenhar)

    def _ao_trocar(self):
        if self._montando:
            return
        if self.seletor_periodo.ativa != self._periodo_lido:
            self.atualizar()             # outro período: números e gráficos
        else:
            self._ler_colunas()          # só a visão (por dia ou por hora)
            self.redesenhar()

    def atualizar(self):
        """Relê a seção no banco (uma consulta, calculada no SQL)."""
        dias = self.dias
        ok, r = self.app.tentar(getattr(self.app.banco, self.CONSULTA), dias)
        if not ok:
            return
        self.resultado, self._periodo_lido = r, self.seletor_periodo.ativa
        self.lbl_ranking.config(text=self.APOIO_RANKING.format(dias=dias))
        self.mostrar(r, dias)
        self._ler_colunas()
        self.redesenhar()

    def mostrar(self, r, dias):
        """Os números e o ranking (cada seção)."""
        raise NotImplementedError

    def _ler_colunas(self):
        """Por dia (hoje em destaque) ou por hora (o pico em destaque)."""
        r = self.resultado
        if self.seletor_visao is not None and \
                self.seletor_visao.ativa == VISOES[1]:
            horas = r["por_hora"]
            pico = max(range(24), key=lambda h: horas[h])
            self.colunas = [(f"{h:02d}h" if h % 3 == 0 else "", n)
                            for h, n in enumerate(horas)]
            self.destaque, self.nome_destaque = pico, f"{pico:02d}h"
            return
        dias = len(r["por_dia"])
        self.colunas = [
            (d.strftime("%d/%m") if dias <= 7 or n % 5 == 0 else "", total)
            for n, (d, total) in enumerate(r["por_dia"])]
        self.destaque, self.nome_destaque = None, "Hoje"

    def redesenhar(self, event=None):
        if self.resultado is None:
            return
        desenhar_ranking(self.cv_ranking, self.ranking,
                         self.AVISO_RANKING or self.AVISO)
        desenhar_colunas(self.cv_colunas, self.colunas, self.destaque,
                         self.nome_destaque, self.AVISO)

    def _mostrar(self, chave, valor, apoio, cor=None, cor_apoio=None):
        self.numeros.mostrar(chave, valor, apoio,
                             cor=COR[cor] if cor else None,
                             cor_apoio=COR[cor_apoio] if cor_apoio else None)


def _em(n, dias):
    return f"{n} em {dias} dias"


def _com(*partes):
    """"Laboratório 2 · Carla Nogueira" (sem as partes vazias)."""
    return "  ·  ".join(p for p in partes if p)


class SecaoVeiculos(SecaoPainel):
    SUBTITULO = "Estacionamento agora e entradas de carro"
    NUMEROS = [("agora", "No estacionamento"), ("hoje", "Entradas hoje"),
               ("pendentes", "Pendentes"), ("antigo", "Há mais tempo"),
               ("autorizado", "Com autorizado")]
    CONSULTA = "painel_veiculos"
    RANKING = "Por tipo de acesso"
    APOIO_RANKING = "entradas em {dias} dias"
    COLUNAS = "Entradas"
    VISOES = VISOES
    AVISO = "Nenhum carro neste período"

    def mostrar(self, r, dias):
        agora, vagas = r["no_estacionamento"], r["vagas"]
        lotado = bool(vagas) and agora >= vagas
        self._mostrar("agora", agora,
                      _com(f"de {vagas} vagas", "lotado" if lotado else "")
                      if vagas else "sem controle de vagas",
                      cor="erro" if lotado else None)
        self._mostrar("hoje", r["entradas_hoje"],
                      plural(r["saidas_hoje"], "saída hoje", "saídas hoje"))
        self._mostrar("pendentes", r["pendentes"],
                      plural(r["dono_fora"], "com o dono fora",
                             "com o dono fora") if r["dono_fora"]
                      else "após o fechamento",
                      cor="alerta" if r["pendentes"] else None)
        antigo = r["mais_antigo"]
        if antigo is None:
            self._mostrar("antigo", "—", "estacionamento vazio")
        else:
            self._mostrar("antigo", duracao(antigo["ha"]),
                          _com(antigo["placa"], antigo["nome"]))
        com_senha = r["sem_o_dono"] - r["com_autorizado"]
        self._mostrar("autorizado", r["com_autorizado"],
                      _com(f"saídas em {dias} dias",
                           f"+ {com_senha} com senha" if com_senha else ""))
        self.ranking = [(PLURAL_TIPO.get(t, t), total, f"{dentro} agora")
                        for t, total, dentro in r["por_tipo"]]


class SecaoEntregas(SecaoPainel):
    SUBTITULO = "Encomendas na portaria e entregadores"
    NUMEROS = [("aguardando", "Aguardando"),
               ("recebidas", "Recebidas hoje"),
               ("retiradas", "Retiradas hoje"),
               ("tempo", "Espera média"),
               ("entregadores", "Entregadores hoje")]
    COR_DESTAQUE = "texto"
    CONSULTA = "painel_entregas"
    RANKING = "Quem mais recebe"
    COLUNAS = "Encomendas recebidas"
    AVISO = "Nenhuma encomenda neste período"

    def mostrar(self, r, dias):
        antiga = r["mais_antiga"]
        self._mostrar("aguardando", r["aguardando"],
                      f"mais antiga: {duracao(antiga['ha'])}" if antiga
                      else "nenhuma na portaria")
        self._mostrar("recebidas", r["recebidas_hoje"],
                      _em(r["recebidas_periodo"], dias))
        self._mostrar("retiradas", r["retiradas_hoje"],
                      _em(r["retiradas_periodo"], dias))
        if r["tempo_medio"] is None:
            self._mostrar("tempo", "—", f"sem retiradas em {dias} dias")
        else:
            self._mostrar("tempo", duracao(r["tempo_medio"]),
                          f"em {plural(r['retiradas_periodo'], 'retirada', 'retiradas')}")
        self._mostrar("entregadores", r["entregadores_hoje"],
                      f"{r['entregadores_dentro']} dentro agora"
                      if r["entregadores_dentro"]
                      else _em(r["entregadores_periodo"], dias))
        self.ranking = [(nome, n, f"{aguardam} aguardando" if aguardam else "")
                        for nome, n, aguardam in r["destinatarios"]]


class SecaoChaves(SecaoPainel):
    SUBTITULO = "Chaves emprestadas e o uso de cada uma"
    NUMEROS = [("emprestadas", "Emprestadas agora"),
               ("emprestimos", "Empréstimos hoje"),
               ("devolucoes", "Devoluções hoje"),
               ("fora", "Mais tempo fora"),
               ("tempo", "Tempo médio fora")]
    COR_DESTAQUE = "texto"
    CONSULTA = "painel_chaves"
    RANKING = "Chaves mais usadas"
    COLUNAS = "Empréstimos"
    AVISO = "Nenhum empréstimo neste período"

    def mostrar(self, r, dias):
        cadastradas = r["cadastradas"]
        self._mostrar("emprestadas", r["emprestadas"],
                      f"de {plural(cadastradas, 'chave', 'chaves')}"
                      if cadastradas else "nenhuma chave cadastrada")
        self._mostrar("emprestimos", r["emprestimos_hoje"],
                      _em(r["emprestimos_periodo"], dias))
        self._mostrar("devolucoes", r["devolucoes_hoje"],
                      _em(r["devolucoes_periodo"], dias))
        fora = r["mais_tempo_fora"]
        if fora is None:
            self._mostrar("fora", "—", "todas na portaria")
        else:
            self._mostrar("fora", duracao(fora["ha"]),
                          _com(fora["chave"], fora["nome"]))
        if r["tempo_medio_fora"] is None:
            self._mostrar("tempo", "—", f"sem devoluções em {dias} dias")
        else:
            self._mostrar("tempo", duracao(r["tempo_medio_fora"]),
                          f"em {plural(r['devolucoes_periodo'], 'devolução', 'devoluções')}")
        self.ranking = [(nome, n, "emprestada" if fora_agora else "")
                        for nome, n, fora_agora in r["mais_usadas"]]


class SecaoOcorrencias(SecaoPainel):
    SUBTITULO = "Livro de ocorrências: abertas, por categoria e por dia"
    NUMEROS = [("abertas", "Abertas"), ("hoje", "Registradas hoje"),
               ("periodo", "No período"), ("tempo", "Até resolver"),
               ("antiga", "Mais antiga")]
    CONSULTA = "painel_ocorrencias"
    RANKING = "Por categoria"
    COLUNAS = "Ocorrências registradas"
    AVISO = "Nenhuma ocorrência neste período"

    def mostrar(self, r, dias):
        abertas = r["abertas"]
        self._mostrar("abertas", abertas,
                      "aguardando solução" if abertas else "nenhuma pendente",
                      cor="alerta" if abertas else None)
        self._mostrar("hoje", r["hoje"],
                      self.app.relogio().strftime(FORMATO_DIA))
        self._mostrar("periodo", r["no_periodo"], f"últimos {dias} dias")
        if r["tempo_medio"] is None:
            self._mostrar("tempo", "—", f"nenhuma resolvida em {dias} dias")
        else:
            self._mostrar("tempo", duracao(r["tempo_medio"]),
                          f"em {plural(r['resolvidas_periodo'], 'resolvida', 'resolvidas')}")
        antiga = r["mais_antiga"]
        if antiga is None:
            self._mostrar("antiga", "—", "nenhuma aberta")
        else:
            self._mostrar("antiga", duracao(antiga["ha"]),
                          f"aberta  ·  {antiga['categoria']}")
        self.ranking = [(categoria, n, f"{abertas_dela} abertas"
                         if abertas_dela > 1 else
                         "1 aberta" if abertas_dela else "")
                        for categoria, n, abertas_dela in r["por_categoria"]]


class SecaoFuncionarios(SecaoPainel):
    SUBTITULO = "Presença dos funcionários e os setores"
    NUMEROS = [("dentro", "Dentro agora"), ("hoje", "Vieram hoje"),
               ("antigo", "Há mais tempo"),
               ("permanencia", "Permanência"),
               ("cadastrados", "Cadastrados")]
    CONSULTA = "painel_funcionarios"
    RANKING = "Por setor"
    APOIO_RANKING = "funcionários cadastrados"
    COLUNAS = "Presença por dia"
    AVISO = "Nenhum funcionário neste período"
    AVISO_RANKING = "Nenhum funcionário cadastrado"

    def mostrar(self, r, dias):
        cadastrados = r["cadastrados"]
        self._mostrar("dentro", r["dentro"],
                      f"de {plural(cadastrados, 'funcionário', 'funcionários')}")
        self._mostrar("hoje", r["vieram_hoje"],
                      self.app.relogio().strftime(FORMATO_DIA))
        antigo = r["ha_mais_tempo"]
        if antigo is None:
            self._mostrar("antigo", "—", "ninguém dentro agora")
        else:
            self._mostrar("antigo", duracao(antigo["ha"]),
                          f"dentro  ·  {antigo['nome']}")
        if r["permanencia_media"] is None:
            self._mostrar("permanencia", "—", f"sem saídas em {dias} dias")
        else:
            self._mostrar("permanencia", duracao(r["permanencia_media"]),
                          f"média de {plural(r['saidas_periodo'], 'saída', 'saídas')}")
        sem = r["sem_matricula"]
        self._mostrar("cadastrados", cadastrados,
                      "nenhum cadastrado" if not cadastrados else
                      plural(sem, "sem matrícula", "sem matrícula") if sem
                      else "todos com matrícula",
                      cor_apoio="alerta" if sem else None)
        self.ranking = [(setor, n, f"{dentro} dentro" if dentro else "")
                        for setor, n, dentro in r["por_setor"]]


SECOES_DO_PAINEL = {"Veículos": SecaoVeiculos, "Entregas": SecaoEntregas,
                    "Chaves": SecaoChaves, "Ocorrências": SecaoOcorrencias,
                    "Funcionários": SecaoFuncionarios}
