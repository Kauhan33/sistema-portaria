"""
Página Pessoas, com três subabas (2.3: a antiga página Bloqueios virou a
desativação, aqui dentro):

- Ativas: todo mundo que pode entrar (busca no banco,
  banco.buscar_pessoas), ordenada pela coluna clicada no cabeçalho (1º
  clique crescente, 2º decrescente; abre ordenada pela situação: no campus,
  fora, e depois pelo nome);
- Pessoas desativadas: as pessoas (CPFs) desativadas — com o cadastro ou "(sem
  cadastro)" —, o motivo, quando e quem desativou; "Mostrar reativadas"
  traz também as que já voltaram;
- Veículos desativados: as placas desativadas, com o dono (quem tem a placa
  no cadastro), o motivo, quando e quem desativou.

Desativado não entra (RN12). Só o administrador desativa e reativa (o
porteiro vê as listas, com o aviso); tudo vai ao histórico. No banco é a
tabela de bloqueios de sempre (dados.Banco.desativar / reativar).

"Nova pessoa" (cabeçalho) cadastra CPF, nome, celular, placa (opcional)
e tipo SEM registrar entrada, com a mesma validação e os mesmos limites da
entrada; CPF já cadastrado é recusado e abre a ficha que já existe; CPF
desativado avisa (pode cadastrar, mas continua sem entrar).

À direita (Ativas e Pessoas desativadas), a ficha da pessoa escolhida: nome, CPF,
celular e tipo, placa desenhada (Mercosul ou antiga), número de visitas,
faixa de situação, os botões (sempre à vista, no pé da ficha) Registrar
entrada e Editar (o mesmo diálogo da Nova pessoa, com o CPF fixo:
qualquer usuário corrige o cadastro, como já fazia) e, para o
administrador, Desativar / Reativar e Excluir (RN42: só o cadastro de
quem nunca teve visita; com histórico, o botão explica que é preciso
desativar); e duas seções:
- Visitas: o histórico de visitas dela, da mais recente para a mais
  antiga (entrada, saída, duração, tipo, placa e situação), com os dados
  que foram preenchidos em cada registro;
- Veículo (RN35): "Quem pode retirar" o carro da placa dela sem o dono e
  sem senha, com Adicionar, Validade (RN45: trocar a data) e Remover. O
  porteiro só adiciona ou muda a validade com o dono no campus (o botão
  fica apagado, com a dica); o administrador, a qualquer hora. Qualquer um
  remove. O administrador desativa (ou reativa) a placa aqui também.
"""

import tkinter as tk
import unicodedata
from datetime import datetime
from tkinter import ttk

from . import horarios, mensagens
from .componentes import (Alternador, Aviso, Botao, Cabecalho, Campo, Cartao,
                          Dialogo, EsperaDigitacao, OrdenacaoTabela, Placa,
                          Seletor, campo_rotulado, inserir_linha, link, plural,
                          tabela, titulo_cartao)
from .consultas import encontrar_dentro
from .estilo import (COR, ESPACO_CARTOES, FONTE, ICONE, MARGEM, fonte_icone,
                     px)
from .usuarios import (eh_admin, pode_excluir_pessoa,
                       pode_gerenciar_desativacoes)
from .validacao import (DESATIVADO, MAXIMO_BUSCA, MAXIMO_MOTIVO, MAXIMO_NOME,
                        O_QUE, TIPOS_ACESSO, converter_data, cpf_valido,
                        formatar_celular, formatar_desativacao,
                        formatar_placa, normalizar, normalizar_desativacao,
                        so_digitos, validar_campos, validar_desativacao,
                        validar_placas, MAXIMO_PLACAS_PESSOA)
from .veiculos import (DONO_PRECISA_ESTAR, pode_cadastrar_autorizado,
                       validar_autorizado, validar_nova_validade)

ABAS = ("Ativas", "Pessoas desativadas", "Veículos desativados")
COLUNAS = [("nome", "Nome", 160, "w"), ("cpf", "CPF", 112, "w"),
           ("celular", "Celular", 115, "w"), ("placa", "Placa", 80, "w"),
           ("tipo", "Tipo", 110, "w"), ("visitas", "Visitas", 66, "center"),
           ("ultima", "Última visita", 124, "w"),
           ("situacao", "Situação", 95, "w")]
# a ficha mostra o resto; os values continuam completos
COLUNAS_VISIVEIS = ("nome", "cpf", "visitas", "ultima")
LIMITE_BUSCA = 200
SEM_SELECAO = "Escolha uma pessoa na lista para ver a ficha."
SEM_CADASTRO = "(sem cadastro)"
SECOES_FICHA = ("Visitas", "Veículo")
CARROS_EM_BOTOES = 3     # RN47: mais carros que isso viram uma lista na ficha
# Abaixo desta altura (px lógicos) a página fica compacta: no notebook
# 1366x670 a página tem uns 536
ALTURA_CONFORTAVEL = 700
COLUNAS_AUTORIZADOS = [("nome", "Nome", 124, "w"),
                       ("cpf", "CPF", 104, "w"),
                       ("validade", "Válido até", 92, "w")]
SEM_VEICULO = ("Sem veículo cadastrado. A lista de quem pode retirar vale "
               "para a placa da pessoa.")
LIMITE_VISITAS = 200
SEM_VISITAS = "Nenhuma visita registrada."

# Pessoas desativadas (CPF) e Veículos desativados (placa): colunas de cada lista.
# Com a ficha ao lado, a de pessoas mostra nome, CPF e motivo; com largura
# sobrando (tela grande), também quando e quem desativou.
COLUNAS_DESATIVACAO = {
    "cpf": [("nome", "Nome", 140, "w"), ("valor", "CPF", 104, "w"),
            ("motivo", "Motivo", 150, "w"),
            ("criado", "Desativada em", 124, "w"), ("por", "Por", 90, "w"),
            ("reativado", "Reativada em", 190, "w")],
    "placa": [("valor", "Placa", 90, "w"), ("nome", "Pessoa", 150, "w"),
              ("motivo", "Motivo", 300, "w"),
              ("criado", "Desativado em", 124, "w"), ("por", "Por", 90, "w"),
              ("reativado", "Reativado em", 190, "w")],
}
VISIVEIS_ESTREITA = ("nome", "valor", "motivo")
# estreita mostrando também as reativadas: a coluna Situação entra e o
# motivo fica só na ficha
VISIVEIS_ESTREITA_REATIVADAS = ("nome", "valor")
LARGURA_PARA_TODAS = 720        # px lógicos da tabela de pessoas desativadas
TEXTOS_LISTA = {
    "cpf": {"botao": "Desativar CPF", "reativadas": "Mostrar reativadas",
            "vazia": "Nenhuma pessoa desativada",
            "uma": "pessoa desativada", "varias": "pessoas desativadas",
            "porteiro": "Pessoas desativadas não entram. Só um administrador "
                        "desativa ou reativa."},
    "placa": {"botao": "Desativar placa", "reativadas": "Mostrar reativados",
              "vazia": "Nenhum veículo desativado",
              "uma": "veículo desativado", "varias": "veículos desativados",
              "porteiro": "Veículos desativados não entram. Só um "
                          "administrador desativa ou reativa."},
}
SO_ADMIN = "Somente o administrador desativa ou reativa pessoas e veículos."

# Situação na lista: (ordem, texto da bolinha, cor). Crescente = quem está
# no campus primeiro (o que a guarita mais procura).
NO_CAMPUS, FORA = 0, 2
# token da cor de cada situação de visita (as do Movimento); o nome, e não
# a cor, porque a cor depende do tema em uso
COR_SITUACAO = {horarios.NO_CAMPUS: "sucesso",
                horarios.TEMPO_EXCEDIDO: "alerta",
                horarios.SAIDA_PENDENTE: "erro",
                horarios.SAIU: "texto_3"}   # é texto: precisa de 4,5:1


def _sem_acento(texto):
    """'Érico' -> 'erico': a ordem alfabética não separa os acentuados."""
    decomposto = unicodedata.normalize("NFD", texto.casefold())
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def _data(texto):
    """Data da tela para comparar como data (vazio = a mais antiga)."""
    return (converter_data(texto) if texto else None) or datetime.min


def duracao(entrada, saida):
    """'4 h 30 min' entre dois momentos (datetime)."""
    minutos = max(0, round((saida - entrada).total_seconds() / 60))
    return horarios.formatar_horas(minutos / 60)


def descrever_desativacao(d):
    """'Desativada em 20/10/2026 10:00 por ana.admin. Motivo: ...' (e a
    reativação, se houver)."""
    texto = (f"{O_QUE[d['tipo']]} {DESATIVADO[d['tipo']]} em {d['criado_em']} "
             f"por {d['criado_por']}. Motivo: {d['motivo']}")
    if not d["ativo"]:
        texto += (f" Reativad{'a' if d['tipo'] == 'cpf' else 'o'} em "
                  f"{d['reativado_em']} por {d['reativado_por']}.")
    return texto


def texto_das_placas(p):
    """Coluna Placa da lista: a principal e quantas mais a pessoa tem
    ("ABC1D23 +1", RN47); "—" sem veículo."""
    if not p["placas"]:
        return "—"
    extra = len(p["placas"]) - 1
    return formatar_placa(p["placas"][0]) + (f" +{extra}" if extra else "")


