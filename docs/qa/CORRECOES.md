# Correções dos testes de QA

Dois testes de QA foram feitos sobre a versão 4ccbd07 (rodada 2):
[QA 1 — fluxos](RELATORIO_QA1.md) e [QA 2 — casos difíceis](RELATORIO_QA2.md).
Aqui está a situação de cada achado no ramo `regras-horario` (rodada 4).
Os testes citados ficam em `tests/` (todos falham sem a correção e passam com
ela). Suíte: 535 → 573 testes, todos verdes (1 pulado, o da cópia do banco
real, que só roda com `PORTARIA_BANCO_V7`).

Prints antes/depois no notebook (1366×670 a 125%), nos dois temas:
`docs/qa/prints/antes_*.png` e `docs/qa/prints/depois_*.png`.

## Decisões tomadas (para conferir com o aluno)

1. **Evento soma ao dia** (decisão do coordenador). Sábado 07–14 com
   formatura 18–23 abre nas duas janelas; num domingo ou feriado o evento é a
   única janela; o fechamento do dia é o fim da última janela. As janelas
   fixas (visitante, entregador, prestador) só valem dentro de uma janela
   aberta. Consequência: na formatura de domingo 18–23, convidado
   "Visitante" (janela 08–18) é sempre exceção (sugestão do QA 2 para
   depois: opção "o evento libera visitantes").
2. **Retroativo com o campus fechado** (coordenador): uma SAÍDA lançada num
   horário em que o campus estava fechado para a categoria (madrugada,
   domingo sem evento, entre as duas janelas do sábado) é exceção com
   autorização, mesmo que recente. Para a ENTRADA isso já vale pela janela
   da categoria. "Fechado para a categoria" considera o `abre_antes` dela
   (funcionário 1 h antes) e a tolerância depois do último fechamento.
3. **Prazo da categoria** (coordenador): "dia já fechou, só com senha" usa
   fechamento + tolerância da categoria. A saída real da funcionária às
   23:00, lançada às 23:10, é normal; a do aluno, às 23:10, pede a senha.
4. **Excluir visita com carro no estacionamento**: o carro **não** é apagado
   (ele está fisicamente lá). A confirmação avisa ("O carro ABC-1234 dessa
   visita continua no estacionamento"), a estadia aberta perde só a ligação
   com a visita (o responsável continua pelo CPF/cadastro) e o histórico
   registra "Veículo mantido no estacionamento". Para tirá-lo, saída pela
   placa. As estadias já encerradas daquela visita vão junto com ela.
   Sem migração de esquema (a chave continua `ON DELETE CASCADE`; a estadia
   aberta é desligada antes do DELETE).
5. **CPF na busca do porteiro**: só pelos 11 dígitos (busca exata). O
   celular continua por pedaço (o porteiro já o vê na ficha). O
   administrador continua achando por qualquer pedaço. Ordenar Pessoas pela
   coluna CPF usa o texto mascarado para o porteiro.
6. **Diálogo de autorização (N04)**: as senhas erradas contam num contador
   próprio de cada computador (guardado no banco, não zera ao reabrir),
   com a mesma espera crescente do login (30 s, 1, 2, 4, 8, 15 min). Ele
   trava só o diálogo naquela estação; o login do administrador nunca é
   afetado. Cada erro vira "Autorização recusada" e a trava, "Autorização
   travada" no histórico (autor = quem operava; o texto digitado só aparece
   se for um login que existe).
7. **Programa antigo rebaixando o banco**: não há como proteger o código já
   distribuído das versões 5 e 6 (ele regrava o `user_version` sem conferir).
   O código novo (banco v10) guarda a versão também na tabela `meta`: se o
   banco foi rebaixado, ele atualiza de novo (todos os passos podem repetir;
   backup antes) e avisa o administrador; se a `meta` disser uma versão mais
   nova, recusa abrir, mesmo com o `user_version` rebaixado (proteção para as
   versões futuras). Falha de migração pelas regras do banco diz que foi a
   atualização, em vez de "Este veículo já está no estacionamento".
8. **Correção com a linha desatualizada**: recusada sem gravar nada
   ("Este registro foi alterado em outra estação…"), com a condição no
   próprio UPDATE (trava otimista). Não há mescla automática.

## QA 1

