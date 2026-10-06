export const TERMS_VERSION = "2026-10-06";

// Email secrets stay in memory. Remove the entire fragment before analytics,
// outgoing navigation or the first API request can observe the URL.
export function consumeAccountLink(location, history) {
  const url = new URL(location.href);
  const values = new URLSearchParams(url.hash.slice(1));
  const kind = ["verify-email", "reset-password"].find(key => values.has(key));
  if (!kind) return null;
  const token = values.get(kind);
  url.hash = "";
  history.replaceState(null, "", url.href);
  if (values.getAll(kind).length !== 1 || !/^[A-Za-z0-9_-]{32,256}$/.test(token || "")) return { kind, token: null };
  return { kind, token };
}

const profileTextLimits = Object.freeze({display_name:200,first_name:100,last_name:100,phone:100,location:300,headline:300,street:300,postal_code:32,city:200,country:2});
const genders = ["undisclosed", "female", "male", "diverse"];

export function registrationPayload({ email, password, displayName = "", language, profile = {}, termsAccepted, privacyAcknowledged }) {
  if (termsAccepted !== true || privacyAcknowledged !== true) throw new TypeError("TERMS_REQUIRED");
  const optional = {};
  for (const [key, limit] of Object.entries(profileTextLimits)) {
    if (!Object.hasOwn(profile, key)) continue;
    if (typeof profile[key] !== "string" || profile[key].trim().length > limit) throw new TypeError("PROFILE_INVALID");
    optional[key] = key === "country" ? profile[key].trim().toUpperCase() : profile[key].trim();
  }
  if (optional.country && !/^[A-Z]{2}$/.test(optional.country)) throw new TypeError("PROFILE_INVALID");
  if (Object.hasOwn(profile, "gender")) {
    if (!genders.includes(profile.gender)) throw new TypeError("PROFILE_INVALID");
    optional.gender = profile.gender;
  }
  if (Object.hasOwn(profile, "date_of_birth")) {
    const birth = profile.date_of_birth === "" || profile.date_of_birth == null ? null : profile.date_of_birth;
    if (birth !== null && (typeof birth !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(birth)
      || !Number.isFinite(Date.parse(birth + "T00:00:00Z")) || new Date(birth + "T00:00:00Z").toISOString().slice(0,10) !== birth
      || birth > new Date().toISOString().slice(0,10))) throw new TypeError("PROFILE_INVALID");
    optional.date_of_birth = birth;
  }
  if (Object.hasOwn(profile, "spoken_languages")) {
    if (!Array.isArray(profile.spoken_languages) || profile.spoken_languages.length > 20
      || profile.spoken_languages.some(item => typeof item !== "string" || !item.trim() || item.trim().length > 40)) throw new TypeError("PROFILE_INVALID");
    optional.spoken_languages = profile.spoken_languages.map(item => item.trim());
  }
  if (typeof displayName !== "string" || displayName.trim().length > 200) throw new TypeError("PROFILE_INVALID");
  return { ...optional, email: email.trim(), password, display_name: displayName.trim(), language: ["de", "en", "sq"].includes(language) ? language : "de", terms_version: TERMS_VERSION, terms_accepted: true, privacy_acknowledged: true };
}

export function readAccountProfile(value) {
  if (!value || typeof value !== "object") return null;
  const profile = value.profile || {};
  return {
    display_name: typeof profile.display_name === "string" ? profile.display_name.slice(0, 200) : "",
    first_name: typeof profile.first_name === "string" ? profile.first_name.slice(0, 100) : "",
    last_name: typeof profile.last_name === "string" ? profile.last_name.slice(0, 100) : "",
    phone: typeof profile.phone === "string" ? profile.phone.slice(0, 100) : "",
    location: typeof profile.location === "string" ? profile.location.slice(0, 300) : "",
    headline: typeof profile.headline === "string" ? profile.headline.slice(0, 300) : "",
    language: ["de", "en", "sq"].includes(profile.language) ? profile.language : "de",
    gender: genders.includes(profile.gender) ? profile.gender : "undisclosed",
    date_of_birth: typeof profile.date_of_birth === "string" && /^\d{4}-\d{2}-\d{2}$/.test(profile.date_of_birth) ? profile.date_of_birth : null,
    street: typeof profile.street === "string" ? profile.street.slice(0, 300) : "",
    postal_code: typeof profile.postal_code === "string" ? profile.postal_code.slice(0, 32) : "",
    city: typeof profile.city === "string" ? profile.city.slice(0, 200) : "",
    country: typeof profile.country === "string" ? profile.country.slice(0, 2) : "",
    spoken_languages: Array.isArray(profile.spoken_languages) ? profile.spoken_languages.filter(item => typeof item === "string" && item.trim() && item.length <= 40).slice(0,20) : [],
    updated_at: typeof profile.updated_at === "string" ? profile.updated_at : null,
    preferences: { email_notifications: profile.preferences?.email_notifications === true }
  };
}

