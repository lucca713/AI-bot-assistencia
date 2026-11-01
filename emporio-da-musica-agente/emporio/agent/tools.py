"""Ferramentas do agente (function calling).

Como funciona:
1. Cada ferramenta tem um modelo Pydantic de entrada. Dele geramos o JSON
   Schema enviado ao modelo (ele sabe quais parâmetros existem) e
   validamos o que o modelo mandar de volta.
2. O modelo decide QUAL ferramenta chamar e COM QUAIS argumentos.
3. O nosso código executa a consulta (SQL fixo, revisado — o LLM nunca
   escreve SQL) e devolve um JSON já "mastigado": preços formatados, prazos
   calculados, avisos de qualidade de dados.

Nomes e descrições das ferramentas estão em português porque fazem parte do
"prompt": o modelo conversa em português com o cliente e raciocina melhor
quando o vocabulário das ferramentas é o mesmo do domínio.
"""

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from emporio.clock import Clock
from emporio.db import catalog, orders, policies, tickets
from emporio.domain.order_rules import STATUS_LABELS, evaluate_deadlines, payment_label
from emporio.domain.payments import simulate_payment
from emporio.domain.pricing import quote_price
from emporio.domain.money import format_brl
from emporio.domain.store_hours import store_status
from emporio.domain.text import normalize

logger = logging.getLogger(__name__)

# Rótulos em português para as chaves de specs do CSV.
SPEC_LABELS = {
    "top": "tampo", "back_sides": "fundo e laterais", "neck": "braço", "strings": "cordas",
    "scale": "escala", "electronics": "eletrônica/captação", "color": "cor", "body": "corpo",
    "hardware": "ferragens", "keys": "teclas", "pieces": "peças", "polyphony": "polifonia",
    "shells": "cascos", "type": "tipo",
}
SPEC_VALUES = {"steel": "aço", "nylon": "nylon", "yes": "sim", "no": "não", "included": "inclusas"}


# =============================================================================
# Infraestrutura
# =============================================================================
@dataclass
class ToolContext:
    """Dependências que as ferramentas recebem a cada execução."""

    pool: ConnectionPool
    clock: Clock
    conversation_id: str | None


class ToolInput(BaseModel):
    # Modelos locais às vezes mandam um parâmetro a mais: em vez de falhar
    # (o que custaria mais uma rodada do modelo), ignoramos o extra.
    # A validação do Pydantic é "lax": "5" vira 5, "true" vira True.
    model_config = ConfigDict(extra="ignore")


@dataclass
class Tool:
    name: str
    description: str
    input_model: type[ToolInput]
    handler: Callable[[ToolContext, Any], dict]
    schema_overrides: Callable[[dict], None] | None = None

    def definition(self) -> dict:
        """Formato de ferramenta do Ollama (padrão "function calling")."""
        parameters = to_ollama_parameters(self.input_model.model_json_schema())
        if self.schema_overrides:
            self.schema_overrides(parameters)
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": parameters},
        }


@dataclass
class ToolResult:
    name: str
    input: dict
    output: dict
    is_error: bool
    duration_ms: int

    def to_message(self) -> dict:
        """Mensagem de resultado que volta para o modelo."""
        return {
            "role": "tool",
            "tool_name": self.name,
            "content": json.dumps(self.output, ensure_ascii=False, default=str),
        }


# Restrições do JSON Schema que o Ollama não suporta: viram texto na descrição.
_CONSTRAINT_HINTS = (
    ("minimum", "mínimo"), ("exclusiveMinimum", "maior que"), ("maximum", "máximo"),
    ("maxLength", "até {} caracteres"), ("minItems", "mínimo {} item(ns)"), ("maxItems", "máximo {} itens"),
)


