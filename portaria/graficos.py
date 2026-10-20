"""
Gráficos de barras desenhados num Canvas do Tkinter (sem biblioteca extra).
Usados pelo Painel; cada função apaga o Canvas e desenha de novo.

Disciplina de cor (sistema Guarita): uma cor só nas barras e um único
destaque — o dia de hoje em vermelho UNA. O título fica no cartão, fora
do Canvas.
"""

from .componentes import ret_arredondado
from .estilo import COR, FONTE, px

SEM_DADOS = "Sem entradas neste período"


def _vazio(cv, itens):
    """Apaga; sem dados, escreve o aviso no meio e devolve True."""
    cv.delete("all")
    if not itens or max(i[1] for i in itens) == 0:
        cv.create_text(cv.winfo_width() / 2, cv.winfo_height() / 2,
                       text=SEM_DADOS, fill=COR["texto_3"], font=FONTE["corpo"])
        return True
    return False


def desenhar_barras_horizontais(cv, itens):
    """itens: lista de (rótulo, valor, texto à direita). Barras de uma cor."""
    if _vazio(cv, itens):
        return
    w, h = cv.winfo_width(), cv.winfo_height()
    maximo = max(i[1] for i in itens)
    esq, dir_ = px(104), px(150)
    area = max(w - esq - dir_, px(10))
    passo = min(h / len(itens), px(40))
    espessura = px(12)
    for n, (rotulo, valor, extra) in enumerate(itens):
        meio = passo * n + passo / 2
        comprimento = max(area * valor / maximo, px(3)) if valor else 0
        cv.create_text(esq - px(12), meio, text=rotulo, anchor="e",
                       fill=COR["texto_2"], font=FONTE["grafico"])
        cv.create_rectangle(esq, meio - espessura / 2, esq + area,
                            meio + espessura / 2, fill=COR["superficie_2"],
                            width=0)
        if comprimento:
            ret_arredondado(cv, esq, meio - espessura / 2, esq + comprimento,
                            meio + espessura / 2, px(3), COR["texto_2"],
                            COR["superficie_2"])
        cv.create_text(esq + area + px(12), meio, text=str(valor), anchor="w",
                       fill=COR["texto"], font=FONTE["grafico_valor"])
        cv.create_text(esq + area + px(40), meio, text=extra, anchor="w",
                       fill=COR["texto_3"], font=FONTE["grafico"])


def desenhar_barras_verticais(cv, itens):
    """itens: lista de (rótulo, valor); o último (hoje) fica em destaque."""
    if _vazio(cv, itens):
        return
    w, h = cv.winfo_width(), cv.winfo_height()
    maximo = max(v for _, v in itens)
    esq, topo, base = px(8), px(22), h - px(30)
    # linhas de grade claras (metade e topo); o valor vai em cima da barra
    for fracao in (0.5, 1.0):
        y = base - (base - topo) * fracao
        cv.create_line(esq, y, w - esq, y, fill=COR["borda"])
    cv.create_line(esq, base, w - esq, base, fill=COR["borda_campo"])
    largura = (w - 2 * esq) / len(itens)
    for n, (rotulo, valor) in enumerate(itens):
        hoje = n == len(itens) - 1
        cor = COR["marca"] if hoje else COR["barra"]
        x0 = esq + n * largura + largura * 0.22
        x1 = esq + (n + 1) * largura - largura * 0.22
        altura = (base - topo) * valor / maximo
        if altura >= px(2):
            r = px(4)
            ret_arredondado(cv, x0, base - altura, x1, base, r, cor,
                            COR["superficie"])
            if altura > r:      # só o topo é arredondado
                cv.create_rectangle(x0, base - r, x1, base, fill=cor, width=0)
        cv.create_text((x0 + x1) / 2, base - altura - px(10), text=str(valor),
                       fill=COR["texto"] if hoje else COR["texto_2"],
                       font=FONTE["grafico_valor"])
        cv.create_text((x0 + x1) / 2, base + px(15),
                       text="Hoje" if hoje else rotulo,
                       fill=COR["texto"] if hoje else COR["texto_3"],
                       font=FONTE["rotulo"] if hoje else FONTE["grafico"])