class AbaPessoas:
    def __init__(self, aba, app):
        self.aba = aba
        self.app = app
        self.admin = pode_gerenciar_desativacoes(app.usuario)
        self.pessoas = []
        self.desativacoes = {}        # cpf -> desativação em vigor
        self.placas_desativadas = {}  # placa -> desativação em vigor
        self.selecionada = None       # pessoa da ficha
        self.placa_da_ficha = ""      # o carro escolhido na ficha (RN47)
        self.desativacao_da_ficha = None   # CPF sem cadastro na ficha
        self.visitas = []             # visitas da pessoa (mais recente primeiro)
        self.dialogo = None
        self.aba_atual = ABAS[0]

        cab = Cabecalho(aba, "Pessoas").posicionar()
        self.cabecalho = cab
        self.lbl_total = cab.subtitulo
        self.btn_nova = Botao(cab.acoes, "Nova pessoa", self.nova_pessoa,
                              "primario", icone=ICONE["mais"],
                              fundo_pai=COR["fundo"])
        self.btn_nova.pack()
        self.seletor = Seletor(aba, ABAS, self.mostrar_aba)
        self.seletor.pack(fill="x", padx=px(MARGEM), pady=(0, px(12)))
        self.corpo = corpo = tk.Frame(aba, bg=COR["fundo"])
        corpo.pack(fill="both", expand=True, padx=px(MARGEM),
                   pady=(0, px(MARGEM)))
        self._montar_ficha(corpo)
        self.cartao_ativas = self._montar_lista(corpo)
        self.desativadas = ListaDesativacoes(self, corpo, "cpf")
        self.veiculos_desativados = ListaDesativacoes(self, corpo, "placa")
        self.compacta = None
        self.aba.bind("<Configure>", self._ao_redimensionar, add="+")
        self.seletor.selecionar(ABAS[0])

    def _ao_redimensionar(self, event):
        if event.widget is self.aba:
            self.aplicar_densidade(event.height < px(ALTURA_CONFORTAVEL))

    def aplicar_densidade(self, compacta):
        """Tela baixa (notebook 1366x670): cabeçalho, subabas e ficha com
        menos respiro, para os botões da ficha e a lista caberem."""
        if compacta == self.compacta:
            return
        self.compacta = compacta
        self.cabecalho.pack_configure(
            pady=(px(8), px(8)) if compacta else (px(20), px(16)))
        self.seletor.compactar(compacta)
        self.seletor.pack_configure(pady=(0, px(6) if compacta else px(12)))
        self.cartao_ficha.miolo.pack_configure(
            padx=px(16 if compacta else 20), pady=px(14 if compacta else 20))
        self.seletor_ficha.compactar(compacta)
        self.seletor_ficha.pack_configure(
            pady=(px(8), px(6)) if compacta else (px(12), px(10)))
        self.faixa.definir_respiro(4 if compacta else 7)
        self._altura_autorizados()
        self.botoes_veiculo.pack_configure(pady=(px(6 if compacta else 10), 0))
        if compacta:
            self.lbl_veiculo_dica.pack_forget()
        elif self.selecionada is not None:
            self.mostrar_autorizados(self.selecionada)
        self.mostrar_secao(self.seletor_ficha.ativa or SECOES_FICHA[0])

    # --------------------------------------------------------------
    # Subabas
    # --------------------------------------------------------------
    def mostrar_aba(self, nome):
        """Ativas e Pessoas desativadas: lista + ficha; Veículos desativados: a
        lista com a largura toda."""
        self.aba_atual = nome
        cartoes = {ABAS[0]: self.cartao_ativas,
                   ABAS[1]: self.desativadas.cartao,
                   ABAS[2]: self.veiculos_desativados.cartao}
        for cartao in (*cartoes.values(), self.cartao_ficha):
            cartao.pack_forget()
        if nome != ABAS[2]:
            self.cartao_ficha.pack(side="right", fill="y")
        cartoes[nome].pack(side="left", fill="both", expand=True,
                           padx=(0, px(ESPACO_CARTOES)) if nome != ABAS[2]
                           else 0)
        self.limpar_ficha()
        self.atualizar()

    def mostrar_contadores(self, n):
        """Contagens no subtítulo e nas subabas (app.atualizar_contadores)."""
        self.lbl_total.config(
            text=plural(n["pessoas"], "pessoa cadastrada", "pessoas cadastradas")
            + f"  ·  {n['no_campus']} no campus agora")
        for aba, chave in ((ABAS[1], "desativadas"),
                           (ABAS[2], "veiculos_desativados")):
            self.seletor.definir_texto(
                aba, f"{aba} ({n[chave]})" if n[chave] else aba)

    def mostrar_desativacao(self, tipo, valor):
        """Abre Pessoas desativadas (CPF) ou Veículos desativados (placa) com a
        desativação em vigor de `valor` selecionada."""
        self.seletor.selecionar(ABAS[1] if tipo == "cpf" else ABAS[2])
        lista = self.desativadas if tipo == "cpf" else self.veiculos_desativados
        lista.selecionar_valor(valor)

    # --------------------------------------------------------------
    # Montagem
    # --------------------------------------------------------------
    def _montar_lista(self, corpo):
        cartao = Cartao(corpo, pad=0)
        m = cartao.miolo
        m.pack_configure(padx=px(1), pady=px(8))
        barra = tk.Frame(m, bg=COR["superficie"])
        barra.pack(fill="x", padx=px(19), pady=(px(6), px(12)))
        campo = Campo(barra, icone=ICONE["busca"],
                      dica_vazio="Buscar por nome, CPF, celular, placa ou tipo",
                      maximo=MAXIMO_BUSCA)
        campo.pack(fill="x")
        self.busca = campo.entrada
        self.espera_busca = EsperaDigitacao(self.busca, self.atualizar)
        self.busca.bind("<Return>", lambda e: "break")

        rodape = tk.Frame(m, bg=COR["superficie"])
        rodape.pack(side="bottom", fill="x", padx=px(19), pady=(px(8), px(2)))
        self.lbl_status = tk.Label(rodape, text="", font=FONTE["dica"],
                                   bg=COR["superficie"], fg=COR["texto_3"])
        self.lbl_status.pack(side="left")

        quadro, self.tabela = tabela(m, COLUNAS, situacao="Situação",
                                     mostrar=COLUNAS_VISIVEIS)
        quadro.pack(fill="both", expand=True, padx=px(12))
        self.tabela.bind("<<TreeviewSelect>>", self.ao_selecionar)
        self.tabela.bind("<Double-1>", self._ao_duplo_clique)
        self.ordenacao = OrdenacaoTabela(
            self.tabela,
            {"#0": "Situação", "nome": "Nome", "cpf": "CPF",
             "visitas": "Visitas", "ultima": "Última visita"},
            {"#0": self._ordem_situacao,
             "nome": lambda p: _sem_acento(p["nome"]),
             # o porteiro ordena pelo que vê (o CPF mascarado)
             "cpf": lambda p: self.app.exibir_cpf(p["cpf"]),
             "visitas": lambda p: p["visitas"],
             "ultima": lambda p: _data(p["ultima_visita"])},
            self.mostrar_lista, coluna="#0",
            desempate=lambda p: _sem_acento(p["nome"]))
        return cartao

    def _ao_duplo_clique(self, event):
        # duplo clique no cabeçalho ordena; só na linha começa a entrada
        if self.tabela.identify_region(event.x, event.y) in ("cell", "tree"):
            self.registrar_entrada()

    def _montar_ficha(self, corpo):
        cartao = Cartao(corpo, pad=20)
        cartao.config(width=px(372))
        cartao.pack_propagate(False)
        self.cartao_ficha = cartao
        fundo = COR["superficie"]

        # estado vazio (nada escolhido)
        self.vazio = tk.Frame(cartao.miolo, bg=fundo)
        self.vazio.place(relx=0.5, rely=0.4, anchor="center")
        tk.Label(self.vazio, text=ICONE["pessoa"], font=fonte_icone(28),
                 bg=fundo, fg=COR["texto_3"]).pack()
        self.lbl_vazio = tk.Label(self.vazio, text=SEM_SELECAO,
                                  font=FONTE["corpo"], bg=fundo,
                                  fg=COR["texto_2"], wraplength=px(240))
        self.lbl_vazio.pack(pady=(px(10), 0))

        self._montar_sem_cadastro(cartao.miolo)

        self.conteudo = tk.Frame(cartao.miolo, bg=fundo)
        c = self.conteudo
        # os botões vão primeiro, no pé: ficam à vista mesmo na tela baixa
        self._montar_botoes(c)
        self.lbl_titulo = titulo_cartao(c, "")
        self.lbl_titulo.pack(anchor="w")
        self.lbl_cpf = tk.Label(c, font=FONTE["cpf"], bg=fundo,
                                fg=COR["texto_2"])
        self.lbl_cpf.pack(anchor="w")
        # celular e tipo (o que antes era a seção Cadastro)
        self.lbl_contato = tk.Label(c, font=FONTE["corpo"], bg=fundo,
                                    fg=COR["texto_2"], anchor="w")
        self.lbl_contato.pack(anchor="w", fill="x", pady=(px(2), 0))

        # placa e, ao lado, os números (lado a lado: a ficha cabe no
        # notebook 1366x670)
        self.linha_placa = linha = tk.Frame(c, bg=fundo)
        linha.pack(fill="x", pady=(px(10), 0))
        self.desenho_placa = Placa(linha, fundo, largura=150)
        self.desenho_placa.pack(side="left")
        self.lbl_visitas = self._numero(linha, "visitas")
        self.lbl_ultima = self._numero(linha, "última vinda")

        self.faixa = Aviso(c)
        self.seletor_ficha = Seletor(c, SECOES_FICHA, self.mostrar_secao,
                                     fundo_pai=fundo)
        self.seletor_ficha.pack(fill="x", pady=(px(12), px(10)))
        self.secoes = {"Visitas": self._montar_visitas(c),
                       "Veículo": self._montar_veiculo(c)}
        self.seletor_ficha.selecionar(SECOES_FICHA[0])

    def _montar_sem_cadastro(self, pai):
        """Ficha de um CPF desativado que nunca foi cadastrado."""
        fundo = COR["superficie"]
        self.sem_cadastro = f = tk.Frame(pai, bg=fundo)
        titulo_cartao(f, SEM_CADASTRO).pack(anchor="w")
        self.lbl_cpf_sem_cadastro = tk.Label(f, font=FONTE["cpf"], bg=fundo,
                                             fg=COR["texto_2"])
        self.lbl_cpf_sem_cadastro.pack(anchor="w")
        self.faixa_sem_cadastro = Aviso(f)
        self.faixa_sem_cadastro.pack(fill="x", pady=(px(14), 0))
        tk.Label(f, text="Este CPF nunca foi cadastrado. A desativação vale "
                         "para a primeira entrada dele.", font=FONTE["dica"],
                 bg=fundo, fg=COR["texto_3"], wraplength=px(320),
                 justify="left").pack(anchor="w", pady=(px(10), 0))
        self.btn_reativar_sem_cadastro = None
        if self.admin:
            self.btn_reativar_sem_cadastro = Botao(
                f, "Reativar", self._reativar_da_ficha, "secundario")
            self.btn_reativar_sem_cadastro.pack(anchor="w", pady=(px(14), 0))

    def _montar_botoes(self, c):
        """Pé da ficha: Registrar entrada e Editar; para o administrador,
        Desativar (ou Reativar) e Excluir."""
        fundo = COR["superficie"]
        self.rodape_ficha = rodape = tk.Frame(c, bg=fundo)
        rodape.pack(side="bottom", fill="x", pady=(px(10), 0))
        botoes = tk.Frame(rodape, bg=fundo)
        botoes.pack(fill="x")
        self.btn_entrada = Botao(botoes, "Registrar entrada",
                                 self.registrar_entrada, "primario")
        self.btn_entrada.pack(side="left")
        self.btn_editar = Botao(botoes, "Editar", self.editar, "secundario",
                                icone=ICONE["editar"])
        self.btn_editar.pack(side="left", padx=(px(8), 0))
        self.btn_desativar = self.btn_excluir = None
        self.linha_admin = None
        if self.admin:          # RN12: só o administrador desativa
            self.linha_admin = admin = tk.Frame(rodape, bg=fundo)
            admin.pack(fill="x", pady=(px(8), 0))
            self.btn_desativar = Botao(admin, "Desativar",
                                       self.desativar_selecionada, "perigo",
                                       icone=ICONE["bloqueio"], largura=132)
            self.btn_desativar.pack(side="left")
            # RN42: excluir só quem nunca teve visita (o clique explica)
            self.btn_excluir = Botao(admin, "Excluir",
                                     self.excluir_selecionada, "perigo",
                                     icone=ICONE["lixo"])
            self.btn_excluir.pack(side="left", padx=(px(8), 0))

    def _montar_visitas(self, c):
        """Histórico de visitas: um "cartão" de texto por visita, com
        rolagem (cabe na largura da ficha, ao contrário de uma tabela de
        seis colunas)."""
        fundo = COR["superficie"]
        secao = tk.Frame(c, bg=fundo)
        self.lista_visitas = tk.Text(
            secao, bg=fundo, fg=COR["texto"], font=FONTE["corpo"], wrap="word",
            relief="flat", bd=0, highlightthickness=0, cursor="arrow",
            padx=0, pady=0, spacing1=0, spacing3=0, height=8, width=10,
            tabs=(px(318), "right"))
        barra = ttk.Scrollbar(secao, orient="vertical",
                              command=self.lista_visitas.yview,
                              style="Fina.Vertical.TScrollbar")
        self.lista_visitas.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.lista_visitas.pack(side="left", fill="both", expand=True)
        t = self.lista_visitas
        t.tag_configure("situacao", font=FONTE["corpo_semi"])
        t.tag_configure("datas", font=FONTE["corpo"], foreground=COR["texto"])
        t.tag_configure("detalhe", font=FONTE["dica"], foreground=COR["texto_2"])
        t.tag_configure("como", font=FONTE["dica"], foreground=COR["texto_3"])
        t.tag_configure("separa", font=(FONTE["dica"][0], 4))
        for situacao, token in COR_SITUACAO.items():
            t.tag_configure(situacao, foreground=COR[token])
        t.bind("<MouseWheel>", lambda e: t.yview_scroll(
            -1 if e.delta > 0 else 1, "units") or "break")
        return secao

    def _montar_veiculo(self, c):
        """RN35: quem pode retirar o carro da pessoa sem ela e sem senha;
        e (administrador) desativar ou reativar o veículo."""
        fundo = COR["superficie"]
        secao = tk.Frame(c, bg=fundo)
        # RN47: com mais de um carro, a pessoa escolhe de qual se fala
        # (a placa desenhada no alto e a lista abaixo seguem a escolha)
        self.linha_carros = tk.Frame(secao, bg=fundo)
        tk.Label(self.linha_carros, text="Carro", font=FONTE["dica"], bg=fundo,
                 fg=COR["texto_3"]).pack(side="left", padx=(0, px(6)))
        self.chips_carros = {}
        self.lista_carros = None
        self.cab_veiculo = cab = tk.Frame(secao, bg=fundo)
        cab.pack(fill="x")
        # desativar a placa (RN12): só o administrador, um link no título
        self.btn_desativar_veiculo = None
        if self.admin:
            self.btn_desativar_veiculo = link(cab, "Desativar placa",
                                              self.desativar_veiculo,
                                              cor=COR["erro"])
        self.lbl_veiculo = tk.Label(cab, font=FONTE["rotulo"], bg=fundo,
                                    fg=COR["texto"], anchor="w")
        self.lbl_veiculo.pack(side="left", fill="x", expand=True)
        self.lbl_veiculo_dica = tk.Label(
            secao, font=FONTE["dica"], bg=fundo, fg=COR["texto_3"],
            justify="left", anchor="w", wraplength=px(320),
            text="Levam o carro sem o dono e sem senha, se estiverem no "
                 "campus a pé e não estiverem desativados.")
        self.lbl_veiculo_dica.pack(fill="x", pady=(px(2), px(8)))
        self.quadro_autorizados, self.tabela_autorizados = tabela(
            secao, COLUNAS_AUTORIZADOS, altura=3, rolagem=True, compacta=True)
        self.quadro_autorizados.pack(fill="x")
        self.botoes_veiculo = tk.Frame(secao, bg=fundo)
        self.botoes_veiculo.pack(fill="x", pady=(px(10), 0))
        self.btn_adicionar_autorizado = Botao(
            self.botoes_veiculo, "Adicionar", self.adicionar_autorizado,
            "secundario")
        self.btn_adicionar_autorizado.pack(side="left")
        self.btn_validade_autorizado = Botao(
            self.botoes_veiculo, "Validade", self.editar_validade,
            "secundario", icone=ICONE["editar"])
        self.btn_validade_autorizado.pack(side="left", padx=(px(8), 0))
        self.btn_remover_autorizado = Botao(
            self.botoes_veiculo, "Remover", self.remover_autorizado, "perigo")
        self.btn_remover_autorizado.pack(side="left", padx=(px(8), 0))
        self.lbl_dono_fora = tk.Label(secao, font=FONTE["dica"], bg=fundo,
                                      fg=COR["alerta"], justify="left",
                                      anchor="w", wraplength=px(320))
        self.lbl_veiculo_desativado = tk.Label(
            secao, font=FONTE["rotulo"], bg=fundo, fg=COR["erro"],
            justify="left", anchor="w", wraplength=px(320))
        self.autorizados = []
        return secao

    def mostrar_autorizados(self, pessoa):
        """Lista "Quem pode retirar" da placa da pessoa e o estado dos
        botões (o porteiro só adiciona com o dono no campus). A placa é a
        escolhida em "Carro" (RN47); sem escolha, a principal."""
        placa = self.placa_da_ficha
        self.autorizados = []
        self.tabela_autorizados.delete(*self.tabela_autorizados.get_children())
        self._mostrar_desativacao_do_veiculo(placa)
        if not placa:
            self.lbl_veiculo.config(text=SEM_VEICULO, font=FONTE["corpo"],
                                    fg=COR["texto_2"], wraplength=px(320),
                                    justify="left")
            for w in (self.lbl_veiculo_dica, self.quadro_autorizados,
                      self.botoes_veiculo, self.lbl_dono_fora):
                w.pack_forget()
            self.seletor_ficha.definir_texto("Veículo", "Veículo")
            return
        self.lbl_veiculo.config(
            text=f"Quem pode retirar o carro {formatar_placa(placa)}",
            font=FONTE["rotulo"], fg=COR["texto"])
        if self.compacta:       # tela baixa: a dica sai da frente
            self.lbl_veiculo_dica.pack_forget()
        else:
            self.lbl_veiculo_dica.pack(fill="x", pady=(px(2), px(8)),
                                       after=self.cab_veiculo)
        # a lista é quem encolhe quando falta altura (ela tem rolagem): os
        # botões vão para o pé da seção ANTES dela na ordem do pack, e
        # ficam sempre inteiros (com a faixa de pessoa desativada, eles
        # saíam espremidos e sem como rolar até eles)
        self.quadro_autorizados.pack(
            fill="both", expand=True, pady=(px(4), 0),
            after=self.lbl_veiculo_dica if not self.compacta
            else self.cab_veiculo)
        self.botoes_veiculo.pack(side="bottom", fill="x",
                                 pady=(px(6 if self.compacta else 10), 0),
                                 before=self.quadro_autorizados)
        ok, lista = self.app.tentar(self.app.banco.listar_autorizados, placa)
        if ok:
            self.autorizados = lista
        hoje = self.app.relogio().date()
        for i, a in enumerate(self.autorizados):
            vencida = a["valido_ate"] is not None and a["valido_ate"] < hoje
            validade = ("venceu" if vencida else "sem prazo"
                        if a["valido_ate"] is None
                        else f"{a['valido_ate']:%d/%m/%Y}")
            inserir_linha(self.tabela_autorizados, i,
                          (a["nome"], self.app.exibir_cpf(a["cpf"]), validade),
                          iid=str(a["id"]),
                          tags=("apagado",) if vencida else ())
        n = len(self.autorizados)
        self.seletor_ficha.definir_texto("Veículo",
                                         f"Veículo ({n})" if n else "Veículo")
        ok, _ = pode_cadastrar_autorizado(eh_admin(self.app.usuario),
                                          bool(pessoa["dentro_desde"]))
        self.btn_adicionar_autorizado.definir_ativo(ok)
        self.btn_validade_autorizado.definir_ativo(ok and bool(self.autorizados))
        if ok:
            self.lbl_dono_fora.pack_forget()
        else:
            self.lbl_dono_fora.config(text="O dono precisa estar no campus "
                                           "para o porteiro adicionar ou "
                                           "mudar a validade.")
            self.lbl_dono_fora.pack(side="bottom", fill="x", pady=(px(6), 0),
                                    before=self.botoes_veiculo)
        self.btn_remover_autorizado.definir_ativo(bool(self.autorizados))

    def _mostrar_desativacao_do_veiculo(self, placa):
        """Na seção Veículo: "Veículo desativado: motivo" e o botão
        Desativar / Reativar placa (administrador)."""
        desativado = self.placas_desativadas.get(placa) if placa else None
        if desativado:
            self.lbl_veiculo_desativado.config(
                text=f"Veículo desativado: {desativado['motivo']}")
            self.lbl_veiculo_desativado.pack(fill="x", pady=(px(2), px(4)),
                                             after=self.cab_veiculo)
        else:
            self.lbl_veiculo_desativado.pack_forget()
        if self.btn_desativar_veiculo is not None:
            if placa:
                self.btn_desativar_veiculo.config(
                    text="Reativar placa" if desativado else "Desativar placa",
                    fg=COR["foco"] if desativado else COR["erro"])
                self.btn_desativar_veiculo.pack(side="right", before=
                                                self.lbl_veiculo)
            else:
                self.btn_desativar_veiculo.pack_forget()

    def adicionar_autorizado(self):
        """Abre o diálogo "Quem pode retirar"; devolve o diálogo."""
        if not self._exigir_selecao():
            return None
        p = self.selecionada
        ok, motivo = pode_cadastrar_autorizado(eh_admin(self.app.usuario),
                                               bool(p["dentro_desde"]))
        if not ok:
            mensagens.aviso("Quem pode retirar", motivo)
            return None
        self.dialogo = DialogoAutorizado(self, dict(p, placa=self.placa_da_ficha))
        return self.dialogo

    def editar_validade(self):
        """Veículo › Validade (RN45): nova data de quem está selecionado
        na lista; devolve o diálogo."""
        if not self._exigir_selecao():
            return None
        selecao = self.tabela_autorizados.selection()
        if not selecao:
            mensagens.aviso("Atenção", "Selecione na lista quem terá a "
                                       "validade alterada.")
            return None
        ok, motivo = pode_cadastrar_autorizado(
            eh_admin(self.app.usuario), bool(self.selecionada["dentro_desde"]))
        if not ok:
            mensagens.aviso("Quem pode retirar", motivo)
            return None
        a = next(x for x in self.autorizados if str(x["id"]) == selecao[0])
        self.dialogo = DialogoValidade(self, a)
        return self.dialogo

    def remover_autorizado(self):
        selecao = self.tabela_autorizados.selection()
        if not selecao:
            mensagens.aviso("Atenção", "Selecione quem sai da lista.")
            return
        a = next(x for x in self.autorizados if str(x["id"]) == selecao[0])
        placa = formatar_placa(a["placa"])
        if not self.app.perguntar(
                mensagens.confirmar, "Remover da lista",
                f"{a['nome']} não poderá mais retirar o carro {placa} sem o "
                "dono. A remoção fica no histórico."):
            return
        ok, _ = self.app.tentar(self.app.banco.remover_autorizado, a["id"],
                                autor=self.app.autor)
        if ok:
            self.mostrar_autorizados(self.selecionada)

    def mostrar_secao(self, nome):
        """Visitas ou Veículo. Na tela baixa, com o Veículo aberto, a placa
        e os números saem da frente: sobra altura para a lista de quem
        pode retirar."""
        if nome == SECOES_FICHA[1] and self.compacta:
            self.linha_placa.pack_forget()
        else:
            self.linha_placa.pack(fill="x", pady=(px(10), 0),
                                  after=self.lbl_contato)
        for secao, frame in getattr(self, "secoes", {}).items():
            if secao == nome:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

    @staticmethod
    def _numero(pai, legenda):
        bloco = tk.Frame(pai, bg=COR["superficie"])
        bloco.pack(side="left", anchor="center", padx=(px(18), 0))
        valor = tk.Label(bloco, text="—", font=FONTE["numero"],
                         bg=COR["superficie"], fg=COR["texto"])
        valor.pack(anchor="w")
        tk.Label(bloco, text=legenda, font=FONTE["dica"], bg=COR["superficie"],
                 fg=COR["texto_3"]).pack(anchor="w")
        return valor

    # --------------------------------------------------------------
    # Dados
    # --------------------------------------------------------------
    def _situacao_da_pessoa(self, p):
        """(ordem, texto da coluna Situação, texto da bolinha, cor)."""
        if p["dentro_desde"]:
            return NO_CAMPUS, "No campus", "No campus", COR["sucesso"]
        return FORA, "—", "Fora", COR["barra"]

    def _ordem_situacao(self, p):
        return self._situacao_da_pessoa(p)[0]

    def _ler_desativacoes(self):
        ok, ativas = self.app.tentar(self.app.banco.listar_desativacoes)
        ativas = ativas if ok else []
        self.desativacoes = {d["valor"]: d for d in ativas
                             if d["tipo"] == "cpf"}
        self.placas_desativadas = {d["valor"]: d for d in ativas
                                   if d["tipo"] == "placa"}

    def atualizar(self):
        """Relê a subaba aberta, as desativações em vigor e os números."""
        self._ler_desativacoes()
        if self.aba_atual == ABAS[0]:
            self._atualizar_ativas()
        elif self.aba_atual == ABAS[1]:
            self.desativadas.atualizar()
        else:
            self.veiculos_desativados.atualizar()
        ok, n = self.app.tentar(self.app.banco.contadores)
        if ok:
            self.mostrar_contadores(n)

    def _atualizar_ativas(self):
        ok, pessoas = self.app.tentar(
            self.app.banco.buscar_pessoas, self.busca.get(), LIMITE_BUSCA,
            so_cpf_completo=not eh_admin(self.app.usuario), so_ativas=True)
        if not ok:
            return
        self.pessoas = pessoas
        self.mostrar_lista()
        status = plural(len(pessoas), "pessoa na lista", "pessoas na lista")
        if len(pessoas) >= LIMITE_BUSCA:
            status += f" (as {LIMITE_BUSCA} primeiras: refine a busca)"
        self.lbl_status.config(text=status + "  ·  o cabeçalho ordena  ·  "
                                             "duplo clique: nova entrada")

    def mostrar_lista(self):
        """Redesenha a lista na ordem escolhida (mantém a seleção)."""
        selecao = self.tabela.selection()
        self.tabela.delete(*self.tabela.get_children())
        for i, p in enumerate(self.ordenacao.ordenar(self.pessoas)):
            _, situacao, texto, cor = self._situacao_da_pessoa(p)
            inserir_linha(self.tabela, i, (
                p["nome"], self.app.exibir_cpf(p["cpf"]),
                formatar_celular(p["celular"]), texto_das_placas(p),
                p["tipo"], p["visitas"], p["ultima_visita"] or "—", situacao),
                iid=str(p["id"]), situacao=texto, cor=cor)
        if selecao and self.tabela.exists(selecao[0]):
            self.tabela.selection_set(selecao[0])

    def ao_selecionar(self, event=None):
        selecao = self.tabela.selection()
        if not selecao:
            return
        p = next(p for p in self.pessoas if p["id"] == int(selecao[0]))
        self.mostrar_ficha(p)

    def limpar_ficha(self, texto=SEM_SELECAO):
        """Ficha vazia (nada escolhido)."""
        self.selecionada = self.desativacao_da_ficha = None
        self.conteudo.pack_forget()
        self.sem_cadastro.pack_forget()
        self.lbl_vazio.config(text=texto)
        self.vazio.place(relx=0.5, rely=0.4, anchor="center")

    def mostrar_ficha(self, p):
        """Ficha da pessoa `p` (de banco.buscar_pessoa / buscar_pessoas)."""
        mesma = (self.selecionada is not None
                 and self.selecionada["id"] == p["id"])
        self.selecionada = p
        self.desativacao_da_ficha = None
        self.vazio.place_forget()
        self.sem_cadastro.pack_forget()
        self.conteudo.pack(fill="both", expand=True)
        self.lbl_titulo.config(text=p["nome"])
        self.lbl_cpf.config(text="CPF " + self.app.exibir_cpf(p["cpf"]))
        self.lbl_visitas.config(text=str(p["visitas"]))
        self.lbl_ultima.config(text=(p["ultima_visita"] or "—")[:5])
        self.lbl_contato.config(text=f"{formatar_celular(p['celular'])}  ·  "
                                     f"{p['tipo']}")
        desativacao = self.desativacoes.get(p["cpf"])
        if desativacao:
            self._faixa("erro", descrever_desativacao(desativacao))
        elif p["dentro_desde"]:
            self._faixa("sucesso", f"No campus desde {p['dentro_desde']}.")
        else:
            self.faixa.pack_forget()
        if self.btn_desativar is not None:
            self.btn_desativar.definir_texto(
                *(("Reativar", "secundario") if desativacao
                  else ("Desativar", "perigo")))
        self.btn_entrada.definir_ativo(desativacao is None)
        if not mesma or self.placa_da_ficha not in p["placas"]:
            self.placa_da_ficha = p["placa"] or next(iter(p["placas"]), "")
        self._mostrar_carros(p)
        self._mostrar_placa()
        self.mostrar_visitas(p)
        self.mostrar_autorizados(p)

    def _mostrar_carros(self, p):
        """A linha "Carro" da seção Veículo: um botão por placa (RN47),
        o escolhido destacado e o desativado em vermelho. Com um carro só
        (ou nenhum), a linha some. Com mais de CARROS_EM_BOTOES, os botões
        não cabem na largura da ficha: vira uma lista (a linha continua
        uma só, também no notebook)."""
        for chip in self.chips_carros.values():
            chip.destroy()
        self.chips_carros = {}
        if self.lista_carros is not None:
            self.lista_carros.destroy()
            self.lbl_quantos_carros.destroy()
            self.lista_carros = None
        if len(p["placas"]) < 2:
            self.linha_carros.pack_forget()
            self._altura_autorizados()
            return
        fundo = COR["superficie"]
        if len(p["placas"]) > CARROS_EM_BOTOES:
            rotulos = {(formatar_placa(placa) + (" (desativado)" if placa in
                        self.placas_desativadas else "")): placa
                       for placa in p["placas"]}
            self.lista_carros = Campo(self.linha_carros, fundo_pai=fundo,
                                      opcoes=list(rotulos), largura=200)
            self.lista_carros.pack(side="left")
            escolhida = next(r for r, pl in rotulos.items()
                             if pl == self.placa_da_ficha)
            self.lista_carros.var.set(escolhida)
            self.lista_carros.entrada.bind(
                "<<ComboboxSelected>>", lambda e: self.escolher_carro(
                    rotulos[self.lista_carros.var.get()]))
            self.lbl_quantos_carros = tk.Label(
                self.linha_carros, text=f"{len(p['placas'])} carros",
                font=FONTE["dica"], bg=fundo, fg=COR["texto_3"])
            self.lbl_quantos_carros.pack(side="left", padx=(px(8), 0))
            self.linha_carros.pack(fill="x", pady=(0, px(4 if self.compacta
                                                        else 8)),
                                   before=self.cab_veiculo)
            self._altura_autorizados()
            return
        for placa in p["placas"]:
            escolhida = placa == self.placa_da_ficha
            chip = tk.Label(
                self.linha_carros, text=formatar_placa(placa),
                font=FONTE["rotulo"] if escolhida else FONTE["corpo"],
                bg=COR["selecao"] if escolhida else fundo,
                fg=(COR["erro"] if placa in self.placas_desativadas
                    else COR["texto"] if escolhida else COR["texto_2"]),
                padx=px(8), pady=px(2), cursor="hand2", takefocus=1,
                highlightthickness=1,
                highlightbackground=COR["foco"] if escolhida else COR["borda"],
                highlightcolor=COR["foco"])
            chip.pack(side="left", padx=(0, px(6)))
            for evento in ("<Button-1>", "<Return>", "<space>"):
                chip.bind(evento, lambda e, pl=placa: self.escolher_carro(pl))
            self.chips_carros[placa] = chip
        self.linha_carros.pack(fill="x", pady=(0, px(4 if self.compacta
                                                    else 8)),
                               before=self.cab_veiculo)
        self._altura_autorizados()

    def _altura_autorizados(self):
        """Linhas da lista de quem pode retirar: 3; na tela baixa, 2; na
        tela baixa com a linha Carro (RN47), 1 — os botões continuam à
        vista no notebook 1366x670."""
        com_carros = bool(self.linha_carros.winfo_manager())
        self.tabela_autorizados.configure(
            height=(1 if com_carros else 2) if self.compacta else 3)

    def escolher_carro(self, placa):
        """Ficha › Veículo › Carro: passa a falar desse carro."""
        if self.selecionada is None or placa not in self.selecionada["placas"]:
            return
        self.placa_da_ficha = placa
        self._mostrar_carros(self.selecionada)
        self._mostrar_placa()
        self.mostrar_autorizados(self.selecionada)

    def mostrar_ficha_sem_cadastro(self, desativacao):
        """CPF desativado sem cadastro: CPF, desativação e Reativar."""
        self.selecionada = None
        self.desativacao_da_ficha = desativacao
        self.vazio.place_forget()
        self.conteudo.pack_forget()
        self.sem_cadastro.pack(fill="both", expand=True)
        self.lbl_cpf_sem_cadastro.config(
            text="CPF " + self.app.exibir_cpf(desativacao["valor"]))
        self.faixa_sem_cadastro.mostrar(
            "erro" if desativacao["ativo"] else "neutro",
            descrever_desativacao(desativacao))
        if self.btn_reativar_sem_cadastro is not None:
            self.btn_reativar_sem_cadastro.definir_ativo(desativacao["ativo"])

    # --------------------------------------------------------------
    # Histórico de visitas da pessoa
    # --------------------------------------------------------------
    def mostrar_visitas(self, pessoa):
        ok, visitas = self.app.tentar(self.app.banco.visitas_da_pessoa,
                                      pessoa["id"], LIMITE_VISITAS)
        if not ok:
            return
        ok, config = self.app.tentar(self.app.banco.ler_configuracao)
        agora = self.app.relogio()
        self.visitas = [self._descrever_visita(r, pessoa, config if ok else None,
                                               agora) for r in visitas]
        total = max(pessoa["visitas"], len(visitas))   # a contagem real
        self.seletor_ficha.definir_texto(
            "Visitas", f"Visitas ({total})" if total else "Visitas")
        t = self.lista_visitas
        t.config(state="normal")
        t.delete("1.0", tk.END)
        if not self.visitas:
            t.insert(tk.END, SEM_VISITAS, "como")
        elif total > len(visitas):
            t.insert(tk.END, f"Mostrando as {len(visitas)} mais recentes de "
                             f"{total} visitas.", "como")
            t.insert(tk.END, "\n", "separa")
        for i, v in enumerate(self.visitas):
            if i:
                t.insert(tk.END, "\n", "separa")
            t.insert(tk.END, chr(0x25CF) + " ", v["situacao"])
            t.insert(tk.END, v["situacao"], ("situacao", v["situacao"]))
            t.insert(tk.END, f"\t{v['duracao']}\n", "detalhe")
            t.insert(tk.END, f"{v['entrada']}  {chr(0x2192)}  {v['saida']}\n",
                     "datas")
            t.insert(tk.END, f"{v['tipo']}  ·  {v['placa'] or 'a pé'}\n",
                     "detalhe")
            if v["como"]:
                t.insert(tk.END, f"Registrado como {v['como']}\n", "como")
        t.config(state="disabled")
        t.yview_moveto(0)

    @staticmethod
    def _descrever_visita(r, pessoa, config, agora):
        """Os campos da visita como a ficha mostra: saída só com a hora se
        foi no mesmo dia; duração até agora se ainda está no campus; nome e
        celular da época, se eram outros."""
        entrada = converter_data(r["entrada"])
        if r["saida"]:
            fim = converter_data(r["saida"])
            saida = (r["saida"][-5:] if r["saida"][:10] == r["entrada"][:10]
                     else r["saida"])
            tempo = duracao(entrada, fim)
            situacao = horarios.SAIU
        else:
            saida = "sem saída"
            tempo = duracao(entrada, agora) + " até agora"
            situacao = (horarios.situacao(config, r, agora) if config
                        else horarios.NO_CAMPUS)
        diferentes = []
        if r["nome"] != pessoa["nome"]:
            diferentes.append(r["nome"])
        if r["celular"] != pessoa["celular"]:
            diferentes.append(formatar_celular(r["celular"]))
        return {"id": r["id"], "entrada": r["entrada"], "saida": saida,
                "duracao": tempo, "tipo": r["tipo"],
                "placa": formatar_placa(r["placa"]), "situacao": situacao,
                "como": " · ".join(diferentes)}

    def _faixa(self, tipo, texto):
        self.faixa.mostrar(tipo, texto)
        self.faixa.pack(fill="x", pady=(px(10), 0), before=self.seletor_ficha)

    def _mostrar_placa(self):
        placa = self.placa_da_ficha if self.selecionada else ""
        self.desenho_placa.mostrar(placa,
                                   bloqueada=placa in self.placas_desativadas)

    def _exigir_selecao(self):
        if self.selecionada is None:
            mensagens.aviso("Atenção", "Selecione uma pessoa na lista.")
            return False
        return True

    # --------------------------------------------------------------
    # Ações
    # --------------------------------------------------------------
    def nova_pessoa(self):
        """Cabeçalho › Nova pessoa: abre o diálogo (e devolve)."""
        self.dialogo = DialogoPessoa(self)
        return self.dialogo

    def editar(self):
        """Ficha › Editar: o mesmo diálogo, com o CPF fixo."""
        if not self._exigir_selecao():
            return None
        self.dialogo = DialogoPessoa(self, self.selecionada)
        return self.dialogo

    def abrir_ficha(self, pessoa, aviso=None):
        """Mostra a ficha de `pessoa` na subaba certa (Ativas, ou
        Pessoas desativadas se o CPF estiver desativado), com um aviso opcional
        (tipo, texto) na faixa."""
        self._ler_desativacoes()
        if pessoa["cpf"] in self.desativacoes:
            self.mostrar_desativacao("cpf", pessoa["cpf"])
        else:
            if self.aba_atual != ABAS[0]:
                self.seletor.selecionar(ABAS[0])
            else:
                self.atualizar()
            if self.tabela.exists(str(pessoa["id"])):
                self.tabela.selection_set(str(pessoa["id"]))
                self.tabela.see(str(pessoa["id"]))
            self.mostrar_ficha(pessoa)
        if aviso:
            self._faixa(*aviso)

    def recarregar_ficha(self):
        """Relê a lista e a pessoa da ficha (depois de gravar)."""
        cpf = self.selecionada["cpf"] if self.selecionada else None
        self.atualizar()
        if cpf is None:
            return
        ok, pessoa = self.app.tentar(self.app.banco.buscar_pessoa, cpf)
        if ok and pessoa:
            self.mostrar_ficha(pessoa)
        else:
            self.limpar_ficha()

    def registrar_entrada(self):
        if not self._exigir_selecao():
            return
        p = self.selecionada
        if p["dentro_desde"]:
            mensagens.aviso(
                "Atenção", f"{p['nome']} já está no campus desde "
                           f"{p['dentro_desde']}.\nRegistre a saída na página "
                           "Entrada e saída.")
            return
        self.app.preencher_pessoa(p)

    # --- desativação (RN12: só o administrador) ----------------------
    def _exigir_admin(self):
        if not pode_gerenciar_desativacoes(self.app.usuario):
            mensagens.erro("Acesso negado", SO_ADMIN)
            return False
        return True

    def desativar_selecionada(self):
        """Ficha › Desativar (ou Reativar, se a pessoa já está
        desativada). Devolve o diálogo, se abriu um."""
        if not self._exigir_selecao() or not self._exigir_admin():
            return None
        p = self.selecionada
        desativacao = self.desativacoes.get(p["cpf"])
        if desativacao:
            self.reativar(desativacao)
            return None
        self.dialogo = DialogoDesativar(self, "cpf", p["cpf"], p["nome"])
        return self.dialogo

    def excluir_selecionada(self):
        """Ficha › Excluir (RN42): só o administrador e só o cadastro de
        quem nunca teve visita; com visitas, explica que é preciso
        desativar. Devolve True se excluiu."""
        if not self._exigir_selecao():
            return False
        p = self.selecionada
        ok, motivo = pode_excluir_pessoa(self.app.usuario, p["visitas"])
        if not ok:
            if eh_admin(self.app.usuario):
                mensagens.aviso("Excluir pessoa", motivo)
            else:
                mensagens.erro("Acesso negado", motivo)
            return False
        if not self.app.perguntar(
                mensagens.confirmar, "Excluir pessoa",
                f"Excluir o cadastro de {p['nome']} (CPF "
                f"{self.app.exibir_cpf(p['cpf'])})?\nEla nunca teve visita. "
                "A exclusão não pode ser desfeita e fica no histórico."):
            return False
        ok, _ = self.app.tentar(self.app.banco.excluir_pessoa, p["id"],
                                self.app.autor)
        if not ok:
            return False
        self.app.atualizar_contadores()
        self.atualizar()
        self.limpar_ficha(f"{p['nome']}: cadastro excluído.")
        return True

    def desativar_veiculo(self):
        """Ficha › Veículo › Desativar (ou Reativar) veículo."""
        if not self._exigir_selecao() or not self._exigir_admin():
            return None
        placa = self.placa_da_ficha
        if not placa:
            return None
        desativacao = self.placas_desativadas.get(placa)
        if desativacao:
            self.reativar(desativacao)
            return None
        self.dialogo = DialogoDesativar(self, "placa", placa,
                                        self.selecionada["nome"])
        return self.dialogo

    def _reativar_da_ficha(self):
        if self.desativacao_da_ficha is not None:
            self.reativar(self.desativacao_da_ficha)

    def reativar(self, desativacao):
        """Pergunta e reativa (a entrada volta a ser permitida)."""
        if not self._exigir_admin():
            return False
        tipo = desativacao["tipo"]
        quem = desativacao["nome"] or SEM_CADASTRO
        rotulo = formatar_desativacao(tipo, desativacao["valor"])
        texto = (f"Reativar {quem} (CPF {self.app.exibir_cpf(desativacao['valor'])})?"
                 if tipo == "cpf" else f"Reativar o veículo {rotulo}?")
        if not self.app.perguntar(mensagens.confirmar, "Reativar",
                                  texto + "\nA entrada volta a ser permitida. "
                                          "A reativação fica no histórico."):
            return False
        ok, _ = self.app.tentar(self.app.banco.reativar, desativacao["id"],
                                self.app.autor)
        if ok:
            self.depois_de_mudar()
        return ok

    def depois_de_mudar(self, tipo=None, valor=None):
        """Desativou ou reativou: relê a página, os contadores e o
        Movimento; a ficha mostra a pessoa como ficou."""
        self.app.atualizar_contadores()
        self.app.recarregar_registros()
        # desativou uma pessoa ou, pela lista, uma placa: a lista mostra;
        # o veículo desativado pela ficha continua na ficha
        if tipo is not None and (tipo == "cpf" or self.selecionada is None):
            self.mostrar_desativacao(tipo, valor)
            return
        if self.selecionada is not None:
            self.recarregar_ficha()
        else:
            self.atualizar()
            self.limpar_ficha()

    def avisar_se_no_campus(self, tipo, valor):
        """Desativou alguém que está no campus agora: vale para as
        próximas entradas (a visita aberta continua)."""
        dentro = encontrar_dentro(self.app.registros, valor)
        if dentro:
            nomes = ", ".join(r["nome"] for r in dentro)
            mensagens.info("Atenção", f"{O_QUE[tipo]} "
                                      f"{formatar_desativacao(tipo, valor)} "
                                      f"{DESATIVADO[tipo]}.\n\nNo campus "
                                      f"agora: {nomes}.\nA desativação vale "
                                      "para as próximas entradas.")


