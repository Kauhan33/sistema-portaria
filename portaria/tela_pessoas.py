"""
Página Pessoas: lista + ficha. À esquerda, todo mundo que já passou pela
portaria (busca no banco, banco.buscar_pessoas), ordenada pela coluna
clicada no cabeçalho (1º clique crescente, 2º decrescente; abre ordenada
pela situação: no campus, bloqueado, fora, e depois pelo nome). À direita,
a ficha da pessoa escolhida: placa desenhada, número de visitas, faixa de
bloqueio e duas seções:
- Cadastro: o formulário para corrigir o cadastro ou começar uma entrada;
- Visitas: o histórico de visitas dela, da mais recente para a mais
  antiga (entrada, saída, duração, tipo, placa e situação), com os dados
  que foram preenchidos em cada registro;
- Veículo (RN35): "Quem pode retirar" o carro da placa dela sem o dono e
  sem senha, com Adicionar e Remover. O porteiro só adiciona com o dono no
  campus (o botão fica apagado, com a dica); o administrador, a qualquer
  hora. Qualquer um remove.
"""

import tkinter as tk
import unicodedata
from datetime import datetime
from tkinter import ttk

from . import horarios, mensagens
from .componentes import (Aviso, Botao, Cabecalho, Campo, Cartao, Dialogo,
                          EsperaDigitacao, OrdenacaoTabela, Placa, Seletor,
                          campo_rotulado, inserir_linha, plural, rotulo_campo,
                          tabela, titulo_cartao)
from .estilo import (COR, ESPACO_CARTOES, FONTE, ICONE, MARGEM, fonte_icone,
                     px)
from .usuarios import eh_admin
from .validacao import (MAXIMO_BUSCA, MAXIMO_NOME, TIPOS_ACESSO,
                        converter_data, cpf_valido,
                        formatar_celular, formatar_placa, normalizar,
                        so_digitos, validar_campos)
from .veiculos import (DONO_PRECISA_ESTAR, descrever_validade,
                       pode_cadastrar_autorizado, validar_autorizado)

COLUNAS = [("nome", "Nome", 160, "w"), ("cpf", "CPF", 112, "w"),
           ("celular", "Celular", 115, "w"), ("placa", "Placa", 80, "w"),
           ("tipo", "Tipo", 110, "w"), ("visitas", "Visitas", 66, "center"),
           ("ultima", "Última visita", 124, "w"),
           ("situacao", "Situação", 95, "w")]
# a ficha mostra o resto; os values continuam completos
COLUNAS_VISIVEIS = ("nome", "cpf", "visitas", "ultima")
LIMITE_BUSCA = 200
SEM_SELECAO = "Escolha uma pessoa na lista para ver a ficha."
SECOES_FICHA = ("Cadastro", "Visitas", "Veículo")
COLUNAS_AUTORIZADOS = [("nome", "Quem pode retirar", 150, "w"),
                       ("cpf", "CPF", 104, "w"),
                       ("validade", "Validade", 86, "w")]
SEM_VEICULO = ("Sem veículo cadastrado. A lista de quem pode retirar vale "
               "para a placa da pessoa.")
LIMITE_VISITAS = 200
SEM_VISITAS = "Nenhuma visita registrada."

# Situação na lista: (ordem, texto da bolinha, cor). Crescente = quem está
# no campus primeiro (o que a guarita mais procura), depois os bloqueados.
NO_CAMPUS, BLOQUEADO, FORA = 0, 1, 2
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


