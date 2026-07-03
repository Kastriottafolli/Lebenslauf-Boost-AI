/* ── Lebenslauf Boost AI — Frontend-Logik ── */
const API = "";

const state = {
  sessionId: null,
  step: 1,
  content: "",
  provider: "claude",
  results: [],
  design: "modern",
  format: "pdf",
  hasCv: false,
  photo: null,
  serverProviders: {},
};

const KEY_STORE = "lba_api_keys";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ── Init ──
document.addEventListener("DOMContentLoaded", async () => {
  applyI18n();
  loadKeys();
  wireEvents();
  renderRefineChips();
  updateKeyFields();
  updatePhotoThumb();
  initReveal();
  window.addEventListener("scroll", () => {
    document.querySelector(".topbar").classList.toggle("scrolled", window.scrollY > 8);
  }, { passive: true });
  // Cursor-folgendes Licht im Hero
  const heroEl = $("#hero");
  if (heroEl) {
    heroEl.addEventListener("mousemove", (e) => {
      const r = heroEl.getBoundingClientRect();
      heroEl.style.setProperty("--mx", `${((e.clientX - r.left) / r.width) * 100}%`);
      heroEl.style.setProperty("--my", `${((e.clientY - r.top) / r.height) * 100}%`);
    }, { passive: true });
  }
  await loadStatus();
  await createSession();
});

async function loadStatus() {
  try {
    const r = await fetch(`${API}/api/status`);
    const s = await r.json();
    state.serverProviders = s.providers || {};
  } catch (e) { /* ignore */ }
  updateBadges();
}

// Badge ist "an", wenn der Nutzer einen Key eingegeben hat ODER der Server einen hat.
function updateBadges() {
  const keys = getKeys();
  const ready = {
    claude: !!keys.anthropic || !!state.serverProviders.claude,
    openai: !!keys.openai || !!state.serverProviders.openai,
  };
  const badges = $("#providerBadges");
  badges.innerHTML = "";
  for (const [name, on] of Object.entries(ready)) {
    const b = document.createElement("span");
    b.className = `badge ${on ? "on" : "off"}`;
    b.textContent = `${on ? "●" : "○"} ${name}`;
    badges.appendChild(b);
  }
}

async function createSession() {
  try {
    const r = await fetch(`${API}/api/session?language=${LANG}`, { method: "POST" });
    const s = await r.json();
    state.sessionId = s.session_id;
  } catch (e) {
    toast("Server nicht erreichbar / server unreachable", "err");
  }
}

// ── Events ──
function wireEvents() {
  $("#langToggle").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-lang]");
    if (!btn) return;
    LANG = btn.dataset.lang;
    $$("#langToggle button").forEach((b) => b.classList.toggle("active", b === btn));
    applyI18n();
    renderRefineChips();
    if (state.content) renderPreview();
  });

  // Provider
  $("#providerSelect").addEventListener("change", (e) => {
    state.provider = e.target.value;
    updateKeyFields();
  });

  // API-Key-Felder: speichern + Badge aktualisieren
  ["keyOpenai", "keyAnthropic"].forEach((id) => {
    $("#" + id).addEventListener("input", () => { saveKeys(); updateBadges(); });
  });
  // Key sichtbar/unsichtbar
  const EYE_ON = '<svg class="ic" viewBox="0 0 24 24"><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/></svg>';
  const EYE_OFF = '<svg class="ic" viewBox="0 0 24 24"><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/><path d="M4 4l16 16"/></svg>';
  $("#apiKeys").addEventListener("click", (e) => {
    const eye = e.target.closest(".key-eye");
    if (!eye) return;
    const inp = $("#" + eye.dataset.target);
    inp.type = inp.type === "password" ? "text" : "password";
    eye.innerHTML = inp.type === "password" ? EYE_ON : EYE_OFF;
  });

  // Upload
  const dz = $("#dropzone"), fi = $("#fileInput");
  fi.addEventListener("change", () => fi.files[0] && uploadCv(fi.files[0]));
  ["dragover", "dragenter"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
  dz.addEventListener("drop", (e) => { const f = e.dataTransfer.files[0]; if (f) uploadCv(f); });

  // Generate / navigation
  $("#generateBtn").addEventListener("click", generate);
  $("#backTo1").addEventListener("click", () => goStep(1));
  $("#toStep3").addEventListener("click", () => { goStep(3); updatePhotoThumb(); renderPreview(); });
  $("#backTo2").addEventListener("click", () => goStep(2));

  // Foto: hochladen / entfernen
  $("#photoInput").addEventListener("change", (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => { state.photo = reader.result; updatePhotoThumb(); renderPreview(); };
    reader.readAsDataURL(f);
  });
  $("#photoRemove").addEventListener("click", () => {
    state.photo = null;
    $("#photoInput").value = "";
    updatePhotoThumb();
    renderPreview();
  });

  // Editor live -> preview
  $("#cvEditor").addEventListener("input", (e) => { state.content = e.target.value; });

  // Refine
  $("#refineBtn").addEventListener("click", () => {
    const v = $("#refineInput").value.trim();
    if (v) refine(v);
  });
  $("#refineInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { const v = e.target.value.trim(); if (v) refine(v); }
  });

  // Designs
  $("#designs").addEventListener("click", (e) => {
    const c = e.target.closest(".design-card");
    if (!c) return;
    $$(".design-card").forEach((d) => d.classList.toggle("active", d === c));
    state.design = c.dataset.design;
    renderPreview();
  });

  // Format
  $("#formatSelect").addEventListener("change", (e) => {
    state.format = e.target.value;
    $$(".fmt").forEach((f) => f.classList.toggle("active", f.contains(e.target)));
  });

  // Download
  $("#downloadBtn").addEventListener("click", download);
}

