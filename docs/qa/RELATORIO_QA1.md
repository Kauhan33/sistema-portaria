> Cópia do relatório do teste de QA 1, feito na versão 4ccbd07 (antes do
> modo noturno). Os scripts e prints citados ficaram fora do repositório; a
> situação de cada achado está em [CORRECOES.md](CORRECOES.md). Todos os
> dados são fictícios.

# Relatório QA 1 — Testador de fluxos

Código testado: cópia congelada `scratchpad/time/qa/repo` (commit 4ccbd07). Nada foi
alterado nela. Todos os dados são fictícios.

## Como foi testado

- App de verdade (`AppPortaria(..., relogio=...)`) rodando da cópia congelada, banco
  novo na pasta `qa1/`, caixas de mensagem gravadas (não bloqueiam), diálogos de
  autorização e de veículo respondidos por script **depois** de fotografados.
  Conferência sempre no banco (`sqlite3`) além da tela.
- Harness: `qa1/harness.py`. Cenários: `s1_dia.py` (primeiro acesso, porteiro, manhã),
  `s2_tarde.py` (retroativo, correção, Painel), `s3_noite.py` (fechamento, pendências,
  Encerrar o dia), `s4_veiculos.py` (carro: casos de borda), `s5_config.py`
  (Configurações), `s6_teclado_sessao.py` (Tab/Enter/F2, calendário, sessão, senha),
  `s7_telas.py` (notebook, CSV, senha do admin logado), `s8_meia_noite.py`, `s9_prints.py`.
- **Prints**: este PC tem tela 1080×1920 (retrato) a 175%, então a janela de 1366 px não
  cabe. Simulei a mesma geometria **lógica**: `estilo.ESCALA` e `tk scaling` em 0,98, e
  a janela com 1093×536 px lógicos, que é o mesmo que 1366×670 reais a 125%. O layout
  (inclusive a troca para o modo compacto) depende só de medidas lógicas, então o que
  aparece cortado no print também aparece cortado no notebook. "Monitor comum" = 1100×760
  lógicos. Captura com PrintWindow, sem multiplicar a escala. Pasta: `qa1/prints/`.

## Resumo

| Gravidade | Confirmados | Suspeitas |
|---|---|---|
| Alta | 3 | 0 |
| Média | 6 | 0 |
| Baixa | 13 | 2 |
| Melhoria | 3 | 0 |

O que funcionou bem (sem problema): primeiro acesso, senha igual ao login recusada,
criar porteiro, autorização do porteiro (senha errada conta como tentativa, porteiro
não autoriza a si mesmo), autorização do admin logado sem senha e com senha no dia
fechado, janelas de cada categoria, saída a pé/de carro, volta a pé com a faixa
"O carro … está no estacionamento", "Saiu junto?", Desfazer da saída de carro
(visita e estadia voltam), Encerrar o dia (saída no prazo + tolerância; carros ficam),
porteiro não encerra o dia nem vê Excluir, sessão que expira fecha o Corrigir sem
gravar, Enter fora da Entrada e saída não cadastra, F2 de outra página, Entrada que
acompanha o relógio, exportar CSV (BOM, `;`, CPF formatado), trocar senha.
Números Painel × Movimento × Pessoas bateram em todos os momentos conferidos
(6/8/2 às 11:05; 2 no campus e 3 carros às 09:00 do dia seguinte).

---

## Confirmados (reproduzi)

### A1 — Saída rápida pela placa de um carro que já saiu dá saída na PESSOA, sem perguntar — **Alta**
- Passos: (porteiro, 09:00) entregador entra com placa BRA2E19 → Saída rápida
  `BRA2E19` → "Só o carro saiu" → digitar `BRA2E19` de novo na Saída rápida + Enter.
- Acontece: o aviso diz "Saída de Davi registrada às 09:00" e o banco grava a saída da
  visita; nenhuma pergunta. A pessoa continua no campus de fato, mas sai da lista.
- Deveria: pela placa só sai o **carro** (README); sem carro no estacionamento, avisar
  "Esse carro não está no estacionamento" (ou perguntar se é a pessoa que está saindo).
- Onde: `portaria/tela_cadastro.py:1074-1094` (sem estadia aberta, cai em
  `encontrar_dentro`, que casa pela placa da visita).
- Correção: quando a chave não é número, se não há estadia aberta, não procurar visita
  pela placa; mostrar o erro. (Mesmo efeito com segunda leitura da placa na guarita.)

### A2 — Configurações › Funcionamento: depois de um erro, o botão "Salvar funcionamento" some no notebook e o erro não sai mais — **Alta**
- Passos: notebook 1366×670 → Configurações → Lançamento retroativo = `0` → Salvar
  funcionamento → corrigir para `3` (ou trocar de página e voltar).
