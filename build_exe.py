"""
Gera o executável do Windows: dist/Portaria.exe (um arquivo só, sem console).

Precisa do PyInstaller (pip install pyinstaller) só para GERAR o .exe; quem
usa o .exe não precisa de Python. O programa em si continua só com a
biblioteca padrão.

    python build_exe.py

O banco (portaria.db), a pasta backups/ e o portaria.log ficam ao lado do
.exe, criados no primeiro uso (veja pasta_do_programa() em
portaria_universidade.py).
"""

import os
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
ICONE = os.path.join(RAIZ, "assets", "portaria.ico")


def main():
    try:
        import PyInstaller.__main__
    except ImportError:
        sys.exit("PyInstaller não encontrado. Instale com: pip install pyinstaller")

    os.chdir(RAIZ)
    PyInstaller.__main__.run([
        "portaria_universidade.py",
        "--name", "Portaria",
        "--onefile",
        "--windowed",                                   # sem a janela preta
        "--icon", ICONE,                                # ícone do arquivo .exe
        "--add-data", f"{ICONE}{os.pathsep}assets",     # ícone da janela
        "--clean",
        "--noconfirm",
    ])
    print("\nPronto: dist/Portaria.exe")


if __name__ == "__main__":
    main()
