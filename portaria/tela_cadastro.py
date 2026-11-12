"""
Páginas "Cadastro" e "Controle de acesso" (a antiga Entrada e saída): registrar a entrada de uma
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

from . import horarios, mensagens
from .componentes import (Aviso, BotaoTk, Cabecalho, Campo, CampoTexto,
                          Cartao, Chip, Contador, Placa, rotulo_campo,
                          titulo_cartao)
from .dados import ENTRADA_RECUSADA
from .estilo import COR, CORES_TIPO, FONTE, ICONE, MARGEM, px
from .tela_autorizacao import autorizar_excecao
from .tela_comando import PainelComando
from .tela_veiculo import (A_PE, COM_CARRO, entrar_com_outro_carro,
                           ENTRAR_COM_SENHA, JA_SAIU, OUTRO_CARRO,
                           vai_entrar_de_carro)
from .validacao import (checar_desativacao, codigo_da_visita, cpf_valido,
                        formatar_cpf, formatar_placa, FORMATO,
                        MAXIMO_ANFITRIAO, MAXIMO_CRACHA, MAXIMO_EMPRESA,
                        MAXIMO_MOTIVO_VISITA, MAXIMO_NOME, normalizar,
                        PLACA_OBRIGATORIA, placa_valida, so_digitos,
                        TIPOS_ACESSO, validar)
from .veiculos import esta_lotado, regra_lotado
from .tela_controle import ControleMixin, ESPACOS, FILTRO_TODOS, LISTAS, _px

DICA_CPF = "Digite o CPF primeiro: quem já veio tem os dados preenchidos."
SUCESSO_CADASTRO = "Registro cadastrado com sucesso!"   # texto do enunciado
DICA_PLACA = "obrigatória" if PLACA_OBRIGATORIA else "opcional"
ALTURA_CADASTRO = 660       # abaixo disso o Cadastro usa menos respiro
# Posição (linha, coluna, colunas ocupadas) de cada campo do Cadastro, com o
# rótulo na linha de cima. Dois blocos, na ordem em que o porteiro pergunta:
# a Pessoa (quem é) e a Visita (quando, com qual carro e por quê). A ordem
# daqui é também a ordem do Tab.
GRADE = {
    "cpf": (0, 0, 1),
    "nome": (0, 1, 2),
    "celular": (0, 3, 1),
    "empresa": (3, 0, 2),
    "tipo": (3, 2, 2),
    # linha 5: o título do bloco Visita
    "data": (6, 0, 1),
    "hora": (6, 1, 1),
    "placa": (6, 2, 1),
    "cracha": (6, 3, 1),
    "motivo": (8, 0, 2),
    "anfitriao": (8, 2, 1),
    "saida": (8, 3, 1),
}
COLUNAS_DO_FORMULARIO = 4
LIMITE_ANFITRIAO_NA_FAIXA = 24     # o resto do nome vira reticências
LINHA_VISITA, LINHA_BOTOES = 5, 10


class DataEHora:
    """Os campos Data e Horário da entrada (separados, como pede o
    enunciado), falando como um campo só: "dd/mm/aaaa hh:mm"."""

    def __init__(self, data, hora):
        self.data, self.hora = data, hora

    def get(self):
        return f"{self.data.get().strip()} {self.hora.get().strip()}".strip()

    def delete(self, inicio=0, fim=None):
        self.data.delete(0, tk.END)
        self.hora.delete(0, tk.END)

    def insert(self, indice, texto):
        partes = str(texto).split(None, 1)
        self.data.insert(tk.END, partes[0] if partes else "")
        self.hora.insert(tk.END, partes[1] if len(partes) > 1 else "")

    def focus_set(self):
        self.data.focus_set()

    focus = focus_set


class AbaCadastro(ControleMixin):
    """As duas telas do enunciado, que dividem o mesmo formulário e a mesma
    lista: `aba` é a página Cadastro; `aba_controle`, a Controle de acesso."""

    def __init__(self, aba, app, aba_controle):
        self.aba = aba
        self.aba_controle = aba_controle
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
        self.aba_controle.bind("<Configure>", self._ao_redimensionar)
        self.aba.bind("<Configure>", self._ao_redimensionar_cadastro)

    # --------------------------------------------------------------
    # Montagem
    # --------------------------------------------------------------
    def _montar_cabecalho(self):
        """Título, data e quantos estão no campus; à direita o campo
        Comando (2.4, no lugar da saída rápida: F2 ou Ctrl+K levam o
        cursor até ele; só o CPF ou a placa continuam dando a saída)."""
        self.cabecalho_cadastro = Cabecalho(
            self.aba, "Cadastro",
            "Cadastro de pessoas que terão acesso à portaria").posicionar()
        cab = Cabecalho(self.aba_controle, "Controle de acesso").posicionar()
        self.cabecalho = cab
        self.lbl_no_campus = tk.Label(cab.linha, font=FONTE["corpo_semi"],
                                      bg=COR["fundo"], fg=COR["sucesso"])
        self.lbl_no_campus.pack(side="left")
        # RN37: uma etiqueta ao lado do título (some sem controle de vagas)
        self.chip_estacionamento = Chip(cab.topo, COR["fundo"])
        self.lbl_estacionamento = self.chip_estacionamento.lbl

        self.comando = PainelComando(cab.acoes, self)
        # os nomes de antes continuam valendo (testes e interface.py)
        self.lbl_saida_rapida = self.comando.lbl_titulo
        self.campo_saida_rapida_quadro = self.comando.campo
        self.campo_saida_rapida = self.comando.linha

    def _montar_formulario(self):
        """Tela de Cadastro: o formulário à esquerda, com a ficha da pessoa
        (placa desenhada e histórico) à direita."""
        self.cartao_form = Cartao(self.aba, pad=ESPACOS["normal"]["cartao"])
        self.cartao_form.pack(fill="x", padx=px(MARGEM))
        m = self.cartao_form.miolo
        self.cab_form = tk.Frame(m, bg=COR["superficie"])
        self.cab_form.pack(fill="x")
        self.titulo_form = titulo_cartao(self.cab_form, "Pessoa")
        corpo = tk.Frame(m, bg=COR["superficie"])
        corpo.pack(fill="x")
        self.ficha = tk.Frame(corpo, bg=COR["superficie"], width=px(214))
        self.divisor_ficha = tk.Frame(corpo, bg=COR["borda"], width=1)
        self.form = form = tk.Frame(corpo, bg=COR["superficie"])
        form.pack(side="left", fill="x", expand=True)

        # CPF primeiro: é por ele que a pessoa é reconhecida
        self.var_cpf = tk.StringVar(self.aba)
        self.cpf = self._peca("cpf", "CPF *", Campo(form, numeros=11, var=self.var_cpf))
        self.nome = self._peca("nome", "Nome completo *",
                               Campo(form, maximo=MAXIMO_NOME))
        self.celular = self._peca("celular", "Telefone *",
                                  Campo(form, numeros=11), "com DDD")
        campo_placa = Campo(form, placa=True)
        self.var_placa = campo_placa.var
        self._peca("placa", "Placa", campo_placa, DICA_PLACA)
        self.lbl_dica_placa = self.apoios["placa"]
        self.tipo = self._peca("tipo", "Tipo de acesso *",
                               Campo(form, opcoes=TIPOS_ACESSO))
        self.empresa = self._peca("empresa", "Empresa *",
                                  Campo(form, maximo=MAXIMO_EMPRESA))
        # RN48: data e horário separados; o calendário (DateEntry do
        # enunciado) e o relógio são os do seletor_data.py
        self.campo_data_entrada = self._peca(
            "data", "Data *",
            Campo(form, seletor="data", relogio=self.app.relogio), "dd/mm/aaaa")
        self.campo_hora_entrada = self._peca(
            "hora", "Horário *",
            Campo(form, seletor="hora", relogio=self.app.relogio), "hh:mm")
        self.entrada = DataEHora(self.campo_data_entrada,
                                 self.campo_hora_entrada)
        self.campo_motivo = CampoTexto(form, MAXIMO_MOTIVO_VISITA)
        self.motivo = self._peca("motivo", "Motivo da visita *", self.campo_motivo)
        self.motivo.bind_enter(self.cadastrar)
        linha_motivo = self.pecas["motivo"][0]
        self.contador_motivo = Contador(linha_motivo, self.campo_motivo)
        self.contador_motivo.pack(side="right")
        # 3.2: quem a visita procura e o crachá entregue (opcionais)
        self.anfitriao = self._peca("anfitriao", "Quem procura",
                                    Campo(form, maximo=MAXIMO_ANFITRIAO))
        self.cracha = self._peca("cracha", "Crachá",
                                 Campo(form, numeros=MAXIMO_CRACHA), "opcional")
        self.saida = self._peca("saida", "Saída", self._campo_data(form),
                                "se já saiu")

        # Faixa de situação da pessoa (neutra, nova, já veio, dentro,
        # desativada) e os botões do enunciado: Cadastrar, Limpar e Cancelar
        self.aviso_pessoa = Aviso(m)
        self.lbl_pessoa = self.aviso_pessoa.lbl
        self.linha_botoes = tk.Frame(m, bg=COR["superficie"])
        self.btn_cadastrar = BotaoTk(self.linha_botoes, "Cadastrar",
                                     self.cadastrar, "primario")
        self.btn_cadastrar.pack(side="left")
        self.btn_limpar = BotaoTk(self.linha_botoes, "Limpar", self.limpar)
        self.btn_limpar.pack(side="left", padx=(px(8), 0))
        self.btn_cancelar = BotaoTk(self.linha_botoes, "Cancelar", self.cancelar,
                                    "fantasma")
        self.btn_cancelar.pack(side="left", padx=(px(8), 0))
        tk.Label(self.linha_botoes, text="* campos obrigatórios",
                 font=FONTE["dica"], bg=COR["superficie"],
                 fg=COR["texto_3"]).pack(side="left", padx=(px(14), 0))

        self._montar_ficha()
        self._posicionar_formulario()
        # Liga o preenchimento automático e os alertas só depois de tudo montado
        self.var_cpf.trace_add("write", self._ao_digitar_cpf)
        self.var_placa.trace_add("write", self._ao_digitar_placa)

    def _peca(self, chave, texto, campo, apoio=""):
        """Rótulo + campo do formulário (posicionados depois, pela GRADE)."""
        rotulo, self.apoios[chave] = rotulo_campo(self.form, texto, apoio)
        self.pecas[chave] = (rotulo, campo)
        return campo.entrada

    def _ao_redimensionar_cadastro(self, event):
        """Cadastro em tela baixa (notebook 1366x768): menos respiro."""
        if event.widget is self.aba:
            self._densidade_do_cadastro(event.height < px(ALTURA_CADASTRO))

    def _densidade_do_cadastro(self, compacta):
        self.cabecalho_cadastro.pack_configure(
            pady=_px((6, 6)) if compacta else _px((20, 16)))
        self.cartao_form.miolo.pack_configure(
            padx=px(14 if compacta else 18), pady=px(8 if compacta else 18))
        self.cab_form.pack_configure(pady=(0, px(4 if compacta else 10)))
        self.aviso_pessoa.definir_respiro(4 if compacta else 9)
        for linha in (3, 6, 8):
            self.form.grid_rowconfigure(linha, pad=px(2 if compacta else 8))
        self.secao_visita.grid_configure(
            pady=(px(2 if compacta else 10), px(2 if compacta else 8)))
        self.titulo_visita.pack_configure(pady=(px(3 if compacta else 10), 0))

    def _posicionar_formulario(self):
        n = COLUNAS_DO_FORMULARIO
        self.form.columnconfigure(tuple(range(n)), weight=1, uniform="f")
        for chave, (rotulo, campo) in self.pecas.items():
            linha, coluna, juntas = GRADE[chave]
            # quem manda na largura é a grade (colunas iguais), não o texto
            caixa = campo.texto if chave == "motivo" else campo.entrada
            caixa.config(width=1)
            rotulo.grid(row=linha, column=coluna, columnspan=juntas, sticky="ew",
                        pady=(0, px(4)),
                        padx=(0, px(12) if coluna + juntas < n else 0))
            campo.grid(row=linha + 1, column=coluna, columnspan=juntas,
                       sticky="new", pady=(0, px(8)),
                       padx=(0, px(12) if coluna + juntas < n else 0))
        for chave in GRADE:                 # o Tab segue a ordem da tela
            self.pecas[chave][1].lift()
        self.titulo_form.pack(side="left")
        self.aviso_pessoa.grid(in_=self.form, row=2, column=0,
                               columnspan=COLUNAS_DO_FORMULARIO, sticky="ew",
                               pady=(px(2), px(10)))
        # o segundo bloco: um fio e o título "Visita"
        self.secao_visita = tk.Frame(self.form, bg=COR["superficie"])
        tk.Frame(self.secao_visita, bg=COR["borda"], height=1).pack(fill="x")
        self.titulo_visita = titulo_cartao(self.secao_visita, "Visita")
        self.titulo_visita.pack(anchor="w", pady=(px(10), 0))
        self.secao_visita.grid(row=LINHA_VISITA, column=0,
                               columnspan=COLUNAS_DO_FORMULARIO, sticky="ew",
                               pady=(px(10), px(8)))
        self.linha_botoes.grid(in_=self.form, row=LINHA_BOTOES, column=0,
                               columnspan=COLUNAS_DO_FORMULARIO, sticky="w",
                               pady=(px(6), 0))
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

    def _esta_visivel(self):
        # a página fica dentro do Notebook de páginas (self.aba.master)
        return self.aba.master.select() == str(self.aba)

    # --------------------------------------------------------------
    # Registrar a entrada e limpar
    # --------------------------------------------------------------
    def cadastrar(self, event=None):
        if event is not None and not self._esta_visivel():
            return  # Enter só registra na página Cadastro
        self.acompanhar_relogio()      # Entrada intocada = o agora exato
        registro = normalizar(self.nome.get(), self.cpf.get(),
                              self.celular.get(), self.var_placa.get(),
                              self.tipo.get(), self.entrada.get(),
                              self.saida.get(), empresa=self.empresa.get(),
                              motivo=self.motivo.get(),
                              anfitriao=self.anfitriao.get(),
                              cracha=self.cracha.get())
        texto = self.registrar_entrada(registro, self._placa_sugerida(),
                                       (self._auto or {}).get("pessoa_id"),
                                       self._digitar_outro_carro)
        if texto:
            self.limpar()
            # enunciado: mensagem de confirmação depois de salvar, na tela
            # em que a pessoa está (com o código de identificação)
            self._situacao("sucesso", texto)

    def cancelar(self):
        """Botão Cancelar do Cadastro: descarta o que foi digitado e vai ao
        Controle de acesso."""
        self.limpar()
        self._situacao("neutro", DICA_CPF)
        self.app.ir_para(self.aba_controle)

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
        if placa != registro["placa"]:
            # escolheu outro carro do cadastro (RN47): ele pode estar
            # desativado (RN12)
            ok, msg = checar_desativacao(dict(registro, placa=placa), ativas)
            if not ok:
                self.registrar_recusa(dict(registro, placa=placa))
                mensagens.erro("Acesso negado", msg)
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
        ok, id_visita = self.app.tentar(
            self.app.banco.inserir, registro, autor=self.app.autor,
            autorizacao=autorizacao, **carros, **lotacao)
        if not ok:
            return None
        self.app.recarregar_registros()
        self.app.atualizar_tabela()
        hora = registro["entrada"][-5:]
        # texto do enunciado do exercício, na faixa (sem caixa para fechar);
        # é o único caminho da entrada: Pessoas › Registrar entrada, o
        # retroativo, a entrada com outro carro e o comando passam por aqui
        texto = (f"{SUCESSO_CADASTRO} Entrada de "
                 f"{registro['nome'].split()[0]} às {hora}"
                 + self._com_autorizacao(autorizacao)
                 + f" Código {codigo_da_visita(id_visita)}."
                 + (f" Crachá {registro['cracha']}."
                    if registro.get("cracha") else ""))
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
                                       self._ultima_visita_de_carro(pessoa_id),
                                       self._outros_carros(pessoa_id, sugerida))
        if resposta == OUTRO_CARRO:
            if ao_outro_carro is not None:
                ao_outro_carro()
            return None
        if resposta is None:
            return None
        if resposta not in (COM_CARRO, A_PE):
            return resposta                 # um dos outros carros (RN47)
        return sugerida if resposta == COM_CARRO else ""

    def _outros_carros(self, pessoa_id, sugerida):
        """RN47: os outros carros do cadastro que não estão no
        estacionamento (o que está lá não entra de novo)."""
        if pessoa_id is None:
            return []
        ok, placas = self.app.tentar(self.app.banco.placas_da_pessoa,
                                     pessoa_id)
        return [p for p in (placas if ok else [])
                if p != sugerida and self._carro_no_estacionamento(p) is None]

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
        self.empresa.delete(0, tk.END)
        self.motivo.delete(0, tk.END)
        self.anfitriao.delete(0, tk.END)
        self.cracha.delete(0, tk.END)
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
        estado["filtro"] = self.filtro.get()
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
        self.filtro.set(estado.get("filtro", FILTRO_TODOS))
        self.seletor_lista.selecionar(estado["lista"])
        self.var_cpf.set(estado["cpf"])
        self.atualizar_tabela()
        self.comando.restaurar(estado.get("comando"))

    def _campos_digitaveis(self):
        return {**self._campos_pessoa(), "cpf": self.var_cpf,
                "saida": self.saida, "anfitriao": self.anfitriao,
                "cracha": self.cracha}

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
                "placa": self.var_placa, "tipo": self.tipo,
                "empresa": self.empresa, "motivo": self.motivo}

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
        self._mostrar_autorizacao(cpf, pessoa)

    def _mostrar_autorizacao(self, cpf, pessoa):
        """Visitante autorizado (3.2): quem tem autorização de entrada
        válida hoje já vem com os dados dela, e a faixa diz quem autorizou.
        Pessoa desativada ou que já está dentro continua barrada."""
        ok, a = self.app.tentar(self.app.banco.autorizacao_valida, cpf)
        if not ok or a is None:
            return
        if self._auto is None:            # pessoa nova: o CPF trocado limpa
            self._auto = {"cpf": cpf, "pessoa_id": None, "campos": {},
                          "placas": []}
        automaticos = self._auto["campos"]
        campos = {"nome": self.nome, "empresa": self.empresa,
                  "motivo": self.motivo, "anfitriao": self.anfitriao}
        for chave, campo in campos.items():
            atual = campo.get().strip()
            # o motivo da última visita dá lugar ao da autorização
            troca = chave == "motivo" and atual == automaticos.get("motivo")
            if a[chave] and (not atual or troca):
                self._escrever(campo, a[chave])
                automaticos[chave] = campo.get()
        if self.aviso_pessoa.tipo in ("info", "sucesso"):
            # curta, para caber numa linha também na janela pequena
            quem = a["anfitriao"]
            if len(quem) > LIMITE_ANFITRIAO_NA_FAIXA:
                quem = quem[:LIMITE_ANFITRIAO_NA_FAIXA - 1].rstrip() + "…"
            self._situacao(
                "sucesso", f"Entrada autorizada por {quem} "
                           f"(autorização nº {a['id']:03d}).")

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
            # RN47: a placa que o CPF preencheu e a pessoa tem outros carros
            carros = len((self._auto or {}).get("placas", ()))
            self.lbl_dica_placa.config(
                text=(f"{carros} carros no cadastro"
                      if carros > 1 and placa and self._placa_sugerida()
                      else DICA_PLACA), fg=COR["texto_3"], font=FONTE["dica"])
            self.lbl_placa_status.config(text="")
            self.lbl_placa_status.pack_configure(pady=0)

    def _preencher_automatico(self, pessoa, sem_placa=False):
        # o motivo vem da última visita (o porteiro confere ou troca)
        ok, visitas = self.app.tentar(self.app.banco.visitas_da_pessoa,
                                      pessoa["id"], 1)
        pessoa = dict(pessoa, motivo=visitas[0]["motivo"] if ok and visitas
                      else "")
        preenchidos = {}
        for chave, campo in self._campos_pessoa().items():
            if chave == "placa" and sem_placa:
                continue
            if not campo.get().strip() and pessoa[chave]:
                self._escrever(campo, pessoa[chave])
                preenchidos[chave] = campo.get()
        self._auto = {"cpf": pessoa["cpf"], "pessoa_id": pessoa["id"],
                      "campos": preenchidos, "placas": pessoa["placas"]}
        self._ao_digitar_placa()

    def _desfazer_preenchimento(self):
        """CPF trocado: apaga o que foi preenchido sozinho e não foi mexido."""
        # (o "quem procura" pode ter vindo da autorização de entrada)
        campos = {**self._campos_pessoa(), "anfitriao": self.anfitriao}
        for chave, valor in self._auto["campos"].items():
            if campos[chave].get() == valor:
                self._escrever(campos[chave], "")
        self._auto = None
