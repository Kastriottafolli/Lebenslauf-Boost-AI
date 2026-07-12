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

function setProgress(pct) {
  const fill = $("#loaderProgressFill");
  const ring = $("#loaderRingProgress");
  const pctEl = $("#loaderPct");
  const clamped = Math.min(100, Math.max(0, pct));
  if (fill) fill.style.width = `${clamped}%`;
  if (ring) ring.style.strokeDashoffset = `${264 - (264 * clamped) / 100}`;
  if (pctEl) pctEl.textContent = `${Math.round(clamped)}%`;
}

function tickProgress(target = 92, speed = 0.35) {
  clearInterval(progressTimer);
  progressTimer = setInterval(() => {
    if (progressVal < target) {
      progressVal += (target - progressVal) * speed * 0.08 + 0.4;
      setProgress(progressVal);
    }
  }, 80);
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

export function showOverlay(msg, steps, mode = "generate") {
  const overlay = $("#overlay");
  overlay.classList.remove("hidden", "mode-export", "mode-refine");
  if (mode === "export") overlay.classList.add("mode-export");
  if (mode === "refine") overlay.classList.add("mode-refine");

  mascotLoading(true, mode);

  $("#loaderMsg").textContent = msg;
  resetProgress();
  tickProgress(mode === "export" ? 88 : 92);

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
      let i = 0;
      stepTimer = setInterval(() => {
        const items = ul.children;
        if (i < items.length - 1) {
          items[i].className = "done";
          i += 1;
          items[i].className = "act";
          progressVal = Math.min(progressVal + 18, 90);
          setProgress(progressVal);
        }
      }, 1600);
    }
  }
}

export function hideOverlay() {
  finishProgress();
  setTimeout(() => {
    clearInterval(stepTimer);
    clearInterval(progressTimer);
    $("#overlay").classList.add("hidden");
    resetProgress();
    mascotLoading(false);
  }, 280);
}

/** Netzwerkfehler in verständliche Meldungen übersetzen. */
export function errMsg(e) {
  if (e.name === "AbortError") return t("timeout");
  if (e.message === "Failed to fetch") return t("noServer");
  return e.message;
}
