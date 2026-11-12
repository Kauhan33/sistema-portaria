"""
Casos de teste documentados (formato do guia: entrada, esperado, resultado).

    python -m tests.relatorio                 # grava numa pasta temporária
    python -m tests.relatorio C:\\pasta\\saida  # grava onde for pedido
    python -m tests.relatorio --sem-suite     # não roda a suíte completa

Cada caso (CT-01 a CT-nn) descreve, como um testador manual, a entrada e o
resultado esperado, e aponta o(s) teste(s) automático(s) do unittest que
comprovam o caso. O script roda só esses testes, marca PASSOU ou FALHOU em
cada caso (todos os testes do caso precisam passar) e grava:

    relatorio_testes.html   para abrir no navegador
    relatorio_testes.csv    para o Excel (separado por ponto e vírgula)
    relatorio_testes.json   para o documento Word

com a data e a hora, o total, os aprovados, a matriz de rastreabilidade
(RF/RN x CT) e, como evidência, o resultado da suíte completa
(`python -m unittest`, rodada num processo separado, como na linha de
comando). Nada é gravado dentro do repositório.
"""

import csv
import html
import io
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime

from portaria import VERSAO

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOME = "relatorio_testes"

POSITIVO, NEGATIVO = "positivo", "negativo"
# seções do relatório (e do Word): a linguagem de comandos (2.4) tem a sua
SISTEMA, LINGUAGEM = "Sistema", "Linguagem de comandos"


def caso(id_, requisitos, tipo, titulo, entrada, esperado, testes,
         secao=SISTEMA, fase=""):
    return {"id": id_, "requisitos": requisitos, "tipo": tipo,
            "titulo": titulo, "entrada": entrada, "esperado": esperado,
            "testes": ["tests." + t for t in testes], "secao": secao,
            "fase": fase}


def caso_da_linguagem(id_, fase, requisitos, tipo, titulo, entrada,
                      esperado, testes):
    """Caso da seção "Linguagem de comandos", com a fase do analisador."""
    return caso(id_, requisitos, tipo, f"[{fase}] {titulo}", entrada,
                esperado, testes, secao=LINGUAGEM, fase=fase)


