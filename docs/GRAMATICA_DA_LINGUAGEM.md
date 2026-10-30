# Linguagem de comandos da portaria (versão 2.4)

**Decisões do aluno (29/10/2026):**
- a linguagem tem os comandos do CRUD de Pessoas;
- quando falta um dado, o comando abre o mesmo diálogo do formulário;
- todos podem ligar o modo didático, que mostra o CPF mascarado;
- "a pé" se escreve `sem carro`.

**Versão 2.5:** uma pessoa pode ter mais de um carro (RN47). O `cadastrar`
aceita um `placa` por carro e o `editar` ganhou `sem placa X`, que tira um
carro do cadastro. A gramática continua LL(1): "sem" é a única opção do
`editar` que começa com essa palavra.

**Implementada na versão 2.4** (`portaria/linguagem/`): a seção 8 conta
como ficou. Um teste confere que a EBNF da seção 3 é a mesma do código
(`portaria/linguagem/gramatica.py`) e que ela é LL(1).

Esta é a proposta da linguagem da 2.4 (item E1 do plano). Ela atualiza o
esboço de `docs/IDEIAS_NOVAS.md`, seção 2, com o que mudou até a 2.3:
- bloquear virou desativar e reativar;
- Pessoas tem cadastro, edição e exclusão;
- placa antiga;
- dois carros da mesma pessoa.

**Regra de ouro:** o comando é só outra porta de entrada. Ele é traduzido para
o mesmo registro que o formulário monta e passa pelas mesmas funções:
`validacao`, `horarios` e `Banco`, com as mesmas regras RN01 a RN45. Quando o
formulário abriria um diálogo, o comando abre o mesmo diálogo, por exemplo:
- "De carro ou a pé?";
- "Com qual carro está saindo?";
- a autorização do administrador.

## 1. Comandos

A linguagem cobre o CRUD da pessoa e da visita (Criar, Ler, Atualizar e
Excluir), além das consultas da guarita.

| Comando | Exemplo | Faz | Quem |
|---|---|---|---|
| `entrada` | `entrada 529.982.247-25 aluno placa ABC1D23` | Registra a entrada (Criar visita) | todos |
| `saida` | `saida 52998224725` · `saida placa ABC1D23` · `saida 52998224725 sem carro` | Registra a saída da pessoa ou do carro | todos |
| *(implícito)* | `52998224725` · `ABC1D23` | Só o CPF ou só a placa equivale a `saida`, como na Saída rápida de hoje | todos |
| `cadastrar` | `cadastrar 111.444.777-35 visitante nome "Bruno Almeida" cel 31987651234` | Nova pessoa, sem entrada (RN41, o "Cadastrar" do enunciado) | todos |
| `editar` | `editar 11144477735 cel 31999990000 tipo professor` · `editar 11144477735 placa NEY4829 sem placa ABC1D23` | Muda nome, celular ou tipo; inclui (`placa`) ou tira (`sem placa`) carros (RN47, 2.5) | todos |
| `excluir` | `excluir 11144477735` | Exclui o cadastro de quem nunca teve visita (RN42) | admin |
| `desativar` | `desativar 11144477735 motivo "agressão ao porteiro"` · `desativar placa ABC1D23 motivo "..."` | Pessoa ou veículo desativado não entra (RN12) | admin |
| `reativar` | `reativar 11144477735` · `reativar placa ABC1D23` | Encerra a desativação (RN12) | admin |
| `situacao` | `situacao 52998224725` · `situacao placa ABC1D23` | Ficha resumida: dentro ou fora, desde quando, carro, desativado | todos |
| `dentro` | `dentro` · `dentro visitante` | Quem está no campus agora (pode filtrar por tipo) | todos |
| `buscar` | `buscar maria visitante semana` · `buscar ABC1D23 de 01/10/2026 ate 15/10/2026` | Procura no histórico | todos |
| `pendentes` | `pendentes` | Saídas pendentes, tempo excedido e carros com o dono fora | todos |
| `ajuda` | `ajuda` · `ajuda entrada` | Mostra a gramática, gerada da própria tabela de palavras | todos |

A linguagem aceita maiúsculas e minúsculas, com ou sem acento: `saída`,
`SAIDA`, `situação`. Os tipos também podem vir no plural (`visitantes`).

## 2. Tokens (análise léxica)

