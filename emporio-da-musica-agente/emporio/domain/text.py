"""Normalização de texto para buscas tolerantes ("violão" == "violao" == "VIOLÃO")."""

import re
import unicodedata


def normalize(text: str | None) -> str:
    """Minúsculas, sem acentos e com espaços simples."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", without_accents.lower()).strip()


def only_digits(text: str | None) -> str:
    """'(67) 99812-3456' -> '67998123456'."""
    return re.sub(r"\D", "", text or "")