export function accountErrorCopy(error, language = "de") {
  const labels = {
    EMAIL_VERIFICATION_REQUIRED: ["Bestätige zuerst deine E-Mail-Adresse. Du kannst dir unten einen neuen Link schicken lassen.", "Confirm your email address first. You can request a new link below.", "Konfirmo fillimisht adresën e email-it. Mund të kërkosh një link të ri më poshtë."],
    MAIL_UNAVAILABLE: ["Der E-Mail-Versand ist vorübergehend nicht verfügbar. Bitte versuche es später erneut.", "Email delivery is temporarily unavailable. Please try again later.", "Dërgimi i email-it është përkohësisht i padisponueshëm. Provo përsëri më vonë."],
    TERMS_REQUIRED: ["Bitte lies und bestätige die Nutzungsbedingungen und den Datenschutzhinweis.", "Please read and acknowledge the terms and privacy information.", "Lexo dhe konfirmo kushtet e përdorimit dhe informacionin e privatësisë."],
    API_TIMEOUT: ["Der Server braucht länger. Bitte versuche es erneut.", "The server is taking longer. Please try again.", "Serveri po vonon. Provo përsëri."],
    INVALID_TOKEN: ["Dieser Link ist ungültig oder abgelaufen. Fordere einen neuen Link an.", "This link is invalid or expired. Request a new link.", "Ky link është i pavlefshëm ose ka skaduar. Kërko një link të ri."]
  };
  labels.ACCOUNT_LINK_INVALID = labels.INVALID_TOKEN;
  labels.TERMS_ACCEPTANCE_REQUIRED = labels.TERMS_REQUIRED;
  labels.CURRENT_PASSWORD_INVALID = ["Das aktuelle Passwort ist nicht korrekt. Bitte prüfe es erneut.", "The current password is incorrect. Please check it again.", "Fjalëkalimi aktual është i pasaktë. Kontrolloje sërish."];
  labels.DELETION_CONFIRMATION_REQUIRED = ["Bestätige dein Passwort und gib DELETE ein, um dein Konto zu schließen.", "Confirm your password and type DELETE to close your account.", "Konfirmo fjalëkalimin dhe shkruaj DELETE për të mbyllur llogarinë."];
  labels.PASSWORD_MISMATCH = ["Die beiden Passwörter stimmen nicht überein.", "The two passwords do not match.", "Dy fjalëkalimet nuk përputhen."];
  labels.PROFILE_INVALID = ["Prüfe deine optionalen Profilangaben. Geburtsdatum, Land und Sprachen müssen gültig sein.", "Check your optional profile details. Date of birth, country and languages must be valid.", "Kontrollo të dhënat opsionale të profilit. Datëlindja, shteti dhe gjuhët duhet të jenë të vlefshme."];
  const fallback = error?.status === 429
    ? ["Bitte warte kurz, bevor du es erneut versuchst.", "Please wait briefly before trying again.", "Prit pak përpara se të provosh sërish."]
    : ["Das hat nicht funktioniert. Prüfe deine Eingaben und versuche es erneut.", "That did not work. Check your details and try again.", "Nuk funksionoi. Kontrollo të dhënat dhe provo përsëri."];
  return (labels[error?.code] || labels[error?.message] || fallback)[{ de: 0, en: 1, sq: 2 }[language] ?? 0];
}

export function explainerMedia(language, base) {
  const selected = ["de", "en", "sq"].includes(language) ? language : "de";
  const root = new URL("static/video/", base);
  return { video: new URL(`tafolliboost-${selected}.mp4`, root).href, captions: new URL(`tafolliboost-${selected}.vtt`, root).href, poster: new URL(`tafolliboost-poster-${selected}.jpg`, root).href, language: selected };
}
