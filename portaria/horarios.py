"""
Regras de horário de acesso (RN16 a RN24): funcionamento do campus por dia
da semana, feriados, eventos, janela de entrada, permanência máxima e
tolerância de cada categoria, limite geral de 24 h, lançamento retroativo
e a situação de cada visita aberta (no campus, tempo excedido, saída
pendente).

Como validacao.py, tudo aqui é função pura: recebe a configuração e o
momento ("agora" é sempre um parâmetro — o relógio é injetado) e devolve
um resultado. Nada aqui lê o relógio do computador, o banco ou a tela.

Verificação semântica: validacao.validar diz se a entrada está BEM
ESCRITA (a data existe, não está no futuro, o CPF não está dentro duas
vezes); excecoes_da_entrada diz se ela FAZ SENTIDO para aquela categoria
naquele dia. "Aluno entrando domingo às 10:00" é uma entrada válida, mas
não faz sentido: vira uma EXCEÇÃO, que só passa com autorização do
administrador.

Como cada categoria é descrita (RegraCategoria):
- janela "do funcionamento" (relativa = True): a entrada vale de
  (abertura − abre_antes) até (fechamento + fecha_depois) minutos.
  fecha_depois é 0 (até o fechamento) ou negativo, o corte de entrada: o
  aluno tem −30, ou seja, só entra até 30 min antes de fechar;
- janela "fixa" (relativa = False): das horas `janela.abre` às
  `janela.fecha`, e só em dia em que o campus abre;
- RN23: NINGUÉM entra depois do fechamento sem autorização. Qualquer
  janela termina, no máximo, no fechamento do dia (um visitante às 16:00
  de sábado, com o campus fechando às 14:00, é exceção);
- permanência: `permanencia_min` minutos depois da entrada ou, com
  ate_fechamento = True, até o fechamento + `permanencia_min`. Passou
  dela, a visita fica "Tempo excedido" (só um alerta);
- tolerância (RN22): `tolerancia_min` minutos depois do fechamento até a
  visita aberta virar "Saída pendente" (padrão: 30 para professor e
  funcionário, 0 para os outros).

Lançamento retroativo (RN24): uma data/hora no passado (entrada ou saída)
  a) até `horas_retroativo` (3 h) atrás, com o fechamento daquele dia
     ainda por vir: normal;
  b) mais antiga que isso: exceção, com autorização do administrador;
  c) de um dia que JÁ FECHOU (ex.: 23:10 lançando 22:00, ou lançando
     ontem): exceção que só passa com a SENHA de um administrador, mesmo
     com o administrador logado.
Até MINUTOS_TOLERANCIA_AGORA (5) minutos no passado ainda conta como
"agora": quem digita 10:00 às 10:03 não está lançando nada retroativo.
"""

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from .validacao import FORMATO, converter_data

