"""
Portaria da Universidade - Controle de entrada e saída
UC – Teoria da Computação e Compiladores | Faculdade UNA

Apenas bibliotecas padrão do Python (tkinter, datetime, json, os, re).
Os registros são salvos automaticamente em 'registros_portaria.json'.

Atalho: pressione ENTER para cadastrar (na aba Cadastro).
A aba Dashboard mostra estatísticas dos dados coletados.
"""

import json
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

# ------------------------------------------------------------------
# Constantes
# ------------------------------------------------------------------
ARQUIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "registros_portaria.json")
FORMATO = "%d/%m/%Y %H:%M"
TIPOS_ACESSO = ["Aluno", "Professor", "Funcionário", "Visitante",
                "Entregador", "Prestador de serviço"]

# Mude para True se a placa também for obrigatória
PLACA_OBRIGATORIA = False

# DDDs válidos no Brasil
DDDS_VALIDOS = {
    11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28,
    31, 32, 33, 34, 35, 37, 38, 41, 42, 43, 44, 45, 46, 47, 48, 49,
    51, 53, 54, 55, 61, 62, 63, 64, 65, 66, 67, 68, 69,
    71, 73, 74, 75, 77, 79, 81, 82, 83, 84, 85, 86, 87, 88, 89,
    91, 92, 93, 94, 95, 96, 97, 98, 99,
}

# Placa antiga (ABC1234) e Mercosul (ABC1D23)
REGEX_PLACA = re.compile(r"^([A-Z]{3}[0-9]{4}|[A-Z]{3}[0-9][A-Z][0-9]{2})$")

# Lista em memória com todos os registros (dicionários)
registros = []


# ------------------------------------------------------------------
# Persistência
# ------------------------------------------------------------------
def carregar_registros():
    if os.path.exists(ARQUIVO):
        try:
            with open(ARQUIVO, "r", encoding="utf-8") as f:
                registros.extend(json.load(f))
        except (json.JSONDecodeError, OSError):
            messagebox.showwarning("Aviso",
                                   "Não foi possível ler o arquivo de registros.")


def salvar_registros():
    try:
        with open(ARQUIVO, "w", encoding="utf-8") as f:
            json.dump(registros, f, ensure_ascii=False, indent=2)
    except OSError:
        messagebox.showerror("Erro", "Não foi possível salvar o arquivo.")


# ------------------------------------------------------------------
# Validadores e formatadores (padrões brasileiros)
# ------------------------------------------------------------------
def so_digitos(texto):
    return re.sub(r"\D", "", texto)


def cpf_valido(cpf):
    """CPF: 11 dígitos numéricos com os dois dígitos verificadores corretos."""
    if len(cpf) != 11 or not cpf.isdigit() or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11 % 10
        if digito != int(cpf[tamanho]):
            return False
    return True


def celular_valido(cel):
    """Celular: DDD (2 dígitos) + 9 obrigatório + 8 dígitos = 11 dígitos."""
    if len(cel) != 11 or not cel.isdigit():
        return False
    if int(cel[:2]) not in DDDS_VALIDOS:
        return False
    return cel[2] == "9"


def placa_valida(placa):
    return bool(REGEX_PLACA.match(placa))


def formatar_cpf(c):
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}" if len(c) == 11 else c


def formatar_celular(c):
    return f"({c[:2]}) {c[2:7]}-{c[7:]}" if len(c) == 11 else c


def formatar_placa(p):
    # Placa antiga ganha hífen (ABC-1234); Mercosul fica ABC1D23
    if re.match(r"^[A-Z]{3}[0-9]{4}$", p):
        return f"{p[:3]}-{p[3:]}"
    return p


def converter_data(texto):
    """Converte 'dd/mm/aaaa hh:mm' em datetime. Retorna None se inválido."""
    try:
        return datetime.strptime(texto.strip(), FORMATO)
    except ValueError:
        return None


