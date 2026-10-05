import writing from "../../../static/application-writing.json" with { type: "json" };
import { keywords } from "../browser/demo.js";
import { demoCv, analyze } from "../browser/demo.js";
export const DOCUMENTS = ["cv", "cover_letter", "motivation_letter", "email"];
export function parseProfile(source) {
  const lines = source.trim().split(/\r?\n/).filter(Boolean);
  const profile = { name: (lines[0] || "").replace(/^#+\s*/, ""), email: source.match(/[\w.+-]+@[\w.-]+\.[a-z]{2,}/i)?.[0] || "", phone: source.match(/(?:\+\d{1,3}[ ()-]*)?(?:\d[ ()-]*){9,15}/)?.[0]?.trim() || "", location: "", headline: "", experience: "", education: "", skills: "", languages: "", source_text: source, confirmed: false };
  const sections = { experience: /^(?:berufserfahrung|experience|work experience|professional experience|përvoja profesionale|përvojë pune)$/i, education: /^(?:ausbildung|education|arsimimi)$/i, skills: /^(?:kenntnisse|fähigkeiten|skills|technical skills|aftësitë|njohuritë)$/i, languages: /^(?:sprachen|languages|gjuhët)$/i };
  let current = null;
  for (const line of source.split(/\r?\n/)) {
    const heading = line.replace(/^#{1,2}\s*/, "").trim();
    const found = Object.entries(sections).find(([, pattern]) => pattern.test(heading));
    if (found) {
      current = found[0];
      continue;
    }
    if (/^#{1,2}\s/.test(line)) {
      current = null;
      continue;
    }
    if (current) profile[current] += (profile[current] ? "\n" : "") + line;
  }
  for (const key of Object.keys(sections)) profile[key] = profile[key].trim();
  if (lines[1] && !/[@#]|\d{4}/.test(lines[1]) && lines[1].length < 120) profile.headline = lines[1].trim();
  return profile;
}
export function canonicalSource(profile) {
  let source = profile.source_text;
  const extracted = parseProfile(source);
  for (const key of ["name", "email", "phone"]) if (profile[key] && extracted[key] && profile[key] !== extracted[key]) source = source.replace(extracted[key], profile[key]);
  return source;
}
export function profileSource(profile) {
  const labels = { name: "Name", email: "Email", phone: "Phone", location: "Location", headline: "Headline", experience: "Experience", education: "Education", skills: "Skills", languages: "Languages" };
  return Object.entries(labels).filter(([key]) => profile[key]?.trim()).map(([key, label]) => `${label}: ${profile[key].trim()}`).join("\n") + "\n\n" + profile.source_text;
}
export function applicationPrompt(language, document = "package") {
  const locale = writing.languages[language] || writing.languages.de;
  return writing.prompt.replace("{language}", locale.language) + (document === "package" ? " Return ONLY a JSON object with exactly four string fields: cv (complete Markdown resume), cover_letter, motivation_letter, email. No fences." : ` Return ONLY the complete updated ${document} in Markdown.`);
}
// Rank original, complete source excerpts; never turn a job requirement into a candidate fact.
export function relevantExcerpts(source, description, limit = 2) {
  const terms = keywords(description);
  const lines = source.split(/\r?\n/).flatMap(line => line.split(/(?<=[.!?])\s+(?=\p{Lu})/u)).map(l => l.replace(/^[-*•#]+\s*/, "").trim()).filter(l => l.length >= 35 && l.length <= 400 && !/@|https?:\/\//i.test(l));
  const unique = [...new Set(lines)];
  return unique.map((line, index) => ({line, index, score: terms.filter(t => keywords(line).includes(t)).length})).sort((a,b) => b.score-a.score || a.index-b.index).slice(0,limit).map(v=>v.line);
}
export function demoPackage(profile, job, language = "de", wishes = "") {
  const locale = writing.languages[language] || writing.languages.de;
  const resume = canonicalSource(profile).trim();
  const confirmed = Object.entries(profile).filter(([k,v]) => k !== "source_text" && typeof v === "string" && v.trim());
  const factSource = [profile.experience, profile.education, profile.skills, resume].filter(Boolean).join("\n");
  const facts = relevantExcerpts(factSource, job.description);
  const tasks = relevantExcerpts(job.description, factSource);
  const values = {name:profile.name || locale.name, role:job.title || locale.role, company:job.company || locale.company, greeting:job.recipient || locale.greeting, fact1:facts[0] || locale.nofact, fact2:facts[1] || facts[0] || locale.nofact, task1:tasks[0] || locale.notask, task2:tasks[1] || tasks[0] || locale.notask, personal:wishes.trim() || locale.personal, contact:[profile.email,profile.phone].filter(Boolean).join(" · ")};
  const interpolate = template => template.replace(/\{(\w+)\}/g, (_,key) => values[key] ?? "").trim();
  const additions = confirmed.filter(([k,v]) => !["name","email","phone"].includes(k) && !resume.includes(v));
  return {cv:demoCv(resume,job.description,language) + (additions.length ? "\n\n## " + locale.confirmed + "\n" + additions.map(([k,v])=>`${k}: ${v}`).join("\n") : ""), cover_letter:interpolate(locale.cover), motivation_letter:interpolate(locale.motivation), email:interpolate(locale.email)};
}
export function validatePackage(raw) {
  let value;
  try {
    value = typeof raw === "string" ? JSON.parse(raw) : raw;
  } catch {
    throw new Error("KI-Ausgabe war keine g\xFCltige Bewerbungsmappe / invalid application package. Bitte erneut versuchen.");
  }
  if (!value || DOCUMENTS.some((k) => typeof value[k] !== "string" || value[k].trim().length < 10 || value[k].length > 6e4)) throw new Error("Unvollst\xE4ndige Bewerbungsmappe / incomplete application package.");
  return Object.fromEntries(DOCUMENTS.map((k) => [k, value[k].trim()]));
}
export function assessPackage(documents, job, source) {
  const analysis = analyze(documents.cv, job.description);
  const newNumbers = [...documents.cv.matchAll(/\b\d+(?:[.,]\d+)?\s*%/g)].map((m) => m[0]).filter((n) => !source.includes(n));
  return { ...analysis, checks: { placeholders: DOCUMENTS.some((k) => /\[[^\]]+\]/.test(documents[k])), new_metrics: [...new Set(newNumbers)], short_letters: ["cover_letter","motivation_letter"].filter(k=>documents[k].trim().split(/\s+/).length<120) }, notice: "Keyword-Abdeckung ist keine Einstellungswahrscheinlichkeit / keyword coverage is not a hiring probability." };
}