DIAS_SEMANA = ["Segunda-feira", "Terça-feira", "Quarta-feira",
               "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
LIMITE_VISITA_HORAS = 24          # regra geral: nenhuma visita passa disso
MINUTOS_AVISO_PADRAO = 30         # aviso antes de fechar
HORAS_RETROATIVO_PADRAO = 3       # lançamento mais antigo que isso é exceção
MINUTOS_TOLERANCIA_AGORA = 5      # até isso no passado ainda é "agora"
TOLERANCIA_PADRAO = 30            # professor e funcionário, depois de fechar
MINIMO_JUSTIFICATIVA = 10         # caracteres da justificativa da exceção
LIMITE_MINUTOS = 24 * 60          # nenhum ajuste passa de um dia
MAXIMO_MINUTOS_AVISO = 180        # 0 = sem aviso antes de fechar
MAXIMO_HORAS_RETROATIVO = 72
MAXIMO_TOLERANCIA = 240           # minutos depois do fechamento
FORMATO_HORA = "%H:%M"
FORMATO_DATA = "%d/%m/%Y"
_REGEX_HORA = re.compile(r"^\d{2}:\d{2}$")

# Situação de uma visita na tabela Movimento
NO_CAMPUS = "No campus"
TEMPO_EXCEDIDO = "Tempo excedido"
SAIDA_PENDENTE = "Saída pendente"
SAIU = "Saiu"


@dataclass(frozen=True)
class Horario:
    """Das `abre` às `fecha` no mesmo dia (fecha > abre)."""
    abre: time
    fecha: time

    def __str__(self):
        return f"{self.abre:%H:%M}–{self.fecha:%H:%M}"


@dataclass(frozen=True)
class Evento:
    """Data com horário especial: substitui o funcionamento do dia,
    mesmo num domingo ou feriado."""
    data: date
    horario: Horario
    descricao: str


@dataclass(frozen=True)
class RegraCategoria:
    relativa: bool                 # True: janela do funcionamento; False: fixa
    abre_antes: int = 0            # (relativa) minutos antes de abrir
    fecha_depois: int = 0          # (relativa) 0 = até fechar; −30 = corte
    janela: Horario | None = None  # (fixa) ex.: 08:00–18:00
    ate_fechamento: bool = False   # permanência até o fechamento + permanencia_min
    permanencia_min: int = 0
    tolerancia_min: int = 0        # depois do fechamento, até a saída pendente


@dataclass
class Configuracao:
    funcionamento: dict            # 0 (segunda) .. 6 (domingo) -> Horario | None
    regras: dict                   # tipo de acesso -> RegraCategoria
    feriados: dict = field(default_factory=dict)   # date -> descrição
    eventos: dict = field(default_factory=dict)    # date -> Evento
    minutos_aviso: int = MINUTOS_AVISO_PADRAO
    horas_retroativo: int = HORAS_RETROATIVO_PADRAO


@dataclass(frozen=True)
class Expediente:
    """O campus aberto num dia: abre, fecha (datetime) e de onde veio."""
    abre: datetime
    fecha: datetime
    origem: str                    # "funcionamento" ou "Evento: <descrição>"


def hora(texto):
    """'07:30' -> time(7, 30)."""
    return datetime.strptime(texto, FORMATO_HORA).time()


def configuracao_padrao():
    """Os horários decididos para o campus (todos editáveis pelo admin)."""
    semana = Horario(hora("06:30"), hora("23:00"))
    funcionamento = {dia: semana for dia in range(5)}
    funcionamento[5] = Horario(hora("07:00"), hora("14:00"))
    funcionamento[6] = None                                    # domingo
    regras = {
        "Aluno": RegraCategoria(True, 0, -30, ate_fechamento=True),
        "Professor": RegraCategoria(True, 30, 0, ate_fechamento=True,
                                    tolerancia_min=TOLERANCIA_PADRAO),
        "Funcionário": RegraCategoria(True, 60, 0, permanencia_min=12 * 60,
                                      tolerancia_min=TOLERANCIA_PADRAO),
        "Visitante": RegraCategoria(False, janela=Horario(hora("08:00"), hora("18:00")),
                                    permanencia_min=4 * 60),
        "Entregador": RegraCategoria(False, janela=Horario(hora("07:00"), hora("17:00")),
                                     permanencia_min=60),
        "Prestador de serviço": RegraCategoria(
            False, janela=Horario(hora("07:00"), hora("19:00")),
            permanencia_min=10 * 60),
    }
    return Configuracao(funcionamento, regras)


# ------------------------------------------------------------------
# O campus num dia
# ------------------------------------------------------------------
def expediente(config, dia):
    """Horário do campus no dia (Expediente) ou None se fechado.
    O evento vale mais que tudo; depois o feriado; depois a semana."""
    evento = config.eventos.get(dia)
    if evento is not None:
        return _no_dia(dia, evento.horario, f"Evento: {evento.descricao}")
    if dia in config.feriados:
        return None
    horario = config.funcionamento.get(dia.weekday())
    return _no_dia(dia, horario, "funcionamento") if horario else None


def _no_dia(dia, horario, origem):
    return Expediente(datetime.combine(dia, horario.abre),
                      datetime.combine(dia, horario.fecha), origem)


def motivo_fechado(config, dia):
    """Por que o campus está fechado no dia: 'feriado: Natal', 'domingo'."""
    if dia in config.feriados:
        return f"feriado: {config.feriados[dia]}"
    return DIAS_SEMANA[dia.weekday()].lower()


def janela_entrada(config, tipo, dia):
    """(início, fim) em que a categoria pode entrar no dia, ou None se o
    campus não abre. Sem regra para o tipo: o dia inteiro. Nenhuma janela
    passa do fechamento (RN23: depois de fechar, só com autorização)."""
    aberto = expediente(config, dia)
    if aberto is None:
        return None
    regra = config.regras.get(tipo)
    if regra is None:
        meia_noite = datetime.combine(dia, time())
        return meia_noite, meia_noite + timedelta(days=1)
    if regra.relativa:
        inicio = aberto.abre - timedelta(minutes=regra.abre_antes)
        fim = aberto.fecha + timedelta(minutes=regra.fecha_depois)
    else:
        inicio = datetime.combine(dia, regra.janela.abre)
        fim = datetime.combine(dia, regra.janela.fecha)
    return inicio, min(fim, aberto.fecha)


def entrada_permitida(config, tipo, entrada):
    """A entrada cai na janela da categoria? Olha também a janela do dia
    anterior e a do seguinte (ex.: funcionário que entra 60 min antes de
    um campus que abre à meia-noite e meia)."""
    for desvio in (-1, 0, 1):
        janela = janela_entrada(config, tipo, entrada.date() + timedelta(days=desvio))
        if janela and janela[0] <= entrada <= janela[1]:
            return True
    return False


# ------------------------------------------------------------------
# Exceções (VERIFICAÇÃO SEMÂNTICA 6): o que pede autorização do admin
# ------------------------------------------------------------------
@dataclass
class Excecoes:
    """Regras violadas (textos) e se a autorização só vale com a SENHA de
    um administrador (lançamento num dia que já fechou, RN24 c)."""
    regras: list = field(default_factory=list)
    so_com_senha: bool = False

    def __bool__(self):
        return bool(self.regras)

    def juntar(self, outras):
        self.regras += outras.regras
        self.so_com_senha = self.so_com_senha or outras.so_com_senha
        return self


def retroativo(config, rotulo, momento, agora):
    """
    RN24: lançamento de `momento` (entrada ou saída) visto do `agora`.
    Até MINUTOS_TOLERANCIA_AGORA no passado é "agora" (nada a autorizar);
    num dia que já fechou, só com a senha de um administrador; mais antigo
    que o limite de horas, com autorização. Devolve Excecoes.
    """
    atraso = agora - momento
    if atraso <= timedelta(minutes=MINUTOS_TOLERANCIA_AGORA):
        return Excecoes()
    fechou = fechamento_do_dia(config, momento)
    if agora > fechou:
        return Excecoes([f"{rotulo} retroativa: {momento:{FORMATO}} é de um "
                         f"dia já encerrado (fechou {_quando_fechou(fechou)})."
                         " Só com a senha de um administrador."], True)
    if atraso > timedelta(hours=config.horas_retroativo):
        return Excecoes([f"{rotulo} retroativa: {momento:{FORMATO}} é de mais "
                         f"de {config.horas_retroativo} h atrás."])
    return Excecoes()


def _quando_fechou(fechou):
    if fechou.time() == time():
        return f"à meia-noite de {fechou - timedelta(days=1):{FORMATO_DATA}}"
    return f"às {fechou:%H:%M} de {fechou:{FORMATO_DATA}}"


def excecoes_da_entrada(config, tipo, entrada, agora):
    """Regras que a entrada (datetime) viola: lançamento retroativo e fora
    da janela da categoria (inclusive campus fechado). Vazio = normal."""
    excecoes = retroativo(config, "Entrada", entrada, agora)
    if not entrada_permitida(config, tipo, entrada):
        excecoes.regras.append(_fora_da_janela(config, tipo, entrada))
    return excecoes


def _fora_da_janela(config, tipo, entrada):
    dia = entrada.date()
    janela = janela_entrada(config, tipo, dia)
    if janela is None:
        return (f"Campus fechado em {dia:{FORMATO_DATA}} "
                f"({motivo_fechado(config, dia)}).")
    return (f"{tipo}: entrada às {entrada:%H:%M} fora do horário permitido "
            f"({janela[0]:%H:%M}–{janela[1]:%H:%M}).")


def excecoes_da_duracao(entrada, saida):
    """Regra geral: nenhuma visita passa de LIMITE_VISITA_HORAS."""
    if saida - entrada <= timedelta(hours=LIMITE_VISITA_HORAS):
        return []
    horas = (saida - entrada) / timedelta(hours=1)
    return [f"Visita de {formatar_horas(horas)} (o máximo é "
            f"{LIMITE_VISITA_HORAS} h)."]


def formatar_horas(horas):
    """30.0 -> '30 h'; 25.5 -> '25 h 30 min'."""
    inteiras, minutos = divmod(round(horas * 60), 60)
    if not inteiras:
        return f"{minutos} min"
    return f"{inteiras} h" + (f" {minutos:02d} min" if minutos else "")


def excecoes_do_registro(config, registro, agora):
    """Exceções de um registro novo (datas no formato da tela)."""
    entrada = converter_data(registro["entrada"])
    excecoes = excecoes_da_entrada(config, registro["tipo"], entrada, agora)
    if registro.get("saida"):
        saida = converter_data(registro["saida"])
        excecoes.juntar(retroativo(config, "Saída", saida, agora))
        excecoes.regras += excecoes_da_duracao(entrada, saida)
    return excecoes


def excecoes_da_correcao(config, original, novo, agora):
    """
    Exceções de uma correção: só o que MUDOU é conferido de novo (corrigir
    o nome de uma visita que já foi exceção não pede outra autorização).
    - entrada mudou: retroativa e janela;
    - só o tipo mudou: janela;
    - saída mudou: retroativa;
    - entrada ou saída mudou e há saída: limite de 24 h.
    """
    entrada = converter_data(novo["entrada"])
    mudou_entrada = novo["entrada"] != original["entrada"]
    mudou_saida = novo["saida"] != original["saida"]
    excecoes = Excecoes()
    if mudou_entrada:
        excecoes = excecoes_da_entrada(config, novo["tipo"], entrada, agora)
    elif novo["tipo"] != original["tipo"] and not entrada_permitida(
            config, novo["tipo"], entrada):
        excecoes.regras.append(_fora_da_janela(config, novo["tipo"], entrada))
    if novo["saida"] and mudou_saida:
        excecoes.juntar(retroativo(config, "Saída",
                                   converter_data(novo["saida"]), agora))
    if novo["saida"] and (mudou_entrada or mudou_saida):
        excecoes.regras += excecoes_da_duracao(entrada,
                                               converter_data(novo["saida"]))
    return excecoes


# ------------------------------------------------------------------
# Permanência, saída pendente e situação da visita
# ------------------------------------------------------------------
def fechamento_do_dia(config, momento):
    """Fechamento do dia de `momento` (23:00 de segunda a sexta, ou o fim
    do evento). Dia sem expediente (domingo, feriado): a meia-noite."""
    aberto = expediente(config, momento.date())
    if aberto is None:
        return datetime.combine(momento.date() + timedelta(days=1), time())
    return aberto.fecha


def limite_permanencia(config, tipo, entrada):
    """Até quando a categoria pode ficar (nunca mais que 24 h)."""
    teto = entrada + timedelta(hours=LIMITE_VISITA_HORAS)
    regra = config.regras.get(tipo)
    if regra is None:
        return teto
    base = fechamento_do_dia(config, entrada) if regra.ate_fechamento else entrada
    return min(base + timedelta(minutes=regra.permanencia_min), teto)


def prazo_saida(config, tipo, entrada):
    """
    RN22: até quando a visita pode ficar aberta sem virar "Saída
    pendente": o fechamento do dia da entrada (23:00 de segunda a sexta,
    ou o fim do evento) + a tolerância da categoria (30 min para professor
    e funcionário, 0 para os outros). Nunca passa de 24 h.
    Entrada DEPOIS desse prazo (só com autorização): o prazo é a própria
    entrada, ou seja, a visita já nasce pendente, porque o dia dela acabou.
    É também o horário da saída automática do "Encerrar o dia".
    """
    regra = config.regras.get(tipo)
    tolerancia = timedelta(minutes=regra.tolerancia_min if regra else 0)
    prazo = max(fechamento_do_dia(config, entrada) + tolerancia, entrada)
    return min(prazo, entrada + timedelta(hours=LIMITE_VISITA_HORAS))


def situacao(config, registro, agora):
    """
    Situação da visita (registro com datas no formato da tela), calculada
    com o relógio: não depende de o programa estar aberto no fechamento.
    """
    if registro["saida"]:
        return SAIU
    entrada = converter_data(registro["entrada"])
    if agora > prazo_saida(config, registro["tipo"], entrada):
        return SAIDA_PENDENTE
    if agora > limite_permanencia(config, registro["tipo"], entrada):
        return TEMPO_EXCEDIDO
    return NO_CAMPUS


def contar_situacoes(config, registros, agora):
    """{situação: quantidade} das visitas abertas."""
    contagem = {NO_CAMPUS: 0, TEMPO_EXCEDIDO: 0, SAIDA_PENDENTE: 0}
    for r in registros:
        if not r["saida"]:
            contagem[situacao(config, r, agora)] += 1
    return contagem


def minutos_para_fechar(config, agora):
    """Minutos até o fechamento de hoje, se faltam no máximo
    `config.minutos_aviso` (com o campus aberto); senão None."""
    aberto = expediente(config, agora.date())
    if aberto is None or not aberto.abre <= agora < aberto.fecha:
        return None
    faltam = math.ceil((aberto.fecha - agora) / timedelta(minutes=1))
    return faltam if faltam <= config.minutos_aviso else None


# ------------------------------------------------------------------
# Validação do que o administrador digita na página Configurações.
# Cada função devolve (valor, "") ou (None, mensagem de erro).
# ------------------------------------------------------------------
def ler_hora(texto, rotulo):
    texto = texto.strip()
    if _REGEX_HORA.match(texto):
        try:
            return hora(texto), ""
        except ValueError:
            pass
    return None, f"{rotulo}: horário inválido. Use hh:mm (ex.: 07:30)."


def ler_horario(abre, fecha, rotulo):
    """Dois textos hh:mm -> Horario, com fecha depois de abre."""
    inicio, erro = ler_hora(abre, rotulo)
    if erro:
        return None, erro
    fim, erro = ler_hora(fecha, rotulo)
    if erro:
        return None, erro
    if fim <= inicio:
        return None, f"{rotulo}: o fechamento precisa ser depois da abertura."
    return Horario(inicio, fim), ""


def ler_numero(texto, rotulo, minimo, maximo, unidade):
    """Número inteiro (aceita o sinal de menos tipográfico) entre os limites."""
    texto = texto.strip().replace("−", "-")
    try:
        valor = int(texto)
    except ValueError:
        return None, f"{rotulo}: digite um número inteiro de {unidade}."
    if not minimo <= valor <= maximo:
        return None, f"{rotulo}: use de {minimo} a {maximo} {unidade}."
    return valor, ""


def ler_minutos(texto, rotulo, minimo=0, maximo=LIMITE_MINUTOS):
    return ler_numero(texto, rotulo, minimo, maximo, "minutos")


def ler_parametros(minutos_aviso, horas_retroativo):
    """(minutos do aviso antes de fechar, horas do limite de retroativo)."""
    minutos, erro = ler_numero(minutos_aviso, "Aviso antes de fechar", 0,
                               MAXIMO_MINUTOS_AVISO, "minutos")
    if erro:
        return None, erro
    horas, erro = ler_numero(horas_retroativo, "Lançamento retroativo", 1,
                             MAXIMO_HORAS_RETROATIVO, "horas")
    if erro:
        return None, erro
    return (minutos, horas), ""


def ler_funcionamento(linhas):
    """linhas: 7 x (aberto, abre, fecha) de segunda a domingo."""
    funcionamento = {}
    for dia, (aberto, abre, fecha) in enumerate(linhas):
        if not aberto:
            funcionamento[dia] = None
            continue
        horario, erro = ler_horario(abre, fecha, DIAS_SEMANA[dia])
        if erro:
            return None, erro
        funcionamento[dia] = horario
    return funcionamento, ""


def ler_regra(tipo, relativa, de, ate, ate_fechamento, permanencia,
              tolerancia="0"):
    """Uma linha da tabela de categorias. Na janela do funcionamento,
    `de` e `ate` são minutos; na fixa, horários hh:mm. `ate` nunca passa
    do fechamento (RN23): 0 = até fechar, negativo = antes."""
    if relativa:
        abre_antes, erro = ler_minutos(de, f"{tipo} (antes de abrir)")
        if erro:
            return None, erro
        fecha_depois, erro = ler_minutos(ate, f"{tipo} (até)",
                                         minimo=-LIMITE_MINUTOS, maximo=0)
        if erro:
            return None, erro + " Ninguém entra depois de fechar."
        janela = None
    else:
        abre_antes = fecha_depois = 0
        janela, erro = ler_horario(de, ate, f"{tipo} (janela de entrada)")
        if erro:
            return None, erro
    minutos, erro = ler_minutos(permanencia, f"{tipo} (permanência)",
                                minimo=0 if ate_fechamento else 1)
    if erro:
        return None, erro
    tolerancia, erro = ler_minutos(tolerancia, f"{tipo} (tolerância)",
                                   maximo=MAXIMO_TOLERANCIA)
    if erro:
        return None, erro
    return RegraCategoria(relativa, abre_antes, fecha_depois, janela,
                          ate_fechamento, minutos, tolerancia), ""


def ler_data(texto, rotulo="Data"):
    try:
        return datetime.strptime(texto.strip(), FORMATO_DATA).date(), ""
    except ValueError:
        return None, f"{rotulo} inválida. Use dd/mm/aaaa."


def ler_feriado(data, descricao, config):
    dia, erro = ler_data(data)
    if erro:
        return None, erro
    if len(descricao.strip()) < 3:
        return None, "Informe o nome do feriado (ex.: Natal)."
    if dia in config.feriados:
        return None, f"{dia:{FORMATO_DATA}} já é feriado."
    return (dia, descricao.strip()), ""


def ler_evento(data, abre, fecha, descricao, config):
    dia, erro = ler_data(data)
    if erro:
        return None, erro
    horario, erro = ler_horario(abre, fecha, "Horário do evento")
    if erro:
        return None, erro
    if len(descricao.strip()) < 3:
        return None, "Descreva o evento (ex.: Formatura de Direito)."
    if dia in config.eventos:
        return None, f"Já há um evento em {dia:{FORMATO_DATA}}."
    return Evento(dia, horario, descricao.strip()), ""


# ------------------------------------------------------------------
# Textos (tela e histórico)
# ------------------------------------------------------------------
def descrever_horario(horario):
    return str(horario) if horario else "fechado"


def descrever_regra(tipo, regra):
    """Uma frase com a regra: 'Aluno: entrada de 06:30 até 30 min antes
    de fechar; fica até o fechamento'."""
    if regra.relativa:
        antes = f"{regra.abre_antes} min antes de abrir" if regra.abre_antes else "a abertura"
        if regra.fecha_depois < 0:
            depois = f"{-regra.fecha_depois} min antes de fechar"
        else:
            depois = "o fechamento"
        janela = f"entrada desde {antes} até {depois}"
    else:
        janela = f"entrada das {regra.janela.abre:%H:%M} às {regra.janela.fecha:%H:%M}"
    if regra.ate_fechamento:
        fica = "fica até o fechamento" + (
            f" + {formatar_horas(regra.permanencia_min / 60)}"
            if regra.permanencia_min else "")
    else:
        fica = f"fica no máximo {formatar_horas(regra.permanencia_min / 60)}"
    if regra.tolerancia_min:
        fica += f"; tolerância de {regra.tolerancia_min} min depois de fechar"
    return f"{tipo}: {janela}; {fica}"
