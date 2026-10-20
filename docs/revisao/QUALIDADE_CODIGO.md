# Revisão de qualidade do código — Sistema de Portaria

Revisão geral de estrutura, duplicação e preparação para a reforma visual.
Base: código atual de `portaria/` e `tests/` (199 testes passando, ~33–36 s).
Critérios: skills *code-reviewer* (checklist de revisão) e *clean-code*
(SRP, DRY, KISS, funções pequenas, nada de arquitetura além do necessário).

> Observação: o script `code_quality_checker.py` da skill code-reviewer foi
> conferido e é só um esqueleto (não faz análise nenhuma). No lugar dele foram
> feitas medições próprias, fora do projeto: tamanho das funções (via `ast`),
> contagem de estilos fixos no código, tempo de cada parte dos testes e perfil
> (`cProfile`) da criação da janela.

---

## 1. Resumo

**O que está bom (manter):**
- A separação **regras × banco × tela** já existe e é o ponto forte do projeto:
  `validacao.py`, `usuarios.py` e `consultas.py` não importam Tkinter e são
  testados sem janela, com o relógio injetado (`agora=`, `relogio=`).
- `dados.py` grava cada operação **e** o histórico na mesma transação, usa
  parâmetros `?` em todo SQL e converte erros do SQLite em `ErroDados`.
- As regras de negócio estão comentadas (RN02, RN11, RN12, "VERIFICAÇÃO SEMÂNTICA").
- Os testes de tela clicam de verdade com a janela oculta: isso vai ser a rede
  de segurança da reforma visual.

**O que atrapalha a reforma visual:**
1. **`interface.py` (845 linhas) faz seis coisas**: janela/tema, sessão, ações
   do Cadastro, montagem do Cadastro (`_montar_cadastro` tem 146 linhas),
   Dashboard e desenho de gráficos.
2. **O visual está espalhado**: 70 ocorrências de `"Segoe UI"` e 40 cores
   em hexadecimal fixas em 8 arquivos; `estilo.py` tem só 3 cores e 2 fontes.
   Quatro botões e dois cartões copiam o estilo em vez de usar `botao()`/`cartao()`.
3. **Montagem de formulário repetida**: 6 versões de "rótulo + campo", 5 de
   "tabela + rolagem", 3 do "placa sempre maiúscula", 2 do "só números", 2 da
   tabela de histórico — cada uma com fonte, cor e espaçamento um pouco diferentes.
4. **As telas mexem no interior do `AppPortaria`** (`app._avisar`,
   `app.registros = ...`, `app.busca.get()`, `app.janela.register`).
5. **Os testes dependem dos nomes internos dos widgets** e fazem `patch` de
   `messagebox` em 5 módulos: se a reforma renomear ou mover algo, os testes
   quebram ou, pior, passam sem testar.
6. **Lentidão dos testes**: ~11 s dos ~33 s são PBKDF2 (2 hashes de 200 mil
   iterações em cada teste de tela); ~20 s são criar e destruir um `tk.Tk()`
   por teste.

Nenhum achado é falha de segurança grave nem perda de dados no uso normal; o
mais sério em comportamento são erros de arquivo/data que fecham o programa na
abertura (Q15).

---

## 2. Achados

Prioridade: **Alta** = fazer antes da reforma visual · **Média** = fazer junto ·
**Baixa** = quando der. Esforço: **P** (até 1 h) · **M** (meio dia) · **G** (1 dia ou mais).

### 2.1 Código de produção

