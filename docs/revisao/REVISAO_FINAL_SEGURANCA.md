# Revisão final de segurança (Onda 3) — Sistema de Portaria

Data: 20/10/2026 · Escopo: `git diff 5362601..reforma` (HEAD `2d864ce`), com foco em
`portaria/*.py` e `portaria_universidade.py`.
Método: leitura do código, comparação com a auditoria anterior (`SEGURANCA.md`, S01–S20)
e provas de conceito executadas **fora** do repositório, com bancos temporários. Nenhum
arquivo do projeto foi alterado além deste relatório. A suíte `python -B -m unittest`
passou inteira (329 testes, OK) e o `git status` continuou limpo.

PoCs (pasta da sessão, fora do git): `scratchpad/time/onda3-seguranca/`
- `poc.py`: camada de dados, login, senha, backup, CSV, log e máscara (saída em `saida_poc.txt`).
- `poc_ui.py`: telas com Tk oculto e caixas falsas, como nos testes do projeto (`saida_poc_ui.txt`).
- `poc_timer_nativo.py`: prova no Windows real de que o `after()` do Tk roda enquanto uma
  caixa nativa (`askyesno`, "Salvar como") está aberta (`saida_timer_nativo.txt`).

## 1. Resumo

A reforma resolveu de fato a maior parte do que prometeu. A correção do S01 barra o
bloqueio na tela. O banco confere o perfil quando recebe o autor. As tentativas de login
sobrevivem a reabrir o programa. O hash usa 600 mil iterações e é refeito no login. O
"Login recusado" não grava mais a senha digitada no campo errado. As mensagens do SQLite
não chegam mais ao usuário. O histórico mascara o CPF, há backup diário e a sessão expira.
O log não guarda dados pessoais nem senha (conferido).

Há **um problema novo que vale corrigir antes do `main`**:

- **N01. Uma ação confirmada depois de a sessão expirar roda sem autor, ou seja, sem
  checagem de perfil e sem histórico.** O timer de inatividade continua rodando enquanto
  uma caixa nativa do Windows está aberta (provado em `poc_timer_nativo.py`). Se o
  administrador clica em "Excluir" ou "Exportar CSV" e sai de perto com a caixa aberta,
  depois de 10 minutos a sessão é encerrada, mas a caixa continua na tela. Quem clicar
  "Sim" ou escolher o arquivo depois disso apaga os registros, ou gera um CSV com CPF e
  celular completos, **sem nenhuma linha no histórico**. Isso foi comprovado nas PoCs
  NOVO-SESSAO-1 e 2. A causa é que `app.autor` vira `None` e o `Banco` trata `autor=None`
  como "chamada interna: sem checagem e sem histórico".

E uma **promessa que não é verdade em todo lugar**:

- **N02. O porteiro ainda vê o CPF completo de qualquer pessoa** pela página Pessoas: ao
  escolher uma pessoa e clicar em "Registrar entrada", o campo CPF da Entrada recebe o
  número inteiro. O mesmo acontece no campo da janela Corrigir. O celular aparece completo
  na ficha da página Pessoas. As tabelas estão mascaradas, mas os formulários não (PoCs
  MASC-1, 2 e 3).

O restante é "seria bom" ou continua aberto como já estava: arquivo do banco sem
proteção (S02), histórico sem proteção contra `DELETE` (S10), LGPD sem retenção nem
anonimização (S08) e backups sem política.

## 2. Tabela de achados

Severidade no contexto do trabalho: app desktop local, atacante provável **interno**
(porteiro ou alguém no PC da guarita). Esforço: **P** = até 1 h · **M** = algumas horas.

### 2.1 Itens da auditoria anterior