def validar(nome_txt, cpf_txt, cel_txt, placa_txt, tipo_txt,
            entrada_txt, saida_txt):
    """Retorna (ok, mensagem). Contém as verificações semânticas."""
    if not nome_txt.strip():
        return False, "O nome da pessoa é obrigatório."
    if len(nome_txt.strip().split()) < 2:
        return False, "Informe o nome completo (nome e sobrenome)."

    if not cpf_txt:
        return False, "O CPF é obrigatório."
    if not cpf_valido(cpf_txt):
        return False, "CPF inválido.\nDigite os 11 números (somente números)."

    if not cel_txt:
        return False, "O celular é obrigatório."
    if not celular_valido(cel_txt):
        return False, ("Celular inválido.\nUse DDD + 9 + 8 dígitos "
                       "(ex.: 31 9 1234 5678, somente números).")

    if placa_txt:
        if not placa_valida(placa_txt):
            return False, ("Placa inválida.\nUse o formato antigo (ABC1234) "
                           "ou Mercosul (ABC1D23).")
    elif PLACA_OBRIGATORIA:
        return False, "A placa do veículo é obrigatória."

    if tipo_txt not in TIPOS_ACESSO:  # VERIFICAÇÃO SEMÂNTICA 1
        return False, "Selecione um tipo de acesso válido."

    entrada_dt = converter_data(entrada_txt)
    if entrada_dt is None:
        return False, f"Data/hora de entrada inválida.\nUse o formato {FORMATO}."

    if saida_txt.strip():
        saida_dt = converter_data(saida_txt)
        if saida_dt is None:
            return False, f"Data/hora de saída inválida.\nUse o formato {FORMATO}."
        if saida_dt < entrada_dt:  # VERIFICAÇÃO SEMÂNTICA 2
            return False, "A saída não pode ser anterior à entrada."
    else:
        # VERIFICAÇÃO SEMÂNTICA 3: mesma pessoa não pode entrar duas vezes
        for r in registros:
            if r.get("cpf") == cpf_txt and not r.get("saida"):
                return False, ("Este CPF já possui uma entrada sem saída.\n"
                               "Registre a saída antes de uma nova entrada.")
    return True, ""


# ------------------------------------------------------------------
# Ações dos botões
# ------------------------------------------------------------------
def agora():
    return datetime.now().strftime(FORMATO)


def atualizar_tabela(filtro=""):
    for item in tabela.get_children():
        tabela.delete(item)
    filtro = filtro.strip().lower()
    filtro_num = so_digitos(filtro)
    for i, r in enumerate(registros):
        cpf = r.get("cpf", "")
        if filtro:
            achou = (filtro in r["nome"].lower()
                     or filtro in r["tipo"].lower()
                     or filtro in r.get("placa", "").lower()
                     or (filtro_num and (filtro_num in cpf
                                         or filtro_num in r.get("celular", ""))))
            if not achou:
                continue
        tabela.insert("", "end", iid=str(i), values=(
            r["nome"],
            formatar_cpf(cpf),
            formatar_celular(r.get("celular", "")),
            formatar_placa(r.get("placa", "")) or "—",
            r["tipo"],
            r["entrada"],
            r["saida"] or "— dentro —"))
    total_dentro = sum(1 for r in registros if not r["saida"])
    lbl_status.config(text=f"Registros: {len(registros)}   |   "
                           f"Pessoas dentro agora: {total_dentro}")
    atualizar_dashboard()


def cadastrar(event=None):
    if event is not None and abas.select() != str(aba_cad):
        return  # Enter só cadastra na aba Cadastro
    ok, msg = validar(nome.get(), so_digitos(cpf.get()),
                      so_digitos(celular.get()), var_placa.get().strip(),
                      tipo.get(), entrada.get(), saida.get())
    if not ok:
        messagebox.showerror("Dados inválidos", msg)
        return
    registros.append({
        "nome": nome.get().strip(),
        "cpf": so_digitos(cpf.get()),
        "celular": so_digitos(celular.get()),
        "placa": var_placa.get().strip(),
        "tipo": tipo.get(),
        "entrada": entrada.get().strip(),
        "saida": saida.get().strip(),
    })
    salvar_registros()
    atualizar_tabela(busca.get())
    limpar()
    messagebox.showinfo("Cadastro", "Registro cadastrado com sucesso!")


def limpar():
    nome.delete(0, tk.END)
    cpf.delete(0, tk.END)
    celular.delete(0, tk.END)
    var_placa.set("")
    tipo.set("")
    entrada.delete(0, tk.END)
    entrada.insert(0, agora())
    saida.delete(0, tk.END)
    nome.focus()


