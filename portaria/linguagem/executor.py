"""
EXECUÇÃO: o plano do semântico vira ação, pelos MESMOS caminhos do
formulário.

    entrada        AbaCadastro.registrar_entrada (o caminho único da
                   entrada: o formulário também passa por ele) -> Banco.inserir
    saida          AbaCadastro.dar_saida (botão, duplo clique e a Saída
                   rápida usam o mesmo) -> Banco.registrar_saidas
    saida_carro    AbaCadastro.saida_do_carro (a placa na Saída rápida)
    cadastrar...   os mesmos métodos do Banco que os diálogos de Pessoas
                   chamam (cadastrar_pessoa, atualizar_pessoa,
                   excluir_pessoa, desativar, reativar)
    consultas      só leitura (situacao, dentro, buscar, pendentes, ajuda)

Quando falta algo que o formulário perguntaria, o fluxo da tela abre o
MESMO diálogo ("Vai entrar de carro?", "Com qual carro está saindo?", a
autorização do administrador) e conclui. O banco confere tudo de novo.

A `porta` é a página Entrada e saída (AbaCadastro); `app` é a janela
principal (o contrato público de interface.py: banco, usuario, autor,
relogio, tentar, perguntar, exibir_cpf).
"""

from dataclasses import dataclass, field
from datetime import datetime

from .. import horarios, mensagens
from ..usuarios import eh_admin
from ..validacao import (FORMATO, formatar_celular, formatar_desativacao,
                         formatar_placa)
from ..validacao import DESATIVADO, O_QUE
from .gramatica import EXEMPLOS, FAZ, SO_ADMIN, regras_de
from .lexico import COMANDOS

SUCESSO, INFO, AVISO, ERRO, CANCELADO = ("sucesso", "info", "aviso", "erro",
                                         "cancelado")
MOSTRAR_NO_CONSOLE = 8           # linhas de uma consulta (o resto: "e mais")
LIMITE_BUSCA = 200
NADA_GRAVADO = "Nada foi gravado."


@dataclass
class Resposta:
    nivel: str                     # sucesso, info, aviso, erro, cancelado
    texto: str                     # a linha de resposta embaixo do campo
    linhas: list = field(default_factory=list)   # detalhes (consultas)


def _primeiro(nome):
    return nome.split()[0] if nome else "?"


def _cortar(linhas, total=None):
    """No máximo MOSTRAR_NO_CONSOLE linhas, com "e mais N"."""
    total = len(linhas) if total is None else total
    if total <= MOSTRAR_NO_CONSOLE:
        return linhas
    return linhas[:MOSTRAR_NO_CONSOLE] + [
        f"… e mais {total - MOSTRAR_NO_CONSOLE}"]


