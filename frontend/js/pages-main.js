import './main.js';
import { renderAnalysis } from './ui/generate.js';
import { SAMPLE, analyze } from './browser/demo.js';
import { uploadCv } from './ui/upload.js';
import { getLang } from './i18n.js';
import { state } from './state.js';
import { goStep } from './ui/steps.js';
import { updateBadges, updateKeyFields } from './ui/keys.js';

const COPY = {
  de:{
    keyNote:'Dein Key bleibt nur für diesen geöffneten Tab im Speicher. Beim Generieren werden Lebenslauf, Stelle und Wünsche direkt an den ausgewählten KI-Anbieter gesendet. API-Nutzung kann kostenpflichtig sein. Leer lassen = regelbasierter Demo-Modus.',
    f6d:'Ohne API-Key bleiben Lebenslauf und Bearbeitung in deinem Browser. Mit Key sendest du deine Angaben direkt an den ausgewählten KI-Anbieter. Keys werden nicht dauerhaft gespeichert.',
    f1d:'Die Browser-App liest den Text deines Lebenslaufs lokal. Der Keyword-Check vergleicht ihn mit der Stelle. KI-Anfragen verwenden den Lebenslauf als Quelle; prüfe die Ausgabe auf Richtigkeit.',
    f3d:'Mit deinen eigenen API-Keys kannst du Claude und OpenAI nutzen. Ohne Key erstellt die App deutlich markierte, regelbasierte Demo-Entwürfe.',
    pl1d:'PDF, Word oder TXT lokal einlesen. Ein Bewerbungsfoto kannst du später separat hinzufügen.',
    photoHint:'Optional: Lade ein Foto separat hoch. Es wird in Vorschau und Download eingefügt.',
    cvTitle:'2 · Lebenslauf hochladen',
    wishesHint:'Mit API-Key frei umsetzen. Im Demo-Modus wird „kürzer“ unterstützt; weitere Wünsche bearbeitest du im Editor.',
    atsHint:'Ein einfacher Wortabgleich mit der Stelle — keine Bewertung deiner Eignung.',
    mascotCompare:'Vergleiche die Entwürfe. Ohne API-Key sind beide regelbasierte Demo-Versionen.',
    mascotTour2Analysis:'Prüfe die enthaltenen und fehlenden Begriffe. Ergänze nur Fähigkeiten, die du tatsächlich besitzt.',
  },
  en:{
    keyNote:'Your key stays in memory only for this open tab. Generating sends your resume, job posting and preferences directly to the selected AI provider. API usage may incur charges. Leave blank for the rule-based demo.',
    f6d:'Without an API key, your resume and edits stay in your browser. With a key, your data goes directly to the selected AI provider. Keys are not saved persistently.',
    f1d:'The browser app reads your resume locally. The keyword check compares it with the job. AI requests use your resume as source material; review the output for accuracy.',
    f3d:'Use Claude and OpenAI with your own API keys. Without a key, the app creates clearly marked, rule-based demo drafts.',
    pl1d:'Read PDF, Word or TXT locally. You can add a photo separately later.',
    photoHint:'Optional: upload a photo separately. It will appear in the preview and download.',
    cvTitle:'2 · Upload resume',
    wishesHint:'Free-form preferences require an API key. Demo mode supports “shorter”; make other changes in the editor.',
    atsHint:'A simple word match against the posting — not an assessment of your suitability.',
    mascotCompare:'Compare the drafts. Without API keys, both are rule-based demo versions.',
    mascotTour2Analysis:'Check matched and missing terms. Only add skills you actually have.',
  },
};
// Register overrides before main.js initializes its UI.
import { setOverrides } from './i18n.js';
setOverrides(COPY);
function browserText() {
  const lang=getLang();
  document.querySelectorAll('[data-browser-de]').forEach(el=>el.textContent=el.dataset[lang==='en'?'browserEn':'browserDe']);
  document.querySelector('.foot').lastElementChild.textContent='Browser-App · Claude + OpenAI · PDF + Word';
}
document.addEventListener('DOMContentLoaded', () => {
  browserText();
  let analysisTimer;
  document.querySelector('#cvEditor').addEventListener('input', () => {
    clearTimeout(analysisTimer);
    analysisTimer = setTimeout(() => renderAnalysis(analyze(document.querySelector('#cvEditor').value, document.querySelector('#jobDescription').value)), 250);
  });
  document.querySelector('#langToggle').addEventListener('click',browserText);
  document.querySelector('#loadExample').addEventListener('click',async () => {
    const lang=getLang(), example=SAMPLE[lang];
    const button=document.querySelector('#loadExample'); button.disabled=true;
    try {
      // Loading a public sample always starts in free demo mode, without using existing keys.
      for (const id of ['keyOpenai','keyAnthropic']) document.getElementById(id).value='';
      document.querySelector('#jobDescription').value=example.job;
      document.querySelector('#wishes').value='';
      document.querySelector('#providerSelect input[value="compare"]').checked=true;
      state.provider='compare'; updateKeyFields(); updateBadges();
      await uploadCv(new File([example.cv],lang==='en'?'Example-resume.txt':'Beispiel-Lebenslauf.txt',{type:'text/plain'}));
      goStep(1);
      document.querySelector('#exampleStatus').textContent=lang==='en'
        ? 'Fictional sample loaded. Click “Generate resume” below. No API key needed.'
        : 'Fiktives Beispiel geladen. Klicke unten auf „Lebenslauf generieren“. Kein API-Key nötig.';
      document.querySelector('#generateBtn').scrollIntoView({behavior:'smooth',block:'center'});
    } finally {button.disabled=false;}
  });
});
