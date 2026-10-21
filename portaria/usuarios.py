"""
Usuários do sistema: senha com hash, perfis, permissões e bloqueio por
tentativas erradas. Como validacao.py, não depende do Tkinter.

Login para a tela usar: `entrar(banco, login, senha)`. Ele confere a senha,
guarda as tentativas erradas no banco (continuam valendo se o programa for
fechado e aberto de novo) e registra o "Login recusado" sem gravar o texto
digitado quando ele não é um login existente (pode ser uma senha digitada
no campo errado).

Autorização de exceção (diálogo do administrador na guarita):
`conferir_autorizador`. Ele NÃO usa o contador do login (N04): errar a
senha ali trava só o diálogo, naquela estação, e nunca o login do
administrador (antes, 5 chutes no diálogo travavam o administrador em
todas as estações, inclusive no login normal).
"""

import hashlib
import hmac
import math
import os
import platform
import re
import time
from datetime import datetime, timedelta

from .validacao import converter_data, nome_valido

PERFIS = {"admin": "Administrador", "porteiro": "Porteiro"}
# Tema escolhido por cada usuário (menu da conta). "sistema" = seguir o
# Windows. Os textos do menu ficam em estilo.PREFERENCIAS_TEMA.
TEMAS = ("claro", "escuro", "sistema")
TEMA_PADRAO = "sistema"
SENHA_MINIMA = 8
SENHA_MAXIMA = 128
REGEX_LOGIN = re.compile(r"^[a-z0-9._]{3,20}$")
# Recomendação atual da OWASP para PBKDF2-SHA256. Os testes baixam
# ITERACOES (tests/__init__.py), por isso gerar_hash lê o valor na hora.
ITERACOES_PADRAO = 600_000
ITERACOES = ITERACOES_PADRAO
LIMITE_TENTATIVAS = 5
SEGUNDOS_BLOQUEIO = 30           # primeiro bloqueio; dobra a cada novo
SEGUNDOS_BLOQUEIO_MAXIMO = 15 * 60
HORAS_PARA_CORRIGIR = 24
# Sessão encerrada depois deste tempo sem teclado/mouse (a tela liga)
MINUTOS_INATIVIDADE = 10
# Ação que chegou depois do fim da sessão (ex.: "Sim" numa caixa que ficou
# aberta enquanto a inatividade encerrava a sessão): a tela e o banco recusam
SESSAO_ENCERRADA = "A sessão foi encerrada. Entre novamente."

# Senhas que caem primeiro numa tentativa de adivinhação
SENHAS_COMUNS = {
    "12345678", "123456789", "1234567890", "87654321", "11111111",
    "00000000", "12341234", "11223344", "abcd1234", "abc12345",
    "password", "password1", "senha123", "senha1234", "mudar123",
    "qwerty123", "qwertyui", "iloveyou", "admin123", "administrador",
    "portaria", "portaria1", "portaria123", "porteiro", "porteiro1",
    "universidade", "faculdade",
}

# Tentativas erradas de logins que não existem dividem um contador só, e o
# histórico não guarda o texto digitado (pode ser a senha no campo errado).
CHAVE_LOGIN_INEXISTENTE = "*"
LOGIN_INEXISTENTE = "(login inexistente)"
# Contador do diálogo de autorização, um por estação (computador), na mesma
# tabela das tentativas de login: o "@" não cabe num login, então as chaves
# nunca se misturam com as dos usuários.
CHAVE_AUTORIZACAO = "autorizacao@{}"


# ------------------------------------------------------------------
# Senha (RNF02: nunca é guardada nem mostrada em texto aberto)
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


def _hash_falso():
    if ITERACOES not in _hashes_falsos:
        _hashes_falsos[ITERACOES] = gerar_hash("senha-que-ninguem-usa")
    return _hashes_falsos[ITERACOES]


# ------------------------------------------------------------------
# Cadastro de usuário e troca de senha
# ------------------------------------------------------------------
def normalizar_login(login):
    return login.strip().lower()


def validar_senha(senha, confirmacao, login=""):
    """Retorna (ok, mensagem). Com `login`, recusa também senha igual ao login."""
    if len(senha) < SENHA_MINIMA:
        return False, f"A senha deve ter pelo menos {SENHA_MINIMA} caracteres."
    if len(senha) > SENHA_MAXIMA:
        return False, f"A senha pode ter no máximo {SENHA_MAXIMA} caracteres."
    if senha.lower() in SENHAS_COMUNS or (login and senha.lower() == login.lower()):
        return False, ("Essa senha é fácil de adivinhar.\n"
                       "Escolha outra (não use o login nem sequências).")
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
    return validar_senha(senha, confirmacao, login)


