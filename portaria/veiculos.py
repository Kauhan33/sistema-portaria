"""
Regras do veículo da versão 2.2 (funções puras, como validacao.py e
horarios.py: nada aqui lê o relógio, o banco ou a tela).

RN35 — pessoas autorizadas a retirar o veículo. O carro sai sem o dono e
SEM a senha do administrador quando quem leva:
  - está na lista de autorizados DAQUELA placa;
  - com a autorização ativa e dentro da validade (sem data = até alguém
    remover; com data, vale até o fim daquele dia);
  - está no campus, entrou a pé (a visita dela não tem placa) e sai agora;
  - não tem bloqueio de CPF.
Nos demais casos continua valendo a RN32 (só com a senha). Quem cadastra:
o porteiro, só com o dono presente (visita aberta do dono no campus); o
administrador, a qualquer hora. Remover só diminui a permissão: qualquer
usuário remove (remoção lógica, com histórico).

RN37 — lotação do estacionamento: com `vagas` > 0 (0 = sem controle, até
4 dígitos), o cabeçalho mostra "Estacionamento 47/50". A entrada de carro
com o estacionamento lotado AVISA e pede a confirmação do porteiro; com
"Bloquear quando lotado" ligado, só com a senha do administrador.
"""

from datetime import date, datetime

from .validacao import (MAXIMO_DATA, MAXIMO_NOME, checar_tamanho, cpf_valido,
                        nome_valido, placa_valida)

FORMATO_DIA = "%d/%m/%Y"
MAXIMO_VAGAS = 9999              # 4 dígitos (RN37)
DONO_PRECISA_ESTAR = ("O dono precisa estar no campus: o porteiro só cadastra "
                      "quem pode retirar o carro com o dono presente.")
SEM_PRAZO = "sem prazo (até remover)"


def pode_cadastrar_autorizado(admin, dono_no_campus):
    """(ok, motivo): o administrador cadastra a qualquer hora; o porteiro,
    só com o dono no campus naquele momento."""
    if admin or dono_no_campus:
        return True, ""
    return False, DONO_PRECISA_ESTAR


def conferir_autorizado(placa, dono_cpf, cpf, nome, valido_ate, hoje):
    """
    (ok, motivo) dos dados já lidos (valido_ate: date ou None). Conferido
    na tela e de novo no banco.
    """
    if not placa_valida(placa or ""):
        return False, "O dono não tem veículo cadastrado (placa)."
    if not cpf_valido(cpf or ""):
        return False, "CPF inválido: confira os números de quem vai retirar."
    if cpf == dono_cpf:
        return False, "O dono já pode sair com o próprio carro."
    ok, msg = checar_tamanho("Nome completo", nome or "", MAXIMO_NOME)
    if not ok:
        return False, msg
    if not nome_valido(nome or ""):
        return False, "Informe o nome completo de quem vai retirar (só letras)."
    if valido_ate is not None and valido_ate < hoje:
        return False, "A validade não pode ser antes de hoje."
    return True, ""


def ler_validade(texto):
    """'' -> None (sem prazo); 'dd/mm/aaaa' -> date. (valor, erro)."""
    texto = (texto or "").strip()
    if not texto:
        return None, ""
    ok, msg = checar_tamanho("Válido até", texto, MAXIMO_DATA)
    if not ok:
        return None, msg
    try:
        return datetime.strptime(texto, FORMATO_DIA).date(), ""
    except ValueError:
        return None, "Válido até: data inválida. Use dd/mm/aaaa ou deixe vazio."


def validar_autorizado(dono, cpf, nome, validade, hoje):
    """
    Formulário "Quem pode retirar" da ficha da pessoa. `dono`: a pessoa da
    ficha (cpf, placa). Devolve (dados, "") com placa, dono_cpf, cpf, nome
    e valido_ate (date ou None), ou (None, motivo).
    """
    nome = " ".join((nome or "").split())
    valido_ate, erro = ler_validade(validade)
    if erro:
        return None, erro
    ok, msg = conferir_autorizado(dono.get("placa", ""), dono["cpf"], cpf,
                                  nome, valido_ate, hoje)
    if not ok:
        return None, msg
    return {"placa": dono["placa"], "dono_cpf": dono["cpf"], "cpf": cpf,
            "nome": nome, "valido_ate": valido_ate}, ""


def autorizacao_vale(autorizado, dia):
    """Ativa e dentro da validade no dia `dia` (date)."""
    if not autorizado.get("ativo", True):
        return False
    fim = autorizado.get("valido_ate")
    return fim is None or dia <= fim


def pode_levar(autorizado, dia, visita_a_pe, cpf_bloqueado):
    """
    RN35: (ok, motivo) de quem sai do campus agora levar o carro da placa
    autorizada sem o dono e sem senha. `autorizado`: a linha da lista
    (ou None se a pessoa não está na lista daquela placa).
    """
    if autorizado is None:
        return False, "não está na lista de quem pode retirar este carro"
    if not autorizado.get("ativo", True):
        return False, "a autorização foi removida"
    if not autorizacao_vale(autorizado, dia):
        return False, "a autorização venceu"
    if not visita_a_pe:
        return False, "entrou com outro veículo"
    if cpf_bloqueado:
        return False, "o CPF está bloqueado"
    return True, ""


def descrever_validade(valido_ate):
    """None -> 'sem prazo (até remover)'; date -> 'até 31/12/2026'."""
    if valido_ate is None:
        return SEM_PRAZO
    return f"até {valido_ate:{FORMATO_DIA}}"


def dia_iso(valor):
    """date ou None -> 'AAAA-MM-DD' ou '' (como fica no banco)."""
    return valor.isoformat() if isinstance(valor, date) else ""


def dia_do_banco(texto):
    """'AAAA-MM-DD' ou '' -> date ou None."""
    return date.fromisoformat(texto) if texto else None


# ------------------------------------------------------------------
# Lotação do estacionamento (RN37)
# ------------------------------------------------------------------
def esta_lotado(ocupadas, vagas):
    """Com controle (vagas > 0), lotado quando os carros no estacionamento
    chegam ao número de vagas (50/50 já é lotado)."""
    return vagas > 0 and ocupadas >= vagas


def texto_lotacao(ocupadas, vagas):
    """'Estacionamento 47/50' para o cabeçalho; '' sem controle."""
    return f"Estacionamento {ocupadas}/{vagas}" if vagas > 0 else ""


def regra_lotado(ocupadas, vagas):
    """'Estacionamento lotado (50/50)'."""
    return f"Estacionamento lotado ({ocupadas}/{vagas})"


def ler_vagas(texto):
    """Campo "Vagas" de Configurações: (número, "") ou (None, erro)."""
    texto = (texto or "").strip()
    if not texto.isdigit() or len(texto) > len(str(MAXIMO_VAGAS)):
        return None, (f"Vagas do estacionamento: digite um número de 0 a "
                      f"{MAXIMO_VAGAS} (0 = sem controle).")
    return int(texto), ""
