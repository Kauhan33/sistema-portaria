"""
Gera o instalador do Windows: dist/Instalar_Portaria_<versão>.exe

    python build_instalador.py

1. Gera o dist/Portaria.exe (build_exe.py, com o PyInstaller).
2. Compila instalador/portaria.iss com o Inno Setup 6 (ISCC.exe).

Só quem GERA o instalador precisa do PyInstaller e do Inno Setup
(winget install JRSoftware.InnoSetup). Quem instala não precisa de nada.
"""

import os
import shutil
import subprocess
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)
from portaria import VERSAO  # noqa: E402

LOCAIS_ISCC = [
    os.environ.get("ISCC", ""),
    shutil.which("ISCC.exe") or "",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6",
                 "ISCC.exe"),
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]


def achar_iscc():
    for caminho in LOCAIS_ISCC:
        if caminho and os.path.isfile(caminho):
            return caminho
    sys.exit("Inno Setup 6 não encontrado. Instale com: "
             "winget install JRSoftware.InnoSetup")


def main():
    iscc = achar_iscc()
    subprocess.run([sys.executable, os.path.join(RAIZ, "build_exe.py")],
                   check=True)
    subprocess.run([iscc, f"/DVersao={VERSAO}", f"/DRaiz={RAIZ}",
                    os.path.join(RAIZ, "instalador", "portaria.iss")],
                   check=True)
    print(f"\nPronto: dist/Instalar_Portaria_{VERSAO}.exe")


if __name__ == "__main__":
    main()
