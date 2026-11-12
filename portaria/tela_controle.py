"""
Página "Controle de acesso" (tela 3 do enunciado do A3): o Movimento (as
visitas do dia e quem está dentro), a pesquisa, o filtro, os veículos no
estacionamento, as faixas de alerta e as saídas, com o Desfazer.

É a metade "controle" da classe AbaCadastro (tela_cadastro.py), separada na
3.2 para cada arquivo cuidar de uma tela: aqui ficam os métodos do Controle
(ControleMixin) e as constantes deles; lá, o formulário do Cadastro. Os dois
dividem o mesmo objeto (self), porque dividem a lista, o relógio e a faixa de
avisos.
"""

import tkinter as tk
from datetime import datetime

from . import horarios, mensagens
from .componentes import (Aviso, bolinha, BotaoTk, Campo, Cartao,
                          data_por_extenso, EsperaDigitacao, inserir_linha,
                          link, mostrar_colunas, plural, Seletor, tabela,
                          titulo_cartao)
from .estilo import COR, FONTE, fonte_icone, ICONE, MARGEM, px
from .tela_autorizacao import autorizar_excecao
from .tela_comando import DICA_VAZIO
from .tela_edicao import JanelaEdicao
from .tela_veiculo import (A_PE, COM_CARRO, com_qual_carro, JUNTO, LEVA,
                           liberar_sem_o_dono, responsavel_saiu_junto,
                           saiu_com_o_veiculo, vai_levar_o_carro)
from .usuarios import eh_admin, pode_editar, pode_excluir
from .validacao import (checar_saida, codigo_da_visita, formatar_celular,
                        formatar_placa, FORMATO, MAXIMO_BUSCA, normalizar,
                        TIPOS_ACESSO)
from .veiculos import esta_lotado, ordem_dos_carros, texto_lotacao
SEGUNDOS_PARA_DESFAZER = 10
SAIDA_JA_FEITA = ("Essa visita já tinha saída ou foi excluída em outra "
                  "estação. A tabela foi atualizada.")
LIMITE_BUSCA = 200
COLUNAS = [("Nome", "Nome", 110, "w"), ("CPF", "CPF", 116, "w"),
           ("Celular", "Telefone", 112, "w"), ("Placa", "Placa", 78, "w"),
           ("Tipo", "Tipo de acesso", 152, "w"),
           ("Entrada", "Entrada", 126, "w"), ("Saida", "Saída", 126, "w"),
           ("Codigo", "Código", 72, "center"), ("Empresa", "Empresa", 150, "w"),
           ("Motivo", "Motivo", 190, "w"), ("Cracha", "Crachá", 126, "w"),
           ("Anfitriao", "Quem procura", 150, "w")]
# o celular, a empresa e o motivo continuam nos values, mas não aparecem
COLUNAS_VISIVEIS = ("Codigo", "Nome", "CPF", "Placa", "Tipo", "Entrada", "Saida")
# desafio extra (registro de prestadores): filtrando por prestador, a tabela
# mostra a empresa e o motivo no lugar da placa e do tipo
COLUNAS_PRESTADOR = ("Codigo", "Nome", "CPF", "Empresa", "Motivo", "Entrada",
                     "Saida")
# quem está dentro não tem saída: no lugar dela, o crachá que a pessoa levou
COLUNAS_DENTRO = ("Codigo", "Nome", "CPF", "Placa", "Tipo", "Entrada", "Cracha")
FILTRO_TODOS = "Todos"
FILTROS = [FILTRO_TODOS, horarios.NO_CAMPUS, horarios.SAIU] + TIPOS_ACESSO
PRESTADOR = "Prestador de serviço"
COLUNAS_VEICULOS = [("placa", "Placa", 96, "w"),
                    ("responsavel", "Responsável", 190, "w"),
                    ("tipo", "Tipo de acesso", 130, "w"),
                    ("desde", "Desde", 120, "w"),
                    ("autorizados", "Pode retirar", 96, "center"),
                    ("onde", "Responsável está", 130, "w")]
LARGURA_SITUACAO_VEICULO = 190     # cabe "Dono fora do campus" com a bolinha
LISTAS = ("Pessoas", "Veículos")

# Abaixo desta altura da página (px lógicos) o layout fica compacto: num
# notebook 1366x768 a 125% a página tem uns 540 (670 px reais).
ALTURA_CONFORTAVEL = 740
# Espaços (px lógicos) de cada densidade
# (2.3: o Movimento sobe — menos espaço entre os dois cartões — e ganha a
# linha do título; as subabas Pessoas | Veículos ficam logo embaixo dele)
ESPACOS = {
    "normal": {"topo": (20, 16), "cartao": 18, "titulo": 10,
               "movimento": (10, MARGEM), "miolo_mov": 10,
               "titulo_mov": (6, 4), "barra": (0, 10)},
    "compacta": {"topo": (6, 6), "cartao": 8, "titulo": 6,
                 "movimento": (4, 10), "miolo_mov": 3,
                 "titulo_mov": (0, 0), "barra": (0, 2)},
}
# Na compacta o rótulo "Comando (F2 · Ctrl+K)" sai de cima do campo e vai
# para dentro dele (sobra altura para o Movimento)
DICA_COMANDO = DICA_VAZIO
DICA_BUSCA = "Pesquisar: nome, CPF, placa, empresa ou código…"


# Situação da visita -> (token da cor da bolinha, marca da linha em
# destaque). Guarda o NOME do token: a cor depende do tema em uso.
APARENCIA = {horarios.NO_CAMPUS: ("sucesso", None),
             horarios.TEMPO_EXCEDIDO: ("alerta", "excedido"),
             horarios.SAIDA_PENDENTE: ("erro", "pendente"),
             horarios.SAIU: ("barra", None),
             horarios.NO_ESTACIONAMENTO: ("sucesso", None),
             horarios.DONO_FORA: ("alerta", None),
             horarios.VEICULO_PENDENTE: ("erro", "pendente")}
