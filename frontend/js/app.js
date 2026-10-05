import { DESIGNS, designFor } from "./core/document-designs.js";
import { parseLines } from "./browser/export.js";
import { jobDetails } from "./core/job.js";
import { LANGUAGES, translate } from "./core/locale.js";
import { DOCUMENTS, parseProfile, profileSource, applicationPrompt, demoPackage, validatePackage, assessPackage } from "./core/application.js";
import { API_BASE, BROWSER_ONLY, api, newSession, getSession, setLoginToken } from "./core/client.js";
import { SAMPLE } from "./browser/demo.js";
import { readDocument } from "./browser/import.js";
import branding from "../../static/branding.json" with { type: "json" };
import { TOUR, GUIDES, helpForTopic, boostyAnswer, questionContainsSecret } from "./core/boosty.js";
import { mountAdmin } from "./admin.js";
const $ = (selector) => document.querySelector(selector), $$ = (selector) => [...document.querySelectorAll(selector)];
const labels = { name: ["Name", "Name"], email: ["E-Mail", "Email"], phone: ["Telefon", "Phone"], location: ["Ort / Adresse", "Location / address"], headline: ["Berufliche \xDCberschrift", "Professional headline"], experience: ["Berufserfahrung (Korrekturen / Erg\xE4nzungen)", "Experience (corrections / additions)"], education: ["Ausbildung", "Education"], skills: ["Kenntnisse", "Skills"], languages: ["Sprachen", "Languages"] };
const docLabels = { cv: ["Lebenslauf", "Resume"], cover_letter: ["Anschreiben", "Cover letter"], motivation_letter: ["Motivation", "Motivation"], email: ["E-Mail", "Email"] };
const state = { language: LANGUAGES.includes(new URLSearchParams(location.search).get("lang")) ? new URLSearchParams(location.search).get("lang") : "de", profile: parseProfile(""), documents: null, document: "cv", photo: null, keys: {}, models: {}, provider: "openai", step: 1, isDemo: true, projectId: null, account: null, analysis: null, versions: [] };
const tr = (de, en, sq) => translate(state.language, de, en, sq);
let toastTimer, installPrompt, editorMode = false, accountMode="login", accountBusy=false, studioEntered=false;
let comparisonResults = [];
let tourIndex = 0, tourTarget, tourActive = false, embeddedAdmin;
let chatEpoch = 0, chatPending = false;
let saveTimer, saveEpoch = 0, saveChain = Promise.resolve(), saveDirty = false, savePaused=false, generationPending=false;
let boostyConfig = {enabled:false}, boostyTopic="start", guideFrame;
function usage(event) {
  if (!BROWSER_ONLY) api("/api/usage", { session_id: getSession().session_id, event }).catch(() => {});
}
function boostyTip() {
  const tip = TOUR[tourIndex];
  $("#launcherTip").textContent = studioEntered ? tr(...labelsForStep(state.step)) : tr("Dein Start","Get started","Fillo këtu");
  $("#boostyTip").textContent = tip[state.language];
}
function labelsForStep(step) {
  return ({1:["Dein Profil","Your profile","Profili yt"],2:["Deine Stelle","Your opportunity","Vendi yt i punës"],3:["Prüfen & erstellen","Review & create","Kontrollo & krijo"],4:["Deine Mappe","Your application","Dosja jote"]})[step];
}
function enterStudio({guide=true}={}) {
  if(!state.account){openAccount();return;}
  studioEntered=true;
  document.body.dataset.view="studio";
  $("#how").hidden=true;
  $("#workspace").hidden=false;
  $$("[data-studio]").forEach(el=>el.hidden=false);
  window.scrollTo({top:0,behavior:"instant"});
  $("#workspaceTitle").focus({preventScroll:true});
  boostyTip();
  if(guide)followStep();
  scheduleGuide();
}
function returnWelcome() {
  studioEntered=false;
  stopGuide();
  document.body.dataset.view="welcome";
  $("#how").hidden=false;
  $("#workspace").hidden=true;
  $$("[data-studio]").forEach(el=>el.hidden=true);
  $("#accountDialog").close();
  window.scrollTo({top:0,behavior:"instant"});
  $("#welcomeLogin").focus({preventScroll:true});
  boostyTip();
  scheduleGuide();
}
function followStep() {
  if (!studioEntered || !$("#followBoosty").checked) return;
  const tip=TOUR[[0,0,3,5,7][state.step]];
  tourIndex=TOUR.indexOf(tip);tourTarget?.classList.remove("boosty-tour-target");
  tourTarget=$(tip.target);tourActive=true;
  delete $("#guideText").dataset.topic;
  $("#guideText").textContent=tip[state.language];
  $("#boostyGuide").hidden=false;
  $("#boostyGuide").classList.remove("arriving");
  requestAnimationFrame(()=>$("#boostyGuide").classList.add("arriving"));
  boostyTip();scheduleGuide();
}
function guideTo(index) {
  tourTarget?.classList.remove("boosty-tour-target");
  const tip = TOUR[index];
  if (tip.step === 4 && !state.documents) {
    notify(tr("Erstelle zuerst deine Bewerbungsmappe. Danach begleite ich dich zum Export.", "Create your application first. Then I can guide you to export."));
    return;
  }
  showStep(tip.step);
  tourIndex = index;
  tourActive = true;
  tourTarget = $(tip.target);
  tourTarget?.classList.add("boosty-tour-target");
  tourTarget?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "center" });
  boostyTip();
  delete $("#guideText").dataset.topic;
  $("#guideText").textContent = tip[state.language];
  $("#boostyGuide").hidden = false;
  scheduleGuide();
}
function chatMessage(role, content) {
  const root = $("#boostyAnswer"), message = document.createElement("article");
  message.className = "chat-message " + role;
  const label = document.createElement("strong");
  label.textContent = role === "user" ? tr("Du", "You", "Ti") : "Boosty";
  const text = document.createElement("p"); text.textContent = content;
  message.append(label,text); root.append(message);
  while (root.children.length > 60) root.firstElementChild.remove();
  root.scrollTop = root.scrollHeight;
  return {message,text};
}
function setBoostyAnswer(value, target = null) {
  boostyTopic = value.topic;
  const bubble = target || chatMessage("assistant", "");
  bubble.message.classList.remove("pending");
  bubble.text.textContent = value.content;
  if (GUIDES[value.topic] !== undefined || ["admin","privacy"].includes(value.topic)) {
    const button = document.createElement("button"); button.type="button"; button.className="text-button";
    button.textContent=tr("Zeig mir die Stelle →","Show me where →","Më trego ku →");
    button.addEventListener("click",()=>{boostyTopic=value.topic;showBoostyTarget();});
    bubble.message.append(button);
  }
  $("#boostyShow").hidden = true;
  $("#chatAnnouncement").textContent=value.content;
  $("#boostyAnswer").scrollTop=$("#boostyAnswer").scrollHeight;
}

