"use strict";

/* ---------- helpers ----------------------------------------------------------------- */
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const mad = (x) => (x == null ? "—" : Math.round(x).toLocaleString("fr-FR").replace(/ /g, " ") + " MAD");
const fmtNum = (v) => (v == null || v === "" ? "" : Number(v).toLocaleString("fr-FR", { maximumFractionDigits: 2 }).replace(/[\u202f\u00a0]/g, " "));
const parseNum = (s) => { const t = String(s).replace(/[\s\u202f\u00a0]/g, "").replace(",", "."); return t === "" || isNaN(+t) ? null : +t; };
const pct = (x, d = 0) => (x == null ? "—" : (x * 100).toFixed(d) + " %");
const SEV_ORDER = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
const CAPS = { screening: 40, kyc: 25, transactions: 30, financial: 20, inherent: 15 };

function toast(msg, ms = 4000) {
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), ms);
}

function download(name, text, type = "text/plain") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

let busyTimer = null;
function busy(text, sub = "") {
  const el = $("#busy");
  if (!text) { el.classList.add("hidden"); clearInterval(busyTimer); return; }
  $("#busy-text").textContent = text;
  const start = Date.now();
  const tick = () => { $("#busy-sub").textContent = `${sub}${sub ? " · " : ""}${Math.round((Date.now() - start) / 1000)} s`; };
  tick(); clearInterval(busyTimer); busyTimer = setInterval(tick, 1000);
  el.classList.remove("hidden");
}

/* ---------- API --------------------------------------------------------------------- */
const state = { config: null, docs: [], csv: null, draft: null, step: 1 };

function password() { try { return sessionStorage.getItem("cr-pw") || ""; } catch { return ""; } }

function askPassword() {
  return new Promise((resolve) => {
    const modal = $("#pw-modal");
    modal.classList.remove("hidden");
    $("#pw-input").value = "";
    $("#pw-input").focus();
    const done = (ok) => { modal.classList.add("hidden"); $("#pw-form").onsubmit = null; $("#pw-cancel").onclick = null; resolve(ok); };
    $("#pw-form").onsubmit = (e) => {
      e.preventDefault();
      try { sessionStorage.setItem("cr-pw", $("#pw-input").value); } catch { /* private mode */ }
      done(true);
    };
    $("#pw-cancel").onclick = () => done(false);
  });
}

