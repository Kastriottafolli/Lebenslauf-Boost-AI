/* Boosti — Gleit-Tour: führt mit Erledigt-Buttons Schritt für Schritt durch die App. */
import { $ } from "../dom.js";
import { t } from "../i18n.js";
import { state } from "../state.js";

let wrap, bubble, nameEl, textEl, bodyEl, submitBtn;
let hideTimer = null;
let targetEl = null;
let repositionTimer = null;

let tourMain = 1;
let tourIndex = 0;
let tourActive = true;
let tourPaused = false;
let currentSide = null;
let flyTimer = null;

const MOODS = ["idle", "think", "warn", "happy", "celebrate", "point", "write"];

/* Tour-Ablauf: submit = Erledigt-Button; ohne submit klickt der Nutzer den echten Button. */
function getTourSteps(main) {
  const tours = {
    1: [
      { key: "mascotTour1Job", label: "mascotTour1JobLabel", target: "#jobDescription", submit: true, check: () => $("#jobDescription").value.trim().length >= 10, problem: "job" },
      { key: "mascotTour1Cv", label: "mascotTour1CvLabel", target: "#dropzone", submit: true },
      { key: "mascotTour1Wishes", label: "mascotTour1WishesLabel", target: "#wishes", submit: true },
      { key: "mascotTour1Provider", label: "mascotTour1ProviderLabel", target: "#providerSelect", submit: true },
      { key: "mascotTour1Keys", label: "mascotTour1KeysLabel", target: "#apiKeys", submit: true },
      { key: "mascotTour1Gen", label: "mascotTour1GenLabel", target: "#generateBtn", submit: false },
    ],
    2: [
      { key: "mascotTour2Edit", label: "mascotTour2EditLabel", target: "#cvEditor", submit: true },
      { key: "mascotTour2Analysis", label: "mascotTour2AnalysisLabel", target: ".analysis", submit: true },
      { key: "mascotTour2Next", label: "mascotTour2NextLabel", target: "#toStep3", submit: false },
    ],
    3: [
      { key: "mascotTour3Design", label: "mascotTour3DesignLabel", target: "#designs", submit: true },
      { key: "mascotTour3Photo", label: "mascotTour3PhotoLabel", target: ".photo-row", submit: true },
      { key: "mascotTour3File", label: "mascotTour3FileLabel", target: "#filename", submit: true },
      { key: "mascotTour3Download", label: "mascotTour3DownloadLabel", target: "#downloadBtn", submit: false },
    ],
  };
  return tours[main] || [];
}

function tourSteps() { return getTourSteps(tourMain); }

/** Boosti + Tour starten. */
export function initMascot() {
  wrap = $("#mascot");
  bubble = $("#mascotBubble");
  nameEl = $("#mascotName");
  textEl = $("#mascotText");
  bodyEl = $("#mascotBody");
  submitBtn = $("#mascotSubmit");
  if (!wrap) return;

  bodyEl?.addEventListener("click", () => {
    wrap.classList.toggle("minimized");
    tourPaused = wrap.classList.contains("minimized");
    if (!tourPaused) showTourStep(false);
  });

  submitBtn?.addEventListener("click", onSubmit);

  window.addEventListener("scroll", scheduleReposition, { passive: true });
  window.addEventListener("resize", scheduleReposition, { passive: true });
  // Nutzer scrollt selbst → Auto-Scroll sofort abbrechen, nicht dagegen ankämpfen.
  window.addEventListener("wheel", cancelSlowScroll, { passive: true });
  window.addEventListener("touchmove", cancelSlowScroll, { passive: true });

  setTimeout(() => startTour(1), 900);
}

/** Erledigt-Klick: prüfen, ggf. warnen, sonst weiter. */
function onSubmit() {
  const step = tourSteps()[tourIndex];
  if (!step) return;
  if (step.check && !step.check()) {
    if (step.problem) mascotProblem(step.problem);
    return;
  }
  advanceTour(true);
}

function scheduleReposition() {
  clearTimeout(repositionTimer);
  repositionTimer = setTimeout(() => {
    if (tourActive && !tourPaused) positionNearCurrent();
  }, 80);
}

/** Tour für Haupt-Schritt starten. */
export function startTour(main, index = 0) {
  tourMain = main;
  tourIndex = index;
  tourActive = true;
  tourPaused = false;
  wrap?.classList.remove("minimized");
  showTourStep(true);
}

export function mascotOnStep(main) {
  startTour(main, 0);
}

