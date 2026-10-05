export const BROWSER_ONLY = __RUNTIME__ === "browser" && !__API_BASE__;
export const API_BASE = __API_BASE__.replace(/\/$/, "");
let session = { session_id: "", session_token: "" }, loginToken = "";
export function setSession(value) {
  session = value;
}
export function getSession() {
  return session;
}
export function setLoginToken(value) {
  loginToken = value || "";
}
export async function api(path, body, method = body ? "POST" : "GET", options = {}) {
  if (BROWSER_ONLY) throw new Error("Diese Funktion ben\xF6tigt den Serverbetrieb / this feature requires server mode.");
  const timeoutMs = options.timeoutMs ?? 150000;
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0 || timeoutMs > 300000) {
    throw new TypeError("timeoutMs must be between 1 and 300000.");
  }
  const headers = { "X-Boosty-Request": "1" };
  if (session.session_token) headers["X-Session-Token"] = session.session_token;
  if (loginToken) headers.Authorization = `Bearer ${loginToken}`;
  if (body && !(body instanceof FormData)) headers["Content-Type"] = "application/json";
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
  try {
    let response;
    try {
      response = await fetch(API_BASE + path, { method, headers, body: body ? body instanceof FormData ? body : JSON.stringify(body) : void 0, credentials: "include", signal: controller.signal });
    } catch {
      const error = new Error(timedOut
        ? "Der Server antwortet nicht rechtzeitig. Bitte erneut versuchen / server response timed out. Please try again."
        : "Server nicht erreichbar / server unreachable.");
      error.code = timedOut ? "API_TIMEOUT" : "API_UNREACHABLE";
      throw error;
    }
    if (!response.ok) {
      let detail;
      try { detail = (await response.json()).detail; } catch { /* Preserve HTTP status even without JSON. */ }
      const error = new Error(typeof detail === "string" ? detail : typeof detail?.message === "string" ? detail.message : `${response.status}: Eingaben pr\xFCfen / check input.`);
      error.status = response.status;
      if (typeof detail?.code === "string" && /^[A-Z_]{1,64}$/.test(detail.code)) error.code = detail.code;
      throw error;
    }
    try { return await response.json(); }
    catch {
      const error = new Error(timedOut
        ? "Der Server antwortet nicht rechtzeitig. Bitte erneut versuchen / server response timed out. Please try again."
        : "Ungültige Serverantwort / invalid server response.");
      error.code = timedOut ? "API_TIMEOUT" : "API_RESPONSE_INVALID";
      throw error;
    }
  } finally {
    clearTimeout(timer);
  }
}
export async function newSession(language = "de", options = {}) {
  session = BROWSER_ONLY ? { session_id: crypto.randomUUID(), session_token: "" } : await api(`/api/session?language=${language}`, {}, "POST", options);
  return session;
}