function showBoostyTarget() {
  $("#boostyDialog").close();
  if(!studioEntered && !["admin","privacy","save"].includes(boostyTopic)) {
    notify(tr("Erstelle zuerst ein Konto oder logge dich ein.","Create an account or sign in first.","Krijo llogari ose hyr fillimisht."));
    $("#welcomeLogin").focus();return;
  }
  if(!studioEntered && boostyTopic==="admin") {notify(helpForTopic("admin",state.language).content);return;}
  if (boostyTopic === "admin" || boostyTopic === "privacy" || boostyTopic === "save") {
    stopGuide();
    tourTarget = $(boostyTopic === "admin" ? "#adminLink" : boostyTopic === "save" ? (state.account?"#projectsBtn":studioEntered?"#accountBtn":"#welcomeLogin") : "#privacyBtn");
    tourTarget.classList.add("boosty-tour-target");
    tourActive = true;
    $("#guideText").dataset.topic=boostyTopic;
    $("#guideText").textContent = helpForTopic(boostyTopic,state.language).content;
    $("#boostyGuide").hidden = false;
    tourTarget.scrollIntoView({behavior:"smooth",block:"center"});
    scheduleGuide();
  } else {
    guideTo(GUIDES[boostyTopic]);
    if (boostyTopic==="language" || (state.documents && ["quality","documents"].includes(boostyTopic))) {
      tourTarget?.classList.remove("boosty-tour-target");
      tourTarget=$(boostyTopic==="language"?"#outputLanguage":boostyTopic==="quality"?"#quality":"#documentTabs");
      tourTarget?.classList.add("boosty-tour-target");
      $("#guideText").dataset.topic=boostyTopic;
      $("#guideText").textContent=helpForTopic(boostyTopic,state.language).content;
      tourTarget?.scrollIntoView({behavior:"smooth",block:"center"});
      scheduleGuide();
    }
  }
}
async function askBoosty(event) {
  event.preventDefault();
  const question = $("#boostyQuestion").value.trim();
  if (!question || chatPending) return;
  if (question.length > 2000) return;
  chatPending = true;
  const epoch = chatEpoch, language = state.language;
  const submit = $("#boostyForm button"); submit.disabled = true;
  chatMessage("user",question); $("#boostyQuestion").value="";
  const bubble=chatMessage("assistant",tr("Ich schaue nach …","Let me check …","Po kontrolloj …"));
  bubble.message.classList.add("pending");
  try {
    let value=boostyAnswer(question,language);
    // Credentials never belong in a help request, including accidental pastes.
    if (questionContainsSecret(question)) {
      value=helpForTopic("privacy",language);
    } else if (state.account && boostyConfig.enabled) {
      try {
        const result=await api("/api/assistant",{session_id:getSession().session_id,question,language,consent:true});
        value=helpForTopic(result.topic,language);
      } catch {
        value={...value,content:tr("Die KI-Hilfe ist gerade nicht erreichbar. Hier ist meine lokale Hilfe:\n\n","AI help is currently unavailable. Here is my local help:\n\n","Ndihma IA nuk është e arritshme. Ja ndihma lokale:\n\n")+value.content};
      }
    }
    if (epoch !== chatEpoch) return;
    setBoostyAnswer(value,bubble);
  } finally {
    if (epoch === chatEpoch) {chatPending=false;submit.disabled=false;$("#boostyQuestion").focus();}
  }
}

function stopGuide() {
  tourTarget?.classList.remove("boosty-tour-target");
  tourActive = false;
  $("#boostyGuide").hidden = true;
  $("#boostyPointer").setAttribute("hidden","");
}
function placeLauncher() {
  const launcher=$("#boostyLauncher"),workspace=$("#workspace").getBoundingClientRect(),compact=studioEntered && workspace.top<220;
  launcher.classList.toggle("compact",compact);
  launcher.hidden=false;
  if(!compact){launcher.style.top="";launcher.style.left="";launcher.style.bottom="";launcher.style.right="";return;}
  const size=64,gap=8,preferred=innerHeight-size-16;
  const controls=$$("input,textarea,select,button,a,.field,#preview,#quality,h1,h2,h3,.boosty-guide").filter(el=>el!==launcher&&!launcher.contains(el)).map(el=>el.getBoundingClientRect()).filter(r=>r.width&&r.height);
  for(const x of [innerWidth-size-gap,gap])for(const y of [preferred,...Array.from({length:Math.max(0,Math.floor((innerHeight-size-gap)/24))},(_,i)=>gap+i*24)]) {
    if(controls.some(r=>x<r.right+4&&x+size>r.left-4&&y<r.bottom+4&&y+size>r.top-4))continue;
    launcher.style.left=x+"px";launcher.style.top=y+"px";launcher.style.right="auto";launcher.style.bottom="auto";return;
  }
  // On very small screens the inline companion still offers a chat button.
  launcher.hidden=true;
}