class Executor:
    def __init__(self, app, porta):
        self.app, self.porta = app, porta

    def executar(self, plano):
        return getattr(self, "_" + plano.acao)(**plano.dados)

    def _quando(self, momento):
        hoje = self.app.relogio().strftime("%d/%m/%Y")
        return momento[-5:] if momento.startswith(hoje) else momento

    def _depois_de_mudar(self):
        """Relê o Movimento, os contadores e a página Pessoas (se aberta)."""
        self.app.atualizar_tabela()
        if "tela_pessoas" in self.app.__dict__:
            self.app.tela_pessoas.atualizar()

    def _resultado_da_tela(self, ok):
        """Depois de um fluxo da tela: o aviso que ela mostrou ou nada."""
        if ok:
            return Resposta(SUCESSO, self.porta.ultimo_aviso or "Feito.")
        return Resposta(CANCELADO, NADA_GRAVADO)

    # --------------------------------------------------------------
    # Entrada e saída: os fluxos da página Entrada e saída
    # --------------------------------------------------------------
    def _entrada(self, registro, sugerida, pessoa_id, confirmar_tipo):
        if confirmar_tipo and not self.app.perguntar(
                mensagens.confirmar, "Tipo diferente do cadastro",
                confirmar_tipo):
            return Resposta(CANCELADO, "Entrada não registrada: o tipo do "
                                       "comando é diferente do cadastro.")
        outro_carro = []
        texto = self.porta.registrar_entrada(
            dict(registro), sugerida=sugerida, pessoa_id=pessoa_id,
            ao_outro_carro=lambda: outro_carro.append(True))
        if texto:
            return Resposta(SUCESSO, texto)
        if outro_carro:
            return Resposta(INFO, "Escreva a placa do outro carro: entrada "
                                  f"{self.app.exibir_cpf(registro['cpf'])} "
                                  "placa ABC1D23")
        return Resposta(CANCELADO, NADA_GRAVADO)

    def _saida(self, registros, momento, com_veiculo=None, a_pe=None,
               levados=None):
        self.porta.ultimo_aviso = ""
        ok = self.porta.dar_saida(registros, com_veiculo=com_veiculo,
                                  levados=levados, momento=momento,
                                  a_pe=a_pe)
        return self._resultado_da_tela(ok)

    def _saida_carro(self, estadia):
        self.porta.ultimo_aviso = ""
        self.app.recarregar_registros()          # (a tela usa o movimento)
        return self._resultado_da_tela(self.porta.saida_do_carro(estadia))

    def _carro_sem_dono(self, estadia):
        self.porta.ultimo_aviso = ""
        return self._resultado_da_tela(self.porta.sair_so_o_carro(estadia))

    # --------------------------------------------------------------
    # CRUD da pessoa (os mesmos métodos do Banco que Pessoas usa)
    # --------------------------------------------------------------
    def _cadastrar(self, dados, confirmar):
        app = self.app
        if confirmar and not app.perguntar(mensagens.confirmar,
                                           "CPF desativado", confirmar):
            return Resposta(CANCELADO, NADA_GRAVADO)
        ok, _ = app.tentar(app.banco.cadastrar_pessoa, dados["cpf"],
                           dados["nome"], dados["celular"], dados["placa"],
                           dados["tipo"], app.autor)
        if not ok:
            return Resposta(ERRO, NADA_GRAVADO)
        self._depois_de_mudar()
        return Resposta(SUCESSO, f"Pessoa cadastrada: {dados['nome']} "
                                 f"({dados['tipo']}). A entrada não foi "
                                 "registrada.")

    def _editar(self, pessoa, dados, mudou):
        app = self.app
        ok, _ = app.tentar(app.banco.atualizar_pessoa, pessoa["id"],
                           dados["nome"], dados["celular"], dados["placa"],
                           dados["tipo"], autor=app.autor)
        if not ok:
            return Resposta(ERRO, NADA_GRAVADO)
        self._depois_de_mudar()
        return Resposta(SUCESSO, f"Alterações salvas: {dados['nome']} ("
                                 + ", ".join(mudou) + ").")

    def _excluir(self, pessoa):
        app = self.app
        if not app.perguntar(
                mensagens.confirmar, "Excluir pessoa",
                f"Excluir o cadastro de {pessoa['nome']} (CPF "
                f"{app.exibir_cpf(pessoa['cpf'])})?\nEla nunca teve visita. "
                "A exclusão não pode ser desfeita e fica no histórico."):
            return Resposta(CANCELADO, NADA_GRAVADO)
        ok, _ = app.tentar(app.banco.excluir_pessoa, pessoa["id"], app.autor)
        if not ok:
            return Resposta(ERRO, NADA_GRAVADO)
        self._depois_de_mudar()
        return Resposta(SUCESSO, f"{pessoa['nome']}: cadastro excluído.")

    def _desativar(self, tipo, valor, motivo, nome):
        app = self.app
        ok, _ = app.tentar(app.banco.desativar, tipo, valor, motivo, app.autor)
        if not ok:
            return Resposta(ERRO, NADA_GRAVADO)
        self._depois_de_mudar()
        rotulo = (f"{nome or 'CPF'} ({app.exibir_cpf(valor)})" if tipo == "cpf"
                  else formatar_desativacao(tipo, valor))
        texto = f"{O_QUE[tipo]} {DESATIVADO[tipo]}: {rotulo}. Motivo: {motivo}"
        dentro = [r for r in app.registros if not r["saida"] and (
            r["cpf"] == valor or r.get("placa") == valor)]
        if dentro:
            texto += (". No campus agora: " + ", ".join(r["nome"]
                                                       for r in dentro)
                      + " (vale para as próximas entradas)")
        return Resposta(SUCESSO, texto + ".")

    def _reativar(self, desativacao):
        app = self.app
        tipo, valor = desativacao["tipo"], desativacao["valor"]
        quem = desativacao["nome"] or "(sem cadastro)"
        pergunta = (f"Reativar {quem} (CPF {app.exibir_cpf(valor)})?"
                    if tipo == "cpf" else
                    f"Reativar o veículo {formatar_desativacao(tipo, valor)}?")
        if not app.perguntar(mensagens.confirmar, "Reativar",
                             pergunta + "\nA entrada volta a ser permitida. "
                                        "A reativação fica no histórico."):
            return Resposta(CANCELADO, NADA_GRAVADO)
        ok, _ = app.tentar(app.banco.reativar, desativacao["id"], app.autor)
        if not ok:
            return Resposta(ERRO, NADA_GRAVADO)
        self._depois_de_mudar()
        rotulo = (app.exibir_cpf(valor) if tipo == "cpf"
                  else formatar_desativacao(tipo, valor))
        return Resposta(SUCESSO, f"{'Pessoa reativada' if tipo == 'cpf' else 'Veículo reativado'}"
                                 f": {rotulo}. A entrada volta a ser "
                                 "permitida.")

    # --------------------------------------------------------------
    # Consultas (só leitura)
    # --------------------------------------------------------------
    def _situacao(self, **dados):
        if "placa" in dados:
            return situacao_do_veiculo(dados, self._quando)
        return situacao_da_pessoa(dados, self.app.exibir_cpf, self._quando)

    def _dentro(self, tipo):
        self.app.recarregar_registros()
        return quem_esta_dentro(self.app.registros, tipo,
                                self.app.exibir_cpf, self._quando)

    def _buscar(self, texto, termo_tipo, tipo, inicio, fim):
        app = self.app
        ok, registros = app.tentar(app.banco.buscar_registros, texto,
                                   LIMITE_BUSCA,
                                   so_cpf_completo=not eh_admin(app.usuario))
        if not ok:
            return Resposta(ERRO, "A busca não foi feita.")
        return resultado_da_busca(registros, texto, tipo, inicio, fim,
                                  app.exibir_cpf)

    def _pendentes(self):
        app = self.app
        app.recarregar_registros()
        ok, config = app.tentar(app.banco.ler_configuracao)
        ok2, estadias = app.tentar(app.banco.listar_estacionamento)
        if not (ok and ok2):
            return Resposta(ERRO, "A consulta não foi feita.")
        return pendencias(config, app.registros, estadias, app.relogio(),
                          self._quando)

    def _ajuda(self, sobre):
        return ajuda(sobre, eh_admin(self.app.usuario))


