"""Busca na tabela e números do dashboard, calculados a partir dos registros."""

import re
from datetime import timedelta

from .validacao import (TIPOS_ACESSO, converter_data, formatar_celular,
                        formatar_cpf, formatar_placa, so_digitos)

# Campos de um registro na ordem e com o nome que aparecem no histórico
CAMPOS_REGISTRO = [("cpf", "CPF", formatar_cpf), ("nome", "Nome", str),
                   ("celular", "Celular", formatar_celular),
                   ("placa", "Placa", formatar_placa), ("tipo", "Tipo", str),
                   ("entrada", "Entrada", str), ("saida", "Saída", str)]


def descrever_alteracoes(antes, depois):
    """Lista 'Campo: valor antigo → valor novo' só do que mudou."""
    mudancas = []
    for chave, rotulo, formatar in CAMPOS_REGISTRO:
        velho, novo = antes.get(chave, ""), depois.get(chave, "")
        if velho != novo:
            mudancas.append(f"{rotulo}: {formatar(velho) or '—'} → "
                            f"{formatar(novo) or '—'}")
    return mudancas


def filtrar(registros, texto):
    """Registros que batem com a busca (nome, CPF, celular, placa ou tipo)."""
    texto = texto.strip().lower()
    numeros = so_digitos(texto)
    resultado = []
    for r in registros:
        if texto:
            achou = (texto in r["nome"].lower()
                     or texto in r["tipo"].lower()
                     or texto in r.get("placa", "").lower()
                     or (numeros and (numeros in r.get("cpf", "")
                                      or numeros in r.get("celular", ""))))
            if not achou:
                continue
        resultado.append(r)
    return resultado


def encontrar_dentro(registros, texto):
    """
    Saída rápida: registros ainda abertos cujo CPF ou placa é exatamente o
    digitado. Aceita CPF com pontos/traço e placa com hífen ou minúscula.
    Só correspondência exata, para não dar saída na pessoa errada.
    """
    bruto = re.sub(r"[\s.\-]", "", texto).upper()
    if not bruto:
        return []
    abertos = [r for r in registros if not r["saida"]]
    if bruto.isdigit():
        return [r for r in abertos if r["cpf"] == bruto] if len(bruto) == 11 else []
    return [r for r in abertos if r.get("placa") == bruto]


def formatar_duracao(td):
    minutos = int(td.total_seconds() // 60)
    h, m = divmod(minutos, 60)
    return f"{h}h {m:02d}min" if h else f"{m}min"


def resumo(registros, hoje):
    """Totais para o dashboard. `hoje` é um date."""
    por_tipo = {t: [0, 0] for t in TIPOS_ACESSO}          # [total, dentro]
    por_dia = {hoje - timedelta(days=i): 0 for i in range(6, -1, -1)}
    permanencias = []
    entradas_hoje = com_veiculo = dentro = 0

    for r in registros:
        contagem = por_tipo.setdefault(r["tipo"], [0, 0])
        contagem[0] += 1
        if not r["saida"]:
            contagem[1] += 1
            dentro += 1
        if r.get("placa"):
            com_veiculo += 1
        entrada_dt = converter_data(r["entrada"])
        if entrada_dt:
            dia = entrada_dt.date()
            if dia in por_dia:
                por_dia[dia] += 1
            if dia == hoje:
                entradas_hoje += 1
            saida_dt = converter_data(r["saida"]) if r["saida"] else None
            if saida_dt:
                permanencias.append(saida_dt - entrada_dt)

    media = (sum(permanencias, timedelta()) / len(permanencias)
             if permanencias else None)
    return {
        "total": len(registros),
        "dentro": dentro,
        "entradas_hoje": entradas_hoje,
        "com_veiculo": com_veiculo,
        "por_tipo": por_tipo,
        "por_dia": por_dia,
        "permanencia_media": media,
        "saidas": len(permanencias),
    }
