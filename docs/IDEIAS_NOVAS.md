# Ideias novas — Sistema de Portaria (visão de produto)

Base da análise: cópia congelada do projeto (README, `IDEIAS_E_MELHORIAS.md`,
`docs/design/PROPOSTA_DESIGN.md`, prints em `docs/design/final/`, relatórios em
`docs/revisao/`) e o README do projeto "Analisador Pedidos Lanchonete" (voz e
léxico reaproveitáveis). Nada no projeto foi alterado.

**Como ler:**
- **Esforço:** P = até meio dia · M = 1 a 2 dias · G = 3 dias ou mais (com ajuda de IA, contando os testes).
- **Valor:** para a portaria de verdade **e** para a nota/apresentação.
- **pip/internet:** "não" quer dizer só a biblioteca padrão e funciona offline.
- ⭐ = entra nas 5 recomendadas (seção final).
- Itens que **já estavam** no `IDEIAS_E_MELHORIAS.md` aparecem com a marca *(já registrada)* e uma proposta mais concreta. O resto é novo.

O sistema já cobre muito bem a regra do dia a dia: CPF, horários, exceções,
veículos, bloqueios. As lacunas que sobram são de três tipos: (1) o que a
guarita faz e o sistema ainda não vê (visitante com anfitrião, crachá,
ocorrências, evacuação), (2) o que a disciplina pede e ainda está só no
comentário do código (uma linguagem de verdade com as três fases) e (3) o que
a entrega pede (casos de teste no Word, dados para mostrar).

---

## A. Operação real da portaria

### A1. Visitante completo: anfitrião, setor, motivo e crachá numerado ⭐ *(já registrada, proposta concreta)*
- **Problema:** hoje um visitante entra e o sistema não sabe *quem ele veio ver*. Exemplo: às 15:00 a coordenação liga perguntando "o fornecedor da gráfica já chegou?"; o porteiro precisa lembrar de cabeça. E o crachá de visitante 07 sumiu: ninguém sabe quem ficou com ele.
- **Na tela:** quando o Tipo é Visitante, Prestador ou Entregador, aparece uma terceira linha no formulário: **Vai até** (nome/setor, com sugestões do que já foi digitado antes), **Motivo** (lista curta: reunião, entrega, manutenção, evento, outro) e **Crachá** (número; o campo sugere o primeiro livre). No Movimento, coluna "Crachá". Na saída, a pergunta "Devolveu o crachá 07?" (Sim / Não, ficou pendente). Faixa no topo: "2 crachás não devolvidos hoje". Configurações ganha "Crachás: 1 a 30".
- **Esforço:** M · **Valor:** alto (é o que toda portaria real tem; vira RF novo no Word).
- **Dependências/riscos:** migração do banco (v9) com colunas opcionais na visita; não pode deixar o fluxo de aluno mais lento (os campos só aparecem para as categorias externas). Cuidado com o layout compacto 1366×768: a linha extra precisa caber (talvez recolher a ficha do veículo como já é feito).
- **pip/internet:** não.

### A2. Visitantes esperados (agenda do dia)
- **Problema:** o professor avisa por WhatsApp "amanhã às 14h vem a banca externa, 3 pessoas". O porteiro anota num papel; na hora, digita tudo do zero. E se a banca chega às 18:30 (fora da janela do visitante), precisa chamar o administrador, que já tinha concordado na véspera.
- **Na tela:** página **Esperados** (ou aba dentro de Pessoas): administrador cadastra nome, CPF (opcional), data, horário previsto, anfitrião e, se quiser, uma **autorização antecipada** de horário com justificativa. Na Entrada e saída, faixa discreta "3 esperados hoje · próximo 14:00 Banca TCC". Ao digitar um CPF esperado, a faixa verde diz "Esperado por Coord. Engenharia às 14:00" e os campos do A1 já vêm preenchidos; a exceção de horário passa direto porque já foi autorizada (e o histórico grava "autorização prévia de X").
- **Esforço:** M · **Valor:** alto (menos interrupção do administrador; demonstra bem as regras de exceção).
- **Dependências:** A1 (anfitrião/setor). Risco: a autorização antecipada precisa ter validade (só naquela data) e ser conferida também no banco, como a de 24 h.
- **pip/internet:** não.

### A3. Passagem de turno e livro de ocorrências
- **Problema:** o porteiro da noite chega e o da tarde diz de boca: "o portão 2 está emperrado, tem uma mochila achada no armário, o carro ABC-1D23 vai dormir aqui com autorização". Metade se perde. Em portaria real existe o "livro de ocorrências" em papel.
- **Na tela:** botão **Ocorrência** (ícone de caderno) na barra superior: texto livre, categoria (manutenção, achados e perdidos, segurança, aviso), opcionalmente ligada a uma pessoa/placa. Ao clicar em **Sair**, aparece o **Resumo do turno**: entradas e saídas feitas por este usuário, quem continua no campus, pendências, ocorrências do turno e um campo "Recado para o próximo turno". O próximo login mostra o recado num cartão até alguém marcar "Lido".
- **Esforço:** M · **Valor:** alto (operação) / médio (nota).
- **Dependências/riscos:** tabela nova `ocorrencias`; texto livre pode receber dado pessoal: mascarar CPF no texto com a função que já existe (`mascarar_cpfs_no_texto`).
- **pip/internet:** não.

