"""
Senhas e códigos de recuperação (RNF02, RN31, RN38), sem depender do banco
nem da tela: o dados.py e o usuarios.py usam o MESMO código, sem import
circular (este módulo não importa nenhum dos dois).

- Hash: PBKDF2-SHA256 com sal aleatório, num texto único
  'pbkdf2_sha256$iterações$sal$hash'. A senha nunca é guardada nem
  mostrada em texto aberto, nem vai para o histórico ou o log.
- Tentativas erradas (contar_falha): depois de LIMITE_TENTATIVAS erros
  seguidos, trava por um tempo que dobra a cada novo bloqueio (30 s,
  1 min, 2 min... até 15 min). Vale para o login (por usuário) e para o
  diálogo de autorização (por estação: CHAVE_AUTORIZACAO).
- Códigos de recuperação do administrador (RN38): 8 códigos de uso único
  no formato K7QM-2F9X, sem os caracteres que se confundem (0 e O, 1, I
  e L). Só o hash de cada um vai para o banco.
"""

import hashlib
import hmac
import os
import platform
import re
import secrets
from datetime import timedelta

# Recomendação atual da OWASP para PBKDF2-SHA256. Os testes baixam
# ITERACOES (tests/__init__.py), por isso gerar_hash lê o valor na hora.
ITERACOES_PADRAO = 600_000
ITERACOES = ITERACOES_PADRAO
LIMITE_TENTATIVAS = 5
SEGUNDOS_BLOQUEIO = 30           # primeiro bloqueio; dobra a cada novo
SEGUNDOS_BLOQUEIO_MAXIMO = 15 * 60
# Contador do diálogo de autorização, um por estação (computador), na mesma
# tabela das tentativas de login: o "@" não cabe num login, então as chaves
# nunca se misturam com as dos usuários.
CHAVE_AUTORIZACAO = "autorizacao@{}"

# Códigos de recuperação (RN38)
QUANTIDADE_CODIGOS = 8
TAMANHO_CODIGO = 8               # sem o hífen do meio
ALFABETO_CODIGO = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"   # sem 0, O, 1, I, L
_REGEX_CODIGO = re.compile(f"^[{ALFABETO_CODIGO}]{{{TAMANHO_CODIGO}}}$")


# ------------------------------------------------------------------
# Hash
# ------------------------------------------------------------------
def gerar_hash(senha, sal=None, iteracoes=None):
    """
    PBKDF2-SHA256 com sal aleatório. Devolve um texto único com tudo o que
    é preciso para conferir depois: 'pbkdf2_sha256$iterações$sal$hash'.
    Sem `iteracoes`, usa o ITERACOES do módulo no momento da chamada.
    """
    iteracoes = ITERACOES if iteracoes is None else iteracoes
    sal = sal or os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, iteracoes)
    return f"pbkdf2_sha256${iteracoes}${sal.hex()}${h.hex()}"


def conferir_senha(senha, guardado):
    """True se `senha` gera o mesmo hash guardado (comparação em tempo
    constante). Hash em formato desconhecido nunca confere."""
    try:
        algoritmo, iteracoes, sal, _ = guardado.split("$")
        if algoritmo != "pbkdf2_sha256":
            return False
        calculado = gerar_hash(senha, bytes.fromhex(sal), int(iteracoes))
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(calculado, guardado)


def precisa_atualizar_hash(guardado):
    """True se o hash foi gerado com menos iterações que as atuais."""
    try:
        return int(guardado.split("$")[1]) < ITERACOES
    except (ValueError, AttributeError, IndexError):
        return False


# Usado quando o login não existe, para a resposta demorar o mesmo tempo
# e não revelar quais usuários existem. Gerado na primeira vez que precisa,
# com as iterações em vigor.
_hashes_falsos = {}


def hash_falso():
    if ITERACOES not in _hashes_falsos:
        _hashes_falsos[ITERACOES] = gerar_hash("senha-que-ninguem-usa")
    return _hashes_falsos[ITERACOES]


# ------------------------------------------------------------------
# Tentativas erradas (bloqueio progressivo)
# ------------------------------------------------------------------
def segundos_de_bloqueio(bloqueios_anteriores):
    """Espera crescente: 30 s, 1 min, 2 min, 4 min... até 15 min."""
    return min(SEGUNDOS_BLOQUEIO * 2 ** min(bloqueios_anteriores, 10),
               SEGUNDOS_BLOQUEIO_MAXIMO)


def contar_falha(falhas, bloqueios, agora):
    """
    Mais um erro (senha ou código de recuperação). Devolve o novo estado
    (falhas, bloqueios, bloqueado_ate, segundos): na LIMITE_TENTATIVAS-ésima
    falha seguida as falhas zeram, o número de bloqueios sobe e o contador
    trava por `segundos`; antes disso, bloqueado_ate e segundos são None.
    """
    falhas += 1
    if falhas < LIMITE_TENTATIVAS:
        return falhas, bloqueios, None, None
    segundos = segundos_de_bloqueio(bloqueios)
    return 0, bloqueios + 1, agora + timedelta(seconds=segundos), segundos


def estacao_atual():
    """Nome deste computador (identifica a estação no contador e no
    histórico da autorização)."""
    return platform.node() or "esta estação"


# ------------------------------------------------------------------
# Códigos de recuperação (RN38)
# ------------------------------------------------------------------
def formatar_codigo(codigo):
    """'K7QM2F9X' -> 'K7QM-2F9X' (como aparece na tela e na impressão)."""
    meio = TAMANHO_CODIGO // 2
    return f"{codigo[:meio]}-{codigo[meio:]}"


def gerar_codigos(quantidade=QUANTIDADE_CODIGOS):
    """Códigos novos (formatados), sorteados com `secrets` e sem repetir."""
    codigos = set()
    while len(codigos) < quantidade:
        codigos.add("".join(secrets.choice(ALFABETO_CODIGO)
                            for _ in range(TAMANHO_CODIGO)))
    return [formatar_codigo(c) for c in sorted(codigos)]


def normalizar_codigo(texto):
    """
    O código como foi digitado -> os 8 caracteres que entram no hash
    ('k7qm 2f9x' ou 'K7QM-2F9X' -> 'K7QM2F9X'), ou '' se não tem o formato.
    """
    codigo = re.sub(r"[\s\-]", "", texto or "").upper()
    return codigo if _REGEX_CODIGO.match(codigo) else ""
