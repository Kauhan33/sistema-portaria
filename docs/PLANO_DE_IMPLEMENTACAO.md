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
- **Esquema:** a versão do banco depois da entrega. Hoje o banco está na v14.
  Toda migração é atômica (`PRAGMA user_version`) e faz um backup antes.
- **RN nova:** a numeração continua a partir da RN35 (na 2.3 foram da RN41
  à RN45; na 2.4, a RN46; na 2.5, a RN47; na 3.0, a RN48 e a RN49; na 3.2, da
  RN50 à RN57; a próxima livre é a RN58).

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
| **2.3** ✅ | Pessoas, desativação e CRUD | P1, P2, P3, P4, P5, P6 | v11 (sem mudança) | ~2 dias |
| **2.4** ✅ | Compiladores: linha de comando | E1, E2, E4, F1 | v11 (sem mudança) | ~6 dias |
| **2.5** ✅ | Pessoas com mais de um carro | P7, P8 | v12 | ~1 dia |
| **2.5.1** ✅ | Revisão geral com testes por ataque | F3 | v12 (sem mudança) | ~1 dia |
| **3.0** ✅ | Atividade A3 | A3-1 a A3-5 | v13 | ~3 dias |
| **3.1** ✅ | Visual repaginado | — | v13 (sem mudança) | ~2 dias |
| **3.2** ✅ | Todos os desafios extras e melhorias gerais | A1, A2, A3, A5, F2, C1, C2, B1, B2 e os módulos do enunciado | v14 | ~4 dias |
| Depois | O que ficou de fora | A4, A6, D3, C3, B8, N09, S02 | — | — |
| Extras | Se sobrar tempo | E3, E6, D1, D2, E5 | — | — |
| Contínuo | Qualidade e entrega | F3, limpeza de código, Word da entrega | — | — |

**Ordem recomendada e por quê:**
- **2.2** fecha o assunto "veículo" enquanto as regras da rodada 5 estão
  frescas. Também resolve o risco mais sério de operação: o único
  administrador esquecer a senha.
- **2.3** (feita em 29/10/2026) atende ao pedido da professora de CRUD em
  todas as abas e aos ajustes do aluno: a página Bloqueios virou a
  desativação dentro de Pessoas, com "Nova pessoa", Editar e Excluir.
- **2.4** (feita em 29/10/2026) é o diferencial da disciplina: a linha de
  comando com léxico, sintático, semântico e o modo didático.
- **2.5** (feita em 30/10/2026) atende ao pedido do aluno: cadastrar e ver
  mais de uma placa por pessoa; a subaba "Desativadas" virou "Pessoas
  desativadas"; e corrige o fechamento do programa ao abrir essa subaba.
- **3.0 e 3.1** atendem ao enunciado da Atividade A3 e repaginam o visual.
- **3.2** (feita em 12/11/2026) juntou num só passo o que estava previsto
  para a 2.6, a 2.7 e a 2.8, mais os desafios extras do enunciado que
  faltavam.

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
    pronto na 2.7 com o C2.
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

## Versão 2.3 — Pessoas, desativação e CRUD (sem mudança de esquema) ✅

Pedidos do aluno depois do teste da 2.2.1 e o pedido da professora de CRUD
em todas as abas. Feita em 29/10/2026, sem migração: a desativação usa a
tabela `bloqueios` que já existia (desativar = bloqueio ativo do CPF ou da
placa), então nenhum bloqueio antigo se perdeu.

### P1. Entrada e saída: o Movimento sobe · P ✅
- Menos espaço entre "Nova entrada" e o Movimento; o título "Movimento" numa
  linha própria (com o status ao lado), as subabas **Pessoas | Veículos (n)**
  logo embaixo, à esquerda, e a busca e os botões à direita.
- Na tela 1366×670 a tabela continua com 4 linhas.

### P2. Placa: tema escuro e modelo antigo · P ✅
- O recorte branco nos cantos da faixa azul sumiu (os cantos se misturam
  com a moldura) e o fundo do desenho é o do cartão, lido a cada desenho
  (acompanha a troca de tema).
- Placa antiga (LLL-NNNN): cinza claro, moldura escura, faixa superior cinza
  e o hífen (NEY-4829), em todos os lugares que usam `Placa`.

