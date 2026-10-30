# Ideias e melhorias — Sistema de Portaria

Análise feita em 16/10/2026 sobre a v1 (`versoes/v1_original/`).

## 1. O que a disciplina pede × o que já temos

**Exercício (slides 01):** nome, tipo de acesso, entrada, saída, Cadastrar, Limpar,
Excluir, tabela, mensagem de sucesso, salvar em arquivo (opcional) e, no fim,
apontar no código 1 token, 1 símbolo da tabela de símbolos e 1 verificação
semântica.
→ **Tudo atendido.** A v1 vai além: CPF, celular, placa, busca, dashboard.

**Documentação (slides 02):** entregar **sistema + documento Word + testes**. O Word
precisa de: capa, identificação, objetivo, usuários, requisitos funcionais (RF),
não funcionais (RNF), regras de negócio (RN), telas com prints e legenda, fluxo e
casos de teste (inclusive negativos, com "passou/falhou").
→ **Ainda não existe.** Os próprios slides dão exemplos que a v1 não cumpre:
- RN02 — "Somente usuário administrador pode excluir registros" (hoje qualquer um exclui).
- RNF02 — "A senha digitada não deve aparecer em texto aberto" (não há login).
- Fluxo "LOGIN → MENU → CADASTRO → VALIDAÇÃO → SALVAR" (não há login).

## 2. Falhas encontradas na v1 (testadas)

| # | Situação | Hoje | Deveria |
|---|---|---|---|
| F1 ✅ | Nome "123 456" | Aceita | Recusar números/símbolos no nome |
| F2 ✅ | Entrada em 16/10/2030 (futuro) | Aceita | Recusar data futura |
| F3 ✅ | Visita retroativa (09:00–10:00) de quem já está dentro desde 08:00 | Aceita | Recusar período sobreposto do mesmo CPF |
| F4 ✅ | Rótulo do campo de data | Mostra `%d/%m/%Y %H:%M` | Mostrar `dd/mm/aaaa hh:mm` |
| F5 ✅ | Excluir registro | Qualquer um, sem rastro | Só administrador, com registro de quem excluiu |
| F6 ✅ | Código todo num arquivo, a janela abre ao importar | Impossível testar automaticamente | Separar lógica da interface |

## 3. Roteiro sugerido

Ordem pensada para cada etapa já deixar algo entregável. O plano das próximas
versões (2.2 a 2.7, com regras RN35 em diante, banco, telas e testes de cada
ideia) está em `docs/PLANO_DE_IMPLEMENTACAO.md`.

### Etapa 1 — Base sólida (pré-requisito do resto)
- ✅ Corrigir F1–F4 (16/10/2026).
- ✅ Separar em módulos: `portaria/validacao.py`, `dados.py`, `consultas.py`,
  `interface.py` (16/10/2026).
- ✅ **Testes automatizados** com `unittest`: 41 testes, positivos e negativos.
  Viram a seção "Testes" do Word (16/10/2026).
- ✅ Extra: arquivo danificado não é mais sobrescrito (na v1, um JSON corrompido
  fazia o próximo cadastro apagar todo o histórico) e a gravação é atômica.
- ✅ Trocar JSON por **SQLite** (16/10/2026): `portaria.db`, datas em ISO para
  consultas por período, regras `CHECK` no banco, transações, versão do esquema
  (`PRAGMA user_version`) e migração automática do JSON da v1. 52 testes.

**Etapa 1 concluída.**

### Etapa 2 — Funções para o porteiro
- ✅ **Login** de porteiro e administrador (16/10/2026): senha com hash PBKDF2 e
  campo oculto (RNF02); só administrador exclui (RN02); primeiro acesso cria o
  admin, sem senha padrão; bloqueio de 30 s após 5 erros; aba Usuários; histórico
  de ações (quem cadastrou, deu saída, excluiu…). 97 testes.
- Próximos ajustes do login: o próprio usuário trocar a senha; sair sozinho
  depois de X minutos parado; obrigar troca da senha redefinida pelo admin.
- ✅ **Cadastro de pessoas separado das visitas** (16/10/2026): tabela `pessoas`
  (esquema v3, migrada das visitas antigas); CPF virou o primeiro campo e
  preenche nome, celular, placa e tipo sozinho; aviso de quem já está no campus;
  aba Pessoas com busca, correção de dados e "Registrar entrada". 127 testes.
  Pendente: excluir/anonimizar pessoa a pedido dela (LGPD).
- ✅ **Saída rápida** (17/10/2026): duplo clique na linha; campo com CPF ou placa
  exatos + Enter (F2); carona pela placa pergunta antes; várias linhas no botão;
  aviso com Desfazer por 10 s (bloqueado se a pessoa já entrou de novo).
  149 testes.
- ✅ **Corrigir registro** (17/10/2026): todos os campos, mesmas validações;
  porteiro só registros com entrada nas últimas 24 h (RN11 — a primeira versão
  era "só de hoje", mas travava o turno da noite depois da meia-noite);
  histórico "antes → depois" ligado a cada registro (esquema v4); CPF errado
  migra a visita para a pessoa certa. 177 testes.
- ✅ **Lista de bloqueio** (17/10/2026): CPF ou placa com motivo (esquema v5);
  na 2.3 virou a **desativação** de pessoa e de veículo, dentro de Pessoas;
  alerta ao digitar; entrada recusada e registrada no histórico (RN12); só admin
  cria/remove, porteiro vê; remoção guardada; marcação na aba Pessoas. 199 testes.
  Ideia futura: "liberar uma vez" pelo admin sem remover o bloqueio.
