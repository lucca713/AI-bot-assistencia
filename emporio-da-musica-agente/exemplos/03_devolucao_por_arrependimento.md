# Exemplo 3: Devolução: dados do pedido em tempo real + política (não trivial)

> Gerado automaticamente por `scripts/gerar_exemplos.py` em 01/11/2026 18:49, modelo `gemini-flash-lite-latest` via `gemini`.
> Data/hora simulada: Agora é sexta-feira, 20/02/2026 15:00 (horário de Campo Grande/MS). A loja está ABERTA e fecha às 18:00.

**Cenário:** Cliente quer devolver uma compra. O agente precisa verificar a identidade, consultar o pedido, calcular se está dentro dos 7 dias do direito de arrependimento, explicar as condições do manual e abrir um chamado para a equipe.

---

**🧑 Cliente:** Me arrependi da minha compra, posso devolver meu pedido?

<details><summary>🔧 Ferramentas usadas: `consultar_politicas`</summary>

**consultar_politicas** (1 ms)

Entrada:
```json
{
  "secoes": [
    "trocas_devolucoes"
  ]
}
```
Saída:
```json
{
  "fonte": "Manual de Políticas e Procedimentos v2.1 (jun/2025)",
  "secoes": [
    {
      "secao": "trocas_devolucoes",
      "conteudo": "## 4. Política de Trocas e Devoluções\n\nA Empório da Música segue as diretrizes do Código de Defesa do Consumidor (Lei nº 8.078/90) e oferece condições claras para trocas e devoluções.\n\n### 4.1 Direito de Arrependimento (Compras Online)\n\n- O cliente pode solicitar a devolução em até 7 (sete) dias corridos após o recebimento do produto, sem necessidade de justificativa.\n- O produto deve estar em sua embalagem original, sem sinais de uso, com todos os acessórios e manuais.\n- O reembolso será realizado na mesma forma de pagamento original em até 10 dias úteis.\n- O frete de devolução é por conta da loja em caso de arrependimento.\n\n### 4.2 Trocas por Defeito\n\n- Produtos com defeito de fabricação podem ser trocados em até 30 (trinta) dias corridos após a compra.\n- Após os 30 dias, o cliente deve acionar a garantia diretamente com o fabricante. A Empório da Música pode intermediar o processo mediante solicitação.\n- Danos causados por mau uso, quedas, exposição a umidade excessiva ou modificações não autorizadas não são cobertos.\n\n### 4.3 Trocas por Preferência\n\n- Trocas por preferência (cor, modelo, tamanho) são permitidas em até 7 dias, mediante disponibilidade do produto desejado.\n- O produto deve estar em perfeito estado e na embalagem original.\n- Diferenças de valor serão cobradas ou reembolsadas conforme o caso.\n\n##
... (truncado)
```

</details>

**🎸 Tom:** Pode sim! Para compras feitas pela internet, você tem até 7 dias corridos após o recebimento para solicitar a devolução por arrependimento. 

O instrumento precisa estar na embalagem original, sem sinais de uso e com todos os acessórios e manuais, combinado? 

Para a gente dar início ao processo, me informe o **número do seu pedido** junto com o seu **e-mail ou telefone cadastrado**? Assim eu já localizo os dados por aqui! 🎸

<sub>2.1s · 2 chamada(s) ao modelo</sub>

---

**🧑 Cliente:** É o pedido 7, meu e-mail é leticia.rocha@jmail.com

<details><summary>🔧 Ferramentas usadas: `consultar_pedido`</summary>

**consultar_pedido** (2 ms)

Entrada:
```json
{
  "email_ou_telefone": "leticia.rocha@jmail.com",
  "numero_pedido": 7
}
```
Saída:
```json
{
  "encontrado": true,
  "primeiro_nome_cliente": "Letícia",
  "pedidos": [
    {
      "numero_pedido": 7,
      "data_compra": "03/02/2026",
      "status": "Entregue",
      "total": "R$ 159,90",
      "forma_pagamento": "Cartão de crédito em 3x",
      "itens": [
        "1x Shelby SU-21S Soprano Sunburst"
      ],
      "prazos_e_direitos": {
        "data_de_referencia": "20/02/2026",
        "data_recebimento_considerada": "17/02/2026",
        "aviso": "A base não registra a data real de entrega; foi considerada a data prevista de entrega. Se o cliente recebeu em outra data, confirme com ele.",
        "dias_desde_o_recebimento": 3,
        "arrependimento_7_dias": {
          "dentro_do_prazo": true,
          "prazo_final": "24/02/2026",
          "dias_restantes": 4
        },
        "troca_por_preferencia_7_dias": {
          "dentro_do_prazo": true,
          "prazo_final": "24/02/2026",
          "dias_restantes": 4
        },
        "troca_por_defeito_na_loja_30_dias": {
          "dentro_do_prazo": true,
          "prazo_final": "05/03/2026",
          "dias_restantes": 13
        },
        "garantia_legal_90_dias": {
          "dentro_do_prazo": true,
          "prazo_final": "18/05/2026",
          "dias_restantes": 87
        }
      },
      "codigo_rastreio": "BRKR1122334BR",
      "onde_rastrear": "Site dos Correios ou da Jadlog",
      "previsao_entrega": "17/02/2026"
    }
  ]
}
```

</details>

**🎸 Tom:** Oi, Letícia! Localizei seu pedido por aqui. 

Como você recebeu o **Shelby SU-21S Soprano Sunburst** há poucos dias, você ainda está super dentro do prazo de 7 dias para o arrependimento (o prazo vai até 24/02). 

Para eu abrir o chamado de devolução com a nossa equipe, você me confirma o seu nome completo e um telefone de contato para retorno? 🎸

<sub>2.0s · 2 chamada(s) ao modelo</sub>

---

**🧑 Cliente:** Quero sim, pode abrir. Meu nome é Letícia Rocha e meu telefone é (67) 99789-0123.

<details><summary>🔧 Ferramentas usadas: `abrir_chamado`</summary>

**abrir_chamado** (2 ms)

Entrada:
```json
{
  "numero_pedido": 7,
  "tipo": "devolucao",
  "contato": "(67) 99789-0123",
  "resumo": "Cliente solicita a devolução do pedido 7 (Shelby SU-21S Soprano Sunburst) por arrependimento, dentro do prazo de 7 dias.",
  "nome_cliente": "Letícia Rocha"
}
```
Saída:
```json
{
  "protocolo": "EMP-20260220-00001",
  "prazo_retorno": "até 24 horas úteis",
  "situacao_da_loja": "Agora é sexta-feira, 20/02/2026 15:00 (horário de Campo Grande/MS). A loja está ABERTA e fecha às 18:00.",
  "observacao": "O chamado foi registrado para a equipe. Não prometa o resultado da análise."
}
```

</details>

**🎸 Tom:** Prontinho, Letícia! O seu chamado de devolução foi aberto com sucesso.

O seu número de protocolo é **EMP-20260220-00001**. Nossa equipe vai analisar o caso e entrará em contato com você pelo telefone informado em até 24 horas úteis para orientar sobre os próximos passos e o envio do produto. 

Se precisar de mais alguma coisa é só chamar! 🎸

<sub>2.3s · 2 chamada(s) ao modelo</sub>

---

### Verificação automática

- Ferramentas esperadas: `abrir_chamado`, `consultar_pedido`, `consultar_politicas` → ✅ todas usadas
- Ferramentas efetivamente usadas: `abrir_chamado`, `consultar_pedido`, `consultar_politicas`
- Tempo total de resposta: 6.4s
