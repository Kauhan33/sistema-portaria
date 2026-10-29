"""
Linguagem de comandos (2.4): uma classe de testes por fase do analisador.

    TestLexico      texto -> tokens (CPF, placa, data, hora, aspas, acentos)
    TestGramatica   a EBNF é LL(1) e é a mesma do documento
    TestSintatico   ordem, falta, sobra, "você quis dizer…?"
    TestSemantico   as checagens com a tabela de símbolos (banco de teste)
    TestConsultas   as respostas de situacao, dentro, buscar, pendentes e
                    ajuda (funções puras do executor)

A execução (o resultado no banco é o MESMO do formulário) é testada na
tela de verdade, em test_interface_comando.py.
"""

import os
import re
import tempfile
import unittest
from datetime import date, datetime

from portaria import dados
from portaria.linguagem import gramatica, lexico
from portaria.linguagem.erros import (LEXICO, SEMANTICO, SINTATICO,
                                      ErroDeAnalise, formatar_erro)
from portaria.linguagem.executor import (ajuda, pendencias, quem_esta_dentro,
                                         resultado_da_busca,
                                         situacao_da_pessoa)
from portaria.linguagem.interpretador import (FALHOU, NAO_RODOU, PASSOU,
                                              analisar, analisar_forma)
from portaria.linguagem.lexico import (CPF, DATA, ERRO, FIM, HORA, NUMERO,
                                       PALAVRA, PALAVRA_CHAVE, PLACA, TEXTO,
                                       TIPO, COMANDO, analisar_lexico,
                                       mascarar_linha, reconhecer_placa,
                                       tokenizar)
from portaria.linguagem.semantico import (AUTORIZACAO, AVISO, ERRO as
                                          C_ERRO, OK, PERGUNTA)
from portaria.linguagem.sintatico import (AnalisadorSintatico, ComandoAjuda,
                                          ComandoBuscar, ComandoCadastrar,
                                          ComandoDentro, ComandoDesativar,
                                          ComandoEditar, ComandoEntrada,
                                          ComandoExcluir, ComandoImplicito,
                                          ComandoPendentes, ComandoReativar,
                                          ComandoSaida, ComandoSituacao,
                                          analisar_sintatico, arvore_visual)
from portaria.validacao import (FORMATO, MAXIMO_COMANDO, formatar_cpf,
                                mascarar_cpf, placa_valida)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGORA = datetime(2026, 10, 21, 10, 0)            # quarta-feira
ANA, BETO, CARLA, DUDA = ("52998224725", "11144477735", "39053344705",
                          "86288366757")
NOVO = "12345678909"                             # CPF válido, sem cadastro


def tipos(texto):
    return [t.tipo for t in analisar_lexico(texto)]


def erro_de(funcao, *args):
    try:
        funcao(*args)
    except ErroDeAnalise as e:
        return e
    raise AssertionError("esperava um ErroDeAnalise")


def arvore(texto):
    return analisar_sintatico(analisar_lexico(texto))


