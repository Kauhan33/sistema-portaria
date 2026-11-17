"""
Gera assets/portaria.ico (o símbolo da cancela, em vários tamanhos, para a
janela e para o .exe) e assets/logo_portaria.png (a Imagem/Logo do login: a
cancela vermelha numa placa branca).

3.5: o símbolo "Cancela suave" (a mesma ideia de antes, poste e braço
listrado, redesenhada com volumes arredondados: base, poste, eixo com
parafuso e o braço erguido, com listras inclinadas). As medidas estão numa
grade de 256 x 256 unidades, as mesmas de marca_cancela em
portaria/componentes.py (a barra lateral, desenhada pelo próprio programa).
Em 16 px o braço fica na horizontal e as listras viram cortes retos, na
grade de pixels, para continuar nítido na barra de tarefas.

Cada tamanho é desenhado em alta resolução (no mínimo 1024 px) e reduzido
com filtro BOX: bordas suaves, sem serrilhado.

Só é preciso rodar de novo se o símbolo mudar. Usa o Pillow (pip install
pillow), que NÃO é necessário para usar o programa.
"""

import math
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter

VERMELHO = (217, 0, 27)          # COR["marca"] de estilo.py
VERMELHO_TOPO = (230, 22, 46)    # esmalte: um pouco mais claro em cima
VERMELHO_BASE = (196, 0, 24)     # e um pouco mais escuro embaixo
BRANCO = (255, 255, 255)
TAMANHOS_DO_ICONE = (16, 24, 32, 48, 64, 128, 256)
LADO_DO_LOGO = 72


# ----------------------------------------------------------------- formas
def ret(x0, y0, x1, y1, r=0, n=24):
    """Retângulo de cantos arredondados; r é um número ou uma tupla
    (sup-esq, sup-dir, inf-dir, inf-esq)."""
    if not isinstance(r, (tuple, list)):
        r = (r, r, r, r)
    cantos = [((x0 + r[0], y0 + r[0]), r[0], 180),
              ((x1 - r[1], y0 + r[1]), r[1], 270),
              ((x1 - r[2], y1 - r[2]), r[2], 0),
              ((x0 + r[3], y1 - r[3]), r[3], 90)]
    pts = []
    for (cx, cy), raio, ini in cantos:
        if raio <= 0:
            pts.append((cx, cy))
            continue
        for i in range(n + 1):
            a = math.radians(ini + 90 * i / n)
            pts.append((cx + raio * math.cos(a), cy + raio * math.sin(a)))
    return pts


def circulo(cx, cy, r, n=160):
    return [(cx + r * math.cos(2 * math.pi * i / n),
             cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def girar(pts, cx, cy, graus):
    a = math.radians(graus)
    c, s = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * c - (y - cy) * s,
             cy + (x - cx) * s + (y - cy) * c) for x, y in pts]


def listra(x, topo, base, largura, inclinacao):
    """Listra inclinada (paralelogramo) entre as alturas topo e base."""
    return [(x, topo), (x + largura, topo),
            (x + largura + inclinacao, base), (x + inclinacao, base)]


