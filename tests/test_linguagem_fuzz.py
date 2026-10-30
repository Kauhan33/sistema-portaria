"""
Fuzz da linguagem de comandos (revisão 2.5.1): milhares de linhas
sorteadas — palavras da linguagem misturadas, CPFs válidos e inválidos,
placas, datas, horas, textos com e sem aspas, símbolos, acentos, emoji e
linhas cortadas no meio — passam pelas três fases. Para cada uma:

- a análise nunca levanta exceção: ou passa, ou para numa fase com um
  ErroDeAnalise (léxico, sintático ou semântico) e a coluna do ^ cai
  dentro da linha;
- a análise só lê o banco (nada é gravado);
- para o porteiro, nada do que a tela mostra (a linha, o erro, a tabela de
  símbolos e as checagens) tem um CPF inteiro (RN14).

PORTARIA_FUZZ=20000 roda uma versão longa.
"""
import os
import random
import re
import sqlite3
import unittest

from portaria.linguagem.erros import FASES
from portaria.linguagem.interpretador import analisar
from portaria.validacao import formatar_cpf, mascarar_cpf

from .test_linguagem import BETO, CARLA, DUDA, NOVO, BaseBanco

LINHAS = int(os.environ.get("PORTARIA_FUZZ", "1500"))

PALAVRAS = (
    ["entrada", "saida", "saída", "cadastrar", "editar", "excluir",
     "desativar", "reativar", "situacao", "situação", "dentro", "buscar",
     "pendentes", "ajuda", "ENTRADA", "entrda", "sai"]
    + ["placa", "nome", "cel", "tipo", "motivo", "sem", "carro", "as", "em",
       "de", "ate", "até"]
    + ["aluno", "professores", "visitante", "prestador", "entregador",
       "funcionario", "hoje", "ontem", "semana", "mes"])
CPFS = [CARLA, DUDA, BETO, NOVO, formatar_cpf(CARLA), formatar_cpf(BETO),
        "12345678900", "1234567890", "123456789012", mascarar_cpf(CARLA)]
OUTROS = ["ABC1D23", "abc-1234", "AB12345", "QWE1E34", "ZZZ9Z99",
          "21/10/2026", "32/13/2026", "29/02/2025", "29/02/2028", "08:00",
          "24:61", "7:5", "31987651234", "0", "9" * 40, '"Bruno Almeida"',
          '"sem fim', '""', '"Ana é \U0001F600"', "@", "#", ";", "--",
          "' OR 1=1 --", "%", "_", "\\", "\t", "maria", "Zé", "ção",
          "\U0001F697", "​", "ＡＢＣ１Ｄ２３"]


def linha_aleatoria(r):
    pedacos = []
    for _ in range(r.randint(0, 9)):
        pedacos.append(r.choice([r.choice(PALAVRAS), r.choice(CPFS),
                                 r.choice(OUTROS)]))
    texto = " ".join(pedacos)
    if r.random() < 0.15:                       # cortada no meio
        texto = texto[:r.randint(0, len(texto))]
    if r.random() < 0.05:
        texto = "  " + texto + "   "
    return texto


class TestFuzzDaLinguagem(BaseBanco):
    def contagem(self):
        con = sqlite3.connect(self.banco.caminho)
        try:
            return tuple(con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                         for t in ("registros", "pessoas", "auditoria",
                                   "bloqueios", "placas_pessoa",
                                   "estadias_veiculo"))
        finally:
            con.close()

    def test_linhas_aleatorias(self):
        r = random.Random(2026)
        antes = self.contagem()
        fases, inteiros = set(), [CARLA, DUDA, BETO, formatar_cpf(CARLA),
                                  formatar_cpf(DUDA), formatar_cpf(BETO)]
        for _ in range(LINHAS):
            texto = linha_aleatoria(r)
            for usuario in (self.admin, self.porteiro):
                exibir = formatar_cpf if usuario is self.admin else mascarar_cpf
                try:
                    a = analisar(texto, self.banco, usuario, self.agora, exibir)
                except Exception as e:                      # noqa: BLE001
                    self.fail(f"{texto!r}: {type(e).__name__}: {e}")
                if a.erro is not None:
                    self.assertIn(a.erro.fase, FASES, texto)
                    fases.add(a.erro.fase)
                    if a.erro.coluna is not None:
                        self.assertGreaterEqual(a.erro.coluna, 1, texto)
                        self.assertLessEqual(a.erro.coluna, len(texto) + 1,
                                             texto)
                    a.linhas_do_erro()
                if usuario is self.porteiro:
                    tela = " ".join(
                        [a.linha_exibida] + a.linhas_do_erro()
                        + [s.chave + " " + s.descricao for s in a.simbolos]
                        + [c.descricao + " " + c.detalhe for c in a.checagens])
                    # o número logo depois de "cel" é o celular, que o
                    # porteiro digitou e vê (não é CPF)
                    tela = re.sub(r"(?i)\bcel\s+\d+", "cel #", tela)
                    for cpf in inteiros:
                        self.assertNotIn(cpf, tela, f"porteiro viu {cpf}: "
                                                    f"{texto!r}")
        self.assertEqual(self.contagem(), antes, "a análise gravou no banco")
        self.assertEqual(len(fases), 3, fases)   # as três fases apareceram


if __name__ == "__main__":
    unittest.main()
