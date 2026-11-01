"""Leitura e tratamento dos CSVs da loja.

Cada função ``clean_*`` recebe as linhas cruas (dicts do csv.DictReader) e
devolve linhas tipadas e validadas. ``quality_report`` lista as
inconsistências encontradas, que o ETL imprime no terminal e que estão
documentadas no README.
"""

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from emporio.domain.data_quality import description_conflicts, detect_brand
from emporio.domain.money import to_money
from emporio.domain.text import normalize, only_digits

# Tradução de valores de specs para enriquecer a busca em português
# (o cliente digita "aço" ou "elétrico", o CSV tem "steel" e "yes").
SPEC_SEARCH_SYNONYMS = {
    "steel": "aco folk",
    "nylon": "nylon classico",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return [{k.strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(fh)]


def _date_or_none(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def _text_or_none(value: str) -> str | None:
    return value or None


@dataclass
class CleanData:
    categories: list[dict] = field(default_factory=list)
    products: list[dict] = field(default_factory=list)
    promotions: list[dict] = field(default_factory=list)
    customers: list[dict] = field(default_factory=list)
    orders: list[dict] = field(default_factory=list)
    order_items: list[dict] = field(default_factory=list)


def clean_categories(rows: list[dict]) -> list[dict]:
    return [{"category_id": int(r["category_id"]), "name": r["name"], "description": r["description"]}
            for r in rows]


def clean_products(rows: list[dict], categories: list[dict]) -> list[dict]:
    category_names = {c["category_id"]: c["name"] for c in categories}
    products = []
    for r in rows:
        specs = json.loads(r["specs"]) if r["specs"] else {}
        category_id = int(r["category_id"])
        conflicts = description_conflicts(r["name"], r["description"], specs)
        trusted = not conflicts

        # Texto de busca: nome + categoria + specs (+ descrição só se confiável).
        spec_terms = []
        for key, value in specs.items():
            value = str(value)
            spec_terms.append(SPEC_SEARCH_SYNONYMS.get(value, value))
            if key == "electronics" and value == "yes":
                spec_terms.append("eletrico eletroacustico captacao")
        search_parts = [r["name"], category_names.get(category_id, ""), *spec_terms]
        if trusted:
            search_parts.append(r["description"])

        products.append({
            "product_id": int(r["product_id"]),
            "category_id": category_id,
            "name": r["name"],
            "brand": detect_brand(r["name"]),
            "price_brl": to_money(r["price_brl"]),
            "description": r["description"],
            "description_trusted": trusted,
            "data_quality_notes": "; ".join(conflicts) or None,
            "stock_quantity": int(r["stock_quantity"]),
            "status": r["status"],
            "specs": specs,
            "created_at": _date_or_none(r["created_at"]),
            "name_norm": normalize(r["name"]),
            "search_text": normalize(" ".join(search_parts)),
        })
    return sorted(products, key=lambda p: p["product_id"])


def clean_promotions(rows: list[dict]) -> list[dict]:
    return [{
        "promotion_id": int(r["promotion_id"]),
        "product_id": int(r["product_id"]),
        "discount_percent": int(r["discount_percent"]),
        "campaign": r["description"],
        "campaign_norm": normalize(r["description"]),
        "is_active": r["is_active"] == "1",
    } for r in rows]


def clean_customers(rows: list[dict]) -> list[dict]:
    return [{
        "customer_id": int(r["customer_id"]),
        "name": r["name"],
        "phone": _text_or_none(r["phone"]),
        "phone_digits": only_digits(r["phone"]) or None,
        "email": r["email"].lower() or None,
        "city": _text_or_none(r["city"]),
    } for r in rows]


def clean_orders(rows: list[dict]) -> list[dict]:
    return [{
        "order_id": int(r["order_id"]),
        "customer_id": int(r["customer_id"]),
        "order_date": date.fromisoformat(r["order_date"]),
        "status": r["status"],
        "total_brl": to_money(r["total_brl"]),
        "payment_method": _text_or_none(r["payment_method"]),
        "tracking_code": _text_or_none(r["tracking_code"]),
        "estimated_delivery": _date_or_none(r["estimated_delivery"]),
        "notes": _text_or_none(r["notes"]),
    } for r in rows]


def clean_order_items(rows: list[dict]) -> list[dict]:
    return [{"order_id": int(r["order_id"]), "product_id": int(r["product_id"]),
             "quantity": int(r["quantity"])} for r in rows]


def load_clean_data(raw_dir: Path) -> CleanData:
    """Lê todos os CSVs de ``raw_dir`` e devolve os dados tratados."""
    categories = clean_categories(read_csv(raw_dir / "categories.csv"))
    return CleanData(
        categories=categories,
        products=clean_products(read_csv(raw_dir / "products.csv"), categories),
        promotions=clean_promotions(read_csv(raw_dir / "promotions.csv")),
        customers=clean_customers(read_csv(raw_dir / "customers.csv")),
        orders=clean_orders(read_csv(raw_dir / "orders.csv")),
        order_items=clean_order_items(read_csv(raw_dir / "order_items.csv")),
    )


def quality_report(data: CleanData) -> list[str]:
    """Inconsistências encontradas nos dados (não impedem a carga)."""
    findings: list[str] = []
    products = {p["product_id"]: p for p in data.products}

    for p in data.products:
        if not p["description_trusted"]:
            findings.append(f"Produto {p['product_id']} ({p['name']}): {p['data_quality_notes']} "
                            "-> descrição ocultada do agente.")
        if p["status"] != "active" and p["stock_quantity"] > 0:
            findings.append(f"Produto {p['product_id']} ({p['name']}): status '{p['status']}' com "
                            f"{p['stock_quantity']} em estoque -> status prevalece (não vendável).")

    used_categories = {p["category_id"] for p in data.products}
    for c in data.categories:
        if c["category_id"] not in used_categories:
            findings.append(f"Categoria {c['category_id']} ({c['name']}) não tem produtos cadastrados.")

    promos_by_product = defaultdict(list)
    for promo in data.promotions:
        promos_by_product[promo["product_id"]].append(promo)
    for product_id, promos in promos_by_product.items():
        if len(promos) > 1:
            desc = ", ".join(f"{x['campaign']} {x['discount_percent']}%"
                             f"{' (ativa)' if x['is_active'] else ''}" for x in promos)
            findings.append(f"Produto {product_id} tem {len(promos)} promoções cadastradas: {desc}.")

    items_by_order = defaultdict(list)
    for item in data.order_items:
        items_by_order[item["order_id"]].append(item)
    for order in data.orders:
        items_total = sum((products[i["product_id"]]["price_brl"] * i["quantity"]
                           for i in items_by_order[order["order_id"]]), Decimal("0"))
        if items_total != order["total_brl"]:
            findings.append(f"Pedido {order['order_id']}: total R$ {order['total_brl']} difere da soma "
                            f"dos itens a preço atual (R$ {items_total}) -> mantido o total do pedido.")
        for item in items_by_order[order["order_id"]]:
            if products[item["product_id"]]["status"] == "coming_soon":
                findings.append(f"Pedido {order['order_id']} contém o produto {item['product_id']}, "
                                "que está como 'coming_soon' (em breve).")

    emails = Counter(c["email"] for c in data.customers if c["email"])
    for email, count in emails.items():
        if count > 1:
            ids = [c["customer_id"] for c in data.customers if c["email"] == email]
            findings.append(f"E-mail {email} compartilhado por {count} clientes {ids} -> "
                            "a verificação de pedido considera todos.")
    return findings
