# Revisão de segurança — Sistema de Portaria

Data da revisão: 19/10/2026 · Escopo: `portaria/*.py`, `portaria_universidade.py`, `.gitignore`
Método: modelagem de ameaças (STRIDE), leitura de código e provas de conceito executadas
**fora** da pasta do projeto (banco temporário). Nenhum arquivo do projeto foi alterado.

## 1. Resumo

O código está acima da média em vários pontos: todas as consultas SQL são parametrizadas,
a senha usa PBKDF2 com sal e comparação em tempo constante, o login não revela quais
usuários existem, não há senha padrão e cada ação grava o histórico na mesma transação.
Também não há `eval`, `pickle`, `subprocess` nem dependências de terceiros.

Os problemas que contam de verdade são poucos:

1. **A regra RN12 (bloqueio) pode ser burlada pela tela "Corrigir"**: um CPF ou placa
   bloqueado entra no sistema se o porteiro registrar outro CPF e depois "corrigir" o
   registro. A prova de conceito confirmou o problema (seção 4, S01).
2. **O `portaria.db` é a única barreira real.** Ele fica ao lado do programa, sem
   criptografia e sem permissão de pasta. Quem copia o arquivo leva todos os CPFs e
   celulares. Quem consegue editá-lo vira administrador e apaga o histórico. E não
   existe backup.
3. **LGPD**: os dados pessoais ficam para sempre, também no histórico, e excluir um
   registro não apaga o CPF. Não há retenção, anonimização nem atendimento ao titular.

O resto é "seria bom": sessão sem tempo limite, bloqueio de tentativas só em memória,
política de senha fraca, permissões checadas só na tela e mensagens técnicas do SQLite.

## 2. Modelo de ameaças (curto)

**Ativos:** dados pessoais (nome, CPF, celular, placa, horários de entrada e saída, ou
seja, onde a pessoa estava), lista de bloqueio, hashes de senha, histórico de auditoria.

**Atores:**
| Ator | Acesso | Motivação típica |
|---|---|---|
| Porteiro (perfil `porteiro`) | Tela do app | Deixar entrar um conhecido bloqueado, apagar um erro, consultar o celular de alguém |
| Admin descuidado | Tela do app | Deixa a sessão aberta e reutiliza ou compartilha senha |
| Outra pessoa no computador da portaria | Conta do Windows e arquivos | Copiar o `.db` num pendrive, editar o banco com o "DB Browser for SQLite" |
| Ladrão ou descarte do PC | Disco | Ler o banco inteiro |

**Fronteiras de confiança:** (1) teclado → app (validação); (2) app → `portaria.db`
(nenhuma proteção: o arquivo é aberto direto); (3) o disco e a pasta do programa
(permissões do Windows).

**STRIDE resumido:**
| Categoria | Ameaça principal | Situação |
|---|---|---|
| Spoofing | Usar a sessão aberta de outra pessoa; adivinhar senha | Sem expiração por inatividade (S05); tentativas só em memória (S06) |
| Tampering | Burlar RN12 pela correção; editar o `.db` | **S01**, S02 |
| Repudiation | Apagar ou alterar o histórico; admin agir como porteiro | S10, S07 |
| Information disclosure | Copiar o `.db`; porteiro ver todo o histórico com CPF | **S02**, S08, S09 |
| Denial of service | Perder o banco (disco, arquivo corrompido, exclusão) | S03 |
| Elevation of privilege | Esvaziar `usuarios` → "Primeiro acesso" → novo admin | S02/S19 |

> Hipótese realista: o atacante mais provável é **interno** (porteiro ou alguém com acesso
> ao PC), não um hacker remoto. O app não abre portas de rede.

## 3. Provas de conceito executadas

Script em `scratchpad/time/seguranca/poc.py` (fora do projeto), com banco temporário:

| # | Teste | Resultado |
|---|---|---|
| 1 | Porteiro cadastra a entrada de um CPF bloqueado | Recusado (correto) |
| 2 | Porteiro cadastra um CPF livre e depois "Corrige" para o CPF bloqueado e a placa bloqueada | **Aceito**: a pessoa bloqueada consta "dentro" |
| 3 | `Banco.excluir([...], autor="paulo")` (porteiro) | **Aceito**: a camada de dados não checa o perfil |
| 4 | Senha digitada no campo "Usuário" na tela de login | **Gravada** no histórico como usuário do "Login recusado" |
| 5 | 5 erros de senha → 30 s; novo `ControleTentativas` (reabrir o app) | Bloqueio zerado |
| 6 | Nome com 100.000 letras; nome com letra cirílica (homóglifo) | Ambos aceitos |
| 7 | Login duplicado | Mensagem mostra `UNIQUE constraint failed: usuarios.login` |
| 8 | `DELETE FROM auditoria` e `DELETE FROM usuarios` com o sqlite3 | Histórico apagado sem rastro; o app volta ao "Primeiro acesso" |
| 9 | `PRAGMA foreign_keys` | 0 (chaves estrangeiras não são aplicadas) |