// ── Stepper ──
function goStep(n) {
  state.step = n;
  const hero = $("#hero");
  if (hero) hero.style.display = n === 1 ? "" : "none";
  $$(".panel").forEach((p) => p.classList.toggle("active", p.id === `panel-${n}`));
  $$(".step").forEach((s) => {
    const sn = Number(s.dataset.step);
    s.classList.toggle("active", sn === n);
    s.classList.toggle("done", sn < n);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ── API-Keys (Bring your own key) ──
function getKeys() {
  return {
    openai: ($("#keyOpenai")?.value || "").trim(),
    anthropic: ($("#keyAnthropic")?.value || "").trim(),
  };
}
function saveKeys() {
  try { localStorage.setItem(KEY_STORE, JSON.stringify(getKeys())); } catch (e) {}
}
function loadKeys() {
  try {
    const k = JSON.parse(localStorage.getItem(KEY_STORE) || "{}");
    if (k.openai) $("#keyOpenai").value = k.openai;
    if (k.anthropic) $("#keyAnthropic").value = k.anthropic;
  } catch (e) {}
}
// Zeigt nur die zum gewählten Anbieter passenden Key-Felder.
function updateKeyFields() {
  const need = state.provider === "compare"
    ? ["openai", "anthropic"]
    : state.provider === "openai" ? ["openai"] : ["anthropic"];
  $$("#apiKeys .key-field").forEach((f) => {
    f.hidden = !need.includes(f.dataset.key);
  });
}

// ── Upload (RAG) ──
async function uploadCv(file) {
  const status = $("#uploadStatus");
  const dz = $("#dropzone");
  dz.classList.remove("dz-ok");
  status.className = "upload-status";
  status.textContent = t("uploading");
  const fd = new FormData();
  fd.append("session_id", state.sessionId);
  fd.append("file", file);
  fd.append("openai_key", getKeys().openai);
  try {
    const r = await fetch(`${API}/api/upload-cv`, { method: "POST", body: fd });
    if (!r.ok) throw new Error((await r.json()).detail || "Upload-Fehler");
    const d = await r.json();
    state.hasCv = true;
    dz.classList.add("dz-ok");
    status.className = "upload-status ok";
    let msg = t("uploadOk")(d.filename, d.characters, d.rag_mode);
    if (d.photo) {
      state.photo = d.photo;
      updatePhotoThumb();
      msg += " " + t("photoDetected");
    }
    status.textContent = msg;
  } catch (e) {
    status.className = "upload-status err";
    status.textContent = "⚠️ " + e.message;
  }
}

// ── Generate ──
// POST mit Zeitabschaltung (verhindert ewiges „wird generiert …").
async function postJSON(url, body, timeoutMs = 90000) {
  const ctrl = new AbortController();
  const tid = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    return await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
  } finally { clearTimeout(tid); }
}

function errMsg(e) {
  if (e.name === "AbortError") return t("timeout");
  if (e.message === "Failed to fetch") return t("noServer");
  return e.message;
}

async function generate() {
  const job = $("#jobDescription").value.trim();
  if (job.length < 10) { toast(t("needJob"), "err"); return; }
  if (!state.hasCv) toast(t("needCv"), "");

  showOverlay(
    state.provider === "compare" ? t("comparing") : t("generating"),
    t("loadSteps")
  );
  try {
    const body = {
      session_id: state.sessionId,
      job_description: job,
      wishes: $("#wishes").value.trim(),
      provider: state.provider,
      language: LANG,
      technique: $("#technique").value,
      keys: getKeys(),
    };
    const r = await postJSON(`${API}/api/generate`, body);
    if (!r.ok) throw new Error((await r.json()).detail || "Fehler");
    const data = await r.json();
    state.results = data.results;
    renderResult(data);
    goStep(2);
  } catch (e) {
    toast("⚠️ " + errMsg(e), "err");
  } finally { hideOverlay(); }
}

function renderResult(data) {
  const bar = $("#compareBar");
  if (data.mode === "compare") {
    bar.classList.remove("hidden");
    bar.innerHTML = `<div class="rec">⚖️ ${data.recommendation || ""}</div>`;
    data.results.forEach((res) => {
      const isWin = res.provider === data.winner_provider;
      const card = document.createElement("div");
      card.className = "cmp-pick" + (isWin ? " winner" : "");
      card.innerHTML =
        `<h4>${res.provider.toUpperCase()} ${isWin ? `<span class="tag">${t("winner")}</span>` : ""}</h4>
         <div class="pscore">${res.analysis.ats_score}%</div>`;
      card.addEventListener("click", () => {
        $$(".cmp-pick").forEach((c) => c.classList.remove("active"));
        card.classList.add("active");
        chooseResult(res);
        toast(t("chosen")(res.provider.toUpperCase()), "ok");
      });
      bar.appendChild(card);
    });
    // Standard: Gewinner wählen
    const winner = data.results.find((r) => r.provider === data.winner_provider) || data.results[0];
    chooseResult(winner);
    [...bar.querySelectorAll(".cmp-pick")].forEach((c) => {
      if (c.querySelector("h4").textContent.includes(winner.provider.toUpperCase())) c.classList.add("active");
    });
  } else {
    bar.classList.add("hidden");
    chooseResult(data.results[0]);
  }
}

function chooseResult(res) {
  state.content = res.content;
  state.provider = res.provider;
  $("#cvEditor").value = res.content;
  $("#genMeta").textContent =
    `${res.provider} · ${res.model}${res.is_demo ? " · " + t("demoNote") : ""} · ${res.technique}`;
  renderAnalysis(res.analysis);
}

function renderAnalysis(a) {
  const n = a.matched_keywords.length;
  const total = n + a.missing_keywords.length;
  const pill = $("#scorePill");
  if (pill) {
    if (!total) { pill.textContent = "–"; }
    else {
      const start = performance.now(), dur = 700;
      const tick = (now) => {
        const p = Math.min(1, (now - start) / dur);
        const cur = Math.round((1 - Math.pow(1 - p, 3)) * n);
        pill.textContent = `${cur}/${total}`;
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }
  }
  const fill = $("#scoreBarFill");
  if (fill) { fill.style.width = "0%"; requestAnimationFrame(() => { fill.style.width = (a.ats_score || 0) + "%"; }); }
  const matched = $("#matchedChips"), missing = $("#missingChips");
  matched.innerHTML = n
    ? a.matched_keywords.map((k) => `<span class="chip good">${esc(k)}</span>`).join("")
    : "<span class='hint'>—</span>";
  missing.innerHTML = a.missing_keywords.length
    ? a.missing_keywords.map((k) => `<span class="chip warn">${esc(k)}</span>`).join("")
    : "<span class='hint'>—</span>";
}

// ── Refine (Conversation History) ──
function renderRefineChips() {
  const wrap = $("#refineChips");
  wrap.innerHTML = "";
  t("refineQuick").forEach((label) => {
    const c = document.createElement("span");
    c.className = "chip action";
    c.textContent = label;
    c.addEventListener("click", () => refine(label));
    wrap.appendChild(c);
  });
}

async function refine(instruction) {
  showOverlay(t("refining"));
  try {
    const body = {
      session_id: state.sessionId,
      instruction,
      current_content: $("#cvEditor").value,
      provider: state.provider === "compare" ? "claude" : state.provider,
      language: LANG,
      keys: getKeys(),
    };
    const r = await postJSON(`${API}/api/refine`, body);
    if (!r.ok) throw new Error((await r.json()).detail || "Fehler");
    const res = await r.json();
    chooseResult(res);
    $("#refineInput").value = "";
    $("#compareBar").classList.add("hidden");
  } catch (e) {
    toast("⚠️ " + errMsg(e), "err");
  } finally { hideOverlay(); }
}

// ── Foto ──
function updatePhotoThumb() {
  const thumb = $("#photoThumb");
  if (state.photo) {
    thumb.innerHTML = `<img src="${state.photo}" alt="Foto">`;
  } else {
    thumb.innerHTML = `<span>${t("noPhoto")}</span>`;
  }
  $("#photoRemove").style.visibility = state.photo ? "visible" : "hidden";
}

// ── Preview ──
function renderPreview() {
  const p = $("#preview");
  p.className = `paper d-${state.design}`;
  let html = "";
  if (state.photo) {
    const pos = state.design === "classic" ? "center" : "right";
    html += `<img class="cv-photo ${pos}" src="${state.photo}" alt="Foto">`;
  }
  html += mdToHtml($("#cvEditor").value || state.content);
  p.innerHTML = html;
}

function mdToHtml(md) {
  const lines = md.split("\n");
  let html = "", inList = false, sub = [];
  const closeList = () => { if (inList) { html += "</ul>"; inList = false; } };
  const flushSub = () => {
    if (sub.length) {
      html += `<p class="p-title">${esc(sub[0])}</p>`;
      if (sub.length > 1) html += `<p class="p-contact">${esc(sub.slice(1).join(" · "))}</p>`;
      sub = [];
    }
  };
  let seenSection = false, lastName = false;
  for (let raw of lines) {
    const s = raw.replace(/\*\*/g, "").replace(/`/g, "").trim();
    if (!s) continue;
    if (s.startsWith("> ")) { closeList(); flushSub(); html += `<p class="p-note">${esc(s.slice(2))}</p>`; lastName = false; }
    else if (s.startsWith("# ")) { closeList(); flushSub(); html += `<h1>${esc(s.slice(2))}</h1>`; lastName = true; }
    else if (s.startsWith("### ")) { closeList(); flushSub(); seenSection = true; html += `<h3>${esc(s.slice(4))}</h3>`; lastName = false; }
    else if (s.startsWith("## ")) { closeList(); flushSub(); seenSection = true; html += `<h2>${esc(s.slice(3))}</h2>`; lastName = false; }
    else if (s.startsWith("- ") || s.startsWith("* ")) { flushSub(); if (!inList) { html += "<ul>"; inList = true; } html += `<li>${esc(s.slice(2))}</li>`; lastName = false; }
    else {
      closeList();
      if ((lastName || sub.length) && !seenSection) { sub.push(s); }
      else html += `<p>${esc(s)}</p>`;
      lastName = false;
    }
  }
  closeList(); flushSub();
  return html || "<p class='hint'>—</p>";
}

// ── Download ──
async function download() {
  const body = {
    session_id: state.sessionId,
    content: $("#cvEditor").value || state.content,
    format: state.format,
    design: state.design,
    language: LANG,
    filename: $("#filename").value.trim() || "Lebenslauf",
    photo: state.photo || null,
  };
  showOverlay("…");
  try {
    const r = await fetch(`${API}/api/export`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error("Export-Fehler");
    const blob = await r.blob();
    const cd = r.headers.get("Content-Disposition") || "";
    const m = cd.match(/filename="(.+?)"/);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = m ? m[1] : `${body.filename}.${state.format}`;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    toast(t("downloadOk"), "ok");
  } catch (e) {
    toast("⚠️ " + e.message, "err");
  } finally { hideOverlay(); }
}

// ── Helpers ──
let stepTimer = null;
function showOverlay(msg, steps) {
  $("#loaderMsg").textContent = msg;
  const ul = $("#loaderSteps");
  clearInterval(stepTimer);
  if (ul) {
    ul.innerHTML = "";
    if (steps && steps.length) {
      steps.forEach((s, i) => {
        const li = document.createElement("li");
        li.textContent = s;
        if (i === 0) li.className = "act";
        ul.appendChild(li);
      });
      let i = 0;
      stepTimer = setInterval(() => {
        const items = ul.children;
        if (i < items.length - 1) {
          items[i].className = "done";
          i += 1;
          items[i].className = "act";
        }
      }, 1800);
    }
  }
  $("#overlay").classList.remove("hidden");
}
function hideOverlay() { clearInterval(stepTimer); $("#overlay").classList.add("hidden"); }

// ── Scroll-Reveal: Elemente gleiten gestaffelt ins Bild ──
function initReveal() {
  const els = document.querySelectorAll(".card, .pstep, .feature, .howto-head, .hero > *");
  if (!("IntersectionObserver" in window)) return;
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
    });
  }, { threshold: 0.12 });
  els.forEach((el, i) => {
    el.classList.add("rv");
    el.style.setProperty("--rvd", `${(i % 6) * 70}ms`);
    io.observe(el);
  });
}
let toastTimer;
function toast(msg, kind = "") {
  const el = $("#toast");
  el.textContent = msg;
  el.className = `toast ${kind}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 3400);
}
function esc(s) { return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }
