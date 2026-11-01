# CLAUDE.md: contexto para continuar este projeto

> Este arquivo é lido automaticamente pelo Claude Code. Ele resume o que é o projeto, o que já está
> pronto e verificado, o que falta e as armadilhas conhecidas. **Leia inteiro antes de agir.**
> O projeto foi construído em 01/11/2026, em outra máquina, numa sessão com o Claude Code.

## 1. O que é

**Desafio técnico (fase 1) para a vaga de AI Engineer na Artefact.** O enunciado pede um **agente de
atendimento por mensagens de texto, em Python**, para a *Empório da Música*, loja fictícia de
instrumentos em Campo Grande/MS.

O agente deve:
- assumir a persona e o tom da loja;
- responder com base nos dados (CSVs → PostgreSQL) e no manual de políticas (PDF);
- saber quando consultar **dados** (preço, estoque, pedido) e quando consultar **políticas** (trocas, horários, pagamento);
- lidar com perguntas fora do escopo.

O projeto está em `emporio-da-musica-agente/`. Se o usuário já seguiu a Etapa 5 do `PENDENCIAS.md`,
ele está na raiz do repositório. O `README.md` do projeto explica tudo em detalhe, e o `PENDENCIAS.md`
é o checklist do usuário.

### Regras do enunciado (não violar)

- **Python** como linguagem principal.
- **Repositório público** no GitHub com **histórico de commits com progresso real**: nada de force-push nem de squash de tudo num commit só. **Não alterar o repositório depois do prazo.**
- O **README** precisa ter: como rodar, justificativa das decisões técnicas, limitações e o que faria com mais tempo, e **uso de assistentes de código** (o workflow do usuário).
- **De 3 a 5 conversas de exemplo** (`.md`, `.txt` ou imagem), ao menos uma **não trivial** (dados em tempo real ou regra de política).

## 2. Decisões já tomadas (não reverter sem o usuário pedir)

| Decisão | Motivo |
|---|---|
| **LLM: só Ollama (local)**, modelo padrão `qwen3:14b` | **Escolha explícita do usuário** (gratuito). **Não** proponha migrar para API paga. |
| Function calling com **loop próprio** (`emporio/agent/agent.py`), sem LangChain | fluxo pequeno, auditável; o painel da UI mostra cada ferramenta |
| **O LLM nunca escreve SQL**: 7 ferramentas com SQL fixo (`emporio/db/*.py`) | segurança (LGPD) e precisão |
| **Contas no código** (`emporio/domain/`): preço, PIX, parcelas, prazos, horário | LLM erra contas; o manual exige consultar o sistema |
| Políticas: **índice de seções** na descrição da ferramenta `consultar_politicas` (sem embeddings) | o manual tem só 10 seções (~3k tokens) |
| PostgreSQL, schema próprio **`emporio`**; as tabelas em `public` não são tocadas | dados tipados e com restrições |
| Manual curado em `data/politicas_da_loja.md` (fonte da base de conhecimento) | o PDF tem tabelas e inconsistências |

## 3. Mapa do código

```
emporio/domain/      regras puras (pricing, payments, store_hours, order_rules, data_quality, text)
emporio/etl/         transform.py (limpa CSVs + relatório de qualidade), policies.py (md -> seções), loader.py
emporio/db/          schema.sql, connection.py (pool, search_path), catalog/orders/policies/conversations/tickets.py
emporio/agent/       prompts.py (persona), tools.py (7 ferramentas), llm.py (OllamaLLM, streaming), agent.py (loop)
emporio/api/main.py  FastAPI: POST /api/chat/stream (SSE), POST /api/chat, GET /api/conversations/{id}, /api/tickets, /api/health
emporio/cli.py       chat no terminal (--debug, --agora)
web/                 front-end HTML/CSS/JS puro (streaming, painel "Bastidores", aba "Chamados")
scripts/setup_db.py  cria schema e carrega dados   |   scripts/gerar_exemplos.py  5 cenários -> exemplos/*.md
tests/               pytest (sem LLM)
```

## 4. O que JÁ foi verificado na máquina original

Essa máquina não tinha pip, Ollama nem GPU.

- ✅ **24 testes** de domínio e ETL passando (`test_pricing_payments`, `test_store_hours`, `test_order_rules`, `test_etl`).
- ✅ `schema.sql` aplicado num PostgreSQL 16 real; dados carregados (65 produtos, 20 pedidos, 10 seções do manual, 4 promoções ativas).
- ✅ Consultas SQL de busca (trigramas), pedidos, verificação por e-mail/telefone e promoções testadas direto no `psql`.
- ✅ Gravação do chat testada no banco (conversations, chat_messages, tool_calls, tickets).
- ✅ Todo o Python compila; o JS passou em `node --check`.

## 5. O que NUNCA foi executado (verifique primeiro)

- ❌ `emporio/agent/llm.py` contra um **Ollama real**, incluindo o streaming com `tool_calls` e o parâmetro `think`.
- ❌ O **loop do agente**, a **API FastAPI/SSE**, o **front-end** no navegador e a **CLI**.
- ❌ `tests/test_agent_parts.py` (precisa do pydantic instalado).
- ❌ `scripts/setup_db.py` via psycopg (só a versão equivalente em SQL foi testada).

**Se der erro na primeira execução, é provavelmente algo pequeno. Corrija na causa.** Pontos mais prováveis:

| Ponto | O que conferir |
|---|---|
| `llm.py`: `chunk.message.tool_calls` | o formato dos argumentos (Mapping) pode variar; o código já converte com `dict(...)` |
| Modelo sem suporte a `think` | o código tenta de novo sem o parâmetro (`_send_think`) |
| `connection.py`: `options="-c search_path=..."` | se a conexão falhar, confira esse parâmetro do pool |
| Windows | emojis na CLI podem exigir `PYTHONUTF8=1`; fuso horário exige o pacote `tzdata` (está no requirements) |

## 6. Próximos passos (na ordem)

1. **Ambiente:** venv → `pip install -r requirements-dev.txt` → `ollama pull qwen3:14b` → criar o banco → `.env` (a partir do `.env.example`) → `python -m scripts.setup_db` → `pytest`. Os detalhes estão no README, seção "Como rodar". O `.env` **não** está no Git: o usuário precisa criá-lo.
2. **Teste manual:** `uvicorn emporio.api.main:app` → <http://localhost:8000>. Use as perguntas e os valores esperados da seção 8.
3. **Ajustes**, se o modelo errar. Ordem sugerida:
   1. `LLM_THINK=true`;
   2. um modelo maior;
   3. o prompt (`prompts.py`) e as descrições das ferramentas (`tools.py`).

   **Cada ajuste é um commit pequeno.**
4. **Exemplos:** `python -m scripts.gerar_exemplos` → revise cada `exemplos/*.md` (verificação automática ✅, preços batendo com a saída das ferramentas). Para regerar um cenário: `--only N`.
5. **README, seção "Uso de assistentes de código":** preencher os trechos entre colchetes e remover o aviso ✏️. **Pergunte ao usuário** o que ele fez e escreva com as palavras dele. Não invente.
6. **Repositório:** deixar o README visível na raiz do GitHub (Etapa 5 do `PENDENCIAS.md`), conferir que não há segredos (`git ls-files`), apagar o `PENDENCIAS.md` antes da entrega.

## 7. Armadilhas: NÃO faça

- **Nunca escreva conversas de exemplo à mão** nem edite respostas do agente nos `.md`. Elas têm de sair do `scripts/gerar_exemplos.py`. Se ficarem ruins, ajuste o sistema e gere de novo.
- **Nunca versione segredos.** Já aconteceu uma vez: o arquivo `DB HOST localhost DB PORT.txt`, com a senha, foi para o GitHub e depois saiu do controle de versão. O `.gitignore` da raiz cobre esse arquivo, o `.env` e a pasta do enunciado.
- **Nunca faça force-push nem reescreva o histórico** (regra do enunciado). Commits só com o OK do usuário.
- **Não remova `to_ollama_parameters`** (`tools.py`). A biblioteca `ollama-python` aceita só `type`, `items`, `description` e `enum` em cada parâmetro e **descarta o resto em silêncio**. Um `int | None` do Pydantic (`anyOf`) chegaria ao modelo sem tipo.
- **Não reduza `LLM_NUM_CTX`** abaixo de ~12k. O padrão do Ollama é pequeno e cortaria o system prompt sem avisar.
- **Não coloque data/hora no system prompt.** Ele é fixo, e o contexto dinâmico vai na mensagem do usuário (`build_user_turn`), o que preserva o cache de prefixo do Ollama. As marcações `[CONTEXTO DO SISTEMA]` são removidas do texto do cliente (anti-falsificação).
- **Não deixe o LLM calcular preço ou prazo.** As ferramentas devolvem valores já formatados vindos de `emporio/domain/`.
- **Não "conserte" os 6 produtos com descrição inconsistente** (135, 137, 139, 140, 142, 144) passando a confiar na descrição. Nome e specs são a fonte da verdade; está documentado no README.
- As inconsistências do manual já estão resolvidas e documentadas (WhatsApp 3341-4444 × 3321-4500, e-mail com acento, parcela mínima). Não reabra a questão.

## 8. Valores esperados (para conferir o agente)

| Pergunta / caso | Resultado correto |
|---|---|
| Preço do **Takamine GD20** (id 95) | **R$ 2.199,00**; PIX **R$ 2.089,05**; a promoção de 12% ("Oferta Especial") está **inativa** |
| Violões disponíveis até R$ 1.000 (categoria 5) | **12** produtos; o mais barato é o Tagima Memphis AC-39 (R$ 429,90) |
| Promoções ativas | 4: produtos 90 (18%), 94 (8%), 121 (20%), 127 (10%) |
| **Pedido 7** + `leticia.rocha@jmail.com`, com `SIMULATED_NOW=2026-02-20T15:00` | entregue (previsto 17/02/2026), **3 dias** → dentro do arrependimento de 7 dias (prazo 24/02/2026) |
| **Pedido 8** + `anacarol.ferreira@coldmail.com` | enviado, rastreio **BRJL5544332BR**, previsão 28/02/2026 |
| Pedido com e-mail errado | resposta genérica, sem revelar se o pedido existe |
| Giannini GF-3D (id 96) | **esgotado**; o agente sugere alternativas |
| Endereço | Rua 14 de Maio, 3200, Centro, Campo Grande/MS, CEP 79202-333 |
| Cordas / amplificador | a loja não vende acessórios; o agente não inventa loja parceira |
| Domingo ou feriado | loja fechada; o contexto informa a próxima abertura |