def excluir_selecionado():
    selecionado = tabela.selection()
    if not selecionado:
        messagebox.showwarning("Atenção", "Selecione um registro na tabela.")
        return
    if not messagebox.askyesno("Confirmar", "Excluir o registro selecionado?"):
        return
    for i in sorted((int(i) for i in selecionado), reverse=True):
        registros.pop(i)
    salvar_registros()
    atualizar_tabela(busca.get())


def registrar_saida():
    """Marca a saída (data/hora atual) do registro selecionado."""
    selecionado = tabela.selection()
    if not selecionado:
        messagebox.showwarning("Atenção", "Selecione um registro na tabela.")
        return
    r = registros[int(selecionado[0])]
    if r["saida"]:
        messagebox.showinfo("Aviso", "Esta pessoa já tem a saída registrada.")
        return
    if datetime.now() < converter_data(r["entrada"]):
        messagebox.showerror("Dados inválidos",
                             "A saída não pode ser anterior à entrada.")
        return
    r["saida"] = agora()
    salvar_registros()
    atualizar_tabela(busca.get())
    messagebox.showinfo("Saída", "Saída registrada com sucesso!")


# ------------------------------------------------------------------
# Interface
# ------------------------------------------------------------------
janela = tk.Tk()
janela.title("Portaria da Universidade")
janela.geometry("1020x720")
janela.minsize(900, 620)
janela.configure(bg="#f4f6fa")

estilo = ttk.Style()
estilo.theme_use("clam")
estilo.configure("Treeview", rowheight=26, font=("Segoe UI", 10))
estilo.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
estilo.configure("TNotebook", background="#f4f6fa", borderwidth=0)
estilo.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=[18, 7])

# Validação de digitação: só números, com limite de tamanho
def _so_numeros(limite):
    return (janela.register(
        lambda p: p == "" or (p.isascii() and p.isdigit() and len(p) <= limite)),
        "%P")

# Placa: letras/números, máximo 7, sempre maiúscula
def _placa_ok(p):
    return p == "" or (p.isascii() and p.isalnum() and len(p) <= 7)

# Cabeçalho
topo = tk.Frame(janela, bg="#d9001b")
topo.pack(fill="x")
tk.Label(topo, text="🏛  Portaria da Universidade", bg="#d9001b", fg="white",
         font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=20, pady=(12, 0))
tk.Label(topo, text="Controle de entrada e saída de pessoas no campus",
         bg="#d9001b", fg="#ffd9de", font=("Segoe UI", 10)
         ).pack(anchor="w", padx=20, pady=(0, 12))

# Abas
abas = ttk.Notebook(janela)
abas.pack(fill="both", expand=True)
aba_cad = tk.Frame(abas, bg="#f4f6fa")
aba_dash = tk.Frame(abas, bg="#f4f6fa")
abas.add(aba_cad, text="  📋 Cadastro  ")
abas.add(aba_dash, text="  📊 Dashboard  ")

# Formulário
form = tk.Frame(aba_cad, bg="#f4f6fa")
form.pack(fill="x", padx=20, pady=14)
form.columnconfigure((0, 1, 2), weight=1, uniform="col")

fonte_lbl = ("Segoe UI", 10, "bold")
fonte_dica = ("Segoe UI", 8)

def rotulo(texto, linha, coluna, **kw):
    tk.Label(form, text=texto, bg="#f4f6fa", font=fonte_lbl
             ).grid(row=linha, column=coluna, sticky="w", **kw)

# Linha 0-1: nome (2 colunas) e tipo
rotulo("Nome completo: *", 0, 0)
nome = ttk.Entry(form, font=("Segoe UI", 10))
nome.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 10), pady=(0, 8))

rotulo("Tipo de acesso: *", 0, 2)
tipo = ttk.Combobox(form, values=TIPOS_ACESSO, state="readonly",
                    font=("Segoe UI", 10))
tipo.grid(row=1, column=2, sticky="ew", pady=(0, 8))

# Linha 2-3: CPF, celular, placa
rotulo("CPF (somente números): *", 2, 0)
cpf = ttk.Entry(form, font=("Segoe UI", 10), validate="key",
                validatecommand=_so_numeros(11))
