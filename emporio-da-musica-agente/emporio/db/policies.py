"""Consultas da base de conhecimento (seções do manual de políticas)."""

from psycopg import Connection


def list_sections(conn: Connection) -> list[dict]:
    """Índice do manual: slug, número, título e subtítulos (sem o conteúdo)."""
    return conn.execute(
        "SELECT slug, number, title, summary FROM policy_sections ORDER BY number"
    ).fetchall()


def get_sections(conn: Connection, slugs: list[str]) -> list[dict]:
    return conn.execute(
        "SELECT slug, number, title, content FROM policy_sections WHERE slug = ANY(%s) ORDER BY number",
        (slugs,),
    ).fetchall()