Os scripts `security_auditor.py` e `threat_modeler.py` da skill foram inspecionados. São
modelos vazios que não analisam nada (`findings = []`), por isso não foram usados como
evidência.

## 4. Achados

Severidade considerando o contexto (app desktop local, uso numa portaria real com LGPD).
Esforço: **P** = até 1 h · **M** = algumas horas · **G** = 1 dia ou mais.

| ID | Sev. | Arquivo:linha | Problema | Cenário concreto | Correção sugerida | Esf. |
|---|---|---|---|---|---|---|
| S01 | **Alta** | `tela_edicao.py:134-153`; `dados.py:280-324` | A correção de registro não chama `checar_bloqueio`: RN12 só é verificada em `interface.py:159-170` (cadastro). | O porteiro cadastra o amigo bloqueado com o CPF de outra pessoa (ou sem placa) e em seguida usa "Corrigir" para pôr o CPF e a placa verdadeiros. O registro fica válido e a pessoa bloqueada consta "dentro". Confirmado na PoC 2. | Em `JanelaEdicao.salvar`, após `validar`, carregar `listar_bloqueios()` e chamar `checar_bloqueio(novo, ativos)`, recusando e registrando "Correção recusada (bloqueio)". Melhor ainda: fazer a checagem também em `Banco.editar`/`Banco.inserir`, dentro da transação (consulta `bloqueios WHERE ativo=1`), para nenhum caminho escapar. Criar teste. | P |
| S02 | **Alta** | `portaria_universidade.py:30-38`; `dados.py:165` | `portaria.db` fica ao lado do .exe/.py, sem criptografia, sem permissão de pasta e sem nenhuma checagem de integridade. Toda a autorização (perfis, RN02, RN11, RN12) só vale dentro do app. | (a) Alguém copia `portaria.db` num pendrive e leva nome, CPF, celular, placa e horários de todos. (b) Um porteiro com o "DB Browser" faz `DELETE FROM usuarios`, reabre o app, cai no "Primeiro acesso" e vira admin (PoC 8). Ou então apaga o bloqueio, a exclusão ou o histórico. (c) Se a pasta do programa for gravável por todos, também dá para trocar o próprio .exe. | Guardar o banco em `%PROGRAMDATA%\Portaria\` (ou `%LOCALAPPDATA%` de uma conta Windows exclusiva da portaria), com ACL só para essa conta e para administradores (`icacls`). Ligar o **BitLocker** no disco (resolve o furto do PC sem mudar código). Instalar o programa em `Program Files` (somente leitura para usuários comuns). Documentar no README que o porteiro não pode ter acesso de administrador no Windows. A criptografia em nível de campo (SQLCipher ou `cryptography`) fica para depois, porque exige dependência externa. | M |
| S03 | Média | `dados.py` (inexistente) | Não há backup: falha de disco, arquivo corrompido ou exclusão acidental perde todo o histórico e o próprio controle de acesso. | O HD do PC da portaria queima: todos os registros, bloqueios e usuários somem, e ninguém consegue nem fazer login. | Backup automático ao abrir/fechar o app com `sqlite3.Connection.backup()` para outra pasta/unidade, mantendo N cópias com rotação. Mesmo cuidado com ACL e criptografia que o banco (o backup também é dado pessoal). Opção "Fazer backup agora" na aba de admin. | M |
| S04 | Média | `dados.py:261` (excluir), `280` (editar), `355` (bloquear), `365` (desbloquear), `404` (atualizar_pessoa), `439/447/454` (usuários) | As permissões (RN02, RN11, RN12, gestão de usuários e bloqueios) são checadas **só nas telas** (`interface.py:303`, `tela_edicao.py:144`, `tela_bloqueios.py:136`, `interface.py:499`). O `Banco` recebe só o login em texto (`autor`) e aceita qualquer operação. | Hoje o único caminho de abuso pela interface é o S01. Mas qualquer botão, atalho ou tela nova que chame `banco.excluir` esquece a regra (PoC 3). Com `autor=None`, o banco nem grava histórico (`dados.py:484`). | Passar o **usuário** (dict com perfil) para o `Banco` (ou para uma camada de serviço) e checar lá: `excluir`/`bloquear`/`desbloquear`/`criar_usuario`/`definir_*` exigem admin; `editar` aplica `pode_editar` com a entrada original **e** a nova. Tornar `autor` obrigatório (lançar erro se vazio). Os testes de dados passam a cobrir as recusas. | M |
| S05 | Média | `interface.py:124-142` | A sessão não expira por inatividade. | O admin entra no PC da portaria para criar um bloqueio e esquece de sair. O porteiro do turno seguinte passa a excluir registros e remover bloqueios como admin, e o histórico mostra o admin. | Timer com `janela.after()` reiniciado em `bind_all("<Any-KeyPress>")`/`<Motion>`; após X min sem uso (ex.: 10 min para admin, 30 min para porteiro) chama `sair()` com o evento "Sessão encerrada por inatividade". Fechar janelas `Toplevel` abertas. | P |
| S06 | Média | `usuarios.py:137-155`; `interface.py:61`; `tela_login.py:90-117` | O bloqueio por tentativas fica só em memória, é global (não por usuário), é fixo (30 s) e zera ao reiniciar o app. | Alguém no PC tenta senhas do admin: 5 tentativas, fecha e reabre o app, mais 5, e assim por diante, sem limite real. Com o mínimo de 6 caracteres (S07), senhas fracas caem. | Gravar `falhas` e `bloqueado_ate` por login numa tabela (ou colunas em `usuarios`, mais uma linha para logins inexistentes) e aplicar espera crescente (30 s, 1 min, 5 min…). Avisar o admin no histórico ("5 falhas para ana.admin"). Usar o relógio de parede (`time.time`) para persistir. | M |
| S07 | Média | `usuarios.py:17,61-66`; `tela_usuarios.py:182-205` | Senha mínima de 6 caracteres sem lista de senhas comuns. O usuário não troca a própria senha. O admin define e conhece a senha do porteiro, e não há troca obrigatória no primeiro login. | O admin cria o porteiro com "123456" e conhece essa senha. Se algo errado for feito "como paulo", não dá para provar quem foi (repúdio). Num banco copiado (S02), senhas de 6 letras minúsculas são quebradas offline em horas. | Mínimo de 8 caracteres e bloqueio de uma lista curta de senhas comuns (inclusive senha = login). Botão "Trocar minha senha" para todos os perfis (pede a senha atual). Coluna `trocar_senha=1` quando o admin cria ou redefine, forçando a troca no próximo login. | M |
| S08 | Média | `dados.py:272-274`, `322-324`; `consultas.py:16-24`; `interface.py:164-168`; `dados.py:261-274` | LGPD: nome, CPF e celular em texto puro também no **histórico** (exclusão, correção, entrada recusada). Excluir um registro não apaga a pessoa (`pessoas`) nem o CPF guardado no histórico. Não há prazo de retenção nem como anonimizar ou atender ao titular (art. 18). | Uma pessoa pede a exclusão dos dados dela. O admin exclui as visitas, mas o CPF continua em `pessoas` e em "Exclusão de registro … CPF 529…" para sempre. O banco cresce com anos de deslocamentos de terceiros sem finalidade. | (1) No histórico, gravar CPF mascarado (`***.982.247-**`) ou só o `pessoa_id`/`registro_id`. (2) Função de admin "Anonimizar pessoa": troca nome e CPF por pseudônimo nos registros, apaga a linha de `pessoas` e registra o evento sem dados pessoais. (3) Retenção configurável (ex.: apagar ou anonimizar visitas com mais de 12 meses, mantendo só contagens para o dashboard), rodada ao abrir o app. (4) Texto de aviso de privacidade no README (finalidade e base legal: segurança/legítimo interesse). | G |
| S09 | Média | `interface.py:426-434`; `tela_pessoas.py:131-140`; `consultas.py:27-42` | Minimização: o porteiro vê e busca CPF e celular **completos** de todas as visitas e pessoas desde o início, e não só de quem está no campus ou no turno. | Um porteiro procura o celular de uma aluna pelo nome e vê também todos os horários em que ela entrou e saiu nos últimos meses. | Para o perfil porteiro: mascarar CPF e celular na tabela (mostrar completo só no registro selecionado), limitar a lista padrão a "dentro agora + últimos N dias" e exigir admin para o histórico completo. A busca por CPF continua funcionando (compara o valor completo internamente). | M |
| S10 | Média | `dados.py:61-68`, `481-488`, `484` | O histórico (auditoria) não tem proteção de integridade: qualquer `DELETE`/`UPDATE` direto no arquivo apaga ou altera o rastro sem deixar sinal (PoC 8). `_evento` ignora a gravação quando `autor` vem vazio. | Depois de deixar entrar alguém bloqueado (S01), quem tem acesso ao arquivo apaga as linhas "Registro corrigido" e ninguém percebe. | (1) Triggers `BEFORE UPDATE/DELETE ON auditoria … RAISE(ABORT)` (evitam apagar por engano ou por código). (2) Encadeamento por hash: coluna `hash = sha256(hash_anterior + momento + usuario + acao + detalhe)` e um botão "Verificar histórico" na aba de admin, que mostra onde a corrente quebrou. (3) `autor` obrigatório. Não impede um atacante com o arquivo, mas **detecta** a adulteração, e isso basta para a auditoria. | M |
| S11 | Baixa | `tela_login.py:101-103` | O "Login recusado" grava no histórico exatamente o que foi digitado no campo Usuário. | O porteiro digita a senha no campo errado e ela aparece em texto puro na aba Usuários, para qualquer admin (PoC 4). | Gravar o login só se existir (`buscar_usuario` ≠ None) ou se casar com `REGEX_LOGIN`. Caso contrário, gravar "(login inexistente)". | P |
| S12 | Baixa | `dados.py:167`, `173`; `interface.py:88`, `98`; `tela_login.py:105` | A mensagem de erro mostra a exceção do SQLite ao usuário (`UNIQUE constraint failed: usuarios.login`, caminhos, `database is locked`). | Vaza nomes de tabelas e colunas e confunde o porteiro. É baixo num app local. | Mensagem amigável na tela e detalhe técnico num log local (`logging` num arquivo com rotação, sem dados pessoais). Tratar `IntegrityError` de login duplicado com mensagem própria. | P |
| S13 | Baixa | `validacao.py:42-47`, `195`; `tela_bloqueios.py:140`; `tela_login.py:95`; `tela_usuarios.py:144` | Não há limite de tamanho para nome, motivo do bloqueio e login digitado. `isalpha()` aceita qualquer letra Unicode (homóglifos cirílicos, PoC 6). | Um nome com 100 mil caracteres trava a tabela e incha o banco. "Аna Silva" com A cirílico parece igual a "Ana Silva" e engana a busca. | Limites: nome ≤ 100, motivo ≤ 200, login e senha ≤ 128 (também como `CHECK (length(...) <= N)` no esquema). Normalizar com `unicodedata.normalize("NFC")` e, se quiser, aceitar só letras latinas (`[A-Za-zÀ-ÿ' -]`). | P |
| S14 | Baixa | `dados.py:501-530`, `545-547` | Migração do JSON v1: os arquivos `.migrado` e `.danificado-*` ficam para sempre ao lado do programa, com CPF e celular em texto puro. Os registros importados não passam por `validar`/`checar_bloqueio` (só pelos CHECKs) e não geram evento no histórico. | Cópia esquecida dos dados pessoais fora do banco, sem controle algum. Registros com CPF inválido ou tipo inexistente entram no sistema. | Gerar o evento "Importação do JSON v1 (N registros, M ignorados)". Validar com `validar_campos`. Depois de confirmar com o admin, apagar o `.migrado` (ou movê-lo para a pasta protegida do backup). O `.gitignore` já cobre `registros_portaria*`, o que está correto. | P |
| S15 | Baixa | `usuarios.py:19`, `38-46` | PBKDF2-SHA256 com 200 mil iterações, abaixo da recomendação atual da OWASP (600 mil). Não há "rehash" ao entrar. | Só importa se o banco vazar (S02). Reduz o tempo de quebra offline. | `ITERACOES = 600_000`. Em `autenticar`, se o hash guardado tiver menos iterações, gerar um novo com a senha correta e chamar `definir_senha` (o formato já guarda as iterações, então a migração é transparente). | P |
| S16 | Baixa | `dados.py:165` | `PRAGMA foreign_keys` não é ligado, então os `REFERENCES` do esquema não valem (PoC 9). | `registros.pessoa_id` pode apontar para uma pessoa apagada sem erro. | `con.execute("PRAGMA foreign_keys = ON")` logo após conectar (antes, conferir se a migração não viola nada). | P |
| S17 | Baixa | `validacao.py:252`; `usuarios.py:115-118` | O cadastro aceita entrada retroativa sem limite, e a RN11 depende do relógio do Windows. | O porteiro cria uma "visita" de meses atrás (álibi). Fica registrado no histórico com a hora real, mas não é barrado. | Para o porteiro, limitar a entrada a no máximo 24 h no passado (mesma regra da RN11). Para mudar o relógio é preciso ser administrador do Windows, o que reforça o S02. | P |
| S18 | Baixa | `dados.py:404-411`; `tela_pessoas.py:170-187` | A alteração de dados de pessoa grava só "nome (pessoa #id)", sem o antes e depois. O porteiro altera qualquer pessoa, sem a janela de 24 h. | O celular de alguém é trocado e o histórico não diz qual era o anterior. | Reaproveitar `descrever_alteracoes` também para pessoas (com o CPF mascarado, ver S08). | P |
| S19 | Baixa | `tela_login.py:26`, `34`; `dados.py:416-418` | "Primeiro acesso" vale sempre que `usuarios` estiver vazia: quem abrir primeiro vira admin. | Instalação nova deixada aberta, ou a tabela esvaziada via S02. | Fazer o primeiro acesso logo na instalação. Opcional: exigir que o banco seja novo (`registros` vazia) para permitir o "Primeiro acesso"; se houver registros e não houver usuários, mostrar erro de integridade. | P |
| S20 | Baixa | `interface.py:124-132` | O perfil e o "ativo" são lidos só no login. Um usuário desativado ou rebaixado continua com a sessão aberta. | Pouco relevante num único PC. Importa se houver duas instâncias abertas. | Reconsultar `buscar_usuario` antes de ações de admin (barato) ou no timer de inatividade (S05). | P |

### Itens verificados e sem problema

- **SQL injection:** todas as consultas com dados de usuário usam `?`. As duas f-strings de
  SQL só recebem constantes: `dados.py:159` (`VERSAO_ESQUEMA`, um inteiro do código) e
  `dados.py:340-347` (`filtro` é um literal escolhido por um booleano).
- **Hash de senha:** sal aleatório de 16 bytes (`os.urandom`), formato com as iterações
  guardadas e `hmac.compare_digest` (`usuarios.py:28-46`).
- **Enumeração de usuários:** hash falso para login inexistente (`usuarios.py:51`, `87-89`),
  checagem de `ativo` só depois do hash e mensagem única "Usuário ou senha incorretos".
- **Sem senha padrão;** a senha é mascarada nos campos (`show="•"`).
- **Histórico na mesma transação** da operação (`dados.py:481-488`) e bloqueios
  removidos ficam guardados (não são apagados).
- **Dependências:** só biblioteca padrão, sem risco de supply chain. JSON lido com `json.load`
  (sem `pickle`/`eval`).
- **Git:** `.gitignore` exclui `*.db`, `registros_portaria*`, `entrega/` e `material_aula/`.

## 5. As 5 correções que eu faria primeiro

1. **S01: checar bloqueio na correção** (P). É o único furo de regra de negócio
   explorável pela própria tela. Colocar `checar_bloqueio` em `JanelaEdicao.salvar` e
   também dentro de `Banco.inserir`/`Banco.editar`, mais um teste para cada caminho.
2. **S02 + S03: proteger o arquivo e ter backup** (M). Mover o banco para
   `%PROGRAMDATA%\Portaria` com ACL restrita, recomendar o BitLocker no README e criar o
   backup automático via `sqlite3.backup()` com rotação. Isso resolve o maior risco real
   (vazamento ou perda de tudo).
3. **S05 + S06: sessão com tempo limite e tentativas persistentes por usuário** (P+M).
   O cenário "admin esqueceu logado" é o mais provável numa portaria.
4. **S04 + S10: autorização e histórico na camada de dados** (M). O `Banco` passa a
   receber o usuário e a checar o perfil, `autor` fica obrigatório, e a auditoria ganha
   triggers anti-DELETE/UPDATE e encadeamento por hash com o botão "Verificar histórico".
5. **S08 (primeira parte) + S11: tirar dados pessoais do histórico** (P–M). Mascarar o
   CPF nos detalhes de auditoria e não gravar o texto livre do login recusado. Em seguida,
   criar a função "Anonimizar pessoa" e a retenção configurável, para atender à LGPD.