| Item | Status | Sev. | Evidência | Correção sugerida |
|---|---|---|---|---|
| **S01** Bloqueio burlado pela "Corrigir" | **Resolvido** (na tela) | Baixa (resto) | `poc_ui` S01-ui: o porteiro troca o CPF para um bloqueado e recebe "Acesso negado", sem gravar nada. `tela_edicao.py:122-128` chama `checar_bloqueio_correcao`, que também barra quem reabre a visita. **Mas** `Banco.editar` e `Banco.inserir` não conferem o bloqueio: `poc` S01-db, `editar(..., autor="paulo")` para CPF e placa bloqueados foi **aceito**. | Defesa em profundidade, que pode ficar para depois: em `Banco.editar`/`_inserir`, `SELECT 1 FROM bloqueios WHERE ativo=1 AND ((tipo='cpf' AND valor=?) OR (tipo='placa' AND valor=?))` e recusar com o mesmo critério de `checar_bloqueio_correcao`. O "Desfazer saída" (10 s) também reabre uma visita sem conferir bloqueio, com risco desprezível. |
| S02 Banco sem proteção ao lado do programa | **Aberto** | Alta (implantação) / Média (trabalho) | `portaria_universidade.py:53-55`: banco, `backups/` e log continuam em `pasta_do_programa()`. O README não diz nada sobre ACL, BitLocker ou conta do Windows. | Mínimo: uma seção "Implantação segura" no README (pasta com acesso só da conta da portaria e do admin, BitLocker, porteiro sem admin do Windows, backups em outra unidade). Mudar o caminho para `%PROGRAMDATA%` pode ficar para depois. |
| S03 Sem backup | **Resolvido** (com ressalvas, ver N05) | — | `backup.backup_diario` com `quick_check`, cópia `.tmp` mais `os.replace` e rotação de 30 (`poc` BK2: 40 dias geraram 30 arquivos). | Ver N05. |
| **S04** Permissões só na tela | **Parcial** | Média | Com autor, o banco recusa: `excluir`, `bloquear`, `definir_senha` de outro usuário, `criar_usuario` e `registros_do_periodo` como porteiro foram todos **RECUSADOS** (`poc` S04a/c). Sem autor, tudo passa sem checagem e sem histórico: `excluir(autor=None)` apagou e gravou 0 eventos (S04b). Esse caminho é **alcançável pela tela** (N01). | Ver N01: autor obrigatório nas operações sensíveis. |
| **S05** Sessão sem expiração | **Resolvido**, com o furo N01 | — | `poc_ui` S05: com 11 min sem uso, a sessão é encerrada, o Corrigir aberto é fechado e o histórico registra "Sessão encerrada por inatividade". | Ver N01. |
| **S06** Tentativas só em memória | **Resolvido** (efeito colateral N04) | — | `poc` S06a: 5 erros, `Banco` reaberto ("fechar e abrir o programa") e a senha certa ainda é recusada com "Aguarde 29 s". A espera dobra até 15 min, por login. `ControleTentativas` (`usuarios.py:286`) ficou como código morto, usado só nos testes. | Remover `ControleTentativas` ou marcar como legado. |
| **S07** Política de senha | **Parcial** | Baixa | Feito: mínimo de 8, lista de senhas comuns, senha = login recusada no cadastro e "Trocar minha senha" com a senha atual (`poc` SENHA1/2 recusados). Falta: (a) troca **obrigatória** no 1º acesso (o diálogo só diz "peça para ele trocar"), então o admin continua conhecendo a senha do porteiro; (b) **Redefinir senha** chama `validar_senha(senha, confirmacao)` **sem o login** (`tela_usuarios.py:172`) e aceita senha = login (SENHA5); (c) A→B→A é aceito (SENHA3), o que é aceitável. | (b) passar `alvo["login"]` (P). (a) coluna `trocar_senha` e pedir a troca ao entrar (M, pode ficar para depois). |
| **S08** LGPD: histórico e retenção | **Parcial** | Média | Feito: o CPF é mascarado em todo detalhe do histórico (`_evento` → `mascarar_cpfs_no_texto`; S08a sem nenhum CPF completo). Falta: o **celular completo** continua no histórico da correção (S08b: `Celular: (31) 98765-4321 → (31) 99999-0000`); excluir a visita **não apaga a pessoa** (S08c); não há retenção, anonimização nem aviso de privacidade. | Para depois: "Anonimizar pessoa" e retenção. Antes do `main`, só o aviso de privacidade no README (P). Opcional: mascarar o celular em `descrever_alteracoes` (P). |
| **S09** Porteiro vê CPF e celular completos | **Parcial** | Média | Tabelas do Movimento, Pessoas e Bloqueios mascaradas (`app.exibir_cpf`). **Vazamentos restantes:** N02 (formulários) e N06 (máscara mais busca). A busca do porteiro continua indo ao histórico inteiro. | Ver N02 e N06. |
| S10 Histórico sem integridade | **Aberto** | Média | `poc` S10: `DELETE FROM auditoria WHERE acao='Exclusão de registro'` apagou sem rastro. `_evento` continua ignorando a gravação quando `autor` vem vazio. | Mínimo (P): triggers `BEFORE UPDATE/DELETE ON auditoria BEGIN SELECT RAISE(ABORT,'histórico é somente leitura'); END` na migração v7. Evitam apagar por engano ou por código (quem tem o arquivo ainda pode remover o trigger). A corrente de hash fica para depois. |
| **S11** Senha gravada no "Login recusado" | **Resolvido** | — | `poc` S11: `entrar(b, "MinhaSenha#99", …)` grava `(login inexistente) / Login recusado`. | — |
| **S12** Erro técnico do SQLite na tela | **Resolvido** | — | `poc` S12: login duplicado mostra "Já existe um usuário com esse login.". `mensagem_amigavel` cobre locked, corrupt, readonly e disk. O detalhe vai para o log. | — |
| S13 Sem limite de tamanho / homóglifos | Aberto | Baixa | `validar_campos` não limita o tamanho do nome; o motivo do bloqueio não tem máximo. | Para depois: `len(nome) <= 100`, `motivo <= 200`. |
| S14 Migração JSON sem evento/validação | Aberto | Baixa | `importar_json` sem `validar_campos` nem evento no histórico; o `.migrado` continua ao lado do programa. | Para depois. |
| **S15** PBKDF2 200k | **Resolvido** | — | `poc` S15: um hash de 200k vira **600000** após o login (0,24 s). | — |
| S16 `foreign_keys` desligado | **Resolvido** (não estava na lista) | — | `dados.py:429` `PRAGMA foreign_keys = ON` em toda conexão; a v6 religa órfãos. | — |
| S17 Entrada retroativa sem limite | Aberto | Baixa | `validar` não tem limite no passado. | Para depois. |
| S18 Alteração de pessoa sem antes/depois | Aberto | Baixa | `atualizar_pessoa` grava só "nome (pessoa #id)" e não chama `_exigir` (nem confere "ativo"). | Para depois. |
| S19 "Primeiro acesso" | **Aberto e agravado no banco** (N03) | Baixa | `poc` S19: `criar_usuario(..., "admin", hash)` **sem autor**, com usuários já existentes, criou um **novo admin** (`intruso`). | Ver N03. |
| S20 Perfil lido só no login | **Parcial** | Baixa | Operações com `_exigir` releem perfil e "ativo" (S20b: porteiro desativado recusado no `editar`). `inserir`, `registrar_saidas`, `desfazer_saidas` e `atualizar_pessoa` não conferem nada: porteiro **desativado** com a sessão aberta ainda registra entrada (S20). | Chamar `_exigir(con, autor, so_admin=False)` nessas quatro (P). |

