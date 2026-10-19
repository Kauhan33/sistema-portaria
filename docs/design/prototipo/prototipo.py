"""
Protótipo do novo visual do Sistema de Portaria — telas Cadastro e Login.
Só biblioteca padrão (tkinter, ctypes). Dados falsos, sem usar o projeto.

Uso:
    python prototipo.py                 # abre o Cadastro (nítido, DPI aware)
    python prototipo.py login           # abre o Login
    python prototipo.py cadastro --foto saida.png [--estado campus|ok|bloqueado|novo]
    python prototipo.py cadastro --borrado   # sem DPI aware (como o app atual)
"""

import ctypes
import sys
import tkinter as tk
from datetime import datetime

import componentes as c
from componentes import COR, ICONE, px

ARGS = sys.argv[1:]
TELA = next((a for a in ARGS if a in ("cadastro", "login")), "cadastro")
FOTO = ARGS[ARGS.index("--foto") + 1] if "--foto" in ARGS else None
ESTADO = ARGS[ARGS.index("--estado") + 1] if "--estado" in ARGS else "campus"
NITIDO = "--borrado" not in ARGS

if NITIDO:
    c.ligar_nitidez()

AGORA = datetime(2026, 10, 19, 19, 14)
DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
DATA_EXTENSO = f"{DIAS[AGORA.weekday()]}, {AGORA.day} de {MESES[AGORA.month - 1]}"

REGISTROS = [  # nome, cpf, celular, placa, tipo, entrada, saída
    ("Carlos Andrade", "111.444.777-35", "(31) 93333-4444", "QWE-1234",
     "Professor", "19/10/2026 17:14", ""),
    ("Mariana Souza", "390.533.447-05", "(31) 98765-1234", "—", "Aluno",
     "19/10/2026 18:14", ""),
    ("Bruno Teixeira", "714.602.380-01", "(31) 99654-0021", "RTA5B21",
     "Prestador de serviço", "19/10/2026 16:40", "19/10/2026 18:02"),
    ("Mariana Souza", "390.533.447-05", "(31) 98765-1234", "—", "Aluno",
     "18/10/2026 16:14", "18/10/2026 19:14"),
    ("João Pereira", "529.982.247-25", "(31) 99111-2222", "BRA2E19",
     "Visitante", "17/10/2026 14:14", "17/10/2026 16:14"),
    ("Ana Ribeiro", "529.982.247-25", "(31) 99111-2222", "—", "Funcionário",
     "16/10/2026 15:14", "16/10/2026 20:14"),
    ("Rafael Costa", "111.444.777-35", "(31) 93333-4444", "HJK4F56",
     "Entregador", "15/10/2026 17:14", "15/10/2026 18:14"),
    ("Lúcia Martins", "052.311.870-44", "(31) 98222-7310", "—", "Aluno",
     "15/10/2026 08:02", "15/10/2026 12:30"),
]

FICHAS = {
    "campus": dict(cpf="39053344705", nome="Mariana Souza", celular="31987651234",
                   placa="", tipo="Aluno", visitas="7", ultima="18/10/2026 19:14",
                   aviso=("alerta", "Mariana está no campus desde 18:14. "
                          "Registre a saída antes.",
                          ICONE["alerta"], "Registrar saída")),
    "ok": dict(cpf="11144477735", nome="Carlos Andrade", celular="31933334444",
               placa="QWE1E34", tipo="Professor", visitas="23",
               ultima="16/10/2026 07:52",
               aviso=("sucesso", "Já cadastrado. Confira os dados e registre "
                      "a entrada.",
                      ICONE["ok"], None)),
    "bloqueado": dict(cpf="52998224725", nome="Ana Ribeiro", celular="31991112222",
                      placa="BRA2E19", tipo="Funcionário", visitas="2",
                      ultima="17/10/2026 14:14",
                      aviso=("erro", "CPF bloqueado: comportamento agressivo. "
                             "A entrada será recusada.",
                             ICONE["erro"], "Ver bloqueio")),
    "novo": dict(cpf="", nome="", celular="", placa="", tipo="", visitas="—",
                 ultima="—",
                 aviso=("neutro", "Digite o CPF primeiro: quem já veio tem os "
                        "dados preenchidos.", ICONE["info"], None)),
}


