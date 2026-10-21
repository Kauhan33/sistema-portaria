# Proposta de design: Sistema de Portaria

Objetivo: tirar a cara de "programa antigo" das telas sem sair do Python + Tkinter, sem instalar nada (`pip`) e sem quebrar os testes automatizados.

Pasta de trabalho do designer (prints e protótipo):
`docs/design/`

> Os prints e o protótipo foram copiados para esta pasta (`docs/design/`).

---

## 1. Telas atuais (antes)

Fotografadas com o app real, numa pasta temporária, usando dados de exemplo (escala de tela de 125%):

| Tela | Arquivo |
|---|---|
| Login | `...\designer\antes\1_login.png` |
| Cadastro (CPF de quem já está no campus) | `...\designer\antes\2_cadastro.png` |
| Pessoas | `...\designer\antes\3_pessoas.png` |
| Bloqueios | `...\designer\antes\4_bloqueios.png` |
| Dashboard | `...\designer\antes\5_dashboard.png` |
| Usuários | `...\designer\antes\6_usuarios.png` |
| Corrigir registro (janela) | `...\designer\antes\7_corrigir.png` |

Caminho completo da pasta: `antes/`
Script que gera os prints: `...\designer\shots_antes.py`

---

## 2. Diagnóstico: por que parece feio e antigo

Em ordem de impacto:

1. **Texto borrado (o problema que mais pesa).** O programa não avisa o Windows de que sabe lidar com escala de tela (DPI). Com 125%, o Windows desenha a janela em 100% e a estica como se fosse uma imagem. Por isso todas as letras ficam levemente embaçadas. Compare `depois\cadastro_ok.png` (nítido) com `depois\cadastro_sem_dpi.png` (mesmo protótipo, borrado). Isso se resolve com uma linha de `ctypes`, que faz parte da biblioteca padrão.
2. **Botões em arco-íris.** Só a tela de Cadastro tem 6 cores de botão: verde, azul, laranja, cinza, vermelho e laranja de novo na saída rápida. Como cor não indica importância, nada se destaca. Além disso, branco sobre o laranja `#E08A00` tem contraste 2,69:1 e branco sobre o verde `#0A9A5A` tem 3,63:1. Os dois **reprovam no WCAG AA** (o mínimo é 4,5:1).
3. **Abas do tema `clam`.** São cinza-bege, com borda chanfrada, estilo Windows XP/Linux de 2005. São a "assinatura" visual de Tkinter cru.
4. **Cabeçalho vermelho gigante, que toma 107 px de altura** em toda tela. O vermelho da UNA está em todo lugar (cabeçalho, faixas dos cartões, botão Sair, dicas, avisos de erro). Nessa quantidade, vermelho deixa de ser marca e vira alarme. E numa portaria vermelho já quer dizer "bloqueado".
5. **Formulário sem hierarquia.** Rótulos em negrito com instruções dentro ("CPF (somente números): \*", "Celular com DDD (somente números): \*", "Entrada (dd/mm/aaaa hh:mm): \*") deixam tudo com o mesmo peso. Asteriscos em quase todos os campos, quando seria melhor marcar só os opcionais.
6. **Tudo empilhado sem agrupamento.** Na tela de Cadastro, em sequência: formulário, botões, saída rápida, busca, tabela. Não há superfícies (cartões) que separem "cadastrar" de "consultar". A saída rápida (F2), uma das ações mais usadas, aparece como uma linha solta no meio.
7. **Tabelas cruas.** O cabeçalho cinza-bege é chanfrado, as linhas não têm zebra, a seleção é azul-petróleo escura (`#4A6984`) e o texto de situação vem como "— dentro —". Na aba Pessoas, a linha inteira fica verde ou vermelha conforme a situação, o que cansa a leitura. A seta da barra de rolagem é de Windows 95.
8. **Ícones em emoji** (🏛 📋 👥 🚫 📊 👤 ✎ ⚠ ✓ ↺): o Windows os desenha monocromáticos e desalinhados com o texto, e cada um tem um tamanho diferente.
9. **Detalhes que denunciam:** campos de data com o botão "Agora" no tema clam, ao lado do campo; checkbox "Mostrar bloqueios removidos" com fundo cinza diferente do da tela; linhas removidas em `#999` (contraste 2,85:1, reprova); o card do dashboard "TOTAL DE REGISTROS" em CAIXA ALTA convivendo com "Alunos" em caixa normal.
10. **Tamanho de janela.** A janela pede 1020×720 com mínimo de 900×620 (em pixels lógicos). Num notebook 1366×768 a 125%, a tela útil tem uns 1093×570, então a parte de baixo (tabela, rodapé) some.

O que já está bom e será mantido: a fonte Segoe UI, o fundo cinza-claro, a lógica de avisos (preenchimento pelo CPF, alerta de bloqueio, "Desfazer" da saída) e os gráficos feitos em Canvas.

---

## 3. Três caminhos técnicos

| Critério | (a) Tkinter/ttk puro + componentes desenhados | (b) sv-ttk (Sun Valley) | (c) CustomTkinter |
|---|---|---|---|
| Visual que dá para alcançar | Alto: a gente decide cada pixel. Cantos arredondados com anti-serrilhado (técnica abaixo), ícones Segoe Fluent, placa Mercosul desenhada. | Alto e "nativo Windows 11" já pronto (botões, campos com linha de foco, switches). Cor de destaque azul fixa: trocar exige editar as imagens PNG do tema. | Alto e moderno, mas com cara de "app CustomTkinter" (fácil de reconhecer, genérico). **Não tem tabela**: continua o `ttk.Treeview` cru, que destoa. |
| Só Python padrão? | **Sim** (tkinter, ctypes). | **Não** (1 pacote pip). Dá para "vendorizar" (copiar os `.tcl` e PNGs, licença MIT) e carregar com `tk.call("source", ...)`, mas é código de terceiros dentro do projeto. | **Não** (customtkinter + darkdetect + packaging). |
| Esforço | Médio: ~400 linhas de componentes (`componentes.py`, já escritos no protótipo) e troca das chamadas nas telas. | Baixo para os widgets ttk, mas o projeto usa muito `tk.Frame`/`tk.Label`/`tk.Button` com `bg=`, que o tema **não** pinta. Seria preciso converter para ttk e criar estilos. Médio no total. | Alto: reescrever todas as telas com `CTkButton`, `CTkEntry`, `CTkFrame`, `CTkComboBox` (API diferente do ttk: `command=` em vez de `<<ComboboxSelected>>`, outro jeito de `values`/`state`). |
| Risco nos testes (hoje 193 métodos `test_`; o pedido fala em 199) | Baixo, se os nomes forem mantidos (`app.cpf`, `app.tabela`, `app.lbl_aviso`...). As abas viram barra lateral **sem mudar** `app.abas` (truque na seção 6). | Baixo: os widgets continuam ttk/tk. | Alto: `CTkLabel` não é `tk.Label` e `CTkButton` não é `tk.Button` (os testes fazem `isinstance(w, tk.Label)`/`tk.Button`). `CTkEntry` não é o widget de entrada real (fica dentro). |
| Executável (PyInstaller) | Nada muda: as fontes são do Windows e não há arquivos extras. | Precisa de `--collect-data sv_ttk` (erro comum: o .exe abre sem tema). | Precisa de `--add-data` com a pasta `customtkinter` (temas .json e fontes). Erro comum no .exe. |
| Desempenho | Bom (Canvas simples e imagens pequenas em cache). | Bom. Carregar o tema leva um instante. | Mais pesado com muitos widgets; redimensionar a janela pisca. |
| Windows 10 | Funciona (troca Segoe Fluent Icons por Segoe MDL2 Assets e Segoe UI Variable por Segoe UI automaticamente). | Funciona. | Funciona. |

