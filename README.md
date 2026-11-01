# 🎸 Empório da Música: agente de atendimento com IA

Agente de atendimento por mensagens de texto para a **Empório da Música**, loja (fictícia) de instrumentos musicais em Campo Grande/MS. Desenvolvido em **Python** como desafio técnico para a vaga de AI Engineer.

O agente responde dúvidas recorrentes dos clientes sobre produtos, preços, disponibilidade, pedidos, trocas, pagamento, frete e horários. Ele consulta **dados reais da operação** (PostgreSQL) e o **manual de políticas da loja**, com a persona e o tom de voz definidos pela própria loja.

## Como rodar (passo a passo)

Você vai precisar de **Python 3.10+**, **PostgreSQL 13+** e uma **chave gratuita do Gemini**. Não precisa de GPU.

**1. Baixe o projeto e instale as dependências**

```bash
git clone https://github.com/lucca713/AI-bot-assistencia.git
cd AI-bot-assistencia/emporio-da-musica-agente
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

**2. Pegue uma chave grátis do Gemini**

Entre em <https://aistudio.google.com/apikey> com uma conta Google e clique em *Create API key*. Não pede cartão.

**3. Crie um banco vazio no PostgreSQL**

```bash
psql -h localhost -U postgres -c "CREATE DATABASE loja_musica;"
```

**4. Configure o `.env`**

```bash
cp .env.example .env             # Windows: copy .env.example .env
```

Abra o `.env` e preencha duas coisas: a senha do PostgreSQL em `DB_PASSWORD` e a chave do Gemini em `LLM_API_KEY`. O resto já vem pronto (`LLM_PROVIDER=gemini`).

**5. Crie as tabelas e carregue os dados**

```bash
python -m scripts.setup_db
```

Esse comando cria **todas** as tabelas sozinho, a partir dos CSVs e do manual que já estão no repositório. Não é preciso importar nada à mão.

**6. Suba o servidor e abra o chat**

```bash
uvicorn emporio.api.main:app --port 8000
```

Abra **<http://localhost:8000>** no navegador e converse com o agente. Algumas perguntas para testar: *"Quanto custa o Takamine GD20?"*, *"Quais violões vocês têm até R$ 1.000?"*, *"Me arrependi da compra, posso devolver?"* (use o pedido **7** com o e-mail **leticia.rocha@jmail.com**). O painel **Bastidores** mostra cada consulta que o agente fez.

Para conferir se banco e modelo estão acessíveis: <http://localhost:8000/api/health>.

> **Prefere rodar o modelo localmente, sem chave?** No `.env`, troque para `LLM_PROVIDER=ollama` e `LLM_MODEL=qwen3:14b`, instale o [Ollama](https://ollama.com/download) e rode `ollama pull qwen3:14b`. Detalhes na documentação completa.

## Destaques

- **Function calling com 7 ferramentas:** o modelo decide *o que* consultar; o SQL é fixo e revisado (o LLM nunca escreve SQL).
- **Regras de negócio em Python:** preço, PIX, parcelamento, prazos de devolução e horário são calculados pelo código, não pelo modelo.
- **Provedor de modelo trocável no `.env`:** Gemini ou Groq (API grátis) ou Ollama (local, os dados não saem da máquina).
- **Privacidade (LGPD):** pedidos só são consultados com o e-mail ou telefone do cadastro.
- **Interface web** com respostas em streaming e um painel **"Bastidores"**, que mostra cada ferramenta usada pelo agente.
- **Histórico de conversa e chamados** para a equipe humana, salvos no PostgreSQL.

## 📖 Documentação completa

**➡️ [`emporio-da-musica-agente/README.md`](emporio-da-musica-agente/README.md)**

Lá estão: como rodar em detalhe (incluindo problemas comuns de conexão com o banco), arquitetura, justificativa das decisões técnicas, tratamento dos dados, suposições, limitações e uso de assistentes de código. As conversas de exemplo estão em [`emporio-da-musica-agente/exemplos/`](emporio-da-musica-agente/exemplos/).

## Estrutura

```
emporio-da-musica-agente/
├── emporio/      código do agente (domínio, ETL, banco, agente, API)
├── web/          interface de chat
├── data/         CSVs da loja e manual de políticas
├── scripts/      setup do banco e geração das conversas de exemplo
├── exemplos/     conversas de exemplo geradas pelo agente
└── tests/        testes automatizados
```
