"""
Regras de validação do cadastro (padrões brasileiros) e verificações semânticas.

Nada aqui depende do Tkinter: as funções recebem dados e devolvem resultados,
por isso podem ser testadas automaticamente.
"""

import re
from datetime import datetime

# ------------------------------------------------------------------
# Constantes
# ------------------------------------------------------------------
FORMATO = "%d/%m/%Y %H:%M"            # usado pelo datetime
FORMATO_EXIBICAO = "dd/mm/aaaa hh:mm"  # mostrado para o usuário
ANO_MINIMO = 2000                      # antes disso é erro de digitação
TIPOS_ACESSO = ["Aluno", "Professor", "Funcionário", "Visitante",
                "Entregador", "Prestador de serviço"]

# Mude para True se a placa também for obrigatória
PLACA_OBRIGATORIA = False

# DDDs válidos no Brasil
DDDS_VALIDOS = {
    11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28,
    31, 32, 33, 34, 35, 37, 38, 41, 42, 43, 44, 45, 46, 47, 48, 49,
    51, 53, 54, 55, 61, 62, 63, 64, 65, 66, 67, 68, 69,
    71, 73, 74, 75, 77, 79, 81, 82, 83, 84, 85, 86, 87, 88, 89,
    91, 92, 93, 94, 95, 96, 97, 98, 99,
}

# Placa antiga (ABC1234) e Mercosul (ABC1D23)
REGEX_PLACA = re.compile(r"^([A-Z]{3}[0-9]{4}|[A-Z]{3}[0-9][A-Z][0-9]{2})$")


# ------------------------------------------------------------------
# Validadores de campo
# ------------------------------------------------------------------
def so_digitos(texto):
    return re.sub(r"\D", "", texto)


def nome_valido(nome):
    """Nome e sobrenome, só com letras (acentos, hífen e apóstrofo permitidos)."""
    partes = nome.split()
    if len(partes) < 2:
        return False
    return all(p.replace("-", "").replace("'", "").isalpha() for p in partes)


def cpf_valido(cpf):
    """CPF: 11 dígitos numéricos com os dois dígitos verificadores corretos."""
    if len(cpf) != 11 or not cpf.isdigit() or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11 % 10
        if digito != int(cpf[tamanho]):
            return False
    return True


def celular_valido(cel):
    """Celular: DDD (2 dígitos) + 9 obrigatório + 8 dígitos = 11 dígitos."""
    if len(cel) != 11 or not cel.isdigit():
        return False
    if int(cel[:2]) not in DDDS_VALIDOS:
        return False
    return cel[2] == "9"


def placa_valida(placa):
    return bool(REGEX_PLACA.match(placa))


def converter_data(texto):
    """Converte 'dd/mm/aaaa hh:mm' em datetime. Retorna None se inválido."""
    try:
        return datetime.strptime(texto.strip(), FORMATO)
    except ValueError:
        return None


# ------------------------------------------------------------------
# Formatadores (para exibir na tabela)
# ------------------------------------------------------------------
def formatar_cpf(c):
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}" if len(c) == 11 else c


def mascarar_cpf(c):
    """
    CPF para o histórico e relatórios (LGPD): só os 6 dígitos do meio
    aparecem, o bastante para conferir sem expor o número inteiro.
    Aceita o CPF com ou sem pontuação: '529.982.247-25' → '***.982.247-**'.
    """
    d = so_digitos(c or "")
    return f"***.{d[3:6]}.{d[6:9]}-**" if len(d) == 11 else ("***" if d else "")


# CPF formatado (529.982.247-25) ou 11 dígitos logo depois da palavra "CPF"
_CPF_NO_TEXTO = re.compile(
    r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)|(?<=CPF )\d{11}(?!\d)")


def mascarar_cpfs_no_texto(texto):
    """Mascara os CPFs que aparecem num texto livre (detalhe do histórico).
    Celular (11 dígitos sem a palavra CPF antes) não é confundido com CPF."""
    return _CPF_NO_TEXTO.sub(lambda m: mascarar_cpf(m.group()), texto or "")


def formatar_celular(c):
    return f"({c[:2]}) {c[2:7]}-{c[7:]}" if len(c) == 11 else c


def formatar_placa(p):
    # Placa antiga ganha hífen (ABC-1234); Mercosul fica ABC1D23
    if re.match(r"^[A-Z]{3}[0-9]{4}$", p):
        return f"{p[:3]}-{p[3:]}"
    return p