### A4. Lista de evacuação (quem está no campus agora)
- **Problema:** alarme de incêndio às 19:40. A brigada pergunta "quantas pessoas e quem está lá dentro?". Hoje dá para ver a tabela, mas não há uma lista pronta para imprimir ou levar no celular, por tipo e com os veículos.
- **Na tela:** atalho **F12 / botão "Evacuação"** em qualquer página: abre a lista de todos no campus agrupada por tipo (com contagem), crachá, anfitrião e os carros no estacionamento, com a hora em letras grandes ("Situação às 19:40 — 214 pessoas"). Botões: **Imprimir** (HTML aberto no navegador) e **Marcar presentes** (check em cada nome no ponto de encontro; quem ficou sem check aparece em vermelho no fim).
- **Esforço:** P (a lista) · M (com a marcação no ponto de encontro) · **Valor:** alto (é a pergunta mais séria que se faz a uma portaria; impressiona numa apresentação).
- **Riscos:** a lista impressa tem dados pessoais (nome); mostrar CPF mascarado e lembrar de descartar. Se o PC da guarita estiver fora do ar, a lista não existe: ver A6 sobre contingência.
- **pip/internet:** não (`webbrowser` + HTML).

### A5. Encomendas recebidas na portaria
- **Problema:** chega uma caixa dos Correios para o Laboratório de Química. O porteiro guarda e anota no caderno; três dias depois ninguém sabe quem retirou.
- **Na tela:** página **Encomendas**: registrar (destinatário/setor, remetente, código de rastreio opcional, foto não), lista "Aguardando retirada (4)", e **Entregar** pede o nome de quem retirou (ou o CPF de alguém cadastrado: o preenchimento automático já existe).
- **Esforço:** M · **Valor:** médio.
- **Riscos:** amplia o escopo; vale só se sobrar tempo. Mostra bem a reutilização dos componentes (tabela, faixa, campo de CPF).
- **pip/internet:** não.

### A6. Passe temporário e "liberar uma vez" *(já registrada, proposta concreta)*
- **Problema:** professor substituto dá aula no sábado às 13:30 por um mês; a cada sábado o porteiro chama o administrador. Ou uma pessoa bloqueada precisa entrar uma única vez para uma audiência acompanhada.
- **Na tela:** na ficha da pessoa (Pessoas), administrador clica em **Criar passe**: tipo do passe (janela especial de horário · liberar o bloqueio uma vez), validade (de/até), dias da semana, justificativa. A faixa da Entrada mostra "Passe válido até 30/11 (sábados 13:00–18:00)". Liberação única some depois do uso. Tudo no histórico.
- **Esforço:** M · **Valor:** médio.
- **Dependências:** reutiliza o motor de exceções de `horarios.py`; o banco precisa conferir o passe (mesma ideia da checagem de 24 h).
- **pip/internet:** não.

---

## B. Segurança e LGPD

### B1. Retenção, anonimização e "relatório do titular" *(já registrada como S08; proposta concreta)*
- **Problema:** um ex-visitante pede, pela LGPD, para saber que dados o sistema tem dele e depois para apagá-los. Hoje não há como responder sem abrir o banco à mão, e as visitas de três anos atrás ficam para sempre.
- **Na tela:** em Configurações, seção **Privacidade**: "Guardar visitas identificadas por **12** meses" (depois disso o nome, CPF, celular e placa viram "Anonimizado", mas a visita continua contando no Painel). Na ficha da pessoa (admin): **Relatório do titular** (HTML com tudo o que existe sobre aquele CPF: cadastro, visitas, bloqueios, menções no histórico) e **Anonimizar a pedido** (justificativa obrigatória; não deixa se houver bloqueio ativo ou visita aberta).
- **Esforço:** M · **Valor:** alto (LGPD é ponto forte para qualquer banca; fecha uma limitação que o próprio README admite).
- **Riscos:** os backups diários guardam o dado por até 30 dias: documentar isso no Word ("a anonimização chega aos backups em até 30 dias"). Bloqueio precisa de exceção (interesse legítimo de segurança). Rodar a anonimização ao abrir o programa, numa transação, com teste de relógio fixo.
- **pip/internet:** não.

### B2. Histórico à prova de adulteração (cadeia de hashes) *(já registrada como S10; proposta concreta)*
- **Problema:** alguém com acesso ao PC abre o `portaria.db` num editor de SQLite e apaga a linha "Exceção autorizada por…". Hoje isso não deixa rastro.
- **Na tela:** cada linha do histórico guarda `hash = sha256(hash_anterior + conteúdo da linha)`. Em Usuários › Atividade, botão **Verificar integridade**: "OK — 3.412 eventos conferidos" ou "Quebra na sequência: o evento de 20/10 14:03 foi alterado ou removido". Primeira camada: triggers no SQLite que recusam `UPDATE`/`DELETE` no histórico.
- **Esforço:** M · **Valor:** médio (operação) / alto (apresentação: é a mesma ideia de um blockchain, explicável em 1 minuto).
- **Riscos:** quem tem o arquivo pode recalcular a cadeia inteira. Para dificultar, o "selo do dia" (último hash) vai também no nome/metadado do backup diário: adulterar exigiria refazer todos os backups. Ser honesto no Word sobre esse limite.
- **pip/internet:** não (`hashlib`).

### B3. Recuperação de acesso do único administrador *(já registrada; proposta concreta)*
- **Problema:** a única pessoa administradora esquece a senha numa sexta à noite. Ninguém consegue mais autorizar exceção, encerrar o dia nem criar usuário. Hoje a saída é mexer no banco.
- **Na tela:** no primeiro acesso, depois de criar o admin, a tela **Códigos de recuperação** mostra 8 códigos de uso único (ex.: `K7QM-2F9X`) com "Imprimir" e a caixa "Guardei em lugar seguro". No login, link **Esqueci a senha** → código + nova senha. O código usado é queimado e fica no histórico. Além disso, faixa no Painel do admin: "Só existe 1 administrador ativo. Crie um segundo."
- **Esforço:** P/M · **Valor:** alto (é um risco real de travar a operação).
- **Riscos:** os códigos são guardados só como hash (PBKDF2, como a senha); contam como tentativa de login para o bloqueio progressivo.
- **pip/internet:** não (`secrets`, `hashlib`).