cpf.grid(row=3, column=0, sticky="ew", padx=(0, 10))

rotulo("Celular com DDD (somente números): *", 2, 1)
celular = ttk.Entry(form, font=("Segoe UI", 10), validate="key",
                    validatecommand=_so_numeros(11))
celular.grid(row=3, column=1, sticky="ew", padx=(0, 10))

rotulo("Placa do veículo:" + (" *" if PLACA_OBRIGATORIA else ""), 2, 2)
var_placa = tk.StringVar()
var_placa.trace_add("write", lambda *a: var_placa.set(var_placa.get().upper())
                    if var_placa.get() != var_placa.get().upper() else None)
placa = ttk.Entry(form, font=("Segoe UI", 10), textvariable=var_placa,
                  validate="key",
                  validatecommand=(janela.register(_placa_ok), "%P"))
placa.grid(row=3, column=2, sticky="ew")

tk.Label(form, text="Ex.: 12345678909", bg="#f4f6fa", fg="#666",
         font=fonte_dica).grid(row=4, column=0, sticky="w")
tk.Label(form, text="Ex.: 31912345678 (DDD + 9 + 8 dígitos)", bg="#f4f6fa",
         fg="#666", font=fonte_dica).grid(row=4, column=1, sticky="w")
tk.Label(form, text="ABC1234 ou ABC1D23 (deixe vazio se a pé)", bg="#f4f6fa",
         fg="#666", font=fonte_dica).grid(row=4, column=2, sticky="w")

# Linha 5-6: entrada e saída
rotulo(f"Data e hora da entrada ({FORMATO}): *", 5, 0, pady=(8, 0))
linha_entrada = tk.Frame(form, bg="#f4f6fa")
linha_entrada.grid(row=6, column=0, sticky="ew", padx=(0, 10))
entrada = ttk.Entry(linha_entrada, font=("Segoe UI", 10))
entrada.pack(side="left", fill="x", expand=True)
ttk.Button(linha_entrada, text="Agora", width=7,
           command=lambda: (entrada.delete(0, tk.END),
                            entrada.insert(0, agora()))
           ).pack(side="left", padx=(6, 0))

rotulo(f"Data e hora da saída ({FORMATO}):", 5, 1, pady=(8, 0))
linha_saida = tk.Frame(form, bg="#f4f6fa")
linha_saida.grid(row=6, column=1, sticky="ew", padx=(0, 10))
saida = ttk.Entry(linha_saida, font=("Segoe UI", 10))
saida.pack(side="left", fill="x", expand=True)
ttk.Button(linha_saida, text="Agora", width=7,
           command=lambda: (saida.delete(0, tk.END), saida.insert(0, agora()))
           ).pack(side="left", padx=(6, 0))

tk.Label(form, text="Saída em branco = pessoa ainda no campus.",
         bg="#f4f6fa", fg="#666", font=fonte_dica
         ).grid(row=7, column=1, sticky="w")
tk.Label(form, text="* campos obrigatórios", bg="#f4f6fa", fg="#d9001b",
         font=fonte_dica).grid(row=7, column=0, sticky="w")

# Botões
botoes = tk.Frame(aba_cad, bg="#f4f6fa")
botoes.pack(fill="x", padx=20)

def botao(pai, texto, cor, comando, lado="left"):
    b = tk.Button(pai, text=texto, bg=cor, fg="white", activebackground=cor,
                  activeforeground="white", relief="flat", cursor="hand2",
                  font=("Segoe UI", 10, "bold"), padx=14, pady=6,
                  command=comando)
    b.pack(side=lado, padx=(0, 8))
    return b

botao(botoes, "+ Cadastrar (Enter)", "#0a9a5a", cadastrar)
botao(botoes, "Limpar", "#1f6fd1", limpar)
botao(botoes, "Registrar saída", "#e08a00", registrar_saida)
botao(botoes, "✕ Excluir selecionado", "#e03131", excluir_selecionado,
      lado="right")

# Busca
barra_busca = tk.Frame(aba_cad, bg="#f4f6fa")
barra_busca.pack(fill="x", padx=20, pady=(14, 4))
tk.Label(barra_busca, text="Buscar (nome, CPF, celular, placa ou tipo):",
         bg="#f4f6fa", font=fonte_lbl).pack(side="left")