- Acontece: a faixa de erro empurra o botão para fora do cartão (botão em y=522 numa
  janela de 525 px, só 3 px visíveis); ao reler (`atualizar`) os valores voltam mas a
  faixa vermelha continua e o botão continua inacessível. Não há Enter nem rolagem.
- Deveria: botão sempre visível; faixa some ao reler/corrigir.
- Onde: `portaria/tela_configuracoes.py:144-147` (botão `side="bottom"` + faixa
  empacotada depois), `441-448` (`_resultado`), `430-439` (`atualizar` não esconde as faixas).
- Print: `prints/s5_04_config_func_erro.png`, `prints/s7_05_config_apos_erro.png`
  (antes do erro: `prints/s5_01_config_func_notebook.png`).
- Correção: pôr a faixa acima do botão num frame com o botão fixo, esconder as faixas em
  `atualizar()`, e/ou ligar Enter ao salvar.

### A3 — Configurações › Categorias: no notebook, erro e "Salvo" ficam fora da tela (o admin não sabe se gravou) — **Alta**
- Passos: notebook → Configurações → Categorias → Aluno "Até" = `30` → Salvar regras.
- Acontece: nada visível muda; a faixa de erro é empacotada depois da grade, abaixo do
  fim do cartão (`winfo_ismapped()=0`). O mesmo vale para "Salvo: N alteração(ões)".
  Com um valor inválido o admin acha que salvou e nada foi gravado.
- Deveria: mensagem visível perto do botão Salvar regras.
- Onde: `portaria/tela_configuracoes.py:201` (faixa criada) e `441-448`.
- Print: `prints/s10_01_categorias_erro_notebook.png`.
- Correção: empacotar a faixa antes da grade (`before=self.grade_categorias`) ou na
  linha do título, ao lado do botão.

### M1 — Excluir a visita que trouxe o carro apaga o carro do estacionamento — **Média**
- Passos: visitante entra com ABC1234 → sai a pé (carro fica) → volta a pé → admin
  seleciona a 1ª visita (a do carro) → Excluir → Sim.
- Acontece: `estadias_veiculo` perde a estadia aberta (ON DELETE CASCADE); o carro some
  da lista de Veículos e do Painel, embora esteja fisicamente lá. A confirmação não avisa.
- Deveria: avisar ("o carro ABC-1234 dessa visita continua no estacionamento") e manter a
  estadia (ou recusar/pedir confirmação específica).
- Onde: `portaria/dados.py:562` (`ON DELETE CASCADE`), `portaria/tela_cadastro.py:1015-1022`.
- Correção: `ON DELETE SET NULL` para estadia aberta, ou checar estadia aberta antes de
  excluir e perguntar.

### M2 — Evento substitui o dia inteiro: "formatura no sábado 18:00–23:00" cancela a manhã do sábado — **Média** (regra)
- Passos: Configurações → Eventos → 24/10/2026 (sábado) 18:00–23:00 "Formatura de
  Direito" → sábado 08:00 registrar Aluno; sábado 15:00 Professor.
- Acontece: os dois viram exceção ("fora do horário permitido (18:00–22:30)" /
  "(17:30–23:00)"). O exemplo do próprio README transforma o sábado normal 07–14 em
  campus fechado até 17:30.
- Deveria: ou o evento estende o horário do dia (união com o funcionamento), ou a tela
  avisa ao cadastrar: "o horário normal do dia (07:00–14:00) deixa de valer".
- Onde: `portaria/horarios.py:159-168` (`expediente`), `tela_configuracoes.py:388-402`.
- Correção mínima: aviso na faixa ao adicionar evento em dia que já abre; ideal: opção
  "substituir" × "estender".

### M3 — Mesmo CPF com dois carros: a saída "de carro" fecha o carro errado — **Média**
- Passos: Ana entra com AAA1111 → sai a pé → volta com **outro** carro BBB2222 (o sistema
  aceita) → sai pela saída rápida do CPF.
- Acontece: a pergunta é "Saiu com o veículo AAA-1111?" e, com "Saiu de carro", fecha a
  estadia de AAA1111; BBB2222 (o carro com que ela entrou nessa visita) fica no
  estacionamento.
- Deveria: perguntar pelo(s) carro(s) dela (ou pelo da visita) — ou recusar a 2ª placa
  enquanto houver carro dela no estacionamento (README lista "vários carros" como futuro).
