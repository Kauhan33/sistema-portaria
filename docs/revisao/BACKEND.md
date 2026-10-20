# Revisão de backend e dados — Sistema de Portaria

Revisão de `portaria/dados.py`, `portaria/consultas.py` e de como as telas usam o banco.
Restrições respeitadas: continua SQLite + biblioteca padrão, sem servidor.
Nenhum arquivo do projeto foi alterado além deste relatório.

## 1. Resumo

- **O banco em si aguenta tranquilo**: SQLite com 100 mil visitas (1 ano a 300/dia) ocupa
  32 MB e responde qualquer consulta bem escrita em menos de 1 ms a 50 ms.
- **O gargalo está em como os dados são usados**: a tela carrega *todas* as visitas
  (`listar()`), converte cada data com `strptime` e recalcula o dashboard em Python **depois de
  cada operação e a cada tecla da busca**. O custo cresce em linha reta com o histórico:
  - com 1 ano de uso: **2,7 s de tela travada a cada Cadastrar ou Saída rápida** e
    **1,2 s a cada tecla** na busca. Com 600 operações por dia (300 entradas + 300
    saídas), isso dá ~27 min/dia de tela congelada;
  - com 3 anos de uso: 7,9 s por operação e 3,8 s por tecla. Na prática, inutilizável.
- 85% do tempo de `listar()` é a conversão de data (`de_iso` com `strptime`). Fatiar a string
  é 19x mais rápido. Mostrar só "hoje + quem está dentro" deixa o custo **constante**
  (0,4 ms com 300 mil registros, contra 3,5 s hoje).
- **Integridade**: a regra "uma visita aberta por CPF" só existe em Python, sobre uma cópia
  em memória. Com duas estações no mesmo arquivo, **reproduzi duas visitas abertas para o
  mesmo CPF**. `PRAGMA foreign_keys` está **desligado**. Um banco de versão mais nova é
  **rebaixado para v5 sem aviso**. Uma visita retroativa **sobrescreve** os dados atuais da
  pessoa. Todos esses casos foram reproduzidos.
- **Operação**: não há backup automático nem exportação. As duas coisas cabem em ~30 linhas
  cada, com `con.backup()` e `csv`: o backup leva 185 ms e a exportação 234 ms com 100 mil
  registros.

## 2. Como foi medido

- Ambiente: Windows 11, Python 3.12.10, SQLite 3.49.1, disco local. Mediana de 5 execuções
  (3 nos ciclos completos).
- Bancos gerados com o **esquema real** (`Banco()` cria o v5), em pasta temporária fora do
  projeto. Cenário: 300 entradas/dia, 75% de pessoas recorrentes, ~190 pessoas dentro no
  momento da medição, 2 eventos de auditoria por visita e 40 bloqueios ativos.

| Banco | Registros | Pessoas | Auditoria | Tamanho |
|---|---:|---:|---:|---:|
| ~3 dias | 1.000 | 901 | 1.794 | 0,4 MB |
| ~1 mês | 10.000 | 4.703 | 19.805 | 3,3 MB |
| **~1 ano** | **100.000** | **31.167** | **199.816** | **32,3 MB** |
| ~3 anos | 300.000 | 88.971 | 599.815 | 98,0 MB |

- Tela medida com a `AppPortaria` real (janela Tk oculta e `messagebox` simulado, como em
  `tests/test_interface.py`).
- Os scripts `database_migration_tool.py` e `api_load_tester.py` da skill senior-backend são
  modelos sem análise real: devolvem 0 achados, e o primeiro ainda falha no console cp1252.
  Por isso as medições usaram scripts próprios (gerador, `medir.py`, `medir_tela.py` e
  `prototipos.py`), mantidos fora do projeto.

## 3. Medições

### 3.1 Operações do backend (hoje)

