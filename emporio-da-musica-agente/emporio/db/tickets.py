"""Chamados para a equipe humana (reclamações, devoluções, trocas...)."""

from datetime import datetime

from psycopg import Connection


def create_ticket(
    conn: Connection,
    *,
    conversation_id: str | None,
    ticket_type: str,
    customer_name: str,
    contact: str,
    order_id: int | None,
    summary: str,
    now: datetime,
) -> dict:
    row = conn.execute("""
        INSERT INTO tickets (conversation_id, ticket_type, customer_name, contact, order_id, summary)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING ticket_id
    """, (conversation_id, ticket_type, customer_name, contact, order_id, summary)).fetchone()
    # Protocolo legível para o cliente: EMP-20260220-00001
    protocol = f"EMP-{now:%Y%m%d}-{row['ticket_id']:05d}"
    conn.execute("UPDATE tickets SET protocol = %s WHERE ticket_id = %s", (protocol, row["ticket_id"]))
    return {"ticket_id": row["ticket_id"], "protocol": protocol}


def list_tickets(conn: Connection, limit: int = 50) -> list[dict]:
    return conn.execute("""
        SELECT ticket_id, protocol, ticket_type, customer_name, contact, order_id, summary, status,
               created_at, conversation_id
          FROM tickets
         ORDER BY created_at DESC
         LIMIT %s
    """, (limit,)).fetchall()