async function api(path, { method = "GET", body, form, protectedCall = false } = {}) {
  if (protectedCall && state.config?.password_required && !password()) {
    if (!(await askPassword())) throw new Error("Password required.");
  }
  const headers = { "X-App-Password": password() };
  if (body) headers["Content-Type"] = "application/json";
  const res = await fetch(path, { method, headers, body: form || (body && JSON.stringify(body)) });
  if (res.status === 401) {
    try { sessionStorage.removeItem("cr-pw"); } catch { /* ignore */ }
    if (protectedCall && (await askPassword())) return api(path, { method, body, form, protectedCall });
    throw new Error("Wrong password.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : `Error ${res.status}`);
  return data;
}

/* ---------- navigation -------------------------------------------------------------- */
function showView(view) {
  document.querySelectorAll(".nav button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  $("#view-new").classList.toggle("hidden", view !== "new");
  $("#view-demo").classList.toggle("hidden", view !== "demo");
  if (view === "demo") loadDemo();
}

function setStep(n) {
  state.step = n;
  for (const i of [1, 2, 3]) $(`#step-${i}`).classList.toggle("hidden", i !== n);
  document.querySelectorAll("#stepper .step").forEach((s) => {
    const i = +s.dataset.step;
    s.classList.toggle("active", i === n);
    s.classList.toggle("done", i < n);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ---------- step 1: upload ------------------------------------------------------------ */
function fileIcon(name) {
  const ext = name.split(".").pop().toUpperCase();
  return `<span class="file-icon">${esc(ext.slice(0, 4))}</span>`;
}

function renderFiles() {
  $("#doc-list").innerHTML = state.docs.map((f, i) => `
    <li>${fileIcon(f.name)}<span class="file-name" title="${esc(f.name)}">${esc(f.name)}</span>
      <span class="muted small">${(f.size / 1024).toFixed(0)} KB</span>
      <button class="icon-btn" data-remove-doc="${i}" aria-label="Remove ${esc(f.name)}">×</button></li>`).join("");
  $("#csv-list").innerHTML = state.csv ? `
    <li>${fileIcon(state.csv.name)}<span class="file-name">${esc(state.csv.name)}</span>
      <button class="icon-btn" data-remove-csv aria-label="Remove CSV">×</button></li>` : "";
  $("#btn-extract").disabled = state.docs.length === 0;
}

function addDocs(files) {
  for (const f of files) {
    if (!/\.(pdf|png|jpe?g)$/i.test(f.name)) { toast(`${f.name}: only PDF, PNG or JPG`); continue; }
    if (state.docs.some((d) => d.name === f.name && d.size === f.size)) continue;
    state.docs.push(f);
  }
  renderFiles();
}

function setupDrop(zone, input, onFiles) {
  zone.addEventListener("click", () => input.click());
  zone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("over"));
  zone.addEventListener("drop", (e) => { e.preventDefault(); zone.classList.remove("over"); onFiles([...e.dataTransfer.files]); });
  input.addEventListener("change", () => { onFiles([...input.files]); input.value = ""; });
}

function amountValue() { return parseInt($("#amount").value.replace(/[^\d]/g, ""), 10) || 0; }

async function readDocuments() {
  const form = new FormData();
  state.docs.forEach((f) => form.append("files", f, f.name));
  if (state.csv) form.append("transactions", state.csv, state.csv.name);
  busy(`Reading ${state.docs.length} document(s)…`, "usually 10–60 s");
  try {
    state.draft = await api("/api/extract", { method: "POST", form, protectedCall: true });
    renderReview();
    setStep(2);
  } catch (e) {
    toast(e.message, 7000);
  } finally {
    busy(null);
  }
}

/* ---------- step 2: review ------------------------------------------------------------ */
const FIN_ROWS = [
  ["revenue", "Revenue (chiffre d'affaires)"], ["ebitda", "EBITDA (EBE)"], ["net_income", "Net income"],
  ["total_assets", "Total assets"], ["total_liabilities", "Total liabilities (excl. equity)"], ["equity", "Equity"],
  ["current_assets", "Current assets (incl. cash)"], ["current_liabilities", "Current liabilities (incl. overdraft)"],
  ["annual_debt_service", "Annual debt service"], ["interest_expense", "Interest expense"],
  ["financial_debt", "Financial debt (incl. overdraft)"],
];

function cell(col, value, attrs) {
  if (col.type === "select") {
    return `<select ${attrs}>${col.options.map((o) => `<option value="${esc(o.value ?? o)}" ${String(o.value ?? o) === String(value ?? "") ? "selected" : ""}>${esc(o.label ?? o)}</option>`).join("")}</select>`;
  }
  if (col.readonly) return `<span>${esc(value)}</span>`;
  return `<input type="${col.type === "number" ? "number" : "text"}" ${col.type === "number" ? 'step="any"' : ""} value="${esc(value ?? "")}" ${attrs}>`;
}

/** Editable table bound to an array of row objects. */
function editableTable(el, columns, rows, { addLabel, newRow, removable = true, onChange } = {}) {
  const render = () => {
    el.innerHTML = `<div class="table-wrap"><table><thead><tr>${columns.map((c) => `<th>${esc(c.label)}</th>`).join("")}${removable ? "<th></th>" : ""}</tr></thead>
      <tbody>${rows.length ? rows.map((r, i) => `<tr>${columns.map((c) => `<td>${cell(c, r[c.key], `data-row="${i}" data-key="${c.key}" aria-label="${esc(c.label)}"`)}</td>`).join("")}
        ${removable ? `<td><button class="icon-btn" data-del="${i}" aria-label="Remove row">×</button></td>` : ""}</tr>`).join("")
      : `<tr><td colspan="${columns.length + 1}" class="muted small">None found.</td></tr>`}</tbody></table></div>
      ${addLabel ? `<div class="table-actions"><button class="btn sm" data-add>+ ${esc(addLabel)}</button></div>` : ""}`;
  };
  el.addEventListener("input", (e) => {
    const { row, key } = e.target.dataset;
    if (row === undefined) return;
    const col = columns.find((c) => c.key === key);
    rows[+row][key] = col.type === "number" ? (e.target.value === "" ? null : Number(e.target.value)) : e.target.value;
    onChange?.();
  });
  el.addEventListener("click", (e) => {
    if (e.target.dataset.del !== undefined) { rows.splice(+e.target.dataset.del, 1); render(); onChange?.(); }
    if (e.target.dataset.add !== undefined) { rows.push(newRow()); render(); onChange?.(); }
  });
  render();
  return { render };
}

function renderReview() {
  const d = state.draft, ex = d.extraction, cfg = state.config;
  const docTypes = Object.entries(cfg.doc_types).map(([value, label]) => ({ value, label }));
  const byIndex = Object.fromEntries(ex.documents.map((x) => [x.file_index, x]));
  state.review = {
    company: { ...ex },
    documents: d.file_names.map((name, i) => ({ file: name, doc_type: byIndex[i]?.doc_type ?? "other", year: byIndex[i]?.year ?? null,
      holder: byIndex[i]?.holder ?? "", issued: byIndex[i]?.issued ?? "", summary: byIndex[i]?.summary ?? "Not classified", file_index: i })),
    directors: ex.directors.map((x) => ({ ...x })),
    shareholders: ex.shareholders.map(({ ubos, ...s }) => ({ ...s })),
    ubos: ex.shareholders.flatMap((s) => s.ubos.map((u) => ({ shareholder: s.name, ...u }))),
    financials: ex.financials.map((f) => ({ ...f })),
  };
  const R = state.review;

  $("#step-2").innerHTML = `
    ${ex.warnings.map((w) => `<div class="banner warn">⚠️ <div>${esc(w)}</div></div>`).join("")}
    <div class="banner info small">✓ ${esc(d.model_note)} ${d.transactions ? `· ${d.transactions} transactions loaded` : "· no transaction history"} — check every value: the agents use this data, not the PDFs.</div>
    <div class="card"><h2>Documents</h2><div id="t-docs"></div></div>
    <div class="card"><h2>Company</h2>
      <div class="grid-3">
        ${[["company_name", "Name"], ["legal_form", "Legal form"], ["city", "City"], ["ice", "ICE"], ["rc", "RC"],
           ["incorporation_date", "Incorporation date (YYYY-MM-DD)"], ["activity", "Activity"]].map(([k, l]) =>
          `<label class="field">${l}<input type="text" data-company="${k}" value="${esc(R.company[k])}"></label>`).join("")}
        <label class="field">Sector<select data-company="sector">${cfg.sectors.map((s) => `<option ${s === R.company.sector ? "selected" : ""}>${esc(s)}</option>`).join("")}</select></label>
      </div>
    </div>
    <div class="grid-2">
      <div class="card"><h2>Directors / legal representatives</h2><div id="t-dirs"></div></div>
      <div class="card"><h2>Shareholders</h2><div id="t-sh"></div></div>
    </div>
    <div class="card"><h2>Beneficial owners behind corporate shareholders</h2><div id="t-ubo"></div></div>
    <div class="card"><h2>Financial statements <span class="muted small">(MAD)</span></h2><div id="t-fin"></div></div>
    <div class="actions">
      <button class="btn" id="btn-back-1">← Back to upload</button>
      <button class="btn primary" id="btn-run">Run due diligence →</button>
    </div>`;

  editableTable($("#t-docs"), [
    { key: "file", label: "File", readonly: true },
    { key: "doc_type", label: "Type", type: "select", options: docTypes },
    { key: "year", label: "Year (bilan)", type: "number" },
    { key: "holder", label: "Person / entity (ID, register, credit report)" },
    { key: "issued", label: "Issued (YYYY-MM-DD)" },
    { key: "summary", label: "What the AI saw", readonly: true },
  ], R.documents, { removable: false });
  editableTable($("#t-dirs"), [
    { key: "name", label: "Name" }, { key: "role", label: "Role" }, { key: "nationality", label: "Nationality" },
  ], R.directors, { addLabel: "Add director", newRow: () => ({ name: "", role: "", nationality: "MA" }) });
  let uboTable;
  const shOptions = () => R.shareholders.filter((s) => s.type === "company").map((s) => s.name);
  editableTable($("#t-sh"), [
    { key: "name", label: "Name" },
    { key: "type", label: "Type", type: "select", options: ["person", "company", "other"] },
    { key: "country", label: "Country" }, { key: "pct", label: "%", type: "number" },
  ], R.shareholders, { addLabel: "Add shareholder", newRow: () => ({ name: "", type: "person", country: "MA", pct: 0 }),
    onChange: () => uboTable?.render() });
  const uboColumns = [
    { key: "shareholder", label: "Corporate shareholder", type: "select", get options() { return ["", ...shOptions()]; } },
    { key: "name", label: "Beneficial owner" }, { key: "country", label: "Country" },
    { key: "pct_of_entity", label: "% of that company", type: "number" },
  ];
  uboTable = editableTable($("#t-ubo"), uboColumns, R.ubos, { addLabel: "Add beneficial owner",
    newRow: () => ({ shareholder: shOptions()[0] ?? "", name: "", country: "MA", pct_of_entity: 100 }) });
  renderFinancials();

  $("#step-2").oninput = (e) => {
    const k = e.target.dataset.company;
    if (k) R.company[k] = e.target.value;
  };
  $("#btn-back-1").onclick = () => setStep(1);
  $("#btn-run").onclick = runAnalysis;
}

function renderFinancials() {
  const R = state.review, el = $("#t-fin");
  R.financials.sort((a, b) => a.year - b.year);
  el.innerHTML = `<div class="table-wrap"><table><thead><tr><th>Item</th>${R.financials.map((f, i) =>
      `<th class="num">${f.year} <button class="icon-btn" data-del-year="${i}" aria-label="Remove ${f.year}">×</button></th>`).join("")}</tr></thead>
    <tbody>${FIN_ROWS.map(([k, label]) => `<tr><td>${esc(label)}</td>${R.financials.map((f, i) =>
      `<td><input type="text" inputmode="decimal" class="num-input" data-fin="${i}" data-key="${k}" value="${esc(fmtNum(f[k]))}" aria-label="${esc(label)} ${f.year}"></td>`).join("")}</tr>`).join("")}
    </tbody></table></div>
    <div class="table-actions"><button class="btn sm" id="add-year">+ Add year</button>
    ${R.financials.length ? "" : `<span class="muted small"> No financial statements found.</span>`}</div>`;
  el.oninput = (e) => {
    const i = e.target.dataset.fin;
    if (i !== undefined) R.financials[+i][e.target.dataset.key] = parseNum(e.target.value);
  };
  el.onfocusout = (e) => {
    const i = e.target.dataset.fin;
    if (i !== undefined) e.target.value = fmtNum(R.financials[+i][e.target.dataset.key]);
  };
  el.onclick = (e) => {
    const del = e.target.dataset.delYear;
    if (del !== undefined) { R.financials.splice(+del, 1); renderFinancials(); }
    if (e.target.id === "add-year") {
      const year = Math.max(new Date().getFullYear() - 2, ...R.financials.map((f) => f.year + 1));
      R.financials.push(Object.fromEntries([["year", year], ...FIN_ROWS.map(([k]) => [k, null])]));
      renderFinancials();
    }
  };
}

function reviewedExtraction() {
  const R = state.review;
  const ubos = R.ubos.filter((u) => u.name.trim());
  return {
    ...R.company,
    directors: R.directors.filter((x) => x.name.trim()),
    shareholders: R.shareholders.filter((s) => s.name.trim()).map((s) => ({ ...s, pct: s.pct ?? 0,
      ubos: ubos.filter((u) => u.shareholder === s.name).map(({ shareholder, ...u }) => ({ ...u, pct_of_entity: u.pct_of_entity ?? 0 })) })),
    financials: R.financials,
    documents: R.documents.map(({ file, ...x }) => ({ ...x, year: x.year || null })),
  };
}

async function runAnalysis() {
  if (!amountValue()) { toast("Enter the requested amount in step 1."); return; }
  busy("Agents at work…", "documents · screening · KYC · financials · transactions · policies");
  try {
    const out = await api("/api/run", { method: "POST", protectedCall: true, body: {
      draft_id: state.draft.draft_id, extraction: reviewedExtraction(), product: $("#product").value, amount_mad: amountValue() } });
    renderOutcome($("#step-3"), out, { onBack: () => setStep(1) });
    setStep(3);
  } catch (e) {
    toast(e.message, 8000);
  } finally {
    busy(null);
  }
}

/* ---------- results ------------------------------------------------------------------- */
function renderOutcome(el, out, { onBack } = {}) {
  if (out.status === "stopped") return renderStopped(el, out, onBack);
  if (out.status === "review") return renderReviewPause(el, out, onBack);
  return renderDone(el, out, onBack);
}

function renderStopped(el, out, onBack) {
  const miss = out.intake.missing;
  const letter = [`Documents to request from ${out.company.name}:`, "",
    ...miss.map((m) => `- ${m.label} (${m.reason} ${m.policy})`)].join("\n");
  el.innerHTML = `
    <div class="card" style="border-color:var(--high)">
      <div style="display:flex;gap:14px;align-items:flex-start">
        <div class="x" style="width:40px;height:40px;font-size:20px">!</div>
        <div><h2 style="margin-bottom:4px">Analysis stopped — the file is incomplete</h2>
          <div class="muted">${esc(out.company.name)} · ${miss.length} document(s) must be provided before the agents can run.</div></div>
      </div>
    </div>
    <div class="card"><h2>Documents to request</h2>
      ${miss.map((m) => `<div class="missing-item"><span class="x">×</span>
        <div><b>${esc(m.label)}</b><div class="muted small">${esc(m.reason)}</div></div><span class="ref">${esc(m.policy)}</span></div>`).join("")}
      ${out.intake.notes.map((n) => `<div class="banner warn small" style="margin-top:12px">${esc(n)}</div>`).join("")}
      <div class="actions">
        <button class="btn" data-copy>Copy request list</button>
        <button class="btn" data-dl>Download as text</button>
        ${onBack ? `<button class="btn primary" data-back>Add documents →</button>` : ""}
      </div>
    </div>`;
  el.querySelector("[data-copy]").onclick = () => navigator.clipboard.writeText(letter).then(() => toast("Copied."));
  el.querySelector("[data-dl]").onclick = () => download("documents_to_request.txt", letter);
  el.querySelector("[data-back]")?.addEventListener("click", onBack);
}

function renderReviewPause(el, out, onBack) {
  const p = out.review;
  el.innerHTML = `
    <div class="card" style="border-color:var(--high)">
      <div class="result-head">
        ${gauge(p.score, p.level)}
        <div><h2 style="margin-bottom:6px">${esc(p.company)} — escalated to Compliance</h2>
          <span class="pill ${esc(p.level)}">${esc(p.level)} risk${p.blocked ? " · BLOCKED" : ""}</span>
          <p class="muted" style="margin:10px 0 0">The workflow is paused. A reviewer must record a decision before the report is issued.</p></div>
      </div>
    </div>
    <form class="card" id="review-form">
      <h2>Compliance checklist</h2>
      <ul class="check-list">${p.checklist.map((c, i) => `<li><input type="checkbox" id="chk${i}">
        <label for="chk${i}"><b>${esc(c.action)}</b><div class="muted small">${esc(c.reason)} · <span class="ref">${esc(c.policy || "")}</span></div></label></li>`).join("")}</ul>
      <h2 style="margin-top:20px">Decision</h2>
      <div class="decisions">
        ${[["REQUEST_INFORMATION", "Request information"], ["APPROVE_WITH_CONDITIONS", "Approve with conditions"], ["REJECT", "Reject"], ["PENDING", "Pending"]]
          .map(([v, l], i) => `<label class="decision"><input type="radio" name="decision" value="${v}" ${i === 0 ? "checked" : ""}>${l}</label>`).join("")}
      </div>
      <div class="grid-2"><label class="field">Reviewer<input type="text" name="reviewer" required></label>
        <label class="field">Comment<textarea name="comment"></textarea></label></div>
      <div class="actions"><button class="btn primary">Record decision and issue report →</button></div>
    </form>`;
  el.querySelector("#review-form").onsubmit = async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    busy("Recording the decision…");
    try {
      const done = await api(`/api/review/${out.thread_id}`, { method: "POST", body: {
        decision: f.get("decision"), reviewer: f.get("reviewer"), comment: f.get("comment") } });
      renderOutcome(el, done, { onBack });
    } catch (err) { toast(err.message, 7000); } finally { busy(null); }
  };
}

function gauge(score, level) {
  const col = { Low: "var(--low)", Medium: "var(--medium)", High: "var(--high)" }[level];
  return `<div class="gauge" style="--pct:${score};--col:${col}" role="img" aria-label="Risk score ${score} out of 100">
    <div class="gauge-inner"><div><b>${score}</b><span class="muted small">/ 100</span></div></div></div>`;
}

function renderDone(el, out, onBack) {
  const r = out.risk, m = out.metrics || {}, fr = m.financial_ratios || {}, tx = m.txn_summary || {};
  const findings = [...out.findings].sort((a, b) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity]);
  const hd = out.human_decision;
  el.innerHTML = `
    <div class="card">
      <div class="result-head">
        ${gauge(r.score, r.level)}
        <div>
          <div class="muted small">${esc(out.company.sector_label || "")} · ${esc(out.company.city || "")}</div>
          <h2 style="font-size:22px;margin:2px 0 8px">${esc(out.company.name)}</h2>
          <span class="pill ${esc(r.level)}">${esc(r.level)} risk${r.blocked ? " · BLOCKED" : ""}</span>
          <span class="muted small" style="margin-left:8px">${esc(out.company.requested_product || "")}</span>
          <p class="recommendation" style="border-color:${{ Low: "var(--low)", Medium: "var(--medium)", High: "var(--high)" }[r.level]}">${esc(r.recommendation)}</p>
          ${hd ? `<p class="small" style="margin:10px 0 0"><b>Reviewer decision:</b> ${esc(hd.decision)} — ${esc(hd.reviewer)}${hd.comment ? ` — ${esc(hd.comment)}` : ""}</p>` : ""}
        </div>
      </div>
    </div>
    <div class="grid-4">
      <div class="kpi"><span>Findings</span><b>${findings.filter((f) => f.severity !== "info").length}</b></div>
      <div class="kpi"><span>Due diligence</span><b style="font-size:15px">${esc(r.due_diligence)}</b></div>
      <div class="kpi"><span>Next review</span><b>${esc(r.next_review)}</b></div>
      <div class="kpi"><span>Request / revenue</span><b>${pct(fr.exposure_to_revenue)}</b></div>
    </div>
    <div class="card" style="margin-top:18px">
      <div class="tabs" role="tablist">
        <button class="active" data-tab="findings">Findings</button><button data-tab="overview">Score & figures</button>
        <button data-tab="report">Full report</button><button data-tab="audit">Audit trail</button>
      </div>
      <div data-panel="findings">
        ${findings.length ? `<div class="table-wrap"><table><thead><tr><th>Severity</th><th>Finding & evidence</th><th>Policy</th><th>Action</th></tr></thead><tbody>
          ${findings.map((f) => `<tr><td><span class="sev ${esc(f.severity)}">${esc(f.severity)}</span></td>
            <td><b>${esc(f.title)}</b><div class="muted small">${esc(f.evidence)}</div></td>
            <td><span class="ref" title="${esc(f.policy_excerpt || "")}">${esc(f.policy_ref || "—")}</span></td><td class="small">${esc(f.action)}</td></tr>`).join("")}
          </tbody></table></div>` : `<div class="banner ok">✓ No KYC, AML or credit concern detected.</div>`}
      </div>
      <div data-panel="overview" class="hidden">
        <div class="grid-2">
          <div><h3>Score breakdown</h3><div class="bars">${Object.entries(r.breakdown).map(([k, v]) =>
            `<div class="row"><span>${esc(k)}</span><div class="bar"><div style="width:${(v / CAPS[k]) * 100}%"></div></div><b>${v}/${CAPS[k]}</b></div>`).join("")}</div></div>
          <div><h3>Key figures ${fr.year ? `(${esc(fr.year)})` : ""}</h3><table>
            <tr><td>Revenue</td><td class="num">${mad(fr.revenue)}</td></tr>
            <tr><td>Debt / equity</td><td class="num">${fr.debt_to_equity ?? "—"}</td></tr>
            <tr><td>Current ratio</td><td class="num">${fr.current_ratio ?? "—"}</td></tr>
            <tr><td>DSCR</td><td class="num">${fr.dscr ?? "—"}</td></tr>
            <tr><td>Stressed DSCR (EBITDA −20%, +200 bp)</td><td class="num">${fr.stressed_dscr ?? "—"}</td></tr>
            <tr><td>Interest coverage</td><td class="num">${fr.interest_cover ?? "—"}</td></tr>
            <tr><td>Financial debt / EBITDA (after financing)</td><td class="num">${fr.debt_to_ebitda ?? "—"}</td></tr>
            <tr><td>Net margin</td><td class="num">${pct(fr.net_margin, 1)}</td></tr>
            <tr><td>Cash deposits / revenue</td><td class="num">${tx.count ? pct(tx.cash_ratio) : "—"}</td></tr>
            <tr><td>Account credits / revenue</td><td class="num">${tx.count ? pct(tx.turnover_ratio) : "—"}</td></tr>
          </table></div>
        </div>
      </div>
      <div data-panel="report" class="hidden">
        <iframe class="report" sandbox title="Due diligence report"></iframe>
      </div>
      <div data-panel="audit" class="hidden"><div class="table-wrap"><table><thead><tr><th>Time (UTC)</th><th>Agent</th><th>Action</th><th>Detail</th></tr></thead><tbody>
        ${out.audit_log.map((a) => `<tr><td class="small">${esc(a.ts.slice(11, 19))}</td><td><b>${esc(a.agent)}</b></td><td>${esc(a.action)}</td><td class="small muted">${esc(a.detail)}</td></tr>`).join("")}
      </tbody></table></div></div>
      <div class="actions">
        <button class="btn" data-dl="html">Download report (HTML)</button>
        <button class="btn" data-dl="md">Markdown</button>
        <button class="btn" data-dl="json">JSON</button>
        ${onBack ? `<button class="btn primary" data-new>New analysis</button>` : ""}
      </div>
    </div>`;
  el.querySelector("iframe.report").srcdoc = out.report_html;
  el.querySelector(".tabs").onclick = (e) => {
    const t = e.target.dataset.tab;
    if (!t) return;
    el.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === t));
    el.querySelectorAll("[data-panel]").forEach((p) => p.classList.toggle("hidden", p.dataset.panel !== t));
  };
  const id = out.company.company_id;
  el.querySelectorAll("[data-dl]").forEach((b) => (b.onclick = () => {
    const kind = b.dataset.dl;
    if (kind === "html") download(`${id}_due_diligence.html`, out.report_html, "text/html");
    if (kind === "md") download(`${id}_due_diligence.md`, out.report_md, "text/markdown");
    if (kind === "json") download(`${id}_due_diligence.json`, JSON.stringify({ company: out.company, risk: r, findings: out.findings,
      escalation: out.escalation, human_decision: hd, audit_log: out.audit_log }, null, 2), "application/json");
  }));
  el.querySelector("[data-new]")?.addEventListener("click", () => {
    state.docs = []; state.csv = null; state.draft = null; renderFiles(); onBack();
  });
}

/* ---------- demo -------------------------------------------------------------------- */
let demoLoaded = false;
async function loadDemo() {
  if (demoLoaded) return;
  const companies = await api("/api/demo");
  demoLoaded = true;
  $("#demo-grid").innerHTML = companies.map((c) => `
    <div class="card demo-card" style="margin:0">
      <div class="muted small">${esc(c.company_id)} · ${esc(c.city)}</div>
      <b>${esc(c.name)}</b><div class="muted small">${esc(c.sector)}</div>
      <button class="btn primary sm" data-demo="${esc(c.company_id)}">Run due diligence</button>
    </div>`).join("");
  $("#demo-grid").onclick = async (e) => {
    const id = e.target.dataset.demo;
    if (!id) return;
    busy("Agents at work…", id);
    try {
      const out = await api(`/api/demo/${id}`, { method: "POST" });
      renderOutcome($("#demo-result"), out);
      $("#demo-result").scrollIntoView({ behavior: "smooth" });
    } catch (err) { toast(err.message, 7000); } finally { busy(null); }
  };
}

/* ---------- boot -------------------------------------------------------------------- */
async function boot() {
  document.querySelector(".nav").onclick = (e) => e.target.dataset.view && showView(e.target.dataset.view);
  setupDrop($("#drop-docs"), $("#input-docs"), addDocs);
  setupDrop($("#drop-csv"), $("#input-csv"), (files) => { state.csv = files.find((f) => /\.csv$/i.test(f.name)) || state.csv; renderFiles(); });
  document.addEventListener("click", (e) => {
    if (e.target.dataset.removeDoc !== undefined) { state.docs.splice(+e.target.dataset.removeDoc, 1); renderFiles(); }
    if (e.target.dataset.removeCsv !== undefined) { state.csv = null; renderFiles(); }
  });
  $("#amount").addEventListener("blur", () => { const v = amountValue(); $("#amount").value = v ? v.toLocaleString("fr-FR").replace(/ /g, " ") : ""; });
  $("#btn-extract").onclick = readDocuments;
  setStep(1);
  renderFiles();
  try {
    state.config = await api("/api/config");
    const c = state.config;
    $("#status").innerHTML = c.provider
      ? `<span class="dot ${c.key_configured ? "" : "off"}"></span>${c.key_configured ? `AI reader: ${esc(c.provider)}` : `${esc(c.key_variable)} not set`}`
      : `<span class="dot off"></span>${esc(c.error)}`;
    if (c.provider && !c.key_configured) {
      $("#privacy-note").insertAdjacentHTML("beforebegin", `<div class="banner warn">⚠️ <div><b>${esc(c.key_variable)}</b> is not set on the server: documents cannot be read. Demo files still work.</div></div>`);
    }
  } catch (e) {
    toast(`Cannot reach the server: ${e.message}`);
  }
}
boot();
