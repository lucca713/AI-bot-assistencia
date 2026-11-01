"""Divide o manual de políticas (Markdown curado) em seções.

Estratégia de retrieval (justificada no README): o manual tem só 10 seções
bem delimitadas (~3 mil tokens). Em vez de embeddings + busca vetorial, cada
seção vira um documento com um slug, e o agente recebe o ÍNDICE (slug +
título + subtítulos) na descrição da ferramenta ``consultar_politicas``. O
próprio LLM escolhe quais seções ler. Para um documento pequeno e bem
estruturado isso é mais preciso que similaridade vetorial (que pode trazer
um trecho parecido, mas errado) e não exige infraestrutura extra.
"""

import re
from dataclasses import dataclass
from pathlib import Path

# "## 4. Política de Trocas e Devoluções {#trocas_devolucoes}"
SECTION_RE = re.compile(r"^## (\d+)\.\s+(.+?)\s+\{#([a-z0-9_]+)\}\s*$")
SUBSECTION_RE = re.compile(r"^### (.+?)\s*$")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass(frozen=True)
class PolicySection:
    slug: str
    number: int
    title: str
    summary: str      # "4.1 Direito de Arrependimento; 4.2 Trocas por Defeito; ..."
    content: str      # markdown da seção, incluindo o título


def parse_policy_markdown(markdown: str) -> list[PolicySection]:
    """Converte o manual em uma lista de seções (na ordem do documento)."""
    text = HTML_COMMENT_RE.sub("", markdown)
    sections: list[PolicySection] = []
    current: dict | None = None

    def close_current() -> None:
        if current:
            sections.append(PolicySection(
                slug=current["slug"],
                number=current["number"],
                title=current["title"],
                summary="; ".join(current["subsections"]) or current["title"],
                content="\n".join(current["lines"]).strip(),
            ))

    for line in text.splitlines():
        header = SECTION_RE.match(line)
        if header:
            close_current()
            number, title, slug = int(header.group(1)), header.group(2), header.group(3)
            current = {"slug": slug, "number": number, "title": title,
                       "subsections": [], "lines": [f"## {number}. {title}"]}
            continue
        if current is None:
            continue  # texto antes da primeira seção (capa) é ignorado
        sub = SUBSECTION_RE.match(line)
        if sub:
            current["subsections"].append(sub.group(1))
        current["lines"].append(line)
    close_current()

    slugs = [s.slug for s in sections]
    if len(slugs) != len(set(slugs)):
        raise ValueError("Slugs de seção duplicados no manual de políticas.")
    if not sections:
        raise ValueError("Nenhuma seção encontrada. Os títulos seguem o formato '## N. Título {#slug}'?")
    return sections


def load_policy_sections(path: Path) -> list[PolicySection]:
    return parse_policy_markdown(path.read_text(encoding="utf-8"))
