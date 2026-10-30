"""
Página "Entrada e saída" (antiga aba Cadastro): registrar a entrada de uma
pessoa (com preenchimento automático pelo CPF, faixa de situação e alerta
de desativação), dar saída (saída rápida F2 por CPF ou placa, botão ou duplo
clique), desfazer a saída, corrigir e excluir registros.

A tabela "Movimento" mostra o dia: as entradas e saídas de hoje e todo
mundo que ainda está no campus (app.registros = banco.listar_movimento).
Com texto na busca, ela procura no histórico inteiro (banco.buscar_registros).
O seletor [Pessoas | Veículos] troca para os carros no estacionamento.

Veículo com estadia própria (dados.py): a entrada com placa abre a estadia
do carro, e a mesma placa não entra de novo enquanto ele estiver lá. Na
entrada de quem tem placa cadastrada (preenchida sozinha pelo CPF), a
tela pergunta "vai entrar de carro?" (RN34). Na saída de quem tem carro
no estacionamento, pergunta se ele saiu com o carro (tela_veiculo.py); a
pessoa que volta a pé vê a faixa "O carro está no estacionamento" e, na
próxima saída, pode sair com ele. O VEÍCULO SÓ SAI COM O DONO (RN32): a
saída rápida pela placa tira o carro junto com o dono no campus; sem o
dono (fora do campus, ou ele fica), só com a senha de um administrador.
LOTAÇÃO (RN37): com vagas definidas, o cabeçalho mostra "Estacionamento
47/50"; a entrada de carro com ele lotado avisa e pede a confirmação (ou,
com "Bloquear quando lotado", a senha do administrador).
DOIS CARROS DA MESMA PESSOA (RN40): a entrada com outro carro avisa que o
primeiro ainda está lá (entrar, "já saiu" com a senha, cancelar; o terceiro
só com a senha); a saída de quem tem dois carros pergunta uma vez "Com qual
carro Carla está saindo?" e sai um só.
QUEM PODE RETIRAR (RN35): quem está na lista da placa e sai a pé ouve
"Vai levar o carro BRA2E19 de Carla?" (na saída pelo CPF, pelo Movimento
ou pela placa) e leva o carro sem senha; o Desfazer devolve os dois.

Regras de horário (horarios.py): entrada fora do horário da categoria,
retroativa antiga ou visita acima de 24 h é uma EXCEÇÃO e pede a
autorização do administrador (tela_autorizacao.py). A situação de cada
visita aberta é calculada com o relógio do app: "Tempo excedido" (âmbar)
e "Saída pendente" (vermelho, depois do fechamento do dia da entrada).
Faixas no topo da página avisam as saídas pendentes (o administrador
encerra o dia), quando o campus está perto de fechar e, nessa mesma janela
de aviso, os carros com o dono fora do campus (RN36: "2 carros com o dono
fora do campus — fechamento às 23:00", com o link para a lista Veículos).

O tempo passa sozinho (ao_passar_o_tempo, a cada 30 s pelo app): o campo
Entrada acompanha o relógio enquanto ninguém mexe nele (e o registro usa
o "agora" exato do clique), e a situação de cada linha do Movimento é
recalculada junto com as faixas, sem reler o banco.

Fala com a janela principal só pelo contrato público do app (ver
interface.py).
"""

import tkinter as tk
from datetime import datetime

from . import horarios, mensagens
from .componentes import (Aviso, Botao, Cabecalho, Campo, Cartao,
                          EsperaDigitacao, Placa, Seletor, bolinha, data_por_extenso, inserir_linha,
                          link, plural, rotulo_campo, tabela, titulo_cartao)
from .dados import ENTRADA_RECUSADA
from .estilo import (COR, CORES_TIPO, ESPACO_CARTOES, FONTE, ICONE, MARGEM,
                     fonte_icone, px)