### B4. "Ausentar": travar a guarita na hora
- **Problema:** o porteiro sai da cabine para abrir o portão do caminhão. A sessão só expira em 10 min; nesse tempo qualquer um que passe pelo balcão vê CPFs e pode registrar coisas no nome dele.
- **Na tela:** botão **Ausentar** (ícone de cadeado, atalho Ctrl+L) no rodapé da barra lateral: cobre a janela com o painel vermelho do login ("Guarita travada por Carla às 14:32"), sem perder o que estava no formulário. Desbloqueia com a senha do mesmo usuário; outro usuário entrando = troca de turno (descarta o formulário e oferece o Resumo do turno do A3).
- **Esforço:** P · **Valor:** médio.
- **Riscos:** reaproveitar o mesmo caminho do "sessão expirada" para não abrir brecha nos diálogos que ficam abertos (o bug B1/N01 da revisão mostra que esse caminho é delicado).
- **pip/internet:** não.

---

## C. Relatórios e dados

### C1. Painel com período e horário de pico ⭐ *(já registrada; proposta concreta)*
- **Problema:** a segurança do campus quer saber "precisamos de 2 porteiros às 18h30 nas segundas?". O Painel só mostra hoje e os últimos 7 dias.
- **Na tela:** no topo do Painel, seletor **Hoje · 7 dias · 30 dias · Período…** (o calendário desenhado já existe). Os cartões passam a valer para o período. Gráfico novo: **mapa de calor dia da semana × hora** (7 × 17 quadradinhos desenhados no Canvas, tons do mesmo cinza-azulado do Guarita, o pico com o vermelho da marca e o número). Segundo gráfico novo: **permanência média por tipo** (barras horizontais, como as de hoje).
- **Esforço:** M · **Valor:** alto (decisão real de escala de porteiros; é o gráfico que mais "enche os olhos" num slide).
- **Dependências:** consultas agregadas no SQL (o padrão já está em `consultas`/`dados`); dados suficientes para o gráfico aparecer bonito → F2.
- **pip/internet:** não.

### C2. Relatórios imprimíveis (HTML → PDF pelo navegador) *(PDF já registrado)*
- **Problema:** a direção pede "o relatório de acessos de setembro" e "a lista de exceções autorizadas no mês" em PDF para arquivar. O CSV exige Excel e não é um documento.
- **Na tela:** botão **Relatório** no Painel com modelos: *Movimento do período*, *Exceções autorizadas no período*, *Resumo do turno*, *Lista de evacuação* (A4), *Relatório do titular* (B1). O programa gera um HTML com o visual Guarita (cabeçalho, data, quem gerou, CPF mascarado) e abre no navegador; o usuário usa **Imprimir → Salvar como PDF**.
- **Esforço:** M (um gerador com `string.Template` serve para todos) · **Valor:** alto.
- **pip/internet:** não. *Alternativas:* gerar o PDF direto com `reportlab` **exige pip**; escrever um PDF simples "à mão" (texto e linhas, fonte Helvetica, ~150 linhas de Python) é possível só com a biblioteca padrão, mas acentos e quebra de página dão trabalho: só se a professora exigir `.pdf` gerado pelo próprio programa.
- **Riscos:** o arquivo HTML fica na pasta temporária com dados pessoais: apagar ao fechar o programa e registrar a geração no histórico, como no CSV.

### C3. Auditoria da operação (para o administrador)
- **Problema:** o administrador desconfia que um porteiro "esquece" de dar saída e deixa tudo para o Encerrar o dia, ou que pede exceção demais. Hoje os dados existem no histórico, mas espalhados.
- **Na tela:** em Usuários, aba **Indicadores**: por usuário e período — entradas, saídas, correções, exceções pedidas, saídas automáticas que caíram no turno dele, entradas recusadas por bloqueio. Linha clicável abre os eventos.
- **Esforço:** M · **Valor:** médio.
- **Riscos:** tom de "vigilância de funcionário": mostrar como qualidade da operação, sem ranking.
- **pip/internet:** não.

---

## D. Experiência de uso e acessibilidade

### D1. Retorno sonoro (o porteiro olha para a pessoa, não para a tela)
- **Problema:** com fila no portão, o porteiro digita o CPF olhando para o visitante. A faixa vermelha "CPF bloqueado" só funciona se ele olhar para a tela.
- **Na tela:** sons curtos e diferentes: "entrada registrada" (um bipe agudo), "atenção" (dois bipes: tempo excedido, esperado fora do horário), "bloqueado/recusado" (som grave longo). Liga/desliga e volume no menu da conta. Nada muda visualmente; o som complementa a cor (e ajuda quem tem dificuldade para distinguir verde/vermelho).
- **Esforço:** P · **Valor:** médio/alto.
- **Riscos:** `winsound` só existe no Windows (o projeto já é Windows, RNF04); nos testes, trocar o tocador por um falso.
- **pip/internet:** não (`winsound`).

### D2. Digitação mais rápida e legível: máscara, atalhos à vista e tamanho do texto *(máscara já registrada)*
- **Problema:** o porteiro digita `52998224725` e não percebe que trocou dois dígitos; o porteiro novo não sabe que existe F2; um porteiro de 60 anos acha o texto pequeno no notebook.
- **Na tela:** (a) **máscara enquanto digita** no CPF (`529.982.247-25`), celular e placa, aceitando colar com ou sem pontos; (b) **F1 = cola de atalhos**: um cartão por cima da tela com Enter, F2, Ctrl+L, F12, Ctrl+K…; (c) **A− / A+** no menu da conta (90 %, 100 %, 115 %, 130 %), guardado por usuário — os tokens de `estilo.py` já calculam a escala, então é multiplicar.
- **Esforço:** M · **Valor:** médio.
- **Riscos:** máscara mexe na posição do cursor (clássico bug de Tk); o tamanho grande precisa de teste no 1366×768.
- **pip/internet:** não.

