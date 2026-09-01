const state = { leads: [] };

const $ = id => document.getElementById(id);
const fmt = value => {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? value
    : new Intl.DateTimeFormat("es-MX", { dateStyle: "medium" }).format(d);
};

function badge(action, label) {
  const cls = {
    FIRST_EMAIL: "first",
    FOLLOW_UP_1: "follow1",
    FOLLOW_UP_2: "follow2",
    RECYCLE: "recycle",
    REVIEW_RESPONSE: "reply",
  }[action] || "";
  return `<span class="badge ${cls}">${label}</span>`;
}

async function health() {
  const el = $("connection");
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "Sin conexión");
    el.textContent = `EspoCRM conectado · ${data.ourEmail}`;
    el.className = "connection ok";
  } catch (err) {
    el.textContent = "EspoCRM sin conexión";
    el.className = "connection error";
  }
}

async function load() {
  $("leadRows").innerHTML = `<tr><td colspan="7" class="loading">Leyendo EspoCRM…</td></tr>`;
  try {
    const res = await fetch("/api/leads");
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Error leyendo leads");
    state.leads = data.list || [];
    renderSummary();
    render();
  } catch (err) {
    $("leadRows").innerHTML = `<tr><td colspan="7"><div class="errorBox">${escapeHtml(err.message)}</div></td></tr>`;
  }
}

function renderSummary() {
  const list = state.leads;
  $("countDue").textContent = list.filter(x => x.decision.due).length;
  $("countF1").textContent = list.filter(x => x.decision.action === "FOLLOW_UP_1").length;
  $("countF2").textContent = list.filter(x => x.decision.action === "FOLLOW_UP_2").length;
  $("countRecycle").textContent = list.filter(x => x.decision.action === "RECYCLE" && x.decision.due).length;
  $("countReplies").textContent = list.filter(x => x.decision.action === "REVIEW_RESPONSE").length;
}

function render() {
  const query = $("search").value.trim().toLowerCase();
  const filter = $("filter").value;

  const rows = state.leads.filter(item => {
    const text = `${item.name} ${item.email} ${item.company}`.toLowerCase();
    if (query && !text.includes(query)) return false;
    if (filter === "ALL") return true;
    if (filter === "DUE") return item.decision.due;
    return item.decision.action === filter;
  });

  if (!rows.length) {
    $("leadRows").innerHTML = `<tr><td colspan="7" class="empty">No hay leads para este filtro.</td></tr>`;
    return;
  }

  $("leadRows").innerHTML = rows.map(item => {
    const d = item.decision;
    return `
      <tr>
        <td>
          <span class="leadName">${escapeHtml(item.name)}</span>
          <span class="leadEmail">${escapeHtml(item.email || item.company || "")}</span>
        </td>
        <td>${escapeHtml(item.status)}</td>
        <td>${d.outbound_count}</td>
        <td>${fmt(d.last_contact_at)}</td>
        <td>${badge(d.action, d.label)}</td>
        <td class="${d.due ? "due" : "future"}">${d.next_action_at ? fmt(d.next_action_at) : (d.due ? "Ahora" : "—")}</td>
        <td><button data-id="${item.id}" class="openDetail">Ver</button></td>
      </tr>
    `;
  }).join("");

  document.querySelectorAll(".openDetail").forEach(btn => {
    btn.addEventListener("click", () => openDetail(btn.dataset.id));
  });
}

async function openDetail(id) {
  const dialog = $("detailDialog");
  $("detailContent").innerHTML = `<div class="loading">Leyendo historial…</div>`;
  dialog.showModal();

  try {
    const res = await fetch(`/api/leads/${id}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Error leyendo historial");

    const lead = data.lead;
    const d = data.decision;
    const canDraft = ["FIRST_EMAIL", "FOLLOW_UP_1", "FOLLOW_UP_2"].includes(d.action);
    const isFirstEmail = d.action === "FIRST_EMAIL";

    $("detailContent").innerHTML = `
      <p class="eyebrow">LEAD</p>
      <h2>${escapeHtml(lead.name || "(Sin nombre)")}</h2>

      <div class="detailGrid">
        <div class="detailCard"><span>Status</span><strong>${escapeHtml(lead.status || "—")}</strong></div>
        <div class="detailCard"><span>Emails enviados</span><strong>${d.outbound_count}</strong></div>
        <div class="detailCard"><span>Emails recibidos</span><strong>${d.inbound_count}</strong></div>
      </div>

      <div class="actionBox">
        <small>SIGUIENTE ACCIÓN</small>
        <h3>${escapeHtml(d.label)}</h3>
        <p>${escapeHtml(d.reason)}</p>
        <strong>${d.next_action_at ? fmt(d.next_action_at) : (d.due ? "Ahora" : "—")}</strong>

        <div class="actionButtons">
          ${canDraft ? `<button class="primary" id="generateDraft" data-id="${lead.id}">${isFirstEmail ? "Regenerar First Email" : "Generar texto de seguimiento"}</button>` : ""}
          <a class="crmLink" href="${data.crmUrl}" target="_blank" rel="noreferrer">Abrir en EspoCRM ↗</a>
        </div>
      </div>

      <div id="draftBox" class="draftBox hidden">
        <div class="draftLabel">Asunto</div>
        <input id="draftSubject" class="draftSubject" type="text">

        <div class="draftLabel">Texto</div>
        <textarea id="draftBody" class="draftBody"></textarea>

        <div class="draftActions">
          <button class="primary" id="copyDraft">Copiar texto</button>
          <button class="secondary" id="copySubject">Copiar asunto</button>
          <span id="copyState" class="copyState"></span>
        </div>
      </div>

      <div class="timeline">
        <h3>Emails relacionados</h3>
        ${data.emails.length ? data.emails.map(e => `
          <div class="timelineItem">
            <strong>${escapeHtml(e.subject || "(Sin asunto)")}</strong>
            <small>${escapeHtml(e.status || "")} · ${fmt(e.dateSent || e.createdAt)}</small>
          </div>
        `).join("") : `<p class="future">No se encontraron emails relacionados.</p>`}
      </div>
    `;

    if (canDraft) {
      $("generateDraft").addEventListener("click", () => generateDraft(lead.id));
      if (isFirstEmail) {
        generateDraft(lead.id, true);
      }
    }
  } catch (err) {
    $("detailContent").innerHTML = `<div class="errorBox">${escapeHtml(err.message)}</div>`;
  }
}

async function generateDraft(id, automatic = false) {
  const button = $("generateDraft");
  const original = button.textContent;
  button.disabled = true;
  button.textContent = automatic ? "Preparando First Email…" : "Generando…";

  try {
    const res = await fetch(`/api/leads/${id}/email-draft`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "No se pudo generar el borrador");

    $("draftSubject").value = data.draft.subject || "";
    $("draftBody").value = data.draft.body || "";
    $("draftBox").classList.remove("hidden");

    $("copyDraft").onclick = () => copyText($("draftBody").value, "Texto copiado");
    $("copySubject").onclick = () => copyText($("draftSubject").value, "Asunto copiado");

    $("draftBody").focus();
  } catch (err) {
    alert(err.message);
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

async function copyText(text, message) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }

  const state = $("copyState");
  if (state) {
    state.textContent = message;
    setTimeout(() => state.textContent = "", 1600);
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

$("search").addEventListener("input", render);
$("filter").addEventListener("change", render);
$("refresh").addEventListener("click", load);
$("dialogClose").addEventListener("click", () => $("detailDialog").close());

health();
load();