# ------------------------------------------------------------------
# Os casos de teste (o que vai para a seção "Testes" do Word)
# ------------------------------------------------------------------
CASOS = [
    # --- Entrada (cadastro) e validação dos campos -----------------
    caso("CT-01", ["RF01", "RF08"], POSITIVO, "Registrar entrada válida",
         "Porteiro preenche nome \"Ana Silva\", CPF 529.982.247-25, celular "
         "31 98765-4321, placa ABC1D23 e tipo Visitante e clica em "
         "Registrar entrada.",
         "A entrada é gravada com a data e a hora atuais, aparece na tabela "
         "Movimento, o formulário é limpo e a faixa verde mostra o texto do "
         "enunciado: \"Registro cadastrado com sucesso! Entrada de Ana às "
         "hh:mm.\"",
         ["test_interface.TestCadastroComoAdmin."
          "test_cadastrar_salva_no_banco_e_limpa_o_formulario",
          "test_validacao.TestValidar.test_cadastro_completo_e_aceito"]),
    caso("CT-02", ["RF08"], POSITIVO, "CPF de quem já veio preenche a ficha",
         "Digitar no campo CPF o número de uma pessoa que já visitou o "
         "campus.",
         "Nome, celular, placa e tipo se preenchem sozinhos (só nos campos "
         "vazios) e basta o CPF para registrar a entrada.",
         ["test_interface.TestPreenchimentoAutomatico."
          "test_cpf_de_quem_ja_veio_preenche_os_dados",
          "test_interface.TestPreenchimentoAutomatico."
          "test_basta_o_cpf_para_cadastrar_a_entrada"]),
    caso("CT-03", ["RN01"], NEGATIVO, "Campos obrigatórios vazios",
         "Nome: vazio. CPF: vazio. Porteiro clica em Registrar entrada.",
         "O sistema não salva e mostra a mensagem \"O nome da pessoa é "
         "obrigatório.\" (cada campo obrigatório vazio tem a sua mensagem).",
         ["test_interface.TestCadastroComoAdmin."
          "test_nome_e_cpf_vazios_nao_salvam_e_avisam",
          "test_validacao.TestValidar.test_campos_obrigatorios_vazios"]),
    caso("CT-04", ["RN06"], NEGATIVO, "CPF inválido",
         "CPF 123.456.789-00 (dígito verificador errado) e os outros campos "
         "corretos; clicar em Registrar entrada.",
         "A faixa avisa \"CPF inválido\" já durante a digitação; ao "
         "registrar, a mensagem \"CPF inválido\" aparece e nada é gravado.",
         ["test_interface.TestCadastroComoAdmin.test_cpf_invalido_nao_salva",
          "test_interface.TestPreenchimentoAutomatico."
          "test_cpf_invalido_avisa_na_hora",
          "test_validacao.TestValidar.test_cpf_com_digito_errado"]),
    caso("CT-05", ["RN06"], NEGATIVO, "Nome, celular e placa fora do padrão",
         "Nome \"123 456\"; ou nome sem sobrenome (\"Ana\"); ou celular sem "
         "o 9 depois do DDD; ou placa \"AB12\".",
         "Recusa com a mensagem do campo (\"O nome deve conter apenas "
         "letras\", \"Informe o nome completo\", \"Celular inválido\", "
         "\"Placa inválida\") e nada é gravado.",
         ["test_interface.TestCadastroComoAdmin."
          "test_cadastro_invalido_mostra_erro_e_nao_salva",
          "test_validacao.TestValidar.test_nome_com_numeros",
          "test_validacao.TestValidar.test_nome_sem_sobrenome",
          "test_validacao.TestCampos.test_celular",
          "test_validacao.TestValidar.test_placa_invalida"]),
    caso("CT-06", ["RN06"], NEGATIVO, "Data fora do formato dd/mm/aaaa hh:mm",
         "Entrada \"2026-10-16 08:00\" ou saída \"amanhã\".",
         "Recusa: \"Data/hora de entrada inválida. Use o formato dd/mm/aaaa "
         "hh:mm\" (erro léxico/sintático do campo).",
         ["test_validacao.TestValidar.test_data_em_formato_errado"]),
    caso("CT-07", ["RN07"], NEGATIVO, "Entrada ou saída no futuro",
         "Entrada em 16/10/2030 08:00 (data futura) ou saída depois de "
         "agora.",
         "Recusa: \"A entrada não pode estar no futuro\" / \"A saída não pode "
         "estar no futuro\".",
         ["test_validacao.TestValidar.test_entrada_no_futuro",
          "test_validacao.TestValidar.test_saida_no_futuro"]),
    caso("CT-08", ["RN05"], NEGATIVO, "CPF que já está no campus",
         "Registrar nova entrada para um CPF que entrou às 08:00 e ainda não "
         "saiu.",
         "Recusa: \"Este CPF já possui uma entrada sem saída\". O banco "
         "também recusa uma segunda visita aberta do mesmo CPF.",
         ["test_validacao.TestValidar.test_segunda_entrada_aberta_do_mesmo_cpf",
          "test_dados.TestIntegridade."
          "test_segunda_visita_aberta_do_mesmo_cpf_e_recusada_pelo_banco"]),
    caso("CT-09", ["RF01"], POSITIVO, "Botão Limpar",
         "Preencher o formulário e clicar em Limpar.",
         "Todos os campos voltam ao início (Entrada com a hora atual) e a "
         "faixa de situação some.",
         ["test_interface.TestPreenchimentoAutomatico."
          "test_limpar_volta_ao_inicio"]),
    caso("CT-10", ["RN33"], NEGATIVO, "Tamanho máximo dos campos",
         "Colar no campo Nome um texto de 120 letras; enviar ao banco um "
         "nome de 81 caracteres sem passar pela tela.",
         "A colagem entra cortada em 80 caracteres; a validação e o banco "
         "recusam \"Nome completo: no máximo 80 caracteres\".",
         ["test_interface_limites.TestTamanhoDosCampos."
          "test_nome_colado_longo_entra_cortado_no_cadastro",
          "test_interface_limites.TestTamanhoDosCampos."
          "test_limite_de_cada_campo",
          "test_tamanhos.TestValidacao.test_nome_da_visita",
          "test_tamanhos.TestTamanhoMaximoNoBanco.test_visita_com_nome_longo"]),

    # --- Saída -------------------------------------------------------
    caso("CT-11", ["RF02"], POSITIVO, "Registrar a saída",
         "Duplo clique na linha de quem está no campus; ou CPF formatado "
         "na Saída rápida (F2) + Enter.",
         "A saída é gravada com a data e a hora atuais e a situação da "
         "linha passa a \"Saiu\".",
         ["test_interface.TestSaidaRapida.test_duplo_clique_na_linha",
          "test_interface.TestSaidaRapida.test_saida_pelo_cpf_formatado",
          "test_dados.TestBanco.test_registrar_saida"]),
    caso("CT-12", ["RN03"], NEGATIVO, "Saída sem entrada aberta",
         "Saída rápida com um CPF que não está no campus, ou com a placa "
         "ZZZ9999 que não está no estacionamento; duplo clique em quem já "
         "saiu.",
         "Mensagem \"Ninguém no campus com esse CPF\" / \"ZZZ-9999 não está no "
         "estacionamento\" / \"já tem a saída registrada\"; nada é gravado.",
         ["test_interface.TestSaidaRapida.test_cpf_ou_placa_sem_ninguem_dentro",
          "test_interface.TestSaidaRapida.test_duplo_clique_em_quem_ja_saiu",
          "test_validacao.TestChecarSaida.test_quem_ja_saiu"]),
    caso("CT-13", ["RN04"], NEGATIVO, "Saída antes da entrada",
         "Entrada 16/10/2026 08:00 e saída 16/10/2026 07:00 (no cadastro e "
         "na janela Corrigir registro).",
         "Recusa: \"A saída não pode ser anterior à entrada\". O banco "
         "também recusa.",
         ["test_validacao.TestValidar.test_saida_antes_da_entrada",
          "test_interface.TestCorrigirComoAdmin."
          "test_nao_pode_colocar_saida_antes_da_entrada",
          "test_dados.TestBanco.test_banco_recusa_saida_antes_da_entrada"]),

    # --- Consulta, exclusão e correção ------------------------------
    caso("CT-14", ["RF03"], POSITIVO, "Buscar no histórico",
         "Digitar na busca do Movimento o nome de quem veio em outro dia.",
         "A tabela mostra o registro antigo (a busca procura no histórico "
         "inteiro, não só no movimento do dia).",
         ["test_interface.TestMovimento.test_busca_acha_registro_antigo"]),
    caso("CT-15", ["RF04", "RN02"], POSITIVO, "Administrador exclui registro",
         "Administrador seleciona uma linha, clica em Excluir e confirma.",
         "O registro sai da tabela e do banco e o histórico guarda "
         "\"Exclusão de registro\" com o login de quem excluiu.",
         ["test_interface.TestCadastroComoAdmin.test_registrar_saida_e_excluir"]),
    caso("CT-16", ["RN02"], NEGATIVO, "Porteiro tenta excluir",
         "Logado como porteiro: procurar o botão Excluir; acionar a exclusão "
         "mesmo assim; mandar a exclusão direto ao banco.",
         "O botão não aparece; a ação mostra \"Somente o administrador pode "
         "excluir registros.\"; o banco recusa. Nada é apagado.",
         ["test_interface.TestPorteiro."
          "test_porteiro_nao_ve_botao_excluir_nem_aba_usuarios",
          "test_interface.TestPorteiro.test_porteiro_nao_consegue_excluir",
          "test_dados.TestPermissoesNoBanco.test_porteiro_nao_exclui_registro"]),
    caso("CT-17", ["RF09", "RN11"], POSITIVO, "Corrigir registro com histórico",
         "Selecionar o registro de hoje, clicar em Corrigir, mudar o nome e "
         "salvar.",
         "A correção é gravada e a janela mostra o histórico \"antes → "
         "depois\" com quem corrigiu.",
         ["test_interface.TestCorrigirComoAdmin.test_corrige_registro_de_hoje",
          "test_interface.TestCorrigirComoAdmin."
          "test_janela_mostra_o_historico_do_registro"]),
    caso("CT-18", ["RN11", "RN12"], NEGATIVO,
         "Correção fora do permitido",
         "Porteiro tenta corrigir um registro com entrada há mais de 24 h; "
         "ou corrigir o CPF de uma visita para o CPF de uma pessoa "
         "desativada.",
         "Recusa (\"Acesso negado\" / \"Acesso negado ... Pessoa "
         "desativada\") e nada muda; o banco também recusa.",
         ["test_interface.TestCorrigirComoPorteiro."
          "test_porteiro_nao_corrige_registro_antigo",
          "test_interface.TestCorrigirComoPorteiro."
          "test_nao_burla_a_desativacao_pela_correcao",
          "test_dados.TestDesativacaoNoBanco."
          "test_banco_recusa_entrada_e_correcao_de_desativado"]),

    # --- Login e usuários -------------------------------------------
    caso("CT-19", ["RF06", "RNF02"], POSITIVO, "Login com senha oculta",
         "Abrir o programa; digitar usuário e senha corretos.",
         "A senha aparece como \"•\"; entra no sistema; a senha fica no "
         "banco só como hash PBKDF2 (o texto da senha não aparece em nada "
         "que é guardado).",
         ["test_interface.TestLogin.test_abre_na_tela_de_login_com_senha_oculta",
          "test_interface.TestLogin.test_login_certo_entra_no_sistema",
          "test_usuarios.TestSenha.test_senha_nao_aparece_no_que_e_guardado",
          "test_usuarios.TestSenha.test_padrao_de_producao_e_600_mil_iteracoes"]),
    caso("CT-20", ["RF06", "RN09"], NEGATIVO, "Senha errada ou usuário desativado",
         "Senha errada; ou login de um usuário desativado com a senha certa.",
         "Não entra e a faixa de erro aparece na tela de login.",
         ["test_interface.TestLogin.test_senha_errada_nao_entra",
          "test_interface.TestLogin.test_usuario_desativado_nao_entra"]),
    caso("CT-21", ["RN10"], NEGATIVO, "Bloqueio por tentativas",
         "Errar a senha 5 vezes seguidas e, em seguida, digitar a certa; "
         "fechar e abrir o programa.",
         "\"Aguarde ...\": nem a senha certa entra por 30 s (o tempo dobra a "
         "cada bloqueio); reabrir o programa não zera o bloqueio.",
         ["test_interface.TestLogin.test_bloqueio_depois_de_muitas_tentativas",
          "test_interface.TestLogin."
          "test_bloqueio_continua_ao_abrir_o_programa_de_novo",
          "test_usuarios.TestEntrar.test_bloqueio_cresce_a_cada_vez"]),
    caso("CT-22", ["RF06", "RN15"], POSITIVO, "Primeiro acesso cria o administrador",
         "Abrir o programa com o banco vazio e preencher nome, login e senha "
         "de 8 ou mais caracteres.",
         "O sistema pede para criar o administrador (não há senha padrão), "
         "cria e entra.",
         ["test_interface.TestPrimeiroAcesso."
          "test_banco_vazio_pede_para_criar_o_administrador",
          "test_interface.TestPrimeiroAcesso.test_cria_administrador_e_entra"]),
    caso("CT-23", ["RN15"], NEGATIVO, "Senha fraca",
         "No primeiro acesso, senha \"123\"; ou senha igual ao login; ou "
         "senha comum.",
         "Recusa com a mensagem (\"pelo menos 8 caracteres\" / igual ao "
         "login) e o usuário não é criado.",
         ["test_interface.TestPrimeiroAcesso.test_senha_curta_e_recusada",
          "test_usuarios.TestSenha.test_senha_minima_de_8_caracteres",
          "test_usuarios.TestSenha.test_senha_comum_ou_igual_ao_login_e_recusada"]),
    caso("CT-24", ["RN39"], NEGATIVO, "Troca de senha obrigatória",
         "Usuário criado pelo administrador entra com a senha provisória e "
         "tenta usar como nova senha o próprio login; antes de trocar, "
         "tenta uma operação direto no banco.",
         "Entra direto em \"Defina sua senha\"; a senha igual ao login é "
         "recusada; o banco recusa qualquer operação até a troca.",
         ["test_troca_de_senha.TestDefinaSuaSenhaNaTela."
          "test_usuario_criado_entra_direto_na_troca_de_senha",
          "test_troca_de_senha.TestDefinaSuaSenhaNaTela."
          "test_senha_igual_ao_login_e_recusada_na_troca",
          "test_troca_de_senha.TestTrocaDeSenhaNoBanco."
          "test_com_a_troca_pendente_o_banco_recusa_qualquer_operacao"]),
    caso("CT-25", ["RF22", "RN38"], POSITIVO, "Esqueci a senha com código",
         "No login, \"Esqueci a senha\": usuário do administrador, um dos 8 "
         "códigos de recuperação e a senha nova; depois, o mesmo código de "
         "novo.",
         "A senha é trocada e o login volta com a senha nova; o código é "
         "queimado e não funciona uma segunda vez; no banco fica só o hash.",
         ["test_recuperacao.TestEsqueciASenhaNaTela."
          "test_codigo_certo_volta_ao_login_com_a_senha_nova",
          "test_recuperacao.TestCodigosNoBanco."
          "test_codigo_certo_troca_a_senha_e_nao_funciona_de_novo",
          "test_recuperacao.TestCodigosNoBanco."
          "test_so_o_hash_vai_para_o_banco_e_o_codigo_nao_vai_ao_historico"]),
    caso("CT-26", ["RN38"], NEGATIVO, "Código de recuperação errado",
         "\"Esqueci a senha\" com um código inventado.",
         "Mostra o erro, continua na mesma tela e a tentativa conta no "
         "bloqueio progressivo do login.",
         ["test_recuperacao.TestEsqueciASenhaNaTela."
          "test_codigo_errado_mostra_o_erro_e_fica",
          "test_recuperacao.TestCodigosNoBanco."
          "test_codigo_errado_conta_como_tentativa"]),

    # --- Desativação de pessoa e de veículo (até a 2.2: bloqueio) ----
    caso("CT-27", ["RF10", "RN12"], NEGATIVO,
         "Pessoa ou veículo desativado",
         "Registrar a entrada de uma pessoa desativada (CPF); ou entrar de "
         "carro com um veículo desativado (placa); ou gravar a entrada "
         "direto no banco, sem a tela.",
         "\"Acesso negado\" com \"Pessoa desativada\" (ou \"Veículo "
         "desativado\"), o motivo, quando e quem desativou; nada é gravado, "
         "a recusa fica no histórico e o banco também recusa.",
         ["test_interface.TestDesativacaoNoCadastro."
          "test_cadastro_de_pessoa_desativada_e_recusado_e_registrado",
          "test_validacao.TestDesativacao."
          "test_entrada_com_veiculo_desativado_e_recusada",
          "test_interface_entrada_de_carro.TestEntradaDeCarroOuAPe."
          "test_de_carro_com_veiculo_desativado_e_recusado",
          "test_interface.TestAbaDesativadas."
          "test_banco_recusa_a_entrada_de_desativado_mesmo_sem_a_tela"]),
    caso("CT-28", ["RN12"], NEGATIVO, "Porteiro não desativa",
         "Logado como porteiro: abrir Pessoas › Pessoas desativadas e Veículos "
         "desativados; tentar desativar uma pessoa direto no banco.",
         "Vê as listas (CPF mascarado), sem \"Desativar\" nem "
         "\"Reativar\"; o banco recusa.",
         ["test_interface.TestDesativacaoNoCadastro."
          "test_porteiro_ve_as_listas_mas_nao_desativa_nem_reativa",
          "test_dados.TestPermissoesNoBanco."
          "test_porteiro_nao_desativa_nem_reativa"]),

    # --- Horários e autorização do administrador ---------------------
    caso("CT-29", ["RF15", "RN17", "RN20"], NEGATIVO, "Aluno com o campus fechado",
         "Porteiro registra a entrada de um Aluno num domingo (campus "
         "fechado); depois, um funcionário depois das 23:00.",
         "Não grava direto: abre \"Autorização do administrador\" com a "
         "regra violada (\"Campus fechado ...\"); sem autorização, nada é "
         "gravado.",
         ["test_interface_horarios.TestAutorizacaoComoPorteiro."
          "test_aluno_no_domingo_abre_a_autorizacao_com_a_regra",
          "test_interface_horarios.TestNinguemEntraDepoisDeFechar."
          "test_funcionario_depois_das_23h_pede_autorizacao",
          "test_horarios.TestExcecoes.test_aluno_no_domingo_e_excecao_com_o_motivo"]),
    caso("CT-30", ["RF16", "RN20"], POSITIVO, "Exceção autorizada",
         "Na mesma situação, um administrador digita login, senha e a "
         "justificativa no diálogo.",
         "A entrada é gravada e o histórico registra \"Exceção autorizada\" "
         "com quem autorizou, quem operava e o porquê. Uma entrada dentro do "
         "horário não pede autorização.",
         ["test_interface_horarios.TestAutorizacaoComoPorteiro."
          "test_admin_certo_grava_com_o_historico_da_excecao",
          "test_interface_horarios.TestAutorizacaoComoPorteiro."
          "test_entrada_normal_nao_pede_autorizacao"]),
    caso("CT-31", ["RN20", "RN31"], NEGATIVO, "Autorização inválida",
         "No diálogo de autorização: senha errada; justificativa vazia; o "
         "porteiro digita o próprio login.",
         "Nada é gravado; a senha errada conta no contador da estação "
         "(depois de 5, só o diálogo trava); justificativa é obrigatória; "
         "porteiro não autoriza.",
         ["test_interface_horarios.TestAutorizacaoComoPorteiro."
          "test_senha_errada_nao_grava_e_conta_tentativa_da_estacao",
          "test_interface_horarios.TestAutorizacaoComoPorteiro."
          "test_justificativa_vazia_e_recusada",
          "test_interface_horarios.TestAutorizacaoComoPorteiro."
          "test_porteiro_nao_autoriza_a_si_mesmo"]),
    caso("CT-32", ["RN19"], NEGATIVO, "Visita acima de 24 h",
         "Dar a saída de uma visita aberta há 30 h; gravar no banco uma "
         "visita de 30 h sem autorização.",
         "A tela pede autorização; o banco recusa a visita de mais de 24 h "
         "sem a autorização de um administrador ativo.",
         ["test_interface_horarios.TestAutorizacaoComoPorteiro."
          "test_saida_acima_de_24h_pede_autorizacao",
          "test_regras_no_banco.TestVisitaAcimaDe24h.test_banco_recusa_sem_autorizacao"]),
    caso("CT-33", ["RN24"], POSITIVO, "Lançamento retroativo de até 3 h",
         "Às 10:00, registrar uma entrada às 08:00 (dia aberto, dentro da "
         "janela da categoria).",
         "Grava normalmente, sem pedir autorização.",
         ["test_interface_horarios.TestLancamentoRetroativoNaTela."
          "test_a_ate_3_h_nao_pede_autorizacao",
          "test_horarios.TestLancamentoRetroativo.test_a_ate_3_h_com_o_dia_aberto_e_normal"]),
    caso("CT-34", ["RN24"], NEGATIVO, "Retroativo antigo ou de dia encerrado",
         "Registrar uma entrada de mais de 3 h atrás; registrar às 23:10 uma "
         "entrada das 22:00 de um aluno (dia já encerrado), inclusive com o "
         "administrador logado.",
         "Mais de 3 h: pede autorização (login e senha ao porteiro). Dia "
         "encerrado: só com a SENHA de um administrador, mesmo logado.",
         ["test_interface_horarios.TestLancamentoRetroativoNaTela."
          "test_b_mais_de_3_h_pede_login_e_senha_ao_porteiro",
          "test_interface_horarios.TestLancamentoRetroativoNaTela."
          "test_c_dia_que_ja_fechou_porteiro_precisa_da_senha",
          "test_interface_horarios.TestRetroativoComAdminLogado."
          "test_c_admin_logado_redigita_a_propria_senha"]),

    # --- Veículos -----------------------------------------------------
    caso("CT-35", ["RF19", "RN32"], POSITIVO, "Dono sai com o carro",
         "Quem entrou de carro dá a saída e responde \"Saiu de carro\"; ou "
         "sai a pé, volta a pé e depois sai de carro.",
         "A visita e a estadia do carro são fechadas, sem senha.",
         ["test_interface.TestEstadiaDeVeiculo."
          "test_saiu_de_carro_fecha_visita_e_estadia",
          "test_interface.TestEstadiaDeVeiculo."
          "test_dono_no_campus_saindo_junto_nao_pede_senha",
          "test_interface.TestEstadiaDeVeiculo."
          "test_saiu_a_pe_volta_a_pe_e_sai_de_carro"]),
    caso("CT-36", ["RN32"], NEGATIVO, "Veículo sem o dono",
         "O dono saiu a pé; o porteiro dá a saída pela placa do carro; "
         "o administrador digita a senha errada; tentativa direto no banco.",
         "\"O veículo só sai com o dono\": pede a senha de um administrador "
         "e a justificativa; com a senha errada o carro fica; o banco "
         "recusa sem autorização.",
         ["test_interface.TestEstadiaDeVeiculo."
          "test_placa_com_o_dono_fora_pede_a_senha_do_administrador",
          "test_interface.TestEstadiaDeVeiculo.test_senha_errada_nao_tira_o_carro",
          "test_regras_no_banco.TestVeiculoSoSaiComODono."
          "test_banco_recusa_tirar_o_carro_sem_o_dono_e_sem_autorizacao"]),
    caso("CT-37", ["RN26"], NEGATIVO, "Placa que já está no estacionamento",
         "Registrar a entrada de carro com a placa de um carro que ainda "
         "está no estacionamento.",
         "Recusa: \"O veículo ... já está no estacionamento desde ...\"; o "
         "banco também recusa.",
         ["test_interface.TestEstadiaDeVeiculo."
          "test_placa_que_ja_esta_no_estacionamento_nao_entra_de_novo",
          "test_regras_no_banco.TestEstadiasDeVeiculo."
          "test_placa_no_estacionamento_e_recusada_pelo_banco"]),
    caso("CT-38", ["RF23", "RN35"], POSITIVO, "Autorizado leva o carro",
         "Carla (dona) cadastrou Bruno em \"Quem pode retirar\"; Bruno está "
         "no campus a pé e dá a saída pelo CPF.",
         "Pergunta \"Vai levar o carro ... de Carla?\"; com \"Sim, leva o "
         "carro\" saem Bruno e o carro, sem senha (\"Veículo saiu com "
         "autorizado\").",
         ["test_autorizados.TestSaidaComAutorizadoNaTela."
          "test_saida_pelo_cpf_pergunta_e_leva_o_carro_sem_senha",
          "test_autorizados.TestQuemLevaOCarro.test_autorizado_no_campus_leva_sem_senha"]),
    caso("CT-39", ["RN35"], NEGATIVO, "Autorização que não vale",
         "Autorização vencida; pessoa fora da lista; porteiro cadastrando "
         "um autorizado com o dono fora do campus.",
         "Nos dois primeiros, continua valendo a senha do administrador "
         "(RN32); o cadastro do porteiro é recusado (também no banco).",
         ["test_autorizados.TestQuemLevaOCarro.test_vencido_pede_senha",
          "test_autorizados.TestQuemLevaOCarro.test_quem_nao_esta_na_lista_pede_senha",
          "test_autorizados.TestQuemCadastra."
          "test_porteiro_com_o_dono_fora_e_recusado_direto_no_banco"]),
    caso("CT-40", ["RF26", "RN40"], POSITIVO, "Dois carros da mesma pessoa",
         "Ana já tem um carro no estacionamento e entra com outro; depois "
         "dá a saída.",
         "Aviso \"Ana já tem o ... no estacionamento\" com \"Entrar, ficam os "
         "dois\"; na saída, UMA pergunta \"Com qual carro Ana está saindo?\".",
         ["test_dois_carros.TestDoisCarrosNaTela."
          "test_entrada_com_outro_carro_avisa_e_ficam_os_dois",
          "test_dois_carros.TestDoisCarrosNaTela."
          "test_saida_pergunta_uma_vez_com_os_dois_carros"]),
    caso("CT-41", ["RN40"], NEGATIVO, "Terceiro carro",
         "Com dois carros dela no estacionamento, Ana entra com um terceiro; "
         "e o mesmo direto no banco.",
         "Só com a senha de um administrador; cancelando, nada muda; o banco "
         "recusa sem a senha.",
         ["test_dois_carros.TestDoisCarrosNaTela.test_terceiro_carro_so_com_a_senha",
          "test_dois_carros.TestDoisCarrosNoBanco."
          "test_terceiro_carro_sem_senha_e_recusado_direto_no_banco"]),
    caso("CT-42", ["RN37"], NEGATIVO, "Estacionamento lotado",
         "Com 2 vagas ocupadas de 2, entrar de carro; com \"Bloquear quando "
         "lotado\" ligado, entrar de carro.",
         "Aviso \"Estacionamento lotado (2/2)\" pedindo confirmação; com o "
         "bloqueio, só com a senha de um administrador (o banco confere).",
         ["test_lotacao.TestLotacaoNaTela.test_lotado_avisa_e_pede_confirmacao",
          "test_lotacao.TestLotacaoNaTela.test_bloquear_quando_lotado_pede_a_senha",
          "test_lotacao.TestLotacaoNoBanco.test_bloquear_quando_lotado_exige_a_senha"]),

    # --- Arquivo: backup, CSV e migração do banco ------------------------
    caso("CT-43", ["RF13"], POSITIVO, "Backup diário automático",
         "Abrir o programa duas vezes no mesmo dia e por mais de 30 dias.",
         "Na abertura é criado o backup do dia (um por dia) e ficam só os "
         "30 mais recentes.",
         ["test_interface.TestAbertura.test_backup_diario_criado_na_abertura",
          "test_backup.TestBackup.test_backup_diario_so_um_por_dia",
          "test_backup.TestBackup.test_backup_diario_guarda_so_os_mais_recentes"]),
    caso("CT-44", ["RF07"], POSITIVO, "Exportar CSV",
         "Administrador, no Painel, exporta os registros de um período.",
         "Grava o CSV para o Excel com o período pedido e a exportação vai "
         "para o histórico.",
         ["test_backup.TestExportarCsv.test_exporta_o_periodo_formatado_para_o_excel",
          "test_backup.TestExportarCsv.test_exportacao_fica_no_historico",
          "test_interface.TestDashboard.test_exportar_csv"]),
    caso("CT-45", ["RF07"], NEGATIVO, "Exportação proibida ou perigosa",
         "Porteiro tenta exportar; nome de pessoa começando com \"=\" (fórmula).",
         "Porteiro: recusado e nenhum arquivo é gravado; o texto que parece "
         "fórmula vai como texto (não vira fórmula no Excel).",
         ["test_interface.TestPorteiro.test_porteiro_nao_exporta_csv",
          "test_backup.TestExportarCsv.test_porteiro_nao_exporta_e_nada_e_gravado",
          "test_backup.TestExportarCsv.test_texto_que_parece_formula_nao_vira_formula"]),
    caso("CT-46", ["RNF08"], POSITIVO, "Migração do banco",
         "Abrir a versão 2.2 sobre um banco da versão anterior (v10) com "
         "dados; e numa pasta com o arquivo JSON da versão 1.",
         "O banco vira v11 sem perder nada (backup antes); o JSON é "
         "importado e guardado como .migrado.",
         ["test_regras_no_banco.TestMigracaoV10ParaV11."
          "test_v10_com_dados_vira_v11_sem_perder_nada",
          "test_dados.TestMigracao.test_importa_tudo_e_guarda_o_json_como_migrado"]),
    caso("CT-47", ["RNF08"], NEGATIVO, "Migração que falha ou banco mais novo",
         "Erro no meio da migração; abrir um banco de versão mais nova que "
         "o programa.",
         "A migração que falha não muda nada; o banco mais novo é recusado "
         "sem ser alterado.",
         ["test_regras_no_banco.TestMigracaoV10ParaV11."
          "test_migracao_que_falha_nao_muda_nada",
          "test_dados.TestIntegridade."
          "test_banco_de_versao_mais_nova_e_recusado_sem_alterar_nada"]),

    # --- Versão 2.3: pessoas, desativação e CRUD ----------------------
    caso("CT-48", ["RF27", "RN41"], POSITIVO, "Nova pessoa sem entrada",
         "Em Pessoas, \"Nova pessoa\": CPF 529.982.247-25, \"Fernanda "
         "Souza\", celular 31 98765-4321, placa NEY4829 e tipo Visitante; "
         "clicar em Cadastrar.",
         "A pessoa é cadastrada e a ficha dela abre (placa antiga NEY-4829) "
         "com \"Pessoa cadastrada. A entrada não foi registrada.\"; nenhuma "
         "visita é gravada; o histórico registra \"Pessoa cadastrada\".",
         ["test_interface.TestNovaPessoa."
          "test_cadastra_sem_registrar_entrada_e_abre_a_ficha",
          "test_dados.TestPessoas.test_cadastrar_pessoa_sem_entrada"]),
    caso("CT-49", ["RF27", "RN41"], NEGATIVO, "Nova pessoa com CPF repetido",
         "\"Nova pessoa\" com o CPF de alguém já cadastrado; ou com nome "
         "sem sobrenome, CPF ou celular inválido; ou o mesmo CPF direto no "
         "banco.",
         "CPF repetido: já na digitação avisa \"Já cadastrado\"; ao salvar, "
         "nada é cadastrado e a ficha que já existe abre. Campos inválidos: "
         "a mesma mensagem da entrada. O banco também recusa.",
         ["test_interface.TestNovaPessoa."
          "test_cpf_ja_cadastrado_e_recusado_e_abre_a_ficha",
          "test_interface.TestNovaPessoa.test_mesma_validacao_da_entrada",
          "test_dados.TestPessoas."
          "test_cadastrar_pessoa_recusa_repetida_invalida_e_longa"]),
    caso("CT-50", ["RF28", "RN42"], NEGATIVO, "Excluir pessoa com visita",
         "Administrador abre a ficha de uma pessoa que já teve visita e "
         "clica em Excluir; ou exclui direto no banco.",
         "Nada é excluído: \"Esta pessoa tem 1 visita no histórico e não "
         "pode ser excluída ... use Desativar.\" O banco também recusa "
         "(e recusa o porteiro).",
         ["test_interface.TestExcluirPessoa."
          "test_com_visita_o_botao_explica_que_e_preciso_desativar",
          "test_interface.TestExcluirPessoa."
          "test_banco_recusa_porteiro_e_pessoa_com_visita",
          "test_dados.TestPessoas."
          "test_excluir_pessoa_com_visita_ou_por_porteiro_e_recusado"]),
    caso("CT-51", ["RN12"], NEGATIVO, "Porteiro tenta reativar",
         "Logado como porteiro: em Pessoas › Pessoas desativadas, escolher a pessoa "
         "e tentar Reativar (pela lista ou pela ficha); ou reativar direto "
         "no banco.",
         "\"Somente o administrador desativa ou reativa\"; a pessoa continua "
         "desativada; o banco recusa.",
         ["test_interface.TestDesativacaoNoCadastro."
          "test_porteiro_pela_ficha_tambem_nao_reativa",
          "test_interface.TestDesativacaoNoCadastro."
          "test_porteiro_ve_as_listas_mas_nao_desativa_nem_reativa",
          "test_dados.TestPermissoesNoBanco."
          "test_porteiro_nao_desativa_nem_reativa"]),
    caso("CT-52", ["RNF01"], POSITIVO, "Placa antiga desenhada",
         "Digitar a placa NEY4829 (modelo antigo) na Entrada e saída; abrir "
         "a ficha de quem tem essa placa; trocar para o tema escuro.",
         "A placa aparece cinza, com moldura escura e o hífen (NEY-4829), "
         "sem a faixa azul \"BRASIL\"; a Mercosul continua igual; no tema "
         "escuro os cantos não têm recorte branco.",
         ["test_interface.TestPlacaNoFormulario."
          "test_placa_antiga_e_mercosul_desenhadas_no_formulario",
          "test_componentes.TestComponentes."
          "test_placa_antiga_cinza_com_hifen_e_sem_brasil",
          "test_componentes.TestComponentes."
          "test_placa_sem_recorte_branco_nos_cantos_no_escuro"]),
    caso("CT-53", ["RF29", "RN43"], POSITIVO, "Editar usuário",
         "Administrador, em Usuários › Contas, escolhe o porteiro Paulo, "
         "clica em Editar, troca o nome para \"Paulo Souza\" e o perfil "
         "para Administrador e salva; depois tenta mudar o próprio perfil.",
         "O nome e o perfil mudam e o histórico registra \"Usuário "
         "alterado\" com o antes e o depois; mudar o próprio perfil é "
         "recusado (\"Você não pode mudar o seu próprio perfil\").",
         ["test_interface.TestEditarUsuario.test_admin_edita_nome_e_perfil",
          "test_interface.TestEditarUsuario."
          "test_nao_muda_o_proprio_perfil_mas_muda_o_nome",
          "test_dados.TestCrudNoBanco.test_editar_nome_e_perfil_de_usuario"]),

    # --- Linguagem de comandos (2.4): um bloco por fase do analisador -----
    caso_da_linguagem(
        "CT-54", "Léxico", ["RF14", "RN06"], POSITIVO,
        "CPF, placa, acentos e plurais viram tokens",
        "No campo Comando: \"SAÍDA 529.982.247-25\", \"52998224725\", "
        "\"ABC1234\", \"abc-1234\", \"ABC1D23\", \"Situação\", \"até\", "
        "\"visitantes\".",
        "Tokens COMANDO saida, CPF, NUMERO (11 dígitos: o sintático decide "
        "se é CPF ou celular), PLACA antiga e Mercosul (o autômato termina "
        "em q8), COMANDO situacao, PALAVRA_CHAVE ate e TIPO Visitante, cada "
        "um com a coluna.",
        ["test_linguagem.TestLexico.test_cpf_com_e_sem_pontos",
         "test_linguagem.TestLexico.test_placa_antiga_e_mercosul",
         "test_linguagem.TestLexico.test_automato_da_placa",
         "test_linguagem.TestLexico."
         "test_automato_aceita_o_mesmo_que_a_validacao",
         "test_linguagem.TestLexico.test_acentos_maiusculas_e_plurais"]),
    caso_da_linguagem(
        "CT-55", "Léxico", ["RF14", "RN06"], NEGATIVO,
        "Placa, data, símbolo e aspas fora da linguagem",
        "\"saida placa AB12345\"; \"buscar maria de 32/13/2026\"; "
        "\"entrada 529.982.247-25 visitante @casa\"; "
        "'desativar placa ABC1D23 motivo \"furto'.",
        "Erro [Léxico] com o ^ na coluna: \"AB12345\" não é uma placa "
        "(coluna 13); o dia 32 e o mês 13 não existem (coluna 17); o "
        "símbolo \"@\" não pertence à linguagem (coluna 34); texto sem "
        "aspas de fechamento. Nada é gravado.",
        ["test_linguagem.TestLexico.test_placa_invalida",
         "test_linguagem.TestLexico.test_data_invalida",
         "test_linguagem.TestLexico.test_simbolo_estranho",
         "test_linguagem.TestLexico.test_aspas_abertas",
         "test_linguagem.TestLexico.test_tokenizar_continua_depois_do_erro"]),
    caso_da_linguagem(
        "CT-56", "Sintático", ["RF14"], POSITIVO,
        "Os 13 comandos montam a árvore (gramática LL(1))",
        "Um exemplo de cada comando: entrada, saida, só o CPF ou a placa, "
        "cadastrar, editar, excluir, desativar, reativar, situacao, dentro, "
        "buscar, pendentes e ajuda.",
        "Cada linha vira a árvore do seu comando (ComandoEntrada, "
        "ComandoSaida...). A gramática não tem conflito LL(1): os conjuntos "
        "FIRST de cada escolha são disjuntos, e a EBNF do documento é a do "
        "código.",
        ["test_linguagem.TestSintatico."
         "test_cada_comando_monta_a_sua_arvore",
         "test_linguagem.TestGramatica.test_a_gramatica_e_ll1",
         "test_linguagem.TestGramatica.test_conflito_e_detectado",
         "test_linguagem.TestGramatica."
         "test_o_documento_tem_a_mesma_gramatica",
         "test_linguagem.TestGramatica.test_uma_funcao_por_regra",
         "test_linguagem.TestGramatica.test_os_exemplos_sao_validos"]),
    caso_da_linguagem(
        "CT-57", "Sintático", ["RF14"], NEGATIVO,
        "Ordem errada, falta argumento e comando desconhecido",
        "\"visitante entrada 52998224725\"; \"saida placa\" (a linha "
        "acaba); 'desativar 52998224725 \"briga\"'; \"entrda 52998224725 "
        "aluno\".",
        "Erro [Sintático]: esperado um comando, encontrado o tipo "
        "\"visitante\" (dica: o comando vem primeiro); fim da linha: "
        "esperado a PLACA; esperado \"motivo\" antes do texto; comando "
        "desconhecido \"entrda\" — \"Você quis dizer entrada?\" (Tab "
        "corrige). O console mostra a linha e o ^.",
        ["test_linguagem.TestSintatico.test_ordem_errada",
         "test_linguagem.TestSintatico.test_falta_argumento",
         "test_linguagem.TestSintatico.test_falta_motivo",
         "test_linguagem.TestSintatico.test_comando_desconhecido_sugere",
         "test_interface_comando.TestCampoComando."
         "test_erro_no_console_no_formato_do_compilador"]),
    caso_da_linguagem(
        "CT-58", "Semântico", ["RN03", "RN05", "RN06", "RN12"], NEGATIVO,
        "Frase bem escrita que não faz sentido",
        "\"entrada 12345678900 aluno\" (dígito errado); \"entrada\" de quem "
        "já está no campus; \"saida\" de quem já saiu; \"entrada ... placa "
        "QWE1E34\" com a placa desativada.",
        "Erro [Semântico] com a regra: os dígitos verificadores não "
        "conferem (RN06); está no campus desde 08:14 (RN05, com a dica "
        "\"saida CPF\"); não está no campus, saiu hoje às 09:34 (RN03); "
        "veículo desativado (RN12, o ^ na placa) e a recusa vai ao "
        "histórico, como no formulário.",
        ["test_linguagem.TestSemantico.test_cpf_invalido",
         "test_linguagem.TestSemantico.test_ja_no_campus",
         "test_linguagem.TestSemantico.test_saida_sem_entrada_aberta",
         "test_linguagem.TestSemantico.test_desativado",
         "test_interface_comando.TestComandoAbreOsDialogos."
         "test_desativado_vai_ao_historico"]),
    caso_da_linguagem(
        "CT-59", "Semântico", ["RN02", "RN12", "RN46"], NEGATIVO,
        "Porteiro em comando de administrador",
        "Porteiro digita \"excluir 11144477735\", 'desativar 11144477735 "
        "motivo \"teste de motivo\"' e \"reativar placa QWE1E34\".",
        "Erro [Semântico] na coluna 1: só o administrador (RN02/RN12/RN42). "
        "Nada muda no banco (que também recusaria). O administrador passa "
        "na mesma checagem.",
        ["test_linguagem.TestSemantico.test_porteiro_em_comando_de_admin",
         "test_interface_comando.TestPrivacidade."
         "test_comando_de_admin_recusado_para_o_porteiro"]),
    caso_da_linguagem(
        "CT-60", "Semântico", ["RF14", "RN46"], POSITIVO,
        "Aviso de tipo, opção repetida e período invertido",
        "\"entrada 11144477735 prestador sem carro\" (o cadastro diz "
        "Visitante); \"entrada ... placa ABC1234 placa XYZ9876\"; \"buscar "
        "maria de 15/10/2026 ate 01/10/2026\".",
        "Tipo diferente é um AVISO (como uma conversão de tipo): pergunta "
        "\"Registrar como Prestador de serviço?\" e, com Não, nada é "
        "gravado. A placa dada duas vezes é \"variável declarada duas "
        "vezes\" (erro). O período que termina antes de começar é erro.",
        ["test_linguagem.TestSemantico.test_tipo_diferente_e_aviso",
         "test_interface_comando.TestComandoAbreOsDialogos."
         "test_tipo_diferente_pergunta_antes",
         "test_linguagem.TestSemantico.test_opcao_repetida_e_contraditoria",
         "test_linguagem.TestSemantico.test_periodo_invertido"]),
    caso_da_linguagem(
        "CT-61", "Semântico", ["RN17", "RN24"], POSITIVO,
        "Horário e retroativo pedem a autorização",
        "\"entrada ... visitante sem carro em 18/10/2026 08:00\" (dia já "
        "fechado); às 19:30, \"entrada ... visitante sem carro as 19:10\" "
        "(fora da janela 08:00–18:00); \"as 20:00\" (futuro).",
        "Os dois primeiros passam no semântico com a checagem "
        "AUTORIZACAO (a execução abre a autorização do administrador); o "
        "horário no futuro é erro (RN07).",
        ["test_linguagem.TestSemantico."
         "test_retroativo_e_horario_pedem_autorizacao",
         "test_linguagem.TestSemantico.test_saida_retroativa_e_futuro"]),
    caso_da_linguagem(
        "CT-62", "Execução", ["RF02", "RF14"], POSITIVO,
        "Campo Comando (F2 ou Ctrl+K) e a Saída rápida de antes",
        "F2 ou Ctrl+K em qualquer página; no campo, só \"111.444.777-35\" "
        "ou só \"qwe-1234\" e Enter.",
        "O cursor vai ao campo Comando (no lugar da Saída rápida). Só o "
        "CPF dá a saída da pessoa (com a pergunta do carro); só a placa "
        "tira o carro (\"Beto saiu junto com o carro?\"), como antes.",
        ["test_interface_comando.TestCampoComando."
         "test_f2_e_ctrl_k_levam_ao_campo",
         "test_interface_comando.TestSaidaRapidaContinua."
         "test_so_o_cpf_da_a_saida",
         "test_interface_comando.TestSaidaRapidaContinua."
         "test_so_a_placa_tira_o_carro",
         "test_interface.TestSaidaRapida.test_saida_pelo_cpf_formatado",
         "test_interface.TestSaidaRapida."
         "test_placa_tira_o_carro_e_pergunta_pelo_responsavel"]),
    caso_da_linguagem(
        "CT-63", "Léxico", ["RF14", "RN33"], POSITIVO,
        "Realce, Tab e o máximo de 200 caracteres",
        "Digitar \"entrada 52998224725 visitante placa ABC1D23\"; \"entr\" + "
        "Tab; \"situacao bet\" + Tab; colar 300 caracteres.",
        "Cada token ganha a sua cor a cada tecla (o erro, vermelho e "
        "sublinhado); Tab completa \"entrada\" e troca o pedaço do nome "
        "pelo CPF de Beto Rocha; a colagem entra cortada em 200.",
        ["test_interface_comando.TestCampoComando.test_realce_por_token",
         "test_interface_comando.TestCampoComando."
         "test_tab_completa_comando_e_palavra",
         "test_interface_comando.TestCampoComando."
         "test_tab_troca_o_nome_pelo_cpf",
         "test_interface_comando.TestCampoComando.test_uma_linha_com_maximo"]),
    caso_da_linguagem(
        "CT-64", "Execução", ["RN14", "RN46", "RNF05"], POSITIVO,
        "Privacidade: CPF mascarado e nada gravado",
        "Porteiro digita o CPF inteiro em \"situacao\", \"entrada\" e "
        "\"dentro\", abre o modo didático e usa o Tab; um texto marcador "
        "vai em \"buscar\" e em \"desativar\".",
        "Resposta, console, modo didático e tabela de símbolos mostram "
        "***.444.777-**; o Tab escreve o CPF mascarado e o comando ainda "
        "funciona. O texto do comando não aparece no log, no histórico nem "
        "no arquivo do banco.",
        ["test_interface_comando.TestPrivacidade."
         "test_porteiro_ve_o_cpf_mascarado",
         "test_interface_comando.TestPrivacidade."
         "test_tab_do_porteiro_escreve_o_cpf_mascarado",
         "test_interface_comando.TestPrivacidade."
         "test_o_texto_do_comando_nao_e_gravado",
         "test_linguagem.TestSemantico.test_porteiro_ve_o_cpf_mascarado",
         "test_linguagem.TestLexico."
         "test_mascarar_linha_mantem_as_colunas"]),
    caso_da_linguagem(
        "CT-65", "Semântico", ["RF32"], POSITIVO,
        "Modo didático mostra onde o comando parou",
        "Ligar \"Didático\" e digitar \"entrada 11144477735 visitante\" de "
        "quem já está no campus; depois \"saida placa AB12345\".",
        "Faixa Léxico ✓ → Sintático ✓ → Semântico ✗ → Execução —, a mesma "
        "mensagem do console e as abas Tokens, Árvore (o nó com erro em "
        "vermelho), Símbolos e Checagens (a última, RN05, \"Parou "
        "aqui\"); no erro léxico, a árvore diz que parou no Léxico.",
        ["test_interface_comando.TestModoDidatico."
         "test_mostra_onde_parou_com_o_mesmo_erro",
         "test_interface_comando.TestModoDidatico."
         "test_erro_lexico_e_digitacao",
         "test_interface_comando.TestModoDidatico."
         "test_no_com_erro_fica_vermelho",
         "test_linguagem.TestSemantico.test_fases_e_simbolos"]),
    caso_da_linguagem(
        "CT-66", "Execução", ["RN24", "RN34", "RN40", "RN46"], POSITIVO,
        "O comando abre os mesmos diálogos do formulário",
        "\"entrada 11144477735\" de quem tem placa no cadastro; \"saida\" de "
        "quem tem dois carros; entrada retroativa de dia fechado.",
        "Abre \"Beto vai entrar de carro?\", \"Com qual carro Beto está "
        "saindo?\" e a autorização do administrador; cancelar não grava "
        "nada; com a senha, grava a \"Exceção autorizada\".",
        ["test_interface_comando.TestComandoAbreOsDialogos."
         "test_vai_entrar_de_carro",
         "test_interface_comando.TestComandoAbreOsDialogos."
         "test_com_qual_carro",
         "test_interface_comando.TestComandoAbreOsDialogos."
         "test_autorizacao_do_administrador"]),
    caso_da_linguagem(
        "CT-67", "Execução", ["RF01", "RF02", "RN46"], POSITIVO,
        "Entrada e saída: o banco fica igual ao do formulário",
        "Dois bancos iguais: num, o formulário; no outro, \"entrada "
        "529.982.247-25 visitante nome \"Ana Silva\" cel ... placa "
        "ABC1D23\", \"entrada CPF\" (pergunta do carro), \"saida CPF sem "
        "carro\" e a entrada retroativa autorizada.",
        "Visitas, estadias dos carros, pessoas e histórico (quem fez o "
        "quê) iguais nos dois bancos: o comando é só outra porta de "
        "entrada.",
        ["test_interface_comando.TestExecucaoIgualAoFormulario."
         "test_entrada_de_pessoa_nova",
         "test_interface_comando.TestExecucaoIgualAoFormulario."
         "test_entrada_com_a_pergunta_do_carro",
         "test_interface_comando.TestExecucaoIgualAoFormulario."
         "test_saida_a_pe",
         "test_interface_comando.TestExecucaoIgualAoFormulario."
         "test_retroativo_com_autorizacao"]),
    caso_da_linguagem(
        "CT-68", "Execução", ["RF27", "RF28", "RF10", "RN46"], POSITIVO,
        "CRUD de pessoas pela linguagem",
        "Administrador: cadastrar, editar (celular e tipo), desativar, "
        "reativar e excluir a mesma pessoa pelos diálogos de Pessoas num "
        "banco e pelos comandos no outro.",
        "Os dois bancos ficam iguais (pessoas, desativações e histórico); "
        "a página Pessoas mostra a pessoa cadastrada pelo comando.",
        ["test_interface_comando.TestExecucaoIgualAoFormulario."
         "test_crud_da_pessoa",
         "test_interface_comando.TestExecucaoIgualAoFormulario."
         "test_cadastrar_atualiza_a_pagina_pessoas",
         "test_linguagem.TestSemantico.test_crud_da_pessoa"]),
    caso_da_linguagem(
        "CT-69", "Semântico", ["RF33", "RN47"], POSITIVO,
        "Vários carros no cadastrar e no editar",
        "cadastrar 123.456.789-09 visitante nome \"Rui Lima\" cel "
        "31987651234 placa NEY4829 placa ABC1D23; depois \"editar ... placa "
        "NEY4829 sem placa QWE1E34\".",
        "O cadastro fica com os dois carros (NEY4829 é a principal); o "
        "editar inclui um carro e tira outro, e a principal continua a "
        "mesma enquanto não for tirada.",
        ["test_linguagem.TestSemantico."
         "test_varias_placas_no_cadastrar_e_no_editar"]),
    caso_da_linguagem(
        "CT-70", "Semântico", ["RN47"], NEGATIVO,
        "Carro que não é da pessoa, incluído e tirado juntos, mais de 5",
        "\"editar ... sem placa NEY4829\" (não está no cadastro); \"placa "
        "NEY4829 sem placa NEY4829\"; cadastrar com 6 placas; \"sem NEY4829\" "
        "(falta a palavra placa).",
        "Erro semântico com a regra RN47 e o ^ no carro (\"não está no "
        "cadastro\", \"incluído e tirado\", \"No máximo 5 placas\"); o "
        "último é erro sintático: esperado \"placa\". Nada é gravado.",
        ["test_linguagem.TestSemantico.test_varias_placas_erros"]),
    caso_da_linguagem(
        "CT-71", "Execução", ["RF33", "RN46", "RN47"], POSITIVO,
        "Vários carros pela linguagem = pelo formulário",
        "Num banco, Nova pessoa com dois carros e Editar trocando um deles; "
        "no outro, os mesmos passos por cadastrar e editar; depois "
        "\"situacao\".",
        "Os dois bancos ficam iguais (pessoas, carros e histórico) e o "
        "situacao mostra \"2 carros no cadastro: ABC1D23, QWE1E34\".",
        ["test_interface_comando.TestExecucaoIgualAoFormulario."
         "test_varias_placas_igual_ao_formulario"]),

    # --- Versão 2.5: pessoas com mais de um carro ------------------------
    caso("CT-72", ["RF27", "RF33", "RN47"], POSITIVO,
         "Cadastrar pessoa com mais de uma placa",
         "Pessoas › Nova pessoa: CPF, nome, celular e tipo; no campo Placas, "
         "BRA2E19 + Enter e NEY4829 + Enter; Cadastrar.",
         "As duas placas aparecem embaixo do campo e ficam no cadastro (a 1ª "
         "é a principal); a lista mostra \"BRA2E19 +1\" e a ficha tem a "
         "linha Carro com as duas.",
         ["test_interface.TestVariasPlacas.test_nova_pessoa_com_duas_placas",
          "test_interface.TestVariasPlacas."
          "test_ficha_lista_e_escolha_do_carro",
          "test_placas.TestPlacasNoBanco."
          "test_cadastro_com_varias_placas_principal_primeiro",
          "test_placas.TestPlacasNoBanco."
          "test_a_mesma_placa_pode_ser_de_duas_pessoas"]),
    caso("CT-73", ["RN47", "RN33"], NEGATIVO,
         "Placa inválida, repetida ou mais de 5",
         "No campo Placas: AB12 + Enter; a placa que já está na lista; e "
         "seis placas no cadastro (direto no banco).",
         "\"Placa inválida: AB12\" na faixa do diálogo; a repetida é "
         "ignorada; a sexta é recusada (\"No máximo 5 placas por "
         "pessoa\"). Nada é gravado.",
         ["test_interface.TestVariasPlacas.test_placa_invalida_ou_repetida",
          "test_placas.TestValidarPlacas.test_no_maximo_cinco",
          "test_placas.TestValidarPlacas."
          "test_placa_invalida_e_nomeada_na_mensagem",
          "test_placas.TestPlacasNoBanco."
          "test_cadastro_recusa_placa_invalida_e_passar_do_maximo"]),
    caso("CT-74", ["RF28", "RN47", "RN35"], POSITIVO,
         "Editar: incluir e tirar carros",
         "Editar a pessoa com QWE1234: incluir NEY4829 e ABC1D23, tirar "
         "QWE1234 pelo ×, salvar. Num carro com alguém na lista de quem "
         "pode retirar, tirar esse carro do cadastro.",
         "O cadastro fica com NEY4829 (principal) e ABC1D23; o histórico "
         "registra as placas incluídas e tiradas; quem podia retirar o carro "
         "tirado sai da lista.",
         ["test_interface.TestVariasPlacas."
          "test_enter_no_campo_adiciona_e_o_x_tira",
          "test_placas.TestPlacasNoBanco.test_editar_inclui_e_tira_placas",
          "test_placas.TestPlacasNoBanco."
          "test_tirar_a_placa_remove_quem_podia_retirar_aquele_carro"]),
    caso("CT-75", ["RN34", "RN47", "RN12"], POSITIVO,
         "Entrada de quem tem dois carros: escolhe com qual",
         "Beto tem QWE1234 e NEY4829. O porteiro digita o CPF dele e "
         "Registrar entrada; na pergunta, escolhe NEY4829.",
         "O campo Placa avisa \"2 carros no cadastro\"; a pergunta tem um "
         "botão por carro (o que já está no estacionamento não aparece); a "
         "visita e a estadia ficam com NEY4829. Carro desativado escolhido: "
         "\"Acesso negado\".",
         ["test_interface_entrada_de_carro.TestEntradaComVariosCarros."
          "test_um_botao_por_carro_e_entra_com_o_escolhido",
          "test_interface_entrada_de_carro.TestEntradaComVariosCarros."
          "test_carro_que_ja_esta_no_estacionamento_nao_aparece",
          "test_interface_entrada_de_carro.TestEntradaComVariosCarros."
          "test_carro_desativado_escolhido_e_recusado",
          "test_interface_entrada_de_carro.TestEntradaComVariosCarros."
          "test_dica_do_campo_placa_conta_os_carros",
          "test_placas.TestPlacasNoBanco."
          "test_visita_com_outro_carro_guarda_a_placa"]),
    caso("CT-76", ["RN47", "RN35", "RN12"], POSITIVO,
         "Ficha: escolher o carro de que se fala",
         "Na ficha de quem tem dois carros, clicar no segundo na linha "
         "Carro; adicionar alguém em Quem pode retirar; Desativar placa.",
         "A placa desenhada muda; a pessoa adicionada vale só para aquele "
         "carro; o carro desativado fica em vermelho na linha Carro.",
         ["test_interface.TestVariasPlacas."
          "test_ficha_lista_e_escolha_do_carro",
          "test_interface.TestVariasPlacas.test_desativar_o_carro_escolhido",
          "test_placas.TestPlacasNoBanco."
          "test_autorizado_so_para_um_carro_da_pessoa"]),
    caso("CT-77", ["RN47"], POSITIVO,
         "Banco da 2.4 atualizado para a 2.5",
         "Abrir com a 2.5 um banco da 2.4 (esquema v11) com visitas de "
         "carros diferentes da mesma pessoa.",
         "O banco vira v12 com backup antes; nada se perde; o cadastro de "
         "cada pessoa passa a ter a placa principal e as placas das visitas.",
         ["test_placas.TestMigracaoV11ParaV12."
          "test_v11_vira_v12_com_as_placas_das_visitas",
          "test_placas.TestMigracaoV11ParaV12.test_migrar_de_novo_nao_duplica"]),
    caso("CT-78", ["RF10", "RNF01"], POSITIVO,
         "Abrir Pessoas desativadas e Veículos desativados",
         "Clicar nas subabas Pessoas desativadas e Veículos desativados, com "
         "e sem \"Mostrar reativadas\".",
         "As listas abrem e o programa continua aberto (na 2.4 ele fechava "
         "com \"maximum recursion depth exceeded\"); um erro inesperado "
         "numa tela mostra o aviso sem fechar o programa.",
         ["test_interface.TestAbaDesativadas."
          "test_abrir_a_aba_nao_entra_em_recursao",
          "test_interface.TestAbertura."
          "test_erro_inesperado_com_a_pilha_cheia_nao_derruba"]),

    # --- Revisão 2.5.1: testes por ataque (aleatórios, fuzz, concorrência)
    caso("CT-79", ["RN25", "RN47", "RF09"], POSITIVO,
         "Desfazer a saída depois de corrigir a placa",
         "A visita entra com o carro BRA2E19 e sai com ele; a placa da "
         "visita é corrigida para RST4A56 (ou apagada); a saída é desfeita.",
         "Volta ao estacionamento o carro da placa corrigida (ou nenhum, se "
         "a visita ficou sem placa). Antes, voltava o BRA2E19 ligado a uma "
         "visita que diz RST4A56 (achado pelas sequências aleatórias).",
         ["test_aleatorio.TestCasosAchados."
          "test_desfazer_saida_depois_de_corrigir_a_placa",
          "test_aleatorio.TestCasosAchados."
          "test_desfazer_saida_depois_de_apagar_a_placa"]),
    caso("CT-80", ["RN05", "RN25", "RN47"], POSITIVO,
         "Sequências aleatórias: as regras nunca quebram",
         "750 operações sorteadas (entradas, saídas, desfazer, correções, "
         "exclusões, carros, desativações, cadastro com várias placas, quem "
         "pode retirar, Encerrar o dia), conferindo tudo depois de cada uma. "
         "Na revisão rodaram também 32 sementes de 1.500 passos (48 mil "
         "operações).",
         "Nenhuma regra quebra: um CPF com no máximo uma visita aberta, uma "
         "placa com no máximo uma estadia aberta, a placa principal entre os "
         "carros da pessoa, o histórico só cresce, contadores certos, banco "
         "íntegro; recusa é sempre a mensagem para o usuário (ErroDados).",
         ["test_aleatorio.TestSequenciasAleatorias."
          "test_invariantes_em_sequencias_aleatorias"]),
    caso("CT-81", ["RN05", "RN25", "RN11"], POSITIVO,
         "Duas estações no mesmo banco ao mesmo tempo",
         "Threads com o banco aberto no mesmo arquivo: a mesma pessoa "
         "entrando nas duas, a mesma saída, o mesmo carro, 8 estações "
         "gravando 15 entradas cada, a correção de uma visita que a outra "
         "estação mudou e o mesmo cadastro com placas nas duas.",
         "Uma estação ganha e a outra recebe a mensagem (ou nada a fazer); "
         "nenhuma entrada se perde, nada fica duplicado e nunca aparece um "
         "erro do SQLite.",
         ["test_duas_estacoes.TestDuasEstacoes.test_mesma_pessoa_entrando_nas_duas",
          "test_duas_estacoes.TestDuasEstacoes.test_mesma_saida_nas_duas",
          "test_duas_estacoes.TestDuasEstacoes."
          "test_mesmo_carro_entrando_com_duas_pessoas",
          "test_duas_estacoes.TestDuasEstacoes."
          "test_muitas_entradas_juntas_nenhuma_se_perde",
          "test_duas_estacoes.TestDuasEstacoes."
          "test_correcao_com_a_visita_mudada_pela_outra",
          "test_duas_estacoes.TestDuasEstacoes."
          "test_cadastro_com_placas_ao_mesmo_tempo"]),
    caso("CT-82", ["RN33"], NEGATIVO,
         "Textos estranhos nas validações",
         "Milhares de textos sorteados (acentos, emoji, controle, números "
         "enormes, SQL, datas impossíveis como 31/04 e 29/02/2025) em todos "
         "os campos: visita, placas, desativação, horários, feriados, "
         "eventos, vagas, validade, senha e login.",
         "Cada função responde \"pode\" ou \"não pode\" com a mensagem; "
         "nenhuma exceção.",
         ["test_entradas_estranhas.TestEntradasEstranhas.test_visita",
          "test_entradas_estranhas.TestEntradasEstranhas.test_campos_soltos",
          "test_entradas_estranhas.TestEntradasEstranhas."
          "test_configuracoes_e_regras",
          "test_entradas_estranhas.TestEntradasEstranhas.test_contas"]),
    caso("CT-83", ["RF03", "RF11"], POSITIVO,
         "Atividade: o filtro acha evento antigo",
         "Usuários › Atividade com mais de 200 eventos depois de um "
         "\"Cadastro de entrada\"; filtrar por \"cadastro de\".",
         "O evento antigo aparece (o filtro procura no histórico inteiro, no "
         "banco, depois da pausa na digitação). Antes, só os 200 mais "
         "recentes eram filtrados.",
         ["test_interface.TestAbaUsuarios."
          "test_filtro_da_atividade_acha_evento_antigo",
          "test_interface.TestAbaUsuarios.test_filtro_da_atividade"]),
    caso("CT-84", ["RF33", "RN47"], POSITIVO,
         "Ficha com 5 carros",
         "Na ficha de quem tem 5 carros (um deles desativado), escolher o "
         "último na linha Carro.",
         "Com mais de 3 carros a linha Carro é uma lista (os botões não "
         "cabiam: o 4º saía cortado e o 5º sumia); o desativado aparece "
         "marcado; a placa desenhada e a lista de quem pode retirar seguem "
         "a escolha.",
         ["test_interface.TestVariasPlacas.test_cinco_carros_viram_uma_lista"]),
    caso("CT-85", ["RNF03"], POSITIVO,
         "Lista de Pessoas e buscar com período no histórico grande",
         "Banco com 2 anos (146 mil visitas, 20 mil pessoas): abrir Pessoas "
         "sem busca; buscar com período.",
         "As consultas usam os índices (uma visita aberta por CPF; a "
         "entrada): a lista de Pessoas caiu de 0,3 s para 12 ms.",
         ["test_desempenho.TestPlanoDasConsultas."
          "test_pessoas_no_campus_primeiro_usa_o_indice_de_visita_aberta",
          "test_desempenho.TestPlanoDasConsultas."
          "test_buscar_com_periodo_usa_o_indice_da_entrada"]),
    caso("CT-86", ["RN33", "RNF05"], NEGATIVO,
         "Exportação CSV sem fórmula do Excel",
         "Exportar textos que começam com =, +, -, @, TAB ou retorno de carro.",
         "A célula recebe um apóstrofo na frente: o Excel mostra o texto e "
         "não executa a fórmula (CSV injection, OWASP).",
         ["test_backup.TestCelulaDoCsv."
          "test_textos_que_o_excel_leria_como_formula"]),
    caso_da_linguagem(
        "CT-87", "Execução", ["RF03", "RN46"], POSITIVO,
        "buscar com período num histórico grande",
        "Ana tem 210 visitas recentes e 3 em janeiro de 2025: \"buscar ana "
        "de 01/01/2025 ate 31/01/2025\". Também: hoje, ontem, semana, mes.",
        "\"3 visitas encontradas\" (o período e o tipo vão para o SQL antes "
        "do limite de 200; antes respondia \"Nada encontrado\"); semana = 7 "
        "dias e mes = 30 dias, contando hoje.",
        ["test_linguagem_caminhos.TestBuscarPelaTela."
         "test_buscar_periodo_antigo_com_historico_grande",
         "test_linguagem_caminhos.TestBuscarNoBanco."
         "test_periodo_e_tipo_vao_para_o_sql_antes_do_limite",
         "test_linguagem_caminhos.TestCaminhosDoSemantico."
         "test_periodos_do_buscar"]),
    caso_da_linguagem(
        "CT-88", "Léxico", ["RN14", "RN46"], NEGATIVO,
        "Fuzz: linhas aleatórias e a privacidade do porteiro",
        "1.500 linhas sorteadas (palavras da linguagem misturadas, CPFs, "
        "placas, datas, aspas sem fechamento, símbolos, emoji, linhas "
        "cortadas) nas três fases, como administrador e como porteiro; "
        "\"entrada \\\"Ana 52998224725\" como porteiro.",
        "A análise nunca levanta exceção, para numa fase com o ^ dentro da "
        "linha e não grava nada; o porteiro nunca vê um CPF inteiro (antes, "
        "depois de aspas sem fechamento, o CPF aparecia na linha repetida "
        "pelo console).",
        ["test_linguagem_fuzz.TestFuzzDaLinguagem.test_linhas_aleatorias",
         "test_linguagem.TestLexico."
         "test_cpf_depois_de_aspas_sem_fechamento_e_mascarado"]),
    caso("CT-89", ["RF09", "RN47", "RN35"], POSITIVO,
         "Corrigir a placa digitada errado tira a placa dos carros",
         "Ana entra com ABC1D28 (digitado errado; o carro é o ABC1D23) e a "
         "visita é corrigida. Outra visita com NEY4829 é corrigida, mas uma "
         "visita anterior também usou NEY4829. Uma visita do CPF errado é "
         "passada para o CPF certo.",
         "ABC1D28 sai dos carros de Ana (e de quem podia retirá-lo) e não "
         "aparece mais em \"Vai entrar de carro?\"; NEY4829 fica, porque "
         "outra visita a usou; a placa sai também da pessoa do CPF errado; "
         "se era a principal, a principal vira a do carro mais recente; o "
         "histórico registra.",
         ["test_placas.TestCorrecaoDaPlaca."
          "test_placa_digitada_errado_sai_dos_carros",
          "test_placas.TestCorrecaoDaPlaca.test_placa_usada_em_outra_visita_fica",
          "test_placas.TestCorrecaoDaPlaca."
          "test_principal_tirada_passa_para_a_da_visita_mais_recente",
          "test_placas.TestCorrecaoDaPlaca."
          "test_cpf_trocado_tira_a_placa_da_pessoa_errada",
          "test_placas.TestCorrecaoDaPlaca."
          "test_quem_podia_retirar_o_carro_errado_sai_da_lista"]),
    # --- Versão 3.0: o enunciado da Atividade A3, tela por tela --------
    caso("CT-90", ["RF34", "RNF02"], POSITIVO,
         "Login: mostrar e ocultar a senha",
         "Digitar a senha e marcar e desmarcar o Checkbutton Mostrar senha.",
         "A senha começa escondida, aparece com a marca e volta a esconder; "
         "o texto digitado não muda.",
         ["test_enunciado_a3.TestTela1Login.test_senha_comeca_escondida_e_o_checkbutton_mostra",
          "test_enunciado_a3.TestPrimeiroAcessoComCheckbutton."
          "test_mostra_as_duas_senhas_e_limpar_nao_apaga_o_que_nao_deve"]),
    caso("CT-91", ["RF34"], POSITIVO, "Login: Limpar e a imagem do logo",
         "Clicar em Limpar depois de um erro; abrir o login.",
         "Os campos esvaziam, a senha volta a esconder e o erro some. O logo é "
         "uma imagem (assets/logo_portaria.png), que também vai no .exe.",
         ["test_enunciado_a3.TestTela1Login.test_limpar_esvazia_esconde_a_senha_e_o_erro",
          "test_enunciado_a3.TestTela1Login.test_logo_e_uma_imagem_de_verdade",
          "test_enunciado_a3.TestTela1Login.test_arquivo_do_logo_existe_e_vai_no_exe"]),
    caso("CT-92", ["RF34", "RN38"], NEGATIVO,
         "Login: campos vazios e dados incorretos",
         "Entrar com campos vazios, só espaços, senha errada e usuário que "
         "não existe.",
         "Nenhum entra. Vazio pede para informar; errado dá a mesma mensagem "
         "para usuário e senha (não entrega quem existe).",
         ["test_enunciado_a3.TestTela1Login.test_impede_campos_vazios",
          "test_enunciado_a3.TestTela1Login.test_dados_incorretos_dao_mensagem_de_erro",
          "test_enunciado_a3.TestTela1Login.test_usuario_que_nao_existe_da_a_mesma_mensagem"]),
    caso("CT-93", ["RF01", "RN48"], POSITIVO,
         "Cadastro completo: salva no SQLite, gera o código e confirma",
         "Preencher nome, CPF, telefone, tipo, empresa, data, horário e motivo "
         "e clicar em Cadastrar.",
         "A visita e a empresa ficam no banco; a faixa verde confirma com o "
         "código (\"Código 001\"), cada cadastro tem o seu, e o formulário "
         "fica limpo.",
         ["test_enunciado_a3.TestTela2Cadastro.test_salva_tudo_no_sqlite",
          "test_enunciado_a3.TestTela2Cadastro.test_gera_codigo_e_confirma_depois_de_salvar",
          "test_enunciado_a3.TestTela2Cadastro.test_cada_cadastro_tem_o_seu_codigo"]),
    caso("CT-94", ["RN01", "RN06", "RN48"], NEGATIVO,
         "Cadastro: cada campo obrigatório e CPF inválido",
         "Deixar vazio (ou só com espaços) cada campo; CPF com dígitos errados "
         "ou repetidos; data e horário que não existem.",
         "Nada é gravado e a mensagem diz o campo.",
         ["test_enunciado_a3.TestTela2Cadastro.test_cada_campo_obrigatorio",
          "test_enunciado_a3.TestTela2Cadastro.test_so_espacos_nao_contam",
          "test_enunciado_a3.TestTela2Cadastro.test_cpf_vazio_ou_invalido_e_recusado",
          "test_enunciado_a3.TestTela2Cadastro.test_data_ou_horario_invalidos"]),
    caso("CT-95", ["RN05"], NEGATIVO, "Cadastro: não duplica a entrada",
         "Cadastrar duas vezes o mesmo CPF, sem saída.",
         "A segunda é recusada: \"entrada sem saída\".",
         ["test_enunciado_a3.TestTela2Cadastro.test_nao_duplica_a_entrada_em_aberto",
          "test_enunciado_a3.TestTela3Controle.test_impede_segunda_entrada_sem_saida"]),
    caso("CT-96", ["RF35"], POSITIVO, "Cadastro: Limpar e Cancelar",
         "Preencher e clicar em Limpar; preencher e clicar em Cancelar.",
         "Limpar esvazia tudo e volta a data e o horário para agora; Cancelar "
         "não grava e vai ao Controle de acesso.",
         ["test_enunciado_a3.TestTela2Cadastro.test_limpar_esvazia_todos_os_campos",
          "test_enunciado_a3.TestTela2Cadastro.test_cancelar_descarta_e_vai_ao_controle"]),
    caso("CT-97", ["RN33", "RN14", "RN48"], NEGATIVO,
         "Motivo: limite, colagem, SQL injection e CPF no texto",
         "Colar 250 caracteres, texto com quebras de linha, comando SQL, "
         "emoji e um CPF no motivo.",
         "Para em 200, fica numa linha, é gravado como texto, sem quebrar nada, "
         "e o CPF vai mascarado.",
         ["test_enunciado_a3.TestTela2Cadastro.test_motivo_tem_limite_e_contador",
          "test_enunciado_a3.TestTela2Cadastro.test_motivo_colado_com_quebras_vira_uma_linha_so",
          "test_enunciado_a3.TestTela2Cadastro.test_codigo_e_sql_injection_no_motivo_nao_quebram",
          "test_enunciado_a3.TestTela2Cadastro.test_cpf_no_motivo_vai_mascarado_na_tela_do_porteiro"]),
    caso("CT-98", ["RN48"], POSITIVO,
         "Quem já veio traz a empresa e o motivo; cadastro antigo completa",
         "Digitar o CPF de quem já veio; de quem veio antes da 3.0, sem empresa.",
         "Os campos vêm preenchidos. O cadastro antigo pede a empresa e o "
         "motivo uma vez e fica completo.",
         ["test_enunciado_a3.TestTela2Cadastro.test_cpf_de_quem_ja_veio_traz_empresa_e_ultimo_motivo",
          "test_enunciado_a3.TestTela2Cadastro.test_cadastro_antigo_sem_empresa_pede_para_completar",
          "test_enunciado_a3.TestTela3Controle.test_registrar_entrada_com_cadastro_antigo_abre_o_cadastro"]),
    caso("CT-99", ["RF35", "RF03"], POSITIVO,
         "Controle: as colunas, a pesquisa e o filtro",
         "Pesquisar por nome, CPF e empresa; filtrar por Todos, Dentro, Saiu "
         "e por tipo de acesso; juntar os dois.",
         "A tabela tem Código, Nome, CPF, Tipo de acesso, Entrada, Saída e "
         "Situação e mostra só as linhas certas.",
         ["test_enunciado_a3.TestTela3Controle.test_colunas_do_enunciado",
          "test_enunciado_a3.TestTela3Controle.test_pesquisa_localiza_por_nome_cpf_e_empresa",
          "test_enunciado_a3.TestTela3Controle.test_filtro_todos_dentro_saiu_e_tipos",
          "test_enunciado_a3.TestTela3Controle.test_filtro_e_pesquisa_juntos"]),
    caso("CT-100", ["RF35", "RN05"], POSITIVO,
         "Controle: Registrar entrada e saída com horário automático",
         "Selecionar uma pessoa e clicar em Registrar entrada; depois, em "
         "Registrar saída.",
         "Os horários são os do relógio do sistema, a situação passa de "
         "\"Dentro\" para \"Saiu\" e a tabela atualiza a cada operação.",
         ["test_enunciado_a3.TestTela3Controle.test_registrar_entrada_com_horario_automatico",
          "test_enunciado_a3.TestTela3Controle.test_registrar_saida_com_horario_automatico",
          "test_enunciado_a3.TestTela3Controle.test_situacao_dentro_ou_saiu",
          "test_enunciado_a3.TestTela3Controle.test_tabela_atualiza_depois_de_cada_operacao"]),
    caso("CT-101", ["RF35"], NEGATIVO, "Controle: ações sem seleção ou repetidas",
         "Clicar em Registrar entrada e saída sem selecionar; dar saída em "
         "quem já saiu.",
         "Avisa e não grava; a saída de quem já saiu não muda o horário.",
         ["test_enunciado_a3.TestTela3Controle.test_registrar_entrada_sem_selecao_avisa",
          "test_enunciado_a3.TestTela3Controle.test_registrar_saida_sem_selecao_avisa",
          "test_enunciado_a3.TestTela3Controle.test_saida_de_quem_ja_saiu_e_recusada"]),
    caso("CT-102", ["RF35"], POSITIVO, "Controle: Atualizar e Voltar",
         "Outra estação grava uma entrada; clicar em Atualizar e em Voltar.",
         "Atualizar mostra a entrada nova; Voltar abre o Cadastro.",
         ["test_enunciado_a3.TestTela3Controle.test_atualizar_le_o_que_a_outra_estacao_gravou",
          "test_enunciado_a3.TestTela3Controle.test_voltar_vai_ao_cadastro"]),
    caso("CT-103", ["RF37", "RN48"], POSITIVO,
         "Desafio extra: registro de prestadores de serviços",
         "Filtrar o Controle por Prestador de serviço.",
         "A tabela troca a Placa e o Tipo pela Empresa e o Motivo; ao voltar "
         "para Todos, as colunas voltam.",
         ["test_enunciado_a3.TestTela3Controle.test_prestador_mostra_empresa_e_motivo"]),
    caso("CT-104", ["RF36", "RN49"], POSITIVO,
         "Desafio extra: registro de ocorrências",
         "Registrar, pesquisar, filtrar, marcar como resolvida e excluir.",
         "Fica no livro com a categoria, o usuário e a situação; o administrador "
         "exclui com confirmação; tudo no histórico.",
         ["test_enunciado_a3.TestOcorrencias.test_registra_e_aparece_no_livro",
          "test_enunciado_a3.TestOcorrencias.test_filtros_e_pesquisa",
          "test_enunciado_a3.TestOcorrencias.test_resolver_e_filtro_so_abertas",
          "test_enunciado_a3.TestOcorrencias.test_excluir_pede_confirmacao_e_fica_no_historico"]),
    caso("CT-105", ["RN49", "RN02", "RN14"], NEGATIVO,
         "Ocorrências: dados inválidos, permissão e CPF no texto",
         "Sem categoria, descrição curta, CPF e placa inválidos; porteiro "
         "tentando excluir direto no banco; CPF na descrição; duas estações "
         "resolvendo a mesma.",
         "Recusa com a mensagem certa; o banco confere a permissão de novo; o "
         "CPF fica mascarado; a segunda estação é avisada.",
         ["test_enunciado_a3.TestOcorrencias.test_validacao",
          "test_enunciado_a3.TestOcorrenciasNoBanco.test_porteiro_nao_exclui_nem_com_a_tela_burlada",
          "test_enunciado_a3.TestOcorrencias.test_cpf_digitado_na_descricao_vai_mascarado",
          "test_enunciado_a3.TestOcorrencias.test_resolver_duas_vezes_em_duas_estacoes"]),
    caso("CT-106", ["RNF04"], POSITIVO, "Requisitos técnicos do enunciado",
         "Ler o código-fonte: widgets, estruturas e bibliotecas.",
         "Tem Entry, Button, Label, Combobox, Checkbutton, Treeview, Text e "
         "PhotoImage; IF/ELSE, FOR/WHILE, funções e TRY/EXCEPT; SQLite3, "
         "Datetime e CSV, só da biblioteca padrão.",
         ["test_enunciado_a3.TestRequisitosTecnicos.test_widgets_pedidos",
          "test_enunciado_a3.TestRequisitosTecnicos.test_estruturas_pedidas",
          "test_enunciado_a3.TestRequisitosTecnicos.test_bibliotecas_pedidas",
          "test_enunciado_a3.TestRequisitosTecnicos.test_so_biblioteca_padrao"]),
    caso("CT-107", ["RNF03"], POSITIVO,
         "Dia inteiro de uso não consome os recursos do Windows",
         "Repetir 25 vezes: cadastrar, dar saída, corrigir e abrir todas as "
         "páginas e diálogos.",
         "O número de objetos gráficos do processo não cresce.",
         ["test_enunciado_a3.TestSemVazamentoDeRecursos."
          "test_usar_as_telas_nao_consome_objetos_graficos"]),
    # --- Versão 3.1: o visual novo continua sendo Tkinter de verdade ------
    caso("CT-110", ["RNF01", "RNF04"], POSITIVO,
         "Botão arredondado é um tk.Button e responde a mouse e teclado",
         "Clicar, soltar fora, Enter, Espaço e invoke() num botão do Cadastro; "
         "desativar o botão e tentar de novo.",
         "É um tk.Button com o fundo em imagem; aciona uma vez por clique, não "
         "aciona soltando fora nem desativado, e o fundo acompanha o tamanho.",
         ["test_visual.TestBotaoTk.test_e_um_tk_button_com_fundo_em_imagem",
          "test_visual.TestBotaoTk.test_clique_aciona_uma_vez",
          "test_visual.TestBotaoTk.test_soltar_fora_do_botao_nao_aciona",
          "test_visual.TestBotaoTk.test_invoke_enter_e_espaco_acionam",
          "test_visual.TestBotaoTk.test_desativado_nao_aciona_por_nenhum_caminho",
          "test_visual.TestBotaoTk.test_fundo_acompanha_o_tamanho_do_botao"]),
    caso("CT-111", ["RNF01", "RNF07"], POSITIVO,
         "Uma ação principal por tela e Excluir longe das ações do dia a dia",
         "Conferir as variantes dos botões do Cadastro, do Controle de acesso e "
         "de Pessoas, e a posição do Excluir.",
         "Só Cadastrar e Registrar entrada são preenchidos de vermelho; as "
         "outras ações têm contorno ou só texto; Excluir fica à direita, "
         "separado.",
         ["test_visual.TestTelasRepaginadas.test_um_botao_principal_por_tela",
          "test_visual.TestTelasRepaginadas.test_excluir_fica_longe_das_acoes_do_dia_a_dia",
          "test_visual.TestBotaoTk.test_so_o_primario_e_preenchido_de_vermelho"]),
    caso("CT-112", ["RNF01"], POSITIVO,
         "Cadastro em blocos, com o Tab na ordem da tela",
         "Percorrer o Cadastro com a tecla Tab a partir do CPF.",
         "Bloco Pessoa (CPF, nome, telefone, empresa, tipo) e bloco Visita "
         "(data, horário, placa, motivo, saída), nessa ordem, e depois os "
         "botões.",
         ["test_visual.TestTelasRepaginadas.test_tab_segue_a_ordem_da_tela_no_cadastro",
          "test_visual.TestTelasRepaginadas.test_blocos_pessoa_e_visita"]),
    caso("CT-113", ["RF34", "RNF07"], POSITIVO,
         "Caixa de seleção desenhada, nos dois temas",
         "Marcar e desmarcar Mostrar senha e Só abertas; trocar o tema.",
         "É um tk.Checkbutton com a caixa em imagem (vermelha com o visto "
         "quando marcada); cada tema tem a sua; o tema escuro remonta as telas "
         "com os componentes novos.",
         ["test_visual.TestCheckbutton.test_e_um_tk_checkbutton_com_a_caixa_desenhada",
          "test_visual.TestCheckbutton.test_clicar_marca_e_desmarca",
          "test_visual.TestCheckbutton.test_cada_tema_tem_as_suas_imagens",
          "test_visual.TestTelasRepaginadas.test_tema_escuro_remonta_com_os_componentes_novos"]),
    # --- 3.2: desafios extras que faltavam e melhorias -----------------
    caso("CT-114", ["RF41", "RN51"], POSITIVO,
         "Chaves: entregar e devolver",
         "Cadastrar a chave Laboratório 2; entregar a Maria Souza; devolver.",
         "A chave aparece como emprestada, com quem está e desde quando; na "
         "devolução volta para Na portaria e o histórico guarda os dois "
         "momentos e quem atendeu.",
         ["test_modulos.TestChaves.test_entregar_e_devolver",
          "test_livros.TestChavesNaTela.test_entregar_e_devolver",
          "test_livros.TestChavesNaTela.test_historico_e_remover",
          "test_livros.TestChavesNaTela.test_cpf_de_quem_tem_cadastro_puxa_o_nome"]),
    caso("CT-115", ["RN51", "RN02"], NEGATIVO,
         "Chaves: a mesma chave não sai duas vezes",
         "Entregar a chave que já está emprestada (inclusive por outra "
         "estação); devolver a que está na portaria; porteiro cadastrar ou "
         "remover chave; remover a chave emprestada.",
         "Tudo recusado com mensagem; o próprio banco trava a segunda entrega "
         "(índice único), mesmo sem a checagem do programa.",
         ["test_modulos.TestChaves.test_chave_emprestada_nao_sai_de_novo",
          "test_modulos.TestChaves.test_o_banco_trava_duas_entregas_mesmo_sem_a_checagem",
          "test_modulos.TestChaves.test_devolver_o_que_nao_esta_emprestado_e_recusado",
          "test_modulos.TestChaves.test_remover_so_admin_e_so_na_portaria",
          "test_modulos.TestChaves.test_cadastro_so_do_administrador",
          "test_livros.TestChavesNaTela.test_outra_estacao_entregou_antes",
          "test_livros.TestChavesDoPorteiro.test_porteiro_entrega_mas_nao_cadastra_nem_remove"]),
    caso("CT-116", ["RF40", "RN52"], POSITIVO,
         "Encomendas: registrar a chegada e a retirada",
         "Registrar uma encomenda dos Correios para Helena Souza; depois "
         "informar quem retirou.",
         "A encomenda fica Aguardando retirada (as pendentes vêm primeiro); "
         "na retirada guarda quem levou, quando e quem atendeu.",
         ["test_modulos.TestEncomendas.test_registrar_e_retirar",
          "test_modulos.TestEncomendas.test_pendentes_primeiro_e_busca",
          "test_livros.TestEncomendasNaTela.test_registrar_retirar_e_filtrar",
          "test_livros.TestEncomendasNaTela.test_pesquisa"]),
    caso("CT-117", ["RN52", "RN02", "RN33"], NEGATIVO,
         "Encomendas: campos, retirada repetida e exclusão",
         "Destinatário ou remetente vazios ou longos; retirar duas vezes; "
         "porteiro excluir; CPF digitado na descrição.",
         "Recusa com a mensagem do campo; a segunda retirada é recusada; só o "
         "administrador exclui (com confirmação); o CPF da descrição é "
         "gravado mascarado.",
         ["test_modulos.TestEncomendas.test_campos_obrigatorios_e_limites",
          "test_modulos.TestEncomendas.test_nao_se_retira_duas_vezes",
          "test_modulos.TestEncomendas.test_excluir_so_administrador",
          "test_modulos.TestEncomendas.test_cpf_na_descricao_vai_mascarado",
          "test_livros.TestEncomendasNaTela.test_validacao_no_dialogo",
          "test_livros.TestEncomendasNaTela.test_excluir_pede_confirmacao"]),
    caso("CT-118", ["RF39", "RN53"], POSITIVO,
         "Visitante autorizado: a autorização preenche o Cadastro",
         "Criar a autorização de entrada para um CPF (hoje até depois de "
         "amanhã); digitar esse CPF no Cadastro e cadastrar.",
         "O Cadastro mostra \"Entrada autorizada por ...\" e já traz nome, "
         "empresa, motivo e quem procura; a entrada conta como uso da "
         "autorização.",
         ["test_modulos.TestAutorizacoes.test_criar_e_situacoes",
          "test_modulos.TestAutorizacoes.test_autorizacao_valida_do_dia",
          "test_modulos.TestAutorizacoes.test_entrada_conta_como_uso",
          "test_livros.TestAutorizacoesNaTela.test_criar_aparece_valida_e_selecionada",
          "test_livros.TestAutorizacoesNaTela.test_registrar_entrada_leva_ao_cadastro_com_os_dados"]),
    caso("CT-119", ["RF39", "RN53", "RN33"], POSITIVO,
         "Emissão da autorização de entrada (página para imprimir)",
         "Selecionar a autorização e escolher Emitir.",
         "Abre no navegador a página da autorização, pronta para imprimir "
         "(o que foi digitado aparece como texto, nunca como marcação); a "
         "emissão fica no histórico; para o porteiro o CPF sai mascarado.",
         ["test_modulos.TestAutorizacoes.test_emissao_fica_no_historico",
          "test_livros.TestAutorizacoesNaTela.test_emitir_abre_a_pagina_para_imprimir",
          "test_livros.TestAutorizacoesNaTela.test_o_que_foi_digitado_nao_vira_marcacao_na_pagina",
          "test_livros.TestAutorizacoesDoPorteiro.test_cpf_mascarado_na_lista_e_na_pagina_impressa"]),
    caso("CT-120", ["RN53", "RN12"], NEGATIVO,
         "Autorização: datas, cancelamento e pessoa desativada",
         "Validade que termina antes de começar, no passado ou acima de 90 "
         "dias; CPF inválido; sem motivo ou sem quem autoriza; cancelar duas "
         "vezes; autorização para um CPF desativado.",
         "Recusa com a mensagem; a autorização cancelada ou vencida não "
         "preenche o Cadastro; a pessoa desativada continua barrada mesmo "
         "autorizada.",
         ["test_modulos.TestAutorizacoes.test_validacao",
          "test_modulos.TestAutorizacoes.test_cancelar_duas_vezes_e_recusado",
          "test_modulos.TestAutorizacoes.test_porteiro_so_acha_o_cpf_inteiro",
          "test_livros.TestAutorizacoesNaTela.test_o_dialogo_abre_com_hoje_e_recusa_o_que_falta",
          "test_livros.TestAutorizacoesNaTela.test_cancelar_e_botoes",
          "test_livros.TestAutorizacoesNaTela.test_trocar_o_cpf_limpa_o_que_veio_da_autorizacao",
          "test_livros.TestAutorizacoesNaTela.test_pessoa_desativada_continua_barrada_mesmo_autorizada"]),
    caso("CT-121", ["RF38", "RN54"], POSITIVO,
         "Funcionários: matrícula, setor, cargo e o ponto de hoje",
         "Cadastrar um funcionário com matrícula F-0142, setor e cargo; "
         "registrar a entrada dele.",
         "A página Funcionários lista a matrícula, o setor, o cargo e a "
         "entrada e a saída de hoje.",
         ["test_modulos.TestFuncionarios.test_salvar_e_listar",
          "test_modulos.TestFuncionarios.test_ponto_de_hoje",
          "test_livros.TestFuncionariosNaTela.test_novo_funcionario",
          "test_livros.TestFuncionariosNaTela.test_editar_dados_e_ponto_de_hoje"]),
    caso("CT-122", ["RN54"], NEGATIVO,
         "Funcionários: matrícula repetida e quem não é funcionário",
         "Matrícula de outro funcionário; matrícula com caractere inválido; "
         "dados de funcionário para um Visitante; CPF que já tem cadastro.",
         "Recusa com mensagem; nada é gravado.",
         ["test_modulos.TestFuncionarios.test_matricula_nao_se_repete_e_tem_formato",
          "test_modulos.TestFuncionarios.test_quem_nao_e_funcionario_e_recusado",
          "test_livros.TestFuncionariosNaTela.test_validacao_e_cpf_que_ja_existe"]),
    caso("CT-123", ["RN50"], POSITIVO,
         "Visita com crachá e quem procura",
         "Cadastrar a entrada com Quem procura = Diretoria e Crachá 12; "
         "filtrar por Dentro; dar a saída.",
         "A visita guarda os dois; o filtro Dentro mostra a coluna Crachá; a "
         "saída lembra de recolher o crachá, que fica livre de novo.",
         ["test_modulos.TestCrachaEAnfitriao.test_visita_guarda_quem_procura_e_o_cracha",
          "test_modulos.TestCrachaEAnfitriao.test_cracha_volta_a_ficar_livre_na_saida",
          "test_modulos.TestCrachaEAnfitriao.test_corrigir_mantem_ou_troca_o_cracha",
          "test_livros.TestCrachaNoCadastro.test_cadastro_guarda_o_cracha_e_quem_procura",
          "test_livros.TestCrachaNoCadastro.test_filtro_dentro_mostra_o_cracha_e_a_saida_pede_de_volta"]),
    caso("CT-124", ["RN50"], NEGATIVO,
         "O mesmo crachá não fica com duas pessoas",
         "Entregar o crachá 12 a quem entra enquanto ele está com outra "
         "pessoa dentro; crachá com letras ou com 4 dígitos; desfazer a saída "
         "de quem tinha o crachá que já foi para outra pessoa.",
         "Recusa dizendo com quem o crachá está; só números, até 3 dígitos; a "
         "visita desfeita volta sem o crachá.",
         ["test_modulos.TestCrachaEAnfitriao.test_cracha_nao_fica_com_duas_pessoas",
          "test_modulos.TestCrachaEAnfitriao.test_cracha_invalido_e_limite_de_quem_procura",
          "test_modulos.TestCrachaEAnfitriao."
          "test_desfazer_a_saida_nao_rouba_o_cracha_de_quem_pegou_depois",
          "test_livros.TestCrachaNoCadastro.test_cracha_em_uso_e_recusado",
          "test_livros.TestCrachaNoCadastro.test_cracha_so_aceita_numeros_e_tres_digitos"]),
    caso("CT-125", ["RF42", "RN33"], POSITIVO,
         "Recado de turno (passagem de turno)",
         "Deixar um recado em Ocorrências; abrir o Controle de acesso com "
         "outro usuário e marcar como lido.",
         "O recado aparece numa faixa do Controle de acesso até alguém marcar "
         "como lido (o mais antigo primeiro); recado vazio, curto ou longo é "
         "recusado; CPF no texto vai mascarado.",
         ["test_modulos.TestRecados.test_deixar_listar_e_marcar_como_lido",
          "test_modulos.TestRecados.test_recado_vazio_curto_ou_longo_e_recusado",
          "test_modulos.TestRecados.test_cpf_no_recado_vai_mascarado",
          "test_livros.TestRecadoDeTurno.test_recado_aparece_no_controle_ate_ser_lido",
          "test_livros.TestRecadoDeTurno.test_o_mais_antigo_primeiro"]),
    caso("CT-126", ["RF44", "RF43", "RN02"], POSITIVO,
         "Painel por período, horário de pico e relatório para imprimir",
         "No Painel, alternar Por dia / Por hora e 7 dias / 30 dias; emitir o "
         "Relatório de um período.",
         "O gráfico muda de período e destaca a hora de mais entradas; o "
         "relatório abre no navegador, pronto para imprimir, e a emissão fica "
         "no histórico; data inválida é recusada; o porteiro não tem o botão.",
         ["test_livros.TestPainelERelatorio.test_por_dia_em_7_e_30_dias",
          "test_livros.TestPainelERelatorio.test_por_hora_destaca_o_pico",
          "test_livros.TestPainelERelatorio.test_grafico_desenha_nos_dois_modos_sem_erro",
          "test_livros.TestPainelERelatorio.test_relatorio_para_imprimir",
          "test_livros.TestPainelERelatorio.test_relatorio_recusa_data_invalida",
          "test_livros.TestPainelDoPorteiro.test_porteiro_nao_tem_relatorio"]),
    caso("CT-127", ["RF45", "RN57"], POSITIVO,
         "Dados de demonstração: só o administrador",
         "Em Configurações > Dados e privacidade, preencher com dados de "
         "demonstração; repetir; tentar como porteiro (direto no banco).",
         "O sistema ganha pessoas (CPFs fictícios válidos), visitas, chaves, "
         "encomendas, autorizações e ocorrências coerentes; repetir não "
         "duplica; o porteiro não vê a seção e o banco recusa.",
         ["test_modulos.TestDemonstracao.test_so_administrador",
          "test_modulos.TestDemonstracao.test_enche_o_banco_com_dados_coerentes",
          "test_modulos.TestDemonstracao.test_rodar_de_novo_nao_duplica",
          "test_modulos.TestDemonstracao.test_cpf_ficticio_e_valido",
          "test_modulos.TestDemonstracao.test_carro_de_quem_esta_dentro_fica_no_estacionamento",
          "test_livros.TestDadosEPrivacidade.test_dados_de_demonstracao",
          "test_livros.TestDadosEPrivacidade."
          "test_todas_as_paginas_abrem_com_os_dados_de_demonstracao"]),
    caso("CT-128", ["RF47", "RN55", "RN02"], POSITIVO,
         "LGPD: anonimizar uma pessoa e aplicar o prazo de guarda",
         "Anonimizar pelo CPF, com justificativa; aplicar o prazo de 12 "
         "meses.",
         "Nome, CPF, telefone, placa e empresa da pessoa e das visitas dela "
         "viram textos neutros; as visitas continuam contando no Painel; o "
         "mesmo CPF pode voltar como pessoa nova; quem está dentro ou "
         "desativado não é anonimizado; só o administrador.",
         ["test_modulos.TestPrivacidade.test_anonimizar_troca_os_dados_e_mantem_a_visita",
          "test_modulos.TestPrivacidade.test_so_administrador_e_com_justificativa",
          "test_modulos.TestPrivacidade.test_quem_esta_dentro_ou_desativado_nao_e_anonimizado",
          "test_modulos.TestPrivacidade.test_o_mesmo_cpf_pode_voltar_como_pessoa_nova",
          "test_modulos.TestPrivacidade.test_prazo_de_guarda",
          "test_modulos.TestPrivacidade.test_prazo_invalido",
          "test_livros.TestDadosEPrivacidade.test_anonimizar_pela_tela",
          "test_livros.TestDadosEPrivacidade.test_prazo_de_guarda_pela_tela"]),
    caso("CT-129", ["RN55"], NEGATIVO,
         "O que foi anonimizado não volta a ter dados pessoais",
         "Depois de anonimizar: desfazer a saída da visita, corrigir a "
         "visita, dar matrícula, alterar o cadastro, anonimizar de novo.",
         "Tudo recusado: a visita continua encerrada e com os textos neutros "
         "(caso achado pelas sequências aleatórias da 3.2).",
         ["test_modulos.TestAnonimizadoNaoVolta.test_desfazer_a_saida_nao_reabre_a_visita",
          "test_modulos.TestAnonimizadoNaoVolta.test_corrigir_a_visita_e_recusado",
          "test_modulos.TestAnonimizadoNaoVolta.test_nao_vira_funcionario_de_novo",
          "test_modulos.TestAnonimizadoNaoVolta.test_o_cadastro_nao_e_mais_alteravel",
          "test_modulos.TestPrivacidade.test_anonimizar_duas_vezes_e_recusado"]),
    caso("CT-130", ["RN56", "RNF05"], NEGATIVO,
         "Histórico encadeado: alteração por fora é denunciada",
         "Com outro programa, alterar o detalhe ou o autor de um evento do "
         "histórico, ou apagar um evento do meio; depois Conferir histórico.",
         "A conferência aponta o primeiro evento que não bate; sem alteração, "
         "responde que o histórico está íntegro; eventos novos continuam a "
         "corrente; o banco da 3.1 é encadeado na migração, sem perder nada.",
         ["test_modulos.TestHistoricoProtegido.test_historico_integro",
          "test_modulos.TestHistoricoProtegido.test_evento_alterado_por_fora_e_achado",
          "test_modulos.TestHistoricoProtegido.test_evento_apagado_do_meio_e_achado",
          "test_modulos.TestHistoricoProtegido.test_trocar_o_autor_tambem_quebra",
          "test_modulos.TestHistoricoProtegido.test_eventos_novos_continuam_a_corrente",
          "test_modulos.TestHistoricoProtegido.test_o_elo_depende_do_anterior",
          "test_modulos.TestMigracaoV14.test_banco_da_3_1_ganha_os_modulos_sem_perder_nada",
          "test_modulos.TestMigracaoV14.test_migrar_duas_vezes_nao_estraga",
          "test_livros.TestDadosEPrivacidade.test_conferir_o_historico"]),
    caso("CT-131", ["RF46", "RNF01"], POSITIVO,
         "Tamanho da letra, código da pessoa e menu com onze páginas",
         "Escolher Letra: Maior no menu do usuário; sair e entrar com outro "
         "usuário; abrir a ficha de uma pessoa; usar a janela pequena.",
         "A letra aumenta em todas as páginas e é de cada usuário (a tela de "
         "login volta ao normal); a ficha mostra o código (P012); as onze "
         "páginas do menu cabem na janela pequena.",
         ["test_modulos.TestLetra.test_cada_usuario_tem_a_sua",
          "test_livros.TestTamanhoDaLetra.test_letra_maior_aumenta_e_volta",
          "test_livros.TestTamanhoDaLetra.test_e_de_cada_usuario_e_o_login_fica_normal",
          "test_livros.TestTamanhoDaLetra.test_todas_as_paginas_abrem_com_a_letra_maior",
          "test_livros.TestCodigoDaPessoa.test_ficha_mostra_o_codigo_do_cadastro",
          "test_livros.TestMenuCabeNaTelaPequena.test_o_menu_com_onze_paginas_cabe_em_536_px"]),
    caso_da_linguagem(
        "CT-108", "Semântico", ["RN46", "RN48"], NEGATIVO,
        "Empresa e motivo: as mesmas regras do formulário",
        "entrada de CPF novo sem empresa; cadastrar com empresa vazia.",
        "Recusa, como o formulário; nada é gravado.",
        ["test_enunciado_a3.TestLinguagemComEmpresaEMotivo."
         "test_entrada_nova_sem_empresa_e_recusada_como_no_formulario",
         "test_enunciado_a3.TestLinguagemComEmpresaEMotivo.test_empresa_vazia_e_recusada"]),
    caso_da_linguagem(
        "CT-109", "Execução", ["RN46", "RN48"], POSITIVO,
        "Empresa e motivo pela linguagem",
        "entrada ... empresa \"Alfa Ltda\" motivo \"Reunião\"; entrada só com o "
        "CPF de quem já veio; cadastrar e editar a empresa.",
        "Grava igual ao formulário; quem já veio reaproveita a empresa e o "
        "último motivo.",
        ["test_enunciado_a3.TestLinguagemComEmpresaEMotivo.test_entrada_nova_com_tudo",
         "test_enunciado_a3.TestLinguagemComEmpresaEMotivo."
         "test_quem_ja_veio_reaproveita_empresa_e_motivo",
         "test_enunciado_a3.TestLinguagemComEmpresaEMotivo.test_cadastrar_e_editar_empresa"]),
]