| Achado | Gravidade | Situação | Teste |
|---|---|---|---|
| A1 placa de carro que já saiu dá saída na pessoa | Alta | Corrigido: pela placa só sai o carro; sem carro, "não está no estacionamento" | `test_interface.TestSaidaRapida.test_placa_de_carro_que_ja_saiu_nao_da_saida_na_pessoa` |
| A2 Funcionamento: botão some no notebook depois de um erro | Alta | Corrigido: botão no topo do cartão; mensagem no lugar da nota | `test_interface.TestTelaPequena.test_configuracoes_botao_e_mensagens_sempre_visiveis` |
| A3 Categorias: erro/"Salvo" fora da tela | Alta | Corrigido: mensagem logo abaixo de "Salvar regras" | idem |
| M1 excluir a visita apaga o carro | Média | Corrigido (decisão 4) | `test_interface.TestExcluirVisitaComCarro`, `test_regras_no_banco.TestEstadiasDeVeiculo.test_excluir_a_visita_nao_tira_o_carro_que_esta_la` |
| M2 evento substitui o dia | Média | Corrigido: evento soma (decisão 1) | `test_horarios.TestFuncionamento.test_evento_soma_ao_funcionamento_do_sabado`, `TestJanelaPorCategoria.test_evento_no_sabado_a_noite_soma_a_manha` |
| M3 dois carros: fecha o carro errado | Média | Corrigido: pergunta primeiro pelo carro da visita; o banco fecha o carro escolhido | `test_interface.TestEstadiaDeVeiculo.test_dois_carros_*`, `test_regras_no_banco.TestEstadiasDeVeiculo.test_dois_carros_*` |
| M4 retroativo incoerente na madrugada | Média | Corrigido (decisão 2) | `test_horarios.TestLancamentoRetroativo.test_b_saida_com_o_campus_fechado_e_excecao_mesmo_recente` |
| M5 notebook: Movimento com 1–2 linhas e aviso cortado | Média | Corrigido: 4 linhas com a faixa de pendências; aviso com Desfazer na linha inteira | `test_interface.TestTelaPequena.test_aviso_com_desfazer_cabe_e_movimento_com_pendencias` |
| M6 porteiro não lança a saída real na tolerância | Média | Corrigido (decisão 3) | `test_horarios.TestLancamentoRetroativo.test_c_usa_o_prazo_da_categoria` |
| B1 Painel: números cortados | Baixa | Não corrigido: o QA 1 viu com a escala simulada de 0,98; no print atual (125%) "3h 18min" cabe | — |
| B2 Pessoas: colunas CPF e Última visita cortadas | Baixa | Não corrigido: mexe na largura das colunas e na ficha; fica para a revisão visual | — |
| B3 Pessoas diz "No campus" para "Saída pendente" | Baixa | Não corrigido: a lista de Pessoas não lê a configuração de horários; baixo impacto | — |
| B4 virada da meia-noite com a tela parada | Baixa | Corrigido: o tique relê o dia | `test_interface.TestBuscaEViradaDoDia.test_virada_da_meia_noite_rele_o_dia` |
| B5 "Adicionar" do evento cortado | Baixa | Corrigido: botão na linha da data | print `depois_*_config_eventos_1366x670.png` |
| B6 domingo desligado diz "Aberto" | Baixa | Corrigido: "Fechado" | print `depois_*_config_funcionamento_erro_1366x670.png` |
| B7 busca do admin some no notebook | Baixa | Corrigido: na tela baixa o título "Movimento" sai e a busca fica com a largura | print `depois_*_movimento_admin_1366x670.png` |
| B8 calendário deixa escolher data futura | Baixa | Não corrigido: o cadastro já recusa; mexer no seletor afeta os campos de feriado/evento (que aceitam futuro) | — |
| B9 correção que fecha a visita não pergunta pelo carro | Baixa | Não corrigido: comportamento de correção (o carro sai pela placa); registrado | — |
| B10 campo do Novo bloqueio aceita qualquer texto | Baixa | Não corrigido: o campo serve a CPF ou placa conforme o tipo; o Salvar já valida | — |
| B11 fechar à meia-noite (24:00) | Baixa | Não corrigido: exige janela que passa da meia-noite (junto com a melhoria do evento até 01:00) | — |
| B12 README "Versão atual 2.0" | Baixa | Corrigido: diz que a 2.1 está em desenvolvimento | — |
| B13 faixa de erro antiga não some | Baixa | Corrigido: reler a página traz a nota de volta | `test_interface.TestTelaPequena.test_configuracoes_botao_e_mensagens_sempre_visiveis` |
| E1–E3 melhorias | — | Registradas (IDEIAS_E_MELHORIAS.md) | — |
| S1 Desfazer do carro sem explicação | Suspeita | Não corrigido | — |
| S2 redefinir senha igual ao login | Suspeita | Não corrigido (S07, já registrado) | — |

