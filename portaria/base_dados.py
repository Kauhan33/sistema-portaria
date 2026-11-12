"""
O que o banco (dados.py) e os módulos dele (dados_modulos.py) usam em comum:
o erro com a mensagem para o usuário e as datas no formato ISO do banco.
Fica num arquivo próprio para os dois poderem importar sem depender um do
outro.
"""

from datetime import datetime

from .validacao import FORMATO

FORMATO_ISO = "%Y-%m-%d %H:%M"
FORMATO_ISO_SEGUNDOS = "%Y-%m-%d %H:%M:%S"


class ErroDados(Exception):
    """
    Falha ao ler ou gravar os registros. A mensagem (str) é para o usuário;
    o erro técnico do SQLite, quando houver, fica em `detalhe` e no log.
    """

    def __init__(self, mensagem, detalhe=""):
        super().__init__(mensagem)
        self.detalhe = detalhe


def para_iso(texto):
    """Formato da tela → ISO. Usa strptime de propósito: também valida."""
    return datetime.strptime(texto, FORMATO).strftime(FORMATO_ISO) if texto else ""


def de_iso(texto):
    """ISO → formato da tela, fatiando o texto (19x mais rápido que strptime;
    roda em toda linha das listagens)."""
    if not texto:
        return ""
    if len(texto) != 16:
        return datetime.strptime(texto, FORMATO_ISO).strftime(FORMATO)
    return f"{texto[8:10]}/{texto[5:7]}/{texto[:4]} {texto[11:16]}"
