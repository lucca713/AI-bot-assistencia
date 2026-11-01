# ✅ O que falta para entregar o desafio

> Arquivo de trabalho pessoal. **Apague antes da entrega**: o avaliador não precisa ver isso.
> Siga na ordem. Marque `[x]` conforme for concluindo.

---

## Etapa 0: Agora, neste computador

- [ ] **Enviar a limpeza do repositório para o GitHub.** O `.txt` com a senha e a pasta do enunciado deixaram de ser versionados, mas continuam no seu computador:
  ```bash
  cd ~/Área\ de\ trabalho/sistema_ia_para_loja_musica
  git add -A
  git commit -m "chore: remove credenciais e enunciado do repositório, adiciona .gitignore"
  git push
  ```
- [ ] **Trocar a senha do PostgreSQL.** O arquivo com a senha antiga ainda aparece no 1º commit do histórico, e trocar a senha a torna inútil:
  ```bash
  sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'nova_senha_forte';"
  ```
  Depois, atualize `DB_PASSWORD` no `.env`.

---

## Etapa 1: Preparar o outro computador

Os detalhes de cada passo estão no README, seção **Como rodar**.

- [ ] Clonar o repositório: `git clone https://github.com/lucca713/AI-bot-assistencia.git`
- [ ] Abrir o Claude Code **na pasta do repositório** (`cd AI-bot-assistencia && claude`). Ele lê o `CLAUDE.md` sozinho e já sabe o que é o projeto e o que falta. Para começar, peça algo como *"leia o CLAUDE.md e me ajude a rodar o projeto"*.
- [ ] Entrar na pasta do projeto: `cd AI-bot-assistencia/emporio-da-musica-agente`
- [ ] Criar o ambiente Python e instalar as dependências:
  ```bash
  python -m venv .venv
  source .venv/bin/activate        # Windows: .venv\Scripts\activate
  pip install -r requirements-dev.txt
  ```