class AbaPessoas:
    def __init__(self, aba, app):
        self.aba = aba
        self.app = app
        self.pessoas = []
        self.bloqueados = {}          # cpf -> motivo do bloqueio ativo
        self.selecionada = None
        self.visitas = []             # visitas da pessoa (mais recente primeiro)

        cab = Cabecalho(aba, "Pessoas").posicionar()
        self.lbl_total = cab.subtitulo
        corpo = tk.Frame(aba, bg=COR["fundo"])
        corpo.pack(fill="both", expand=True, padx=px(MARGEM),
                   pady=(0, px(MARGEM)))
        self._montar_ficha(corpo)
        self._montar_lista(corpo)
        self.atualizar()

    # --------------------------------------------------------------
    # Montagem
    # --------------------------------------------------------------
    def _montar_lista(self, corpo):
        cartao = Cartao(corpo, pad=0)
        cartao.pack(side="left", fill="both", expand=True,
                    padx=(0, px(ESPACO_CARTOES)))
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

    def _ao_duplo_clique(self, event):
        # duplo clique no cabeçalho ordena; só na linha começa a entrada
        if self.tabela.identify_region(event.x, event.y) in ("cell", "tree"):
            self.registrar_entrada()

    def _montar_ficha(self, corpo):
        cartao = Cartao(corpo, pad=20)
        cartao.config(width=px(372))
        cartao.pack_propagate(False)
        cartao.pack(side="right", fill="y")
        fundo = COR["superficie"]

        # estado vazio (nada escolhido)
        self.vazio = tk.Frame(cartao.miolo, bg=fundo)
        self.vazio.place(relx=0.5, rely=0.4, anchor="center")
        tk.Label(self.vazio, text=ICONE["pessoa"], font=fonte_icone(28),
                 bg=fundo, fg=COR["texto_3"]).pack()
        tk.Label(self.vazio, text=SEM_SELECAO, font=FONTE["corpo"], bg=fundo,
                 fg=COR["texto_2"], wraplength=px(240)).pack(pady=(px(10), 0))

        self.conteudo = tk.Frame(cartao.miolo, bg=fundo)
        c = self.conteudo
        self.lbl_titulo = titulo_cartao(c, "")
        self.lbl_titulo.pack(anchor="w")
        self.lbl_cpf = tk.Label(c, font=FONTE["cpf"], bg=fundo,
                                fg=COR["texto_2"])
        self.lbl_cpf.pack(anchor="w")

        self.linha_placa = linha = tk.Frame(c, bg=fundo)
        linha.pack(fill="x", pady=(px(12), 0))
        self.desenho_placa = Placa(linha, fundo, largura=170)
        self.desenho_placa.pack(side="left")
        numeros = tk.Frame(linha, bg=fundo)
        numeros.pack(side="left", padx=(px(18), 0))
        self.lbl_visitas = self._numero(numeros, "visitas")
        self.lbl_ultima = self._numero(numeros, "última vinda")

        self.faixa = Aviso(c)
        self.seletor_ficha = Seletor(c, SECOES_FICHA, self.mostrar_secao,
                                     fundo_pai=fundo)
        self.seletor_ficha.pack(fill="x", pady=(px(12), px(12)))
        self.secoes = {"Cadastro": self._montar_cadastro(c),
                       "Visitas": self._montar_visitas(c),
                       "Veículo": self._montar_veiculo(c)}
        self.seletor_ficha.selecionar(SECOES_FICHA[0])

    def _montar_cadastro(self, c):
        fundo = COR["superficie"]
        secao = tk.Frame(c, bg=fundo)
        form = tk.Frame(secao, bg=fundo)
        form.pack(fill="x")
        form.columnconfigure((0, 1), weight=1, uniform="p")

        def grupo(texto, linha_, coluna, campo, juntas=1, apoio=""):
            frame, _ = rotulo_campo(form, texto, apoio)
            frame.grid(row=linha_, column=coluna, columnspan=juntas, sticky="w",
                       pady=(0, px(4)))
            campo.grid(row=linha_ + 1, column=coluna, columnspan=juntas,
                       sticky="ew", pady=(0, px(12)),
                       padx=(0, px(10)) if coluna == 0 and juntas == 1 else 0)
            return campo

        self.campo_nome = grupo("Nome completo", 0, 0,
                                Campo(form, maximo=MAXIMO_NOME), juntas=2)
        self.nome = self.campo_nome.entrada
        # Q04: as mesmas restrições de digitação da Entrada e saída
        self.celular = grupo("Celular", 2, 0, Campo(form, numeros=11)).entrada
        campo_placa = grupo("Placa", 2, 1, Campo(form, placa=True),
                            apoio="opcional")
        self.var_placa, self.caixa_placa = campo_placa.var, campo_placa.entrada
        self.var_placa.trace_add("write", lambda *a: self._mostrar_placa())
        self.tipo = grupo("Tipo de acesso", 4, 0, Campo(form, opcoes=TIPOS_ACESSO),
                          juntas=2).entrada

        botoes = tk.Frame(secao, bg=fundo)
        botoes.pack(fill="x", pady=(px(4), 0))
        Botao(botoes, "Registrar entrada", self.registrar_entrada,
              "primario").pack(side="left")
        Botao(botoes, "Salvar alterações", self.salvar,
              "secundario").pack(side="left", padx=(px(8), 0))
        return secao

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
        """RN35: quem pode retirar o carro da pessoa sem ela e sem senha."""
        fundo = COR["superficie"]
        secao = tk.Frame(c, bg=fundo)
        self.lbl_veiculo = tk.Label(secao, font=FONTE["rotulo"], bg=fundo,
                                    fg=COR["texto"], anchor="w")
        self.lbl_veiculo.pack(fill="x")
        self.lbl_veiculo_dica = tk.Label(
            secao, font=FONTE["dica"], bg=fundo, fg=COR["texto_3"],
            justify="left", anchor="w", wraplength=px(320),
            text="Levam o carro sem o dono e sem senha, se estiverem no "
                 "campus a pé e sem bloqueio.")
        self.lbl_veiculo_dica.pack(fill="x", pady=(px(2), px(8)))
        self.quadro_autorizados, self.tabela_autorizados = tabela(
            secao, COLUNAS_AUTORIZADOS, altura=4, rolagem=True, compacta=True)
        self.quadro_autorizados.pack(fill="both", expand=True)
        self.botoes_veiculo = tk.Frame(secao, bg=fundo)
        self.botoes_veiculo.pack(fill="x", pady=(px(10), 0))
        self.btn_adicionar_autorizado = Botao(
            self.botoes_veiculo, "Adicionar", self.adicionar_autorizado,
            "secundario", icone=ICONE["mais"])
        self.btn_adicionar_autorizado.pack(side="left")
        self.btn_remover_autorizado = Botao(
            self.botoes_veiculo, "Remover", self.remover_autorizado, "perigo")
        self.btn_remover_autorizado.pack(side="left", padx=(px(8), 0))
        self.lbl_dono_fora = tk.Label(secao, font=FONTE["dica"], bg=fundo,
                                      fg=COR["alerta"], justify="left",
                                      anchor="w", wraplength=px(320))
        self.autorizados = []
        return secao

    def mostrar_autorizados(self, pessoa):
        """Lista "Quem pode retirar" da placa da pessoa e o estado dos
        botões (o porteiro só adiciona com o dono no campus)."""
        placa = pessoa["placa"]
        self.autorizados = []
        self.tabela_autorizados.delete(*self.tabela_autorizados.get_children())
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
        self.lbl_veiculo_dica.pack(fill="x", pady=(px(2), px(8)),
                                   after=self.lbl_veiculo)
        self.quadro_autorizados.pack(fill="both", expand=True,
                                     after=self.lbl_veiculo_dica)
        self.botoes_veiculo.pack(fill="x", pady=(px(10), 0),
                                 after=self.quadro_autorizados)
        ok, lista = self.app.tentar(self.app.banco.listar_autorizados, placa)
        if ok:
            self.autorizados = lista
        hoje = self.app.relogio().date()
        for i, a in enumerate(self.autorizados):
            vencida = a["valido_ate"] is not None and a["valido_ate"] < hoje
            validade = ("venceu" if vencida
                        else descrever_validade(a["valido_ate"]).replace(
                            "sem prazo (até remover)", "sem prazo"))
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
        if ok:
            self.lbl_dono_fora.pack_forget()
        else:
            self.lbl_dono_fora.config(text="O dono precisa estar no campus "
                                           "para o porteiro adicionar.")
            self.lbl_dono_fora.pack(fill="x", pady=(px(6), 0),
                                    after=self.botoes_veiculo)
        self.btn_remover_autorizado.definir_ativo(bool(self.autorizados))

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
        self.dialogo = DialogoAutorizado(self, p)
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
        """Cadastro ou Visitas. Nas visitas a placa e os números saem da
        frente: sobra altura para a lista (tela pequena)."""
        if nome == SECOES_FICHA[1]:
            self.linha_placa.pack_forget()
        else:
            self.linha_placa.pack(fill="x", pady=(px(12), 0), after=self.lbl_cpf)
        for secao, frame in getattr(self, "secoes", {}).items():
            if secao == nome:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

    @staticmethod
    def _numero(pai, legenda):
        bloco = tk.Frame(pai, bg=COR["superficie"])
        bloco.pack(anchor="w")
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
        if p["cpf"] in self.bloqueados:
            texto = ("No campus · " if p["dentro_desde"] else "") + "Bloqueado"
            ordem = NO_CAMPUS if p["dentro_desde"] else BLOQUEADO
            return ordem, texto, "Bloqueado", COR["erro"]
        if p["dentro_desde"]:
            return NO_CAMPUS, "No campus", "No campus", COR["sucesso"]
        return FORA, "—", "Fora", COR["barra"]

    def _ordem_situacao(self, p):
        return self._situacao_da_pessoa(p)[0]

    def atualizar(self):
        ok, pessoas = self.app.tentar(
            self.app.banco.buscar_pessoas, self.busca.get(), LIMITE_BUSCA,
            so_cpf_completo=not eh_admin(self.app.usuario))
        if not ok:
            return
        ok, bloqueios = self.app.tentar(self.app.banco.listar_bloqueios)
        self.bloqueados = {b["valor"]: b["motivo"] for b in (bloqueios or [])
                           if b["tipo"] == "cpf"}
        self.pessoas = pessoas
        self.mostrar_lista()

        ok, n = self.app.tentar(self.app.banco.contadores)
        if ok:
            self.lbl_total.config(
                text=plural(n["pessoas"], "pessoa cadastrada",
                            "pessoas cadastradas")
                + f"  ·  {n['no_campus']} no campus agora")
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
                formatar_celular(p["celular"]), formatar_placa(p["placa"]) or "—",
                p["tipo"], p["visitas"], p["ultima_visita"] or "—", situacao),
                iid=str(p["id"]), situacao=texto, cor=cor)
        if selecao and self.tabela.exists(selecao[0]):
            self.tabela.selection_set(selecao[0])

    def ao_selecionar(self, event=None):
        selecao = self.tabela.selection()
        if not selecao:
            return
        p = next(p for p in self.pessoas if p["id"] == int(selecao[0]))
        self.selecionada = p
        self.vazio.place_forget()
        self.conteudo.pack(fill="both", expand=True)
        self.lbl_titulo.config(text=p["nome"])
        self.lbl_cpf.config(text="CPF " + self.app.exibir_cpf(p["cpf"]))
        self.lbl_visitas.config(text=str(p["visitas"]))
        self.lbl_ultima.config(text=(p["ultima_visita"] or "—")[:5])
        self.nome.delete(0, tk.END)
        self.nome.insert(0, p["nome"])
        self.celular.delete(0, tk.END)
        self.celular.insert(0, p["celular"])
        self.var_placa.set(p["placa"])
        self.tipo.set(p["tipo"])
        motivo = self.bloqueados.get(p["cpf"])
        if motivo:
            self._faixa("erro", f"CPF bloqueado: {motivo}")
        elif p["dentro_desde"]:
            self._faixa("sucesso", f"No campus desde {p['dentro_desde']}.")
        else:
            self.faixa.pack_forget()
        self._mostrar_placa()
        self.mostrar_visitas(p)
        self.mostrar_autorizados(p)

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
        self.faixa.pack(fill="x", pady=(px(14), 0), before=self.seletor_ficha)

    def _mostrar_placa(self):
        self.desenho_placa.mostrar(self.var_placa.get().strip())

    def _exigir_selecao(self):
        if self.selecionada is None:
            mensagens.aviso("Atenção", "Selecione uma pessoa na lista.")
            return False
        return True

    # --------------------------------------------------------------
    # Ações
    # --------------------------------------------------------------
    def salvar(self):
        if not self._exigir_selecao():
            return
        p = self.selecionada
        dados = normalizar(self.nome.get(), p["cpf"], self.celular.get(),
                           self.var_placa.get(), self.tipo.get(), "", "")
        ok, msg = validar_campos(dados)
        if not ok:
            mensagens.erro("Dados inválidos", msg)
            return
        ok, _ = self.app.tentar(self.app.banco.atualizar_pessoa, p["id"],
                                dados["nome"], dados["celular"], dados["placa"],
                                dados["tipo"], autor=self.app.autor)
        if not ok:
            return
        self.atualizar()
        self.ao_selecionar()
        self._faixa("sucesso", "Alterações salvas.")

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
                           autor=app.autor)
        if not ok:
            return
        self.fechar()
        self.aba.mostrar_autorizados(self.dono)
