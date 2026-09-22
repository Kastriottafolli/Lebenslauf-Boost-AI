// Deterministic demo: only source facts are retained; job keywords are never added as skills.
const STOP = new Set(('der die das den dem des ein eine einer einem einen und oder mit für von im in am an auf zu zur zum ist sind wir du sie ihr ihre ihren unser unsere suchen gesucht bieten haben hast erfahrung entwickelst schreibst arbeitest willkommen sowie als bei sich auch the a an and or to of for in on with is are we you your our this that will have has from as be').split(' '));
export function keywords(text) {
  const words = (text.toLowerCase().match(/[\p{L}\p{N}][\p{L}\p{N}+#.-]*/gu) || []).map(w => w.replace(/[.-]+$/, ''));
  const counts = new Map();
  for (const w of words) if (w.length > 2 && !STOP.has(w) && !/^\d+$/.test(w)) counts.set(w, (counts.get(w) || 0) + 1);
  return [...counts].sort((a,b) => b[1] - a[1]).slice(0,24).map(([w]) => w);
}
export function analyze(content, job) {
  const words = new Set((content.split('\n').filter(l => !l.startsWith('>')).join('\n').toLowerCase().match(/[\p{L}\p{N}][\p{L}\p{N}+#.-]*/gu) || []).map(w=>w.replace(/[.-]+$/, '')));
  const matched_keywords = [], missing_keywords = [];
  for (const word of keywords(job)) (words.has(word) ? matched_keywords : missing_keywords).push(word);
  return { ats_score: Math.round(100 * matched_keywords.length / (matched_keywords.length + missing_keywords.length || 1)), matched_keywords, missing_keywords };
}
export function demoCv(source, job, language = 'de', variant = 'claude') {
  const lines = source.trim().split(/\r?\n/).map(l => l.trim());
  const note = language === 'en'
    ? '> DEMO: Rule-based formatting of your source text; no AI request was made.'
    : '> DEMO: Regelbasierte Aufbereitung deiner Angaben; keine KI-Anfrage.';
  let content = lines.join('\n');
  if (!/^# /m.test(content)) {
    const name = lines.shift().replace(/^#+\s*/, '');
    content = `# ${name}\n\n${lines.join('\n')}`;
  }
  if (variant === 'openai') {
    // Reorder only adjacent bullet points, preserving headings, jobs, dates and every fact.
    content = content.replace(/(?:^[-*] .*(?:\n|$))+/gm, block => {
      const ranked = block.trim().split('\n').map((line, index) => ({ line, index, score: analyze(line, job).matched_keywords.length }));
      ranked.sort((a,b) => b.score-a.score || a.index-b.index);
      return ranked.map(x=>x.line).join('\n')+'\n';
    });
  }
  return `${content.trim()}\n\n${note}`;
}
export function demoRefine(content, instruction, language = 'de') {
  let text = content;
  if (/kürzer|short|1 seite|one page|1 page|kompakt/i.test(instruction)) {
    text = text.replace(/(?:^[-*] .*(?:\n|$)){3,}/gm, block => block.trim().split('\n').slice(0,2).join('\n')+'\n');
  } else if (/kennzahl|number|metric|technisch|technical/i.test(instruction)) {
    text = text.replace(/(?:^[-*] .*(?:\n|$))+/gm, block => block.trim().split('\n').map((line,index)=>({line,index,score:/kennzahl|number|metric/i.test(instruction) ? Number(/\d/.test(line)) : keywords(line).length})).sort((a,b)=>b.score-a.score || a.index-b.index).map(x=>x.line).join('\n')+'\n');
  } else if (/förmlich|formal/i.test(instruction)) {
    text = text.replace(/\b(?:Ich habe|I have)\s+/g, '').replace(/\b(?:super|really|sehr)\s+/gi, '');
  } else {
    throw new Error(language === 'en' ? 'Free-form rewriting requires an API key. In demo mode, try Shorter, More metrics, Technical or Formal, or edit the text directly.' : 'Freie Umformulierungen benötigen einen API-Key. Nutze im Demo-Modus Kürzer, Mehr Kennzahlen, Technischer oder Förmlicher — oder bearbeite den Text direkt.');
  }
  if (text === content) throw new Error(language === 'en' ? 'No matching change found in demo mode. Edit the text directly or use an API key for AI rewriting.' : 'Für diese Anpassung gibt es im Demo-Modus keine passende Änderung. Bearbeite den Text direkt oder nutze einen API-Key für KI-Umformulierungen.');
  return text;
}
export const SAMPLE = {
  de: {
    job: 'Frontend Developer (m/w/d)\nWir suchen Erfahrung mit JavaScript, TypeScript, React und HTML/CSS. Du entwickelst barrierefreie Oberflächen, schreibst Tests und arbeitest mit Git im agilen Team. Kenntnisse in REST-APIs und Performance-Optimierung sind willkommen.',
    cv: '# Alex Beispiel\nFrontend Developer\nalex@example.com · Berlin\n\n## Profil\nFrontend-Entwicklung mit Fokus auf verständliche und barrierefreie Webanwendungen.\n\n## Berufserfahrung\n### Frontend Developer · Musterfirma GmbH · 2022–2025\n- Umsetzung responsiver Oberflächen mit React, TypeScript und CSS.\n- Zusammenarbeit im agilen Team und Code-Reviews mit Git.\n- Verkürzung der Ladezeit um 25 % durch Performance-Optimierung.\n- Anbindung von REST-APIs und automatisierte Tests.\n\n## Ausbildung\nB.Sc. Medieninformatik · Beispielhochschule · 2018–2022\n\n## Kenntnisse\nJavaScript, TypeScript, React, HTML, CSS, Git, Tests\n\n## Sprachen\nDeutsch: fließend · Englisch: sehr gut',
  },
  en: {
    job: 'Frontend Developer\nWe are looking for JavaScript, TypeScript, React and HTML/CSS experience. Build accessible interfaces, write tests and use Git in an agile team. REST APIs and performance optimization are a plus.',
    cv: '# Alex Example\nFrontend Developer\nalex@example.com · Berlin\n\n## Profile\nFrontend development focused on clear, accessible web applications.\n\n## Experience\n### Frontend Developer · Example Company · 2022–2025\n- Built responsive interfaces using React, TypeScript and CSS.\n- Collaborated in an agile team and reviewed code using Git.\n- Reduced loading times by 25% through performance optimization.\n- Integrated REST APIs and automated tests.\n\n## Education\nB.Sc. Media Informatics · Example University · 2018–2022\n\n## Skills\nJavaScript, TypeScript, React, HTML, CSS, Git, tests\n\n## Languages\nGerman: fluent · English: advanced',
  },
};
