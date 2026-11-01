# Exemplos de interação

As conversas desta pasta são geradas pelo agente **real** (nada é escrito à mão):

```bash
python -m scripts.gerar_exemplos            # todos os cenários
python -m scripts.gerar_exemplos --only 3   # só um cenário
```

Cada arquivo traz as mensagens do cliente, as respostas do agente, as ferramentas chamadas (com entrada e saída) e uma verificação automática das ferramentas esperadas para o cenário. Os cenários usam data/hora simulada, porque os pedidos da base são de out/2025 a mar/2026.

Os cenários estão definidos em `scripts/gerar_exemplos.py`.