### Recomendação: caminho (a)

- É o único que cumpre "só Python padrão" sem discussão, e o protótipo mostra que o resultado **não fica fraco** (veja os prints da seção 7).
- O maior ganho visual vem de três coisas que nenhum pacote resolve sozinho: **nitidez (DPI)**, **disciplina de cor** e **hierarquia/agrupamento**. As três são gratuitas no caminho (a).
- Para ser franco sobre os limites do (a):
  - O `Canvas` do Tk no Windows **não tem anti-serrilhado**. O protótipo contorna isso gerando os cantos como pequenas imagens em que cada pixel é misturado com a cor do fundo (que sempre é conhecida). Funciona muito bem em superfícies de cor lisa, mas um cartão sobre um fundo em degradê não daria certo.
  - `ttk.Entry` e `ttk.Combobox` continuam quadrados por dentro. O canto arredondado vem de uma moldura desenhada em volta.
  - Não há animação nem sombra suave. O desenho usa contornos de 1 px e contraste de superfícies em vez de sombra.
  - O `Treeview` não pinta uma célula só: a cor vale para a linha inteira. A situação vira uma bolinha colorida (imagem) na primeira coluna.
- Se um dia o requisito "sem pip" cair, a alternativa (b) é a próxima melhor, mas ainda exigiria converter os `tk.*` para ttk.

---

## 4. Sistema de design: "Guarita"

**Ideia:** o porteiro olha a tela de relance, dezenas de vezes por hora. A interface deve ser **calma** (neutros, um só botão escuro por tela) e **gritar só quando importa**, como uma cancela: verde = pode entrar, âmbar = atenção, vermelho = bloqueado. O vermelho da UNA vira **identidade** (símbolo, item ativo do menu, tela de login) e para de competir com o vermelho de "bloqueado".

**O elemento memorável** (a única ousadia): a **placa Mercosul desenhada** na ficha da pessoa, com faixa azul "BRASIL" e caracteres em **Bahnschrift**. A Bahnschrift é a versão da Microsoft da DIN 1451, parente direta da FE-Schrift usada nas placas. Isso é vocabulário de portaria, não decoração. O resto fica quieto.

**Símbolo:** uma cancela (poste + braço listrado) num quadrado vermelho UNA, desenhada no Canvas. Não usa o logotipo oficial da faculdade.

### 4.1 Cores

| Token | Hex | Uso | Contraste (WCAG) |
|---|---|---|---|
| `marca` | `#D9001B` | Vermelho UNA: símbolo, traço do item ativo no menu, painel do login | branco sobre ele 5,29:1 ✔ AA |
| `marca_escura` | `#B80017` | Hover de algo na cor da marca | branco 6,88:1 ✔ |
| `fundo` | `#F3F4F6` | Fundo da janela | |
| `lateral` | `#EEF0F3` | Barra lateral | |
| `superficie` | `#FFFFFF` | Cartões, campos, tabela | |
| `superficie_2` | `#F8F9FB` | Cabeçalho de tabela, linha zebrada | texto 14,99:1 ✔ |
| `borda` | `#E1E4EA` | Contorno de cartão (decorativo) | (não exigido) |
| `borda_campo` | `#C5CBD5` | Contorno do campo | |
| `traco_campo` | `#8C95A6` | Linha de baixo do campo (identifica o campo) | 3,02:1 ✔ (≥3 p/ componente) |
| `texto` | `#1B2330` | Texto principal | 15,79:1 ✔ AAA |
| `texto_2` | `#475467` | Texto secundário, cabeçalho de tabela | 7,69:1 ✔ |
| `texto_3` | `#5B6578` | Dicas, legendas, itens desativados (no lugar de `#999`) | 5,87:1 no branco, 5,14:1 na lateral ✔ |
| `primario` | `#1B2330` | Botão principal (um por tela) | branco 15,79:1 ✔ |
| `primario_hover` | `#2E3A4D` | | branco 11,48:1 ✔ |
| `foco` | `#1F5FBF` | Anel/linha de foco do teclado, links ("Desfazer") | 6,09:1 ✔ |
| `selecao` | `#E3E9F4` | Linha selecionada na tabela | texto 12,96:1 ✔ |
| `hover` | `#E8EBF0` | Fundo ao passar o mouse | |

**Cores de estado** (texto / fundo / borda), usadas em faixas de aviso e na situação:

| Estado | Texto | Fundo | Borda | Contraste texto/fundo |
|---|---|---|---|---|
| sucesso | `#0B6B3A` | `#E8F5EE` | `#B5DEC5` | 5,89:1 ✔ |
| alerta | `#8A4600` | `#FFF4E0` | `#F2D29B` | 6,52:1 ✔ |
| erro | `#B00017` | `#FDECEE` | `#F3BAC2` | 6,44:1 ✔ |
| info | `#1D4E9E` | `#EAF1FC` | `#BCD0F0` | 7,01:1 ✔ |
| neutro | `#475467` | `#F3F4F6` | `#E1E4EA` | 6,9:1 ✔ |

Os contrastes foram calculados com a fórmula WCAG 2.x pelo script `...\designer\contraste.py`. Regra: **a cor nunca é o único sinal**. Todo estado tem ícone e texto ("No campus", "Saiu", "CPF bloqueado: ...").

**Cores por tipo de acesso** (só no ponto ao lado do nome do tipo e, se necessário, no Painel), todas com contraste ≥ 4,5:1 no branco: Aluno `#1D4E9E`, Professor `#6B3FA0`, Funcionário `#0B6B3A`, Visitante `#8A4600`, Entregador `#B00017`, Prestador `#475467`.

### 4.2 Tipografia (fontes do Windows, nada para instalar)

| Token | Fonte (com reserva para Win 10) | Tamanho | Uso |
|---|---|---|---|
| `titulo_grande` | Segoe UI Variable Display Semibold → Segoe UI Semibold | 28 pt | "Portaria" no login |
| `titulo_pagina` | idem | 18 pt | "Entrada e saída", "Pessoas"... |
| `titulo_cartao` | Segoe UI Variable Text Semibold → Segoe UI Semibold | 12 pt | "Nova entrada", "Movimento" |
| `corpo` | Segoe UI Variable Text → Segoe UI | 10 pt | campos, tabela, texto |
| `corpo_semi` | Segoe UI Variable Text Semibold | 10 pt | avisos, item ativo do menu |
| `rotulo` | Segoe UI Variable Text Semibold | 9 pt | rótulo de campo, cabeçalho de tabela |
| `dica` | Segoe UI Variable Text | 9 pt | dicas, legendas |
| `numero` / `kpi` | Bahnschrift / Bahnschrift SemiBold | 20–54 pt | números do Painel, relógio do login, histórico da pessoa |
| `placa` | Bahnschrift SemiBold SemiCondensed | 22 pt | placa Mercosul |
| `icone` | Segoe Fluent Icons → Segoe MDL2 Assets | 11–12 pt | ícones (sem emoji) |

Regras: frases em caixa normal, **nada de CAIXA ALTA** em rótulos ("Total de registros", não "TOTAL DE REGISTROS"); o formato vai como apoio cinza ao lado do rótulo ("Entrada · dd/mm/aaaa hh:mm"); marca-se o que é **opcional**, não o obrigatório.

Ícones usados (código do glifo; no código Python escreva `chr(0xE8AB)` e nunca o caractere colado no arquivo): entrada/saída E8AB, pessoas E716, bloqueio E733, painel E9F9, usuários E7EF, sair E7E8, busca E721, adicionar E710, excluir E74D, editar E70F, relógio E823, desfazer E7A7, ok E73E, alerta E7BA, erro E783, info E946, seta E72A. Folha de conferência: `...\designer\glifos.png`.

### 4.3 Espaçamento, raios, tamanhos