| Operação | 1.000 | 10.000 | 100.000 | 300.000 |
|---|---:|---:|---:|---:|
| `Banco()` (abrir + migrações) | 3,6 ms | 3,3 ms | 3,4 ms | 3,3 ms |
| `listar()` | 11 ms | 119 ms | **1.184 ms** | **3.539 ms** |
| `listar_pessoas()` | 9 ms | 40 ms | **447 ms** | **1.441 ms** |
| `buscar_pessoa(cpf)` | 0,3 ms | 0,4 ms | 0,5 ms | 0,3 ms |
| `listar_bloqueios()` | 0,6 ms | 0,7 ms | 0,7 ms | 0,7 ms |
| `consultas.resumo()` (dashboard) | 6,5 ms | 71 ms | **705 ms** | **2.117 ms** |
| `filtrar('silva')` | 0,2 ms | 1,5 ms | 18 ms | 53 ms |
| `encontrar_dentro(cpf)` | 0,0 ms | 0,1 ms | 2,4 ms | 6,0 ms |
| `validar()` (sobreposição) | 0,0 ms | 0,3 ms | 3,8 ms | 15 ms |
| `buscar(id)` | 11 ms | 124 ms | 1.163 ms | 3.509 ms |
| `eventos_do_registro(id)` | 0,3 ms | 0,3 ms | 0,3 ms | 0,3 ms |
| `listar_eventos(200)` | 1,5 ms | 1,9 ms | 1,5 ms | 1,5 ms |
| `inserir()` isolado | 6,1 ms | 5,9 ms | 5,4 ms | 5,6 ms |
| ciclo de cadastro sem Tk (bloqueios + validar + inserir + listar + resumo) | 25 ms | 199 ms | **1.889 ms** | **5.725 ms** |

### 3.2 Tela real (Tkinter)

| Operação na tela | 1.000 | 10.000 | 100.000 | 300.000 |
|---|---:|---:|---:|---:|
| Abrir a tela principal (login → abas) | 383 ms | 389 ms | **3.271 ms** | **9.735 ms** |
| Clicar **Cadastrar** (fluxo completo) | 33 ms | 269 ms | **2.677 ms** | **7.941 ms** |
| **Saída rápida** por CPF | 32 ms | 267 ms | **2.624 ms** | **7.892 ms** |
| Uma tecla na busca do Cadastro ("s") | 13 ms | 127 ms | **1.246 ms** | **3.760 ms** |
| `atualizar_tabela('')` (roda após cada operação) | 14 ms | 137 ms | 1.380 ms | 4.160 ms |
| `atualizar_dashboard()` | 7 ms | 71 ms | 709 ms | 2.122 ms |
| Abrir a aba Pessoas | 17 ms | 79 ms | 691 ms | 2.128 ms |
| Uma tecla na busca de Pessoas | 11 ms | 48 ms | 480 ms | 1.554 ms |

Limite prático, considerando que acima de ~100 ms já se nota atraso: **~10 mil registros,
ou seja, pouco mais de um mês de uso**.

### 3.3 Alternativas medidas (SQL + índices)