# ------------------------------------------------------------------
# As respostas das consultas (funções puras: testadas sem a tela)
# ------------------------------------------------------------------
def situacao_da_pessoa(d, exibir_cpf, quando):
    pessoa, cpf = d["pessoa"], d["cpf"]
    desativacao = d["desativacao"]
    if pessoa is None:
        texto = f"Nenhum cadastro com o CPF {exibir_cpf(cpf)}."
        if desativacao:
            texto += f" CPF desativado: {desativacao['motivo']}."
        return Resposta(INFO, texto)
    linhas = [f"CPF {exibir_cpf(cpf)} · {pessoa['tipo']} · celular "
              f"{formatar_celular(pessoa['celular'])}"]
    if d["abertas"]:
        texto = (f"{pessoa['nome']} está no campus desde "
                 f"{quando(d['abertas'][0]['entrada'])}")
    elif d["ultima_saida"]:
        texto = (f"{pessoa['nome']} está fora do campus (última saída "
                 f"{quando(d['ultima_saida'])})")
    else:
        texto = f"{pessoa['nome']} está fora do campus (nunca veio)"
    for e in d["carros"]:
        linhas.append(f"Carro {formatar_placa(e['placa'])} no estacionamento "
                      f"desde {quando(e['entrada'])}")
    if pessoa["placa"] and not d["carros"]:
        linhas.append(f"Placa no cadastro: {formatar_placa(pessoa['placa'])}")
    linhas.append(f"{pessoa['visitas']} visita(s) no histórico")
    if desativacao:
        linhas.append(f"DESATIVADA desde {desativacao['criado_em'][:10]}: "
                      f"{desativacao['motivo']}")
        texto += " · desativada"
    return Resposta(AVISO if desativacao else INFO, texto + ".", linhas)


def situacao_do_veiculo(d, quando):
    placa, estadia = formatar_placa(d["placa"]), d["estadia"]
    desativacao = d["desativacao"]
    if estadia is None:
        texto = f"O carro {placa} não está no estacionamento"
    else:
        dono = ("o dono está no campus" if estadia["responsavel_dentro"]
                else "o dono está FORA do campus")
        texto = (f"O carro {placa} está no estacionamento desde "
                 f"{quando(estadia['entrada'])} ({estadia['nome']}; {dono})")
    linhas = []
    if desativacao:
        linhas.append(f"DESATIVADO desde {desativacao['criado_em'][:10]}: "
                      f"{desativacao['motivo']}")
        texto += " · desativado"
    return Resposta(AVISO if desativacao else INFO, texto + ".", linhas)


