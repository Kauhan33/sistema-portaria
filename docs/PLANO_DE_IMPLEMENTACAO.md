# Plano de implementação — Sistema de Portaria

Data: 21/10/2026 · Base: versão 2.1 + rodada 5 (RN32 a RN34: veículo só sai com
o dono, tamanho máximo dos campos, "de carro ou a pé?").

Este plano junta **todas** as ideias já sugeridas e as organiza para
implementação:
- as de `docs/IDEIAS_NOVAS.md` (códigos A1…F3);
- as pendências da revisão (`IDEIAS_E_MELHORIAS.md`, seção 5);
- as sugestões feitas depois da rodada 5 (códigos V1…V4).

As ideias estão agrupadas em versões. Cada versão é entregável sozinha.

## Como ler

- **Esforço:** P = até meio dia · M = 1 a 2 dias · G = 3 dias ou mais, contando os testes.
- **Esquema:** a versão do banco depois da entrega. Hoje o banco está na v10.
  Toda migração é atômica (`PRAGMA user_version`) e faz um backup antes.
- **RN nova:** a numeração continua a partir da RN35.

**O que todo item precisa ter para ser considerado pronto** (vale para todos e
não se repete abaixo):
1. A regra fica numa função pura (sem tela), como em `horarios.py` e
   `validacao.py`.
2. O **banco confere a regra de novo**: a tela nunca é a única trava.
3. Há testes `unittest` positivos **e** negativos. O total de testes não diminui.
4. Todo campo novo tem tamanho máximo nas três camadas: digitação,
   validação e banco (RN33).
5. CPF aparece mascarado em listas, histórico e impressões
   (`validacao.mascarar_cpfs_no_texto`).
6. As telas seguem o visual Guarita, com prints claro e escuro em
   `docs/design/final/`, e cabem em 1366×768.
7. O README (incluindo a seção Versões) e a regra em `IDEIAS_E_MELHORIAS.md`
   estão atualizados.

---

## Visão geral

| Versão | Tema | Itens | Esquema | Esforço |
|---|---|---|---|---|
| **2.2** ✅ | Veículo e acesso do administrador | V0, V1, V2, V3, B3, S07, B4, V4, V5 | v11 | ~5 dias |
| **2.3** | Compiladores: linha de comando | E1, E2, E4, F1 | v11 (sem mudança) | ~6 dias |
| **2.4** | Visitante e operação da guarita | A1, A4, A3, A2, A6, A5 (opcional) | v12 | ~6 dias |
| **2.5** | Dados, relatórios e apresentação | F2, D3, C1, C2, C3 | v12 (sem mudança) | ~5 dias |
| **2.6** | LGPD e segurança | B1, B2, B8, N09, S02 | v13 | ~4 dias |
| Extras | Se sobrar tempo | E3, E6, D1, D2, E5 | — | — |
| Contínuo | Qualidade e entrega | F3, limpeza de código, Word da entrega | — | — |

**Ordem recomendada e por quê:**
- **2.2** fecha o assunto "veículo" enquanto as regras da rodada 5 estão
  frescas. Também resolve o risco mais sério de operação: o único
  administrador esquecer a senha.
- **2.3** é o diferencial da disciplina. Tem que estar pronta bem antes da
  data de entrega, por isso vem logo em seguida.
- **2.4 a 2.6** podem ser feitas na ordem que a professora valorizar mais.
  Para a apresentação, a 2.5 (modo treinamento e Painel) dá o maior efeito.

---

## Versão 2.2 — Veículo e acesso do administrador (esquema v11) ✅

Entregue em 21/10/2026 (branch `versao-2.2`). Ordem feita: V0, S07, B3, V1,
V2, V3, B4, V4, com uma migração só para a v11.

### V0. O banco confere a senha do administrador sozinho · P ✅
- **Hoje:** o diálogo confere a senha e manda ao banco a marca
  `com_senha: True`. O banco confia nessa marca. Esta é uma limitação
  registrada na rodada 5.
- **Proposta:** a autorização leva `login` e `senha`, e o próprio `Banco`
  recalcula o PBKDF2 e conta a tentativa no contador da estação (RN31).
  - Mover o hash de senha (`conferir_senha`, `gerar_hash`) para um módulo novo,
    `portaria/senhas.py`, que não importa `dados`. Assim `dados` e `usuarios`
    usam o mesmo código sem import circular.
  - A senha nunca vai para o histórico nem para o log.