### D3. Modo treinamento / demonstração ⭐
- **Problema:** (1) porteiro novo precisa aprender sem sujar o banco real; (2) **na apresentação**, projetar o banco real seria expor dados pessoais (LGPD), e um banco vazio deixa o Painel sem graça.
- **Na tela:** no login, link discreto **Modo treinamento** (ou `Portaria.exe --treino`). Abre um banco separado (`treinamento.db`, refeito a cada abertura a partir do gerador F2) com 3 meses de movimento fictício. Uma faixa laranja fixa no topo de todas as páginas: "MODO TREINAMENTO — nada aqui é real". Opcional: um roteiro guiado de 6 passos ("Registre a entrada do visitante… agora tente a placa bloqueada…").
- **Esforço:** P/M (com o F2 pronto) · **Valor:** alto (resolve a apresentação e o treino de verdade).
- **Riscos:** nunca pode apontar para o `portaria.db` (caminho fixo e teste que garante); backups não rodam no modo treino.
- **pip/internet:** não.

---

## E. Ligação com Compiladores (nota e apresentação)

### E1. Linha de comando da portaria ⭐ *(feita na versão 2.4: `docs/GRAMATICA_DA_LINGUAGEM.md`)*
- **Problema:** em horário de pico (07:00 e 18:30), o porteiro experiente quer registrar sem tirar a mão do teclado: `entrada 52998224725 visitante placa ABC1D23` e Enter. Para a disciplina, é o lugar onde léxico, sintático e semântico deixam de ser comentário no código e viram funcionalidade.
- **Na tela:** a "Saída rápida (F2)" vira **Comando (F2 ou Ctrl+K)**: o mesmo campo no topo, que continua aceitando só um CPF ou placa (vira `saida` implícito, então nada do que já funciona quebra). A resposta aparece abaixo, num pequeno console com as últimas linhas. Detalhes, gramática e erros na seção 2.
- **Esforço:** G · **Valor:** alto (é o diferencial da disciplina).
- **Riscos:** o maior é a linguagem ter **regras próprias** diferentes do formulário. Regra de ouro: a árvore do comando é traduzida para o **mesmo** objeto que o formulário monta e passa pelas **mesmas** funções (`validacao.validar`, `horarios.excecoes_*`, `Banco`). A linguagem é só outra porta de entrada.
- **pip/internet:** não (`re`, `dataclasses`, `difflib`).

### E2. Modo didático: tokens, árvore, tabela de símbolos e checagens na tela ⭐ *(feita na 2.4)*
- **Problema:** a professora precisa *ver* as fases acontecendo. Ler o comentário no `portaria_universidade.py` não tem o mesmo efeito de digitar um comando errado e ver em qual fase ele parou.
- **Na tela:** interruptor **Modo didático** ao lado do campo de comando. Liga um painel lateral com uma faixa de fases (Léxico ✓ → Sintático ✓ → Semântico ✗ → Execução —) e quatro abas: **Tokens** (tabela lexema/tipo/coluna e "fichas" coloridas), **Árvore** (desenhada no Canvas), **Símbolos** (as entradas consultadas: pessoa, veículo, bloqueio, usuário logado) e **Checagens** (lista com ✓/✗ e a regra de negócio: "RN05 um CPF não pode ter duas entradas abertas ✗"). Mockup na seção 2.5.
- **Esforço:** M (depois do E1) · **Valor:** alto (é o que mais impressiona numa banca de Compiladores).
- **pip/internet:** não.

### E3. Lote de comandos: lançar o "caderno" de quando o sistema caiu
- **Problema:** faltou luz das 14:00 às 16:00; o porteiro anotou 23 entradas e saídas num caderno. Hoje ele precisa lançar uma por uma no formulário, com a senha do administrador em cada retroativo.
- **Na tela:** em Entrada e saída (admin), **Lançar lote**: uma caixa de texto (ou "Abrir .txt") onde se digita uma linha por movimento: `entrada 52998224725 visitante as 14:05`. Botão **Analisar** mostra **todos** os erros de uma vez, com linha e coluna ("linha 7, col 22: esperado HORA depois de 'as'"), como um compilador. Só com zero erros aparece **Executar lote**, que pede a senha do administrador **uma vez** (RN24) e grava tudo numa única transação (ou tudo, ou nada).
- **Esforço:** M (depois do E1) · **Valor:** alto (é o caso de contingência real e é exatamente "compilar um programa": recuperação de erro em modo pânico, relatório de erros, não gerar código com erro).
- **Riscos:** lote não pode virar porta para burlar as regras: cada linha passa pelas mesmas checagens; a ordem cronológica importa (o semântico simula o estado: "linha 9: saída de Pedro, mas a entrada dele só aparece na linha 12").
- **pip/internet:** não.

### E4. Realce de sintaxe, autocompletar e "você quis dizer…?" *(feita na 2.4)*
- **Problema:** o comando digitado errado gera frustração; o porteiro não lembra se é `saida` ou `saída`, nem o CPF inteiro de quem quer dar saída.
- **Na tela:** o campo de comando colore os pedaços **enquanto se digita** (comando em tinta escura, CPF em azul, placa em fundo de placa, tipo em verde, texto entre aspas em cinza, erro léxico sublinhado em vermelho): é o analisador léxico rodando a cada tecla. **Tab** completa comando, tipo e — a partir da tabela de símbolos — nome → CPF ("maria so" + Tab → lista "Mariana Souza (no campus)"). Comando desconhecido traz sugestão por semelhança, como na Lanchonete.
- **Esforço:** M · **Valor:** médio (operação) / alto (demonstração do léxico em tempo real).
- **Riscos:** Tk `Entry` não colore trechos: usar um `Text` de uma linha com *tags*. Para o porteiro, o autocompletar deve mostrar o CPF mascarado.
- **pip/internet:** não (`difflib`).