# ------------------------------------------------------------------
# Execução
# ------------------------------------------------------------------
class Resultado(unittest.TestResult):
    """Guarda o resultado de cada teste pelo id."""

    def __init__(self):
        super().__init__()
        self.por_id = {}

    def addSuccess(self, test):
        super().addSuccess(test)
        self.por_id[test.id()] = "ok"

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.por_id[test.id()] = "falhou"

    def addError(self, test, err):
        super().addError(test, err)
        self.por_id[test.id()] = "erro"

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.por_id[test.id()] = "pulado"


def rodar_casos(casos=CASOS):
    """Roda os testes dos casos; devolve os casos com o resultado."""
    nomes = sorted({t for c in casos for t in c["testes"]})
    resultado = Resultado()
    # uma suíte só, em ordem de id: os testes da mesma classe ficam juntos
    # e o setUpClass/tearDownClass (a janela Tk) roda uma vez por classe
    suite = unittest.TestSuite()
    for nome in nomes:
        try:
            suite.addTests(unittest.defaultTestLoader.loadTestsFromName(nome))
        except (AttributeError, ImportError):
            resultado.por_id[nome] = "não encontrado"
    inicio = time.perf_counter()
    suite.run(resultado)
    duracao = time.perf_counter() - inicio
    saida = []
    for c in casos:
        testes = [{"id": t, "resultado": resultado.por_id.get(t, "não rodou")}
                  for t in c["testes"]]
        passou = all(t["resultado"] == "ok" for t in testes)
        saida.append(dict(c, testes=testes,
                          resultado="PASSOU" if passou else "FALHOU"))
    return saida, len(nomes), duracao