## QA 2

| Achado | Gravidade | Situação | Teste |
|---|---|---|---|
| A1 correção com linha desatualizada apaga a saída de outra estação | Alta | Corrigido (decisão 8) | `test_regras_no_banco.TestCorridaEntreEstacoes.test_correcao_com_linha_desatualizada_e_recusada`, `test_interface.TestLinhaDesatualizada.test_correcao_aberta_antes_da_saida_de_outra_estacao` |
| A2 janela fixa entra com o campus fechado em dia de evento | Alta | Corrigido: janela fixa só dentro de janela aberta | `test_horarios.TestJanelaPorCategoria.test_janela_fixa_so_dentro_do_campus_aberto` |
| M1 dois carros: fecha o carro errado | Média | Corrigido (ver QA 1 M3), também pela placa ("saiu junto") | `test_interface.TestEstadiaDeVeiculo.test_placa_do_segundo_carro_saiu_junto_fecha_esse_carro` |
| M2 CPF mascarado reconstruído pela busca | Média | Corrigido (decisão 5) | `test_dados.TestConsultasNoBanco.test_porteiro_so_acha_cpf_pelos_11_digitos`, `test_interface.TestPorteiro.test_busca_do_porteiro_nao_revela_digitos_do_cpf` |
| M3 importação do JSON sem validação; ano 9999 derruba o login | Média | Corrigido: mesmas regras do cadastro, motivos no aviso, evento no histórico, estadia do carro; data absurda já gravada não derruba a tela | `test_dados.TestMigracao.test_importacao_aplica_as_regras_do_cadastro`, `test_interface.TestDataAbsurdaNoBanco`, `test_horarios.TestDataAbsurda` |
| M4 N04: diálogo de autorização trava o admin em todas as estações | Média | Corrigido (decisão 6) | `test_interface_horarios.TestAutorizacaoComoPorteiro.test_cinco_senhas_erradas_travam_so_o_dialogo_desta_estacao` |
| M5 busca sem espera trava a tela | Média | Corrigido: espera de 300 ms entre teclas (uma busca por CPF digitado) e CPF completo pelo índice (0,25 s → 10 ms) | `test_interface.TestBuscaEViradaDoDia.test_busca_espera_a_pausa_na_digitacao`, `test_dados.TestConsultasNoBanco.test_busca_pelo_cpf_completo_usa_o_indice` |
| M6 excluir a visita tira o carro | Média | Corrigido (decisão 4) | ver QA 1 M1 |
| B1 duas saídas simultâneas: a segunda sobrescreve | Baixa | Corrigido: `AND saida = ''` no UPDATE | `test_regras_no_banco.TestCorridaEntreEstacoes.test_duas_saidas_ao_mesmo_tempo_a_segunda_nao_sobrescreve` |
| B2 Encerrar o dia com saída falsa no histórico | Baixa | Corrigido: só registra o que o UPDATE gravou | `test_regras_no_banco.TestCorridaEntreEstacoes.test_encerrar_o_dia_nao_registra_saida_falsa` |
| B3 migração v8 não repete; banco rebaixado não abre | Baixa | Corrigido (decisão 7) | `test_dados.TestIntegridade.test_banco_rebaixado_por_programa_antigo_abre_e_avisa`, `test_versao_mais_nova_na_meta_e_recusada_mesmo_rebaixada`, `test_migracao_recusada_diz_que_e_a_atualizacao` |
| B4 hora "9:5" | Baixa | Corrigido: normalizada para "09:05" | `test_validacao.TestCampos.test_normalizar_completa_a_hora_de_um_digito` |
| B5 ano "0026"/"0001" | Baixa | Corrigido: antes de 2000, "Confira o ano" | `test_validacao.TestValidar.test_ano_absurdo_e_recusado` |
| B6 limite de 3 h depende dos segundos | Baixa | Corrigido: segundos não contam | `test_horarios.TestLancamentoRetroativo.test_os_segundos_do_relogio_nao_contam` |
| B7 desfazer no banco sem a hora | Baixa | Não corrigido: a tela sempre passa a hora; exigir no banco quebraria chamadas internas e testes antigos de propósito | — |
| B8 ficha "Visitas (200)" | Baixa | Corrigido: total real e "Mostrando as 200 mais recentes de N" | `test_interface.TestHistoricoEOrdemNaPaginaPessoas.test_ficha_com_mais_visitas_que_o_limite_mostra_o_total_real` |
| B9 virada da meia-noite | Baixa | Corrigido (ver QA 1 B4) | idem |
| B10 relógio do Windows muda com o programa aberto | Baixa | Não corrigido: a inatividade usa o relógio injetado (os testes dependem dele); trocar para `time.monotonic` fica registrado | — |
| B11 código morto | Baixa | Parcial: `LARGURA_HORA` removida; `verificar_integridade`, `listar`, `listar_pessoas` e `ControleTentativas` ficam (usados nos testes) | — |
| S1 configuração antiga na outra estação | Suspeita | Não corrigido (vale na próxima ação) | — |
| S2 lista do Encerrar o dia × o que é encerrado | Suspeita | Não corrigido; o banco agora só registra o que gravou (B2) | — |
| Melhorias 1–6 | — | 6 (ordenar CPF mascarado) feita; as outras registradas em IDEIAS_E_MELHORIAS.md | — |