### E5. Comando por voz *(já registrada; proposta com cuidado de LGPD)*
- **Problema:** porteiro com as mãos ocupadas (segurando o portão, recebendo uma caixa) quer perguntar "quantos estão no campus?" ou "o carro ABC-1D23 está aí?".
- **Na tela:** botão de microfone ao lado do campo de comando (o anel animado da Lanchonete). O texto reconhecido cai **no mesmo campo**, passa pelo mesmo léxico/sintático/semântico e aparece no modo didático; a resposta pode ser falada.
- **Esforço:** M (reaproveitando `voice.py` da Lanchonete) · **Valor:** médio (operação) / alto (efeito "uau" na apresentação).
- **pip/internet:** **sim, no caminho da Lanchonete**: `SpeechRecognition` + `PyAudio` (pip) e reconhecimento pelo Google (internet). Isso **quebra o requisito de só biblioteca padrão** se for obrigatório, então: import opcional (`try/except ImportError`), botão escondido quando não houver as bibliotecas.
  - *Alternativa sem pip:* **falar** as respostas é possível só com a biblioteca padrão chamando a voz do Windows por `subprocess` + PowerShell (`System.Speech`, offline, voz pt-BR "Maria" costuma vir no Windows em português). **Reconhecer** fala sem pip pelo mesmo caminho é arriscado: o reconhecedor de desktop do Windows raramente tem pt-BR.
- **Riscos (importante):** mandar a voz do porteiro dizendo um CPF para o Google é **enviar dado pessoal a terceiro** — contradiz o RNF05 ("dados ficam só no computador"). Proposta: por voz, só comandos **sem dado pessoal** (`dentro`, `pendentes`, `situacao placa …`); CPF por voz fica bloqueado com a mensagem "Por privacidade, CPF só pelo teclado". Isso vira um bom slide sobre LGPD. Barulho da portaria e números ditados ("cinco dois nove…") também erram muito.

### E6. Busca com linguagem de consulta → SQL (a fase de geração de código)
- **Problema:** a busca de hoje é um texto livre. O administrador quer "visitantes com placa começando em ABC desde 01/10" e não consegue.
- **Na tela:** a caixa "Buscar no histórico" passa a aceitar filtros: `tipo:visitante placa:ABC* desde:01/10/2026 nome:"maria"`. Texto sem filtro continua funcionando como hoje. No modo didático aparece o **SQL gerado**: `WHERE tipo = ? AND placa LIKE ? AND entrada >= ? AND nome LIKE ?` com os parâmetros ao lado.
- **Esforço:** M · **Valor:** médio (operação) / alto (nota: cobre a **síntese/geração de código**, a fase que E1 não cobre, e a **checagem de tipos**: `desde:abc` → "o filtro 'desde' espera uma DATA").
- **Riscos:** gerar sempre SQL **parametrizado** (nunca concatenar texto: dá para mostrar na apresentação por que isso evita *SQL injection*); campos permitidos numa lista fixa (porteiro não filtra por CPF completo).
- **pip/internet:** não.

---

## F. Qualidade de engenharia

### F1. Casos de teste prontos para o Word ⭐
- **Problema:** a entrega exige "casos de teste, inclusive negativos, com passou/falhou". O projeto tem 508 testes `unittest`, mas o Word precisa de uma tabela legível; copiar à mão é demorado e desatualiza.
- **Na tela (do desenvolvedor):** `python -m tests.relatorio` roda a suíte e gera `relatorio_testes.html` e `.csv` com: ID (CT-001…), requisito ligado (RF/RN), descrição em português, tipo (positivo/negativo), entrada, resultado esperado, **Passou/Falhou** e a data. A descrição vem da docstring de cada teste (padrão: `"""CT-045 | RN05 | negativo | CPF já no campus não entra de novo"""`). Também gera a **matriz de rastreabilidade** RN × testes. Os testes da linguagem (E1) entram como uma seção própria: léxicos, sintáticos e semânticos.
- **Esforço:** P/M (o script) + tempo de escrever docstrings nos testes mais importantes (não precisa ser nos 508; 40–60 bem escolhidos bastam para o Word) · **Valor:** alto (é item obrigatório da entrega).
- **pip/internet:** não (`unittest.TextTestResult` personalizado).

### F2. Gerador de dados fictícios (seed)
- **Problema:** prints do Word, Painel da apresentação, teste de desempenho e modo treinamento precisam de meses de dados realistas, sem nenhum dado real.
- **Como funciona:** `python -m portaria.demo --meses 3 --banco demo.db`: nomes de uma lista fictícia, CPFs válidos gerados pelo algoritmo do dígito verificador, placas antigas e Mercosul, horários com picos em 07:00, 12:00 e 18:30, alguns tempos excedidos, exceções autorizadas, bloqueios e veículos pendentes. Semente fixa (`random.seed`) para o resultado ser sempre o mesmo (prints reproduzíveis).
- **Esforço:** P/M · **Valor:** alto (suporta D3, C1 e os prints).
- **Riscos:** os dados precisam passar pelas regras (usar as funções do `Banco`, não `INSERT` direto), senão o Painel mostra coisas impossíveis.
- **pip/internet:** não.

### F3. Um comando de verificação antes de cada entrega
- **Problema:** antes de entregar/apresentar, é fácil esquecer um passo: rodar os testes, gerar o `.exe` novo, conferir que não ficou nome/RA no repositório, atualizar o número de testes no README.
- **Como funciona:** `python verificar.py` em sequência: `unittest` (com o total), `compileall`, procura de termos proibidos no que vai para o git (lista lida de um arquivo local fora do git), confere a versão do esquema do banco e a migração em banco temporário, gera o `.exe` (se o PyInstaller existir) e abre o `.exe` em modo `--treino` por 5 s para ver se não quebra. Termina com "Pronto para entregar" ou a lista do que falhou. Junto: a limpeza já listada (`ControleTentativas` não usado, listagens antigas, `__getattr__`/`NOMES_DO_CADASTRO`).
- **Esforço:** P · **Valor:** médio.
- **pip/internet:** não para o script; o `.exe` **exige pip** (`pyinstaller`), como já acontece hoje. *Opcional:* GitHub Actions rodando os testes a cada push (internet; sem custo para repositório público).

