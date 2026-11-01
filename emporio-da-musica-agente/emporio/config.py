"""Configuração da aplicação, lida de variáveis de ambiente (arquivo .env).

Todas as opções estão documentadas em ``.env.example``.
"""

import os
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
WEB_DIR = PROJECT_ROOT / "web"
STORE_TIMEZONE = ZoneInfo("America/Campo_Grande")

load_dotenv(PROJECT_ROOT / ".env")


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _env_bool(name: str, default: bool) -> bool:
    return _env(name, str(default)).strip().lower() in ("1", "true", "sim", "yes")


@dataclass(frozen=True)
class Settings:
    # Banco de dados
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str
    db_schema: str

    # LLM (Ollama)
    ollama_host: str
    llm_model: str
    llm_temperature: float
    llm_num_ctx: int          # janela de contexto em tokens (o padrão do Ollama é pequeno demais)
    llm_think: bool           # modo "pensar" (modelos como qwen3); melhora decisões, aumenta latência
    llm_timeout_s: float
    llm_keep_alive: str       # quanto tempo o modelo fica carregado na memória após uso

    # Agente
    agent_max_steps: int      # máximo de rodadas modelo->ferramenta por mensagem
    history_max_turns: int    # quantas trocas anteriores vão para o contexto do modelo

    # Relógio simulado (os pedidos da base são de out/2025 a mar/2026)
    simulated_now: datetime | None

    @property
    def db_conninfo(self) -> str:
        # make_conninfo escapa valores com espaço ou aspas (ex.: senhas).
        return make_conninfo(host=self.db_host, port=self.db_port, dbname=self.db_name,
                             user=self.db_user, password=self.db_password)


def parse_simulated_now(raw: str | None) -> datetime | None:
    """'2026-02-20T10:30' -> datetime no fuso da loja."""
    if not raw:
        return None
    parsed = datetime.fromisoformat(raw)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=STORE_TIMEZONE)


@lru_cache
def get_settings() -> Settings:
    return Settings(
        db_host=_env("DB_HOST", "localhost"),
        db_port=int(_env("DB_PORT", "5432")),
        db_user=_env("DB_USERNAME", "postgres"),
        db_password=_env("DB_PASSWORD", ""),
        # DB_NAME é aceito como alternativa (nome comum em outros projetos).
        db_name=_env("DB_DATABASE", _env("DB_NAME", "loja_musica")),
        db_schema=_env("DB_SCHEMA", "emporio"),
        ollama_host=_env("OLLAMA_HOST", "http://localhost:11434"),
        llm_model=_env("LLM_MODEL", "qwen3:14b"),
        llm_temperature=float(_env("LLM_TEMPERATURE", "0.2")),
        llm_num_ctx=int(_env("LLM_NUM_CTX", "16384")),
        llm_think=_env_bool("LLM_THINK", False),
        llm_timeout_s=float(_env("LLM_TIMEOUT_S", "300")),
        llm_keep_alive=_env("LLM_KEEP_ALIVE", "30m"),
        agent_max_steps=int(_env("AGENT_MAX_STEPS", "6")),
        history_max_turns=int(_env("HISTORY_MAX_TURNS", "8")),
        simulated_now=parse_simulated_now(os.getenv("SIMULATED_NOW")),
    )