# ----------------------------------------------------------------------
# Léxico
# ----------------------------------------------------------------------
class TestLexico(unittest.TestCase):
    def test_cpf_com_e_sem_pontos(self):
        """CT-54 | RN06 | positivo | o léxico reconhece o CPF com pontos
        e o número de 11 dígitos (que ainda pode ser CPF ou celular)."""
        com, sem = analisar_lexico("529.982.247-25 52998224725")[:2]
        self.assertEqual((com.tipo, com.valor), (CPF, ANA))
        self.assertEqual((sem.tipo, sem.valor), (NUMERO, ANA))
        self.assertEqual((com.coluna, sem.coluna), (1, 16))

    def test_placa_antiga_e_mercosul(self):
        """CT-54 | RN06 | positivo | placa antiga (com ou sem hífen,
        minúscula) e Mercosul."""
        tokens = analisar_lexico("ABC1234 abc-1234 ABC1D23")
        self.assertEqual([t.tipo for t in tokens[:3]], [PLACA] * 3)
        self.assertEqual([t.valor for t in tokens[:3]],
                         ["ABC1234", "ABC1234", "ABC1D23"])

    def test_automato_da_placa(self):
        aceitou, caminho = reconhecer_placa("ABC1D23")
        self.assertTrue(aceitou)
        self.assertEqual(caminho, ["q0", "q1", "q2", "q3", "q5", "q6", "q7",
                                   "q8"])
        aceitou, caminho = reconhecer_placa("ABC-1234")
        self.assertEqual(caminho[4], "q4")              # o estado do hífen
        aceitou, caminho = reconhecer_placa("AB12345")
        self.assertFalse(aceitou)
        self.assertEqual(caminho, ["q0", "q1", "q2"])   # para no 3º caractere

    def test_automato_aceita_o_mesmo_que_a_validacao(self):
        """O autômato e validacao.placa_valida (a regex do formulário)
        aceitam exatamente as mesmas placas (sem hífen)."""
        amostras = ["ABC1234", "ABC1D23", "AB12345", "ABCD123", "ABC12D3",
                    "ABC123", "ABC12345", "1BC1234", "ABC1DD3", "XYZ9A87",
                    "QWE1E34", "ABC0000", "ZZZ9Z99", ""]
        for p in amostras:
            with self.subTest(placa=p):
                self.assertEqual(reconhecer_placa(p)[0], placa_valida(p))

    def test_placa_invalida(self):
        """CT-55 | RN06 | negativo | AB12345 não é placa: erro léxico na
        coluna 13."""
        e = erro_de(analisar_lexico, "saida placa AB12345")
        self.assertEqual((e.fase, e.coluna, e.tamanho), (LEXICO, 13, 7))
        self.assertIn('"AB12345" não é uma placa', e.mensagem)
        self.assertIn("ABC1D23", e.dica)

    def test_data_invalida(self):
        """CT-55 | RN06 | negativo | data que não existe e data fora do
        formato."""
        e = erro_de(analisar_lexico, "buscar maria de 32/13/2026")
        self.assertEqual((e.fase, e.coluna), (LEXICO, 17))
        self.assertIn("o dia 32 e o mês 13 não existem", e.mensagem)
        e = erro_de(analisar_lexico, "buscar maria de 31/02/2026")
        self.assertIn("não existe no calendário", e.mensagem)
        e = erro_de(analisar_lexico, "buscar maria de 1/10/2026")
        self.assertIn("não é uma data", e.mensagem)
        self.assertEqual(analisar_lexico("de 01/10/2026")[1].valor,
                         date(2026, 10, 1))

    def test_hora_invalida(self):
        self.assertIn("não existe", erro_de(analisar_lexico,
                                            "saida 1 as 25:00").mensagem)
        self.assertIn("hh:mm", erro_de(analisar_lexico,
                                       "saida 1 as 9:05").dica)
        self.assertEqual(analisar_lexico("as 14:05")[1].valor, (14, 5))

    def test_aspas_abertas(self):
        """CT-55 | RN12 | negativo | texto sem aspas de fechamento."""
        texto = 'desativar placa ABC1D23 motivo "furto'
        e = erro_de(analisar_lexico, texto)
        self.assertEqual((e.fase, e.coluna), (LEXICO, texto.index('"') + 1))
        self.assertIn("sem aspas de fechamento", e.mensagem)

    def test_simbolo_estranho(self):
        """CT-55 | RN06 | negativo | o símbolo @ não pertence à linguagem."""
        e = erro_de(analisar_lexico,
                    "entrada 529.982.247-25 visitante @casa")
        self.assertEqual((e.fase, e.coluna), (LEXICO, 34))
        self.assertIn('o símbolo "@"', e.mensagem)

    def test_acentos_maiusculas_e_plurais(self):
        """CT-54 | RF14 | positivo | SAÍDA, Situação, até e os plurais."""
        tokens = analisar_lexico("SAÍDA Situação até VISITANTES prestadores "
                                 "Funcionário mês")
        self.assertEqual([(t.tipo, t.valor) for t in tokens[:-1]], [
            (COMANDO, "saida"), (COMANDO, "situacao"),
            (PALAVRA_CHAVE, "ate"), (TIPO, "Visitante"),
            (TIPO, "Prestador de serviço"), (TIPO, "Funcionário"),
            ("PERIODO", "mes")])

    def test_texto_palavra_e_fim(self):
        tokens = analisar_lexico('nome "Bruno   Almeida" maria')
        self.assertEqual([t.tipo for t in tokens],
                         [PALAVRA_CHAVE, TEXTO, PALAVRA, FIM])
        self.assertEqual(tokens[1].valor, "Bruno Almeida")
        self.assertEqual(tokens[-1].coluna, len('nome "Bruno   Almeida" '
                                                'maria') + 1)

    def test_data_hora_numero(self):
        self.assertEqual(tipos("em 18/10/2026 08:00 31987651234"),
                         [PALAVRA_CHAVE, DATA, HORA, NUMERO, FIM])

    def test_tokenizar_continua_depois_do_erro(self):
        """O realce do campo usa a análise tolerante: todos os erros, com
        um token ERRO no lugar de cada lexema ruim."""
        tokens, erros = tokenizar("saida @ placa AB12345")
        self.assertEqual([t.tipo for t in tokens],
                         [COMANDO, ERRO, PALAVRA_CHAVE, ERRO, FIM])
        self.assertEqual([e.coluna for e in erros], [7, 15])

    def test_maximo_da_linha(self):
        e = erro_de(analisar_lexico, "ajuda " + "x" * MAXIMO_COMANDO)
        self.assertIn(f"passa de {MAXIMO_COMANDO} caracteres", e.mensagem)

    def test_cpf_mascarado_so_vale_pelo_tab(self):
        mascarado = mascarar_cpf(ANA)
        self.assertEqual(analisar_lexico(mascarado, {mascarado: ANA})[0].valor,
                         ANA)
        e = erro_de(analisar_lexico, "saida " + mascarado)
        self.assertIn("só vale quando é escolhido pelo Tab", e.mensagem)

    def test_mascarar_linha_mantem_as_colunas(self):
        """Porteiro (RN14): o CPF some da linha mostrada, o celular não, e o
        ^ do erro continua na coluna certa (o tamanho não muda)."""
        linha = "cadastrar 52998224725 aluno cel 31987651234 529.982.247-25"
        mascarada = mascarar_linha(linha)
        self.assertEqual(len(mascarada), len(linha))
        self.assertNotIn(ANA, mascarada)
        self.assertNotIn("529.982.247-25", mascarada)
        self.assertIn("***982247**", mascarada)
        self.assertIn("31987651234", mascarada)
        self.assertIn("***.982.247-**", mascarada)


