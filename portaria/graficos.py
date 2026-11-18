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


def desenhar_barras_verticais(cv, itens, destaque=None, nome_destaque="Hoje"):
    """itens: lista de (rótulo, valor). A barra `destaque` (a última, se
    não vier) fica na cor da marca, com `nome_destaque` embaixo. Com muitas
    barras (30 dias, 24 horas) só a de destaque mostra o valor, e os
    rótulos vazios não são desenhados."""
    if _vazio(cv, itens):
        return
    destaque = len(itens) - 1 if destaque is None else destaque
    denso = len(itens) > 12
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
        hoje = n == destaque
        cor = COR["marca"] if hoje else COR["barra"]
        folga = 0.14 if denso else 0.22
        x0 = esq + n * largura + largura * folga
        x1 = esq + (n + 1) * largura - largura * folga
        altura = (base - topo) * valor / maximo if maximo else 0
        if altura >= px(2):
            r = px(2 if denso else 4)
            ret_arredondado(cv, x0, base - altura, x1, base, r, cor,
                            COR["superficie"])
            if altura > r:      # só o topo é arredondado
                cv.create_rectangle(x0, base - r, x1, base, fill=cor, width=0)
        if hoje or not denso:
            cv.create_text((x0 + x1) / 2, base - altura - px(10),
                           text=str(valor),
                           fill=COR["texto"] if hoje else COR["texto_2"],
                           font=FONTE["grafico_valor"])
        if denso and not hoje and abs(n - destaque) <= 1:
            rotulo = ""             # (não encosta no rótulo do destaque)
        cv.create_text((x0 + x1) / 2, base + px(15),
                       text=nome_destaque if hoje else rotulo,
                       fill=COR["texto"] if hoje else COR["texto_3"],
                       font=FONTE["rotulo"] if hoje else FONTE["grafico"])


def _sem_dados(cv, itens, aviso):
    """Como _vazio, com o aviso de cada painel (ex.: "Nenhuma encomenda
    neste período")."""
    cv.delete("all")
    if not itens or max(i[1] for i in itens) == 0:
        cv.create_text(cv.winfo_width() / 2, cv.winfo_height() / 2,
                       text=aviso, fill=COR["texto_3"], font=FONTE["corpo"])
        return True
    return False


def _medir(widget, texto, fonte):
    return int(widget.tk.call("font", "measure", fonte, texto))


def cortar_texto(widget, texto, fonte, largura):
    """O texto inteiro, se couber em `largura` px; senão, cortado com "…"."""
    if _medir(widget, texto, fonte) <= largura:
        return texto
    while texto and _medir(widget, texto + "…", fonte) > largura:
        texto = texto[:-1]
    return texto.rstrip() + "…" if texto else ""


def desenhar_colunas(cv, itens, destaque=None, nome_destaque="Hoje",
                     aviso=SEM_DADOS):
    """desenhar_barras_verticais com o aviso do painel quando não há dados."""
    if not _sem_dados(cv, itens, aviso):
        desenhar_barras_verticais(cv, itens, destaque, nome_destaque)


def desenhar_ranking(cv, itens, aviso=SEM_DADOS):
    """
    itens: lista de (nome, valor, texto de apoio), na ordem de cima para
    baixo, com barras de uma cor só. Com altura, cada linha tem o nome em
    cima da barra e o valor e o apoio à direita: cabe nome comprido
    ("Coordenação de Engenharia"). Na janela baixa, tudo numa linha só, com
    o nome cortado com "…" se não couber.
    """
    if _sem_dados(cv, itens, aviso):
        return
    w, h = cv.winfo_width(), cv.winfo_height()
    maximo = max(i[1] for i in itens)
    esq, dir_ = px(2), w - px(2)
    passo = min(h / len(itens), px(44))
    duas_linhas = passo >= px(30)
    espessura = px(8) if duas_linhas else min(px(10), max(passo - px(6), px(4)))
    rotulos = min(w * 0.38, px(170))          # (uma linha) coluna dos nomes
    for n, (nome, valor, extra) in enumerate(itens):
        if duas_linhas:
            texto = passo * n + (passo - px(28)) / 2 + px(8)
            barra = texto + px(12)
        else:
            texto = passo * n + passo / 2
            barra = texto - espessura / 2
        x = dir_
        if extra:
            cv.create_text(x, texto, text=extra, anchor="e",
                           fill=COR["texto_3"], font=FONTE["grafico"])
            x -= _medir(cv, extra, FONTE["grafico"]) + px(10)
        cv.create_text(x, texto, text=str(valor), anchor="e",
                       fill=COR["texto"], font=FONTE["grafico_valor"])
        x -= _medir(cv, str(valor), FONTE["grafico_valor"]) + px(12)
        largura_nome = (x if duas_linhas else rotulos) - esq - px(8)
        cv.create_text(esq, texto, anchor="w", fill=COR["texto_2"],
                       font=FONTE["grafico"],
                       text=cortar_texto(cv, nome, FONTE["grafico"],
                                         largura_nome))
        inicio, fim_ = (esq, dir_) if duas_linhas else (esq + rotulos, x)
        if fim_ - inicio < px(10):
            continue
        cv.create_rectangle(inicio, barra, fim_, barra + espessura,
                            fill=COR["superficie_2"], width=0)
        if valor:
            fim = inicio + max((fim_ - inicio) * valor / maximo, px(3))
            ret_arredondado(cv, inicio, barra, fim, barra + espessura, px(3),
                            COR["texto_2"], COR["superficie_2"])
