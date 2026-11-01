"""Acesso ao PostgreSQL.

Padrão "repository": cada módulo agrupa as consultas SQL de uma área
(catálogo, pedidos, políticas, conversas, chamados). As ferramentas do
agente nunca escrevem SQL; elas chamam essas funções. Assim o LLM não gera
SQL livre (o que seria um risco de segurança e de consultas erradas) e cada
consulta é revisável e testável.
"""
