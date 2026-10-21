"""
Perguntas sobre o carro (estadia de veículo, dados.py):

- a pessoa que sai tem um carro no estacionamento: "Saiu com o veículo
  ABC-1234?" → [Saiu de carro] fecha a visita e a estadia; [Saiu a pé — o
  carro fica] fecha só a visita;
- a saída é do carro (saída rápida pela placa ou lista de veículos) e o
  responsável está no campus: "Fulano saiu junto?" → [Saiu junto] fecha os
  dois; [Só o carro saiu] o carro sairia sem o dono;
- O VEÍCULO SÓ SAI COM O DONO (RN32): o carro sairia sem o dono (ele está
  fora do campus ou fica no campus) → a mensagem "O veículo só sai com o
  dono" e, se o porteiro chamar um administrador, o diálogo de autorização
  com a senha (tela_autorizacao.py, veiculo=True).

Esc ou Cancelar: nada é registrado. Enter escolhe o botão destacado. A
tela abre a pergunta por app.perguntar: se a sessão acabar com ela
aberta, a resposta é None e nada é gravado.
"""

from .componentes import Dialogo, Placa
from .dados import VEICULO_SEM_DONO
from .estilo import px
from .tela_autorizacao import autorizar_excecao
from .validacao import formatar_placa

COM_CARRO, A_PE = "carro", "a_pe"
JUNTO, SO_CARRO = "junto", "so_carro"
LIBERAR = "liberar"


class JanelaVeiculo(Dialogo):
    def __init__(self, app, titulo, subtitulo, placa, opcoes, padrao=None,
                 largura=460):
        """opcoes: [(texto do botão, valor, variante)], da direita para a
        esquerda. `padrao`: o valor do Enter (sem ele, o da 1ª opção).
        `resultado` fica com o valor escolhido (None = cancelou)."""
        self.app = app
        self.resultado = None
        self.opcoes = opcoes
        self.padrao = opcoes[0][1] if padrao is None else padrao
        super().__init__(app.janela, titulo, subtitulo, largura=largura,
                         ao_usar=app.registrar_uso)
        self.desenho = Placa(self.miolo, largura=190)
        self.desenho.pack(anchor="w", pady=(0, px(4)))
        self.desenho.mostrar(placa)
        for texto, valor, variante in opcoes:
            self.adicionar_botao(texto, lambda v=valor: self.escolher(v), variante)
        self.adicionar_botao("Cancelar", self.fechar)
        self.abrir(confirmar=lambda: self.escolher(self.padrao))

    def escolher(self, valor):
        self.resultado = valor
        self.fechar()

    def esperar(self):
        """Trava até o diálogo fechar (os testes trocam por uma resposta)."""
        self.janela.wait_window()


def _perguntar(app, titulo, subtitulo, placa, opcoes, padrao=None,
               largura=460):
    dialogo = JanelaVeiculo(app, titulo, subtitulo, placa, opcoes, padrao,
                            largura)
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
        f"{nome} está saindo. O carro registrado com essa pessoa está no "
        f"estacionamento desde {_desde(app, estadia)}.", estadia["placa"],
        [("Saiu de carro", COM_CARRO, "primario"),
         ("Saiu a pé — o carro fica", A_PE, "secundario")])


def responsavel_saiu_junto(app, estadia):
    """JUNTO, SO_CARRO ou None (cancelou)."""
    primeiro = estadia["nome"].split()[0]
    return app.perguntar(
        _perguntar, app, f"{primeiro} saiu junto com o carro?",
        f"O carro {formatar_placa(estadia['placa'])} está saindo e o "
        f"dono, {estadia['nome']}, está no campus. O veículo só sai com o "
        "dono: sem ele, só com a senha de um administrador.", estadia["placa"],
        [("Saiu junto", JUNTO, "primario"),
         ("Só o carro saiu", SO_CARRO, "secundario")])


def _onde_esta_o_dono(estadia):
    return ("continua no campus e não sai junto" if estadia["responsavel_dentro"]
            else "não está no campus")


def texto_so_sai_com_o_dono(app, estadia):
    """'O dono do veículo ABC-1234 (Ana Silva, CPF ***.982.247-**) não está
    no campus. O veículo só sai com o dono; ...' (CPF mascarado para o
    porteiro, como nas listas)."""
    return (f"O dono do veículo {formatar_placa(estadia['placa'])} "
            f"({estadia['nome']}, CPF {app.exibir_cpf(estadia['cpf'])}) "
            f"{_onde_esta_o_dono(estadia)}. O veículo só sai com o dono; para "
            "liberar, um administrador precisa digitar a senha.")


def liberar_sem_o_dono(app, estadia):
    """RN32: mostra "O veículo só sai com o dono" e, se o porteiro chamar um
    administrador, pede a senha dele (até o administrador logado redigita
    a sua) e a justificativa. Devolve a autorização ou None."""
    placa = formatar_placa(estadia["placa"])
    texto = texto_so_sai_com_o_dono(app, estadia)
    resposta = app.perguntar(
        _perguntar, app, "O veículo só sai com o dono", texto,
        estadia["placa"],
        [("Liberar com a senha do administrador", LIBERAR, "primario")])
    if resposta != LIBERAR:
        return None
    regra = (f"{VEICULO_SEM_DONO}: {placa} — o dono, {estadia['nome']}, "
             f"{_onde_esta_o_dono(estadia)}.")
    return autorizar_excecao(app, [regra], f"A saída do veículo {placa}",
                             veiculo=True)
