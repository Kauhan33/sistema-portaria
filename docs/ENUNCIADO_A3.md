# Enunciado da Atividade A3 × Sistema de Portaria

Cada item pedido no enunciado, onde ele está no sistema e o teste que o
comprova. Os testes ficam em [`tests/test_enunciado_a3.py`](../tests/test_enunciado_a3.py),
na mesma ordem do enunciado:

```bash
python -m unittest tests.test_enunciado_a3 -v
```

## Tela 1: Login

| Pedido | No sistema | Teste (`TestTela1Login`) |
|---|---|---|
| Entry usuário e Entry senha | `tela_login.py` (caixas `tk.Entry`) | `test_componentes_do_enunciado` |
| Checkbutton mostrar senha | `tk.Checkbutton` "Mostrar senha" | `test_senha_comeca_escondida_e_o_checkbutton_mostra` |
| Button entrar e limpar | `tk.Button` Entrar e Limpar | `test_limpar_esvazia_esconde_a_senha_e_o_erro` |
| Label | títulos, rótulos e a faixa de erro | `test_componentes_do_enunciado` |
| Imagem/Logo | `assets/logo_portaria.png` em `tk.PhotoImage` | `test_logo_e_uma_imagem_de_verdade` |
| Validar usuário e senha | `usuarios.autenticar` (PBKDF2, bloqueio progressivo) | `test_dados_incorretos_dao_mensagem_de_erro` |
| Impedir campos vazios | "Informe o usuário e a senha." | `test_impede_campos_vazios` |
| Mensagem de erro em dados incorretos | a mesma para usuário ou senha errados | `test_usuario_que_nao_existe_da_a_mesma_mensagem` |
| Ver e ocultar a senha | o Checkbutton troca a opção `show` | `test_senha_comeca_escondida_e_o_checkbutton_mostra` |
| Login válido abre a tela principal | `AppPortaria.entrar` | `TestLoginValidoAbreAPrincipal` |
| Função de autenticação | `usuarios.autenticar`, `tela_login.entrar` | `test_dados_incorretos_dao_mensagem_de_erro` |

## Tela 2: Cadastro

| Pedido | No sistema | Teste (`TestTela2Cadastro`) |
|---|---|---|
| Entry nome, CPF, telefone e empresa | `tk.Entry` | `test_componentes_do_enunciado` |
| Combobox tipo de acesso | `ttk.Combobox` só leitura, com os 6 tipos | `test_componentes_do_enunciado` |
| DateEntry data | campo Data com o calendário (`seletor_data.py`, feito em Canvas: o sistema só usa a biblioteca padrão, e o `DateEntry` é de um pacote externo) | `test_data_abre_o_calendario` |
| Entry horário | campo Horário, com o relógio | `test_data_e_horario_comecam_em_agora` |
| Text motivo | `tk.Text` (`CampoTexto`), com limite e contador | `test_motivo_tem_limite_e_contador` |
| Button cadastrar, limpar e cancelar | `tk.Button` | `test_limpar_esvazia_todos_os_campos`, `test_cancelar_descarta_e_vai_ao_controle` |
| Label | rótulos com `*` nos obrigatórios | `test_componentes_do_enunciado` |
| Campos obrigatórios | `validacao.validar_campos` | `test_cada_campo_obrigatorio`, `test_so_espacos_nao_contam` |
| Validar CPF | dígitos verificadores | `test_cpf_vazio_ou_invalido_e_recusado` |
| Não duplicar o mesmo registro de entrada | a tela, a validação e um índice único no banco (RN05) | `test_nao_duplica_a_entrada_em_aberto` |
| Salvar em SQLite | `dados.Banco` | `test_salva_tudo_no_sqlite` |
| Código de identificação de cada cadastro | o número da visita, "007" (RN48) | `test_cada_cadastro_tem_o_seu_codigo` |
| Confirmação depois de salvar | faixa verde "Registro cadastrado com sucesso! ... Código 007." | `test_gera_codigo_e_confirma_depois_de_salvar` |

## Tela 3: Controle de entrada e saída

Página **Controle de acesso** do menu.

| Pedido | No sistema | Teste (`TestTela3Controle`) |
|---|---|---|
| Entry pesquisa | busca por nome, CPF, telefone, placa, tipo ou empresa | `test_pesquisa_localiza_por_nome_cpf_e_empresa` |
| Combobox filtro | Todos, Dentro, Saiu e cada tipo de acesso | `test_filtro_todos_dentro_saiu_e_tipos` |
| Treeview: Código, Nome, CPF, Tipo de acesso, Entrada, Saída, Situação | `ttk.Treeview` (mais a Placa) | `test_colunas_do_enunciado` |
| Registrar Entrada | na pessoa selecionada na lista | `test_registrar_entrada_com_horario_automatico` |
| Registrar Saída | nas linhas selecionadas | `test_registrar_saida_com_horario_automatico` |
| Atualizar | relê o banco (o que outra estação gravou) | `test_atualizar_le_o_que_a_outra_estacao_gravou` |
| Voltar | volta ao Cadastro | `test_voltar_vai_ao_cadastro` |
| Localizar pessoa cadastrada | a pesquisa vai ao histórico inteiro | `test_pesquisa_localiza_por_nome_cpf_e_empresa` |
| Horário automático de entrada e de saída | o relógio do sistema | `test_registrar_entrada_com_horario_automatico`, `test_registrar_saida_com_horario_automatico` |
| Situação "Dentro" ou "Saiu" | a 1ª coluna da tabela | `test_situacao_dentro_ou_saiu` |
| Impedir segunda entrada sem saída | RN05, na tela e no banco | `test_impede_segunda_entrada_sem_saida` |
| Atualizar a tabela depois de cada operação | | `test_tabela_atualiza_depois_de_cada_operacao` |

## Requisitos técnicos

| Pedido | No sistema | Teste (`TestRequisitosTecnicos`) |
|---|---|---|
| Tkinter: Entry, Button, Label, Combobox, Checkbutton, Treeview | em todas as telas | `test_widgets_pedidos` |
| IF/ELSE, FOR/WHILE, funções, TRY/EXCEPT | em todos os módulos | `test_estruturas_pedidas` |
| Banco SQLite | `portaria/dados.py` | `test_bibliotecas_pedidas` |
| Bibliotecas Tkinter, SQLite3, Datetime e CSV | só a biblioteca padrão do Python | `test_so_biblioteca_padrao` |

## Desafio extra (pelo menos 2; o sistema tem 3)

| Desafio | No sistema | Teste |
|---|---|---|
| **Controle de veículos e placas** | Estadia do carro, até 5 placas por pessoa, lotação, "o veículo só sai com o dono" (RN25 a RN40, RN47) | `tests/test_placas.py`, `tests/test_interface_veiculo.py` |
| **Registro de prestadores de serviços** | Tipo "Prestador de serviço", com empresa e motivo; o filtro mostra as duas colunas (RN48) | `TestTela3Controle.test_prestador_mostra_empresa_e_motivo` |
| **Registro de ocorrências** | Página **Ocorrências**: categoria, descrição, CPF e placa opcionais; resolver e excluir (RN49) | `TestOcorrencias`, `TestOcorrenciasNoBanco` |

## Além do enunciado

A relação com a disciplina de Compiladores continua: o campo **Comando** entende
uma linguagem com análise léxica, sintática e semântica
([gramática](GRAMATICA_DA_LINGUAGEM.md)), e os testes por ataque estão descritos
no [README](../README.md#testes-automatizados).