def _simplify_property(prop: dict) -> dict:
    """Converte uma propriedade do Pydantic para o subconjunto aceito pelo Ollama.

    O modelo ``Tool`` da biblioteca do Ollama só aceita ``type``, ``items``,
    ``description`` e ``enum`` em cada parâmetro; o resto (``anyOf``,
    ``default``, ``maximum``...) seria DESCARTADO em silêncio. Por exemplo,
    ``int | None`` vira ``anyOf: [integer, null]`` no Pydantic e chegaria ao
    modelo sem tipo nenhum. Aqui "achatamos" o anyOf e levamos padrão e
    limites para a descrição, onde o modelo consegue lê-los.
    """
    prop = dict(prop)
    if "anyOf" in prop:  # Optional[X] -> X
        non_null = [opt for opt in prop.pop("anyOf") if opt.get("type") != "null"]
        prop = {**(non_null[0] if non_null else {}), **prop}

    out: dict = {"type": prop.get("type", "string")}
    if "enum" in prop:
        out["enum"] = prop["enum"]
    if "items" in prop:
        out["items"] = {k: v for k, v in prop["items"].items() if k in ("type", "enum")}

    hints = []
    if prop.get("default") is not None:
        hints.append(f"padrão: {json.dumps(prop['default'], ensure_ascii=False)}")
    for key, label in _CONSTRAINT_HINTS:
        if key in prop:
            hints.append(label.format(prop[key]) if "{}" in label else f"{label} {prop[key]}")
    description = prop.get("description", "")
    if hints:
        description = f"{description} ({'; '.join(hints)})".strip()
    if description:
        out["description"] = description
    return out


def to_ollama_parameters(model_schema: dict) -> dict:
    return {
        "type": "object",
        "required": model_schema.get("required", []),
        "properties": {name: _simplify_property(p) for name, p in model_schema.get("properties", {}).items()},
    }


_NULL_STRINGS = {"", "null", "none", "None", "NULL"}


def _clean_arguments(raw: Any) -> dict:
    """Normaliza argumentos vindos do modelo.

    Modelos locais às vezes mandam os argumentos como string JSON, ou mandam
    "null"/"" no lugar de omitir um parâmetro opcional.
    """
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if not (isinstance(v, str) and v.strip() in _NULL_STRINGS)}


class ToolRegistry:
    """Guarda as ferramentas e executa a que o modelo pediu."""

    def __init__(self, tools: list[Tool]) -> None:
        # Ordem estável: o Ollama reaproveita o processamento do prompt quando o
        # começo dele (system + ferramentas) não muda entre requisições.
        self._tools = {t.name: t for t in tools}

    def definitions(self) -> list[dict]:
        return [t.definition() for t in self._tools.values()]

    def run(self, ctx: ToolContext, name: str, raw_input: Any) -> ToolResult:
        started = time.perf_counter()
        tool = self._tools.get(name)
        arguments = _clean_arguments(raw_input)
        is_error = True
        try:
            if tool is None:
                output = {"erro": f"Ferramenta desconhecida: {name}. Disponíveis: {list(self._tools)}"}
            else:
                args = tool.input_model.model_validate(arguments)
                output = tool.handler(ctx, args)
                is_error = False
        except ValidationError as exc:
            # Devolvemos o erro ao modelo: ele costuma corrigir os argumentos e tentar de novo.
            output = {"erro": "Parâmetros inválidos", "detalhes": exc.errors(include_url=False)}
        except ToolUserError as exc:
            output = {"erro": str(exc)}
        except Exception:  # noqa: BLE001 — qualquer falha vira resposta controlada
            logger.exception("Falha na ferramenta %s", name)
            output = {"erro": "Falha interna ao consultar o sistema. Peça desculpas ao cliente e "
                              "ofereça abrir um chamado para a equipe."}
        return ToolResult(
            name=name, input=arguments, output=output,
            is_error=is_error, duration_ms=int((time.perf_counter() - started) * 1000),
        )


class ToolUserError(Exception):
    """Erro de uso da ferramenta que deve ser explicado ao modelo (ex.: seção inexistente)."""


