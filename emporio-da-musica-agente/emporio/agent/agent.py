"""Loop agêntico: modelo <-> ferramentas, com memória da conversa.

Abordagem: function calling (estilo ReAct). A cada mensagem do cliente:

    1. Carrega o histórico da conversa do banco (últimas N trocas).
    2. Envia ao modelo: system prompt + histórico + mensagem nova (com contexto
       de data/hora e status da loja).
    3. Se o modelo pedir ferramentas, executa e devolve os resultados.
       Repete até ele responder em texto (ou até AGENT_MAX_STEPS).
    4. Salva a troca inteira (mensagem, chamadas de ferramenta, resposta).

Por que um loop manual em vez de um framework (LangChain etc.)? O fluxo é
pequeno e assim cada passo fica visível e debugável: dá para mostrar na tela
quais ferramentas foram chamadas, com quais argumentos, e auditar tudo no
banco. Ver README, "Decisões técnicas".

O método principal é um *gerador* de eventos (``stream_reply``). A API usa
os eventos para streaming na tela; a CLI e os testes usam ``reply``, que só
espera o evento final.
"""

import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass, field

from psycopg_pool import ConnectionPool

from emporio.agent.llm import LLMError, LLMResponse, OllamaLLM
from emporio.agent.prompts import build_system_prompt, build_user_turn
from emporio.agent.tools import ToolContext, ToolRegistry, build_registry
from emporio.clock import Clock
from emporio.config import Settings
from emporio.db import catalog, conversations, policies
from emporio.domain.store_hours import store_status

logger = logging.getLogger(__name__)

FALLBACK_REPLY = ("Desculpa, me enrolei aqui para montar a resposta. 😅 Pode repetir a pergunta "
                  "de outro jeito? Se preferir, posso abrir um chamado para alguém da equipe te atender.")
MAX_MESSAGE_CHARS = 2000


@dataclass
class AgentReply:
    conversation_id: str
    text: str
    tool_calls: list[dict] = field(default_factory=list)
    thinking: str = ""
    stats: dict = field(default_factory=dict)