### 2.2 Problemas novos trazidos pela reforma

| Item | Status | Sev. | Evidência | Correção sugerida |
|---|---|---|---|---|
| **N01** Ação sensível concluída **depois** da sessão expirar roda com `autor=None` (sem checagem, sem histórico) | **Novo** | **Média-Alta** (corrigir antes do `main`) | 1) `poc_timer_nativo.py`, Windows real: o `after()` disparou em 1,5 s **com o `askyesno` e o "Salvar como" abertos**, ou seja, a inatividade encerra a sessão por baixo da caixa nativa, que `sair()` não consegue fechar (não é `Toplevel`). 2) `poc_ui` NOVO-SESSAO-1: "Excluir" confirmado depois da expiração apagou o registro e o histórico só mostra "Sessão encerrada por inatividade". 3) NOVO-SESSAO-2: o "Salvar como" do CSV voltou depois da expiração e gravou o arquivo com `714.287.938-60` completo, sem o evento "Exportação de registros". Também afetados: "Desativar usuário" (`definir_ativo`) e a saída rápida múltipla (sem histórico). "Bloquear" e "Remover bloqueio" falham sozinhos (NOT NULL em `criado_por`/`removido_por`). | Duas linhas de defesa (P): **(a)** no `Banco`, `autor` **obrigatório** nas operações sensíveis (`excluir`, `editar`, `registros_do_periodo`, `definir_ativo`, `definir_senha`, `bloquear`, `desbloquear`): `_exigir` lança `ErroDados("Sessão encerrada. Entre de novo.")` se `autor is None`. O único caso sem autor é `criar_usuario` com a tabela vazia (N03). Ajustar os testes que chamam sem autor. **(b)** Na tela, em `AppPortaria.tentar`/`gravar`: se `self.usuario is None`, não executar e avisar "Sua sessão foi encerrada". |
| **N02** CPF completo para o porteiro nos formulários; celular completo na ficha | **Novo** (promessa da reforma incompleta) | Média | `poc_ui` MASC-3: Pessoas → "Registrar entrada" põe `71428793860` no campo CPF da Entrada, e a lista de Pessoas cobre **todo mundo que já passou**. MASC-1: o campo CPF do Corrigir mostra o CPF completo (só visitas de 24 h para o porteiro). MASC-2: celular `31987654321` na ficha de Pessoas. O celular também está nos `values` ocultos das tabelas. | Mínimo realista (P): **documentar** no README que o porteiro vê o CPF completo ao iniciar uma entrada pela ficha. Ou então: para o porteiro, `preencher_pessoa` guarda o CPF num atributo interno, mostra o campo mascarado e somente leitura (M). Mascarar o celular na ficha de Pessoas para o porteiro (P). |
| **N03** `criar_usuario(autor=None)` cria **admin** mesmo com usuários existentes | **Novo** (por causa do `_exigir` que aceita `None`) | Baixa-Média | `poc` S19: aceito. Pela tela, é alcançável se a tela de "Primeiro acesso" foi montada com o banco vazio e outra estação criou o admin nesse meio-tempo (banco em rede, `wal=False`). | Em `criar_usuario`: se `autor is None` e `SELECT 1 FROM usuarios` encontrar alguém, então recusar, na mesma transação (P). Resolve também o S19 pelo código. |
| **N04** Travar o admin de propósito (DoS do login) | **Novo** | Baixa-Média | `poc` NOVO-DoS: 8 ciclos de 5 senhas erradas, o contador `bloqueios` nunca diminui, a espera fica em **900 s** e a senha certa é recusada ("Aguarde 895 s"). Quem estiver no PC mantém o admin fora indefinidamente, com 5 cliques a cada 15 min. Não há saída: nenhuma tela zera `tentativas_login`. Um segundo admin também não consegue liberar. | Para depois (P): (a) zerar `bloqueios` depois de 24 h sem falhas; (b) na página Usuários, "Liberar login" para outro admin (`gravar_tentativas_login(login, 0, 0, None)` mais um evento); (c) documentar o desbloqueio manual. O teto de 15 min já limita o estrago. |
| **N05** Backups: dados pessoais completos, sem política | **Novo** | Média (LGPD) | `poc` BK1: `backups/portaria-AAAA-MM-DD.db` ao lado do banco, em texto puro, com **hashes de senha** e com a pessoa que já tinha sido "excluída". Até 30 diários, mais **backups de antes da migração (`portaria-antes-v6-...db`), que nunca entram na rotação**, mais `fazer_backup` manual (sem botão hoje). Ficam no **mesmo disco**: não protegem contra a falha do HD, que era o cenário do S03. Não há instrução de restauração. | (P) README: os backups têm os mesmos dados do banco, recomendar copiar para outra unidade com acesso restrito, como restaurar (fechar o programa e copiar `portaria-AAAA-MM-DD.db` para `portaria.db`), e que uma exclusão por LGPD só some dos backups depois de 30 dias. (P) Incluir os `portaria-antes-*` numa limpeza (ex.: apagar após 90 dias). |
| **N06** Máscara mais busca reconstroem o CPF | **Novo** | Baixa | `poc` MASC: com `***.287.938-**`, os 2 dígitos verificadores são calculados, então sobram **1000 candidatos**. A busca do Movimento do porteiro (`buscar_registros`, substring de dígitos no histórico inteiro) confirmou o único válido, `71428793860`. Na prática são até 1000 buscas manuais, o que torna isso pouco provável. | Para depois: para o porteiro, aceitar busca por CPF só com 11 dígitos exatos (P). A máscara do gov.br (`***.xxx.xxx-**`) é aceitável. |
| N07 CSV com CPF e celular completos | **Novo**, aceitável | Baixa | Só o admin (`poc` CSV1 recusado para o porteiro), fica no histórico (CSV2) e o diálogo avisa "O arquivo leva CPF e celular completos". O destino é livre (Desktop, pendrive), sem prazo. `_celula` não cobre `\t`/`\r` iniciais (CSV4), mas os dados validados não começam assim. O furo real é o N01 (exportar sem autor). | Para depois: opção "CPF mascarado" no export (padrão marcado). Incluir `\t` e `\r` em `_celula` (P). |
| N08 Log de erros | **Verificado, sem problema** | — | `poc` LOG: nenhum CPF, celular ou senha no `portaria.log`. `_erro` grava só a mensagem do SQLite (sem valores); `_erro_inesperado` grava o traceback (sem variáveis locais). Rotação de 3 × 1 MB. | Manter. |
| N09 Troca de senha sem limite de tentativas da senha atual | **Novo** | Baixa | `poc` SENHA4: 30 chutes da senha atual no "Trocar minha senha" sem nenhum bloqueio (`falhas=0`). Na prática só serve para descobrir a senha de quem deixou a sessão aberta e reaproveitá-la depois. | Contar a falha no mesmo `tentativas_login` do usuário e encerrar a sessão no limite (P). Pode ficar para depois. |
| N10 Migração v6 fecha visitas duplicadas sozinha | **Verificado, risco baixo** | Baixa | Roda uma vez (v5 → v6), dentro de transação, com backup antes, evento "Saída automática (atualização)" por `(sistema)` (login impossível pela `REGEX_LOGIN`) e aviso ao admin. Nada é apagado. Para abusar, seria preciso gravar um banco v5 adulterado no lugar do atual, o que já exige acesso ao arquivo (S02). | Nenhuma. |