- **Arquivos:** `senhas.py` (novo), `usuarios.py`, `dados.py`
  (`_conferir_autorizacao`, `_conferir_autorizacao_veiculo`), `tela_autorizacao.py`.
- **Testes:**
  - autorização com a marca `com_senha` mas senha errada é recusada;
  - senha certa é aceita;
  - cinco senhas erradas travam a estação (RN31).
- **Pronto quando:** nenhum caminho do `Banco` aceita exceção de senha sem
  recalcular o hash.

### V1. Pessoas autorizadas a retirar o veículo · M · RN35 ✅
- **Problema:** o caso mais comum de "carro sem o dono" é previsível, como o
  cônjuge ou um motorista. Hoje esse caso sempre precisa do administrador.
- **Regra (RN35):** o carro sai sem o dono e **sem senha** quando todas as
  condições abaixo valem:
  - quem leva está na lista de autorizados **daquela placa**;
  - a autorização está ativa e dentro da validade;
  - a pessoa está no campus (entrou a pé) e não tem bloqueio de CPF.
  
  O carro sai junto com a saída dessa pessoa. O histórico grava "Veículo saiu
  com autorizado: placa X levada por Y (autorizado por Z em dd/mm)". Nos demais
  casos continua valendo a RN32 (senha do administrador).
- **Banco (v11):** tabela
  `autorizados_veiculo(id, placa, cpf, nome, valido_ate, criado_por, criado_em,
  ativo, removido_em, removido_por)`. Fica um índice por placa. Remover é
  lógico, como nos bloqueios.
- **Quem cadastra (decidido):**
  - o **porteiro** cadastra só com o dono presente, ou seja, com uma visita
    aberta do dono no campus naquele momento. O banco confere isso também;
  - o **administrador** cadastra a qualquer hora;
  - qualquer usuário pode **remover**, porque remover só diminui a permissão;
  - o histórico grava quem cadastrou e se o dono estava presente.
- **Validade (decidido):** opcional. Sem data, a autorização vale até ser
  removida; com data, vence sozinha.
- **Tela:**
  - **Cadastro:** na ficha da pessoa (Pessoas), seção **Veículo** com
    "Quem pode retirar" e os botões Adicionar e Remover. Para o porteiro, o
    botão Adicionar só fica ativo com o dono no campus e mostra a dica
    "o dono precisa estar no campus".
  - **Saída de quem é autorizado:** a pergunta "Vai levar o carro BRA2E19 de
    Carla?" com as opções Sim, leva o carro / Não.
  - **Aba Veículos:** coluna "Pode retirar" com a quantidade de autorizados.
- **Limites:** nome 80, CPF 11, placa 7.
- **Testes:**
  - autorizado no campus leva o carro sem senha;
  - autorizado vencido, removido, fora do campus ou bloqueado: pede senha;
  - autorizado de **outra** placa: pede senha;
  - desfazer a saída devolve o carro ao estacionamento;
  - porteiro cadastrando com o dono fora do campus é recusado, inclusive
    direto no `Banco`;
  - administrador cadastra com o dono fora;
  - porteiro remove e o histórico registra a remoção.

### V2. Alerta de "carro esquecido" antes do fechamento · P · RN36 ✅
- **Problema:** o carro só aparece como pendente **depois** do fechamento,
  quando o dono já foi embora.
- **Regra (RN36):** a partir do aviso de fechamento que já existe (X minutos
  antes), a faixa amarela da Entrada e saída mostra "2 carros com o dono fora do
  campus — fechamento às 23:00", com link para a aba Veículos já filtrada.
- **Arquivos:** `horarios.py` (momento do aviso), `tela_cadastro.py` (faixa),
  `dados.py` (consulta de estadias com o responsável fora).
- **Testes:** com relógio fixo, o alerta só aparece dentro da janela de aviso e
  some quando o carro sai ou o dono volta.

