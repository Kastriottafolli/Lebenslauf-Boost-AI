/* API-Keys (Bring your own key): Eingabe, Speicherung, Sichtbarkeit. */
import { $, $$ } from "../dom.js";
import { state } from "../state.js";

const KEY_STORE = "lba_api_keys";

export function getKeys() {
  return {
    openai: ($("#keyOpenai")?.value || "").trim(),
    anthropic: ($("#keyAnthropic")?.value || "").trim(),
  };
}

// Keys stay only in the current tab's input fields, never in persistent storage.
export function saveKeys() {}
export function loadKeys() {
  try { localStorage.removeItem(KEY_STORE); } catch { /* storage may be blocked */ }
}

/** Zeigt nur die zum gewählten Anbieter passenden Key-Felder. */
export function updateKeyFields() {
  const need = state.provider === "compare"
    ? ["openai", "anthropic"]
    : state.provider === "openai" ? ["openai"] : ["anthropic"];
  $$("#apiKeys .key-field").forEach((f) => {
    f.hidden = !need.includes(f.dataset.key);
  });
}

/** Badge ist "an", wenn der Nutzer einen Key eingegeben hat ODER der Server einen hat. */
export function updateBadges() {
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

const EYE_ON = '<svg class="ic" viewBox="0 0 24 24"><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/></svg>';
const EYE_OFF = '<svg class="ic" viewBox="0 0 24 24"><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/><path d="M4 4l16 16"/></svg>';

export function toggleEye(eyeButton) {
  const inp = $("#" + eyeButton.dataset.target);
  inp.type = inp.type === "password" ? "text" : "password";
  eyeButton.innerHTML = inp.type === "password" ? EYE_ON : EYE_OFF;
}
