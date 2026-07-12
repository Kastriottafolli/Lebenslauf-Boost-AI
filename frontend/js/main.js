/* Einstiegspunkt: Initialisierung + globale Event-Verkabelung. */
import * as api from "./api.js";
import { $, $$ } from "./dom.js";
import { applyI18n, setLang } from "./i18n.js";
import { state } from "./state.js";
import { toast } from "./ui/feedback.js";
import { download, renderPreview, updatePhotoThumb } from "./ui/exporter.js";
import { generate, refine, renderRefineChips } from "./ui/generate.js";
import { loadKeys, saveKeys, toggleEye, updateBadges, updateKeyFields } from "./ui/keys.js";
import { initHeroSpotlight, initOrbParallax, initReveal, init3DTilt, ripple } from "./ui/motion.js";
import { initMascot, mascotRefreshLang } from "./ui/mascot.js";
import { goStep } from "./ui/steps.js";
import { wireDropzone } from "./ui/upload.js";

document.addEventListener("DOMContentLoaded", async () => {
  applyI18n();
  loadKeys();
  wireEvents();
  renderRefineChips();
  updateKeyFields();
  updatePhotoThumb();
  initReveal();
  initHeroSpotlight();
  init3DTilt();
  initOrbParallax();
  initMascot();
  window.addEventListener("scroll", () => {
    $(".topbar").classList.toggle("scrolled", window.scrollY > 8);
  }, { passive: true });
  await loadStatus();
  await createSession();
});

async function loadStatus() {
  try {
    const s = await api.fetchStatus();
    state.serverProviders = s.providers || {};
  } catch (e) { /* ignore */ }
  updateBadges();
}

async function createSession() {
  try {
    const s = await api.createSession(document.documentElement.lang || "de");
    state.sessionId = s.session_id;
  } catch (e) {
    toast("Server nicht erreichbar / server unreachable", "err");
  }
}

function wireEvents() {
  // Sprache
  $("#langToggle").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-lang]");
    if (!btn) return;
    setLang(btn.dataset.lang);
    $$("#langToggle button").forEach((b) => b.classList.toggle("active", b === btn));
    applyI18n();
    renderRefineChips();
    mascotRefreshLang();
    if (state.content) renderPreview();
  });

  // Anbieter
  $("#providerSelect").addEventListener("change", (e) => {
    state.provider = e.target.value;
    updateKeyFields();
  });

  // API-Key-Felder: speichern + Badge aktualisieren
  ["keyOpenai", "keyAnthropic"].forEach((id) => {
    $("#" + id).addEventListener("input", () => { saveKeys(); updateBadges(); });
  });
  $("#apiKeys").addEventListener("click", (e) => {
    const eye = e.target.closest(".key-eye");
    if (eye) toggleEye(eye);
  });

  // Upload
  wireDropzone();

  // Generieren / Navigation
  $("#generateBtn").addEventListener("click", (e) => {
    ripple(e, $("#generateBtn"));
    generate();
  });
  $("#backTo1").addEventListener("click", () => goStep(1));
  $("#toStep3").addEventListener("click", () => {
    goStep(3);
    updatePhotoThumb();
    renderPreview();
  });
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

  // Editor live -> Zustand
  $("#cvEditor").addEventListener("input", (e) => { state.content = e.target.value; });

  // Verfeinern
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
