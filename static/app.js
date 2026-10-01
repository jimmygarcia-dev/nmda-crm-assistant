const state = { leads: [] };

const $ = id => document.getElementById(id);
const fmt = value => {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? value
    : new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(d);
};

function showToast(message, type = "success") {
  let container = $("toastContainer");
  if (!container) {
    container = document.createElement("div");
    container.id = "toastContainer";
    container.style.cssText = "position:fixed;top:16px;right:16px;z-index:2147483647;display:flex;flex-direction:column;gap:8px;pointer-events:none;";
    document.body.appendChild(container);
  }
  const toast = document.createElement("div");
  toast.style.cssText = `
    background:${type === "error" ? "#dc2626" : "#16a34a"};
    color:white;padding:12px 16px;border-radius:8px;
    box-shadow:0 4px 12px rgba(0,0,0,.15);
    font-size:14px;max-width:360px;pointer-events:auto;
    animation:slideIn .2s ease-out;
  `;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = "slideOut .2s ease-in forwards";
    toast.addEventListener("animationend", () => toast.remove());
  }, 3500);
}

const style = document.createElement("style");
style.textContent = `
@keyframes slideIn { from { opacity:0; transform:translateX(100%); } to { opacity:1; transform:translateX(0); } }
@keyframes slideOut { from { opacity:1; transform:translateX(0); } to { opacity:0; transform:translateX(100%); } }
`;
document.head.appendChild(style);

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

function contactStatus(type, value) {
  const present = Boolean(String(value || "").trim());
  const label = type === "email" ? "Email" : "Website";
  const icon = type === "email"
    ? '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M2.5 4.5h15v11h-15zM3 5l7 5.5L17 5"/></svg>'
    : '<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7.5"/><path d="M2.8 10h14.4M10 2.5c2 2.1 3 4.6 3 7.5s-1 5.4-3 7.5c-2-2.1-3-4.6-3-7.5s1-5.4 3-7.5z"/></svg>';
  const stateLabel = present ? "available" : "missing";
  return `<span class="contactIcon ${present ? "present" : "missing"}" role="img" aria-label="${label}: ${stateLabel}" title="${label}: ${stateLabel}">${icon}</span>`;
}

async function health() {
  const el = $("connection");
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (data.crmUrl) {
      const openCrm = $("openCrm");
      openCrm.href = data.crmUrl;
      openCrm.hidden = false;
    }
    if (!res.ok || !data.ok) throw new Error(data.error || "Connection failed");
    el.textContent = `EspoCRM connected · ${data.ourEmail}`;
    el.className = "connection ok";
  } catch (err) {
    el.textContent = "EspoCRM disconnected";
    el.className = "connection error";
  }
}

