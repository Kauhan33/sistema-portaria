"""
Backup do banco e exportação de registros para planilha (CSV).

- fazer_backup: cópia consistente agora (pode ser com o programa em uso).
- backup_diario: no máximo uma cópia por dia, guardando as N mais recentes;
  pensado para rodar ao abrir o programa.
- exportar_csv: registros de um período para abrir no Excel.

Antes de copiar, o banco passa por PRAGMA quick_check: um banco com defeito
não vira "backup" (não substituiria uma cópia boa na rotação).
Os backups e o CSV têm CPF e celular: guarde-os com o mesmo cuidado que o
próprio banco (pasta com acesso restrito, disco criptografado).
"""

import csv
import glob
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime

from .dados import SEGUNDOS_ESPERA, ErroDados, copiar_banco, log, mensagem_amigavel
from .validacao import formatar_celular, formatar_cpf, formatar_placa

PREFIXO = "portaria"
MANTER_BACKUPS = 30
CABECALHO_CSV = ["Nome", "CPF", "Celular", "Placa", "Tipo", "Entrada", "Saída"]


def pasta_padrao(caminho_banco):
    """Pasta 'backups' ao lado do banco."""
    return os.path.join(os.path.dirname(os.path.abspath(caminho_banco)), "backups")


def verificar_banco(caminho_banco):
    """(ok, mensagem) do PRAGMA quick_check no arquivo."""
    try:
        with closing(sqlite3.connect(caminho_banco, timeout=SEGUNDOS_ESPERA)) as con:
            linhas = [linha[0] for linha in con.execute("PRAGMA quick_check")]
    except sqlite3.Error as e:
        log.error("quick_check falhou: %s", e)
        return False, mensagem_amigavel(e)
    if linhas == ["ok"]:
        return True, ""
    log.error("quick_check: %s", "; ".join(linhas[:10]))
    return False, ("O banco de dados apresenta defeitos.\n"
                   "Avise o administrador: é preciso restaurar o último backup.")


def _copiar_verificado(caminho_banco, destino):
    if not os.path.exists(caminho_banco):
        raise ErroDados("O banco de dados não foi encontrado para o backup.")
    ok, msg = verificar_banco(caminho_banco)
    if not ok:
        raise ErroDados("Backup não realizado.\n" + msg)
    os.makedirs(os.path.dirname(os.path.abspath(destino)), exist_ok=True)
    return copiar_banco(caminho_banco, destino)


def fazer_backup(caminho_banco, pasta=None, agora=None):
    """Backup manual agora. Devolve o caminho do arquivo criado."""
    agora = agora or datetime.now()
    pasta = pasta or pasta_padrao(caminho_banco)
    destino = os.path.join(pasta, f"{PREFIXO}-manual-{agora:%Y%m%d-%H%M%S}.db")
    return _copiar_verificado(caminho_banco, destino)


def backups_diarios(pasta):
    """Backups diários da pasta, do mais antigo para o mais recente."""
    return sorted(glob.glob(os.path.join(pasta, f"{PREFIXO}-????-??-??.db")))


def backup_diario(caminho_banco, pasta=None, manter=MANTER_BACKUPS, hoje=None):
    """
    Cria o backup do dia se ainda não existe e apaga os diários mais antigos,
    deixando os `manter` mais recentes. Devolve o caminho criado, ou None se
    o de hoje já existia. Backups manuais e de antes de atualizações não
    entram na rotação.
    """
    hoje = hoje or date.today()
    pasta = pasta or pasta_padrao(caminho_banco)
    destino = os.path.join(pasta, f"{PREFIXO}-{hoje:%Y-%m-%d}.db")
    if os.path.exists(destino):
        return None
    _copiar_verificado(caminho_banco, destino)
    for velho in backups_diarios(pasta)[:-max(1, manter)]:
        try:
            os.remove(velho)
        except OSError as e:   # aberto em outro programa: tenta amanhã
            log.warning("Não foi possível apagar o backup antigo %s: %s",
                        os.path.basename(velho), e)
    return destino


def _celula(valor):
    """Evita que o Excel interprete um texto como fórmula (=, +, -, @)."""
    texto = str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@") else texto


def exportar_csv(banco, caminho_csv, desde, ate, autor=None):
    """
    Grava num CSV as visitas com entrada entre `desde` e `ate` (date,
    inclusive). Separador ';' e UTF-8 com BOM, para o Excel em português
    abrir certo; CPF, celular e placa formatados. Só administrador (quando
    `autor` é informado) e fica no histórico. Devolve quantos registros.
    """
    if ate < desde:
        raise ErroDados("A data final não pode ser anterior à inicial.")
    registros = banco.registros_do_periodo(desde, ate, autor=autor)
    temporario = caminho_csv + ".tmp"
    try:
        with open(temporario, "w", newline="", encoding="utf-8-sig") as f:
            escritor = csv.writer(f, delimiter=";")
            escritor.writerow(CABECALHO_CSV)
            for r in registros:
                escritor.writerow([_celula(v) for v in (
                    r["nome"], formatar_cpf(r["cpf"]),
                    formatar_celular(r["celular"]), formatar_placa(r["placa"]),
                    r["tipo"], r["entrada"], r["saida"])])
        os.replace(temporario, caminho_csv)
    except OSError as e:
        log.error("Erro ao gravar o CSV: %s", e)
        if os.path.exists(temporario):
            os.remove(temporario)
        raise ErroDados("Não foi possível gravar o arquivo.\n"
                        "Confira se ele não está aberto no Excel e se há "
                        "permissão na pasta.", detalhe=str(e)) from e
    return len(registros)
