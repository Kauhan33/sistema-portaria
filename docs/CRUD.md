# Matriz CRUD — Sistema de Portaria (versão 2.4)

Levantamento feito no código da versão 2.3 e revisto na 2.4 (`portaria/tela_*.py` e
`portaria/dados.py`), página por página e aba por aba: como cada operação
de **C**riar, **L**er (*Read*), **A**tualizar (*Update*) e **E**xcluir
(*Delete*) é feita, quem pode e qual o botão. Toda escrita passa pela regra
em função pura (`validacao.py`, `usuarios.py`, `horarios.py`,
`veiculos.py`), é conferida de novo no banco (`dados.Banco`, com o perfil de
quem faz) e vai para o histórico (Usuários › Atividade).

Legenda: **Todos** = porteiro e administrador; **Admin** = só o
administrador. O porteiro vê o CPF mascarado (`***.982.247-**`) em todas as
listas.

## Matriz

| Página › aba | Criar | Ler | Atualizar | Excluir |
|---|---|---|---|---|
| **Entrada e saída › Movimento › Pessoas** (visitas) | **Todos** — formulário "Nova entrada", botão **Registrar entrada** (ou Enter) | **Todos** — tabela Movimento (hoje + quem está no campus); a busca vai ao histórico inteiro | **Todos** — **Registrar saída** (botão, duplo clique, campo Comando F2/Ctrl+K com só o CPF ou a placa, Desfazer) e **Corrigir** (porteiro: entrada nas últimas 24 h, RN11; admin: qualquer uma) | **Admin** — **Excluir** (RN02); o porteiro nem vê o botão |
| **Entrada e saída › Movimento › Veículos** (estadias) | Automático — a entrada **com placa** abre a estadia do carro (RN25); não há criação solta | **Todos** — subaba **Veículos (n)** | **Todos** — **Registrar saída** do carro (pela placa ou duplo clique); sem o dono, só com a senha do admin (RN32); a placa e o horário se corrigem pela visita (**Corrigir**) | Não se exclui: a estadia é histórico do estacionamento. Sai junto quando a visita encerrada que a abriu é excluída (RN28) |
| **Pessoas › Ativas** | **Todos** — **Nova pessoa** (CPF, nome, celular, placa opcional, tipo; sem entrada; RN41) | **Todos** — lista com busca e ordenação + ficha (visitas, veículo) | **Todos** — ficha › **Editar** (mesmo diálogo, CPF fixo) | **Admin** — ficha › **Excluir**, só sem visitas (RN42); com histórico, **Desativar** (RN12) |
| **Pessoas › Desativadas** | **Admin** — **Desativar CPF** (lista) ou ficha › **Desativar**, com motivo (RN12) | **Todos** — nome (ou "(sem cadastro)"), CPF, motivo, quando e quem; **Mostrar reativadas** | **Admin** — **Reativar** (lista ou ficha); o motivo não se edita: reative e desative de novo (os dois ficam no histórico) | Não se apaga: reativar encerra a desativação, que fica guardada (quem e quando) |
| **Pessoas › Veículos desativados** | **Admin** — **Desativar placa** (lista) ou ficha › Veículo › **Desativar placa** | **Todos** — placa, pessoa dona, motivo, quando e quem; **Mostrar reativados** | **Admin** — **Reativar** (lista) ou ficha › **Reativar placa** | Não se apaga (como acima) |
| **Pessoas › ficha › Veículo** (quem pode retirar o carro, RN35) | **Todos** — **Adicionar** (porteiro só com o dono no campus; admin a qualquer hora) | **Todos** — lista da placa (nome, CPF, validade) | **Todos** — **Validade** (RN45; mesma permissão de Adicionar) | **Todos** — **Remover** (remoção lógica, com histórico: remover só diminui a permissão) |
| **Pessoas › ficha › Visitas** | — (a visita nasce na Entrada e saída) | **Todos** — histórico da pessoa | Pela **Entrada e saída › Corrigir** | Pela **Entrada e saída › Excluir** (Admin) |
| **Painel** | — | **Todos** — números do dia, gráficos e horários; **Exportar CSV** (Admin) | — | — |
| **Usuários › Contas** | **Admin** — **Novo usuário** | **Admin** — lista de contas e a **Atividade** (histórico, com filtro) | **Admin** — **Editar** (nome e perfil; RN43), **Redefinir senha** (RN39), **Ativar**; cada um troca a própria senha (menu da conta) | **Admin** — **Desativar** (não apaga: o login identifica quem fez cada ação no histórico; RN08 garante um admin ativo) |
| **Usuários › Exceções** | — (as exceções nascem nas autorizações da guarita) | **Admin** — período, tipo e quem autorizou; **Exportar CSV** | — | — |
| **Configurações › Funcionamento** (horários, aviso, retroativo, vagas) | — (os 7 dias da semana e os parâmetros sempre existem) | **Admin** | **Admin** — **Salvar funcionamento** (RN16, RN22, RN37) | — ("Fechado" desliga o dia) |
| **Configurações › Categorias** | — (as 6 categorias são os tipos de acesso) | **Admin** | **Admin** — **Salvar regras** (RN17, RN18, RN21) | — |
| **Configurações › Feriados** | **Admin** — **Adicionar** | **Admin** — lista | **Admin** — **Editar** (a linha volta aos campos; o botão vira **Salvar alteração**; RN44) | **Admin** — **Remover** |
| **Configurações › Eventos** | **Admin** — **Adicionar** | **Admin** — lista | **Admin** — **Editar** (RN44) | **Admin** — **Remover** |

