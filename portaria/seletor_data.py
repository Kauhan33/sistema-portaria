"""
Seletor de data e hora (pop-up no estilo Guarita), desenhado num Canvas,
só com a biblioteca padrão.

- Campo de data e hora: primeiro o CALENDÁRIO (grade do mês, hoje com um
  anel, ‹ › troca o mês e « » o ano); escolhido o dia, o RELÓGIO: as horas
  em dois anéis (00 a 11 por fora, 12 a 23 por dentro) e depois os minutos
  (de 5 em 5; clicar entre eles, a roda do mouse e os botões −1/+1 fazem o
  ajuste fino). OK preenche "dd/mm/aaaa hh:mm".
- Campo só de data (feriados, eventos, exportar CSV): só o calendário.
- Campo só de hora (Configurações): só o relógio.

Digitar no campo continua valendo: a primeira tecla fecha o pop-up. Esc
fecha, clicar fora fecha. O pop-up abre embaixo do campo e, se não couber,
em cima; nunca sai da área útil do monitor (cabe em 1366×670).

As contas de geometria (que hora fica em cada ponto do mostrador, onde
abrir) são funções puras, testadas sem tela.
"""

import calendar
import ctypes
import math
import tkinter as tk
import tkinter.font as tkfont
from datetime import date, datetime

from .componentes import MESES, ret_arredondado
from .estilo import COR, FONTE, px

DATA_HORA, DATA, HORA = "data_hora", "data", "hora"
FORMATOS = {DATA_HORA: "%d/%m/%Y %H:%M", DATA: "%d/%m/%Y", HORA: "%H:%M"}
CALENDARIO, HORAS, MINUTOS = "calendario", "horas", "minutos"
DIAS_DA_SEMANA = ("D", "S", "T", "Q", "Q", "S", "S")    # começa no domingo
# medidas em px lógicos
LARGURA, ALTURA = 300, 360
CELULA = 36
RAIO = 112                    # mostrador do relógio
ANEL_FORA, ANEL_DENTRO = 0.80, 0.53
ANEL_FINO = 0.60              # minuto fora dos de 5 em 5 (não cobre o número)
FOLGA = 4                     # distância entre o campo e o pop-up

calendar.setfirstweekday(calendar.SUNDAY)


# ----------------------------------------------------------------------
# Contas puras (testadas sem tela)
# ----------------------------------------------------------------------
def angulo(dx, dy):
    """Ângulo em graus a partir do "meio-dia" do mostrador, no sentido do
    relógio (y do Canvas cresce para baixo)."""
    return math.degrees(math.atan2(dx, -dy)) % 360


def hora_no_ponto(dx, dy, raio):
    """Hora (0–23) clicada no ponto (dx, dy) relativo ao centro: o anel de
    fora é 00–11, o de dentro 12–23."""
    posicao = round(angulo(dx, dy) / 30) % 12
    dentro = math.hypot(dx, dy) < raio * (ANEL_FORA + ANEL_DENTRO) / 2
    return posicao + 12 if dentro else posicao


def minuto_no_ponto(dx, dy):
    """Minuto (0–59) no ângulo do ponto: o ajuste fino é clicar entre os
    números (cada minuto ocupa 6 graus)."""
    return round(angulo(dx, dy) / 6) % 60


def ponto_no_mostrador(posicao, total, raio, fracao):
    """(dx, dy) da posição `posicao` de `total` (0 em cima) no anel."""
    a = math.radians(posicao * 360 / total)
    return raio * fracao * math.sin(a), -raio * fracao * math.cos(a)