- **Visitante**: campos "quem vai visitar / setor" e "motivo"; crachá numerado.
- ✅ **Alerta de permanência** (20/10/2026, versão 2.1): "Tempo excedido" acima
  da permanência máxima de cada categoria e "Saída pendente" depois do
  fechamento, com "Encerrar o dia" (ver a seção da 2.1).
- **Estacionamento**: vagas ocupadas × capacidade.
- **Máscara automática** nos campos (CPF vira 000.000.000-00 enquanto digita) e
  seletor de data.

### Etapa 3 — Relatórios e dashboard
- ✅ **Painel** redesenhado (20/10/2026): no campus agora, entradas de hoje,
  permanência média, com veículo; gráficos por tipo e dos últimos 7 dias,
  calculados no banco (rápido com anos de dados).
- ✅ **Exportar CSV** de um período (Excel), só administrador (20/10/2026).
  Ainda não: PDF.
- ✅ **Backup automático diário** ao abrir o programa (20/10/2026).
- Filtro por período (data inicial e final) no Painel.
- Gráfico de **horário de pico** (entradas por hora do dia).
- Tempo médio de permanência por tipo; visitantes mais frequentes.

### Etapa 4 — Diferencial ligado a Compiladores ⭐ (feita na versão 2.4 ✅)
**Linha de comando da portaria**: um campo onde o porteiro digita comandos curtos,
analisados como uma mini linguagem:

```
entrada 529.982.247-25 visitante placa ABC1D23
saida 52998224725
saida placa ABC1D23
buscar maria visitante hoje
dentro
```

(Ideia original abaixo; a linguagem que foi feita está em
`docs/GRAMATICA_DA_LINGUAGEM.md` e na seção "Versão 2.4".)

- **Léxico**: tokens `COMANDO`, `CPF`, `PLACA`, `TIPO`, `PERIODO`, `DESCONHECIDO`.
- **Sintático**: gramática (ex.: `entrada <cpf> <tipo> [placa <placa>]`), erro se a ordem estiver errada.
- **Semântico**: CPF válido? pessoa já está dentro? placa bloqueada? saída sem entrada?
- **Tabela de símbolos**: pessoas e veículos conhecidos.
- **Modo didático**: mostra na tela os tokens, a árvore e as checagens de cada comando —
  ótimo para a apresentação, porque o professor vê as três fases acontecendo.

Reaproveita a experiência da Lanchonete (`lexer.py`, `semantic.py`). Extra opcional:
comando por **voz**, como na Lanchonete.

### Etapa 5 — Entrega
- Documento Word completo (capa, RF, RNF, RN, telas com prints, fluxo, testes) na
  pasta `entrega/` (fora do git).
- ✅ **Casos de teste para o Word** (22/10/2026, item F1 do plano, adiantado):
  `python -m tests.relatorio` roda os casos CT-01 a CT-53 (53 na 2.3; positivos e
  negativos, cada um ligado a RF/RN e ao teste automático que o comprova) e a
  suíte completa, e grava `relatorio_testes.html`, `.csv` e `.json` fora do
  repositório. 834 testes automatizados na 2.3.
- ✅ Executável `Portaria.exe` com PyInstaller (`build_exe.py`, 20/10/2026).
- ✅ **Instalador do Windows** com Inno Setup (`build_instalador.py` +
  `instalador/portaria.iss`, 21/10/2026): programa em Arquivos de Programas,
  dados em `C:\ProgramData\Portaria` (`portaria/caminhos.py`), atalhos,
  desinstalador que preserva os dados; o `.exe` portátil continua.
- ✅ **Versão 2.1 publicada** (21/10/2026, release v2.1.0 com o instalador e o
  `.exe` portátil), zerada: sem dados de teste nem usuários.
- ✅ Repositório no GitHub **sem** nome, RA ou professora (material e entrega
  ficam fora do git): github.com/Kauhan33/sistema-portaria.

### Versão 2.0 — reforma com time de agentes (19 e 20/10/2026) ✅
Quatro auditorias (design, segurança, código, backend: `docs/revisao/` e
`docs/design/`), implementação em ondas e revisão final com correções:
- ✅ Visual "Guarita": barra lateral, login novo, texto nítido (DPI), layout
  compacto para notebook 1366×768, ícone próprio.
- ✅ Desempenho: tabela principal = movimento do dia + quem está no campus;
  busca e Painel no banco (de ~1,2 s para milissegundos com 1 ano de dados).
- ✅ Integridade: uma entrada aberta por CPF garantida no banco, chaves
  estrangeiras, migrações atômicas com backup antes, recusa de banco mais novo.
- ✅ Login: tentativas gravadas e espera crescente, PBKDF2 600 mil, senha
  mínima 8, troca da própria senha, sessão que expira em 10 min.
- ✅ Privacidade: CPF mascarado no histórico e para o porteiro; permissões
  conferidas também no banco.
- ✅ Revisão final corrigida: ação depois da sessão expirada, notebook,
  saída em linha desatualizada, falha de backup, burla do bloqueio pela correção.
- 359 testes automatizados.

### Versão 2.1 — regras de horário de acesso (20/10/2026) ✅
Decisões do aluno; modelo em `portaria/horarios.py` (funções puras, relógio
injetado), guardado no banco (esquema v7) e editável na página Configurações.
- ✅ Correção: visita com entrada em outro dia e saída hoje sumia do Movimento
  (faltava a parte "saídas de hoje" na consulta; índice novo em `saida`).
- ✅ Funcionamento por dia da semana (seg–sex 06:30–23:00, sáb 07:00–14:00,
  dom fechado), feriados e eventos (o evento substitui o dia, até em domingo).
- ✅ Janela de entrada e permanência por categoria: aluno, professor e
  funcionário relativos ao funcionamento; visitante, entregador e prestador
  com janela fixa, só em dia aberto.
- ✅ Exceções com autorização do administrador (login e senha ou, se ele
  estiver logado, só a confirmação), justificativa obrigatória e o evento
  "Exceção autorizada" no histórico; o banco recusa visita acima de 24 h sem
  autorização.
- ✅ Tempo excedido, saída pendente, faixas de alerta, aviso antes de fechar,
  Encerrar o dia e o número novo no Painel.
- ✅ Página Configurações (só administrador), com validação e histórico.
- 443 testes automatizados (relógio fixo nos testes de tela).

### Versão 2.1 — rodada 2, depois dos testes do aluno (21/10/2026) ✅
- ✅ Saída pendente no fechamento do dia da entrada para todas as categorias,
  com tolerância (30 min) só para professor e funcionário. Saiu a regra
  "max(fechamento, permanência)", que deu a um visitante das 22:55 prazo até
  02:55. Entrada depois do prazo (autorizada) já nasce pendente.
- ✅ Ninguém entra depois do fechamento sem autorização (funcionário até o
  fechamento; janelas fixas param no fechamento).
- ✅ Lançamento retroativo: até 3 h com o dia aberto é normal; mais antigo
  pede autorização; de dia que já fechou, só com a senha (até o administrador
  logado redigita a dele). 5 min de folga para o "agora".
- ✅ Bug: o campo Entrada ficava parado na hora em que o formulário foi limpo.
- ✅ Veículo com estadia própria (banco v8): sair a pé e deixar o carro,
  voltar a pé, sair de carro, saída pela placa, lista de veículos, veículo
  pendente (o Encerrar o dia não tira o carro).
- ✅ Pessoas: histórico de visitas na ficha e ordenação pelo cabeçalho.
- ✅ Calendário e relógio desenhados nos campos de data e hora.
- ✅ A situação das linhas do Movimento muda sozinha a cada 30 s.
- 508 testes automatizados.
- Ideias para depois: ordenar também o Movimento e a lista de veículos pelo
  cabeçalho (a OrdenacaoTabela já está em componentes.py); levar a regra do
  retroativo também para dentro do banco (hoje ela é conferida na tela);
  vaga numerada no estacionamento; vários carros para a mesma pessoa.
- Ideias para depois (da primeira rodada): avisar o administrador por e-mail/WhatsApp das saídas
  pendentes; "liberar uma vez" a categoria para uma pessoa (ex.: professor
  substituto no sábado); horário por pessoa além da categoria; eventos de vários
  dias de uma vez; relatório das exceções autorizadas no período.

### Versão 2.1 — rodada 3, modo noturno (21/10/2026) ✅
- ✅ Tema **Claro / Escuro / Seguir o Windows** por usuário, no menu da conta;
  gravado no banco (v9, migração atômica com backup antes) e aplicado no
  próximo login. Usuários antigos começam no claro; novos seguem o Windows.
- ✅ Troca sem fechar o programa: sessão, página e formulário de entrada
  continuam. A tela de login segue o tema do Windows.
- ✅ Paleta escura própria ("Guarita à noite"), contraste WCAG AA conferido
  por teste nos dois temas, placa Mercosul branca, barra de título escura.
- 535 testes automatizados.
- Ideias para depois: acompanhar a troca de tema do Windows com o programa
  aberto (hoje vale no próximo login); manter a seção aberta de cada página
  (ex.: Configurações › Feriados) ao trocar o tema.

### Versão 2.1 — rodada 4, correções dos dois testes de QA (21/10/2026) ✅
Dois testes de QA (fluxos e casos difíceis) sobre a rodada 2; relatórios em
`docs/qa/` e a situação de cada achado em `docs/qa/CORRECOES.md`.
- ✅ Regras de horário revistas pelo coordenador: o **evento soma** ao dia
  (sábado 07–14 + formatura 18–23 = duas janelas; domingo/feriado: só o
  evento); janela fixa de categoria só dentro de uma janela aberta; saída
  lançada com o **campus fechado** é sempre exceção; "dia já fechou, só com
  senha" usa o **prazo da categoria** (fechamento + tolerância).
- ✅ Veículos: a placa só tira o carro (nunca a pessoa); pessoa com dois
  carros fecha o carro certo; excluir a visita mantém o carro que está lá.
- ✅ Estações ao mesmo tempo: correção com a linha desatualizada é recusada
  (trava otimista), saída e Encerrar o dia com condição no UPDATE.
- ✅ Segurança: busca do porteiro só acha CPF pelos 11 dígitos; importação do
  JSON antigo com as regras do cadastro e no histórico; diálogo de
  autorização com contador próprio por estação (fecha a N04); banco v10 com
  a versão na tabela meta (programa antigo que rebaixa o banco é percebido).
