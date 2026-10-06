export const ANALYTICS_PREFERENCE_VERSION = '2026-10-06';
export const ANALYTICS_STORAGE_KEY = 'boosty_analytics_preferences';
export const ANALYTICS_RETENTION_DAYS = 180;
const PREFERENCE_LIFETIME = ANALYTICS_RETENTION_DAYS * 86400000;
const PAGES = new Set(['home', 'app', 'account', 'pricing', 'imprint', 'privacy', 'terms', 'withdrawal', 'resume', 'cover-letter']);
const TOKEN = /^[A-Za-z0-9_-]{43}$/;
const COPY = {
  de: {title:'Optionale Nutzungsanalyse', body:'Mit deiner Einwilligung erfassen wir Gerät, ungefähres Land, maskierte IP-Adresse und aktive Zeit. So verstehen wir die Nutzung und verbessern die App. Ohne Einwilligung stehen dir alle notwendigen Funktionen zur Verfügung.', necessary:'Nur notwendig', allow:'Statistik erlauben', privacy:'Datenschutzerklärung', settings:'Statistik-Einstellungen', current:'Mit „Nur notwendig“ kannst du deine Einwilligung jederzeit widerrufen. Deine Auswahl gilt für 180 Tage.'},
  en: {title:'Optional usage analytics', body:'With your consent, we record device type, approximate country, masked IP address and active time. This helps us understand usage and improve the app. All necessary features remain available without consent.', necessary:'Necessary only', allow:'Allow statistics', privacy:'Privacy policy', settings:'Statistics settings', current:'Choose “Necessary only” to withdraw consent at any time. Your choice lasts for 180 days.'},
  sq: {title:'Analizë opsionale e përdorimit', body:'Me pëlqimin tënd, regjistrojmë llojin e pajisjes, shtetin e përafërt, adresën IP të maskuar dhe kohën aktive. Kjo na ndihmon të kuptojmë përdorimin dhe të përmirësojmë aplikacionin. Të gjitha funksionet e nevojshme mbeten të disponueshme pa pëlqim.', necessary:'Vetëm të nevojshmet', allow:'Lejo statistikat', privacy:'Politika e privatësisë', settings:'Cilësimet e statistikave', current:'Zgjidh “Vetëm të nevojshmet” për ta tërhequr pëlqimin në çdo kohë. Zgjedhja jote vlen për 180 ditë.'},
};

export function readAnalyticsPreference(storage, now = Date.now()) {
  try {
    const value = JSON.parse(storage?.getItem(ANALYTICS_STORAGE_KEY) || 'null');
    if (!value || value.version !== ANALYTICS_PREFERENCE_VERSION || !['necessary', 'analytics'].includes(value.choice)) return null;
    const timestamp = Date.parse(value.timestamp);
    if (!Number.isFinite(timestamp) || timestamp > now || now - timestamp >= PREFERENCE_LIFETIME) return null;
    return {version:value.version, choice:value.choice, timestamp:value.timestamp};
  } catch { return null; }
}

// Short samples deliberately discard sleep, suspended timers and clock jumps.
export function createEngagementClock({now = Date.now, performanceNow = now} = {}) {
  let previousWall = now(), previousPerformance = performanceNow(), previouslyActive = false, milliseconds = 0;
  return {
    sample(active) {
      const wall = now(), performance = performanceNow();
      const elapsedWall = wall - previousWall, elapsedPerformance = performance - previousPerformance;
      if (active && previouslyActive && elapsedWall >= 0 && elapsedPerformance >= 0 && elapsedWall <= 2500 && elapsedPerformance <= 2500) milliseconds = Math.min(86400000, milliseconds + Math.min(elapsedWall, elapsedPerformance));
      previousWall = wall; previousPerformance = performance; previouslyActive = active;
      return Math.floor(milliseconds / 1000);
    },
    reset(active = false) {previousWall = now(); previousPerformance = performanceNow(); previouslyActive = active; milliseconds = 0;},
    seconds() {return Math.floor(milliseconds / 1000);},
  };
}