def posicao_na_tela(campo, tamanho, area):
    """
    (x, y) do pop-up: embaixo do campo; se não couber, em cima; se também
    não couber (tela baixa), ao lado dele, sem cobri-lo. Sempre dentro da
    área útil `area` = (x0, y0, x1, y1) do monitor.
    campo = (x, y, largura, altura) do campo; tamanho = (largura, altura).
    """
    cx, cy, cl, ca = campo
    largura, altura = tamanho
    x0, y0, x1, y1 = area
    x = min(max(cx, x0), x1 - largura)
    if cy + ca + FOLGA + altura <= y1:
        y = cy + ca + FOLGA
    elif cy - altura - FOLGA >= y0:
        y = cy - altura - FOLGA
    else:
        x = cx + cl + FOLGA
        if x + largura > x1:
            x = cx - largura - FOLGA
        y = min(cy + ca // 2 - altura // 2, y1 - altura)
    return max(min(x, x1 - largura), x0), max(y, y0)


def area_util(widget):
    """Área útil do monitor (sem a barra de tarefas), em pixels reais."""
    try:
        retangulo = (ctypes.c_long * 4)()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, retangulo, 0):
            return tuple(retangulo)
    except (AttributeError, OSError):
        pass
    return 0, 0, widget.winfo_screenwidth(), widget.winfo_screenheight()


def ler_valor(texto, modo, padrao):
    """O que já está no campo (se for válido) ou `padrao` (datetime)."""
    try:
        lido = datetime.strptime(texto.strip(), FORMATOS[modo])
    except ValueError:
        return padrao
    if modo == HORA:
        return padrao.replace(hour=lido.hour, minute=lido.minute)
    if modo == DATA:
        return datetime.combine(lido.date(), padrao.time())
    return lido


