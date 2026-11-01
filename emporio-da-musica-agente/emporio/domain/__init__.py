"""Regras de negócio da loja, em Python puro.

Por que separar isso do LLM? Porque contas (descontos, parcelas, prazos em
dias) são exatamente o tipo de tarefa em que modelos de linguagem erram de
forma silenciosa. O agente decide *quando* precisa de uma informação; o
código calcula *qual* é a informação. O manual da loja diz: "nunca fornecer
informações sobre preços, estoque ou prazos sem consultar o sistema".
"""
