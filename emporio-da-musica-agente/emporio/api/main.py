"""API HTTP + front-end.

Rodar:  uvicorn emporio.api.main:app --reload
Abrir:  http://localhost:8000

Rotas:
    POST /api/chat/stream          envia mensagem; resposta em streaming (Server-Sent Events)
    POST /api/chat                 envia mensagem; resposta completa em JSON (útil para testes/curl)
    GET  /api/conversations/{id}   histórico visível de uma conversa (para recarregar a tela)
    GET  /api/store-status         loja aberta/fechada agora
    GET  /api/tickets              chamados abertos pelo agente (visão da equipe)
    GET  /api/health               saúde do banco e do Ollama
    GET  /                         front-end (pasta web/)
"""

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from emporio.agent.agent import MAX_MESSAGE_CHARS, StoreAgent
from emporio.agent.llm import LLMError
from emporio.clock import Clock
from emporio.config import WEB_DIR, get_settings
from emporio.db import conversations, tickets
from emporio.db.connection import create_pool
from emporio.domain.store_hours import store_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

state: dict = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Abre o pool de conexões e monta o agente uma vez, na subida do servidor."""
    settings = get_settings()
    pool = create_pool(settings.db_conninfo, settings.db_schema)
    clock = Clock(settings.simulated_now)
    state.update(settings=settings, pool=pool, clock=clock, agent=StoreAgent(settings, pool, clock))
    if clock.is_simulated:
        logging.getLogger(__name__).info("Relógio SIMULADO: %s", settings.simulated_now.isoformat())
    yield
    pool.close()


app = FastAPI(title="Empório da Música — Agente de Atendimento", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    conversation_id: str | None = None


def _sse(event: dict) -> str:
    """Formata um evento no padrão Server-Sent Events."""
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    # Endpoint síncrono de propósito: o FastAPI roda geradores síncronos numa
    # thread separada, então o servidor continua atendendo outras requisições.
    agent: StoreAgent = state["agent"]
    events = (_sse(e) for e in agent.stream_reply(req.message, req.conversation_id, channel="web"))
    return StreamingResponse(events, media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    try:
        reply = state["agent"].reply(req.message, req.conversation_id, channel="api")
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"conversation_id": reply.conversation_id, "reply": reply.text,
            "tool_calls": reply.tool_calls, "stats": reply.stats}


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str) -> dict:
    with state["pool"].connection() as conn:
        if not conversations.conversation_exists(conn, conversation_id):
            raise HTTPException(status_code=404, detail="Conversa não encontrada")
        messages = conversations.load_visible_messages(conn, conversation_id)
    return {"conversation_id": conversation_id, "messages": messages}


@app.get("/api/store-status")
def get_store_status() -> dict:
    status = store_status(state["clock"].now())
    return {"is_open": status.is_open, "description": status.describe(),
            "simulated_clock": state["clock"].is_simulated}


@app.get("/api/tickets")
def get_tickets() -> dict:
    with state["pool"].connection() as conn:
        return {"tickets": tickets.list_tickets(conn)}


@app.get("/api/health")
def health() -> dict:
    result = {"database": "ok", "model": state["agent"].model, "ollama": "ok"}
    try:
        with state["pool"].connection() as conn:
            conn.execute("SELECT 1")
    except Exception as exc:  # noqa: BLE001
        result["database"] = f"erro: {exc}"
    try:
        import ollama
        ollama.Client(host=state["settings"].ollama_host, timeout=5).list()
    except Exception as exc:  # noqa: BLE001
        result["ollama"] = f"erro: {exc}"
    return result


# O front-end é servido pela mesma aplicação (montado por último para não
# "engolir" as rotas /api).
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
