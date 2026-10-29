"""
Usuários do sistema: perfis, permissões, login e bloqueio por tentativas
erradas. O hash da senha e o contador de tentativas ficam em senhas.py
(o mesmo código que o banco usa para conferir a senha do administrador).
Como validacao.py, não depende do Tkinter.

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

import math
import re
import time
from datetime import datetime, timedelta

from .senhas import (CHAVE_AUTORIZACAO, ITERACOES_PADRAO, LIMITE_TENTATIVAS,
                     SEGUNDOS_BLOQUEIO, SEGUNDOS_BLOQUEIO_MAXIMO, conferir_senha,
                     contar_falha, estacao_atual, gerar_codigos, gerar_hash,
                     hash_falso, normalizar_codigo, precisa_atualizar_hash,
                     segundos_de_bloqueio)
from .validacao import (MAXIMO_LOGIN, MAXIMO_NOME, MAXIMO_SENHA,
                        checar_tamanho, converter_data, nome_valido)

PERFIS = {"admin": "Administrador", "porteiro": "Porteiro"}
# Tema escolhido por cada usuário (menu da conta). "sistema" = seguir o
# Windows. Os textos do menu ficam em estilo.PREFERENCIAS_TEMA.
TEMAS = ("claro", "escuro", "sistema")
TEMA_PADRAO = "sistema"
SENHA_MINIMA = 8
SENHA_MAXIMA = MAXIMO_SENHA
REGEX_LOGIN = re.compile(r"^[a-z0-9._]{3,%d}$" % MAXIMO_LOGIN)
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


# ------------------------------------------------------------------
# Cadastro de usuário e troca de senha
# ------------------------------------------------------------------
def normalizar_login(login):
    return login.strip().lower()


def validar_senha(senha, confirmacao, login=""):
    """Retorna (ok, mensagem). Com `login`, recusa também senha igual ao login."""
    if len(senha) < SENHA_MINIMA:
        return False, f"A senha deve ter pelo menos {SENHA_MINIMA} caracteres."
    ok, msg = checar_tamanho("Senha", senha, SENHA_MAXIMA)
    if not ok:
        return False, msg
    if senha.lower() in SENHAS_COMUNS or (login and senha.lower() == login.lower()):
        return False, ("Essa senha é fácil de adivinhar.\n"
                       "Escolha outra (não use o login nem sequências).")
    if senha != confirmacao:
        return False, "A confirmação não é igual à senha."
    return True, ""


def validar_novo_usuario(nome, login, senha, confirmacao, perfil,
                         logins_existentes):
    """Retorna (ok, mensagem). `login` já normalizado."""
    for rotulo, texto, maximo in (("Nome completo", " ".join(nome.split()),
                                   MAXIMO_NOME),
                                  ("Usuário", login, MAXIMO_LOGIN)):
        ok, msg = checar_tamanho(rotulo, texto, maximo)
        if not ok:
            return False, msg
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


def validar_edicao_usuario(alvo, nome, perfil, logado, admins_ativos):
    """
    RN43 (2.3): (ok, mensagem) para o administrador editar o nome e o
    perfil de uma conta. O login não muda (é ele que identifica quem fez
    cada ação no histórico). Ninguém muda o próprio perfil, e o último
    administrador ativo não vira porteiro (RN08).
    """
    nome = " ".join((nome or "").split())
    ok, msg = checar_tamanho("Nome completo", nome, MAXIMO_NOME)
    if not ok:
        return False, msg
    if not nome_valido(nome):
        return False, "Informe o nome completo do usuário (só letras)."
    if perfil not in PERFIS:
        return False, "Selecione o perfil do usuário."
    if perfil != alvo["perfil"]:
        if logado is not None and alvo["id"] == logado["id"]:
            return False, "Você não pode mudar o seu próprio perfil."
        if (alvo["perfil"] == "admin" and alvo.get("ativo", True)
                and admins_ativos <= 1):
            return False, ("O sistema precisa de pelo menos um "
                           "administrador ativo.")
    return True, ""


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


def precisa_trocar_senha(usuario):
    """RN39: o usuário entrou com uma senha que o administrador definiu
    (criou a conta ou redefiniu a senha) e precisa escolher a dele antes
    de qualquer tela."""
    return bool(usuario and usuario.get("trocar_senha"))


def definir_senha_inicial(banco, login, nova, confirmacao):
    """
    RN39 — "Defina sua senha" no primeiro login: a nova senha não pode ser
    a provisória (a que o administrador passou), nem igual ao login, nem
    fácil. Retorna (ok, mensagem); se ok, a pendência acabou e o histórico
    registra "Senha alterada".
    """
    u = banco.buscar_usuario(normalizar_login(login or ""))
    if u is None or not u["ativo"]:
        return False, "Usuário não encontrado ou desativado."
    if conferir_senha(nova, u["senha"]):
        return False, ("A senha nova deve ser diferente da que o "
                       "administrador passou.")
    ok, msg = validar_senha(nova, confirmacao, u["login"])
    if not ok:
        return False, msg
    banco.definir_senha(u["id"], gerar_hash(nova), autor=u["login"])
    return True, "Senha definida."


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
        conferir_senha(senha, hash_falso())
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
        return {k: u[k] for k in ("id", "login", "nome", "perfil", "tema",
                                  "trocar_senha")}, ""

    return None, contar_erro_de_login(banco, chave, quem, falhas, bloqueios,
                                      agora, "Usuário ou senha incorretos.")


def contar_erro_de_login(banco, chave, quem, falhas, bloqueios, agora, motivo,
                         acao="Login recusado"):
    """Mais um erro no login de `chave` (senha errada ou código de
    recuperação errado: os dois contam no mesmo bloqueio progressivo).
    Grava o contador e o evento; devolve o motivo para a tela."""
    falhas, bloqueios, ate, segundos = contar_falha(falhas, bloqueios, agora)
    banco.gravar_tentativas_login(chave, falhas, bloqueios, ate)
    if segundos:
        banco.registrar_evento(quem, acao,
                               f"{LIMITE_TENTATIVAS} tentativas erradas seguidas; "
                               f"bloqueado por {segundos} s")
        motivo += f"\nMuitas tentativas erradas. Aguarde {segundos} s."
    else:
        banco.registrar_evento(quem, acao)
    return motivo


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

    V0: o banco chama esta MESMA função ao receber uma autorização com a
    senha (dados.Banco._autorizacao_conferida): a senha é recalculada lá
    também e o contador da estação vale para os dois caminhos.
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
    quem = u["login"] if u else LOGIN_INEXISTENTE
    motivo = "Usuário ou senha incorretos."
    falhas, bloqueios, ate, segundos = contar_falha(falhas, bloqueios, agora)
    banco.gravar_tentativas_login(chave, falhas, bloqueios, ate)
    if segundos:
        banco.registrar_evento(operador, "Autorização travada",
                               f"{LIMITE_TENTATIVAS} senhas erradas seguidas "
                               f"(última para {quem}) na estação {estacao}; "
                               f"diálogo travado por {segundos} s")
        motivo += ("\nMuitas senhas erradas: a autorização fica travada "
                   f"nesta estação por {segundos} s.")
    else:
        banco.registrar_evento(operador, "Autorização recusada",
                               f"Senha errada para {quem} na estação {estacao}")
    return None, motivo


# ------------------------------------------------------------------
# Códigos de recuperação do administrador (RN38)
# ------------------------------------------------------------------
CODIGO_INCORRETO = "Usuário ou código de recuperação incorretos."


def gerar_codigos_recuperacao(banco, usuario):
    """Gera os 8 códigos do administrador, grava só o hash de cada um
    (os anteriores deixam de valer) e devolve os códigos para mostrar UMA
    vez. Só o próprio administrador."""
    codigos = gerar_codigos()
    banco.salvar_codigos_recuperacao(
        usuario["id"], [gerar_hash(normalizar_codigo(c)) for c in codigos],
        autor=usuario["login"])
    return codigos


def gerar_novos_codigos(banco, usuario, senha_atual):
    """Menu da conta → "Gerar novos códigos": pede a senha atual.
    Devolve (códigos, "") ou (None, motivo)."""
    u = banco.buscar_usuario(usuario["login"])
    if u is None or not u["ativo"] or u["perfil"] != "admin":
        return None, "Só o administrador tem códigos de recuperação."
    if not conferir_senha(senha_atual or "", u["senha"]):
        return None, "A senha atual não confere."
    return gerar_codigos_recuperacao(banco, u), ""


def recuperar_senha(banco, login, codigo, nova, confirmacao, agora=None):
    """
    Login → "Esqueci a senha" (RN38): login + código de recuperação + nova
    senha. Devolve (ok, mensagem). O código certo é queimado (não serve de
    novo) e a senha nova vale na hora. Código errado conta como tentativa
    errada no MESMO bloqueio progressivo do login daquele usuário; com o
    login travado, nem o código certo passa. A senha nova é conferida antes
    (senha fraca não gasta código nem conta tentativa).
    """
    agora = agora or datetime.now()
    login = normalizar_login(login or "")
    if not login or not (codigo or "").strip():
        return False, "Informe o usuário e um código de recuperação."
    u = banco.buscar_usuario(login)
    chave = u["login"] if u else CHAVE_LOGIN_INEXISTENTE
    quem = u["login"] if u else LOGIN_INEXISTENTE
    falhas, bloqueios, bloqueado_ate = banco.ler_tentativas_login(chave)
    if bloqueado_ate is not None and bloqueado_ate > agora:
        restante = math.ceil((bloqueado_ate - agora).total_seconds())
        return False, f"Muitas tentativas erradas. Aguarde {restante} s."
    ok, msg = validar_senha(nova, confirmacao, login)
    if not ok:
        return False, msg
    normalizado = normalizar_codigo(codigo)
    if u is None or not normalizado:
        conferir_senha(normalizado or "-", hash_falso())   # mesmo tempo
    elif banco.usar_codigo_recuperacao(u["login"], normalizado,
                                       gerar_hash(nova)):
        return True, ("Senha redefinida com o código de recuperação, que não "
                      "vale mais. Entre com a senha nova.")
    return False, contar_erro_de_login(banco, chave, quem, falhas, bloqueios,
                                       agora, CODIGO_INCORRETO,
                                       acao="Recuperação de senha recusada")


def precisa_de_outro_admin(usuarios_cadastrados):
    """RN38: True se só existe 1 administrador ativo (a faixa do Painel
    pede um segundo: se ele perder a senha e os códigos, ninguém entra)."""
    return sum(1 for u in usuarios_cadastrados
               if u["perfil"] == "admin" and u["ativo"]) == 1


# ------------------------------------------------------------------
# Permissões (RN02: somente administrador exclui registros)
# ------------------------------------------------------------------
def eh_admin(usuario):
    return usuario is not None and usuario["perfil"] == "admin"


pode_excluir = eh_admin
pode_gerenciar_usuarios = eh_admin
# RN12 (2.3): desativar e reativar pessoa ou veículo (a mesma permissão
# que valia para bloquear e desbloquear: só o administrador)
pode_gerenciar_desativacoes = eh_admin


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


def pode_excluir_pessoa(usuario, visitas):
    """
    RN42 (2.3): (ok, mensagem) para excluir o cadastro de uma pessoa. Só o
    administrador, e só se ela nunca teve visita (cadastro feito por
    engano): o histórico da portaria não se apaga. Com visitas, o caminho
    é desativar (RN12).
    """
    if not eh_admin(usuario):
        return False, "Somente o administrador exclui o cadastro de pessoas."
    if visitas:
        vezes = "1 visita" if visitas == 1 else f"{visitas} visitas"
        return False, (f"Esta pessoa tem {vezes} no histórico e não pode ser "
                       "excluída: o histórico da portaria não se apaga.\n"
                       "Para impedir a entrada, use Desativar.")
    return True, ""


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
