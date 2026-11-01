# Exemplo 2: Consulta de preço + promoção expirada

> Gerado automaticamente por `scripts/gerar_exemplos.py` em 01/11/2026 18:48, modelo `gemini-flash-lite-latest` via `gemini`.
> Data/hora simulada: Agora é sexta-feira, 20/02/2026 11:00 (horário de Campo Grande/MS). A loja está ABERTA e fecha às 18:00.

**Cenário:** Cliente pergunta o preço do Takamine GD20 e cita uma promoção que já foi encerrada (o manual exige transparência e proíbe prometer desconto vencido).

---

**🧑 Cliente:** Quanto custa o Takamine GD20?

<details><summary>🔧 Ferramentas usadas: `buscar_produtos`, `simular_pagamento`</summary>

**buscar_produtos** (5 ms)

Entrada:
```json
{
  "termo": "Takamine GD20"
}
```
Saída:
```json
{
  "total_encontrado": 4,
  "exibindo": 4,
  "produtos": [
    {
      "produto_id": 95,
      "nome": "Takamine GD20 Dreadnought Natural",
      "marca": "Takamine",
      "categoria": "Violões",
      "disponivel_para_venda": true,
      "situacao": "disponível (5 em estoque)",
      "preco_tabela": "R$ 2.199,00",
      "preco_final": "R$ 2.199,00",
      "preco_final_numero": 2199.0,
      "preco_pix": "R$ 2.089,05",
      "promocao_ativa": null,
      "relevancia": 1.0
    },
    {
      "produto_id": 115,
      "nome": "Takamine GC1CE Elétrico Nylon Natural",
      "marca": "Takamine",
      "categoria": "Violões",
      "disponivel_para_venda": true,
      "situacao": "disponível (5 em estoque)",
      "preco_tabela": "R$ 2.499,00",
      "preco_final": "R$ 2.499,00",
      "preco_final_numero": 2499.0,
      "preco_pix": "R$ 2.374,05",
      "promocao_ativa": null,
      "relevancia": 0.71
    },
    {
      "produto_id": 100,
      "nome": "Takamine GC5CE Elétrico Nylon Natural",
      "marca": "Takamine",
      "categoria": "Violões",
      "disponivel_para_venda": true,
      "situacao": "disponível (3 em estoque)",
      "preco_tabela": "R$ 3.299,00",
      "preco_final": "R$ 3.299,00",
      "preco_final_numero": 3299.0,
      "preco_pix": "R$ 3.134,05",
      "promocao_ativa": null,
      "relevancia": 0.71
    },
    {
      "produto_id": 105,
      "nome": "Takamine GN51CE Elétrico Aço Natural",
      "marca": "Takamine",
      "categoria": "Violões",
      "d
... (truncado)
```

**simular_pagamento** (0 ms)

Entrada:
```json
{
  "valor": 2199,
  "preco_ja_promocional": false
}
```
Saída:
```json
{
  "valor_base": "R$ 2.199,00",
  "pix": {
    "valor": "R$ 2.089,05",
    "observacao": "5% de desconto (economia de R$ 109,95)."
  },
  "debito": {
    "valor": "R$ 2.199,00",
    "observacao": "À vista, todas as bandeiras."
  },
  "boleto": {
    "valor": "R$ 2.199,00",
    "observacao": "À vista, compensação em até 3 dias úteis."
  },
  "cartao_credito": {
    "maximo_parcelas_sem_juros": 12,
    "parcela_no_maximo": "12x de R$ 183,25",
    "opcoes": [
      "1x de R$ 2.199,00",
      "2x de R$ 1.099,50",
      "3x de R$ 733,00",
      "4x de R$ 549,75",
      "5x de R$ 439,80",
      "6x de R$ 366,50",
      "7x de R$ 314,14",
      "8x de R$ 274,88",
      "9x de R$ 244,33",
      "10x de R$ 219,90",
      "11x de R$ 199,91",
      "12x de R$ 183,25"
    ]
  },
  "pode_combinar_formas_de_pagamento": true,
  "regra_combinacao": "Combinação (ex.: PIX + cartão) permitida para compras acima de R$ 2.000,00."
}
```

</details>

**🎸 Tom:** O **Takamine GD20 Dreadnought Natural** custa **R$ 2.199,00**. No PIX, tem 5% de desconto e sai por **R$ 2.089,05**, ou você pode parcelar em até 12x sem juros de **R$ 183,25** no cartão de crédito. Temos ele disponível em estoque por aqui!

Posso te ajudar com mais alguma coisa?

<sub>9.3s · 3 chamada(s) ao modelo</sub>

---

**🧑 Cliente:** Vi que ele estava na Oferta Especial com 12% de desconto. Ainda tá valendo?

<details><summary>🔧 Ferramentas usadas: `consultar_promocoes`</summary>

**consultar_promocoes** (1 ms)

Entrada:
```json
{
  "produto_id": 95,
  "campanha": "Oferta Especial"
}
```
Saída:
```json
{
  "promocoes_ativas": 0,
  "promocoes": [
    {
      "produto_id": 95,
      "produto": "Takamine GD20 Dreadnought Natural",
      "campanha": "Oferta Especial",
      "desconto_percentual": 12,
      "ativa": false,
      "preco_atual_sem_desconto": "R$ 2.199,00"
    }
  ],
  "aviso": "Nenhuma das promoções encontradas está ativa (encerradas). Informe com transparência e apresente o preço atual; nunca prometa o desconto."
}
```

</details>

**🎸 Tom:** A campanha "Oferta Especial" já foi encerrada, então esse desconto de 12% não está mais ativo, viu? O valor oficial do **Takamine GD20** é **R$ 2.199,00**, mas lembrando que no PIX ele sai por **R$ 2.089,05** ou em até 12x sem juros de **R$ 183,25** no cartão de crédito. 

Se quiser garantir o seu, temos unidades disponíveis em estoque. Posso tirar mais alguma dúvida sobre ele?

<sub>2.3s · 2 chamada(s) ao modelo</sub>

---

### Verificação automática

- Ferramentas esperadas: `buscar_produtos`, `consultar_promocoes` → ✅ todas usadas
- Ferramentas efetivamente usadas: `buscar_produtos`, `consultar_promocoes`, `simular_pagamento`
- Tempo total de resposta: 11.6s
