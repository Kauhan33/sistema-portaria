"""
Relatório de exceções (V4, Usuários › Exceções): tudo o que passou por
cima de uma regra num período — horário, retroativo, mais de 24 h, veículo
sem o dono, veículo com autorizado (RN35), estacionamento lotado liberado
com a senha (RN37), saídas automáticas e código de recuperação usado
(RN38).

Funções puras: recebem os eventos do histórico (banco.listar_excecoes) e
devolvem as linhas do relatório (quando, tipo, pessoa com o CPF mascarado,
quem autorizou, quem operava e a justificativa), lidas do texto que o
próprio dados.py grava em cada evento.
"""

import re

from .dados import (CODIGO_RECUPERACAO_USADO, EXCECAO_AUTORIZADA,
                    LOTACAO_LIBERADA, SAIDA_AUTOMATICA_ATUALIZACAO,
                    SAIDA_AUTOMATICA_ENCERRAMENTO, VEICULO_COM_AUTORIZADO,
                    VEICULO_SEM_DONO)
from .validacao import mascarar_cpf, mascarar_cpfs_no_texto

HORARIO, RETROATIVO, MAIS_DE_24H = "Horário", "Retroativo", "Mais de 24 h"
TIPO_DA_ACAO = {
    VEICULO_SEM_DONO: "Veículo sem o dono",
    VEICULO_COM_AUTORIZADO: "Veículo com autorizado",
    LOTACAO_LIBERADA: "Lotação com senha",
    SAIDA_AUTOMATICA_ENCERRAMENTO: "Saída automática",
    SAIDA_AUTOMATICA_ATUALIZACAO: "Saída automática",
    CODIGO_RECUPERACAO_USADO: "Código de recuperação",
}
# opções do filtro "Tipo", na ordem da tela
TIPOS = (HORARIO, RETROATIVO, MAIS_DE_24H, "Veículo sem o dono",
         "Veículo com autorizado", "Lotação com senha", "Saída automática",
         "Código de recuperação")
TODOS = "Todos"
SEM_VALOR = "—"
_JUSTIFICATIVA = re.compile(r"Justificativa: (.*?)\. Operador:", re.DOTALL)
_OPERADOR = re.compile(r"Operador: (\S+?)\.(?:\s|$)")


def tipos_do_evento(acao, detalhe):
    """Tipos de uma exceção. A "Exceção autorizada" pode ter mais de um
    (ex.: entrada retroativa fora do horário): olha as regras gravadas."""
    if acao != EXCECAO_AUTORIZADA:
        return [TIPO_DA_ACAO.get(acao, acao)]
    regras = detalhe.split(" Justificativa:")[0]
    tipos = []
    if "retroativa" in regras:
        tipos.append(RETROATIVO)
    if "o máximo é" in regras:
        tipos.append(MAIS_DE_24H)
    if ("fora do horário" in regras or "Campus fechado" in regras
            or not tipos):
        tipos.insert(0, HORARIO)
    return tipos


def ler_excecao(evento):
    """Uma linha do relatório a partir do evento do histórico (com o nome
    e o CPF da visita ligada, quando há)."""
    detalhe = evento["detalhe"]
    justificativa = _JUSTIFICATIVA.search(detalhe)
    operador = _OPERADOR.search(detalhe)
    pessoa = SEM_VALOR
    if evento.get("nome"):
        pessoa = evento["nome"]
        if evento.get("cpf"):
            pessoa += f" ({mascarar_cpf(evento['cpf'])})"
    return {"quando": evento["momento"][:16],
            "tipos": tipos_do_evento(evento["acao"], detalhe),
            "pessoa": pessoa,
            "autorizou": evento["usuario"],
            "operava": operador.group(1) if operador else evento["usuario"],
            "justificativa": (mascarar_cpfs_no_texto(justificativa.group(1))
                              if justificativa else SEM_VALOR),
            "detalhe": detalhe}


def filtrar(linhas, tipo=TODOS, autorizou=TODOS):
    """Linhas do tipo e de quem autorizou escolhidos (TODOS = sem filtro)."""
    return [l for l in linhas
            if (tipo in (TODOS, "", None) or tipo in l["tipos"])
            and (autorizou in (TODOS, "", None) or l["autorizou"] == autorizou)]


def quem_autorizou(linhas):
    """Opções do filtro "Quem autorizou" (sem repetir, em ordem)."""
    return sorted({l["autorizou"] for l in linhas})
