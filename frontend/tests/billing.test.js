import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { PLANNED_PRICING, readPricing, readBalance, checkoutProviders, safeCheckoutUrl, packageProject, PackageRequests } from "../js/core/billing.js";
import { validJobUrl, jobImportProblem } from "../js/core/job.js";

test("planned pricing never enables a payment and invalid pricing fails closed", () => {
  assert.deepEqual(checkoutProviders(PLANNED_PRICING), []);
  assert.equal(readPricing({ ...PLANNED_PRICING, currency: "USD" }), null);
  assert.equal(readPricing({ ...PLANNED_PRICING, offers: [{ id: "single", credits: -1, amount_cents: 199 }] }), null);
  assert.equal(readPricing({ ...PLANNED_PRICING, free_period: "daily" }), null);
  const live = readPricing({ ...PLANNED_PRICING, payments_enabled: true, providers: { stripe: true, paypal: false } });
  assert.deepEqual(checkoutProviders(live), ["stripe"]);
  assert.equal(readBalance({ available: 3, reserved: 0, free_total: 3, used: 0 }).available, 3);
  assert.equal(readBalance({ available: -1, reserved: 0, free_total: 3, used: 0 }), null);
});

test("checkout URLs are limited to the actual payment provider", () => {
  assert.equal(safeCheckoutUrl("https://checkout.stripe.com/c/pay/test", "stripe"), "https://checkout.stripe.com/c/pay/test");
  assert.equal(safeCheckoutUrl("https://www.paypal.com/checkoutnow?token=test", "paypal"), "https://www.paypal.com/checkoutnow?token=test");
  for (const url of ["http://checkout.stripe.com", "https://checkout.stripe.com.evil.test", "https://evil@checkout.stripe.com", "https://checkout.stripe.com:8443", "javascript:alert(1)", "https://www.paypal.com"])
    assert.equal(safeCheckoutUrl(url, "stripe"), null);
});

test("uncertain generation retries reuse one ID, changed content and success start a new ID", () => {
  let count=0; const requests=new PackageRequests(()=>`id-${++count}`);
  const first=requests.start({ job: "original" });
  requests.failed({ code: "API_TIMEOUT" }, first.request_id);
  assert.equal(requests.start({ job: "original" }).request_id, first.request_id);
  requests.failed({ status: 409, code: "PACKAGE_IN_PROGRESS" }, first.request_id);
  assert.equal(requests.start({ job: "original" }).request_id, first.request_id);
  requests.failed({ status: 502 }, first.request_id);
  assert.equal(requests.start({ job: "original" }).request_id, first.request_id);
  const changed=requests.start({ job: "changed" });
  assert.notEqual(changed.request_id, first.request_id);
  requests.succeeded(changed.request_id);
  assert.notEqual(requests.start({ job: "changed" }).request_id, changed.request_id);
  const denied=requests.start({ job: "empty-credit" });
  requests.failed({ status: 402, code: "CREDITS_EXHAUSTED" }, denied.request_id);
  assert.notEqual(requests.start({ job: "empty-credit" }).request_id, denied.request_id);
});

test("job import provides actionable categories without exposing raw server errors", () => {
  assert.equal(validJobUrl(" https://example.com/job "), "https://example.com/job");
  assert.equal(validJobUrl("https://secret@example.com/job"), null);
  assert.equal(validJobUrl("javascript:alert(1)"), null);
  assert.equal(jobImportProblem({ code: "API_TIMEOUT", message: "secret internal error" }), "timeout");
  assert.equal(jobImportProblem({ status: 429 }), "busy");
  assert.equal(jobImportProblem({ status: 500, message: "parser internals" }), "blocked");
});

test("job import recognizes safe public HTTP 422 timeout messages in German and English", () => {
  for(const message of [
    "StepStone antwortet nicht rechtzeitig. Versuche den Link erneut oder öffne die Anzeige im Browser und kopiere ihren Stellentext / portal timed out; retry the link or paste the job text.",
    "portal timed out; retry the link or paste the job text.",
    "Import-Zeitüberschreitung / import timed out"
  ]) assert.equal(jobImportProblem({status:422,message}),"timeout");
});

test("job import keeps unrelated, unsafe and non-422 errors out of the public timeout category", () => {
  for(const error of [
    {status:500,message:"portal timed out; retry the link or paste the job text."},
    {status:422,message:"socket timed out"},
    {status:422,message:"<script>portal timed out</script>"},
    {status:422,message:"portal timed out\nTraceback: private parser details"},
    {status:422,message:"portal timed out "+"x".repeat(500)},
    {status:422,message:{text:"portal timed out"}},
    {status:422,message:"StepStone: Die Verbindung zur Stellenanzeige konnte nicht abgeschlossen werden."}
  ]) assert.equal(jobImportProblem(error),"blocked");
});

test("a generated package adopts its server-owned history ID and exact revision", () => {
  const state={projectId:'old-draft',projectRevision:9};
  const result={project_id:'c4e82d3e-a206-4d64-9931-e8bdf2b3bc14',project_revision:1};
  Object.assign(state,packageProject(result));
  assert.deepEqual(state,{projectId:result.project_id,projectRevision:1,projectStatus:'ready'});
  for(const invalid of [{},{...result,project_revision:null},{...result,project_revision:0},{...result,project_id:'../../admin'}])
    assert.throws(()=>packageProject(invalid),/PACKAGE_PROJECT_UNAVAILABLE/);
});

test("public offer cards provide all pricing nodes before startup and use localized singular copy", async () => {
  const html=await readFile('frontend/index.html','utf8');
  const cards=[...html.matchAll(/<article\b[^>]*data-pricing-offer="([^"]+)"[^>]*>([\s\S]*?)<\/article>/g)];
  assert.deepEqual(cards.map(card=>card[1]),['single','bundle10']);
  for(const [,id,markup] of cards){
    for(const node of ['data-price','data-offer-credits','data-offer-unit','data-payment-state','data-checkout-actions'])assert.ok(markup.includes(node),`${id}: missing ${node}`);
  }
  assert.match(cards[0][2],/data-offer-unit data-de="Bewerbung" data-en="application" data-sq="aplikim"/);
});
