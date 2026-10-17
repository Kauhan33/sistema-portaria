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
- **Editar registro** para corrigir erro de digitação (com histórico da alteração).
- **Lista de bloqueio**: CPF/placa com acesso negado e motivo; alerta ao cadastrar.
- **Visitante**: campos "quem vai visitar / setor" e "motivo"; crachá numerado.
- **Alerta de permanência**: destacar visitante/entregador dentro há mais de X horas
  e listar quem ainda está no campus no fim do expediente.
- **Estacionamento**: vagas ocupadas × capacidade.
- **Máscara automática** nos campos (CPF vira 000.000.000-00 enquanto digita) e
  seletor de data.

### Etapa 3 — Relatórios e dashboard
- Filtro por período (data inicial e final) na tabela e no dashboard.
- Gráfico de **horário de pico** (entradas por hora do dia).
- Tempo médio de permanência por tipo; visitantes mais frequentes.
- **Exportar** relatório do dia/período em CSV (Excel) e PDF.
- Backup automático diário.

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
- Executável `.exe` com PyInstaller (já feito na Lanchonete).
- Repositório no GitHub **sem** nome, RA ou professora (material e entrega ficam fora do git).

## 4. Rascunho de requisitos para o Word

**RF**: RF01 cadastrar entrada · RF02 registrar saída · RF03 consultar/buscar
histórico · RF04 excluir registro (admin) · RF05 exibir dashboard · RF06 login ·
RF07 exportar relatório · RF08 comando digitado (Etapa 4).

**RNF**: RNF01 interface simples com botões identificados · RNF02 senha oculta e
armazenada com hash · RNF03 busca responde na hora · RNF04 roda no Windows só com
Python padrão (ou .exe) · RNF05 dados pessoais ficam só no computador da portaria (LGPD).

**RN**: RN01 campos obrigatórios · RN02 só admin exclui · RN03 saída só com entrada
aberta · RN04 saída não anterior à entrada · RN05 um CPF não pode ter duas entradas
abertas · RN06 CPF/celular/placa válidos · RN07 entrada não pode ser no futuro ·
RN08 sempre existe ao menos um administrador ativo · RN09 usuário desativado não
entra · RN10 5 senhas erradas bloqueiam o login por 30 s.