function showTourStep(glide = true) {
  const steps = tourSteps();
  const step = steps[tourIndex];
  if (!step || tourPaused || !tourActive) return;

  clearTimeout(hideTimer);
  clearTarget();

  if (nameEl) {
    nameEl.textContent = `${t("mascotName")} · ${t(step.label)} (${tourIndex + 1}/${steps.length})`;
  }
  if (textEl) textEl.textContent = t(step.key);
  if (submitBtn) {
    submitBtn.textContent = t("mascotSubmit");
    submitBtn.classList.toggle("hidden", !step.submit);
  }

  bubble?.classList.remove("hidden", "kind-warn", "kind-ok", "kind-err");
  setMood("point");
  highlightTarget(step.target);

  if (glide) {
    wrap?.classList.add("gliding");
    requestAnimationFrame(() => positionNearCurrent());
    setTimeout(() => {
      if (!bodyEl?.classList.contains("fly-left") && !bodyEl?.classList.contains("fly-right")) {
        wrap?.classList.remove("gliding");
      }
    }, 1000);
  } else {
    positionNearCurrent();
  }
}

/* Boosti bleibt immer am Seitenrand — auf der Seite, wo der aktuelle Punkt liegt. */
function positionNearCurrent() {
  const step = tourSteps()[tourIndex];
  if (!step || !wrap) return;
  const el = $(step.target);
  if (!el) return;

  const rect = el.getBoundingClientRect();
  const pad = 16;
  const mw = wrap.offsetWidth || 300;
  const mh = wrap.offsetHeight || 180;

  // Gleiche Seite wie das Ziel: Punkt links → Boosti links, Punkt rechts → rechts.
  const targetCenter = rect.left + rect.width / 2;
  const side = targetCenter <= window.innerWidth / 2 ? "left" : "right";
  const left = side === "left" ? pad : window.innerWidth - mw - pad;

  // Vertikal auf Zielhöhe, aber im sichtbaren Bereich bleiben.
  let top = rect.top + rect.height / 2 - mh / 2;
  top = Math.max(76, Math.min(window.innerHeight - mh - pad, top));

  // Seitenwechsel → kleine Fluganimation.
  if (currentSide && side !== currentSide) flyAcross(side);
  currentSide = side;

  wrap.style.top = `${top}px`;
  wrap.style.left = `${left}px`;
  wrap.style.right = "auto";
  wrap.style.bottom = "auto";
  wrap.classList.add("touring");
  wrap.classList.toggle("side-left", side === "left");
  bubble?.classList.remove("place-left", "place-bottom", "place-right");
  bubble?.classList.add(`place-${side}`);
}

/* Flug zur anderen Seite: Gleiten + Flatter-Animation in Flugrichtung. */
function flyAcross(side) {
  if (!wrap) return;
  wrap.classList.add("gliding");
  bodyEl?.classList.remove("fly-left", "fly-right");
  void bodyEl?.offsetWidth; // Animation neu starten
  bodyEl?.classList.add(side === "left" ? "fly-left" : "fly-right");
  clearTimeout(flyTimer);
  flyTimer = setTimeout(() => {
    bodyEl?.classList.remove("fly-left", "fly-right");
    wrap?.classList.remove("gliding");
  }, 950);
}

function advanceTour(happy = true) {
  const steps = tourSteps();
  if (happy) {
    setMood("happy");
    setTimeout(() => setMood("point"), 500);
  }
  if (tourIndex < steps.length - 1) {
    tourIndex += 1;
    setTimeout(() => showTourStep(true), happy ? 450 : 0);
  } else {
    setMood("celebrate");
    sayKey(`mascotTour${tourMain}Done`, "celebrate", { kind: "ok", persist: true, force: true });
    submitBtn?.classList.add("hidden");
  }
}

/** Externe Ereignisse (Download beendet Tour). */
export function tourNotify(event) {
  if (!tourActive || tourPaused) return;
  if (event === "downloaded" && tourMain === 3) {
    tourActive = false;
    setMood("celebrate");
    sayKey("mascotTourFinished", "celebrate", { kind: "ok", persist: true, force: true });
    submitBtn?.classList.add("hidden");
    resetPosition();
  }
}

function resetPosition() {
  if (!wrap) return;
  currentSide = null;
  wrap.classList.remove("touring", "side-left");
  wrap.style.removeProperty("top");
  wrap.style.removeProperty("left");
  wrap.style.right = "24px";
  wrap.style.bottom = "24px";
}

export function sayKey(key, mood = "idle", opts = {}) {
  if (tourActive && !opts.force && !tourPaused) return;
  const msg = t(key);
  if (typeof msg === "string") say(msg, mood, { ...opts, force: true });
}

export function say(text, mood = "idle", opts = {}) {
  if (!textEl || !bubble) return;
  if (tourActive && !opts.force && !tourPaused) return;

  clearTimeout(hideTimer);
  if (!opts.keepTarget) clearTarget();

  if (nameEl && opts.force) nameEl.textContent = t("mascotName");
  textEl.textContent = text;
  bubble.classList.remove("hidden", "kind-warn", "kind-ok", "kind-err");
  if (opts.kind) bubble.classList.add(`kind-${opts.kind}`);
  setMood(mood);
  if (opts.target) highlightTarget(opts.target);

  if (!opts.persist && !opts.keepOpen) {
    hideTimer = setTimeout(() => {
      if (tourActive && !tourPaused) showTourStep(false);
    }, opts.duration ?? 5200);
  }
}