---

## 1. Recomendação: as 5 primeiras, em ordem

| # | Ideia | Esforço | Por quê, nessa ordem |
|---|---|---|---|
| 1 | **E1 + E2 — Linha de comando com modo didático** | G + M | É o que liga o sistema à disciplina de forma visível e testável. Hoje a relação com Compiladores está num comentário; com isso, a professora digita um comando errado e **vê** em que fase ele parou. Também ajuda a portaria de verdade (pico das 07:00 e 18:30). Fazer primeiro porque é o mais longo e o mais valioso para a nota. |
| 2 | **F1 — Casos de teste prontos para o Word** | P/M | A entrega exige casos de teste com passou/falhou. Já existem 508 testes: falta só transformá-los em documento. Encaixar logo depois do E1 para os testes léxicos/sintáticos/semânticos já entrarem no relatório. |
| 3 | **A1 — Visitante com anfitrião, setor, motivo e crachá** | M | É a lacuna funcional mais óbvia para quem conhece portaria ("quem ele veio ver?", "cadê o crachá 07?"). Rende RF e RN novos no Word e um teste negativo fácil de mostrar (crachá já em uso). |
| 4 | **F2 + D3 — Dados fictícios e Modo treinamento** | P/M | Resolve a apresentação: dados ricos sem expor ninguém (bom argumento de LGPD), Painel cheio, demonstração repetível. Na portaria real, serve para treinar o porteiro novo. |
| 5 | **C1 — Painel com período e horário de pico** | M | Com os dados do item 4, o mapa de calor dia × hora é o gráfico mais bonito do sistema e responde a uma pergunta real de gestão ("quantos porteiros às 18:30?"). Fecha a apresentação com dados. |

**Ganhos rápidos se sobrar meio dia:** A4 (lista de evacuação, P, impacto forte na fala), D1 (sons, P), B3 (códigos de recuperação do admin, P/M). **Se sobrar mais:** E3 (lote do caderno) é o passo seguinte natural do E1 e o mais "compilador" de todos; E6 mostra a geração de código. **Voz (E5)** só depois, opcional e com a regra "CPF não se dita".

---

## 2. Esboço da linha de comando da portaria

> Este é o esboço original. A linguagem implementada na 2.4 (com o CRUD de
> pessoas, desativar no lugar de bloquear e `sem carro`) está em
> `docs/GRAMATICA_DA_LINGUAGEM.md`.

### 2.1 Comandos

| Comando | Exemplo | Faz |
|---|---|---|
| `entrada` | `entrada 529.982.247-25 visitante placa ABC1D23` | Registra a entrada (mesmas regras do formulário) |
| `saida` | `saida 52998224725` · `saida placa ABC1D23` · `saida 52998224725 sem veiculo` | Dá a saída da pessoa ou do carro; `sem veiculo` = saiu a pé, o carro fica |
| *(implícito)* | `52998224725` · `ABC1D23` | Só CPF ou placa = `saida` (o comportamento da Saída rápida de hoje) |
| `dentro` | `dentro` · `dentro visitante` | Lista quem está no campus (filtra por tipo) |
| `buscar` | `buscar maria visitante semana` · `buscar ABC1D23 de 01/10/2026 ate 15/10/2026` | Procura no histórico |
| `situacao` | `situacao 52998224725` · `situacao placa ABC1D23` | Mostra a ficha: está dentro? desde quando? bloqueado? carro? |
| `pendentes` | `pendentes` | Saídas e veículos pendentes, tempo excedido |
| `bloquear` | `bloquear placa ABC1D23 motivo "furto no estacionamento"` | Cria bloqueio (só administrador) |
| `ajuda` | `ajuda` · `ajuda entrada` | Mostra a gramática do comando, gerada da própria tabela de palavras |

Opções da `entrada`: `placa <PLACA>`, `nome "<texto>"`, `cel <NUMERO>`, `visita "<anfitrião/setor>"` (com A1), `crachá <NUMERO>` (com A1), `as <HORA>` ou `em <DATA> <HORA>` (lançamento retroativo, com a regra RN24).
Palavras aceitam com ou sem acento e maiúsculas (`saída`, `SAIDA`, `situação`); tipos aceitam plural (`visitantes`).

### 2.2 Tokens (análise léxica)

| Token | Padrão (expressão regular) | Exemplos |
|---|---|---|
| `COMANDO` | palavra da lista: entrada, saida, dentro, buscar, situacao, pendentes, bloquear, ajuda | `entrada`, `Saída` |
| `PALAVRA_CHAVE` | placa, nome, cel, visita, cracha, motivo, sem, veiculo, de, ate, as, em | `placa`, `até` |
| `TIPO` | aluno, professor, funcionario, visitante, entregador, prestador (e plurais) | `visitante` |
| `PERIODO` | hoje, ontem, semana, mes | `hoje` |
| `CPF` | `\d{3}\.\d{3}\.\d{3}-\d{2}` (com pontuação: sem ambiguidade) | `529.982.247-25` |
| `NUMERO` | `\d+` | `52998224725`, `31987651234`, `07` |
| `PLACA` | `[A-Z]{3}-?\d[A-Z0-9]\d{2}` (antiga e Mercosul) | `ABC1D23`, `ABC-1234` |
| `DATA` | `\d{2}/\d{2}/\d{4}` | `01/10/2026` |
| `HORA` | `\d{2}:\d{2}` | `14:05` |
| `TEXTO` | `"[^"]*"` | `"furto no estacionamento"` |
| `PALAVRA` | `[a-záéíóúâêôãõç]+` que não é nenhuma das anteriores | `maria` (termo de busca) |
| `FIM` | fim da linha | — |

