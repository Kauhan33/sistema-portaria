# Sistema de Portaria da Universidade

Projeto da disciplina **Teoria da Computação e Compiladores** (8º período — UNA).
Controle de entrada e saída de pessoas no campus, feito em Python com Tkinter, e
relacionado com as fases de um compilador (léxica, sintática e semântica).

## Como executar

Requer só o Python 3 (Tkinter já vem na instalação padrão do Windows).

```bash
python portaria_universidade.py
```

Os registros ficam no banco SQLite `portaria.db` (módulo `sqlite3`, já incluso
no Python), criado ao lado do programa. Se houver um `registros_portaria.json` da
versão 1 na mesma pasta, ele é importado na primeira execução e renomeado para
`registros_portaria.json.migrado`, que fica como backup.

### Primeiro acesso e login

Na primeira vez o sistema pede para **criar o administrador** (não existe senha
padrão). Depois disso abre sempre na tela de login.

| Perfil | Pode |
|---|---|
| Porteiro | Cadastrar entradas, registrar saídas, buscar, ver e corrigir o cadastro de pessoas, ver o dashboard |
| Administrador | Tudo do porteiro + **excluir registros** + aba **Usuários** (criar, ativar/desativar, redefinir senha, ver o histórico de ações) |

## Testes automatizados

```bash
python -m unittest -v
```

149 testes (biblioteca padrão `unittest`) cobrindo validações, regras de negócio,
login, senhas, permissões, cadastro de pessoas e preenchimento automático, saída
rápida e desfazer, banco
de dados, histórico, migração do JSON, busca, dashboard e a própria tela (preenche campos e clica nos botões com a janela oculta).

## O que o sistema faz hoje

- Cadastro com CPF, nome completo, celular, placa (opcional), tipo de acesso,
  entrada e saída — tecla **Enter** cadastra.
- **Cadastro de pessoas separado das visitas**: ao digitar o CPF de quem já veio,
  nome, celular, placa e tipo se preenchem sozinhos (só nos campos vazios; trocar
  o CPF desfaz o preenchimento). Avisa se a pessoa ainda está no campus.
- **Saída rápida**: duplo clique na linha de quem está dentro, ou o campo
  "Saída rápida" (atalho **F2**) com o CPF ou a placa + Enter — só aceita o CPF
  ou a placa exatos, e pergunta antes se a placa trouxer mais de uma pessoa
  (carona). O botão "Registrar saída" aceita várias linhas selecionadas. Em vez de
  uma caixa para fechar, aparece um aviso com **Desfazer** por 10 segundos.
- Aba **Pessoas**: todos que já passaram pela portaria, com nº de visitas, última
  visita e quem está no campus; dá para corrigir os dados e começar uma nova
  entrada já preenchida (botão ou duplo clique).
- Validações no padrão brasileiro: CPF com dígitos verificadores, celular com DDD
  válido e 9, placa antiga (ABC1234) ou Mercosul (ABC1D23).
- Nome completo só com letras (acentos, hífen e apóstrofo permitidos).
- Regras: entrada e saída não podem estar no futuro; saída não pode ser anterior
  à entrada; o mesmo CPF não pode estar no campus duas vezes ao mesmo tempo.
- O próprio banco também barra CPF incompleto e saída anterior à entrada
  (restrições `CHECK`), e cada operação é uma transação: ou grava tudo, ou nada.
- Botões Cadastrar, Limpar, Registrar saída e Excluir selecionado (este só
  aparece para o administrador — RN02).
- Login com perfis porteiro e administrador. Senha digitada aparece como `••••`
  e é guardada só como hash PBKDF2-SHA256 com sal (RNF02). Depois de 5 senhas
  erradas seguidas, o login fica bloqueado por 30 segundos.
- Histórico de ações: quem entrou, cadastrou, registrou saída, excluiu (com os
  dados do registro apagado), criou ou desativou usuário e redefiniu senha.
- Busca por nome, CPF, celular, placa ou tipo.
- Aba **Dashboard**: totais por tipo, pessoas dentro agora, entradas do dia,
  veículos, permanência média e gráficos (por tipo e últimos 7 dias).

## Estrutura da pasta

| Caminho | Conteúdo |
|---|---|
| `portaria_universidade.py` | Ponto de entrada (é o arquivo que se executa) e a relação com Compiladores |
| `portaria/validacao.py` | Regras de CPF, celular, placa, nome, datas e verificações semânticas |
| `portaria/dados.py` | Banco SQLite (pessoas, visitas, usuários, histórico) e migrações |
| `portaria/consultas.py` | Busca na tabela e números do dashboard |
| `portaria/usuarios.py` | Senhas (hash), perfis, permissões e bloqueio por tentativas |
| `portaria/interface.py` | Janela principal, sessão, abas Cadastro e Dashboard |
| `portaria/tela_login.py` | Tela de login e de primeiro acesso |
| `portaria/tela_pessoas.py` | Aba Pessoas (lista, busca, correção de dados, nova entrada) |
| `portaria/tela_usuarios.py` | Aba Usuários e histórico de ações (só administrador) |
| `portaria/estilo.py` | Cores, fontes e botões compartilhados |
| `tests/` | Testes automatizados |
| `IDEIAS_E_MELHORIAS.md` | Análise do código, falhas encontradas e roteiro de melhorias |
| `versoes/v1_original/` | Cópia da versão feita no Claude gratuito, para comparar antes × depois |
| `material_aula/` | Slides da disciplina (enunciado do exercício e guia de documentação) — local, fora do git |
| `entrega/` | O que vai para a faculdade (Word com capa, prints, .exe) — local, fora do git |