## Reexecução dos scripts dos QAs (código corrigido)

Os scripts foram copiados e apontados para o código corrigido (fora do
repositório). Resultado:

- QA 2 `t4_concorrencia`: correção desatualizada **recusada**, a saída da
  outra estação fica; corrida de saídas: a estação atrasada grava `[]` e
  fica 1 "Saída registrada".
- QA 2 `t7_seguranca`: 35 chutes no diálogo → o admin **entra** com a senha
  certa em todas as rodadas; 0 "Login recusado"; reconstrução do CPF pela
  busca do porteiro **falha** (30 buscas, CPF errado).
- QA 2 `t1_tempo`: domingo com evento 18–23 → visitante/entregador/prestador
  fora da janela são exceção; `9:5` → `09:05`; ano 0026 recusado; segundos
  não contam.
- QA 2 `t2_autorizacao` / `t6_gui`: importação ignora os 4 inválidos com os
  motivos, abre a estadia, grava "Importação do arquivo antigo"; ano 9999
  não derruba o login.
- QA 2 `t3_veiculos`: excluir a visita de origem mantém o carro; dois carros
  → sai o da visita.
- QA 2 `t5c_downgrade`: o programa v5 ainda rebaixa (não há como mudar o
  código antigo), mas o v10 reabre com aviso e sem estadia duplicada.
- QA 2 `t10_encerrar_corrida`: nenhuma saída automática falsa.
- QA 2 `t9_gui2` (100 mil visitas): digitar o CPF na busca faz 1 consulta
  (pior tecla 1 ms); a busca do CPF completo leva ~0,05 s na tela; ficha
  "Visitas (503)"; virada do dia relê o cabeçalho.
- QA 1 `s4_veiculos`: a placa de novo → "não está no estacionamento",
  Davi continua no campus; a exclusão avisa e mantém o ABC-1234.
- QA 1 `s3_noite`: a saída da Marta às 23:00 (tolerância) é gravada sem
  senha; sábado com formatura: aluno às 08:00 entra normal.
- QA 1 `s5_config` / `s7_telas`: botão Salvar e mensagens visíveis no
  notebook.

## Limitações conhecidas

- O programa antigo (versões 5 e 6) continua podendo abrir e rebaixar o
  banco; o novo percebe e se recupera, mas não impede.
- No QA 1, com a escala simulada de 0,98, o Movimento mostra 3 linhas e
  meia com a faixa de pendências e o aviso; no notebook real (125%) e no
  teste automatizado, 4.
- As regras de janela e retroativo continuam conferidas só na tela (o
  banco confere a autorização das 24 h).
