export const BROWSER_ONLY = __RUNTIME__ === "browser" && !__API_BASE__;
export const API_BASE = __API_BASE__;
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
export async function api(path, body, method = body ? "POST" : "GET") {
  if (BROWSER_ONLY) throw new Error("Diese Funktion ben\xF6tigt den Serverbetrieb / this feature requires server mode.");
  const headers = {};
  if (session.session_token) headers["X-Session-Token"] = session.session_token;
  if (loginToken) headers.Authorization = `Bearer ${loginToken}`;
  if (body && !(body instanceof FormData)) headers["Content-Type"] = "application/json";
  let response;
  try {
    response = await fetch(API_BASE + path, { method, headers, body: body ? body instanceof FormData ? body : JSON.stringify(body) : void 0, credentials: "include", signal: AbortSignal.timeout(15e4) });
  } catch {
    throw new Error("Server nicht erreichbar / server unreachable.");
  }
  if (!response.ok) {
    let detail;
    try {
      detail = (await response.json()).detail;
    } catch {
    }
    throw new Error(typeof detail === "string" ? detail : `${response.status}: Eingaben pr\xFCfen / check input.`);
  }
  return response.json();
}
export async function newSession(language = "de") {
  session = BROWSER_ONLY ? { session_id: crypto.randomUUID(), session_token: "" } : await api(`/api/session?language=${language}`, {}, "POST");
  return session;
}
