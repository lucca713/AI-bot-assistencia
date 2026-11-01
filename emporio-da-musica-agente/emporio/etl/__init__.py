"""ETL: CSVs + manual de políticas -> schema limpo no PostgreSQL.

- ``transform``  leitura e limpeza dos CSVs (Python puro, testável)
- ``policies``   divide o manual (Markdown curado) em seções
- ``loader``     grava tudo no banco em uma única transação
"""