### V3. Lotação do estacionamento · P/M · RN37 ✅
- **Regra (RN37):**
  - Em Configurações, o campo "Vagas" (0 = sem controle; limite de 4 dígitos).
  - Com vagas definidas, o cabeçalho mostra "Estacionamento 47/50".
  - A entrada de carro com o estacionamento lotado **avisa** ("Estacionamento
    lotado (50/50)") e pede confirmação ao porteiro. Em Configurações, a opção
    "Bloquear quando lotado" (desligada) faz a entrada exigir a senha do
    administrador.
  - O valor inicial é 0 vagas, ou seja, sem controle.
- **Banco (v11):** `parametros.vagas` e `parametros.bloquear_lotado`.
- **Testes:** contagem com estadias abertas; aviso no limite exato (50/50);
  o valor 0 desliga o controle.

### B3. Códigos de recuperação do administrador · P/M · RN38 ✅
- **Regra (RN38):**
  - **Geração:** no primeiro acesso, depois de criar o administrador, o sistema
    gera 8 códigos de uso único (formato `K7QM-2F9X`). Eles aparecem uma única
    vez, com a opção "Imprimir" e a caixa "Guardei em lugar seguro". Os códigos
    são guardados só como hash PBKDF2.
  - **Uso:** no login, "Esqueci a senha" pede o código e a nova senha. O código
    é queimado, fica no histórico e conta como tentativa para o bloqueio
    progressivo.
  - **Novos códigos:** a opção "Gerar novos códigos" no menu do administrador
    invalida os antigos.
  - **Aviso:** com só 1 administrador ativo, o Painel do administrador mostra a
    faixa "Só existe 1 administrador ativo. Crie um segundo."
- **Banco (v11):** tabela `codigos_recuperacao(id, usuario_id, hash, usado_em)`.
- **Testes:**
  - código certo troca a senha e não funciona de novo;
  - código errado conta como tentativa;
  - gerar novos códigos invalida os antigos;
  - o código não aparece em log nem no histórico.

### S07. Troca de senha obrigatória e senha diferente do login · P · RN39 ✅
- **Regra (RN39):**
  - Depois de o administrador criar um usuário ou redefinir a senha dele, o
    primeiro login abre "Defina sua senha" antes de qualquer tela.
  - Nenhuma senha pode ser igual ao login. O cadastro e a troca de senha já
    recusam, mas a **redefinição pelo administrador** ainda não: em
    `tela_usuarios.py`, `validar_senha` é chamada sem o login.
- **Banco (v11):** `usuarios.trocar_senha` (0/1).
- **Testes:**
  - usuário criado entra direto na troca de senha;
  - senha igual ao login é recusada também na redefinição.

### B4. "Ausentar": travar a guarita na hora · P ✅
- **Tela:** botão de cadeado no rodapé da barra lateral, com atalho Ctrl+L.
  - Cobre a janela com o painel de login: "Guarita travada por Paulo às 14:32".
  - O que estava no formulário é mantido.
  - A mesma senha destrava. Se **outro** usuário entrar, é troca de turno: o
    formulário é descartado.
- **Cuidado:** usar o mesmo caminho do "sessão expirada", que já fecha os
  diálogos abertos (bug N01 da revisão).
- **Testes:**
  - travar e destravar mantém o rascunho;
  - outro usuário descarta o rascunho;
  - nenhum diálogo fica acessível por cima da trava.

### V4. Relatório de exceções · M ✅
- **Problema:** é preciso saber, de um período, tudo o que passou por cima da
  regra: horário, retroativo, mais de 24 h, veículo sem o dono, saídas
  automáticas do Encerrar o dia e autorizados (V1).
- **Tela:** em Usuários, aba **Exceções** (só administrador).
  - **Filtros:** período (com o calendário que já existe), tipo de exceção e
    quem autorizou.
  - **Colunas:** quando, tipo, pessoa (CPF mascarado), quem autorizou, quem
    operava e justificativa.
  - **Saídas:** "Exportar CSV" (mesmo padrão do Painel) e "Imprimir", que fica
    pronto na 2.5 com o C2.
- **Base:** eventos da tabela `auditoria`. As ações já gravadas são
  "Exceção autorizada", "Veículo saiu sem o dono", "Saída automática
  (encerramento)" e "Saída automática (atualização)". Para facilitar o filtro,
  passar os nomes das ações para constantes de `dados.py`, como já é feito com
  `VEICULO_SEM_DONO`.
- **Testes:** cada tipo de exceção aparece no filtro certo; o período respeita
  o fuso local; o porteiro não abre a aba.

### V5. Dois carros da mesma pessoa no estacionamento · M · RN40 ✅
*(achado no teste do aluno da 2.2, em 21/10/2026)*
- **Problema:** a pessoa sai a pé, deixa o carro A e volta com o carro B. Na
  saída, a pergunta "Saiu com o veículo B?" é respondida com "Saiu de carro"
  e o programa para ali: nunca pergunta pelo carro A. O carro A fica como
  "Dono fora do campus" e só sai com a senha do administrador. Na entrada com
  B, nada avisava que A ainda estava lá.
- **Regra (RN40), decidida pelo aluno.** Uma pessoa dirige um carro de cada
  vez.
  1. **Entrada:** quem já tem carro no estacionamento e entra com **outro**
     recebe um aviso antes de gravar: "Carla já tem o BRA2E19 no
     estacionamento desde 08:20". As opções são:
     - **Entrar, ficam os dois** (padrão);
     - **O BRA2E19 já saiu**: corrige o esquecimento da guarita, com a senha
       do administrador e justificativa. Vai para o relatório de exceções;
     - **Cancelar**.
  2. **Limite:** até **2 carros** da mesma pessoa ao mesmo tempo. Um terceiro
     só entra com a senha do administrador.
  3. **Saída:** **uma** pergunta, "Com qual carro Carla está saindo?". Há um
     botão por placa, com o horário de entrada, e "A pé, os carros ficam".
     Sai **um** carro com a pessoa.
  4. **O carro que fica** segue RN32, RN35 e RN36. Ele sai quando o dono volta
     a pé e sai com ele, quando um autorizado o leva, ou com a senha do
     administrador. O alerta de carro esquecido mostra esse carro antes do
     fechamento.
- **Banco confere:**
  - o limite de 2 carros abertos por CPF, a não ser com autorização do
    administrador;
  - uma saída de pessoa fecha no máximo uma estadia dela;
  - "já saiu" sem a senha é recusado.
- **Arquivos:** `veiculos.py` (regras puras), `dados.py`, `tela_veiculo.py`
  (pergunta com as placas), `tela_cadastro.py` (`_perguntar_veiculos` e
  entrada).
- **Testes:**
  - A + B: a saída oferece os dois; escolher A deixa B, e o contrário;
  - "A pé" deixa os dois;
  - terceiro carro sem senha é recusado, inclusive direto no `Banco`;
  - "já saiu" sem senha é recusado;
  - saída rápida pela placa A continua pedindo "saiu junto?";
  - Desfazer devolve o carro certo.

---

## Versão 2.3 — Compiladores: linha de comando (sem mudança de esquema)

A gramática, os tokens, os erros por fase e o mockup estão em
`docs/IDEIAS_NOVAS.md`, seção 2.

**Regra de ouro:** o comando é traduzido para o **mesmo** objeto que o
formulário monta e passa pelas **mesmas** funções: `validacao`, `horarios` e
`Banco` (incluindo RN32 a RN39). A linguagem é só outra porta de entrada.

### E1. Linha de comando da portaria · G
- **Módulos novos** em `portaria/comando/`:
  - `lexico.py`: tokens COMANDO, CPF, PLACA, TIPO, HORA, DATA, TEXTO,
    DESCONHECIDO, com linha e coluna;
  - `sintatico.py`: descendente recursivo; monta a árvore;
  - `semantico.py`: usa a tabela de símbolos (pessoas, veículos, bloqueios,
    usuário logado) e as regras de negócio;
  - `executor.py`: chama o `Banco`.
- **Tela:**
  - A "Saída rápida (F2)" vira **Comando (F2 ou Ctrl+K)**. Um CPF ou uma placa
    sozinhos continuam significando `saida`, então nada do que funciona hoje
    quebra.
  - Abaixo do campo fica um console com as últimas respostas.
  - Exceção de horário, retroativo e veículo sem o dono abrem os **mesmos**
    diálogos de autorização.
- **Testes** (uma classe por fase):
  - léxico: CPF com e sem pontos, placa antiga e Mercosul, palavra
    desconhecida;
  - sintático: ordem errada, falta argumento;
  - semântico: CPF inválido, já no campus, bloqueado, carro sem o dono;
  - execução: o resultado é o mesmo do formulário.

### E2. Modo didático · M (depois do E1)
- Interruptor ao lado do campo de comando. Abre um painel com a faixa de fases
  (Léxico → Sintático → Semântico → Execução) e quatro abas:
  - **Tokens**;
  - **Árvore**, desenhada no Canvas;
  - **Símbolos**;
  - **Checagens**, com a RN de cada uma.
- **Testes:** o painel mostra em qual fase o comando parou e o mesmo erro do
  console.

### E4. Realce de sintaxe, autocompletar e "você quis dizer…?" · M
- O campo vira um `Text` de uma linha com *tags* coloridas pelo léxico a cada
  tecla.
- **Tab** completa o comando, o tipo e o nome (o nome vira o CPF mascarado).
- Comando desconhecido recebe uma sugestão por semelhança (`difflib`).

### F1. Casos de teste prontos para o Word · P/M ✅ (adiantado, 22/10/2026: CT-01 a CT-47; a seção dos testes da linguagem fica para o E1)
- `python -m tests.relatorio` gera `relatorio_testes.html` e `.csv`, com:
  - colunas CT-nnn, RN ligada, positivo ou negativo, descrição e
    Passou/Falhou;
  - uma matriz RN × testes;
  - uma seção própria para os testes da linguagem.
- Docstring padrão nos 40 a 60 testes mais importantes:
  `"""CT-045 | RN05 | negativo | CPF já no campus não entra de novo"""`.

---

## Versão 2.4 — Visitante e operação da guarita (esquema v12)

### A1. Visitante completo: anfitrião, setor, motivo e crachá · M · RN41
- Para Visitante, Prestador e Entregador, aparece uma linha extra no
  formulário:
  - **Vai até:** nome ou setor, com sugestões; até 60 caracteres;
  - **Motivo:** reunião, entrega, manutenção, evento ou outro;
  - **Crachá:** sugere o primeiro número livre, de 1 a 50 (faixa ajustável em
    Configurações).
- **Regra (RN41):**
  - um crachá não fica com duas pessoas ao mesmo tempo;
  - na saída, o sistema pergunta "Devolveu o crachá 07?";
  - os crachás não devolvidos aparecem numa faixa.
- **Banco (v12):** colunas opcionais `anfitriao`, `motivo` e `cracha` em
  `registros`; `parametros.crachas` com a faixa de números.

### A4. Lista de evacuação · P
- Atalho **F12** em qualquer página: todos no campus, agrupados por tipo, com
  crachá, anfitrião e os carros, e a hora em destaque.
- Opções "Imprimir" (HTML no navegador) e "Marcar presentes".
- CPF sempre mascarado.

### A3. Livro de ocorrências e passagem de turno · M
- Botão **Ocorrência**: texto de até 500 caracteres, categoria e, se quiser,
  uma pessoa ou placa ligada.
- Ao **Sair**, aparece o "Resumo do turno" com um "Recado para o próximo
  turno". O recado fica num cartão até alguém marcar "Lido".
- **Banco (v12):** tabelas `ocorrencias` e `recados_turno`. CPF digitado no
  texto é mascarado.

### A2. Visitantes esperados · M (depois do A1)
- O administrador agenda nome, CPF (opcional), data, hora, anfitrião e, se
  quiser, uma **autorização antecipada** de horário, válida só naquela data.
- A faixa mostra "3 esperados hoje".
- Ao digitar o CPF de um esperado, os campos do A1 já vêm preenchidos.
- **Banco (v12):** tabela `esperados`. O banco confere a autorização
  antecipada.

### A6. Passe temporário e "liberar uma vez" · M
- Na ficha da pessoa, o administrador cria um passe:
  - janela especial de horário (de/até, dias da semana); ou
  - liberação de um bloqueio uma única vez.
- O motor de exceções de `horarios.py` aceita o passe. A liberação única some
  depois do uso.
- **Banco (v12):** tabela `passes`.

### A5. Encomendas (opcional) · M
- Página **Encomendas**: registrar, ver "Aguardando retirada" e
  "Entregar a…". Também reaproveita os componentes.

---

## Versão 2.5 — Dados, relatórios e apresentação (sem mudança de esquema)

### F2. Gerador de dados fictícios · P/M
- `python -m portaria.demo --meses 3 --banco demo.db`. Usa semente fixa e
  sempre passa pelas funções do `Banco`, sem `INSERT` direto.
- Os dados incluem picos às 07:00, 12:00 e 18:30, exceções, bloqueios,
  veículos sem o dono e autorizados (V1).

### D3. Modo treinamento · P/M (depois do F2)
- Link no login ou `Portaria.exe --treino`. Usa um banco separado
  (`treinamento.db`), refeito a cada abertura.
- Uma faixa laranja fixa diz "MODO TREINAMENTO — nada aqui é real".
- No modo treinamento não há backup.
- Um teste garante que esse modo nunca aponta para o `portaria.db`.

### C1. Painel com período e horário de pico · M
- Seletor no topo do Painel: Hoje, 7 dias, 30 dias ou Período…
- Gráfico novo: mapa de calor dia da semana × hora.
- Gráfico novo: permanência média por tipo.
- Todas as consultas são agregadas no SQL.

### C2. Relatórios imprimíveis (HTML → PDF pelo navegador) · M
- Um gerador com `string.Template` serve para todos os modelos:
  - Movimento do período;
  - Exceções (V4);
  - Resumo do turno (A3);
  - Evacuação (A4);
  - Relatório do titular (B1).
- O arquivo temporário é apagado ao fechar o programa, e cada geração vai para
  o histórico.

### C3. Indicadores da operação por usuário · M
- Em Usuários, aba **Indicadores**: entradas, saídas, correções, exceções
  pedidas e recusas por bloqueio, por usuário e período.
- Sem ranking, para não virar vigilância de funcionário.

---

## Versão 2.6 — LGPD e segurança (esquema v13)

### B1. Retenção, anonimização e relatório do titular · M · RN42
- **Retenção:** em Configurações › Privacidade, "Guardar visitas identificadas
  por 12 meses". Depois disso, nome, CPF, celular e placa viram "Anonimizado",
  e a contagem do Painel continua igual.
- **Relatório do titular:** usa o C2.
- **Anonimizar a pedido:** exige justificativa. Não é permitido com bloqueio
  ativo ou visita aberta.
- **Backups:** o Word deve dizer que a anonimização chega aos backups em até
  30 dias.

### B2. Histórico à prova de adulteração · M
- **Proteção:**
  - triggers que recusam `UPDATE` e `DELETE` em `auditoria`;
  - coluna `hash = sha256(hash_anterior + linha)`;
  - "selo do dia" no nome do backup.
- **Verificação:** em Usuários › Atividade, botão **Verificar integridade**.
- **Limite honesto:** quem tem o arquivo pode recalcular a cadeia. O Word deve
  explicar isso.

### B8, N09 e S02
- **B8:** migração que mascara os CPFs do histórico gravado antes da 2.0.
- **N09:** limite de tentativas na senha atual em "Trocar minha senha".
- **S02:** documentar no README e no Word que o banco depende das permissões
  do Windows e do BitLocker. Não há criptografia própria sem pip.

---

## Extras (se sobrar tempo)

| Código | Ideia | Esforço | Observação |
|---|---|---|---|
| E3 | Lote de comandos ("caderno" de quando o sistema caiu) | M | Depois do E1. Mostra todos os erros com linha e coluna. Pede a senha do administrador uma vez e grava tudo numa transação. |
| E6 | Busca com linguagem de consulta → SQL parametrizado | M | Cobre a fase de geração de código. O modo didático mostra o SQL. |
| D1 | Retorno sonoro (`winsound`) | P | Sons de "registrado", "atenção" e "bloqueado". Liga e desliga no menu da conta. |
| D2 | Máscara enquanto digita, F1 com os atalhos, A−/A+ no tamanho do texto | M | Cuidado com o cursor do Tk na máscara. |
| E5 | Comando por voz | M | Opcional e exige pip e internet. CPF não pode ser ditado (LGPD). |

## Contínuo (a cada versão)

- **F3 `verificar.py`:** roda os testes, o `compileall` e a varredura de termos
  proibidos (lista local, fora do git). Confere o esquema e a migração num
  banco temporário. Gera o `.exe` e o abre por 5 s.
- **Limpeza de código:** `ControleTentativas` não usado, listagens antigas,
  `__getattr__`/`NOMES_DO_CADASTRO`.
- **Word da entrega:** na pasta `entrega/`, fora do git. Usa os prints do modo
  treinamento e o relatório do F1.
- **Publicação:** sempre zerada, sem dados de teste nem usuários. O `.exe`
  abre no "Primeiro acesso". Atualizar `dist/`, `entrega/`, o README e os
  prints.

---

## Decisões tomadas (21/10/2026)

| Item | Pergunta | Decisão |
|---|---|---|
| V1 | Quem cadastra os autorizados a retirar o veículo? | O **porteiro, com o dono presente** (dono no campus naquele momento). O administrador cadastra a qualquer hora. |
| V1 | A autorização tem validade? | **Opcional.** |
| V3 | Estacionamento lotado: avisar ou bloquear? | **Avisa e pede confirmação.** Bloquear fica como opção em Configurações. |
| V3 | Número de vagas inicial | **0**, ou seja, sem controle até o administrador definir. |
| B3 | Quantos códigos de recuperação? | **8.** |
| A1 | Faixa dos crachás | **1 a 50**, ajustável em Configurações. |
| A1 | Motivos da visita | Reunião, entrega, manutenção, evento, outro. Não foi perguntado: ficou o padrão. |
| B1 | Retenção das visitas identificadas | **12 meses.** |
| Ordem | O que vem depois da 2.2 | **2.3 Compiladores**, depois a 2.4, a 2.5 e a 2.6. |
