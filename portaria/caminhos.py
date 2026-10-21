"""
Onde o programa guarda os dados (banco, backups e log).

- Instalado: o instalador grava `instalado.ini` ao lado do Portaria.exe
  ([Portaria] dados=C:\\ProgramData\\Portaria). A pasta do programa
  (Arquivos de Programas) é protegida contra gravação pelo Windows, por
  isso os dados ficam nessa outra pasta, compartilhada por todos os
  usuários do computador.
- Portátil (o .exe sem o .ini, ex.: num pendrive) ou rodando pelo código:
  os dados ficam ao lado do programa, como sempre foi.
"""

import configparser
import os
import sys

ARQUIVO_INSTALACAO = "instalado.ini"


def pasta_do_programa():
    """Pasta do Portaria.exe ou, rodando pelo código, a raiz do projeto."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pasta_do_ini(pasta):
    ini = os.path.join(pasta, ARQUIVO_INSTALACAO)
    if not os.path.isfile(ini):
        return ""
    # sem interpolação: o "%" de %LOCALAPPDATA% é do Windows, não do .ini
    leitor = configparser.ConfigParser(interpolation=None)
    try:
        leitor.read(ini, encoding="utf-8")
        return os.path.expandvars(leitor.get("Portaria", "dados",
                                             fallback="").strip())
    except (configparser.Error, UnicodeDecodeError):
        return ""


def pasta_de_dados(pasta=None):
    """
    Pasta onde ficam portaria.db, backups/ e portaria.log. Se a pasta do
    instalador não puder ser criada, usa a pasta de dados do usuário do
    Windows (%LOCALAPPDATA%\\Portaria) para o programa não deixar de abrir.
    """
    pasta = pasta or pasta_do_programa()
    destino = _pasta_do_ini(pasta)
    if not destino:
        return pasta
    try:
        os.makedirs(destino, exist_ok=True)
        return destino
    except OSError:
        reserva = os.path.join(os.environ.get("LOCALAPPDATA", pasta), "Portaria")
        os.makedirs(reserva, exist_ok=True)
        return reserva