- [ ] Instalar o [Ollama](https://ollama.com/download) e baixar o modelo: `ollama pull qwen3:14b`. Escolha o modelo pela memória da placa de vídeo; a tabela está no README.
- [ ] Instalar o PostgreSQL e criar o banco `loja_musica` (README, passos 3.1 e 3.2).
- [ ] Criar o `.env` a partir do `.env.example` e preencher a senha do banco (README, passo 3.3).
- [ ] Carregar os dados: `python -m scripts.setup_db`
- [ ] Rodar os testes: `pytest` (todos devem passar)

---

## Etapa 2: Testar o agente na mão

- [ ] Subir a interface: `uvicorn emporio.api.main:app` e abrir <http://localhost:8000>
- [ ] Testar estas perguntas e conferir no painel **Bastidores** se a ferramenta usada faz sentido:

| Pergunta | O que conferir |
|---|---|
| Quais opções de violões disponíveis custando até R$1000? | lista só violões disponíveis, com preço ≤ R$ 1.000 |
| Quanto custa o Takamine GD20? | **R$ 2.199,00**; no PIX **R$ 2.089,05** |
| Qual o endereço da loja? | Rua 14 de Maio, 3200, Centro, Campo Grande/MS |
| Me arrependi da minha compra, posso devolver meu pedido? | pede o número do pedido e o e-mail **antes** de consultar |
| Vocês vendem cordas? | explica que a loja só vende instrumentos, sem inventar loja parceira |
| Tem Black Friday? | diz que a promoção não está ativa e não promete desconto |
| Qual a capital da França? | recusa com educação e volta para o assunto da loja |

> Para testar devolução de forma realista, coloque `SIMULATED_NOW=2026-02-20T15:00` no `.env`
> e use o **pedido 7** com o e-mail **leticia.rocha@jmail.com** (entregue há 3 dias, dentro do prazo de 7 dias).

- [ ] **Se o agente errar muito**, tente nesta ordem:
  1. ligar o modo pensar: `LLM_THINK=true` no `.env` (fica mais lento, mas decide melhor);
  2. usar um modelo maior (`qwen3:32b`, se a placa aguentar);
  3. ajustar o prompt em `emporio/agent/prompts.py` ou as descrições das ferramentas em `emporio/agent/tools.py`.

  Cada ajuste vira um commit. Isso mostra progresso real no histórico.

---

## Etapa 3: Gerar as conversas de exemplo (entregável obrigatório)

O enunciado pede de 3 a 5 conversas, sendo pelo menos uma não trivial.

- [ ] Gerar: `python -m scripts.gerar_exemplos` (cria 5 arquivos em `exemplos/`)
- [ ] Abrir cada arquivo e conferir:
  - [ ] a "Verificação automática" no fim mostra ✅;
  - [ ] os preços citados batem com a saída das ferramentas;
  - [ ] o exemplo 3 (devolução) mostra a verificação do pedido, o prazo de 7 dias e o protocolo do chamado.
- [ ] Se algum cenário sair ruim, ajuste e regere só ele: `python -m scripts.gerar_exemplos --only 3`
- [ ] (Opcional) Tirar um print da interface web com uma conversa e salvar em `exemplos/` (o enunciado aceita imagem).
- [ ] Commit: `git add exemplos && git commit -m "docs: adiciona conversas de exemplo geradas pelo agente"`

---

## Etapa 4: Finalizar o README

- [ ] Seção **Uso de assistentes de código**:
  - [ ] apagar a linha "✏️ Revise e complete esta seção…";
  - [ ] preencher os trechos entre colchetes do item 5 (máquina, modelo usado, o que você ajustou depois de testar);
  - [ ] reler tudo e deixar com as suas palavras. O avaliador quer entender o **seu** workflow.
- [ ] Se trocou de modelo, atualizar o padrão citado no README e no `.env.example`.
- [ ] Commit: `git commit -am "docs: completa README com workflow e resultados dos testes"`

---

## Etapa 5: Organização do repositório

- [ ] **Deixar o README visível na página inicial do GitHub.** Hoje o projeto está dentro da subpasta `emporio-da-musica-agente/`, e quem abre o repositório não vê o README. Escolha uma opção:
  - **(a) Mover o projeto para a raiz**, a melhor opção. Na pasta raiz do repositório:
    ```bash
    git rm emporio-da-musica-agente/.gitignore     # a raiz já tem um .gitignore completo
    git mv emporio-da-musica-agente/* emporio-da-musica-agente/.env.example .
    git commit -m "chore: move projeto para a raiz do repositório"
    ```
    (O `.env` não é versionado; mova-o à mão: `mv emporio-da-musica-agente/.env .`)
  - **(b)** Criar um `README.md` curto na raiz com um link para `emporio-da-musica-agente/README.md`.
- [ ] Conferir que não há segredos versionados: `git ls-files | grep -iE "\.env$|senha|password|DB HOST"` (não deve aparecer nada).
- [ ] Apagar os arquivos de trabalho (este checklist e o `CLAUDE.md` da raiz):
  ```bash
  git rm PENDENCIAS.md CLAUDE.md   # ajuste os caminhos se o projeto ainda estiver na subpasta
  git commit -m "chore: remove anotações de trabalho"
  ```
- [ ] Último `git push`.

---

## Etapa 6: Entrega

- [ ] Abrir o repositório no GitHub **deslogado** (aba anônima) e confirmar que ele é público e que o README aparece.
- [ ] Responder o e-mail do processo seletivo com o link: <https://github.com/lucca713/AI-bot-assistencia>
- [ ] **Não alterar mais nada no repositório depois do prazo.**

### Checklist final dos entregáveis do enunciado

| Entregável | Onde está | OK? |
|---|---|---|
| Repositório público com histórico de commits real | GitHub | [ ] |
| README: como rodar (ambiente, modelo, comandos) | README, "Como rodar" | [ ] |
| README: justificativas (framework, LLM, retrieval, prompt) | README, "Decisões técnicas" | [ ] |
| README: limitações e o que faria com mais tempo | README, "Limitações…" | [ ] |
| README: uso de assistentes de código | README, "Uso de assistentes…" | [ ] |
| 3 a 5 conversas, ao menos uma não trivial | `exemplos/` | [ ] |
