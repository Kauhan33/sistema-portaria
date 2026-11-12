"""
Página Painel: cinco números do movimento (no campus agora, entradas de
hoje, permanência média, veículos no estacionamento agora — com os
pendentes depois do fechamento, ou o total de visitas com veículo, no
apoio — e tempo excedido — as visitas abertas acima da permanência máxima
da categoria, com as saídas pendentes no apoio) e dois gráficos (pessoas por tipo de
acesso e entradas nos últimos 7 dias). Os números vêm do banco
(banco.resumo_painel, calculado no SQL); o desenho fica em graficos.py.
O administrador exporta os registros de um período para planilha (CSV).
RN38: com só 1 administrador ativo, a faixa "Só existe 1 administrador
ativo. Crie um segundo." aparece para o administrador (se ele perder a
senha e os códigos de recuperação, ninguém mais entra como administrador).
"""

import tkinter as tk
from datetime import datetime, timedelta

from . import backup, horarios, impressao, mensagens
from .componentes import (Aviso, Botao, Cabecalho, Cartao, Dialogo, Seletor,
                          campo_rotulado, plural, titulo_cartao)
from .consultas import formatar_duracao
from .estilo import COR, ESPACO_CARTOES, FONTE, ICONE, MARGEM, px
from .graficos import desenhar_barras_horizontais, desenhar_barras_verticais
from .usuarios import eh_admin, precisa_de_outro_admin
from .validacao import TIPOS_ACESSO

PLURAL_TIPO = {"Aluno": "Alunos", "Professor": "Professores",
               "Funcionário": "Funcionários", "Visitante": "Visitantes",
               "Entregador": "Entregadores",
               "Prestador de serviço": "Prestadores"}
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


class AbaDashboard:
    def __init__(self, aba, app):
        self.aba = aba
        self.app = app
        self.cards = {}                            # chave -> (valor, apoio)
        self.com_veiculo = 0                       # visitas com placa (total)
        self.dados = {"tipos": [], "dias": []}     # dados prontos dos gráficos
        self.destaque, self.nome_destaque = None, "Hoje"
        self.btn_exportar = self.btn_relatorio = None
        self.dialogo = None

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
        self._montar_numeros()
        self._montar_graficos()
        self.atualizar()

    # --------------------------------------------------------------
    # Montagem
    # --------------------------------------------------------------
    def _montar_numeros(self):
        self.linha_numeros = linha = tk.Frame(self.aba, bg=COR["fundo"])
        linha.pack(fill="x", padx=px(MARGEM - ESPACO_CARTOES // 2))
        linha.columnconfigure(tuple(range(len(NUMEROS))), weight=1,
                              uniform="numeros")
        for coluna, (chave, rotulo) in enumerate(NUMEROS):
            cartao = Cartao(linha, pad=14)
            cartao.grid(row=0, column=coluna, sticky="nsew",
                        padx=px(ESPACO_CARTOES // 2))
            m = cartao.miolo
            tk.Label(m, text=rotulo, font=FONTE["corpo_semi"], bg=COR["superficie"],
                     fg=COR["texto_2"]).pack(anchor="w")
            destaque = coluna == 0
            valor = tk.Label(m, text="0", bg=COR["superficie"],
                             font=FONTE["kpi_destaque" if destaque else "kpi"],
                             fg=COR["sucesso"] if destaque else COR["texto"])
            valor.pack(anchor="w", pady=(px(2), 0))
            apoio = tk.Label(m, text="", font=FONTE["dica"], bg=COR["superficie"],
                             fg=COR["texto_3"])
            apoio.pack(anchor="w", side="bottom")
            self.cards[chave] = (valor, apoio)

    def _montar_graficos(self):
        area = tk.Frame(self.aba, bg=COR["fundo"])
        area.pack(fill="both", expand=True, padx=px(MARGEM - ESPACO_CARTOES // 2),
                  pady=(px(ESPACO_CARTOES), px(MARGEM)))
        area.columnconfigure((0, 1), weight=1, uniform="g")
        area.rowconfigure(0, weight=1)
        self.cv_tipos = self._novo_grafico(area, 0, "Pessoas por tipo de acesso",
                                           "todas as visitas")
        self.cv_dias = self._novo_grafico(area, 1, "Entradas", "hoje em destaque",
                                          com_periodo=True)

    def _novo_grafico(self, area, coluna, titulo, apoio, com_periodo=False):
        cartao = Cartao(area, pad=18)
        cartao.grid(row=0, column=coluna, sticky="nsew",
                    padx=px(ESPACO_CARTOES // 2))
        cab = tk.Frame(cartao.miolo, bg=COR["superficie"])
        cab.pack(fill="x", pady=(0, px(12)))
        titulo_cartao(cab, titulo).pack(side="left")
        rotulo = tk.Label(cab, text=apoio, font=FONTE["dica"],
                          bg=COR["superficie"], fg=COR["texto_3"])
        rotulo.pack(side="right")
        if com_periodo:
            # por dia ou por hora (o horário de pico), em 7 ou 30 dias
            self.lbl_apoio_dias = rotulo
            self.seletor_periodo = Seletor(cab, tuple(PERIODOS),
                                           lambda o: self._ao_trocar_visao(),
                                           fundo_pai=COR["superficie"])
            self.seletor_visao = Seletor(cab, VISOES,
                                         lambda o: self._ao_trocar_visao(),
                                         fundo_pai=COR["superficie"])
            for seletor in (self.seletor_visao, self.seletor_periodo):
                seletor.compactar()
                seletor.pack(side="left", padx=(px(16), 0))
            self._montando = True
            self.seletor_visao.selecionar(VISOES[0])
            self.seletor_periodo.selecionar("7 dias")
            self._montando = False
        cv = tk.Canvas(cartao.miolo, bg=COR["superficie"], height=px(ALTURA_GRAFICO),
                       highlightthickness=0, bd=0)
        cv.pack(fill="both", expand=True)
        cv.bind("<Configure>", self.redesenhar_graficos)
        return cv

    # --------------------------------------------------------------
    # Dados
    # --------------------------------------------------------------
    def atualizar(self):
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
                          f"em {plural(r['saidas'], 'visita encerrada', 'visitas encerradas')}")
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
        dias = PERIODOS[self.seletor_periodo.ativa]
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
                      if pendentes else "acima do tempo permitido")
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
                                  before=self.linha_numeros)
        else:
            self.faixa_admin.pack_forget()

    def _mostrar(self, chave, valor, apoio):
        self.cards[chave][0].config(text=str(valor))
        self.cards[chave][1].config(text=apoio)

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