| Token | Valor (px lógicos, multiplicar pela escala) |
|---|---|
| Escala de espaço | 4 · 8 · 12 · 16 · 20 · 24 · 32 · 48 |
| Margem da página | 24 |
| Respiro interno do cartão | 18–20 |
| Distância entre cartões | 16 |
| Altura de campo / botão | 36 (= 45 px reais a 125%, acima do alvo mínimo de 44) |
| Altura de linha da tabela | 34 |
| Raio: campo, aviso pequeno | 4 |
| Raio: botão, aviso, item de menu | 6 |
| Raio: cartão, placa | 8 / 7 |
| Raio: avatar | círculo |
| Largura da barra lateral | 232 |
| Contorno | 1 px; foco 2 px |

### 4.4 Componentes

| Componente | Especificação |
|---|---|
| **Botão primário** | Fundo `primario`, texto branco semibold, raio 6, altura 36. Hover `primario_hover`, pressionado `#10161F`. Pode mostrar a tecla ("Enter") em cinza claro. **Um por tela.** |
| **Botão secundário** | Fundo branco, contorno `borda_campo`, texto `texto`. Hover `superficie_2`. |
| **Botão perigo** | Fundo branco, contorno e texto de `erro`, com ícone de lixeira. Hover: fundo `erro` claro. Sempre com confirmação. |
| **Botão fantasma** | Sem fundo, texto `texto`. Hover `hover`. Para "Limpar formulário" e "Cancelar". |
| **Foco do teclado** | Todo botão e item de menu recebe Tab; com foco, o contorno vira `foco` com 2 px. Espaço/Enter acionam. |
| **Campo** | Branco, contorno `borda_campo` com raio 4 e **linha de baixo `traco_campo`** (como no Windows 11). Com foco, a linha de baixo vira 2 px `foco`. Ícone opcional à direita (relógio = "agora", lupa = busca). |
| **Combobox** | `ttk.Combobox` sem borda (estilo `Liso.TCombobox`) dentro da mesma moldura do campo. |
| **Aviso (faixa)** | Fundo, borda e texto do estado, raio 6, ícone à esquerda, ação opcional sublinhada à direita ("Registrar saída", "Ver bloqueio"). Substitui as dicas coloridas soltas. |
| **Toast** | Linha no rodapé da tabela: ícone ✓ verde + texto + link "Desfazer". Some em 10 s (como hoje). |
| **Tabela** | `Tabela.Treeview`: sem bordas, cabeçalho `superficie_2` em `rotulo` cinza, linhas de 34 px, zebra `superficie_2`, seleção `selecao` com texto escuro, primeira coluna "Situação" com bolinha (verde = no campus, cinza = saiu, vermelha = bloqueado), barra de rolagem fina sem setas. |
| **Cartão** | Branco, raio 8, contorno `borda`, título `titulo_cartao` e ações à direita do título. Sem a faixa vermelha no topo. |
| **Barra lateral** | Fundo `lateral`. Item = ícone + texto (40 px). O item ativo tem pílula branca e **traço vermelho UNA** de 3×18 px à esquerda. O hover tem fundo `hover`. O contador fica à direita, em cinza (Pessoas 128, Bloqueios 2). No rodapé: avatar com iniciais, nome, perfil e botão sair. |
| **Placa** | Canvas 200×66: borda escura de 2 px, faixa azul `#0B3C9C` com "BRASIL", "BR" e bandeira; caracteres em Bahnschrift. Sem placa: caixa tracejada clara "Sem veículo (a pé) / ABC1234 ou ABC1D23". |

---

## 5. Proposta por tela

### Moldura (todas as telas depois do login)

```
+----------------+----------------------------------------------------+
| [#] Portaria   | Título da página               [ação da página]    |
|     Universid. | subtítulo com o estado do momento                  |
|                | +--------------- cartão -------------------------+ |
| | Entrada e... | |                                                | |
|   Pessoas  128 | +------------------------------------------------+ |
|   Bloqueios  2 | +--------------- cartão -------------------------+ |
|   Painel       | |                                                | |
|   Usuários     | +------------------------------------------------+ |
| -------------- |                                                    |
| (CD) Carla     |                                                    |
| Admin.  [sair] |                                                    |
+----------------+----------------------------------------------------+
  "|" antes de "Entrada" = traço vermelho UNA do item ativo
```

- O cabeçalho vermelho sai e devolve uns 107 px de altura para a tabela. O usuário logado e o botão Sair vão para o rodapé da barra lateral.
- As abas viram **barra lateral**: navegação vertical aguenta 5 itens com contador e combina com o Windows 11 (Configurações, Outlook novo).
- Opcional (Windows 11, só `ctypes`): pintar a barra de título com a cor `lateral` via `DwmSetWindowAttribute(DWMWA_CAPTION_COLOR=35)`.

### Login

**Antes:** cartão pequeno com faixa vermelha, flutuando no cinza, embaixo do cabeçalho vermelho.
**Depois** (`depois\login.png`): tela dividida. **Painel vermelho UNA à esquerda** (o único lugar onde o vermelho ocupa área grande): símbolo da cancela, "Portaria", uma linha de descrição e um **relógio grande em Bahnschrift** com a data por extenso, que lembra o relógio de parede da guarita. À direita, o formulário: "Entrar", uma frase de ajuda, os campos Usuário e Senha, o aviso de erro como faixa vermelha clara, o botão primário de largura total "Entrar · Enter" e a dica "Esqueceu a senha? Peça ao administrador para redefinir." No primeiro acesso (criar administrador), o mesmo layout com 4 campos.

### Cadastro → "Entrada e saída"

**Depois** (`depois\cadastro_campus.png`, `cadastro_ok.png`, `cadastro_bloqueado.png`):

```
Entrada e saída                               Saída rápida (F2)
Segunda-feira, 19 de outubro . 2 no campus    [CPF ou placa   (lupa)] [Registrar saída  Enter]

+- Nova entrada ------------------------------- Limpar formulário -+
| CPF             Nome completo                      | Veículo     |
| [____________]  [________________________________] | [ PLACA ]   |
| [! Mariana está no campus desde 18:14.  Registrar saída]  | ----------- |
| Celular  só números  Placa  opcional  Tipo de acesso | Histórico   |
| [____________]  [____________]  [Aluno        v]   | 7     18/10 |
| Entrada  dd/mm/aaaa hh:mm  Saída  vazio = no campus| visitas     |
| [________ (h)]  [________ (h)]  [Registrar entrada Enter] | o Aluno |
+------------------------------------------------------------------+
+- Movimento  [Buscar...  (lupa)]  [Registrar saída] [Corrigir] [Excluir] -+
| Situação     Nome    CPF    Placa    Tipo de acesso    Entrada    Saída   |
| o No campus  ...                                                          |
| 8 registros . 2 no campus      ok Saída de Bruno registrada.  Desfazer   |
+---------------------------------------------------------------------------+
```

- A **saída rápida sobe para o cabeçalho da página**: é a ação mais frequente da guarita e o F2 continua levando o cursor até ela.
- A dica do CPF (`lbl_pessoa`) vira uma **faixa de status** que muda de estado: neutra ("Digite o CPF primeiro…"), verde ("Já cadastrado…"), âmbar ("está no campus desde…", com o atalho "Registrar saída"), vermelha ("CPF bloqueado…", com "Ver bloqueio") e azul ("Pessoa nova…").
- **Ficha da pessoa** à direita: a placa desenhada (atualiza enquanto se digita; placa bloqueada mostra a borda vermelha), o número de visitas, a última vinda e o tipo.
- Botões: **um primário** ("Registrar entrada · Enter"). "Limpar formulário" vira fantasma no título do cartão. "Registrar saída", "Corrigir" e "Excluir" (só para admin, na variante perigo) ficam na barra da tabela, porque agem sobre a linha selecionada.
- Os campos de data trocam o botão "Agora" por um **ícone de relógio dentro do campo**.
- Tabela: a coluna Situação com bolinha vem primeiro; a coluna Celular fica **escondida com `displaycolumns`** (os `values` continuam iguais, então os testes não mudam). O status e o "Desfazer" ficam no rodapé do cartão.