# =============================================================================
# Formatação compartilhada
# =============================================================================
def _availability(row: dict) -> dict:
    status, stock = row["status"], row["stock_quantity"]
    if status == "discontinued":
        return {"disponivel_para_venda": False, "situacao": "descontinuado (não faz mais parte do catálogo)"}
    if status == "coming_soon":
        return {"disponivel_para_venda": False, "situacao": "em breve (ainda não disponível para venda)"}
    if stock <= 0:
        return {"disponivel_para_venda": False, "situacao": "esgotado temporariamente"}
    if stock <= 2:
        return {"disponivel_para_venda": True, "situacao": f"disponível — últimas {stock} unidade(s)"}
    return {"disponivel_para_venda": True, "situacao": f"disponível ({stock} em estoque)"}


def _price(row: dict) -> dict:
    return quote_price(row["price_brl"], row.get("promo_percent"), row.get("promo_campaign")).to_dict()


def _description(row: dict) -> dict:
    if row["description_trusted"]:
        return {"descricao": row["description"]}
    return {
        "descricao": None,
        "aviso_cadastro": "A descrição deste produto está inconsistente no cadastro e foi ocultada. "
                          "Use apenas nome e especificações; não afirme marca/modelo além do nome.",
    }


def _specs(specs: dict) -> dict:
    return {SPEC_LABELS.get(k, k): SPEC_VALUES.get(str(v), v) for k, v in (specs or {}).items()}


def _product_summary(row: dict) -> dict:
    return {
        "produto_id": row["product_id"],
        "nome": row["name"],
        "marca": row["brand"],
        "categoria": row["category_name"],
        **_availability(row),
        **_price(row),
    }


# =============================================================================
# 1. buscar_produtos
# =============================================================================
class BuscarProdutosInput(ToolInput):
    termo: str | None = Field(
        None, max_length=120,
        description="Nome, marca, modelo ou característica (ex.: 'Takamine GD20', 'ukulele tenor', "
                    "'eletroacústico nylon'). Tolera erros de digitação. Deixe vazio para listar "
                    "apenas por categoria e/ou preço.")
    categoria_id: int | None = Field(None, description="ID da categoria (ver lista no prompt).")
    preco_min: float | None = Field(None, ge=0, description="Preço mínimo em reais (preço final, já com promoção).")
    preco_max: float | None = Field(None, gt=0, description="Preço máximo em reais (preço final, já com promoção).")
    somente_disponiveis: bool = Field(
        True, description="true = só produtos à venda e com estoque. Use false para checar itens "
                          "esgotados, descontinuados ou em breve.")
    ordenar_por: Literal["relevancia", "menor_preco", "maior_preco"] = "relevancia"
    limite: int = Field(5, ge=1, le=10, description="Quantidade máxima de produtos retornados.")


def buscar_produtos(ctx: ToolContext, args: BuscarProdutosInput) -> dict:
    term = normalize(args.termo) or None
    with ctx.pool.connection() as conn:
        rows = catalog.search_products(
            conn, term_norm=term, category_id=args.categoria_id,
            min_price=Decimal(str(args.preco_min)) if args.preco_min is not None else None,
            max_price=Decimal(str(args.preco_max)) if args.preco_max is not None else None,
            only_available=args.somente_disponiveis, order_by=args.ordenar_por, limit=args.limite,
        )

    total = rows[0]["total_found"] if rows else 0
    products = []
    for row in rows:
        item = _product_summary(row)
        if term:
            item["relevancia"] = round(float(row["score"]), 2)  # 1.0 = correspondência exata
        products.append(item)

    result: dict = {"total_encontrado": total, "exibindo": len(products), "produtos": products}

    # Cliente pediu um modelo pelo nome e só buscamos itens disponíveis: se o modelo
    # existe mas está esgotado/descontinuado, o agente precisa saber disso para não
    # dizer "não temos esse modelo" (manual 7.3: informar e sugerir alternativas).
    if term and args.somente_disponiveis and (not rows or float(rows[0]["score"]) < 0.9):
        with ctx.pool.connection() as conn:
            unavailable = [r for r in catalog.search_products(
                conn, term_norm=term, category_id=args.categoria_id, min_price=None, max_price=None,
                only_available=False, order_by="relevancia", limit=3,
            ) if float(r["score"]) >= 0.6 and not _availability(r)["disponivel_para_venda"]]
        if unavailable:
            result["indisponiveis_com_esse_nome"] = [_product_summary(r) for r in unavailable]
            result["dica_indisponiveis"] = (
                "O modelo pedido existe no catálogo, mas não está disponível para venda agora. "
                "Diga isso ao cliente (com a situação exata) e ofereça alternativas; use "
                "detalhes_produto para ver as sugestões de produtos semelhantes.")
            return result

    if not rows:
        result["dica"] = ("Nenhum produto encontrado com esses filtros. Se fizer sentido, tente outro "
                          "termo, outra categoria ou somente_disponiveis=false. Não invente produtos.")
    elif term and float(rows[0]["score"]) < 0.6:
        result["dica"] = "Não houve correspondência exata; estes são os resultados mais próximos."
    return result


