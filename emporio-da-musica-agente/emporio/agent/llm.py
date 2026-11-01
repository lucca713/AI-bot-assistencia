"""Clientes do modelo de linguagem.

O agente conversa com o LLM só por estas classes, que têm o mesmo método
``stream_chat``:

- ``OllamaLLM``: modelo local via Ollama (padrão; os dados não saem da máquina);
- ``OpenAICompatibleLLM``: APIs na nuvem compatíveis com OpenAI e com plano
  gratuito (Groq, Gemini), para quem não tem GPU ou não pode instalar o Ollama.

``create_llm`` escolhe pelo ``LLM_PROVIDER`` do .env; o resto do sistema não muda.

Usamos streaming: os tokens chegam à tela enquanto o modelo gera, o que faz
muita diferença na percepção de velocidade de um modelo local.
"""

import json
import logging
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx
import ollama

from emporio.config import Settings

logger = logging.getLogger(__name__)

# Alguns modelos "pensantes" deixam tags <think> no texto mesmo com o modo desligado.
_THINK_TAGS = re.compile(r"<think>.*?</think>", re.DOTALL)


@dataclass
class LLMResponse:
    content: str = ""
    thinking: str = ""
    tool_calls: list[dict] = field(default_factory=list)  # [{"name": str, "arguments": dict}]
    prompt_tokens: int = 0
    output_tokens: int = 0
    done_reason: str | None = None


class LLMError(Exception):
    """Falha ao falar com o modelo, com mensagem pronta para mostrar ao usuário."""


def strip_think_tags(text: str) -> str:
    return _THINK_TAGS.sub("", text).strip()


class OllamaLLM:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = ollama.Client(host=settings.ollama_host, timeout=settings.llm_timeout_s)
        # Nem todo modelo aceita o parâmetro "think". Se o Ollama recusar,
        # desligamos e passamos a não enviá-lo.
        self._send_think = True

    @property
    def model(self) -> str:
        return self._settings.llm_model

    def ping(self) -> None:
        self._client.list()

    def stream_chat(self, messages: list[dict], tools: list[dict] | None) -> Iterator[tuple[str, Any]]:
        """Gera eventos ("token", texto) e ("thinking", texto) e termina com ("done", LLMResponse)."""
        try:
            yield from self._stream(messages, tools)
        except ollama.ResponseError as exc:
            if self._send_think and "think" in str(exc.error).lower():
                logger.info("Modelo %s não suporta 'think'; repetindo sem o parâmetro.", self.model)
                self._send_think = False
                yield from self._stream(messages, tools)
                return
            if exc.status_code == 404:
                raise LLMError(f"O modelo '{self.model}' não está instalado no Ollama. "
                               f"Rode: ollama pull {self.model}") from exc
            raise LLMError(f"Erro retornado pelo Ollama: {exc.error}") from exc
        except httpx.TimeoutException as exc:
            raise LLMError("O modelo demorou demais para responder. Tente de novo ou use um modelo "
                           "menor (LLM_MODEL no .env).") from exc
        except (ConnectionError, httpx.ConnectError) as exc:
            raise LLMError(f"Não consegui conectar ao Ollama em {self._settings.ollama_host}. "
                           "Verifique se ele está rodando (comando: ollama serve).") from exc

    def _stream(self, messages: list[dict], tools: list[dict] | None) -> Iterator[tuple[str, Any]]:
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                # Temperatura baixa: atendimento pede respostas consistentes, não criativas.
                "temperature": self._settings.llm_temperature,
                # O padrão do Ollama é pequeno; sem isso o começo do prompt
                # (persona e regras) seria cortado em silêncio.
                "num_ctx": self._settings.llm_num_ctx,
            },
            "keep_alive": self._settings.llm_keep_alive,
        }
        if tools:
            kwargs["tools"] = tools
        if self._send_think:
            kwargs["think"] = self._settings.llm_think

        response = LLMResponse()
        for chunk in self._client.chat(**kwargs):
            message = chunk.message
            if message.thinking:
                response.thinking += message.thinking
                yield "thinking", message.thinking
            if message.content:
                response.content += message.content
                yield "token", message.content
            for call in message.tool_calls or []:
                response.tool_calls.append({
                    "name": call.function.name,
                    "arguments": dict(call.function.arguments or {}),
                })
            if chunk.done:
                response.prompt_tokens = chunk.prompt_eval_count or 0
                response.output_tokens = chunk.eval_count or 0
                response.done_reason = chunk.done_reason

        response.content = strip_think_tags(response.content)
        yield "done", response


# ---------------------------------------------------------------------------
# APIs compatíveis com OpenAI (Groq, Gemini...): alternativa gratuita na nuvem
# ---------------------------------------------------------------------------

# Provedores com plano gratuito e endpoint compatível com a API da OpenAI
# (o modelo padrão de cada um fica em config.DEFAULT_MODELS).
PROVIDER_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
}
# Planos gratuitos limitam tokens por minuto: esperamos um pouco e tentamos de novo.
_MAX_RATE_LIMIT_WAIT_S = 30