- ✅ Notebook 1366×670: Configurações com botão e mensagens sempre visíveis;
  Movimento com 4 linhas e o aviso com Desfazer inteiro; busca com espera
  de 300 ms entre teclas.
- 573 testes automatizados.
- Ideias para depois (dos QAs): evento que passa da meia-noite; opção "o
  evento libera visitantes"; situação "Na tolerância" (hoje o professor fica
  "Tempo excedido" entre 23:00 e 23:30); inatividade medida com o relógio
  monotônico; levar a janela e o retroativo também para dentro do banco.

### Versão 2.2 — veículo e acesso do administrador (21/10/2026) ✅
Plano em `docs/PLANO_DE_IMPLEMENTACAO.md` (seção "Versão 2.2"). Banco na
versão 11, numa migração só (atômica, com backup antes).
- ✅ **V0** — o banco confere a senha do administrador sozinho: o hash saiu
  para `portaria/senhas.py` (sem importar `dados`); a autorização leva login
  e senha e o `Banco` recalcula o PBKDF2 com o contador da estação (RN31).
  A marca "com_senha" vinda de fora é ignorada e a autorização de outro
  usuário sem a senha dele é recusada.
- ✅ **S07 / RN39** — troca de senha obrigatória no primeiro login e
  redefinição pelo administrador recusando senha igual ao login.
- ✅ **B3 / RN38** — 8 códigos de recuperação do administrador, "Esqueci a
  senha" no login, "Gerar novos códigos" no menu da conta e a faixa "Só
  existe 1 administrador ativo" no Painel.
- ✅ **V1 / RN35** — pessoas autorizadas a retirar o veículo (ficha da
  pessoa › Veículo, coluna "Pode retirar" na lista de veículos).
- ✅ **V2 / RN36** — alerta de carro esquecido na janela de aviso de
  fechamento.
- ✅ **V3 / RN37** — lotação do estacionamento (vagas, aviso ou bloqueio).
- ✅ **B4** — "Ausentar": cadeado no rodapé da barra lateral ou Ctrl+L.
- ✅ **V4** — Relatório de exceções em Usuários (filtros, CSV).
- ✅ **V5 / RN40** — dois carros da mesma pessoa (achado no teste do aluno):
  aviso na entrada com outro carro, limite de 2 e uma pergunta só na saída.
- 782 testes automatizados.
- Ideias para depois: "Imprimir" o relatório de exceções (C2, versão 2.6);
  limite de tentativas na senha atual de "Gerar novos códigos" (junto com a
  N09); filtro "só dono fora" na lista de veículos a partir da faixa do
  carro esquecido.

### Versão 2.2.1 — entrega da disciplina (22/10/2026) ✅
- ✅ Confirmação da entrada com o texto do enunciado, na faixa verde (sem
  caixa extra): "Registro cadastrado com sucesso! Entrada de Ana às 14:30."
  O item 9 do desafio ("Mostrar 'Registro cadastrado com sucesso!'") passa
  a ser atendido ao pé da letra. Os tipos de acesso continuam os do campus
  (sem "Morador"), por decisão do aluno; o Word explica a adaptação.
- ✅ Casos de teste documentados (`python -m tests.relatorio`, CT-01 a CT-47)
  e prints novos da versão atual (`docs/design/final/v221_*`).
- 784 testes automatizados.

### Versão 2.3 — pessoas, desativação e CRUD (29/10/2026) ✅
Pedidos do aluno depois do teste da 2.2.1 e o da professora (CRUD em todas
as abas). Plano em `docs/PLANO_DE_IMPLEMENTACAO.md` (seção "Versão 2.3"; o
de Compiladores passou a ser a 2.4). Sem mudança de esquema (banco v11).
- ✅ **P1** — Entrada e saída: o Movimento sobe; título numa linha própria
  (com o status ao lado), subabas Pessoas | Veículos logo embaixo, busca e
  botões à direita. Na tela 1366×670 a tabela continua com 4 linhas.
- ✅ **P2** — Placa sem o recorte branco no tema escuro (o fundo segue o
  cartão e a troca de tema) e o desenho da **placa antiga** (cinza, moldura
  escura, NEY-4829) no formulário, nos diálogos e na ficha.
- ✅ **P3 / RN12** — a página Bloqueios virou a **desativação** dentro de
  Pessoas (subabas Ativas | Desativadas | Veículos desativados). Fica na
  mesma tabela `bloqueios` (desativar = bloqueio ativo), sem migração.
- ✅ **P4 / RN41** — **Nova pessoa** (cadastro sem entrada) e **Editar** na
  ficha.
- ✅ **P5 / RN42** — **Excluir pessoa** só pelo administrador e só sem visita.
- ✅ **P6 / RN43–RN45** — CRUD em todas as abas (`docs/CRUD.md`): editar
  usuário, editar feriado e evento e editar a validade de quem pode retirar
  o carro. Painel e Exceções são só leitura (justificado na matriz).
- 834 testes automatizados; casos de teste CT-01 a CT-53.