# ----------------------------------------------------------------------
class Prototipo:
    def __init__(self):
        self.raiz = tk.Tk()
        self.raiz.title("Portaria da Universidade")
        self.raiz.configure(bg=COR["fundo"])
        self.raiz.geometry(f"{px(1180)}x{px(760)}+0+0")
        self.f = c.Fontes()
        c.aplicar_estilo_ttk(self.raiz, self.f)
        if TELA == "login":
            self.montar_login()
        else:
            self.montar_principal()

    # ------------------------------------------------------------------
    # Moldura: barra lateral + área de conteúdo
    # ------------------------------------------------------------------
    def montar_principal(self):
        f = self.f
        lateral = tk.Frame(self.raiz, bg=COR["lateral"], width=px(232))
        lateral.pack(side="left", fill="y")
        lateral.pack_propagate(False)
        tk.Frame(self.raiz, bg=COR["borda"], width=1).pack(side="left", fill="y")

        marca = tk.Frame(lateral, bg=COR["lateral"])
        marca.pack(fill="x", padx=px(16), pady=(px(20), px(24)))
        c.marca_cancela(marca, COR["lateral"]).pack(side="left")
        txt = tk.Frame(marca, bg=COR["lateral"])
        txt.pack(side="left", padx=(px(12), 0))
        tk.Label(txt, text="Portaria", font=(f.titulo_cartao[0], 13),
                 bg=COR["lateral"], fg=COR["texto"]).pack(anchor="w")
        tk.Label(txt, text="Universidade", font=f.dica, bg=COR["lateral"],
                 fg=COR["texto_3"]).pack(anchor="w")

        menu = tk.Frame(lateral, bg=COR["lateral"])
        menu.pack(fill="x", padx=px(10))
        for texto, ico, ativo, cont in [
                ("Entrada e saída", "entrada", True, None),
                ("Pessoas", "pessoas", False, "128"),
                ("Bloqueios", "bloqueio", False, "2"),
                ("Painel", "painel", False, None),
                ("Usuários", "usuarios", False, None)]:
            c.ItemMenu(menu, f, texto, ICONE[ico], ativo, cont).pack(fill="x")

        # usuário logado no rodapé da barra lateral
        rodape = tk.Frame(lateral, bg=COR["lateral"])
        rodape.pack(side="bottom", fill="x", padx=px(16), pady=px(16))
        tk.Frame(lateral, bg=COR["borda"], height=1).pack(side="bottom", fill="x",
                                                          padx=px(16))
        c.circulo_iniciais(rodape, f, "CD", COR["lateral"]).pack(side="left")
        quem = tk.Frame(rodape, bg=COR["lateral"])
        quem.pack(side="left", padx=(px(10), 0))
        tk.Label(quem, text="Carla Dias", font=f.corpo_semi, bg=COR["lateral"],
                 fg=COR["texto"]).pack(anchor="w")
        tk.Label(quem, text="Administrador", font=f.dica, bg=COR["lateral"],
                 fg=COR["texto_3"]).pack(anchor="w")
        sair = tk.Label(rodape, text=ICONE["sair"], font=f.icone(12),
                        bg=COR["lateral"], fg=COR["texto_2"], cursor="hand2")
        sair.pack(side="right")

        self.conteudo = tk.Frame(self.raiz, bg=COR["fundo"])
        self.conteudo.pack(side="left", fill="both", expand=True)
        self.montar_cadastro()

    # ------------------------------------------------------------------
    # Tela Entrada e saída (antiga aba Cadastro)
    # ------------------------------------------------------------------
    def montar_cadastro(self):
        f, area = self.f, self.conteudo
        G = px(24)  # margem da página

        # Cabeçalho da página
        topo = tk.Frame(area, bg=COR["fundo"])
        topo.pack(fill="x", padx=G, pady=(px(20), px(16)))
        titulos = tk.Frame(topo, bg=COR["fundo"])
        titulos.pack(side="left")
        tk.Label(titulos, text="Entrada e saída", font=f.titulo_pagina,
                 bg=COR["fundo"], fg=COR["texto"]).pack(anchor="w")
        linha = tk.Frame(titulos, bg=COR["fundo"])
        linha.pack(anchor="w")
        tk.Label(linha, text=DATA_EXTENSO.capitalize() + "  ·  ", font=f.corpo,
                 bg=COR["fundo"], fg=COR["texto_2"]).pack(side="left")
        tk.Label(linha, text="2 pessoas no campus agora", font=f.corpo_semi,
                 bg=COR["fundo"], fg=COR["sucesso"][0]).pack(side="left")

        rapida = tk.Frame(topo, bg=COR["fundo"])
        rapida.pack(side="right", anchor="s")
        tk.Label(rapida, text="Saída rápida (F2)", font=f.rotulo,
                 bg=COR["fundo"], fg=COR["texto_2"]).pack(anchor="w",
                                                          pady=(0, px(4)))
        lin = tk.Frame(rapida, bg=COR["fundo"])
        lin.pack()
        campo = c.Campo(lin, f, fundo_pai=COR["fundo"], largura=230,
                        icone=ICONE["busca"])
        campo.pack(side="left")
        campo.entrada.insert(0, "CPF ou placa")
        campo.entrada.config(fg=COR["texto_3"])
        c.Botao(lin, "Registrar saída", variante="secundario", fontes=f,
                fundo_pai=COR["fundo"], dica_tecla="Enter").pack(side="left",
                                                                 padx=(px(8), 0))

        # Cartão "Nova entrada": formulário + ficha da pessoa
        ficha = FICHAS[ESTADO]
        cartao = c.Cartao(area, COR["fundo"], pad=18)
        cartao.pack(fill="x", padx=G)
        m = cartao.miolo
        cab = tk.Frame(m, bg=COR["superficie"])
        cab.pack(fill="x", pady=(0, px(10)))
        tk.Label(cab, text="Nova entrada", font=f.titulo_cartao,
                 bg=COR["superficie"], fg=COR["texto"]).pack(side="left")
        c.Botao(cab, "Limpar formulário", variante="fantasma", fontes=f,
                altura=30).pack(side="right")

        corpo = tk.Frame(m, bg=COR["superficie"])
        corpo.pack(fill="x")
        lado = tk.Frame(corpo, bg=COR["superficie"])
        lado.pack(side="right", fill="y")
        tk.Frame(corpo, bg=COR["borda"], width=1).pack(side="right", fill="y",
                                                       padx=px(20))
        form = tk.Frame(corpo, bg=COR["superficie"])
        form.pack(side="left", fill="x", expand=True)
        form.columnconfigure((0, 1, 2), weight=1, uniform="f")

        def rotulo(texto, l, col, apoio=""):
            fr = tk.Frame(form, bg=COR["superficie"])
            fr.grid(row=l, column=col, sticky="w", pady=(0, px(4)))
            tk.Label(fr, text=texto, font=f.rotulo, bg=COR["superficie"],
                     fg=COR["texto"]).pack(side="left")
            if apoio:
                tk.Label(fr, text="  " + apoio, font=f.dica, bg=COR["superficie"],
                         fg=COR["texto_3"]).pack(side="left")

        def campo_(l, col, span=1, valor="", **kw):
            cp = c.Campo(form, f, **kw)
            cp.grid(row=l, column=col, columnspan=span, sticky="ew",
                    padx=(0, px(12) if col + span < 3 else 0))
            if valor:
                if kw.get("widget") == "combo":
                    cp.entrada.set(valor)
                else:
                    cp.entrada.insert(0, valor)
            return cp

        def dica(texto, l, col, span=1):
            tk.Label(form, text=texto, font=f.dica, bg=COR["superficie"],
                     fg=COR["texto_3"]).grid(row=l, column=col, columnspan=span,
                                             sticky="w", pady=(px(4), 0))

        rotulo("CPF", 0, 0)
        rotulo("Nome completo", 0, 1)
        self.cpf = campo_(1, 0, valor=ficha["cpf"])
        campo_(1, 1, span=2, valor=ficha["nome"])

        aviso = c.Aviso(form, f)
        aviso.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(px(10), px(14)))
        aviso.mostrar(*ficha["aviso"])

        rotulo("Celular com DDD", 3, 0, "só números")
        rotulo("Placa", 3, 1, "opcional")
        rotulo("Tipo de acesso", 3, 2)
        campo_(4, 0, valor=ficha["celular"])
        campo_(4, 1, valor=ficha["placa"])
        campo_(4, 2, widget="combo", valor=ficha["tipo"], state="readonly",
               values=list(c.CORES_TIPO))

        rotulo("Entrada", 6, 0, "dd/mm/aaaa hh:mm")
        rotulo("Saída", 6, 1, "vazio = no campus")
        form.grid_rowconfigure(6, pad=px(14))
        campo_(7, 0, valor="19/10/2026 19:14", icone=ICONE["relogio"])
        campo_(7, 1, icone=ICONE["relogio"])

        c.Botao(form, "Registrar entrada", variante="primario", fontes=f,
                dica_tecla="Enter").grid(row=7, column=2, sticky="ew")

        # Ficha da pessoa (coluna direita)
        tk.Label(lado, text="Veículo", font=f.rotulo, bg=COR["superficie"],
                 fg=COR["texto"]).pack(anchor="w", pady=(0, px(6)))
        placa = c.Placa(lado, f, COR["superficie"], largura=200)
        placa.pack(anchor="w")
        placa.mostrar(ficha["placa"])
        tk.Frame(lado, bg=COR["borda"], height=1).pack(fill="x", pady=px(16))
        tk.Label(lado, text="Histórico da pessoa", font=f.rotulo,
                 bg=COR["superficie"], fg=COR["texto"]).pack(anchor="w")
        nums = tk.Frame(lado, bg=COR["superficie"])
        nums.pack(anchor="w", fill="x", pady=(px(6), 0))
        for i, (valor, legenda) in enumerate([(ficha["visitas"], "visitas"),
                                              (ficha["ultima"][:5], "última vinda")]):
            bloco = tk.Frame(nums, bg=COR["superficie"])
            bloco.pack(side="left", padx=(0, px(28)))
            tk.Label(bloco, text=valor, font=(f.numero_semi, 20),
                     bg=COR["superficie"], fg=COR["texto"]).pack(anchor="w")
            tk.Label(bloco, text=legenda, font=f.dica, bg=COR["superficie"],
                     fg=COR["texto_3"]).pack(anchor="w")
        if ficha["tipo"]:
            chip = tk.Frame(lado, bg=COR["superficie"])
            chip.pack(anchor="w", pady=(px(12), 0))
            cor = c.CORES_TIPO[ficha["tipo"]]
            tk.Label(chip, text="●", font=f.dica, bg=COR["superficie"],
                     fg=cor).pack(side="left")
            tk.Label(chip, text=" " + ficha["tipo"], font=f.corpo_semi,
                     bg=COR["superficie"], fg=COR["texto"]).pack(side="left")

        # Cartão da tabela
        tab = c.Cartao(area, COR["fundo"], pad=0)
        tab.pack(fill="both", expand=True, padx=G, pady=(px(16), G))
        t = tab.miolo
        t.pack_configure(padx=px(1), pady=px(8))
        barra = tk.Frame(t, bg=COR["superficie"])
        barra.pack(fill="x", padx=px(19), pady=(px(6), px(12)))
        tk.Label(barra, text="Movimento", font=f.titulo_cartao,
                 bg=COR["superficie"], fg=COR["texto"]).pack(side="left")
        busca = c.Campo(barra, f, largura=280, icone=ICONE["busca"])
        busca.pack(side="left", padx=(px(16), 0))
        busca.entrada.insert(0, "Buscar nome, CPF, placa ou tipo")
        busca.entrada.config(fg=COR["texto_3"])
        c.Botao(barra, "Excluir", variante="perigo", icone=ICONE["lixo"],
                fontes=f).pack(side="right")
        c.Botao(barra, "Corrigir", variante="secundario", icone=ICONE["editar"],
                fontes=f).pack(side="right", padx=(0, px(8)))
        c.Botao(barra, "Registrar saída", variante="secundario",
                icone=ICONE["seta"], fontes=f).pack(side="right", padx=(0, px(8)))

        rod = tk.Frame(t, bg=COR["superficie"])
        rod.pack(side="bottom", fill="x", padx=px(19), pady=(px(8), px(2)))
        quadro = tk.Frame(t, bg=COR["superficie"])
        quadro.pack(fill="both", expand=True, padx=px(12))
        cols = ("Nome", "CPF", "Celular", "Placa", "Tipo", "Entrada", "Saida")
        tabela = c.ttk.Treeview(quadro, style="Tabela.Treeview", columns=cols,
                                show="tree headings", selectmode="extended")
        tabela.heading("#0", text="Situação", anchor="w")
        tabela.column("#0", width=px(104), stretch=False, anchor="w")
        for col, titulo, larg, anc in [
                ("Nome", "Nome", 170, "w"), ("CPF", "CPF", 118, "w"),
                ("Celular", "Celular", 112, "w"), ("Placa", "Placa", 86, "w"),
                ("Tipo", "Tipo de acesso", 150, "w"),
                ("Entrada", "Entrada", 128, "w"), ("Saida", "Saída", 128, "w")]:
            tabela.heading(col, text=titulo, anchor="w")
            tabela.column(col, width=px(larg), anchor=anc)
        self.img_dentro = c.bolinha(COR["sucesso"][0])
        self.img_fora = c.bolinha("#AEB7C6")
        self.img_dentro_z = c.bolinha(COR["sucesso"][0], COR["superficie_2"])
        self.img_fora_z = c.bolinha("#AEB7C6", COR["superficie_2"])
        tabela.tag_configure("zebra", background=COR["superficie_2"])
        tabela.tag_configure("dentro", foreground=COR["texto"])
        for i, r in enumerate(REGISTROS):
            dentro = not r[6]
            zebra = i % 2 == 1
            img = ((self.img_dentro_z if zebra else self.img_dentro) if dentro
                   else (self.img_fora_z if zebra else self.img_fora))
            tabela.insert("", "end", iid=str(i), image=img,
                          text="No campus" if dentro else "Saiu",
                          values=r[:6] + (r[6] or "—",),
                          tags=("zebra",) if zebra else ())
        tabela.configure(displaycolumns=("Nome", "CPF", "Placa", "Tipo",
                                         "Entrada", "Saida"))
        tabela.selection_set("1")
        rol = c.ttk.Scrollbar(quadro, orient="vertical", command=tabela.yview,
                              style="Fina.Vertical.TScrollbar")
        tabela.configure(yscrollcommand=rol.set)
        tabela.pack(side="left", fill="both", expand=True)
        rol.pack(side="right", fill="y", padx=(px(2), px(4)))

        tk.Label(rod, text="8 registros  ·  2 no campus  ·  duplo clique registra "
                           "a saída", font=f.dica, bg=COR["superficie"],
                 fg=COR["texto_3"]).pack(side="left")
        toast = tk.Frame(rod, bg=COR["superficie"])
        toast.pack(side="right")
        tk.Label(toast, text=ICONE["ok"], font=f.icone(10), bg=COR["superficie"],
                 fg=COR["sucesso"][0]).pack(side="left", padx=(0, px(6)))
        tk.Label(toast, text="Saída de Bruno registrada às 18:02.",
                 font=f.corpo_semi, bg=COR["superficie"],
                 fg=COR["sucesso"][0]).pack(side="left")
        tk.Label(toast, text="Desfazer", font=(f.rotulo[0], 9, "underline"),
                 bg=COR["superficie"], fg=COR["foco"], cursor="hand2"
                 ).pack(side="left", padx=(px(10), 0))

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    def montar_login(self):
        f = self.f
        painel = tk.Frame(self.raiz, bg=COR["marca"], width=px(470))
        painel.pack(side="left", fill="y")
        painel.pack_propagate(False)
        dentro = tk.Frame(painel, bg=COR["marca"])
        dentro.pack(fill="both", expand=True, padx=px(48), pady=px(48))
        c.marca_cancela(dentro, COR["marca"], tamanho=56, cor="#FFFFFF",
                        traco=COR["marca"]).pack(anchor="w")
        tk.Label(dentro, text="Portaria", font=f.titulo_grande, bg=COR["marca"],
                 fg="#FFFFFF").pack(anchor="w", pady=(px(20), 0))
        tk.Label(dentro, text="Controle de entrada e saída\ndo campus da universidade",
                 font=(f.corpo[0], 12), bg=COR["marca"], fg="#FFFFFF",
                 justify="left").pack(anchor="w", pady=(px(4), 0))

        relogio = tk.Frame(dentro, bg=COR["marca"])
        relogio.pack(side="bottom", anchor="w")
        tk.Label(relogio, text=AGORA.strftime("%H:%M"), font=(f.numero, 54),
                 bg=COR["marca"], fg="#FFFFFF").pack(anchor="w")
        tk.Label(relogio, text=DATA_EXTENSO.capitalize(), font=(f.corpo[0], 12),
                 bg=COR["marca"], fg="#FFFFFF").pack(anchor="w")

        lado = tk.Frame(self.raiz, bg=COR["superficie"])
        lado.pack(side="left", fill="both", expand=True)
        caixa = tk.Frame(lado, bg=COR["superficie"])
        caixa.place(relx=0.5, rely=0.5, anchor="center", width=px(360))
        tk.Label(caixa, text="Entrar", font=f.titulo_pagina, bg=COR["superficie"],
                 fg=COR["texto"]).pack(anchor="w")
        tk.Label(caixa, text="Use o usuário e a senha que o administrador "
                             "cadastrou para você.", font=f.corpo,
                 bg=COR["superficie"], fg=COR["texto_2"], wraplength=px(360),
                 justify="left").pack(anchor="w", pady=(px(4), px(24)))
        for texto, valor, senha in [("Usuário", "carla", False),
                                    ("Senha", "segredo", True)]:
            tk.Label(caixa, text=texto, font=f.rotulo, bg=COR["superficie"],
                     fg=COR["texto"]).pack(anchor="w", pady=(0, px(4)))
            cp = c.Campo(caixa, f, show="•" if senha else "")
            cp.pack(fill="x", pady=(0, px(16)))
            cp.entrada.insert(0, valor)
        erro = c.Aviso(caixa, f)
        erro.pack(fill="x", pady=(0, px(16)))
        erro.mostrar("erro", "Usuário ou senha incorretos.", ICONE["erro"])
        c.Botao(caixa, "Entrar", variante="primario", fontes=f, altura=40,
                dica_tecla="Enter").pack(fill="x")
        tk.Label(caixa, text="Esqueceu a senha? Peça ao administrador para "
                             "redefinir.", font=f.dica, bg=COR["superficie"],
                 fg=COR["texto_3"]).pack(anchor="w", pady=(px(16), 0))

    # ------------------------------------------------------------------
    def foto(self, caminho):
        from PIL import ImageGrab
        r = self.raiz
        r.update()
        esc = 1 if NITIDO else ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
        x, y = r.winfo_rootx(), r.winfo_rooty()
        ImageGrab.grab(tuple(int(v * esc) for v in (
            x, y, x + r.winfo_width(), y + r.winfo_height()))).save(caminho)
        r.destroy()


if __name__ == "__main__":
    app = Prototipo()
    if FOTO:
        app.raiz.after(900, lambda: app.foto(FOTO))
    app.raiz.mainloop()