### Pessoas

**Antes:** busca, tabela com linhas inteiras verdes/vermelhas e um formulário embaixo, cortado pela borda da janela.
**Depois:** **lista + detalhe**.
- Esquerda (≈60%): título "Pessoas · 128 cadastradas · 2 no campus", busca e tabela (Situação com bolinha: verde no campus, vermelha bloqueado, sem cor quando fora).
- Direita (≈40%): cartão "Ficha" com nome em `titulo_cartao`, CPF em Bahnschrift, a placa desenhada, os números (visitas, última vinda), a faixa vermelha se estiver bloqueada e o formulário de edição (nome, celular, placa, tipo). Ações: "Registrar entrada" (primário) e "Salvar alterações" (secundário). Sem seleção: estado vazio "Escolha uma pessoa na lista para ver a ficha."

### Bloqueios

**Antes:** formulário com faixa vermelha, rótulos soltos, tabela cinza e "Remover bloqueio" num botão cinza grande.
**Depois:**
- Cabeçalho: "Bloqueios" e "2 ativos". À direita, botão perigo "+ Novo bloqueio" (só admin), que abre/fecha o cartão de formulário. Para o porteiro, uma faixa info: "CPFs e placas desta lista não podem entrar. Só um administrador cria ou remove bloqueios."
- Formulário em linha: Tipo (CPF/Placa), Valor, Motivo, [Cancelar] [Bloquear].
- Tabela: Situação com bolinha vermelha (ativo) ou cinza (removido); Tipo, CPF/Placa, Pessoa, Motivo, Bloqueado em, Por. Removidos em `texto_3`, não em `#999`. O interruptor "Mostrar removidos" vai para a barra da tabela, com fundo correto.
- "Remover bloqueio" vira botão secundário na barra da tabela, ativo só com uma linha selecionada.

### Painel (Dashboard)

**Antes:** 11 cartões com faixas de 6 cores, CAIXA ALTA e dois gráficos coloridos.
**Depois:**
- Linha de **4 números** (não 11): **No campus agora** (destaque: Bahnschrift 40 pt, verde), Entradas hoje, Permanência média e Com veículo. Rótulos em caixa normal e uma linha de apoio cinza.
- "Pessoas por tipo": **barras horizontais de uma cor só** (`texto_2`), com o valor e "x no campus" ao lado. Os seis cartões por tipo somem, porque o gráfico já mostra a mesma coisa.
- "Entradas nos últimos 7 dias": barras cinza-azuladas com **hoje em vermelho UNA** (o único destaque), linhas de grade claras e topo das barras com raio 4.
- Os dois gráficos ficam dentro de cartões, com título em `titulo_cartao` e estado vazio "Sem entradas neste período".

### Usuários

**Antes:** formulário de criação sempre aberto ocupando a lateral, botões laranja/azul e o histórico espremido embaixo.
**Depois:**
- Cabeçalho "Usuários" com o botão primário "+ Novo usuário", que abre o formulário num **diálogo** (Toplevel com o mesmo visual da janela Corrigir).
- Cartão "Contas": tabela com Usuário, Nome, Perfil e Situação (bolinha verde ativo / cinza desativado). Ações na barra: "Redefinir senha" (secundário) e "Desativar"/"Ativar" (o texto muda conforme a linha; perigo ao desativar).
- Cartão "Atividade" (antigo Histórico de ações) com busca por usuário/ação. Ocupa o resto da altura.

### Janela "Corrigir registro"

**Antes:** cartão com faixa vermelha, "Salvar correção" verde e "Cancelar" cinza à esquerda, e a tabela de histórico.
**Depois:**
- Diálogo branco, sem faixa. Título "Corrigir registro #12" e subtítulo cinza "Entrada de Carlos Andrade em 19/10/2026 17:14. Toda correção fica no histórico."
- Campos em 2 colunas com o componente Campo (o CPF em Bahnschrift).
- **Rodapé do diálogo** com fundo `superficie_2` e botões à direita: [Salvar correção] (primário) e [Cancelar] (secundário). Esc fecha e Enter salva (como hoje).
- "Histórico deste registro" como tabela compacta (linha de 30 px) e o detalhe numa faixa info ao clicar.

---

## 6. Plano de implementação

**Princípio:** trocar o visual sem trocar nomes. Todo atributo que os testes usam continua existindo e com o mesmo tipo de comportamento.

### Passos (rodar `python -m unittest` ao fim de cada um)

1. **`portaria/estilo.py`**: vira a casa dos tokens: `COR`, `Fontes`, `px()`, `ligar_nitidez()` e `aplicar_estilo_ttk()` (copiar de `prototipo\componentes.py`). **Manter** `FUNDO`, `VERMELHO`, `BORDA`, `fonte_lbl`, `fonte_dica`, `botao()` e `cartao()` como apelidos, para as telas continuarem importando. `botao(pai, texto, cor, comando, lado)` passa a criar o `Botao` novo, convertendo a cor antiga em variante (verde → primário, vermelho → perigo, o resto → secundário).
2. **`portaria/componentes.py`** (novo): `Cartao`, `Botao`, `Campo`, `Aviso`, `Placa`, `ItemMenu`, `bolinha`, `marca_cancela`. Adicionar `tests/test_componentes.py` (Botao: `cget("text")`, `invocar()`, teclado; Campo: `.entrada` aceita `insert/get/delete/validatecommand`).
3. **`portaria_universidade.py`**: chamar `ligar_nitidez()` **antes** de criar a janela. Isso só vale ao abrir o programa de verdade: nos testes a escala continua 1 e nada muda. Geometria inicial `px(1180)×px(760)`, mínimo `px(1000)×px(640)` e, se a tela for pequena, abrir maximizada (`state("zoomed")`).
4. **`portaria/interface.py`**:
   - Barra lateral + `ttk.Notebook` **com as abas escondidas**: `style.layout("Paginas.TNotebook.Tab", [])`. O menu chama `self.abas.select(frame)` e escuta `<<NotebookTabChanged>>` para acender o item. Assim `app.abas.select(...)`, `app.aba_cad` etc. continuam valendo nos testes.
   - `app.sessao` = rodapé da lateral (continua sem aparecer na tela de login); `app.lbl_usuario` continua um `tk.Label` com o perfil ("Administrador").
   - Cadastro no novo layout: `app.cpf`, `app.nome`, `app.celular` passam a ser o `.entrada` de um `Campo` (um `tk.Entry`, com a mesma API do `ttk.Entry`); `app.tipo` continua `ttk.Combobox`; `app.lbl_pessoa` = `aviso.lbl` (um `tk.Label`); `_dica_pessoa(texto, cor)` vira `aviso.mostrar(estado, texto, ícone)`.
   - `app.lbl_dica_placa` continua sendo um `tk.Label` com o texto `DICA_PLACA` (o apoio ao lado do rótulo "Placa"). O alerta "PLACA BLOQUEADA — …" segue nele e também pinta a placa desenhada.
   - Tabela: estilo `Tabela.Treeview`, `show="tree headings"`, bolinha no `#0`, zebra e `displaycolumns` sem Celular. **Os `values` não mudam** (inclusive "— dentro —").
   - `lbl_aviso` e `btn_desfazer` continuam mostrados/escondidos com `pack` (um teste confere `winfo_manager() == "pack"`).
   - Dashboard: 4 números, gráficos de uma cor e `px()` em todas as medidas do Canvas.
