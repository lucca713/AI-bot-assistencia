"""Horário de funcionamento e feriados (manual, seção 2)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from emporio.domain.store_hours import easter_sunday, holiday_name, store_status

TZ = ZoneInfo("America/Campo_Grande")


def at(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=TZ)


def test_weekday_open_and_closing_time():
    status = store_status(at("2026-02-20T10:30"))  # sexta-feira
    assert status.is_open
    assert status.closes_at.hour == 18


def test_saturday_closes_at_13():
    assert store_status(at("2026-02-21T12:59")).is_open
    after = store_status(at("2026-02-21T13:00"))
    assert not after.is_open
    assert after.next_opening == at("2026-02-23T09:00")  # domingo fechado -> segunda


def test_before_opening_same_day():
    status = store_status(at("2026-02-20T08:00"))
    assert not status.is_open
    assert status.next_opening == at("2026-02-20T09:00")
    assert "hoje" in status.describe()


def test_holidays_are_closed():
    # 01/11/2026 é domingo e 02/11 é Finados: próxima abertura na terça.
    status = store_status(at("2026-11-01T14:00"))
    assert status.next_opening == at("2026-11-03T09:00")
    assert holiday_name(date(2026, 11, 2)) == "Finados"


def test_good_friday_from_easter():
    assert easter_sunday(2026) == date(2026, 4, 5)
    assert holiday_name(date(2026, 4, 3)) == "Sexta-feira Santa"
    assert not store_status(at("2026-04-03T10:00")).is_open
