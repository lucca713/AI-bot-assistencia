"""Consultas de catálogo: produtos, categorias e promoções."""

from decimal import Decimal

from psycopg import Connection

# Preço final já com a promoção ativa (se houver). Usado nos filtros de preço:
# "violões até R$ 1.000" deve considerar o preço que o cliente vai pagar.
_PRICED_PRODUCTS_CTE = """
WITH priced AS (
    SELECT p.*,
           c.name AS category_name,
           ap.discount_percent AS promo_percent,
           ap.campaign         AS promo_campaign,
           round(p.price_brl * (100 - coalesce(ap.discount_percent, 0)) / 100.0, 2) AS final_price,
           -- Relevância textual (0 a 1) via trigramas: tolera acento, maiúscula e erro de digitação.
           -- O nome pesa mais que o texto completo (categoria/specs/descrição).
           CASE WHEN %(term)s::text IS NULL THEN 1.0
                ELSE greatest(word_similarity(%(term)s, p.name_norm),
                              0.85 * word_similarity(%(term)s, p.search_text))
           END AS score
      FROM products p
      JOIN categories c USING (category_id)
      LEFT JOIN v_active_promotion ap USING (product_id)
)
"""

# Whitelist de ordenação: o valor vem do LLM, então nunca interpolamos texto livre.
_ORDER_BY = {
    "relevancia": "score DESC, final_price ASC",
    "menor_preco": "final_price ASC",
    "maior_preco": "final_price DESC",
}

MIN_SEARCH_SCORE = 0.3


def list_categories(conn: Connection) -> list[dict]:
    return conn.execute("""
        SELECT c.category_id, c.name, c.description,
               count(p.product_id) FILTER (WHERE p.status = 'active' AND p.stock_quantity > 0)
                   AS available_products
          FROM categories c
          LEFT JOIN products p USING (category_id)
         GROUP BY c.category_id
         ORDER BY c.category_id
    """).fetchall()


def search_products(
    conn: Connection,
    *,
    term_norm: str | None,
    category_id: int | None,
    min_price: Decimal | None,
    max_price: Decimal | None,
    only_available: bool,
    order_by: str,
    limit: int,
) -> list[dict]:
    """Busca produtos. Cada linha traz ``total_found`` (total antes do LIMIT)."""
    sql = _PRICED_PRODUCTS_CTE + f"""
        SELECT *, count(*) OVER () AS total_found
          FROM priced
         WHERE score >= %(min_score)s
           AND (%(category_id)s::int IS NULL OR category_id = %(category_id)s)
           AND (%(min_price)s::numeric IS NULL OR final_price >= %(min_price)s)
           AND (%(max_price)s::numeric IS NULL OR final_price <= %(max_price)s)
           AND (NOT %(only_available)s OR (status = 'active' AND stock_quantity > 0))
         ORDER BY {_ORDER_BY[order_by]}
         LIMIT %(limit)s
    """
    return conn.execute(sql, {
        "term": term_norm, "min_score": MIN_SEARCH_SCORE, "category_id": category_id,
        "min_price": min_price, "max_price": max_price,
        "only_available": only_available, "limit": limit,
    }).fetchall()


def get_product(conn: Connection, product_id: int) -> dict | None:
    sql = _PRICED_PRODUCTS_CTE + "SELECT * FROM priced WHERE product_id = %(product_id)s"
    return conn.execute(sql, {"term": None, "product_id": product_id}).fetchone()


def find_alternatives(conn: Connection, product: dict, limit: int = 3) -> list[dict]:
    """Produtos disponíveis da mesma categoria com preço parecido (manual 7.3:
    para item esgotado/descontinuado, sugerir alternativas semelhantes)."""
    sql = _PRICED_PRODUCTS_CTE + """
        SELECT * FROM priced
         WHERE category_id = %(category_id)s
           AND product_id <> %(product_id)s
           AND status = 'active' AND stock_quantity > 0
         ORDER BY abs(final_price - %(price)s) ASC
         LIMIT %(limit)s
    """
    return conn.execute(sql, {
        "term": None, "category_id": product["category_id"], "product_id": product["product_id"],
        "price": product["final_price"], "limit": limit,
    }).fetchall()


def list_promotions(
    conn: Connection,
    *,
    product_id: int | None = None,
    campaign_norm: str | None = None,
) -> list[dict]:
    """Promoções (ativas e inativas) filtradas por produto e/ou nome da campanha."""
    return conn.execute("""
        SELECT pr.promotion_id, pr.product_id, pr.discount_percent, pr.campaign, pr.is_active,
               p.name AS product_name, p.price_brl, p.status AS product_status, p.stock_quantity
          FROM promotions pr
          JOIN products p USING (product_id)
         WHERE (%(product_id)s::int IS NULL OR pr.product_id = %(product_id)s)
           AND (%(campaign)s::text IS NULL OR pr.campaign_norm LIKE '%%' || %(campaign)s || '%%')
         ORDER BY pr.is_active DESC, pr.discount_percent DESC
    """, {"product_id": product_id, "campaign": campaign_norm}).fetchall()


def list_active_promotions(conn: Connection) -> list[dict]:
    return conn.execute("""
        SELECT pr.promotion_id, pr.product_id, pr.discount_percent, pr.campaign, pr.is_active,
               p.name AS product_name, p.price_brl, p.status AS product_status, p.stock_quantity
          FROM promotions pr
          JOIN products p USING (product_id)
         WHERE pr.is_active
         ORDER BY pr.discount_percent DESC
    """).fetchall()