export function createAnalyticsController({language = 'de', page = 'home', apiBase = '', enabled = true, staticRoutes = false, root, environment = {}} = {}) {
  const win = environment.window || globalThis.window, doc = environment.document || globalThis.document;
  const now = environment.now || Date.now;
  const performanceNow = environment.performanceNow || (() => win.performance.now());
  const interval = environment.setInterval || ((work, delay) => win.setInterval(work, delay));
  const cancelInterval = environment.clearInterval || (id => win.clearInterval(id));
  const transportFetch = environment.fetch || ((...args) => globalThis.fetch(...args));
  let storage = environment.storage;
  if (storage === undefined) {try {storage = win.localStorage;} catch {storage = null;}}
  let locale = COPY[language] ? language : 'de', currentPage = PAGES.has(page) ? page : 'home';
  let preference = readAnalyticsPreference(storage, now()), mounted = false, settingsOpen = !preference, unloaded = false;
  if (!preference) {try {storage?.removeItem(ANALYTICS_STORAGE_KEY);} catch { /* Invalid preferences never authorize collection. */ }}
  let visitToken = '', pendingStart = false, generation = 0, revocations = 0, tokenIssuedAt = 0, heartbeatPending = false, sampleTimer, heartbeatTimer, banner, generatedSettings;
  const clock = createEngagementClock({now, performanceNow});
  const visibleAndFocused = () => doc.visibilityState === 'visible' && doc.hasFocus();
  const allowed = () => preference?.choice === 'analytics' && enabled && mounted && !unloaded;
  const node = (tag, text, className) => {const el = doc.createElement(tag); if (text) el.textContent = text; if (className) el.className = className; return el;};
  async function request(path, body, keepalive = false) {
    if (!enabled) return null;
    const abort = new AbortController();
    const timeout = globalThis.setTimeout(() => abort.abort(), 10000);
    try {
      const response = await transportFetch(String(apiBase).replace(/\/$/, '') + '/api/traffic/' + path, {method:'POST', credentials:'omit', headers:{'Content-Type':'application/json', 'X-Boosty-Request':'1'}, body:JSON.stringify(body), referrerPolicy:'no-referrer', keepalive, signal:abort.signal});
      return response.ok ? await response.json() : null;
    } catch { return null; }
    finally { globalThis.clearTimeout(timeout); }
  }
  function endToken(token, withdraw, activeSeconds) {
    if (!TOKEN.test(token)) return Promise.resolve();
    return request('end', {visit_token:token, active_seconds:activeSeconds, ...(withdraw ? {withdraw:true} : {})}, true);
  }
  function stop(withdraw = false) {
    generation++; clock.sample(!!visitToken && visibleAndFocused());
    const token = visitToken, seconds = clock.seconds(); visitToken = ''; tokenIssuedAt = 0; clock.reset();
    return endToken(token, withdraw, seconds);
  }
  function ensurePreferenceCurrent() {
    if (preference && !readAnalyticsPreference({getItem:() => JSON.stringify(preference)}, now())) {
      preference = null; settingsOpen = true; try {storage?.removeItem(ANALYTICS_STORAGE_KEY);} catch {} stop(false); render();
    }
  }
  async function start() {
    ensurePreferenceCurrent();
    if (!allowed() || !visibleAndFocused() || visitToken || pendingStart) return;
    const requestGeneration = generation, requestPage = currentPage, requestRevocations = revocations; pendingStart = true;
    try {
      const result = await request('start', {page:requestPage, analytics_consent:true});
      const token = result?.visit_token;
      if (!TOKEN.test(token || '')) return;
      if (requestGeneration !== generation || !allowed() || currentPage !== requestPage) {
        await endToken(token, requestRevocations !== revocations || preference?.choice !== 'analytics', 0); return;
      }
      visitToken = token; tokenIssuedAt = now(); clock.reset(visibleAndFocused());
    } finally {
      pendingStart = false;
      if (allowed() && requestGeneration !== generation) start();
    }
  }
  function sample() {
    ensurePreferenceCurrent();
    clock.sample(allowed() && !!visitToken && visibleAndFocused());
  }
  async function heartbeat() {
    sample();
    if (allowed() && visitToken && now() - tokenIssuedAt >= 86400000 - 30000) {
      stop(false); start(); return;
    }
    if (allowed() && visitToken && visibleAndFocused() && !heartbeatPending) {
      heartbeatPending = true;
      try { await request('heartbeat', {visit_token:visitToken, active_seconds:clock.seconds()}); }
      finally { heartbeatPending = false; }
    } else if (allowed() && !visitToken) start();
  }
  function privacyUrl() {
    const base = doc.querySelector('meta[name="app-base"]')?.content || '/';
    const url = new URL('datenschutz/' + (staticRoutes && locale !== 'de' ? locale + '/' : ''), new URL(base, win.location.href));
    if (!staticRoutes) url.searchParams.set('lang', locale);
    return url.href;
  }
  function render() {
    if (!banner) return;
    const copy = COPY[locale]; banner.hidden = !settingsOpen; banner.setAttribute('aria-label', copy.settings);
    const heading = node('h2', copy.title), description = node('p', copy.body), expiry = node('p', copy.current, 'analytics-preference-note');
    const actions = node('div', '', 'analytics-consent-actions');
    [['necessary', copy.necessary], ['analytics', copy.allow]].forEach(([choice, title]) => {
      const button = node('button', title, 'button outline analytics-choice'); button.type = 'button'; button.dataset.analyticsChoice = choice;
      button.addEventListener('click', () => choose(choice)); actions.append(button);
    });
    const link = node('a', copy.privacy); link.href = privacyUrl();
    banner.replaceChildren(heading, description, actions, expiry, link);
    doc.querySelectorAll('[data-analytics-settings]').forEach(button => {button.textContent = copy.settings;});
  }
  function choose(choice) {
    if (!['necessary', 'analytics'].includes(choice)) return;
    preference = {version:ANALYTICS_PREFERENCE_VERSION, choice, timestamp:new Date(now()).toISOString()};
    try {storage?.setItem(ANALYTICS_STORAGE_KEY, JSON.stringify(preference));} catch { /* Choice still applies for this page when storage is unavailable. */ }
    settingsOpen = false; render();
    if (choice === 'necessary') {revocations++; stop(true);} else start();
  }
  function storageChanged(event) {
    if (event.key !== ANALYTICS_STORAGE_KEY && event.key !== null) return;
    preference = readAnalyticsPreference(storage, now()); settingsOpen = !preference;
    if (preference?.choice !== 'analytics') {revocations++; stop(true);} else start();
    render();
  }
  function activityChanged() {sample(); start();}
  function pageHide() {unloaded = true; stop(false);}
  function pageShow() {unloaded = false; clock.reset(); start();}
  function settingsClicked(event) {
    if (event.target.closest?.('[data-analytics-settings]')) {event.preventDefault(); openSettings();}
  }
  function mount() {
    if (mounted) return controller;
    mounted = true; banner = node('section', '', 'analytics-consent-banner'); banner.dataset.boostyAnalyticsBanner = '1'; banner.setAttribute('role', 'region');
    (root || doc.body).append(banner);
    if (!doc.querySelector('[data-analytics-settings]')) {
      generatedSettings = node('button', COPY[locale].settings, 'analytics-settings'); generatedSettings.type = 'button'; generatedSettings.dataset.analyticsSettings = '1';
      (doc.querySelector('footer') || root || doc.body).append(generatedSettings);
    }
    doc.addEventListener('click', settingsClicked); doc.addEventListener('visibilitychange', activityChanged);
    win.addEventListener('storage', storageChanged); win.addEventListener('focus', activityChanged); win.addEventListener('blur', activityChanged); win.addEventListener('pagehide', pageHide); win.addEventListener('pageshow', pageShow);
    sampleTimer = interval(sample, 1000); heartbeatTimer = interval(heartbeat, 15000);
    render(); start(); return controller;
  }
  function openSettings() {if (!mounted) mount(); settingsOpen = true; render();}
  function setLanguage(value) {locale = COPY[value] ? value : 'de'; render();}
  function setPage(value) {
    const next = PAGES.has(value) ? value : 'home';
    if (next === currentPage) return;
    currentPage = next; stop(false); start();
  }
  function destroy() {
    if (!mounted) return;
    stop(false); mounted = false; cancelInterval(sampleTimer); cancelInterval(heartbeatTimer);
    doc.removeEventListener('click', settingsClicked); doc.removeEventListener('visibilitychange', activityChanged);
    win.removeEventListener('storage', storageChanged); win.removeEventListener('focus', activityChanged); win.removeEventListener('blur', activityChanged); win.removeEventListener('pagehide', pageHide); win.removeEventListener('pageshow', pageShow);
    banner.remove(); generatedSettings?.remove(); banner = null;
  }
  const controller = {mount, setLanguage, openSettings, setPage, destroy};
  return controller;
}
