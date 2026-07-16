/* Generieren, Anbieter-Vergleich, Verfeinern und Keyword-Analyse. */
import * as api from "../api.js";
import { $, $$, esc } from "../dom.js";
import { getLang, t } from "../i18n.js";
import { state } from "../state.js";
import { errMsg, hideOverlay, showOverlay, toast } from "./feedback.js";
import { mascotProblem, sayKey } from "./mascot.js";
import { getKeys } from "./keys.js";
import { animateCompareCards, staggerChips } from "./motion.js";
import { goStep } from "./steps.js";

export async function generate() {
  const job = $("#jobDescription").value.trim();
  if (job.length < 10) { toast(t("needJob"), "err"); mascotProblem("job"); return; }
  if (!state.hasCv) { toast(t("needCv"), ""); mascotProblem("cv"); }

  const btn = $("#generateBtn");
  if (btn) btn.disabled = true;

  const mode = state.provider === "compare" ? "compare" : "generate";
  showOverlay(
    mode === "compare" ? t("comparing") : t("generating"),
    t("loadSteps"),
    mode
  );
  try {
    const data = await api.generateCv({
      session_id: state.sessionId,
      job_description: job,
      wishes: $("#wishes").value.trim(),
      provider: state.provider,
      language: getLang(),
      technique: $("#technique").value,
      keys: getKeys(),
    });
    state.results = data.results;
    renderResult(data);
    // Overlay bleibt ~5–10 s sichtbar, dann weiter zu Seite 2
    await hideOverlay();
    goStep(2);
    if (data.mode === "compare") sayKey("mascotCompare", "happy", { kind: "ok", force: true, persist: true });
  } catch (e) {
    toast("⚠️ " + errMsg(e), "err");
    mascotProblem("error");
    await hideOverlay({ immediate: true });
  } finally {
    if (btn) btn.disabled = false;
  }
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
    animateCompareCards(bar);
  } else {
    bar.classList.add("hidden");
    chooseResult(data.results[0]);
  }
}

export function chooseResult(res) {
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
  staggerChips(matched);
  staggerChips(missing);
}

export function renderRefineChips() {
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

export async function refine(instruction) {
  showOverlay(t("refining"), null, "refine");
  try {
    const res = await api.refineCv({
      session_id: state.sessionId,
      instruction,
      current_content: $("#cvEditor").value,
      provider: state.provider === "compare" ? "claude" : state.provider,
      language: getLang(),
      keys: getKeys(),
    });
    chooseResult(res);
    $("#refineInput").value = "";
    $("#compareBar").classList.add("hidden");
    await hideOverlay();
  } catch (e) {
    toast("⚠️ " + errMsg(e), "err");
    mascotProblem("error");
    await hideOverlay({ immediate: true });
  }
}
