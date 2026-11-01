/* =============================================================================
   Front-end do chat (JavaScript puro, sem build).

   Fluxo de uma mensagem:
     1. POST /api/chat/stream com { message, conversation_id }
     2. A resposta chega em streaming (Server-Sent Events). Eventos:
          start      -> id da conversa (guardado no localStorage)
          token      -> pedaço do texto sendo gerado
          tool_start -> o agente começou a consultar uma ferramenta
          tool_end   -> resultado da ferramenta (vai para o painel "Bastidores")
          done       -> texto final + estatísticas
          error      -> falha (ex.: Ollama desligado)
   ============================================================================= */

const $ = (sel) => document.querySelector(sel);
const messagesEl = $("#messages");
const inputEl = $("#input");
const sendBtn = $("#send");
const traceList = $("#trace-list");

// Nome amigável de cada ferramenta, mostrado enquanto o agente trabalha.
const TOOL_LABELS = {
  buscar_produtos: "🔎 Buscando no catálogo",
  detalhes_produto: "🎼 Vendo detalhes do produto",
  consultar_promocoes: "🏷️ Checando promoções",
  simular_pagamento: "💳 Calculando pagamento",
  consultar_pedido: "📦 Consultando pedido",
  consultar_politicas: "📘 Lendo as políticas da loja",
  abrir_chamado: "📝 Abrindo chamado para a equipe",
};

const STORAGE_KEY = "emporio.conversation_id";
let conversationId = storageGet(STORAGE_KEY);
let busy = false;
let turnCounter = 0;

// ---------------------------------------------------------------- utilitários
function storageGet(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}
function storageSet(key, value) {
  try { value ? localStorage.setItem(key, value) : localStorage.removeItem(key); } catch { /* sem storage */ }
}

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/** Markdown mínimo e seguro: negrito, itálico, listas e parágrafos.
 *  O HTML é escapado ANTES, então o texto do modelo nunca injeta tags. */
function renderMarkdown(text) {
  const inline = (s) => s
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])\*(?!\s)(.+?)\*(?=[\s).,!?:;]|$)/g, "$1<strong>$2</strong>") // *negrito* estilo WhatsApp
    .replace(/(^|[\s(])_(?!\s)(.+?)_(?=[\s).,!?:;]|$)/g, "$1<em>$2</em>");

  const html = [];
  let list = null;
  for (const raw of escapeHtml(text).split("\n")) {
    const line = raw.trim();
    const item = line.match(/^(?:[-•*]|\d+[.)])\s+(.*)$/);
    if (item) {
      list = list || [];
      list.push(`<li>${inline(item[1])}</li>`);
      continue;
    }
    if (list) { html.push(`<ul>${list.join("")}</ul>`); list = null; }
    if (line) html.push(`<p>${inline(line)}</p>`);
  }
  if (list) html.push(`<ul>${list.join("")}</ul>`);
  return html.join("");
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ---------------------------------------------------------------- mensagens
function addMessage(role, text) {
  $("#empty-state")?.remove();
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const avatar = role === "assistant" ? '<div class="avatar" aria-hidden="true">🎸</div>' : "";
  wrap.innerHTML = `${avatar}<div><div class="bubble"></div><div class="msg-meta"></div></div>`;
  const bubble = wrap.querySelector(".bubble");
  if (role === "user") bubble.textContent = text;
  else bubble.innerHTML = text ? renderMarkdown(text) : '<span class="typing"><span></span><span></span><span></span></span>';
  messagesEl.appendChild(wrap);
  scrollToBottom();
  return { bubble, meta: wrap.querySelector(".msg-meta") };
}

// ---------------------------------------------------------------- painel
function addTraceTurn(question) {
  turnCounter += 1;
  if (turnCounter === 1) traceList.innerHTML = "";
  const turn = document.createElement("div");
  turn.className = "trace-turn";
  turn.innerHTML = `<h3>Mensagem ${turnCounter}</h3><p class="trace-question"></p><div class="items"></div><div class="trace-stats"></div>`;
  turn.querySelector(".trace-question").textContent = `“${question}”`;
  traceList.prepend(turn);
  return turn;
}

function addTraceItem(turn, ev) {
  const item = document.createElement("details");
  item.className = `trace-item${ev.is_error ? " error" : ""}`;
  item.innerHTML = `
    <summary><code></code><span class="ms">${ev.duration_ms} ms${ev.is_error ? " · erro" : ""}</span></summary>
    <div class="label">Entrada</div><pre class="in"></pre>
    <div class="label">Saída</div><pre class="out"></pre>`;
  item.querySelector("code").textContent = ev.name;
  item.querySelector(".in").textContent = JSON.stringify(ev.input, null, 2);
  item.querySelector(".out").textContent = JSON.stringify(ev.output, null, 2);
  turn.querySelector(".items").appendChild(item);
}