class ListaDesativacoes:
    """Subaba Pessoas desativadas (tipo "cpf") ou Veículos desativados ("placa"):
    a lista, "Mostrar reativadas" e, para o administrador, Desativar e
    Reativar. Selecionar uma pessoa abre a ficha dela ao lado."""

    def __init__(self, pagina, corpo, tipo):
        self.pagina, self.app, self.tipo = pagina, pagina.app, tipo
        self.textos = TEXTOS_LISTA[tipo]
        self.linhas = []
        self.colunas = COLUNAS_DESATIVACAO[tipo]
        self.todas = tuple(c[0] for c in self.colunas)
        self.sem_reativacao = self.todas[:-1]
        self.cartao = Cartao(corpo, pad=0)
        m = self.cartao.miolo
        m.pack_configure(padx=px(1), pady=px(8))
        self.btn_desativar = self.btn_reativar = None
        if pagina.admin:
            barra = tk.Frame(m, bg=COR["superficie"])
            barra.pack(fill="x", padx=px(19), pady=(px(6), px(12)))
            self.btn_desativar = Botao(barra, self.textos["botao"],
                                       self.desativar, "perigo",
                                       icone=ICONE["bloqueio"])
            self.btn_desativar.pack(side="left")
            self.btn_reativar = Botao(barra, "Reativar", self.reativar,
                                      "secundario")
            self.btn_reativar.pack(side="left", padx=(px(8), 0))
        else:
            faixa = Aviso(m)
            faixa.mostrar("info", self.textos["porteiro"])
            faixa.pack(fill="x", padx=px(19), pady=(px(6), px(12)))
        # rodapé: quantas e "Mostrar reativadas" (a barra de cima fica com
        # os botões: cabe ao lado da ficha no notebook)
        rodape = tk.Frame(m, bg=COR["superficie"])
        rodape.pack(side="bottom", fill="x", padx=px(19), pady=(px(6), 0))
        self.lbl_status = tk.Label(rodape, text="", font=FONTE["dica"],
                                   bg=COR["superficie"], fg=COR["texto_3"])
        self.lbl_status.pack(side="left")
        self.ver_reativadas = tk.BooleanVar(pagina.aba, value=False)
        Alternador(rodape, self.textos["reativadas"], self.ver_reativadas,
                   self.atualizar).pack(side="right")
        quadro, self.tabela = tabela(m, self.colunas, situacao="Situação",
                                     mostrar=self._visiveis(0))
        quadro.pack(fill="both", expand=True, padx=px(12))
        self.tabela.bind("<<TreeviewSelect>>", lambda e: self._ao_selecionar())
        self.tabela.bind("<Configure>", lambda e: self._ajustar_colunas(),
                         add="+")

    def _visiveis(self, largura):
        """Colunas mostradas: a lista de pessoas, com a ficha ao lado, só
        mostra quando e quem desativou se houver largura."""
        reativadas = self.ver_reativadas.get()
        if self.tipo == "cpf" and largura < px(LARGURA_PARA_TODAS):
            return (VISIVEIS_ESTREITA_REATIVADAS if reativadas
                    else VISIVEIS_ESTREITA)
        return self.todas if reativadas else self.sem_reativacao

    def _ajustar_colunas(self):
        """Colunas conforme a largura; a coluna Situação (bolinha) só
        aparece com as reativadas na lista (sem elas, todas estão
        desativadas)."""
        if getattr(self, "_ajustando", False):
            return      # o <Configure> gerado abaixo chama de novo: já basta
        visiveis = self._visiveis(self.tabela.winfo_width())
        mostrar = "tree headings" if self.ver_reativadas.get() else "headings"
        # o Tk devolve "show" como tupla de objetos (não como texto): compara
        # palavra por palavra, senão nunca fica igual e o ajuste não para
        atual = " ".join(str(p) for p in self.tabela["show"])
        if (tuple(self.tabela["displaycolumns"]) != visiveis
                or atual != mostrar):
            self._ajustando = True
            try:
                self.tabela.configure(displaycolumns=visiveis, show=mostrar)
                self.tabela.event_generate("<Configure>")   # encaixa larguras
            finally:
                self._ajustando = False

    def atualizar(self):
        ok, linhas = self.app.tentar(self.app.banco.listar_desativacoes,
                                     self.ver_reativadas.get(), tipo=self.tipo)
        if not ok:
            return
        self.linhas = linhas
        selecao = self.tabela.selection()
        self._ajustar_colunas()
        self.tabela.delete(*self.tabela.get_children())
        for i, d in enumerate(linhas):
            valor = (self.app.exibir_cpf(d["valor"]) if self.tipo == "cpf"
                     else formatar_placa(d["valor"]))
            nome = d["nome"] or (SEM_CADASTRO if self.tipo == "cpf" else "—")
            reativacao = ("" if d["ativo"] else
                          f"{d['reativado_em']} por {d['reativado_por']}")
            valores = ((nome, valor) if self.tipo == "cpf" else (valor, nome))
            situacao = (DESATIVADO[self.tipo].capitalize() if d["ativo"]
                        else "Reativad" + ("a" if self.tipo == "cpf" else "o"))
            inserir_linha(self.tabela, i, (
                *valores, d["motivo"], d["criado_em"], d["criado_por"],
                reativacao), iid=str(d["id"]), situacao=situacao,
                cor=COR["erro"] if d["ativo"] else COR["barra"],
                tags=() if d["ativo"] else ("apagado",))
        if selecao and self.tabela.exists(selecao[0]):
            self.tabela.selection_set(selecao[0])
        ativas = sum(1 for d in linhas if d["ativo"])
        self.lbl_status.config(
            text=plural(ativas, self.textos["uma"], self.textos["varias"])
            if ativas else self.textos["vazia"])
        self._ao_selecionar()

    def _selecionada(self):
        selecao = self.tabela.selection()
        return next((d for d in self.linhas
                     if selecao and str(d["id"]) == selecao[0]), None)

    def _ao_selecionar(self):
        """Reativar só com uma desativação em vigor; na de pessoas, a ficha
        ao lado mostra quem foi escolhido."""
        d = self._selecionada()
        if self.btn_reativar is not None:
            self.btn_reativar.definir_ativo(d is not None and d["ativo"])
        if self.tipo != "cpf":
            return
        if d is None:
            if self.pagina.desativacao_da_ficha or self.pagina.selecionada:
                self.pagina.limpar_ficha()
            return
        ok, pessoa = self.app.tentar(self.app.banco.buscar_pessoa, d["valor"])
        if ok and pessoa:
            self.pagina.mostrar_ficha(pessoa)
        else:
            self.pagina.mostrar_ficha_sem_cadastro(d)

    def selecionar_valor(self, valor):
        """Seleciona a desativação em vigor de `valor` (CPF ou placa)."""
        d = next((d for d in self.linhas if d["valor"] == valor
                  and d["ativo"]), None)
        if d is not None:
            self.tabela.selection_set(str(d["id"]))
            self.tabela.see(str(d["id"]))
            self._ao_selecionar()

    def desativar(self):
        """Desativar CPF / Desativar placa: abre o diálogo (devolve)."""
        if not self.pagina._exigir_admin():
            return None
        self.pagina.dialogo = DialogoDesativar(self.pagina, self.tipo)
        return self.pagina.dialogo

    def reativar(self):
        if not self.pagina._exigir_admin():
            return False
        d = self._selecionada()
        if d is None:
            mensagens.aviso("Atenção", "Selecione uma linha da lista.")
            return False
        if not d["ativo"]:
            mensagens.info("Aviso", "Esta desativação já foi encerrada "
                                    "(reativada).")
            return False
        return self.pagina.reativar(d)