LARGURA_SITUACAO = 140         # cabe "Saída pendente" com a bolinha
MOSTRAR_NO_ENCERRAMENTO = 8    # nomes listados na confirmação


def aparencia(situacao):
    """(cor da bolinha no tema em uso, marca da linha em destaque)."""
    token, destaque = APARENCIA[situacao]
    return COR[token], destaque


def _px(par):
    """(antes, depois) em px lógicos -> px reais."""
    return tuple(px(n) for n in par)


class ControleMixin:
    """Os métodos do Controle de acesso (ver o texto no alto)."""

    def _montar_alertas(self):
        """Faixas que só aparecem quando importam (sem caixa de diálogo):
        saídas pendentes e o campus perto de fechar."""
        self.alertas = tk.Frame(self.aba_controle, bg=COR["fundo"])
        self.alertas.pack(fill="x", padx=px(MARGEM))
        self.faixa_pendentes = Aviso(self.alertas, fundo_pai=COR["fundo"])
        self.faixa_fechamento = Aviso(self.alertas, fundo_pai=COR["fundo"])
        self.faixa_esquecidos = Aviso(self.alertas, fundo_pai=COR["fundo"])
        self.faixa_recado = Aviso(self.alertas, fundo_pai=COR["fundo"])
        self.recado = None

    # --------------------------------------------------------------
    # Densidade: normal ou compacta (tela baixa)
    # --------------------------------------------------------------
    def _ao_redimensionar(self, event):
        if event.widget is self.aba_controle:
            self._escolher_densidade(event.height)

    def _escolher_densidade(self, altura):
        """Compacta quando a página, tirando as faixas de alerta, é baixa."""
        livre = altura - self.alertas.winfo_reqheight()
        self._aplicar_densidade(livre < px(ALTURA_CONFORTAVEL))

    def _aplicar_densidade(self, compacta):
        """
        Controle de acesso. Compacta (página baixa, ex.: notebook 1366x768
        a 125%): espaços menores e linhas da tabela mais baixas.
        """
        if compacta == self.compacta:
            return
        self.compacta = compacta
        densidade = "compacta" if compacta else "normal"
        e = ESPACOS[densidade]
        self.cabecalho.pack_configure(pady=_px(e["topo"]))
        if compacta:
            self.lbl_saida_rapida.pack_forget()
        else:
            self.lbl_saida_rapida.pack(anchor="w", pady=(0, px(4)),
                                       before=self.comando.linha_campo)
        self.campo_saida_rapida_quadro.lbl_vazio.config(
            text=DICA_COMANDO[densidade])
        self.seletor_lista.compactar(compacta)
        self.cartao_mov.pack_configure(pady=_px(e["movimento"]))
        self.cartao_mov.miolo.pack_configure(pady=px(e["miolo_mov"]))
        self.barra_titulo_mov.pack_configure(pady=_px(e["titulo_mov"]))
        self.barra_mov.pack_configure(pady=_px(e["barra"]))
        for tab in (self.tabela, self.tabela_veiculos):
            tab.configure(style="Compacta.Tabela.Treeview" if compacta
                          else "Tabela.Treeview")
        for faixa in self._faixas():
            faixa.definir_respiro(5 if compacta else 9)

    def _montar_movimento(self):
        """Tela de Controle de acesso: o título numa linha própria; embaixo
        as subabas Pessoas | Veículos, a pesquisa e o filtro (Combobox); a
        tabela; e, no pé, os botões das ações."""
        self.cartao_mov = Cartao(self.aba_controle, pad=0)
        self.cartao_mov.pack(fill="both", expand=True, padx=px(MARGEM))
        m = self.cartao_mov.miolo
        m.pack_configure(padx=px(1))
        self.barra_titulo_mov = tk.Frame(m, bg=COR["superficie"])
        self.barra_titulo_mov.pack(fill="x", padx=px(19))
        self.titulo_mov = titulo_cartao(self.barra_titulo_mov, "Movimento")
        self.titulo_mov.pack(side="left")
        self.barra_mov = barra = tk.Frame(m, bg=COR["superficie"])
        barra.pack(fill="x", padx=px(19))
        self.seletor_lista = Seletor(barra, LISTAS, self.mostrar_lista,
                                     fundo_pai=COR["superficie"])
        self.seletor_lista.pack(side="left", anchor="s")
        self.campo_busca = Campo(barra, largura=300, icone=ICONE["busca"],
                                 dica_vazio=DICA_BUSCA, maximo=MAXIMO_BUSCA)
        self.busca = self.campo_busca.entrada
        self.espera_busca = EsperaDigitacao(self.busca, self.atualizar_tabela)
        self.busca.bind("<Return>", lambda e: "break")   # Enter na busca não cadastra
        self.busca.bind("<KP_Enter>", lambda e: "break")
        self.campo_filtro = Campo(barra, opcoes=FILTROS, largura=190)
        self.filtro = self.campo_filtro.entrada
        self.filtro.set(FILTRO_TODOS)
        self.filtro.bind("<<ComboboxSelected>>",
                         lambda e: self.atualizar_tabela())

        # os botões do enunciado, no pé da lista (ficam sempre à vista)
        self.barra_acoes = acoes = tk.Frame(m, bg=COR["superficie"])
        self.btn_entrada_controle = BotaoTk(
            acoes, "Registrar entrada", self.registrar_entrada_selecionada,
            "primario")
        self.btn_saida = BotaoTk(acoes, "Registrar saída", self.registrar_saida)
        self.btn_corrigir = BotaoTk(acoes, "Corrigir", self.editar_selecionado)
        self.btn_excluir = None
        if pode_excluir(self.app.usuario):  # RN02: o porteiro nem vê o botão
            self.btn_excluir = BotaoTk(acoes, "Excluir",
                                       self.excluir_selecionado, "perigo")
        self.btn_atualizar = BotaoTk(acoes, "Atualizar", self.atualizar,
                                     "fantasma")
        self.btn_voltar = BotaoTk(acoes, "Voltar", self.voltar, "fantasma")

        # o status ("6 entradas hoje · 5 no campus") e o aviso que some
        # sozinho ficam na linha do título, à direita dele: sobra altura
        # para a tabela (antes era uma linha de rodapé)
        self.status_mov = linha = tk.Frame(self.barra_titulo_mov,
                                           bg=COR["superficie"])
        linha.pack(side="left", fill="x", expand=True, anchor="s",
                   padx=(px(16), 0), pady=(0, px(1)))
        self.lbl_status = tk.Label(linha, text="", font=FONTE["dica"],
                                   bg=COR["superficie"], fg=COR["texto_3"])
        self.lbl_status.pack(side="left")
        # aviso que some sozinho (com o Desfazer da saída): enquanto ele
        # aparece, ocupa o lugar do status (não corta: quebra a linha)
        self.quadro_aviso = aviso = tk.Frame(linha, bg=COR["superficie"])
        self.lbl_aviso_icone = tk.Label(aviso, text="", font=fonte_icone(10),
                                        bg=COR["superficie"], fg=COR["sucesso"])
        self.lbl_aviso_icone.pack(side="left", padx=(0, px(6)))
        self.lbl_aviso = tk.Label(aviso, text="", font=FONTE["corpo_semi"],
                                  bg=COR["superficie"], fg=COR["sucesso"],
                                  justify="left", anchor="w")
        self.lbl_aviso.pack(side="left")
        # a janela fechou (ou o usuário saiu) com o aviso ainda na tela: o
        # "esconder" agendado não roda mais sobre um rótulo que não existe
        self.lbl_aviso.bind("<Destroy>", lambda e: self._cancelar_aviso(),
                            add="+")
        self.btn_desfazer = link(aviso, "Desfazer", self.desfazer_saida)

        self.quadro_pessoas, self.tabela = tabela(
            m, COLUNAS, situacao="Situação", mostrar=COLUNAS_VISIVEIS,
            selecao="extended", largura_situacao=LARGURA_SITUACAO)
        self.tabela.bind("<Double-1>", self._ao_duplo_clique)
        self.quadro_veiculos, self.tabela_veiculos = tabela(
            m, COLUNAS_VEICULOS, situacao="Situação",
            largura_situacao=LARGURA_SITUACAO_VEICULO)
        self.tabela_veiculos.bind("<Double-1>", self._ao_duplo_clique_veiculo)
        for tab in (self.tabela, self.tabela_veiculos):
            # Enter com o foco na tabela não cadastra (o formulário está vazio)
            tab.bind("<Return>", lambda e: "break")
            tab.bind("<KP_Enter>", lambda e: "break")
        self.seletor_lista.selecionar(LISTAS[0])

    def mostrar_lista(self, lista):
        """Seletor do Movimento: as pessoas (visitas) ou os veículos no
        estacionamento. Na lista de veículos não há busca, Corrigir nem
        Excluir: o carro sai pela placa ou pelo "Registrar saída"."""
        self.lista = lista
        pessoas = lista == LISTAS[0]
        botoes = [self.btn_entrada_controle, self.btn_saida, self.btn_corrigir,
                  self.btn_excluir, self.btn_atualizar, self.btn_voltar]
        for w in botoes + [self.campo_busca, self.campo_filtro,
                           self.quadro_pessoas, self.quadro_veiculos,
                           self.barra_acoes]:
            if w is not None:
                w.pack_forget()
        if pessoas:
            self.campo_filtro.pack(side="right")
            self.campo_busca.pack(side="left", fill="x", expand=True,
                                  padx=(px(16), px(12)))
        # o pé primeiro: se faltar altura, é a tabela que encolhe
        self.barra_acoes.pack(side="bottom", fill="x", padx=px(19),
                              pady=(px(8), px(10)))
        visiveis = (botoes if pessoas
                    else [self.btn_saida, self.btn_atualizar, self.btn_voltar])
        # o que apaga fica longe das ações do dia a dia: Excluir à direita
        if pessoas and self.btn_excluir is not None:
            self.btn_excluir.pack(side="right")
        for i, botao in enumerate(b for b in visiveis
                                  if b is not None and b is not self.btn_excluir):
            botao.pack(side="left", padx=(0 if i == 0 else px(8), 0))
        quadro = self.quadro_pessoas if pessoas else self.quadro_veiculos
        quadro.pack(fill="both", expand=True, padx=px(12))
        if hasattr(self, "lbl_status"):
            self._mostrar_status()

    # --------------------------------------------------------------
    # Tabela
    # --------------------------------------------------------------
    def atualizar(self):
        """Página aberta: relê o movimento do banco."""
        self.app.recarregar_registros()
        self.atualizar_tabela()

    def atualizar_situacoes(self):
        """Recalcula a situação (texto, bolinha e destaque) de cada linha
        mostrada com o relógio de agora, sem reler o banco."""
        agora = self.app.relogio()
        for i, iid in enumerate(self.tabela.get_children()):
            registro = self.mostrados.get(int(iid))
            if registro is None:
                continue
            situacao = self._situacao_da_visita(registro, agora)
            cor, destaque = aparencia(situacao)
            tags = (destaque,) if destaque else (("zebra",) if i % 2 else ())
            self.tabela.item(iid, text=situacao, image=bolinha(self.tabela, cor),
                             tags=tags)
        for i, iid in enumerate(self.tabela_veiculos.get_children()):
            estadia = self._estadia(iid)
            if estadia is None:
                continue
            situacao = self._situacao_do_veiculo(estadia, agora)
            cor, destaque = aparencia(situacao)
            tags = (destaque,) if destaque else (("zebra",) if i % 2 else ())
            self.tabela_veiculos.item(iid, text=situacao, tags=tags,
                                      image=bolinha(self.tabela_veiculos, cor))

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
        self._dia_mostrado = agora.date()
        texto = self.busca.get().strip()
        if texto:
            # o filtro vai ao SQL, antes do limite: senão uma visita antiga
            # sumia quando o termo tinha muitas visitas mais novas
            ok, registros = self.app.tentar(
                self.app.banco.buscar_registros, texto, LIMITE_BUSCA,
                so_cpf_completo=not eh_admin(self.app.usuario),
                **self._filtro_do_banco())
            if not ok:
                return
        else:
            registros = self._filtrados(self.app.registros)
        mostrar_colunas(self.tabela, {
            PRESTADOR: COLUNAS_PRESTADOR,
            horarios.NO_CAMPUS: COLUNAS_DENTRO}.get(self.filtro.get(),
                                                    COLUNAS_VISIVEIS))
        selecao = self.tabela.selection()
        self.tabela.delete(*self.tabela.get_children())
        self.mostrados = {}
        for i, r in enumerate(registros):
            self.mostrados[r["id"]] = r
            situacao = self._situacao_da_visita(r, agora)
            cor, destaque = aparencia(situacao)
            inserir_linha(self.tabela, i, (
                r["nome"],
                self.app.exibir_cpf(r.get("cpf", "")),
                formatar_celular(r.get("celular", "")),
                formatar_placa(r.get("placa", "")) or "—",
                r["tipo"],
                r["entrada"],
                r["saida"] or "—",
                codigo_da_visita(r["id"]),
                r.get("empresa") or "—",
                r.get("motivo") or "—",
                r.get("cracha") or "—",
                r.get("anfitriao") or "—"), iid=str(r["id"]),
                situacao=situacao, cor=cor,
                tags=(destaque,) if destaque else (), zebra=not destaque)
        manter = [i for i in selecao if self.tabela.exists(i)]
        if manter:
            self.tabela.selection_set(manter)
        filtrando = self.filtro.get() != FILTRO_TODOS
        self._encontrados = len(registros) if texto or filtrando else None
        self._atualizar_veiculos(agora)
        self._mostrar_status()

        dentro = sum(1 for r in self.app.registros if not r["saida"])
        self.cabecalho.subtitulo.config(
            text=data_por_extenso(self.app.relogio()) + "  ·  ")
        self.lbl_no_campus.config(
            text="Ninguém dentro agora" if not dentro else
            plural(dentro, "pessoa dentro", "pessoas dentro") + " agora")
        self._mostrar_lotacao()
        self.atualizar_alertas()

    def _filtro_do_banco(self):
        filtro = self.filtro.get()
        if filtro == horarios.NO_CAMPUS:
            return {"situacao": "dentro"}
        if filtro == horarios.SAIU:
            return {"situacao": "saiu"}
        return {"tipo": filtro} if filtro in TIPOS_ACESSO else {}

    def _filtrados(self, registros):
        """Combobox do Controle: Todos, Dentro, Saiu ou um tipo de acesso."""
        filtro = self.filtro.get()
        if filtro == horarios.NO_CAMPUS:
            return [r for r in registros if not r["saida"]]
        if filtro == horarios.SAIU:
            return [r for r in registros if r["saida"]]
        if filtro in TIPOS_ACESSO:
            return [r for r in registros if r["tipo"] == filtro]
        return registros

    def _mostrar_lotacao(self):
        """RN37: "· Estacionamento 47/50" no cabeçalho (âmbar se lotado);
        sem controle de vagas, nada."""
        vagas = self.config.vagas if self.config else 0
        texto = texto_lotacao(len(self.veiculos), vagas)
        lotado = esta_lotado(len(self.veiculos), vagas)
        self.lbl_estacionamento.config(
            text=texto, fg=COR["alerta"] if lotado else COR["texto_2"])
        if texto:
            self.chip_estacionamento.pack(side="left", anchor="s",
                                          padx=(px(14), 0), pady=(0, px(7)))
        else:
            self.chip_estacionamento.pack_forget()

    def _mostrar_status(self):
        """Status do Movimento (ao lado do título), conforme a lista mostrada."""
        if self.lista == LISTAS[1]:
            status = (plural(len(self.veiculos), "veículo", "veículos")
                      + " no estacionamento  ·  duplo clique registra a saída "
                        "do carro")
        elif getattr(self, "_encontrados", None) is not None:
            n = self._encontrados
            status = plural(n, "registro encontrado",
                            "registros encontrados")
            if self.busca.get().strip():
                status += " no histórico"
            if n >= LIMITE_BUSCA:
                status += f" (os {LIMITE_BUSCA} mais recentes)"
        else:
            hoje = self.app.relogio().strftime("%d/%m/%Y")
            entradas_hoje = sum(1 for r in self.app.registros
                                if r["entrada"].startswith(hoje))
            status = (f"{plural(entradas_hoje, 'entrada', 'entradas')} hoje"
                      "  ·  duplo clique registra a saída")
        self.lbl_status.config(text=status)

    # --------------------------------------------------------------
    # Veículos no estacionamento
    # --------------------------------------------------------------
    def _situacao_do_veiculo(self, estadia, agora):
        if self.config is None:
            return horarios.NO_ESTACIONAMENTO
        return horarios.situacao_veiculo(self.config, estadia, agora)

    def _atualizar_veiculos(self, agora):
        """Relê os carros no estacionamento e redesenha a lista deles."""
        ok, veiculos = self.app.tentar(self.app.banco.listar_estacionamento)
        if not ok:
            return
        ok, autorizados = self.app.tentar(self.app.banco.contar_autorizados,
                                          agora.date())
        autorizados = autorizados if ok else {}
        self.veiculos = veiculos
        tab = self.tabela_veiculos
        selecao = tab.selection()
        tab.delete(*tab.get_children())
        for i, e in enumerate(veiculos):
            situacao = self._situacao_do_veiculo(e, agora)
            cor, destaque = aparencia(situacao)
            inserir_linha(tab, i, (
                formatar_placa(e["placa"]), e["nome"], e["tipo"] or "—",
                self._quando(e["entrada"]),
                autorizados.get(e["placa"]) or "—",
                horarios.NO_CAMPUS if e["responsavel_dentro"] else horarios.SAIU),
                iid=str(e["id"]), situacao=situacao, cor=cor,
                tags=(destaque,) if destaque else (), zebra=not destaque)
        manter = [i for i in selecao if tab.exists(i)]
        if manter:
            tab.selection_set(manter)
        self.seletor_lista.definir_texto(
            LISTAS[1], f"Veículos ({len(veiculos)})" if veiculos else "Veículos")

    def _estadia(self, iid):
        return next((e for e in self.veiculos if e["id"] == int(iid)), None)

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
        carros = self._veiculos_pendentes(agora)
        if pendentes or carros:
            self._mostrar_pendencias(pendentes, len(carros))

        minutos = horarios.minutos_para_fechar(self.config, agora)
        if minutos is not None:
            fecha = horarios.janela_atual(self.config, agora).fecha
            dentro = sum(contagem.values())
            texto = (f"Campus fecha às {fecha:%H:%M} (em {minutos} min)  ·  "
                     + (f"{dentro} no campus" if dentro else "ninguém no campus"))
            self.faixa_fechamento.mostrar("info", texto, icone=ICONE["relogio"])
        esquecidos = horarios.aviso_carros_esquecidos(self.config,
                                                      self.veiculos, agora)
        if esquecidos:
            self.faixa_esquecidos.mostrar(
                "alerta", esquecidos, icone=ICONE["carro"],
                acao="Ver veículos",
                comando=lambda: self.seletor_lista.selecionar(LISTAS[1]))
        self._mostrar_recado()
        self._posicionar_faixas([f for f, visivel in (
            (self.faixa_recado, self.recado is not None),
            (self.faixa_pendentes, pendentes > 0 or bool(carros)),
            (self.faixa_fechamento, minutos is not None),
            (self.faixa_esquecidos, bool(esquecidos))) if visivel])
        if self.aba_controle.winfo_height() > 1:  # faixas mudam a altura livre
            self.alertas.update_idletasks()
            self._escolher_densidade(self.aba_controle.winfo_height())

    def _veiculos_pendentes(self, agora):
        return [e for e in self.veiculos if self._situacao_do_veiculo(e, agora)
                == horarios.VEICULO_PENDENTE]

    def _mostrar_pendencias(self, pendentes, carros):
        """Faixa vermelha: saídas pendentes (o administrador encerra o dia)
        e carros que passaram do fechamento (saem só pela placa)."""
        admin = eh_admin(self.app.usuario)
        partes = []
        if pendentes:
            partes.append(plural(pendentes, "saída pendente", "saídas pendentes"))
        if carros:
            partes.append(plural(carros, "veículo pendente",
                                 "veículos pendentes"))
        texto = " e ".join(partes) + " depois do fechamento."
        if 1 < self.aba_controle.winfo_height() < px(ALTURA_CONFORTAVEL):
            pass         # tela baixa: uma linha só (sobra altura ao Movimento)
        elif pendentes and not admin:
            texto += (" Registre a saída ou chame um administrador para "
                      "encerrar o dia.")
        elif carros and not pendentes:
            texto += " Registre a saída do carro pela placa."
        acao, comando = None, None
        if pendentes and admin:
            acao, comando = "Encerrar o dia", self.encerrar_dia
        elif carros:
            acao, comando = "Ver veículos", lambda: self.seletor_lista.selecionar(
                LISTAS[1])
        self.faixa_pendentes.mostrar("erro", texto, icone=ICONE["alerta"],
                                     acao=acao, comando=comando)

    def _faixas(self):
        return (self.faixa_recado, self.faixa_pendentes,
                self.faixa_fechamento, self.faixa_esquecidos)

    def _mostrar_recado(self):
        """O recado de turno mais antigo que ninguém leu ainda."""
        ok, recados = self.app.tentar(self.app.banco.listar_recados, True)
        self.recado = recados[-1] if ok and recados else None
        if self.recado is not None:
            r = self.recado
            self.faixa_recado.mostrar(
                "info", f"Recado de {r['autor']} ({r['momento']}): {r['texto']}",
                acao="Marcar como lido", comando=self.marcar_recado_lido)

    def marcar_recado_lido(self):
        if self.recado is not None:
            self.app.tentar(self.app.banco.marcar_recado_lido,
                            self.recado["id"], self.app.autor)
            self.atualizar_alertas()

    def _posicionar_faixas(self, faixas):
        """As faixas visíveis ficam lado a lado, dividindo a largura (uma
        sozinha ocupa tudo): sobra altura para o Movimento na tela
        pequena."""
        for faixa in self._faixas():
            faixa.grid_forget()
        for coluna in range(len(self._faixas())):
            usada = coluna < len(faixas)
            self.alertas.columnconfigure(coluna, weight=1 if usada else 0,
                                         uniform="faixas" if usada else "")
        for coluna, faixa in enumerate(faixas):
            ultima = coluna == len(faixas) - 1
            faixa.grid(row=0, column=coluna, sticky="nsew", pady=(0, px(8)),
                       padx=0 if ultima else (0, px(8)))

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
        carros = self._veiculos_pendentes(self.app.relogio())
        aviso_carros = ("" if not carros else
                        "\n\n" + plural(len(carros), "veículo continua",
                                         "veículos continuam")
                        + " no estacionamento: o carro está lá. Registre a "
                          "saída dele pela placa quando sair.")
        return ("Dar saída automática a "
                + plural(len(pendentes), "visita pendente", "visitas pendentes")
                + ", no prazo do dia de cada entrada (fechamento + tolerância "
                  "da categoria)?\n\n"
                + "\n".join(linhas)
                + "\n\nCada uma fica no histórico como "
                  "\"Saída automática (encerramento)\"."
                + aviso_carros)

    def _registro(self, iid):
        """Registro da linha da tabela (iid = id no banco). Se a linha já
        saiu do movimento (ex.: deu saída e a entrada foi ontem), relê."""
        registro = self.mostrados.get(int(iid))
        if registro is None:
            ok, registro = self.app.tentar(self.app.banco.buscar, int(iid))
        return registro

    def voltar(self):
        """Botão Voltar do Controle: de volta ao Cadastro."""
        self.app.ir_para(self.aba)

    def registrar_entrada_selecionada(self):
        """
        Botão Registrar entrada do Controle: a pessoa escolhida na lista
        (localizada pela pesquisa) entra de novo, com o horário de agora e os
        dados do cadastro. Quem está dentro é recusado (RN05). Falta empresa
        ou motivo (cadastro antigo): abre o Cadastro já preenchido.
        """
        selecao = self.tabela.selection()
        if len(selecao) != 1:
            mensagens.aviso("Atenção", "Selecione uma pessoa na lista (a "
                                       "pesquisa acha pelo nome ou CPF).")
            return
        visita = self._registro(selecao[0])
        if visita is None:
            return
        ok, pessoa = self.app.tentar(self.app.banco.buscar_pessoa, visita["cpf"])
        if not ok:
            return
        p = pessoa or visita
        empresa = p.get("empresa") or visita.get("empresa", "")
        motivo = visita.get("motivo", "")
        if not empresa or not motivo:
            self.app.preencher_pessoa(p)
            (self.empresa if not self.empresa.get() else self.motivo).focus_set()
            self._situacao("alerta", "Cadastro antigo: informe a empresa e o "
                                     "motivo da visita para registrar a entrada.")
            return
        placa = p.get("placa", "")
        if placa and self._carro_no_estacionamento(placa) is not None:
            placa = ""                  # o carro já está lá: entra a pé
        registro = normalizar(p["nome"], p["cpf"], p["celular"], placa, p["tipo"],
                              self._agora_texto(), "", empresa=empresa,
                              motivo=motivo)

        def outro_carro():
            self.app.preencher_pessoa(p)
            self._digitar_outro_carro()
        self.registrar_entrada(registro, placa, p.get("id") if pessoa else None,
                               outro_carro)

    def _saida_de(self, cpf):
        """Link "Registrar saída" da faixa: dá saída na visita aberta."""
        self.app.recarregar_registros()
        abertos = [r for r in self.app.registros
                   if r["cpf"] == cpf and not r["saida"]]
        if abertos and self._dar_saida(abertos):
            ok, pessoa = self.app.tentar(self.app.banco.buscar_pessoa, cpf)
            if ok:
                self._mostrar_situacao(cpf, pessoa)

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
        ids = [int(i) for i in selecionado]
        ok, estadias = self.app.tentar(self.app.banco.listar_estacionamento)
        if not ok:
            return
        carros = [formatar_placa(e["placa"]) for e in estadias
                  if e["registro_id"] in ids]
        aviso_carros = "" if not carros else (
            "\n\n" + ("O carro " if len(carros) == 1 else "Os carros ")
            + ", ".join(carros)
            + (" dessa visita continua" if len(carros) == 1
               else " dessas visitas continuam")
            + " no estacionamento: ele não é apagado com a visita. Para "
              "tirá-lo, registre a saída pela placa.")
        if not self.app.perguntar(
                mensagens.confirmar,
                "Excluir registro",
                "Excluir " + plural(len(selecionado), "registro selecionado",
                                    "registros selecionados") + "?\n"
                "A exclusão fica registrada no histórico." + aviso_carros):
            return
        ok, _ = self.app.tentar(self.app.banco.excluir, ids,
                                autor=self.app.autor)
        self.app.atualizar_tabela()
        if ok:
            self.avisar(plural(len(ids), "registro excluído",
                               "registros excluídos")
                        + (f"; {', '.join(carros)} continua(m) no "
                           "estacionamento." if carros else "."))

    # --------------------------------------------------------------
    # Saída: botão, duplo clique e saída rápida por CPF ou placa
    # --------------------------------------------------------------
    def registrar_saida(self):
        """Botão: saída (data/hora atual) das linhas selecionadas; na lista
        de veículos, a saída do carro selecionado."""
        if self.lista == LISTAS[1]:
            selecionado = self.tabela_veiculos.selection()
            if not selecionado:
                mensagens.aviso("Atenção", "Selecione um veículo na lista.")
                return
            self.registrar_saida_veiculo(selecionado[0])
            return
        selecionado = self.tabela.selection()
        if not selecionado:
            mensagens.aviso("Atenção", "Selecione um registro na tabela.")
            return
        self._dar_saida([self._registro(i) for i in selecionado])

    def _ao_duplo_clique_veiculo(self, event):
        linha = self.tabela_veiculos.identify_row(event.y)
        if linha:
            self.registrar_saida_veiculo(linha)
        return "break"

    def registrar_saida_veiculo(self, iid):
        estadia = self._estadia(iid)
        if estadia is not None:
            self._saida_do_carro(estadia)

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
        """Enter no campo Comando (o nome de antes continua): a linha passa
        pelo léxico, sintático e semântico e, sem erro, é executada pelos
        mesmos caminhos do formulário (tela_comando.py). Só o CPF ou só a
        placa continuam dando a saída, como na Saída rápida: pela placa
        SÓ o carro sai (nunca a pessoa: QA1 A1); o CPF de quem saiu a pé
        e deixou o carro oferece a saída do carro, com a senha (RN32)."""
        return self.comando.executar(event)

    def _saida_do_carro(self, estadia):
        """O carro sai (placa ou lista de veículos). Com o dono no campus,
        pergunta se ele saiu junto: junto, os dois saem sem senha. Sem o
        dono (fora do campus ou "Só o carro saiu"), RN32: só com a senha
        de um administrador."""
        if estadia["responsavel_dentro"]:
            visita = next((r for r in self.app.registros if r["cpf"] ==
                           estadia["cpf"] and not r["saida"]), None)
            resposta = responsavel_saiu_junto(self.app, estadia)
            if resposta is None:
                return False
            if resposta == JUNTO and visita is not None:
                return self._dar_saida([visita],
                                       com_veiculo={visita["id"]: estadia["id"]})
        levou = self._autorizado_leva(estadia)
        if levou is not None:
            return levou
        return self._sair_so_o_carro(estadia)

    def _autorizado_leva(self, estadia):
        """RN35 na saída pela placa: alguém da lista dessa placa está no
        campus a pé? Pergunta a cada um se vai levar o carro; "Sim" dá a
        saída dessa pessoa com o carro (sem senha). None = ninguém levou
        (segue para a RN32); False = cancelou."""
        ok, autorizados = self.app.tentar(self.app.banco.autorizados_no_campus,
                                          estadia["placa"],
                                          self.app.relogio().date())
        if not ok:
            return False
        for autorizado in autorizados:
            visita = next((r for r in self.app.registros
                           if r["id"] == autorizado["registro_id"]), None)
            if visita is None:
                continue
            resposta = vai_levar_o_carro(self.app, autorizado["nome"], estadia,
                                         autorizado)
            if resposta is None:
                return False
            if resposta == LEVA:
                return self._dar_saida([visita],
                                       com_veiculo={visita["id"]: estadia["id"]},
                                       levados={visita["id"]: estadia})
        return None

    def _sair_so_o_carro(self, estadia):
        """O carro sai sem o dono: mensagem + senha do administrador."""
        autorizacao = liberar_sem_o_dono(self.app, estadia)
        if autorizacao is None:
            return False
        momento = self.app.relogio().replace(second=0, microsecond=0)
        saida = momento.strftime(FORMATO)
        ok, gravou = self.app.tentar(self.app.banco.registrar_saida_veiculo,
                                     estadia["id"], saida, autor=self.app.autor,
                                     autorizacao=autorizacao)
        if not ok:
            return False
        self.app.atualizar_tabela()
        if not gravou:
            mensagens.aviso("Saída", "Esse carro já tinha saído (outra "
                                     "estação). A lista foi atualizada.")
            return False
        self._saida_para_desfazer = saida
        self.avisar(f"Saída do carro {formatar_placa(estadia['placa'])} "
                    f"registrada às {momento:%H:%M}, sem o dono (liberada por "
                    f"{autorizacao['autorizado_por']}).",
                    desfazer={"veiculos": [estadia["id"]]})
        return True

    def _perguntar_veiculos(self, registros):
        """Quem sai e tem carro no estacionamento: saiu com ele? Com dois
        carros (saiu a pé e voltou com outro), pergunta primeiro pelo carro
        desta visita e depois pelos outros, até um "Saiu de carro".
        RN40: com dois carros dela no estacionamento, UMA pergunta ("Com
        qual carro Carla está saindo?") e sai um só.
        RN35: quem saiu a pé (sem carro dele) e está na lista da placa de
        outro carro no estacionamento ouve "Vai levar o carro X de Y?".
        Devolve ({id da visita: id da estadia que sai},
        {id da visita: [placas que ficam]}, {id da visita: estadia levada
        de outro dono}) ou None (cancelou)."""
        ok, estadias = self.app.tentar(self.app.banco.listar_estacionamento)
        if not ok:
            return None
        por_cpf = {}
        for e in sorted(estadias, key=lambda e: (e["entrada"], e["id"])):
            por_cpf.setdefault(e["cpf"], []).append(e)
        de_carro, a_pe, levados = {}, {}, {}
        for r in registros:
            carros = ordem_dos_carros(por_cpf.get(r["cpf"], []), r["id"])
            if len(carros) == 1:
                resposta = saiu_com_o_veiculo(self.app, r["nome"], carros[0])
                resposta = carros[0]["id"] if resposta == COM_CARRO else resposta
            elif carros:
                resposta = com_qual_carro(self.app, r["nome"], carros)
            if carros:
                if resposta is None:
                    return None
                if resposta == A_PE:
                    a_pe[r["id"]] = [e["placa"] for e in carros]
                else:
                    de_carro[r["id"]] = resposta
            if r["id"] not in de_carro and not r["placa"]:
                estadia = self._perguntar_se_leva(r, set(de_carro.values()))
                if estadia is False:
                    return None
                if estadia is not None:
                    de_carro[r["id"]] = estadia["id"]
                    levados[r["id"]] = estadia
        return de_carro, a_pe, levados

    def _perguntar_se_leva(self, registro, ja_saindo):
        """RN35: a estadia que quem sai vai levar, None (nenhuma) ou False
        (cancelou)."""
        ok, levaveis = self.app.tentar(self.app.banco.veiculos_que_pode_levar,
                                       registro["cpf"],
                                       self.app.relogio().date())
        if not ok:
            return None
        for estadia in levaveis:
            if estadia["id"] in ja_saindo:
                continue
            resposta = vai_levar_o_carro(self.app, registro["nome"], estadia,
                                         estadia["autorizado"])
            if resposta is None:
                return False
            if resposta == LEVA:
                return estadia
        return None

    def dar_saida(self, registros, com_veiculo=None, levados=None,
                  momento=None, a_pe=None):
        """A saída de uma pessoa, pelo mesmo caminho do botão, do duplo
        clique e da Saída rápida (a linha de comando usa este)."""
        return self._dar_saida(registros, com_veiculo, levados, momento, a_pe)

    def saida_do_carro(self, estadia):
        """A saída do carro pela placa (Saída rápida e linha de comando)."""
        return self._saida_do_carro(estadia)

    def sair_so_o_carro(self, estadia):
        """O carro sai sem o dono: só com a senha (RN32)."""
        return self._sair_so_o_carro(estadia)

    def _dar_saida(self, registros, com_veiculo=None, levados=None,
                   momento=None, a_pe=None):
        """Registra a saída agora; avisa sem travar a tela e oferece desfazer.
        Quem tem carro no estacionamento responde se saiu com ele (a não ser
        que `com_veiculo` já diga; `a_pe` = as placas que ficam, para o
        aviso). Visita que passaria de 24 h é exceção: pede a autorização
        antes. `momento` (comando "saida ... as 14:05"): a saída num horário
        de hoje que já passou; o lançamento retroativo segue a RN24
        (horarios.retroativo), como na correção."""
        agora = self.app.relogio().replace(second=0, microsecond=0)
        retroativa = momento is not None
        momento = momento or agora
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
        a_pe, levados = dict(a_pe or {}), dict(levados or {})
        if com_veiculo is None:
            respostas = self._perguntar_veiculos(prontos)
            if respostas is None:
                return False
            com_veiculo, a_pe, levados = respostas
        regras = horarios.Excecoes([
            f"{r['nome']}: {regra}" for r in prontos
            for regra in horarios.excecoes_da_duracao(
                datetime.strptime(r["entrada"], FORMATO), momento)])
        if retroativa:
            ok, config = self.app.tentar(self.app.banco.ler_configuracao)
            if not ok:
                return False
            for r in prontos:
                regras.juntar(horarios.retroativo(config, "Saída", momento,
                                                  self.app.relogio(),
                                                  r["tipo"]))
        autorizacao = None
        if regras:
            autorizacao = autorizar_excecao(self.app, regras, "Esta saída")
            if autorizacao is None:
                return False
        saida = momento.strftime(FORMATO)
        ok, gravados = self.app.tentar(
            self.app.banco.registrar_saidas, [r["id"] for r in prontos], saida,
            autor=self.app.autor, autorizacao=autorizacao,
            com_veiculo=dict(com_veiculo))
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
                 + self._com_carro(gravadas, com_veiculo, a_pe, levados)
                 + self._com_autorizacao(autorizacao))
        crachas = [r["cracha"] for r in gravadas if r.get("cracha")]
        if crachas:                        # (o crachá volta para a portaria)
            texto += (". Recolha " + ("o crachá " if len(crachas) == 1
                                      else "os crachás ") + ", ".join(crachas))
        nao_gravadas = len(recusas) + len(prontos) - len(gravadas)
        if nao_gravadas:
            texto += (f" ({nao_gravadas} já tinha(m) saída ou foi(ram) "
                      "excluída(s) em outra estação.)")
        self._saida_para_desfazer = saida
        self.avisar(texto, desfazer=gravados)
        return True

    @staticmethod
    def _com_carro(gravadas, com_veiculo, a_pe, levados=None):
        """' de carro' / ' a pé (o carro ABC-1234 fica)' / ' (levou o carro
        BRA2E19 de Carla)', se for o caso."""
        ids = {r["id"] for r in gravadas}
        levou = [e for i, e in (levados or {}).items() if i in ids]
        if len(ids) == 1 and levou:
            e = levou[0]
            return (f" (levou o carro {formatar_placa(e['placa'])} de "
                    f"{e['nome'].split()[0]}, autorizado)")
        if ids & set(com_veiculo):
            return " (saiu de carro)" if len(ids) == 1 else " (com os carros)"
        ficam = [formatar_placa(p) for i, placas in a_pe.items() if i in ids
                 for p in placas]
        if len(ficam) == 1:
            return f" (a pé; o carro {ficam[0]} fica no estacionamento)"
        if ficam:
            return (f" (a pé; os carros {', '.join(ficam)} ficam no "
                    "estacionamento)")
        return ""

    def desfazer_saida(self):
        """Desfaz só as saídas que esta tela gravou, com o horário gravado
        (nunca a saída dada ou corrigida por outra estação)."""
        ids = self._para_desfazer
        if not ids:
            return
        if isinstance(ids, dict):            # saída só do carro
            ok, desfeitas = self.app.tentar(
                self.app.banco.desfazer_saida_veiculos, ids["veiculos"],
                self._saida_para_desfazer, autor=self.app.autor)
            if ok:
                self.app.atualizar_tabela()
                self.avisar("Saída desfeita: o carro voltou a constar no "
                            "estacionamento." if desfeitas else "",
                            icone=ICONE["desfazer"])
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
        """Mensagem na linha do título do Movimento que some sozinha; com `desfazer`
        (ids), mostra o link Desfazer."""
        if self._timer_aviso:
            self.aba.after_cancel(self._timer_aviso)
        self.ultimo_aviso = texto          # a linha de comando repete
        self.lbl_aviso.config(text=texto)
        self.lbl_aviso_icone.config(text=(icone or ICONE["ok"]) if texto else "")
        self._para_desfazer = desfazer
        if desfazer:
            self.btn_desfazer.pack(side="left", padx=(px(10), 0))
        else:
            self.btn_desfazer.pack_forget()
        if texto:
            self.lbl_status.pack_forget()
            self.quadro_aviso.pack(side="left", fill="x")
            largura = self.status_mov.winfo_width()
            self.lbl_aviso.config(wraplength=max(largura - px(130), px(240))
                                  if largura > 1 else 0)
        else:
            self._mostrar_status_no_rodape()
        self._timer_aviso = self.aba.after(SEGUNDOS_PARA_DESFAZER * 1000,
                                           self._esconder_aviso)

    def _cancelar_aviso(self):
        if self._timer_aviso:
            try:
                self.aba.after_cancel(self._timer_aviso)
            except tk.TclError:
                pass
            self._timer_aviso = None

    def _esconder_aviso(self):
        self._timer_aviso = None
        self._para_desfazer = None
        self.lbl_aviso.config(text="")
        self.lbl_aviso_icone.config(text="")
        self.btn_desfazer.pack_forget()
        self._mostrar_status_no_rodape()

    def _mostrar_status_no_rodape(self):
        self.quadro_aviso.pack_forget()
        self.lbl_status.pack(side="left")
