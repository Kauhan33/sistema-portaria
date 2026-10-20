# Revisão final de código (Onda 3) — Sistema de Portaria

Escopo: a reforma inteira, `git diff 5362601..reforma` (HEAD `2d864ce`), com
foco nas **costuras** entre as partes feitas separadamente (1A telas, 1B dados
e segurança, 2 visual "Guarita").
Critérios: skills *code-reviewer* (checklist) e *clean-code* (SRP, DRY, KISS,
nada de código morto).

Como foi feito:
- `python -m unittest`: **329 testes, todos passando** (~27 s).
- O app **rodou de verdade** (Tk real, `ligar_nitidez()` ligado, escala 1,25
  do monitor) numa pasta temporária fora do repositório, com dados de
  exemplo, e os fluxos foram exercitados por roteiros que chamam os métodos
  da tela como os testes fazem. Caixas nativas ("Sim/Não") foram respondidas
  de verdade por outra thread (`PostMessage` IDYES).
- Um banco **v5 criado pelo código do main** (`git archive 5362601`, numa
  pasta temporária com acento e espaço no caminho) foi aberto com o código novo.
- Nenhum arquivo do repositório foi alterado além deste relatório.

---

## 1. Resumo

| # | Gravidade | Bug confirmado | Onde |
|---|-----------|----------------|------|
| B1 | **Alta** | Sessão expira com uma caixa "Sim/Não" ou "Salvar como" aberta → a ação roda **sem autor**: exclui registro, desativa usuário e exporta CSV **sem checar permissão e sem histórico** | `interface.py:192-208`, `dados.py:461-467`, `dados.py:983-990` |
| B2 | **Alta** | Em 1366×768 a 125% a tabela **Movimento some** (0 linhas visíveis); `minsize` (1250×800 px) é maior que a tela; a janela "Corrigir" tem 754 px de altura e os botões ficam fora da tela | `interface.py:88-95, 334-335`; layout de `tela_cadastro.py`; `tela_edicao.py` |
| B3 | Média | Saída numa linha desatualizada (outra estação já deu saída ou excluiu) mostra "Saída registrada" falsa, e o **Desfazer desfaz a saída feita pela outra estação** | `tela_cadastro.py:592-619`, `dados.py:642-650` |
| B4 | Média | Banco v5 + pasta `backups` impossível de criar → o programa **não abre** (OSError escapa; só `ErroDados` é tratado) | `dados.py:415-422`, `interface.py:152-160` |
| B5 | Média/Baixa | Usuário **desativado** (ou login inexistente) continua cadastrando entrada, dando saída e alterando pessoa: só algumas operações conferem o autor no banco | `dados.py:592-598, 642-669, 856-863` |
| B6 | Baixa | Exportação grava "Exportação de registros" no histórico **antes** de gravar o arquivo; se a gravação falha, o histórico mente | `dados.py:749-764`, `backup.py:118-136` |
| B7 | Baixa | Admin redefine a senha de quem está bloqueado por tentativas → o usuário continua bloqueado (até 15 min) | `dados.py:909-921` |
| B8 | Baixa | A migração v6 não limpa o histórico antigo: CPFs completos e o texto digitado no login (pode ser senha) continuam na Atividade | `dados.py:306-359` |
| B9 | Baixa | "N registros **hoje**" conta visitas abertas de dias anteriores | `tela_cadastro.py:297-299` |
| B10 | Baixa | Comentário "RELAÇÃO COM COMPILADORES" aponta `FAMILIA = "Segoe UI"` em `estilo.py`, que **não existe** | `portaria_universidade.py:81-84` |

Suspeitas (não reproduzidas ou herdadas do main): hora de entrada "velha" no
formulário (S1, Média), primeiro acesso em duas estações (S2), CPF mascarado
contornável pelo porteiro (S3), Enter na tabela tenta cadastrar (S4), `.exe`
antigo rebaixa a versão do banco (S5).

