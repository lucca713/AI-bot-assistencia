-- =============================================================================
-- Schema do agente da Empório da Música
-- =============================================================================
-- As tabelas importadas "cruas" no schema public (ex.: desafio_tecnico_ai_eng,
-- ordem_items) são mantidas intactas. Aqui criamos um schema próprio, com:
--   * tipos corretos (NUMERIC para dinheiro, DATE para datas, JSONB para specs)
--   * chaves primárias/estrangeiras e CHECKs (o banco rejeita dado inválido)
--   * colunas derivadas pelo ETL (marca, texto normalizado para busca, flags
--     de qualidade de dados)
--   * tabelas operacionais do agente (conversas, chamados, log de ferramentas)
--
-- O script é idempotente (IF NOT EXISTS): pode rodar várias vezes.
-- O placeholder {schema} é substituído pelo valor de DB_SCHEMA (padrão: emporio).
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- similaridade por trigramas (busca tolerante a erros)

CREATE SCHEMA IF NOT EXISTS {schema};

-- ---------------------------------------------------------------------------
-- Catálogo
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS {schema}.categories (
    category_id  integer PRIMARY KEY,
    name         text NOT NULL,
    description  text
);

CREATE TABLE IF NOT EXISTS {schema}.products (
    product_id           integer PRIMARY KEY,
    category_id          integer NOT NULL REFERENCES {schema}.categories (category_id),
    name                 text NOT NULL,
    brand                text,                                   -- derivada do nome pelo ETL
    price_brl            numeric(10, 2) NOT NULL CHECK (price_brl >= 0),
    description          text,
    description_trusted  boolean NOT NULL DEFAULT true,         -- false = descrição contradiz nome/specs
    data_quality_notes   text,                                   -- motivo da inconsistência
    stock_quantity       integer NOT NULL CHECK (stock_quantity >= 0),
    status               text NOT NULL CHECK (status IN ('active', 'discontinued', 'coming_soon')),
    specs                jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at           date,
    name_norm            text NOT NULL,                          -- nome sem acento/minúsculo
    search_text          text NOT NULL                           -- nome + categoria + specs (+ descrição confiável)
);

CREATE INDEX IF NOT EXISTS products_name_trgm   ON {schema}.products USING gin (name_norm gin_trgm_ops);
CREATE INDEX IF NOT EXISTS products_search_trgm ON {schema}.products USING gin (search_text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS products_category    ON {schema}.products (category_id);

CREATE TABLE IF NOT EXISTS {schema}.promotions (
    promotion_id      integer PRIMARY KEY,
    product_id        integer NOT NULL REFERENCES {schema}.products (product_id),
    discount_percent  integer NOT NULL CHECK (discount_percent > 0 AND discount_percent < 100),
    campaign          text NOT NULL,          -- coluna "description" do CSV (é o nome da campanha)
    campaign_norm     text NOT NULL,
    is_active         boolean NOT NULL
);

-- Melhor promoção ATIVA de cada produto. Promoções não são cumulativas
-- (manual 6.2); se houver mais de uma ativa, vale a de maior desconto.
CREATE OR REPLACE VIEW {schema}.v_active_promotion AS
SELECT DISTINCT ON (product_id)
       product_id, promotion_id, discount_percent, campaign
  FROM {schema}.promotions
 WHERE is_active
 ORDER BY product_id, discount_percent DESC;

-- ---------------------------------------------------------------------------
-- Clientes e pedidos
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS {schema}.customers (
    customer_id   integer PRIMARY KEY,
    name          text NOT NULL,
    phone         text,
    phone_digits  text,          -- só dígitos, para comparar "(67) 99812-3456" com "67998123456"
    email         text,          -- minúsculo
    city          text
);

CREATE INDEX IF NOT EXISTS customers_email ON {schema}.customers (email);
CREATE INDEX IF NOT EXISTS customers_phone ON {schema}.customers (phone_digits);

CREATE TABLE IF NOT EXISTS {schema}.orders (
    order_id            integer PRIMARY KEY,
    customer_id         integer NOT NULL REFERENCES {schema}.customers (customer_id),
    order_date          date NOT NULL,
    status              text NOT NULL CHECK (status IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled')),
    total_brl           numeric(10, 2) NOT NULL CHECK (total_brl >= 0),
    payment_method      text,
    tracking_code       text,
    estimated_delivery  date,
    notes               text
);

CREATE INDEX IF NOT EXISTS orders_customer ON {schema}.orders (customer_id);

CREATE TABLE IF NOT EXISTS {schema}.order_items (
    order_id    integer NOT NULL REFERENCES {schema}.orders (order_id),
    product_id  integer NOT NULL REFERENCES {schema}.products (product_id),
    quantity    integer NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (order_id, product_id)
);

-- ---------------------------------------------------------------------------
-- Base de conhecimento (manual de políticas, dividido por seção)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS {schema}.policy_sections (
    slug     text PRIMARY KEY,       -- ex.: trocas_devolucoes
    number   integer NOT NULL UNIQUE,
    title    text NOT NULL,
    summary  text NOT NULL,          -- títulos das subseções (vira o "índice" para o agente)
    content  text NOT NULL           -- markdown completo da seção
);

-- ---------------------------------------------------------------------------
-- Operação do agente
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS {schema}.conversations (
    conversation_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    channel          text NOT NULL DEFAULT 'web',
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);

-- Histórico COMPLETO da conversa, no formato de mensagens do Ollama
-- (role/content/tool_calls/tool_name), em JSONB. Inclui as chamadas de
-- ferramenta e seus resultados, para o modelo lembrar o que já consultou.
-- visible_text guarda só o que aparece na tela (mensagem do cliente sem o
-- contexto automático, resposta final do agente) para reconstruir o chat.
CREATE TABLE IF NOT EXISTS {schema}.chat_messages (
    conversation_id  uuid NOT NULL REFERENCES {schema}.conversations (conversation_id) ON DELETE CASCADE,
    seq              integer NOT NULL,
    role             text NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    message          jsonb NOT NULL,
    visible_text     text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (conversation_id, seq)
);

-- Auditoria: toda chamada de ferramenta feita pelo agente.
CREATE TABLE IF NOT EXISTS {schema}.tool_calls (
    id               bigserial PRIMARY KEY,
    conversation_id  uuid REFERENCES {schema}.conversations (conversation_id) ON DELETE CASCADE,
    tool_name        text NOT NULL,
    input            jsonb NOT NULL,
    output           jsonb,
    is_error         boolean NOT NULL DEFAULT false,
    duration_ms      integer,
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- Chamados abertos pelo agente para a equipe humana (reclamações,
-- devoluções, trocas, pedidos de atendimento humano).
-- order_id não tem FK de propósito: o ETL pode recarregar os pedidos sem
-- apagar chamados já registrados.
CREATE TABLE IF NOT EXISTS {schema}.tickets (
    ticket_id        serial PRIMARY KEY,
    protocol         text UNIQUE,
    conversation_id  uuid REFERENCES {schema}.conversations (conversation_id) ON DELETE SET NULL,
    ticket_type      text NOT NULL CHECK (ticket_type IN
                       ('reclamacao', 'devolucao', 'troca', 'garantia', 'cancelamento', 'atendimento_humano', 'outro')),
    customer_name    text NOT NULL,
    contact          text NOT NULL,
    order_id         integer,
    summary          text NOT NULL,
    status           text NOT NULL DEFAULT 'aberto',
    created_at       timestamptz NOT NULL DEFAULT now()
);
