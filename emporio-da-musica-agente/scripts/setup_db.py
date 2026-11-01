"""Cria o schema e carrega os dados (CSVs + manual de políticas).

Uso:
    python -m scripts.setup_db           # cria/atualiza e recarrega os dados
    python -m scripts.setup_db --reset   # apaga o schema inteiro (inclusive conversas) e recria

Pode rodar quantas vezes quiser: os dados de catálogo/pedidos/políticas são
recarregados; conversas e chamados são preservados (exceto com --reset).
"""

import argparse

from emporio.config import DATA_DIR, get_settings
from emporio.etl.loader import load_everything, table_counts
from emporio.etl.policies import load_policy_sections
from emporio.etl.transform import load_clean_data, quality_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="apaga e recria o schema do zero")
    args = parser.parse_args()
    settings = get_settings()

    print("1/3 Lendo e tratando os CSVs...")
    data = load_clean_data(DATA_DIR / "raw")
    sections = load_policy_sections(DATA_DIR / "politicas_da_loja.md")

    print("\nRelatório de qualidade dos dados:")
    for finding in quality_report(data):
        print(f"  - {finding}")

    print(f"\n2/3 Gravando no PostgreSQL ({settings.db_name}, schema '{settings.db_schema}')...")
    load_everything(settings.db_conninfo, settings.db_schema, data, sections, reset=args.reset)

    print("\n3/3 Conferindo:")
    for table, count in table_counts(settings.db_conninfo, settings.db_schema).items():
        print(f"  {table:<16} {count:>4} linhas")
    print("\nPronto! Agora rode a API (uvicorn emporio.api.main:app) ou a CLI (python -m emporio.cli).")


if __name__ == "__main__":
    main()
