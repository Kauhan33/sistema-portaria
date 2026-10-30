"""
Perguntas sobre o carro (estadia de veículo, dados.py):

- na ENTRADA de quem tem placa cadastrada (RN34): "Fulano vai entrar de
  carro?" → [De carro — ABC-1234] a placa entra na visita (abre a estadia);
  [A pé] entra sem placa; [Com outro carro] volta ao campo Placa para
  digitar a outra. O botão destacado (e o Enter) é "De carro" se a última
  visita dela foi de carro, senão "A pé";
- a pessoa que sai tem um carro no estacionamento: "Saiu com o veículo
  ABC-1234?" → [Saiu de carro] fecha a visita e a estadia; [Saiu a pé — o
  carro fica] fecha só a visita;
- a saída é do carro (saída rápida pela placa ou lista de veículos) e o
  responsável está no campus: "Fulano saiu junto?" → [Saiu junto] fecha os
  dois; [Só o carro saiu] o carro sairia sem o dono;
- O VEÍCULO SÓ SAI COM O DONO (RN32): o carro sairia sem o dono (ele está
  fora do campus ou fica no campus) → a mensagem "O veículo só sai com o
  dono" e, se o porteiro chamar um administrador, o diálogo de autorização
  com a senha (tela_autorizacao.py, veiculo=True);
- DOIS CARROS DA MESMA PESSOA (RN40): na entrada com outro carro, "Carla
  já tem o BRA2E19 no estacionamento desde 08:20" → [Entrar — ficam os
  dois] (padrão) / [O BRA2E19 já saiu] (senha do administrador) /
  Cancelar; com 2 carros dela lá, o terceiro só com a senha. Na saída de
  quem tem mais de um carro, UMA pergunta: "Com qual carro Carla está
  saindo?" → um botão por placa (com o horário) / [A pé — os carros ficam];
- QUEM PODE RETIRAR (RN35): quem sai está na lista da placa de um carro no
  estacionamento → "Vai levar o carro BRA2E19 de Carla?" → [Sim, leva o
  carro] o carro sai junto, sem senha; [Não] sai sem ele.

Esc ou Cancelar: nada é registrado. Enter escolhe o botão destacado. A
tela abre a pergunta por app.perguntar: se a sessão acabar com ela
aberta, a resposta é None e nada é gravado.
"""

from .componentes import Botao, Dialogo, Placa
from .dados import VEICULO_SEM_DONO
from .estilo import px
from .tela_autorizacao import autorizar_excecao
from .validacao import formatar_placa
from .veiculos import aviso_outro_carro, precisa_senha_para_outro_carro

COM_CARRO, A_PE = "carro", "a_pe"
JUNTO, SO_CARRO = "junto", "so_carro"
OUTRO_CARRO = "outro_carro"
LIBERAR = "liberar"
LEVA, NAO_LEVA = "leva", "nao_leva"
ENTRAR, ENTRAR_COM_SENHA, JA_SAIU = "entrar", "entrar_com_senha", "ja_saiu"


class JanelaVeiculo(Dialogo):
    def __init__(self, app, titulo, subtitulo, placa, opcoes, padrao=None,
                 largura=460, no_miolo=()):
        """opcoes: [(texto do botão, valor, variante)], da direita para a
        esquerda. `padrao`: o valor do Enter (sem ele, o da 1ª opção).
        `no_miolo`: mais opções, uma embaixo da outra sob a placa (um
        botão por carro, RN47). `resultado` fica com o valor escolhido
        (None = cancelou)."""
        self.app = app
        self.resultado = None
        self.opcoes = opcoes
        self.padrao = opcoes[0][1] if padrao is None else padrao
        super().__init__(app.janela, titulo, subtitulo, largura=largura,
                         ao_usar=app.registrar_uso)
        self.desenho = Placa(self.miolo, largura=190)
        self.desenho.pack(anchor="w", pady=(0, px(4)))
        self.desenho.mostrar(placa)
        for texto, valor, variante in no_miolo:
            Botao(self.miolo, texto, lambda v=valor: self.escolher(v),
                  variante).pack(fill="x", pady=(px(6), 0))
        self.no_miolo = no_miolo
        self.valores = [v for _, v, _ in (*no_miolo, *opcoes)]
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
               largura=460, no_miolo=()):
    dialogo = JanelaVeiculo(app, titulo, subtitulo, placa, opcoes, padrao,
                            largura, no_miolo)
    dialogo.esperar()
    if dialogo.janela.winfo_exists():
        dialogo.fechar()
    return dialogo.resultado


def _desde(app, estadia):
    """'08:00' se o carro entrou hoje; senão a data e a hora."""
    hoje = app.relogio().strftime("%d/%m/%Y")
    entrada = estadia["entrada"]
    return entrada[-5:] if entrada.startswith(hoje) else entrada