- Onde: `portaria/tela_cadastro.py:1152-1153` (`por_cpf` guarda uma estadia por CPF),
  `portaria/dados.py:1204-1209` e `1251-1263` (`ORDER BY e.entrada LIMIT 1`).
- Correção: na entrada com placa, se o CPF já tem carro no estacionamento, avisar/recusar;
  na saída, usar a estadia aberta da própria visita (`registro_id`).

### M4 — Regra do retroativo (RN24 c) fica incoerente na madrugada — **Média** (regra)
- Passos (funções puras, confirmadas em `horarios.retroativo`):
  - 23:10 lançando saída de 23:04 → **só com senha de admin**;
  - 00:30 lançando saída de 00:10 → **nada** (normal);
  - 05:50 lançando saída de 02:00 → só autorização simples (sem senha).
- Acontece: lançamentos depois do fechamento mas antes da meia-noite exigem senha;
  os da madrugada (mesma situação: campus já fechado) não.
- Deveria: tratar "período fechado" igual dos dois lados da meia-noite (ex.: o dia
  operacional vai do fechamento ao próximo fechamento, ou qualquer momento fora do
  expediente com atraso > 5 min pede senha).
- Onde: `portaria/horarios.py:233-251` e `337-343` (`fechamento_do_dia` usa a data do momento).

### M5 — Notebook: Movimento mostra 1–2 linhas e o aviso do rodapé fica cortado — **Média**
- Passos: notebook, 23:10, com "5 saídas pendentes e 3 veículos pendentes…" (faixa de 2
  linhas) → olhar o Movimento; dar uma saída a pé.
