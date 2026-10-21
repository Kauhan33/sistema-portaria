> Cópia do relatório do teste de QA 2, feito na versão 4ccbd07 (antes do
> modo noturno). Os scripts e prints citados ficaram fora do repositório; a
> situação de cada achado está em [CORRECOES.md](CORRECOES.md). Todos os
> dados são fictícios.

# Relatório QA 2: casos difíceis

Sistema de Portaria, cópia congelada no commit `4ccbd07` (esquema v8, 508 testes passando).
Não alterei nada no repositório nem no banco real. O banco do aluno foi **copiado** só para o teste de migração e, deste relatório, saem apenas contagens e configurações, sem nenhum dado pessoal. Todos os nomes, CPFs e placas daqui são fictícios.

Scripts que reproduzem cada achado: `qa2\scripts\` (rodar de dentro dessa pasta com `python <script>.py`; eles criam bancos em `qa2\tmp\`).

| Script | O que cobre |
|---|---|
| `t1_tempo.py` | calendário, evento, sábado, tolerância, meia-noite, retroativo, datas inválidas |
| `t2_autorizacao.py` | limite de 24 h e autorização direto no banco, desfazer, importação do JSON |
| `t3_veiculos.py` | carona, placa trocada, dois carros, excluir com carro, placa bloqueada, Encerrar o dia |
| `t4_concorrencia.py`, `t4b_carga.py` | linha desatualizada, corrida entre estações, carga com 3 processos |
| `t5_migrar.py`, `t5_mk_antigo.py`, `t5c_downgrade.py` | migração do banco do aluno (cópia), de v5/v6/v7 para v8, código antigo abrindo o v8 |
| `t6_gui.py`, `t9_gui2.py` | tela: registro do ano 9999, hora "9:5", ano 0001, busca por tecla, ficha, relógio, meia-noite |
| `t7_seguranca.py` | N04 (travar o admin), CPF mascarado reconstruído pela busca |
| `t8_gerar.py`, `t8_medir.py` | desempenho com 100 mil visitas, 20 mil pessoas, 2 mil estadias e 200 mil eventos |
| `t10_encerrar_corrida.py` | Encerrar o dia em paralelo com outra estação; log sem dados pessoais |

## Contagem

| Gravidade | Confirmados | Suspeitas |
|---|---|---|
| Alta | 2 | 0 |
| Média | 6 | 0 |
| Baixa | 11 | 2 |
| Melhoria | 6 | 0 |

---

## Confirmados

### A1. A correção feita com a linha desatualizada apaga a saída que outra estação registrou (perda de atualização) · **Alta**
- **Passos** (`t4_concorrencia.py`, parte 1):
  1. A estação 1 abre "Corrigir" numa visita aberta (com carro).
  2. A estação 2 registra a saída de carro.
  3. A estação 1 corrige só o nome e salva.
- **O que acontece:** a visita volta a ficar **sem saída** (reaberta). O carro continua fora do estacionamento e o histórico só mostra "Registro corrigido — Nome: ...". Nada indica que a saída foi apagada, e o `checar_bloqueio_correcao` também não é aplicado, porque o `original` já não tinha saída.
- **O que deveria:** recusar com "o registro mudou em outra estação, reabra a correção" ou, no mínimo, mesclar só os campos alterados.
- **Onde:** `portaria/dados.py:1082-1116` (`editar` grava todos os campos do formulário, inclusive `saida`) e `portaria/tela_edicao.py:139-178` (manda `novo` montado a partir do `original` lido ao abrir a janela).
- **Correção:** `editar` recebe o `original` e faz `UPDATE ... WHERE id=? AND entrada=? AND saida=? AND placa=?` (ou compara antes de gravar). Com `rowcount` 0, levanta `ErroDados("Este registro foi alterado em outra estação...")`.

### A2. Visitante, entregador e prestador (janela fixa) entram com o campus fechado em dia de evento, sem pedir autorização · **Alta**
- **Passos** (`t1_tempo.py`, "Evento num domingo"): cadastrar um evento no domingo 25/10, das 18:00 às 23:00. Visitante às 08:00 ou às 10:00, entregador às 07:00 e prestador às 07:30 são **aceitos** (`entrada_permitida = True`), e a visita fica "No campus". O mesmo vale num dia útil com evento noturno (o evento substitui o funcionamento): visitante às 09:00 é aceito, enquanto o aluno às 09:00 é recusado.
- **O que deveria:** de acordo com a RN16/RN17, a janela fixa vale "só em dia em que o campus abre" e dentro do expediente. Com o campus fechado até as 18:00, a entrada às 08:00 é uma exceção.
- **Onde:** `portaria/horarios.py:197-200`. O fim é limitado por `min(fim, aberto.fecha)`, mas o início não é limitado pela abertura.
- **Correção:** `return max(inicio, aberto.abre), min(fim, aberto.fecha)` na janela fixa. Se ficar vazia (início ≥ fim), não há janela.

### M1. Pessoa com dois carros: a saída "de carro" fecha o carro errado · **Média**
- **Passos** (`t3_veiculos.py`, "pessoa com DOIS carros"): a pessoa entra com GHI1J23, sai a pé, volta com KLM4N56 e sai "com o veículo". Resultado: **GHI1J23 é fechado** e **KLM4N56 continua** no estacionamento. A saída rápida pela placa KLM4N56 com a resposta "saiu junto" também fecha a estadia mais antiga (GHI), porque a escolha é feita pelo CPF.
- **O que deveria:** fechar a estadia do carro com que a pessoa saiu: a da placa digitada ou, se houver mais de uma, perguntar qual.
- **Onde:** `portaria/dados.py:1251-1260` (`_fechar_estadia_do_responsavel` escolhe por CPF, `ORDER BY e.entrada LIMIT 1`). Em `portaria/tela_cadastro.py:1152`, `por_cpf = {e["cpf"]: e ...}` guarda só um carro por CPF, então a tela pergunta só sobre um deles.
- **Correção:** passar o id da estadia em `com_veiculo` (`{id_visita: id_estadia}`). Na tela, agrupar as estadias por CPF numa lista e perguntar sobre cada carro.

### M2. O CPF mascarado (RN14) pode ser reconstruído pela busca · **Média**
- **Passos** (`t7_seguranca.py`): o porteiro vê `***.982.247-**`. Ele busca "d982247" para d = 0..9 até a pessoa aparecer, repete para o dígito anterior e depois para o primeiro. Os dois dígitos verificadores saem por cálculo. **CPF completo em 19 buscas** (no máximo 30), tanto em Pessoas (`buscar_pessoas`) quanto no Movimento (`buscar_registros`).
- **O que deveria:** a busca do porteiro não pode responder sobre os dígitos ocultos.
- **Onde:** `portaria/dados.py:286-301` (`_condicao_busca` faz `instr(cpf, ?)` com qualquer pedaço), usado em `:843` e `:1558`.
- **Correção:** no perfil porteiro, buscar CPF só com os 11 dígitos exatos (`cpf = ?`) ou só nos 6 dígitos visíveis. Fazer o mesmo com o celular, se ele também for tratado como dado sensível.

### M3. A importação do JSON antigo não valida nada, não deixa histórico e, com uma data absurda, impede o login · **Média**
- **Passos** (`t2_autorizacao.py` e `t6_gui.py`, parte 1): colocar `registros_portaria.json` ao lado do programa com estes registros:
  - uma visita de 8 dias;
  - tipo "Hacker";
  - CPF `00000000000`;
  - visita aberta com placa;
  - entrada `31/12/9999 23:00`.
- **O que acontece:**
  - Os cinco registros são importados.
  - Nenhum evento vai para o histórico (`autor=None`).
  - O carro não ganha estadia.
  - A visita do ano 9999 faz `horarios.situacao` levantar `OverflowError`, e o **login quebra** (`AppPortaria.entrar` → `atualizar_tabela`). O Painel também quebra. O programa fica inutilizável até alguém apagar a linha direto no banco.
- **O que deveria:** cada registro passar por `validacao.validar` (CPF, tipo, data não futura) e pela regra das 24 h, a estadia ser aberta e haver um evento "Importação do arquivo antigo" com a quantidade. Também a tela não pode cair por causa de uma linha ruim.
- **Onde:** `portaria/dados.py:1763-1792` (`importar_json` chama `_inserir` direto). O estouro acontece em `portaria/horarios.py:207-209` e `:342`.
- **Correção:** validar antes de `_inserir` e ignorar o que não passar, como já é feito com o que o SQLite recusa. Registrar o evento com o autor `(sistema)`. Em `situacao` e `contar_situacoes`, tratar `OverflowError` mostrando a linha como "No campus" e registrando no log.

### M4. N04, efeito real: quem está na guarita trava o administrador pelo diálogo de autorização · **Média**
- **Passos** (`t7_seguranca.py`): digitar 5 senhas erradas para "admin" no diálogo de autorização, que usa o mesmo `usuarios.entrar` do login. A trava fica assim:
  - 1º bloqueio: 30 s;
  - depois 1, 2, 4 e 8 min;
  - depois **15 min a cada 5 chutes, para sempre**.

  Com 35 chutes em cerca de 46 min o admin está travado, e mesmo a senha certa recebe "Aguarde 899 s".
- **Efeito:**
  - A trava vale para **todas as estações** e também para o login normal do admin, porque o contador fica no banco.
  - Se o admin já está logado, a sessão dele continua, mas ele não consegue autorizar exceções "só com senha" (dia já fechado), porque a própria senha dele é recusada.
  - Com um único administrador, um porteiro mal-intencionado (ou só atrapalhado) paralisa autorizações, encerramento e configurações.
  - O contador de bloqueios só zera com um acerto.
- **Onde:** `portaria/tela_autorizacao.py:122-123` e `portaria/usuarios.py:200-245`.
- **Correção:** um contador próprio do diálogo, por estação e operador, que bloqueia o **diálogo** (ou o porteiro) após N erros sem travar o login do administrador. Outra opção é fazer `bloqueios` decair com o tempo.

### M5. Buscas sem espera entre teclas e com varredura completa travam a tela (RNF03) · **Média**
- **Passos** (`t9_gui2.py`, com 100 mil visitas e 20 mil pessoas): digitar um CPF de 11 dígitos na busca do Movimento leva **1,64 s** de tela travada, e na de Pessoas **1,87 s**. Cada tecla dispara uma consulta, inclusive Shift e as setas, por causa do `<KeyRelease>`. Apagar a busca de Pessoas custa 0,37 s por tecla.
- **Causas:**
  - Busca por dígitos ou sem resultado varre a tabela inteira com a função Python `minusculo` (cerca de 320 ms).
  - `buscar_pessoas("")` ordena 20 mil linhas com `ORDER BY NOT EXISTS (subconsulta)` (cerca de 370 ms).
- **Onde:** `portaria/tela_cadastro.py:368`, `portaria/tela_pessoas.py:102`, `portaria/dados.py:286-301` e `:1558-1577`.
- **Correção:**
  - Debounce: `after_cancel` e `after(250, ...)`, e ignorar teclas que não mudam o texto.
  - Com 11 dígitos, usar `cpf = ?` pelo índice.
  - Em Pessoas, trocar o `NOT EXISTS` por `LEFT JOIN registros d ON d.cpf = p.cpf AND d.saida=''` (índice `idx_um_aberto_por_cpf`), ou paginar sem a prioridade de quem está dentro.

### M6. Excluir a visita de origem tira do estacionamento o carro que ainda está lá · **Média**
- **Passos** (`t3_veiculos.py`, "excluir a visita de ORIGEM"): a pessoa sai a pé e o carro fica. O admin exclui a visita em que ela entrou com o carro. O carro **some** da lista Veículos e do contador (`ON DELETE CASCADE`). O histórico só mostra "Exclusão de registro"; não há "Estadia removida" e não há aviso na confirmação.
- **O que deveria:** o carro está fisicamente no estacionamento (RN25). A exclusão deve ser recusada ou avisada ("o carro ABC-1234 continua no estacionamento"), e a estadia deve continuar existindo (`registro_id` NULL), com um evento próprio.
- **Onde:** `portaria/dados.py:562` (`ON DELETE CASCADE`) e `:1058-1073`.
- **Correção:** mudar para `ON DELETE SET NULL` (exige migração v9) ou, mais simples, recusar a exclusão enquanto houver estadia aberta ligada à visita.

### B1. Duas estações dando saída na mesma visita: a segunda sobrescreve a primeira · **Baixa**
- **Passos** (`t4_concorrencia.py`, parte 2, com um gancho determinístico entre o SELECT e o UPDATE): a estação 2 grava a saída às 09:00, e a estação 1 grava 09:05 por cima e informa "gravado". O histórico fica com duas "Saída registrada".
- **Onde:** `portaria/dados.py:1010-1021`. O SELECT roda fora da transação (o sqlite3 só abre BEGIN no primeiro UPDATE) e o `UPDATE` não tem `AND saida = ''`.
- **Correção:** `UPDATE registros SET saida=? WHERE id=? AND saida=''` e só contar e registrar o evento se `rowcount` for diferente de zero. Outra opção é abrir a transação com `BEGIN IMMEDIATE`.

### B2. "Encerrar o dia" em paralelo com uma saída real: evento falso no histórico · **Baixa**
- **Passos** (`t10_encerrar_corrida.py`): enquanto o admin encerra o dia, outra estação dá a saída real às 00:20. O banco mantém 00:20, mas devolve e registra "Saída automática (encerramento) ... 23:00" para essa visita, e o aviso conta uma saída automática a mais.
- **Onde:** `portaria/dados.py:1191-1197` (`rowcount` ignorado).
- **Correção:** só registrar o evento e incluir na lista quando o `UPDATE ... AND saida=''` alterar uma linha.

### B3. A migração para a v8 não pode ser repetida: um banco rebaixado não abre mais · **Baixa**
- **Passos** (`t5c_downgrade.py`): um banco v8 com um carro dentro é aberto pelo programa da v5 (commit `a0fcc00^`), que **regrava `user_version = 5`** sem conferir a versão. Ao abrir de novo no v8, a migração v8 reinsere as estadias e falha: **"Este veículo já está no estacionamento."** O programa não abre mais. A mensagem é enganosa e não houve perda de dados (o backup "antes-v8-de-v5" é feito).
- O código v6 também abriu o banco v8, mas só porque o v5 já o tinha rebaixado. O código v7 **recusa corretamente** sem alterar o arquivo (hash igual, `t5_migrar.py`).
- **Onde:** `portaria/dados.py:585-594` e `:609` (`MIGRAR_ESTADIAS` sem `NOT EXISTS`).
- **Correção:** acrescentar `AND NOT EXISTS (SELECT 1 FROM estadias_veiculo e WHERE e.saida='' AND e.placa=r.placa)` ao `MIGRAR_ESTADIAS`. Os passos v5 a v7 já usam `IF NOT EXISTS` e `ON CONFLICT`.

### B4. Hora com um dígito ("9:5") é aceita, mas o aviso sai errado e a correção pede autorização à toa · **Baixa**
- **Passos** (`t6_gui.py`, parte 2, e `t1_tempo.py`):
  - Entrada "21/10/2026 9:5" é gravada certa (09:05), mas o rodapé diz **"Entrada de Fulano registrada às 6 9:5."**
  - Na correção, a mesma hora escrita "7:05" em vez de "07:05" conta como "entrada mudou" e pede **autorização de retroativo**, e o histórico registra a "alteração".
- **Onde:** `portaria/tela_cadastro.py:791` (`registro["entrada"][-5:]`), `portaria/horarios.py:317-318` (compara textos) e `validacao.converter_data` (o `strptime` aceita 1 dígito).
- **Correção:** normalizar as datas digitadas (`de_iso(para_iso(t))`) logo em `validacao.normalizar`.

### B5. Ano absurdo: "0026" é aceito e "0001" derruba a ação · **Baixa**
- **Passos** (`t1_tempo.py` e `t6_gui.py`, parte 3):
  - "21/10/0026 10:00" passa em `validar` e vira "dia já encerrado" (só com senha). Com a autorização, seria gravado.
  - "01/01/0001 00:00" gera um `OverflowError` não tratado em `excecoes_do_registro`, e o usuário vê "Erro inesperado".
- **Onde:** `portaria/validacao.py` (`validar` só recusa o futuro) e `portaria/horarios.py:207-208`.
- **Correção:** recusar entradas mais antigas que um limite razoável (ex.: ano < 2000, ou mais de 1 ano para trás) com a mensagem "Confira o ano".

### B6. O limite de 3 h do retroativo depende dos segundos, que não aparecem na tela · **Baixa**
- **Passos** (`t1_tempo.py`, "Retroativo: limites"): uma entrada às 10:00 vista às 13:00:00 é normal. Vista às 13:00:30, quando o relógio da tela ainda mostra 13:00, vira **exceção**. O mesmo vale perto do fechamento (23:05:30 contra 23:00).
- **Onde:** `portaria/horarios.py:240-250`.
- **Correção:** truncar o `agora` aos minutos (`agora.replace(second=0, microsecond=0)`), como `_dar_saida` já faz.

### B7. O desfazer no banco não aplica a RN11 nem exige a hora da saída · **Baixa** (defesa em profundidade)
- **Passos** (`t2_autorizacao.py`): `desfazer_saidas([id], autor="porteiro")` sem `saida` **reabre uma visita de um ano atrás**. A tela sempre passa `saida=`, então hoje só uma chamada direta faz isso.
- **Onde:** `portaria/dados.py:1028-1056`.
- **Correção:** tornar `saida` obrigatório para quem não é admin, ou aplicar `pode_editar` à entrada.

### B8. Ficha e ordenação de Pessoas mostram só os 200 carregados como se fossem todos · **Baixa**
- **Passos** (`t8_medir.py` e `t9_gui2.py`):
  - Uma pessoa com 503 visitas aparece como **"Visitas (200)"**.
  - Ordenar Pessoas por "Visitas ▼" põe no topo quem tem mais visitas **entre os 200 carregados**. No banco, outra pessoa tem 503.
- **Onde:** `portaria/tela_pessoas.py:355` e `:304`, com `LIMITE_BUSCA` e `LIMITE_VISITAS` = 200.
- **Correção:** usar a contagem real (`pessoa["visitas"]`) no rótulo, com "mostrando as 200 mais recentes". Ordenar no SQL ou avisar "ordenação entre os 200 mostrados".

### B9. Virada da meia-noite com a tela parada · **Baixa**
- **Passos** (`t9_gui2.py`): às 00:05, só com o tique de 30 s, o cabeçalho continua com **"Quarta-feira, 21 de outubro"**, o Movimento continua com as visitas encerradas de ontem e o campo Entrada já mostra 22/10. Tudo se corrige na primeira ação.
- **Onde:** `portaria/tela_cadastro.py:451-455` (o tique não recarrega) e `:540`.
- **Correção:** no tique, se `relogio().date()` mudou, chamar `app.atualizar_tabela()`.

### B10. Mudança do relógio do Windows com o programa aberto · **Baixa**
- **Passos** (`t9_gui2.py`):
  - Atrasar o relógio 1 h faz a sessão **não expirar** por mais 1 h, porque a inatividade é medida com o relógio de parede.
  - Uma entrada gravada antes do acerto fica "no futuro": a saída é recusada com "A saída não pode ser anterior à entrada" até o relógio passar dela.
- **Onde:** `portaria/interface.py:354-365`.
- **Correção:** medir a inatividade com `time.monotonic()`. Para a saída, mostrar uma mensagem que fale do relógio do computador.

### B11. Código morto novo e duplicado · **Baixa**
- `LARGURA_HORA` (`portaria/tela_configuracoes.py`) não é usada.
- `Banco.verificar_integridade` (`dados.py:733`) não é chamada pelo app e duplica `backup.verificar_banco`.
- `Banco.listar` e `Banco.listar_pessoas` só são usadas nos testes, e `ControleTentativas` também. As duas últimas já constam como pendência.
- **Correção:** remover, ou usar `verificar_integridade` no lugar da cópia em `backup.py`.

## Suspeitas (análise de código, não reproduzidas na tela)

### S1. Configuração antiga na outra estação · **Baixa**
O tique usa `self.config`, lido no último `atualizar_tabela` (`tela_cadastro.py:502-504`). Depois que o admin muda horários ou eventos numa estação, as outras mostram situações e faixas pela regra antiga até a próxima ação. Correção: reler a configuração no tique (custa cerca de 1 ms).

### S2. A lista de "Encerrar o dia" pode não bater com o que é encerrado · **Baixa**
A confirmação é montada com `self.config` e `self.app.registros` da tela (`tela_cadastro.py:681-690`). O banco recalcula com a configuração atual (`dados.py:1182-1187`), então a lista mostrada pode ser diferente da executada. Correção: o banco devolver uma prévia, ou a tela reler a configuração antes.

## Melhorias

1. **Evento não pode passar da meia-noite.** `ler_horario` exige fechamento > abertura no mesmo dia (`horarios.py:442`), então "19:00–02:00" é recusado. Uma festa até 01:00 precisa de uma autorização por pessoa.
2. **Visitante em evento noturno sempre precisa de autorização.** A janela fixa é 08–18, e às 19:00 de um evento de formatura todo convidado vira exceção (`t1_tempo.py`). Sugestão: em dia de evento, a janela fixa segue o horário do evento, ou o evento ganha a opção "libera visitantes".
3. **Professor e funcionário aparecem como "Tempo excedido" durante a tolerância.** Para o professor (permanência "até o fechamento"), das 23:00 às 23:30 a visita fica "Tempo excedido", embora a regra diga que ele tem tolerância (`horarios.py:380-383`, `t1_tempo.py`). Sugestão: limite de permanência = fechamento + tolerância, ou uma situação "Na tolerância".
4. **O banco confere só as 24 h.** Janela, campus fechado e retroativo são conferidos só na tela, e qualquer outro caminho (importação, script) ignora essas regras. Vale pelo menos documentar no README que a defesa em profundidade cobre só a RN19.
5. **Relógio injetado ignorado em parte do banco.** `bloquear`, `desbloquear` e `_evento` usam `datetime.now()` e não `self.relogio` (`dados.py:1515`, `:1526` e `:1749`). Em teste com relógio fixo, o histórico sai com a hora real.
6. **Ordenar Pessoas pela coluna CPF usa o número completo** (`tela_pessoas.py:122`) enquanto o porteiro vê o CPF mascarado. O vazamento é pequeno, mas para o porteiro é melhor ordenar pelo texto mascarado.

---

## O que foi testado e está correto

- **Limite de 24 h no banco:** recusa autorização de porteiro, de login inexistente e de admin desativado, além de justificativa curta ou só com espaços. A saída rápida e a saída em lote acima de 24 h pedem autorização. O porteiro não consegue passar das 24 h pela correção, porque a RN11 barra antes.
- **Retroativo:**
  - exatamente 5 min continua sendo "agora";
  - exatamente 3 h é normal e 3 h + 1 min é exceção;
  - às 23:03, lançar 22:57 exige senha (dia fechado) e lançar 22:58 é normal;
  - domingo usa a meia-noite como fechamento;
  - 23:50 lançado às 00:10 exige senha e também conta como fora da janela.
- **Calendário:**
  - sábado: aluno até 13:30, professor a partir de 06:30;
  - corte do aluno às 22:30;
  - 31/02, 29/02/2027 e "24:00" são recusados e 29/02/2028 é aceito;
  - espaços nas pontas são aceitos.
- **Veículos:**
  - carona com a mesma placa é recusada;
  - trocar a placa para uma que já está dentro é recusado;
  - desfazer a saída de carro reabre a estadia;
  - a placa bloqueada depois da entrada ainda pode sair;
  - "Encerrar o dia" não fecha carros, e eles ficam "Veículo pendente";
  - o contador de veículos é igual ao estacionamento.
- **Migração do banco do aluno (cópia, v7 → v8):**
  - 7 visitas e 2 usuários preservados;
  - os 2 carros abertos viraram 2 estadias;
  - as regras do funcionário e do professor e o retroativo de 12 h para 3 h foram atualizados, com aviso;
  - backup `portaria-antes-v8-de-v7-*.db` criado;
  - `quick_check` e `foreign_key_check` OK;
  - reabrir não refaz nada.
- **Migrações v5, v6 e v7 → v8** (bancos criados pelo código antigo, com `git archive` numa pasta temporária): sem perda, login funciona, estadias criadas, a carona fica sem estadia como documentado e há backup.
- **Concorrência:** WAL ativo. 3 processos × 200 entradas e saídas simultâneas deram 600 visitas, 0 erros e 0 abertas, com latência máxima de 66 ms por operação.
- **Log** (`portaria.log`): só a mensagem do SQLite, sem CPF nem nome (`t10_encerrar_corrida.py`).
- **Tique de 30 s:** leve mesmo com 5.310 visitas abertas esquecidas (0,09 s).

## Desempenho

Banco com 100.300 visitas, 20.000 pessoas, 2.000 estadias (200 abertas), 200.003 eventos no histórico e 300 pessoas no campus, num arquivo de 44 MB (`t8_gerar.py` e `t8_medir.py`). Mediana de 3 a 10 repetições neste PC.

| Operação | Mediana | Observação |
|---|---|---|
| Abrir o banco (sem migração) | 1,1 ms | |
| `quick_check` (integridade) | 78 ms | |
| Cadastrar uma entrada | 4,4 ms | máximo 73 ms (primeira escrita) |
| Movimento (hoje + abertas) | 1,6 ms | |
| Login e montagem da tela principal | 294–335 ms | |
| `atualizar_tabela` depois de gravar | 18 ms | 0,15 s com 5.310 abertas |
| **Tique de 30 s** | **9,6 ms** | 0,09 s com 5.310 abertas; não trava |
| Busca no histórico "silva" (texto) | 5,4 ms | o LIMIT 200 corta cedo |
| **Busca no histórico por dígitos "9982"** | **326 ms** | varredura completa; **por tecla** |
| **Busca no histórico sem resultado** | **315 ms** | varredura completa |
| **Digitar 11 dígitos na busca do Movimento** | **1,64 s** | sem debounce |
| `buscar_pessoas("")` (lista inicial) | 368 ms | `ORDER BY NOT EXISTS` |
| `buscar_pessoas("souza")` | 76 ms | |
| **Digitar 11 dígitos na busca de Pessoas** | **1,87 s** | sem debounce |
| `listar_pessoas` (20 mil, código só usado nos testes) | 323 ms | |
| Abrir a página Pessoas | 384 ms | |
| Ordenar Pessoas (qualquer coluna) | 2–3 ms | só os 200 carregados (B8) |
| Ficha de pessoa com 503 visitas | 7,8 ms | mostra 200 (B8) |
| Painel (resumo no SQL e situações) | 72 ms | 0,22 s com 5.310 abertas |
| `resumo_painel` | 62 ms | |
| Veículos (200 abertos) | 2,0 ms | |
| Contadores da barra lateral | 1,4 ms | |
| Encerrar o dia (nada pendente) | 3,8 ms | |
| Histórico (200 eventos) / de uma visita | 2,2 / 1,0 ms | |