### Versão 2.4 — Compiladores: linha de comando (29/10/2026) ✅
Plano em `docs/PLANO_DE_IMPLEMENTACAO.md` (seção "Versão 2.4") e a
gramática aprovada pelo aluno em `docs/GRAMATICA_DA_LINGUAGEM.md`. Sem
mudança de esquema (banco v11).
- ✅ **E1 / RF14 / RN46** — a "Saída rápida (F2)" virou o campo
  **Comando (F2 ou Ctrl+K)**, no mesmo lugar: a linguagem da portaria em
  `portaria/linguagem/` (léxico, gramática LL(1) conferida pelo código,
  sintático por descida recursiva, tabela de símbolos, semântico com a RN
  de cada checagem e executor). 13 comandos, inclusive o CRUD de pessoas;
  só o CPF ou só a placa continuam dando a saída. O comando monta o mesmo
  registro do formulário e passa pelas mesmas funções; quando falta o que o
  formulário perguntaria, abre o mesmo diálogo. Resposta numa linha e
  console recolhível com as últimas respostas (linha, ^, fase e dica).
- ✅ **E2 / RF32** — **modo didático** (na 2.4, interruptor "Didático"; desde
  a 2.5.3, só pelo atalho Ctrl+Shift+D, listado em Configurações › Atalhos): a faixa
  Léxico → Sintático → Semântico → Execução (✓/✗/—) e as abas Tokens,
  Árvore (desenhada no Canvas, o nó com erro em vermelho), Símbolos e
  Checagens; janela por cima da tabela (cabe no 1366×670), claro e escuro.
- ✅ **E4** — realce por token a cada tecla, Tab que completa comando,
  palavra, tipo e nome (o nome vira o CPF, mascarado para o porteiro) e o
  "você quis dizer…?" (difflib).
- ✅ **F1** — casos CT-54 a CT-68 na seção "Linguagem de comandos" do
  relatório, por fase; a execução é testada comparando o banco do comando
  com o do formulário.
- Privacidade: para o porteiro, toda resposta, o console e o modo didático
  mostram o CPF mascarado; o texto dos comandos não vai para o log nem para
  o banco.
- 920 testes automatizados; casos de teste CT-01 a CT-68.
- Ideias para depois: lote de comandos (E3), busca traduzida para SQL (E6),
  as opções `visita` e `cracha` com o visitante completo (A1, 2.6), "sem
  placa" no `editar` (feito na 2.5), histórico das linhas digitadas (seta
  para cima) só na memória.

### Versão 2.5 — Pessoas com mais de um carro (30/10/2026) ✅
Pedido do aluno depois do teste da 2.4. Esquema do banco v12 (migração com
backup antes; nada se perde).
- ✅ **P7 / RF33 / RN47** — uma pessoa pode ter até 5 placas no cadastro
  (tabela `placas_pessoa`; a migração traz a placa do cadastro e as das
  visitas). Nova pessoa e Editar têm o campo **Placas** (Enter ou
  "Adicionar"; × tira); a ficha tem a linha **Carro** para escolher de qual
  carro se fala ("Quem pode retirar" e "Desativar placa" seguem a escolha);
  a lista mostra "ABC1D23 +1"; "Vai entrar de carro?" tem um botão por
  carro. Linguagem: `cadastrar ... placa A placa B` e `editar CPF placa X
  sem placa Y`.
- ✅ **P8** — a subaba "Desativadas" virou **"Pessoas desativadas"**; abrir
  essa subaba não fecha mais o programa (RecursionError do ajuste das
  colunas, versão 2.4.1 que não chegou a ser publicada); os testes de tela
  falham quando um callback do Tk dá erro.
- 974 testes automatizados; casos de teste CT-01 a CT-78.

### Versão 2.5.1 — Revisão geral com testes por ataque (30/10/2026) ✅
Sem mudança de esquema (banco v12).
- Testes novos: `tests/test_aleatorio.py` (sequências aleatórias com as
  invariantes), `tests/test_linguagem_fuzz.py`, `tests/test_duas_estacoes.py`,
  `tests/test_entradas_estranhas.py`, `tests/test_desempenho.py` (plano das
  consultas) e `tests/test_linguagem_caminhos.py` (o que a cobertura mostrou
  sem teste). Fora da suíte, na revisão: 48 mil operações aleatórias, 20
  mil linhas de fuzz, 30 mil ações de "macaco" na janela visível e o
  banco de 2 anos (146 mil visitas) para medir o tempo.
- Corrigidos: desfazer a saída depois de corrigir a placa; CPF do porteiro
  depois de aspas sem fechamento; `buscar` com período antigo; filtro da
  Atividade; ficha com mais de 3 carros; texto do "Vai entrar de carro?".