def validar_troca_senha(guardado, senha_atual, nova, confirmacao, login=""):
    """
    Troca da própria senha. Retorna (ok, mensagem). `guardado` é o hash
    atual do usuário (banco.buscar_usuario(login)["senha"]).
    """
    if not conferir_senha(senha_atual, guardado):
        return False, "A senha atual não confere."
    if nova == senha_atual:
        return False, "A senha nova deve ser diferente da atual."
    return validar_senha(nova, confirmacao, login)


def trocar_senha(banco, usuario, senha_atual, nova, confirmacao):
    """
    O próprio usuário troca a senha (pede a atual). Retorna (ok, mensagem).
    Se ok, a senha já foi gravada e o histórico registra "Senha alterada".
    """
    u = banco.buscar_usuario(usuario["login"])
    if u is None or not u["ativo"]:
        return False, "Usuário não encontrado ou desativado."
    ok, msg = validar_troca_senha(u["senha"], senha_atual, nova, confirmacao,
                                  u["login"])
    if not ok:
        return False, msg
    banco.definir_senha(u["id"], gerar_hash(nova), autor=u["login"])
    return True, "Senha alterada com sucesso."


# ------------------------------------------------------------------
# Login
# ------------------------------------------------------------------
def _conferir(banco, u, senha):
    """
    Confere a senha de `u` (ou um hash falso, se o login não existe). Se o
    hash guardado for de um padrão antigo (menos iterações, ex.: 200 mil),
    grava um novo com as iterações atuais: a migração acontece sozinha,
    no primeiro login de cada usuário.
    """
    if u is None:
        conferir_senha(senha, _hash_falso())
        return False
    if not conferir_senha(senha, u["senha"]):
        return False
    if precisa_atualizar_hash(u["senha"]):
        banco.atualizar_hash_senha(u["id"], gerar_hash(senha))
    return bool(u["ativo"])


def autenticar(banco, login, senha):
    """Devolve o usuário (id, login, nome, perfil) ou None se não puder entrar."""
    u = banco.buscar_usuario(normalizar_login(login))
    if not _conferir(banco, u, senha):
        return None
    return {k: u[k] for k in ("id", "login", "nome", "perfil")}


def segundos_de_bloqueio(bloqueios_anteriores):
    """Espera crescente: 30 s, 1 min, 2 min, 4 min... até 15 min."""
    return min(SEGUNDOS_BLOQUEIO * 2 ** min(bloqueios_anteriores, 10),
               SEGUNDOS_BLOQUEIO_MAXIMO)


def entrar(banco, login, senha, agora=None):
    """
    Login completo para a tela. Devolve (usuario, "") ou (None, motivo).

    - As tentativas erradas ficam no banco, por login. Depois de
      LIMITE_TENTATIVAS erros seguidos o login fica bloqueado por um tempo
      que dobra a cada novo bloqueio (segundos_de_bloqueio). Durante o
      bloqueio a senha nem é conferida. Um acerto zera tudo.
    - Logins inexistentes dividem um único contador, e o histórico grava
      LOGIN_INEXISTENTE no lugar do texto digitado (S11).
    - Hash de senha antigo é atualizado ao entrar (ver _conferir).
    `agora` (datetime) existe para os testes; o padrão é o relógio do PC.
    """
    agora = agora or datetime.now()
    login = normalizar_login(login or "")
    if not login or not senha:
        return None, "Informe o usuário e a senha."
    u = banco.buscar_usuario(login)
    chave = u["login"] if u else CHAVE_LOGIN_INEXISTENTE
    quem = u["login"] if u else LOGIN_INEXISTENTE

    falhas, bloqueios, bloqueado_ate = banco.ler_tentativas_login(chave)
    if bloqueado_ate is not None and bloqueado_ate > agora:
        restante = math.ceil((bloqueado_ate - agora).total_seconds())
        return None, f"Muitas tentativas erradas. Aguarde {restante} s."

    if _conferir(banco, u, senha):
        if falhas or bloqueios:
            banco.gravar_tentativas_login(chave, 0, 0, None)
        return {k: u[k] for k in ("id", "login", "nome", "perfil", "tema")}, ""

    falhas += 1
    motivo = "Usuário ou senha incorretos."
    if falhas >= LIMITE_TENTATIVAS:
        segundos = segundos_de_bloqueio(bloqueios)
        banco.gravar_tentativas_login(chave, 0, bloqueios + 1,
                                      agora + timedelta(seconds=segundos))
        banco.registrar_evento(quem, "Login recusado",
                               f"{LIMITE_TENTATIVAS} tentativas erradas seguidas; "
                               f"bloqueado por {segundos} s")
        motivo += f"\nMuitas tentativas erradas. Aguarde {segundos} s."
    else:
        banco.gravar_tentativas_login(chave, falhas, bloqueios, None)
        banco.registrar_evento(quem, "Login recusado")
    return None, motivo