def quem_esta_dentro(registros, tipo, exibir_cpf, quando):
    abertos = [r for r in registros if not r["saida"]
               and (tipo is None or r["tipo"] == tipo)]
    abertos.sort(key=lambda r: datetime.strptime(r["entrada"], FORMATO))
    filtro = f" ({tipo})" if tipo else ""
    if not abertos:
        return Resposta(INFO, f"Ninguém no campus agora{filtro}.")
    linhas = [f"{r['nome']} · {r['tipo']} · {exibir_cpf(r['cpf'])} · desde "
              f"{quando(r['entrada'])}"
              + (f" · {formatar_placa(r['placa'])}" if r["placa"] else "")
              for r in abertos]
    n = len(abertos)
    return Resposta(INFO, f"{n} {'pessoa' if n == 1 else 'pessoas'} no "
                          f"campus agora{filtro}.", _cortar(linhas))


def resultado_da_busca(registros, texto, tipo, inicio, fim, exibir_cpf):
    achados = []
    for r in registros:
        if tipo and r["tipo"] != tipo:
            continue
        dia = datetime.strptime(r["entrada"], FORMATO).date()
        if inicio is not None and not inicio <= dia <= fim:
            continue
        achados.append(r)
    if not achados:
        return Resposta(INFO, "Nada encontrado no histórico.")
    linhas = [f"{r['entrada']} · {r['nome']} · {r['tipo']} · "
              f"{exibir_cpf(r['cpf'])}"
              + (f" · {formatar_placa(r['placa'])}" if r["placa"] else "")
              + (f" · saída {r['saida'][-5:]}" if r["saida"] else
                 " · no campus")
              for r in achados]
    n = len(achados)
    limite = f" (os {LIMITE_BUSCA} mais recentes)" if len(registros) >= \
        LIMITE_BUSCA else ""
    return Resposta(INFO, f"{n} {'visita encontrada' if n == 1 else 'visitas encontradas'}"
                          f" no histórico{limite}.", _cortar(linhas))


def pendencias(config, registros, estadias, agora, quando):
    """Saídas pendentes, tempo excedido e carros com o dono fora do campus
    (as mesmas situações das bolinhas do Movimento, horarios.situacao)."""
    linhas, contagem = [], {}
    for r in registros:
        if r["saida"]:
            continue
        situacao = horarios.situacao(config, r, agora)
        if situacao in (horarios.SAIDA_PENDENTE, horarios.TEMPO_EXCEDIDO):
            contagem[situacao] = contagem.get(situacao, 0) + 1
            linhas.append(f"{situacao}: {r['nome']} ({r['tipo']}, entrada "
                          f"{quando(r['entrada'])})")
    for e in estadias:
        situacao = horarios.situacao_veiculo(config, e, agora)
        if situacao in (horarios.DONO_FORA, horarios.VEICULO_PENDENTE):
            contagem[situacao] = contagem.get(situacao, 0) + 1
            linhas.append(f"{situacao}: carro {formatar_placa(e['placa'])} "
                          f"de {e['nome']} (desde {quando(e['entrada'])})")
    if not linhas:
        return Resposta(INFO, "Nenhuma pendência: ninguém com tempo "
                              "excedido, saída pendente ou carro sem o dono.")
    resumo = ", ".join(f"{n} {s.lower()}" for s, n in contagem.items())
    return Resposta(AVISO, f"Pendências: {resumo}.", _cortar(linhas))


def ajuda(sobre=None, admin=True):
    """O texto do `ajuda`, gerado da gramática (gramatica.py)."""
    if sobre is None:
        linhas = [f"{c:<10} {EXEMPLOS[c].split(' · ')[0]}"
                  + ("   (admin)" if c in SO_ADMIN else "")
                  for c in COMANDOS if admin or c not in SO_ADMIN]
        linhas.append("Só o CPF ou só a placa = saida. Tab completa; "
                      "\"ajuda entrada\" mostra a regra.")
        return Resposta(INFO, f"{len(linhas) - 1} comandos. Exemplos:",
                        linhas)
    linhas = regras_de(sobre)
    if sobre in ("entrada", "saida"):
        opcao = "opcao_ent" if sobre == "entrada" else "opcao_sai"
        linhas += regras_de(opcao)
    linhas += ["Ex.: " + e for e in EXEMPLOS[sobre].split(" · ")]
    return Resposta(INFO, f"{sobre}: {FAZ[sobre]}.", linhas)
