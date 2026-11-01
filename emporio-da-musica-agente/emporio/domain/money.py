"""Utilitários de dinheiro.

Valores monetários usam ``Decimal`` (nunca ``float``): 0.1 + 0.2 em float é
0.30000000000000004, e isso não pode aparecer num preço para o cliente.
"""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def to_money(value: Decimal | float | int | str) -> Decimal:
    """Converte qualquer número para Decimal com 2 casas (arredondamento comercial)."""
    # str() antes de Decimal() evita herdar a imprecisão de um float.
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def format_brl(value: Decimal | float | int | str) -> str:
    """Formata no padrão brasileiro: 1234.5 -> 'R$ 1.234,50'."""
    amount = to_money(value)
    # Formata no padrão americano (1,234.50) e troca os separadores.
    us_style = f"{amount:,.2f}"
    br_style = us_style.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {br_style}"