# =============================================================================
# 2. detalhes_produto
# =============================================================================
class DetalhesProdutoInput(ToolInput):
    produto_id: int = Field(description="ID do produto (obtido em buscar_produtos).")


def detalhes_produto(ctx: ToolContext, args: DetalhesProdutoInput) -> dict:
    with ctx.pool.connection() as conn:
        row = catalog.get_product(conn, args.produto_id)
        if row is None:
            raise ToolUserError(f"Produto {args.produto_id} não existe. Use buscar_produtos para achar o ID.")
        alternatives = [] if _availability(row)["disponivel_para_venda"] else catalog.find_alternatives(conn, row)

    result = {**_product_summary(row), **_description(row), "especificacoes": _specs(row["specs"])}
    if alternatives:
        result["alternativas_disponiveis"] = [_product_summary(a) for a in alternatives]
    return result


# =============================================================================
# 3. consultar_promocoes
# =============================================================================
class ConsultarPromocoesInput(ToolInput):
    produto_id: int | None = Field(None, description="Filtra promoções de um produto específico.")
    campanha: str | None = Field(
        None, max_length=60,
        description="Nome da campanha perguntada pelo cliente (ex.: 'Black Friday', 'Queima de Estoque').")


def consultar_promocoes(ctx: ToolContext, args: ConsultarPromocoesInput) -> dict:
    with ctx.pool.connection() as conn:
        if args.produto_id is None and not args.campanha:
            rows = catalog.list_active_promotions(conn)
        else:
            rows = catalog.list_promotions(conn, product_id=args.produto_id,
                                           campaign_norm=normalize(args.campanha) or None)

    promos = []
    for r in rows:
        item = {
            "produto_id": r["product_id"], "produto": r["product_name"], "campanha": r["campaign"],
            "desconto_percentual": r["discount_percent"], "ativa": r["is_active"],
        }
        if r["is_active"]:
            quote = quote_price(r["price_brl"], r["discount_percent"], r["campaign"])
            item.update(preco_original=format_brl(quote.list_price), preco_promocional=format_brl(quote.final_price))
        else:
            item["preco_atual_sem_desconto"] = format_brl(r["price_brl"])
        promos.append(item)

    active = [p for p in promos if p["ativa"]]
    result: dict = {"promocoes_ativas": len(active), "promocoes": promos}
    if promos and not active:
        result["aviso"] = ("Nenhuma das promoções encontradas está ativa (encerradas). Informe com "
                           "transparência e apresente o preço atual; nunca prometa o desconto.")
    if not promos:
        result["aviso"] = "Nenhuma promoção cadastrada para esse filtro."
    return result


# =============================================================================
# 4. simular_pagamento
# =============================================================================
class SimularPagamentoInput(ToolInput):
    valor: float = Field(gt=0, le=1_000_000, description="Valor total da compra em reais (use 'preco_final_numero').")
    preco_ja_promocional: bool = Field(
        description="true se o valor já tem desconto de promoção (então o PIX não dá desconto extra).")