| ID | Prior. | Arquivo:linha | Problema | Sugestão | Esf. |
|----|--------|---------------|----------|----------|------|
| Q01 | Alta | `interface.py:443-845` (`_montar_cadastro` 529-674 = 146 linhas) | Classe `AppPortaria` acumula janela, sessão, aba Cadastro (montagem + ações), Dashboard e gráficos. Qualquer mudança visual mexe no arquivo central. | Extrair `tela_cadastro.py` (classe `AbaCadastro`, igual às outras abas), `tela_dashboard.py` (`AbaDashboard`) e `graficos.py` (as duas funções de desenho). `AppPortaria` fica com janela, sessão, abas e serviços (~200 linhas). Ver seção 3. | G |
| Q02 | Alta | `estilo.py:5-10`; cores/fontes fixas em `interface.py:30-32, 452-476, 549-674, 697-801`, `tela_login.py:49-58, 70-80`, `tela_pessoas.py:42-117`, `tela_bloqueios.py:35-104`, `tela_usuarios.py:39-103`, `tela_edicao.py:29-112` | 70× `"Segoe UI"` e 40 cores hex fora de `estilo.py`. O tema do `ttk.Style` está dentro de `interface.py:450-456`. Quem refizer o visual precisa caçar cor por cor. | Completar `estilo.py` com **tokens nomeados** (ex.: `VERDE`, `AZUL`, `LARANJA`, `CINZA`, `TEXTO`, `TEXTO_SUAVE`, `BRANCO`; `FONTE_TITULO`, `FONTE_CAMPO`, `FONTE_ROTULO`, `FONTE_DICA`) e uma função `aplicar_tema(janela)` com a configuração do `ttk.Style`. Trocar os literais pelos nomes, sem mudar a aparência. | M |
| Q03 | Alta | `interface.py:572` + `676-679`; `tela_pessoas.py:100-103`; `tela_edicao.py:76-79` | "Placa sempre maiúscula" escrito 3 vezes; nas duas últimas é uma `lambda` com `if/else` em 3 linhas, difícil de ler e de explicar. | `componentes.campo_placa(pai)` que cria o `StringVar`, o `trace` e a validação de digitação (letras/números, até 7) e devolve `(entry, var)`. | P |
| Q04 | Média | `interface.py:523-527` e `573-574`; `tela_pessoas.py:93-96`; `tela_edicao.py:73-80` | "Só números" duplicado; e **inconsistente**: na janela Corrigir, CPF/celular/placa aceitam qualquer tecla; na aba Pessoas a placa aceita hífen e depois dá "Placa inválida". | `componentes.campo_numeros(pai, limite)` e `campo_placa` (Q03) usados nas três telas. Opcional: `validacao.normalizar_placa()` que tira hífen/espaço, usada por `normalizar()` e `normalizar_bloqueio()`. | P |
| Q05 | Alta | `interface.py:534-542`; `tela_pessoas.py:83-86, 107-109`; `tela_edicao.py:62-71, 82-84`; `tela_usuarios.py:42-48, 54-55`; `tela_login.py:75-82`; `tela_bloqueios.py:57-60` | Seis funções internas diferentes para "rótulo + campo", cada uma com fonte/cor/espaço próprios (fundo cinza no Cadastro, branco nas outras). É exatamente o que a reforma visual vai querer padronizar. | Em `componentes.py`: `rotulo(pai, texto)`, `campo(pai, rotulo, **opções)`, `combo(pai, rotulo, valores)`, `dica(pai, texto)`. As telas passam a dizer **o quê** montar; o **como** fica num lugar só. Manter `grid`/`pack` como decisão da tela. | M |
| Q06 | Média | `interface.py:652-670`; `tela_pessoas.py:50-61`; `tela_bloqueios.py:86-96`; `tela_usuarios.py:70-80` (sem rolagem), `95-108`; `tela_edicao.py:97-105` (sem rolagem) | Cinco montagens de `Treeview` + `Scrollbar`. As colunas ficam ora numa constante `COLUNAS` no topo (Pessoas, Bloqueios), ora em listas soltas no meio do código. | `componentes.tabela(pai, colunas, altura=None)` que devolve a `Treeview` já com rolagem. Colunas sempre numa constante no topo do módulo. | P |
| Q07 | Média | `tela_usuarios.py:95-103, 126-128`; `tela_edicao.py:97-105, 116-118`; `dados.py:477-478, 487` | A tabela de histórico (momento, usuário, ação, detalhe) é montada e preenchida igual em 2 telas; o formato `"%Y-%m-%d %H:%M:%S"` aparece 2× como texto solto. | `componentes.tabela_eventos(pai, altura)` + `preencher_eventos(tabela, eventos)`; constante `FORMATO_ISO_SEGUNDOS` em `dados.py`. | P |
| Q08 | Média | `interface.py:473-477` (Sair), `623-627` (Registrar), `631-635` (Desfazer); `tela_login.py:53-58` | Quatro botões copiam o estilo à mão em vez de usar `estilo.botao()`. Na reforma ficariam com a cara antiga. | `botao()` com variantes simples (`pequeno=True`, `link=True`, `preencher=True`) ou `botao_link()`. | P |
| Q09 | Baixa | `tela_bloqueios.py:46-51`; `tela_pessoas.py:70-74` | Cópias de `estilo.cartao()` com outro espaçamento (e uma sem a faixa vermelha). | `cartao(pai, faixa=True, folga=(16, 12))` e usar nos dois lugares. | P |
| Q10 | Alta | `tela_edicao.py:156-159` (`app.registros = ...`, `app.busca.get()`, `app._avisar`); `tela_pessoas.py:93` (`app.janela.register`); `app.usuario["login"]` 9× nas telas | As telas conhecem o interior do `AppPortaria`; `_avisar` é privado e é chamado de fora. Renomear um widget do Cadastro (`busca`) quebra a janela Corrigir. | Definir um **contrato pequeno e público** do app, documentado no docstring de `interface.py`: `banco`, `usuario`, `autor` (property com o login), `tentar()`, `registros`, `recarregar_registros()`, `atualizar_telas()`, `avisar()`, `preencher_pessoa()`. As telas usam só isso. Nada de framework. | M |
| Q11 | Média | `interface.py:101-108`, `414`; `tela_edicao.py:156-157` | Três jeitos de recarregar a lista. O padrão `tentar(listar)[1] or self.registros` trata uma lista vazia legítima como falha e mantém dados velhos. | Um único `recarregar_registros()` (já é o miolo de `_gravar`) usado nos três lugares. | P |
| Q12 | Média | `interface.py:164-166` (detalhe do bloqueio), `260-268` (dica da pessoa), `377-383` ("Beto e Ana"), `427-434` (linha da tabela), `815-844` (textos dos cards e dados dos gráficos); `tela_pessoas.py:132-136` (situação) | Regras de **texto exibido** misturadas com a montagem dos widgets: não dá para testar sem Tk e a reforma pode alterá-las sem perceber. | Mover para `consultas.py` como funções puras (`linha_registro(r)`, `juntar_nomes(nomes)`, `situacao_pessoa(p, bloqueados)`, `textos_dashboard(resumo, hoje)`) com testes em `test_consultas.py`. A tela só coloca o texto no lugar. | M |
| Q13 | Média | `tela_login.py:62-65` | Liga o Enter varrendo `miolo.winfo_children()` atrás de `ttk.Entry`. Se a reforma envolver cada campo num `Frame` (muito comum), o Enter para de funcionar **sem erro nenhum**. | `_campo()` guarda os campos numa lista; ligar o Enter nessa lista. | P |
| Q14 | Média | `messagebox` usado direto em `interface.py`, `tela_pessoas.py`, `tela_bloqueios.py`, `tela_usuarios.py`, `tela_edicao.py`; `tests/test_interface.py:49-57` | Os testes precisam fazer `patch` em 5 módulos. Ao mover código para um módulo novo (Q01), se esquecerem o patch, aparece uma caixa modal de verdade e o teste trava. E se o design trocar caixas por avisos na tela, são 6 arquivos para mexer. | Módulo `mensagens.py` com `erro()`, `aviso()`, `info()`, `confirmar()` (repassam para `messagebox`). Todas as telas usam ele; o teste faz **um** patch. | P |
| Q15 | Média | `dados.py:96-97` (`de_iso` → `ValueError`), `523` (`os.replace` → `OSError`), `547` (`OSError` dentro do `except`) | Erros que não viram `ErroDados`. `AppPortaria._carregar` (`interface.py:82-89`) só captura `ErroDados`: se o JSON antigo estiver aberto em outro programa / somente leitura, ou houver data corrompida no banco, o programa **fecha na abertura** com traceback. | Capturar `OSError`/`ValueError` nesses pontos e relançar como `ErroDados` com mensagem clara. | P |
| Q16 | Baixa | `interface.py:236-239`, `241-251` | `_bloqueio_ativo` abre o banco a cada tecla da placa/CPF; se o banco falhar, `tentar()` abre **uma caixa de erro por tecla**. A variável `ok` (237) não é usada. | Ler a lista de bloqueios ativos uma vez (ao montar/ao voltar para a aba) ou consultar sem diálogo. | P |
| Q17 | Baixa | `interface.py:438`, `646-647`, `810-845` | Cada tecla na busca chama `atualizar_tabela`, que recalcula o `resumo` e redesenha os dois gráficos do Dashboard. Mistura "filtrar a tabela" com "os dados mudaram". | Separar `atualizar_tabela(filtro)` de `atualizar_telas()`; o Dashboard só atualiza quando os dados mudam ou quando a aba é aberta. | P |
| Q18 | Baixa | `interface.py:144-146, 285-294, 307-310, 321-324`; `tela_pessoas.py:151, 161-165`; `tela_bloqueios.py:172-176`; `tela_usuarios.py:133-138` | "Selecione um … na lista" + `next(...)` sem valor padrão repetidos 7×; `next` lança `StopIteration` se tabela e lista se desencontrarem. | `componentes.item_selecionado(tabela, itens, mensagem)` → item ou `None` (já avisando). | P |
| Q19 | Baixa | `interface.py:196-206` | Campos do Cadastro misturam `Entry` (nome, celular) e `StringVar` (CPF, placa); por isso `_escrever` precisa de `hasattr(campo, "set")`. | Usar `StringVar` em todos os campos do formulário (`self.var_nome`…). Leitura e escrita ficam iguais, e os testes deixam de depender do tipo de widget. | M |
| Q20 | Média | `portaria_universidade.py:13-20`, `48-52`, `57-58`, `69-71`; `interface.py:2-4` | A lista de módulos está desatualizada (faltam `tela_pessoas`, `tela_bloqueios`, `tela_edicao`, `estilo`). O comentário **Relação com Compiladores** cita `interface.py`, a linha `self.cpf = ttk.Entry(form, font=("Segoe UI", 10), validate="key", ...)` e `interface.excluir_selecionado()` — Q01/Q02/Q05 mudam isso. | Atualizar no **mesmo commit** de cada extração. Escolher, para o exemplo de tokens, uma linha que não vá mudar com a reforma (ou atualizar o texto junto). | P |
| Q21 | Baixa | `interface.py:30-36` | `PLURAL_TIPO` é dado de domínio e `CORES_TIPO` repete cores da paleta, ambos dentro do arquivo da janela. | `PLURAL_TIPO` para `validacao.py` (ao lado de `TIPOS_ACESSO`); `CORES_TIPO` para `estilo.py`. | P |
| Q22 | Baixa | `dados.py:482-488` | `_evento` ignora em silêncio quando `autor` é `None`, e quase todos os métodos têm `autor=None` por padrão. Um esquecimento apaga a auditoria sem aviso. | Comentar a regra no docstring ou tornar `autor` obrigatório nos métodos chamados pelas telas. | P |
| Q23 | Baixa | `tela_login.py:25-28` | Se `tem_usuarios()` falhar, `self.primeiro_acesso` nunca é criado. | Definir `self.primeiro_acesso = False` antes do `try`. | P |
| Q24 | Baixa | `interface.py:93-99` | `tentar()` só captura `ErroDados`; qualquer outro erro num botão vai só para o console — no `.exe` sem console o usuário não vê nada. | `janela.report_callback_exception = ...` mostrando "Erro inesperado" com `mensagens.erro`. | P |
| Q25 | Baixa | `interface.py:514-521` | `_ao_trocar_aba` é uma corrente de `if/elif` comparando `str(frame)`; cada aba nova exige mexer aqui. | Dicionário `{str(frame): tela}` e chamar `tela.atualizar()`; convenção: toda aba tem `__init__(aba, app)` e `atualizar()`. | P |

