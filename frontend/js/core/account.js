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

export function registrationPayload({ email, password, displayName = "", language, termsAccepted, privacyAcknowledged }) {
  if (termsAccepted !== true || privacyAcknowledged !== true) throw new TypeError("TERMS_REQUIRED");
  return { email: email.trim(), password, display_name: displayName.trim(), language: ["de", "en", "sq"].includes(language) ? language : "de", terms_version: TERMS_VERSION, terms_accepted: true, privacy_acknowledged: true };
}

export function readAccountProfile(value) {
  if (!value || typeof value !== "object") return null;
  const profile = value.profile || {};
  return {
    display_name: typeof profile.display_name === "string" ? profile.display_name.slice(0, 120) : "",
    first_name: typeof profile.first_name === "string" ? profile.first_name.slice(0, 100) : "",
    last_name: typeof profile.last_name === "string" ? profile.last_name.slice(0, 100) : "",
    phone: typeof profile.phone === "string" ? profile.phone.slice(0, 100) : "",
    location: typeof profile.location === "string" ? profile.location.slice(0, 300) : "",
    headline: typeof profile.headline === "string" ? profile.headline.slice(0, 300) : "",
    language: ["de", "en", "sq"].includes(profile.language) ? profile.language : "de",
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
  const fallback = error?.status === 429
    ? ["Bitte warte kurz, bevor du es erneut versuchst.", "Please wait briefly before trying again.", "Prit pak përpara se të provosh sërish."]
    : ["Das hat nicht funktioniert. Prüfe deine Eingaben und versuche es erneut.", "That did not work. Check your details and try again.", "Nuk funksionoi. Kontrollo të dhënat dhe provo përsëri."];
  return (labels[error?.code] || fallback)[{ de: 0, en: 1, sq: 2 }[language] ?? 0];
}

export function explainerMedia(language, base) {
  const selected = ["de", "en", "sq"].includes(language) ? language : "de";
  const root = new URL("static/video/", base);
  return { video: new URL(`tafolliboost-${selected}.mp4`, root).href, captions: new URL(`tafolliboost-${selected}.vtt`, root).href, poster: new URL(`tafolliboost-poster-${selected}.jpg`, root).href, language: selected };
}