| Operação | 10.000 | 100.000 | 300.000 |
|---|---:|---:|---:|
| Só o `SELECT` de todos (sem converter datas) | 12 ms | 138 ms | 419 ms |
| `de_iso()` atual em todas as linhas (`strptime`) | 100 ms | **994 ms** | 2.970 ms |
| `de_iso` por fatiamento de string | 5 ms | **53 ms** | 162 ms |
| **Hoje + quem está dentro** (UNION ALL com índices, ver §6.1) | — | — | **0,42 ms** |
| Mesmo, com `WHERE entrada >= ? OR saida = ''` (vira SCAN) | 0,9 ms | 10 ms | 31 ms |
| Resumo do dashboard em SQL (`GROUP BY tipo` + 7 dias) | 4,2 ms | **52 ms** | 157 ms |
| `COUNT` de quem está dentro: sem índice → com índice parcial | 0,3 → 0,0 ms | 8,2 → 0,0 ms | 25 → 0,0 ms |
| Busca `LIKE '%silva%'` com `LIMIT 500` | 1,5 ms | **1,6 ms** | 1,7 ms |
| Sobreposição do CPF em SQL (usa índice de cpf) | 0,0 ms | 0,0 ms | 0,0 ms |
| Pessoas: 200 por nome (`LIKE 'ana%'`) + índice `nome COLLATE NOCASE` | 0,6 ms | **2,7 ms** | 1,8 ms |
| Auditoria de um dia: sem índice → com índice em `momento` | 1,0 ms | 12 → 0,7 ms | 37 → 0,7 ms |
| Criar os índices novos + `ANALYZE` (custo único da migração) | 23 ms | 168 ms | 482 ms |
| Commit: journal DELETE (padrão) × WAL + `synchronous=NORMAL` | 3,6 / 0,1 ms | 3,6 / 0,1 ms | 3,3 / 0,1 ms |
| `con.backup()` do arquivo inteiro | 21 ms | 185 ms | 557 ms |
| `VACUUM INTO` (cópia compacta) | — | 92 ms | 276 ms |
| Exportar todos os registros em CSV | — | 234 ms (9 MB) | 702 ms (27 MB) |
| `PRAGMA quick_check` / `integrity_check` | — | 69 / 343 ms | 207 / 1.715 ms |

## 4. Achados

Prioridade: **Alta** = afeta o uso diário ou a integridade dos dados; **Média** = risco real,
mas contornável; **Baixa** = melhoria. Esforço: P (< 1 h), M (meio dia), G (> 1 dia).
As linhas citadas são do código atual da árvore de trabalho.