## 3. O que corrigir antes do `main` (mínimo razoável)

1. **N01 + N03** (P, cerca de 1 h): `autor` obrigatório nas operações sensíveis do `Banco`;
   `criar_usuario` sem autor só com a tabela vazia; `AppPortaria.tentar` recusa quando
   `self.usuario is None`. Criar dois testes: "excluir depois de sair()" e "exportar depois
   de sair()".
2. **N02** (P): no mínimo, deixar de afirmar "CPF mascarado para o porteiro" sem ressalva
   e documentar a exceção (formulário de entrada e Corrigir). Se der tempo, mascarar o
   celular na ficha de Pessoas para o porteiro.
3. **README, "Segurança e LGPD"** (P): onde ficam banco, backups, log e CSV; quem deve ter
   acesso à pasta (ACL e conta do Windows), BitLocker; como restaurar um backup; prazo
   dos backups; finalidade e base legal (segurança do campus, legítimo interesse). Isso
   cobre o S02 e o N05 no nível de um trabalho de faculdade.

## 4. Pode ficar para depois

- S10: triggers de somente leitura na auditoria (P) e depois a corrente de hash.
- S08: "Anonimizar pessoa", retenção configurável e celular mascarado no histórico.
- S07: troca obrigatória no primeiro acesso; passar o login ao `validar_senha` na redefinição.
- N04: liberar login travado (outro admin) e o contador de bloqueios que zera com o tempo.
- S20/S18: `_exigir(..., so_admin=False)` em `inserir`, saídas e `atualizar_pessoa`.
- S01 no banco (defesa em profundidade), S13, S14, S17, N06, N07, N09; remover `ControleTentativas`.