5. **`portaria/tela_login.py`**: layout dividido. `campo_login`, `campo_senha` (`show="•"`) e `campo_confirmacao` = `.entrada` dos Campos; `lbl_erro` = `Aviso.lbl` (a faixa só aparece com texto). **Corrigir o laço** que liga o Enter procurando `isinstance(campo, ttk.Entry)` em `miolo.winfo_children()`: com o Campo, o Entry fica um nível abaixo. Ligar explicitamente na lista de campos.
6. **`portaria/tela_pessoas.py`, `tela_bloqueios.py`, `tela_usuarios.py`, `tela_edicao.py`**: novo layout de cada tela (seção 5), mantendo `tabela`, `lbl_total`, `lbl_titulo`, `historico`, `lbl_detalhe`, `busca`, `ver_removidos` etc.
7. **Conferência visual**: gerar os prints de novo (adaptar `shots_antes.py`), conferir o contraste e testar no Windows 10 se possível (reserva de fontes e ícones).
8. **PyInstaller**: nada novo para empacotar. Conferir que o .exe sai nítido (o `ligar_nitidez()` resolve; também dá para pôr `dpiAware` no manifesto).

### Riscos para os testes e como evitar

| Risco | Onde | Como evitar |
|---|---|---|
| `isinstance(w, tk.Button)` para provar que o porteiro **não** vê "Excluir" | `test_porteiro_nao_ve_botao_excluir...` | Com o `Botao` (Canvas), o teste passaria **sem testar nada**. Atualizar o teste para considerar `Botao` também (ex.: `hasattr(w, "texto")`). O `Botao` já responde `cget("text")`. |
| `isinstance(w, tk.Label)` procurando "dd/mm/aaaa hh:mm" | `test_rotulo_mostra_formato_legivel` | O apoio ao lado do rótulo "Entrada" continua sendo `tk.Label` com esse texto. |
| Textos conferidos literalmente: "— dentro —", "No campus", "CPF BLOQUEADO — …", "No campus agora: 1", "pelo menos", "incorretos", "Aguarde" | vários | Fase 1: **não mudar esses textos**. Se quiser a escrita nova ("CPF bloqueado: …"), mudar código e teste no mesmo commit. |
| Abas → barra lateral | `app.abas.select(...)` | Notebook com abas escondidas (passo 4). |
| `ttk.Entry` → `tk.Entry` dentro do Campo | `app.cpf` e outros | Mesma API; os testes não checam o tipo. `validatecommand` e `textvariable` funcionam igual. |
| Trocar `showinfo` de sucesso por toast | `msg.showinfo` nos testes | Fica para uma fase posterior e exige ajustar os testes junto. |
| Medidas em pixel com DPI | geometria, `rowheight`, larguras de coluna, gráficos | Tudo passa por `px()`. Nos testes, escala 1. |
| Ícones colados como caractere no código | todos | Escrever `chr(0xE8AB)`: os glifos são de uso privado e uma ferramenta de limpeza pode apagá-los. |

### Ordem sugerida de commits

1. `estilo.py` + `componentes.py` + testes dos componentes (nenhuma tela muda).
2. Nitidez (DPI) + `px()`: o ganho imediato, com risco baixo.
3. Moldura (barra lateral) + Login.
4. Entrada e saída (Cadastro).
5. Pessoas, Bloqueios, Usuários, Corrigir.
6. Painel.

---

## 7. Protótipo (depois)

Feito **só com biblioteca padrão** (tkinter + ctypes), dados falsos, sem importar o projeto.

| Arquivo | Caminho |
|---|---|
| Componentes e tokens | `prototipo/componentes.py` |
| Telas (Cadastro e Login) | `prototipo/prototipo.py` |

Para rodar: `python prototipo.py` (Cadastro), `python prototipo.py login`, `python prototipo.py cadastro --estado ok|campus|bloqueado|novo`, `--borrado` (sem DPI, para comparar).

| Print | Caminho |
|---|---|
| Cadastro: pessoa no campus (aviso âmbar, sem veículo) | `...\designer\depois\cadastro_campus.png` |
| Cadastro: pessoa conhecida (aviso verde, placa Mercosul) | `...\designer\depois\cadastro_ok.png` |
| Cadastro: CPF bloqueado (aviso vermelho) | `...\designer\depois\cadastro_bloqueado.png` |
| Cadastro sem correção de DPI (para comparar a nitidez) | `...\designer\depois\cadastro_sem_dpi.png` |
| Login | `...\designer\depois\login.png` |

Pasta completa: `depois/`

**Avaliação franca do protótipo:** o caminho (a) chegou a um resultado de app atual de Windows 11. Cantos e bolinhas saem lisos graças à mistura com o fundo, o texto sai nítido e a hierarquia ficou clara. Limitações vistas na prática:
- A janela de 1180×760 mostra só ~4–5 linhas da tabela de movimento. Em telas maiores ou com a janela maximizada, a tabela cresce.
- O `Combobox` aberto (a lista) ainda tem a aparência padrão. Dá para ajustar a fonte e as cores, mas não o canto.
- As caixas de diálogo `messagebox` continuam as do Windows (nítidas, mas fora do visual).

---

## 8. Notas sobre as ferramentas consultadas

- **ui-ux-pro-max**: confirmou o padrão "painel administrativo denso em dados", com os pontos de contraste mínimo de 4,5:1, rótulos visíveis nos campos, feedback de envio, foco visível e nada de emoji como ícone. A paleta azul/laranja e as fontes Fira sugeridas foram **descartadas**: não existem no Windows sem instalação e a marca aqui é o vermelho UNA.
- **frontend-design**: guiou a escolha de um único elemento marcante (a placa e o relógio do login), o vermelho só como identidade, a escrita direta ("Registrar entrada", "Limpar formulário", "Esqueceu a senha? Peça ao administrador…") e a ausência de CAIXA ALTA e de rótulos decorativos.
- **ui-design-system**: a estrutura de tokens (cores, tipo, espaço, raios) segue a skill, mas o script `design_token_generator.py` dela tem erro de sintaxe (linha 64) e não rodou. Os tokens foram montados à mão e o contraste foi verificado com `...\designer\contraste.py`.

---

## 9. Implementação (Onda 2)

O sistema real foi redesenhado com este sistema de design. Prints do app de
verdade (banco temporário com dados de exemplo, escala 125%, relógio fixo em
19:14): `docs/design/final/`.

| Tela | Print |
|---|---|
| Login e primeiro acesso | `final/login.png`, `final/primeiro_acesso.png` |
| Entrada e saída: já cadastrado, no campus, bloqueado, pessoa nova | `final/cadastro_ok.png`, `final/cadastro_campus.png`, `final/cadastro_bloqueado.png`, `final/cadastro_novo.png` |
| Entrada e saída vista pelo porteiro (CPF mascarado, sem Excluir) | `final/cadastro_porteiro.png` |
| Entrada e saída no notebook 1366×768 a 125% (layout compacto) | `final/cadastro_compacto.png` |
| Pessoas (ficha comum e bloqueada) | `final/pessoas.png`, `final/pessoas_bloqueada.png` |
| Bloqueios (administrador e porteiro) | `final/bloqueios_admin.png`, `final/bloqueios_porteiro.png` |
| Painel | `final/painel.png` |
| Usuários | `final/usuarios.png` |
| Diálogos: Corrigir, Trocar senha, Novo usuário, Exportar CSV | `final/corrigir.png`, `final/trocar_senha.png`, `final/novo_usuario.png`, `final/exportar_csv.png` |
| Corrigir visto pelo porteiro (CPF mascarado; o lápis libera digitar outro) | `final/corrigir_porteiro.png` |

Diferenças conscientes em relação ao protótipo:

