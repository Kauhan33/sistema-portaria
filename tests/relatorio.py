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


def caso(id_, requisitos, tipo, titulo, entrada, esperado, testes):
    return {"id": id_, "requisitos": requisitos, "tipo": tipo,
            "titulo": titulo, "entrada": entrada, "esperado": esperado,
            "testes": ["tests." + t for t in testes]}


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
         "Logado como porteiro: abrir Pessoas › Desativadas e Veículos "
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
         "Logado como porteiro: em Pessoas › Desativadas, escolher a pessoa "
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
        w.writerow(["ID", "Requisito/Regra", "Tipo", "Caso", "Entrada",
                    "Esperado", "Resultado", "Testes automáticos"])
        for c in rel["casos"]:
            w.writerow([c["id"], " ".join(c["requisitos"]), c["tipo"],
                        c["titulo"], c["entrada"], c["esperado"],
                        c["resultado"],
                        " | ".join(f"{t['id']} ({t['resultado']})"
                                   for t in c["testes"])])


def gravar_html(rel, caminho):
    e = html.escape
    suite = rel["suite_completa"]
    linhas = []
    for c in rel["casos"]:
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