def vai_entrar_de_carro(app, nome, placa, veio_de_carro, outras=()):
    """RN34: COM_CARRO, A_PE, OUTRO_CARRO ou None (cancelou).
    veio_de_carro: a última visita foi de carro (destaca "De carro").
    `outras` (RN47): os outros carros do cadastro; escolhendo um deles,
    devolve a placa dele."""
    primeiro = nome.split()[0] if nome.split() else "A pessoa"
    padrao = COM_CARRO if veio_de_carro else A_PE

    def variante(valor):
        return "primario" if valor == padrao else "secundario"

    if outras:
        carros = [(f"De carro — {formatar_placa(p)}", valor, variante(valor))
                  for p, valor in ((placa, COM_CARRO),
                                   *((o, o) for o in outras))]
        return app.perguntar(
            _perguntar, app, f"{primeiro} vai entrar de carro?",
            f"{nome} tem {len(carros)} veículos cadastrados. Escolha com "
            "qual vai entrar; a pé, a visita fica sem placa.", placa,
            [("A pé", A_PE, variante(A_PE)),
             ("Com outro carro", OUTRO_CARRO, "fantasma")],
            padrao, 520, carros)
    return app.perguntar(
        _perguntar, app, f"{primeiro} vai entrar de carro?",
        f"{nome} tem o veículo {formatar_placa(placa)} cadastrado. De carro, "
        "a placa entra na visita; a pé, a visita fica sem placa.", placa,
        [(f"De carro — {formatar_placa(placa)}", COM_CARRO,
          variante(COM_CARRO)),
         ("A pé", A_PE, variante(A_PE)),
         ("Com outro carro", OUTRO_CARRO, "fantasma")],
        padrao, 520)


def saiu_com_o_veiculo(app, nome, estadia):
    """COM_CARRO, A_PE ou None (cancelou)."""
    placa = formatar_placa(estadia["placa"])
    return app.perguntar(
        _perguntar, app, f"Saiu com o veículo {placa}?",
        f"{nome} está saindo. O carro registrado com essa pessoa está no "
        f"estacionamento desde {_desde(app, estadia)}.", estadia["placa"],
        [("Saiu de carro", COM_CARRO, "primario"),
         ("Saiu a pé — o carro fica", A_PE, "secundario")])


def com_qual_carro(app, nome, estadias):
    """RN40: a pessoa tem mais de um carro no estacionamento. Devolve o id
    da estadia com que ela sai, A_PE ou None (cancelou). `estadias` já na
    ordem (o carro desta visita primeiro: é o do Enter)."""
    primeiro = nome.split()[0] if nome.split() else "A pessoa"
    placas = ", ".join(formatar_placa(e["placa"]) for e in estadias)
    opcoes = [(f"{formatar_placa(e['placa'])} — desde {_desde(app, e)}",
               e["id"], "primario" if i == 0 else "secundario")
              for i, e in enumerate(estadias)]
    opcoes.append(("A pé — os carros ficam", A_PE, "fantasma"))
    return app.perguntar(
        _perguntar, app, f"Com qual carro {primeiro} está saindo?",
        f"{nome} tem {len(estadias)} carros no estacionamento ({placas}). "
        "Uma pessoa sai com um carro só; o outro fica e sai depois com ela, "
        "com quem pode retirar ou com a senha do administrador.",
        estadias[0]["placa"], opcoes, estadias[0]["id"],
        largura=180 * len(estadias) + 260)


def entrar_com_outro_carro(app, nome, placa_nova, estadias):
    """RN40, na entrada com outro carro: ENTRAR, ENTRAR_COM_SENHA,
    (JA_SAIU, id da estadia) ou None (cancelou)."""
    carros = [(formatar_placa(e["placa"]), _desde(app, e)) for e in estadias]
    senha = precisa_senha_para_outro_carro(len(estadias))
    if senha:
        opcoes = [("Entrar com a senha do administrador", ENTRAR_COM_SENHA,
                   "primario")]
        texto = (f"{nome} já tem "
                 + " e ".join(f"o {p} (desde {d})" for p, d in carros)
                 + f" no estacionamento. Um terceiro carro, o "
                   f"{formatar_placa(placa_nova)}, só entra com a senha de um "
                   "administrador. Se um deles já saiu, corrija.")
    else:
        opcoes = [("Entrar — ficam os dois", ENTRAR, "primario")]
        texto = (f"{nome} está entrando com o {formatar_placa(placa_nova)}. "
                 "Se o carro de antes ainda está lá, os dois ficam no "
                 "estacionamento; se ele saiu sem registro, corrija agora.")
    opcoes += [(f"O {p} já saiu", (JA_SAIU, e["id"]), "secundario")
               for (p, _), e in zip(carros, estadias)]
    return app.perguntar(
        _perguntar, app, aviso_outro_carro(nome, carros), texto,
        estadias[0]["placa"], opcoes, opcoes[0][1],
        largura=160 * len(opcoes) + 240)


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


def vai_levar_o_carro(app, nome, estadia, autorizado):
    """RN35: LEVA, NAO_LEVA ou None (cancelou). `nome`: quem sai;
    `autorizado`: a linha da lista (quem cadastrou e quando)."""
    placa = formatar_placa(estadia["placa"])
    dono = estadia["nome"].split()[0] if estadia["nome"].split() else "dono"
    onde = ("continua no campus" if estadia["responsavel_dentro"]
            else "está fora do campus")
    return app.perguntar(
        _perguntar, app, f"Vai levar o carro {placa} de {dono}?",
        f"{nome} pode retirar este carro (autorizado por "
        f"{autorizado['criado_por']} em {autorizado['criado_em'][:10]}). "
        f"O dono, {estadia['nome']}, {onde}. Levando, o carro sai junto, "
        "sem a senha do administrador.", estadia["placa"],
        [("Sim, leva o carro", LEVA, "primario"),
         ("Não", NAO_LEVA, "secundario")])


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
