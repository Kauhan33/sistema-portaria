"""
Gráficos de barras desenhados num Canvas do Tkinter (sem biblioteca extra).
Usados pela aba Dashboard; cada função apaga o Canvas e desenha de novo.
"""

from .estilo import COR, FONTE

SEM_DADOS = "Sem dados ainda"


def _titulo_e_vazio(cv, titulo, vazio):
    """Desenha o título; se não houver dados, avisa no meio e devolve True."""
    cv.delete("all")
    cv.create_text(14, 18, text=titulo, anchor="w", fill=COR["texto"],
                   font=FONTE["titulo_secao"])
    if vazio:
        cv.create_text(cv.winfo_width() / 2, cv.winfo_height() / 2,
                       text=SEM_DADOS, fill=COR["texto_vazio"],
                       font=FONTE["corpo"])
    return vazio


def desenhar_barras_horizontais(cv, titulo, itens):
    """itens: lista de (rótulo, valor, texto à direita, cor)."""
    if _titulo_e_vazio(cv, titulo, not itens or max(i[1] for i in itens) == 0):
        return
    w, h = cv.winfo_width(), cv.winfo_height()
    maximo = max(i[1] for i in itens)
    esq, dir_, topo = 130, 190, 42
    area = max(w - esq - dir_, 10)
    passo = (h - topo - 10) / len(itens)
    for i, (rotulo, valor, extra, cor) in enumerate(itens):
        y = topo + i * passo
        comprimento = area * valor / maximo
        cv.create_text(esq - 8, y + passo / 2, text=rotulo, anchor="e",
                       fill=COR["texto_2"], font=FONTE["legenda"])
        cv.create_rectangle(esq, y + passo * 0.2, esq + max(comprimento, 2),
                            y + passo * 0.8, fill=cor, outline="")
        cv.create_text(esq + comprimento + 8, y + passo / 2, text=extra,
                       anchor="w", fill=COR["texto_status"],
                       font=FONTE["rotulo"])


def desenhar_barras_verticais(cv, titulo, itens, cor):
    """itens: lista de (rótulo, valor)."""
    if _titulo_e_vazio(cv, titulo, not itens or max(v for _, v in itens) == 0):
        return
    w, h = cv.winfo_width(), cv.winfo_height()
    maximo = max(v for _, v in itens)
    esq, topo, base = 20, 56, h - 30
    largura = max((w - 2 * esq) / len(itens), 10)
    cv.create_line(esq, base, w - esq, base, fill=COR["linha_grafico"])
    for i, (rotulo, valor) in enumerate(itens):
        x0 = esq + i * largura + largura * 0.2
        x1 = esq + (i + 1) * largura - largura * 0.2
        altura = (base - topo) * valor / maximo
        cv.create_rectangle(x0, base - altura, x1, base, fill=cor, outline="")
        cv.create_text((x0 + x1) / 2, base - altura - 9, text=str(valor),
                       fill=COR["texto_status"], font=FONTE["rotulo"])
        cv.create_text((x0 + x1) / 2, base + 14, text=rotulo,
                       fill=COR["texto_rotulo"], font=FONTE["dica"])
