# 🎸 Empório da Música: agente de atendimento

Protótipo de um agente de mensagens de texto que atende os clientes da **Empório da Música**, loja (fictícia) de instrumentos musicais em Campo Grande/MS. O agente responde dúvidas recorrentes (produtos, preços, disponibilidade, pedidos, trocas, pagamento, frete, horários) consultando **dados reais da operação** (PostgreSQL) e o **manual de políticas da loja**, com a persona e o tom de voz definidos no próprio manual.

- **LLM local via Ollama** (gratuito, sem chave de API)
- **Function calling** com 7 ferramentas que acessam o banco por SQL fixo e revisado
- **Regras de negócio determinísticas em Python** (preço, PIX, parcelamento, prazos, horário)
- **Interface web** com respostas em streaming e um painel "Bastidores" que mostra o que o agente consultou
- **Histórico de conversa persistido** no PostgreSQL, além de chamados para a equipe humana

---

## Sumário

1. [Como rodar](#como-rodar)
2. [Arquitetura](#arquitetura)
3. [Decisões técnicas](#decisões-técnicas)
4. [Tratamento dos dados](#tratamento-dos-dados)
5. [Suposições adotadas](#suposições-adotadas)
6. [Limitações conhecidas e próximos passos](#limitações-conhecidas-e-próximos-passos)
7. [Exemplos de interação](#exemplos-de-interação)
8. [Uso de assistentes de código](#uso-de-assistentes-de-código)
9. [Estrutura do projeto](#estrutura-do-projeto)

---

## Como rodar

### Pré-requisitos

| Ferramenta | Versão | Para quê |
|---|---|---|
| Python | 3.10+ | aplicação |
| PostgreSQL | 13+ | dados da loja, histórico e chamados |
| [Ollama](https://ollama.com/download) | recente | roda o modelo de linguagem localmente |

### 1. Ambiente Python

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

### 2. Modelo de linguagem (Ollama)

Instale o Ollama, baixe o modelo e deixe o serviço rodando:

```bash
ollama pull qwen3:14b
ollama serve                        # no Windows/macOS o app já deixa o serviço rodando
```

#### Qual modelo usar

O modelo precisa ter **suporte a ferramentas (tools)**. A recomendação depende da memória da placa de vídeo:

| Hardware | Modelo sugerido (`LLM_MODEL`) | Observação |
|---|---|---|
| GPU com 8 GB | `qwen3:8b` | bom equilíbrio |
| GPU com 12–16 GB | `qwen3:14b` (**padrão**) | melhor escolha de ferramentas e português |
| GPU com 24 GB+ | `qwen3:32b` | mais preciso, mais lento |
| Só CPU / pouca RAM | `qwen3:4b` | funciona, mas lento e erra mais |

Para trocar, basta mudar `LLM_MODEL` no `.env` (e rodar `ollama pull <modelo>`).

#### Alternativa sem GPU: API gratuita (Groq ou Gemini)

Se a máquina não tem GPU (ou não dá para instalar o Ollama), o agente também fala com APIs na nuvem compatíveis com a API da OpenAI e com plano gratuito. Nada mais no sistema muda: ferramentas, regras e banco são os mesmos.

| Provedor | Chave (grátis, sem cartão) | `.env` | Modelo padrão |
|---|---|---|---|
| Groq | <https://console.groq.com/keys> | `LLM_PROVIDER=groq` | `meta-llama/llama-4-scout-17b-16e-instruct` |
| Gemini | <https://aistudio.google.com/apikey> | `LLM_PROVIDER=gemini` | `gemini-3.5-flash` |

Preencha `LLM_API_KEY` com a chave e deixe `LLM_MODEL` vazio para usar o modelo padrão do provedor. Os planos gratuitos limitam tokens por minuto: quando o limite estoura, o cliente espera o tempo indicado pela API e tenta de novo.

> ⚠️ Com um provedor na nuvem, as mensagens dos clientes saem da máquina. Para produção, o caminho recomendado continua sendo o modelo local (ver [Decisões técnicas](#2-modelo-e-provedor-ollama-local)).

### 3. Banco de dados (PostgreSQL)

> **Não é preciso importar os CSVs manualmente.** O script do passo 3.4 lê os arquivos de `data/raw/`, trata os dados e cria tudo. Você só precisa de um PostgreSQL rodando e de um banco vazio.

#### 3.1 Instalar e iniciar o PostgreSQL

Escolha **uma** das opções:

<details open>
<summary><b>Linux (Ubuntu/Debian)</b></summary>

```bash
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql

# Define a senha do usuário "postgres" (use a mesma no .env)
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'sua_senha_aqui';"
```
</details>

<details>
<summary><b>Windows</b></summary>

1. Baixe o instalador em <https://www.postgresql.org/download/windows/> e instale. O instalador pede a **senha do usuário `postgres`**: anote, ela vai no `.env`.
2. Mantenha a porta padrão **5432**.
3. O serviço inicia sozinho com o Windows. O `psql` fica em `C:\Program Files\PostgreSQL\<versão>\bin\`; use o **SQL Shell (psql)** do menu Iniciar ou adicione essa pasta ao PATH.
</details>

<details>
<summary><b>Docker (qualquer sistema)</b></summary>

```bash
docker run --name emporio-postgres -d -p 5432:5432 \
  -e POSTGRES_PASSWORD=sua_senha_aqui \
  -e POSTGRES_DB=loja_musica \
  postgres:16
```

Esse comando já cria o banco `loja_musica`, então pule o passo 3.2.
</details>

#### 3.2 Criar o banco vazio

```bash
psql -h localhost -U postgres -c "CREATE DATABASE loja_musica;"
```

#### 3.3 Configurar a conexão (`.env`)

```bash
cp .env.example .env               # Windows: copy .env.example .env
```

Abra o `.env` e preencha com os dados do seu PostgreSQL:

| Variável | Exemplo | O que é |
|---|---|---|
| `DB_HOST` | `localhost` | endereço do servidor (`localhost` se o banco roda na mesma máquina) |
| `DB_PORT` | `5432` | porta (5432 é o padrão) |
| `DB_USERNAME` | `postgres` | usuário do banco |
| `DB_PASSWORD` | `sua_senha_aqui` | senha desse usuário |
| `DB_DATABASE` | `loja_musica` | nome do banco criado no passo 3.2 (`DB_NAME` também é aceito) |
| `DB_SCHEMA` | `emporio` | schema onde o projeto cria suas tabelas (não precisa mudar) |

> 🔒 O `.env` está no `.gitignore` e **nunca** deve ir para o GitHub. Só o `.env.example`, sem senha real, é versionado.

Para testar a conexão antes de seguir:

```bash
psql -h localhost -p 5432 -U postgres -d loja_musica -c "SELECT version();"
```

#### 3.4 Criar as tabelas e carregar os dados

```bash
python -m scripts.setup_db
```

O script:
1. lê os CSVs e o manual de políticas;
2. imprime um **relatório de qualidade dos dados**;
3. cria a extensão `pg_trgm` (busca tolerante a erros de digitação), o schema `emporio` e as tabelas (tipadas, com chaves e restrições);
4. carrega tudo em **uma única transação** (se algo falhar, nada fica pela metade);
5. mostra quantas linhas foram carregadas em cada tabela.

Pode rodar quantas vezes quiser: catálogo, pedidos e políticas são recarregados, e conversas e chamados são preservados. Para apagar tudo e recriar do zero (inclusive conversas), use `python -m scripts.setup_db --reset`.

> As tabelas que já existirem no schema `public` (por exemplo, de uma importação manual dos CSVs) não são alteradas.

#### Problemas comuns de conexão

| Erro | Causa provável | Solução |
|---|---|---|
| `connection refused` / `Connection timed out` | PostgreSQL não está rodando ou está em outra porta | Linux: `sudo systemctl start postgresql`. Windows: em "Serviços", inicie `postgresql-x64-<versão>`. Confira `DB_PORT`. |
| `password authentication failed for user "postgres"` | senha errada no `.env` | Corrija `DB_PASSWORD` ou redefina a senha (comando do passo 3.1). |
| `database "loja_musica" does not exist` | o banco não foi criado | Rode o passo 3.2. |
| `permission denied to create extension "pg_trgm"` | o usuário do `.env` não é superusuário | Rode uma vez como superusuário: `psql -U postgres -d loja_musica -c "CREATE EXTENSION pg_trgm;"` |
| `extension "pg_trgm" is not available` | pacote de extensões não instalado | Linux: `sudo apt install postgresql-contrib`. No Windows e no Docker ela já vem instalada. |

Com a API rodando (passo 4), `http://localhost:8000/api/health` mostra se o banco e o Ollama estão acessíveis.

### 4. Usar o agente

**Interface web** (recomendado):

```bash
uvicorn emporio.api.main:app --reload
# abra http://localhost:8000
```

**Terminal:**

```bash
python -m emporio.cli --debug                    # --debug mostra as ferramentas chamadas
python -m emporio.cli --agora 2026-02-20T10:30   # simula data/hora (ver abaixo)
```

**API** (para integrar com outro canal, ex.: WhatsApp):

```bash
curl -X POST localhost:8000/api/chat -H "Content-Type: application/json" \
     -d '{"message": "Quanto custa o Takamine GD20?"}'
```

> 💡 **Relógio simulado.** Os pedidos da base são de out/2025 a mar/2026. Para testar prazos de devolução e "loja aberta/fechada" de forma realista, defina `SIMULATED_NOW=2026-02-20T10:30` no `.env` (ou use `--agora` na CLI).

### 5. Testes e exemplos

```bash
pytest                              # testes das regras de negócio, ETL e ferramentas (não usam LLM)
python -m scripts.gerar_exemplos    # roda as conversas de exemplo com o agente real -> exemplos/*.md
```

---

## Arquitetura

```
 Cliente ──► Front-end web / CLI / API REST
                    │  (streaming SSE)
                    ▼
            ┌───────────────────┐   system prompt (persona + regras, fixo)
            │   StoreAgent      │   + histórico (últimas N trocas, do Postgres)
            │   loop agêntico   │   + mensagem do cliente + contexto (data/hora, loja aberta?)
            └───┬──────────▲────┘
     pede tool  │          │ resultado (JSON já formatado)
                ▼          │
            ┌───────────────────┐        ┌──────────────────────────┐
            │  ToolRegistry     │──────► │ domain/ (Python puro)     │ preço, PIX, parcelas,
            │  7 ferramentas    │        │ regras determinísticas    │ prazos, horário, feriados
            │  (Pydantic)       │        └──────────────────────────┘
            └───┬───────────────┘
                ▼
            ┌───────────────────┐        ┌──────────────────────────┐
            │  db/ repositórios │──────► │ PostgreSQL (schema       │ catálogo, pedidos, políticas,
            │  SQL fixo         │        │ emporio)                 │ conversas, chamados, logs
            └───────────────────┘        └──────────────────────────┘
                    ▲
            ETL (scripts/setup_db.py): CSVs + manual curado ──► tratamento ──► carga
```

As camadas vão de dentro para fora, e cada uma só conhece a de dentro:

| Camada | Pasta | Responsabilidade |
|---|---|---|
| Domínio | `emporio/domain/` | Regras de negócio puras. Sem banco, sem LLM, 100% testável. |
| Dados | `emporio/etl/`, `emporio/db/` | Tratamento dos CSVs e do manual; consultas SQL por área (padrão *repository*). |
| Agente | `emporio/agent/` | Prompt, ferramentas, cliente do LLM e o loop. |
| Interface | `emporio/api/`, `emporio/cli.py`, `web/` | HTTP + streaming, terminal e front-end. |

### As ferramentas do agente

| Ferramenta | Quando o agente usa | O que o código garante |
|---|---|---|
| `buscar_produtos` | produto, preço, "vocês têm…?", recomendações | busca tolerante a acento e erro de digitação (trigramas); preço final com promoção ativa; preço no PIX; disponibilidade |
| `detalhes_produto` | especificações, item esgotado | specs traduzidas; **alternativas disponíveis** se o item estiver esgotado/descontinuado (manual 7.3) |
| `consultar_promocoes` | "tem Black Friday?", "o que está em promoção?" | diz se a promoção está **ativa**; nunca deixa prometer desconto vencido |
| `simular_pagamento` | parcelamento, PIX, cartão | regras de parcela mínima por faixa, PIX não cumulativo, combinação de pagamentos |
| `consultar_pedido` | status, rastreio, devolução | **exige e-mail/telefone do cadastro** (LGPD); prazos de arrependimento/troca/garantia já calculados |
| `consultar_politicas` | regras, endereço, horários, frete, garantia | devolve as seções do manual escolhidas pelo modelo a partir do índice |
| `abrir_chamado` | reclamação, devolução, troca, falar com humano | registra para a equipe e devolve protocolo e prazo de retorno (24h úteis) |

---

## Decisões técnicas

### 1. Abordagem do agente: function calling com loop próprio

O modelo recebe o catálogo de ferramentas e decide, a cada mensagem, se precisa consultar **dados** (produto, pedido, promoção) ou **políticas** (manual), no estilo ReAct: pensa, chama a ferramenta, lê o resultado e responde.

- **Por que não um agente de SQL** (o LLM escrevendo SQL)? Seria um risco de segurança (o cliente poderia induzir uma consulta aos dados de outras pessoas) e de precisão (consultas erradas e silenciosas). Com ferramentas, o SQL é fixo e revisado, e o LLM só escolhe os parâmetros, que são validados com Pydantic.
- **Por que não LangChain/LlamaIndex?** O fluxo é pequeno (cerca de 100 linhas em `agent.py`). Um loop explícito deixa cada passo visível e auditável: a tela mostra as ferramentas chamadas e o banco registra todas em `tool_calls`. Um framework adicionaria abstração sem ganho real aqui.
- **"O LLM decide, o código calcula."** Preço com desconto, parcelas, dias desde a entrega e loja aberta são calculados em Python (`emporio/domain/`) e entregues prontos ao modelo. LLMs erram contas de forma silenciosa, e o manual diz: *"nunca fornecer informações sobre preços, estoque ou prazos sem consultar o sistema"*.

### 2. Modelo e provedor: Ollama (local)

- **Gratuito e privado.** Roda na máquina, sem custo por mensagem e sem enviar dados de clientes a terceiros, o que combina com o capítulo de LGPD do manual.
- **Família Qwen3** como padrão: tem suporte nativo a ferramentas no Ollama, bom desempenho em português e tamanhos para vários hardwares (tabela em [Qual modelo usar](#qual-modelo-usar)).
- **Configurações importantes** (`emporio/agent/llm.py`):
  - `num_ctx=16384`: o contexto padrão do Ollama é pequeno e **cortaria o começo do prompt em silêncio** (persona e regras).
  - `temperature=0.2`: atendimento pede consistência, não criatividade.
  - modo `think` configurável (`LLM_THINK`): melhora decisões, mas aumenta a latência.
- **Trocar de provedor** exige apenas outra classe com o método `stream_chat`. Já existem duas, escolhidas por `LLM_PROVIDER`: `OllamaLLM` e `OpenAICompatibleLLM` (Groq, Gemini ou qualquer API compatível com OpenAI). O histórico fica salvo no formato do Ollama e é convertido na hora (`to_openai_messages`: ids das chamadas de ferramenta e argumentos em JSON), então dá para trocar de provedor sem perder conversas.
- **Adaptações para modelos locais:**
  - Schema de ferramentas "achatado": a biblioteca do Ollama descarta `anyOf`, `default` e limites, então esses campos viram texto na descrição (`to_ollama_parameters`).
  - Argumentos tolerantes: aceita JSON em string, `"null"` e números como texto.
  - Validação Pydantic em modo *lax*.
  - Na última rodada o modelo é chamado sem ferramentas, o que o obriga a responder.

### 3. Retrieval das políticas: índice de seções em vez de embeddings

O manual tem **10 seções bem delimitadas (~3 mil tokens)**. Em vez de dividir em pedaços e usar busca vetorial, cada seção vira um documento com *slug* (`trocas_devolucoes`, `frete_entregas`…) e o **índice** (títulos e subtítulos) vai na descrição da ferramenta `consultar_politicas`. O próprio LLM escolhe o que ler.

- **Mais preciso para um documento pequeno e estruturado.** A similaridade vetorial pode trazer um trecho parecido, mas errado (ex.: "troca por defeito" quando a pergunta era sobre "arrependimento").
- **Sem infraestrutura extra.** Não precisa de modelo de embeddings nem de pgvector.
- **A seção vem inteira**, então o agente sempre vê a regra junto com as condições e exceções.
- Com um manual muito maior, eu partiria para busca híbrida (BM25 + embeddings em pgvector) com re-ranking.

### 4. Estratégia de prompt

O prompt está em `emporio/agent/prompts.py`:

- **Persona tirada do manual (seção 7):** "Tom", informal mas profissional, *"como um amigo que entende de música"*, seguindo o fluxo de atendimento da loja (saudação → entendimento → consulta → resposta → fechamento).
- **Mapa de roteamento explícito** (tipo de pergunta → ferramenta). Modelos locais menores se beneficiam muito dessa clareza.
- **Regras com o porquê** ("informação errada pode configurar propaganda enganosa"), o que ajuda o modelo a generalizar.
- **Prompt fixo + contexto dinâmico no fim.** Data/hora e o status "loja aberta/fechada" entram junto da mensagem do cliente, num bloco `[CONTEXTO DO SISTEMA]`, e não no system prompt. Assim o Ollama reaproveita o processamento do início do prompt entre requisições (cache de prefixo), o que deixa a resposta bem mais rápida. O cliente não consegue falsificar esse bloco: as marcações são removidas do texto dele.
- **Formato WhatsApp:** respostas curtas, listas e negrito só em produto e preço.

### 5. Persistência do histórico

Faz sentido para a experiência: o cliente diz o número do pedido numa mensagem e "pode abrir o chamado" na seguinte.

- **Onde:** no PostgreSQL (`chat_messages`), no formato de mensagens do modelo, incluindo chamadas e resultados de ferramentas. O agente lembra o que já consultou.
- **Janela de contexto:** vão para o modelo as últimas `HISTORY_MAX_TURNS` trocas, sempre cortadas no início de uma troca, para nunca deixar um resultado de ferramenta sem a chamada que o originou.
- **Atomicidade:** uma troca é salva inteira (em uma transação) só quando termina. Se o modelo falhar no meio, o histórico continua consistente.
- **Na web**, o id da conversa fica no `localStorage`: recarregar a página restaura o chat.

### 6. Interface

FastAPI serve a API e o front-end (HTML/CSS/JS puros, sem build).

- **Streaming (SSE):** o texto aparece enquanto o modelo gera, o que é essencial para um LLM local.
- **Painel "Bastidores":** mostra cada ferramenta chamada, com entrada e saída (útil para a equipe e para quem avalia).
- **Aba "Chamados":** visão da equipe com os casos encaminhados.
- **Experiência geral:** status "loja aberta/fechada", sugestões de perguntas, layout responsivo e tema escuro.

### 7. Segurança e privacidade

- **Pedidos só com verificação:** só aparecem se o e-mail ou telefone informado bater com o cadastro do dono. Quando não bate, a resposta é genérica e não revela se o pedido existe.
- **SQL fixo e parametrizado:** o LLM nunca escreve SQL. Valores livres, como a ordenação, passam por *whitelist*.
- **Prompt injection:** o prompt instrui a ignorar pedidos de "ignore as instruções" e o bloco de contexto não pode ser falsificado.
- **Exposição mínima:** a ferramenta de pedido devolve só o primeiro nome do cliente.

---

## Tratamento dos dados

O ETL (`emporio/etl/`) transforma os CSVs em um schema tipado (`emporio/db/schema.sql`):

- `NUMERIC` para dinheiro (nada de `float`), `DATE` para datas e `JSONB` para specs
- chaves primárias e estrangeiras e `CHECK` de status
- colunas derivadas: marca, texto normalizado para busca e flags de qualidade

O relatório de qualidade, impresso pelo `setup_db`, encontrou:

| Problema encontrado | Decisão |
|---|---|
| **6 produtos com descrição que contradiz o nome**. Ex.: *"Music Man Bass 1X"* descrito como *"Fender Jazz Bass"*; *"Korg Synth 1 Pro"* descrito como *"Roland com 88 teclas"* (specs: 61). | Nome e specs são a fonte da verdade. A descrição é **ocultada do agente**, que recebe um aviso para não afirmar marca/modelo além do nome. Detecção automática em `domain/data_quality.py`. |
| Produtos `discontinued`/`coming_soon` com estoque > 0 | O status prevalece: não são oferecidos para venda. |
| Produtos com mais de uma promoção cadastrada | Promoções não são cumulativas (manual 6.2): vale só a **ativa** de maior desconto (view `v_active_promotion`). |
| Totais de pedidos (3 e 20) diferentes da soma dos itens | Mantido o total do pedido (pode ter havido desconto na época). |
| E-mail `bruno.martins@jmail.com` em 2 clientes | A verificação de pedido considera todos os cadastros com aquele contato. |
| Categorias 6, 7 e 8 (sopros e cordas orquestrais) sem produtos | O agente informa que não há itens no momento, sem inventar. |
| Telefones em formatos variados | Normalizados para dígitos; o cliente pode digitar com ou sem DDD/+55. |

**Manual de políticas:** o PDF foi convertido para Markdown estruturado (`data/politicas_da_loja.md`), fiel ao texto original, com tabelas como tabelas. Encontrei inconsistências **no próprio manual**, resolvidas com notas de curadoria marcadas no arquivo:

| Inconsistência | Resolução |
|---|---|
| WhatsApp **(67) 3321-4500** (seção 7) × **(67) 3341-4444** (capa e seção 1.2) | Vale o 3341-4444, que aparece duas vezes, inclusive nos dados cadastrais. |
| E-mail com acento (`empóriodamusica`) na seção 1.2 × sem acento na capa | Vale o sem acento (e-mail com acento não é usual). |
| Tabela diz "parcela mínima R$ 100" × seção 3.1 detalha faixas (R$ 50 / R$ 80 / R$ 100) | Prevalece a regra mais específica (3.1), implementada em `domain/payments.py`. |

---

## Suposições adotadas

O enunciado pede para assumir interpretações razoáveis e documentá-las:

1. **Data de entrega:** a base não tem a data real de entrega, só a prevista (`estimated_delivery`). Para pedidos entregues, uso a data prevista como data de recebimento e o agente avisa o cliente disso.
2. **Compras online:** todos os pedidos da base têm entrega, então tratei todos como online para fins do direito de arrependimento (7 dias após o recebimento).
3. **Troca por preferência (7 dias):** o manual não diz a partir de quando. Considerei a data de recebimento, como no arrependimento.
4. **Parcelamento "até 3x sem valor mínimo (exceto abaixo de R$ 50)":** interpretado como parcela mínima de R$ 50 em 2x e 3x.
5. **Feriados:** o manual diz "fechado em feriados", sem listá-los. Considerei os nacionais, a Sexta-feira Santa, o 11/10 (criação de MS), o 26/08 (aniversário de Campo Grande) e o 13/06 (Santo Antônio, padroeiro). A lista está em `domain/store_hours.py`.
6. **Lojas parceiras:** o manual pede para sugerir lojas parceiras para acessórios "quando possível", mas não lista nenhuma. O agente não inventa nomes.
7. **Ações que exigem decisão humana** (aprovar devolução, cancelar pedido): o agente **não executa**. Ele explica a política, verifica os prazos e **abre um chamado** para a equipe.

---

## Limitações conhecidas e próximos passos

**Limitações:**

- **Qualidade depende do modelo local.** Modelos pequenos (4B) às vezes escolhem a ferramenta errada ou parafraseiam valores. Os de 14B+ são bem mais confiáveis.
- **Latência:** em CPU, uma resposta pode levar dezenas de segundos. O streaming ameniza, mas não resolve.
- **Planos gratuitos na nuvem têm cota baixa.** No Gemini grátis, testei cerca de 15 a 20 requisições por minuto/dia por modelo, e cada mensagem do cliente usa de 1 a 4 chamadas ao modelo. Serve para demonstração, não para atendimento real. Os modelos "latest" do Gemini também ficaram sobrecarregados (erro 503) durante os testes; o cliente tenta de novo sozinho, mas a resposta demora.
- **Frete para outras cidades** é calculado por CEP/peso no sistema real, que não temos. O agente explica a regra e as modalidades, mas não dá o valor.
- **Feriados municipais/estaduais** são uma lista fixa no código, e não há horário especial (Black Friday, Natal).
- **Concorrência:** duas mensagens simultâneas na mesma conversa podem se intercalar no histórico. A interface bloqueia o envio enquanto espera, mas a API não.
- **Autenticação:** não há login. A verificação de pedido por e-mail/telefone é uma proteção básica, não uma autenticação forte.

**Com mais tempo eu faria:**

1. **Conjunto de avaliação automatizado** com dezenas de perguntas, medindo a escolha da ferramenta certa, a fidelidade dos valores ao que a ferramenta devolveu e a recusa correta fora do escopo, rodando a cada mudança de prompt ou modelo. O `scripts/gerar_exemplos.py` já faz uma verificação simples das ferramentas esperadas.
2. **Guardrail de saída:** checar se todo preço citado na resposta aparece nos resultados das ferramentas daquela troca e, se não aparecer, regerar.
3. **Integração real com o WhatsApp** (Cloud API) usando o endpoint `/api/chat`, com o telefone do remetente como identificação.
4. **Resumo do histórico** para conversas longas, em vez de só cortar as trocas antigas.
5. **Painel da equipe** para responder e fechar chamados, além de métricas (perguntas mais comuns, taxa de chamados).
6. Busca híbrida (pgvector) se o manual crescer, e cache de respostas institucionais frequentes.

---

## Exemplos de interação

A pasta [`exemplos/`](exemplos/) contém conversas **geradas pelo agente real** com `python -m scripts.gerar_exemplos` (modelo `gemini-flash-lite-latest`, plano gratuito, porque a máquina de entrega não tinha o Ollama instalado). Os arquivos mostram exatamente o que o agente respondeu, com as ferramentas chamadas e seus resultados:

| # | Cenário | O que demonstra |
|---|---|---|
| 1 | Violões até R$ 1.000 + parcelamento | busca com filtro de preço; regras de parcelamento e PIX |
| 2 | Preço do Takamine GD20 + promoção encerrada | consulta de preço; transparência com promoção expirada |
| 3 | **"Me arrependi, posso devolver?"** | **não trivial:** verificação de identidade, pedido em tempo real, prazo de 7 dias calculado, política e abertura de chamado |
| 4 | Rastreio + endereço, sábado à noite | pedido em trânsito; manual; loja fechada no dia seguinte (domingo) |
| 5 | Acessórios, assunto alheio, manipulação, item esgotado | escopo; recusa educada; alternativas para produto esgotado |

---

## Uso de assistentes de código

> ✏️ **Revise e complete esta seção com o seu próprio workflow antes de entregar.**

Usei o **Claude Code** (agente de código da Anthropic, no terminal) como par de programação durante todo o projeto. O workflow foi:

1. **Entendimento do problema:** pedi ao assistente que lesse o enunciado, o manual em PDF e os CSVs. Ele levantou as inconsistências dos dados e do manual listadas acima antes de qualquer código.
2. **Decisões:** discutimos as alternativas e eu tomei as decisões de produto. Por exemplo, a escolha do **Ollama** como provedor (gratuito e local), considerando o hardware disponível para teste.
3. **Implementação incremental:** o código foi gerado por camadas (domínio → banco → ETL → ferramentas → agente → API → front), validando cada uma antes da próxima: o schema e as consultas SQL foram testados direto no PostgreSQL e as regras de negócio contra os dados reais.
4. **Verificação de APIs:** em vez de confiar na memória do modelo, o assistente consultou o código-fonte da biblioteca `ollama-python`. Foi assim que encontramos que ela descarta campos de JSON Schema como `anyOf`, o que motivou o conversor `to_ollama_parameters`.
5. **Revisão e testes:** as regras de negócio, o ETL e a conversão de ferramentas têm testes automatizados (`pytest`), que rodam sem LLM. O agente completo foi testado com o Ollama em _[descreva a máquina, ex.: GPU XX GB]_ usando o modelo _[modelo usado]_, e as conversas de `exemplos/` foram geradas com `scripts/gerar_exemplos.py`. _[Descreva aqui o que você ajustou depois de testar: prompt, ferramentas, modelo etc.]_

---

## Estrutura do projeto

```
├── data/
│   ├── raw/                      # CSVs e PDF originais do desafio
│   └── politicas_da_loja.md      # manual curado (fonte da base de conhecimento)
├── emporio/
│   ├── domain/                   # regras de negócio puras (preço, parcelas, prazos, horário)
│   ├── etl/                      # tratamento dos CSVs e do manual + carga no banco
│   ├── db/                       # schema.sql, pool de conexões e consultas por área
│   ├── agent/                    # prompts, ferramentas, cliente Ollama e loop agêntico
│   ├── api/main.py               # FastAPI: chat em streaming, histórico, chamados
│   ├── cli.py                    # chat pelo terminal
│   ├── clock.py                  # relógio (real ou simulado)
│   └── config.py                 # configuração via .env
├── web/                          # front-end (HTML/CSS/JS puros)
├── scripts/
│   ├── setup_db.py               # cria schema e carrega dados
│   └── gerar_exemplos.py         # roda os cenários de exemplo -> exemplos/*.md
├── exemplos/                     # conversas geradas pelo agente
└── tests/                        # pytest (regras, ETL, ferramentas)
```
