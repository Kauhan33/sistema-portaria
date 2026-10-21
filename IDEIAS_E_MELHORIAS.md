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

Ordem pensada para cada etapa já deixar algo entregável.

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

### Etapa 4 — Diferencial ligado a Compiladores ⭐
**Linha de comando da portaria**: um campo onde o porteiro digita comandos curtos,
analisados como uma mini linguagem:

```
entrada 529.982.247-25 visitante placa ABC1D23
saida 52998224725
saida placa ABC1D23
buscar visitante hoje
dentro
```

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
  pasta `entrega/`.
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

## 4. Rascunho de requisitos para o Word

**RF**: RF01 cadastrar entrada · RF02 registrar saída (botão, duplo clique,
saída rápida por CPF/placa) · RF03 consultar/buscar histórico · RF04 excluir
registro (admin) · RF05 exibir Painel · RF06 login e primeiro acesso · RF07
exportar CSV (admin) · RF08 cadastro de pessoas com preenchimento automático ·
RF09 corrigir registro com histórico · RF10 lista de bloqueio · RF11 gerenciar
usuários (admin) · RF12 trocar a própria senha · RF13 backup diário automático ·
RF14 comando digitado (Etapa 4, futuro) · RF15 configurar os horários de
acesso: funcionamento, categorias, feriados e eventos (admin) · RF16 autorizar
exceção de horário (admin) · RF17 encerrar o dia (admin) · RF18 alertar tempo
excedido, saída pendente e fechamento próximo · RF19 registrar a entrada e a
saída do veículo separadas da pessoa (estacionamento) · RF20 ver o histórico
de visitas de cada pessoa · RF21 escolher datas e horas num calendário e
relógio.

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
RN12 CPF ou placa na lista de bloqueio não entra; só o administrador bloqueia e desbloqueia ·
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

## 5. Pendências registradas na revisão final (para a versão 2.1+)

Detalhes em `docs/revisao/REVISAO_FINAL_CODIGO.md` e `REVISAO_FINAL_SEGURANCA.md`.
- Histórico de ações com trava contra alteração (triggers/hash) — S10.
- Prazo de retenção e "anonimizar pessoa" (LGPD) — S08.
- Banco e backups sem criptografia: depende de permissões do Windows/BitLocker — S02.
- Troca de senha obrigatória no primeiro acesso; redefinição pelo admin recusar
  senha igual ao login — S07.
- ✅ Admin travado de propósito pelo diálogo de autorização — N04 (rodada 4:
  contador próprio da estação). Continua: o login normal do admin ainda pode
  ser travado por quem chuta a senha na tela de login (é o bloqueio por
  tentativas, de propósito); limite de tentativas na senha atual em "Trocar
  minha senha" — N09.
- Histórico gravado antes da 2.0 continua com CPF completo — B8.
- Limpeza de código para a apresentação: ControleTentativas (não usado pelas
  telas), listagens antigas do banco, o repasse `__getattr__`/NOMES_DO_CADASTRO.
