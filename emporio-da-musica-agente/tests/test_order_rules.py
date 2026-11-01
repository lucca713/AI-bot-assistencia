"""Prazos de arrependimento, troca e garantia (manual, seções 4 e 8)."""

from datetime import date

from emporio.domain.order_rules import evaluate_deadlines, payment_label


def test_delivered_within_regret_window():
    # Pedido 7 da base: comprado 03/02/2026, entrega prevista 17/02/2026.
    result = evaluate_deadlines("delivered", date(2026, 2, 3), date(2026, 2, 17), today=date(2026, 2, 20))
    assert result["dias_desde_o_recebimento"] == 3
    assert result["arrependimento_7_dias"]["dentro_do_prazo"] is True
    assert result["arrependimento_7_dias"]["prazo_final"] == "24/02/2026"
    assert result["troca_por_defeito_na_loja_30_dias"]["dentro_do_prazo"] is True
    assert "aviso" in result  # data de entrega é estimada


def test_regret_window_last_day_and_after():
    on_limit = evaluate_deadlines("delivered", date(2026, 2, 3), date(2026, 2, 17), today=date(2026, 2, 24))
    assert on_limit["arrependimento_7_dias"]["dentro_do_prazo"] is True
    after = evaluate_deadlines("delivered", date(2026, 2, 3), date(2026, 2, 17), today=date(2026, 2, 25))
    assert after["arrependimento_7_dias"]["dentro_do_prazo"] is False
    assert after["garantia_legal_90_dias"]["dentro_do_prazo"] is True


def test_defect_exchange_counts_from_purchase_date():
    result = evaluate_deadlines("delivered", date(2026, 1, 1), date(2026, 1, 20), today=date(2026, 2, 5))
    assert result["troca_por_defeito_na_loja_30_dias"]["dentro_do_prazo"] is False  # 35 dias da compra


def test_shipped_late_is_flagged():
    result = evaluate_deadlines("shipped", date(2026, 2, 15), date(2026, 2, 28), today=date(2026, 3, 2))
    assert result["entrega_atrasada"] is True


def test_cancelled_has_no_deadlines():
    result = evaluate_deadlines("cancelled", date(2026, 1, 28), None, today=date(2026, 2, 1))
    assert "arrependimento_7_dias" not in result


def test_payment_label():
    assert payment_label("credit_12x") == "Cartão de crédito em 12x"
    assert payment_label("pix") == "PIX"
    assert payment_label(None) is None