- Lista de Pessoas 25 vezes mais rápida com 20 mil pessoas.
- Decisão do aluno: corrigir a placa de uma visita (erro de digitação)
  tira a placa antiga dos carros da pessoa, se nenhuma outra visita dela
  usou essa placa (antes ela ficava no cadastro e aparecia em "Vai entrar
  de carro?").
- 1010 testes automatizados; casos de teste CT-01 a CT-89.

## 4. Rascunho de requisitos para o Word

**RF**: RF01 cadastrar entrada · RF02 registrar saída (botão, duplo clique,
saída rápida por CPF/placa) · RF03 consultar/buscar histórico · RF04 excluir
registro (admin) · RF05 exibir Painel · RF06 login e primeiro acesso · RF07
exportar CSV (admin) · RF08 cadastro de pessoas com preenchimento automático ·
RF09 corrigir registro com histórico · RF10 desativar e reativar pessoa e
veículo (até a 2.2: lista de bloqueio) · RF11 gerenciar
usuários (admin) · RF12 trocar a própria senha · RF13 backup diário automático ·
RF14 linha de comando da portaria: registrar, consultar e o CRUD de pessoas por
comandos digitados (2.4) · RF15 configurar os horários de
acesso: funcionamento, categorias, feriados e eventos (admin) · RF16 autorizar
exceção de horário (admin) · RF17 encerrar o dia (admin) · RF18 alertar tempo
excedido, saída pendente e fechamento próximo · RF19 registrar a entrada e a
saída do veículo separadas da pessoa (estacionamento) · RF20 ver o histórico
de visitas de cada pessoa · RF21 escolher datas e horas num calendário e
relógio · RF22 recuperar a senha do administrador com um código de uso único
(2.2) · RF23 cadastrar quem pode retirar o veículo de uma pessoa (2.2) · RF24
travar a guarita ("Ausentar") (2.2) · RF26 escolher com qual carro a pessoa sai
(2.2) · RF25 relatório de exceções do período,
com exportação (2.2) · RF27 cadastrar pessoa sem registrar entrada ("Nova
pessoa") (2.3) · RF28 editar e excluir o cadastro de uma pessoa (2.3) · RF29
editar o nome e o perfil de um usuário (2.3) · RF30 editar feriado e evento
(2.3) · RF31 editar a validade de quem pode retirar o veículo (2.3) · RF32 modo
didático: mostrar as fases da análise do comando (tokens, árvore, tabela de
símbolos e checagens) (2.4) · RF33 cadastrar e ver mais de uma placa por
pessoa (2.5).

**RNF**: RNF01 interface simples com botões identificados · RNF02 senha oculta e
armazenada com hash · RNF03 tela principal e busca respondem na hora mesmo com
anos de dados · RNF04 roda no Windows só com Python padrão (ou .exe) · RNF05
dados pessoais ficam só no computador da portaria (LGPD) · RNF06 texto nítido com
escala de tela e uso em notebook 1366×768 · RNF07 contraste de cores AA (WCAG).

**RN**: RN01 campos obrigatórios · RN02 só admin exclui · RN03 saída só com entrada
aberta · RN04 saída não anterior à entrada · RN05 um CPF não pode ter duas entradas
abertas · RN06 CPF/celular/placa válidos · RN07 entrada não pode ser no futuro ·
RN08 sempre existe ao menos um administrador ativo · RN09 usuário desativado não
entra · RN10 5 senhas erradas bloqueiam o login por 30 s · RN11 porteiro corrige só registros com
entrada nas últimas 24 h; administrador corrige qualquer um, sempre com histórico ·
RN12 (reescrita na 2.3) pessoa desativada (CPF) ou veículo desativado (placa) não entra:
a entrada é recusada com o motivo, quando e quem desativou; só o administrador desativa
(motivo de 5 a 200 caracteres) e só ele reativa; a desativação não se apaga (reativar
guarda quem e quando) e tudo vai ao histórico; o banco confere de novo na entrada e na
correção (que não pode pôr um desativado no campus) ·
RN13 sem uso por 10 minutos a sessão se encerra · RN14 o porteiro vê o CPF mascarado
nas listas e no histórico · RN15 senha com pelo menos 8 caracteres e diferente do login.
(RN10 na 2.0: a espera começa em 30 s, dobra a cada bloqueio até 15 min e não zera ao
reabrir o programa.)

Novas na 2.1 (regras de horário, atualizadas na rodada 2):
RN16 o campus tem horário por dia da semana; feriado fecha o dia; o evento SOMA uma
janela ao dia (sábado 07–14 com formatura 18–23 abre nas duas; num domingo ou feriado o
evento é a única janela); o fechamento do dia é o fim da última janela · RN17 cada
categoria só entra na sua janela, em cada janela do dia (aluno no funcionamento até
30 min antes de fechar; professor de 30 min antes de abrir até fechar; funcionário de
1 h antes de abrir até fechar; visitante 08–18, entregador 07–17 e prestador 07–19, só
DENTRO de uma janela aberta: visitante às 08:00 num domingo com evento 18–23 é
exceção) · RN18 cada categoria tem
permanência máxima (aluno e professor até fechar; funcionário 12 h; visitante 4 h;
entregador 1 h; prestador 10 h); acima dela a visita fica "Tempo excedido" (só alerta) ·
RN19 nenhuma visita passa de 24 h · RN20 entrada fora da janela, lançamento retroativo
antigo (RN24) e visita acima de 24 h são exceções: só com autorização de um
administrador ativo e justificativa, registradas no histórico com quem autorizou e quem
operava · RN21 a visita aberta fica "Saída pendente" no fechamento do dia da entrada
(23:00 ou o fim do evento), para todas as categorias; professor e funcionário têm 30 min
de tolerância (configurável por categoria; as outras 0); quem entrou depois desse prazo
(autorizado) já nasce pendente; só o administrador encerra o dia (saída automática no
prazo de cada uma, registrada) · RN22 só o administrador altera os horários, e cada
alteração fica no histórico · RN23 ninguém entra depois do fechamento sem autorização
· RN24 lançamento retroativo (entrada ou saída no passado, no cadastro e na correção):
até 3 h, num horário em que a categoria podia estar no campus e antes do prazo do dia,
é normal; mais de 3 h pede autorização; uma SAÍDA num horário com o campus fechado
para a categoria (madrugada, domingo sem evento, entre duas janelas) pede autorização
mesmo se recente; depois do PRAZO DA CATEGORIA (fechamento + tolerância), só com a
senha de um administrador, mesmo com ele logado (a saída real às 23:00 de uma
funcionária, lançada às 23:10, é normal); até 5 min no passado conta como agora; os
segundos do relógio não contam · RN25 o veículo tem estadia própria: a
entrada com placa abre a estadia, a pessoa pode sair a pé e deixar o carro, e o carro
depois do prazo do responsável fica "Veículo pendente" (o Encerrar o dia não o tira:
ele está lá) · RN26 uma placa só tem uma estadia aberta: o carro que já está no
estacionamento não "entra" de novo · RN27 pela placa só sai o carro, nunca a pessoa;
na saída de quem tem mais de um carro no estacionamento, pergunta-se primeiro pelo
carro desta visita · RN28 excluir a visita não tira do estacionamento o carro que
ainda está lá (a confirmação avisa e o histórico registra "Veículo mantido no
estacionamento"; o carro sai pela placa) · RN29 uma correção aberta antes de outra
estação mudar a visita é recusada ("alterado em outra estação"); duas saídas ao mesmo
tempo: vale a primeira · RN30 o porteiro só acha um CPF na busca pelos 11 dígitos ·
RN31 senhas erradas no diálogo de autorização contam num contador da estação: depois
de 5, só o diálogo fica travado naquele computador (espera crescente), nunca o login
do administrador; cada erro e a trava ficam no histórico.

Novas na rodada 5 (pedidos do aluno):
RN32 o VEÍCULO SÓ SAI COM O DONO (o responsável da estadia, quem entrou com o carro):
sem senha, o carro sai junto com o dono — na saída dele ("Saiu de carro", também
depois de sair a pé e voltar a pé) e pela placa com o dono no campus saindo junto;
sem o dono (fora do campus, outra pessoa saindo com o carro, ou pela placa com o dono
ficando no campus), só com a SENHA de um administrador ativo (o administrador logado
também redigita a sua) e justificativa, registrado como "Veículo saiu sem o dono". O
banco confere de novo: fechar uma estadia sem o dono saindo na mesma operação, ou a
correção que apaga/troca a placa ou o dono de um carro que ficou, só com essa
autorização; desfazer, exclusão, importação e "Encerrar o dia" não tiram carro ·
RN33 todo campo de texto tem tamanho máximo (nome 80, login 20, senha 64,
justificativa e motivo 200, descrição 80, buscas 60, saída rápida 14, data e hora 16,
data 10, hora 5, CPF e celular 11, placa 7): a digitação para no máximo, a colagem
corta no máximo, a validação recusa ("X: no máximo N caracteres") e o banco também ·
RN34 na entrada de quem tem placa cadastrada, a pergunta "vai entrar de carro?"
(De carro abre a estadia; A pé entra sem placa; Com outro carro volta ao campo
Placa); não pergunta se a placa foi digitada ou apagada à mão, se o carro já está no
estacionamento ou se não há placa cadastrada; o Enter escolhe "De carro" se a última
visita foi de carro, senão "A pé".

Novas na 2.2 (veículo e acesso do administrador):
RN35 QUEM PODE RETIRAR O VEÍCULO: cada placa tem a lista de pessoas autorizadas a
levar o carro sem o dono; o carro sai SEM SENHA quando quem leva está na lista
daquela placa, com a autorização ativa e na validade (opcional: sem data vale até
alguém remover; com data, até o fim daquele dia), está no campus (entrou a pé) e não
está desativada (RN12); o carro sai junto com a saída dessa pessoa ("Vai levar o carro
BRA2E19 de Carla?" — Sim, leva o carro / Não), registrado como "Veículo saiu com
autorizado" (quem cadastrou e quando); nos outros casos vale a RN32. O porteiro só
cadastra com o dono no campus naquele momento; o administrador, a qualquer hora;
qualquer usuário remove (remoção lógica, com histórico). Tudo conferido também no
banco · RN36 dentro da janela de aviso antes de fechar, a faixa "N carros com o dono
fora do campus — fechamento às HH:MM", com o link para a lista de veículos; some
quando o carro sai ou o dono volta · RN37 lotação: com vagas definidas em
Configurações (0 = sem controle, até 4 dígitos), o cabeçalho mostra "Estacionamento
47/50"; a entrada de carro com o estacionamento lotado avisa ("Estacionamento lotado
(50/50)") e pede confirmação; com "Bloquear quando lotado", só com a senha de um
administrador; o banco confere e registra · RN38 o administrador do primeiro acesso
recebe 8 códigos de recuperação de uso único (K7QM-2F9X, sem caracteres ambíguos),
mostrados uma vez ("Guardei em lugar seguro" para continuar; "Imprimir"); no banco,
só o hash; no login, "Esqueci a senha" troca a senha com um código, que é queimado,
vai ao histórico (sem o código) e, errado, conta no bloqueio progressivo; "Gerar
novos códigos" (com a senha atual) invalida os antigos; com só 1 administrador
ativo, o Painel pede um segundo · RN39 quem o administrador cria, ou cuja senha ele
redefine, define a própria senha no primeiro login, antes de qualquer tela (o banco
recusa qualquer operação dele até isso); nenhuma senha pode ser igual ao login,
inclusive na redefinição pelo administrador. O administrador do primeiro acesso
escolheu a dele e não troca · RN40 DOIS CARROS DA MESMA PESSOA (uma pessoa
dirige um carro de cada vez): quem já tem carro no estacionamento e entra com OUTRO
recebe, antes de gravar, o aviso "Carla já tem o BRA2E19 no estacionamento desde
08:20" — Entrar, ficam os dois (padrão); "O BRA2E19 já saiu" (corrige o esquecimento
da guarita, só com a senha de um administrador e justificativa; vai ao relatório de
exceções como "Carro que já tinha saído"); ou Cancelar. Até 2 carros abertos do
mesmo CPF; um terceiro só com a senha do administrador ("Terceiro carro" no
relatório). Na saída de quem tem mais de um carro, UMA pergunta, "Com qual carro
Carla está saindo?", com um botão por placa (e o horário de entrada) e "A pé — os
carros ficam"; sai no máximo um carro com a pessoa. O carro que fica segue RN32,
RN35 e RN36. O banco confere o limite, que uma saída fecha no máximo um carro dela e
que "já saiu" sem a senha é recusado.

Novas na 2.3 (pessoas, desativação e CRUD):
RN41 NOVA PESSOA: o cadastro de pessoa sem registrar entrada usa a mesma validação e os
mesmos limites da entrada (RN01, RN06, RN33); CPF já cadastrado é recusado e a ficha que
já existe é aberta; CPF desativado avisa (pode cadastrar, e a pessoa continua sem
entrar); qualquer usuário cadastra e edita (o CPF não muda na edição); o banco confere de
novo · RN42 EXCLUIR PESSOA: só o administrador, e só o cadastro de quem nunca teve
visita (cadastro feito por engano); com visitas, a exclusão é recusada e a saída é
desativar (RN12); o banco conta as visitas de novo; vai ao histórico com o CPF
mascarado; a desativação do CPF, se houver, continua valendo · RN43 EDITAR USUÁRIO: o
administrador muda o nome e o perfil; o login não muda (identifica as ações no
histórico); ninguém muda o próprio perfil e o último administrador ativo não vira
porteiro (RN08); "excluir" usuário é desativar (RN09) · RN44 EDITAR FERIADO E EVENTO:
só o administrador, com a mesma validação do cadastro; a data nova não pode repetir a de
outro feriado (ou evento); a mudança vai ao histórico com o antes e o depois · RN45
VALIDADE DE QUEM PODE RETIRAR: muda com a mesma permissão de quem cadastra (RN35: o
porteiro só com o dono no campus); vazio = sem prazo; nunca antes de hoje; vai ao
histórico.

Nova na 2.4 (linguagem de comandos):
RN46 A LINGUAGEM É SÓ OUTRA PORTA: um comando monta o mesmo registro do formulário e
passa pelas mesmas regras e gravações (RN01 a RN45; o banco confere de novo); quando
falta o que o formulário perguntaria (de carro ou a pé, com qual carro, a senha do
administrador, o tipo diferente do cadastro), abre o mesmo diálogo; os comandos do
administrador (excluir, desativar, reativar) são recusados ao porteiro já na análise
semântica (e no banco); para o porteiro, toda resposta, o console e o modo didático
mostram o CPF mascarado (RN14), mesmo que ele tenha digitado o número inteiro; o texto
dos comandos não é gravado no log nem no banco (o histórico recebe só os eventos
normais); a linha tem no máximo 200 caracteres (RN33).

Nova na 2.5 (pessoas com mais de um carro):
RN47 VÁRIOS CARROS POR PESSOA: o cadastro guarda até 5 placas por pessoa, cada uma
no formato antigo ou Mercosul e sem repetir; a primeira é a principal (a que o CPF
preenche na entrada); a mesma placa pode ser de mais de uma pessoa (o carro da
família); quem vem com um carro que não estava no cadastro tem a placa guardada
sozinha; tirar uma placa do cadastro tira também quem podia retirar aquele carro
(RN35, remoção lógica); "Vai entrar de carro?" oferece cada carro que não está no
estacionamento, e o carro escolhido passa pelas mesmas checagens (RN12, RN26); na
correção de uma visita, a placa antiga sai dos carros da pessoa se nenhuma outra
visita dela usou essa placa (2.5.1).

## 5. Pendências registradas na revisão final (para a versão 2.1+)

Detalhes em `docs/revisao/REVISAO_FINAL_CODIGO.md` e `REVISAO_FINAL_SEGURANCA.md`.
- Histórico de ações com trava contra alteração (triggers/hash) — S10.
- Prazo de retenção e "anonimizar pessoa" (LGPD) — S08.
- Banco e backups sem criptografia: depende de permissões do Windows/BitLocker — S02.
- ✅ Troca de senha obrigatória no primeiro acesso; redefinição pelo admin
  recusar senha igual ao login — S07 (versão 2.2, RN39).
- ✅ Admin travado de propósito pelo diálogo de autorização — N04 (rodada 4:
  contador próprio da estação). Continua: o login normal do admin ainda pode
  ser travado por quem chuta a senha na tela de login (é o bloqueio por
  tentativas, de propósito); limite de tentativas na senha atual em "Trocar
  minha senha" — N09.
- Histórico gravado antes da 2.0 continua com CPF completo — B8.
- Limpeza de código para a apresentação: ControleTentativas (não usado pelas
  telas), listagens antigas do banco, o repasse `__getattr__`/NOMES_DO_CADASTRO.
