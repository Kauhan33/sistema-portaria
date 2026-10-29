"""
Erros da linguagem de comandos, iguais em todas as fases.

O console mostra cada erro como um compilador: a linha digitada, um ^
embaixo da posição do problema, a fase entre colchetes e uma dica.

    saida placa AB12345
                ^^^^^^^
    [Léxico] coluna 13: "AB12345" não é uma placa.
    Dica: formatos ABC1234 (antiga) ou ABC1D23 (Mercosul).
"""

LEXICO, SINTATICO, SEMANTICO, EXECUCAO = ("Léxico", "Sintático", "Semântico",
                                          "Execução")
FASES = (LEXICO, SINTATICO, SEMANTICO, EXECUCAO)


class ErroDeAnalise(Exception):
    """
    Um erro de uma fase. `coluna` começa em 1 (None = sem posição, ex.: um
    erro do banco na execução); `tamanho` é quantos caracteres o ^ marca.
    `sugestao` é o "você quis dizer…?" (o campo aplica com Tab) e `regra`,
    a regra de negócio da checagem semântica (ex.: "RN05").
    """

    def __init__(self, fase, mensagem, coluna=None, tamanho=1, dica="",
                 sugestao="", regra="", fim_da_linha=False):
        super().__init__(mensagem)
        self.fase, self.mensagem = fase, mensagem
        self.coluna, self.tamanho = coluna, max(1, tamanho)
        self.dica, self.sugestao, self.regra = dica, sugestao, regra
        self.fim_da_linha = fim_da_linha

    def onde(self):
        """'coluna 13', 'fim da linha' ou '' (sem posição)."""
        if self.fim_da_linha:
            return "fim da linha"
        return f"coluna {self.coluna}" if self.coluna else ""

    def titulo(self):
        """'[Léxico] coluna 13: "AB12345" não é uma placa.'"""
        onde = self.onde()
        regra = f" ({self.regra})" if self.regra and self.regra not in \
            self.mensagem else ""
        return (f"[{self.fase}]" + (f" {onde}" if onde else "") + ": "
                + self.mensagem + regra)


def marcador(erro):
    """A linha do ^ (espaços até a coluna e um ^ por caractere marcado)."""
    if not erro.coluna:
        return ""
    return " " * (erro.coluna - 1) + "^" * erro.tamanho


def formatar_erro(linha, erro):
    """As linhas que o console mostra para o erro (a `linha` digitada já
    vem mascarada para o porteiro: a máscara não muda as colunas)."""
    linhas = [linha]
    if erro.coluna:
        linhas.append(marcador(erro))
    linhas.append(erro.titulo())
    if erro.sugestao:
        linhas.append(f"Você quis dizer {erro.sugestao}? (Tab corrige)")
    if erro.dica:
        linhas.append("Dica: " + erro.dica)
    return linhas