class DialogoPessoa(Dialogo):
    """
    Nova pessoa (CPF, nome, celular, placas opcionais e tipo) ou Editar
    pessoa (o CPF não muda). Placas (RN47): digita uma e Enter (ou
    "Adicionar") para pôr outra; cada uma aparece embaixo com um × para
    tirar. A primeira é a principal (a que o CPF preenche na entrada). Mesma validação e mesmos limites da entrada
    (validacao.validar_campos; o banco confere de novo). Cadastrar NÃO
    registra entrada. CPF já cadastrado: recusa e abre a ficha que já
    existe. CPF desativado: avisa já na digitação e pede confirmação.
    """

    def __init__(self, pagina, pessoa=None):
        self.pagina, self.pessoa = pagina, pessoa
        app = pagina.app
        nova = pessoa is None
        super().__init__(
            app.janela, "Nova pessoa" if nova else "Editar pessoa",
            "Só o cadastro: a entrada não é registrada. Para isso, use "
            "Registrar entrada na ficha." if nova else
            "As visitas antigas continuam com os dados da época.",
            largura=440, ao_usar=app.registrar_uso)
        form = self.miolo
        form.columnconfigure((0, 1), weight=1, uniform="p")

        def campo(texto, linha, coluna, juntas=1, apoio="", **opcoes):
            grupo, c = campo_rotulado(form, texto, apoio, **opcoes)
            grupo.grid(row=linha, column=coluna, columnspan=juntas,
                       sticky="ew", pady=(0, px(14)),
                       padx=(0, px(10)) if coluna == 0 and juntas == 1 else 0)
            return c

        c = campo("CPF", 0, 0, apoio="só números", numeros=11)
        self.cpf, self.var_cpf = c.entrada, c.var
        self.tipo = campo("Tipo de acesso", 0, 1, opcoes=TIPOS_ACESSO).entrada
        self.nome = campo("Nome completo", 1, 0, juntas=2,
                          maximo=MAXIMO_NOME).entrada
        self.celular = campo("Celular com DDD", 2, 0, apoio="só números",
                             numeros=11).entrada
        c = campo("Placas", 2, 1, apoio="Enter adiciona", placa=True)
        self.caixa_placa = c.entrada
        self.caixa_placa.bind("<Return>", self.adicionar_placa)
        self.caixa_placa.bind("<KP_Enter>", self.adicionar_placa)
        # para quem usa o mouse: "Adicionar" na linha do rótulo
        link(c.master.winfo_children()[0], "Adicionar",
             self.adicionar_placa).pack(side="right")
        self.placas = list(pessoa["placas"]) if pessoa else []
        self.linha_placas = tk.Frame(form, bg=COR["superficie"])
        self._desenhar_placas()
        self.faixa = Aviso(form)
        if nova:
            self.var_cpf.trace_add("write", lambda *a: self._ao_digitar_cpf())
        else:
            # o CPF não muda: aparece como na tela (mascarado para o
            # porteiro), sem a trava de "só números" do campo
            self.cpf.config(validate="none")
            self.cpf.insert(0, app.exibir_cpf(pessoa["cpf"]))
            self.cpf.config(state="disabled")
            self.nome.insert(0, pessoa["nome"])
            self.celular.insert(0, pessoa["celular"])
            self.tipo.set(pessoa["tipo"])
        self.adicionar_botao("Cadastrar" if nova else "Salvar alterações",
                             self.salvar, "primario")
        self.adicionar_botao("Cancelar", self.fechar)
        self.abrir(confirmar=self.salvar, foco=self.cpf if nova else self.nome)

    def _mostrar_faixa(self, tipo, texto):
        self.faixa.mostrar(tipo, texto)
        self.faixa.grid(row=4, column=0, columnspan=2, sticky="ew")

    def _placas_digitadas(self):
        """As placas da lista mais a que está no campo (sem Enter)."""
        return self.placas + [self.caixa_placa.get()]

    def adicionar_placa(self, event=None):
        """Enter (ou "Adicionar") no campo Placas: a placa vai para a
        lista e o campo fica livre para a próxima."""
        if not self.caixa_placa.get().strip():
            return "break"
        ok, msg, lista = validar_placas(self._placas_digitadas())
        if not ok:
            self._mostrar_faixa("erro", msg)
            return "break"
        self.placas = lista
        self.caixa_placa.delete(0, tk.END)
        self.faixa.grid_forget()
        self._desenhar_placas()
        return "break"

    def tirar_placa(self, placa):
        if placa in self.placas:
            self.placas.remove(placa)
            self._desenhar_placas()

    def _desenhar_placas(self):
        """Uma etiqueta por placa ("ABC1D23 ×"); a primeira é a principal."""
        for w in self.linha_placas.winfo_children():
            w.destroy()
        if not self.placas:
            self.linha_placas.grid_forget()
            return
        fundo = COR["superficie"]
        for i, placa in enumerate(self.placas):
            etiqueta = tk.Frame(self.linha_placas, bg=COR["selecao"],
                                highlightthickness=1,
                                highlightbackground=COR["borda"])
            etiqueta.pack(side="left", padx=(0, px(6)))
            tk.Label(etiqueta, text=formatar_placa(placa),
                     font=FONTE["rotulo"] if i == 0 else FONTE["corpo"],
                     bg=COR["selecao"], fg=COR["texto"]).pack(
                side="left", padx=(px(8), px(2)), pady=px(2))
            tirar = tk.Label(etiqueta, text="×", font=FONTE["rotulo"],
                             bg=COR["selecao"], fg=COR["texto_2"],
                             cursor="hand2", takefocus=1)
            tirar.pack(side="left", padx=(0, px(6)))
            for evento in ("<Button-1>", "<Return>", "<space>"):
                tirar.bind(evento, lambda e, p=placa: (self.tirar_placa(p),
                                                       "break")[1])
        if len(self.placas) > 1:
            tk.Label(self.linha_placas, text="a 1ª é a principal",
                     font=FONTE["dica"], bg=fundo,
                     fg=COR["texto_3"]).pack(side="left")
        self.linha_placas.grid(row=3, column=0, columnspan=2, sticky="w",
                               pady=(0, px(14)))

    def _desativacao(self, cpf):
        app = self.pagina.app
        ok, ativas = app.tentar(app.banco.listar_desativacoes, tipo="cpf")
        return next((d for d in (ativas or []) if d["valor"] == cpf), None)

    def _ao_digitar_cpf(self):
        """CPF completo: avisa se é inválido, se já está cadastrado ou se
        está desativado."""
        cpf = so_digitos(self.var_cpf.get())
        if len(cpf) != 11:
            self.faixa.grid_forget()
            return
        if not cpf_valido(cpf):
            self._mostrar_faixa("erro", "CPF inválido: confira os números.")
            return
        app = self.pagina.app
        ok, pessoa = app.tentar(app.banco.buscar_pessoa, cpf)
        desativada = self._desativacao(cpf)
        if ok and pessoa:
            self._mostrar_faixa("info", f"Já cadastrado: {pessoa['nome']}. "
                                        "Cadastrar abre a ficha dele.")
        elif desativada:
            self._mostrar_faixa("erro", f"CPF desativado: "
                                        f"{desativada['motivo']}. Pode "
                                        "cadastrar, mas a entrada continua "
                                        "recusada.")
        else:
            self.faixa.grid_forget()

    def salvar(self):
        """Grava; devolve True se gravou."""
        app = self.pagina.app
        cpf = self.pessoa["cpf"] if self.pessoa else self.cpf.get()
        ok, msg, placas = validar_placas(self._placas_digitadas(), max(
            MAXIMO_PLACAS_PESSOA, len(self.pessoa["placas"]) if self.pessoa
            else 0))
        if not ok:
            self._mostrar_faixa("erro", msg)
            return False
        dados = normalizar(self.nome.get(), cpf, self.celular.get(),
                           placas[0] if placas else "", self.tipo.get(), "", "")
        ok, msg = validar_campos(dados)
        if not ok:
            self._mostrar_faixa("erro", msg)
            return False
        if self.pessoa is not None:
            ok, _ = app.tentar(app.banco.atualizar_pessoa, self.pessoa["id"],
                               dados["nome"], dados["celular"], placas,
                               dados["tipo"], autor=app.autor)
            if not ok:
                return False
            self.fechar()
            self.pagina.recarregar_ficha()
            self.pagina._faixa("sucesso", "Alterações salvas.")
            return True
        ok, existente = app.tentar(app.banco.buscar_pessoa, dados["cpf"])
        if not ok:
            return False
        if existente:           # recusa e abre a ficha que já existe
            self.fechar()
            self.pagina.abrir_ficha(existente)
            mensagens.aviso("Pessoa já cadastrada",
                            f"Este CPF já é de {existente['nome']}: nada foi "
                            "cadastrado. A ficha dele está aberta.")
            return False
        desativada = self._desativacao(dados["cpf"])
        if desativada and not app.perguntar(
                mensagens.confirmar, "CPF desativado",
                f"Este CPF está desativado: {desativada['motivo']}\n\n"
                "Cadastrar mesmo assim? A pessoa continua desativada e a "
                "entrada continua recusada."):
            return False
        ok, _ = app.tentar(app.banco.cadastrar_pessoa, dados["cpf"],
                           dados["nome"], dados["celular"], placas,
                           dados["tipo"], app.autor)
        if not ok:
            return False
        self.fechar()
        app.atualizar_contadores()
        ok, pessoa = app.tentar(app.banco.buscar_pessoa, dados["cpf"])
        if ok and pessoa:
            self.pagina.abrir_ficha(pessoa, ("sucesso", "Pessoa cadastrada. "
                                             "A entrada não foi registrada."))
        return True


