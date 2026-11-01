"""Cálculo de preço final de um produto.

Regras (manual, seções 3 e 6.2):
- PIX tem 5% de desconto sobre o preço de tabela.
- Promoções NÃO são cumulativas: o desconto do PIX não vale sobre preço
  promocional.
- Preço promocional deve ser apresentado junto do preço original e do
  percentual de desconto (transparência).
"""

from dataclasses import dataclass
from decimal import Decimal

from emporio.domain.money import format_brl, to_money

PIX_DISCOUNT_PERCENT = Decimal("5")


@dataclass(frozen=True)
class PriceQuote:
    """Resultado do cálculo de preço de um produto."""

    list_price: Decimal                 # preço de tabela
    promo_percent: int | None           # % da promoção ativa (se houver)
    promo_name: str | None              # nome da campanha (ex.: "Oferta Especial")
    final_price: Decimal                # preço a pagar no cartão/boleto/débito
    pix_price: Decimal                  # preço a pagar no PIX

    @property
    def is_promotional(self) -> bool:
        return self.promo_percent is not None

    def to_dict(self) -> dict:
        """Formato entregue ao LLM: valores já formatados, para ele não ter
        que fazer conta nem formatação (fonte comum de erro)."""
        data: dict = {
            "preco_tabela": format_brl(self.list_price),
            "preco_final": format_brl(self.final_price),
            # valor numérico para o agente repassar a `simular_pagamento`
            "preco_final_numero": float(self.final_price),
            "preco_pix": format_brl(self.pix_price),
        }
        if self.is_promotional:
            data["promocao_ativa"] = {
                "campanha": self.promo_name,
                "desconto_percentual": self.promo_percent,
                "regra": "Preço promocional já aplicado. Mostre preço original, "
                "percentual e preço promocional. O desconto do PIX não acumula "
                "com a promoção.",
            }
        else:
            data["promocao_ativa"] = None
        return data


def quote_price(
    list_price: Decimal | float | str,
    promo_percent: int | None = None,
    promo_name: str | None = None,
) -> PriceQuote:
    """Calcula preço final e preço no PIX respeitando a não-cumulatividade."""
    base = to_money(list_price)

    if promo_percent:  # promoção ativa: desconto da campanha, sem PIX extra
        final = to_money(base * (Decimal(100) - Decimal(promo_percent)) / 100)
        pix = final
    else:  # sem promoção: PIX ganha 5%
        promo_percent, promo_name = None, None
        final = base
        pix = to_money(base * (Decimal(100) - PIX_DISCOUNT_PERCENT) / 100)

    return PriceQuote(
        list_price=base,
        promo_percent=promo_percent,
        promo_name=promo_name,
        final_price=final,
        pix_price=pix,
    )