- A tabela Movimento mostra o dia (entradas de hoje + quem está no campus); a
  busca procura no histórico inteiro. A coluna Saída mostra "—" para quem está
  dentro (antes "— dentro —"); a situação fica na 1ª coluna.
- A placa bloqueada aparece na própria placa desenhada (borda e letras
  vermelhas) e numa linha abaixo dela; o apoio ao lado do rótulo "Placa" vira
  "bloqueada".
- Mensagens de bloqueio em caixa normal ("CPF bloqueado: motivo").
- Registrar entrada mostra o aviso no rodapé do Movimento em vez de uma caixa.
- Menu do usuário (Trocar minha senha, Sair) no botão de mais opções (três pontos) do rodapé da barra.
- Painel: o total de registros foi para o subtítulo; o gráfico de 7 dias não
  tem números no eixo (o valor fica em cima de cada barra).
- Janela Corrigir em 4 colunas (duas linhas de campos) e histórico com 2
  linhas visíveis, para caber com os botões num notebook 1366×768 a 125%.
- **Layout compacto da Entrada e saída** (`final/cadastro_compacto.png`):
  quando a página fica baixa (menos de 740 px lógicos, como a janela
  maximizada num notebook 1366×768 a 125%, ~1366×670 px reais), o formulário
  passa a 4 colunas em duas linhas, a ficha da pessoa (placa desenhada e
  histórico) é recolhida, a faixa de situação ocupa o lugar do título
  "Nova entrada" ao lado de "Limpar" e "Registrar entrada", os espaços
  diminuem e as linhas da tabela ficam com 30 px. Assim o Movimento continua
  mostrando umas 4 linhas. Na tela grande o layout é o de sempre.
- As colunas das tabelas dividem a largura disponível na proporção do
  projeto (antes a última coluna ficava cortada em telas menores); na tela
  pequena encolhem até 85% e, abaixo disso, a última fica cortada (caso da
  lista de Pessoas a 1366 px, por causa da ficha ao lado).
- A janela aceita ficar com até 1000×500 px lógicos (antes 1000×640, maior
  que a área útil de um notebook 1366×768 a 125%).
- `depois/cadastro_ok.png` era, por engano, a captura de outra janela; foi
  refeito a partir do protótipo aprovado (`prototipo.py cadastro --estado ok`).

## 10. Tema escuro ("Guarita à noite")

Pedido do aluno: modo noturno com três opções — **Claro**, **Escuro** e
**Seguir o Windows** —, escolhido por **cada usuário** no menu da conta (três
pontos no rodapé da barra lateral) e trocado **sem fechar o programa**.

### Ideia

A guarita à noite: ardósia azulada, nem preto puro (cansa e "vaza" o brilho
das letras) nem o claro invertido. As superfícies **sobem de tom** em vez de
ganhar sombra (fundo `#13171D` → barra lateral `#0F1217` → cartão `#1B2028` →
cabeçalho e zebra `#222833`). A disciplina de cor continua a mesma: tela
calma e cor só quando importa.

Decisões:

- **O botão principal vira claro** (`#E9EDF3` com texto `#13171D`, 15,3:1).
  No claro ele é o ponto mais escuro da tela; no escuro, o mais claro: nos
  dois temas é o elemento de maior contraste, que é o papel dele. A dica
  "Enter" dentro dele ganhou token próprio (`dica_invertida`).
- **Estados** viram texto claro sobre fundo escuro tingido (verde `#5FD08F`
  sobre `#12291E`, âmbar `#F2B45A` sobre `#2E2210`, vermelho `#FF8A93` sobre
  `#33161A`, azul `#8DB8FF` sobre `#14233D`), com borda um tom acima. As
  linhas em destaque da tabela (saída pendente, tempo excedido) usam esses
  fundos.
- **Vermelho UNA**: `#E01A32` nos traços e na barra de "Hoje" (um pouco mais
  vivo, para aparecer no escuro); o **painel do login** fica num vermelho mais
  fundo, `#A8001A`, para não ofuscar à noite (texto branco a 7,8:1).
- **Placa Mercosul continua branca** (é um objeto de verdade): tokens
  `placa_fundo`, `placa_texto` e `placa_erro` iguais nos dois temas.
- **Seleção** azul-acinzentada (`#263A5C`), **foco** e links em `#7DB1FF`.
- **Gráficos**: barras horizontais em `texto_2`, barras dos 7 dias em `barra`
  `#6F7A8C` e "Hoje" em vermelho UNA.
- Cores de **tipo de acesso** clareadas para o fundo escuro (Aluno `#8DB8FF`,
  Professor `#C3A2F0`, Funcionário `#5FD08F`, Visitante `#F2B45A`,
  Entregador `#FF8A93`, Prestador `#B6BFCC`).
- **Tela de login segue sempre o Windows**: ela pertence à estação, não a
  um usuário; usar "o tema do último usuário" exigiria guardar quem usou o
  computador por último (no banco, que é compartilhado entre as estações) e
  mudaria a tela de um porteiro por causa de outro. Depois do login vale a
  preferência de quem entrou; ao sair, volta o tema do Windows.
- **Usuários que já existiam começam no Claro** (como o programa sempre
  abriu: nada muda para eles até escolherem); usuários novos começam em
  "Seguir o Windows".
- **Barra de título**: no Windows 10 (20H1+) e 11 ela fica escura no tema
  escuro (`DwmSetWindowAttribute`, atributo 20, via `ctypes`), também nos
  diálogos. Se o Windows recusar, nada quebra: a barra fica como estava.

Ajustes que valeram também para o claro: `barra` passou de `#AEB7C6` para
`#858E9F` (bolinha "Saiu" e barras do gráfico com 3:1, o mínimo de elemento
gráfico); o "Saiu" escrito no histórico da pessoa passou a usar `texto_3`
(era a cor das barras, abaixo de 4,5:1); e o contorno bege que o tema `clam`
desenhava em volta das páginas (Notebook) sumiu.

### Paleta (mesmos nomes de token nos dois temas)

| Token | Claro | Escuro |
|---|---|---|
| `marca` | #D9001B | #E01A32 |
| `marca_escura` | #B80017 | #C8001C |
| `marca_press` | #9A0013 | #B0001A |
| `painel_login` | #D9001B | #A8001A |
| `texto_sobre_marca` | #FFFFFF | #FFFFFF |
| `fundo` | #F3F4F6 | #13171D |
| `lateral` | #EEF0F3 | #0F1217 |
| `superficie` | #FFFFFF | #1B2028 |
| `superficie_2` | #F8F9FB | #222833 |
| `borda` | #E1E4EA | #2D3440 |
| `borda_campo` | #C5CBD5 | #3E4756 |
| `traco_campo` | #8C95A6 | #7A8599 |
| `texto` | #1B2330 | #E9EDF3 |
| `texto_2` | #475467 | #B6BFCC |
| `texto_3` | #5B6578 | #A0AABA |
| `selecao` | #E3E9F4 | #263A5C |
| `hover` | #E8EBF0 | #262D38 |
| `press` | #DDE1E8 | #2F3744 |
| `barra` | #858E9F | #6F7A8C |
| `rolagem` | #CDD3DC | #4A5465 |
| `primario` | #1B2330 | #E9EDF3 |
| `primario_hover` | #2E3A4D | #D2D9E3 |
| `primario_press` | #10161F | #B9C2CF |
| `texto_invertido` | #FFFFFF | #13171D |
| `dica_invertida` | #AEB7C6 | #4E5868 |
| `foco` | #1F5FBF | #7DB1FF |
| `sucesso` | #0B6B3A | #5FD08F |
| `alerta` | #8A4600 | #F2B45A |
| `erro` | #B00017 | #FF8A93 |
| `erro_press` | #F9D9DE | #4A1E24 |
| `info` | #1D4E9E | #8DB8FF |
| `placa_fundo` | #FFFFFF | #FFFFFF |
| `placa_texto` | #1B2330 | #1B2330 |
| `placa_erro` | #B00017 | #B00017 |
| `placa_azul` | #0B3C9C | #0B3C9C |
| `placa_verde` | #009B3A | #009B3A |

