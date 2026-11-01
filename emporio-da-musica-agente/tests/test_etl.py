"""Tratamento dos dados: CSVs reais do desafio e manual de políticas."""

from emporio.config import DATA_DIR
from emporio.domain.data_quality import description_conflicts, detect_brand
from emporio.domain.text import normalize, only_digits
from emporio.etl.policies import load_policy_sections, parse_policy_markdown
from emporio.etl.transform import load_clean_data, quality_report


def test_normalize_and_digits():
    assert normalize("  Violão  ELÉTRICO ") == "violao eletrico"
    assert only_digits("(67) 99812-3456") == "67998123456"


def test_brand_detection_prefers_first_in_name():
    assert detect_brand("Music Man Bass 1X Electric Bass") == "Music Man"
    assert detect_brand("Bateria Acústica Yamaha Kit 1 Studio") == "Yamaha"
    assert detect_brand("Produto sem marca") is None


def test_description_conflicts():
    assert description_conflicts("Korg Synth 1 Pro", "Sintetizador Roland com 88 teclas", {"keys": "61"}) == [
        "descrição cita a marca Roland, mas o produto é Korg",
        "descrição fala em 88 teclas, specs indicam 61",
    ]
    assert description_conflicts("Yamaha C40", "Violão clássico Yamaha", {"strings": "nylon"}) == []


def test_real_csvs_load_and_flag_inconsistent_products():
    data = load_clean_data(DATA_DIR / "raw")
    assert len(data.products) == 65
    assert len(data.orders) == 20
    untrusted = {p["product_id"] for p in data.products if not p["description_trusted"]}
    assert untrusted == {135, 137, 139, 140, 142, 144}
    # emails normalizados em minúsculo e telefones só com dígitos
    assert all(c["phone_digits"].isdigit() for c in data.customers)
    findings = "\n".join(quality_report(data))
    assert "bruno.martins@jmail.com" in findings
    assert "Categoria 6" in findings


def test_policy_sections_from_curated_manual():
    sections = load_policy_sections(DATA_DIR / "politicas_da_loja.md")
    assert [s.number for s in sections] == list(range(1, 11))
    by_slug = {s.slug: s for s in sections}
    assert "7 (sete) dias corridos" in by_slug["trocas_devolucoes"].content
    assert "4.1 Direito de Arrependimento" in by_slug["trocas_devolucoes"].summary
    assert "<!--" not in by_slug["sobre_a_loja"].content


def test_policy_parser_rejects_duplicates():
    md = "## 1. A {#x}\ntexto\n## 2. B {#x}\ntexto"
    try:
        parse_policy_markdown(md)
    except ValueError:
        return
    raise AssertionError("deveria rejeitar slugs duplicados")