function scheduleGuide() {
  placeLauncher();
  placeGuide();
  cancelAnimationFrame(guideFrame);
  guideFrame = requestAnimationFrame(placeGuide);
}
function placeGuide() {
  if (!tourActive || !tourTarget) return;
  const guide=$("#boostyGuide"), gap=16;
  let r=tourTarget.getBoundingClientRect();
  const area=tourTarget.closest(".studio-content")?.getBoundingClientRect() || r;
  const width=290,height=Math.max(260,guide.offsetHeight || 180);
  const positions=[];
  const right=area.right+gap,left=area.left-width-gap;
  for(const x of [right,left]) {
    if(x<gap || x+width>innerWidth-gap)continue;
    const desired=Math.max(gap,Math.min(innerHeight-height-gap,r.top));
    const controls=$$("button,input,textarea,select,a,#preview").filter(el=>!guide.contains(el) && !el.hidden).map(el=>el.getBoundingClientRect()).filter(rect=>rect.width && rect.height);
    for(const y of [desired,...Array.from({length:Math.max(0,Math.floor((innerHeight-height-gap)/24))},(_,i)=>gap+i*24)]) {
      if(!controls.some(rect=>x<rect.right+4 && x+width>rect.left-4 && y<rect.bottom+4 && y+height>rect.top-4)){positions.push({x,y,distance:Math.abs(y-desired)});break;}
    }
  }
  const panel=tourTarget.closest("[data-panel]");
  if((innerWidth<900 || !positions.length) && panel) {
    let anchor=tourTarget;
    while(anchor.parentElement!==panel)anchor=anchor.parentElement;
    guide.classList.add("inline-guide");
    if(guide.parentElement!==panel || guide.nextElementSibling!==anchor)panel.insertBefore(guide,anchor);
    guide.style.left="";guide.style.top="";
    $("#boostyPointer").setAttribute("hidden","");return;
  }
  guide.classList.remove("inline-guide");
  if(guide.parentElement!==document.body)document.body.append(guide);
  r=tourTarget.getBoundingClientRect();
  if (!r.width || !r.height) {stopGuide();return;}
  const position=positions.sort((a,b)=>a.distance-b.distance)[0] || {x:gap,y:gap};
  guide.style.left=position.x+"px";guide.style.top=position.y+"px";
  const line=$("#boostyLine"),endX=Math.max(gap,Math.min(innerWidth-gap,r.left+(tourTarget.id==="dropzone"?r.width/2:Math.min(r.width/2,70)))),endY=Math.max(gap,Math.min(innerHeight-gap,r.top+Math.min(r.height/2,36)));
  line.setAttribute("x1",String(position.x+42));line.setAttribute("y1",String(position.y+54));line.setAttribute("x2",String(endX));line.setAttribute("y2",String(endY));
  $("#boostyPointer").removeAttribute("hidden");

}
function notify(message, error = false) {
  $("#status").textContent = message;
  $("#status").classList.toggle("error", error);
  $("#status").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("#status").hidden = true, error ? 15e3 : 6500);
}
const waitingFacts = [
 ["Ein klar gegliederter Lebenslauf hilft Menschen und Recruiting-Systemen beim Lesen.", "A clearly structured resume helps people and recruiting systems read it."],
 ["Nutze konkrete Beispiele aus deiner Erfahrung. Ergänze nur Fähigkeiten, die du belegen kannst.", "Use concrete examples from your experience. Add only skills you can substantiate."],
 ["Ein gutes Motivationsschreiben erklärt, warum dich die konkreten Aufgaben interessieren.", "A good motivation letter explains why the specific tasks interest you."],
 ["Prüfe vor dem Versand Namen, Kontaktdaten und die Anhänge deiner E-Mail.", "Check names, contact details and email attachments before sending."],
 ["Keyword-Abdeckung misst Wortüberschneidungen. Sie garantiert keine Einladung.", "Keyword coverage measures word overlap. It does not guarantee an interview."]
];
async function busy(label, work, stages = false) {
  const previousPause=savePaused;savePaused=true;clearTimeout(saveTimer);
  $("#busyTitle").textContent = label;
  $("#busy").hidden = false;
  $("#workspace").setAttribute("aria-busy", "true");
  const blocked = $$("main, header, footer, #boostyLauncher, #boostyGuide").map(el => [el, el.inert]);
  blocked.forEach(([el]) => el.inert = true);
  const report = (percent, phase) => {
    $("#busyProgress").value = percent;
    $("#busyPercent").textContent = `${percent}% ` + tr("der Arbeitsschritte abgeschlossen", "of workflow stages completed");
    $("#busyPhase").textContent = phase;
  };
  let index = 0;
  const fact = () => $("#busyFact").textContent = tr(...waitingFacts[index++ % waitingFacts.length]);
  if (stages) {
    report(25, tr("Angaben geprüft · Anfrage läuft", "Inputs checked · Request in progress"));
    $("#busyExplanation").textContent = tr("Fortschritt der Arbeitsschritte. Die Dauer einer KI-Anfrage lässt sich nicht vorhersagen.", "Completed workflow stages. AI request duration cannot be predicted.");
  } else {
    $("#busyProgress").removeAttribute("value");
    $("#busyPercent").textContent = tr("Boosty arbeitet für dich …", "Boosty is working for you …", "Boosty po punon për ty …");
    $("#busyPhase").textContent = "";
    $("#busyExplanation").textContent = tr("Bitte einen Moment warten. Die Dauer hängt von deinem Anbieter ab.", "Please wait. Timing depends on your provider.");
  }
  fact();
  const timer = setInterval(fact, 7000);
  try {
    await new Promise(requestAnimationFrame);
    const result = await work(report);
    report(100, tr("Fertig", "Complete"));
    return result;
  } finally {
    clearInterval(timer);
    blocked.forEach(([el, previous]) => el.inert = previous);
    $("#busy").hidden = true;
    $("#workspace").removeAttribute("aria-busy");
    savePaused=previousPause;if(!savePaused&&saveDirty)scheduleSave();
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
function editorView() {
  $(".editor-grid").classList.toggle("editor-mode",editorMode);
  $("#toggleEditor").textContent = editorMode ? tr("Vorschau zeigen", "Show preview", "Shfaq parapamjen") : tr("Text bearbeiten", "Edit text", "Redakto tekstin");
  $("#toggleEditor").setAttribute("aria-pressed", String(editorMode));
}
function boostyConnectionView() {
  $("#boostyConnection").textContent=boostyConfig.enabled ? tr("OpenAI-Softwarehilfe bereit", "OpenAI software help ready", "Ndihma OpenAI gati") : tr("Lokale Hilfe bereit · OpenAI-Hilfe wird vom Betreiber aktiviert", "Local help ready · Operator activates OpenAI help", "Ndihma lokale gati · Operatori aktivizon OpenAI");
}
function applyLanguage() {
  document.documentElement.lang = state.language;
  $("#guideHeading").textContent=tr("Boosty zeigt’s dir","Boosty shows you","Boosty të tregon");
  $("#privacyBtn").href=new URL("datenschutz/"+(__RUNTIME__ === "browser" && state.language!=="de"?state.language+"/":"?lang="+state.language),new URL($("meta[name=app-base]")?.content || "./",location.href)).href;
  $("#legalBtn").href=new URL("impressum/"+(__RUNTIME__ === "browser" && state.language!=="de"?state.language+"/":"?lang="+state.language),new URL($("meta[name=app-base]")?.content || "./",location.href)).href;
  document.title = branding.name + " – " + tr("Lebenslauf und Bewerbung mit KI", "AI resume and application builder");
  $$("[data-de]").forEach((el) => el.textContent = el.dataset[state.language] ?? tr(el.dataset.de, el.dataset.en));
  $$("[data-placeholder-de]").forEach((el) => el.placeholder = el.dataset["placeholder" + ({de:"De",en:"En",sq:"Sq"}[state.language])]);
  $("#language").value = state.language;
  $("#preview").setAttribute("aria-label", tr("Dokumentvorschau · separat scrollbar", "Document preview · scroll independently", "Parapamja e dokumentit · lëviz veçmas"));
  $("#boostyLauncher").setAttribute("aria-label", tr("Boosty fragen", "Ask Boosty"));
  $("#documentTabs").setAttribute("aria-label",tr("Dokumente","Documents","Dokumentet"));
  $("#steps").setAttribute("aria-label",tr("Bewerbungsschritte","Application steps","Hapat e aplikimit"));
  $$("[data-close]").forEach(el=>el.setAttribute("aria-label",tr("Schließen","Close","Mbyll")));
  Object.entries(labels).forEach(([key, value]) => $("#profile-" + key).previousElementSibling.textContent = tr(...value));
  renderTabs();
  editorView();
  $("#runtimeNotice").textContent=tr("Deine Bewerbung wird mit OpenAI auf unserem Server erstellt. Du brauchst keinen eigenen API-Key.","Our server creates your application with OpenAI. No personal API key needed.","Serveri ynë krijon aplikimin me OpenAI. Nuk të duhet çelës API.");
  $("#privacyExplanation").textContent=tr("Deine Entwürfe und Bewerbungen werden in deinem Konto gespeichert. Mit deiner Freigabe senden wir Profil und Stellenbeschreibung an OpenAI. Chatfragen werden nicht als Verlauf gespeichert. Du kannst deine Daten und dein Konto löschen.","Drafts and applications are saved in your account. With your permission we send your profile and job description to OpenAI. Help questions are not stored as chat history. You can delete your data and account.","Draftet dhe aplikimet ruhen në llogari. Me miratimin tënd dërgojmë profilin dhe shpalljen te OpenAI. Pyetjet nuk ruhen si historik bisede. Mund të fshish të dhënat dhe llogarinë.");
  $("#guideLink").href = new URL(({de:"de/lebenslauf-mit-ki/",en:"en/ai-resume-builder/",sq:"sq/cv-me-ia/"}[state.language]), baseURL()).href;
  accountView();
  setAccountMode(accountMode);
  boostyConnectionView();
  boostyTip();
  if(tourActive)$("#guideText").textContent=$("#guideText").dataset.topic?helpForTopic($("#guideText").dataset.topic,state.language).content:TOUR[tourIndex][state.language];
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
function requestBody() {
  return {session_id:getSession().session_id,profile:readProfile(),job:job(),wishes:$("#wishes").value.trim(),language:$("#outputLanguage").value,consent:$("#aiConsent").checked};
}
function validateInputs(ai = false) {
  const profile = readProfile();
  if (profile.source_text.length < 10) throw new Error(tr("Bitte den Lebenslauf importieren oder Text einf\xFCgen.", "Import or paste your resume."));
  if (!profile.confirmed) throw new Error(tr("Bitte deine Profilangaben pr\xFCfen und best\xE4tigen.", "Please verify and confirm your profile."));
  if (job().description.length < 10) throw new Error(tr("Bitte die Stellenbeschreibung erg\xE4nzen.", "Please add the job description."));
  if (ai && !$("#aiConsent").checked) {showStep(3);$("#aiConsent").focus();throw new Error(tr("Bitte die Datenübermittlung an OpenAI bestätigen.", "Please confirm sending your details to OpenAI.","Konfirmo dërgimin e të dhënave te OpenAI."));}
  if(!state.account)throw new Error(tr("Bitte anmelden.","Please sign in.","Hyr në llogari."));
}
function showStep(step) {
  if (step === 4 && !state.documents) {
    notify(tr("Erstelle zuerst deine Bewerbungsmappe.", "Create your application package first."));
    return;
  }
  state.step = step;
  if (!tourActive) tourIndex = Math.max(0, TOUR.findIndex(t => t.step === step));
  else stopGuide();
  boostyTip();
  $$("[data-panel]").forEach((el) => el.hidden = Number(el.dataset.panel) !== step);
  $$("[data-step]").forEach((el) => {
    el.classList.toggle("active", Number(el.dataset.step) === step);
    if (Number(el.dataset.step) === step) el.setAttribute("aria-current", "step");
    else el.removeAttribute("aria-current");
  });
  if(studioEntered)$(".studio-content").scrollIntoView({behavior:"instant",block:"start"});
  followStep();
  scheduleSave();
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
    button.textContent = tr(...docLabels[id]);
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", String(id === state.document));
    button.setAttribute("aria-controls", "documentEditor");
    button.tabIndex = id === state.document ? 0 : -1;
    button.classList.toggle("active", id === state.document);
    return button;
  }));
}
function renderPreview() {
  const root = $("#preview"), selected = $("#design").value;
  const theme = designFor(selected), position = root.scrollTop;
  root.dataset.design = selected;
  for (const key of ["accent", "ink", "muted", "rule", "surface"]) root.style.setProperty("--doc-" + key, "#" + theme[key]);
  root.style.setProperty("--doc-font", `"${theme.font}", ${theme.serif ? "Georgia, serif" : "Arial, sans-serif"}`);
  root.style.setProperty("--doc-name-size", theme.nameSize + "px");
  $("#previewDesign").textContent = selected.charAt(0).toUpperCase() + selected.slice(1);
  $("#designHint").textContent = theme[state.language] + " · " + tr("Vorschau und Download verwenden dieses Design.", "Preview and download use this design.", "Parapamja dhe shkarkimi përdorin këtë dizajn.");
  root.replaceChildren();
  const header = document.createElement("header"), body = document.createElement("div");
  header.className = "document-header";
  body.className = "document-body";
  let inHeader = false, headerFinished = false, list;
  for (const line of parseLines(state.documents?.[state.document] || "")) {
    if (line.type === "blank") { list = null; continue; }
    if (line.type === "h1" && !headerFinished && !header.querySelector("h1")) inHeader = true;
    if (["h2", "h3", "bullet"].includes(line.type)) { inHeader = false; headerFinished = true; }
    const container = inHeader && line.type !== "note" ? header : body;
    let node;
    if (line.type === "bullet") {
      if (!list) { list = document.createElement("ul"); container.append(list); }
      node = document.createElement("li"); node.textContent = line.text; list.append(node); continue;
    }
    node = document.createElement(line.type.startsWith("h") ? line.type : line.type === "note" ? "blockquote" : "p");
    node.textContent = line.text;
    list = null;
    container.append(node);
    if (line.type === "h1" && state.document !== "cv") { inHeader = false; headerFinished = true; }
  }
  if (state.document === "cv" && state.photo) {
    const img = document.createElement("img");
    img.src = state.photo; img.alt = tr("Bewerbungsfoto", "Application photo", "Fotoja e aplikimit");
    img.className = "photo-preview"; header.prepend(img);
  }
  root.append(header, body);
  header.hidden = !header.childElementCount;
  root.scrollTop = position;
}
function renderDocument() {
  renderTabs();
  $("#editorLabel").textContent = tr(...docLabels[state.document]);
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
  const total = quality.matched_keywords.length + quality.missing_keywords.length;
  const score = document.createElement("div"); score.className = "quality-score";
  const number = document.createElement("strong"); number.className = "score-number";
  number.textContent = total ? `${quality.ats_score}%` : "—";
  const summary = document.createElement("div");
  const title = document.createElement("strong"); title.textContent = tr("Keyword-Abdeckung", "Keyword coverage");
  const count = document.createElement("p"); count.textContent = total ? `${quality.matched_keywords.length} / ${total} ` + tr("Begriffe im Lebenslauf gefunden", "terms found in resume") : tr("Keine auswertbaren Keywords", "No measurable keywords");
  const meter = document.createElement("meter"); meter.min = 0; meter.max = 100; meter.value = quality.ats_score; meter.setAttribute("aria-label", title.textContent);
  summary.append(title, count, meter); score.append(number, summary); root.append(score);
  const p = document.createElement("p"); p.className = "hint";
  p.textContent = tr("Ein Hinweis auf Wortüberschneidungen, keine Einstellungswahrscheinlichkeit. Alle Angaben vor dem Versand prüfen.", "A word overlap indicator, not a hiring probability. Verify all details before sending."); root.append(p);
  const details = document.createElement("details"), heading = document.createElement("summary");
  heading.textContent = tr("Erfasste Begriffe", "Analyzed terms") + ` · ${quality.matched_keywords.length} ✓ · ${quality.missing_keywords.length} ` + tr("Nicht im Lebenslauf", "Missing from resume"); details.append(heading);
  for (const [words,label,kind] of [[quality.matched_keywords,tr("Gefunden", "Found"),"matched"], [quality.missing_keywords,tr("Nicht im Lebenslauf", "Missing from resume"),"missing"]]) {
    const list = document.createElement("div"); list.className = "keyword-list " + kind; list.append(document.createTextNode(label + ": "));
    words.forEach(word=>{const span=document.createElement("span");span.textContent=word;list.append(span);}); details.append(list);
  }
  root.append(details);
  if (quality.checks.short_letters?.length) {
    const warning = document.createElement("p");
    warning.textContent = tr("Sehr kurze Schreiben prüfen: ", "Review very short letters: ", "Kontrollo letrat shumë të shkurtra: ") + quality.checks.short_letters.map(k => tr(...docLabels[k])).join(", ");
    root.append(warning);
  }
  if (quality.checks.placeholders || quality.checks.new_metrics.length) {
    const note = document.createElement("p");
    note.textContent = tr("Pr\xFCfung n\xF6tig: ", "Needs review: ") + (quality.checks.placeholders ? tr("Platzhalter erg\xE4nzen. ", "Fill in placeholders. ") : "") + (quality.checks.new_metrics.length ? tr("Neue Kennzahlen kontrollieren: ", "Check new metrics: ") + quality.checks.new_metrics.join(", ") : "");
    root.append(note);
  }
}
async function generatePayload(body) {
  if(BROWSER_ONLY)throw new Error(tr("Die KI-Erstellung benötigt den Server.","AI generation requires the server.","Krijimi me IA kërkon serverin."));
  return api("/api/package",body);
}
function usePackage(result) {
  state.models.openai=result.model;
  state.documents = result.documents;
  state.savedProject = false;
  state.isDemo = result.is_demo;
  state.versions = [];
  state.document = "cv";
  $("#generationInfo").textContent = result.is_demo ? tr("DEMO \xB7 Regelbasierte Vorlagen. Platzhalter selbst erg\xE4nzen.", "DEMO \xB7 Rule-based templates. Fill in placeholders yourself.") : `OpenAI · ${result.model}`;
  $("#projectTitle").value = [job().company,job().title].filter(Boolean).join(" · ").slice(0,200);
  $("#projectStatus").value="draft";
  showStep(4);
  renderDocument();
  scheduleSave();
}
async function generate() {
  const demo=false;
  if(generationPending)return;generationPending=true;
  try {
  validateInputs(true);
  await flushSave();
  const existingPackage=!!state.documents;
  await busy(tr(demo ? "Demo-Mappe wird erstellt \u2026" : "Deine Bewerbungsmappe entsteht \u2026", demo ? "Creating demo package \u2026" : "Creating your application package \u2026"), async (report) => {
    const result = await generatePayload(requestBody(demo));
    report(50, tr("Antwort erhalten · Dokumente werden geprüft", "Response received · Checking documents"));
    result.documents = validatePackage(result.documents);
    report(75, tr("Dokumente geprüft · Vorschau wird aufgebaut", "Documents checked · Building preview"));
    if(existingPackage){cancelSave();state.projectId=null;}
    comparisonResults = [];
    $("#comparisonChoices").hidden = true;
    usePackage(result);
  }, true);
  } finally {generationPending=false;}
}
async function refine() {
  validateInputs(true);
  const instruction = $("#revision").value.trim();
  if (instruction.length < 2) throw new Error(tr("Bitte die gew\xFCnschte \xC4nderung eingeben.", "Enter your revision instruction."));
  await busy(tr("Dokument wird angepasst \u2026", "Revising document \u2026"), async () => {
    const body = { ...requestBody(false), document: state.document, current_content: state.documents[state.document], instruction };
    const content = (await api("/api/package/refine", body)).content;
    state.versions.push({ ...state.documents });
    state.documents[state.document] = content;
    state.isDemo = false;
    renderDocument();
    scheduleSave();
    $("#revision").value = "";
  });
}
function exportBody(id) {
  return { content: state.documents[id], document: id, design: $("#design").value, format: $("#format").value, language: $("#outputLanguage").value, filename: $("#filename").value + "_" + id, photo: id === "cv" ? state.photo : null };
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
  return { session_id:getSession().session_id, title:($("#projectTitle").value.trim() || [job().company,job().title].filter(Boolean).join(" · ") || tr("Neue Bewerbung","New application","Aplikim i ri")).slice(0,200), status:$("#projectStatus").value, profile:readProfile(), job:job(), documents:state.documents, language:$("#outputLanguage").value, design:$("#design").value, notes:$("#projectNotes").value, wishes:$("#wishes").value, step:state.step, provider:state.provider, model:state.models.openai || "", photo:state.photo && /^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(state.photo) ? state.photo : null, revision:state.projectRevision || null };
}
function hasDraft() {return !!(readProfile().source_text || Object.keys(labels).some(k=>state.profile[k]) || Object.values(job()).some(Boolean) || state.documents || $("#wishes").value || $("#projectNotes").value || state.photo);}
function saveNotice(kind) {
  const texts={guest:["Bitte anmelden, um Bewerbungen zu erstellen.","Sign in to create applications.","Hyr për të krijuar aplikime."],ready:["Automatisches Speichern aktiv.","Autosave active.","Ruajtja automatike aktive."],pending:["Änderungen werden gespeichert …","Saving changes …","Po ruhen ndryshimet …"],saved:["✓ In deinem Konto gespeichert","✓ Saved to your account","✓ Ruajtur në llogarinë tënde"],error:["Speichern fehlgeschlagen. Daten bleiben im offenen Tab. Erneut speichern oder Projektdatei sichern.","Save failed. Data remains in this open tab. Retry saving or download a project file.","Ruajtja dështoi. Të dhënat mbeten në skedën e hapur. Provo përsëri ose shkarko projektin."]};
  $("#saveStatus").textContent=tr(...texts[kind]);
}
function scheduleSave() {
  if (!state.account || BROWSER_ONLY || !hasDraft()) return;
  saveDirty=true;clearTimeout(saveTimer);saveNotice("pending");
  if(savePaused)return;
  saveTimer=setTimeout(()=>saveCurrent().catch(()=>{}),900);
}
function saveCurrent() {
  clearTimeout(saveTimer);
  const epoch=saveEpoch,account=state.account;
  const pending=saveChain.catch(()=>{}).then(async()=>{
    if (epoch!==saveEpoch || !account || account!==state.account || BROWSER_ONLY || savePaused || !hasDraft()) return;
    saveDirty=false;saveNotice("pending");
    const data=projectData(), id=state.projectId;
    try {
      const result=await api(id?"/api/projects/"+id:"/api/projects",data,id?"PUT":"POST");
      if(epoch!==saveEpoch || account!==state.account) return;
      state.projectId=result.id;state.projectRevision=result.revision;
      saveNotice(saveDirty?"pending":"saved");
    } catch(error) {
      if(epoch===saveEpoch){saveDirty=true;saveNotice("error");if(/anderen Tab|reopen/.test(error.message))$("#saveStatus").textContent+= " " + error.message;}
      throw error;
    }
  });
  saveChain=pending;return pending;
}
async function flushSave() {clearTimeout(saveTimer);await saveChain.catch(()=>{});if(saveDirty)await saveCurrent();}
async function leaveCurrent() {
  try {await flushSave();return true;}catch(error){
    notify(error.message,true);
    return confirm(tr("Die Änderungen konnten nicht gespeichert werden. Sichere bei Bedarf zuerst eine Projektdatei. Trotzdem fortfahren und ungespeicherte Änderungen verwerfen?","Changes could not be saved. Download a project backup first if needed. Continue and discard unsaved changes?","Ndryshimet nuk u ruajtën. Shkarko fillimisht projektin nëse duhet. Vazhdo dhe hiq ndryshimet e paruajtura?"));
  }
}
function cancelSave() {clearTimeout(saveTimer);saveEpoch++;saveDirty=false;}

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
  return { ...value, profile, job: jobValue, documents: value.documents == null ? null : validatePackage(value.documents) };
}
function openProject(raw, id = null) {
  const value = validateProject(raw);
  cancelSave();
  fillProfile(value.profile);
  fillJob(value.job);
  state.documents = value.documents;
  state.document = "cv";
  state.projectId = id;
  state.projectRevision = value._revision || null;
  state.photo = typeof value.photo === "string" && /^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(value.photo) ? value.photo : null;
  $("#wishes").value = value.wishes || "";
  state.provider="openai";state.models.openai=value.model || "";
  state.savedProject = true;
  state.versions = [];
  $("#outputLanguage").value = ["de","en","sq"].includes(value.language) ? value.language : "de";
  $("#design").value = Object.hasOwn(DESIGNS, value.design) ? value.design : "modern";
  $("#projectTitle").value = value.title || "";
  $("#projectStatus").value = value.status || "draft";
  $("#projectNotes").value = value.notes || "";
  $("#generationInfo").textContent = tr("Gespeicherte Bewerbung \xB7 alle Angaben erneut pr\xFCfen.", "Saved application \xB7 verify all details again.");
  showStep(state.documents ? 4 : Math.min(3,value.step || 1));
  if(state.documents)renderDocument();
  clearTimeout(saveTimer);saveDirty=false;
  saveNotice(state.account?"saved":"guest");
}
function accountView() {
  saveNotice(state.account?"ready":"guest");
  $("#welcomeActions").hidden=!!state.account;
  $("#signedInWelcome").hidden=!state.account;
  $("#welcomeNote").hidden=!!state.account;
  $("#accountInfo").textContent = state.account ? state.account + " · " + tr("Deine gespeicherten Bewerbungen findest du unter „Meine Bewerbungen“, auch nach dem nächsten Anmelden.", "Find your saved applications under ‘My applications’, including after signing in again.") : BROWSER_ONLY ? tr("Konten und Cloud-Speicherung ben\xF6tigen den Server. Du kannst eine Projektdatei lokal herunterladen.", "Accounts and cloud storage require the server. You can download a local project file.") : tr("Dein Konto und gespeicherte Bewerbungen bleiben nach dem Abmelden erhalten. Bewahre den Wiederherstellungscode sicher auf.", "Your account and saved applications persist after sign-out. Keep your recovery code safe.");
  $("#accountForm").hidden = BROWSER_ONLY || !!state.account;
  $("#signedInActions").hidden = !state.account;
  $("#socialLogin").hidden=!!state.account;
  $("#socialLoginNotice").hidden=!!state.account;
  $("#accountBtn").textContent = state.account ? tr("Mein Konto", "My account") : tr("Anmelden", "Sign in");
}
function setAccountMode(mode) {
  accountMode=mode;
  $("#loginMode").setAttribute("aria-pressed",String(mode==="login"));
  $("#register").setAttribute("aria-pressed",String(mode==="register"));
  $("#accountPassword").autocomplete=mode==="register"?"new-password":"current-password";
  $("#accountSubmit").textContent=mode==="register"?tr("Konto erstellen","Create account","Krijo llogari"):tr("Einloggen","Sign in","Hyr");
}
function openAccount(mode="login") {setAccountMode(mode);$("#accountDialog").showModal();if(!state.account)$("#accountEmail").focus();}
async function credentials(mode) {
  if (accountBusy || !$("#accountForm").reportValidity()) return;
  accountBusy=true;$("#accountForm").inert=true;
  try {
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
    enterStudio();
    if(hasDraft())scheduleSave();
    if(mode!=="register"){$("#accountDialog").close();if(!hasDraft())await showProjects();}
    else $("#workspace").scrollIntoView({behavior:"instant",block:"start"});
  }
  } finally {accountBusy=false;$("#accountForm").inert=false;}
}
async function showProjects() {
  if (BROWSER_ONLY || !state.account) {
    $("#accountDialog").showModal();
    return;
  }
  await flushSave().catch(error=>notify(error.message,true));
  const projects = await api("/api/projects");
  const root = $("#projectList");
  const statuses={draft:tr("Entwurf","Draft","Draft"),ready:tr("Bereit","Ready","Gati"),sent:tr("Versendet","Sent","Dërguar"),interview:tr("Gespräch","Interview","Intervistë"),offer:tr("Angebot","Offer","Ofertë"),rejected:tr("Absage","Rejected","Refuzuar")};
  $("#historySummary").replaceChildren(...[[projects.length,tr("Bewerbungen","Applications","Aplikime")],[projects.filter(p=>p.has_documents).length,tr("Mappen erstellt","Packages generated","Dosje të krijuara")],[projects.filter(p=>p.status==="sent").length,tr("Als versendet markiert","Marked as sent","Shënuar si të dërguara")]].map(([n,label])=>{const el=document.createElement("span");el.textContent=n+" · "+label;return el;}));
  $("#historySearch").value="";
  $("#historySearch").oninput=()=>{const q=$("#historySearch").value.toLocaleLowerCase();[...root.children].forEach(el=>el.hidden=!el.textContent.toLocaleLowerCase().includes(q));};
  root.replaceChildren();
  if (!projects.length) root.textContent = tr("Noch keine gespeicherten Bewerbungen.", "No saved applications yet.");
  for (const project of projects) {
    const item = document.createElement("div");
    item.className = "project-item";
    const title = document.createElement("strong");
    title.textContent = project.title;
    const info = document.createElement("small");
    info.textContent = [project.company,project.role].filter(Boolean).join(" · ") + "\n" + (statuses[project.status] || project.status) + " · " + tr("Zuletzt gespeichert: ","Last saved: ","Ruajtur së fundi: ") + new Date(project.updated_at).toLocaleString(state.language) + (project.generated_at?"\n"+tr("Mappe erstellt: ","Package generated: ","Dosja e krijuar: ")+new Date(project.generated_at).toLocaleString(state.language):"");
    const row = document.createElement("div");
    row.className = "row";
    for (const type of ["open", "delete"]) {
      const button = document.createElement("button");
      button.className = "button " + (type === "open" ? "outline" : "quiet");
      button.textContent = type === "open" ? tr("\xD6ffnen", "Open") : tr("L\xF6schen", "Delete");
      button.addEventListener("click", action(async () => {
        if (type === "open") {
          if(!await leaveCurrent())return;
          openProject(await api("/api/projects/" + project.id), project.id);
          $("#projectsDialog").close();
        } else if (confirm(tr("Diese Bewerbung endg\xFCltig l\xF6schen?", "Permanently delete this application?"))) {
          if(state.projectId===project.id){clearPersonalMemory();accountView();}
          await api("/api/projects/" + project.id, null, "DELETE");
          item.remove();
        }
      }));
      row.append(button);
    }
    item.append(title, info);
    if(/^https:\/\//i.test(project.url || "")) {const link=document.createElement("a");link.href=project.url;link.textContent=tr("Stellenanzeige öffnen ↗","Open job posting ↗","Hap shpalljen ↗");link.target="_blank";link.rel="noopener noreferrer";item.append(link);}
    item.append(row);
    root.append(item);
  }
  $("#projectsDialog").showModal();
}
function clearPersonalMemory() {
  cancelSave();chatEpoch++;chatPending=false;$("#boostyForm button").disabled=false;
  stopGuide();
  $("#boostyAnswer").textContent = "";
  $("#boostyQuestion").value = "";
  state.keys = {};
  state.models = {};
  state.documents = null;
  state.photo = null;
  state.projectId = null;
  state.projectRevision = null;
  state.versions = [];
  state.savedProject = false;
  comparisonResults = [];
  fillProfile(parseProfile(""));
  fillJob({});
  $("#projectStatus").value="draft";
  for(const id of ["cvFile","photo","projectFile","scanInput","accountPassword","recoveryCode","accountEmail"])if($("#"+id))$("#"+id).value="";
  $("#generationInfo").textContent="";$("#quality").replaceChildren();
  for (const id of ["documentEditor", "wishes", "projectNotes", "projectTitle", "fileStatus", "jobImportStatus"]) {
    const field = $("#" + id);
    if ("value" in field) field.value = "";
    else field.textContent = "";
  }
  for (const id of ["preview", "projectList", "comparisonChoices"]) $("#" + id).replaceChildren();
  $("#comparisonChoices").hidden = true;
  $("#aiConsent").checked = false;
  showStep(1);
}
async function deleteData() {
  if (!confirm(tr("Diese Sitzung und die aktuell ge\xF6ffneten Daten l\xF6schen? Gespeicherte Bewerbungen dieser Sitzung werden ebenfalls gel\xF6scht.", "Delete this session and its open data? Saved applications in this session will also be deleted."))) return;
  cancelSave();
  await saveChain.catch(()=>{});
  if (!BROWSER_ONLY && getSession().session_id) await api("/api/session/" + getSession().session_id, null, "DELETE");
  clearPersonalMemory();
  accountView();
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
      if (message.status === "recognizing text") {
        const percent = Math.round(message.progress * 100);
        $("#busyProgress").value = percent;
        $("#busyPercent").textContent = tr("Texterkennung: ", "Text recognition: ") + percent + "%";
      }
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
    input.maxLength = ({experience:60000,education:6000,skills:6000,languages:1000,name:200,email:254,phone:100,location:300,headline:300})[key];
    if (input.tagName === "TEXTAREA") input.rows = 3;
    else input.type = key === "email" ? "email" : "text";
    input.addEventListener("input", () => $("#confirmed").checked = false);
    label.append(span, input);
    $("#profileFields").append(label);
  }
  $("#outputLanguage").value = state.language;
  applyLanguage();
  window.addEventListener("sharedJob", (event) => {
    if (typeof event.detail?.url === "string") {
      $("#jobUrl").value = event.detail.url;
      showStep(2);
    }
  });
  $("#language").addEventListener("change", () => {
    state.language = $("#language").value;
    const url = new URL(location.href); url.searchParams.set("lang",state.language); history.replaceState(null,"",url);
    applyLanguage();
  });
  $("#workspace").addEventListener("input",event=>{if(!["aiConsent","followBoosty"].includes(event.target.id))scheduleSave();});
  $("#workspace").addEventListener("change",event=>{if(!["aiConsent","followBoosty"].includes(event.target.id))scheduleSave();});
  $("#workspace").addEventListener("click",()=>queueMicrotask(scheduleSave));
  $("#followBoosty").addEventListener("change",()=>$("#followBoosty").checked?followStep():stopGuide());
  $("#newApplication").addEventListener("click",action(async()=>{if(!await leaveCurrent())return;if(!state.account&&hasDraft()&&!confirm(tr("Gastdaten verwerfen und neu beginnen? Sichere vorher deine Projektdatei.","Discard guest data and start again? Download your project first.","Fshi të dhënat e vizitorit dhe fillo sërish? Ruaj fillimisht projektin.")))return;clearPersonalMemory();accountView();followStep();}));
  $("#infoBtn").addEventListener("click",()=>$("#infoDialog").showModal());
  $$("a.brand").forEach(link=>link.addEventListener("click",event=>{event.preventDefault();window.scrollTo({top:0,behavior:"smooth"});}));
  $("#welcomeRegister").addEventListener("click",()=>openAccount("register"));
  $("#welcomeLogin").addEventListener("click",()=>openAccount());
  $("#welcomeHistory").addEventListener("click",action(showProjects));
  $("#boostyQuestion").addEventListener("keydown",event=>{if(event.key==="Enter"&&!event.shiftKey&&!event.isComposing){event.preventDefault();$("#boostyForm").requestSubmit();}});
  $("#boostyLauncher").addEventListener("click", () => $("#helpBtn").click());
  $("#toggleEditor").addEventListener("click", () => { editorMode = !editorMode; editorView(); });
  $("#copyDocument").addEventListener("click", action(async () => {
    await navigator.clipboard.writeText(state.documents[state.document]);
    notify(tr("Text kopiert.", "Text copied."));
  }));
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
    fillJob({ description: SAMPLE[state.language].job, title: state.language === "sq" ? "Zhvillues Frontend" : "Frontend Developer", company: state.language === "sq" ? "Kompania Shembull" : state.language === "de" ? "Beispielfirma" : "Example Company" });
    $("#outputLanguage").value = state.language;
    showStep(1);
    $("#workspace").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    notify(tr("Beispiel geladen. Pr\xFCfe und best\xE4tige die Angaben.", "Example loaded. Verify and confirm the details."));
  });
  $("#jobDescription").addEventListener("change", () => {
    const found = jobDetails($("#jobDescription").value);
    for (const [key,id] of Object.entries({title:"jobTitle",company:"jobCompany",email:"jobEmail"})) if (!$("#"+id).value && found[key]) $("#"+id).value = found[key];
  });
  $("#importJob").addEventListener("click", action(async () => {
    if (BROWSER_ONLY) throw new Error(tr("Stellenlink-Import ben\xF6tigt den Server. Kopiere die Beschreibung in das Textfeld.", "Job URL import requires server mode. Paste the description into the text field."));
    const result = await busy(tr("Stellenanzeige wird gelesen \u2026", "Reading job posting \u2026"), () => api("/api/job/import", { url: $("#jobUrl").value.trim() }));
    const found = jobDetails(result.description);
    fillJob({ ...job(), ...result, title:result.title || found.title || job().title, company:result.company || found.company || job().company, email:result.email || found.email || job().email });
    scheduleSave();
    $("#jobImportStatus").textContent = tr("Importiert. Pr\xFCfe Position, Firma und Stellentext.", "Imported. Verify role, company and job text.") + (result.truncated ? tr(" Text wurde auf 20.000 Zeichen begrenzt.", " Text was limited to 20,000 characters.") : "");
  }));
  $("#generate").addEventListener("click", action(() => generate(false)));
  $("#refine").addEventListener("click", action(refine));
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
      $("#preview").scrollTop = 0;
      renderDocument();
    }
  });
  $("#documentTabs").addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    let index = DOCUMENTS.indexOf(state.document);
    index = event.key === "Home" ? 0 : event.key === "End" ? 3 : (index + (event.key === "ArrowRight" ? 1 : -1) + 4) % 4;
    state.document = DOCUMENTS[index];
    $("#preview").scrollTop = 0;
    renderDocument();
    $("#tab-" + state.document).focus();
  });
  $("#documentEditor").addEventListener("input", (event) => {
    state.documents[state.document] = event.target.value;
    renderPreview();
    renderQuality();
  });
  $("#design").addEventListener("change", () => {
    $("#preview").scrollTop = 0;
    editorMode = false;
    editorView();
    renderPreview();
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
    scheduleSave();
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
    const lines = state.documents.email.split("\n"), subject = lines[0].replace(/^(?:Subject|Betreff|Subjekti):\s*/i, "");
    const value = `mailto:${encodeURIComponent(email)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(lines.slice(1).join("\n").trim())}`;
    if (value.length > 16e3) throw new Error(tr("E-Mail zu lang. Bitte kopieren.", "Email too long. Copy the text instead."));
    location.href = value;
  }));
  $("#backupProject").addEventListener("click", action(() => saveBlob(new Blob([JSON.stringify(projectData(), null, 2)], { type: "application/json" }), "Bewerbung.project.json")));
  $("#projectFile").addEventListener("change", action(async (event) => {
    const file = event.target.files[0];
    if (file.size > 8e6) throw new Error("Projektdatei zu gro\xDF / project file too large");
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
    await saveCurrent();
    notify(tr("Bewerbung gespeichert.", "Application saved."));
  }));
  $("#projectsBtn").addEventListener("click", action(showProjects));
  $("#accountBtn").addEventListener("click",()=>openAccount());
  $("#accountForm").addEventListener("submit", action((event) => {
    event.preventDefault();
    return credentials(accountMode);
  }));
  $("#register").addEventListener("click",()=>setAccountMode("register"));
  $("#loginMode").addEventListener("click",()=>setAccountMode("login"));
  $("#recover").addEventListener("click", action(() => credentials("recover")));
  $("#logout").addEventListener("click", action(async () => {
    if(!await leaveCurrent())return;
    await api("/api/account/logout", {});
    setLoginToken("");
    state.account = null;
    clearPersonalMemory();
    await newSession(state.language);
    $("#accountResult").textContent = "";
    accountView();
    returnWelcome();
    notify(tr("Abgemeldet. Gespeicherte Bewerbungen bleiben in deinem Konto erhalten.", "Signed out. Saved applications remain in your account."));
  }));
  $("#deleteAccount").addEventListener("click", action(async () => {
    if (!confirm(tr("Konto und alle Bewerbungen endg\xFCltig l\xF6schen?", "Permanently delete your account and every application?"))) return;
    cancelSave();
    await saveChain.catch(()=>{});
    await api("/api/account", null, "DELETE");
    setLoginToken("");
    state.account = null;
    clearPersonalMemory();
    $("#accountDialog").close();
    accountView();
    returnWelcome();
    await newSession(state.language);
    notify(tr("Konto gel\xF6scht.", "Account deleted."));
  }));
  $$("[data-close]").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));
  $("#clearData").addEventListener("click", action(deleteData));
  $("#helpBtn").addEventListener("click", () => {
    if(!$("#boostyAnswer").children.length)setBoostyAnswer(boostyAnswer("start", state.language));
    $("#boostyDialog").showModal();
  });
  $("#boostyShow").addEventListener("click",showBoostyTarget);
  $("#guideClose").addEventListener("click",()=>{$("#followBoosty").checked=false;stopGuide();});
  $("#guideNext").addEventListener("click",()=>guideTo((tourIndex+1)%TOUR.length));
  $("#guideChat").addEventListener("click",()=>$("#helpBtn").click());
  window.addEventListener("resize",scheduleGuide);
  document.addEventListener("scroll",scheduleGuide,true);
  $("#boostyNext").addEventListener("click", () => guideTo((tourIndex + 1) % TOUR.length));
  $("#boostyForm").addEventListener("submit", askBoosty);
  $$("[data-boosty]").forEach(button => button.addEventListener("click", () => {
    setBoostyAnswer(boostyAnswer(button.dataset.boosty, state.language));
  }));
  $("#adminLink").addEventListener("click", (event) => {
    event.preventDefault();
    embeddedAdmin?.clear();
    embeddedAdmin = mountAdmin($("#embeddedAdmin"));
    $("#adminDialog").showModal();
  });
  $("#adminDialog").addEventListener("close", () => embeddedAdmin?.clear());
  window.addEventListener("beforeunload", (event) => {
    if (saveDirty || (!state.account && (readProfile().source_text || state.documents))) {
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
  scanButton.dataset.sq = "Lexo foto / skanim (OCR lokal)";
  scanButton.textContent = tr(scanButton.dataset.de, scanButton.dataset.en, scanButton.dataset.sq);
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
    if(state.account)enterStudio();
  }
  if (!BROWSER_ONLY) {try {boostyConfig=await api("/api/assistant/config");} catch { /* Local help remains available. */ }}
  if(!BROWSER_ONLY){
    const config=await api("/api/hosted-config");
    $("#aiCapacity").textContent=tr(`Bis zu ${config.daily_packages} Bewerbungs­mappen pro Tag. Deine Eingaben kannst du jederzeit bearbeiten.`,`Up to ${config.daily_packages} application packages per day. Edit your inputs anytime.`,`Deri në ${config.daily_packages} dosje aplikimi në ditë. Të dhënat mund t'i ndryshosh kurdo.`);
    const providers=await api("/api/oauth/providers");
    $("#socialLogin").replaceChildren(...providers.map(provider=>{const button=document.createElement("button");button.type="button";button.className="button outline";button.disabled=!provider.enabled;button.textContent=provider.name+(provider.enabled?"":tr(" · bald verfügbar"," · coming soon"," · së shpejti"));button.addEventListener("click",()=>{location.href=(API_BASE || location.origin).replace(/\/$/,"")+`/api/oauth/${provider.id}/start`;});return button;}));
  }
  boostyConnectionView();
  const params = new URLSearchParams(location.search);
  if(params.get("auth")==="failed")notify(tr("Die Anmeldung konnte nicht abgeschlossen werden. Nutze deine E-Mail-Anmeldung oder versuche es erneut.","Sign-in could not be completed. Use email sign-in or try again.","Hyrja nuk u përfundua. Përdor email-in ose provo sërish."),true);
  if (params.has("jobUrl")) {
    $("#jobUrl").value = params.get("jobUrl");
    showStep(2);
  }
}
init().catch((error) => notify(error.message, true));