### P3. Bloqueios vira desativação dentro de Pessoas · M · RN12 (reescrita) ✅
- Subabas **Ativas | Desativadas | Veículos desativados**; a página
  Bloqueios saiu da barra lateral.
- Pessoa desativada (CPF) e veículo desativado (placa) não entram; o banco
  confere na entrada e na correção. Só o administrador desativa (motivo de 5
  a 200 caracteres) e reativa. CPF sem cadastro aparece como
  "(sem cadastro)".

### P4. Nova pessoa e Editar · M · RN41 ✅
- "Nova pessoa" cadastra sem registrar entrada, com a validação e os
  limites da entrada; CPF repetido é recusado e abre a ficha; CPF desativado
  avisa. A ficha ganha **Editar** (o mesmo diálogo, com o CPF fixo).

### P5. Excluir pessoa · P · RN42 ✅
- Só o administrador, e só quem nunca teve visita (cadastro por engano); o
  banco conta as visitas de novo. Com histórico, o botão explica que é
  preciso desativar.

### P6. CRUD em todas as abas · M · RN43, RN44, RN45 ✅
- Matriz em `docs/CRUD.md`. Lacunas fechadas: editar usuário (nome e
  perfil, RN43), editar feriado e evento (RN44) e editar a validade de quem
  pode retirar o carro (RN45). Painel e Exceções ficam só leitura (o
  porquê está na matriz e no Word).

---

## Versão 2.4 — Compiladores: linha de comando (sem mudança de esquema) ✅

Entregue em 29/10/2026 (branch `versao-2.4`). A gramática aprovada pelo
aluno (a especificação) está em `docs/GRAMATICA_DA_LINGUAGEM.md`; o esboço
original, em `docs/IDEIAS_NOVAS.md`, seção 2.

**Regra de ouro (RN46):** o comando é traduzido para o **mesmo** registro
que o formulário monta e passa pelas **mesmas** funções: `validacao`,
`horarios` e `Banco` (RN01 a RN45). A linguagem é só outra porta de entrada.

**Decisões do aluno (29/10/2026):**
1. a linguagem tem os comandos do CRUD de Pessoas (cadastrar, editar,
   excluir, desativar, reativar), além de entrada, saida, o implícito,
   situacao, dentro, buscar, pendentes e ajuda;
2. quando falta algo que o formulário perguntaria (de carro ou a pé, com
   qual carro, a senha do administrador, o tipo diferente do cadastro), o
   comando abre o MESMO diálogo do formulário e conclui;
3. o modo didático é para todos, com o CPF sempre mascarado para o
   porteiro;
4. "a pé" se escreve `sem carro`.

### E1. Linha de comando da portaria · G ✅
- **Módulos** em `portaria/linguagem/` (o plano dizia `portaria/comando/`):
  - `lexico.py`: tokens com lexema, tipo, coluna e valor; maiúsculas,
    acentos e plurais; o **autômato finito da placa** (antiga e Mercosul);
    erros léxicos com a coluna;
  - `gramatica.py`: a EBNF, lida pelo próprio código, com FIRST, FOLLOW e
    a conferência **LL(1)** (um teste confere que é a mesma do documento);
  - `sintatico.py`: descida recursiva, um método por regra, árvore de
    `dataclasses`, "você quis dizer…?" (`difflib`);
  - `simbolos.py` e `semantico.py`: a tabela de símbolos (pessoas,
    veículos, desativações, usuário logado e perfil, horários do dia; só
    consulta) e as checagens na ordem, cada uma com a RN (avisos × erros);
  - `executor.py`: grava pelos caminhos do formulário;
  - `interpretador.py`: as três fases de análise juntas (a `Analise` que o
    modo didático mostra).
- **Refatoração da tela (para não duplicar regra):** `AbaCadastro.
  registrar_entrada` virou o caminho único da entrada (o formulário e o
  comando usam); `dar_saida` aceita o "a pé" e o horário do comando (com a
  regra do retroativo); a recusa por desativação vai ao histórico nos dois.