### 2.2 Testes

| ID | Prior. | Arquivo:linha | Problema | Sugestão | Esf. |
|----|--------|---------------|----------|----------|------|
| T01 | Alta | `tests/test_interface.py:61-64`; `usuarios.py:28` | Cada um dos 82 testes de tela gera **2 hashes PBKDF2 de 200 mil iterações** (admin e porteiro). Medido: a suíte de tela cai de **31,2 s para 20,4 s** só baixando as iterações; `test_usuarios` cai de 1,0 s para 0,15 s. Como `iteracoes=ITERACOES` é fixado na definição da função, não dá para trocar com um `patch` simples. | (a) Calcular os dois hashes **uma vez** no módulo de teste (constantes ou `setUpModule`) e passar para `banco.criar_usuario`; (b) em `usuarios.py`, `iteracoes=None` → `iteracoes or ITERACOES`, para os testes poderem baixar `ITERACOES` com `mock.patch`. Manter 1–2 testes com o valor real. | P |
| T02 | Média | `tests/test_interface.py:35-40, 70-72` | Cada teste cria e destrói um `tk.Tk()` (~0,25 s × 82 ≈ 20 s, o maior custo restante). | Um `tk.Tk()` por classe (`setUpClass`) e o app dentro de um `Toplevel` novo por teste. Só vale se continuar simples de entender; com T01 a suíte já fica em ~22 s. | M |
| T03 | Alta | `tests/test_interface.py:417` (`_ao_selecionar`), `623` (`_mostrar_detalhe`), `726` (`_ao_trocar_aba`); ~60 nomes de widgets acessados direto (ver anexo) | Os testes chamam métodos privados e dependem do nome de cada widget (`app.nome`, `app.var_placa`, `lbl_pessoa`, `lbl_dica_placa`, `btn_desfazer`, `campo_saida_rapida`…). É um contrato implícito: a reforma renomeia e quebra 30 testes de uma vez. | Tornar públicos os métodos que os testes usam (`ao_selecionar`, `mostrar_detalhe`, `ao_trocar_aba`) e combinar com quem fizer o design a **lista de nomes que não podem mudar** (anexo A). Alternativa: helpers nos testes (`preencher_cadastro`, `ler_dica`) concentrando o acesso. | M |
| T04 | Média | `tests/test_interface.py:140-143` (`isinstance(w, tk.Label)`), `159-161` (`isinstance(w, tk.Button)`) | Se a reforma trocar por `ttk.Label`/`ttk.Button` ou botão desenhado, o teste "porteiro não vê Excluir" **passa vazio** (`any()` de lista vazia é `False`) e o do formato de data falha pelo motivo errado. | Helper `textos(widget)` que lê `text` de qualquer widget que tenha essa opção, e conferir que achou pelo menos um texto antes do `assertFalse`. | P |
| T05 | Baixa | `tests/test_interface.py:507-508` | `winfo_manager() == "pack"` amarra o teste ao gerenciador de layout do botão Desfazer. | Expor `app.desfazer_visivel()` ou usar `winfo_ismapped()` após `update_idletasks()`. | P |
| T06 | Baixa | `tests/test_interface.py:664-671` | Dois testes sobrescritos com `pass` contam como "passou" sem testar nada; e testes com nome "porteiro…" rodam como admin. | Classe base com os testes comuns; testes só-do-porteiro numa classe própria (ou `@unittest.skip("só porteiro")`). | P |
| T07 | Média | lacunas | Sem teste de tela para: **Dashboard** (cards, gráficos sem dados); **Enter só cadastra na aba Cadastro** (`interface.py:152`); **erro de banco** (`tentar` → caixa de erro; login com "Banco de dados indisponível"); aviso que some sozinho (`_esconder_aviso`); **desfazer parcial** (`interface.py:416-419`); F2 (só testa que o bind existe). São justamente os pontos que a reforma pode quebrar. | Um teste curto para cada (com Q12 feito, os textos do Dashboard viram teste puro em `test_consultas.py`). | M |
| T08 | Baixa | `tests/test_interface.py:16-23` | Os testes de tela usam o relógio real (`ha_uma_hora()`) e uma visita fixa em 15/10/2026. Hoje é robusto (regra de 24 h, sem horário de verão), mas um teste de "entradas hoje" no Dashboard seria frágil perto da meia-noite. | Relógio injetável no `AppPortaria` (como já existe em `ControleTentativas(relogio=...)`) quando os testes do Dashboard forem escritos. | P |

