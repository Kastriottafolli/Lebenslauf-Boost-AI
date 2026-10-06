export const PLANNED_PRICING = Object.freeze({
  currency: "EUR", free_packages: 3, free_period: "calendar_week", free_timezone: "Europe/Berlin", terms_version: "2026-10-06",
  offers: [{ id: "single", credits: 1, amount_cents: 199 }, { id: "bundle10", credits: 10, amount_cents: 999 }],
  payments_enabled: false, providers: { stripe: false, paypal: false }
});

export function readPricing(value) {
  const integer = number => Number.isSafeInteger(number) && number >= 0 && number <= 100000;
  if (!value || value.currency !== "EUR" || value.free_period !== "calendar_week" || value.free_timezone !== "Europe/Berlin"
      || !integer(value.free_packages) || !Array.isArray(value.offers)) return null;
  const offers = ["single", "bundle10"].map(id => value.offers.find(offer => offer.id === id));
  if (offers.some(offer => !offer || !integer(offer.credits) || offer.credits < 1
      || !integer(offer.amount_cents) || offer.amount_cents < 1)) return null;
  return { currency: "EUR", free_period: "calendar_week", free_timezone: "Europe/Berlin", terms_version: /^\d{4}-\d{2}-\d{2}$/.test(value.terms_version || "") ? value.terms_version : PLANNED_PRICING.terms_version, free_packages: value.free_packages,
    offers: offers.map(({ id, credits, amount_cents }) => ({ id, credits, amount_cents })),
    payments_enabled: value.payments_enabled === true,
    providers: { stripe: value.providers?.stripe === true, paypal: value.providers?.paypal === true } };
}

export function readBalance(value) {
  if (!value || !["available", "reserved", "free_total", "used", "free_remaining", "paid_remaining"].every(key => Number.isSafeInteger(value[key]) && value[key] >= 0)) return null;
  if (!value.week_end || !Number.isFinite(Date.parse(value.week_end))) return null;
  return { available: value.available, reserved: value.reserved, free_total: value.free_total, used: value.used,
    free_remaining: value.free_remaining, paid_remaining: value.paid_remaining, week_start: value.week_start, week_end: value.week_end };
}

export function purchaseAcknowledged(values) {
  return values.termsAccepted === true && values.immediatePerformance === true && values.withdrawalAcknowledged === true;
}

export function checkoutProviders(pricing) {
  return pricing.payments_enabled ? ["stripe", "paypal"].filter(provider => pricing.providers[provider]) : [];
}

export function safeCheckoutUrl(value, provider) {
  const hosts = { stripe: ["checkout.stripe.com"], paypal: ["www.paypal.com", "www.sandbox.paypal.com"] };
  let url;
  try { url = new URL(value); } catch { return null; }
  if (url.protocol !== "https:" || url.username || url.password || url.port
      || !hosts[provider]?.includes(url.hostname)) return null;
  return url.href;
}

export function packageProject(value) {
  if (!value || typeof value.project_id !== "string"
      || !/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(value.project_id)
      || !Number.isSafeInteger(value.project_revision) || value.project_revision < 1)
    throw new TypeError("PACKAGE_PROJECT_UNAVAILABLE");
  return { projectId: value.project_id, projectRevision: value.project_revision, projectStatus: "ready" };
}

// Retrying an uncertain network response reuses the request. A completed mappe
// or changed input starts a distinct request, which can consume a new credit.
export class PackageRequests {
  constructor(uuid = () => crypto.randomUUID()) { this.uuid = uuid; this.pending = null; }
  start(payload) {
    const fingerprint = JSON.stringify(payload);
    if (this.pending?.fingerprint !== fingerprint) this.pending = { fingerprint, id: this.uuid() };
    return { ...payload, request_id: this.pending.id };
  }
  clear() { this.pending = null; }
  succeeded(id) { if (this.pending?.id === id) this.clear(); }
  failed(error, id) {
    if (this.pending?.id !== id) return;
    const uncertain = !error.status || error.status >= 500
      || (error.status === 409 && error.code === "PACKAGE_IN_PROGRESS");
    if (!uncertain) this.clear();
  }
}