def rodar_suite_completa():
    """`python -m unittest` num processo separado (a mesma linha de comando
    do README); devolve total, tempo, pulados e se deu OK."""
    inicio = time.perf_counter()
    proc = subprocess.run([sys.executable, "-m", "unittest"], cwd=RAIZ,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    duracao = time.perf_counter() - inicio
    texto = proc.stderr + proc.stdout
    ran = re.search(r"Ran (\d+) tests? in ([\d.]+)s", texto)
    fim = re.search(r"^(OK|FAILED)(.*)$", texto, re.MULTILINE)
    pulados = re.search(r"skipped=(\d+)", fim.group(2)) if fim else None
    return {
        "comando": "python -m unittest",
        "total": int(ran.group(1)) if ran else None,
        "tempo_segundos": float(ran.group(2)) if ran else round(duracao, 1),
        "pulados": int(pulados.group(1)) if pulados else 0,
        "ok": proc.returncode == 0,
        "linha_final": (fim.group(0).strip() if fim else "sem resultado"),
    }


def matriz(casos):
    """{requisito: [CT, ...]} em ordem (RF, RNF, RN; depois o número)."""
    mapa = {}
    for c in casos:
        for r in c["requisitos"]:
            mapa.setdefault(r, []).append(c["id"])

    def chave(r):
        prefixo, numero = re.match(r"([A-Z]+)(\d+)", r).groups()
        return ({"RF": 0, "RNF": 1, "RN": 2}.get(prefixo, 3), int(numero))
    return {r: mapa[r] for r in sorted(mapa, key=chave)}


def montar_relatorio(casos, testes_rodados, duracao, suite):
    agora = datetime.now()
    aprovados = sum(c["resultado"] == "PASSOU" for c in casos)
    return {
        "sistema": "Sistema de Portaria",
        "versao": VERSAO,
        "gerado_em": agora.strftime("%d/%m/%Y %H:%M:%S"),
        "python": platform.python_version(),
        "plataforma": platform.platform(),
        "total_casos": len(casos),
        "aprovados": aprovados,
        "reprovados": len(casos) - aprovados,
        "positivos": sum(c["tipo"] == POSITIVO for c in casos),
        "negativos": sum(c["tipo"] == NEGATIVO for c in casos),
        "secoes": {s: [c["id"] for c in casos if c["secao"] == s]
                   for s in (SISTEMA, LINGUAGEM)},
        "testes_automaticos_dos_casos": testes_rodados,
        "tempo_dos_casos_segundos": round(duracao, 2),
        "suite_completa": suite,
        "casos": casos,
        "matriz": matriz(casos),
    }


# ------------------------------------------------------------------
# Arquivos
# ------------------------------------------------------------------
def gravar_csv(rel, caminho):
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["ID", "Seção", "Requisito/Regra", "Tipo", "Caso",
                    "Entrada", "Esperado", "Resultado", "Testes automáticos"])
        for c in rel["casos"]:
            w.writerow([c["id"], c["secao"], " ".join(c["requisitos"]),
                        c["tipo"],
                        c["titulo"], c["entrada"], c["esperado"],
                        c["resultado"],
                        " | ".join(f"{t['id']} ({t['resultado']})"
                                   for t in c["testes"])])


