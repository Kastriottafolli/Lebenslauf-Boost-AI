import { PROVIDERS, callProvider } from "./core/providers.js";
import { DOCUMENTS, parseProfile, profileSource, applicationPrompt, demoPackage, validatePackage, assessPackage } from "./core/application.js";
import { BROWSER_ONLY, api, newSession, getSession, setLoginToken } from "./core/client.js";
import { SAMPLE } from "./browser/demo.js";
import { readDocument } from "./browser/import.js";
import branding from "../../static/branding.json" with { type: "json" };
import { BOOSTY_SYSTEM, TOUR, boostyAnswer } from "./core/boosty.js";
import { mountAdmin } from "./admin.js";
const $ = (selector) => document.querySelector(selector), $$ = (selector) => [...document.querySelectorAll(selector)];
const labels = { name: ["Name", "Name"], email: ["E-Mail", "Email"], phone: ["Telefon", "Phone"], location: ["Ort / Adresse", "Location / address"], headline: ["Berufliche \xDCberschrift", "Professional headline"], experience: ["Berufserfahrung (Korrekturen / Erg\xE4nzungen)", "Experience (corrections / additions)"], education: ["Ausbildung", "Education"], skills: ["Kenntnisse", "Skills"], languages: ["Sprachen", "Languages"] };
const docLabels = { cv: ["Lebenslauf", "Resume"], cover_letter: ["Anschreiben", "Cover letter"], motivation_letter: ["Motivation", "Motivation"], email: ["E-Mail", "Email"] };
const state = { language: new URLSearchParams(location.search).get("lang") === "en" ? "en" : document.documentElement.lang === "en" ? "en" : "de", profile: parseProfile(""), documents: null, document: "cv", photo: null, keys: {}, models: {}, provider: "openai", step: 1, isDemo: true, projectId: null, account: null, analysis: null, versions: [] };
const tr = (de, en) => state.language === "en" ? en : de;
let toastTimer, installPrompt;
let comparisonResults = [];
let tourIndex = 0, tourTarget, tourActive = false, embeddedAdmin;
function usage(event) {
  if (!BROWSER_ONLY) api("/api/usage", { session_id: getSession().session_id, event }).catch(() => {});
}
function boostyTip() {
  const tip = TOUR[tourIndex];
  $("#boostyTip").textContent = tip[state.language];
}
function guideTo(index) {
  tourTarget?.classList.remove("boosty-tour-target");
  const tip = TOUR[index];
  if (tip.step === 4 && !state.documents) {
    notify(tr("Erstelle zuerst eine Mappe mit der Demo oder deiner KI. Danach begleite ich dich zum Export.", "Create an application using demo or AI first. Then I can guide you to export."));
    return;
  }
  tourIndex = index;
  tourActive = true;
  showStep(tip.step);
  tourTarget = $(tip.target);
  tourTarget?.classList.add("boosty-tour-target");
  tourTarget?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "center" });
  boostyTip();
}
async function askBoosty(event) {
  event.preventDefault();
  const question = $("#boostyQuestion").value.trim();
  if (!question) return;
  const answer = $("#boostyAnswer"), submit = $("#boostyForm button");
  submit.disabled = true;
  try {
    if (!$("#boostyAi").checked) {
      answer.textContent = tr("Boosty · Bedienungshilfe\n\n", "Boosty · App help\n\n") + boostyAnswer(question, state.language).content;
      return;
    }
    const options = collectProvider();
    if (!state.keys[state.provider]) throw new Error(tr("Trage deinen API-Key in Schritt 3 ein. Für Bedienungsfragen kannst du KI deaktivieren.", "Enter your API key in step 3. For app help you can disable AI."));
    answer.textContent = tr("Boosty denkt nach …", "Boosty is thinking …");
    const result = BROWSER_ONLY ? await callProvider(state.provider, state.keys[state.provider], BOOSTY_SYSTEM, [{ role: "user", content: `Language: ${state.language}\nQuestion: ${question}` }], options) : await api("/api/assistant", { session_id: getSession().session_id, question, language: state.language, ...options, keys: keysBody(), consent: true });
    answer.textContent = tr("Boosty · KI-Antwort · Angaben prüfen\n\n", "Boosty · AI answer · Verify details\n\n") + result.content;
  } catch (error) {
    answer.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
}
function notify(message, error = false) {
  $("#status").textContent = message;
  $("#status").classList.toggle("error", error);
  $("#status").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("#status").hidden = true, error ? 15e3 : 6500);
}
async function busy(label, work) {
  $("#busyTitle").textContent = label;
  $("#busy").hidden = false;
  $("#workspace").setAttribute("aria-busy", "true");
  try {
    return await work();
  } finally {
    $("#busy").hidden = true;
    $("#workspace").removeAttribute("aria-busy");
  }
}
function action(work) {
  return async (event) => {
    try {
      await work(event);
    } catch (error) {
      notify(error.message || String(error), true);
    }
  };
}
function applyLanguage() {
  document.documentElement.lang = state.language;
  document.title = branding.name + " – " + tr("Lebenslauf und Bewerbung mit KI", "AI resume and application builder");
  $$("[data-de]").forEach((el) => el.textContent = el.dataset[state.language]);
  $$("[data-placeholder-de]").forEach((el) => el.placeholder = el.dataset[state.language === "en" ? "placeholderEn" : "placeholderDe"]);
  $("#language").textContent = state.language === "en" ? "DE" : "EN";
  $("#language").setAttribute("aria-label", tr("Sprache auf Englisch wechseln", "Switch language to German"));
  Object.entries(labels).forEach(([key, value]) => $("#profile-" + key).previousElementSibling.textContent = value[state.language === "en" ? 1 : 0]);
  renderTabs();
  providerView(false);
  $("#runtimeNotice").textContent = BROWSER_ONLY ? tr("Browserbetrieb: Import, Demo und Export laufen lokal. KI-Anfragen gehen direkt an den Anbieter. Stellenlink-Import und Konten ben\xF6tigen den Server.", "Browser mode: import, demo and export run locally. AI requests go directly to your provider. Job URL import and accounts require the server.") : tr("Serverbetrieb: Datei-Import und Stellenlinks werden auf diesem Server verarbeitet. API-Keys werden nicht gespeichert.", "Server mode: file imports and job links are processed on this server. API keys are not stored.");
  $("#privacyExplanation").textContent = BROWSER_ONLY ? tr("Ohne Konto bleiben die Angaben bis zum Neuladen im Arbeitsspeicher des Browsers. Beim Export entstehen pers\xF6nliche Dateien auf deinem Ger\xE4t. Mit API-Key werden Profil und Stellenbeschreibung an den gew\xE4hlten KI-Anbieter gesendet. Dessen Regeln zur Speicherung gelten zus\xE4tzlich.", "Without an account, details remain in browser memory until reload. Exports create personal files on your device. With an API key, your profile and posting are sent to that provider; their retention rules also apply.") : tr("Datei-Uploads werden auf diesem Server verarbeitet und in deiner gesch\xFCtzten Sitzung gespeichert. Bewerbungen werden nur auf deinen Wunsch im Konto gespeichert. Du kannst Sitzung und Konto l\xF6schen. F\xFCr KI-Anfragen gelten zus\xE4tzlich die Datenschutzregeln des gew\xE4hlten Anbieters.", "Uploads are processed on this server and stored in your protected session. Applications are saved to your account only when you choose. You can delete your session or account. AI provider privacy rules additionally apply.");
  $("#guideLink").href = new URL(`${state.language}/` + (state.language === "en" ? "ai-resume-builder/" : "lebenslauf-mit-ki/"), baseURL()).href;
  accountView();
  boostyTip();
  if (state.documents) {
    if (state.savedProject) $("#generationInfo").textContent = tr("Gespeicherte Bewerbung · alle Angaben erneut prüfen.", "Saved application · verify all details again.");
    else if (state.isDemo) $("#generationInfo").textContent = tr("DEMO · Regelbasierte Vorlagen. Platzhalter selbst ergänzen.", "DEMO · Rule-based templates. Fill in placeholders yourself.");
    renderDocument();
  }
}
function baseURL() {
  return new URL(document.querySelector('meta[name="app-base"]')?.content || "./", location.href);
}
function readProfile() {
  const profile = { source_text: $("#source").value.trim(), confirmed: $("#confirmed").checked };
  Object.keys(labels).forEach((k) => profile[k] = $("#profile-" + k).value.trim());
  state.profile = profile;
  return profile;
}
function fillProfile(profile) {
  state.profile = { ...parseProfile(""), ...profile };
  $("#source").value = state.profile.source_text;
  Object.keys(labels).forEach((k) => $("#profile-" + k).value = state.profile[k] || "");
  $("#confirmed").checked = !!state.profile.confirmed;
}
function job() {
  return { title: $("#jobTitle").value.trim(), company: $("#jobCompany").value.trim(), recipient: $("#jobRecipient").value.trim(), email: $("#jobEmail").value.trim(), url: $("#jobUrl").value.trim(), description: $("#jobDescription").value.trim() };
}
function fillJob(value) {
  for (const [key, id] of Object.entries({ title: "jobTitle", company: "jobCompany", recipient: "jobRecipient", email: "jobEmail", url: "jobUrl", description: "jobDescription" })) $("#" + id).value = value[key] || "";
}
function collectProvider() {
  state.keys[state.provider] = $("#apiKey").value.trim();
  state.models[state.provider] = $("#model").value.trim();
  return { provider: state.provider, model: state.models[state.provider], endpoint: $("#azureEndpoint").value.trim() };
}
function keysBody() {
  return Object.fromEntries(PROVIDERS.map((p) => [p.key, state.keys[p.id] || ""]));
}
function requestBody(demo = false) {
  const options = collectProvider();
  return { session_id: getSession().session_id, profile: readProfile(), job: job(), wishes: $("#wishes").value.trim(), language: $("#outputLanguage").value, ...options, keys: keysBody(), demo };
}
function validateInputs(ai = false) {
  const profile = readProfile();
  if (profile.source_text.length < 10) throw new Error(tr("Bitte den Lebenslauf importieren oder Text einf\xFCgen.", "Import or paste your resume."));
  if (!profile.confirmed) throw new Error(tr("Bitte deine Profilangaben pr\xFCfen und best\xE4tigen.", "Please verify and confirm your profile."));
  if (job().description.length < 10) throw new Error(tr("Bitte die Stellenbeschreibung erg\xE4nzen.", "Please add the job description."));
  collectProvider();
  if (ai && !$("#aiConsent").checked) throw new Error(tr("Bitte die Daten\xFCbermittlung an deinen KI-Anbieter best\xE4tigen.", "Please confirm sending your details to the AI provider."));
  if (ai && !state.keys[state.provider]) throw new Error(tr("Bitte einen API-Key eingeben oder die Demo ausw\xE4hlen.", "Enter an API key or select demo."));
}
function showStep(step) {
  if (step === 4 && !state.documents) {
    notify(tr("Erstelle zuerst deine Bewerbungsmappe.", "Create your application package first."));
    return;
  }
  state.step = step;
  if (!tourActive) tourIndex = Math.max(0, TOUR.findIndex(t => t.step === step));
  else tourActive = false;
  boostyTip();
  $$("[data-panel]").forEach((el) => el.hidden = Number(el.dataset.panel) !== step);
  $$("[data-step]").forEach((el) => {
    el.classList.toggle("active", Number(el.dataset.step) === step);
    if (Number(el.dataset.step) === step) el.setAttribute("aria-current", "step");
    else el.removeAttribute("aria-current");
  });
}
function providerView(reset = true) {
  const provider = PROVIDERS.find((p) => p.id === state.provider);
  if (reset) {
    $("#model").value = state.models[state.provider] ?? provider.default_model;
    $("#apiKey").value = state.keys[state.provider] || "";
    $("#apiKey").type = "password";
    $("#keyStatus").textContent = "";
    $("#aiConsent").checked = false;
  }
  $("#modelOptions").replaceChildren(...provider.models.map((m) => {
    const option = document.createElement("option");
    option.value = m;
    return option;
  }));
  $("#azureField").hidden = state.provider !== "azure";
  $("#keyLink").href = provider.key_url;
  $("#modelLink").href = provider.docs_url;
}
async function importResume(file) {
  if (!file) return;
  if (file.size > 10 * 1024 * 1024) throw new Error(tr("Maximal 10 MB.", "Maximum 10 MB."));
  if (!/\.(pdf|docx|txt)$/i.test(file.name)) throw new Error("PDF, DOCX oder TXT / PDF, DOCX or TXT");
  await busy(tr("Lebenslauf wird eingelesen \u2026", "Reading your resume \u2026"), async () => {
    let text, photo;
    if (BROWSER_ONLY) {
      const ext = file.name.split(".").pop().toLowerCase();
      text = ext === "txt" ? await file.text() : await readDocument(file, ext);
    } else {
      const data = new FormData();
      data.append("session_id", getSession().session_id);
      data.append("file", file);
      const result = await api("/api/upload-cv", data);
      text = result.source_text;
      photo = result.photo;
    }
    if (!text || text.trim().length < 10) throw new Error(tr("Kein lesbarer Text. Bei gescannten PDFs zuerst Texterkennung durchf\xFChren.", "No readable text. Scanned PDFs need OCR first."));
    if (text.length > 6e4) throw new Error(tr("Maximal 60.000 Zeichen.", "Maximum 60,000 characters."));
    fillProfile(parseProfile(text));
    state.photo = photo || null;
    $("#fileStatus").textContent = `${file.name} \xB7 ${text.length.toLocaleString()} ${tr("Zeichen \xB7 Angaben pr\xFCfen", "characters \xB7 verify details")}`;
    showStep(1);
  });
}
function renderTabs() {
  const root = $("#documentTabs");
  root.replaceChildren(...DOCUMENTS.map((id) => {
    const button = document.createElement("button");
    button.id = `tab-${id}`;
    button.dataset.document = id;
    button.textContent = docLabels[id][state.language === "en" ? 1 : 0];
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", String(id === state.document));
    button.setAttribute("aria-controls", "documentEditor");
    button.tabIndex = id === state.document ? 0 : -1;
    button.classList.toggle("active", id === state.document);
    return button;
  }));
}
function renderPreview() {
  const root = $("#preview");
  root.replaceChildren();
  if (state.document === "cv" && state.photo) {
    const img = document.createElement("img");
    img.src = state.photo;
    img.alt = tr("Bewerbungsfoto", "Application photo");
    img.className = "photo-preview";
    root.append(img);
  }
  let list;
  for (const raw of (state.documents?.[state.document] || "").split("\n")) {
    const line = raw.trim();
    if (!line) {
      list = null;
      continue;
    }
    const heading = /^(#{1,3})\s+(.+)$/.exec(line);
    const bullet = /^[-*]\s+(.+)$/.exec(line);
    let node;
    if (heading) {
      node = document.createElement(`h${heading[1].length}`);
      node.textContent = heading[2];
      list = null;
    } else if (bullet) {
      if (!list) {
        list = document.createElement("ul");
        root.append(list);
      }
      node = document.createElement("li");
      node.textContent = bullet[1];
      list.append(node);
      continue;
    } else {
      node = document.createElement(line.startsWith("> ") ? "blockquote" : "p");
      node.textContent = line.replace(/^> /, "");
      list = null;
    }
    root.append(node);
  }
}
function renderDocument() {
  renderTabs();
  $("#editorLabel").textContent = docLabels[state.document][state.language === "en" ? 1 : 0];
  $("#documentEditor").value = state.documents[state.document];
  $("#documentEditor").setAttribute("aria-labelledby", "editorLabel");
  renderPreview();
  renderQuality();
}
function renderQuality() {
  if (!state.documents) return;
  const quality = assessPackage(state.documents, job(), profileSource(readProfile()));
  state.analysis = quality;
  const root = $("#quality");
  root.replaceChildren();
  const strong = document.createElement("strong");
  strong.textContent = tr("Keyword-Abdeckung", "Keyword coverage") + `: ${quality.ats_score}%`;
  root.append(strong);
  const p = document.createElement("p");
  p.textContent = tr("Ein Hinweis auf Wort\xFCberschneidungen, keine Einstellungswahrscheinlichkeit. Alle Angaben vor dem Versand pr\xFCfen.", "A word overlap indicator, not a hiring probability. Verify all details before sending.");
  root.append(p);
  const missing = document.createElement("div");
  missing.className = "keyword-list";
  missing.append(document.createTextNode(tr("Nicht belegt im Entwurf: ", "Missing from draft: ")));
  for (const word of quality.missing_keywords) {
    const span = document.createElement("span");
    span.textContent = word;
    missing.append(span);
  }
  if (!quality.missing_keywords.length) missing.append(document.createTextNode(tr("Keine gefunden.", "None found.")));
  root.append(missing);
  if (quality.checks.placeholders || quality.checks.new_metrics.length) {
    const note = document.createElement("p");
    note.textContent = tr("Pr\xFCfung n\xF6tig: ", "Needs review: ") + (quality.checks.placeholders ? tr("Platzhalter erg\xE4nzen. ", "Fill in placeholders. ") : "") + (quality.checks.new_metrics.length ? tr("Neue Kennzahlen kontrollieren: ", "Check new metrics: ") + quality.checks.new_metrics.join(", ") : "");
    root.append(note);
  }
}
async function generatePayload(body) {
  if (body.demo) {
    usage("demo.generate");
    return { documents: demoPackage(body.profile, body.job, body.language), is_demo: true, model: "demo", provider: body.provider };
  }
  if (!BROWSER_ONLY) return api("/api/package", body);
  const config = PROVIDERS.find((p) => p.id === body.provider);
  const documents = body.demo ? demoPackage(body.profile, body.job, body.language) : validatePackage((await callProvider(body.provider, body.keys[config.key], applicationPrompt(body.language), [{ role: "user", content: JSON.stringify({ confirmed_profile: body.profile, job: body.job, preferences: body.wishes }) }], body)).content);
  return { documents, is_demo: body.demo, model: body.demo ? "demo" : body.model || config.default_model, provider: body.provider };
}
function usePackage(result) {
  state.documents = result.documents;
  state.savedProject = false;
  state.isDemo = result.is_demo;
  state.versions = [];
  state.document = "cv";
  $("#generationInfo").textContent = result.is_demo ? tr("DEMO \xB7 Regelbasierte Vorlagen. Platzhalter selbst erg\xE4nzen.", "DEMO \xB7 Rule-based templates. Fill in placeholders yourself.") : `${PROVIDERS.find((p) => p.id === result.provider).name} \xB7 ${result.model}`;
  $("#projectTitle").value = job().company + " \xB7 " + job().title;
  showStep(4);
  renderDocument();
}
async function generate(demo) {
  validateInputs(!demo);
  await busy(tr(demo ? "Demo-Mappe wird erstellt \u2026" : "Deine Bewerbungsmappe entsteht \u2026", demo ? "Creating demo package \u2026" : "Creating your application package \u2026"), async () => {
    const result = await generatePayload(requestBody(demo));
    state.projectId = null;
    comparisonResults = [];
    $("#comparisonChoices").hidden = true;
    usePackage(result);
  });
}
async function comparePackages() {
  validateInputs(true);
  const second = $("#compareProvider").value;
  if (second === state.provider) throw new Error(tr("Zwei unterschiedliche Anbieter w\xE4hlen.", "Choose two different providers."));
  if (!state.keys[second]) throw new Error(tr("Bitte auch beim zweiten Anbieter einen API-Key hinterlegen.", "Enter an API key for the second provider too."));
  const body = requestBody(false);
  await busy(tr("Zwei Bewerbungsentw\xFCrfe entstehen \u2026", "Creating two application drafts \u2026"), async () => {
    const outcomes = await Promise.allSettled([generatePayload(body), generatePayload({ ...body, provider: second, model: state.models[second] || PROVIDERS.find((p) => p.id === second).default_model })]);
    comparisonResults = outcomes.filter((r) => r.status === "fulfilled").map((r) => r.value);
    if (!comparisonResults.length) throw new Error(outcomes.map((r) => r.reason.message).join(" "));
    state.projectId = null;
    const root = $("#comparisonChoices");
    root.replaceChildren();
    root.hidden = false;
    for (const result of comparisonResults) {
      const button = document.createElement("button");
      button.className = "button outline";
      button.textContent = PROVIDERS.find((p) => p.id === result.provider).name + " \xB7 " + result.model;
      button.addEventListener("click", () => {
        usePackage(result);
        notify(tr("Entwurf ausgew\xE4hlt. API-Anbieter zum Nachbearbeiten separat einstellen.", "Draft selected. Choose your revision provider in settings."));
      });
      root.append(button);
    }
    usePackage(comparisonResults[0]);
    const warnings = outcomes.filter((r) => r.status === "rejected").map((r) => r.reason.message);
    if (warnings.length) notify(warnings.join(" "), true);
    else notify(tr("Vergleiche Stil und Fakten. Es gibt keinen automatisch gew\xE4hlten Gewinner.", "Compare wording and facts. No winner is chosen automatically."));
  });
}
async function refine() {
  validateInputs(true);
  const instruction = $("#revision").value.trim();
  if (instruction.length < 2) throw new Error(tr("Bitte die gew\xFCnschte \xC4nderung eingeben.", "Enter your revision instruction."));
  await busy(tr("Dokument wird angepasst \u2026", "Revising document \u2026"), async () => {
    const body = { ...requestBody(false), document: state.document, current_content: state.documents[state.document], instruction };
    let content;
    if (BROWSER_ONLY) {
      content = (await callProvider(state.provider, state.keys[state.provider], applicationPrompt(body.language, state.document), [{ role: "user", content: JSON.stringify({ confirmed_profile: body.profile, job: body.job, current_draft: body.current_content, revision: instruction }) }], collectProvider())).content;
    } else {
      content = (await api("/api/package/refine", body)).content;
    }
    state.versions.push({ ...state.documents });
    state.documents[state.document] = content;
    state.isDemo = false;
    renderDocument();
    $("#revision").value = "";
  });
}
function exportBody(id) {
  return { content: state.documents[id], design: $("#design").value, format: $("#format").value, language: $("#outputLanguage").value, filename: $("#filename").value + "_" + id, photo: id === "cv" ? state.photo : null };
}
async function documentBlob(id) {
  const { exportDocument } = await import("./browser/export.js");
  return exportDocument(exportBody(id));
}
async function saveBlob(blob, filename) {
  if (window.Capacitor?.isNativePlatform?.()) {
    const { Filesystem, Directory } = await import("@capacitor/filesystem");
    const { Share } = await import("@capacitor/share");
    const bytes = await blob.arrayBuffer();
    const data = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(",")[1]);
      reader.onerror = reject;
      reader.readAsDataURL(new Blob([bytes]));
    });
    const file = await Filesystem.writeFile({ path: filename, data, directory: Directory.Cache });
    await Share.share({ title: filename, url: file.uri });
    usage(filename.endsWith(".project.json") ? "project.backup" : "document.export");
    return;
  }
  const url = URL.createObjectURL(blob), link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  usage(filename.endsWith(".project.json") ? "project.backup" : "document.export");
  setTimeout(() => URL.revokeObjectURL(url), 1e3);
}
async function download(all = false) {
  if (!state.documents) throw new Error("Keine Dokumente / no documents");
  await busy(tr("Download wird vorbereitet \u2026", "Preparing your download \u2026"), async () => {
    if (all) {
      const { zipSync, strToU8 } = await import("fflate");
      const files = {};
      for (const id of DOCUMENTS) {
        if (id === "email") {
          files["email.txt"] = strToU8(state.documents.email);
          continue;
        }
        const file = await documentBlob(id);
        files[file.filename] = new Uint8Array(await file.blob.arrayBuffer());
      }
      files["README.txt"] = strToU8(tr("Alle Angaben pr\xFCfen. E-Mail-Anh\xE4nge selbst hinzuf\xFCgen.", "Verify every detail. Add email attachments yourself."));
      await saveBlob(new Blob([zipSync(files)], { type: "application/zip" }), "Bewerbungsmappe.zip");
    } else {
      const file = await documentBlob(state.document);
      await saveBlob(file.blob, file.filename);
    }
  });
}
function projectData() {
  return { session_id: getSession().session_id, title: $("#projectTitle").value.trim() || "Bewerbung", status: $("#projectStatus").value, profile: readProfile(), job: job(), documents: state.documents, language: $("#outputLanguage").value, notes: $("#projectNotes").value };
}
function validateProject(value) {
  if (!value || typeof value !== "object" || !value.profile || typeof value.profile.source_text !== "string" || value.profile.source_text.length > 6e4 || !value.job || typeof value.job.description !== "string" || value.job.description.length > 2e4) throw new Error("Ung\xFCltige Projektdatei / invalid project file");
  const profile = { ...parseProfile("") };
  for (const key of Object.keys(profile)) {
    if (key === "confirmed") {
      profile[key] = value.profile[key] === true;
      continue;
    }
    if (typeof value.profile[key] === "string" && value.profile[key].length <= 6e4) profile[key] = value.profile[key];
  }
  const jobValue = {};
  for (const key of ["title", "company", "recipient", "email", "url", "description"]) jobValue[key] = typeof value.job[key] === "string" ? value.job[key].slice(0, key === "description" ? 2e4 : 2e3) : "";
  return { ...value, profile, job: jobValue, documents: validatePackage(value.documents) };
}
function openProject(raw, id = null) {
  const value = validateProject(raw);
  fillProfile(value.profile);
  fillJob(value.job);
  state.documents = value.documents;
  state.document = "cv";
  state.projectId = id;
  state.savedProject = true;
  state.versions = [];
  $("#outputLanguage").value = value.language === "en" ? "en" : "de";
  $("#projectTitle").value = value.title || "";
  $("#projectStatus").value = value.status || "draft";
  $("#projectNotes").value = value.notes || "";
  $("#generationInfo").textContent = tr("Gespeicherte Bewerbung \xB7 alle Angaben erneut pr\xFCfen.", "Saved application \xB7 verify all details again.");
  showStep(4);
  renderDocument();
}
function accountView() {
  $("#accountInfo").textContent = state.account ? state.account + " · " + tr("Deine gespeicherten Bewerbungen findest du unter „Meine Bewerbungen“, auch nach dem nächsten Anmelden.", "Find your saved applications under ‘My applications’, including after signing in again.") : BROWSER_ONLY ? tr("Konten und Cloud-Speicherung ben\xF6tigen den Server. Du kannst eine Projektdatei lokal herunterladen.", "Accounts and cloud storage require the server. You can download a local project file.") : tr("Dein Konto und gespeicherte Bewerbungen bleiben nach dem Abmelden erhalten. Bewahre den Wiederherstellungscode sicher auf.", "Your account and saved applications persist after sign-out. Keep your recovery code safe.");
  $("#accountForm").hidden = BROWSER_ONLY || !!state.account;
  $("#signedInActions").hidden = !state.account;
  $("#accountBtn").textContent = state.account ? tr("Mein Konto", "My account") : tr("Anmelden", "Sign in");
}
async function credentials(mode) {
  if (!$("#accountForm").reportValidity()) return;
  const body = { email: $("#accountEmail").value, password: $("#accountPassword").value };
  if (mode === "recover") body.recovery_code = $("#recoveryCode").value;
  const result = await api("/api/account/" + mode, body);
  $("#accountPassword").value = "";
  $("#recoveryCode").value = "";
  if (result.recovery_code) {
    $("#accountResult").textContent = tr("Wiederherstellungscode \u2014 jetzt sicher speichern. Er wird nur einmal angezeigt:\n", "Recovery code \u2014 save it securely now. It is shown only once:\n") + result.recovery_code;
  }
  if (result.email) {
    state.account = result.email;
    setLoginToken(result.access_token);
    await newSession(state.language);
    accountView();
  }
}
async function showProjects() {
  if (BROWSER_ONLY || !state.account) {
    $("#accountDialog").showModal();
    return;
  }
  const projects = await api("/api/projects");
  const root = $("#projectList");
  root.replaceChildren();
  if (!projects.length) root.textContent = tr("Noch keine gespeicherten Bewerbungen.", "No saved applications yet.");
  for (const project of projects) {
    const item = document.createElement("div");
    item.className = "project-item";
    const title = document.createElement("strong");
    title.textContent = project.title;
    const info = document.createElement("small");
    info.textContent = project.status + " \xB7 " + new Date(project.updated_at).toLocaleDateString();
    const row = document.createElement("div");
    row.className = "row";
    for (const type of ["open", "delete"]) {
      const button = document.createElement("button");
      button.className = "button " + (type === "open" ? "outline" : "quiet");
      button.textContent = type === "open" ? tr("\xD6ffnen", "Open") : tr("L\xF6schen", "Delete");
      button.addEventListener("click", action(async () => {
        if (type === "open") {
          openProject(await api("/api/projects/" + project.id), project.id);
          $("#projectsDialog").close();
        } else if (confirm(tr("Diese Bewerbung endg\xFCltig l\xF6schen?", "Permanently delete this application?"))) {
          await api("/api/projects/" + project.id, null, "DELETE");
          item.remove();
        }
      }));
      row.append(button);
    }
    item.append(title, info, row);
    root.append(item);
  }
  $("#projectsDialog").showModal();
}
function showInfo(title, text) {
  $("#infoTitle").textContent = title;
  const p = document.createElement("p");
  p.className = "legal-text";
  p.textContent = text;
  $("#infoContent").replaceChildren(p);
  $("#infoDialog").showModal();
}
function clearPersonalMemory() {
  $("#boostyAnswer").textContent = "";
  $("#boostyQuestion").value = "";
  $("#boostyAi").checked = false;
  state.keys = {};
  state.models = {};
  state.documents = null;
  state.photo = null;
  state.projectId = null;
  state.versions = [];
  state.savedProject = false;
  comparisonResults = [];
  fillProfile(parseProfile(""));
  fillJob({});
  for (const id of ["apiKey", "documentEditor", "wishes", "projectNotes", "projectTitle", "fileStatus", "jobImportStatus"]) {
    const field = $("#" + id);
    if ("value" in field) field.value = "";
    else field.textContent = "";
  }
  for (const id of ["preview", "projectList", "comparisonChoices"]) $("#" + id).replaceChildren();
  $("#comparisonChoices").hidden = true;
  $("#aiConsent").checked = false;
  providerView();
  showStep(1);
}
async function deleteData() {
  if (!confirm(tr("Diese Sitzung und die aktuell ge\xF6ffneten Daten l\xF6schen? Gespeicherte Bewerbungen dieser Sitzung werden ebenfalls gel\xF6scht.", "Delete this session and its open data? Saved applications in this session will also be deleted."))) return;
  if (!BROWSER_ONLY && getSession().session_id) await api("/api/session/" + getSession().session_id, null, "DELETE");
  state.keys = {};
  state.models = {};
  state.documents = null;
  state.photo = null;
  state.projectId = null;
  state.versions = [];
  fillProfile(parseProfile(""));
  fillJob({});
  $("#apiKey").value = "";
  $("#aiConsent").checked = false;
  await newSession(state.language);
  showStep(1);
  notify(tr("Sitzungsdaten gel\xF6scht.", "Session data deleted."));
}
async function scanPhoto(file) {
  if (!file) return;
  if (file.size > 10 * 1024 * 1024) throw new Error("Foto max. 10 MB / photo max. 10 MB");
  await busy(tr("Scan wird lokal erkannt \u2026", "Recognizing scan locally \u2026"), async () => {
    const { recognizeImage } = await import("./core/ocr.js");
    const text = await recognizeImage(file, $("#outputLanguage").value, (message) => {
      if (message.status === "recognizing text") $("#busyTitle").textContent = tr("Texterkennung: ", "Text recognition: ") + Math.round(message.progress * 100) + "%";
    });
    fillProfile(parseProfile(text));
    $("#fileStatus").textContent = tr("OCR-Ergebnis: bitte jeden Namen, jede Zahl und jedes Datum pr\xFCfen.", "OCR result: verify every name, number and date.");
    showStep(1);
  });
}
async function init() {
  document.title = branding.name + " \u2013 " + tr("Lebenslauf und Bewerbung mit KI", "AI resume and application builder");
  $("#brandName").textContent = branding.name;
  $(".brand-footer").textContent = branding.name;
  for (const [key, value] of Object.entries(labels)) {
    const label = document.createElement("label");
    label.className = "field" + (["experience", "education", "skills", "languages"].includes(key) ? " wide" : "");
    const span = document.createElement("span");
    span.textContent = value[0];
    const input = document.createElement(["experience", "education", "skills", "languages"].includes(key) ? "textarea" : "input");
    input.id = "profile-" + key;
    input.maxLength = key === "experience" ? 12e3 : ["education", "skills"].includes(key) ? 6e3 : key === "languages" ? 1e3 : 300;
    if (input.tagName === "TEXTAREA") input.rows = 3;
    else input.type = key === "email" ? "email" : "text";
    input.addEventListener("input", () => $("#confirmed").checked = false);
    label.append(span, input);
    $("#profileFields").append(label);
  }
  $("#outputLanguage").value = state.language;
  for (const provider of PROVIDERS) {
    const option = document.createElement("option");
    option.value = provider.id;
    option.textContent = provider.name;
    $("#provider").append(option);
    const second = option.cloneNode(true);
    $("#compareProvider").append(second);
  }
  $("#compareProvider").value = "claude";
  providerView();
  applyLanguage();
  window.addEventListener("sharedJob", (event) => {
    if (typeof event.detail?.url === "string") {
      $("#jobUrl").value = event.detail.url;
      showStep(2);
    }
  });
  $("#language").addEventListener("click", () => {
    state.language = state.language === "de" ? "en" : "de";
    applyLanguage();
  });
  $("#provider").addEventListener("change", () => {
    collectProvider();
    state.provider = $("#provider").value;
    providerView();
  });
  $("#apiKey").addEventListener("input", () => {
    $("#keyStatus").textContent = "";
  });
  $("#model").addEventListener("input", () => {
    $("#keyStatus").textContent = "";
  });
  $("#azureEndpoint").addEventListener("input", () => {
    $("#keyStatus").textContent = "";
  });
  $("#keyEye").addEventListener("click", () => $("#apiKey").type = $("#apiKey").type === "password" ? "text" : "password");
  $("#steps").addEventListener("click", (event) => {
    const button = event.target.closest("[data-step]");
    if (button) showStep(Number(button.dataset.step));
  });
  $$("[data-next]").forEach((button) => button.addEventListener("click", action(() => {
    if (Number(button.dataset.next) === 2 && (!readProfile().confirmed || readProfile().source_text.length < 10)) throw new Error(tr("Profil importieren und Angaben best\xE4tigen.", "Import and confirm your profile."));
    showStep(Number(button.dataset.next));
  })));
  $("#cvFile").addEventListener("change", action((event) => importResume(event.target.files[0])));
  $("#dropzone").addEventListener("dragover", (event) => {
    event.preventDefault();
    $("#dropzone").classList.add("dragging");
  });
  $("#dropzone").addEventListener("dragleave", () => $("#dropzone").classList.remove("dragging"));
  $("#dropzone").addEventListener("drop", action((event) => {
    event.preventDefault();
    $("#dropzone").classList.remove("dragging");
    return importResume(event.dataTransfer.files[0]);
  }));
  $("#source").addEventListener("input", () => $("#confirmed").checked = false);
  $("#parseProfile").addEventListener("click", action(() => {
    if ($("#source").value.trim().length < 10) throw new Error(tr("Bitte zuerst Text eingeben.", "Please enter text first."));
    fillProfile(parseProfile($("#source").value));
    notify(tr("Erkannte Angaben pr\xFCfen; fehlende Felder erg\xE4nzen.", "Verify extracted details; fill in missing fields."));
  }));
  $("#example").addEventListener("click", () => {
    fillProfile(parseProfile(SAMPLE[state.language].cv));
    fillJob({ description: SAMPLE[state.language].job, title: "Frontend Developer", company: "Example Company" });
    $("#outputLanguage").value = state.language;
    showStep(1);
    $("#workspace").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    notify(tr("Beispiel geladen. Pr\xFCfe und best\xE4tige die Angaben.", "Example loaded. Verify and confirm the details."));
  });
  $("#importJob").addEventListener("click", action(async () => {
    if (BROWSER_ONLY) throw new Error(tr("Stellenlink-Import ben\xF6tigt den Server. Kopiere die Beschreibung in das Textfeld.", "Job URL import requires server mode. Paste the description into the text field."));
    const result = await busy(tr("Stellenanzeige wird gelesen \u2026", "Reading job posting \u2026"), () => api("/api/job/import", { url: $("#jobUrl").value.trim() }));
    fillJob({ ...job(), ...result });
    $("#jobImportStatus").textContent = tr("Importiert. Pr\xFCfe Position, Firma und Stellentext.", "Imported. Verify role, company and job text.") + (result.truncated ? tr(" Text wurde auf 20.000 Zeichen begrenzt.", " Text was limited to 20,000 characters.") : "");
  }));
  $("#checkKey").addEventListener("click", action(async () => {
    const options = collectProvider(), key = state.keys[state.provider];
    if (!key) throw new Error("API-Key fehlt / missing API key");
    await busy(tr("API-Zugriff wird gepr\xFCft \u2026", "Testing API access \u2026"), async () => {
      if (BROWSER_ONLY) await callProvider(state.provider, key, "Return only OK.", [{ role: "user", content: "Connection test. Return OK." }], options);
      else await api("/api/provider/test", { ...options, keys: keysBody() });
      $("#keyStatus").textContent = tr("\u2713 Zugriff erfolgreich gepr\xFCft.", "\u2713 Access verified successfully.");
    });
  }));
  $("#generate").addEventListener("click", action(() => generate(false)));
  $("#demo").addEventListener("click", action(() => generate(true)));
  $("#refine").addEventListener("click", action(refine));
  $("#compare").addEventListener("click", action(comparePackages));
  $("#undo").addEventListener("click", () => {
    if (state.versions.length) {
      state.documents = state.versions.pop();
      renderDocument();
    } else notify(tr("Noch keine vorherige KI-Version.", "No earlier AI version yet."));
  });
  $("#documentTabs").addEventListener("click", (event) => {
    const button = event.target.closest("[data-document]");
    if (button) {
      state.document = button.dataset.document;
      renderDocument();
    }
  });
  $("#documentTabs").addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    let index = DOCUMENTS.indexOf(state.document);
    index = event.key === "Home" ? 0 : event.key === "End" ? 3 : (index + (event.key === "ArrowRight" ? 1 : -1) + 4) % 4;
    state.document = DOCUMENTS[index];
    renderDocument();
    $("#tab-" + state.document).focus();
  });
  $("#documentEditor").addEventListener("input", (event) => {
    state.documents[state.document] = event.target.value;
    renderPreview();
    renderQuality();
  });
  $("#download").addEventListener("click", action(() => download(false)));
  $("#downloadPackage").addEventListener("click", action(() => download(true)));
  $("#photo").addEventListener("change", action(async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    if (!/^image\/(jpeg|png|webp)$/.test(file.type) || file.size > 5 * 1024 * 1024) throw new Error("Foto: PNG/JPEG/WebP, max. 5 MB");
    state.photo = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
    renderPreview();
  }));
  $("#removePhoto").addEventListener("click", () => {
    state.photo = null;
    $("#photo").value = "";
    renderPreview();
  });
  $("#copyEmail").addEventListener("click", action(async () => {
    await navigator.clipboard.writeText(state.documents.email);
    notify(tr("E-Mail-Text kopiert.", "Email text copied."));
  }));
  $("#openEmail").addEventListener("click", action(() => {
    const email = job().email;
    if (email && !/^[^\s@?&]+@[^\s@?&]+\.[^\s@?&]+$/.test(email)) throw new Error("Empf\xE4ngeradresse pr\xFCfen / check recipient");
    const lines = state.documents.email.split("\n"), subject = lines[0].replace(/^(?:Subject|Betreff):\s*/i, "");
    const value = `mailto:${encodeURIComponent(email)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(lines.slice(1).join("\n").trim())}`;
    if (value.length > 16e3) throw new Error(tr("E-Mail zu lang. Bitte kopieren.", "Email too long. Copy the text instead."));
    location.href = value;
  }));
  $("#backupProject").addEventListener("click", action(() => saveBlob(new Blob([JSON.stringify(projectData(), null, 2)], { type: "application/json" }), "Bewerbung.project.json")));
  $("#projectFile").addEventListener("change", action(async (event) => {
    const file = event.target.files[0];
    if (file.size > 5e5) throw new Error("Projektdatei zu gro\xDF / project file too large");
    let value;
    try {
      value = JSON.parse(await file.text());
    } catch {
      throw new Error("Ung\xFCltige JSON-Datei / invalid JSON file");
    }
    openProject(value);
    event.target.value = "";
  }));
  $("#saveProject").addEventListener("click", action(async () => {
    if (!state.account) {
      $("#accountDialog").showModal();
      return;
    }
    const result = await api(state.projectId ? "/api/projects/" + state.projectId : "/api/projects", projectData(), state.projectId ? "PUT" : "POST");
    state.projectId = result.id;
    notify(tr("Bewerbung gespeichert.", "Application saved."));
  }));
  $("#projectsBtn").addEventListener("click", action(showProjects));
  $("#accountBtn").addEventListener("click", () => $("#accountDialog").showModal());
  $("#accountForm").addEventListener("submit", action((event) => {
    event.preventDefault();
    return credentials("login");
  }));
  $("#register").addEventListener("click", action(() => credentials("register")));
  $("#recover").addEventListener("click", action(() => credentials("recover")));
  $("#logout").addEventListener("click", action(async () => {
    await api("/api/account/logout", {});
    setLoginToken("");
    state.account = null;
    clearPersonalMemory();
    await newSession(state.language);
    $("#accountResult").textContent = "";
    accountView();
    notify(tr("Abgemeldet. Gespeicherte Bewerbungen bleiben in deinem Konto erhalten.", "Signed out. Saved applications remain in your account."));
  }));
  $("#deleteAccount").addEventListener("click", action(async () => {
    if (!confirm(tr("Konto und alle Bewerbungen endg\xFCltig l\xF6schen?", "Permanently delete your account and every application?"))) return;
    await api("/api/account", null, "DELETE");
    setLoginToken("");
    state.account = null;
    clearPersonalMemory();
    $("#accountDialog").close();
    accountView();
    await newSession(state.language);
    notify(tr("Konto gel\xF6scht.", "Account deleted."));
  }));
  $$("[data-close]").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));
  $("#clearData").addEventListener("click", action(deleteData));
  $("#helpBtn").addEventListener("click", () => {
    $("#boostyAnswer").textContent = boostyAnswer("start", state.language).content;
    $("#boostyDialog").showModal();
  });
  $("#boostyNext").addEventListener("click", () => guideTo((tourIndex + 1) % TOUR.length));
  $("#boostyForm").addEventListener("submit", askBoosty);
  $$("[data-boosty]").forEach(button => button.addEventListener("click", () => {
    $("#boostyAnswer").textContent = boostyAnswer(button.dataset.boosty, state.language).content;
  }));
  $("#adminLink").addEventListener("click", (event) => {
    event.preventDefault();
    embeddedAdmin?.clear();
    embeddedAdmin = mountAdmin($("#embeddedAdmin"));
    $("#adminDialog").showModal();
  });
  $("#adminDialog").addEventListener("close", () => embeddedAdmin?.clear());
  $("#privacyBtn").addEventListener("click", action(async () => {
    const info = BROWSER_ONLY ? branding.operator : await api("/api/public-config");
    showInfo(tr("Datenschutz", "Privacy"), $("#privacyExplanation").textContent + "\n\n" + tr("Verantwortlicher: ", "Controller: ") + info.operator_name + "\n" + info.operator_address + "\n" + info.operator_email + "\n\n" + tr("Konten speichern deine E-Mail-Adresse und einen geschützten Passwort-Hash. Bewerbungen werden auf deinen Wunsch gespeichert und bleiben bis zur Löschung erhalten. Anonyme Uploads werden nach ", "Accounts store your email and a protected password hash. Applications are saved when you choose and remain until deleted. Anonymous uploads are removed after ") + (info.retention_days || 30) + tr(" Tagen bereinigt. Keine Werbe-Tracker oder gespeicherten API-Keys. Keine persönlichen Daten im Service-Worker-Cache. Exporte auf deinem Gerät und Daten beim KI-Anbieter werden durch eine Kontolöschung nicht entfernt. Der Betreiber kann für Support und Verwaltung auf gespeicherte Inhalte zugreifen; Admin-Zugriffe werden protokolliert. Nutzungsereignisse (Konto, Zeitpunkt, Funktion, Erfolg/Fehler) bleiben 30 Tage, Admin-Protokolle und tägliche Summen 90 Tage. Keine IP-Adressen, Frage- oder Dokumenttexte in der Statistik. Bei Kontolöschung wird die Kontozuordnung der Nutzungsereignisse entfernt. Details zu Hosting und Anbietervereinbarungen müssen vor dem öffentlichen Start ergänzt werden.", " days. No advertising trackers or stored API keys. Personal data is never cached by the service worker. Deleting an account does not remove exports on your device or data at AI providers. The operator can access stored content for support and administration; admin access is audited. Usage metadata (account, time, function, result) remains for 30 days, admin audit logs and daily totals for 90 days. Analytics excludes IP addresses, questions and document text. Account deletion removes its association with usage events. Hosting and provider agreements must be documented before public launch."));
  }));
  $("#legalBtn").addEventListener("click", action(async () => {
    const info = BROWSER_ONLY ? branding.operator : await api("/api/public-config");
    showInfo(tr("Impressum", "Legal notice"), info.operator_name ? `${info.operator_name}
${info.operator_address}
${info.operator_email}` : tr("Betreiberangaben noch nicht hinterlegt. Vor \xF6ffentlichem Betrieb m\xFCssen Name, ladungsf\xE4hige Anschrift und Kontakt erg\xE4nzt werden.", "Operator details are not configured. Before public launch, add the legal operator name, postal address and contact."));
  }));
  window.addEventListener("beforeunload", (event) => {
    if (readProfile().source_text || state.documents) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPrompt = event;
    $("#installBtn").hidden = false;
  });
  $("#installBtn").addEventListener("click", action(async () => {
    if (installPrompt) {
      await installPrompt.prompt();
      installPrompt = null;
      $("#installBtn").hidden = true;
    }
  }));
  if ("serviceWorker" in navigator && !window.Capacitor?.isNativePlatform?.()) navigator.serviceWorker.register(new URL("sw.js", baseURL()), { scope: baseURL().pathname }).catch(() => {
  });
  const scanButton = document.createElement("button");
  scanButton.className = "button outline";
  scanButton.dataset.de = "Foto / Scan einlesen (lokale OCR)";
  scanButton.dataset.en = "Read photo / scan (local OCR)";
  scanButton.textContent = tr(scanButton.dataset.de, scanButton.dataset.en);
  const scanInput = document.createElement("input");
  scanInput.type = "file";
  scanInput.accept = "image/png,image/jpeg,image/webp";
  scanInput.hidden = true;
  scanInput.id = "scanInput";
  scanInput.addEventListener("change", action((event) => scanPhoto(event.target.files[0])));
  scanButton.addEventListener("click", action(async () => {
    if (window.Capacitor?.isNativePlatform?.()) {
      const { Camera, CameraResultType, CameraSource } = await import("@capacitor/camera");
      const image = await Camera.getPhoto({ resultType: CameraResultType.Uri, source: CameraSource.Prompt, quality: 90, width: 2400, saveToGallery: false });
      await scanPhoto(await (await fetch(image.webPath)).blob());
    } else scanInput.click();
  }));
  $("#parseProfile").parentElement.append(scanButton, scanInput);
  if (window.Capacitor?.isNativePlatform?.()) {
    const { App } = await import("@capacitor/app");
    const openJob = (event) => {
      try {
        const url = new URL(event.url), jobUrl = url.searchParams.get("jobUrl");
        if (jobUrl) {
          $("#jobUrl").value = jobUrl;
          showStep(2);
        }
      } catch {
      }
    };
    App.addListener("appUrlOpen", openJob);
    const launchUrl = await App.getLaunchUrl();
    if (launchUrl) openJob(launchUrl);
    App.addListener("backButton", () => {
      const dialog = $$("dialog").find((d) => d.open);
      if (dialog) dialog.close();
      else if (state.step > 1) showStep(state.step - 1);
    });
  }
  await newSession(state.language);
  if (!BROWSER_ONLY) {
    const result = await api("/api/account");
    state.account = result.email;
    accountView();
  }
  const params = new URLSearchParams(location.search);
  if (params.has("jobUrl")) {
    $("#jobUrl").value = params.get("jobUrl");
    showStep(2);
  }
}
init().catch((error) => notify(error.message, true));
