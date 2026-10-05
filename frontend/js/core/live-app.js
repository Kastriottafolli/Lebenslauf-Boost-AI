import { LANGUAGES } from "./locale.js";

const LIVE_APP_ORIGINS = new Set(["https://tafolliboost.com"]);
const ACCOUNT_MODES = new Set(["login", "register"]);

// Pages opens the hosted application as a separate page. No account data,
// credentials, API requests or cookies are passed between the two websites.
export function liveAccountUrl(liveAppUrl, language, mode = "login") {
  let url;
  try { url = new URL(liveAppUrl); } catch { return null; }
  if (url.protocol !== "https:" || !LIVE_APP_ORIGINS.has(url.origin)
      || url.username || url.password || url.pathname !== "/"
      || url.search || url.hash || !ACCOUNT_MODES.has(mode)) return null;
  url.searchParams.set("lang", LANGUAGES.includes(language) ? language : "de");
  url.searchParams.set("account", mode);
  return url.href;
}

export function accountModeFromSearch(search) {
  const params = new URLSearchParams(search);
  const modes = params.getAll("account");
  return modes.length === 1 && ACCOUNT_MODES.has(modes[0]) ? modes[0] : null;
}
