(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const state = {
    view: "dashboard",
    jobs: { mode: "recommended", offset: 0, limit: 20, total: 0, q: "", seniority: "", modality: "", threshold: 60 },
    jobsItems: [],
    notif: { offset: 0, limit: 20, total: 0, items: [] },
    sources: [],
    queries: [],
    preview: [],
    dash: null,
  };

  const pageMeta = {
    dashboard: ["Dashboard", "Visão geral da operação, saúde do sistema e últimas execuções"],
    jobs: ["Vagas", "Consulte recomendações, liste vagas e faça busca textual"],
    sources: ["Fontes", "Ingestão, preview e queries configuradas por país"],
    notifications: ["Notificações", "Providers, digest e histórico de envios"],
    llm: ["Scoring / LLM", "Status do provedor, classificação e recomputação de scores"],
    worker: ["Worker", "Status do scheduler e execução manual do pipeline"],
    system: ["Sistema", "Health, observabilidade, métricas e atalhos da API"],
  };

  /* ---------- helpers ---------- */

  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

  const safeUrl = (url) => {
    try {
      const u = new URL(String(url), window.location.origin);
      return (u.protocol === "http:" || u.protocol === "https:") ? u.href : "#";
    } catch { return "#"; }
  };

  const fmtDate = (v) => {
    if (v === null || v === undefined || v === "") return "—";
    let d;
    if (typeof v === "number" || (typeof v === "string" && /^\d+(\.\d+)?$/.test(v))) {
      const n = Number(v);
      d = new Date(n > 1e12 ? n : n * 1000);
    } else {
      d = new Date(v);
    }
    return Number.isNaN(d.getTime()) ? String(v) : d.toLocaleString("pt-BR");
  };

  const fmtNum = (v) => (v === null || v === undefined || v === "" || Number.isNaN(Number(v))) ? "—" : Number(v).toLocaleString("pt-BR");

  const badgeClass = (v) => {
    const s = String(v ?? "").toLowerCase();
    if (["ok", "sent", "excelente", "enabled", "true", "connected", "ativo"].includes(s)) return "ok";
    if (["failed", "error", "err", "ignorar", "offline", "false", "disabled", "desabilitado"].includes(s)) return "err";
    if (["pending", "warn", "relevante", "talvez_relevante", "muito_relevante", "checking"].includes(s)) return s === "relevante" || s === "talvez_relevante" || s === "muito_relevante" ? s : "warn";
    return "muito_relevante";
  };

  const toast = (message, type = "ok") => {
    const el = $("#toast");
    el.textContent = message;
    el.className = "toast show " + type;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => { el.className = "toast " + type; }, 3200);
  };

  const setBusy = (btn, busy, label) => {
    if (!btn) return;
    if (busy) {
      btn.dataset.original = btn.textContent;
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span> ' + esc(label || "processando");
    } else {
      btn.disabled = false;
      btn.textContent = btn.dataset.original || btn.textContent;
    }
  };

  async function api(path, { method = "GET", body, text = false } = {}) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    const raw = await res.text();
    if (!res.ok) {
      let detail = raw;
      try {
        const parsed = JSON.parse(raw);
        detail = parsed.detail || parsed.error || JSON.stringify(parsed);
      } catch { /* raw */ }
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    if (text) return raw;
    if (!raw) return null;
    try { return JSON.parse(raw); } catch { return raw; }
  }

  const jsonBlock = (data) => `<pre class="code">${esc(JSON.stringify(data, null, 2))}</pre>`;

  const detailsBlock = (title, data) => `
    <details class="raw">
      <summary>${esc(title)}</summary>
      ${jsonBlock(data)}
    </details>`;

  const statusRow = (label, value, cls) => `
    <div class="status-item">
      <span class="k">${esc(label)}</span>
      <span class="badge ${badgeClass(cls ?? value)}">${esc(value)}</span>
    </div>`;

  /* ---------- modal ---------- */

  const openModal = (title, bodyHtml, footHtml = "") => {
    $("#modalTitle").textContent = title;
    $("#modalBody").innerHTML = bodyHtml;
    $("#modalFoot").innerHTML = footHtml;
    $("#modalBackdrop").classList.add("open");
  };
  const closeModal = () => $("#modalBackdrop").classList.remove("open");

  const showJsonModal = (title, data) => {
    openModal(title, jsonBlock(data));
  };

  /* ---------- routing ---------- */

  const loaders = {
    dashboard: loadDashboard,
    jobs: loadJobs,
    sources: loadSources,
    notifications: loadNotifications,
    llm: loadLlm,
    worker: loadWorker,
    system: loadSystem,
  };

  function navigate(view, { force = false } = {}) {
    if (!pageMeta[view]) view = "dashboard";
    state.view = view;
    $$(".view").forEach((el) => el.classList.remove("active"));
    const target = $("#view-" + view);
    if (target) target.classList.add("active");
    $$(".nav a").forEach((a) => a.classList.toggle("active", a.dataset.view === view));
    const [title, subtitle] = pageMeta[view];
    $("#pageTitle").textContent = title;
    $("#pageSubtitle").textContent = subtitle;
    if (force || !target.dataset.loaded) {
      target.dataset.loaded = "1";
      loaders[view]?.();
    }
  }

  /* ---------- health ---------- */

  async function refreshHealth() {
    try {
      const h = await api("/health");
      $("#sideHealth").textContent = h.status || "ok";
      $("#sideHealthDot").className = "dot " + (h.status === "ok" ? "ok" : "warn");
      $("#sideEnv").textContent = h.env || "—";
      $("#topHealth").textContent = `${h.status || "ok"} • v${h.version || "0.1.0"}`;
      $("#topHealth").className = "badge " + (h.status === "ok" ? "ok" : "warn");
    } catch (e) {
      $("#sideHealth").textContent = "offline";
      $("#sideHealthDot").className = "dot err";
      $("#topHealth").textContent = "API offline";
      $("#topHealth").className = "badge err";
    }
    $("#sideUpdated").textContent = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  }

  /* ---------- dashboard ---------- */

  async function loadDashboard() {
    await refreshHealth();
    const results = await Promise.allSettled([
      api("/observability"),
      api("/health/detailed"),
      api("/worker/status"),
      api("/scoring/llm/status"),
      api("/jobs/recommended?threshold=60&limit=5"),
    ]);
    const [obs, detailed, worker, llm, top] = results.map((r) => r.status === "fulfilled" ? r.value : null);
    const obsError = results[0].status === "rejected" ? results[0].reason.message : null;
    state.dash = { obs, detailed, worker, llm };

    const stats = obs || {};
    $("#kpiJobs").textContent = fmtNum(stats.jobs_total ?? "—");
    $("#kpiScored").textContent = fmtNum(stats.jobs_scored ?? "—");
    $("#kpiSent").textContent = fmtNum(stats.notifications_sent ?? "—");
    $("#kpiPending").textContent = fmtNum(stats.notifications_pending ?? "—");

    if (obsError) {
      $("#dashClassification").innerHTML = `<div class="empty">Observabilidade indisponível: ${esc(obsError)}</div>`;
      $("#dashRuns").innerHTML = `<div class="empty">Sem dados de execução.</div>`;
      $("#dashScoredHint").textContent = "—";
    } else {
      const by = stats.by_classification || {};
      const rows = [
        ["excelente", "Excelente", by.excelente || 0],
        ["muito_relevante", "Muito relevante", by.muito_relevante || 0],
        ["relevante", "Relevante", by.relevante || 0],
        ["talvez_relevante", "Talvez relevante", by.talvez_relevante || 0],
        ["ignorar", "Ignorar", by.ignorar || 0],
      ];
      const total = rows.reduce((acc, r) => acc + r[2], 0) || 1;
      $("#dashScoredHint").textContent = `${fmtNum(rows.reduce((a, r) => a + r[2], 0))} vagas classificadas`;
      $("#dashClassification").innerHTML = `<div class="bars">${rows.map(([key, label, value]) => `
        <div class="bar-row">
          <span class="muted">${label}</span>
          <div class="bar-track"><div class="bar-fill ${key}" style="width:${Math.max(2, Math.round(value / total * 100))}%"></div></div>
          <span class="mono">${value}</span>
        </div>`).join("")}</div>`;
      renderRuns(stats.recent_runs || []);
    }

    // quick status
    const d = detailed || {};
    const notif = d.notifications || {};
    $("#dashQuickStatus").innerHTML = [
      statusRow("Banco de dados", d.db || "indisponível", d.db === "ok" ? "ok" : "err"),
      statusRow("Scheduler", d.scheduler?.enabled ? "ativo" : "desativado", d.scheduler?.enabled ? "ok" : "warn"),
      statusRow("Telegram", notif.telegram ? "habilitado" : "desabilitado", notif.telegram ? "ok" : "warn"),
      statusRow("Email", notif.email ? "habilitado" : "desabilitado", notif.email ? "ok" : "warn"),
    ].join("");

    $("#dashStatus").innerHTML = [
      statusRow("API", $("#topHealth").textContent || "—", $("#topHealth").textContent.includes("offline") ? "err" : "ok"),
      statusRow("Banco", d.db || "—", d.db === "ok" ? "ok" : "err"),
      statusRow("LLM", d.llm?.provider || "—", d.llm?.enabled ? "ok" : "warn"),
      statusRow("Scheduler", d.scheduler?.enabled ? `a cada ${d.scheduler.interval_minutes} min` : "desativado", d.scheduler?.enabled ? "ok" : "warn"),
      statusRow("Notificações", (notif.telegram || notif.email) ? "provider ativo" : "sem provider", (notif.telegram || notif.email) ? "ok" : "warn"),
      statusRow("Worker", worker?.scheduler_enabled ? "API/scheduler" : "manual", worker?.scheduler_enabled ? "ok" : "warn"),
    ].join("");

    if (top && top.items) {
      $("#dashTop").innerHTML = top.items.length
        ? `<div class="stack">${top.items.map((j) => `
            <div class="row between" style="align-items:flex-start;border-bottom:1px solid var(--border-soft);padding-bottom:10px">
              <div style="min-width:0">
                <div style="font-size:13px;font-weight:650" class="truncate">${esc(j.title)}</div>
                <div class="small muted">${esc(j.location || "—")} • ${esc(j.modality || "—")} • ${esc(j.seniority || "—")}</div>
              </div>
              <button class="btn small ghost" data-action="job-detail" data-id="${esc(j.id)}" type="button">Detalhes</button>
            </div>`).join("")}</div>`
        : '<div class="empty">Nenhuma vaga recomendada ainda. Rode o pipeline ou ingira fontes.</div>';
    } else {
      $("#dashTop").innerHTML = '<div class="empty">Não foi possível carregar recomendações.</div>';
    }
  }

  function renderRuns(runs) {
    if (!runs.length) {
      $("#dashRuns").innerHTML = '<div class="empty">Nenhuma execução registrada neste processo. Rode o pipeline para gerar métricas.</div>';
      return;
    }
    $("#dashRuns").innerHTML = `<table>
      <thead><tr><th>Quando</th><th>Coletadas</th><th>Novas</th><th>Duplicadas</th><th>Erros</th><th>Tempo</th><th>Erros por fonte</th></tr></thead>
      <tbody>${runs.slice().reverse().map((r) => `
        <tr>
          <td class="mono">${esc(fmtDate(r.timestamp))}</td>
          <td>${fmtNum(r.collected)}</td>
          <td>${fmtNum(r.new)}</td>
          <td>${fmtNum(r.duplicates)}</td>
          <td>${fmtNum(r.errors)}</td>
          <td>${esc(r.elapsed_s ?? "—")}s</td>
          <td class="mono small">${esc(Object.entries(r.errors_by_source || {}).filter(([, v]) => v).map(([k, v]) => `${k}:${v}`).join(", ") || "—")}</td>
        </tr>`).join("")}</tbody>
    </table>`;
  }

  /* ---------- jobs ---------- */

  function jobCard(job) {
    const techs = Array.isArray(job.technologies) ? job.technologies.slice(0, 7) : [];
    const url = safeUrl(job.url);
    return `<article class="job-card">
      <div class="row between" style="align-items:flex-start">
        <h3>${esc(job.title || "Sem título")}</h3>
        <span class="badge">#${esc(job.id ?? "—")}</span>
      </div>
      <div class="job-meta">
        <span>${esc(job.location || "Local não informado")}</span>
        <span>•</span><span>${esc(job.modality || "modalidade n/d")}</span>
        <span>•</span><span>${esc(job.seniority || "senioridade n/d")}</span>
      </div>
      ${techs.length ? `<div class="chips">${techs.map((t) => `<span class="chip">${esc(t)}</span>`).join("")}</div>` : ""}
      ${job.description ? `<p class="job-desc">${esc(job.description).slice(0, 220)}${job.description.length > 220 ? "…" : ""}</p>` : ""}
      <div class="job-foot">
        <span class="small muted">${esc(fmtDate(job.first_seen_at))}</span>
        <div class="row">
          <button class="btn small ghost" data-action="job-detail" data-id="${esc(job.id)}" type="button">Detalhes</button>
          <a class="btn small" href="${esc(url)}" target="_blank" rel="noopener">Candidatura</a>
        </div>
      </div>
    </article>`;
  }

  async function loadJobs() {
    const { mode, threshold, limit, seniority, modality, q } = state.jobs;
    $("#jobsPage").textContent = "—";
    $("#jobsList").innerHTML = '<div class="loader"><span class="spinner"></span> carregando vagas</div>';
    try {
      let data;
      if (mode === "search") {
        if (q.trim().length < 2) {
          toast("Informe ao menos 2 caracteres para a busca textual.", "err");
          $("#jobsList").innerHTML = '<div class="empty">Digite um termo com 2 ou mais caracteres.</div>';
          return;
        }
        data = await api(`/jobs/search/text?q=${encodeURIComponent(q.trim())}`);
      } else if (mode === "recommended") {
        data = await api(`/jobs/recommended?threshold=${encodeURIComponent(threshold)}&limit=${encodeURIComponent(limit)}`);
      } else {
        const params = new URLSearchParams({ limit: String(limit), offset: String(state.jobs.offset) });
        if (seniority) params.set("seniority", seniority);
        if (modality) params.set("modality", modality);
        data = await api(`/jobs?${params.toString()}`);
      }
      const items = Array.isArray(data) ? data : (data.items || []);
      state.jobsItems = items;
      state.jobs.total = data.total ?? items.length;
      $("#jobsCount").textContent = `${fmtNum(items.length)} resultado(s) de ${fmtNum(state.jobs.total)}`;
      $("#jobsPage").textContent = mode === "recommended" || mode === "search"
        ? "sem paginação"
        : `offset ${state.jobs.offset}`;
      $("#jobsList").innerHTML = items.length
        ? `<div class="jobs-grid">${items.map(jobCard).join("")}</div>`
        : '<div class="empty">Nenhuma vaga encontrada com esses filtros.</div>';
      $("#jobsPrev").disabled = state.jobs.offset <= 0 || mode !== "all";
      $("#jobsNext").disabled = mode !== "all" || state.jobs.offset + limit >= state.jobs.total;
    } catch (e) {
      $("#jobsList").innerHTML = `<div class="empty">Erro ao carregar vagas: ${esc(e.message)}</div>`;
      toast(e.message, "err");
    }
  }

  async function openJobDetail(id) {
    openModal("Detalhes da vaga", '<div class="loader"><span class="spinner"></span> carregando</div>');
    try {
      const job = await api(`/jobs/${encodeURIComponent(id)}`);
      const techs = Array.isArray(job.technologies) ? job.technologies : [];
      openModal(`Vaga #${esc(job.id)}`, `
        <h4 style="margin:0 0 4px;font-size:17px">${esc(job.title)}</h4>
        <div class="job-meta" style="margin-bottom:12px">
          <span>${esc(job.location || "—")}</span><span>•</span>
          <span>${esc(job.modality || "—")}</span><span>•</span>
          <span>${esc(job.seniority || "—")}</span>
        </div>
        ${techs.length ? `<div class="chips" style="margin:0 0 14px">${techs.map((t) => `<span class="chip">${esc(t)}</span>`).join("")}</div>` : ""}
        <div class="status-list">
          ${statusRow("ID", job.id, "ok")}
          ${statusRow("Fingerprint", String(job.fingerprint || "—").slice(0, 24) + "…", "ok")}
          ${statusRow("Primeira coleta", fmtDate(job.first_seen_at), "ok")}
          ${statusRow("Última coleta", fmtDate(job.last_seen_at), "ok")}
        </div>
        <div class="divider"></div>
        <p style="color:#b8c5d8;font-size:13px;white-space:pre-wrap">${esc(job.description || "Sem descrição.")}</p>
        ${detailsBlock("Resposta completa (JSON)", job)}
      `, `
        <button class="btn small" data-action="recompute-job" data-id="${esc(job.id)}" type="button">Recomputar score</button>
        <a class="btn small primary" href="${esc(safeUrl(job.url))}" target="_blank" rel="noopener">Abrir candidatura</a>
      `);
    } catch (e) {
      openModal("Erro", `<div class="empty">${esc(e.message)}</div>`);
    }
  }

  /* ---------- sources ---------- */

  async function loadSources() {
    $("#sourcesList").innerHTML = '<div class="loader"><span class="spinner"></span> carregando fontes</div>';
    try {
      const data = await api("/sources");
      state.sources = data.sources || [];
      $("#sourcesCount").textContent = `${state.sources.length} fontes ativas`;
      $("#sourcesList").innerHTML = state.sources.length ? state.sources.map((s) => `
        <div class="source-card">
          <div style="display:flex;gap:10px;align-items:flex-start;min-width:0">
            <label class="check" title="Selecionar para ingestão">
              <input type="checkbox" class="source-check" value="${esc(s.name)}" />
            </label>
            <div style="min-width:0">
              <h4>${esc(s.name)}</h4>
              <p>${esc(s.description || "Sem descrição.")}</p>
            </div>
          </div>
          <div class="row" style="flex:0 0 auto">
            <button class="btn small ghost" data-action="preview-source" data-source="${esc(s.name)}" type="button">Preview</button>
            <button class="btn small primary" data-action="ingest-source" data-source="${esc(s.name)}" type="button">Ingerir</button>
          </div>
        </div>`).join("") : '<div class="empty">Nenhuma fonte ativa no pipeline padrão.</div>';

      const select = $("#previewSource");
      select.innerHTML = state.sources.map((s) => `<option value="${esc(s.name)}">${esc(s.name)}</option>`).join("");
    } catch (e) {
      $("#sourcesList").innerHTML = `<div class="empty">Erro ao carregar fontes: ${esc(e.message)}</div>`;
      toast(e.message, "err");
    }
    loadQueries();
  }

  async function loadQueries() {
    $("#queriesList").innerHTML = '<div class="loader"><span class="spinner"></span> carregando queries</div>';
    try {
      const data = await api("/sources/queries");
      state.queries = data.queries || [];
      $("#queriesCount").textContent = `${fmtNum(data.total ?? state.queries.length)} queries`;
      renderQueries();
    } catch (e) {
      $("#queriesList").innerHTML = `<div class="empty">Erro ao carregar queries: ${esc(e.message)}</div>`;
    }
  }

  function renderQueries() {
    const filter = ($("#queryFilter").value || "").toLowerCase().trim();
    const list = state.queries.filter((q) => !filter || String(q.query || "").toLowerCase().includes(filter) || String(q.family || "").toLowerCase().includes(filter));
    $("#queriesList").innerHTML = list.length ? list.map((q) => `
      <div class="query-item">
        <div class="f">${esc(q.family || "geral")}</div>
        <div class="q">${esc(q.query || "")}</div>
      </div>`).join("") : '<div class="empty">Nenhuma query corresponde ao filtro.</div>';
  }

  async function previewSource(name, btn) {
    if (!name) return;
    setBusy(btn, true, "gerando preview");
    $("#previewResult").innerHTML = '<div class="loader"><span class="spinner"></span> executando coleta e scoring</div>';
    try {
      const data = await api(`/sources/preview/${encodeURIComponent(name)}`);
      state.preview = data.preview || [];
      const items = state.preview;
      $("#previewResult").innerHTML = items.length ? `
        <div class="small muted" style="margin-bottom:10px">Fonte <b>${esc(data.source)}</b> • coletadas ${fmtNum(data.collected)} • exibindo ${items.length}</div>
        <div class="stack">${items.map((it, idx) => `
          <div class="job-card">
            <div class="row between" style="align-items:flex-start">
              <h3>${esc(it.title || "Sem título")}</h3>
              <span class="badge ${badgeClass(it.classification)}">${esc(it.score)}/100 • ${esc(it.classification || "—")}</span>
            </div>
            <div class="job-meta">
              <span>${esc(it.company || "—")}</span><span>•</span>
              <span>${esc(it.location || "—")}</span><span>•</span>
              <span>${esc(it.modality || "—")}</span><span>•</span>
              <span>${esc(it.seniority || "—")}</span>
            </div>
            ${(it.technologies || []).length ? `<div class="chips">${it.technologies.slice(0, 8).map((t) => `<span class="chip">${esc(t)}</span>`).join("")}</div>` : ""}
            <div class="row between">
              <button class="btn small ghost" data-action="preview-json" data-index="${idx}" type="button">Ver breakdown</button>
              <a class="btn small" href="${esc(safeUrl(it.url))}" target="_blank" rel="noopener">Abrir vaga</a>
            </div>
          </div>`).join("")}</div>` : '<div class="empty">A fonte não retornou vagas no momento.</div>';
    } catch (e) {
      $("#previewResult").innerHTML = `<div class="empty">Erro no preview: ${esc(e.message)}</div>`;
      toast(e.message, "err");
    } finally {
      setBusy(btn, false);
    }
  }

  /* ---------- notifications ---------- */

  async function loadNotifications() {
    const results = await Promise.allSettled([
      api("/notifications/providers"),
      api("/notifications/digest"),
      api(`/notifications?limit=${state.notif.limit}&offset=${state.notif.offset}`),
    ]);
    const providers = results[0].status === "fulfilled" ? results[0].value : null;
    const digest = results[1].status === "fulfilled" ? results[1].value : null;
    const history = results[2].status === "fulfilled" ? results[2].value : null;

    $("#notifProviders").innerHTML = providers ? `
      ${statusRow("Telegram", providers.telegram?.enabled ? "habilitado" : "desabilitado", providers.telegram?.enabled ? "ok" : "warn")}
      ${statusRow("Email", providers.email?.enabled ? "habilitado" : "desabilitado", providers.email?.enabled ? "ok" : "warn")}
      ${statusRow("Modo sem provider", "cria registro pendente", "warn")}
    ` : '<div class="empty">Não foi possível consultar os providers.</div>';

    if (digest) {
      $("#notifDigest").innerHTML = `
        <div class="kpi-grid" style="grid-template-columns:repeat(2,1fr);margin-bottom:12px">
          <div class="kpi"><div class="label">Total</div><div class="value">${fmtNum(digest.total)}</div></div>
          <div class="kpi"><div class="label">Altamente relevantes</div><div class="value">${fmtNum(digest.highly_relevant)}</div></div>
          <div class="kpi"><div class="label">Relevantes</div><div class="value">${fmtNum(digest.relevant)}</div></div>
          <div class="kpi"><div class="label">Descartadas</div><div class="value">${fmtNum(digest.discarded)}</div></div>
        </div>
        ${digest.top?.length ? `<div class="stack">${digest.top.map((j) => `
          <div class="row between" style="border-bottom:1px solid var(--border-soft);padding-bottom:8px;align-items:flex-start">
            <div style="min-width:0">
              <div style="font-weight:650;font-size:13px" class="truncate">${esc(j.title)}</div>
              <div class="small muted">${esc(j.company || "—")}</div>
            </div>
            <span class="badge ${badgeClass(j.classification)}">${esc(j.score)}/100</span>
          </div>`).join("")}</div>` : '<div class="empty">Nenhuma vaga no top ainda.</div>'}
        ${detailsBlock("Digest completo (JSON)", digest)}`;
    } else {
      $("#notifDigest").innerHTML = '<div class="empty">Não foi possível carregar o digest.</div>';
    }

    if (history) {
      state.notif.items = history.items || [];
      state.notif.total = history.total ?? state.notif.items.length;
      $("#notifPage").textContent = `offset ${state.notif.offset} • ${fmtNum(state.notif.total)} no total`;
      $("#notifPrev").disabled = state.notif.offset <= 0;
      $("#notifNext").disabled = state.notif.offset + state.notif.limit >= state.notif.total;
      $("#notifHistory").innerHTML = state.notif.items.length ? `<table>
        <thead><tr><th>ID</th><th>Vaga</th><th>Provider</th><th>Status</th><th>Criada</th><th>Enviada</th><th></th></tr></thead>
        <tbody>${state.notif.items.map((n, idx) => `
          <tr>
            <td class="mono">#${esc(n.id)}</td>
            <td class="mono">#${esc(n.job_id)}</td>
            <td>${esc(n.provider)}</td>
            <td><span class="badge ${badgeClass(n.status)}">${esc(n.status)}</span></td>
            <td class="mono small">${esc(fmtDate(n.created_at))}</td>
            <td class="mono small">${esc(fmtDate(n.sent_at))}</td>
            <td><button class="btn small ghost" data-action="notification-json" data-index="${idx}" type="button">Payload</button></td>
          </tr>`).join("")}</tbody>
      </table>` : '<div class="empty">Nenhuma notificação registrada.</div>';
    } else {
      $("#notifHistory").innerHTML = '<div class="empty">Não foi possível carregar o histórico.</div>';
    }
  }

  async function sendNotificationTest() {
    const btn = $("#notifTestBtn");
    const raw = $("#notifPayload").value.trim();
    let payload = null;
    if (raw) {
      try { payload = JSON.parse(raw); } catch { toast("Payload JSON inválido.", "err"); return; }
    }
    setBusy(btn, true, "enviando");
    try {
      const data = await api("/notifications/test", { method: "POST", body: payload });
      showJsonModal("Resultado do envio de teste", data);
      toast(data.enabled ? "Teste enviado." : "Nenhum provider habilitado; payload de exemplo retornado.", data.enabled ? "ok" : "err");
      loadNotifications();
    } catch (e) {
      toast(e.message, "err");
      showJsonModal("Erro no envio de teste", { error: e.message });
    } finally {
      setBusy(btn, false);
    }
  }

  /* ---------- LLM ---------- */

  async function loadLlm() {
    $("#llmStatus").innerHTML = '<div class="loader"><span class="spinner"></span> carregando status</div>';
    try {
      const s = await api("/scoring/llm/status");
      $("#llmStatus").innerHTML = [
        statusRow("Habilitado", s.llm_enabled ? "sim" : "não", s.llm_enabled ? "ok" : "warn"),
        statusRow("Provider configurado", s.llm_provider || "—", s.llm_provider === "disabled" ? "warn" : "ok"),
        statusRow("Classe do provider", s.provider_class || "—", s.is_enabled ? "ok" : "warn"),
        statusRow("Provider ativo", s.is_enabled ? "sim" : "não", s.is_enabled ? "ok" : "warn"),
        statusRow("Modelo Ollama", s.ollama_model || "—", "ok"),
        statusRow("Ollama base URL", s.ollama_base_url || "—", "ok"),
        statusRow("API key Ollama", s.has_ollama_api_key ? "configurada" : "não configurada", s.has_ollama_api_key ? "ok" : "warn"),
        statusRow("Modelo OpenAI", s.openai_model || "—", "ok"),
        statusRow("API key OpenAI", s.has_openai_key ? "configurada" : "não configurada", s.has_openai_key ? "ok" : "warn"),
      ].join("") + `<div class="divider"></div><p class="small muted">${esc(s.note || "")}</p>`;
    } catch (e) {
      $("#llmStatus").innerHTML = `<div class="empty">Erro: ${esc(e.message)}</div>`;
    }
  }

  async function classifyLlm() {
    const btn = $("#llmClassifyBtn");
    const payload = {
      title: $("#llmTitle").value.trim(),
      company: $("#llmCompany").value.trim(),
      url: $("#llmUrl").value.trim(),
      location: $("#llmLocation").value.trim(),
      modality: $("#llmModality").value.trim(),
      seniority: $("#llmSeniority").value.trim(),
      technologies: $("#llmTechs").value.split(",").map((s) => s.trim()).filter(Boolean),
      description: $("#llmDescription").value.trim(),
    };
    if (!payload.title) { toast("Informe ao menos o título da vaga.", "err"); return; }
    setBusy(btn, true, "classificando");
    $("#llmResult").innerHTML = "";
    try {
      const data = await api("/scoring/llm/classify", { method: "POST", body: payload });
      $("#llmResult").innerHTML = `<div class="row" style="margin-bottom:10px"><span class="badge ${badgeClass(data.recommendation)}">${esc(data.recommendation || "resultado")}</span><span class="badge">score ${esc(data.relevance_score ?? "—")}</span></div>${jsonBlock(data)}`;
      toast("Classificação concluída.");
    } catch (e) {
      $("#llmResult").innerHTML = `<div class="empty">Erro na classificação: ${esc(e.message)}</div>`;
      toast(e.message, "err");
    } finally {
      setBusy(btn, false);
    }
  }

  async function recomputeJob(id, btn) {
    if (!id) { toast("Informe o ID da vaga.", "err"); return; }
    setBusy(btn, true, "recomputando");
    try {
      const data = await api(`/scoring/recompute/${encodeURIComponent(id)}`, { method: "POST" });
      showJsonModal(`Score recomputado — vaga #${id}`, data);
      toast(`Vaga #${id}: score ${data.final_score ?? "—"}.`);
      closeModal();
    } catch (e) {
      toast(e.message, "err");
      showJsonModal("Erro ao recomputar", { error: e.message });
    } finally {
      setBusy(btn, false);
    }
  }

  /* ---------- worker ---------- */

  async function loadWorker() {
    $("#workerStatus").innerHTML = '<div class="loader"><span class="spinner"></span> carregando status</div>';
    try {
      const s = await api("/worker/status");
      $("#workerStatus").innerHTML = [
        statusRow("Scheduler", s.scheduler_enabled ? "ativo" : "desativado", s.scheduler_enabled ? "ok" : "warn"),
        statusRow("Intervalo", `${s.interval_minutes} min`, "ok"),
        statusRow("Digest", s.digest_enabled ? `${s.digest_time}` : "desativado", s.digest_enabled ? "ok" : "warn"),
        statusRow("Coleta ao iniciar", s.collect_on_start ? "sim" : "não", s.collect_on_start ? "ok" : "warn"),
        statusRow("Modo", s.mode || "—", "ok"),
      ].join("") + `<div class="divider"></div><p class="small muted">${esc(s.note || "")}</p>`;
    } catch (e) {
      $("#workerStatus").innerHTML = `<div class="empty">Erro: ${esc(e.message)}</div>`;
    }
  }

  async function runAction(action, btn) {
    const labels = {
      "run-pipeline": ["POST /worker/run", "rodando pipeline"],
      "ingest-all": ["POST /sources/ingest", "ingerindo fontes"],
      "run-digest": ["POST /worker/digest", "executando digest"],
      "recompute-all": ["POST /scoring/recompute-all", "recomputando scores"],
    };
    const [endpoint, busyLabel] = labels[action] || ["ação", "processando"];
    setBusy(btn, true, busyLabel);
    $("#workerOutput").innerHTML = `<div class="loader"><span class="spinner"></span> ${esc(busyLabel)} — ${esc(endpoint)}</div>`;
    try {
      let data;
      if (action === "run-pipeline") data = await api("/worker/run", { method: "POST" });
      if (action === "ingest-all") data = await api("/sources/ingest", { method: "POST" });
      if (action === "run-digest") data = await api("/worker/digest", { method: "POST" });
      if (action === "recompute-all") data = await api("/scoring/recompute-all", { method: "POST" });
      $("#workerOutput").innerHTML = `${detailsBlock(endpoint + " — resposta", data)}`;
      toast(`${endpoint} concluído.`);
      if (state.view === "dashboard") loadDashboard();
      if (state.view === "worker") loadWorker();
    } catch (e) {
      $("#workerOutput").innerHTML = `<div class="empty">Erro em ${esc(endpoint)}: ${esc(e.message)}</div>`;
      toast(e.message, "err");
    } finally {
      setBusy(btn, false);
    }
  }

  async function ingestSource(name, btn) {
    setBusy(btn, true, "ingerindo");
    try {
      const data = await api(`/sources/ingest/${encodeURIComponent(name)}`, { method: "POST" });
      showJsonModal(`Ingestão — ${name}`, data);
      toast(`Fonte ${name} ingerida.`);
      loadDashboard();
    } catch (e) {
      toast(e.message, "err");
      showJsonModal("Erro na ingestão", { error: e.message });
    } finally {
      setBusy(btn, false);
    }
  }

  async function ingestSelected(btn) {
    const names = $$(".source-check:checked").map((el) => el.value);
    if (!names.length) { toast("Selecione ao menos uma fonte.", "err"); return; }
    setBusy(btn, true, "ingerindo");
    try {
      const data = await api("/sources/ingest", { method: "POST", body: names });
      showJsonModal("Ingestão das fontes selecionadas", data);
      toast("Ingestão concluída.");
      loadDashboard();
    } catch (e) {
      toast(e.message, "err");
      showJsonModal("Erro na ingestão", { error: e.message });
    } finally {
      setBusy(btn, false);
    }
  }

  /* ---------- system ---------- */

  async function loadSystem() {
    const results = await Promise.allSettled([
      api("/health"), api("/health/db"), api("/"), api("/health/detailed"), api("/observability"), api("/metrics", { text: true }),
    ]);
    const [health, db, root, detailed, obs, metrics] = results.map((r) => r.status === "fulfilled" ? r.value : null);

    $("#sysHealth").innerHTML = health
      ? `${statusRow("Status", health.status, health.status === "ok" ? "ok" : "err")}${statusRow("Versão", health.version, "ok")}${statusRow("Ambiente", health.env, "ok")}`
      : '<div class="empty">Health indisponível.</div>';

    $("#sysDb").innerHTML = db
      ? `${statusRow("Status", db.status, db.status === "ok" ? "ok" : "err")}${statusRow("Banco", db.db, db.status === "ok" ? "ok" : "err")}`
      : '<div class="empty">Banco indisponível.</div>';

    $("#sysRoot").innerHTML = root
      ? `<div class="status-list">${Object.entries(root).map(([k, v]) => statusRow(k, String(v), "ok")).join("")}</div>`
      : '<div class="empty">Root indisponível.</div>';

    $("#sysDetailed").innerHTML = detailed ? jsonBlock(detailed) : '<div class="empty">Health detalhado indisponível.</div>';
    $("#sysObservability").innerHTML = obs ? jsonBlock(obs) : '<div class="empty">Observabilidade indisponível.</div>';
    $("#sysMetrics").textContent = metrics || "Métricas indisponíveis.";
  }

  /* ---------- events ---------- */

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    const action = btn.dataset.action;
    if (action === "run-pipeline" || action === "ingest-all" || action === "run-digest" || action === "recompute-all") {
      runAction(action, btn);
    } else if (action === "ingest-selected") {
      ingestSelected(btn);
    } else if (action === "ingest-source") {
      ingestSource(btn.dataset.source, btn);
    } else if (action === "preview-source") {
      const name = btn.dataset.source;
      const select = $("#previewSource");
      if (select) select.value = name;
      previewSource(name, btn);
    } else if (action === "job-detail") {
      openJobDetail(btn.dataset.id);
    } else if (action === "recompute-job") {
      recomputeJob(btn.dataset.id, btn);
    } else if (action === "go-jobs") {
      location.hash = "#jobs";
    } else if (action === "preview-json") {
      const idx = Number(btn.dataset.index);
      showJsonModal("Breakdown do preview", state.preview[idx] || {});
    } else if (action === "notification-json") {
      const idx = Number(btn.dataset.index);
      showJsonModal("Payload da notificação", state.notif.items[idx] || {});
    }
  });

  $("#refreshBtn").addEventListener("click", () => {
    const target = $("#view-" + state.view);
    if (target) delete target.dataset.loaded;
    navigate(state.view, { force: true });
    toast("Dados atualizados.");
  });

  $("#modalClose").addEventListener("click", closeModal);
  $("#modalBackdrop").addEventListener("click", (e) => { if (e.target === $("#modalBackdrop")) closeModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

  window.addEventListener("hashchange", () => navigate(location.hash.replace("#", "") || "dashboard"));

  // jobs filters
  $("#jobsApply").addEventListener("click", () => {
    state.jobs.mode = $("#jobsMode").value;
    state.jobs.q = $("#jobsQ").value;
    state.jobs.seniority = $("#jobsSeniority").value;
    state.jobs.modality = $("#jobsModality").value;
    state.jobs.threshold = Number($("#jobsThreshold").value || 60);
    state.jobs.limit = Number($("#jobsLimit").value || 20);
    state.jobs.offset = 0;
    loadJobs();
  });
  $("#jobsClear").addEventListener("click", () => {
    $("#jobsMode").value = "recommended";
    $("#jobsQ").value = "";
    $("#jobsSeniority").value = "";
    $("#jobsModality").value = "";
    $("#jobsThreshold").value = 60;
    $("#jobsLimit").value = 20;
    state.jobs = { mode: "recommended", offset: 0, limit: 20, total: 0, q: "", seniority: "", modality: "", threshold: 60 };
    loadJobs();
  });
  $("#jobsQ").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#jobsApply").click(); });
  $("#jobsPrev").addEventListener("click", () => { state.jobs.offset = Math.max(0, state.jobs.offset - state.jobs.limit); loadJobs(); });
  $("#jobsNext").addEventListener("click", () => { state.jobs.offset += state.jobs.limit; loadJobs(); });
  $("#jobsMode").addEventListener("change", () => { $("#jobsApply").click(); });

  // sources
  $("#previewBtn").addEventListener("click", () => previewSource($("#previewSource").value, $("#previewBtn")));
  $("#queryFilter").addEventListener("input", renderQueries);

  // notifications
  $("#notifTestBtn").addEventListener("click", sendNotificationTest);
  $("#notifPrev").addEventListener("click", () => { state.notif.offset = Math.max(0, state.notif.offset - state.notif.limit); loadNotifications(); });
  $("#notifNext").addEventListener("click", () => { state.notif.offset += state.notif.limit; loadNotifications(); });

  // llm
  $("#llmClassifyBtn").addEventListener("click", classifyLlm);
  $("#recomputeBtn").addEventListener("click", () => recomputeJob($("#recomputeId").value, $("#recomputeBtn")));

  /* ---------- boot ---------- */

  refreshHealth();
  navigate(location.hash.replace("#", "") || "dashboard", { force: true });
  setInterval(() => {
    if (state.view === "dashboard") loadDashboard();
    else refreshHealth();
  }, 60000);
})();
