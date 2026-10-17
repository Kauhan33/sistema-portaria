"""Cores, fontes e o botão padrão, usados por todas as telas."""

import tkinter as tk

FUNDO = "#f4f6fa"
VERMELHO = "#d9001b"
BORDA = "#dde1ea"

fonte_lbl = ("Segoe UI", 10, "bold")
fonte_dica = ("Segoe UI", 8)


def botao(pai, texto, cor, comando, lado="left"):
    b = tk.Button(pai, text=texto, bg=cor, fg="white", activebackground=cor,
                  activeforeground="white", relief="flat", cursor="hand2",
                  font=("Segoe UI", 10, "bold"), padx=14, pady=6,
                  command=comando)
    b.pack(side=lado, padx=(0, 8))
    return b


def cartao(pai):
    """Caixa branca com borda e faixa vermelha no topo; devolve (caixa, miolo)."""
    caixa = tk.Frame(pai, bg="white", highlightbackground=BORDA,
                     highlightthickness=1)
    tk.Frame(caixa, bg=VERMELHO, height=4).pack(fill="x")
    miolo = tk.Frame(caixa, bg="white")
    miolo.pack(fill="both", expand=True, padx=24, pady=(16, 20))
    return caixa, miolo