def gravar_html(rel, caminho):
    e = html.escape
    suite = rel["suite_completa"]
    linhas, secao = [], None
    for c in rel["casos"]:
        if c["secao"] != secao:                # título de cada seção
            secao = c["secao"]
            linhas.append(f"<tr><th colspan='7' class='secao'>{e(secao)}"
                          "</th></tr>")
        ok = c["resultado"] == "PASSOU"
        testes = "<br>".join(
            f"<code>{e(t['id'].removeprefix('tests.'))}</code> "
            f"({e(t['resultado'])})" for t in c["testes"])
        linhas.append(
            f"<tr><td><b>{e(c['id'])}</b></td>"
            f"<td>{e(' '.join(c['requisitos']))}</td>"
            f"<td>{e(c['tipo'])}</td>"
            f"<td><b>{e(c['titulo'])}</b><br>{e(c['entrada'])}</td>"
            f"<td>{e(c['esperado'])}</td>"
            f"<td class='{'ok' if ok else 'falha'}'>"
            f"{'PASSOU ✓' if ok else 'FALHOU ✗'}</td>"
            f"<td class='testes'>{testes}</td></tr>")
    ids = [c["id"] for c in rel["casos"]]
    cab = "".join(f"<th class='v'>{e(i)}</th>" for i in ids)
    corpo = "".join(
        f"<tr><th>{e(r)}</th>" + "".join(
            f"<td class='m'>{'●' if i in cts else ''}</td>" for i in ids)
        + "</tr>" for r, cts in rel["matriz"].items())
    if suite:
        texto_suite = (f"<p><b>Suíte completa</b> (<code>{e(suite['comando'])}"
                       f"</code>): {suite['total']} testes em "
                       f"{suite['tempo_segundos']:.1f} s, "
                       f"{suite['pulados']} pulado(s) — "
                       f"<b>{e(suite['linha_final'])}</b></p>")
    else:
        texto_suite = "<p>Suíte completa não executada (--sem-suite).</p>"
    pagina = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Relatório de testes — Sistema de Portaria {e(rel['versao'])}</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#222}}
