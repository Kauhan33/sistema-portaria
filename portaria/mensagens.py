"""
Caixas de mensagem do sistema. Todas as telas passam por aqui, e não pelo
messagebox direto: se um dia as caixas virarem avisos dentro da própria
tela, muda-se só este arquivo. Nos testes, um único patch neste módulo
troca todas as caixas por falsas (assim nenhuma janela trava o teste).

`parent` é a janela "dona" da caixa (ex.: a janela Corrigir); sem ele, a
caixa aparece sobre a janela principal.
"""

from tkinter import filedialog, messagebox


def _dono(parent):
    return {"parent": parent} if parent is not None else {}


def erro(titulo, texto, parent=None):
    messagebox.showerror(titulo, texto, **_dono(parent))


def aviso(titulo, texto, parent=None):
    messagebox.showwarning(titulo, texto, **_dono(parent))


def info(titulo, texto, parent=None):
    messagebox.showinfo(titulo, texto, **_dono(parent))


def confirmar(titulo, texto, parent=None):
    """Pergunta Sim/Não; devolve True se a resposta for Sim."""
    return messagebox.askyesno(titulo, texto, **_dono(parent))


def salvar_como(titulo, nome_inicial, parent=None):
    """Diálogo "Salvar como" de planilha CSV; devolve o caminho ou "" se
    cancelar."""
    return filedialog.asksaveasfilename(
        title=titulo, initialfile=nome_inicial, defaultextension=".csv",
        filetypes=[("Planilha (CSV)", "*.csv")], **_dono(parent)) or ""