def simular_pagamento(ctx: ToolContext, args: SimularPagamentoInput) -> dict:
    return simulate_payment(Decimal(str(args.valor)), args.preco_ja_promocional)


# =============================================================================
# 5. consultar_pedido
# =============================================================================
class ConsultarPedidoInput(ToolInput):
    email_ou_telefone: str = Field(
        min_length=5, max_length=120,
        description="E-mail ou telefone do cadastro do cliente — obrigatório para verificar a identidade.")
    numero_pedido: int | None = Field(
        None, ge=1, description="Número do pedido. Se omitido, lista os pedidos mais recentes do cliente.")


_NOT_FOUND = {
    "encontrado": False,
    "mensagem": "Nenhum pedido encontrado para os dados informados. Peça ao cliente para conferir o "
                "número do pedido e o e-mail/telefone do cadastro. Não revele se o pedido existe.",
}


def consultar_pedido(ctx: ToolContext, args: ConsultarPedidoInput) -> dict:
    today = ctx.clock.now().date()
    with ctx.pool.connection() as conn:
        customers = orders.find_customers_by_contact(conn, args.email_ou_telefone)
        if not customers:
            return _NOT_FOUND
        found = orders.get_orders(conn, [c["customer_id"] for c in customers], args.numero_pedido)
        if not found:
            return _NOT_FOUND
        found = found[:5]
        items = {o["order_id"]: orders.get_order_items(conn, o["order_id"]) for o in found}

    result_orders = []
    for o in found:
        entry = {
            "numero_pedido": o["order_id"],
            "data_compra": o["order_date"].strftime("%d/%m/%Y"),
            "status": STATUS_LABELS.get(o["status"], o["status"]),
            "total": format_brl(o["total_brl"]),
            "forma_pagamento": payment_label(o["payment_method"]),
            "itens": [f"{i['quantity']}x {i['product_name']}" for i in items[o["order_id"]]],
            "prazos_e_direitos": evaluate_deadlines(o["status"], o["order_date"], o["estimated_delivery"], today),
        }
        if o["tracking_code"]:
            entry["codigo_rastreio"] = o["tracking_code"]
            entry["onde_rastrear"] = "Site dos Correios ou da Jadlog"
        if o["estimated_delivery"]:
            entry["previsao_entrega"] = o["estimated_delivery"].strftime("%d/%m/%Y")
        if o["notes"]:
            entry["observacoes"] = o["notes"]
        result_orders.append(entry)

    return {
        "encontrado": True,
        # Só o primeiro nome, para a saudação (manual 7.2) — sem expor dados além do necessário.
        "primeiro_nome_cliente": customers[0]["name"].split()[0],
        "pedidos": result_orders,
    }


# =============================================================================
# 6. consultar_politicas
# =============================================================================
class ConsultarPoliticasInput(ToolInput):
    secoes: list[str] = Field(min_length=1, max_length=4,
                              description="Slugs das seções do manual a ler (1 a 4).")


def _make_policy_tool(sections: list[dict]) -> Tool:
    """A lista de seções vem do banco; o índice entra na descrição e no enum."""
    valid = [s["slug"] for s in sections]
    index_lines = []
    for s in sections:
        details = f" ({s['summary']})" if s["summary"] != s["title"] else ""
        index_lines.append(f"- {s['slug']}: {s['number']}. {s['title']}{details}")

    def handler(ctx: ToolContext, args: ConsultarPoliticasInput) -> dict:
        unknown = [slug for slug in args.secoes if slug not in valid]
        if unknown:
            raise ToolUserError(f"Seções inexistentes: {unknown}. Válidas: {valid}")
        with ctx.pool.connection() as conn:
            rows = policies.get_sections(conn, args.secoes)
        return {"fonte": "Manual de Políticas e Procedimentos v2.1 (jun/2025)",
                "secoes": [{"secao": r["slug"], "conteudo": r["content"]} for r in rows]}

    def overrides(parameters: dict) -> None:
        parameters["properties"]["secoes"]["items"]["enum"] = valid

    return Tool(
        name="consultar_politicas",
        description=(
            "Lê seções do Manual de Políticas da loja. Use para qualquer regra ou informação "
            "institucional: endereço, contatos, horários, formas de pagamento, trocas, devoluções, "
            "frete, prazos de entrega, garantia, promoções (regras), privacidade. Leia a seção antes "
            "de responder — não responda regras de memória. Índice do manual:\n" + "\n".join(index_lines)
        ),
        input_model=ConsultarPoliticasInput,
        handler=handler,
        schema_overrides=overrides,
    )