- Acontece: só 1 linha inteira + metade da 2ª (o README promete "umas 4 linhas"); a lista
  Veículos mostra 2 de 3 sem barra de rolagem visível. O aviso de sucesso (com Desfazer)
  é cortado à esquerda e à direita e encosta no status ("…rada de Otto registrada às
  22:55 (exceção autorizada por clara.ad"); também no monitor comum
  ("e Rita registrada às 09:00 (a pé; o carro ABC-1234 fica no estacionar").
- Onde: `portaria/tela_cadastro.py:381-395` (status e aviso na mesma linha, sem limite),
  `171-178`/`637-671` (faixa), `78-80` (ALTURA_CONFORTAVEL).
- Prints: `prints/s3_02_notebook_2310_porteiro.png`, `prints/s1_07_volta_a_pe.png`,
  `prints/s9_01_veiculos_notebook.png`.
- Correção: aviso numa linha própria (ou esconder o status enquanto há aviso) e com
  `wraplength`; faixa de pendências numa linha só no compacto (texto curto + "Detalhes").

### M6 — Porteiro da noite não consegue lançar a saída real de quem saiu na tolerância — **Média** (regra/uso)
- Passos: porteiro, 23:10 → Corrigir da funcionária (tolerância até 23:30) → Saída
  `21/10/2026 23:00` → Salvar.
- Acontece: pede a **senha de um administrador** ("dia já encerrado"), que à noite não
  está. A alternativa é registrar 23:10 (horário errado).
- Deveria: dentro da tolerância da categoria (ou até X min), saída retroativa curta não
  pedir senha.
- Onde: `portaria/horarios.py:243-247`, `tela_edicao.py:172-185`.

### B1 — Painel: números e legendas cortados nos cartões — **Baixa**
- "Permanência média" aparece "lh 27mir" / "9h 02mir"; "acima da permanência da cat".
- Onde: `portaria/tela_dashboard.py:62-83`. Prints: `prints/s2_02_painel_porteiro.png`,
  `prints/s7_03_painel_notebook.png`.
- Correção: formato curto ("1h27"), fonte menor quando não cabe, legenda com quebra.

### B2 — Pessoas: colunas CPF e "Última visita" cortadas — **Baixa**
- CPF "529.982.247-2", "Última" mostra "21," / "2". Prints: `prints/s2_03_pessoas.png`,
  `prints/s7_02_pessoas_ficha_visitas.png`. Onde: `portaria/tela_pessoas.py:29-35`.
- Correção: larguras mínimas/stretch, ou esconder Visitas no compacto.

### B3 — Pessoas diz "No campus" para quem está em "Saída pendente" — **Baixa**
- Às 09:00 do dia seguinte, Movimento mostra "Saída pendente" e Pessoas "No campus".
- Onde: `portaria/tela_pessoas.py:264-272`. Print: `prints/s7_02_pessoas_ficha_visitas.png`.

### B4 — Virada da meia-noite com o app aberto: cabeçalho e contagem ficam de ontem — **Baixa**
- 00:05 (só o timer de 30 s): "Quarta-feira, 21 de outubro" e "3 entradas hoje"
  (de ontem); só o campo Entrada vira 22/10.
- Onde: `portaria/tela_cadastro.py:451-455` (`ao_passar_o_tempo` não relê quando muda o dia).
- Correção: se a data mudou desde a última leitura, chamar `app.atualizar_tabela()`.

### B5 — Configurações › Eventos: botão "Adicionar" cortado no notebook — **Baixa**
- Print: `prints/s5_05_feriados_eventos.png` ("Adicior"). Onde: `tela_configuracoes.py:316-323`.

### B6 — Domingo desligado continua com o rótulo "Aberto" — **Baixa**
- O interruptor desligado tem o texto "Aberto" ao lado (lê-se "Domingo Aberto").
- Print: `prints/s5_01_config_func_notebook.png`. Onde: `tela_configuracoes.py:119-121`.
- Correção: trocar o texto para "Fechado" quando desligado.

### B7 — Busca do Movimento quase some para o admin no notebook — **Baixa**
- Com Registrar saída, Corrigir e Excluir, a busca vira "Buscar no h".
- Print: `prints/s3_03_notebook_2315_admin.png`. Onde: `tela_cadastro.py:417-433`.

### B8 — Calendário de Entrada/Saída deixa escolher data futura — **Baixa**
- Escolhi domingo 25/10 14:00 com "agora" = 21/10; o campo aceitou e só o cadastro recusa.
- Onde: `portaria/seletor_data.py:255-277`. Correção: dias futuros apagados nesses campos.

### B9 — Correção que fecha a visita de quem tem carro não pergunta pelo carro — **Baixa**
- Corrigir → Saída preenchida para visitante com XYZ9A87: o carro fica "No
  estacionamento" sem a pergunta "Saiu com o veículo?". Pode ser intencional, mas é
  diferente do botão/duplo clique. Onde: `tela_edicao.py:131-170`, `dados.py:1310-1350`.

### B10 — Campo "CPF ou placa" do Novo bloqueio aceita qualquer texto — **Baixa**
- O README diz que CPF e placa "só aceitam o que cabe no formato, em todas as telas";
  aqui o campo não tem restrição (a validação só recusa ao salvar).
- Onde: `portaria/tela_bloqueios.py:72` (confirmado no código).

### B11 — Configurações não permitem fechar à meia-noite — **Baixa**
- "Fecha" `24:00` é recusado ("horário inválido"); o máximo é 23:59.
- Onde: `portaria/horarios.py:424-444`. Correção: aceitar 24:00 como fim do dia ou dizer na dica.

### B12 — README desatualizado no topo — **Baixa**
- "Versão atual: 2.0" com tudo da 2.1 descrito. Onde: `README.md:7`.

### B13 — Faixa de erro antiga não some ao reler a página — **Baixa**
- Visto em Funcionamento (A2); vale para as 4 faixas de Configurações.
- Onde: `tela_configuracoes.py:430-439`.

### Melhorias
- **E1** — Ficha de visitas (Pessoas) não mostra que a saída foi automática
  ("encerramento") nem que o carro dela continua no estacionamento
  (`tela_pessoas.py:345-401`).
- **E2** — Carona: quem entra sem a placa perde a ligação com o carro; a saída do carro
  pela placa só pergunta pelo responsável (a pergunta "N pessoas com essa placa" ficou
  inalcançável depois da v8). Ideia: campo "veio no carro de…" opcional.
- **E3** — Painel "Pessoas por tipo de acesso" conta **visitas** de todo o histórico
  (Visitantes 4 = 3 pessoas). Trocar o título para "Visitas por tipo" ou contar pessoas.

## Suspeitas (não reproduzi na tela)

- **S1 — Desfazer a saída só do carro que não pôde ser desfeita apaga o aviso sem
  explicar** — Baixa. Em `tela_cadastro.py:1243-1252`, com `desfeitas == 0` chama
  `avisar("")`; o porteiro não sabe por quê (ex.: a mesma placa entrou de novo).
- **S2 — Redefinir senha (Usuários) aceita senha igual ao login** — Baixa
  (já registrado como S07). `tela_usuarios.py:174` chama `validar_senha(senha,
  confirmacao)` sem o login. Relacionado (conhecido N04): o porteiro, errando a senha
  do admin 5 vezes no diálogo de autorização, trava o login do administrador.

## Observação sobre os testes

O horário gravado no histórico usa o relógio do PC (`datetime.now`), não o relógio do
app; nos prints da janela Corrigir aparece "04:14" num teste das 06:15. Em produção os
dois são o mesmo relógio, então não é defeito — só atenção para quem testar com
relógio injetado.