class DialogoDesativar(Dialogo):
    """Desativar uma pessoa (CPF) ou um veículo (placa): o motivo é
    obrigatório (de 5 a 200 caracteres). Da ficha, o CPF/placa já vem; da
    lista, é digitado."""

    def __init__(self, pagina, tipo, valor=None, nome=None):
        self.pagina, self.tipo, self.valor_fixo = pagina, tipo, valor
        app = pagina.app
        titulo = "Desativar pessoa" if tipo == "cpf" else "Desativar veículo"
        if valor:
            rotulo = formatar_desativacao(tipo, valor)
            quem = (f"{nome} (CPF {app.exibir_cpf(valor)})" if tipo == "cpf"
                    else f"o veículo {rotulo}"
                    + (f", de {nome}," if nome else ""))
        else:
            quem = "esta pessoa" if tipo == "cpf" else "este veículo"
        super().__init__(app.janela, titulo,
                         f"A entrada de {quem} fica recusada até um "
                         "administrador reativar. Fica no histórico.",
                         largura=440, ao_usar=app.registrar_uso)
        form = self.miolo
        self.valor = None
        if not valor:
            grupo, campo = campo_rotulado(
                form, "CPF" if tipo == "cpf" else "Placa",
                "só números" if tipo == "cpf" else "ABC1234 ou ABC1D23",
                **({"numeros": 11} if tipo == "cpf" else {"placa": True}))
            grupo.pack(fill="x", pady=(0, px(14)))
            self.valor = campo.entrada
        grupo, campo = campo_rotulado(form, "Motivo", "aparece na entrada",
                                      contador=True, maximo=MAXIMO_MOTIVO)
        grupo.pack(fill="x")
        self.motivo = campo.entrada
        self.faixa = Aviso(form)
        self.adicionar_botao(titulo.split()[0], self.salvar, "primario")
        self.adicionar_botao("Cancelar", self.fechar)
        self.abrir(confirmar=self.salvar, foco=self.valor or self.motivo)

    def _erro(self, texto):
        self.faixa.mostrar("erro", texto)
        self.faixa.pack(fill="x", pady=(px(12), 0))

    def salvar(self):
        app = self.pagina.app
        valor = normalizar_desativacao(
            self.tipo, self.valor_fixo or (self.valor.get() if self.valor
                                           else ""))
        motivo = " ".join(self.motivo.get().split())
        ok, ativas = app.tentar(app.banco.listar_desativacoes, tipo=self.tipo)
        if not ok:
            return False
        ok, msg = validar_desativacao(self.tipo, valor, motivo, ativas)
        if not ok:
            self._erro(msg)
            return False
        ok, _ = app.tentar(app.banco.desativar, self.tipo, valor, motivo,
                           app.autor)
        if not ok:
            return False
        self.fechar()
        self.pagina.depois_de_mudar(self.tipo, valor)
        self.pagina.avisar_se_no_campus(self.tipo, valor)
        return True


