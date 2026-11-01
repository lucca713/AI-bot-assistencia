"""Simulação de formas de pagamento e parcelamento.

Regras do manual (seção 3.1). Interpretação adotada (documentada no README):
o manual tem uma tabela-resumo ("parcela mínima de R$ 100,00") e uma seção
detalhada por faixas. Prevalece a regra mais específica:

    1x            -> sempre permitido
    2x a 3x       -> parcela mínima de R$ 50,00
    4x a 6x       -> parcela mínima de R$ 80,00
    7x a 12x      -> parcela mínima de R$ 100,00

Todas sem juros. Combinação de formas (ex.: PIX + cartão) só acima de
R$ 2.000,00.
"""

from dataclasses import dataclass
from decimal import Decimal

from emporio.domain.money import format_brl, to_money
from emporio.domain.pricing import PIX_DISCOUNT_PERCENT

COMBINED_PAYMENT_THRESHOLD = Decimal("2000.00")


@dataclass(frozen=True)
class InstallmentTier:
    min_installments: int
    max_installments: int
    min_installment_value: Decimal


INSTALLMENT_TIERS: tuple[InstallmentTier, ...] = (
    InstallmentTier(1, 1, Decimal("0")),
    InstallmentTier(2, 3, Decimal("50.00")),
    InstallmentTier(4, 6, Decimal("80.00")),
    InstallmentTier(7, 12, Decimal("100.00")),
)


def _min_value_for(installments: int) -> Decimal:
    for tier in INSTALLMENT_TIERS:
        if tier.min_installments <= installments <= tier.max_installments:
            return tier.min_installment_value
    raise ValueError(f"Parcelamento em {installments}x não existe (máximo 12x).")


def installment_options(total: Decimal | float | str) -> list[tuple[int, Decimal]]:
    """Lista (número de parcelas, valor da parcela) permitidos para o total."""
    amount = to_money(total)
    options = []
    for n in range(1, 13):
        # Comparamos o valor exato (sem arredondar) com o mínimo da faixa.
        if amount / n >= _min_value_for(n):
            options.append((n, to_money(amount / n)))
    return options


def simulate_payment(total: Decimal | float | str, is_promotional: bool) -> dict:
    """Resumo de todas as formas de pagamento para um valor.

    ``is_promotional`` indica que o valor já é um preço promocional — nesse
    caso o PIX não ganha os 5% extras (promoções não são cumulativas).
    """
    amount = to_money(total)
    if amount <= 0:
        raise ValueError("O valor precisa ser maior que zero.")

    options = installment_options(amount)
    max_n, max_value = options[-1]

    if is_promotional:
        pix = {
            "valor": format_brl(amount),
            "observacao": "Sem desconto adicional: o desconto do PIX não acumula com promoção.",
        }
    else:
        pix_value = to_money(amount * (Decimal(100) - PIX_DISCOUNT_PERCENT) / 100)
        pix = {
            "valor": format_brl(pix_value),
            "observacao": f"5% de desconto (economia de {format_brl(amount - pix_value)}).",
        }

    return {
        "valor_base": format_brl(amount),
        "pix": pix,
        "debito": {"valor": format_brl(amount), "observacao": "À vista, todas as bandeiras."},
        "boleto": {"valor": format_brl(amount), "observacao": "À vista, compensação em até 3 dias úteis."},
        "cartao_credito": {
            "maximo_parcelas_sem_juros": max_n,
            "parcela_no_maximo": f"{max_n}x de {format_brl(max_value)}",
            "opcoes": [f"{n}x de {format_brl(v)}" for n, v in options],
        },
        "pode_combinar_formas_de_pagamento": amount > COMBINED_PAYMENT_THRESHOLD,
        "regra_combinacao": "Combinação (ex.: PIX + cartão) permitida para compras acima de R$ 2.000,00.",
    }