busca = ttk.Entry(barra_busca, font=("Segoe UI", 10))
busca.pack(side="left", fill="x", expand=True, padx=8)
busca.bind("<KeyRelease>", lambda e: atualizar_tabela(busca.get()))

# Tabela
quadro = tk.Frame(aba_cad, bg="#f4f6fa")
quadro.pack(fill="both", expand=True, padx=20, pady=(0, 6))

tabela = ttk.Treeview(
    quadro, show="headings", selectmode="extended",
    columns=("Nome", "CPF", "Celular", "Placa", "Tipo", "Entrada", "Saida"))
for col, titulo, larg, anc in [
        ("Nome", "Nome", 190, "w"), ("CPF", "CPF", 105, "center"),
        ("Celular", "Celular", 115, "center"), ("Placa", "Placa", 75, "center"),
        ("Tipo", "Tipo de acesso", 120, "w"),
        ("Entrada", "Entrada", 115, "center"),
        ("Saida", "Saída", 115, "center")]:
    tabela.heading(col, text=titulo)
    tabela.column(col, width=larg, anchor=anc)

rolagem = ttk.Scrollbar(quadro, orient="vertical", command=tabela.yview)
tabela.configure(yscrollcommand=rolagem.set)
tabela.pack(side="left", fill="both", expand=True)
rolagem.pack(side="right", fill="y")

lbl_status = tk.Label(aba_cad, text="", bg="#f4f6fa", fg="#444",
                      font=("Segoe UI", 9), anchor="w")
lbl_status.pack(fill="x", padx=20, pady=(0, 8))

# ------------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------------
CORES_TIPO = {"Aluno": "#1f6fd1", "Professor": "#7a3fd1",
              "Funcionário": "#0a9a5a", "Visitante": "#e08a00",
              "Entregador": "#d9001b", "Prestador de serviço": "#5a6b7b"}
PLURAL_TIPO = {"Aluno": "Alunos", "Professor": "Professores",
               "Funcionário": "Funcionários", "Visitante": "Visitantes",
               "Entregador": "Entregadores",
               "Prestador de serviço": "Prestadores"}

dados_dash = {"tipos": [], "dias": []}   # dados já calculados para os gráficos
cards = {}                               # nome -> (label do valor, label de apoio)


def criar_card(pai, linha, coluna, chave, titulo, cor):
    caixa = tk.Frame(pai, bg="white", highlightbackground="#dde1ea",
                     highlightthickness=1)
    caixa.grid(row=linha, column=coluna, sticky="nsew", padx=5, pady=5)
    tk.Frame(caixa, bg=cor, height=4).pack(fill="x")
    tk.Label(caixa, text=titulo, bg="white", fg="#555",
             font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
    valor = tk.Label(caixa, text="0", bg="white", fg="#222",
                     font=("Segoe UI", 20, "bold"))
    valor.pack(anchor="w", padx=12)
    apoio = tk.Label(caixa, text="", bg="white", fg="#777",
                     font=("Segoe UI", 8))
    apoio.pack(anchor="w", padx=12, pady=(0, 8))
    cards[chave] = (valor, apoio)


# Linha 1: um card por tipo de acesso
linha_tipos = tk.Frame(aba_dash, bg="#f4f6fa")
linha_tipos.pack(fill="x", padx=15, pady=(14, 0))
linha_tipos.columnconfigure(tuple(range(len(TIPOS_ACESSO))), weight=1,
                            uniform="ct")
for i, t in enumerate(TIPOS_ACESSO):
    criar_card(linha_tipos, 0, i, t, PLURAL_TIPO[t], CORES_TIPO[t])

# Linha 2: resumo geral
linha_resumo = tk.Frame(aba_dash, bg="#f4f6fa")
linha_resumo.pack(fill="x", padx=15)
linha_resumo.columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="cr")
criar_card(linha_resumo, 0, 0, "total", "TOTAL DE REGISTROS", "#222222")
criar_card(linha_resumo, 0, 1, "dentro", "DENTRO AGORA", "#0a9a5a")
criar_card(linha_resumo, 0, 2, "hoje", "ENTRADAS HOJE", "#1f6fd1")
criar_card(linha_resumo, 0, 3, "veiculos", "COM VEÍCULO", "#e08a00")
criar_card(linha_resumo, 0, 4, "permanencia", "PERMANÊNCIA MÉDIA", "#7a3fd1")

