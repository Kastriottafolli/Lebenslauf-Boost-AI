/* Nutzer-Feedback: Toast, Lade-Overlay mit Fortschritt & Schritt-Animationen. */
import { $ } from "../dom.js";
import { t } from "../i18n.js";
import { mascotLoading } from "./mascot.js";

let toastTimer;
export function toast(msg, kind = "") {
  const el = $("#toast");
  el.textContent = msg;
  el.className = `toast ${kind}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 3400);
}

let stepTimer = null;
let progressTimer = null;
let progressVal = 0;

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/** Feste Dauer: 5 s bei Seitenwechsel; kürzer für Refine/Export. */
const STEP_LOAD_MS = 5000;

function minDurationFor(mode) {
  if (mode === "generate" || mode === "compare" || mode === "design") {
    return STEP_LOAD_MS;
  }
  if (mode === "refine") return 2200;
  if (mode === "export") return 1800;
  return 1500;
}

function setProgress(pct) {
  const fill = $("#loaderProgressFill");
  const ring = $("#loaderRingProgress");
  const pctEl = $("#loaderPct");
  const clamped = Math.min(100, Math.max(0, pct));
  if (fill) fill.style.width = `${clamped}%`;
  if (ring) ring.style.strokeDashoffset = `${264 - (264 * clamped) / 100}`;
  if (pctEl) pctEl.textContent = `${Math.round(clamped)}%`;
}

/** Fortschritt linear über die gesamte Ladezeit (bis ~96 %). */
function tickProgress(durationMs, target = 96) {
  clearInterval(progressTimer);
  const started = Date.now();
  progressTimer = setInterval(() => {
    const t = Math.min(1, (Date.now() - started) / durationMs);
    progressVal = target * t;
    setProgress(progressVal);
    if (t >= 1) clearInterval(progressTimer);
  }, 50);
}

function finishProgress() {
  clearInterval(progressTimer);
  progressVal = 100;
  setProgress(100);
}

function resetProgress() {
  clearInterval(progressTimer);
  progressVal = 0;
  setProgress(0);
}

function markStepsDone() {
  const ul = $("#loaderSteps");
  if (!ul) return;
  [...ul.children].forEach((li) => { li.className = "done"; });
}

/**
 * @param {string} msg
 * @param {string[]|null} steps
 * @param {"generate"|"compare"|"refine"|"export"|"design"} mode
 */
export function showOverlay(msg, steps, mode = "generate") {
  const overlay = $("#overlay");
  overlay.classList.remove("hidden", "mode-export", "mode-refine", "mode-design", "mode-compare");
  if (mode === "export") overlay.classList.add("mode-export");
  if (mode === "refine") overlay.classList.add("mode-refine");
  if (mode === "design") overlay.classList.add("mode-design");
  if (mode === "compare") overlay.classList.add("mode-compare");

  const minMs = minDurationFor(mode);
  overlay.dataset.shownAt = String(Date.now());
  overlay.dataset.minMs = String(minMs);

  mascotLoading(true, mode === "design" ? "export" : mode === "compare" ? "generate" : mode);

  $("#loaderMsg").textContent = msg;
  resetProgress();
  tickProgress(minMs, mode === "export" ? 88 : 96);

  const ul = $("#loaderSteps");
  clearInterval(stepTimer);
  if (ul) {
    ul.innerHTML = "";
    if (steps && steps.length) {
      steps.forEach((s, i) => {
        const li = document.createElement("li");
        li.innerHTML = `<span class="step-icon"></span><span class="step-text">${s}</span>`;
        if (i === 0) li.className = "act";
        ul.appendChild(li);
      });
      // 4 Schritte gleichmäßig über die 5 s verteilen
      const stepGap = Math.floor(minMs / Math.max(1, steps.length));
      let i = 0;
      stepTimer = setInterval(() => {
        const items = ul.children;
        if (i < items.length - 1) {
          items[i].className = "done";
          i += 1;
          items[i].className = "act";
        } else {
          items[i].className = "done";
          clearInterval(stepTimer);
        }
      }, stepGap);
    }
  }
}

/**
 * Overlay schließen — wartet die Mindestdauer ab (außer immediate).
 * @param {{ immediate?: boolean }} [opts]
 */
export async function hideOverlay({ immediate = false } = {}) {
  const overlay = $("#overlay");
  if (!immediate) {
    const minMs = Number(overlay.dataset.minMs || 0);
    const shownAt = Number(overlay.dataset.shownAt || Date.now());
    const remaining = Math.max(0, minMs - (Date.now() - shownAt));
    if (remaining > 0) await sleep(remaining);
  }

  markStepsDone();
  finishProgress();
  await sleep(320);

  clearInterval(stepTimer);
  clearInterval(progressTimer);
  overlay.classList.add("hidden");
  resetProgress();
  mascotLoading(false);
  delete overlay.dataset.shownAt;
  delete overlay.dataset.minMs;
}

/** Netzwerkfehler in verständliche Meldungen übersetzen. */
export function errMsg(e) {
  if (e.name === "AbortError") return t("timeout");
  if (e.message === "Failed to fetch") return t("noServer");
  return e.message;
}