Estados (texto, fundo, borda) e cores de tipo: `ESTADOS` e `TIPOS_POR_TEMA`
em `portaria/estilo.py`.

### Como funciona no código

- `estilo.py` tem `PALETAS`, `ESTADOS` e `TIPOS_POR_TEMA` (claro e escuro) e
  `usar_tema(nome)`, que troca o **conteúdo** de `COR`, `ESTADO` e
  `CORES_TIPO` (os mesmos dicionários de sempre: as telas continuam
  escrevendo `COR["texto"]`). Nenhum módulo guarda uma cor numa constante
  (ficaria com o tema da importação): as tabelas de situação guardam o nome
  do token, e as cores dos botões são lidas na hora
  (`Botao.cores_da_variante`).
- `aplicar_tema(janela)` refaz os estilos ttk (Treeview: fundo, zebra,
  seleção, cabeçalho; Combobox e a lista dele; barra de rolagem; Notebook) e
  as cores padrão do tk (`option_add`: menu da conta, caixa de senha do
  `simpledialog`).
- As imagens de canto arredondado ficam num **cache por tema** (voltar ao
  tema anterior reaproveita as dele).
- `resolver_tema("sistema")` lê `AppsUseLightTheme` em
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize`
  (`winreg`); fora do Windows ou sem a chave, claro.
- A troca (`app.trocar_tema`) grava a escolha (`usuarios.tema`, banco v9),
  aplica as cores e **remonta** a barra lateral e as páginas, voltando à
  mesma página e devolvendo o que estava digitado na Entrada e saída (CPF,
  nome, celular, placa, tipo, entrada editada, saída, busca e a lista
  Pessoas/Veículos). Janelas abertas (ex.: Corrigir) são fechadas.

### Contraste (WCAG 2.x, conferido por teste)

Fórmula da luminância relativa da WCAG; texto ≥ 4,5:1 e elemento gráfico
(linha do campo, anel de foco, barras, bolinhas) ≥ 3:1. A lista sai de
`estilo.pares_de_contraste()` e o teste
`tests/test_tema.py::test_contraste_wcag_aa_em_todos_os_pares_dos_dois_temas`
confere cada par nos dois temas: 74 pares por tema, todos passam (menor
texto: 4,8:1 nos dois; menor gráfico: 3,0 no claro e 3,4 no escuro).

| Par (frente / fundo) | Claro | Escuro | Mínimo |
|---|---|---|---|
| texto / fundo | 14,4 (#1B2330 / #F3F4F6) | 15,3 (#E9EDF3 / #13171D) | 4,5 |
| texto_2 / fundo | 7,0 (#475467 / #F3F4F6) | 9,7 (#B6BFCC / #13171D) | 4,5 |
| texto_3 / fundo | 5,3 (#5B6578 / #F3F4F6) | 7,7 (#A0AABA / #13171D) | 4,5 |
| texto / lateral | 13,8 (#1B2330 / #EEF0F3) | 16,0 (#E9EDF3 / #0F1217) | 4,5 |
| texto_2 / lateral | 6,7 (#475467 / #EEF0F3) | 10,1 (#B6BFCC / #0F1217) | 4,5 |
| texto_3 / lateral | 5,1 (#5B6578 / #EEF0F3) | 8,0 (#A0AABA / #0F1217) | 4,5 |
| texto / superficie | 15,8 (#1B2330 / #FFFFFF) | 13,9 (#E9EDF3 / #1B2028) | 4,5 |
| texto_2 / superficie | 7,7 (#475467 / #FFFFFF) | 8,8 (#B6BFCC / #1B2028) | 4,5 |
| texto_3 / superficie | 5,9 (#5B6578 / #FFFFFF) | 7,0 (#A0AABA / #1B2028) | 4,5 |
| texto / superficie_2 | 15,0 (#1B2330 / #F8F9FB) | 12,6 (#E9EDF3 / #222833) | 4,5 |
| texto_2 / superficie_2 | 7,3 (#475467 / #F8F9FB) | 8,0 (#B6BFCC / #222833) | 4,5 |
| texto_3 / superficie_2 | 5,6 (#5B6578 / #F8F9FB) | 6,3 (#A0AABA / #222833) | 4,5 |
| texto / hover | 13,2 (#1B2330 / #E8EBF0) | 11,8 (#E9EDF3 / #262D38) | 4,5 |
| texto_2 / hover | 6,4 (#475467 / #E8EBF0) | 7,5 (#B6BFCC / #262D38) | 4,5 |
| texto_3 / hover | 4,9 (#5B6578 / #E8EBF0) | 5,9 (#A0AABA / #262D38) | 4,5 |
| texto / selecao | 13,0 (#1B2330 / #E3E9F4) | 9,7 (#E9EDF3 / #263A5C) | 4,5 |
| texto_3 / selecao (linha apagada selecionada) | 4,8 (#5B6578 / #E3E9F4) | 4,9 (#A0AABA / #263A5C) | 4,5 |
| foco (link) / superficie | 6,1 (#1F5FBF / #FFFFFF) | 7,5 (#7DB1FF / #1B2028) | 4,5 |
| foco (link) / fundo | 5,5 (#1F5FBF / #F3F4F6) | 8,2 (#7DB1FF / #13171D) | 4,5 |
| texto_invertido / primario | 15,8 (#FFFFFF / #1B2330) | 15,3 (#13171D / #E9EDF3) | 4,5 |
| texto_invertido / primario_hover | 11,5 (#FFFFFF / #2E3A4D) | 12,6 (#13171D / #D2D9E3) | 4,5 |
| texto_invertido / primario_press | 18,2 (#FFFFFF / #10161F) | 10,0 (#13171D / #B9C2CF) | 4,5 |
| dica_invertida / primario | 7,8 (#AEB7C6 / #1B2330) | 6,1 (#4E5868 / #E9EDF3) | 4,5 |
| dica_invertida / primario_hover | 5,7 (#AEB7C6 / #2E3A4D) | 5,1 (#4E5868 / #D2D9E3) | 4,5 |
| texto_3 / hover (botão desativado) | 4,9 (#5B6578 / #E8EBF0) | 5,9 (#A0AABA / #262D38) | 4,5 |
| texto_sobre_marca / marca | 5,3 (#FFFFFF / #D9001B) | 4,8 (#FFFFFF / #E01A32) | 4,5 |
| texto_sobre_marca / marca_escura | 6,9 (#FFFFFF / #B80017) | 6,0 (#FFFFFF / #C8001C) | 4,5 |
| texto_sobre_marca / marca_press | 8,8 (#FFFFFF / #9A0013) | 7,3 (#FFFFFF / #B0001A) | 4,5 |
| texto_sobre_marca / painel_login | 5,3 (#FFFFFF / #D9001B) | 7,8 (#FFFFFF / #A8001A) | 4,5 |
| estado sucesso: texto / fundo | 5,9 (#0B6B3A / #E8F5EE) | 8,0 (#5FD08F / #12291E) | 4,5 |
| texto / fundo do estado sucesso (linha em destaque) | 14,1 (#1B2330 / #E8F5EE) | 13,1 (#E9EDF3 / #12291E) | 4,5 |
| estado alerta: texto / fundo | 6,5 (#8A4600 / #FFF4E0) | 8,5 (#F2B45A / #2E2210) | 4,5 |
| texto / fundo do estado alerta (linha em destaque) | 14,5 (#1B2330 / #FFF4E0) | 13,2 (#E9EDF3 / #2E2210) | 4,5 |
| estado erro: texto / fundo | 6,4 (#B00017 / #FDECEE) | 7,3 (#FF8A93 / #33161A) | 4,5 |
| texto / fundo do estado erro (linha em destaque) | 13,8 (#1B2330 / #FDECEE) | 14,1 (#E9EDF3 / #33161A) | 4,5 |
| estado info: texto / fundo | 7,0 (#1D4E9E / #EAF1FC) | 7,8 (#8DB8FF / #14233D) | 4,5 |
| texto / fundo do estado info (linha em destaque) | 13,9 (#1B2330 / #EAF1FC) | 13,4 (#E9EDF3 / #14233D) | 4,5 |
| estado neutro: texto / fundo | 7,0 (#475467 / #F3F4F6) | 8,0 (#B6BFCC / #222833) | 4,5 |
| texto / fundo do estado neutro (linha em destaque) | 14,4 (#1B2330 / #F3F4F6) | 12,6 (#E9EDF3 / #222833) | 4,5 |
| sucesso / superficie | 6,6 (#0B6B3A / #FFFFFF) | 8,5 (#5FD08F / #1B2028) | 4,5 |
| sucesso / fundo | 6,0 (#0B6B3A / #F3F4F6) | 9,3 (#5FD08F / #13171D) | 4,5 |
| alerta / superficie | 7,1 (#8A4600 / #FFFFFF) | 8,9 (#F2B45A / #1B2028) | 4,5 |
| alerta / fundo | 6,5 (#8A4600 / #F3F4F6) | 9,8 (#F2B45A / #13171D) | 4,5 |
| erro / superficie | 7,3 (#B00017 / #FFFFFF) | 7,3 (#FF8A93 / #1B2028) | 4,5 |
| erro / fundo | 6,7 (#B00017 / #F3F4F6) | 8,0 (#FF8A93 / #13171D) | 4,5 |
| info / superficie | 8,0 (#1D4E9E / #FFFFFF) | 8,1 (#8DB8FF / #1B2028) | 4,5 |
| info / fundo | 7,2 (#1D4E9E / #F3F4F6) | 8,9 (#8DB8FF / #13171D) | 4,5 |
| tipo Aluno / superficie | 8,0 (#1D4E9E / #FFFFFF) | 8,1 (#8DB8FF / #1B2028) | 4,5 |
| tipo Aluno / superficie_2 | 7,6 (#1D4E9E / #F8F9FB) | 7,4 (#8DB8FF / #222833) | 4,5 |
| tipo Aluno / selecao | 6,5 (#1D4E9E / #E3E9F4) | 5,7 (#8DB8FF / #263A5C) | 4,5 |
| tipo Professor / superficie | 7,4 (#6B3FA0 / #FFFFFF) | 7,6 (#C3A2F0 / #1B2028) | 4,5 |
| tipo Professor / superficie_2 | 7,0 (#6B3FA0 / #F8F9FB) | 6,9 (#C3A2F0 / #222833) | 4,5 |
| tipo Professor / selecao | 6,1 (#6B3FA0 / #E3E9F4) | 5,3 (#C3A2F0 / #263A5C) | 4,5 |
| tipo Funcionário / superficie | 6,6 (#0B6B3A / #FFFFFF) | 8,5 (#5FD08F / #1B2028) | 4,5 |
| tipo Funcionário / superficie_2 | 6,3 (#0B6B3A / #F8F9FB) | 7,7 (#5FD08F / #222833) | 4,5 |
| tipo Funcionário / selecao | 5,4 (#0B6B3A / #E3E9F4) | 5,9 (#5FD08F / #263A5C) | 4,5 |
| tipo Visitante / superficie | 7,1 (#8A4600 / #FFFFFF) | 8,9 (#F2B45A / #1B2028) | 4,5 |
| tipo Visitante / superficie_2 | 6,7 (#8A4600 / #F8F9FB) | 8,1 (#F2B45A / #222833) | 4,5 |
| tipo Visitante / selecao | 5,8 (#8A4600 / #E3E9F4) | 6,2 (#F2B45A / #263A5C) | 4,5 |
| tipo Entregador / superficie | 7,3 (#B00017 / #FFFFFF) | 7,3 (#FF8A93 / #1B2028) | 4,5 |
| tipo Entregador / superficie_2 | 7,0 (#B00017 / #F8F9FB) | 6,6 (#FF8A93 / #222833) | 4,5 |
| tipo Entregador / selecao | 6,0 (#B00017 / #E3E9F4) | 5,1 (#FF8A93 / #263A5C) | 4,5 |
| tipo Prestador de serviço / superficie | 7,7 (#475467 / #FFFFFF) | 8,8 (#B6BFCC / #1B2028) | 4,5 |
| tipo Prestador de serviço / superficie_2 | 7,3 (#475467 / #F8F9FB) | 8,0 (#B6BFCC / #222833) | 4,5 |
| tipo Prestador de serviço / selecao | 6,3 (#475467 / #E3E9F4) | 6,1 (#B6BFCC / #263A5C) | 4,5 |
| placa: caracteres / placa | 15,8 (#1B2330 / #FFFFFF) | 15,8 (#1B2330 / #FFFFFF) | 4,5 |
| placa bloqueada / placa | 7,3 (#B00017 / #FFFFFF) | 7,3 (#B00017 / #FFFFFF) | 4,5 |
| placa: BRASIL / faixa azul | 9,8 (#FFFFFF / #0B3C9C) | 9,8 (#FFFFFF / #0B3C9C) | 4,5 |
| traco_campo / superficie (linha do campo) | 3,0 (#8C95A6 / #FFFFFF) | 4,4 (#7A8599 / #1B2028) | 3,0 |
| foco / superficie (anel de foco) | 6,1 (#1F5FBF / #FFFFFF) | 7,5 (#7DB1FF / #1B2028) | 3,0 |
| barra / superficie (gráfico, bolinha Saiu) | 3,3 (#858E9F / #FFFFFF) | 3,8 (#6F7A8C / #1B2028) | 3,0 |
| barra / superficie_2 (bolinha na zebra) | 3,1 (#858E9F / #F8F9FB) | 3,4 (#6F7A8C / #222833) | 3,0 |
| marca / superficie (barra de hoje) | 5,3 (#D9001B / #FFFFFF) | 3,4 (#E01A32 / #1B2028) | 3,0 |
| texto_2 / superficie_2 (barra horizontal) | 7,3 (#475467 / #F8F9FB) | 8,0 (#B6BFCC / #222833) | 3,0 |

### Limitações

- As **caixas de mensagem nativas** do Windows (aviso, erro, Sim/Não) e o
  "Salvar como" continuam no visual do Windows (claro ou escuro conforme o
  próprio Windows; o Tk não controla essas janelas).
- O **menu da conta** fica escuro, mas a moldura dele é desenhada pelo
  Windows (contorno claro fino). Por isso o tema fica direto no menu, sem
  submenu: a seta de submenu do Windows sairia preta.
- "Seguir o Windows" é lido ao entrar e ao escolher no menu; se o Windows
  mudar de tema com o programa aberto, a troca acontece no próximo login (ou
  escolhendo de novo no menu) — trocar sozinho fecharia janelas abertas no
  meio do trabalho.
- Ao trocar o tema, a página volta para a primeira seção dela (ex.:
  Configurações volta para "Funcionamento") e a seleção das tabelas se perde.

Prints (tamanho normal e 1366×670, escala 125%, dados fictícios):
`final/escuro_*.png` — login, Entrada e saída (ficha, bloqueado, pendências,
veículos), calendário e relógio, "Saiu com o veículo?", Pessoas (ficha e
visitas), Bloqueios, Painel, Usuários, Configurações (as três seções),
autorização do administrador, trocar senha, menu da conta, barra de título
e a troca para o claro sem fechar (`escuro_troca_para_claro.png`).