export function setMood(mood) {
  if (!wrap) return;
  MOODS.forEach((m) => wrap.classList.remove(`mood-${m}`));
  if (mood !== "idle" && mood !== "wave") wrap.classList.add(`mood-${mood}`);
  syncLoaderMood(mood);
}

export function highlightTarget(selector) {
  clearTarget();
  const el = typeof selector === "string" ? $(selector) : selector;
  if (!el) return;
  targetEl = el;
  el.classList.add("boosti-target");
  slowScrollTo(el);
  setMood("point");
}

let scrollAnim = null;

function cancelSlowScroll() {
  if (scrollAnim) {
    cancelAnimationFrame(scrollAnim);
    scrollAnim = null;
  }
}

/* Gemächliches Scrollen zum Ziel — Boosti nimmt den Nutzer in Ruhe mit. */
function slowScrollTo(el) {
  cancelSlowScroll();
  const rect = el.getBoundingClientRect();
  const raw = window.scrollY + rect.top + rect.height / 2 - window.innerHeight / 2;
  const endY = Math.max(0, Math.min(raw, document.documentElement.scrollHeight - window.innerHeight));

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    window.scrollTo({ top: endY, behavior: "instant" });
    return;
  }

  const startY = window.scrollY;
  const dist = endY - startY;
  if (Math.abs(dist) < 4) return;

  // Dauer wächst mit der Distanz: min. 1,2s, max. 2,4s.
  const duration = Math.min(2400, Math.max(1200, Math.abs(dist) * 2));
  const start = performance.now();
  const ease = (p) => (p < 0.5 ? 2 * p * p : 1 - (-2 * p + 2) ** 2 / 2);

  const tick = (now) => {
    const p = Math.min(1, (now - start) / duration);
    // "instant" umgeht das CSS scroll-behavior:smooth, das sonst dazwischenfunkt.
    window.scrollTo({ top: startY + dist * ease(p), behavior: "instant" });
    scrollAnim = p < 1 ? requestAnimationFrame(tick) : null;
  };
  scrollAnim = requestAnimationFrame(tick);
}

function clearTarget() {
  if (targetEl) {
    targetEl.classList.remove("boosti-target");
    targetEl = null;
  }
}

export function mascotLoading(active, mode = "generate") {
  const loaderMascot = $("#loaderMascot");
  if (loaderMascot) loaderMascot.classList.toggle("hidden", !active);
  if (active) {
    wrap?.classList.add("tour-hidden");
    const key = mode === "export" ? "mascotExporting" : mode === "refine" ? "mascotRefining" : "mascotGenerating";
    sayKey(key, "write", { persist: true, keepOpen: true, force: true });
    submitBtn?.classList.add("hidden");
  } else {
    wrap?.classList.remove("tour-hidden");
    if (tourActive && !tourPaused) showTourStep(false);
  }
}

function syncLoaderMood(mood) {
  const loaderWrap = $("#loaderMascot");
  if (!loaderWrap) return;
  MOODS.forEach((m) => loaderWrap.classList.remove(`mood-${m}`));
  if (mood !== "idle") loaderWrap.classList.add(`mood-${mood}`);
}

export function mascotRefreshLang() {
  if (tourPaused) return;
  if (tourActive) showTourStep(false);
}

export function mascotProblem(type) {
  const map = {
    job: { key: "mascotNeedJob", target: "#jobDescription", kind: "warn", tourIdx: 0 },
    cv: { key: "mascotNeedCv", target: "#dropzone", kind: "warn", tourIdx: 1 },
    error: { key: "mascotError", kind: "err" },
    upload: { key: "mascotUploadOk", mood: "happy", kind: "ok" },
    done: { key: "mascotDone", mood: "celebrate", kind: "ok" },
    download: { key: "mascotDownloadOk", mood: "celebrate", kind: "ok" },
  };
  const cfg = map[type];
  if (!cfg) return;

  if (cfg.tourIdx !== undefined && tourMain === 1 && tourActive) {
    tourIndex = cfg.tourIdx;
    showTourStep(true);
  }

  if (nameEl) nameEl.textContent = t("mascotName");
  if (textEl) textEl.textContent = t(cfg.key);
  bubble?.classList.remove("kind-warn", "kind-ok", "kind-err");
  if (cfg.kind) bubble?.classList.add(`kind-${cfg.kind}`);
  setMood(cfg.mood || "warn");
  if (cfg.target) highlightTarget(cfg.target);
  if (tourActive && !tourPaused) positionNearCurrent();

  if (type === "upload" || type === "done" || type === "download") {
    hideTimer = setTimeout(() => {
      if (tourActive && !tourPaused) showTourStep(false);
    }, 4200);
  }
}
