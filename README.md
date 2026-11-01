# 🎸 Empório da Música: agente de atendimento com IA

Agente de atendimento por mensagens de texto para a **Empório da Música**, loja (fictícia) de instrumentos musicais em Campo Grande/MS. Desenvolvido em **Python** como desafio técnico para a vaga de AI Engineer.

O agente responde dúvidas recorrentes dos clientes sobre produtos, preços, disponibilidade, pedidos, trocas, pagamento, frete e horários. Ele consulta **dados reais da operação** (PostgreSQL) e o **manual de políticas da loja**, com a persona e o tom de voz definidos pela própria loja.

## Destaques

- **LLM local via Ollama:** gratuito, sem chave de API, e os dados dos clientes não saem da máquina.
- **Function calling com 7 ferramentas:** o modelo decide *o que* consultar; o SQL é fixo e revisado (o LLM nunca escreve SQL).
- **Regras de negócio em Python:** preço, PIX, parcelamento, prazos de devolução e horário são calculados pelo código, não pelo modelo.
- **Privacidade (LGPD):** pedidos só são consultados com o e-mail ou telefone do cadastro.
- **Interface web** com respostas em streaming e um painel **"Bastidores"**, que mostra cada ferramenta usada pelo agente.
- **Histórico de conversa e chamados** para a equipe humana, salvos no PostgreSQL.

## 📖 Documentação completa

**➡️ [`emporio-da-musica-agente/README.md`](emporio-da-musica-agente/README.md)**

Lá estão: como rodar (passo a passo, incluindo a conexão com o banco), arquitetura, justificativa das decisões técnicas, tratamento dos dados, suposições, limitações e uso de assistentes de código.

## Início rápido

```bash
cd emporio-da-musica-agente
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
ollama pull qwen3:14b                               # ou, sem GPU: LLM_PROVIDER=gemini + LLM_API_KEY no .env
cp .env.example .env                                # preencha os dados do PostgreSQL
python -m scripts.setup_db                          # cria as tabelas e carrega os dados
uvicorn emporio.api.main:app                        # abra http://localhost:8000
```

## Estrutura

```
emporio-da-musica-agente/
├── emporio/      código do agente (domínio, ETL, banco, agente, API)
├── web/          interface de chat
├── data/         CSVs da loja e manual de políticas
├── scripts/      setup do banco e geração das conversas de exemplo
├── exemplos/     conversas de exemplo geradas pelo agente
└── tests/        testes automatizados
```