// ---------------------------------------------------------------- envio + streaming
async function sendMessage(text) {
  if (busy || !text.trim()) return;
  busy = true;
  sendBtn.disabled = true;

  addMessage("user", text);
  const { bubble, meta } = addMessage("assistant", "");
  const turn = addTraceTurn(text);
  let streamed = "";
  let runningBadge = null;

  const handle = (ev) => {
    switch (ev.type) {
      case "start":
        conversationId = ev.conversation_id;
        storageSet(STORAGE_KEY, conversationId);
        break;
      case "token":
        streamed += ev.text;
        bubble.innerHTML = renderMarkdown(streamed);
        scrollToBottom();
        break;
      case "tool_start": {
        // Texto gerado antes de chamar uma ferramenta não é a resposta final: volta ao "digitando".
        streamed = "";
        bubble.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';
        runningBadge = document.createElement("span");
        runningBadge.className = "tool-badge running";
        runningBadge.textContent = `${TOOL_LABELS[ev.name] || ev.name}…`;
        meta.appendChild(runningBadge);
        scrollToBottom();
        break;
      }
      case "tool_end":
        if (runningBadge) {
          runningBadge.className = `tool-badge${ev.is_error ? " error" : ""}`;
          runningBadge.textContent = TOOL_LABELS[ev.name] || ev.name;
          runningBadge = null;
        }
        addTraceItem(turn, ev);
        break;
      case "done":
        bubble.innerHTML = renderMarkdown(ev.text);
        turn.querySelector(".trace-stats").textContent =
          `${ev.stats.seconds}s · ${ev.stats.llm_calls} chamada(s) ao modelo · ${ev.stats.model}`;
        if (!ev.tool_calls.length) {
          turn.querySelector(".items").innerHTML = '<p class="muted">Respondeu sem consultar ferramentas.</p>';
        }
        if (ev.tool_calls.some((c) => c.name === "abrir_chamado")) loadTickets();
        scrollToBottom();
        break;
      case "error":
        bubble.classList.add("error");
        bubble.textContent = `⚠️ ${ev.message}`;
        break;
    }
  };

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, conversation_id: conversationId }),
    });
    if (!response.ok) throw new Error(`Erro ${response.status} no servidor`);

    // Lê o stream SSE: eventos separados por linha em branco, cada um "data: {json}".
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sep;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const chunk = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const data = chunk.split("\n").filter((l) => l.startsWith("data: ")).map((l) => l.slice(6)).join("");
        if (data) handle(JSON.parse(data));
      }
    }
  } catch (err) {
    bubble.classList.add("error");
    bubble.textContent = `⚠️ Não foi possível falar com o servidor (${err.message}).`;
  } finally {
    busy = false;
    sendBtn.disabled = false;
    inputEl.focus();
  }
}

// ---------------------------------------------------------------- histórico salvo
async function restoreConversation() {
  if (!conversationId) return;
  try {
    const res = await fetch(`/api/conversations/${conversationId}`);
    if (!res.ok) { storageSet(STORAGE_KEY, null); conversationId = null; return; }
    const data = await res.json();
    data.messages.forEach((m) => addMessage(m.role, m.text));
  } catch { /* servidor fora do ar: começa vazio */ }
}

function newConversation() {
  conversationId = null;
  storageSet(STORAGE_KEY, null);
  window.location.reload();
}

// ---------------------------------------------------------------- status e chamados
async function loadStoreStatus() {
  const pill = $("#store-status");
  try {
    const s = await (await fetch("/api/store-status")).json();
    pill.textContent = s.is_open ? "Loja aberta" : "Loja fechada";
    pill.className = `status-pill ${s.is_open ? "open" : "closed"}`;
    pill.title = s.description + (s.simulated_clock ? " (relógio simulado)" : "");
  } catch {
    pill.textContent = "offline";
  }
}

const TICKET_TYPES = {
  reclamacao: "Reclamação", devolucao: "Devolução", troca: "Troca", garantia: "Garantia",
  cancelamento: "Cancelamento", atendimento_humano: "Atendimento humano", outro: "Outro",
};

async function loadTickets() {
  const list = $("#ticket-list");
  try {
    const { tickets } = await (await fetch("/api/tickets")).json();
    if (!tickets.length) { list.innerHTML = '<p class="muted">Nenhum chamado aberto.</p>'; return; }
    list.innerHTML = "";
    for (const t of tickets) {
      const el = document.createElement("article");
      el.className = "ticket";
      el.innerHTML = `<header><span class="protocol"></span><span class="type"></span></header>
        <div class="muted who"></div><p class="summary"></p>`;
      el.querySelector(".protocol").textContent = t.protocol;
      el.querySelector(".type").textContent = TICKET_TYPES[t.ticket_type] || t.ticket_type;
      el.querySelector(".who").textContent =
        `${t.customer_name} · ${t.contact}${t.order_id ? ` · pedido ${t.order_id}` : ""} · ${new Date(t.created_at).toLocaleString("pt-BR")}`;
      el.querySelector(".summary").textContent = t.summary;
      list.appendChild(el);
    }
  } catch {
    list.innerHTML = '<p class="muted">Não foi possível carregar os chamados.</p>';
  }
}

// ---------------------------------------------------------------- eventos da UI
$("#composer").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  inputEl.value = "";
  inputEl.style.height = "auto";
  sendMessage(text);
});

inputEl.addEventListener("keydown", (e) => {
  // Enter envia; Shift+Enter quebra linha.
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("#composer").requestSubmit();
  }
});
inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = `${Math.min(inputEl.scrollHeight, 160)}px`;
});

document.querySelectorAll(".chip").forEach((chip) =>
  chip.addEventListener("click", () => sendMessage(chip.textContent)));

$("#new-chat").addEventListener("click", newConversation);
$("#toggle-panel").addEventListener("click", () => $("#panel").classList.toggle("open"));
$("#close-panel").addEventListener("click", () => $("#panel").classList.remove("open"));
$("#refresh-tickets").addEventListener("click", loadTickets);

document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((t) => {
    t.classList.toggle("active", t === tab);
    t.setAttribute("aria-selected", String(t === tab));
  });
  $("#tab-trace").hidden = tab.dataset.tab !== "trace";
  $("#tab-tickets").hidden = tab.dataset.tab !== "tickets";
  if (tab.dataset.tab === "tickets") loadTickets();
}));

loadStoreStatus();
restoreConversation();
loadTickets();