# ------------------------------------------------------------------
# Registro completo
# ------------------------------------------------------------------
def normalizar(nome, cpf, celular, placa, tipo, entrada, saida):
    """Monta o registro como será salvo, a partir do texto digitado."""
    return {
        "nome": " ".join(nome.split()),
        "cpf": so_digitos(cpf),
        "celular": so_digitos(celular),
        "placa": placa.strip().upper(),
        "tipo": tipo,
        "entrada": _normalizar_data(entrada),
        "saida": _normalizar_data(saida),
    }


def _normalizar_data(texto):
    """'21/10/2026 9:5' -> '21/10/2026 09:05': a mesma hora escrita de
    outro jeito não conta como mudança (aviso e correção). Inválida fica
    como foi digitada, para validar recusar com a mensagem certa."""
    momento = converter_data(texto)
    return momento.strftime(FORMATO) if momento else texto.strip()


def _periodo(registro):
    """(entrada, saída) como datetime; saída None = ainda dentro."""
    saida = registro.get("saida")
    return (converter_data(registro["entrada"]),
            converter_data(saida) if saida else None)


def _sobrepoe(inicio_a, fim_a, inicio_b, fim_b):
    """Dois períodos se cruzam? fim None = período ainda aberto."""
    return ((fim_b is None or inicio_a < fim_b)
            and (fim_a is None or inicio_b < fim_a))


def validar_campos(registro):
    """
    Dados da pessoa: nome, CPF, celular, placa e tipo. Retorna (ok, mensagem).
    Usado no cadastro de visitas e na edição do cadastro da pessoa.
    """
    if not registro["nome"]:
        return False, "O nome da pessoa é obrigatório."
    if len(registro["nome"].split()) < 2:
        return False, "Informe o nome completo (nome e sobrenome)."
    if not nome_valido(registro["nome"]):
        return False, "O nome deve conter apenas letras."

    if not registro["cpf"]:
        return False, "O CPF é obrigatório."
    if not cpf_valido(registro["cpf"]):
        return False, "CPF inválido.\nDigite os 11 números (somente números)."

    if not registro["celular"]:
        return False, "O celular é obrigatório."
    if not celular_valido(registro["celular"]):
        return False, ("Celular inválido.\nUse DDD + 9 + 8 dígitos "
                       "(ex.: 31 9 1234 5678, somente números).")

    if registro["placa"]:
        if not placa_valida(registro["placa"]):
            return False, ("Placa inválida.\nUse o formato antigo (ABC1234) "
                           "ou Mercosul (ABC1D23).")
    elif PLACA_OBRIGATORIA:
        return False, "A placa do veículo é obrigatória."

    if registro["tipo"] not in TIPOS_ACESSO:  # VERIFICAÇÃO SEMÂNTICA 1
        return False, "Selecione um tipo de acesso válido."
    return True, ""


# ------------------------------------------------------------------
# Lista de bloqueio (RN12: CPF ou placa bloqueados não entram)
# ------------------------------------------------------------------
TIPOS_BLOQUEIO = {"cpf": "CPF", "placa": "Placa"}
MOTIVO_MINIMO = 5
# concordância nas mensagens: "o CPF ... bloqueado" / "a placa ... bloqueada"
COM_ARTIGO = {"cpf": "o CPF", "placa": "a placa"}
COM_DE = {"cpf": "do CPF", "placa": "da placa"}
BLOQUEADO = {"cpf": "bloqueado", "placa": "bloqueada"}


def normalizar_bloqueio(tipo, valor):
    """CPF só com números; placa maiúscula, sem hífen nem espaços."""
    if tipo == "cpf":
        return so_digitos(valor)
    return re.sub(r"[\s\-]", "", valor).upper()


def formatar_bloqueio(tipo, valor):
    return formatar_cpf(valor) if tipo == "cpf" else formatar_placa(valor)


def validar_bloqueio(tipo, valor, motivo, ativos):
    """Retorna (ok, mensagem) para criar um bloqueio. `valor` já normalizado."""
    if tipo not in TIPOS_BLOQUEIO:
        return False, "Escolha se o bloqueio é de CPF ou de placa."
    if tipo == "cpf" and not cpf_valido(valor):
        return False, "CPF inválido.\nDigite os 11 números."
    if tipo == "placa" and not placa_valida(valor):
        return False, "Placa inválida.\nUse ABC1234 ou ABC1D23."
    if len(motivo.strip()) < MOTIVO_MINIMO:
        return False, ("Informe o motivo do bloqueio "
                       f"(pelo menos {MOTIVO_MINIMO} caracteres).")
    if any(b["tipo"] == tipo and b["valor"] == valor for b in ativos):
        esse = "Este CPF" if tipo == "cpf" else "Esta placa"
        return False, f"{esse} já está {BLOQUEADO[tipo]}."
    return True, ""