| ID | Prior. | Arquivo:linha | Problema | Sugestão | Esf. |
|---|---|---|---|---|---|
| B01 | **Alta** | `interface.py:101-108` (`_gravar`, l.105), `interface.py:414`, `interface.py:510`, `tela_edicao.py:156` | Toda operação (cadastrar, saída, desfazer, corrigir, excluir) relê a tabela **inteira** com `listar()`: 1,2 s com 1 ano e 3,5 s com 3 anos, e o tempo só cresce. A tabela principal mostra o histórico todo, que o porteiro não usa. | Novo `listar_periodo(desde)`, que devolve as entradas de hoje (ou do período escolhido) **mais** as visitas ainda abertas, com índice em `entrada` e índice parcial em `saida = ''` (§6.1). Histórico antigo só pela busca, que passa a ser feita no SQL (B04). Custo: 0,4 ms, constante. | M |
| B02 | **Alta** | `dados.py:96-97` (`de_iso`) | `strptime` + `strftime` em cada data responde por 85% do tempo de `listar()` (994 de 1.184 ms com 100 mil). | Converter por fatiamento: `f"{t[8:10]}/{t[5:7]}/{t[:4]} {t[11:16]}"`, 19x mais rápido. Manter `para_iso` com `strptime`, porque ele valida a entrada. | P |
| B03 | **Alta** | `consultas.py:66-103` (`resumo`, `converter_data` na l.81); chamado por `interface.py:438` | O dashboard é recalculado em Python sobre todos os registros (705 ms com 100 mil), e isso acontece **a cada `atualizar_tabela`**, inclusive a cada tecla da busca, mesmo com a aba Dashboard fechada. | (a) Imediato: recalcular só ao abrir a aba Dashboard. (b) Mover para o SQL: `GROUP BY tipo`, `SUM(saida='')`, `julianday` para a permanência e `substr(entrada,1,10)` para os 7 dias. Leva 52 ms com 100 mil. | P (a) / M (b) |
| B04 | **Alta** | `interface.py:646-647` + `423-438`; `consultas.py:27-42` | Cada tecla na busca refaz o Treeview inteiro (~670 ms com 100 mil) e o dashboard: 1,25 s por tecla. | Busca no SQL com `LIKE` e `LIMIT 500` (1,6 ms), mais um *debounce* de ~250 ms com `after()`. Busca vazia mostra o período (B01). | M |
| B05 | **Alta** | `validacao.py:266-282` (sobreposição), usado em `interface.py:171` e `tela_edicao.py:146`, sobre a cópia `self.registros` | A regra "o mesmo CPF não pode estar dentro duas vezes" só existe em Python, sobre uma cópia em memória que pode estar desatualizada. **Reproduzido**: a estação A, com a lista carregada antes, aceitou uma entrada que a estação B já tinha gravado, e o CPF ficou com **2 visitas abertas**. | (1) `CREATE UNIQUE INDEX idx_um_aberto_por_cpf ON registros (cpf) WHERE saida = ''` garante a regra no banco. Testado: dá `IntegrityError`; tratar com mensagem amigável. Ele também acelera "quem está dentro". (2) Checar a sobreposição em SQL (§6.3) dentro da mesma transação do `INSERT`/`UPDATE`, com `BEGIN IMMEDIATE`. | P (1) / M (2) |
| B06 | **Alta** | `dados.py:142` e `dados.py:159` | `PRAGMA user_version = 5` é gravado **sempre**. Um banco criado por uma versão mais nova (ex.: v9) é rebaixado para 5 sem aviso (**reproduzido**), e a versão nova depois roda as migrações de novo sobre dados que já estão no formato novo. | `if versao > VERSAO_ESQUEMA: raise ErroDados("Este banco foi criado por uma versão mais nova do programa. Atualize o programa.")`, antes de tocar no esquema. | P |
| B07 | Média | `dados.py:139-159` (`executescript` nas l.143, 149 e 154; `ALTER TABLE` nas l.146 e 152) | As migrações **não são atômicas**. `executescript()` faz um COMMIT implícito antes de rodar e executa em autocommit, e no modo legado do `sqlite3` o `ALTER TABLE` também fica fora de transação. Por isso o `rollback()` de `_conexao` não desfaz uma migração interrompida no meio. Hoje não houve dano só porque as migrações v3/v4 são idempotentes (`ON CONFLICT DO NOTHING`, `WHERE ... IS NULL`). A próxima que não for idempotente pode deixar o banco pela metade. | Lista ordenada de passos `[(6, sql), (7, sql)…]`; cada passo roda como `BEGIN IMMEDIATE; …; PRAGMA user_version = N; COMMIT;` (§6.2). Fazer **backup antes de migrar** (B17). Testes: banco v5 → v6 e falha simulada no meio. | M |
| B08 | Média | `dados.py:165` (`connect` sem PRAGMAs); FK declarada em `dados.py:38` | `PRAGMA foreign_keys = 0`: o padrão do SQLite, que vale por conexão. O `REFERENCES pessoas (id)` não tem efeito. **Reproduzido**: o banco aceitou `pessoa_id = 99999`. | Em `_conexao`: `con.execute("PRAGMA foreign_keys = ON")`. Antes de ligar, rodar `PRAGMA foreign_key_check` na migração; nos bancos gerados deu 0 violações em 21 ms. | P |
| B09 | Média | `dados.py:216-223` (`_inserir`) | O *upsert* da pessoa sobrescreve nome, celular e tipo com os dados de **qualquer** visita inserida, mesmo de uma retroativa. **Reproduzido**: depois de lançar uma visita da semana passada, a pessoa voltou a ter o nome, o celular e o tipo antigos, embora a última visita seja de hoje. `editar()` (`dados.py:309-317`) já segue a regra certa ("só a visita mais recente atualiza a pessoa"); `_inserir` não. | Criar a pessoa sempre com `ON CONFLICT DO NOTHING` e só atualizar os dados se a visita inserida for a mais recente (mesma consulta de `editar`, l.309-311). Acrescentar o teste "visita retroativa não mexe na pessoa" para `inserir`. | P |
| B10 | Média | `dados.py:390-395`, `dados.py:130-135`; `tela_pessoas.py:44` e `122-127` | `listar_pessoas()` agrega **todas** as pessoas (31 mil com 1 ano) e roda a cada tecla na busca da aba Pessoas: 480 ms por tecla com 100 mil, 1,55 s com 300 mil. Abrir a aba leva 0,7 s (100 mil) e 2,1 s (300 mil). | Busca no SQL (`nome LIKE ? OR cpf LIKE ?`) com `ORDER BY nome COLLATE NOCASE LIMIT 200`, índice `pessoas (nome COLLATE NOCASE)` e debounce: 2,7 ms. "No campus agora" sai do `COUNT` no índice parcial. | M |
| B11 | Média | `dados.py:162-178` (`_conexao`); `.gitignore:9-10` | Journal DELETE + `synchronous=FULL`: cada commit faz fsync (3,6 ms). Uma leitura longa (`listar()` de 1 a 3 s) segura o lock de leitura e pode atrasar ou dar "database is locked" na escrita de outra estação; o timeout padrão é de 5 s. | `PRAGMA journal_mode = WAL` (persistente, uma vez na abertura), `synchronous = NORMAL` (commit em 0,1 ms) e `busy_timeout = 10000`. **Só com o banco em disco local**, porque o WAL não funciona em pasta de rede. Acrescentar `*.db-wal`, `*.db-shm` e `backups/` ao `.gitignore`: são dados pessoais. | P |
| B12 | Média | Arquitetura (cache `self.registros` em `interface.py:63`, `tela_bloqueios.py:161`) | Duas portarias: com SQLite numa pasta compartilhada (SMB), o lock não é confiável. Além disso, cada estação trabalha com uma cópia em memória que não vê o que a outra gravou. Por exemplo, a "Saída rápida" (`encontrar_dentro` sobre a cópia) não encontra quem entrou pela outra guarita. | Recomendação oficial: **um arquivo por computador**. Se for preciso compartilhar: journal DELETE (sem WAL), B05 para garantir a integridade e recarregar "hoje + dentro" (0,4 ms) antes de validar e a cada ~30 s com `after()`. A saída rápida passa a consultar o banco (`WHERE cpf = ? AND saida = ''`, no índice). | M |
| B13 | **Alta** (operação) | `portaria_universidade.py:37` (banco ao lado do programa); não há backup em lugar nenhum | Um ano de registros de acesso fica num único arquivo, sem cópia. Uma pane de disco, uma exclusão acidental ou um arquivo corrompido apaga tudo. | Backup diário automático na abertura com `con.backup()` (185 ms com 100 mil), guardando os últimos 30 em `backups/`, mais `PRAGMA quick_check` na abertura (69 ms) e backup antes de cada migração (§6.4). Orientar a cópia periódica para outro disco ou pendrive. | P |
| B14 | Média | Ausente | Não há exportação (CSV) para relatório, auditoria ou entrega a terceiros. | `Banco.exportar_csv(caminho, desde, ate)` com `csv.writer(delimiter=';')` e `encoding='utf-8-sig'`, para abrir certo no Excel em português, mais um evento na auditoria ("Exportação", período e quantidade), porque o arquivo leva CPF e celular (LGPD). Exportar só para administrador. Tempo: 234 ms com 100 mil (§6.5). | P |
| B15 | Baixa | `dados.py:276-278` (`buscar`) | `buscar(id)` chama `listar()` inteiro para achar um único registro: 1,16 s com 100 mil. Hoje só os testes usam, mas é uma armadilha. | `SELECT … WHERE id = ?`. | P |
| B16 | Baixa | `dados.py:28-40`, `43-50` | Faltam CHECKs. **Reproduzido**: o banco aceitou `tipo = 'Qualquer coisa'` e `entrada = 'lixo'`. `celular` e `placa` não têm formato. | Na próxima reconstrução da tabela (padrão "criar nova, copiar, renomear", numa migração), acrescentar `CHECK (entrada GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]')` e o mesmo para `saida` (ou `''`), `length(celular) = 11` e `placa = '' OR length(placa) = 7`. Para `tipo`, avaliar: um CHECK com a lista exige migração para criar um tipo novo. | M |
| B17 | Baixa | `dados.py:261-274` (`excluir`) | Se a visita apagada era a mais recente, a pessoa continua com os dados dela. A pessoa sem nenhuma visita continua cadastrada, de propósito (`test_excluir_visita_mantem_a_pessoa`). | Depois de excluir, se a visita era a mais recente, recompor a pessoa a partir da visita mais recente que sobrou. Documentar que a pessoa sem visitas fica. | P |
| B18 | Baixa | `dados.py:61-68` | A `auditoria` não tem índice em `momento`: uma consulta por período faz SCAN (12 ms com 200 mil eventos). `listar_eventos` usa `ORDER BY id` e já é rápido. | `CREATE INDEX idx_auditoria_momento ON auditoria (momento)` quando houver filtro por período na aba Usuários (0,7 ms). | P |
| B19 | Baixa | `dados.py:102-111` | `MIGRAR_PESSOAS` considera "mais recente" pelo `MAX(id)`, enquanto `editar()` usa `entrada`. Só afeta bancos antigos com lançamentos retroativos. | Usar `ORDER BY entrada DESC, id DESC`, como em `editar`. | P |
| B20 | Baixa | Política | Os dados crescem ~32 MB/ano e ficam para sempre. O espaço não é problema; a **retenção de CPF e celular** é (LGPD). | O responsável define um prazo, por exemplo 2 anos. Depois disso, anonimizar (`cpf`/`celular` → `''`, mantendo a contagem) ou exportar e remover. Deixar como opção do administrador. | M |
| B21 | Baixa | `interface.py:397-398` (repassar ao front) | O timer `after()` do aviso não é cancelado ao fechar a janela. Nas medições apareceu `invalid command name "…_esconder_aviso"` no stderr. | Cancelar `_timer_aviso` em `sair()` e no fechamento da janela. | P |

