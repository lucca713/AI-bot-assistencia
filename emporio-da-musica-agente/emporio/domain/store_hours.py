"""Horário de funcionamento (manual, seção 2) e feriados.

O status "loja aberta/fechada agora" é calculado aqui e entregue ao agente a
cada mensagem. Assim ele sabe, por exemplo, que fora do expediente deve
informar o horário de retorno (manual, seção 7.1) — sem depender do modelo
saber que dia da semana é hoje.

Suposição documentada: o manual diz "Domingo e Feriados: fechado", mas não
lista os feriados. Consideramos os feriados nacionais, o feriado estadual de
MS e os municipais de Campo Grande listados abaixo.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

WEEKDAY_NAMES = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
                 "sexta-feira", "sábado", "domingo")

# weekday() do Python: 0 = segunda ... 6 = domingo. None = fechado.
WEEKLY_HOURS: dict[int, tuple[time, time] | None] = {
    0: (time(9, 0), time(18, 0)),
    1: (time(9, 0), time(18, 0)),
    2: (time(9, 0), time(18, 0)),
    3: (time(9, 0), time(18, 0)),
    4: (time(9, 0), time(18, 0)),
    5: (time(9, 0), time(13, 0)),
    6: None,
}

# (mês, dia) -> nome
FIXED_HOLIDAYS: dict[tuple[int, int], str] = {
    (1, 1): "Confraternização Universal",
    (4, 21): "Tiradentes",
    (5, 1): "Dia do Trabalho",
    (6, 13): "Santo Antônio (padroeiro de Campo Grande)",
    (8, 26): "Aniversário de Campo Grande",
    (9, 7): "Independência do Brasil",
    (10, 11): "Criação do Estado de Mato Grosso do Sul",
    (10, 12): "Nossa Senhora Aparecida",
    (11, 2): "Finados",
    (11, 15): "Proclamação da República",
    (11, 20): "Dia Nacional de Zumbi e da Consciência Negra",
    (12, 25): "Natal",
}


def easter_sunday(year: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher, calendário gregoriano)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    el = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * el) // 451
    month, day = divmod(h + el - 7 * m + 114, 31)
    return date(year, month, day + 1)


def holiday_name(day: date) -> str | None:
    """Nome do feriado na data, ou None se for dia comum."""
    if (day.month, day.day) in FIXED_HOLIDAYS:
        return FIXED_HOLIDAYS[(day.month, day.day)]
    if day == easter_sunday(day.year) - timedelta(days=2):
        return "Sexta-feira Santa"
    return None


def hours_for(day: date) -> tuple[time, time] | None:
    """Horário de abertura/fechamento do dia (None = loja fechada o dia todo)."""
    if holiday_name(day):
        return None
    return WEEKLY_HOURS[day.weekday()]


@dataclass(frozen=True)
class StoreStatus:
    now: datetime
    is_open: bool
    closes_at: time | None          # preenchido quando a loja está aberta
    next_opening: datetime | None   # preenchido quando a loja está fechada
    holiday: str | None             # feriado de hoje, se houver

    def describe(self) -> str:
        """Frase pronta, em português, usada no contexto do agente e na UI."""
        weekday = WEEKDAY_NAMES[self.now.weekday()]
        header = f"Agora é {weekday}, {self.now:%d/%m/%Y %H:%M} (horário de Campo Grande/MS)."
        if self.holiday:
            header += f" Hoje é feriado: {self.holiday}."
        if self.is_open:
            return f"{header} A loja está ABERTA e fecha às {self.closes_at:%H:%M}."
        nxt = self.next_opening
        when = WEEKDAY_NAMES[nxt.weekday()]
        if nxt.date() == self.now.date():
            when = "hoje"
        elif nxt.date() == self.now.date() + timedelta(days=1):
            when = f"amanhã ({when})"
        return (f"{header} A loja está FECHADA. Próxima abertura: {when}, "
                f"{nxt:%d/%m} às {nxt:%H:%M}.")


def store_status(now: datetime) -> StoreStatus:
    """Calcula se a loja está aberta em ``now`` (datetime no fuso da loja)."""
    today_hours = hours_for(now.date())
    holiday = holiday_name(now.date())

    if today_hours and today_hours[0] <= now.time() < today_hours[1]:
        return StoreStatus(now, True, today_hours[1], None, holiday)

    # Fechada: procura a próxima abertura (hoje mais tarde ou nos próximos dias).
    for offset in range(0, 15):
        day = now.date() + timedelta(days=offset)
        hours = hours_for(day)
        if not hours:
            continue
        opening = datetime.combine(day, hours[0], tzinfo=now.tzinfo)
        if opening > now:
            return StoreStatus(now, False, None, opening, holiday)

    # Nunca deve acontecer (15 dias seguidos fechados), mas não quebramos.
    return StoreStatus(now, False, None, None, holiday)