from .tela_autorizacao import autorizar_excecao
from .tela_comando import DICA_VAZIO, PainelComando
from .tela_edicao import JanelaEdicao
from .tela_veiculo import (A_PE, COM_CARRO, ENTRAR_COM_SENHA, JA_SAIU,
                           JUNTO, LEVA, OUTRO_CARRO, com_qual_carro,
                           entrar_com_outro_carro, liberar_sem_o_dono,
                           responsavel_saiu_junto, saiu_com_o_veiculo,
                           vai_entrar_de_carro, vai_levar_o_carro)
from .usuarios import eh_admin, pode_editar, pode_excluir
from .validacao import (FORMATO, FORMATO_EXIBICAO, MAXIMO_BUSCA,
                        MAXIMO_NOME, PLACA_OBRIGATORIA,
                        TIPOS_ACESSO, checar_desativacao, checar_saida,
                        cpf_valido, formatar_celular, formatar_cpf,
                        formatar_placa, normalizar, placa_valida, so_digitos,
                        validar)
from .veiculos import (esta_lotado, ordem_dos_carros, regra_lotado,
                       texto_lotacao)

DICA_CPF = "Digite o CPF primeiro: quem já veio tem os dados preenchidos."
SUCESSO_CADASTRO = "Registro cadastrado com sucesso!"   # texto do enunciado
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
DICA_BUSCA = "Buscar: nome, placa, CPF…"


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
        self._entrada_automatica = None     # texto que o relógio pôs na Entrada
        self.veiculos = []                  # carros no estacionamento
        self.lista = LISTAS[0]              # lista mostrada no Movimento
        self._dia_mostrado = None           # o "hoje" da última leitura
        self.ultimo_aviso = ""              # o último texto de avisar()

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
        """Título, data e quantos estão no campus; à direita o campo
        Comando (2.4, no lugar da saída rápida: F2 ou Ctrl+K levam o
        cursor até ele; só o CPF ou a placa continuam dando a saída)."""
        cab = Cabecalho(self.aba, "Entrada e saída").posicionar()
        self.cabecalho = cab
        self.lbl_no_campus = tk.Label(cab.linha, font=FONTE["corpo_semi"],
                                      bg=COR["fundo"], fg=COR["sucesso"])
        self.lbl_no_campus.pack(side="left")
        # RN37: ao lado do título (a linha de baixo já é longa)
        self.lbl_estacionamento = tk.Label(cab.topo, font=FONTE["corpo_semi"],
                                           bg=COR["fundo"], fg=COR["texto_2"])
        self.lbl_estacionamento.pack(side="left", anchor="s",
                                     padx=(px(16), 0), pady=(0, px(4)))

        self.comando = PainelComando(cab.acoes, self)
        # os nomes de antes continuam valendo (testes e interface.py)
        self.lbl_saida_rapida = self.comando.lbl_titulo
        self.campo_saida_rapida_quadro = self.comando.campo
        self.campo_saida_rapida = self.comando.linha

    def _montar_alertas(self):
        """Faixas que só aparecem quando importam (sem caixa de diálogo):
        saídas pendentes e o campus perto de fechar."""
        self.alertas = tk.Frame(self.aba, bg=COR["fundo"])
        self.alertas.pack(fill="x", padx=px(MARGEM))
        self.faixa_pendentes = Aviso(self.alertas, fundo_pai=COR["fundo"])
        self.faixa_fechamento = Aviso(self.alertas, fundo_pai=COR["fundo"])
        self.faixa_esquecidos = Aviso(self.alertas, fundo_pai=COR["fundo"])

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
        self.nome = self._peca("nome", "Nome completo",
                               Campo(form, maximo=MAXIMO_NOME))
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
        # desativada), o botão principal e o "Limpar": filhos do cartão para
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
            self._escolher_densidade(event.height)

    def _escolher_densidade(self, altura):
        """Compacta quando a página, tirando as faixas de alerta, é baixa."""
        livre = altura - self.alertas.winfo_reqheight()
        self._aplicar_densidade(livre < px(ALTURA_CONFORTAVEL))

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
        self.cartao_form.miolo.pack_configure(padx=px(e["cartao"]),
                                              pady=px(e["cartao"]))
        self.cab_form.pack_configure(pady=(0, px(e["titulo"])))
        self._posicionar_formulario(compacta)
        self.cartao_mov.pack_configure(pady=_px(e["movimento"]))
        self.cartao_mov.miolo.pack_configure(pady=px(e["miolo_mov"]))
        self.barra_titulo_mov.pack_configure(pady=_px(e["titulo_mov"]))
        self.barra_mov.pack_configure(pady=_px(e["barra"]))
        for tab in (self.tabela, self.tabela_veiculos):
            tab.configure(style="Compacta.Tabela.Treeview" if compacta
                          else "Tabela.Treeview")
        for faixa in self._faixas():
            faixa.definir_respiro(5 if compacta else 9)

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
        """Campo de data/hora: clicar nele (ou no relógio) abre o
        calendário e o relógio (o "Agora" deles usa o relógio do app)."""
        return Campo(form, seletor="data_hora", relogio=self.app.relogio)

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
        """Cartão Movimento: o título numa linha própria, no canto de cima;
        embaixo dele as subabas Pessoas | Veículos à esquerda e, na mesma
        linha, a busca e os botões à direita."""
        self.cartao_mov = Cartao(self.aba, pad=0)
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

        self.btn_excluir = None
        if pode_excluir(self.app.usuario):  # RN02: o porteiro nem vê o botão
            self.btn_excluir = Botao(barra, "Excluir", self.excluir_selecionado,
                                     "perigo", icone=ICONE["lixo"])
        self.btn_corrigir = Botao(barra, "Corrigir", self.editar_selecionado,
                                  "secundario", icone=ICONE["editar"])
        self.btn_saida = Botao(barra, "Registrar saída", self.registrar_saida,
                               "secundario", icone=ICONE["seta"])

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
        barra = [self.btn_excluir, self.btn_corrigir, self.btn_saida,
                 self.campo_busca]
        for w in barra + [self.quadro_pessoas, self.quadro_veiculos]:
            if w is not None:
                w.pack_forget()
        # a ordem do pack importa: a busca entra por último e encolhe se
        # faltar largura (tela pequena), os botões não
        if pessoas and self.btn_excluir is not None:
            self.btn_excluir.pack(side="right")
        if pessoas:
            self.btn_corrigir.pack(side="right", padx=(0, px(8)))
        self.btn_saida.pack(side="right", padx=(0, px(8)) if pessoas else 0)
        if pessoas:
            self.campo_busca.pack(side="left", fill="x", expand=True,
                                  padx=(px(16), px(16)))
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

    def _agora_texto(self):
        return self.app.relogio().strftime(FORMATO)

    # --------------------------------------------------------------
    # O tempo passando: campo Entrada, situação das linhas e faixas
    # --------------------------------------------------------------
    def ao_passar_o_tempo(self):
        """Chamado pelo app a cada 30 s (e pelos testes). Na virada do dia
        relê tudo: o cabeçalho, o movimento e a contagem são "de hoje"."""
        self.acompanhar_relogio()
        if self.app.relogio().date() != self._dia_mostrado:
            self.app.atualizar_tabela()
            return
        self.atualizar_situacoes()
        self.atualizar_alertas()

    def entrada_automatica(self):
        """True enquanto o campo Entrada tem o que o relógio escreveu (o
        usuário não editou)."""
        return self.entrada.get() == self._entrada_automatica

    def acompanhar_relogio(self):
        """A Entrada intocada mostra sempre o agora (o bug do aluno: o campo
        ficava parado na hora em que o formulário foi limpo)."""
        if self.entrada_automatica():
            self._escrever_entrada_agora()

    def _escrever_entrada_agora(self):
        self._entrada_automatica = self._agora_texto()
        self.entrada.delete(0, tk.END)
        self.entrada.insert(0, self._entrada_automatica)

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
            ok, registros = self.app.tentar(
                self.app.banco.buscar_registros, texto, LIMITE_BUSCA,
                so_cpf_completo=not eh_admin(self.app.usuario))
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
            cor, destaque = aparencia(situacao)
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
        self._encontrados = len(registros) if texto else None
        self._atualizar_veiculos(agora)
        self._mostrar_status()

        dentro = sum(1 for r in self.app.registros if not r["saida"])
        self.cabecalho.subtitulo.config(
            text=data_por_extenso(self.app.relogio()) + "  ·  ")
        self.lbl_no_campus.config(
            text="Ninguém no campus agora" if not dentro else
            plural(dentro, "pessoa", "pessoas") + " no campus agora")
        self._mostrar_lotacao()
        self.atualizar_alertas()

    def _mostrar_lotacao(self):
        """RN37: "· Estacionamento 47/50" no cabeçalho (âmbar se lotado);
        sem controle de vagas, nada."""
        vagas = self.config.vagas if self.config else 0
        texto = texto_lotacao(len(self.veiculos), vagas)
        lotado = esta_lotado(len(self.veiculos), vagas)
        self.lbl_estacionamento.config(
            text=(ICONE["carro"] + "  " + texto) if texto else "",
            fg=COR["alerta"] if lotado else COR["texto_2"])

    def _mostrar_status(self):
        """Status do Movimento (ao lado do título), conforme a lista mostrada."""
        if self.lista == LISTAS[1]:
            status = (plural(len(self.veiculos), "veículo", "veículos")
                      + " no estacionamento  ·  duplo clique registra a saída "
                        "do carro")
        elif getattr(self, "_encontrados", None) is not None:
            n = self._encontrados
            status = plural(n, "registro encontrado",
                            "registros encontrados") + " no histórico"
            if n >= LIMITE_BUSCA:
                status += f" (os {LIMITE_BUSCA} mais recentes)"
        else:
            dentro = sum(1 for r in self.app.registros if not r["saida"])
            hoje = self.app.relogio().strftime("%d/%m/%Y")
            entradas_hoje = sum(1 for r in self.app.registros
                                if r["entrada"].startswith(hoje))
            status = (f"{plural(entradas_hoje, 'entrada', 'entradas')} hoje"
                      f"  ·  {dentro} no campus  ·  duplo clique registra a saída")
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
                "No campus" if e["responsavel_dentro"] else "Fora do campus"),
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
        self._posicionar_faixas([f for f, visivel in (
            (self.faixa_pendentes, pendentes > 0 or bool(carros)),
            (self.faixa_fechamento, minutos is not None),
            (self.faixa_esquecidos, bool(esquecidos))) if visivel])
        if self.aba.winfo_height() > 1:          # faixas mudam a altura livre
            self.alertas.update_idletasks()
            self._escolher_densidade(self.aba.winfo_height())

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
        if 1 < self.aba.winfo_height() < px(ALTURA_CONFORTAVEL):
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
        return (self.faixa_pendentes, self.faixa_fechamento,
                self.faixa_esquecidos)

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

    def _esta_visivel(self):
        # a página fica dentro do Notebook de páginas (self.aba.master)
        return self.aba.master.select() == str(self.aba)

    # --------------------------------------------------------------
    # Registrar a entrada e limpar
    # --------------------------------------------------------------
    def cadastrar(self, event=None):
        if event is not None and not self._esta_visivel():
            return  # Enter só registra na página Entrada e saída
        self.acompanhar_relogio()      # Entrada intocada = o agora exato
        registro = normalizar(self.nome.get(), self.cpf.get(),
                              self.celular.get(), self.var_placa.get(),
                              self.tipo.get(), self.entrada.get(),
                              self.saida.get())
        if self.registrar_entrada(registro, self._placa_sugerida(),
                                  (self._auto or {}).get("pessoa_id"),
                                  self._digitar_outro_carro):
            self.limpar()

    def registrar_entrada(self, registro, sugerida="", pessoa_id=None,
                          ao_outro_carro=None):
        """
        O caminho ÚNICO da entrada: o formulário (cadastrar) e a linha de
        comando (linguagem/executor.py) passam por aqui, com as mesmas
        checagens, os mesmos diálogos e a mesma gravação. `sugerida`: a
        placa do cadastro que ninguém confirmou (a pergunta "vai entrar de
        carro?", RN34); `ao_outro_carro`: o que fazer se a resposta for
        "Com outro carro". Devolve o texto do aviso de sucesso ou None.
        """
        # RN12: pessoa ou veículo desativado primeiro, para não preencher
        # a ficha à toa (o banco confere de novo)
        ok, ativas = self.app.tentar(self.app.banco.listar_desativacoes)
        if not ok:
            return None
        ok, msg = checar_desativacao(registro, ativas)
        if not ok:
            self.registrar_recusa(registro)
            mensagens.erro("Acesso negado", msg)
            return None
        placa = self._como_vai_entrar(registro, sugerida, pessoa_id,
                                      ao_outro_carro)
        if placa is None:
            return None
        registro["placa"] = placa
        if registro["placa"] and not registro["saida"]:
            estadia = self._carro_no_estacionamento(registro["placa"])
            if estadia is not None:
                mensagens.erro("Veículo no estacionamento",
                               self._texto_carro_ja_dentro(estadia))
                return None
        # a sobreposição é conferida com TODAS as visitas desse CPF no banco
        # (a tabela só tem o movimento do dia)
        ok, anteriores = self.app.tentar(self.app.banco.listar_por_cpf,
                                         registro["cpf"])
        if not ok:
            return None
        agora = self.app.relogio()
        ok, msg = validar(registro, anteriores, agora)
        if not ok:
            mensagens.erro("Dados inválidos", msg)
            return None
        # VERIFICAÇÃO SEMÂNTICA 6: a entrada faz sentido para a categoria
        # naquele dia e horário? Se não, é exceção: só com autorização
        ok, config = self.app.tentar(self.app.banco.ler_configuracao)
        if not ok:
            return None
        autorizacao = None
        regras = horarios.excecoes_do_registro(config, registro, agora)
        if regras:
            autorizacao = autorizar_excecao(self.app, regras,
                                            f"A entrada de {registro['nome']}")
            if autorizacao is None:
                return None
        carros = self._entrada_com_outro_carro(registro)
        if carros is None:
            return None
        lotacao = self._entrada_com_lotacao(registro, carros)
        if lotacao is None:
            return None
        if not self.app.gravar(self.app.banco.inserir, registro,
                               autorizacao=autorizacao, **carros, **lotacao):
            return None
        self.app.atualizar_tabela()
        hora = registro["entrada"][-5:]
        # texto do enunciado do exercício, na faixa (sem caixa para fechar);
        # é o único caminho da entrada: Pessoas › Registrar entrada, o
        # retroativo, a entrada com outro carro e o comando passam por aqui
        texto = (f"{SUCESSO_CADASTRO} Entrada de "
                 f"{registro['nome'].split()[0]} às {hora}"
                 + self._com_autorizacao(autorizacao))
        self.avisar(texto)
        return texto

    def _entrada_com_outro_carro(self, registro):
        """RN40: quem já tem carro no estacionamento e entra com OUTRO.
        Devolve o que vai ao banco ({} = nada) ou None (cancelou)."""
        if not registro["placa"] or registro["saida"]:
            return {}
        ok, estadias = self.app.tentar(self.app.banco.estadias_abertas_do_cpf,
                                       registro["cpf"])
        if not ok:
            return None
        estadias = [e for e in estadias if e["placa"] != registro["placa"]]
        if not estadias:
            return {}
        resposta = entrar_com_outro_carro(self.app, registro["nome"],
                                          registro["placa"], estadias)
        if resposta is None:
            return None
        if resposta == ENTRAR_COM_SENHA:
            autorizacao = autorizar_excecao(
                self.app, [f"{registro['nome']} já tem {len(estadias)} carros "
                           "no estacionamento: outro só entra com a senha de "
                           "um administrador."],
                f"A entrada do carro {formatar_placa(registro['placa'])}",
                so_com_senha=True)
            return None if autorizacao is None else {
                "autorizacao_carros": autorizacao}
        if isinstance(resposta, tuple) and resposta[0] == JA_SAIU:
            estadia = next(e for e in estadias if e["id"] == resposta[1])
            placa = formatar_placa(estadia["placa"])
            autorizacao = autorizar_excecao(
                self.app, [f"O carro {placa} consta no estacionamento desde "
                           f"{self._quando(estadia['entrada'])}, mas já saiu "
                           "sem registro: a saída dele é corrigida agora."],
                f"A correção da saída do carro {placa}", veiculo=True)
            return None if autorizacao is None else {
                "carro_ja_saiu": estadia["id"],
                "autorizacao_ja_saiu": autorizacao}
        return {}

    def _entrada_com_lotacao(self, registro, carros=None):
        """RN37: entrada de carro com o estacionamento lotado. Avisa e pede
        a confirmação ou, com "Bloquear quando lotado", a senha do
        administrador (até o administrador logado redigita a sua). Devolve
        o que vai para o banco ({} = nada a conferir) ou None (desistiu)."""
        if not registro["placa"] or registro["saida"]:
            return {}
        ok, ocupacao = self.app.tentar(self.app.banco.ocupacao_estacionamento)
        if not ok:
            return None
        ocupadas, vagas, bloquear = ocupacao
        if carros and carros.get("carro_ja_saiu"):
            ocupadas -= 1           # o carro que já tinha saído não conta
        if not esta_lotado(ocupadas, vagas):
            return {}
        regra = regra_lotado(ocupadas, vagas)
        placa = formatar_placa(registro["placa"])
        if bloquear:
            autorizacao = autorizar_excecao(
                self.app, [f"{regra}: a entrada de carro só passa com a senha "
                           "de um administrador."],
                f"A entrada do carro {placa}", so_com_senha=True)
            return None if autorizacao is None else {
                "autorizacao_lotacao": autorizacao}
        if not self.app.perguntar(
                mensagens.confirmar, "Estacionamento lotado",
                f"{regra}.\nRegistrar a entrada do carro {placa} mesmo assim? "
                "A entrada fica no histórico."):
            return None
        return {"lotado_confirmado": True}

    def _como_vai_entrar(self, registro, sugerida, pessoa_id,
                         ao_outro_carro=None):
        """RN34: quem tem placa cadastrada (o CPF a preencheu e ninguém mexeu
        no campo Placa; no comando, nem "placa" nem "sem carro") responde
        se entra de carro. Devolve a placa da visita ('' = a pé) ou None
        (cancelou ou vai digitar outra placa).
        Não pergunta se a Placa foi digitada ou apagada à mão (vale o que
        está no campo), se o carro dela já está no estacionamento (o CPF
        nem preenche a placa: ela volta a pé) ou se não há placa
        cadastrada."""
        if not sugerida or registro["placa"] != sugerida:
            return registro["placa"]
        resposta = vai_entrar_de_carro(self.app, registro["nome"], sugerida,
                                       self._ultima_visita_de_carro(pessoa_id))
        if resposta == OUTRO_CARRO:
            if ao_outro_carro is not None:
                ao_outro_carro()
            return None
        if resposta is None:
            return None
        return sugerida if resposta == COM_CARRO else ""

    def _digitar_outro_carro(self):
        """"Com outro carro" no formulário: o campo Placa fica vazio e com
        o foco, para digitar a outra placa."""
        self.var_placa.set("")
        self.pecas["placa"][1].entrada.focus_set()

    def _placa_sugerida(self):
        """A placa cadastrada que o CPF preencheu, se o campo continua com
        ela (o porteiro não digitou nem apagou); senão ''."""
        auto = (self._auto or {}).get("campos", {}).get("placa", "")
        return auto if auto and self.var_placa.get() == auto else ""

    def _ultima_visita_de_carro(self, pessoa_id):
        if pessoa_id is None:
            return False
        ok, visitas = self.app.tentar(self.app.banco.visitas_da_pessoa,
                                      pessoa_id, 1)
        return bool(ok and visitas and visitas[0]["placa"])

    @staticmethod
    def _com_autorizacao(autorizacao):
        if autorizacao is None:
            return "."
        return f" (exceção autorizada por {autorizacao['autorizado_por']})."

    def _carro_no_estacionamento(self, placa):
        if not placa_valida(placa):
            return None
        ok, estadia = self.app.tentar(self.app.banco.estadia_aberta, placa=placa)
        return estadia if ok else None

    def _texto_carro_ja_dentro(self, estadia):
        return (f"O carro {formatar_placa(estadia['placa'])} já está no "
                f"estacionamento desde {self._quando(estadia['entrada'])} "
                f"(responsável: {estadia['nome']}).\nRegistre a saída dele "
                "pela placa ou deixe a placa vazia (entrada a pé).")

    def registrar_recusa(self, registro):
        """RN12: a entrada recusada vai ao histórico (o comando também)."""
        detalhe = f"{registro['nome'] or '?'}, CPF {formatar_cpf(registro['cpf'])}"
        if registro["placa"]:
            detalhe += f", placa {registro['placa']}"
        self.app.tentar(self.app.banco.registrar_evento, self.app.autor,
                        ENTRADA_RECUSADA, detalhe)

    def limpar(self):
        self._auto = None
        self.nome.delete(0, tk.END)
        self.var_cpf.set("")
        self.celular.delete(0, tk.END)
        self.var_placa.set("")
        self.tipo.set("")
        self._escrever_entrada_agora()
        self.saida.delete(0, tk.END)
        self.cpf.focus()

    def ler_formulario(self):
        """O que está digitado no formulário, na busca e a lista mostrada
        (o app remonta a tela ao trocar o tema e devolve tudo depois).
        Entrada None = o relógio ainda cuida dela."""
        estado = {chave: campo.get()
                  for chave, campo in self._campos_digitaveis().items()}
        estado["entrada"] = (None if self.entrada_automatica()
                             else self.entrada.get())
        estado["busca"], estado["lista"] = self.busca.get(), self.lista
        estado["comando"] = self.comando.ler()      # só na memória
        return estado

    def restaurar_formulario(self, estado):
        """Devolve o que ler_formulario guardou. O CPF vai por último: ao
        completar, ele mostra de novo a situação da pessoa."""
        for chave, campo in self._campos_digitaveis().items():
            if chave != "cpf":
                self._escrever(campo, estado[chave])
        if estado["entrada"] is not None:
            self._escrever(self.entrada, estado["entrada"])
        self._escrever(self.busca, estado["busca"])
        self.seletor_lista.selecionar(estado["lista"])
        self.var_cpf.set(estado["cpf"])
        self.atualizar_tabela()
        self.comando.restaurar(estado.get("comando"))

    def _campos_digitaveis(self):
        return {**self._campos_pessoa(), "cpf": self.var_cpf,
                "saida": self.saida}

    def preencher_pessoa(self, pessoa):
        """Começa uma nova entrada para a pessoa (usado pela página Pessoas)."""
        self.limpar()
        self.var_cpf.set(pessoa["cpf"])
        self.tipo.focus()

    # --------------------------------------------------------------
    # Preenchimento automático pelo CPF, faixa de situação e desativação
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

    def _situacao(self, tipo, texto, acao=None, comando=None, icone=None):
        self.aviso_pessoa.mostrar(tipo, texto, icone=icone, acao=acao,
                                  comando=comando)

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
            # o carro dele já está no estacionamento: a entrada é a pé
            parado = self._carro_no_estacionamento(pessoa["placa"])
            self._preencher_automatico(pessoa, sem_placa=parado is not None)
        self._mostrar_situacao(cpf, pessoa)

    def _mostrar_situacao(self, cpf, pessoa):
        """Faixa e ficha conforme a pessoa: nova, já veio, no campus ou
        desativada (a desativação tem a palavra final)."""
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
            ok, estadia = self.app.tentar(self.app.banco.estadia_aberta, cpf=cpf)
            if ok and estadia:
                self._situacao(
                    "info", f"O carro {formatar_placa(estadia['placa'])} está "
                            "no estacionamento desde "
                            f"{self._quando(estadia['entrada'])}: a entrada é "
                            f"a pé. Na saída, {pessoa['nome'].split()[0]} "
                            "pode sair com o carro (\"Saiu de carro\").",
                    icone=ICONE["carro"])
        desativada = self._desativacao("cpf", cpf)
        if desativada:
            self._situacao("erro", "Pessoa desativada: "
                                   f"{desativada['motivo']}. "
                                   "A entrada será recusada.",
                           "Ver desativação",
                           lambda: self.app.mostrar_desativacao("cpf", cpf))

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

    def _desativacao(self, tipo, valor):
        """A desativação em vigor do CPF ou da placa, ou None."""
        ok, ativas = self.app.tentar(self.app.banco.listar_desativacoes,
                                     tipo=tipo)
        return next((d for d in (ativas or []) if d["valor"] == valor), None)

    def _ao_digitar_placa(self, *args):
        """Placa desenhada acompanha a digitação (Mercosul ou antiga);
        veículo desativado fica vermelho."""
        placa = self.var_placa.get().strip().upper()
        desativado = (self._desativacao("placa", placa)
                      if placa_valida(placa) else None)
        parado = None if desativado else self._carro_no_estacionamento(placa)
        self.desenho_placa.mostrar(placa, bloqueada=desativado is not None)
        if desativado:
            self.lbl_dica_placa.config(text="desativado", fg=COR["erro"],
                                       font=FONTE["rotulo"])
            self.lbl_placa_status.config(
                text=f"Veículo desativado: {desativado['motivo']}",
                fg=COR["erro"])
            self.lbl_placa_status.pack_configure(pady=(px(6), 0))
        elif parado:
            self.lbl_dica_placa.config(text="já no estacionamento",
                                       fg=COR["alerta"], font=FONTE["rotulo"])
            self.lbl_placa_status.config(
                text=f"Já está no estacionamento desde "
                     f"{self._quando(parado['entrada'])} ({parado['nome']}).",
                fg=COR["alerta"])
            self.lbl_placa_status.pack_configure(pady=(px(6), 0))
        else:
            self.lbl_dica_placa.config(text=DICA_PLACA, fg=COR["texto_3"],
                                       font=FONTE["dica"])
            self.lbl_placa_status.config(text="")
            self.lbl_placa_status.pack_configure(pady=0)

    def _preencher_automatico(self, pessoa, sem_placa=False):
        preenchidos = {}
        for chave, campo in self._campos_pessoa().items():
            if chave == "placa" and sem_placa:
                continue
            if not campo.get().strip() and pessoa[chave]:
                self._escrever(campo, pessoa[chave])
                preenchidos[chave] = campo.get()
        self._auto = {"cpf": pessoa["cpf"], "pessoa_id": pessoa["id"],
                      "campos": preenchidos}

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
