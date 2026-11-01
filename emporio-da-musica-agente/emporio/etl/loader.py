"""Grava os dados tratados no PostgreSQL.

Tudo acontece em UMA transação: se qualquer linha violar uma regra (CHECK,
chave estrangeira...), nada é gravado e o banco fica como estava.
"""

import psycopg
from psycopg.types.json import Jsonb

from emporio.db.connection import render_schema_sql
from emporio.etl.policies import PolicySection
from emporio.etl.transform import CleanData

# Ordem importa por causa das chaves estrangeiras.
DATA_TABLES = ("order_items", "orders", "customers", "promotions", "products",
               "categories", "policy_sections")


def _insert_many(cur: psycopg.Cursor, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    columns = list(rows[0].keys())
    placeholders = ", ".join(f"%({c})s" for c in columns)
    cur.executemany(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
        rows,
    )


def load_everything(
    conninfo: str,
    schema: str,
    data: CleanData,
    sections: list[PolicySection],
    reset: bool = False,
) -> None:
    """Cria o schema (se preciso) e recarrega catálogo, pedidos e políticas.

    Conversas, chamados e logs NÃO são apagados, a menos que ``reset=True``
    (que derruba o schema inteiro e recria do zero).
    """
    schema_sql = render_schema_sql(schema)

    with psycopg.connect(conninfo) as conn:  # o "with" faz commit no final (ou rollback em erro)
        with conn.cursor() as cur:
            if reset:
                cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            cur.execute(schema_sql)
            cur.execute(f"SET search_path TO {schema}, public")

            # Recarga completa das tabelas de dados (são pequenas).
            cur.execute(f"TRUNCATE {', '.join(DATA_TABLES)} RESTART IDENTITY CASCADE")

            _insert_many(cur, "categories", data.categories)
            _insert_many(cur, "products",
                         [{**p, "specs": Jsonb(p["specs"])} for p in data.products])
            _insert_many(cur, "promotions", data.promotions)
            _insert_many(cur, "customers", data.customers)
            _insert_many(cur, "orders", data.orders)
            _insert_many(cur, "order_items", data.order_items)
            _insert_many(cur, "policy_sections", [
                {"slug": s.slug, "number": s.number, "title": s.title,
                 "summary": s.summary, "content": s.content}
                for s in sections
            ])


def table_counts(conninfo: str, schema: str) -> dict[str, int]:
    with psycopg.connect(conninfo) as conn:
        return {t: conn.execute(f"SELECT count(*) FROM {schema}.{t}").fetchone()[0]
                for t in DATA_TABLES}