---

## 3. Reorganização proposta dos módulos de tela

Mantém a pasta plana e o prefixo `tela_` que o aluno já conhece (sem
subpacote, para não confundir `telas/usuarios.py` com `usuarios.py`).

**Antes**

```
portaria/
├── validacao.py      regras e verificações semânticas (sem Tk)
├── dados.py          SQLite + migrações + auditoria
├── consultas.py      busca, saída rápida, números do dashboard (sem Tk)
├── usuarios.py       senha, perfis, permissões (sem Tk)
├── estilo.py         3 cores, 2 fontes, botao(), cartao()
├── interface.py      845 linhas: janela + tema + sessão + aba Cadastro
│                     (montagem e ações) + aba Dashboard + gráficos
├── tela_login.py
├── tela_pessoas.py
├── tela_bloqueios.py
├── tela_usuarios.py
└── tela_edicao.py
```

**Depois**

```
portaria/
├── validacao.py      + PLURAL_TIPO, normalizar_placa()            (Q04, Q21)
├── dados.py          + erros de arquivo/data viram ErroDados       (Q15)
├── consultas.py      + textos de exibição puros e testáveis:       (Q12)
│                       linha_registro, juntar_nomes,
│                       situacao_pessoa, textos_dashboard
├── usuarios.py       gerar_hash(iteracoes=None)                    (T01)
│
├── estilo.py         SÓ valores: paleta, fontes, espaçamentos,     (Q02, Q21)
│                     CORES_TIPO e aplicar_tema(janela)
├── componentes.py    peças de tela reutilizáveis:                  (Q03–Q09, Q18)
│                     botao, botao_link, cartao, rotulo, dica,
│                     campo, campo_numeros, campo_placa, campo_data,
│                     combo, barra_busca, tabela, tabela_eventos,
│                     preencher_eventos, item_selecionado
├── mensagens.py      erro, aviso, info, confirmar (única porta     (Q14)
│                     para messagebox — 1 patch nos testes)
│
├── interface.py      ~200 linhas: AppPortaria = janela, cabeçalho, (Q01, Q10, Q11)
│                     sessão (entrar/sair), abas, e o contrato
│                     público: tentar, autor, registros,
│                     recarregar_registros, atualizar_telas, avisar,
│                     preencher_pessoa
├── tela_cadastro.py  AbaCadastro: formulário, preenchimento pelo   (Q01)
│                     CPF, alertas de bloqueio, saída rápida,
│                     desfazer, tabela e busca  (~350 linhas)
├── tela_dashboard.py AbaDashboard: cards + atualizar()             (Q01)
├── graficos.py       desenhar_barras_horizontais/verticais         (Q01)
│                     (funções soltas, só Canvas)
├── tela_login.py     usa componentes; Enter pela lista de campos   (Q13)
├── tela_pessoas.py   usa componentes
├── tela_bloqueios.py usa componentes
├── tela_usuarios.py  usa componentes
└── tela_edicao.py    usa componentes + contrato do app             (Q10)
```