| Token | Padrão | Exemplos |
|---|---|---|
| `COMANDO` | entrada, saida, cadastrar, editar, excluir, desativar, reativar, situacao, dentro, buscar, pendentes, ajuda | `entrada`, `Saída` |
| `PALAVRA_CHAVE` | placa, nome, cel, tipo, motivo, sem, carro, as, em, de, ate | `placa`, `até` |
| `TIPO` | aluno, professor, funcionario, visitante, entregador, prestador (e plurais) | `prestador` = Prestador de serviço |
| `PERIODO` | hoje, ontem, semana, mes | `semana` |
| `CPF` | `\d{3}\.\d{3}\.\d{3}-\d{2}` | `529.982.247-25` |
| `NUMERO` | `\d+` | `52998224725`, `31987651234` |
| `PLACA` | `[A-Z]{3}-?\d[A-Z0-9]\d{2}` (antiga e Mercosul) | `ABC1D23`, `ABC-1234` |
| `DATA` | `\d{2}/\d{2}/\d{4}` | `01/10/2026` |
| `HORA` | `\d{2}:\d{2}` | `14:05` |
| `TEXTO` | `"[^"]*"` | `"Bruno Almeida"` |
| `PALAVRA` | letras que não são nenhuma das anteriores | `maria` (termo de busca) |
| `FIM` | fim da linha | — |

**Ponto didático:** um CPF sem pontuação e um celular são o mesmo token, um
`NUMERO` de 11 dígitos. Quem decide o que ele é é o analisador sintático, pela
posição: depois de `entrada` é CPF, depois de `cel` é celular. O Word vai
mostrar o autômato finito da PLACA.

## 3. Gramática (EBNF)

```
linha      = comando FIM ;
comando    = entrada | saida | implicito | cadastrar | editar | excluir
           | desativar | reativar | situacao | dentro | buscar
           | pendentes | ajuda ;

entrada    = "entrada" cpf [ TIPO ] { opcao_ent } ;
opcao_ent  = "placa" PLACA
           | "sem" "carro"                 (* a pé, mesmo com placa cadastrada *)
           | "nome" TEXTO
           | "cel" NUMERO
           | "as" HORA                     (* hoje, em outro horário *)
           | "em" DATA HORA ;              (* lançamento retroativo, RN24 *)

saida      = "saida" alvo { opcao_sai } ;
opcao_sai  = "placa" PLACA                 (* com qual carro, RN40 *)
           | "sem" "carro"                 (* sai a pé, o carro fica *)
           | "as" HORA ;
implicito  = cpf | PLACA ;                 (* = saida *)

cadastrar  = "cadastrar" cpf TIPO "nome" TEXTO "cel" NUMERO
             { "placa" PLACA } ;           (* até 5 carros, RN47 *)
editar     = "editar" cpf campo { campo } ;
campo      = "nome" TEXTO | "cel" NUMERO | "tipo" TIPO
           | "placa" PLACA                 (* inclui o carro, RN47 *)
           | "sem" "placa" PLACA ;         (* tira o carro do cadastro *)
excluir    = "excluir" cpf ;

desativar  = "desativar" alvo "motivo" TEXTO ;
reativar   = "reativar" alvo ;
situacao   = "situacao" alvo ;
dentro     = "dentro" [ TIPO ] ;
buscar     = "buscar" termo [ TIPO ] [ periodo ] ;
termo      = TEXTO | PALAVRA | cpf | PLACA ;
periodo    = PERIODO | "de" DATA [ "ate" DATA ] ;
pendentes  = "pendentes" ;
ajuda      = "ajuda" [ COMANDO ] ;

alvo       = cpf | "placa" PLACA ;
cpf        = CPF | NUMERO ;
```

**A gramática é LL(1).** Cada comando começa com uma palavra diferente, e cada
opção também. Por isso, olhar um token à frente basta para escolher a regra:
os conjuntos FIRST são disjuntos.

O analisador é uma descida recursiva, com uma função por regra (`_entrada()`,
`_saida()`, `_alvo()`…). A saída é uma árvore de `dataclasses`, como
`ComandoEntrada(cpf, tipo, opcoes)` e `ComandoSaida(alvo, opcoes)`.

## 4. Análise semântica (tabela de símbolos e checagens)

**Tabela de símbolos:**
- pessoas: CPF → nome, tipo, dentro ou fora, desativada;
- veículos: placa → estadia aberta, dono, desativado;
- o usuário logado e o perfil dele;
- as categorias e os horários do dia (`horarios.py`).

O semântico só consulta a tabela. Quem grava é o executor, pelos mesmos
métodos do `Banco`.