async function load() {
  $("leadRows").innerHTML = `<tr><td colspan="8" class="loading">Loading leads from EspoCRM…</td></tr>`;
  try {
    const res = await fetch("/api/leads");
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not load leads");
    state.leads = data.list || [];
    renderSummary();
    render();
  } catch (err) {
    $("leadRows").innerHTML = `<tr><td colspan="8"><div class="errorBox">${escapeHtml(err.message)}</div></td></tr>`;
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
    $("leadRows").innerHTML = `<tr><td colspan="8" class="empty">No leads match this filter.</td></tr>`;
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
        <td><div class="contactStatuses">${contactStatus("email", item.email)}${contactStatus("website", item.website)}</div></td>
        <td>${d.outbound_count}</td>
        <td>${fmt(d.last_contact_at)}</td>
        <td>${badge(d.action, d.label)}</td>
        <td class="${d.due ? "due" : "future"}">${d.next_action_at ? fmt(d.next_action_at) : (d.due ? "Now" : "—")}</td>
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
  $("detailContent").innerHTML = `<div class="loading">Loading activity…</div>`;
  dialog.showModal();
  moveToastContainerToDialog(dialog);

  try {
    const res = await fetch(`/api/leads/${id}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not load activity");

    const lead = data.lead;
    const d = data.decision;
    const canDraft = ["FIRST_EMAIL", "FOLLOW_UP_1", "FOLLOW_UP_2"].includes(d.action);
    const canTask = ["FOLLOW_UP_1", "FOLLOW_UP_2"].includes(d.action);
    const isFirstEmail = d.action === "FIRST_EMAIL";

    $("detailContent").innerHTML = `
      <p class="eyebrow">LEAD</p>
      <h2>${escapeHtml(lead.name || "(Unnamed lead)")}</h2>

      <div class="detailGrid">
        <div class="detailCard"><span>Status</span><strong>${escapeHtml(lead.status || "—")}</strong></div>
        <div class="detailCard"><span>Emails sent</span><strong>${d.outbound_count}</strong></div>
        <div class="detailCard"><span>Emails received</span><strong>${d.inbound_count}</strong></div>
      </div>

      <div class="actionBox">
        <small>NEXT ACTION</small>
        <h3>${escapeHtml(d.label)}</h3>
        <p>${escapeHtml(d.reason)}</p>
        <strong>${d.next_action_at ? fmt(d.next_action_at) : (d.due ? "Now" : "—")}</strong>

        <div class="actionButtons">
          ${canDraft ? `<button class="primary" id="generateDraft" data-id="${lead.id}">${isFirstEmail ? "Generate First Email with AI" : "Generate follow-up"}</button>` : ""}
          ${canTask ? `<button class="secondary" id="createTask" data-id="${lead.id}">Create next-step task</button>` : ""}
          <a class="crmLink" href="${data.crmUrl}" target="_blank" rel="noreferrer">Open in EspoCRM ↗</a>
        </div>
        <div id="taskResult" class="taskResult"></div>
      </div>

      <div id="draftBox" class="draftBox hidden">
        <div id="draftMeta" class="draftMeta"></div>
        <div class="draftLabel">Subject</div>
        <input id="draftSubject" class="draftSubject" type="text">

        <div class="draftLabel">Message</div>
        <textarea id="draftBody" class="draftBody"></textarea>

        <div class="draftActions">
          <button class="primary" id="saveCrmDraft">Create Email Draft</button>
          ${isFirstEmail ? `<button class="secondary" id="createFirstEmailTask" hidden>Create next-step task</button>` : ""}
        </div>
        <div id="emailDraftResult" class="taskResult"></div>
        ${isFirstEmail ? `<div id="firstEmailTaskResult" class="taskResult"></div>` : ""}
      </div>

      <div class="timeline">
        <h3>Related emails</h3>
        ${data.emails.length ? data.emails.map(e => `
          <div class="timelineItem">
            <strong>${escapeHtml(e.subject || "(No subject)")}</strong>
            <small>${escapeHtml(e.status || "")} · ${fmt(e.dateSent || e.createdAt)}</small>
          </div>
        `).join("") : `<p class="future">No related emails found.</p>`}
      </div>
    `;

    if (canDraft) {
      $("generateDraft").addEventListener("click", () => generateDraft(lead.id, isFirstEmail));
    }
    if (canTask) {
      $("createTask").addEventListener("click", () => createFollowupTask(lead.id));
    }
  } catch (err) {
    $("detailContent").innerHTML = `<div class="errorBox">${escapeHtml(err.message)}</div>`;
  }
}

async function generateDraft(id, useAI = false) {
  const button = $("generateDraft");
  const original = button.textContent;
  button.disabled = true;
  button.textContent = useAI ? "Generating with Ollama…" : "Generating…";

  try {
    const res = await fetch(`/api/leads/${id}/email-draft`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not generate the draft");

    $("draftSubject").value = data.draft.subject || "";
    $("draftBody").value = data.draft.body || "";

    const meta = $("draftMeta");
    if (meta) {
      meta.textContent = data.generatedBy === "ollama"
        ? `Generated with Ollama · ${data.model || data.draft.model || ""}`
        : "Follow-up draft";
    }

    $("draftBox").classList.remove("hidden");

    if (useAI) {
      const taskButton = $("createFirstEmailTask");
      if (taskButton) {
        taskButton.hidden = false;
        taskButton.onclick = () => createFollowupTask(
          id,
          "createFirstEmailTask",
          "firstEmailTaskResult",
        );
      }
    }

    $("saveCrmDraft").onclick = () => saveCrmEmailDraft(id);

    $("draftBody").focus();
    showToast(useAI ? "✅ First Email generated with AI" : "✅ Follow-up generated");
  } catch (err) {
    showToast(`❌ ${err.message}`, "error");
    alert(err.message);
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

async function saveCrmEmailDraft(id) {
  const button = $("saveCrmDraft");
  const result = $("emailDraftResult");
  if (!button || !result) return;

  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Saving draft to EspoCRM…";
  result.textContent = "";

  try {
    const res = await fetch(`/api/leads/${id}/email-draft`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subject: $("draftSubject").value,
        body: $("draftBody").value,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not create the draft in EspoCRM");

    const openLink = data.crmEmailUrl
      ? ` · <a href="${escapeHtml(data.crmEmailUrl)}" target="_blank" rel="noreferrer">Open in EspoCRM ↗</a>`
      : "";
    const recipientNote = data.recipientMissing
      ? " This lead has no email address; add a recipient in EspoCRM before sending."
      : "";
    result.innerHTML = `<div class="taskResultOk">Draft saved to EspoCRM.${recipientNote}${openLink}</div>`;
    button.textContent = "Draft saved";
    showToast("✅ Email draft created in EspoCRM");
  } catch (err) {
    result.innerHTML = `<div class="errorBox">${escapeHtml(err.message)}</div>`;
    showToast(`❌ ${err.message}`, "error");
    button.disabled = false;
    button.textContent = original;
  }
}

async function createFollowupTask(
  id,
  buttonId = "createTask",
  resultId = "taskResult",
) {
  const button = $(buttonId);
  const result = $(resultId);
  if (!button || !result) return;
  const original = button.textContent;
  let finalText = original;
  let completed = false;
  button.disabled = true;
  button.textContent = "Creating task in EspoCRM…";
  result.textContent = "";

  try {
    const res = await fetch(`/api/leads/${id}/followup-task`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not create the task");

    if (data.created) {
      const due = fmt(data.task?.dateEnd);
      result.innerHTML = `<div class="taskResultOk">
        Task created: <strong>${escapeHtml(data.task?.name || "")}</strong><br>
        Due: <strong>${due}</strong> ·
        <a href="${data.crmTaskUrl}" target="_blank" rel="noreferrer">View in EspoCRM ↗</a>
      </div>`;
      showToast(`✅ Task created: ${data.task?.name} — due ${due}`);
      finalText = "Task created";
      completed = true;
    } else if (data.already) {
      result.innerHTML = `<div class="taskResultOk taskResultAlready">${escapeHtml(data.message || "Task already exists.")}</div>`;
      showToast("ℹ️ Task already exists; no duplicate was created.");
      finalText = "Task already exists";
      completed = true;
    }
  } catch (err) {
    result.innerHTML = `<div class="errorBox">${escapeHtml(err.message)}</div>`;
    showToast(`❌ ${err.message}`, "error");
  } finally {
    button.disabled = completed;
    button.textContent = finalText;
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
function moveToastContainerToDialog(dialog) {
  const container = $("toastContainer");
  if (container && container.parentElement !== dialog) {
    dialog.appendChild(container);
    container.style.position = "fixed";
    container.style.top = "16px";
    container.style.right = "16px";
    container.style.zIndex = "2147483647";
  }
}

function moveToastContainerToBody() {
  const container = $("toastContainer");
  if (container && container.parentElement !== document.body) {
    document.body.appendChild(container);
    container.style.position = "fixed";
    container.style.top = "16px";
    container.style.right = "16px";
    container.style.zIndex = "2147483647";
  }
}

$("dialogClose").addEventListener("click", () => {
  const dialog = $("detailDialog");
  dialog.close();
  moveToastContainerToBody();
});
$("detailDialog").addEventListener("close", moveToastContainerToBody);

health();
load();