- **Tela:** a "Saída rápida (F2)" virou **Comando (F2 ou Ctrl+K)**, no mesmo
  lugar (`portaria/tela_comando.py`). Só o CPF ou só a placa continuam
  significando `saida`. Resposta numa linha e console recolhível com as
  últimas 30 respostas (linha, ^, fase, dica); máximo de 200 caracteres.
- **Privacidade:** para o porteiro, resposta, console e modo didático com o
  CPF mascarado (a máscara não muda as colunas); o texto do comando não vai
  para o log nem para o banco; os comandos do administrador são recusados ao
  porteiro na fase semântica (e o banco também recusa).

### E2. Modo didático · M ✅
- Interruptor **Didático** ao lado do campo. Janela por cima da tabela
  (cabe no 1366×670), claro e escuro, com a faixa Léxico → Sintático →
  Semântico → Execução (✓/✗/—), a mesma mensagem do console e as abas
  **Tokens** (com o caminho do autômato na placa), **Árvore** (Canvas, o nó
  com erro em vermelho), **Símbolos** e **Checagens** (com a RN). Enquanto
  se digita, mostra o léxico e o sintático; o Enter roda o resto.

### E4. Realce de sintaxe, autocompletar e "você quis dizer…?" · M ✅
- O campo é um `Text` de uma linha (com a mesma interface do `Entry`) e o
  léxico pinta cada token a cada tecla; o erro fica vermelho e sublinhado.
- **Tab** completa comando, palavra-chave, tipo e período; um pedaço do
  nome vira o CPF (mascarado para o porteiro: o campo guarda o CPF de
  verdade só na memória). Repetir o Tab passa para a próxima opção.
- Comando desconhecido recebe a sugestão (`difflib`) e o Tab a aplica.

### F1. Casos de teste prontos para o Word · P/M ✅
- `python -m tests.relatorio` ganhou a seção **"Linguagem de comandos"**
  (CT-54 a CT-68, com a fase de cada caso), além dos CT-01 a CT-53.
- `tests/test_linguagem.py` (uma classe por fase) e
  `tests/test_interface_comando.py` (a tela; a execução compara o banco
  do comando com o do formulário, em dois bancos iguais). 920 testes.

### O que ficou para depois
- Lote de comandos (E3), busca traduzida para SQL (E6), voz (E5).
- `visita` e `cracha` (com o A1, versão 2.6); "sem placa" no `editar` (feito na 2.5);
  corrigir e excluir visita, usuários e configurações pela linguagem.

---

## Versão 2.5 — Pessoas com mais de um carro (esquema v12) ✅

Pedido do aluno depois do teste da 2.4 (30/10/2026).

### P7. Mais de uma placa por pessoa · M · RN47, RF33 ✅
- **Banco (v12):** tabela `placas_pessoa (pessoa_id, placa)`. A migração
  traz a placa do cadastro e as placas com que cada pessoa já veio nas
  visitas (com backup antes, como toda migração). `pessoas.placa` continua
  sendo a **principal**, a que o CPF preenche na entrada.
- **Regra (RN47):** até 5 placas por pessoa, cada uma no formato antigo ou
  Mercosul, sem repetir; a mesma placa pode ser de mais de uma pessoa (o
  carro da família). Quem vem com um carro que não estava no cadastro tem a
  placa guardada sozinha. Tirar uma placa do cadastro tira também quem
  podia retirar aquele carro (RN35, remoção lógica).
- **Nova pessoa e Editar:** o campo **Placas** (Enter ou "Adicionar" põe
  mais uma; o × tira; a 1ª é a principal).
- **Ficha:** com mais de um carro, a linha **Carro** da seção Veículo
  escolhe de qual carro se fala (a placa desenhada, "Quem pode retirar" e
  "Desativar placa" seguem a escolha). A lista mostra "ABC1D23 +1".
- **Entrada:** "Vai entrar de carro?" tem um botão por carro (os que já
  estão no estacionamento não aparecem); o campo Placa avisa "2 carros no
  cadastro".
- **Linguagem:** `cadastrar ... placa A placa B` e `editar CPF placa X
  sem placa Y` (a gramática continua LL(1)); `situacao` lista os carros.

