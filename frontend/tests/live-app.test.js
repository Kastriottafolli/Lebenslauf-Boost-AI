import test from "node:test";
import assert from "node:assert/strict";
import { liveAccountUrl, accountModeFromSearch } from "../js/core/live-app.js";

test("Pages account links carry only the selected language and mode to the hosted app", () => {
  for (const language of ["de", "en", "sq"]) {
    for (const mode of ["login", "register"]) {
      const url = new URL(liveAccountUrl("https://tafolliboost.com", language, mode));
      assert.equal(url.origin, "https://tafolliboost.com");
      assert.equal(url.pathname, "/");
      assert.deepEqual([...url.searchParams], [["lang", language], ["account", mode]]);
      assert.equal(url.hash, "");
    }
  }
  assert.equal(new URL(liveAccountUrl("https://tafolliboost.com", "invalid")).searchParams.get("lang"), "de");
});

test("account navigation rejects untrusted URLs and modes", () => {
  for (const url of [
    undefined, "", "/", "http://tafolliboost.com", "javascript:alert(1)",
    "https://tafolliboost.com.evil.test", "https://evil.test/?next=https://tafolliboost.com",
    "https://evil.test@tafolliboost.com", "https://tafolliboost.com:8443",
    "https://tafolliboost.com/redirect", "https://tafolliboost.com/?next=evil", "https://tafolliboost.com/#evil"
  ]) assert.equal(liveAccountUrl(url, "de", "login"), null);
  assert.equal(liveAccountUrl("https://tafolliboost.com", "de", "recover"), null);
});

test("hosted account entry accepts only one explicit login or registration mode", () => {
  assert.equal(accountModeFromSearch("?lang=sq&account=register"), "register");
  assert.equal(accountModeFromSearch("?account=login&lang=en"), "login");
  for (const search of ["", "?account=", "?account=recover", "?account=https://evil.test", "?account=login&account=register"])
    assert.equal(accountModeFromSearch(search), null);
});
