"""
Perguntas sobre o carro na hora da saída (estadia de veículo, dados.py):

- a pessoa que sai tem um carro no estacionamento: "Saiu com o veículo
  ABC-1234?" → [Saiu de carro] fecha a visita e a estadia; [Saiu a pé — o
  carro fica] fecha só a visita;
- a saída é do carro (saída rápida pela placa ou lista de veículos) e o
  responsável está no campus: "Fulano saiu junto?" → [Saiu junto] fecha os
  dois; [Só o carro saiu] fecha só a estadia.

Esc ou Cancelar: nada é registrado. Enter escolhe o botão principal. A
tela abre a pergunta por app.perguntar: se a sessão acabar com ela
aberta, a resposta é None e nada é gravado.
"""

from .componentes import Dialogo, Placa
from .estilo import px
from .validacao import formatar_placa

COM_CARRO, A_PE = "carro", "a_pe"
JUNTO, SO_CARRO = "junto", "so_carro"


class JanelaVeiculo(Dialogo):
    def __init__(self, app, titulo, subtitulo, placa, opcoes):
        """opcoes: [(texto do botão, valor, variante)], a principal primeiro.
        `resultado` fica com o valor escolhido (None = cancelou)."""
        self.app = app
        self.resultado = None
        self.opcoes = opcoes
        super().__init__(app.janela, titulo, subtitulo, largura=460,
                         ao_usar=app.registrar_uso)
        self.desenho = Placa(self.miolo, largura=190)
        self.desenho.pack(anchor="w", pady=(0, px(4)))
        self.desenho.mostrar(placa)
        for texto, valor, variante in opcoes:
            self.adicionar_botao(texto, lambda v=valor: self.escolher(v), variante)
        self.adicionar_botao("Cancelar", self.fechar)
        self.abrir(confirmar=lambda: self.escolher(opcoes[0][1]))

    def escolher(self, valor):
        self.resultado = valor
        self.fechar()

    def esperar(self):
        """Trava até o diálogo fechar (os testes trocam por uma resposta)."""
        self.janela.wait_window()


def _perguntar(app, titulo, subtitulo, placa, opcoes):
    dialogo = JanelaVeiculo(app, titulo, subtitulo, placa, opcoes)
    dialogo.esperar()
    if dialogo.janela.winfo_exists():
        dialogo.fechar()
    return dialogo.resultado


def _desde(app, estadia):
    """'08:00' se o carro entrou hoje; senão a data e a hora."""
    hoje = app.relogio().strftime("%d/%m/%Y")
    entrada = estadia["entrada"]
    return entrada[-5:] if entrada.startswith(hoje) else entrada


def saiu_com_o_veiculo(app, nome, estadia):
    """COM_CARRO, A_PE ou None (cancelou)."""
    placa = formatar_placa(estadia["placa"])
    return app.perguntar(
        _perguntar, app, f"Saiu com o veículo {placa}?",
        f"{nome} está saindo e o carro dele está no estacionamento desde "
        f"{_desde(app, estadia)}.", estadia["placa"],
        [("Saiu de carro", COM_CARRO, "primario"),
         ("Saiu a pé — o carro fica", A_PE, "secundario")])


def responsavel_saiu_junto(app, estadia):
    """JUNTO, SO_CARRO ou None (cancelou)."""
    primeiro = estadia["nome"].split()[0]
    return app.perguntar(
        _perguntar, app, f"{primeiro} saiu junto com o carro?",
        f"O carro {formatar_placa(estadia['placa'])} está saindo e o "
        f"responsável, {estadia['nome']}, está no campus.", estadia["placa"],
        [("Saiu junto", JUNTO, "primario"),
         ("Só o carro saiu", SO_CARRO, "secundario")])