def to_openai_messages(messages: list[dict]) -> list[dict]:
    """Converte o histórico (formato do Ollama) para o formato da OpenAI.

    A OpenAI exige um id em cada chamada de ferramenta (repetido na mensagem de
    resultado) e os argumentos como string JSON. Os ids são gerados aqui, na
    ordem das mensagens, então o histórico salvo no banco não muda.
    """
    converted: list[dict] = []
    pending_ids: list[str] = []
    for i, msg in enumerate(messages):
        role = msg.get("role")
        if role == "assistant" and msg.get("tool_calls"):
            calls = [{
                "id": f"call_{i}_{j}",
                "type": "function",
                "function": {
                    "name": call["function"]["name"],
                    "arguments": json.dumps(call["function"].get("arguments") or {}, ensure_ascii=False),
                },
            } for j, call in enumerate(msg["tool_calls"])]
            pending_ids = [c["id"] for c in calls]
            converted.append({"role": "assistant", "content": msg.get("content") or None, "tool_calls": calls})
        elif role == "tool":
            call_id = pending_ids.pop(0) if pending_ids else f"call_{i}_orphan"
            converted.append({"role": "tool", "tool_call_id": call_id, "content": msg.get("content", "")})
        else:
            converted.append({"role": role, "content": msg.get("content", "")})
    return converted


class OpenAICompatibleLLM:
    """Mesmo contrato do ``OllamaLLM``, falando com uma API compatível com OpenAI."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = (settings.llm_base_url
                          or PROVIDER_BASE_URLS.get(settings.llm_provider, "")).rstrip("/")
        if not self._base_url:
            raise LLMError(f"Defina LLM_BASE_URL para o provedor '{settings.llm_provider}'.")
        self._client = httpx.Client(timeout=settings.llm_timeout_s,
                                    headers={"Authorization": f"Bearer {settings.llm_api_key}"})

    @property
    def model(self) -> str:
        return self._settings.llm_model

    def ping(self) -> None:
        self._client.get(f"{self._base_url}/models").raise_for_status()

    def stream_chat(self, messages: list[dict], tools: list[dict] | None) -> Iterator[tuple[str, Any]]:
        """Gera os mesmos eventos do ``OllamaLLM`` (sem "thinking")."""
        if not self._settings.llm_api_key:
            raise LLMError(f"Falta a chave da API do provedor '{self._settings.llm_provider}': "
                           "preencha LLM_API_KEY no .env.")
        body: dict = {
            "model": self.model,
            "messages": to_openai_messages(messages),
            "temperature": self._settings.llm_temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            body["tools"] = tools
        try:
            yield from self._stream(body)
        except httpx.TimeoutException as exc:
            raise LLMError("O modelo demorou demais para responder. Tente de novo.") from exc
        except httpx.TransportError as exc:
            raise LLMError(f"Não consegui conectar a {self._base_url}: {exc}") from exc

    def _stream(self, body: dict, attempt: int = 0) -> Iterator[tuple[str, Any]]:
        with self._client.stream("POST", f"{self._base_url}/chat/completions", json=body) as resp:
            if resp.status_code < 400:
                yield from self._read_events(resp)
                return
            detail = resp.read().decode("utf-8", "replace")[:500]
            if resp.status_code == 401:
                raise LLMError("Chave da API inválida (LLM_API_KEY no .env).")
            if resp.status_code != 429:
                raise LLMError(f"Erro {resp.status_code} do provedor: {detail}")
            if attempt >= 2:
                raise LLMError("Limite gratuito do provedor atingido. Espere um minuto e tente de novo.")
            try:
                wait = float(resp.headers.get("retry-after") or 10)
            except ValueError:
                wait = 10.0
        wait = min(wait, _MAX_RATE_LIMIT_WAIT_S)
        logger.warning("Limite de uso do provedor atingido; tentando de novo em %.0fs.", wait)
        time.sleep(wait)
        yield from self._stream(body, attempt + 1)

    @staticmethod
    def _read_events(resp: httpx.Response) -> Iterator[tuple[str, Any]]:
        response = LLMResponse()
        partial_calls: dict[int, dict] = {}  # os argumentos chegam em pedaços, por índice
        for line in resp.iter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            chunk = json.loads(data)
            usage = chunk.get("usage") or (chunk.get("x_groq") or {}).get("usage")
            if usage:
                response.prompt_tokens = usage.get("prompt_tokens") or 0
                response.output_tokens = usage.get("completion_tokens") or 0
            for choice in chunk.get("choices") or []:
                delta = choice.get("delta") or {}
                if delta.get("content"):
                    response.content += delta["content"]
                    yield "token", delta["content"]
                for call in delta.get("tool_calls") or []:
                    slot = partial_calls.setdefault(call.get("index", len(partial_calls)),
                                                    {"name": "", "arguments": ""})
                    fn = call.get("function") or {}
                    slot["name"] += fn.get("name") or ""
                    slot["arguments"] += fn.get("arguments") or ""
                if choice.get("finish_reason"):
                    response.done_reason = choice["finish_reason"]

        for _, call in sorted(partial_calls.items()):
            # Argumentos inválidos seguem como texto: o ToolRegistry tenta interpretar
            # e, se não der, devolve o erro ao modelo.
            try:
                arguments = json.loads(call["arguments"] or "{}")
            except json.JSONDecodeError:
                arguments = call["arguments"]
            response.tool_calls.append({"name": call["name"], "arguments": arguments})
        response.content = strip_think_tags(response.content)
        yield "done", response


def create_llm(settings: Settings) -> OllamaLLM | OpenAICompatibleLLM:
    """Escolhe o cliente pelo LLM_PROVIDER do .env (padrão: ollama)."""
    if settings.llm_provider == "ollama":
        return OllamaLLM(settings)
    return OpenAICompatibleLLM(settings)
