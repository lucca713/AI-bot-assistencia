"""Status de pedido e prazos de troca/devolução/garantia (manual, seções 4 e 8).

Contar dias entre datas é algo que LLMs erram com frequência. Por isso a
ferramenta de pedidos já devolve, calculado aqui, se cada prazo está dentro
ou fora — o agente só precisa explicar ao cliente.

Suposição documentada: a base não tem a data REAL de entrega, apenas
``estimated_delivery``. Para pedidos com status "delivered" usamos a data
estimada como data de recebimento, e avisamos isso no resultado.
"""

from datetime import date, timedelta

STATUS_LABELS = {
    "pending": "Aguardando confirmação do pagamento",
    "confirmed": "Pagamento confirmado — pedido em separação",
    "shipped": "Enviado — a caminho",
    "delivered": "Entregue",
    "cancelled": "Cancelado",
}

PAYMENT_LABELS = {
    "pix": "PIX",
    "debit": "Cartão de débito",
    "boleto": "Boleto bancário",
}

REGRET_DAYS = 7               # 4.1 direito de arrependimento (após o recebimento)
PREFERENCE_EXCHANGE_DAYS = 7  # 4.3 troca por preferência
DEFECT_EXCHANGE_DAYS = 30     # 4.2 troca por defeito na loja (após a compra)
LEGAL_WARRANTY_DAYS = 90      # 8.1 garantia legal (após o recebimento)


def payment_label(method: str | None) -> str | None:
    """'credit_6x' -> 'Cartão de crédito em 6x'."""
    if not method:
        return None
    if method.startswith("credit_"):
        return f"Cartão de crédito em {method.removeprefix('credit_')}"
    return PAYMENT_LABELS.get(method, method)


def _window(start: date, days: int, today: date) -> dict:
    deadline = start + timedelta(days=days)
    remaining = (deadline - today).days
    return {
        "dentro_do_prazo": today <= deadline,
        "prazo_final": deadline.strftime("%d/%m/%Y"),
        "dias_restantes": max(remaining, 0),
    }


def evaluate_deadlines(
    status: str,
    order_date: date,
    estimated_delivery: date | None,
    today: date,
) -> dict:
    """Avalia, para a data ``today``, quais direitos o cliente ainda tem."""
    result: dict = {"data_de_referencia": today.strftime("%d/%m/%Y")}

    if status == "cancelled":
        result["observacao"] = "Pedido cancelado: não há prazos de troca ou devolução aplicáveis."
        return result

    if status in ("pending", "confirmed"):
        result["observacao"] = (
            "Pedido ainda não enviado. Os prazos de arrependimento e garantia "
            "começam a contar a partir do recebimento. Pedidos de cancelamento "
            "devem ser encaminhados à equipe (abrir chamado)."
        )
        return result

    if status == "shipped":
        late = bool(estimated_delivery and today > estimated_delivery)
        result["entrega_atrasada"] = late
        if estimated_delivery:
            result["previsao_entrega"] = estimated_delivery.strftime("%d/%m/%Y")
        result["observacao"] = (
            "Pedido em trânsito. Os prazos de arrependimento e garantia começam "
            "a contar a partir do recebimento."
            + (" A previsão de entrega já passou: ofereça abrir um chamado para a equipe verificar."
               if late else "")
        )
        return result

    # delivered
    received = estimated_delivery or order_date
    result["data_recebimento_considerada"] = received.strftime("%d/%m/%Y")
    result["aviso"] = (
        "A base não registra a data real de entrega; foi considerada a data "
        "prevista de entrega. Se o cliente recebeu em outra data, confirme com ele."
    )
    result["dias_desde_o_recebimento"] = (today - received).days
    result["arrependimento_7_dias"] = _window(received, REGRET_DAYS, today)
    result["troca_por_preferencia_7_dias"] = _window(received, PREFERENCE_EXCHANGE_DAYS, today)
    result["troca_por_defeito_na_loja_30_dias"] = _window(order_date, DEFECT_EXCHANGE_DAYS, today)
    result["garantia_legal_90_dias"] = _window(received, LEGAL_WARRANTY_DAYS, today)
    return result
