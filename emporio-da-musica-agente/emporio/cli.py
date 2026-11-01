"""Conversa com o agente pelo terminal.

Uso:
    python -m emporio.cli                          # conversa normal
    python -m emporio.cli --debug                  # mostra as ferramentas chamadas
    python -m emporio.cli --agora 2026-02-20T10:30 # simula data/hora (ver README)

Comandos durante a conversa: /nova (nova conversa), /sair
"""

import argparse
import json

from emporio.agent.agent import StoreAgent
from emporio.clock import Clock
from emporio.config import get_settings, parse_simulated_now
from emporio.db.connection import create_pool

DIM, BOLD, CYAN, YELLOW, RESET = "\033[2m", "\033[1m", "\033[36m", "\033[33m", "\033[0m"


def main() -> None:
    parser = argparse.ArgumentParser(description="Agente de atendimento da Empório da Música")
    parser.add_argument("--debug", action="store_true", help="mostra chamadas de ferramentas")
    parser.add_argument("--agora", help="data/hora simulada, ex.: 2026-02-20T10:30")
    args = parser.parse_args()

    settings = get_settings()
    clock = Clock(parse_simulated_now(args.agora) or settings.simulated_now)
    pool = create_pool(settings.db_conninfo, settings.db_schema)
    agent = StoreAgent(settings, pool, clock)

    print(f"{BOLD}Empório da Música — atendimento virtual{RESET} {DIM}(modelo: {agent.model}){RESET}")
    if clock.is_simulated:
        print(f"{DIM}Relógio simulado: {clock.now():%d/%m/%Y %H:%M}{RESET}")
    print(f"{DIM}Comandos: /nova, /sair{RESET}\n")

    conversation_id = None
    try:
        while True:
            try:
                text = input(f"{BOLD}Você:{RESET} ").strip()
            except EOFError:
                break
            if not text:
                continue
            if text == "/sair":
                break
            if text == "/nova":
                conversation_id = None
                print(f"{DIM}(nova conversa){RESET}\n")
                continue

            print(f"{CYAN}{BOLD}Tom:{RESET} ", end="", flush=True)
            streamed_any = False
            for event in agent.stream_reply(text, conversation_id, channel="cli"):
                kind = event["type"]
                if kind == "start":
                    conversation_id = event["conversation_id"]
                elif kind == "token":
                    print(event["text"], end="", flush=True)
                    streamed_any = True
                elif kind == "tool_start":
                    if streamed_any:  # texto gerado antes da ferramenta não é a resposta final
                        print()
                        streamed_any = False
                    if args.debug:
                        print(f"\n{YELLOW}  -> {event['name']}({json.dumps(event['input'], ensure_ascii=False)}){RESET}")
                elif kind == "tool_end" and args.debug:
                    preview = json.dumps(event["output"], ensure_ascii=False)
                    print(f"{DIM}  <- {preview[:300]}{'...' if len(preview) > 300 else ''}{RESET}")
                elif kind == "done":
                    if not streamed_any:
                        print(event["text"], end="")
                    stats = event["stats"]
                    print(f"\n{DIM}({stats['seconds']}s, {stats['llm_calls']} chamada(s) ao modelo){RESET}\n")
                elif kind == "error":
                    print(f"\n{YELLOW}Erro: {event['message']}{RESET}\n")
    finally:
        pool.close()


if __name__ == "__main__":
    main()
