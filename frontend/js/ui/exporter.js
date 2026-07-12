/* Schritt 3: Design, Foto, Live-Vorschau und Download (PDF/DOCX). */
import * as api from "../api.js";
import { $, esc } from "../dom.js";
import { getLang, t } from "../i18n.js";
import { state } from "../state.js";
import { hideOverlay, showOverlay, toast } from "./feedback.js";
import { burstConfetti } from "./motion.js";
import { mascotProblem, tourNotify } from "./mascot.js";

// ── Foto ──
export function updatePhotoThumb() {
  const thumb = $("#photoThumb");
  if (state.photo) {
    thumb.innerHTML = `<img src="${state.photo}" alt="Foto">`;
  } else {
    thumb.innerHTML = `<span>${t("noPhoto")}</span>`;
  }
  $("#photoRemove").style.visibility = state.photo ? "visible" : "hidden";
}

// ── Vorschau ──
export function renderPreview() {
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

/** Minimaler Markdown->HTML-Konverter für das Lebenslauf-Format. */
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
export async function download() {
  const body = {
    session_id: state.sessionId,
    content: $("#cvEditor").value || state.content,
    format: state.format,
    design: state.design,
    language: getLang(),
    filename: $("#filename").value.trim() || "Lebenslauf",
    photo: state.photo || null,
  };
  showOverlay(t("exporting"), null, "export");
  try {
    const { blob, filename } = await api.exportCv(body);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || `${body.filename}.${state.format}`;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    burstConfetti(56);
    toast(t("downloadOk"), "ok");
    tourNotify("downloaded");
  } catch (e) {
    toast("⚠️ " + e.message, "err");
    mascotProblem("error");
  } finally { hideOverlay(); }
}
