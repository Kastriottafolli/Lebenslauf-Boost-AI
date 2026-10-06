import {API_BASE, BROWSER_ONLY} from './core/client.js';
import {createAnalyticsController} from './core/analytics.js';

const routes = {'lebenslauf-mit-ki':'resume','ai-resume-builder':'resume','cv-me-ia':'resume','anschreiben-mit-ki':'cover-letter','ai-cover-letter':'cover-letter','leter-aplikimi-me-ia':'cover-letter',impressum:'imprint', datenschutz:'privacy', agb:'terms', widerruf:'withdrawal', preise:'pricing', pricing:'pricing', lebenslauf:'resume', resume:'resume', anschreiben:'cover-letter', 'cover-letter':'cover-letter'};
const segments = location.pathname.split('/').filter(Boolean);
if (!segments.some(segment => /^admin(?:\.html)?$/.test(segment))) {
  const requestedLanguage = new URL(location.href).searchParams.get('lang');
  const language = ['de', 'en', 'sq'].includes(requestedLanguage) ? requestedLanguage : document.documentElement.lang;
  const page = routes[segments.at(-1)] || routes[segments.at(-2)] || 'home';
  const analytics = createAnalyticsController({language, page, apiBase:API_BASE, enabled:!BROWSER_ONLY, staticRoutes:__RUNTIME__==='browser'});
  analytics.mount();
}
