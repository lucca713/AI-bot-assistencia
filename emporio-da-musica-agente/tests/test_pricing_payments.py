"""Preço, PIX e parcelamento (manual, seções 3 e 6.2)."""

from decimal import Decimal

from emporio.domain.money import format_brl
from emporio.domain.payments import installment_options, simulate_payment
from emporio.domain.pricing import quote_price


def test_format_brl():
    assert format_brl(2199) == "R$ 2.199,00"
    assert format_brl("799.9") == "R$ 799,90"
    assert format_brl(Decimal("1234567.891")) == "R$ 1.234.567,89"


def test_pix_gives_5_percent_without_promotion():
    quote = quote_price("2199")
    assert quote.final_price == Decimal("2199.00")
    assert quote.pix_price == Decimal("2089.05")
    assert not quote.is_promotional


def test_promotion_is_not_cumulative_with_pix():
    quote = quote_price("549", 20, "Desconto Exclusivo")
    assert quote.final_price == Decimal("439.20")
    assert quote.pix_price == quote.final_price  # sem 5% extra
    data = quote.to_dict()
    assert data["preco_tabela"] == "R$ 549,00"  # preço original sempre exibido
    assert data["promocao_ativa"]["desconto_percentual"] == 20


def test_installments_respect_minimum_per_tier():
    # R$ 159,90: 2x = 79,95 (ok, >= 50), 3x = 53,30 (ok), 4x = 39,98 (< 80, não pode)
    assert [n for n, _ in installment_options("159.90")] == [1, 2, 3]
    # R$ 599: 6x = 99,83 (>= 80 ok), 7x = 85,57 (< 100, não pode)
    assert max(n for n, _ in installment_options("599")) == 6
    # R$ 2199: 12x = 183,25 (>= 100 ok)
    assert max(n for n, _ in installment_options("2199")) == 12


def test_small_value_only_one_installment():
    assert [n for n, _ in installment_options("90")] == [1]  # 2x = 45 < 50


def test_simulate_payment_combination_rule():
    assert simulate_payment("2000.00", False)["pode_combinar_formas_de_pagamento"] is False
    assert simulate_payment("2000.01", False)["pode_combinar_formas_de_pagamento"] is True


def test_simulate_payment_promotional_has_no_pix_discount():
    result = simulate_payment("439.20", True)
    assert result["pix"]["valor"] == "R$ 439,20"
