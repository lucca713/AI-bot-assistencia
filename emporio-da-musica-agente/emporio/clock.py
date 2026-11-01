"""Relógio da aplicação.

Tudo que depende de "agora" (loja aberta? prazo de devolução vencido?) pede
a hora para um ``Clock`` em vez de chamar ``datetime.now()`` direto. Isso
permite simular uma data — essencial aqui, porque os pedidos da base são de
out/2025 a mar/2026 — e torna os testes determinísticos.
"""

from datetime import datetime

from emporio.config import STORE_TIMEZONE


class Clock:
    def __init__(self, simulated_now: datetime | None = None) -> None:
        self._simulated_now = simulated_now

    @property
    def is_simulated(self) -> bool:
        return self._simulated_now is not None

    def now(self) -> datetime:
        """Data/hora atual no fuso de Campo Grande (ou a data simulada)."""
        if self._simulated_now is not None:
            return self._simulated_now
        return datetime.now(STORE_TIMEZONE)