# ----------------------------------------------------------------------
# Gramática
# ----------------------------------------------------------------------
class TestGramatica(unittest.TestCase):
    def test_a_gramatica_e_ll1(self):
        """CT-56 | RF14 | positivo | os conjuntos FIRST das escolhas são
        disjuntos (um token à frente basta): nenhum conflito LL(1)."""
        self.assertEqual(gramatica.conflitos_ll1(), [])

    def test_conflito_e_detectado(self):
        ruim = gramatica.EBNF.replace('dentro     = "dentro" [ TIPO ] ;',
                                      'dentro     = "dentro" [ TIPO ] '
                                      '[ TIPO ] ;')
        self.assertTrue(gramatica.conflitos_ll1(ruim))
        ruim = gramatica.EBNF.replace('termo      = TEXTO | PALAVRA | cpf '
                                      '| PLACA ;', 'termo      = TEXTO | '
                                      'PALAVRA | cpf | NUMERO ;')
        self.assertIn("NUMERO", " ".join(gramatica.conflitos_ll1(ruim)))

    def test_first_de_cada_comando(self):
        first = {alt: f for regra, alt, f in gramatica.tabela_first()
                 if regra == "comando"}
        self.assertEqual(first["implicito"], ["CPF", "NUMERO", "PLACA"])
        self.assertEqual(first["entrada"], ['"entrada"'])
        self.assertEqual(len(first), 13)

    def test_o_documento_tem_a_mesma_gramatica(self):
        """A EBNF de docs/GRAMATICA_DA_LINGUAGEM.md é a do código."""
        with open(os.path.join(RAIZ, "docs", "GRAMATICA_DA_LINGUAGEM.md"),
                  encoding="utf-8") as f:
            documento = f.read().replace("\r\n", "\n")
        self.assertIn(gramatica.EBNF, documento)

    def test_uma_funcao_por_regra(self):
        """Descida recursiva: cada regra da EBNF tem o seu método."""
        for regra in gramatica.ler_ebnf():
            nome = "linha" if regra == "linha" else "_" + regra
            with self.subTest(regra=regra):
                self.assertTrue(hasattr(AnalisadorSintatico, nome))

    def test_os_exemplos_sao_validos(self):
        """Todo exemplo da tabela de comandos passa no léxico e no
        sintático (e o `ajuda` mostra estes mesmos)."""
        for comando, exemplos in gramatica.EXEMPLOS.items():
            for exemplo in exemplos.split(" · "):
                with self.subTest(exemplo=exemplo):
                    arvore(exemplo)