Pontos verificados que **estão bem**:

- `buscar_pessoa` (0,3 ms) usa o `UNIQUE` de `cpf`.
- `listar_bloqueios` (0,7 ms) **não** roda a cada tecla: `_ao_digitar_cpf` e `_ao_digitar_placa`
  retornam antes de chamá-lo enquanto o CPF não tem 11 dígitos ou a placa não é válida.
- `eventos_do_registro` usa `idx_auditoria_registro`.
- `inserir` grava a visita, a pessoa e a auditoria numa única transação.
- `desfazer_saidas` já checa a regra no SQL.
- O índice único parcial de bloqueios está correto.
- A conexão nova por operação custa pouco (~0,3 ms). Pode continuar assim, desde que os
  PRAGMAs (B08, B11) sejam aplicados dentro de `_conexao`.

## 5. As 5 mudanças que eu faria primeiro

| # | Mudança | Achados | Efeito esperado (100 mil registros = 1 ano) |
|---|---|---|---|
| 1 | **Tabela principal = "hoje + quem está dentro"**: `listar_periodo(desde)` com índices `registros(entrada)` e parcial `registros(cpf) WHERE saida = ''`, mais `de_iso` por fatiamento. | B01, B02, B15 | Recarregar após cada operação: **1.184 ms → < 1 ms**, constante com o tempo. Cadastrar/Saída rápida: 2,7 s → dezenas de ms. Abrir a tela: 3,3 s → ~0,4 s (o custo do Tk). Com 3 anos de dados, o tempo é o mesmo. |
| 2 | **Regras de integridade no banco**: índice **único** parcial "uma visita aberta por CPF", sobreposição checada em SQL na transação, `foreign_keys = ON`, recusa de banco de versão mais nova e `_inserir` que não sobrescreve a pessoa em visita retroativa. | B05, B06, B08, B09 | Fecha a corrida das duas estações e o rebaixamento silencioso do esquema. A pessoa fica sempre com os dados da visita mais recente. Bônus: "quem está dentro" sai de 8 ms para 0 ms. |
| 3 | **Dashboard e buscas no SQL**: dashboard só ao abrir a aba e calculado em SQL; buscas do Cadastro e de Pessoas com `LIKE … LIMIT` e debounce de 250 ms. | B03, B04, B10 | Tecla na busca: **1.246 ms → ~2 ms**. Tecla em Pessoas: 480 ms → ~3 ms. Dashboard: 705 ms → 52 ms, e só quando alguém olha. |
| 4 | **Backup diário automático + `quick_check` + exportação CSV** (só admin, com auditoria). | B13, B14 | Perda máxima de 1 dia de dados em caso de corrupção ou exclusão. Custo de ~250 ms uma vez por dia. O relatório CSV sai em 0,2 s. |
| 5 | **Migrações por passos atômicos + PRAGMAs de abertura**: `MIGRACOES = [(6, …)]` com `BEGIN IMMEDIATE … user_version … COMMIT`, backup antes de migrar, WAL + `synchronous=NORMAL` + `busy_timeout` (disco local) e `.gitignore` com `*.db-wal`/`*.db-shm`/`backups/`. | B07, B11, B18 | Uma migração interrompida não deixa o banco pela metade. Commit de 3,6 ms → 0,1 ms. Uma leitura não bloqueia mais a escrita. A v6 (índices novos) roda em ~170 ms uma única vez. |