class DialogoValidade(Dialogo):
    """RN45: troca a validade de quem pode retirar o carro (vazio = sem
    prazo, até alguém remover; nunca antes de hoje)."""

    def __init__(self, aba, autorizado):
        self.aba, self.autorizado = aba, autorizado
        app = aba.app
        placa = formatar_placa(autorizado["placa"])
        super().__init__(app.janela, "Validade da autorização",
                         f"Até quando {autorizado['nome']} pode retirar o "
                         f"carro {placa}. Vazio = sem prazo (até alguém "
                         "remover).", largura=380, ao_usar=app.registrar_uso)
        grupo, campo = campo_rotulado(self.miolo, "Válido até", "opcional",
                                      seletor="data", relogio=app.relogio)
        grupo.pack(fill="x")
        self.validade = campo.entrada
        if autorizado["valido_ate"] is not None:
            self.validade.insert(0, f"{autorizado['valido_ate']:%d/%m/%Y}")
        self.faixa = Aviso(self.miolo)
        self.adicionar_botao("Salvar", self.salvar, "primario")
        self.adicionar_botao("Cancelar", self.fechar)
        self.abrir(confirmar=self.salvar, foco=self.validade)

    def salvar(self):
        app = self.aba.app
        valido_ate, erro = validar_nova_validade(self.validade.get(),
                                                 app.relogio().date())
        if erro:
            self.faixa.mostrar("erro", erro)
            self.faixa.pack(fill="x", pady=(px(12), 0))
            return False
        ok, _ = app.tentar(app.banco.alterar_validade_autorizado,
                           self.autorizado["id"], valido_ate, autor=app.autor)
        if not ok:
            return False
        self.fechar()
        self.aba.mostrar_autorizados(self.aba.selecionada)
        return True