Ponto didático: um CPF sem pontuação (`52998224725`) e um celular (`31987651234`) são **o mesmo token** `NUMERO` de 11 dígitos. O léxico não sabe a diferença; quem decide é o **sintático**, pela posição (depois de `entrada` é CPF, depois de `cel` é celular). Se possível, mostrar também o **autômato finito** da PLACA no Word (estados q0→q1→q2→q3 letras, q4 dígito, q5 letra-ou-dígito, q6-q7 dígitos).

### 2.3 Gramática (EBNF)

```
linha      = comando FIM ;
comando    = entrada | saida | dentro | buscar | situacao
           | pendentes | bloquear | ajuda | implicito ;

entrada    = "entrada" cpf [ TIPO ] { opcao } ;
opcao      = "placa" PLACA
           | "nome" TEXTO
           | "cel" NUMERO
           | "visita" TEXTO
           | "cracha" NUMERO
           | "as" HORA
           | "em" DATA HORA ;

saida      = "saida" alvo [ "sem" "veiculo" ] [ "as" HORA ] ;
implicito  = cpf | PLACA ;                    (* = saida *)
alvo       = cpf | "placa" PLACA ;
cpf        = CPF | NUMERO ;

dentro     = "dentro" [ TIPO ] ;
buscar     = "buscar" termo [ TIPO ] [ periodo ] ;
termo      = TEXTO | PALAVRA | cpf | PLACA ;
periodo    = PERIODO | "de" DATA [ "ate" DATA ] ;
situacao   = "situacao" alvo ;
pendentes  = "pendentes" ;
bloquear   = "bloquear" alvo "motivo" TEXTO ;
ajuda      = "ajuda" [ COMANDO ] ;
```

Para o lote (E3): `programa = { linha } ;` — cada linha é analisada sozinha; um erro descarta só aquela linha (recuperação em **modo pânico**: pula até o próximo `FIM`) e a análise continua para mostrar todos os erros de uma vez.

**Analisador:** descida recursiva (uma função por regra: `_entrada()`, `_saida()`, `_alvo()`…). A gramática é **LL(1)**: cada comando começa com uma palavra diferente, e cada opção também, então olhar um token à frente basta para decidir a regra — bom ponto para citar na apresentação (conjuntos FIRST disjuntos). A saída é uma **árvore** de `dataclasses` (`ComandoEntrada(cpf, tipo, opcoes)`, `ComandoSaida(alvo, sem_veiculo)`…).

**Tabela de símbolos:** pessoas (CPF → nome, tipo, situação), veículos (placa → estadia aberta?), bloqueios ativos, o usuário logado e o perfil dele, as categorias e os horários do dia (de `horarios.py`). O semântico só **consulta**; quem grava é o executor, pelos mesmos métodos do `Banco`.

**Organização sugerida:** `portaria/linguagem/lexico.py`, `sintatico.py`, `semantico.py`, `executor.py`, `tela_comando.py` + `tests/test_linguagem.py` (dezenas de casos: cada exemplo da tabela abaixo vira um teste e uma linha do relatório F1).

### 2.4 Erros, por fase, com a mensagem mostrada

Formato: a linha digitada com `^` embaixo da posição do erro, a fase entre colchetes e uma dica.

**Léxicos** (o texto tem um "pedaço" que não é palavra da linguagem):

| Digitado | Mensagem |
|---|---|
| `entrada 529.982.247-25 visitante @casa` | **[Léxico] coluna 34:** o símbolo `@` não pertence à linguagem. |
| `bloquear placa ABC1D23 motivo "furto` | **[Léxico] coluna 31:** texto sem aspas de fechamento. Feche com `"`. |
| `saida placa AB12345` | **[Léxico] coluna 13:** `AB12345` não é uma placa. Formatos: ABC1234 ou ABC1D23. |
| `buscar maria de 32/13/2026` | **[Léxico] coluna 17:** `32/13/2026` parece uma data, mas o dia 32 e o mês 13 não existem. |

**Sintáticos** (cada pedaço é válido, mas a ordem está errada ou falta algo):

| Digitado | Mensagem |
|---|---|
| `visitante entrada 52998224725` | **[Sintático] posição 1:** esperado um comando (entrada, saida, buscar…), encontrado o tipo `visitante`. Dica: o comando vem primeiro. |
| `entrda 52998224725 aluno` | **[Sintático] posição 1:** comando desconhecido `entrda`. Você quis dizer **entrada**? |
| `entrada placa ABC1D23` | **[Sintático] posição 2:** depois de `entrada` vem o CPF; encontrado a palavra `placa`. |
| `saida placa` | **[Sintático] fim da linha:** esperado a PLACA depois de `placa`, mas o comando acabou. |
| `buscar maria de 01/10/2026 ate` | **[Sintático] fim da linha:** esperado uma DATA depois de `ate`. |
| `bloquear 52998224725 "briga"` | **[Sintático] posição 3:** esperado `motivo` antes do texto. Ex.: `bloquear 52998224725 motivo "briga"`. |

**Semânticos** (a frase está bem escrita, mas não faz sentido diante dos dados, do relógio ou de quem está logado):