Convenção única para as abas (sem classe base, só combinado):
`class AbaX: __init__(self, aba, app)` monta; `atualizar()` relê os dados.

Fica de fora de propósito (seria exagero para o projeto): MVC/MVVM, injeção de
dependência, classes abstratas, sistema de eventos, pacote `telas/`.

---

## 4. O que fazer ANTES da reforma visual

Cada passo num commit separado, **sem mudar a aparência**, rodando os 199 testes
ao final de cada um.

1. **Testes mais rápidos e menos frágeis** — T01 (hash uma vez), T04 (helper
   de textos), T06; publicar métodos usados nos testes (T03).
2. **`mensagens.py`** e trocar todos os `messagebox` por ele (Q14) — o teste
   passa a fazer 1 patch, e mover código entre módulos deixa de ser arriscado.
3. **Tokens em `estilo.py`** + `aplicar_tema()` (Q02, Q21): trocar cores e
   fontes soltas por nomes. A partir daqui o design mexe num arquivo só.
4. **`componentes.py`** (Q03–Q09, Q18) e usar nas telas pequenas primeiro
   (Pessoas, Bloqueios, Usuários, Edição, Login), depois no Cadastro.
5. **Quebrar `interface.py`** em `tela_cadastro.py`, `tela_dashboard.py` e
   `graficos.py` (Q01) + contrato público do app (Q10, Q11). Atualizar o
   comentário "Relação com Compiladores" e a lista de módulos no mesmo commit (Q20).
