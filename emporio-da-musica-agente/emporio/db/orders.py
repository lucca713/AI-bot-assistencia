"""Consultas de pedidos e clientes.

Privacidade (LGPD, manual seção 9): um pedido só é revelado se o cliente
informar um contato (e-mail ou telefone) que bata com o cadastro do dono do
pedido. Sem isso, qualquer pessoa poderia digitar "pedido 5" e ver dados de
outro cliente.
"""

from psycopg import Connection

from emporio.domain.text import only_digits

MIN_PHONE_DIGITS = 8  # aceita telefone com ou sem DDD/código do país


def find_customers_by_contact(conn: Connection, contact: str) -> list[dict]:
    """Clientes cujo e-mail ou telefone corresponde ao contato informado.

    Retorna lista porque um mesmo e-mail pode estar em mais de um cadastro
    (acontece na base: bruno.martins@jmail.com).
    """
    contact = contact.strip()
    if "@" in contact:
        return conn.execute(
            "SELECT * FROM customers WHERE email = %s ORDER BY customer_id",
            (contact.lower(),),
        ).fetchall()

    digits = only_digits(contact)
    if len(digits) < MIN_PHONE_DIGITS:
        return []
    # "(67) 99812-3456", "67998123456", "+55 67 99812-3456" e "99812-3456"
    # devem achar o mesmo cliente: comparamos pelo final do número.
    return conn.execute(
        """SELECT * FROM customers
            WHERE right(phone_digits, %(n)s) = right(%(digits)s, %(n)s)
            ORDER BY customer_id""",
        {"digits": digits, "n": min(len(digits), 11)},
    ).fetchall()


def get_orders(conn: Connection, customer_ids: list[int], order_id: int | None = None) -> list[dict]:
    """Pedidos dos clientes informados (opcionalmente um pedido específico)."""
    return conn.execute("""
        SELECT o.*, c.name AS customer_name
          FROM orders o
          JOIN customers c USING (customer_id)
         WHERE o.customer_id = ANY(%(customer_ids)s)
           AND (%(order_id)s::int IS NULL OR o.order_id = %(order_id)s)
         ORDER BY o.order_date DESC
    """, {"customer_ids": customer_ids, "order_id": order_id}).fetchall()


def get_order_items(conn: Connection, order_id: int) -> list[dict]:
    return conn.execute("""
        SELECT oi.product_id, oi.quantity, p.name AS product_name, c.name AS category_name
          FROM order_items oi
          JOIN products p USING (product_id)
          JOIN categories c USING (category_id)
         WHERE oi.order_id = %s
         ORDER BY p.name
    """, (order_id,)).fetchall()
