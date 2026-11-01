"""Persistência do histórico de conversa e do log de ferramentas.

O modelo de linguagem é stateless: a cada mensagem do cliente, recarregamos
o histórico do banco e reenviamos. Guardamos as mensagens no formato do
Ollama (role/content/tool_calls/tool_name), então elas voltam ao modelo sem
conversão. O histórico fica completo no banco; quem decide quanto dele cabe
no contexto do modelo é o agente (ver ``agent.py``).
"""

from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb


def create_conversation(conn: Connection, channel: str) -> str:
    row = conn.execute(
        "INSERT INTO conversations (channel) VALUES (%s) RETURNING conversation_id",
        (channel,),
    ).fetchone()
    return str(row["conversation_id"])


def conversation_exists(conn: Connection, conversation_id: str | None) -> bool:
    try:
        UUID(str(conversation_id))
    except ValueError:
        return False
    row = conn.execute(
        "SELECT 1 FROM conversations WHERE conversation_id = %s", (conversation_id,)
    ).fetchone()
    return row is not None


def load_messages(conn: Connection, conversation_id: str) -> list[dict]:
    """Mensagens no formato do modelo, em ordem."""
    rows = conn.execute(
        "SELECT message FROM chat_messages WHERE conversation_id = %s ORDER BY seq",
        (conversation_id,),
    ).fetchall()
    return [r["message"] for r in rows]


def load_visible_messages(conn: Connection, conversation_id: str) -> list[dict]:
    """Só o que aparece na tela: [{'role': 'user'|'assistant', 'text': ...}]."""
    rows = conn.execute(
        """SELECT role, visible_text FROM chat_messages
            WHERE conversation_id = %s AND visible_text IS NOT NULL
            ORDER BY seq""",
        (conversation_id,),
    ).fetchall()
    return [{"role": r["role"], "text": r["visible_text"]} for r in rows]


def append_messages(conn: Connection, conversation_id: str, messages: list[dict]) -> None:
    """Acrescenta mensagens ao final do histórico.

    Cada item: {"message": <dict no formato do modelo>, "visible_text": str | None}
    """
    if not messages:
        return
    # Trava a linha da conversa: duas requisições simultâneas não geram o mesmo seq.
    conn.execute("SELECT 1 FROM conversations WHERE conversation_id = %s FOR UPDATE", (conversation_id,))
    next_seq = conn.execute(
        "SELECT coalesce(max(seq), 0) + 1 AS next FROM chat_messages WHERE conversation_id = %s",
        (conversation_id,),
    ).fetchone()["next"]
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO chat_messages (conversation_id, seq, role, message, visible_text)
               VALUES (%s, %s, %s, %s, %s)""",
            [(conversation_id, next_seq + i, m["message"]["role"], Jsonb(m["message"]), m.get("visible_text"))
             for i, m in enumerate(messages)],
        )
    conn.execute("UPDATE conversations SET updated_at = now() WHERE conversation_id = %s", (conversation_id,))


def log_tool_calls(conn: Connection, conversation_id: str, calls: list[dict]) -> None:
    if not calls:
        return
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO tool_calls (conversation_id, tool_name, input, output, is_error, duration_ms)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            [(conversation_id, c["name"], Jsonb(c["input"]), Jsonb(c["output"]),
              c["is_error"], c["duration_ms"]) for c in calls],
        )