6. **Tirar texto de exibição das telas** para `consultas.py` com testes (Q12)
   e cobrir as lacunas do Dashboard, Enter e erro de banco (T07).
7. Combinar com o design a **lista de nomes preservados** (anexo A); o que
   precisar mudar de nome muda junto com o teste.

Correções rápidas que podem entrar a qualquer momento: Q15, Q13, Q23, Q16.

---

## Anexo A — nomes que os testes usam hoje (contrato implícito)

Se a reforma renomear algum destes, o teste correspondente precisa mudar junto.

- **AppPortaria**: `nome`, `cpf`, `celular`, `var_placa`, `tipo`, `cadastrar`,
  `limpar`, `tabela`, `registrar_saida`, `registrar_saida_da_linha`,
  `excluir_selecionado`, `editar_selecionado`, `janela_edicao`, `btn_excluir`,
  `aba_cad`, `aba_usuarios`, `aba_bloqueios`, `abas`, `_ao_trocar_aba`,
  `lbl_usuario`, `sessao`, `sair`, `usuario`, `tentativas`, `tela_login`,
  `tela_pessoas`, `tela_usuarios`, `tela_bloqueios`, `lbl_pessoa`,
  `lbl_dica_placa`, `campo_saida_rapida`, `saida_rapida`, `lbl_aviso`,
  `btn_desfazer`, `desfazer_saida`, `registros`, `atualizar_tabela`.
