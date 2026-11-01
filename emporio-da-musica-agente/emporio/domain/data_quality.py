"""Detecção de inconsistências no cadastro de produtos.

Encontramos produtos cujo NOME diz uma coisa e a DESCRIÇÃO diz outra, por
exemplo:
    135 "Music Man Bass 1X"        -> descrição fala em "Fender Jazz Bass"
    139 "Bateria ... Yamaha Kit 1" -> descrição fala em "Pearl Export"
    142 "Korg Synth 1 Pro"         -> descrição: "Roland com 88 teclas" (specs: 61)

Se o agente repassar essa descrição, ele informa ao cliente marca/modelo
errados, o que o manual chama de risco de "propaganda enganosa". Decisão: o
nome e as especificações estruturadas (specs) são a fonte da verdade; a
descrição livre marcada como inconsistente não é mostrada ao agente.
"""

import re

from emporio.domain.text import normalize

# Marcas presentes no catálogo (e algumas citadas nas descrições).
KNOWN_BRANDS = (
    "Music Man", "Yamaha", "Tagima", "Giannini", "Rozini", "Shelby", "Crafter",
    "Martin", "Taylor", "Takamine", "Kala", "Ohana", "Kalani", "Fender",
    "Gibson", "Ibanez", "PRS", "Pearl", "Tama", "Korg", "Nord", "Roland",
)


def _mentions(brand: str, text_norm: str) -> bool:
    return re.search(rf"\b{re.escape(normalize(brand))}\b", text_norm) is not None


def detect_brand(name: str) -> str | None:
    """Marca encontrada no nome do produto (a primeira que aparecer)."""
    name_norm = normalize(name)
    found = [(name_norm.find(normalize(b)), b) for b in KNOWN_BRANDS if _mentions(b, name_norm)]
    return min(found)[1] if found else None


def description_conflicts(name: str, description: str, specs: dict) -> list[str]:
    """Motivos pelos quais a descrição contradiz o nome/specs (vazio = ok)."""
    reasons: list[str] = []
    desc_norm = normalize(description)
    brand = detect_brand(name)

    # 1) A descrição cita outra marca que não é a do produto.
    if brand:
        others = [b for b in KNOWN_BRANDS
                  if b != brand and _mentions(b, desc_norm) and not _mentions(b, normalize(name))]
        if others:
            reasons.append(f"descrição cita a marca {', '.join(others)}, mas o produto é {brand}")

    # 2) Números de cordas/teclas na descrição diferentes das specs.
    for spec_key, word in (("strings", "cordas"), ("keys", "teclas")):
        spec_value = str(specs.get(spec_key, ""))
        if not spec_value.isdigit():
            continue  # ex.: strings = "nylon" (violões) não é número
        for mentioned in re.findall(rf"(\d+)\s+{word}", desc_norm):
            if mentioned != spec_value:
                reasons.append(f"descrição fala em {mentioned} {word}, specs indicam {spec_value}")
    return reasons