## CRUD também pela linguagem de comandos (2.4)

O campo **Comando** (F2 ou Ctrl+K, na Entrada e saída) faz o CRUD da
pessoa e da visita por texto. É só outra porta (RN46): cada comando passa
pelas mesmas funções e pelos mesmos métodos do `Banco` dos botões acima,
abre os mesmos diálogos e confirmações e respeita o mesmo perfil — o
porteiro digitando um comando de administrador para já na análise
semântica (e o banco também recusaria). Um teste compara o banco depois do
comando com o banco depois do formulário (`tests/test_interface_comando.py`).

| Operação | Pelo botão | Pelo comando | Quem |
|---|---|---|---|
| Criar visita | Registrar entrada | `entrada 529.982.247-25 aluno placa ABC1D23` | Todos |
| Ler | Movimento, Pessoas, Painel | `situacao CPF`, `situacao placa ABC1D23`, `dentro [tipo]`, `buscar maria visitante semana`, `pendentes` | Todos |
| Atualizar visita (saída) | Registrar saída | `saida CPF [placa X] [sem carro] [as 14:05]`, `saida placa X`, ou só o CPF ou a placa | Todos |
| Criar pessoa | Nova pessoa | `cadastrar CPF visitante nome "Bruno Almeida" cel 31987651234 [placa ABC1234]` | Todos |
| Atualizar pessoa | ficha › Editar | `editar CPF cel 31999990000 tipo professor` | Todos |
| Excluir pessoa | ficha › Excluir | `excluir CPF` (a mesma confirmação) | Admin |
| Desativar | Desativar (lista ou ficha) | `desativar CPF motivo "..."`, `desativar placa ABC1D23 motivo "..."` | Admin |
| Reativar | Reativar | `reativar CPF`, `reativar placa ABC1D23` (a mesma confirmação) | Admin |

Corrigir e excluir uma **visita**, usuários e configurações continuam só
pelos botões (a gramática aprovada não tem esses comandos).

## Lacunas fechadas na versão 2.3

| Lacuna encontrada | Como ficou |
|---|---|
| Pessoa só era criada pela entrada | **Nova pessoa** em Pessoas (RN41), sem registrar entrada |
| Não havia como excluir uma pessoa | **Excluir** (Admin), só para quem nunca teve visita (RN42) |
| Bloqueio era uma página à parte | **Desativar / Reativar** dentro de Pessoas (RN12), com as subabas Desativadas e Veículos desativados |
| A ficha editava num formulário que não cabia no notebook | **Editar** abre o mesmo diálogo da Nova pessoa |
| Nome e perfil de usuário não se editavam | **Editar** em Usuários › Contas (RN43) |
| Feriado e evento só se adicionavam e removiam | **Editar** nos dois (RN44) |
| A validade de quem pode retirar o carro não mudava | **Validade** na ficha › Veículo (RN45) |

## Por que algumas abas não têm todas as operações

- **Painel** é **só leitura**: é um relatório calculado na hora a partir das
  visitas (números do dia, gráficos, horários). Não existe um "registro do
  Painel" para criar, editar ou excluir; mudar o que ele mostra é mudar as
  visitas, na Entrada e saída. A exportação (CSV) é uma leitura.
- **Exceções** é **leitura e exportação**: cada linha é um evento de
  auditoria (quem autorizou o quê, quando e por quê). Por segurança, a
  trilha de auditoria não se edita nem se apaga — senão quem passou por
  cima de uma regra poderia apagar o rastro. O mesmo vale para a
  **Atividade** (histórico).
- **Usuários: "Excluir" é Desativar**: o login aparece no histórico de
  cada ação; apagar a conta deixaria eventos sem dono. Desativada, a conta
  não entra mais (RN09) e pode ser reativada.
- **Desativações** não se apagam pelo mesmo motivo: reativar guarda quem
  reativou e quando.
- **Veículos (estadias)** e **Visitas da ficha** não têm botões próprios de
  criar e excluir: nascem e somem com a visita (Entrada e saída).
- **Configurações › Funcionamento e Categorias** são parâmetros fixos (um
  por dia da semana e um por tipo de acesso): só se lê e se atualiza.
