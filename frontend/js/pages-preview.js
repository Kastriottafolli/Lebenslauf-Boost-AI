/* Static GitHub Pages preview: no API requests or API-key storage. */
import { applyI18n, setLang } from './i18n.js';
import { initReveal, initHeroSpotlight, init3DTilt, initOrbParallax } from './ui/motion.js';

function translate(lang) {
  setLang(lang);
  applyI18n();
  document.querySelectorAll('[data-preview-de]').forEach(el => {
    el.textContent = el.dataset[lang === 'en' ? 'previewEn' : 'previewDe'];
  });
  document.querySelectorAll('#langToggle button').forEach(el => {
    el.classList.toggle('active', el.dataset.lang === lang);
  });
  document.querySelector('.key-note').textContent = lang === 'en'
    ? 'API-key input is disabled in this preview.'
    : 'Die Eingabe von API-Keys ist in dieser Vorschau deaktiviert.';
  document.querySelector('[data-i18n="f6d"]').textContent = lang === 'en'
    ? 'The locally running app also offers a demo mode without an API key.'
    : 'Die lokal gestartete App bietet auch einen Demo-Modus ohne API-Key.';
}
function showStep(step) {
  document.querySelectorAll('.panel').forEach(el => el.classList.toggle('active', el.id === `panel-${step}`));
  document.querySelectorAll('.step').forEach(el => el.classList.toggle('active', el.dataset.step === step));
  document.querySelectorAll('[data-preview-step]').forEach(el => el.setAttribute('aria-pressed', String(el.dataset.previewStep === step)));
  document.querySelector('#hero').hidden = step !== '1';
}
translate('de');
showStep('1');
document.querySelectorAll('[data-preview-step]').forEach(el => el.addEventListener('click', () => showStep(el.dataset.previewStep)));
document.querySelectorAll('#langToggle button').forEach(el => el.addEventListener('click', () => translate(el.dataset.lang)));
// Prevent the browser from opening a dropped CV in the read-only preview.
for (const event of ['dragover', 'drop']) document.addEventListener(event, e => e.preventDefault());
initReveal();
initHeroSpotlight();
init3DTilt();
initOrbParallax();
