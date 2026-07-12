/* Alle HTTP-Aufrufe ans Backend — gebündelt an einer Stelle.
   Die Typen der Antworten sind in src/types/api.d.ts dokumentiert. */

const API = "";

/** POST mit Zeitabschaltung (verhindert ewiges „wird generiert …"). */
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
  } finally {
    clearTimeout(tid);
  }
}

async function toJsonOrThrow(response, fallbackMsg) {
  if (!response.ok) {
    let detail = fallbackMsg;
    try { detail = (await response.json()).detail || fallbackMsg; } catch (e) { /* ignore */ }
    throw new Error(detail);
  }
  return response.json();
}

export async function fetchStatus() {
  const r = await fetch(`${API}/api/status`);
  return toJsonOrThrow(r, "Status-Fehler");
}

export async function createSession(language) {
  const r = await fetch(`${API}/api/session?language=${language}`, { method: "POST" });
  return toJsonOrThrow(r, "Session-Fehler");
}

export async function uploadCv({ sessionId, file, openaiKey }) {
  const fd = new FormData();
  fd.append("session_id", sessionId);
  fd.append("file", file);
  fd.append("openai_key", openaiKey);
  const r = await fetch(`${API}/api/upload-cv`, { method: "POST", body: fd });
  return toJsonOrThrow(r, "Upload-Fehler");
}

export async function generateCv(body) {
  const r = await postJSON(`${API}/api/generate`, body);
  return toJsonOrThrow(r, "Fehler");
}

export async function refineCv(body) {
  const r = await postJSON(`${API}/api/refine`, body);
  return toJsonOrThrow(r, "Fehler");
}

export async function exportCv(body) {
  const r = await fetch(`${API}/api/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error("Export-Fehler");
  const blob = await r.blob();
  const cd = r.headers.get("Content-Disposition") || "";
  const m = cd.match(/filename="(.+?)"/);
  return { blob, filename: m ? m[1] : null };
}
