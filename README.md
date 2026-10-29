# Sistema de Portaria da Universidade

Projeto da disciplina **Teoria da Computação e Compiladores** (8º período — UNA).
Controle de entrada e saída de pessoas no campus, feito em Python com Tkinter, e
relacionado com as fases de um compilador (léxica, sintática e semântica).

**Versão atual: 2.4** — veja [Versões](#versões). Download (instalador ou `.exe` portátil) na página de [Releases](https://github.com/Kauhan33/sistema-portaria/releases).

![Tela Entrada e saída com o campo Comando](docs/design/final/v24_comando_sucesso_claro.png)

Na 2.4 o sistema ganhou uma **linguagem de comandos** com analisador léxico,
sintático e semântico de verdade — veja
[Linguagem de comandos](#linguagem-de-comandos-compiladores).

## Como executar

Requisitos para usar: **Windows 10 ou 11 de 64 bits**. Não precisa instalar
Python nem nada além do programa.

**Com instalador (recomendado):** baixe o `Instalar_Portaria_<versão>.exe` na
página de [Releases](https://github.com/Kauhan33/sistema-portaria/releases) e
siga o assistente (pede a permissão de administrador do Windows uma vez).

- O programa vai para `C:\Arquivos de Programas\Portaria`, com atalho no Menu
  Iniciar (e na Área de Trabalho, se marcar) e desinstalador em "Aplicativos
  instalados".
- Os dados (banco, backups e log) ficam em **`C:\ProgramData\Portaria`**, uma
  pasta que todos os usuários do Windows daquele computador conseguem gravar
  (a pasta Arquivos de Programas é protegida pelo Windows). **Desinstalar não
  apaga os dados.**

**Sem instalar (portátil):** baixe o `Portaria.exe`, coloque numa pasta onde
você pode gravar (ex.: Documentos ou um pendrive) e abra. O banco, os backups e
o log são criados ao lado do `.exe`.

**Aviso "O Windows protegeu o computador":** aparece porque o programa não tem
assinatura digital (um certificado pago). Clique em **Mais informações →
Executar assim mesmo**. Se o antivírus apagar o arquivo baixado, é um falso
positivo comum em programas gerados com o PyInstaller: restaure o arquivo na
quarentena do antivírus ou use o instalador.

**Pelo código-fonte:** requer o Python 3 instalado (Tkinter já vem na instalação
padrão do Windows). Baixar o código pelo botão "Code" e dar dois cliques no
`.py` não funciona num computador sem Python.

```bash
python portaria_universidade.py
```

### Gerar o executável

```bash
pip install pyinstaller
python build_exe.py
```

Gera `dist/Portaria.exe` (arquivo único, sem janela de console, com o ícone da
cancela). O PyInstaller só é necessário para gerar o `.exe`; o programa continua
usando apenas a biblioteca padrão. O ícone fica em `assets/portaria.ico`
(`assets/gerar_icone.py` refaz o ícone, se o símbolo mudar).

### Gerar o instalador

```bash
winget install JRSoftware.InnoSetup
python build_instalador.py
```

Gera o `.exe` e, em seguida, `dist/Instalar_Portaria_<versão>.exe` com o
**Inno Setup 6** (gratuito), a partir de `instalador/portaria.iss`. A versão
vem de `portaria/__init__.py` (`VERSAO`). O instalador grava, ao lado do
programa, um `instalado.ini` dizendo onde ficam os dados
(`C:\ProgramData\Portaria`); sem esse arquivo (o `.exe` portátil ou o
código-fonte), os dados ficam ao lado do programa — veja `portaria/caminhos.py`.

Os registros ficam no banco SQLite `portaria.db` (módulo `sqlite3`, já incluso
no Python), criado na pasta de dados (instalado: `C:\ProgramData\Portaria`;
portátil ou pelo código: ao lado do programa). Se houver um `registros_portaria.json` da
versão 1 na mesma pasta, ele é importado na primeira execução e renomeado para
`registros_portaria.json.migrado`, que fica como backup.

### Primeiro acesso e login

Na primeira vez o sistema pede para **criar o administrador** (não existe senha
padrão) e mostra, uma única vez, os **8 códigos de recuperação** dele (RN38):
"Imprimir" abre uma página no navegador e só dá para continuar marcando
"Guardei os códigos em lugar seguro". Depois disso abre sempre na tela de
login.

- **Defina sua senha** (RN39): quem o administrador cria, ou cuja senha ele
  redefine, entra com uma senha provisória e escolhe a dele antes de
  qualquer outra tela (diferente da provisória e do login). O banco recusa
  qualquer operação de quem ainda não trocou.
- **Esqueci a senha** (RN38): no login, usuário + um código de recuperação +
  a senha nova. O código é queimado (não vale de novo) e o uso vai para o
  histórico, sem o código; código errado conta no mesmo bloqueio progressivo
  do login. "Gerar novos códigos de recuperação" (menu da conta do
  administrador, com a senha atual) invalida os antigos. Com só 1
  administrador ativo, o Painel mostra "Só existe 1 administrador ativo.
  Crie um segundo."
- **Ausentar** (B4): o cadeado no rodapé da barra lateral, ou **Ctrl+L**,
  cobre a janela com o login ("Guarita travada por Paulo às 14:32"),
  guardando o que estava digitado na Entrada e saída e a página aberta. A
  mesma senha destrava e devolve tudo; outro usuário entrando é troca de
  turno (o rascunho é descartado). As janelas abertas fecham, como na sessão
  que expira.

| Perfil | Pode |
|---|---|
| Porteiro | Registrar entradas e saídas, corrigir registros com entrada nas últimas 24 horas, buscar no histórico, cadastrar pessoas sem entrada ("Nova pessoa") e editar o cadastro delas, ver as pessoas e os veículos desativados e o Painel, trocar a própria senha. Nas tabelas, na ficha da pessoa e na janela Corrigir, vê o CPF mascarado (`***.982.247-**`); ver a exceção em [Segurança e LGPD](#segurança-e-lgpd) |
| Administrador | Tudo do porteiro, com o CPF completo + corrigir registros de qualquer data + **excluir registros** + **desativar e reativar** pessoas e veículos + **excluir pessoa** sem visitas + **exportar CSV** + página **Usuários** (criar, editar nome e perfil, ativar/desativar, redefinir senha, ver a atividade do sistema) + **autorizar exceções de horário** + **Encerrar o dia** + página **Configurações** (horários de acesso) |

Depois de 5 senhas erradas seguidas o login fica bloqueado por 30 s (o tempo
dobra a cada novo bloqueio, até 15 min). As tentativas ficam no banco: fechar e
abrir o programa não zera o bloqueio (o administrador libera o login ao
redefinir a senha). Senhas erradas no diálogo **Autorização do administrador**
(conferidas também pelo banco, que recalcula o hash: V0) contam à parte, por
computador: depois de 5, só o diálogo fica travado naquela
estação (mesma espera crescente); o login do administrador não é afetado. Sem teclado ou mouse por 10 minutos, a sessão se encerra
sozinha e o sistema volta ao login; uma confirmação que ficou aberta nesse
meio-tempo (ex.: "Excluir registro?") não faz mais nada: aparece "A sessão foi
encerrada. Entre novamente." e o banco também recusa a ação sem um usuário
logado e ativo.

## Testes automatizados

```bash
python -m unittest -v
```

919 testes (biblioteca padrão `unittest`) cobrindo a **linguagem de
comandos** (uma classe por fase: léxico, gramática LL(1), sintático,
semântico e a execução comparada com o formulário, além do campo, do console
e do modo didático), validações, regras de
negócio, login, senhas, permissões, cadastro de pessoas e preenchimento
automático, saída rápida e desfazer, correção de registros, **desativação de
pessoa e de veículo**, **Nova pessoa, Editar e Excluir pessoa**, editar
usuário, feriado, evento e a validade de quem pode retirar o carro, o
desenho da **placa antiga** e o layout do Movimento,
**regras de horário** (cada categoria dentro e fora da janela, ninguém entra
depois de fechar, feriados, eventos, 24 h, lançamento retroativo nos três
casos, tolerância, tempo excedido, saída pendente, autorização do
administrador com e sem senha, encerrar o dia, Configurações, evento que
soma ao dia, saída com o campus fechado, prazo da categoria), **estadia de
veículo** (sair a pé, voltar, sair de carro, saída pela placa, veículo
pendente, dois carros, exclusão que mantém o carro), **o veículo só sai com o
dono** (senha do administrador, inclusive logado; senha errada; outra pessoa
com o carro; desfazer, correção, exclusão e importação que não burlam), a
pergunta **"de carro ou a pé?"** na entrada, o **tamanho máximo de todos os
campos** (digitação, colagem, validação e banco), a **versão 2.2** (senha do
administrador conferida pelo banco, troca de senha obrigatória, códigos de
recuperação, quem pode retirar o veículo, carro esquecido, lotação,
"Ausentar", o relatório de exceções e os dois carros da mesma pessoa, inclusive ataques direto ao banco sem
passar pela tela e a migração de um banco v10 com dados), duas estações ao mesmo
tempo (correção com a linha desatualizada, saídas e Encerrar o dia em
paralelo), histórico de visitas e ordenação na página Pessoas, o
**calendário e o relógio** dos campos de data, o **modo noturno** (contraste
WCAG AA de todos os pares de cor dos dois temas, tema de cada usuário,
"Seguir o Windows" com o registro simulado, troca sem fechar o programa
mantendo sessão, página e formulário), banco de dados, histórico,
migrações, busca, backup, exportação, Painel e a própria tela (preenche campos
e clica nos botões com a janela oculta), inclusive a sessão que expira com uma
confirmação ou a autorização aberta e o tamanho de um notebook 1366×768 a 125%.
Um teste a mais confere a migração numa **cópia** de um banco real da versão 7
(só roda com `PORTARIA_BANCO_V7=<caminho da cópia>`).
Os testes de tela usam um **relógio fixo** (uma quarta-feira às 10:00): o
resultado não depende da hora em que eles rodam.

**Casos de teste documentados** (os da seção "Testes" do documento Word):

```bash
python -m tests.relatorio [pasta de saída] [--sem-suite]
```

Roda os testes automáticos ligados a cada caso (CT-01 a CT-68, positivos e
negativos, cada um com o RF/RN, a entrada, o resultado esperado e o teste
que o comprova; os CT-54 a CT-68 ficam na seção **"Linguagem de comandos"**,
com a fase do analisador), marca **PASSOU** ou **FALHOU** e grava
`relatorio_testes.html`, `.csv` e `.json` (com a matriz de rastreabilidade
requisito × caso e o resultado da suíte completa `python -m unittest`, como
evidência) numa pasta temporária ou na pasta pedida — nunca dentro do
repositório. `--sem-suite` pula a suíte completa (mais rápido).

## Galeria

As telas `v24_*` (linguagem de comandos) e `v23_*` são da versão atual. As
das versões anteriores mostram recursos que continuam iguais, mas a barra
lateral delas ainda tem a página Bloqueios (desde a 2.3 é Pessoas ›
Desativadas) e a "Saída rápida" no lugar do campo Comando.

| | |
|---|---|
| ![Comando com sucesso](docs/design/final/v24_comando_sucesso_claro.png) | ![Realce e Tab](docs/design/final/v24_realce_autocompletar_claro.png) |
| **Campo Comando (2.4)** — a resposta numa linha e o console com as últimas | **Realce e Tab** — cada token com a sua cor; o nome vira o CPF; "15:0" em vermelho |
| ![Erro léxico](docs/design/final/v24_erro_lexico_claro_1366x670.png) | ![Erro sintático](docs/design/final/v24_erro_sintatico_claro_1366x670.png) |
| **[Léxico]** "AB12345" não é uma placa, com o ^ na coluna 13 | **[Sintático]** comando desconhecido — "Você quis dizer entrada?" |
| ![Erro semântico](docs/design/final/v24_erro_semantico_escuro_1366x670.png) | ![Abre o mesmo diálogo](docs/design/final/v24_comando_dialogo_claro_1366x670.png) |
| **[Semântico]** a pessoa já está no campus (RN05), no tema escuro | O comando **abre o mesmo diálogo** do formulário ("Vai entrar de carro?") |
| ![Modo didático: tokens](docs/design/final/v24_didatico_tokens_claro_1366x670.png) | ![Modo didático: árvore](docs/design/final/v24_didatico_arvore_claro_1366x670.png) |
| **Modo didático › Tokens** — lexema, token, valor (o caminho do autômato da placa) e coluna | **Modo didático › Árvore** — o nó com erro em vermelho (placa desativada, RN12) |
| ![Modo didático: símbolos](docs/design/final/v24_didatico_simbolos_escuro_1366x670.png) | ![Modo didático: checagens](docs/design/final/v24_didatico_checagens_claro_1366x670.png) |
| **Modo didático › Símbolos** — as linhas da tabela de símbolos consultadas | **Modo didático › Checagens** — na ordem, com a RN; "Parou aqui" |
| ![Porteiro: CPF mascarado](docs/design/final/v24_porteiro_mascarado_claro_1366x670.png) | ![Porteiro no modo didático](docs/design/final/v24_porteiro_didatico_escuro_1366x670.png) |
| **Porteiro** — o Tab escreve o CPF mascarado; console e respostas também | **Porteiro no modo didático** — tabela de símbolos com o CPF mascarado |
| ![Entrada e saída 2.3](docs/design/final/v23_entrada_admin_claro.png) | ![Placa antiga no tema escuro](docs/design/final/v23_entrada_porteiro_escuro.png) |
| **Entrada e saída (2.3)** — o Movimento sobe, com as subabas embaixo do título | **Placa antiga** (NEY-4829) no tema escuro, visão do porteiro |
| ![Pessoas: ativas](docs/design/final/v23_pessoas_ativas_claro.png) | ![Pessoas: desativadas](docs/design/final/v23_pessoas_desativadas_claro.png) |
| **Pessoas › Ativas** — ficha com Editar, Desativar e Excluir | **Pessoas › Desativadas** — motivo, quando e quem; "(sem cadastro)" |
| ![Veículos desativados](docs/design/final/v23_pessoas_veiculos_desativados_claro.png) | ![Nova pessoa](docs/design/final/v23_nova_pessoa_claro.png) |
| **Pessoas › Veículos desativados** — placas que não entram | **Nova pessoa** — cadastro sem entrada |
| ![Editar usuário](docs/design/final/v23_usuarios_editar_claro.png) | ![Editar feriado](docs/design/final/v23_config_feriados_claro_1366x670.png) |
| **Usuários › Editar** — nome e perfil (RN43) | **Configurações** — editar feriado e evento (RN44) |
| ![Registro cadastrado com sucesso](docs/design/final/v23_entrada_admin_escuro.png) | ![Movimento perto do fechamento](docs/design/final/v23_movimento_admin_claro.png) |
| **Tema escuro** — "Registro cadastrado com sucesso! Entrada de Júlia às 15:20." | **Movimento** — tempo excedido, saída pendente e os avisos do fechamento |
| ![Login](docs/design/final/login.png) | ![Primeiro acesso](docs/design/final/primeiro_acesso.png) |
| **Login** — painel da guarita com relógio | **Primeiro acesso** — cria o administrador (sem senha padrão) |
| ![Pessoa já cadastrada](docs/design/final/cadastro_ok.png) | ![Pessoa desativada](docs/design/final/v23_entrada_desativada_claro.png) |
| **Entrada e saída** — quem já veio tem os dados preenchidos | **Pessoa desativada** — a entrada é recusada |
| ![Visão do porteiro](docs/design/final/cadastro_porteiro.png) | ![Layout compacto](docs/design/final/cadastro_compacto.png) |
| **Visão do porteiro** — CPF mascarado, sem Excluir | **Notebook 1366×768** — layout compacto |
| ![Painel](docs/design/final/v23_painel_claro.png) | ![Exportar CSV](docs/design/final/exportar_csv.png) |
| **Painel** — números do dia e gráficos | **Exportar CSV** — só administrador |
| ![Usuários](docs/design/final/v23_usuarios_claro.png) | ![Corrigir registro](docs/design/final/corrigir.png) |
| **Usuários** — contas e atividade do sistema | **Corrigir registro** — com o histórico do registro |
| ![Saída pendente e aviso de fechamento](docs/design/final/horarios_movimento_admin.png) | ![Autorização do administrador](docs/design/final/horarios_autorizacao_porteiro.png) |
| **Regras de horário** — saída pendente, tempo excedido e "fecha em 20 min" | **Autorização do administrador** — exceção pedida pelo porteiro |
| ![Configurações](docs/design/final/r2_config_categorias.png) | ![Painel](docs/design/final/r2_painel.png) |
| **Configurações** — janela, permanência e tolerância de cada categoria | **Painel** — veículos no estacionamento e tempo excedido |
| ![Calendário](docs/design/final/r2_calendario.png) | ![Relógio](docs/design/final/r2_relogio_horas.png) |
| **Calendário** — clique no campo de data | **Relógio** — horas em dois anéis, depois os minutos |
| ![Saiu com o veículo?](docs/design/final/r2_saiu_com_o_veiculo.png) | ![Veículos no estacionamento](docs/design/final/v23_movimento_veiculos_claro.png) |
| **Saiu com o veículo?** — sair de carro ou a pé | **Movimento › Veículos** — os carros no estacionamento |
| ![Carro no estacionamento](docs/design/final/r2_carro_no_estacionamento_1366x670.png) | ![Histórico de visitas](docs/design/final/r2_pessoas_historico.png) |
| **De volta, a pé** — o carro dela continua no estacionamento | **Pessoas** — histórico de visitas na ficha |
| ![Lista ordenada](docs/design/final/r2_pessoas_ordenada.png) | ![Senha no retroativo](docs/design/final/r2_autorizacao_senha_admin.png) |
| **Pessoas** — ordenada pelo cabeçalho (▲ ▼) | **Dia que já fechou** — só com a senha, mesmo para o administrador |
| ![Pendências com veículo](docs/design/final/r2_pendencias_com_veiculo.png) | ![Funcionamento](docs/design/final/r2_config_funcionamento_1366x670.png) |
| **Pendências** — saídas e veículo depois do fechamento | **Configurações** — lançamento retroativo de 3 h (notebook 1366×670) |
| ![Entrada e saída no tema escuro](docs/design/final/escuro_entrada_ficha.png) | ![Painel no tema escuro](docs/design/final/escuro_barra_de_titulo.png) |
| **Modo noturno** — Entrada e saída no tema escuro | **Modo noturno** — Painel, com a barra de título escura |
| ![Login no tema escuro](docs/design/final/escuro_login.png) | ![Menu da conta](docs/design/final/escuro_menu_tema.png) |
| **Modo noturno** — o login segue o tema do Windows | **Menu da conta** — Claro, Escuro ou Seguir o Windows |
| ![Vai levar o carro?](docs/design/final/v22_vai_levar_o_carro_claro.png) | ![Quem pode retirar](docs/design/final/v23_pessoas_veiculo_claro.png) |
| **Vai levar o carro?** — quem está na lista leva o carro sem senha (RN35) | **Pessoas › Veículo** — quem pode retirar o carro |
| ![Carro esquecido](docs/design/final/v22_carro_esquecido_claro.png) | ![Exceções](docs/design/final/v23_excecoes_claro.png) |
| **Carro esquecido** e **Estacionamento 3/50** antes do fechamento (RN36, RN37) | **Usuários › Exceções** — tudo o que passou por cima da regra |
| ![Códigos de recuperação](docs/design/final/v22_codigos_de_recuperacao_claro.png) | ![Esqueci a senha](docs/design/final/v22_login_esqueci_a_senha_claro.png) |
| **Códigos de recuperação** — aparecem uma vez (RN38) | **Esqueci a senha** — com um código de uso único |
| ![Dois carros: entrada](docs/design/final/v23_dois_carros_entrada_claro.png) | ![Dois carros: saída](docs/design/final/v23_dois_carros_saida_claro.png) |
| **Dois carros** — o aviso na entrada com outro carro (RN40) | **Com qual carro está saindo?** — uma pergunta só (ABC-1234 é placa antiga) |
| ![Guarita travada](docs/design/final/v22_guarita_travada_escuro.png) | ![Vagas](docs/design/final/v22_config_vagas_claro_1366x670.png) |
| **Ausentar** — guarita travada, o rascunho fica guardado | **Configurações** — vagas e "Bloquear quando lotado" (notebook 1366×670) |
| ![O veículo só sai com o dono](docs/design/final/r5_veiculo_so_sai_com_o_dono_claro.png) | ![Senha do administrador](docs/design/final/r5_senha_do_administrador_claro.png) |
| **O veículo só sai com o dono** — o dono está fora do campus | **Senha do administrador** — libera o carro, com justificativa (contador 68/200) |
| ![Dono fora do campus](docs/design/final/r5_veiculos_dono_fora_escuro_1366x670.png) | ![De carro ou a pé?](docs/design/final/r5_entrada_de_carro_ou_a_pe_claro.png) |
| **Movimento › Veículos** — "Dono fora do campus" (notebook, tema escuro) | **De carro ou a pé?** — na entrada de quem tem placa cadastrada |

**Antes × depois** (a mesma tela na versão 1 e na 2.0):

| Versão 1 | Versão 2.0 |
|---|---|
| ![Antes](docs/design/antes/2_cadastro.png) | ![Depois](docs/design/final/cadastro_campus.png) |

Todos os prints usam dados fictícios. Mais telas em `docs/design/final/`.

## Telas e funcionalidades

O visual segue o sistema de design **Guarita** (`docs/design/PROPOSTA_DESIGN.md`):
tela calma em tons neutros, um só botão escuro por tela, e cor só quando
importa — verde pode entrar, âmbar atenção, vermelho desativado. O vermelho da
UNA aparece como identidade (símbolo, item ativo do menu, painel do login).
Tudo em Tkinter puro: cantos arredondados, botões, placa e gráficos são
desenhados no `Canvas`, os ícones são da fonte Segoe Fluent Icons e o texto
fica nítido em telas com escala de 125% ou 150% (DPI). Num notebook 1366×768
a 125% a página Entrada e saída usa um layout compacto (formulário em duas
linhas, sem a ficha da placa) para a tabela continuar visível. Prints em
`docs/design/final/`.

- **Login**: painel vermelho com o símbolo da cancela e o relógio da guarita;
  à direita, usuário e senha. No primeiro uso, o mesmo layout cria o
  administrador.
- **Modo noturno**: cada usuário escolhe o tema no menu da conta (três
  pontos no rodapé da barra lateral): **Tema: Claro**, **Tema: Escuro** ou
  **Tema: Seguir o Windows** (lê no Windows se os aplicativos estão no modo
  escuro). A troca acontece na hora, **sem fechar o programa**: a sessão
  continua, a página aberta também, e o que estava digitado na Entrada e
  saída volta para o lugar (janelas abertas, como Corrigir, são fechadas). A
  escolha fica gravada no usuário e vale nos próximos logins dele; a tela de
  login segue sempre o tema do Windows. O tema escuro ("Guarita à noite") tem
  paleta própria, com contraste WCAG AA conferido por teste, placa Mercosul
  branca (e a antiga, cinza) sem recorte claro nos cantos e barra de título
  escura no Windows 10/11
  (`docs/design/PROPOSTA_DESIGN.md`, seção 10). As caixas de mensagem
  nativas do Windows seguem o tema do próprio Windows.
- **Barra lateral**: Entrada e saída, Pessoas, Painel, Usuários e
  Configurações (as duas últimas só para o administrador), com o número de
  pessoas cadastradas. (Até a 2.2 havia a página Bloqueios: na 2.3 ela virou
  a desativação, dentro de Pessoas.) No
  rodapé, quem está logado, o menu da conta (**Trocar minha senha**, **Gerar
  novos códigos de recuperação** para o administrador, o **tema** e Sair),
  o **cadeado** ("Ausentar", Ctrl+L) e o botão sair.
- **Entrada e saída** (tecla **Enter** registra a entrada):
  - ao completar o CPF, a faixa de situação diz se a pessoa é nova, já
    cadastrada (nome, celular, placa e tipo se preenchem sozinhos, só nos campos
    vazios), está no campus (com o atalho "Registrar saída") ou está
    **desativada** (a entrada será recusada; atalho "Ver desativação", que
    abre Pessoas › Desativadas);
  - à direita, a **placa desenhada** acompanha a digitação — Mercosul
    (branca, faixa azul "BRASIL") ou **antiga** (cinza, moldura escura,
    NEY-4829) — e fica vermelha se o veículo estiver desativado; embaixo, o
    histórico da pessoa (visitas, última vinda, tipo);
  - o campo **Entrada** acompanha o relógio enquanto ninguém mexe nele, e o
    registro usa o "agora" exato do clique; editado, vale o que foi digitado;
  - clicar num campo de data (ou no ícone dele) abre o **calendário** e depois
    o **relógio** (horas em dois anéis, 00–11 e 12–23; minutos de 5 em 5 com
    ajuste fino), desenhados no estilo Guarita. Digitar continua valendo; Esc
    fecha. Campos só de data (feriados, eventos, exportar) abrem só o
    calendário; os só de hora (Configurações), só o relógio;
  - campo **Comando** no topo (atalhos **F2** e **Ctrl+K**, no lugar da
    antiga Saída rápida): aceita a [linguagem de
    comandos](#linguagem-de-comandos-compiladores) e, como antes, **só o CPF
    ou só a placa** + Enter dão a saída. Pela placa sai o carro: se o dono
    (o responsável) está no campus, a pergunta se ele saiu junto (sai os
    dois, sem senha); placa de carro que não está no estacionamento é
    recusada, nunca dá a saída da pessoa;
  - cartão **Movimento**, logo abaixo do formulário: o título numa linha
    própria (com o status ao lado: "6 entradas hoje · 5 no campus"), as
    subabas **Pessoas | Veículos** embaixo, à esquerda, e a busca e os
    botões à direita. Em Pessoas: as
    entradas e saídas de hoje e todo mundo que ainda está no campus; com texto
    na busca, procura no **histórico inteiro** (nome, CPF, celular, placa ou
    tipo; o porteiro acha um CPF só pelos 11 dígitos, porque ele vê o CPF
    mascarado). A busca espera uma pausa de 300 ms na digitação. A situação
    de cada visita: no campus, saiu, **Tempo excedido**
    (âmbar) ou **Saída pendente** (vermelho, em destaque), recalculada a cada
    30 s junto com as faixas. Duplo clique ou "Registrar saída" dão a saída
    (aceita várias linhas); o aviso com **Desfazer** fica 10 segundos ao
    lado do título. Em Veículos: placa, responsável, desde quando, situação (**No
    estacionamento**, **Dono fora do campus** ou **Veículo pendente**) e se
    o responsável está no campus ou fora;
  - **veículo com estadia própria**: quem entra com placa abre a estadia do
    carro; a mesma placa não entra de novo enquanto ele estiver lá. Na saída
    de quem tem carro no estacionamento, a pergunta **"Saiu com o veículo
    ABC-1234?"** — *Saiu de carro* ou *Saiu a pé — o carro fica*. Quem volta
    vê a faixa **"O carro ABC-1234 está no estacionamento desde 08:00"**
    (ele é o dono e pode sair com o carro) e entra a pé; na próxima saída, a
    pergunta de novo;
  - **dois carros da mesma pessoa** (RN40): quem já tem carro no
    estacionamento e entra com outro vê **"Carla já tem o BRA2E19 no
    estacionamento desde 08:20"** — *Entrar — ficam os dois*, *O BRA2E19 já
    saiu* (corrige o esquecimento da guarita com a senha do administrador)
    ou Cancelar; até 2 carros por pessoa, o terceiro só com a senha. Na
    saída, uma pergunta só: **"Com qual carro Carla está saindo?"**, com um
    botão por placa (e o horário de entrada) e *A pé — os carros ficam*; sai
    um carro com a pessoa e o outro segue as regras do carro que fica;
  - **o veículo só sai com o dono** (RN32): sem o dono — ele está fora do
    campus, fica no campus ("Só o carro saiu") ou é outra pessoa que sai com
    o carro — aparece **"O veículo só sai com o dono"** (com o nome e o CPF
    do dono, mascarado para o porteiro) e, se o porteiro chamar um
    administrador, o diálogo pede a **senha** dele e a justificativa (o
    administrador logado também redigita a própria senha). Fica no histórico
    como **"Veículo saiu sem o dono"**. O banco confere de novo: nenhum
    caminho (saída, placa, correção, exclusão, desfazer, importação,
    Encerrar o dia) tira um carro sem o dono sem essa autorização;
  - **quem pode retirar o veículo** (RN35): quem está na lista da placa de
    um carro no estacionamento, no campus a pé e não desativado, ouve na saída
    (pelo CPF, pelo Movimento ou pela placa do carro) **"Vai levar o carro
    BRA2E19 de Carla?"** — *Sim, leva o carro* (sai sem senha, "Veículo saiu
    com autorizado" no histórico) ou *Não*. O Desfazer devolve a pessoa e o
    carro. A lista Veículos tem a coluna **Pode retirar**;
  - **lotação** (RN37): com vagas definidas em Configurações, o cabeçalho
    mostra **"Estacionamento 47/50"**; a entrada de carro com ele lotado
    avisa e pede confirmação ou, com "Bloquear quando lotado", a senha do
    administrador;
  - **de carro ou a pé?** (RN34): na entrada de quem tem placa cadastrada (o
    CPF preenche a placa e ninguém mexe nela), a pergunta **"Fulano vai
    entrar de carro?"** com a placa desenhada — *De carro — ABC-1234* (abre a
    estadia), *A pé* (sem placa) ou *Com outro carro* (volta ao campo Placa).
    O Enter escolhe *De carro* se a última visita foi de carro, senão *A pé*.
    Não pergunta se a placa foi digitada ou apagada à mão, se o carro já está
    no estacionamento ou se a pessoa não tem placa cadastrada. Vale também
    para quem vem da página Pessoas ("Registrar entrada");
  - **tamanho máximo** em todos os campos (RN33): a digitação para no
    máximo e a colagem corta no máximo (nome 80, login 20, senha 64,
    justificativa e motivo 200 com o contador "123/200", descrição 80,
    buscas 60, linha de comando 200, data e hora 16, data 10, hora 5, CPF
    e celular 11, placa 7). A validação e o banco recusam o que passar;
  - faixas no topo, só quando importam: **saídas pendentes** e **veículos
    pendentes** depois do fechamento (o administrador tem o atalho **Encerrar
    o dia**) e, nos últimos 30 minutos antes de fechar, **"Campus fecha às
    23:00 (em 20 min) · 5 no campus"** (sem caixa de diálogo, não atrapalha o
    uso) e, na mesma janela, **"2 carros com o dono fora do campus —
    fechamento às 23:00"** com o link "Ver veículos" (RN36);
  - "Corrigir" abre a janela **Corrigir registro** (mesmas validações do
    cadastro; o histórico guarda o que mudou e quem mudou). Se outra estação
    mudou a visita enquanto a janela estava aberta (ex.: deu a saída), a
    correção é recusada sem gravar nada. "Excluir" só aparece para o
    administrador (RN02); o carro que a visita trouxe e que ainda está no
    estacionamento **continua lá** (a confirmação avisa; ele sai pela placa).
- **Pessoas**, com três subabas:
  - **Ativas**: lista com busca e situação (no campus, fora), **ordenada
    pela coluna clicada** no cabeçalho (1º clique crescente, 2º decrescente,
    com ▲ ou ▼; datas e números na ordem certa; abre ordenada pela situação
    e depois pelo nome);
  - **Desativadas**: as pessoas (CPFs) que não entram, com o motivo, quando
    e quem desativou — também o CPF desativado que nunca foi cadastrado,
    como "(sem cadastro)"; **Mostrar reativadas** traz as que já voltaram;
  - **Veículos desativados**: as placas que não entram, com o dono, o
    motivo, quando e quem desativou.
  Só o **administrador** desativa (com motivo de 5 a 200 caracteres: pela
  lista, "Desativar CPF" / "Desativar placa", ou pela ficha) e **reativa**;
  o porteiro vê as listas (CPF mascarado). Reativar não apaga: guarda quem
  reativou e quando. **Nova pessoa** (no cabeçalho) cadastra CPF, nome,
  celular, placa (opcional) e tipo **sem registrar entrada**, com a mesma
  validação da entrada; CPF já cadastrado é recusado e abre a ficha; CPF
  desativado avisa. A **ficha** da pessoa escolhida mostra nome, CPF,
  celular e tipo, a placa, as visitas e a situação; no pé, **Registrar
  entrada** (abre a Entrada e saída já preenchida), **Editar** (o mesmo
  diálogo da Nova pessoa, com o CPF fixo) e, para o administrador,
  **Desativar** / Reativar e **Excluir** (só quem nunca teve visita; com
  histórico, o botão explica que é preciso desativar); e duas seções —
  **Visitas** (o histórico dela, da mais recente para a mais antiga:
  entrada, saída, duração, tipo, placa e situação, com o nome e o celular da
  época quando eram outros) e **Veículo** ("Quem pode retirar" o carro da
  placa dela, com validade opcional; Adicionar e Validade — o porteiro só
  com o dono no campus — e Remover; e, para o administrador, "Desativar
  placa").
- **Painel**: no campus agora, entradas de hoje, permanência média,
  **veículos no estacionamento** (com os pendentes, ou o total de visitas com
  veículo, logo abaixo) e **tempo excedido** (com as saídas pendentes logo
  abaixo); gráficos de pessoas por tipo e das entradas dos últimos 7 dias
  (hoje em destaque). O administrador **exporta para CSV** (Excel) os registros de um
  período.
- **Usuários** (administrador): **Contas** (criar em diálogo, **editar** o
  nome e o perfil, ativar/desativar, redefinir senha) com a atividade do sistema e filtro, e
  **Exceções** (V4): tudo o que passou por cima de uma regra no período —
  horário, retroativo, mais de 24 h, veículo sem o dono, veículo com
  autorizado, lotação com senha, carro que já tinha saído, terceiro carro,
  saídas automáticas e código de recuperação
  usado — com os filtros período, tipo e quem autorizou, a pessoa com o CPF
  mascarado e **Exportar CSV** (registrado no histórico).
- **CRUD em todas as abas**: a matriz de cada página × Criar, Ler,
  Atualizar e Excluir (como, quem pode e o botão) está em `docs/CRUD.md`. O
  Painel é só leitura (é um relatório) e as Exceções são leitura e
  exportação (auditoria não se edita).
- **Configurações** (administrador): os horários de acesso, em três seções —
  **Funcionamento** (abre e fecha de cada dia da semana, minutos do aviso
  antes de fechar, o limite do lançamento retroativo, 3 h, e as **vagas do
  estacionamento** com "Bloquear quando lotado"), **Categorias**
  (janela de entrada, permanência máxima e **tolerância** depois do
  fechamento de cada tipo de acesso) e **Feriados e eventos**
  (adicionar, **editar** e remover). Tudo é validado (hh:mm válido, fechamento depois da
  abertura, números nos limites) e cada mudança fica no histórico. O erro ou o
  "Salvo" aparece junto do botão, no lugar da nota de ajuda (visível também
  no notebook 1366×670).

### Regras de horário de acesso

Padrão do campus (tudo editável em Configurações): **segunda a sexta 06:30–23:00,
sábado 07:00–14:00, domingo fechado**. Um **feriado** fecha o campus no dia. Um
**evento** **soma** uma janela ao dia: num sábado normal 07:00–14:00 com
formatura 18:00–23:00, o campus abre nas duas janelas; num domingo ou feriado o
evento é a única janela. O fechamento do dia (saída pendente, Encerrar o dia,
"até fechar") é o fim da última janela.

| Categoria | Pode entrar | Permanência máxima | Tolerância depois de fechar |
|---|---|---|---|
| Aluno | no funcionamento, até 30 min antes de fechar | até o fechamento | — |
| Professor | de 30 min antes de abrir até o fechamento | até o fechamento | 30 min |
| Funcionário | de 1 h antes de abrir até o fechamento | 12 h | 30 min |
| Visitante | 08:00–18:00, só dentro de uma janela aberta | 4 h | — |
| Entregador | 07:00–17:00, só dentro de uma janela aberta | 1 h | — |
| Prestador de serviço | 07:00–19:00, só dentro de uma janela aberta | 10 h | — |

Aluno, professor e funcionário entram em cada janela do dia (no sábado com
formatura: de manhã e à noite). As janelas fixas valem só com o campus aberto:
um visitante às 08:00 num domingo com evento 18:00–23:00 é exceção.

- **Ninguém entra depois do fechamento** sem autorização: toda janela termina,
  no máximo, no fechamento do dia (um visitante às 16:00 de sábado, com o
  campus fechando às 14:00, é exceção). Em Configurações, "Até" só aceita 0
  ou negativo.
- **Exceções** (pedem a autorização do administrador): entrada com o campus
  fechado ou fora da janela da categoria, **lançamento retroativo** antigo e
  qualquer visita com mais de **24 h**. Vale ao registrar a entrada, dar a
  saída (botão, duplo clique ou campo Comando) e corrigir um registro (só o que
  mudou é conferido de novo).
- **Lançamento retroativo** (data/hora de entrada ou de saída no passado, no
  cadastro e na correção): (a) até **3 h** atrás, num horário em que a
  categoria podia estar no campus e antes do prazo do dia — normal; (b) mais
  de 3 h, ou uma **saída num horário com o campus fechado** (madrugada,
  domingo sem evento, entre duas janelas), mesmo recente — exceção com
  autorização; (c) depois do **prazo da categoria** naquele dia (fechamento +
  tolerância: 23:10 lançando 22:00 de um aluno, ou lançando ontem) — só com a
  **senha** de um administrador, inclusive quando o próprio administrador está
  logado (ele redigita a senha). A saída real às 23:00 de uma funcionária
  (tolerância até 23:30), lançada às 23:10, é normal. Até 5 min no passado
  ainda conta como "agora"; os segundos do relógio não contam. O limite de
  3 h muda em Configurações.
- **Autorização do administrador**: um diálogo lista as regras violadas e pede
  a **justificativa** (obrigatória). Com o porteiro logado, um administrador
  digita o login e a senha dele (senha oculta; errar conta num contador da
  estação, que trava só o diálogo, nunca o login do administrador). Com o administrador logado, basta confirmar com a justificativa
  (menos no caso (c), em que a senha é obrigatória). O
  histórico grava a **"Exceção autorizada"** com quem autorizou, quem operava,
  as regras e o porquê, ligada à visita. Se a sessão expirar com o diálogo
  aberto, nada é gravado. O banco confere de novo: visita acima de 24 h sem a
  autorização de um administrador ativo é recusada.
- **Tempo excedido**: visita aberta acima da permanência máxima da categoria
  (âmbar no Movimento e um número no Painel). É só um alerta.
- **Saída pendente**: a visita aberta vira pendente no **fechamento do dia da
  entrada** (23:00 de segunda a sexta, ou o fim do evento), para todas as
  categorias; só professor e funcionário têm a **tolerância** de 30 min
  (configurável por categoria). Quem entrou depois desse prazo (só com
  autorização) já nasce pendente: o dia dela acabou. É calculada com o
  relógio, não depende de o programa estar aberto às 23:00.
- **Encerrar o dia** (administrador): dá a saída de todas as pendentes, de uma
  vez, no prazo de cada uma (fechamento + tolerância), depois de confirmar;
  cada uma fica no histórico como "Saída automática (encerramento)". Os
  **carros não saem** com o Encerrar o dia: o carro está fisicamente lá.
- **Veículo pendente**: o carro ainda no estacionamento depois do prazo do
  responsável (fechamento + tolerância da categoria dele) aparece na faixa de
  pendências e na lista de veículos; sai só pela placa (saída rápida ou
  lista de veículos). Toda saída de veículo fica no histórico.

Regras e segurança:

- Validações no padrão brasileiro: CPF com dígitos verificadores, celular com
  DDD válido e 9, placa antiga (ABC1234) ou Mercosul (ABC1D23); nome completo só
  com letras. CPF, celular e placa só aceitam o que cabe no formato, em todas as
  telas.
- Entrada e saída não podem estar no futuro nem antes de 2000 ("Confira o
  ano"); hora com um dígito ("9:5") vira "09:05"; a saída não pode ser
  anterior à entrada; o mesmo CPF não pode estar no campus duas vezes ao mesmo tempo
  (conferido com todas as visitas daquele CPF no banco).
- O banco também barra CPF incompleto, saída anterior à entrada e duas visitas
  abertas do mesmo CPF; cada operação é uma transação. Duas estações ao mesmo
  tempo: a saída e o Encerrar o dia só gravam a visita ainda aberta, e a
  correção só grava se a visita estiver como a janela a leu.
- O `registros_portaria.json` da versão 1 é importado com as mesmas regras do
  cadastro: o que não passa é ignorado, com os motivos no aviso, e a
  importação fica no histórico.
- A versão do banco fica também na tabela `meta` (banco v11): se um programa
  antigo abrir o banco e rebaixar a versão, o programa novo atualiza de novo
  (com backup) e avisa o administrador; um banco de versão mais nova é
  recusado. O programa antigo já distribuído (versões 5 e 6) não confere a
  versão e não há como protegê-lo: não use versões antigas no mesmo banco.
- Senha guardada só como hash PBKDF2-SHA256 com sal (RNF02); histórico de ações
  com CPFs mascarados. Os códigos de recuperação também ficam só como hash.
- O banco confere sozinho a senha do administrador nas exceções (V0): recalcula
  o hash, conta as senhas erradas da estação e ignora uma marca "com senha"
  vinda de fora; a autorização de outro usuário sem a senha dele é recusada.
- Ao abrir, o programa faz o **backup do dia** (pasta `backups`, guarda os 30
  mais recentes). Avisos da atualização do banco ou de backup que falhou
  aparecem ao administrador. Erros técnicos vão para `portaria.log`; o usuário
  vê só uma mensagem simples.

## Linguagem de comandos (Compiladores)

A 2.4 transformou a relação com Compiladores em funcionalidade: o campo
**Comando** (F2 ou Ctrl+K, na Entrada e saída) entende uma pequena
linguagem, analisada pelas fases de um compilador, em `portaria/linguagem/`.
A gramática (EBNF, aprovada pelo aluno) está em
[`docs/GRAMATICA_DA_LINGUAGEM.md`](docs/GRAMATICA_DA_LINGUAGEM.md); um teste
confere que ela é a mesma do código e que é **LL(1)**.

```
entrada 529.982.247-25 aluno placa ABC1D23
saida 52998224725 sem carro
ABC1D23                                         (só a placa = saída do carro)
cadastrar 111.444.777-35 visitante nome "Bruno Almeida" cel 31987651234
desativar placa ABC1D23 motivo "furto no estacionamento"
buscar maria visitante semana
```

| Comando | Exemplo | Faz | Quem |
|---|---|---|---|
| `entrada` | `entrada 529.982.247-25 aluno placa ABC1D23` | Registra a entrada | todos |
| `saida` | `saida 52998224725` · `saida placa ABC1D23` · `saida 52998224725 sem carro` | Saída da pessoa ou do carro (`placa X`: com qual carro; `as 14:05`: horário de hoje que já passou) | todos |
| *(implícito)* | `52998224725` · `ABC1D23` | Só o CPF ou só a placa = `saida` (a antiga Saída rápida) | todos |
| `cadastrar` | `cadastrar 111.444.777-35 visitante nome "Bruno Almeida" cel 31987651234` | Nova pessoa, sem entrada (RN41) | todos |
| `editar` | `editar 11144477735 cel 31999990000 tipo professor` | Muda nome, celular, placa ou tipo | todos |
| `excluir` | `excluir 11144477735` | Exclui quem nunca teve visita (RN42) | admin |
| `desativar` | `desativar 11144477735 motivo "agressão ao porteiro"` | Pessoa ou veículo não entra (RN12) | admin |
| `reativar` | `reativar placa ABC1D23` | Encerra a desativação | admin |
| `situacao` | `situacao 52998224725` | Dentro ou fora, desde quando, carro, desativado | todos |
| `dentro` | `dentro visitante` | Quem está no campus agora | todos |
| `buscar` | `buscar ABC1D23 de 01/10/2026 ate 15/10/2026` | Procura no histórico (tipo e período opcionais) | todos |
| `pendentes` | `pendentes` | Saídas pendentes, tempo excedido, carro com o dono fora | todos |
| `ajuda` | `ajuda entrada` | Mostra a regra da gramática e os exemplos | todos |

Maiúsculas e acentos tanto faz (`SAÍDA`, `situação`, `até`) e os tipos
aceitam o plural (`visitantes`).

- **Léxico** (`lexico.py`): tokens COMANDO, PALAVRA_CHAVE, TIPO, PERIODO,
  CPF, NUMERO, PLACA (um **autômato finito** reconhece a placa antiga e a
  Mercosul), DATA, HORA, TEXTO, PALAVRA e FIM, cada um com a coluna. O
  campo pinta cada token a cada tecla; o erro fica vermelho e sublinhado.
- **Sintático** (`sintatico.py`): descida recursiva, um método por regra;
  a saída é uma árvore de `dataclasses`. Comando desconhecido recebe o
  "Você quis dizer…?" e o **Tab** corrige.
- **Semântico** (`simbolos.py`, `semantico.py`): a tabela de símbolos
  consulta pessoas, veículos, desativações, o usuário logado e os horários
  do dia; as checagens rodam na ordem, cada uma com a RN, e param no
  primeiro erro. Tipo diferente do cadastro é um **aviso** (pergunta antes).
- **Execução** (`executor.py`): o comando é **só outra porta** (RN46). Ele
  monta o mesmo registro do formulário e passa pelas mesmas funções e pelo
  mesmo `Banco`; quando falta o que o formulário perguntaria ("Vai entrar de
  carro?", "Com qual carro está saindo?", a senha do administrador), abre o
  **mesmo diálogo**. Um teste compara o banco do comando com o do
  formulário.
- **Erros por fase**, no console (recolhível, com as últimas respostas):

```
› saida placa AB12345
              ^^^^^^^
[Léxico] coluna 13: "AB12345" não é uma placa.
Dica: Formatos ABC1234 (antiga) ou ABC1D23 (Mercosul).
```

- **Modo didático** (interruptor ao lado do campo): a faixa Léxico ✓ →
  Sintático ✓ → Semântico ✗ → Execução — e as abas **Tokens**, **Árvore**
  (desenhada no Canvas, o nó com erro em vermelho), **Símbolos** e
  **Checagens**. Abre por cima da tabela e cabe no notebook 1366×670.
- **Tab** completa o comando, a palavra e o tipo, e troca um pedaço do nome
  pelo CPF da pessoa.
- **Privacidade:** para o porteiro, as respostas, o console e o modo
  didático mostram o CPF mascarado (`***.982.247-**`), mesmo digitado
  inteiro; o Tab escreve o CPF mascarado (o campo guarda o número só na
  memória). O texto dos comandos **não** é gravado no log nem no banco.
  Os comandos do administrador são recusados ao porteiro já na fase
  semântica (e o banco também recusa). A linha tem no máximo 200
  caracteres.

## Segurança e LGPD

O sistema guarda dados pessoais (nome, CPF, celular, placa e horários de
entrada e saída). Tudo fica no próprio computador, na **pasta de dados**:
`C:\ProgramData\Portaria` quando instalado; ao lado do programa no `.exe`
portátil ou rodando pelo código:

| Arquivo | O que tem |
|---|---|
| `portaria.db` (e, com o programa aberto, `portaria.db-wal` e `portaria.db-shm`) | O banco: pessoas, visitas, usuários (senha só como hash), histórico de ações, desativações (tabela `bloqueios`) e tentativas de login |
| `backups/portaria-AAAA-MM-DD.db` | Cópia do banco feita ao abrir o programa, uma por dia; ficam as 30 mais recentes |
| `backups/portaria-antes-vX-de-vN-....db` | Cópia feita antes de atualizar o banco para uma versão nova. **Não é apagada sozinha**: apague à mão quando a atualização estiver conferida |
| `portaria.log` (e `.1` a `.3`) | Só erros técnicos (até 3 × 1 MB). Não guarda CPF, celular nem senha |
| CSV exportado | Fica onde o administrador escolher no "Salvar como". Leva **CPF e celular completos** e a exportação fica no histórico |
| `registros_portaria.json.migrado` | Só se havia a versão 1: os registros antigos, em texto |

**Os backups têm tudo o que o banco tem**, inclusive os hashes de senha e os
registros que já foram excluídos no programa (um registro excluído hoje
continua nos backups diários por até 30 dias, e nos `portaria-antes-...` até
alguém apagá-los). Trate a pasta de backups com o mesmo cuidado do banco.

**Quem deve ter acesso** (recomendação para instalar na portaria):

- a pasta de dados e a pasta `backups` só com acesso da conta do Windows
  usada na portaria e do administrador (Propriedades → Segurança no
  Explorador de Arquivos); o porteiro não deve ser administrador do Windows;
- disco com **BitLocker** ligado, para os dados não serem lidos se o
  computador ou o disco for levado;
- de tempos em tempos, uma cópia da pasta `backups` em outro disco (pendrive
  ou HD externo guardado com o administrador): backup no mesmo disco não
  protege contra a falha do disco;
- CSV exportado: guardar em pasta restrita e apagar quando não for mais útil.

**Privacidade na tela:** o porteiro vê o CPF mascarado (`***.982.247-**`) nas
tabelas, na ficha da página Pessoas e na janela Corrigir (o lápis do campo
deixa digitar um CPF novo, sem mostrar o antigo). **Exceção:** em Pessoas →
"Registrar entrada", o CPF completo vai para o campo CPF da Entrada e saída,
porque é o dado necessário para registrar a entrada. O celular aparece
completo na ficha da pessoa (é o campo para corrigi-lo). O histórico de ações
grava os CPFs mascarados (o celular aparece completo quando uma correção o
altera).

**Como restaurar um backup** (ex.: o programa avisa que o banco está
danificado):

1. Feche o programa em todos os computadores que usam esse banco.
2. Na pasta de dados, renomeie `portaria.db` para
   `portaria-danificado.db` (não apague: pode ser útil depois). Se existirem
   `portaria.db-wal` e `portaria.db-shm`, renomeie também (ex.:
   `portaria-danificado.db-wal`), para não serem misturados com a cópia.
3. Abra a pasta `backups` e escolha o backup mais recente que estava bom
   (o nome tem a data: `portaria-2026-10-20.db`).
4. Copie esse arquivo para a pasta de dados e renomeie a cópia para
   `portaria.db`.
5. Abra o programa e confira os registros. O que foi feito depois da data do
   backup não está nele e precisa ser lançado de novo.

**Limitações conhecidas** (registradas para as próximas versões):

- O banco e os backups não são criptografados pelo programa: quem consegue
  abrir a pasta lê os dados. A proteção depende das permissões do Windows e
  do BitLocker (item S02 da auditoria de segurança).
- O histórico de ações não tem trava contra alteração: quem abre o arquivo do
  banco com outra ferramenta consegue apagar linhas sem deixar rastro (S10).
- Ainda não há prazo de retenção nem "anonimizar pessoa": excluir uma visita
  não apaga o cadastro da pessoa, e os dados ficam até alguém excluí-los.

## Estrutura da pasta

| Caminho | Conteúdo |
|---|---|
| `portaria_universidade.py` | Ponto de entrada (é o arquivo que se executa) e a relação com Compiladores |
| `portaria/validacao.py` | Regras de CPF, celular, placa, nome, datas e verificações semânticas |
| `portaria/horarios.py` | Regras de horário de acesso (funções puras): funcionamento, feriados, eventos, categorias, exceções, situação da visita |
| `portaria/dados.py` | Banco SQLite (pessoas, visitas, usuários, histórico, desativações) e migrações |
| `portaria/consultas.py` | Busca e números do Painel (versão em Python, usada nos testes) |
| `portaria/usuarios.py` | Perfis, permissões, login, troca de senha e códigos de recuperação |
| `portaria/senhas.py` | Hash das senhas (PBKDF2), bloqueio progressivo e códigos de recuperação (sem importar o banco) |
| `portaria/veiculos.py` | Quem pode retirar o veículo (RN35) e lotação do estacionamento (RN37) — funções puras |
| `portaria/excecoes.py` | Relatório de exceções: tipo, pessoa, quem autorizou e quem operava (funções puras) |
| `portaria/backup.py` | Backup do banco e exportação para CSV |
| `portaria/estilo.py` | Tokens do design: cores dos temas claro e escuro, fontes, ícones, medidas, escala (DPI), estilos ttk e contraste |
| `portaria/componentes.py` | Peças de tela: cartão, botões, campo, faixa de aviso, placa, tabela, diálogo |
| `portaria/mensagens.py` | Caixas de mensagem e "Salvar como" |
| `portaria/interface.py` | Janela principal, barra lateral, sessão e o contrato que as telas usam |
| `portaria/tela_login.py` | Login, primeiro acesso, "Defina sua senha", "Esqueci a senha" e a guarita travada |
| `portaria/tela_recuperacao.py` | Códigos de recuperação (mostrar uma vez, imprimir, gerar novos) |
| `portaria/tela_cadastro.py` | Entrada e saída (formulário, Movimento) |
| `portaria/tela_comando.py` | Campo Comando: realce, Tab, console e modo didático (2.4) |
| `portaria/linguagem/` | A linguagem de comandos: `lexico.py`, `gramatica.py`, `sintatico.py`, `simbolos.py`, `semantico.py`, `executor.py`, `interpretador.py`, `erros.py` |
| `docs/GRAMATICA_DA_LINGUAGEM.md` | A gramática da linguagem (tokens, EBNF, checagens, erros por fase) |
| `portaria/tela_pessoas.py` | Pessoas: Ativas, Desativadas e Veículos desativados, ficha, Nova pessoa e Editar |
| `portaria/tela_dashboard.py` | Painel e exportação; `graficos.py` desenha as barras |
| `portaria/tela_usuarios.py` | Usuários, atividade e o relatório de exceções (só administrador) |
| `portaria/tela_edicao.py` | Janela "Corrigir registro" com o histórico do registro |
| `portaria/tela_autorizacao.py` | Diálogo "Autorização do administrador" (exceções de horário) |
| `portaria/tela_configuracoes.py` | Configurações dos horários de acesso (só administrador) |
| `portaria/tela_veiculo.py` | Perguntas "Saiu com o veículo?", "Saiu junto?" e "Vai levar o carro?" |
| `portaria/seletor_data.py` | Calendário e relógio dos campos de data e hora (Canvas) |
| `portaria/tela_senha.py` | Janela "Trocar minha senha" |
| `docs/design/` | Proposta de design, protótipo e prints (antes, protótipo e final) |
| `docs/CRUD.md` | Matriz CRUD: cada página e aba × Criar, Ler, Atualizar e Excluir |
| `docs/revisao/` | Relatórios das revisões de segurança, código e backend (antes e depois da reforma) |
| `docs/qa/` | Relatórios dos dois testes de QA, a situação de cada achado (`CORRECOES.md`) e prints antes/depois |
| `build_exe.py` | Gera o `dist/Portaria.exe` com o PyInstaller |
| `build_instalador.py` e `instalador/portaria.iss` | Geram o instalador com o Inno Setup |
| `portaria/caminhos.py` | Escolhe a pasta de dados (instalado × portátil) |
| `assets/` | Ícone do programa (`portaria.ico`) e o script que o gera |
| `tests/` | Testes automatizados |
| `IDEIAS_E_MELHORIAS.md` | Análise do código, falhas encontradas e roteiro de melhorias |
| `docs/IDEIAS_NOVAS.md` | Sugestões de novas funcionalidades e o esboço da linha de comando (Compiladores) |
| `docs/qa/` | Relatórios dos testes de QA e a lista de correções |
| `versoes/v1_original/` | Cópia da versão feita no Claude gratuito, para comparar antes × depois |
| `material_aula/` | Slides da disciplina (enunciado do exercício e guia de documentação) — local, fora do git |
| `entrega/` | O que vai para a faculdade (Word com capa, prints, .exe) — local, fora do git |

## Versões

**2.4** (29/10/2026) — Compiladores: a linguagem de comandos (sem mudança
no banco):

- a **Saída rápida** virou o campo **Comando** (F2 ou Ctrl+K), no mesmo
  lugar; só o CPF ou só a placa continuam dando a saída;
- 13 comandos, inclusive o **CRUD de pessoas** (cadastrar, editar,
  excluir, desativar, reativar), com léxico, gramática **LL(1)**,
  sintático por descida recursiva, tabela de símbolos e semântico com a RN
  de cada checagem (`portaria/linguagem/`);
- o comando é só outra porta (**RN46**): as mesmas regras e gravações do
  formulário e os mesmos diálogos quando falta algo;
- **modo didático** (RF32) com as fases, tokens, árvore, símbolos e
  checagens; realce, **Tab** e "você quis dizer…?";
- CPF mascarado para o porteiro em tudo o que a linguagem mostra; o texto
  dos comandos não é gravado;
- casos de teste CT-01 a CT-68 (seção "Linguagem de comandos") e 919 testes
  automatizados; prints `docs/design/final/v24_*`.

**2.3** (29/10/2026) — pessoas, desativação e CRUD (sem mudança no banco: a
desativação usa a tabela de bloqueios que já existia, e nada se perde):

- **Entrada e saída**: o Movimento sobe; o título fica numa linha própria
  (com o status ao lado) e as subabas **Pessoas | Veículos** logo embaixo,
  com a busca e os botões à direita (4 linhas visíveis no notebook);
- **placa**: sem o recorte branco nos cantos no tema escuro (o fundo segue o
  cartão e a troca de tema) e o desenho da **placa antiga** (cinza, NEY-4829);
- **desativação** (RN12): a página Bloqueios virou as subabas
  **Desativadas** e **Veículos desativados** de Pessoas; pessoa ou veículo
  desativado não entra (o banco confere de novo); só o administrador
  desativa e reativa;
- **Nova pessoa** (RN41), **Editar** e **Excluir pessoa** (RN42: só o
  administrador, só sem visitas);
- **CRUD em todas as abas** (`docs/CRUD.md`): editar usuário (RN43),
  feriado e evento (RN44) e a validade de quem pode retirar o carro (RN45);
- casos de teste CT-01 a CT-53 e 834 testes automatizados; prints
  `docs/design/final/v23_*`.

**2.2.1** (22/10/2026) — ajustes para a entrega da disciplina (sem mudança no banco):

- a confirmação da entrada usa o texto do enunciado do exercício, na faixa
  verde do rodapé (sem caixa para fechar): **"Registro cadastrado com
  sucesso! Entrada de Ana às 14:30."** (com "(exceção autorizada por …)"
  quando houve autorização do administrador);
- **casos de teste documentados** CT-01 a CT-47 (`python -m tests.relatorio`,
  veja [Testes automatizados](#testes-automatizados)), com dois testes de tela
  novos (nome e CPF vazios, CPF inválido);
- prints novos da versão atual (`docs/design/final/v221_*`).

**2.2** (21/10/2026) — veículo e acesso do administrador (banco na versão 11,
numa migração só, com backup antes):

- **V0**: o banco confere a senha do administrador sozinho (hash em
  `portaria/senhas.py`, contador da estação);
- **S07 / RN39**: troca de senha obrigatória no primeiro login e senha nunca
  igual ao login, também na redefinição pelo administrador;
- **B3 / RN38**: códigos de recuperação do administrador, "Esqueci a senha",
  "Gerar novos códigos" e o aviso de um administrador só;
- **V1 / RN35**: quem pode retirar o veículo sem o dono e sem senha;
- **V2 / RN36**: alerta de carro esquecido antes do fechamento;
- **V3 / RN37**: lotação do estacionamento (vagas, aviso ou bloqueio);
- **B4**: "Ausentar" (cadeado ou Ctrl+L), com troca de turno;
- **V4**: relatório de exceções com filtros e CSV;
- **V5 / RN40**: dois carros da mesma pessoa (aviso na entrada, limite de 2,
  "Com qual carro está saindo?");
- 782 testes automatizados.

**2.1** (21/10/2026) — regras de horário de acesso, veículos, modo noturno e instalador:

- funcionamento por dia da semana, feriados e eventos; janela de entrada e
  permanência máxima por categoria; limite geral de 24 h;
- exceções com **autorização do administrador** (login e senha, justificativa,
  histórico "Exceção autorizada"), conferidas também no banco;
- situação **Tempo excedido** e **Saída pendente**, faixas de alerta, aviso
  antes de fechar, **Encerrar o dia** e o número novo no Painel;
- página **Configurações**; banco na versão 7 (migração com backup antes);
- correção: a visita com entrada em outro dia e saída hoje sumia do Movimento;
- rodada 2 (depois dos testes do aluno): pendência no fechamento com
  **tolerância** só para professor e funcionário; ninguém entra depois de
  fechar; **lançamento retroativo** de 3 h, e de dia já fechado só com senha;
  campo Entrada que acompanha o relógio; **veículo com estadia própria**
  (sair a pé, voltar, sair de carro, lista de veículos, veículo pendente);
  histórico de visitas e ordenação na página Pessoas; **calendário e
  relógio** nos campos de data; banco na versão 8;
- rodada 3: **modo noturno** (Claro, Escuro ou Seguir o Windows, escolhido
  por usuário no menu da conta e trocado sem fechar o programa); banco na
  versão 9;
- rodada 4: correções dos dois testes de QA (`docs/qa/CORRECOES.md`): evento
  soma ao dia, retroativo com o campus fechado, prazo da categoria; placa só
  tira o carro, dois carros, exclusão que mantém o carro; corridas entre
  estações; busca do CPF para o porteiro; importação validada; diálogo de
  autorização que não trava o login; telas no notebook 1366×670; banco na
  versão 10;
- rodada 5: **o veículo só sai com o dono** (sem ele, só com a senha de um
  administrador, registrada como "Veículo saiu sem o dono", conferida também
  no banco); pergunta **"de carro ou a pé?"** na entrada de quem tem placa
  cadastrada; **tamanho máximo em todos os campos** (digitação, colagem,
  validação e banco); "Redefinir senha" num diálogo no estilo Guarita;
- **instalador do Windows** (Inno Setup): programa em Arquivos de Programas,
  dados em `C:\ProgramData\Portaria`, atalhos e desinstalador; o `.exe`
  portátil continua disponível;
- 649 testes automatizados.

**2.0** (20/10/2026) — reforma completa, feita com um time de agentes de IA
(design, segurança, código, backend) e revisada antes de publicar:

- visual novo "Guarita" (barra lateral, login com relógio, texto nítido em
  telas com escala, layout compacto para notebook);
- tela principal rápida mesmo com anos de dados (só o movimento do dia + quem
  está no campus; a busca procura no histórico inteiro);
- regras garantidas também no banco (uma entrada aberta por CPF, permissões),
  migrações seguras com backup antes;
- backup diário automático, exportação para CSV e log de erros;
- login mais seguro (tentativas gravadas, espera crescente, senha mínima de 8,
  troca da própria senha, sessão que expira por inatividade);
- privacidade: CPF mascarado para o porteiro e no histórico;
- correções achadas na revisão final (ação após a sessão expirar, notebook
  1366×768, saída em linha desatualizada, falha de backup);
- executável `Portaria.exe` e 359 testes automatizados.

Relatórios e decisões: `docs/revisao/` e `docs/design/PROPOSTA_DESIGN.md`.

**1.x** (16 a 17/10/2026) — organização da versão feita no Claude gratuito:
módulos e testes, SQLite, login, cadastro de pessoas, saída rápida, correção de
registro e lista de bloqueio. A versão original, de um arquivo só, está em
`versoes/v1_original/`.