**Recomendação antes do main:** corrigir **B1** (é furo de permissão e de
auditoria, e é o tipo de pergunta que a banca faz: "e se a sessão cair no
meio?"), **B2** (o alvo declarado é notebook 1366×768 a 125%), **B3** e
**B4**; B10 é uma linha e o aluno vai apresentar esse comentário. O resto pode
ficar como melhoria registrada.

O que **funcionou bem** nos testes de verdade: migração v5→v6 (nada some,
backup antes de migrar, duplicadas abertas fechadas com evento e aviso ao
admin, hash 200 mil → 600 mil no primeiro login, `quick_check` e
`foreign_key_check` limpos, reabrir não migra de novo); caminhos com acento e
espaço (banco, backup e CSV); banco somente leitura dá mensagem amigável;
entrada dupla aberta de duas estações é barrada pelo índice com a mensagem
certa; saída rápida pela placa de uma visita de 3 dias atrás; desfazer a
saída de visita antiga; temporizador do aviso de 10 s depois do logout não
gera erro visível; Painel, Pessoas, Bloqueios e Usuários cabem em 1366×670.

---

## 2. Bugs confirmados

### B1 (Alta) — sessão expira com caixa modal aberta: ação sem autor, sem permissão e sem histórico

**Reproduzir** (roteiros `t2_expira_no_dialogo.py` e `t7_expira_no_salvar_como.py`):
1. Entrar como administrador, selecionar um registro e clicar **Excluir**.
2. Deixar a caixa "Excluir registro?" aberta por mais de 10 min
   (`MINUTOS_INATIVIDADE`). O temporizador do app (`after`) **continua
   rodando durante a caixa nativa** e chama `sair()`: a janela volta ao login.
   O tempo dentro da caixa não conta como uso (a caixa nativa não passa pelos
   `bind` da janela).
3. Clicar **Sim**.

Resultado medido: o registro **é apagado** (7 → 6 registros), **nenhum evento**
"Exclusão de registro" no histórico, e depois aparece "Erro inesperado"
(`TclError: invalid command name ...entry`, a tela já foi destruída).
O mesmo com **Desativar usuário** (paulo ficou desativado, sem evento) e com
**Exportar CSV** (arquivo com CPF e celular completos gravado, sem evento
"Exportação de registros"). Com **Bloquear** o banco recusa
(`criado_por` NOT NULL) e o usuário vê só "O banco recusou os dados".

**Causa:** depois do logout `app.autor` é `None`; `gravar()`/`tentar(...,
autor=self.app.autor)` repassam `None`; no banco `autor=None` significa
"chamada interna": `_exigir` pula a checagem (`dados.py:466-467`) e `_evento`
não grava nada (`dados.py:986`). A limitação documentada no topo de
`dados.py` vaza para a tela.

**Correção sugerida (curta):**
- `AppPortaria.gravar` e as chamadas `tentar(..., autor=...)`: se
  `self.usuario is None`, não executar (devolver `False`). Um lugar só resolve
  quase tudo; as telas que chamam `tentar` com autor (`tela_usuarios`,
  `tela_bloqueios`, `tela_dashboard`, `tela_pessoas`, `desfazer_saida`)
  passariam por um `app.gravar_como_usuario(...)` ou testariam `app.usuario`
  logo depois da caixa.
- Opcional, mais robusto: no banco, separar "interno" de "sem autor" (ex.:
  `autor=AUTOR_SISTEMA` explícito para chamadas internas e `None` recusado).
- Teste: abrir a caixa (mock que avança o relógio e chama
  `conferir_inatividade()` antes de devolver `True`) e conferir que nada foi
  gravado.

### B2 (Alta) — não cabe em 1366×768 a 125%

**Reproduzir** (`t3_dpi.py`; monitor real a 125%, escala 1,25 lida pelo
`ligar_nitidez`): criar a janela, tirar o `minsize` e pôr a área útil de uma
janela maximizada num notebook 1366×768 a 125% (≈ 1366×670 px reais:
768 − barra de tarefas − barra de título).

Medidas:
- `geometry` pedida 1475×950 e **`minsize` 1250×800** — a altura mínima já é
  maior que os 768 px da tela; `ajustar_ao_monitor` maximiza, mas o mínimo
  continua valendo.
- Página **Entrada e saída** pede 1179 px de altura. Em 1366×670 o
  formulário ocupa tudo e o cartão Movimento mostra só a barra (busca,
  Registrar saída, Corrigir, Excluir): **nenhuma linha da tabela aparece**
  (print `prints/t3_admin_cadastro_1366x670.png` na pasta temporária).
  Sem a tabela, o duplo clique para dar saída e o Corrigir ficam inúteis.
- Janela **Corrigir registro**: 879×754 px (mais a barra de título): não
  cabe; o rodapé com "Salvar correção"/"Cancelar" fica abaixo da tela (o
  Enter ainda salva).
- Painel, Pessoas, Bloqueios e Usuários cabem (prints conferidos).

**Correção sugerida:** `minsize` limitado à tela
(`min(px(640), winfo_screenheight() - px(100))`); na Entrada e saída, deixar
a tabela com altura mínima garantida e o formulário mais baixo em telas
pequenas (ex.: ficha "Veículo/Histórico" recolhida ou ao lado em uma linha,
`pad` menor no cartão) — ou um `ttk.PanedWindow` vertical entre formulário e
Movimento; no Corrigir, `tabela_eventos(..., altura=2)` ou o histórico
recolhível. Vale um teste que monta o app com `estilo.ESCALA = 1.25`,
`geometry("1366x670")` e confere `tabela.winfo_height() > 0` depois de
`update()`.

### B3 (Média) — saída em linha desatualizada: sucesso falso e Desfazer da outra estação

**Reproduzir** (`t6_duas_estacoes.py`): estação A mostra "Ana Silva — No
campus". A estação B dá a saída. Em A (sem recarregar), duplo clique na linha.
- A mostra "Saída de Ana registrada às 05:16." com **Desfazer** — mas o
  `UPDATE ... WHERE saida = ''` não mudou nada (quem deu a saída foi B).
- Clicando **Desfazer** em A, a visita **volta para "no campus"**: A desfez a
  saída feita por B (histórico: `ana.admin Saída registrada`, depois
  `paulo Saída desfeita`).
- Se B **excluiu** o registro, A mostra "Saída de Duda registrada" de um
  registro que não existe mais.

**Causa:** `_dar_saida` confia no registro guardado em `self.mostrados` e
`registrar_saidas` não diz quantas linhas mudou.

**Correção sugerida:** `registrar_saidas` devolver a lista de ids realmente
atualizados (`cursor.rowcount`); `_dar_saida` montar a mensagem e o Desfazer
só com esses ids e avisar "já tinha saída / não existe mais" para o resto
(e recarregar a tabela).

### B4 (Média) — banco v5 com backup impossível derruba a abertura

**Reproduzir** (`t5_abrir_v5_sem_backup.py`): copiar um banco v5 para uma
pasta onde `backups` não pode ser criada (no roteiro: um arquivo chamado
`backups`; na vida real: pasta sem permissão de criar subpasta) e abrir
`AppPortaria`.

Resultado: `FileExistsError` sai de `Banco.__init__` →
`_backup_antes_de_migrar` (`os.makedirs`, `dados.py:419`) e não é
`ErroDados`; `_carregar` (`interface.py:157`) só captura `ErroDados` →
exceção no construtor: com `pythonw`/.exe o programa simplesmente não abre.
(No `backup_diario` o mesmo erro é tratado certo: `interface.py:166` captura
`OSError`.) `copiar_banco` também deixa escapar `OSError` do `os.replace`.

**Correção sugerida:** em `_backup_antes_de_migrar`, converter `OSError` em
`ErroDados("Não foi possível fazer a cópia de segurança antes de atualizar o
banco (pasta backups). Nada foi alterado.")`; em `copiar_banco`, tratar
`OSError` junto com `sqlite3.Error`.

### B5 (Média/Baixa) — usuário desativado continua operando

**Reproduzir** (`t4_dados.py`, caso 1): administrador desativa `paulo`;
chamadas com `autor="paulo"` continuam aceitas em `inserir`,
`registrar_saidas` e `atualizar_pessoa` (e com `autor="fantasma"`, login que
nem existe, `inserir` grava o evento em nome de "fantasma").
Na prática: o porteiro desativado que está com a sessão aberta noutra estação
continua registrando entradas até sair.

**Correção sugerida:** `self._exigir(con, autor, so_admin=False)` em
`inserir`, `registrar_saidas`, `desfazer_saidas` e `atualizar_pessoa` (uma
consulta por chave primária, custo desprezível).

### B6 (Baixa) — histórico de exportação antes do arquivo

**Reproduzir** (`t4_dados.py`, caso 3): `exportar_csv` para uma pasta que não
existe → o usuário vê "Não foi possível gravar o arquivo", mas a Atividade
ganhou "Exportação de registros — 5 registro(s) de 20/10/2026 a 20/10/2026".
**Correção:** registrar o evento depois do `os.replace` (ex.:
`registros_do_periodo` só lê e confere permissão; `exportar_csv` chama
`banco.registrar_evento` no fim), ou o texto do evento dizer "solicitada".

### B7 (Baixa) — redefinir senha não desbloqueia

**Reproduzir** (`t4_dados.py`, caso 8): 5 senhas erradas de `paulo`; admin
redefine a senha; login com a senha nova → "Muitas tentativas erradas.
Aguarde 30 s." **Correção:** em `definir_senha` feita por admin para outro
usuário, apagar a linha de `tentativas_login` daquele login (e dizer isso na
mensagem "Senha redefinida").

### B8 (Baixa) — histórico antigo não é limpo na migração

**Reproduzir** (`migrar_com_novo.py`, banco v5 criado pelo main): depois da
migração a Atividade ainda mostra `CPF 71428793860 — Comportamento
agressivo`, `#6 Fabio Neves, CPF 71428793860, ...` e um "Login recusado" com
usuário **`senhaPorta9`** (o texto digitado no campo Usuário, gravado pela
versão antiga — exatamente o caso S11). O código novo só mascara o que grava
daqui para frente. **Correção:** no `_passo_v6`, registrar
`mascarar_cpfs_no_texto` como função SQL e rodar
`UPDATE auditoria SET detalhe = mascarar(detalhe)` e
`UPDATE auditoria SET usuario = '(login inexistente)' WHERE acao = 'Login
recusado' AND usuario NOT IN (SELECT login FROM usuarios)`.

### B9 (Baixa) — "registros hoje" conta visitas de outros dias

`tela_cadastro.py:297-299` usa `len(registros)` do movimento, que inclui quem
entrou dias atrás e ainda está dentro. Com uma visita aberta desde 15/10 e
uma de hoje, a tela diz "2 registros hoje" (o próprio teste
`TestMovimento.test_tabela_tem_so_o_movimento_do_dia` afirma isso). O Painel,
no mesmo momento, diz "Entradas hoje: 1". **Correção:** contar só entradas de
hoje ou trocar o texto para "N no movimento".

### B10 (Baixa, mas vai ser apresentado) — comentário de Compiladores

`portaria_universidade.py:81-84`: "Outro, com literal string, em
portaria/estilo.py: `FAMILIA = "Segoe UI"`" — essa linha não existe mais
(hoje é o dicionário `FAMILIAS = {...}`, `estilo.py:121`). Sugestão: usar
`MARGEM = 24` (`estilo.py:190`, literal inteiro) ou
`FORMATO = "%d/%m/%Y %H:%M"` (`validacao.py:14`, literal string, já citado
na tabela de símbolos). O resto do comentário confere: `self.var_cpf = ...` e
`self.cpf = posicionar(Campo(...))` estão em
`AbaCadastro._montar_formulario` (`tela_cadastro.py:124-125`); `BANCO`,
`FORMATO`, `TIPOS_ACESSO`, `DDDS_VALIDOS`, `REGEX_PLACA`, `COR`, `FONTE`,
`self.registros`, `validar()`, `checar_bloqueio()` e
`excluir_selecionado()` com `self.app.gravar(self.app.banco.excluir, ...)` e
`pode_excluir` existem como descrito.

---

## 3. Suspeitas e observações (não reproduzidas como bug)

- **S1 (Média, herdado do main)** — a hora de entrada é preenchida em
  `limpar()` (`tela_cadastro.py:371`), isto é, logo **depois** do cadastro
  anterior. Se a próxima pessoa chega 2 h depois e o porteiro não clica no
  relógio, a entrada fica com a hora antiga, e passa na validação. Sugestão:
  guardar o valor automático e, no `cadastrar`, se o campo não foi editado,
  usar a hora atual.
- **S2 (Baixa)** — primeiro acesso: `criar_administrador` chama
  `criar_usuario` sem autor (sem checagem) e não reconfere `tem_usuarios()`.
  Duas estações abertas no "Primeiro acesso" criam dois administradores; e
  qualquer código que chame `criar_usuario(..., autor=None)` cria admin.
  Sugestão: em `criar_usuario` com `autor=None`, recusar se já houver usuário.
- **S3 (Baixa, desenho)** — o CPF mascarado para o porteiro é cosmético: em
  Pessoas → "Registrar entrada", o CPF completo vai para o formulário
  (`preencher_pessoa`), e a janela Corrigir mostra o CPF inteiro. Vale
  explicar na apresentação que o objetivo é evitar exposição casual.
- **S4 (Baixa, herdado)** — o Enter é ligado na janela toda; com o foco na
  tabela do Movimento, Enter chama `cadastrar` com o formulário vazio
  ("O nome da pessoa é obrigatório").
- **S5 (observação)** — se alguém abrir o banco v6 com o `.exe` antigo, ele
  grava `user_version = 5` sem perguntar; o código novo migra de novo
  (é idempotente), então não perde dados, mas faz outro backup e pode fechar
  visitas duplicadas criadas pelo antigo.
- **Temporizadores depois de sair:** o da inatividade é cancelado; o do aviso
  de 10 s (`tela_cadastro.py:654`) não é, mas ao disparar sobre a tela
  destruída não mostrou erro (roteiro `t1_timer_aviso.py`). Pode ser
  cancelado em `sair()` por limpeza.
- **Janelas abertas quando a sessão expira:** os `Dialogo` (Corrigir, Trocar
  senha, Novo usuário, Exportar) são fechados por `sair()`; o "Redefinir
  senha" (`simpledialog`, filho da página) some junto com a página e devolve
  `None` (seguro). As caixas nativas não fecham — ver B1.

---

## 4. Testes

**Lacunas nas costuras** (cada uma esconde um bug acima):
- Nenhum teste de "sessão expira com caixa aberta" (B1).
- Nenhum teste de tamanho de janela com `ESCALA = 1.25` (B2): todos os testes
  rodam com escala 1.
- Nenhum teste de saída/desfazer sobre linha desatualizada (B3).
- A migração v5→v6 é testada com `rebaixar_para_v5()` (`test_dados.py:516`),
  que apaga índices de um banco **criado pelo código novo**; não há um banco
  feito pelo código do main (chaves estrangeiras desligadas, hash de 200 mil,
  histórico sem máscara). Sugestão: guardar um `.db` pequeno da v5 em
  `tests/` (gerado uma vez com o código de `5362601`) e migrá-lo no teste.
  Nos testes manuais desta revisão a migração real funcionou.
- Falha do backup antes de migrar (B4) e operações de usuário desativado (B5)
  não têm teste.

**Testes que testam menos do que parecem:**
- `TestSessao.test_teclado_e_mouse_contam_como_uso`
  (`test_interface.py:600`) só confere que o `bind` existe; não gera um
  evento e não olha `ultimo_uso`.
- `TestAbertura.test_erro_inesperado_na_tela_vai_para_o_log`
  (`test_interface.py:641`) chama `janela.report_callback_exception`
  diretamente; nos testes a janela é um `Toplevel`, e o Tk usa o
  `report_callback_exception` da **raiz**, então a ligação real não é
  exercitada (em produção funciona porque a janela é a raiz).
- `self.app.registros = self.banco.listar()` em `test_interface.py:929`,
  `1024` e `1262`: a linha seguinte (`atualizar_tabela`) relê o movimento e
  sobrescreve; a atribuição não faz nada e sugere que a tela usa
  `banco.listar()`.
- `TestControleTentativas` (`test_usuarios.py:318`) testa uma classe que o
  programa não usa mais (ver seção 5).

**Dependência de relógio:** o relógio real aparece em `ha_uma_hora()`
(`test_interface.py:24`, sem a trava de meia-noite que `agora_menos` tem),
mas só em visitas abertas, que entram no movimento de qualquer jeito — ok.
As datas fixas (`VISITA_ANTIGA` e a "aberta" de 15/10/2026) supõem que hoje
é depois de 17/10/2026 (RN11 de 24 h, "fora do movimento do dia"): passam
agora; falhariam num PC com o relógio atrasado. Nenhum teste dorme
(`time.sleep`) nem depende do horário do dia.

---

## 5. Legibilidade (para o aluno explicar)

- **Código morto em produção:**
  - `usuarios.ControleTentativas` (`usuarios.py:286-308`, e o `import time`
    só existe por ela): o login usa `entrar()`; a classe só tem testes.
  - `consultas.filtrar` e `consultas.resumo`: só os testes usam (como
    "versão em Python" para conferir o SQL). Tudo bem manter, mas o
    docstring de `interface.py:10-12` diz "os números em consultas.py", o
    que não é mais verdade (vêm de `banco.resumo_painel`). O README já diz
    "usada nos testes" — alinhar o docstring.
  - `Banco.listar()` e `Banco.listar_pessoas()`: nenhuma tela usa; só
    testes e importação.
  - `AbaCadastro._registro` (`tela_cadastro.py:307-313`): o caminho
    "relê do banco se a linha saiu do movimento" nunca roda (`mostrados` é
    refeito junto com a tabela); o docstring descreve um caso que não
    acontece. Se B3 for corrigido relendo do banco, aí sim ele ganha uso.
- **Mágica difícil de apresentar:** `AppPortaria.__getattr__` +
  `NOMES_DO_CADASTRO` (`interface.py:64-74, 133-142`) faz `app.cpf` virar
  `app.tela_cadastro.cpf` e ainda monta páginas sob demanda. Existe só para
  os testes antigos e para `tela_pessoas`/`tela_dashboard` sob demanda. Para
  a banca, propriedades explícitas (`@property tela_pessoas`) ou os testes
  usando `app.tela_cadastro.cpf` seriam mais fáceis de explicar.
- **Duplicação nova:** `_numero()` igual em `tela_cadastro.py:194` e
  `tela_pessoas.py:145` (vale ir para `componentes.py`);
  `LIMITE_BUSCA = 200` nos dois; quatro variações locais do mesmo ajudante
  "rótulo + Campo + grid" (`rotulo`/`posicionar` em `tela_cadastro`, `grupo`
  em `tela_pessoas`, `novo` em `tela_edicao`, `campo` em `tela_usuarios`),
  quando já existe `componentes.campo_rotulado`.
- **Dois relógios:** a tela usa `app.relogio()` para o dia do movimento e o
  Painel, mas `datetime.now()` em `agora()`, `_dar_saida` e
  `editar_selecionado`. Funciona, mas o aluno vai ter de explicar por que o
  relógio injetado não vale para a saída.
- **Parâmetro sem uso:** `_passo_v5(banco, con, versao)` não usa `banco`
  (existe para todas as migrações terem a mesma assinatura — vale um
  comentário de uma linha).
- **Comentários enganosos:** B10 (Compiladores) e o docstring de
  `interface.py` citado acima. O resto dos docstrings conferidos (contrato
  do app, `dados.py`, `backup.py`, `usuarios.py`) bate com o código.

---

## 6. Roteiros e prints

Tudo fora do repositório, na pasta temporária da sessão
(`scratchpad/time/onda3-codigo/`): `old/criar_banco_v5.py` (banco v5 com o
código do main), `migrar_com_novo.py`, `t1` a `t7` (cenários acima) e
`prints/` (Entrada e saída, Painel, Usuários, Corrigir e login a 1366×670 com
escala 1,25).