# ----------------------------------------------------------------------
# Sintático
# ----------------------------------------------------------------------
class TestSintatico(unittest.TestCase):
    def test_cada_comando_monta_a_sua_arvore(self):
        """CT-56 | RF14 | positivo | os 13 comandos viram a árvore certa."""
        casos = {
            "entrada 529.982.247-25 aluno placa ABC1D23": ComandoEntrada,
            "saida 52998224725 sem carro": ComandoSaida,
            "52998224725": ComandoImplicito, "ABC1D23": ComandoImplicito,
            'cadastrar 11144477735 visitante nome "Bruno Almeida" '
            "cel 31987651234": ComandoCadastrar,
            "editar 11144477735 tipo professor": ComandoEditar,
            "excluir 11144477735": ComandoExcluir,
            'desativar placa ABC1D23 motivo "furto"': ComandoDesativar,
            "reativar 11144477735": ComandoReativar,
            "situacao placa ABC1D23": ComandoSituacao,
            "dentro visitantes": ComandoDentro,
            "buscar maria visitante semana": ComandoBuscar,
            "pendentes": ComandoPendentes, "ajuda entrada": ComandoAjuda}
        for texto, classe in casos.items():
            with self.subTest(texto=texto):
                self.assertIsInstance(arvore(texto), classe)

    def test_campos_da_entrada(self):
        a = arvore('entrada 52998224725 Visitante placa abc1d23 '
                   'nome "Ana Silva" em 18/10/2026 08:00')
        self.assertEqual(a.cpf.valor, ANA)
        self.assertEqual(a.tipo.valor, "Visitante")
        self.assertEqual([o.nome for o in a.opcoes], ["placa", "nome", "em"])
        self.assertEqual(a.opcoes[0].valor.valor, "ABC1D23")
        self.assertEqual(len(a.opcoes[2].valores), 2)

    def test_ordem_errada(self):
        """CT-57 | RF14 | negativo | o tipo antes do comando: erro
        sintático na coluna 1, com a dica do comando primeiro."""
        e = erro_de(arvore, "visitante entrada 52998224725")
        self.assertEqual((e.fase, e.coluna), (SINTATICO, 1))
        self.assertIn('esperado um comando', e.mensagem)
        self.assertIn('o tipo "visitante"', e.mensagem)
        self.assertIn("o comando vem primeiro", e.dica)

    def test_comando_desconhecido_sugere(self):
        """CT-57 | RF14 | negativo | "entrda" -> você quis dizer entrada?"""
        self.assertEqual(erro_de(arvore, "entrda 52998224725").sugestao,
                         "entrada")
        self.assertEqual(erro_de(arvore, "situcao 1").sugestao, "situacao")
        self.assertEqual(erro_de(arvore, "xyz").sugestao, "")

    def test_falta_argumento(self):
        """CT-57 | RF14 | negativo | a linha acaba antes da hora."""
        e = erro_de(arvore, "saida placa")
        self.assertTrue(e.fim_da_linha)
        self.assertEqual(e.coluna, len("saida placa") + 1)
        self.assertIn('esperado a PLACA depois de "placa"', e.mensagem)
        e = erro_de(arvore, "buscar maria de 01/10/2026 ate")
        self.assertIn("esperado uma DATA", e.mensagem)
        e = erro_de(arvore, "entrada placa ABC1D23")
        self.assertIn('depois de "entrada" vem o CPF', e.mensagem)
        self.assertEqual(e.coluna, 9)

    def test_falta_motivo(self):
        e = erro_de(arvore, 'desativar 52998224725 "briga"')
        self.assertIn('esperado "motivo" antes do texto', e.mensagem)
        self.assertIn('motivo "', e.dica)

    def test_sobra_depois_do_comando(self):
        e = erro_de(arvore, "52998224725 visitante")
        self.assertIn("sobrou", e.mensagem)
        self.assertEqual(e.coluna, 13)

    def test_linha_vazia(self):
        self.assertIn("vazia", erro_de(arvore, "   ").mensagem)

    def test_opcao_repetida_e_problema_do_semantico(self):
        """A gramática aceita { opcao }: repetir é erro de significado."""
        a = arvore("entrada 52998224725 placa ABC1D23 placa XYZ9876")
        self.assertEqual(len(a.opcoes), 2)

    def test_arvore_visual(self):
        no = arvore_visual(arvore("entrada 111.444.777-35 visitante "
                                  "placa QWE1E34"))
        self.assertEqual(no.rotulo, "ComandoEntrada")
        self.assertEqual([f.rotulo for f in no.filhos],
                         ["entrada", "cpf", "tipo", "opção placa"])
        placa = no.filhos[-1]
        self.assertEqual([f.rotulo for f in placa.filhos],
                         ["placa", "QWE1E34"])
        self.assertEqual((placa.inicio, placa.fim), (34, 47))

    def test_formato_do_erro_no_console(self):
        e = erro_de(arvore, "saida placa")
        linhas = formatar_erro("saida placa", e)
        self.assertEqual(linhas[1], " " * 11 + "^")
        self.assertTrue(linhas[2].startswith("[Sintático] fim da linha: "))
        self.assertTrue(linhas[3].startswith("Dica: "))


