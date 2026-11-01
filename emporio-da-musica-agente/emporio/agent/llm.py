"""Cliente do modelo de linguagem (Ollama, rodando localmente).

O agente conversa com o LLM só por esta classe. Para trocar de provedor
(ex.: uma API na nuvem), basta escrever outra classe com o mesmo método
``stream_chat`` — o resto do sistema não muda.

Usamos streaming: os tokens chegam à tela enquanto o modelo gera, o que faz
muita diferença na percepção de velocidade de um modelo local.
"""

import logging
import re
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
