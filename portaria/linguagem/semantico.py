"""
Análise SEMÂNTICA: a frase está bem escrita, mas faz sentido?

"entrada 12345678900 aluno" passa no léxico e no sintático, mas o CPF não
tem os dígitos verificadores certos (RN06). "entrada 39053344705" é bem
escrita, mas a pessoa já está no campus (RN05). O semântico olha a árvore
com a tabela de símbolos (simbolos.py) e o relógio, e roda as checagens
NA ORDEM, cada uma com a regra de negócio dela; para na primeira que
falha (nada é gravado), como o formulário.

Regra de ouro: as checagens chamam as MESMAS funções do formulário
(validacao.validar, validacao.checar_desativacao, horarios.excecoes_*,
usuarios.pode_*...). Aqui não há regra nova: só a ordem e a mensagem com
a coluna do token. O banco confere tudo de novo na gravação.

Resultado de cada checagem:
    OK           passou
    ERRO         para aqui (ErroDeAnalise da fase Semântico)
    AVISO        segue, mas o programa pergunta antes (ex.: o tipo do
                 comando é diferente do cadastro, como um compilador que
                 avisa de uma conversão de tipo e deixa seguir)
    PERGUNTA     a execução abre o MESMO diálogo do formulário (ex.: "Vai
                 entrar de carro?", "Com qual carro está saindo?")
    AUTORIZACAO  a execução abre a autorização do administrador (horário,
                 retroativo, veículo sem o dono...)

O produto é um Plano (o que o executor vai fazer, já com o registro
montado como o formulário monta) ou o erro.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .. import horarios
from ..usuarios import eh_admin, pode_excluir_pessoa, pode_gerenciar_desativacoes
from ..validacao import (FORMATO, MAXIMO_PLACAS_PESSOA, checar_desativacao,
                         checar_saida, cpf_valido, formatar_placa, normalizar,
                         validar, validar_campos, validar_desativacao,
                         validar_placas)
from ..veiculos import esta_lotado, regra_lotado
from .erros import SEMANTICO, ErroDeAnalise
from .lexico import PALAVRA_DO_TIPO
from .sintatico import (Alvo, ComandoAjuda, ComandoBuscar, ComandoCadastrar,
                        ComandoDentro, ComandoDesativar, ComandoEditar,
                        ComandoEntrada, ComandoExcluir, ComandoImplicito,
                        ComandoPendentes, ComandoReativar, ComandoSaida,
                        ComandoSituacao, Opcao, Periodo)

OK, ERRO, AVISO, PERGUNTA, AUTORIZACAO = ("ok", "erro", "aviso", "pergunta",
                                          "autorizacao")
# opções que não combinam (como duas declarações que se contradizem)
CONFLITOS = (("placa", "sem carro"), ("as", "em"))
PERIODOS_EM_DIAS = {"hoje": 0, "ontem": 1, "semana": 6, "mes": 29}
EXEMPLO_NOVA = ('entrada {cpf} visitante nome "Bruno Almeida" '
                'cel 31987651234')


@dataclass
class Checagem:
    descricao: str
    regra: str = ""
    estado: str = OK
    detalhe: str = ""
    coluna: int = 0           # o token que ela olhou (0 = a linha toda)
    fim: int = 0


@dataclass
class Plano:
    """O que o executor faz: `acao` e os dados já prontos."""
    acao: str
    dados: dict = field(default_factory=dict)


class AnalisadorSemantico:
    def __init__(self, simbolos):
        self.s = simbolos
        self.agora = simbolos.agora
        self.checagens = []

    # --------------------------------------------------------------
    # Utilitários
    # --------------------------------------------------------------
    def _anotar(self, descricao, regra="", estado=OK, detalhe="",
                token=None):
        coluna, fim = self._posicao(token)
        self.checagens.append(Checagem(descricao, regra, estado, detalhe,
                                       coluna, fim))

    @staticmethod
    def _posicao(token):
        if token is None:
            return 0, 0
        if isinstance(token, Opcao):
            ultimo = token.valores[-1] if token.valores else token.palavra
            return token.palavra.coluna, ultimo.fim
        if isinstance(token, Alvo):
            inicio = (token.palavra or token.valor).coluna
            return inicio, token.valor.fim
        if isinstance(token, Periodo):
            ultimo = token.fim or token.ate or token.inicio or token.palavra
            return token.palavra.coluna, ultimo.fim
        return token.coluna, token.fim

    def _exigir(self, condicao, descricao, regra, mensagem, token=None,
                dica="", recusa=None):
        """Anota a checagem; se falhou, para a análise com o erro."""
        self._anotar(descricao, regra, OK if condicao else ERRO,
                     "" if condicao else mensagem, token)
        if condicao:
            return
        coluna, fim = self._posicao(token)
        erro = ErroDeAnalise(SEMANTICO, mensagem, coluna or None,
                             max(1, fim - coluna), dica, regra=regra)
        erro.recusa = recusa             # entrada recusada vai ao histórico
        raise erro

    @staticmethod
    def _uma_linha(mensagem):
        """A mensagem do formulário (com quebras de linha) numa linha só,
        com ponto entre as partes."""
        partes = [p.strip() for p in mensagem.splitlines() if p.strip()]
        return " ".join(p if p[-1] in ".:!?" else p + "." for p in partes)

    def _cpf(self, token):
        """O CPF (11 dígitos, dígitos verificadores certos: RN06)."""
        cpf = token.valor
        self._exigir(len(cpf) == 11, "CPF com 11 números", "RN06",
                     f"um CPF tem 11 números; este tem {len(cpf)}.", token)
        self._exigir(cpf_valido(cpf), "CPF com dígitos verificadores válidos",
                     "RN06", f"o CPF {self.s.exibir_cpf(cpf)} tem 11 "
                             "números, mas os dígitos verificadores não "
                             "conferem.", token)
        return cpf

    def _opcoes_unicas(self, opcoes, conflitos=CONFLITOS):
        """{nome: Opcao}. Opção repetida é erro (como declarar a mesma
        variável duas vezes); opções que se contradizem também."""
        vistas = {}
        for o in opcoes:
            self._exigir(o.nome not in vistas, f'Opção "{o.nome}" uma vez só',
                         "variável única",
                         f'a opção "{o.nome}" foi informada duas vezes (como '
                         "declarar a mesma variável duas vezes).", o)
            vistas[o.nome] = o
        for a, b in conflitos:
            if a in vistas and b in vistas:
                self._exigir(False, f'"{a}" e "{b}" juntos', "variável única",
                             f'"{a}" e "{b}" não combinam no mesmo comando.',
                             vistas[b])
        return vistas

    def _momento(self, opcoes):
        """A data e a hora do "as HORA" (hoje) ou "em DATA HORA"; None =
        agora."""
        if "as" in opcoes:
            h, m = opcoes["as"].valor.valor
            return self.agora.replace(hour=h, minute=m, second=0,
                                      microsecond=0)
        if "em" in opcoes:
            data, hora = opcoes["em"].valores
            h, m = hora.valor
            return datetime(data.valor.year, data.valor.month, data.valor.day,
                            h, m)
        return None

    def _usuario(self):
        return self.s.usuario_logado()

    def _so_admin(self, descricao, regra, mensagem, token):
        self._exigir(pode_gerenciar_desativacoes(self._usuario()), descricao,
                     regra, mensagem, token,
                     "peça a um administrador (o comando é dele).")

    def _texto_cpf(self, cpf):
        return self.s.exibir_cpf(cpf)

    # --------------------------------------------------------------
    # Entrada
    # --------------------------------------------------------------
    def _entrada(self, no):
        self._usuario()
        opcoes = self._opcoes_unicas(no.opcoes)
        cpf = self._cpf(no.cpf)
        pessoa = self.s.pessoa(cpf)
        tipo = no.tipo.valor if no.tipo else None
        nome = opcoes["nome"].valor.valor if "nome" in opcoes else None
        cel = opcoes["cel"].valor.valor if "cel" in opcoes else None
        if pessoa is None:
            faltam = [o for o, v in (("o tipo", tipo), ("o nome", nome),
                                     ("o celular", cel)) if not v]
            self._exigir(not faltam, "CPF novo traz tipo, nome e celular",
                         "RN01", "CPF não cadastrado: informe "
                         + ", ".join(faltam[:-1])
                         + (" e " if len(faltam) > 1 else "") + faltam[-1]
                         + "." if faltam else "", no.cpf,
                         "Ex.: " + EXEMPLO_NOVA.format(
                             cpf=self._texto_cpf(cpf)))
        else:
            self._anotar("Pessoa cadastrada", "RF08",
                         OK, pessoa["nome"], no.cpf)
            if tipo and tipo != pessoa["tipo"]:
                self._anotar("Tipo igual ao do cadastro", "aviso de tipo",
                             AVISO, f"o cadastro diz {pessoa['tipo']} e o "
                                    f"comando diz {tipo}: o programa "
                                    "pergunta antes de seguir.", no.tipo)
        p = pessoa or {}
        # a placa, como o formulário: digitada, "sem carro" (a pé) ou a do
        # cadastro (aí a pergunta "vai entrar de carro?", RN34), a não ser
        # que o carro dela já esteja no estacionamento (entra a pé)
        sugerida, placa = "", ""
        if "placa" in opcoes:
            placa = opcoes["placa"].valor.valor
        elif "sem carro" not in opcoes and p.get("placa"):
            if self.s.estadia_da_placa(p["placa"]) is not None:
                self._anotar("Carro do cadastro já no estacionamento",
                             "RN26", OK, f"o {formatar_placa(p['placa'])} "
                                         "já está lá: a entrada é a pé.")
            else:
                placa = sugerida = p["placa"]
        momento = self._momento(opcoes) or self.agora
        registro = normalizar(nome or p.get("nome", ""), cpf,
                              cel or p.get("celular", ""), placa,
                              tipo or p.get("tipo", ""),
                              momento.strftime(FORMATO), "")
        ok, msg = checar_desativacao(registro, self.s.desativacoes())
        pessoa_desativada = self.s.desativacao("cpf", cpf)
        if placa:
            self.s.desativacao("placa", placa)
        # o ^ vai no que está desativado: o CPF ou a placa digitada
        onde = (opcoes["placa"] if "placa" in opcoes and not pessoa_desativada
                else no.cpf)
        self._exigir(ok, "Pessoa e veículo ativos", "RN12",
                     self._uma_linha(msg), onde,
                     "a desativação vale até um administrador reativar.",
                     recusa=registro)
        dentro = self.s.visitas_abertas(cpf)
        if dentro:
            self._exigir(False, "Não está no campus", "RN05",
                         f"{dentro[0]['nome']} está no campus desde "
                         f"{self.s.quando(dentro[0]['entrada'])}. Um CPF não "
                         "pode ter duas entradas abertas.", no.cpf,
                         f"para dar a saída: saida {self._texto_cpf(cpf)}")
        self._anotar("Não está no campus", "RN05", OK, "", no.cpf)
        if "placa" in opcoes:
            estadia = self.s.estadia_da_placa(placa)
            self._exigir(estadia is None, "Carro fora do estacionamento",
                         "RN26",
                         f"o carro {formatar_placa(placa)} já está no "
                         f"estacionamento desde {self.s.quando(estadia['entrada'])}"
                         f" (responsável: {estadia['nome']})."
                         if estadia else "", opcoes["placa"],
                         "registre a saída dele pela placa ou entre a pé "
                         '("sem carro").')
        if "as" in opcoes or "em" in opcoes:
            quando = opcoes.get("as") or opcoes.get("em")
            self._exigir(momento <= self.agora, "Entrada não está no futuro",
                         "RN07", "a entrada não pode estar no futuro.",
                         quando)
        ok, msg = validar(registro, self.s.visitas(cpf), self.agora)
        self._exigir(ok, "Registro completo: campos e período (validar)",
                     "RN01, RN05, RN06, RN07", self._uma_linha(msg),
                     opcoes.get("em") or opcoes.get("as"))
        config = self.s.configuracao(registro["tipo"])
        excecoes = horarios.excecoes_do_registro(config, registro, self.agora)
        if excecoes:
            self._anotar("Horário da categoria e lançamento retroativo",
                         "RN17, RN20, RN24", AUTORIZACAO,
                         " ".join(excecoes.regras) + " Abre a autorização "
                         "do administrador.")
        else:
            self._anotar("Horário da categoria e lançamento retroativo",
                         "RN17, RN24", OK)
        if sugerida:
            self._anotar("Vai entrar de carro?", "RN34", PERGUNTA,
                         f"tem a placa {formatar_placa(sugerida)} no "
                         "cadastro: abre a mesma pergunta do formulário.")
        if registro["placa"]:
            self._carros_na_entrada(cpf, registro["placa"])
        confirmar = ""
        if pessoa and tipo and tipo != pessoa["tipo"]:
            confirmar = (f"O cadastro de {pessoa['nome']} diz {pessoa['tipo']} "
                         f"e o comando diz {tipo}.\nRegistrar como {tipo}?")
        return Plano("entrada", {"registro": registro, "sugerida": sugerida,
                                 "pessoa_id": p.get("id"),
                                 "confirmar_tipo": confirmar})

    def _carros_na_entrada(self, cpf, placa):
        """RN40 (outro carro da pessoa) e RN37 (lotação): a execução abre
        os mesmos diálogos do formulário."""
        outros = [e for e in self.s.estadias_do_cpf(cpf) if e["placa"] != placa]
        if outros:
            self._anotar("Outro carro da pessoa no estacionamento", "RN40",
                         PERGUNTA, ", ".join(formatar_placa(e["placa"])
                                             for e in outros)
                         + ": abre a pergunta do formulário.")
        ocupadas, vagas, bloquear = self.s.ocupacao()
        if esta_lotado(ocupadas, vagas):
            self._anotar("Estacionamento com vaga", "RN37",
                         AUTORIZACAO if bloquear else PERGUNTA,
                         regra_lotado(ocupadas, vagas))
        elif vagas:
            self._anotar("Estacionamento com vaga", "RN37", OK,
                         f"{ocupadas}/{vagas}")

    # --------------------------------------------------------------
    # Saída (e o implícito: só o CPF ou só a placa)
    # --------------------------------------------------------------
    def _saida(self, no):
        self._usuario()
        implicito = isinstance(no, ComandoImplicito)
        opcoes = {} if implicito else self._opcoes_unicas(
            no.opcoes, (("placa", "sem carro"),))
        if no.alvo.eh_placa:
            return self._saida_do_carro(no, opcoes)
        cpf = self._cpf(no.alvo.valor)
        abertas = self.s.visitas_abertas(cpf)
        if not abertas:
            return self._sem_visita_aberta(no, cpf, opcoes)
        self._anotar("Está no campus (entrada sem saída)", "RN03", OK,
                     f"{abertas[0]['nome']} desde "
                     f"{self.s.quando(abertas[0]['entrada'])}", no.alvo)
        momento = self._momento(opcoes)
        excecoes = horarios.Excecoes()
        if momento is not None:
            self._exigir(momento <= self.agora, "Saída não está no futuro",
                         "RN07", "a saída não pode estar no futuro.",
                         opcoes["as"])
            config = self.s.configuracao()
            for r in abertas:
                excecoes.juntar(horarios.retroativo(config, "Saída", momento,
                                                    self.agora, r["tipo"]))
        quando = momento or self.agora.replace(second=0, microsecond=0)
        for r in abertas:
            ok, msg = checar_saida(r, quando)
            self._exigir(ok, "Saída não é anterior à entrada", "RN04", msg,
                         opcoes.get("as"))
            excecoes.regras += horarios.excecoes_da_duracao(
                datetime.strptime(r["entrada"], FORMATO), quando)
        if excecoes:
            self._anotar("Retroativo e visita de até 24 h", "RN19, RN24",
                         AUTORIZACAO, " ".join(excecoes.regras)
                         + " Abre a autorização do administrador.")
        dados = {"registros": abertas, "momento": momento}
        carros = self.s.estadias_do_cpf(cpf)
        nome = abertas[0]["nome"]
        if "placa" in opcoes:
            dados.update(self._saida_com_a_placa(cpf, nome, abertas[0],
                                                 carros, opcoes["placa"]))
        elif "sem carro" in opcoes:
            placas = [e["placa"] for e in carros]
            dados.update(com_veiculo={}, a_pe={abertas[0]["id"]: placas})
            self._anotar("Sai a pé", "RN40", OK,
                         ("os carros ficam: " if len(placas) > 1 else
                          "o carro fica: " if placas else "sem carro")
                         + ", ".join(formatar_placa(p) for p in placas),
                         opcoes["sem carro"])
        elif len(carros) > 1:
            self._anotar("Com qual carro está saindo?", "RN40", PERGUNTA,
                         "dois carros no estacionamento: abre a pergunta do "
                         "formulário.")
        elif carros:
            self._anotar("Saiu com o veículo?", "RN25", PERGUNTA,
                         f"o {formatar_placa(carros[0]['placa'])} está no "
                         "estacionamento: abre a pergunta do formulário.")
        return Plano("saida", dados)

    def _saida_com_a_placa(self, cpf, nome, visita, carros, opcao):
        """saida CPF placa X: X é um carro dela (RN40) ou um que ela pode
        levar (RN35); senão, erro."""
        placa = opcao.valor.valor
        proprio = next((e for e in carros if e["placa"] == placa), None)
        if proprio is not None:
            self._anotar("O carro é dela e está no estacionamento", "RN40",
                         OK, formatar_placa(placa), opcao)
            return {"com_veiculo": {visita["id"]: proprio["id"]}}
        levavel = next((e for e in self.s.levaveis(cpf)
                        if e["placa"] == placa), None)
        if levavel is not None and not visita["placa"]:
            self._anotar("Autorizado a retirar o carro", "RN35", OK,
                         f"{formatar_placa(placa)} de {levavel['nome']}",
                         opcao)
            return {"com_veiculo": {visita["id"]: levavel["id"]},
                    "levados": {visita["id"]: levavel}}
        estadia = self.s.estadia_da_placa(placa)
        if estadia is None:
            self._exigir(False, "Carro no estacionamento", "RN25",
                         f"o carro {formatar_placa(placa)} não está no "
                         "estacionamento.", opcao)
        self._exigir(False, "O carro é dela ou ela pode retirá-lo",
                     "RN32, RN35",
                     f"o carro {formatar_placa(placa)} é de {estadia['nome']}"
                     f" e {nome.split()[0]} não está autorizado(a) a "
                     "retirá-lo. O veículo só sai com o dono.", opcao,
                     "saia sem a placa; o carro sai com o dono.")
        return {}

    def _sem_visita_aberta(self, no, cpf, opcoes):
        """Ninguém no campus com esse CPF: o carro dele pode ter ficado
        (sai só com a senha, RN32); senão é erro (RN03)."""
        carros = self.s.estadias_do_cpf(cpf)
        if carros and not opcoes:
            self._anotar("Pessoa fora do campus, carro no estacionamento",
                         "RN32", AUTORIZACAO,
                         f"o {formatar_placa(carros[0]['placa'])} só sai sem "
                         "o dono com a senha de um administrador.", no.alvo)
            return Plano("carro_sem_dono", {"estadia": carros[0]})
        pessoa = self.s.pessoa(cpf)
        if pessoa is None:
            mensagem = ("ninguém no campus nem veículo no estacionamento com "
                        f"o CPF {self._texto_cpf(cpf)}.")
        else:
            saiu = self.s.ultima_saida(cpf)
            mensagem = (f"{pessoa['nome']} não está no campus"
                        + (f" (saiu {self._quando_saiu(saiu)})" if saiu
                           else "") + ". Saída sem entrada aberta.")
        self._exigir(False, "Está no campus (entrada sem saída)", "RN03",
                     mensagem, no.alvo)

    def _quando_saiu(self, saida):
        hoje = self.agora.strftime("%d/%m/%Y")
        return (f"hoje às {saida[-5:]}" if saida.startswith(hoje)
                else f"em {saida}")

    def _saida_do_carro(self, no, opcoes):
        """Pela placa só sai o carro (RN27). Dono no campus: pergunta se
        saiu junto; fora: a senha do administrador (RN32) ou alguém da
        lista leva (RN35)."""
        for o in opcoes.values():
            self._exigir(False, "Opções só na saída pelo CPF", "RN27",
                         "pela placa só sai o carro: as opções valem na "
                         "saída pelo CPF.", o)
        placa = no.alvo.valor.valor
        estadia = self.s.estadia_da_placa(placa)
        self._exigir(estadia is not None, "Carro no estacionamento", "RN27",
                     f"o carro {formatar_placa(placa)} não está no "
                     "estacionamento. Pela placa só sai o carro.", no.alvo,
                     "para a saída de uma pessoa, digite o CPF dela.")
        if estadia["responsavel_dentro"]:
            self._anotar("Saiu junto com o carro?", "RN32", PERGUNTA,
                         f"{estadia['nome']} está no campus: abre a pergunta "
                         "do formulário.")
        else:
            self._anotar("O veículo só sai com o dono", "RN32, RN35",
                         AUTORIZACAO, f"{estadia['nome']} está fora do "
                                      "campus: alguém da lista leva, ou só "
                                      "com a senha de um administrador.")
        return Plano("saida_carro", {"estadia": estadia})

    # --------------------------------------------------------------
    # CRUD da pessoa
    # --------------------------------------------------------------
    def _cadastrar(self, no):
        self._usuario()
        cpf = self._cpf(no.cpf)
        existente = self.s.pessoa(cpf)
        self._exigir(existente is None, "CPF ainda não cadastrado", "RN41",
                     f"este CPF já é de {existente['nome']}: nada foi "
                     "cadastrado." if existente else "", no.cpf,
                     f"para mudar os dados: editar {self._texto_cpf(cpf)} "
                     "cel ...")
        valores = {o.nome: o.valor.valor for o in no.opcoes}
        placas = self._placas(
            [o for o in no.opcoes if o.nome == "placa"], [])
        dados = normalizar(valores.get("nome", ""), cpf,
                           valores.get("cel", ""), placas[0] if placas else "",
                           no.tipo.valor, "", "")
        ok, msg = validar_campos(dados)
        self._exigir(ok, "Nome, celular e placa válidos (validar_campos)",
                     "RN01, RN06, RN33", self._uma_linha(msg))
        dados["placas"] = placas
        desativada = self.s.desativacao("cpf", cpf)
        confirmar = ""
        if desativada:
            self._anotar("CPF ativo", "RN12", AVISO,
                         f"este CPF está desativado: {desativada['motivo']}. "
                         "Pode cadastrar, mas a entrada continua recusada.")
            confirmar = (f"Este CPF está desativado: {desativada['motivo']}"
                         "\n\nCadastrar mesmo assim? A pessoa continua "
                         "desativada e a entrada continua recusada.")
        return Plano("cadastrar", {"dados": dados, "confirmar": confirmar})

    def _placas(self, incluir, tirar, atuais=()):
        """RN47: a lista de carros depois do comando (as atuais, menos as
        tiradas, mais as incluídas), conferida como no formulário."""
        atuais = list(atuais)
        for o in tirar:
            placa = o.valor.valor
            self._exigir(placa not in [i.valor.valor for i in incluir],
                         '"placa" e "sem placa" juntos', "variável única",
                         f"o carro {formatar_placa(placa)} foi incluído e "
                         "tirado no mesmo comando.", o)
            self._exigir(placa in atuais, "Placa no cadastro", "RN47",
                         f"o carro {formatar_placa(placa)} não está no "
                         "cadastro: não há o que tirar.", o)
        tiradas = {o.valor.valor for o in tirar}
        lista = [p for p in atuais if p not in tiradas]
        lista += [o.valor.valor for o in incluir]
        ok, msg, placas = validar_placas(
            lista, max(MAXIMO_PLACAS_PESSOA, len(atuais)))
        self._exigir(ok, f"Até {MAXIMO_PLACAS_PESSOA} carros, cada placa "
                         "válida", "RN47", self._uma_linha(msg),
                     (incluir or tirar or [None])[-1])
        return placas

    def _editar(self, no):
        self._usuario()
        carros = [o for o in no.campos if o.nome in ("placa", "sem placa")]
        campos = self._opcoes_unicas(
            [o for o in no.campos if o not in carros], ())
        cpf = self._cpf(no.cpf)
        pessoa = self.s.pessoa(cpf)
        self._exigir(pessoa is not None, "Pessoa cadastrada", "RF28",
                     f"o CPF {self._texto_cpf(cpf)} não está cadastrado.",
                     no.cpf, 'para cadastrar: cadastrar CPF tipo nome "..." '
                             "cel ...")
        novo = {k: pessoa[k] for k in ("nome", "celular", "tipo")}
        chaves = {"nome": "nome", "cel": "celular", "tipo": "tipo"}
        for nome, opcao in campos.items():
            novo[chaves[nome]] = opcao.valor.valor
        placas = self._placas(
            [o for o in carros if o.nome == "placa"],
            [o for o in carros if o.nome == "sem placa"], pessoa["placas"])
        dados = normalizar(novo["nome"], cpf, novo["celular"],
                           placas[0] if placas else "", novo["tipo"], "", "")
        mudou = [rotulo for chave, rotulo in (
            ("nome", "nome"), ("celular", "celular"), ("tipo", "tipo"))
            if dados[chave] != pessoa[chave]]
        if placas != pessoa["placas"]:
            mudou.append("carros")
        dados["placas"] = placas
        self._exigir(bool(mudou), "Algo muda no cadastro", "RF28",
                     f"o cadastro de {pessoa['nome']} já tem esses dados: "
                     "nada muda.")
        ok, msg = validar_campos(dados)
        self._exigir(ok, "Nome, celular e placa válidos (validar_campos)",
                     "RN01, RN06, RN33", self._uma_linha(msg))
        return Plano("editar", {"pessoa": pessoa, "dados": dados,
                                "mudou": mudou})

    def _excluir(self, no):
        usuario = self._usuario()
        self._exigir(eh_admin(usuario), "Comando do administrador",
                     "RN02, RN42", "somente o administrador exclui o "
                                   "cadastro de pessoas.", no.comando,
                     "peça a um administrador (o comando é dele).")
        cpf = self._cpf(no.cpf)
        pessoa = self.s.pessoa(cpf)
        self._exigir(pessoa is not None, "Pessoa cadastrada", "RN42",
                     f"o CPF {self._texto_cpf(cpf)} não está cadastrado.",
                     no.cpf)
        ok, msg = pode_excluir_pessoa(usuario, pessoa["visitas"])
        self._exigir(ok, "Nunca teve visita", "RN42", self._uma_linha(msg),
                     no.cpf)
        return Plano("excluir", {"pessoa": pessoa})

    def _alvo_da_desativacao(self, alvo):
        if alvo.eh_placa:
            return "placa", alvo.valor.valor
        return "cpf", self._cpf(alvo.valor)

    def _desativar(self, no):
        self._so_admin("Comando do administrador", "RN02, RN12",
                       "só o administrador desativa pessoas e veículos.",
                       no.comando)
        tipo, valor = self._alvo_da_desativacao(no.alvo)
        motivo = " ".join(no.motivo.valor.valor.split())
        self.s.desativacao(tipo, valor)
        ok, msg = validar_desativacao(tipo, valor, motivo,
                                      self.s.desativacoes())
        self._exigir(ok, "Motivo e alvo válidos, ainda ativo",
                     "RN12, RN33", self._uma_linha(msg), no.motivo)
        nome = ""
        if tipo == "cpf":
            pessoa = self.s.pessoa(valor)
            nome = pessoa["nome"] if pessoa else ""
            if self.s.visitas_abertas(valor):
                self._anotar("Pessoa no campus agora", "RN12", AVISO,
                             "a visita aberta continua: a desativação vale "
                             "para as próximas entradas.")
        return Plano("desativar", {"tipo": tipo, "valor": valor,
                                   "motivo": motivo, "nome": nome})

    def _reativar(self, no):
        self._so_admin("Comando do administrador", "RN02, RN12",
                       "só o administrador reativa pessoas e veículos.",
                       no.comando)
        tipo, valor = self._alvo_da_desativacao(no.alvo)
        desativacao = self.s.desativacao(tipo, valor)
        rotulo = ("o CPF " + self._texto_cpf(valor) if tipo == "cpf"
                  else "o veículo " + formatar_placa(valor))
        self._exigir(desativacao is not None, "Está desativado(a)", "RN12",
                     f"{rotulo} não está desativado(a).", no.alvo)
        return Plano("reativar", {"desativacao": desativacao})

    # --------------------------------------------------------------
    # Consultas
    # --------------------------------------------------------------
    def _situacao(self, no):
        self._usuario()
        if no.alvo.eh_placa:
            placa = no.alvo.valor.valor
            return Plano("situacao", {
                "placa": placa, "estadia": self.s.estadia_da_placa(placa),
                "desativacao": self.s.desativacao("placa", placa)})
        cpf = self._cpf(no.alvo.valor)
        return Plano("situacao", {
            "cpf": cpf, "pessoa": self.s.pessoa(cpf),
            "abertas": self.s.visitas_abertas(cpf),
            "carros": self.s.estadias_do_cpf(cpf),
            "desativacao": self.s.desativacao("cpf", cpf),
            "ultima_saida": self.s.ultima_saida(cpf)})

    def _dentro(self, no):
        self._usuario()
        return Plano("dentro", {"tipo": no.tipo.valor if no.tipo else None})

    def _buscar(self, no):
        usuario = self._usuario()
        termo = no.termo
        if termo.tipo in ("CPF", "NUMERO") and len(termo.valor) == 11:
            self._cpf(termo)
        inicio = fim = None
        p = no.periodo
        if p is not None:
            hoje = self.agora.date()
            if p.inicio is None:                       # hoje, semana...
                dias = PERIODOS_EM_DIAS[p.palavra.valor]
                fim = hoje - timedelta(days=1) if p.palavra.valor == "ontem" \
                    else hoje
                inicio = fim - timedelta(days=0 if dias <= 1 else dias)
            else:
                inicio = p.inicio.valor
                fim = p.fim.valor if p.fim is not None else hoje
                self._exigir(inicio <= fim, "Período em ordem", "período",
                             "o período termina antes de começar.", p)
            self._anotar("Período", "busca", OK,
                         f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}", p)
        # a palavra vai como foi digitada (o banco compara com acento)
        texto = termo.lexema if termo.tipo == "PALAVRA" else termo.valor
        if not eh_admin(usuario) and termo.tipo == "NUMERO" \
                and len(termo.valor) != 11:
            self._anotar("CPF só pelos 11 números", "RN30", AVISO,
                         "para o porteiro, o CPF só é encontrado pelos 11 "
                         "números.", termo)
        return Plano("buscar", {"texto": texto, "termo_tipo": termo.tipo,
                                "tipo": no.tipo.valor if no.tipo else None,
                                "inicio": inicio, "fim": fim})

    def _pendentes(self, no):
        self._usuario()
        return Plano("pendentes", {})

    def _ajuda(self, no):
        return Plano("ajuda", {"sobre": no.sobre.valor if no.sobre else None})

    # --------------------------------------------------------------
    def analisar(self, arvore):
        """O Plano do comando, ou ErroDeAnalise (Semântico). As checagens
        feitas ficam em self.checagens (também quando para no erro)."""
        acoes = {ComandoEntrada: self._entrada, ComandoSaida: self._saida,
                 ComandoImplicito: self._saida,
                 ComandoCadastrar: self._cadastrar,
                 ComandoEditar: self._editar, ComandoExcluir: self._excluir,
                 ComandoDesativar: self._desativar,
                 ComandoReativar: self._reativar,
                 ComandoSituacao: self._situacao,
                 ComandoDentro: self._dentro, ComandoBuscar: self._buscar,
                 ComandoPendentes: self._pendentes, ComandoAjuda: self._ajuda}
        return acoes[type(arvore)](arvore)


def palavra_do_tipo(tipo):
    """'Prestador de serviço' -> 'prestador' (para escrever um comando)."""
    return PALAVRA_DO_TIPO.get(tipo, tipo.lower())