# ----------------------------------------------------------------------
# Semântico (com a tabela de símbolos num banco de teste)
# ----------------------------------------------------------------------
class BaseBanco(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.agora = AGORA
        self.banco = dados.Banco(os.path.join(self.pasta.name, "p.db"),
                                 relogio=lambda: self.agora)
        self.banco.criar_usuario("Ana Admin", "ana", "admin", "x")
        self.banco.criar_usuario("Paulo Porteiro", "paulo", "porteiro", "x",
                                 "ana")
        self.admin = {"login": "ana", "perfil": "admin", "nome": "Ana Admin"}
        self.porteiro = {"login": "paulo", "perfil": "porteiro",
                         "nome": "Paulo Porteiro"}
        # Carla no campus com o carro; Duda já saiu; Beto cadastrado
        self.banco.inserir({"nome": "Carla Souza", "cpf": CARLA,
                            "celular": "31987654321", "placa": "ABC1D23",
                            "tipo": "Aluno", "entrada": "21/10/2026 08:14",
                            "saida": ""}, autor="ana")
        self.banco.inserir({"nome": "Duda Martins", "cpf": DUDA,
                            "celular": "31987654321", "placa": "",
                            "tipo": "Professor", "entrada": "21/10/2026 07:00",
                            "saida": "21/10/2026 09:34"}, autor="ana")
        self.banco.cadastrar_pessoa(BETO, "Beto Rocha", "31987651234",
                                    "QWE1E34", "Visitante", "ana")

    def tearDown(self):
        self.pasta.cleanup()

    def analisar(self, texto, usuario=None):
        usuario = usuario or self.admin
        exibir = formatar_cpf if usuario is self.admin else mascarar_cpf
        return analisar(texto, self.banco, usuario, self.agora, exibir)

    def erro(self, texto, usuario=None):
        a = self.analisar(texto, usuario)
        self.assertIsNotNone(a.erro, texto)
        self.assertEqual(a.erro.fase, SEMANTICO)
        return a.erro

    def estados(self, a):
        return {c.regra: c.estado for c in a.checagens}


class TestSemantico(BaseBanco):
    def test_cpf_invalido(self):
        """CT-58 | RN06 | negativo | os dígitos verificadores não conferem:
        a frase está bem escrita, mas o CPF não existe."""
        e = self.erro("entrada 12345678900 aluno")
        self.assertEqual((e.regra, e.coluna), ("RN06", 9))
        self.assertIn("dígitos verificadores não conferem", e.mensagem)
        self.assertIn("um CPF tem 11 números",
                      self.erro("saida 1234567890").mensagem)

    def test_ja_no_campus(self):
        """CT-58 | RN05 | negativo | Carla já está no campus."""
        e = self.erro(f"entrada {CARLA}")
        self.assertEqual(e.regra, "RN05")
        self.assertIn("Carla Souza está no campus desde 08:14", e.mensagem)
        self.assertIn("saida 390.533.447-05", e.dica)

    def test_saida_sem_entrada_aberta(self):
        """CT-58 | RN03 | negativo | Duda saiu às 09:34; e o CPF sem nenhum
        registro (também pelo implícito, a antiga Saída rápida)."""
        e = self.erro(f"saida {DUDA}")
        self.assertEqual(e.regra, "RN03")
        self.assertIn("Duda Martins não está no campus (saiu hoje às 09:34)",
                      e.mensagem)
        e = self.erro(NOVO)
        self.assertIn("ninguém no campus nem veículo", e.mensagem)

    def test_desativado(self):
        """CT-58 | RN12 | negativo | placa ou pessoa desativada: para no
        semântico, com o ^ no que está desativado, e a recusa vai ao
        histórico (como no formulário)."""
        self.banco.desativar("placa", "QWE1E34", "furto no estacionamento",
                             "ana")
        e = self.erro(f"entrada {BETO} visitante placa QWE1E34")
        self.assertEqual(e.regra, "RN12")
        self.assertIn("furto no estacionamento", e.mensagem)
        self.assertEqual(e.coluna, len(f"entrada {BETO} visitante ") + 1)
        self.assertEqual(e.recusa["placa"], "QWE1E34")
        # a placa do cadastro também é conferida (como no formulário)
        self.assertEqual(self.erro(f"entrada {BETO} visitante").regra, "RN12")
        a = self.analisar(f"entrada {BETO} visitante sem carro")
        self.assertIsNone(a.erro)
        self.banco.desativar("cpf", BETO, "agressão ao porteiro", "ana")
        e = self.erro(f"entrada {BETO} visitante sem carro")
        self.assertEqual((e.regra, e.coluna), ("RN12", 9))

    def test_porteiro_em_comando_de_admin(self):
        """CT-59 | RN02 | negativo | excluir, desativar e reativar são do
        administrador: o porteiro para no semântico."""
        for texto in [f"excluir {BETO}",
                      f'desativar {BETO} motivo "teste de motivo"',
                      "reativar placa QWE1E34"]:
            with self.subTest(texto=texto):
                e = self.erro(texto, self.porteiro)
                self.assertIn("RN02", e.regra)
                self.assertIn("administrador", e.mensagem)
                self.assertEqual(e.coluna, 1)
        a = self.analisar(f'desativar {BETO} motivo "teste de motivo"')
        self.assertIsNone(a.erro)
        self.assertEqual(a.plano.acao, "desativar")

    def test_tipo_diferente_e_aviso(self):
        """CT-60 | RF14 | positivo | o tipo diferente do cadastro é um
        AVISO (segue, mas pergunta), como a conversão de tipo."""
        a = self.analisar(f"entrada {BETO} prestador sem carro")
        self.assertIsNone(a.erro)
        self.assertIn(AVISO, [c.estado for c in a.checagens])
        self.assertIn("Registrar como Prestador de serviço?",
                      a.plano.dados["confirmar_tipo"])
        self.assertEqual(a.plano.dados["registro"]["tipo"],
                         "Prestador de serviço")

    def test_periodo_invertido(self):
        """CT-60 | RF03 | negativo | o período termina antes de começar."""
        e = self.erro("buscar maria de 15/10/2026 ate 01/10/2026")
        self.assertIn("termina antes de começar", e.mensagem)
        self.assertEqual(e.coluna, len("buscar maria ") + 1)

    def test_retroativo_e_horario_pedem_autorizacao(self):
        """CT-61 | RN24 | positivo | o lançamento de um dia que já fechou e
        a entrada fora da janela da categoria passam no semântico com a
        checagem AUTORIZACAO: a execução abre o diálogo do admin."""
        a = self.analisar(f"entrada {BETO} visitante sem carro "
                          "em 18/10/2026 08:00")
        self.assertIsNone(a.erro)
        self.assertEqual(self.estados(a)["RN17, RN20, RN24"], AUTORIZACAO)
        self.agora = AGORA.replace(hour=19, minute=30)
        a = self.analisar(f"entrada {BETO} visitante sem carro as 19:10")
        self.assertEqual(self.estados(a)["RN17, RN20, RN24"], AUTORIZACAO)
        e = self.erro(f"entrada {BETO} visitante sem carro as 20:00")
        self.assertEqual(e.regra, "RN07")                  # no futuro

    def test_cpf_novo_sem_dados(self):
        e = self.erro(f"entrada {NOVO}")
        self.assertEqual(e.regra, "RN01")
        self.assertIn("informe o tipo, o nome e o celular", e.mensagem)
        self.assertIn('nome "Bruno Almeida"', e.dica)
        e = self.erro(f'entrada {NOVO} visitante nome "Rui Lima"')
        self.assertIn("informe o celular", e.mensagem)

    def test_opcao_repetida_e_contraditoria(self):
        """CT-60 | RN06 | negativo | "placa" duas vezes = variável declarada
        duas vezes; "placa" com "sem carro" não combinam."""
        e = self.erro(f"entrada {BETO} placa ABC1234 placa XYZ9876")
        self.assertIn("informada duas vezes", e.mensagem)
        self.assertEqual(e.coluna, len(f"entrada {BETO} placa ABC1234 ") + 1)
        e = self.erro(f"entrada {BETO} placa ABC1234 sem carro")
        self.assertIn("não combinam", e.mensagem)

    def test_carro_ja_no_estacionamento(self):
        e = self.erro(f"entrada {BETO} placa ABC1D23")
        self.assertEqual(e.regra, "RN26")
        self.assertIn("já está no estacionamento", e.mensagem)

    def test_pergunta_do_carro_rn34(self):
        """Beto tem placa no cadastro e não disse "placa" nem "sem carro":
        a execução abre a pergunta do formulário (RN34)."""
        a = self.analisar(f"entrada {BETO}")
        self.assertIsNone(a.erro)
        self.assertEqual(self.estados(a)["RN34"], PERGUNTA)
        self.assertEqual(a.plano.dados["sugerida"], "QWE1E34")
        a = self.analisar(f"entrada {BETO} sem carro")
        self.assertEqual(a.plano.dados["registro"]["placa"], "")
        self.assertEqual(a.plano.dados["sugerida"], "")

    def test_saida_pela_placa_e_pelo_cpf(self):
        a = self.analisar("ABC1D23")
        self.assertEqual(a.plano.acao, "saida_carro")
        self.assertEqual(self.estados(a)["RN32"], PERGUNTA)   # saiu junto?
        a = self.analisar(f"saida {CARLA} sem carro")
        self.assertEqual(a.plano.dados["com_veiculo"], {})
        self.assertEqual(list(a.plano.dados["a_pe"].values()), [["ABC1D23"]])
        a = self.analisar(f"saida {CARLA} placa ABC1D23")
        self.assertEqual(len(a.plano.dados["com_veiculo"]), 1)
        e = self.erro(f"saida {CARLA} placa XYZ9876")
        self.assertIn("não está no estacionamento", e.mensagem)
        e = self.erro("saida placa XYZ9876")
        self.assertEqual(e.regra, "RN27")

    def test_saida_retroativa_e_futuro(self):
        a = self.analisar(f"saida {CARLA} sem carro as 09:00")
        self.assertIsNone(a.erro)
        self.assertEqual(a.plano.dados["momento"],
                         datetime(2026, 10, 21, 9, 0))
        self.assertNotIn("RN19, RN24", self.estados(a))   # 1 h atrás: normal
        self.agora = AGORA.replace(hour=13, minute=30)    # 4 h 30 atrás
        a = self.analisar(f"saida {CARLA} sem carro as 09:00")
        self.assertEqual(self.estados(a)["RN19, RN24"], AUTORIZACAO)
        self.assertEqual(self.erro(f"saida {CARLA} as 14:00").regra, "RN07")
        self.assertEqual(self.erro(f"saida {CARLA} as 08:00").regra, "RN04")

    def test_crud_da_pessoa(self):
        a = self.analisar(f'cadastrar {NOVO} visitante nome "Rui Lima" '
                          "cel 31987651234")
        self.assertEqual(a.plano.acao, "cadastrar")
        e = self.erro(f'cadastrar {BETO} visitante nome "Rui Lima" '
                      "cel 31987651234")
        self.assertEqual(e.regra, "RN41")
        e = self.erro(f'cadastrar {NOVO} visitante nome "Rui" cel 31987651234')
        self.assertIn("nome completo", e.mensagem)
        a = self.analisar(f"editar {BETO} cel 31999990000 tipo professor")
        self.assertEqual(a.plano.dados["mudou"], ["celular", "tipo"])
        self.assertIn("nada muda", self.erro(f"editar {BETO} tipo "
                                             "visitante").mensagem)
        self.assertIn("não está cadastrado", self.erro(f"editar {NOVO} tipo "
                                                       "aluno").mensagem)
        self.assertEqual(self.analisar(f"excluir {BETO}").plano.acao,
                         "excluir")
        e = self.erro(f"excluir {CARLA}")
        self.assertEqual(e.regra, "RN42")
        self.assertIn("não pode ser excluída", e.mensagem)
        e = self.erro(f"reativar {BETO}")
        self.assertIn("não está desativado", e.mensagem)

    def test_porteiro_ve_o_cpf_mascarado(self):
        """CT-59 | RN14 | positivo | para o porteiro, a linha, o erro e a
        tabela de símbolos mostram o CPF mascarado."""
        a = self.analisar(f"entrada {CARLA}", self.porteiro)
        tudo = " ".join([a.linha_exibida] + a.linhas_do_erro()
                        + [s.chave + s.descricao for s in a.simbolos])
        self.assertNotIn(CARLA, tudo)
        self.assertNotIn(formatar_cpf(CARLA), tudo)
        self.assertIn("***.533.447-**", tudo)
        self.assertIn("***533447**", a.linha_exibida)
        a = self.analisar(f"entrada {CARLA}")              # o admin vê
        self.assertIn(CARLA, a.linha_exibida)

    def test_fases_e_simbolos(self):
        a = self.analisar(f"entrada {CARLA}")
        self.assertEqual(list(a.fases.values()),
                         [PASSOU, PASSOU, FALHOU, NAO_RODOU])
        categorias = [s.categoria for s in a.simbolos]
        self.assertEqual(categorias[0], "Usuário")
        self.assertIn("Pessoa", categorias)
        self.assertEqual(a.checagens[-1].estado, C_ERRO)
        a = analisar_forma("saida placa AB12345")
        self.assertEqual(list(a.fases.values()),
                         [FALHOU, NAO_RODOU, NAO_RODOU, NAO_RODOU])
        a = self.analisar("dentro")
        self.assertIsNone(a.erro)
        self.assertEqual(a.fases["Semântico"], PASSOU)
        self.assertTrue(all(c.estado == OK for c in a.checagens))


# ----------------------------------------------------------------------
# As respostas das consultas (funções puras do executor)
# ----------------------------------------------------------------------
class TestConsultas(BaseBanco):
    def quando(self, momento):
        return momento[-5:] if momento.startswith("21/10/2026") else momento

    def test_situacao(self):
        a = self.analisar(f"situacao {CARLA}", self.porteiro)
        r = situacao_da_pessoa(a.plano.dados, mascarar_cpf, self.quando)
        self.assertIn("Carla Souza está no campus desde 08:14", r.texto)
        self.assertIn("CPF ***.533.447-**", r.linhas[0])
        self.assertIn("Carro ABC1D23 no estacionamento", " ".join(r.linhas))

    def test_dentro_e_buscar(self):
        registros = self.banco.listar()
        r = quem_esta_dentro(registros, None, mascarar_cpf, self.quando)
        self.assertEqual(r.texto, "1 pessoa no campus agora.")
        self.assertIn("***.533.447-**", r.linhas[0])
        r = quem_esta_dentro(registros, "Visitante", mascarar_cpf, self.quando)
        self.assertIn("Ninguém", r.texto)
        r = resultado_da_busca(registros, "", "Professor", date(2026, 10, 21),
                               date(2026, 10, 21), formatar_cpf)
        self.assertEqual(r.texto, "1 visita encontrada no histórico.")
        self.assertIn("saída 09:34", r.linhas[0])

    def test_pendentes(self):
        config = self.banco.ler_configuracao()
        noite = AGORA.replace(hour=23, minute=40)
        r = pendencias(config, self.banco.listar(),
                       self.banco.listar_estacionamento(), noite, self.quando)
        self.assertIn("saída pendente", r.texto)
        self.assertTrue(any("Carla Souza" in linha for linha in r.linhas))

    def test_ajuda_vem_da_gramatica(self):
        r = ajuda()
        self.assertEqual(len(r.linhas), 13)
        self.assertTrue(r.linhas[0].startswith("entrada"))
        r = ajuda(admin=False)
        self.assertFalse(any(linha.startswith("excluir") for linha in
                             r.linhas))
        r = ajuda("entrada")
        self.assertIn('entrada    = "entrada" cpf [ TIPO ] { opcao_ent } ;',
                      r.linhas)
        self.assertTrue(any(re.match(r"opcao_ent", linha) for linha in
                            r.linhas))


if __name__ == "__main__":
    unittest.main()


# ----------------------------------------------------------------------
# O comentário "RELAÇÃO COM COMPILADORES" aponta para linhas reais
# ----------------------------------------------------------------------
class TestComentarioDeCompiladores(unittest.TestCase):
    def test_as_linhas_citadas_existem(self):
        """Cada "arquivo, linha N:" do comentário em
        portaria_universidade.py tem embaixo o código daquela linha."""
        with open(os.path.join(RAIZ, "portaria_universidade.py"),
                  encoding="utf-8") as f:
            comentario = f.read()
        citacoes = re.findall(r"#    (portaria/\S+\.py), linha (\d+):\n"
                              r"#        (.+)\n", comentario)
        self.assertGreaterEqual(len(citacoes), 5)
        for arquivo, linha, codigo in citacoes:
            with self.subTest(arquivo=arquivo, linha=linha):
                with open(os.path.join(RAIZ, arquivo), encoding="utf-8") as f:
                    linhas = f.read().splitlines()
                self.assertEqual(linhas[int(linha) - 1].strip(),
                                 codigo.strip())