## 6. Esboços (para orientar a implementação)

### 6.1 Hoje + quem está dentro

```sql
-- v6
CREATE INDEX IF NOT EXISTS idx_registros_entrada ON registros (entrada);
CREATE UNIQUE INDEX IF NOT EXISTS idx_um_aberto_por_cpf ON registros (cpf) WHERE saida = '';
```

```python
def listar_periodo(self, desde_iso):
    """Visitas com entrada a partir de `desde_iso` + todas as ainda abertas."""
    cols = "id, nome, cpf, celular, placa, tipo, entrada, saida"
    sql = (f"SELECT * FROM (SELECT {cols} FROM registros WHERE entrada >= ? "
           f"UNION ALL SELECT {cols} FROM registros "
           f"WHERE saida = '' AND +entrada < ?) ORDER BY entrada DESC, id DESC")
    ...
```

Cuidados medidos:

- `WHERE entrada >= ? OR saida = ''` vira SCAN (31 ms com 300 mil). O `UNION ALL` usa os
  dois índices (0,42 ms).
- `ORDER BY id` no lugar de `ORDER BY entrada` faz o planejador varrer pela chave primária
  (25 ms).
- O `+` em `+entrada` impede o uso do índice de `entrada` na parte "abertas", que seria pior.
  Sem ele, a consulta levou 38 ms.

