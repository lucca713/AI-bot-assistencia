"""Pool de conexões com o PostgreSQL."""

import re
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

SCHEMA_SQL_PATH = Path(__file__).with_name("schema.sql")
_VALID_SCHEMA = re.compile(r"^[a-z_][a-z0-9_]*$")


def validate_schema_name(schema: str) -> str:
    # O nome do schema entra direto no SQL, então só aceitamos identificadores simples.
    if not _VALID_SCHEMA.match(schema):
        raise ValueError(f"Nome de schema inválido: {schema!r}")
    return schema


def render_schema_sql(schema: str) -> str:
    return SCHEMA_SQL_PATH.read_text(encoding="utf-8").replace("{schema}", validate_schema_name(schema))


def create_pool(conninfo: str, schema: str) -> ConnectionPool:
    """Cria o pool. Cada conexão já nasce com o search_path no schema da loja,
    então as consultas podem escrever ``products`` em vez de ``emporio.products``.
    Linhas voltam como dict (``row["name"]``)."""
    schema = validate_schema_name(schema)
    return ConnectionPool(
        conninfo,
        min_size=1,
        max_size=5,
        kwargs={"row_factory": dict_row, "options": f"-c search_path={schema},public"},
        open=True,
    )