**Exemplos de checagem, cada uma com a sua regra:**
- CPF com dígitos verificadores válidos (RN06);
- placa no formato antigo ou Mercosul;
- celular com DDD válido;
- opção repetida, como dar a placa duas vezes ("variável declarada duas
  vezes");
- CPF novo sem tipo e nome: erro com um exemplo do comando completo;
- pessoa já no campus (RN05); saída sem entrada aberta (RN03);
- pessoa ou veículo desativado (RN12);
- horário da categoria (RN17) e retroativo (RN24): abrem a autorização do
  administrador;
- tipo diferente do cadastro: é um **aviso**, e o programa pergunta se pode
  seguir, como um compilador que avisa de uma conversão de tipo;
- comando só de administrador digitado pelo porteiro (RN02 e RN12).

## 5. Erros por fase

O console mostra a linha digitada com `^` embaixo da posição do erro, a fase
entre colchetes e uma dica.

- **[Léxico]:** símbolo fora da linguagem (`@`), texto sem aspas de fechamento,
  `AB12345` não é placa, `32/13/2026` não é data.
- **[Sintático]:**
  - comando fora do lugar (`visitante entrada ...`);
  - comando desconhecido, com "você quis dizer **entrada**?";
  - falta argumento (`saida placa` e a linha acaba);
  - falta `motivo` antes do texto.
- **[Semântico]:** as checagens da seção 4.

## 6. Privacidade

- Para o porteiro, as respostas do console e o modo didático mostram o CPF
  mascarado (`***.982.247-**`), mesmo que ele tenha digitado o número inteiro.
- O texto dos comandos não é gravado no log nem no banco. O histórico continua
  recebendo só os eventos normais.

## 7. O que fica para depois

- Lote de comandos (E3, "caderno de quando o sistema caiu").
- Comando por voz (E5).
- Busca traduzida para SQL (E6).
- Opções do visitante completo, `visita` e `cracha`, que entram com a 2.5 (A1).

## 8. Como ficou na implementação (2.4)

**Módulos** (`portaria/linguagem/`, só biblioteca padrão):

| Fase | Módulo | O que faz |
|---|---|---|
| Léxico | `lexico.py` | `tokenizar()` (tolerante, para o realce) e `analisar_lexico()` (para no 1º erro); `Token(tipo, lexema, coluna, valor)`; o autômato finito da placa em `TRANSICOES_PLACA` |
| Gramática | `gramatica.py` | o texto EBNF da seção 3, lido pelo próprio módulo; FIRST, FOLLOW e `conflitos_ll1()` (vazio = LL(1)); os exemplos do `ajuda` |
| Sintático | `sintatico.py` | `AnalisadorSintatico`, um método por regra (`linha`, `_comando`, `_entrada`, `_opcao_ent`...); árvore de `dataclasses` |
| Semântico | `simbolos.py` e `semantico.py` | a tabela de símbolos (só consulta o banco) e as checagens na ordem, cada uma com a regra |
| Execução | `executor.py` | grava pelos caminhos do formulário (`AbaCadastro.registrar_entrada`, `dar_saida`, `saida_do_carro`) e pelos mesmos métodos do `Banco` que os diálogos de Pessoas |
| (as três) | `interpretador.py` | `analisar()` junta léxico, sintático e semântico numa `Analise` (o que o modo didático mostra) |

**Formato dos erros:** `[Fase] coluna N: mensagem (RN)` ou `[Fase] fim da
linha: ...`, com a linha digitada e o `^` embaixo, a sugestão ("Você quis
dizer entrada? (Tab corrige)") e a dica.

**Decisões da implementação** (não mudam a gramática):
- `semana` = os últimos 7 dias (hoje e os 6 anteriores); `mes` = os
  últimos 30 dias; `ontem` = só ontem; `de DATA` sem `ate` vai até hoje.
- Opções que não combinam são erro semântico, como as repetidas: `placa` com
  `sem carro`, `as` com `em`.
- Na saída pela placa (`saida placa X` ou só `X`) só sai o carro (RN27):
  as opções `placa`, `sem carro` e `as` valem só na saída pelo CPF.
- `saida CPF placa X`: X é um carro da pessoa (RN40) ou um que ela pode
  retirar (RN35); `saida CPF as HORA` é uma saída de hoje num horário que
  já passou, com a regra do retroativo (RN24), como na correção.
- `entrada` de quem tem placa no cadastro, sem `placa` nem `sem carro`:
  abre a pergunta "Vai entrar de carro?" (RN34); "Com outro carro" pede
  para escrever `placa`. Se o carro dela já está no estacionamento, a
  entrada é a pé, como no formulário.
- `editar` muda nome, celular e tipo. Na 2.5 (RN47), `placa X` inclui o
  carro X no cadastro (a principal continua a mesma) e `sem placa X` tira;
  os dois podem se repetir no mesmo comando (`placa` e `sem placa` do mesmo
  carro juntos é erro semântico). O `cadastrar` aceita um `placa` por
  carro, até 5; a primeira é a principal.
- Tipo diferente do cadastro é um **aviso**: o programa pergunta
  "Registrar como Prestador de serviço?" e, com Não, nada é gravado.
- Excluir e reativar pedem a mesma confirmação dos diálogos de Pessoas.
- O CPF mascarado que o Tab escreve para o porteiro (`***.982.247-**`) só
  vale se veio do Tab: o campo guarda o CPF de verdade só na memória.
- A linha tem no máximo **200 caracteres** (`validacao.MAXIMO_COMANDO`):
  a digitação para no máximo e a colagem entra cortada, como nos outros
  campos (RN33).
- **RN46** resume a regra de ouro, a privacidade e as permissões da
  linguagem (`IDEIAS_E_MELHORIAS.md`, seção 4).