Antes de criar o índice único, contar os CPFs com duas ou mais visitas abertas
(`GROUP BY cpf HAVING COUNT(*) > 1`). Se houver, avisar o administrador em vez de falhar
calado. Nos bancos gerados não houve nenhum.

### 6.2 Migrações e abertura

```python
MIGRACOES = [
    (6, """CREATE INDEX IF NOT EXISTS idx_registros_entrada ON registros (entrada);
           CREATE UNIQUE INDEX IF NOT EXISTS idx_um_aberto_por_cpf ON registros (cpf) WHERE saida = '';
           CREATE INDEX IF NOT EXISTS idx_pessoas_nome ON pessoas (nome COLLATE NOCASE);
           CREATE INDEX IF NOT EXISTS idx_auditoria_momento ON auditoria (momento);"""),
]

def _migrar(self, con):
    versao = con.execute("PRAGMA user_version").fetchone()[0]
    if versao > VERSAO_ESQUEMA:
        raise ErroDados("Este banco foi criado por uma versão mais nova do programa.")
    if 0 < versao < VERSAO_ESQUEMA:
        self.fazer_backup(motivo=f"antes-v{VERSAO_ESQUEMA}")
    for alvo, sql in MIGRACOES:
        if versao < alvo:
            # tudo ou nada: se falhar, o _conexao faz rollback e user_version não muda
            con.executescript(f"BEGIN IMMEDIATE;\n{sql}\nPRAGMA user_version = {alvo};\nCOMMIT;")

@contextmanager
def _conexao(self):
    con = sqlite3.connect(self.caminho, timeout=10)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 10000")
    ...
# uma vez no __init__ (disco local): PRAGMA journal_mode = WAL; PRAGMA synchronous = NORMAL
```