| Digitado | Mensagem |
|---|---|
| `entrada 12345678900 aluno` | **[Semântico]** o CPF 123.456.789-00 tem 11 dígitos, mas os dígitos verificadores não conferem (RN06). |
| `entrada 52998224725 visitante placa ABC1D23 placa XYZ9876` | **[Semântico]** a placa foi informada duas vezes (como declarar a mesma variável duas vezes). |
| `entrada 11144477735` *(CPF novo, sem tipo nem nome)* | **[Semântico]** CPF não cadastrado: informe o tipo e o nome. Ex.: `entrada 111.444.777-35 visitante nome "Bruno Almeida" cel 31987651234`. |
| `entrada 39053344705` *(já está dentro)* | **[Semântico]** Mariana Souza está no campus desde 18:14. Um CPF não pode ter duas entradas abertas (RN05). Para dar a saída: `saida 39053344705`. |
| `saida 86288366757` *(não está dentro)* | **[Semântico]** Lúcia Martins não está no campus (saiu hoje às 18:34). Saída sem entrada aberta (RN03). |
| `entrada 11144477735 visitante placa QWE1E34` *(placa bloqueada)* | **[Semântico]** a placa QWE-1E34 está bloqueada: "furto no estacionamento" (RN12). Entrada recusada e registrada no histórico. |
| `entrada 11144477735 visitante` *(às 19:10)* | **[Semântico]** visitante só entra das 08:00 às 18:00 (RN17). É uma exceção: **[Pedir autorização do administrador]** (abre o mesmo diálogo do formulário). |
| `entrada 52998224725 prestador` *(cadastro diz Aluno)* | **[Semântico — aviso]** o cadastro diz Aluno e o comando diz Prestador. Registrar como Prestador? **[Sim] [Não]** (como um compilador que avisa de conversão de tipo, mas deixa seguir). |
| `bloquear placa ABC1D23 motivo "teste"` *(porteiro logado)* | **[Semântico]** só o administrador cria bloqueios (RN12). |
| `buscar maria de 15/10/2026 ate 01/10/2026` | **[Semântico]** o período termina antes de começar. |
| `entrada 52998224725 aluno em 18/10/2026 08:00` | **[Semântico]** lançamento de um dia que já fechou: só com a senha de um administrador (RN24). **[Digitar senha do administrador]** |

Detalhe de privacidade: para o porteiro, toda resposta do console e o modo didático mostram o **CPF mascarado** (`***.982.247-**`), mesmo que ele tenha digitado o número completo; o texto dos comandos **não** é gravado em log nem no banco (o histórico continua recebendo só os eventos normais, já mascarados).

### 2.5 Como aparece na tela

O campo "Saída rápida (F2)" do topo vira o campo de comando (mesma posição, mesma tecla). Com o **Modo didático** desligado, só aparece a resposta numa linha abaixo do campo e um console recolhível com as últimas 5 linhas. Ligado, abre um painel à direita (no notebook 1366×768, abre como janela por cima da tabela):

```
┌ Comando  (F2 · Ctrl+K) ────────────────────────────────────────────┐ [● Modo didático]
│ entrada 111.444.777-35 visitante placa QWE1E34                     │
└────────────────────────────────────────────────────────────────────┘
  ✗ A placa QWE-1E34 está bloqueada: "furto no estacionamento" (RN12).

┌ Análise do comando ───────────────────────────────────────────────────────┐
│  Léxico ✓  ──▶  Sintático ✓  ──▶  Semântico ✗  ──▶  Execução —          │
│                                                                            │
│  [Tokens]  Árvore   Símbolos   Checagens                                   │
│  ┌──────┬────────────────┬───────────────┬────────┐                        │
│  │  #   │ Lexema         │ Token         │ Coluna │                        │
│  ├──────┼────────────────┼───────────────┼────────┤                        │
│  │  1   │ entrada        │ COMANDO       │ 1      │                        │
│  │  2   │ 111.444.777-35 │ CPF           │ 9      │                        │
│  │  3   │ visitante      │ TIPO          │ 24     │                        │
│  │  4   │ placa          │ PALAVRA_CHAVE │ 34     │                        │
│  │  5   │ QWE1E34        │ PLACA         │ 40     │                        │
│  │  6   │                │ FIM           │ 47     │                        │
│  └──────┴────────────────┴───────────────┴────────┘                        │
└────────────────────────────────────────────────────────────────────────────┘
```

Aba **Árvore** (desenhada no Canvas, nós arredondados no estilo Guarita, o nó com problema em vermelho):

```
                    ComandoEntrada
           ┌──────────┼───────────┬─────────────┐
       "entrada"     cpf         tipo         opção
                      │           │         ┌────┴────┐
              111.444.777-35  visitante  "placa"  QWE1E34  ✗ bloqueada
```

Aba **Símbolos**: as linhas da tabela de símbolos que o semântico consultou (`CPF 111.444.777-35 → Bruno Almeida · Visitante · fora do campus`; `Placa QWE1E34 → BLOQUEADA desde 12/10`; `Usuário → carla · Porteiro`; `Hoje → quarta, 06:30–23:00; visitante 08:00–18:00`).

Aba **Checagens**: a lista na ordem em que roda, cada uma com a regra de negócio:
```
✓ CPF com dígitos verificadores válidos (RN06)
✓ Pessoa cadastrada (tabela de símbolos)
✓ Não está no campus (RN05)
✓ Visitante dentro da janela 08:00–18:00 (RN17)
✗ Placa bloqueada (RN12)  → para aqui; nada é gravado
```

Cores das fichas de token (mesma paleta do Guarita, cor só quando importa): comando em tinta escura, CPF/NUMERO em azul, PLACA na moldura da placa Mercosul já desenhada, TIPO em verde, TEXTO em cinza, erro em vermelho com sublinhado ondulado.

### 2.6 Roteiro de 3 minutos para a apresentação (no Modo treinamento)

1. `entrada 529.982.247-25 visitante placa ABC1D23` → tudo ✓, mostra tokens e árvore; a linha aparece no Movimento.
2. `entrada 529.982.247-25 visitante @casa` → para no **léxico**.
3. `visitante entrada 52998224725` → para no **sintático**.
4. `entrada 52998224725 aluno` → para no **semântico**: "já está no campus" (frase perfeita, sem sentido no contexto).
5. `52998224725` (sem comando) → saída implícita: mostra que a árvore ganhou um nó `saida` que ninguém digitou.
6. (Se o E6 estiver pronto) `tipo:visitante placa:ABC*` na busca → mostra o **SQL gerado**.
