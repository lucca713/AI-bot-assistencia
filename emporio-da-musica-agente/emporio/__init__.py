"""Empório da Música — agente de atendimento ao cliente.

Visão geral dos pacotes (de dentro para fora):

- ``emporio.domain``  regras de negócio puras (preço, parcelamento, horário,
                      prazos de troca). Não dependem de banco nem de LLM, por
                      isso são fáceis de testar.
- ``emporio.etl``     tratamento dos CSVs e do manual de políticas.
- ``emporio.db``      acesso ao PostgreSQL (schema, conexões e consultas).
- ``emporio.agent``   o agente: prompt, ferramentas e o loop com o modelo (Ollama).
- ``emporio.api``     API HTTP (FastAPI) que também serve o front-end.
- ``emporio.cli``     interface de linha de comando.
"""