def estacao_atual():
    """Nome deste computador (identifica a estação no contador e no
    histórico da autorização)."""
    return platform.node() or "esta estação"


def conferir_autorizador(banco, login, senha, estacao, operador, agora=None):
    """
    Confere quem autoriza uma exceção no diálogo "Autorização do
    administrador". Devolve (usuario, "") ou (None, motivo).

    N04: as senhas erradas contam num contador PRÓPRIO da estação
    (CHAVE_AUTORIZACAO), com a mesma espera crescente do login. Depois de
    LIMITE_TENTATIVAS erros seguidos, o diálogo fica travado nesta estação;
    o login do administrador continua funcionando em todas (inclusive
    nesta). O contador fica no banco: fechar e abrir o programa não zera.
    Cada senha errada vira "Autorização recusada" no histórico, e a trava,
    "Autorização travada", com quem estava operando como autor (o texto
    digitado só aparece se for um login que existe).
    """
    agora = agora or datetime.now()
    login = normalizar_login(login or "")
    if not login or not senha:
        return None, "Informe o login e a senha do administrador."
    chave = CHAVE_AUTORIZACAO.format(estacao)
    falhas, bloqueios, bloqueado_ate = banco.ler_tentativas_login(chave)
    if bloqueado_ate is not None and bloqueado_ate > agora:
        restante = math.ceil((bloqueado_ate - agora).total_seconds())
        return None, (f"Muitas senhas erradas nesta estação: a autorização "
                      f"fica travada por mais {restante} s.\nO login do "
                      "administrador não foi afetado.")
    u = banco.buscar_usuario(login)
    if _conferir(banco, u, senha):
        if falhas or bloqueios:
            banco.gravar_tentativas_login(chave, 0, 0, None)
        return {k: u[k] for k in ("id", "login", "nome", "perfil")}, ""
    falhas += 1
    quem = u["login"] if u else LOGIN_INEXISTENTE
    motivo = "Usuário ou senha incorretos."
    if falhas >= LIMITE_TENTATIVAS:
        segundos = segundos_de_bloqueio(bloqueios)
        banco.gravar_tentativas_login(chave, 0, bloqueios + 1,
                                      agora + timedelta(seconds=segundos))
        banco.registrar_evento(operador, "Autorização travada",
                               f"{LIMITE_TENTATIVAS} senhas erradas seguidas "
                               f"(última para {quem}) na estação {estacao}; "
                               f"diálogo travado por {segundos} s")
        motivo += ("\nMuitas senhas erradas: a autorização fica travada "
                   f"nesta estação por {segundos} s.")
    else:
        banco.gravar_tentativas_login(chave, falhas, bloqueios, None)
        banco.registrar_evento(operador, "Autorização recusada",
                               f"Senha errada para {quem} na estação {estacao}")
    return None, motivo


# ------------------------------------------------------------------
# Permissões (RN02: somente administrador exclui registros)
# ------------------------------------------------------------------
def eh_admin(usuario):
    return usuario is not None and usuario["perfil"] == "admin"


pode_excluir = eh_admin
pode_gerenciar_usuarios = eh_admin
pode_gerenciar_bloqueios = eh_admin


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
# Bloqueio por tentativas erradas (só na memória)
# ------------------------------------------------------------------
class ControleTentativas:
    """
    Depois de LIMITE_TENTATIVAS erros seguidos, bloqueia por alguns segundos.
    Fica só na memória (zera ao fechar o programa). A versão que guarda as
    tentativas no banco, por login, é `entrar()`.
    """

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