# =============================================================================
# 7. abrir_chamado
# =============================================================================
class AbrirChamadoInput(ToolInput):
    tipo: Literal["reclamacao", "devolucao", "troca", "garantia", "cancelamento",
                  "atendimento_humano", "outro"]
    nome_cliente: str = Field(min_length=2, max_length=120)
    contato: str = Field(min_length=5, max_length=120, description="Telefone ou e-mail para retorno.")
    resumo: str = Field(min_length=10, max_length=1500,
                        description="Resumo objetivo do caso para a equipe (o que o cliente quer e por quê).")
    numero_pedido: int | None = Field(None, ge=1)


def abrir_chamado(ctx: ToolContext, args: AbrirChamadoInput) -> dict:
    now: datetime = ctx.clock.now()
    with ctx.pool.connection() as conn:
        ticket = tickets.create_ticket(
            conn, conversation_id=ctx.conversation_id, ticket_type=args.tipo,
            customer_name=args.nome_cliente, contact=args.contato,
            order_id=args.numero_pedido, summary=args.resumo, now=now,
        )
    return {
        "protocolo": ticket["protocol"],
        "prazo_retorno": "até 24 horas úteis",
        "situacao_da_loja": store_status(now).describe(),
        "observacao": "O chamado foi registrado para a equipe. Não prometa o resultado da análise.",
    }


# =============================================================================
# Montagem
# =============================================================================
def build_registry(policy_sections: list[dict]) -> ToolRegistry:
    return ToolRegistry([
        Tool("buscar_produtos",
             "Busca instrumentos no catálogo com preço atualizado (promoção ativa já aplicada), preço no "
             "PIX e disponibilidade em estoque. Use para perguntas sobre produtos, preços, disponibilidade "
             "e recomendações. Combine termo, categoria e faixa de preço.",
             BuscarProdutosInput, buscar_produtos),
        Tool("detalhes_produto",
             "Detalhes de um produto: especificações técnicas, descrição, preço, estoque e — se ele "
             "estiver indisponível — alternativas semelhantes disponíveis.",
             DetalhesProdutoInput, detalhes_produto),
        Tool("consultar_promocoes",
             "Verifica promoções e se estão ATIVAS. Use quando o cliente perguntar sobre uma "
             "promoção/campanha específica ou sobre o que está em promoção. Sem parâmetros, lista as "
             "promoções ativas.",
             ConsultarPromocoesInput, consultar_promocoes),
        Tool("simular_pagamento",
             "Calcula formas de pagamento para um valor: PIX (com ou sem desconto), débito, boleto e "
             "todas as opções de parcelamento sem juros permitidas pelas regras da loja.",
             SimularPagamentoInput, simular_pagamento),
        Tool("consultar_pedido",
             "Consulta status, itens, rastreio, previsão de entrega e prazos de troca/devolução/garantia "
             "(já calculados) de pedidos. Exige o e-mail ou telefone do cadastro para proteger os dados "
             "do cliente (LGPD).",
             ConsultarPedidoInput, consultar_pedido),
        _make_policy_tool(policy_sections),
        Tool("abrir_chamado",
             "Registra um chamado para a equipe humana: reclamação, devolução, troca, garantia, "
             "cancelamento ou pedido para falar com um atendente. Antes de chamar, tenha nome e contato "
             "do cliente e confirme com ele que deseja abrir o chamado.",
             AbrirChamadoInput, abrir_chamado),
    ])
