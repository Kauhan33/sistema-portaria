"""
Usuários do sistema: senha com hash, perfis, permissões e bloqueio por
tentativas erradas. Como validacao.py, não depende do Tkinter.
"""

import hashlib
import hmac
import math
import os
import re
import time
from datetime import timedelta

from .validacao import converter_data, nome_valido

PERFIS = {"admin": "Administrador", "porteiro": "Porteiro"}
SENHA_MINIMA = 6
REGEX_LOGIN = re.compile(r"^[a-z0-9._]{3,20}$")
ITERACOES = 200_000
LIMITE_TENTATIVAS = 5
SEGUNDOS_BLOQUEIO = 30
HORAS_PARA_CORRIGIR = 24


# ------------------------------------------------------------------
# Senha (RNF02: nunca é guardada nem mostrada em texto aberto)
# ------------------------------------------------------------------
def gerar_hash(senha, sal=None, iteracoes=ITERACOES):
    """
    PBKDF2-SHA256 com sal aleatório. Devolve um texto único com tudo o que
    é preciso para conferir depois: 'pbkdf2_sha256$iterações$sal$hash'.
    """
    sal = sal or os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, iteracoes)
    return f"pbkdf2_sha256${iteracoes}${sal.hex()}${h.hex()}"


def conferir_senha(senha, guardado):
    try:
        algoritmo, iteracoes, sal, _ = guardado.split("$")
        if algoritmo != "pbkdf2_sha256":
            return False
        calculado = gerar_hash(senha, bytes.fromhex(sal), int(iteracoes))
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(calculado, guardado)


# Usado quando o login não existe, para a resposta demorar o mesmo tempo
# e não revelar quais usuários existem.
_HASH_FALSO = gerar_hash("senha-que-ninguem-usa")


# ------------------------------------------------------------------
# Cadastro de usuário
# ------------------------------------------------------------------
def normalizar_login(login):
    return login.strip().lower()


def validar_senha(senha, confirmacao):
    if len(senha) < SENHA_MINIMA:
        return False, f"A senha deve ter pelo menos {SENHA_MINIMA} caracteres."
    if senha != confirmacao:
        return False, "A confirmação não é igual à senha."
    return True, ""


def validar_novo_usuario(nome, login, senha, confirmacao, perfil,
                         logins_existentes):
    """Retorna (ok, mensagem). `login` já normalizado."""
    if not nome_valido(" ".join(nome.split())):
        return False, "Informe o nome completo do usuário (só letras)."
    if not REGEX_LOGIN.match(login):
        return False, ("Usuário inválido.\nUse de 3 a 20 letras minúsculas, "
                       "números, ponto ou sublinhado (ex.: maria.souza).")
    if login in logins_existentes:
        return False, "Já existe um usuário com esse login."
    if perfil not in PERFIS:
        return False, "Selecione o perfil do usuário."
    return validar_senha(senha, confirmacao)


def autenticar(banco, login, senha):
    """Devolve o usuário (id, login, nome, perfil) ou None se não puder entrar."""
    u = banco.buscar_usuario(normalizar_login(login))
    if u is None:
        conferir_senha(senha, _HASH_FALSO)
        return None
    if not conferir_senha(senha, u["senha"]) or not u["ativo"]:
        return None
    return {k: u[k] for k in ("id", "login", "nome", "perfil")}


# ------------------------------------------------------------------
# Permissões (RN02: somente administrador exclui registros)
# ------------------------------------------------------------------
def eh_admin(usuario):
    return usuario is not None and usuario["perfil"] == "admin"


pode_excluir = eh_admin
pode_gerenciar_usuarios = eh_admin


def pode_editar(usuario, registro, agora):
    """
    Retorna (ok, mensagem). Administrador corrige qualquer registro; o
    porteiro só os com entrada nas últimas HORAS_PARA_CORRIGIR horas (erro
    de digitação do turno, mesmo virando a meia-noite) — RN11.
    """
    if eh_admin(usuario):
        return True, ""
    entrada = converter_data(registro["entrada"])
    if (usuario is not None and entrada is not None
            and timedelta(0) <= agora - entrada
            <= timedelta(hours=HORAS_PARA_CORRIGIR)):
        return True, ""
    return False, (f"O porteiro só pode corrigir registros com entrada nas "
                   f"últimas {HORAS_PARA_CORRIGIR} horas.\n"
                   "Para registros mais antigos, peça a um administrador.")


def pode_desativar(alvo, logado, admins_ativos):
    """Retorna (ok, mensagem) para desativar o usuário `alvo`."""
    if alvo["id"] == logado["id"]:
        return False, "Você não pode desativar o seu próprio usuário."
    if alvo["perfil"] == "admin" and alvo["ativo"] and admins_ativos <= 1:
        return False, "O sistema precisa de pelo menos um administrador ativo."
    return True, ""


# ------------------------------------------------------------------
# Bloqueio por tentativas erradas
# ------------------------------------------------------------------
class ControleTentativas:
    """Depois de LIMITE_TENTATIVAS erros seguidos, bloqueia por alguns segundos."""

    def __init__(self, relogio=time.monotonic):
        self.relogio = relogio
        self.falhas = 0
        self.bloqueado_ate = 0.0

    def segundos_restantes(self):
        return max(0, math.ceil(self.bloqueado_ate - self.relogio()))

    def registrar_falha(self):
        self.falhas += 1
        if self.falhas >= LIMITE_TENTATIVAS:
            self.falhas = 0
            self.bloqueado_ate = self.relogio() + SEGUNDOS_BLOQUEIO

    def registrar_sucesso(self):
        self.falhas = 0