# ----------------------------------------------------------------------
# Pop-up
# ----------------------------------------------------------------------
class SeletorDataHora:
    def __init__(self, campo, modo=DATA_HORA, relogio=None, ao_escolher=None):
        """campo: componentes.Campo (o texto vai em campo.entrada);
        relogio: função do "agora" (o app passa o dele); ao_escolher: chamado
        depois de preencher o campo."""
        self.campo, self.modo = campo, modo
        self.relogio = relogio or datetime.now
        self.ao_escolher = ao_escolher
        hoje = self.relogio()
        self.hoje = hoje.date()
        self.valor = ler_valor(campo.entrada.get(), modo, hoje.replace(
            second=0, microsecond=0))
        self.mes = (self.valor.year, self.valor.month)
        self.etapa = HORAS if modo == HORA else CALENDARIO

        self.janela = tk.Toplevel(campo)
        self.janela.withdraw()
        self.janela.overrideredirect(True)
        self.janela.configure(bg=COR["borda_campo"])
        self.cv = tk.Canvas(self.janela, width=px(LARGURA), height=px(ALTURA),
                            bg=COR["superficie"], highlightthickness=0, bd=0)
        self.cv.pack(padx=1, pady=1)
        self.cv.bind("<MouseWheel>", self._roda)
        self.janela.bind("<Escape>", lambda e: self.fechar())
        self.desenhar()
        self._posicionar()
        self.janela.deiconify()
        self.janela.lift()

    # ------------------------------------------------------------ geral
    def existe(self):
        try:
            return bool(self.janela.winfo_exists())
        except tk.TclError:
            return False

    def fechar(self):
        if self.existe():
            self.janela.destroy()

    def _posicionar(self):
        self.janela.update_idletasks()
        campo = self.campo
        x, y = posicao_na_tela(
            (campo.winfo_rootx(), campo.winfo_rooty(), campo.winfo_width(),
             campo.winfo_height()),
            (self.janela.winfo_reqwidth(), self.janela.winfo_reqheight()),
            area_util(self.janela))
        self.janela.geometry(f"+{x}+{y}")
        self.posicao = (x, y)

    def desenhar(self):
        self.cv.delete("all")
        {CALENDARIO: self._desenhar_calendario, HORAS: self._desenhar_horas,
         MINUTOS: self._desenhar_minutos}[self.etapa]()

    def _botao(self, x, y, texto, comando, largura=None, principal=False,
               ancora="w"):
        """Botão desenhado no Canvas (cantos de 6 px, como os Botao).
        Devolve a largura usada."""
        fonte = FONTE["botao"]
        largura = largura or (tkfont.Font(root=self.cv, font=fonte)
                              .measure(texto) + px(28))
        if ancora == "e":
            x -= largura
        altura = px(32)
        fundo = COR["primario"] if principal else COR["superficie"]
        borda = None if principal else COR["borda_campo"]
        tag = f"botao-{texto}"
        ret_arredondado(self.cv, x, y, x + largura, y + altura, px(6), fundo,
                        COR["superficie"], borda, tag=tag)
        self.cv.create_text(x + largura / 2, y + altura / 2, text=texto,
                            font=fonte, tags=tag,
                            fill=COR["texto_invertido"] if principal
                            else COR["texto"])
        self.cv.tag_bind(tag, "<Button-1>", lambda e: comando())
        self.cv.tag_bind(tag, "<Enter>", lambda e: self.cv.config(cursor="hand2"))
        self.cv.tag_bind(tag, "<Leave>", lambda e: self.cv.config(cursor=""))
        return largura

    def _rodape(self, botoes):
        """Linha de botões embaixo: [(texto, comando, principal)], o
        primeiro à esquerda e o último (principal) à direita."""
        y = px(ALTURA) - px(46)
        self.cv.create_line(0, y - px(8), px(LARGURA), y - px(8),
                            fill=COR["borda"])
        esquerda, direita = px(12), px(LARGURA) - px(12)
        for texto, comando, principal in botoes:
            if principal or texto == "Cancelar":
                direita -= self._botao(direita, y, texto, comando,
                                       principal=principal, ancora="e") + px(8)
            else:
                esquerda += self._botao(esquerda, y, texto, comando) + px(8)

    # ------------------------------------------------------------ calendário
    def _desenhar_calendario(self):
        cv, w = self.cv, px(LARGURA)
        ano, mes = self.mes
        cv.create_text(w / 2, px(24), text=f"{MESES[mes - 1].capitalize()} {ano}",
                       font=FONTE["titulo_cartao"], fill=COR["texto"])
        for texto, x, comando in (("«", px(20), lambda: self.mudar_ano(-1)),
                                  ("‹", px(48), lambda: self.mudar_mes(-1)),
                                  ("›", w - px(48), lambda: self.mudar_mes(1)),
                                  ("»", w - px(20), lambda: self.mudar_ano(1))):
            self._seta(x, px(24), texto, comando)
        x0 = (w - 7 * px(CELULA)) / 2
        for i, letra in enumerate(DIAS_DA_SEMANA):
            cv.create_text(x0 + (i + .5) * px(CELULA), px(56), text=letra,
                           font=FONTE["rotulo"], fill=COR["texto_3"])
        for linha, semana in enumerate(calendar.monthcalendar(ano, mes)):
            for coluna, dia in enumerate(semana):
                if dia:
                    self._dia(date(ano, mes, dia),
                              x0 + coluna * px(CELULA),
                              px(72) + linha * px(CELULA - 2))
        atalho = "Agora" if self.modo == DATA_HORA else "Hoje"
        self._rodape([(atalho, self.agora, False),
                      ("Cancelar", self.fechar, False)])

    def _seta(self, x, y, texto, comando):
        tag = f"seta-{texto}"
        r = px(14)
        self.cv.create_oval(x - r, y - r, x + r, y + r, fill=COR["superficie"],
                            outline="", tags=tag)
        self.cv.create_text(x, y - 1, text=texto, font=FONTE["titulo_cartao"],
                            fill=COR["texto_2"], tags=tag)
        self.cv.tag_bind(tag, "<Button-1>", lambda e: comando())
        self.cv.tag_bind(tag, "<Enter>", lambda e: self.cv.config(cursor="hand2"))
        self.cv.tag_bind(tag, "<Leave>", lambda e: self.cv.config(cursor=""))

    def _dia(self, dia, x, y):
        cv, c = self.cv, px(CELULA)
        tag = f"d{dia.isoformat()}"
        escolhido = dia == self.valor.date()
        meio = px(CELULA - 4) // 2
        cx, cy = x + c / 2, y + c / 2
        if escolhido:
            ret_arredondado(cv, cx - meio, cy - meio, cx + meio, cy + meio, meio,
                            COR["primario"], COR["superficie"], tag=tag)
        elif dia == self.hoje:
            ret_arredondado(cv, cx - meio, cy - meio, cx + meio, cy + meio, meio,
                            COR["superficie"], COR["superficie"], COR["foco"],
                            px(2), tag=tag)
        else:
            cv.create_rectangle(x, y, x + c, y + c, fill=COR["superficie"],
                                outline="", tags=tag)
        cv.create_text(cx, cy, text=str(dia.day), tags=tag,
                       font=FONTE["corpo_semi"] if escolhido or dia == self.hoje
                       else FONTE["corpo"],
                       fill=COR["texto_invertido"] if escolhido else COR["texto"])
        cv.tag_bind(tag, "<Button-1>", lambda e, d=dia: self.escolher_dia(d))
        cv.tag_bind(tag, "<Enter>", lambda e: cv.config(cursor="hand2"))
        cv.tag_bind(tag, "<Leave>", lambda e: cv.config(cursor=""))

    def mudar_mes(self, passo):
        ano, mes = self.mes
        mes += passo
        ano, mes = ano + (mes - 1) // 12, (mes - 1) % 12 + 1
        self.mes = (ano, mes)
        self.desenhar()

    def mudar_ano(self, passo):
        self.mes = (self.mes[0] + passo, self.mes[1])
        self.desenhar()

    def escolher_dia(self, dia):
        self.valor = datetime.combine(dia, self.valor.time())
        self.mes = (dia.year, dia.month)
        if self.modo == DATA:
            self.confirmar()
            return
        self.etapa = HORAS
        self.desenhar()

    def agora(self):
        """Atalho "Agora"/"Hoje": preenche com o relógio do app."""
        agora = self.relogio().replace(second=0, microsecond=0)
        self.valor = (agora if self.modo != DATA else
                      datetime.combine(agora.date(), self.valor.time()))
        self.confirmar()

    # ------------------------------------------------------------ relógio
    def _centro(self):
        return px(LARGURA) / 2, px(62) + px(RAIO)

    def _cabecalho_relogio(self):
        cv, w = self.cv, px(LARGURA)
        if self.modo == DATA_HORA:
            tag = "voltar-data"
            cv.create_text(px(16), px(24), text=f"{self.valor:%d/%m/%Y}",
                           anchor="w", font=FONTE["corpo_semi"],
                           fill=COR["foco"], tags=tag)
            cv.tag_bind(tag, "<Button-1>", lambda e: self.voltar(CALENDARIO))
        hora_cor = COR["texto"] if self.etapa == HORAS else COR["texto_3"]
        minuto_cor = COR["texto"] if self.etapa == MINUTOS else COR["texto_3"]
        cv.create_text(w - px(64), px(26), text=f"{self.valor:%H}", anchor="e",
                       font=FONTE["numero"], fill=hora_cor, tags="ver-horas")
        cv.create_text(w - px(58), px(26), text=":", font=FONTE["numero"],
                       fill=COR["texto_3"])
        cv.create_text(w - px(52), px(26), text=f"{self.valor:%M}", anchor="w",
                       font=FONTE["numero"], fill=minuto_cor, tags="ver-minutos")
        cv.tag_bind("ver-horas", "<Button-1>", lambda e: self.voltar(HORAS))
        cv.tag_bind("ver-minutos", "<Button-1>", lambda e: self.voltar(MINUTOS))

    def _mostrador(self, numeros, escolhido, ao_clicar):
        """Círculo claro com os números; o escolhido ganha a bolinha escura
        e o ponteiro. numeros: [(valor, texto, posição, total, fração)]."""
        cv = self.cv
        cx, cy = self._centro()
        r = px(RAIO)
        cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=COR["superficie_2"],
                       outline=COR["superficie_2"], tags="mostrador")
        cv.tag_bind("mostrador", "<Button-1>",
                    lambda e: ao_clicar(e.x - cx, e.y - cy))
        for valor, texto, posicao, total, fracao in numeros:
            if valor != escolhido:
                continue
            dx, dy = ponto_no_mostrador(posicao, total, r, fracao)
            cv.create_line(cx, cy, cx + dx, cy + dy, fill=COR["primario"],
                           width=px(2), tags="mostrador")
            b = px(15)
            ret_arredondado(cv, cx + dx - b, cy + dy - b, cx + dx + b,
                            cy + dy + b, b, COR["primario"], COR["superficie_2"],
                            tag="mostrador")
        cv.create_oval(cx - px(3), cy - px(3), cx + px(3), cy + px(3),
                       fill=COR["primario"], outline="", tags="mostrador")
        for valor, texto, posicao, total, fracao in numeros:
            dx, dy = ponto_no_mostrador(posicao, total, r, fracao)
            dentro = fracao < ANEL_FORA
            cv.create_text(cx + dx, cy + dy, text=texto, tags="mostrador",
                           font=FONTE["dica"] if dentro else FONTE["corpo"],
                           fill=COR["texto_invertido"] if valor == escolhido
                           else (COR["texto_2"] if dentro else COR["texto"]))
        cv.tag_bind("mostrador", "<Enter>", lambda e: cv.config(cursor="hand2"))
        cv.tag_bind("mostrador", "<Leave>", lambda e: cv.config(cursor=""))

    def _desenhar_horas(self):
        self._cabecalho_relogio()
        numeros = [(h, f"{h:02d}", h, 12, ANEL_FORA) for h in range(12)]
        numeros += [(h, f"{h:02d}", h - 12, 12, ANEL_DENTRO)
                    for h in range(12, 24)]
        self._mostrador(numeros, self.valor.hour, self._clique_hora)
        botoes = [("Cancelar", self.fechar, False)]
        if self.modo == HORA:
            botoes.insert(0, ("Agora", self.agora, False))
        self._rodape(botoes)

    def _desenhar_minutos(self):
        self._cabecalho_relogio()
        numeros = [(m, f"{m:02d}", m, 60, ANEL_FORA) for m in range(0, 60, 5)]
        if self.valor.minute % 5:          # o minuto fino, por dentro do anel
            m = self.valor.minute
            numeros.append((m, f"{m:02d}", m, 60, ANEL_FINO))
        self._mostrador(numeros, self.valor.minute, self._clique_minuto)
        self._rodape([("−1", lambda: self.ajustar_minuto(-1), False),
                      ("+1", lambda: self.ajustar_minuto(1), False),
                      ("OK", self.confirmar, True)])

    def _clique_hora(self, dx, dy):
        self.escolher_hora(hora_no_ponto(dx, dy, px(RAIO)))

    def _clique_minuto(self, dx, dy):
        self.escolher_minuto(minuto_no_ponto(dx, dy))

    def escolher_hora(self, hora):
        self.valor = self.valor.replace(hour=hora)
        self.etapa = MINUTOS
        self.desenhar()

    def escolher_minuto(self, minuto):
        self.valor = self.valor.replace(minute=minuto)
        self.desenhar()

    def ajustar_minuto(self, passo):
        self.escolher_minuto((self.valor.minute + passo) % 60)

    def _roda(self, event):
        if self.etapa == MINUTOS:
            self.ajustar_minuto(1 if event.delta > 0 else -1)

    def voltar(self, etapa):
        if etapa == CALENDARIO and self.modo == HORA:
            return
        self.etapa = etapa
        self.desenhar()

    # ------------------------------------------------------------ fim
    def confirmar(self):
        """Escreve o valor no campo, no formato dele, e fecha."""
        entrada = self.campo.entrada
        entrada.delete(0, tk.END)
        entrada.insert(0, self.valor.strftime(FORMATOS[self.modo]))
        self.fechar()
        entrada.focus_set()
        entrada.icursor(tk.END)
        if self.ao_escolher:
            self.ao_escolher()