h1{{color:#B0121B;font-size:22px}} h2{{color:#B0121B;font-size:17px}}
table{{border-collapse:collapse;width:100%;font-size:12px;margin-bottom:24px}}
th,td{{border:1px solid #ccc;padding:5px;vertical-align:top;text-align:left}}
th{{background:#F3E5E6}} td.ok{{color:#176B2C;font-weight:bold}}
td.falha{{color:#B0121B;font-weight:bold}} td.testes{{font-size:11px}}
th.v{{writing-mode:vertical-rl;font-size:10px}} td.m{{text-align:center}}
th.secao{{background:#B0121B;color:#fff;font-size:13px}}
code{{font-size:11px}}
</style></head><body>
<h1>Relatório de testes — Sistema de Portaria {e(rel['versao'])}</h1>
<p>Gerado em {e(rel['gerado_em'])} · Python {e(rel['python'])} ·
{e(rel['plataforma'])}</p>
<p><b>{rel['aprovados']} de {rel['total_casos']} casos aprovados</b>
({rel['positivos']} positivos, {rel['negativos']} negativos), comprovados por
{rel['testes_automaticos_dos_casos']} testes automáticos em
{rel['tempo_dos_casos_segundos']:.1f} s.</p>
{texto_suite}
<h2>Casos de teste</h2>
<table><tr><th>ID</th><th>Requisito/Regra</th><th>Tipo</th>
<th>Entrada</th><th>Esperado</th><th>Resultado</th>
<th>Teste automático que comprova</th></tr>
{''.join(linhas)}</table>
<h2>Matriz de rastreabilidade (requisito × caso de teste)</h2>
<table><tr><th></th>{cab}</tr>{corpo}</table>
</body></html>
"""
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(pagina)


def gravar(rel, pasta):
    os.makedirs(pasta, exist_ok=True)
    caminhos = {ext: os.path.join(pasta, f"{NOME}.{ext}")
                for ext in ("html", "csv", "json")}
    gravar_html(rel, caminhos["html"])
    gravar_csv(rel, caminhos["csv"])
    with open(caminhos["json"], "w", encoding="utf-8") as f:
        json.dump(rel, f, ensure_ascii=False, indent=2)
    return caminhos


def _dentro_de(pasta, raiz):
    try:
        return os.path.commonpath([os.path.normcase(pasta),
                                   os.path.normcase(raiz)]) == os.path.normcase(raiz)
    except ValueError:          # discos diferentes no Windows
        return False


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    com_suite = "--sem-suite" not in argv
    argv = [a for a in argv if a != "--sem-suite"]
    pasta = (os.path.abspath(argv[0]) if argv
             else os.path.join(tempfile.gettempdir(), "portaria_relatorio"))
    if _dentro_de(pasta, RAIZ):
        print("Escolha uma pasta fora do repositório "
              "(os relatórios não vão para o git).", file=sys.stderr)
        return 2
    os.chdir(RAIZ)
    print(f"Rodando os testes dos {len(CASOS)} casos...")
    # a saída dos testes (avisos do Tk, log) não polui o relatório
    with open(os.devnull, "w") as nulo:
        antigo = sys.stderr
        sys.stderr = nulo
        try:
            casos, rodados, duracao = rodar_casos()
        finally:
            sys.stderr = antigo
    suite = None
    if com_suite:
        print("Rodando a suíte completa (python -m unittest)...")
        suite = rodar_suite_completa()
    rel = montar_relatorio(casos, rodados, duracao, suite)
    caminhos = gravar(rel, pasta)
    for c in rel["casos"]:
        print(f"  {c['id']}  {c['resultado']:6}  {c['tipo']:8}  {c['titulo']}")
    print(f"\n{rel['aprovados']}/{rel['total_casos']} casos aprovados "
          f"({rel['positivos']} positivos, {rel['negativos']} negativos).")
    if suite:
        print(f"Suíte completa: {suite['total']} testes em "
              f"{suite['tempo_segundos']:.1f} s — {suite['linha_final']}")
    for caminho in caminhos.values():
        print("Gravado:", caminho)
    ok = rel["reprovados"] == 0 and (suite is None or suite["ok"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