class DialogoAutorizado(Dialogo):
    """RN35: CPF e nome de quem pode retirar o carro da pessoa e a
    validade (opcional: vazio = até alguém remover)."""

    def __init__(self, aba, dono):
        self.aba, self.dono = aba, dono
        app = aba.app
        placa = formatar_placa(dono["placa"])
        super().__init__(app.janela, "Quem pode retirar",
                         f"Esta pessoa vai poder levar o carro {placa} de "
                         f"{dono['nome']} sem o dono e sem a senha do "
                         "administrador, se estiver no campus a pé.",
                         largura=420, ao_usar=app.registrar_uso)
        form = self.miolo
        form.columnconfigure((0, 1), weight=1, uniform="a")
        grupo, campo = campo_rotulado(form, "CPF", "só números", numeros=11)
        grupo.grid(row=0, column=0, sticky="ew", padx=(0, px(10)),
                   pady=(0, px(14)))
        self.cpf = campo.entrada
        self.var_cpf = campo.var
        self.var_cpf.trace_add("write", lambda *a: self._ao_digitar_cpf())
        grupo, campo = campo_rotulado(form, "Válido até", "opcional",
                                      seletor="data", relogio=app.relogio)
        grupo.grid(row=0, column=1, sticky="ew", pady=(0, px(14)))
        self.validade = campo.entrada
        grupo, campo = campo_rotulado(form, "Nome completo",
                                      maximo=MAXIMO_NOME)
        grupo.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.nome = campo.entrada
        self.faixa = Aviso(form)
        self.lbl_erro = self.faixa.lbl
        self.adicionar_botao("Adicionar", self.salvar, "primario")
        self.adicionar_botao("Cancelar", self.fechar)
        self.abrir(confirmar=self.salvar, foco=self.cpf)

    def _ao_digitar_cpf(self):
        """CPF de quem já veio preenche o nome (se estiver vazio)."""
        cpf = so_digitos(self.var_cpf.get())
        if len(cpf) != 11 or not cpf_valido(cpf) or self.nome.get().strip():
            return
        ok, pessoa = self.aba.app.tentar(self.aba.app.banco.buscar_pessoa, cpf)
        if ok and pessoa:
            self.nome.insert(0, pessoa["nome"])

    def salvar(self):
        app = self.aba.app
        dados, erro = validar_autorizado(self.dono, so_digitos(self.cpf.get()),
                                         self.nome.get(), self.validade.get(),
                                         app.relogio().date())
        if erro:
            self.faixa.mostrar("erro", erro)
            self.faixa.grid(row=2, column=0, columnspan=2, sticky="ew",
                            pady=(px(12), 0))
            return
        ok, _ = app.tentar(app.banco.adicionar_autorizado, dados["dono_cpf"],
                           dados["cpf"], dados["nome"], dados["valido_ate"],
                           autor=app.autor, placa=self.dono["placa"])
        if not ok:
            return
        self.fechar()
        self.aba.mostrar_autorizados(self.dono)