### P8. "Pessoas desativadas" e a correção da 2.4.1 · P ✅
- A subaba **Desativadas** passou a se chamar **Pessoas desativadas**.
- Abrir essa subaba (ou Veículos desativados) fechava o programa com
  RecursionError: o ajuste das colunas comparava a opção `show` da tabela
  (uma tupla no Tk) com um texto, e cada ajuste gerava outro
  `<Configure>`. Corrigido; os testes de tela agora falham quando um
  callback do Tk dá erro, e um erro inesperado com a pilha cheia não
  derruba mais o programa.

## Versão 3.0 — Atividade A3 (esquema v13) ✅

O enunciado da Atividade A3 pede três telas e pelo menos dois desafios extras.
O que ele pede, item por item, está em [`ENUNCIADO_A3.md`](ENUNCIADO_A3.md).

### A3-1. Login do enunciado · P · RF34 ✅
- `tk.Checkbutton` **Mostrar senha** (RNF02: começa escondida, e cada
  formulário novo volta a esconder), `tk.Button` **Entrar** e **Limpar** e a
  **imagem** do logo (`assets/logo_portaria.png`, com a marca desenhada de
  reserva se o arquivo faltar).

### A3-2. Cadastro separado do Controle de acesso · G · RF35, RN48 ✅
- A antiga "Entrada e saída" virou duas páginas: **Cadastro** (o formulário) e
  **Controle de acesso** (o Movimento e o campo Comando). Uma classe só
  (`AbaCadastro`) cuida das duas: `aba` e `aba_controle`.
- Cadastro: **Empresa** e **Motivo** (`tk.Text`, `CampoTexto`) obrigatórios,
  **Data** e **Horário** separados, botões **Cadastrar**, **Limpar** e
  **Cancelar** (`tk.Button`, `BotaoTk`), confirmação com o **código**.
- Controle: **filtro** (Combobox), colunas **Código** e **Situação**
  ("Dentro" ou "Saiu"), botões **Registrar entrada** (na pessoa selecionada),
  **Registrar saída**, **Atualizar** e **Voltar**.
- **Banco (v13):** `registros.empresa`, `registros.motivo`, `pessoas.empresa`.

### A3-3. Ocorrências · M · RF36, RN49 ✅
- Página **Ocorrências** (`tela_ocorrencias.py`): pesquisa, filtro por
  categoria, "Só abertas" (`tk.Checkbutton`), Nova ocorrência, Marcar como
  resolvida e Excluir (administrador). **Banco (v13):** tabela `ocorrencias`.

### A3-4. Prestadores de serviços · P · RF37 ✅
- Filtrando por **Prestador de serviço**, a tabela mostra Empresa e Motivo no
  lugar da Placa e do Tipo; a pesquisa também acha pela empresa.

### A3-5. Linguagem de comandos · P · RN46, RN48 ✅
- `entrada ... empresa "..." motivo "..."`, `cadastrar ... empresa "..."` e
  `editar ... empresa "..."`, com as mesmas regras do formulário. Quem já veio
  reaproveita a empresa do cadastro e o motivo da última visita.

---

## Versão 3.1 — Visual repaginado (sem mudança de esquema) ✅

- Menu lateral grafite, um botão principal por tela (vermelho UNA), `tk.Button`
  arredondado e `tk.Checkbutton` desenhado, Cadastro em blocos e hierarquia de
  ações no Controle de acesso. Ver `design/PROPOSTA_DESIGN.md`, seção 11.

---

## Versão 3.2 — Todos os desafios extras e melhorias gerais (esquema v14) ✅

Feita em 12/11/2026. O banco da 3.1 (v13) é migrado sozinho, com backup antes.

### M1. Funcionários · P/M · RF38, RN54 ✅
- Página **Funcionários**: matrícula, setor, cargo e o ponto de hoje.
- **Banco:** colunas `matricula`, `setor` e `cargo` em `pessoas`.

### M2. Autorizações de entrada · M · RF39, RN53 ✅ (era o A2)
- Página **Autorizações**: criar, emitir (página para imprimir) e cancelar.
- O Cadastro reconhece o CPF autorizado e preenche os dados.
- **Banco:** tabela `autorizacoes_entrada`.

### M3. Encomendas · M · RF40, RN52 ✅ (era o A5)
- Página **Encomendas**: chegada e retirada. **Banco:** tabela `encomendas`.