As migrações v1→v5 atuais podem continuar como estão: são idempotentes. O novo padrão vale
da v6 em diante.

### 6.3 Sobreposição no SQL (mesma regra de `_sobrepoe`)

```sql
SELECT entrada, saida FROM registros
WHERE cpf = :cpf AND id <> :id_editado
  AND (saida = '' OR saida > :entrada)
  AND (:saida = '' OR entrada < :saida)
LIMIT 1;
```

Usa `idx_registros_cpf` e leva 0,0 ms. Deve rodar dentro da transação de `inserir`/`editar`
(`BEGIN IMMEDIATE`): assim nenhuma outra estação grava entre a checagem e o `INSERT`.

### 6.4 Backup diário

```python
def backup_diario(self, pasta, manter=30):
    os.makedirs(pasta, exist_ok=True)
    destino = os.path.join(pasta, f"portaria-{date.today():%Y-%m-%d}.db")
    if os.path.exists(destino):
        return
    tmp = destino + ".tmp"
    with closing(sqlite3.connect(self.caminho)) as src, closing(sqlite3.connect(tmp)) as dst:
        src.backup(dst)               # cópia consistente mesmo com o banco em uso
    os.replace(tmp, destino)          # nunca deixa backup pela metade com nome final
    for velho in sorted(glob.glob(os.path.join(pasta, "portaria-*.db")))[:-manter]:
        os.remove(velho)
```

Na abertura, `PRAGMA quick_check`. Se não vier `ok`, avisar e indicar o último backup.

### 6.5 Exportação CSV

```python
def exportar_csv(self, caminho, desde_iso, ate_iso, autor):
    with self._conexao() as con, open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Nome", "CPF", "Celular", "Placa", "Tipo", "Entrada", "Saída"])
        n = 0
        for nome, cpf, cel, placa, tipo, ent, sai in con.execute(
                "SELECT nome, cpf, celular, placa, tipo, entrada, saida FROM registros "
                "WHERE entrada >= ? AND entrada < ? ORDER BY entrada", (desde_iso, ate_iso)):
            w.writerow([nome, formatar_cpf(cpf), formatar_celular(cel), placa, tipo,
                        de_iso(ent), de_iso(sai)])
            n += 1
        self._evento(con, autor, "Exportação CSV", f"{n} registros de {desde_iso} a {ate_iso}")
    return n
```

## 7. Testes a acrescentar (em `tests/test_dados.py`)

- Banco com `user_version` maior que `VERSAO_ESQUEMA` → `ErroDados`, e o arquivo continua
  intacto.
- Migração v5 → v6 cria os índices. Banco com duas visitas abertas do mesmo CPF → aviso, não
  quebra.
- Segunda visita aberta do mesmo CPF inserida direto pelo `Banco` → `ErroDados`, cobrindo o
  caso das duas estações.
- `inserir` de visita retroativa não altera nome, celular e tipo da pessoa.
- `foreign_keys` ligado: `pessoa_id` inexistente é recusado.
- `listar_periodo`: devolve as visitas de hoje e as abertas de ontem, e não as fechadas de
  ontem.
- `backup_diario` cria um arquivo que abre e tem as mesmas contagens; com `manter=2`, apaga os
  mais antigos.
- `exportar_csv` gera o cabeçalho, o BOM e as datas no formato da tela, e grava o evento.