# ----------------------------------------------------------------- folha
class Folha:
    """Folha de `px` pixels, desenhada em unidades (0..256) e em alta
    resolução. Em 48 px ou mais, uma margem de 8 unidades em volta."""

    def __init__(self, px):
        self.px = px
        self.W = px * max(4, -(-1024 // px))
        margem = 8 if px >= 48 else 0
        self.k = self.W / 256 * (256 - 2 * margem) / 256
        self.off = margem * self.W / 256
        self.img = Image.new("RGBA", (self.W, self.W), (0, 0, 0, 0))
        self.detalhe = "g" if px >= 48 else ("m" if px >= 24 else "p")

    def mascara(self, *formas):
        m = Image.new("L", (self.W, self.W), 0)
        d = ImageDraw.Draw(m)
        for f in formas:
            d.polygon([(self.off + x * self.k, self.off + y * self.k)
                       for x, y in f], fill=255)
        return m

    @staticmethod
    def uniao(*ms):
        r = ms[0]
        for m in ms[1:]:
            r = ImageChops.lighter(r, m)
        return r

    def pintar(self, m, cor, opacidade=1.0):
        camada = Image.new("RGBA", (self.W, self.W), cor + (255,))
        if opacidade < 1:
            m = m.point(lambda v: int(v * opacidade))
        camada.putalpha(m)
        self.img = Image.alpha_composite(self.img, camada)

    def esmalte(self, m):
        """A placa vermelha com um gradiente vertical discreto."""
        a, b = self.off, self.off + 256 * self.k
        col = Image.new("RGBA", (1, self.W))
        for y in range(self.W):
            t = min(1, max(0, (y - a) / max(1, b - a)))
            col.putpixel((0, y), tuple(
                int(VERMELHO_TOPO[i] + (VERMELHO_BASE[i] - VERMELHO_TOPO[i]) * t)
                for i in range(3)) + (255,))
        camada = col.resize((self.W, self.W))
        camada.putalpha(m)
        self.img = Image.alpha_composite(self.img, camada)

    def sombra(self, m, limite):
        """Sombra curta e suave do desenho branco, só dentro da placa."""
        s = ImageChops.offset(m, 0, int(6 * self.k))
        s = s.filter(ImageFilter.GaussianBlur(7 * self.k))
        self.pintar(ImageChops.multiply(s, limite), (90, 0, 12), 0.35)

    def pronta(self):
        p = self.img.convert("RGBa").resize((self.px, self.px), Image.BOX)
        return p.convert("RGBA")


# ---------------------------------------------------------------- desenho
def desenhar(f, inverso=False):
    """Placa vermelha e cancela branca; inverso: placa branca e cancela
    vermelha (o logo do login)."""
    placa = f.mascara(ret(0, 0, 256, 256, 56))
    if inverso:
        f.pintar(placa, BRANCO)
        traco = VERMELHO
    else:
        f.esmalte(placa)
        traco = BRANCO
    if f.detalhe == "p":            # 16 px: grade de 16 unidades = 1 pixel
        corpo = f.uniao(
            f.mascara(ret(32, 192, 96, 214, 6)),                  # base
            f.mascara(ret(48, 96, 80, 200, 0)),                   # poste
            f.mascara(circulo(64, 96, 32)),                       # eixo
            f.mascara(ret(64, 80, 236, 112, (0, 16, 16, 0))))     # braço
        cortes = f.mascara(ret(128, 80, 144, 112), ret(176, 80, 192, 112))
        f.pintar(ImageChops.subtract(corpo, cortes), traco)
        return
    angulo = -12 if f.detalhe == "g" else 0
    cx, cy, meia = 72, 96, 18
    braco = girar(ret(cx, cy - meia, 230, cy + meia, (0, meia, meia, 0)),
                  cx, cy, angulo)
    corpo = f.uniao(
        f.mascara(ret(36, 192, 108, 212, 10)),                    # base
        f.mascara(ret(58, 100, 86, 200, 0)),                      # poste
        f.mascara(braco),
        f.mascara(circulo(cx, cy, 30)))                           # eixo
    faixas = [listra(x, cy - meia - 2, cy + meia + 2, 18, -16)
              for x in (124, 166, 208)]
    cortes = f.uniao(
        f.mascara(*[girar(p, cx, cy, angulo) for p in faixas]),
        f.mascara(circulo(cx, cy, 10)))                           # parafuso
    corpo = ImageChops.subtract(corpo, cortes)
    if f.detalhe == "g" and not inverso:
        f.sombra(corpo, placa)
    f.pintar(corpo, traco)


def renderizar(px, inverso=False):
    f = Folha(px)
    desenhar(f, inverso)
    return f.pronta()


if __name__ == "__main__":
    pasta = os.path.dirname(os.path.abspath(__file__))
    renderizar(LADO_DO_LOGO, inverso=True).save(
        os.path.join(pasta, "logo_portaria.png"))
    imagens = {t: renderizar(t) for t in TAMANHOS_DO_ICONE}
    destino = os.path.join(pasta, "portaria.ico")
    imagens[256].save(destino, sizes=[(t, t) for t in TAMANHOS_DO_ICONE],
                      append_images=[imagens[t] for t in TAMANHOS_DO_ICONE[:-1]])
    print("ícone salvo em", destino)