### M4. Chaves · M · RF41, RN51 ✅
- Página **Chaves**: cadastro, entrega, devolução e histórico.
- **Banco:** tabelas `chaves` e `emprestimos_chave`, com índice único no
  empréstimo aberto.

### A1. Quem procura e crachá · M · RN50 ✅
- Dois campos opcionais no Cadastro; índice único no crachá em uso; a saída
  lembra de recolher. **Banco:** colunas `anfitriao` e `cracha` em `registros`.
- Ficou mais simples que o plano: sem a faixa de números em Configurações e sem
  sugerir o primeiro crachá livre.

### A3. Recado de turno · P · RF42 ✅
- Botão em Ocorrências; faixa no Controle de acesso até marcar como lido.
- **Banco:** tabela `recados_turno`.

### C1 e C2. Painel e relatório · M · RF43, RF44 ✅
- Entradas por dia ou por hora (o pico em destaque), em 7 ou 30 dias.
- Relatório do período numa página HTML que o navegador imprime
  (`portaria/impressao.py`); o temporário antigo é apagado ao abrir o programa.

### F2. Dados de demonstração · P · RF45, RN57 ✅
- Em Configurações › Dados e privacidade, **só o administrador** (pedido do
  aluno). Passa pelas mesmas regras do banco; repetir não duplica.

### D2 (parte). Tamanho da letra · P · RF46 ✅
- Normal, Grande ou Maior, no menu da conta, de cada usuário.

### B1. Anonimizar e prazo de guarda · M · RF47, RN55 ✅
- Anonimizar pelo CPF, com justificativa, e em lote pelo prazo de guarda.
- Os backups antigos ainda têm os dados até serem apagados (os diários, em 30
  dias): está no README.

### B2. Histórico encadeado · M · RN56 ✅
- Coluna `hash` em `auditoria` (SHA-256 do evento e do elo anterior) e o botão
  **Conferir**.
- **Limite honesto:** quem tem o arquivo pode recalcular a corrente, e apagar
  as últimas linhas não é percebido. Sem triggers.

### Código ✅
- `tela_cadastro.py` dividido: o Controle de acesso foi para `tela_controle.py`.
- Módulos novos em arquivos próprios: `dados_modulos.py`, `base_dados.py`,
  `tela_livros.py` e `impressao.py`.

---

## O que ficou para depois

- **A4. Lista de evacuação** (F12): todos no campus, para imprimir.
- **A6. Passe temporário** e "liberar uma vez".
- **D3. Modo treinamento** com banco separado (hoje os dados de demonstração
  entram no banco em uso).
- **C3. Indicadores** da operação por usuário.
- **Relatório do titular** (LGPD) e mapa de calor dia × hora no Painel.
- **Corrigir registro** ainda não edita o crachá nem quem procura (os valores
  são mantidos).
- **B8:** mascarar os CPFs do histórico gravado antes da 2.0. **N09:** limite
  de tentativas na senha atual em "Trocar minha senha". **S02:** o banco não é
  criptografado (depende das permissões do Windows e do BitLocker).
- **Assinatura do instalador:** o aviso do SmartScreen só some com um
  certificado pago.

---

## Extras (se sobrar tempo)

| Código | Ideia | Esforço | Observação |
|---|---|---|---|
| E3 | Lote de comandos ("caderno" de quando o sistema caiu) | M | Depois do E1. Mostra todos os erros com linha e coluna. Pede a senha do administrador uma vez e grava tudo numa transação. |
| E6 | Busca com linguagem de consulta → SQL parametrizado | M | Cobre a fase de geração de código. O modo didático mostra o SQL. |
| D1 | Retorno sonoro (`winsound`) | P | Sons de "registrado", "atenção" e "desativado". Liga e desliga no menu da conta. |
| D2 | Máscara enquanto digita e F1 com os atalhos | M | Cuidado com o cursor do Tk na máscara. O tamanho da letra saiu na 3.2. |
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
| Ordem | O que vem depois da 2.2 | **2.3 Pessoas, desativação e CRUD** (pedido do aluno e da professora, 29/10/2026), depois **2.4 Compiladores**, a **2.5 Pessoas com mais de um carro** (pedido do aluno, 30/10/2026), a 2.6, a 2.7 e a 2.8. |
