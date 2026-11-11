"""
Páginas para imprimir (versão 3.2): a autorização de entrada e o relatório
do período. O programa monta um HTML simples, grava num arquivo temporário
e abre no navegador, que imprime ou salva em PDF. Nada de biblioteca
externa. O arquivo é apagado pouco depois (e ao fechar o programa).
"""

import atexit
import html
import os
import tempfile
import webbrowser

SEGUNDOS_ATE_APAGAR = 120
_temporarios = []

ESTILO = """
body { font-family: "Segoe UI", Arial, sans-serif; color: #1a2130;
       max-width: 820px; margin: 32px auto; padding: 0 24px; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 15px; margin: 24px 0 8px; }
.apoio { color: #475467; font-size: 13px; margin: 0 0 20px; }
.barra { height: 8px; margin: 0 0 20px; background: repeating-linear-gradient(
         90deg, #d9001b 0 34px, #ffffff 34px 68px); border: 1px solid #d9001b; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #e3e6eb; }
th { color: #475467; font-weight: 600; }
.dados td:first-child { color: #475467; width: 190px; }
.numeros { display: flex; gap: 12px; margin: 0 0 8px; }
.numero { border: 1px solid #e3e6eb; border-radius: 8px; padding: 8px 14px; }
.numero b { display: block; font-size: 20px; }
.assinaturas { display: flex; gap: 40px; margin-top: 56px; }
.assinaturas div { flex: 1; border-top: 1px solid #1a2130; padding-top: 6px;
                   font-size: 12px; color: #475467; }
.rodape { color: #5b6578; font-size: 12px; margin-top: 28px; }
@media print { body { margin: 0 auto; } .nao-imprimir { display: none; } }
"""


def e(texto):
    """Texto seguro para o HTML (o que foi digitado nunca vira marcação)."""
    return html.escape(str(texto if texto not in (None, "") else "—"))


def pagina(titulo, corpo):
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>{e(titulo)}</title><style>{ESTILO}</style></head>
<body>
<p class="nao-imprimir apoio">Use Ctrl+P para imprimir ou salvar em PDF.</p>
{corpo}
</body></html>"""


def autorizacao_html(a, cpf_na_tela, emitida_por, momento):
    """A autorização de entrada (desafio extra do A3: emissão de
    autorização). `a` é o dicionário de Banco.buscar_autorizacao."""
    periodo = (a["valida_de"] if a["valida_de"] == a["valida_ate"]
               else f"de {a['valida_de']} a {a['valida_ate']}")
    linhas = "".join(f"<tr><td>{e(rotulo)}</td><td>{e(valor)}</td></tr>"
                     for rotulo, valor in (
                         ("Nome", a["nome"]), ("CPF", cpf_na_tela),
                         ("Empresa", a["empresa"]), ("Motivo", a["motivo"]),
                         ("Autorizado por", a["anfitriao"]),
                         ("Válida", periodo),
                         ("Situação", a["situacao"])))
    corpo = f"""
<div class="barra"></div>
<h1>Autorização de entrada nº {a['id']:03d}</h1>
<p class="apoio">Portaria da Universidade</p>
<table class="dados">{linhas}</table>
<div class="assinaturas"><div>Quem autorizou</div><div>Portaria</div></div>
<p class="rodape">Emitida por {e(emitida_por)} em
{momento.strftime('%d/%m/%Y %H:%M')}. Apresente este documento e um documento
com foto na portaria. A entrada segue as regras de horário do campus.</p>"""
    return pagina(f"Autorização de entrada nº {a['id']:03d}", corpo)


def relatorio_html(registros, desde, ate, cpf_na_tela, emitido_por, momento):
    """Relatório do movimento de um período, para imprimir. `cpf_na_tela`
    formata o CPF como a tela de quem emite mostra (mascarado ou não)."""
    dentro = sum(1 for r in registros if not r["saida"])
    com_carro = sum(1 for r in registros if r.get("placa"))
    por_tipo = {}
    for r in registros:
        por_tipo[r["tipo"]] = por_tipo.get(r["tipo"], 0) + 1
    numeros = "".join(f'<div class="numero"><b>{n}</b>{e(rotulo)}</div>'
                      for rotulo, n in (("visitas", len(registros)),
                                        ("ainda dentro", dentro),
                                        ("com veículo", com_carro)))
    tipos = "".join(f"<tr><td>{e(t)}</td><td>{n}</td></tr>"
                    for t, n in sorted(por_tipo.items(),
                                       key=lambda par: (-par[1], par[0])))
    linhas = "".join(
        "<tr>" + "".join(f"<td>{e(v)}</td>" for v in (
            f"{r['id']:03d}", r["nome"], cpf_na_tela(r["cpf"]), r["tipo"],
            r.get("empresa"), r.get("placa"), r["entrada"], r["saida"]))
        + "</tr>" for r in registros)
    periodo = (desde.strftime("%d/%m/%Y") if desde == ate else
               f"{desde.strftime('%d/%m/%Y')} a {ate.strftime('%d/%m/%Y')}")
    corpo = f"""
<div class="barra"></div>
<h1>Relatório de movimento</h1>
<p class="apoio">Portaria da Universidade · período: {e(periodo)}</p>
<div class="numeros">{numeros}</div>
<h2>Por tipo de acesso</h2>
<table><tr><th>Tipo</th><th>Visitas</th></tr>{tipos or
    '<tr><td colspan="2">Nenhuma visita no período.</td></tr>'}</table>
<h2>Visitas</h2>
<table><tr><th>Código</th><th>Nome</th><th>CPF</th><th>Tipo</th><th>Empresa</th>
<th>Placa</th><th>Entrada</th><th>Saída</th></tr>{linhas}</table>
<p class="rodape">Emitido por {e(emitido_por)} em
{momento.strftime('%d/%m/%Y %H:%M')}. Contém dados pessoais: guarde ou descarte
com cuidado (LGPD).</p>"""
    return pagina("Relatório de movimento", corpo)


def abrir(texto_html, prefixo, dono=None):
    """Grava a página num arquivo temporário e abre no navegador. Devolve
    o caminho."""
    arquivo = tempfile.NamedTemporaryFile(
        "w", suffix=".html", prefix=f"portaria-{prefixo}-", delete=False,
        encoding="utf-8")
    with arquivo:
        arquivo.write(texto_html)
    _temporarios.append(arquivo.name)
    webbrowser.open(f"file:///{arquivo.name.replace(os.sep, '/')}")
    if dono is not None:
        dono.after(SEGUNDOS_ATE_APAGAR * 1000, apagar_temporarios)
    return arquivo.name


def apagar_temporarios():
    while _temporarios:
        try:
            os.remove(_temporarios.pop())
        except OSError:
            pass


atexit.register(apagar_temporarios)