- **TelaLogin**: `campo_login`, `campo_senha`, `campo_nome`,
  `campo_confirmacao`, `entrar`, `criar_administrador`, `lbl_erro`,
  `primeiro_acesso`.
- **AbaUsuarios**: `nome`, `login`, `senha`, `confirmacao`, `criar`, `tabela`,
  `alternar_ativo`, `redefinir_senha`, `historico`, `atualizar`.
- **AbaPessoas**: `atualizar`, `tabela`, `busca`, `lbl_total`, `_ao_selecionar`,
  `nome`, `celular`, `var_placa`, `lbl_titulo`, `salvar`, `registrar_entrada`.
- **AbaBloqueios**: `form`, `tipo`, `valor`, `motivo`, `bloquear`, `remover`,
  `tabela`, `ver_removidos`, `atualizar`.
- **JanelaEdicao**: `janela`, `cpf`, `nome`, `entrada`, `saida`, `salvar`,
  `historico`, `_mostrar_detalhe`, `lbl_detalhe`.
- **Textos conferidos nos testes** (mudar a redação quebra o teste):
  "Registro cadastrado com sucesso!", "— dentro —", "Digite o CPF primeiro",
  "Já cadastrado: 1 visita(s)", "Pessoa nova", "CPF inválido",
  "está no campus desde", "Saída de … registrada", "Saída desfeita",
  "CPF BLOQUEADO — …", "PLACA BLOQUEADA — …", "ABC1234 ou ABC1D23",
  "No campus", "BLOQUEADO", "dd/mm/aaaa hh:mm", "Administrador",
  "incorretos", "Aguarde".

## Anexo B — medições (feitas fora do projeto)

| Medição | Valor |
|---|---|
| Suíte completa | 199 testes, 35,8 s |
| `test_interface` (82 testes) normal / com PBKDF2 barato | 31,2 s / 20,4 s |
| `test_usuarios` normal / com PBKDF2 barato | 1,01 s / 0,15 s |
| `test_dados` (51) / `test_validacao` (32) / `test_consultas` (15) | 1,3 s / ~0 s / ~0 s |
| Um `gerar_hash` (200 mil iterações) | ~0,06 s |
| `tk.Tk()` + `destroy()` | ~0,23 s |
| Primeira fonte com emoji (🏛) no processo | ~0,25 s (só a primeira vez) |
| Funções com mais de 30 linhas | `_montar_cadastro` 146, `tela_login.__init__` 52, `_montar_formulario` (Pessoas) 49, `validar` 46, `editar` 45, `_montar_dashboard` 39, `resumo` 38, `JanelaEdicao.__init__` 38, `_montar_campos` 37, `atualizar_dashboard` 36, `_montar_janela` 35, `_montar_principal` 34, `validar_campos` 33, `bloquear` 33, `_montar_lista` (Bloqueios) 31 |
