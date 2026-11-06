"""
Gera assets/portaria.ico (o símbolo da cancela, em vários tamanhos, para a
janela e para o .exe) e assets/logo_portaria.png (a Imagem/Logo do login: a
cancela vermelha numa placa branca).

Só é preciso rodar de novo se o símbolo mudar. Usa o Pillow (pip install
pillow), que NÃO é necessário para usar o programa.
"""

import os

from PIL import Image, ImageDraw

VERMELHO = (217, 0, 27, 255)       # COR["marca"] de estilo.py
BRANCO = (255, 255, 255, 255)
LADO = 256


def desenhar():
    img = Image.new("RGBA", (LADO, LADO), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, LADO - 8, LADO - 8), radius=52, fill=VERMELHO)
    # poste, base e braço da cancela
    d.rectangle((66, 70, 98, 196), fill=BRANCO)
    d.rectangle((52, 186, 118, 204), fill=BRANCO)
    d.rectangle((66, 70, 200, 112), fill=BRANCO)
    # faixas do braço (os quadradinhos vermelhos)
    for x in (118, 158):
        d.rectangle((x, 82, x + 22, 100), fill=VERMELHO)
    return img


def desenhar_logo(tamanho=72):
    """A cancela em vermelho sobre placa branca, para o painel vermelho.
    Desenhada em tamanho grande e reduzida: as bordas ficam suaves."""
    img = desenhar()
    pixels = img.load()
    for x in range(LADO):
        for y in range(LADO):
            r, g, b, a = pixels[x, y]
            if a:                       # troca o vermelho e o branco
                pixels[x, y] = (BRANCO[:3] + (a,)
                                if (r, g, b) == VERMELHO[:3]
                                else VERMELHO[:3] + (a,))
    return img.resize((tamanho, tamanho), Image.LANCZOS)


if __name__ == "__main__":
    pasta = os.path.dirname(os.path.abspath(__file__))
    desenhar_logo().save(os.path.join(pasta, "logo_portaria.png"))
    destino = os.path.join(pasta, "portaria.ico")
    desenhar().save(destino, sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                    (64, 64), (128, 128), (256, 256)])
    print("ícone salvo em", destino)
