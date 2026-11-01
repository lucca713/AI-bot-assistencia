"""O agente de atendimento.

- ``prompts``  persona e regras (system prompt)
- ``tools``    ferramentas que o modelo pode chamar (function calling)
- ``llm``      cliente do modelo de linguagem (Ollama)
- ``agent``    loop agêntico: modelo <-> ferramentas, com persistência
"""