class StoreAgent:
    def __init__(self, settings: Settings, pool: ConnectionPool, clock: Clock,
                 llm: OllamaLLM | None = None) -> None:
        self._settings = settings
        self._pool = pool
        self._clock = clock
        self._llm = llm or OllamaLLM(settings)

        # Prompt e ferramentas são montados UMA vez, a partir do banco
        # (categorias e índice do manual), e ficam fixos — ver prompts.py.
        with pool.connection() as conn:
            categories = catalog.list_categories(conn)
            sections = policies.list_sections(conn)
        if not sections:
            raise RuntimeError("Base de políticas vazia. Rode antes: python -m scripts.setup_db")
        self._system_prompt = build_system_prompt(categories)
        self._registry: ToolRegistry = build_registry(sections)
        self._tool_definitions = self._registry.definitions()

    # ------------------------------------------------------------------ API pública
    @property
    def model(self) -> str:
        return self._llm.model

    def reply(self, text: str, conversation_id: str | None = None, channel: str = "cli") -> AgentReply:
        """Versão sem streaming: devolve só a resposta final."""
        for event in self.stream_reply(text, conversation_id, channel):
            if event["type"] == "done":
                return AgentReply(
                    conversation_id=event["conversation_id"], text=event["text"],
                    tool_calls=event["tool_calls"], thinking=event["thinking"], stats=event["stats"],
                )
            if event["type"] == "error":
                raise LLMError(event["message"])
        raise RuntimeError("O agente terminou sem resposta.")

    def stream_reply(self, text: str, conversation_id: str | None = None,
                     channel: str = "web") -> Iterator[dict]:
        """Processa uma mensagem do cliente gerando eventos.

        Eventos: start, token, thinking, tool_start, tool_end, done, error.
        """
        text = (text or "").strip()[:MAX_MESSAGE_CHARS]
        started = time.perf_counter()

        with self._pool.connection() as conn:
            if not conversations.conversation_exists(conn, conversation_id):
                conversation_id = conversations.create_conversation(conn, channel)
            history = conversations.load_messages(conn, conversation_id)
        yield {"type": "start", "conversation_id": conversation_id}

        status_text = store_status(self._clock.now()).describe()
        new_messages: list[dict] = [{
            "message": {"role": "user", "content": build_user_turn(text, status_text)},
            "visible_text": text,
        }]
        model_messages = ([{"role": "system", "content": self._system_prompt}]
                          + self._history_window(history)
                          + [new_messages[0]["message"]])

        ctx = ToolContext(pool=self._pool, clock=self._clock, conversation_id=conversation_id)
        tool_log: list[dict] = []
        thinking = ""
        prompt_tokens = output_tokens = 0
        final_text = ""

        try:
            for step in range(self._settings.agent_max_steps):
                # Na última rodada não oferecemos ferramentas: o modelo é obrigado a responder.
                last_step = step == self._settings.agent_max_steps - 1
                tools = None if last_step else self._tool_definitions

                response: LLMResponse | None = None
                for kind, payload in self._llm.stream_chat(model_messages, tools):
                    if kind == "done":
                        response = payload
                    else:
                        yield {"type": kind, "text": payload, "step": step}
                if response is None:
                    raise LLMError("O modelo encerrou a resposta inesperadamente.")
                thinking += response.thinking
                prompt_tokens += response.prompt_tokens
                output_tokens += response.output_tokens

                if response.tool_calls and not last_step:
                    assistant_msg = {
                        "role": "assistant",
                        "content": response.content,
                        "tool_calls": [{"function": {"name": c["name"], "arguments": c["arguments"]}}
                                       for c in response.tool_calls],
                    }
                    model_messages.append(assistant_msg)
                    new_messages.append({"message": assistant_msg})

                    for call in response.tool_calls:
                        yield {"type": "tool_start", "name": call["name"], "input": call["arguments"]}
                        result = self._registry.run(ctx, call["name"], call["arguments"])
                        trace = {"name": result.name, "input": result.input, "output": result.output,
                                 "is_error": result.is_error, "duration_ms": result.duration_ms}
                        tool_log.append(trace)
                        yield {"type": "tool_end", **trace}

                        tool_msg = result.to_message()
                        model_messages.append(tool_msg)
                        new_messages.append({"message": tool_msg})
                    continue

                final_text = response.content.strip()
                break
        except LLMError as exc:
            # Nada é salvo: o histórico continua consistente e o cliente pode tentar de novo.
            yield {"type": "error", "message": str(exc), "conversation_id": conversation_id}
            return

        if not final_text:
            logger.warning("Modelo terminou sem texto (conversa %s).", conversation_id)
            final_text = FALLBACK_REPLY
        new_messages.append({"message": {"role": "assistant", "content": final_text},
                             "visible_text": final_text})

        with self._pool.connection() as conn:  # uma transação: ou salva tudo, ou nada
            conversations.append_messages(conn, conversation_id, new_messages)
            conversations.log_tool_calls(conn, conversation_id, tool_log)

        yield {
            "type": "done",
            "conversation_id": conversation_id,
            "text": final_text,
            "tool_calls": tool_log,
            "thinking": thinking.strip(),
            "stats": {
                "model": self.model,
                "seconds": round(time.perf_counter() - started, 1),
                "llm_calls": min(step + 1, self._settings.agent_max_steps),
                "prompt_tokens": prompt_tokens,
                "output_tokens": output_tokens,
            },
        }

    # ------------------------------------------------------------------ internos
    def _history_window(self, history: list[dict]) -> list[dict]:
        """Últimas N trocas da conversa.

        Modelos locais têm janela de contexto limitada (LLM_NUM_CTX). Cortamos
        sempre no início de uma troca (mensagem do cliente), para nunca deixar
        um resultado de ferramenta "órfão", sem a chamada que o originou.
        """
        user_positions = [i for i, m in enumerate(history) if m.get("role") == "user"]
        max_turns = self._settings.history_max_turns
        if len(user_positions) <= max_turns:
            return history
        return history[user_positions[-max_turns]:]