# Gráficos
area_graficos = tk.Frame(aba_dash, bg="#f4f6fa")
area_graficos.pack(fill="both", expand=True, padx=15, pady=(6, 14))
area_graficos.columnconfigure(0, weight=1, uniform="g")
area_graficos.columnconfigure(1, weight=1, uniform="g")
area_graficos.rowconfigure(0, weight=1)

cv_tipos = tk.Canvas(area_graficos, bg="white", height=260,
                     highlightbackground="#dde1ea", highlightthickness=1)
cv_tipos.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
cv_dias = tk.Canvas(area_graficos, bg="white", height=260,
                    highlightbackground="#dde1ea", highlightthickness=1)
cv_dias.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)


def formatar_duracao(td):
    minutos = int(td.total_seconds() // 60)
    h, m = divmod(minutos, 60)
    return f"{h}h {m:02d}min" if h else f"{m}min"


def desenhar_barras_horizontais(cv, titulo, itens):
    """itens: lista de (rótulo, valor, texto à direita, cor)."""
    cv.delete("all")
    w, h = cv.winfo_width(), cv.winfo_height()
    cv.create_text(14, 18, text=titulo, anchor="w", fill="#222",
                   font=("Segoe UI", 11, "bold"))
    if not itens or max(v for _, v, _, _ in itens) == 0:
        cv.create_text(w / 2, h / 2, text="Sem dados ainda", fill="#888",
                       font=("Segoe UI", 10))
        return
    maximo = max(v for _, v, _, _ in itens)
    esq, dir_, topo = 130, 190, 42
    area = max(w - esq - dir_, 10)
    passo = (h - topo - 10) / len(itens)
    for i, (rotulo_, valor_, extra, cor) in enumerate(itens):
        y = topo + i * passo
        comp = area * valor_ / maximo
        cv.create_text(esq - 8, y + passo / 2, text=rotulo_, anchor="e",
                       fill="#333", font=("Segoe UI", 9))
        cv.create_rectangle(esq, y + passo * 0.2, esq + max(comp, 2),
                            y + passo * 0.8, fill=cor, outline="")
        cv.create_text(esq + comp + 8, y + passo / 2, text=extra, anchor="w",
                       fill="#444", font=("Segoe UI", 9, "bold"))


def desenhar_barras_verticais(cv, titulo, itens, cor):
    """itens: lista de (rótulo, valor)."""
    cv.delete("all")
    w, h = cv.winfo_width(), cv.winfo_height()
    cv.create_text(14, 18, text=titulo, anchor="w", fill="#222",
                   font=("Segoe UI", 11, "bold"))
    if not itens or max(v for _, v in itens) == 0:
        cv.create_text(w / 2, h / 2, text="Sem dados ainda", fill="#888",
                       font=("Segoe UI", 10))
        return
    maximo = max(v for _, v in itens)
    esq, topo, base = 20, 56, h - 30
    larg = max((w - 2 * esq) / len(itens), 10)
    cv.create_line(esq, base, w - esq, base, fill="#ccc")
    for i, (rotulo_, valor_) in enumerate(itens):
        x0 = esq + i * larg + larg * 0.2
        x1 = esq + (i + 1) * larg - larg * 0.2
        altura = (base - topo) * valor_ / maximo
        cv.create_rectangle(x0, base - altura, x1, base, fill=cor, outline="")
        cv.create_text((x0 + x1) / 2, base - altura - 9, text=str(valor_),
                       fill="#444", font=("Segoe UI", 9, "bold"))
        cv.create_text((x0 + x1) / 2, base + 14, text=rotulo_, fill="#555",
                       font=("Segoe UI", 8))


def redesenhar_graficos(event=None):
    desenhar_barras_horizontais(cv_tipos, "Pessoas por tipo de acesso",
                                dados_dash["tipos"])
    desenhar_barras_verticais(cv_dias, "Entradas nos últimos 7 dias",
                              dados_dash["dias"], "#1f6fd1")


cv_tipos.bind("<Configure>", redesenhar_graficos)
cv_dias.bind("<Configure>", redesenhar_graficos)


def atualizar_dashboard():
    hoje = datetime.now().date()
    por_tipo = {t: [0, 0] for t in TIPOS_ACESSO}          # [total, dentro]
    por_dia = {hoje - timedelta(days=i): 0 for i in range(6, -1, -1)}
    permanencias = []
    entradas_hoje = com_veiculo = dentro = 0

    for r in registros:
        contagem = por_tipo.setdefault(r["tipo"], [0, 0])
        contagem[0] += 1
        if not r["saida"]:
            contagem[1] += 1
            dentro += 1
        if r.get("placa"):
            com_veiculo += 1
        entrada_dt = converter_data(r["entrada"])
        if entrada_dt:
            dia = entrada_dt.date()
            if dia in por_dia:
                por_dia[dia] += 1
            if dia == hoje:
                entradas_hoje += 1
            saida_dt = converter_data(r["saida"]) if r["saida"] else None
            if saida_dt:
                permanencias.append(saida_dt - entrada_dt)

    for t in TIPOS_ACESSO:
        total_t, dentro_t = por_tipo[t]
        cards[t][0].config(text=str(total_t))
        cards[t][1].config(text=f"{dentro_t} dentro agora")

    cards["total"][0].config(text=str(len(registros)))
    cards["total"][1].config(text="desde o início")
    cards["dentro"][0].config(text=str(dentro))
    cards["dentro"][1].config(text=f"{len(registros) - dentro} já saíram")
    cards["hoje"][0].config(text=str(entradas_hoje))
    cards["hoje"][1].config(text=hoje.strftime("%d/%m/%Y"))
    cards["veiculos"][0].config(text=str(com_veiculo))
    cards["veiculos"][1].config(text="registros com placa")
    if permanencias:
        media = sum(permanencias, timedelta()) / len(permanencias)
        cards["permanencia"][0].config(text=formatar_duracao(media))
        cards["permanencia"][1].config(text=f"{len(permanencias)} saídas")
    else:
        cards["permanencia"][0].config(text="—")
        cards["permanencia"][1].config(text="sem saídas registradas")

    total = len(registros)
    dados_dash["tipos"] = [
        (PLURAL_TIPO.get(t, t), por_tipo[t][0],
         f"{por_tipo[t][0]} ({por_tipo[t][0] * 100 // total if total else 0}%)"
         f" · {por_tipo[t][1]} dentro",
         CORES_TIPO.get(t, "#888"))
        for t in TIPOS_ACESSO]
    dados_dash["dias"] = [(d.strftime("%d/%m"), n)
                          for d, n in por_dia.items()]
    redesenhar_graficos()


# Tecla ENTER cadastra (exceto na caixa de busca)
janela.bind("<Return>", cadastrar)
janela.bind("<KP_Enter>", cadastrar)
busca.bind("<Return>", lambda e: "break")

# Inicialização
carregar_registros()
limpar()
atualizar_tabela()
janela.mainloop()


# ==================================================================
# RELAÇÃO COM COMPILADORES (desafio final do exercício)
# ==================================================================
# 1) TOKEN (análise léxica)
#    Na linha:  cpf = ttk.Entry(form, font=("Segoe UI", 10), validate="key")
#    Tokens: cpf (identificador), = (operador de atribuição),
#    ttk (identificador), . (ponto), Entry (identificador),
#    ( (abre parênteses), "Segoe UI" (literal string), 10 (literal inteiro).
#
# 2) VARIÁVEL DA TABELA DE SÍMBOLOS
#    Símbolo: registros | Tipo: list | Valor inicial: [] | Escopo: global
#    (também: ARQUIVO -> str, FORMATO -> str, TIPOS_ACESSO -> list,
#     DDDS_VALIDOS -> set, REGEX_PLACA -> re.Pattern)
#
# 3) VERIFICAÇÃO SEMÂNTICA
#    Na função validar(): o código está sintaticamente correto, mas só faz
#    sentido se:  saida_dt < entrada_dt  for falso (saída não anterior à
#    entrada); o CPF passar nos dígitos verificadores; o celular tiver o 9
#    após o DDD; e o mesmo CPF não tiver duas entradas sem saída.