def bloqueios_do_registro(registro, ativos):
    """Bloqueios ativos que pegam o CPF ou a placa deste registro."""
    return [b for b in ativos
            if (b["tipo"] == "cpf" and b["valor"] == registro.get("cpf"))
            or (b["tipo"] == "placa" and registro.get("placa")
                and b["valor"] == registro["placa"])]


def checar_bloqueio(registro, ativos):  # VERIFICAÇÃO SEMÂNTICA 5
    """Retorna (ok, mensagem): a entrada é recusada se houver bloqueio."""
    achados = bloqueios_do_registro(registro, ativos)
    if not achados:
        return True, ""
    linhas = [f"{TIPOS_BLOQUEIO[b['tipo']]} "
              f"{formatar_bloqueio(b['tipo'], b['valor'])} "
              f"{BLOQUEADO[b['tipo']]} em "
              f"{b['criado_em']} por {b['criado_por']}.\nMotivo: {b['motivo']}"
              for b in achados]
    return False, ("Acesso negado.\n\n" + "\n\n".join(linhas) +
                   "\n\nSó um administrador pode remover o bloqueio.")


def checar_bloqueio_correcao(original, novo, ativos):
    """
    Correção de registro (RN12): recusa se a mudança coloca um CPF ou placa
    bloqueados no campus — trocar para um CPF/placa bloqueado ou reabrir a
    visita (apagar a saída). Corrigir o nome de uma visita encerrada de
    alguém bloqueado depois continua permitido.
    """
    trocou = (novo["cpf"] != original["cpf"]
              or novo.get("placa", "") != original.get("placa", ""))
    reabriu = not novo["saida"] and bool(original["saida"])
    if not (trocou or reabriu):
        return True, ""
    return checar_bloqueio(novo, ativos)


def checar_saida(registro, agora=None):
    """Pode registrar a saída agora? Retorna (ok, mensagem)."""
    agora = agora or datetime.now()
    if registro["saida"]:
        return False, f"{registro['nome']} já tem a saída registrada."
    entrada_dt = converter_data(registro["entrada"])
    if entrada_dt is None or agora < entrada_dt:  # RN04
        return False, "A saída não pode ser anterior à entrada."
    return True, ""


def validar(registro, registros, agora=None):
    """
    Retorna (ok, mensagem). `registro` vem de normalizar(); `registros` são
    os já salvos. Contém as verificações semânticas do sistema.
    """
    agora = agora or datetime.now()

    ok, msg = validar_campos(registro)
    if not ok:
        return ok, msg

    entrada_dt = converter_data(registro["entrada"])
    if entrada_dt is None:
        return False, (f"Data/hora de entrada inválida.\n"
                       f"Use o formato {FORMATO_EXIBICAO}.")
    if entrada_dt > agora:  # VERIFICAÇÃO SEMÂNTICA 2
        return False, "A entrada não pode estar no futuro."
    if entrada_dt.year < ANO_MINIMO:
        return False, f"Confira o ano da entrada (antes de {ANO_MINIMO})."

    saida_dt = None
    if registro["saida"]:
        saida_dt = converter_data(registro["saida"])
        if saida_dt is None:
            return False, (f"Data/hora de saída inválida.\n"
                           f"Use o formato {FORMATO_EXIBICAO}.")
        if saida_dt < entrada_dt:  # VERIFICAÇÃO SEMÂNTICA 3
            return False, "A saída não pode ser anterior à entrada."
        if saida_dt > agora:
            return False, "A saída não pode estar no futuro."

    # VERIFICAÇÃO SEMÂNTICA 4: a mesma pessoa não pode estar no campus duas
    # vezes ao mesmo tempo (entrada aberta ou períodos que se cruzam)
    for r in registros:
        if r.get("cpf") != registro["cpf"]:
            continue
        inicio_r, fim_r = _periodo(r)
        if inicio_r is None:
            continue
        if not _sobrepoe(entrada_dt, saida_dt, inicio_r, fim_r):
            continue
        if fim_r is None:
            return False, ("Este CPF já possui uma entrada sem saída "
                           f"(desde {r['entrada']}).\n"
                           "Registre a saída antes de uma nova entrada.")
        return False, ("Este CPF já tem um registro nesse período "
                       f"({r['entrada']} a {r['saida']}).")
    return True, ""
