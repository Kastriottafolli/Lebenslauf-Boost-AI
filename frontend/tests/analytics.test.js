import test from 'node:test';
import assert from 'node:assert/strict';
import {ANALYTICS_PREFERENCE_VERSION, ANALYTICS_STORAGE_KEY, createAnalyticsController, createEngagementClock, readAnalyticsPreference} from '../js/core/analytics.js';

class Target {
  listeners = new Map();
  addEventListener(name, work) {if (!this.listeners.has(name)) this.listeners.set(name, new Set()); this.listeners.get(name).add(work);}
  removeEventListener(name, work) {this.listeners.get(name)?.delete(work);}
  emit(name, event = {}) {for (const work of this.listeners.get(name) || []) work({target:this, preventDefault() {}, ...event});}
}
class Element extends Target {
  constructor(tag) {super(); this.tagName = tag; this.children = []; this.dataset = {}; this.attributes = {}; this.hidden = false;}
  set textContent(value) {this.text = value; this.children = [];}
  get textContent() {return (this.text || '') + this.children.map(child => child.textContent || '').join('');}
  append(...children) {for (const child of children) {child.parent = this; this.children.push(child);}}
  replaceChildren(...children) {this.children = []; this.text = ''; this.append(...children);}
  setAttribute(key, value) {this.attributes[key] = value;}
  remove() {if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this);}
  matches(selector) {return selector === this.tagName || selector === '.analytics-choice' && this.className?.split(' ').includes('analytics-choice') || selector === '[data-analytics-settings]' && this.dataset.analyticsSettings !== undefined;}
  querySelectorAll(selector) {return this.children.flatMap(child => [...(child.matches(selector) ? [child] : []), ...child.querySelectorAll(selector)]);}
  querySelector(selector) {return this.querySelectorAll(selector)[0] || null;}
  closest(selector) {return this.matches(selector) ? this : this.parent?.closest(selector) || null;}
}
const preference = (choice, timestamp) => ({version:ANALYTICS_PREFERENCE_VERSION, choice, timestamp:new Date(timestamp).toISOString()});
const flush = () => new Promise(resolve => setImmediate(resolve));
function browser({choice, enabled = true, fetch: customFetch} = {}) {
  let wall = Date.parse('2026-10-06T12:00:00Z'), performance = 0, timerId = 0;
  const values = new Map(choice ? [[ANALYTICS_STORAGE_KEY, JSON.stringify(preference(choice, wall))]] : []);
  const storage = {getItem:key => values.get(key) || null, setItem:(key, value) => values.set(key, value), removeItem:key => values.delete(key)};
  const doc = new Target(); doc.body = new Element('body'); doc.body.append(new Element('footer')); doc.visibilityState = 'visible'; doc.focused = true; doc.hasFocus = () => doc.focused;
  doc.createElement = tag => new Element(tag); doc.querySelector = selector => doc.body.querySelector(selector); doc.querySelectorAll = selector => doc.body.querySelectorAll(selector);
  const win = new Target(); win.location = {href:'https://example.test/?email=private@example.test#verify-email=secret'};
  const timers = new Map(), requests = [];
  const fetch = async (url, options) => {requests.push({url, ...options, body:JSON.parse(options.body)}); if (customFetch) return customFetch(url, options); return new Response(JSON.stringify(url.endsWith('/start') ? {visit_token:'a'.repeat(43)} : {ok:true}), {headers:{'Content-Type':'application/json'}});};
  const controller = createAnalyticsController({page:'home', apiBase:'https://example.test/', enabled, environment:{document:doc, window:win, storage, now:() => wall, performanceNow:() => performance, fetch, setInterval:(callback, delay) => {timers.set(++timerId, {callback, delay}); return timerId;}, clearInterval:id => timers.delete(id)}});
  const result = {controller, doc, win, requests, values, storage, timers, advance(ms) {wall += ms; performance += ms;}, tick(ms = 1000) {this.advance(ms); for (const timer of timers.values()) if (timer.delay === 1000) timer.callback();}, heartbeat() {for (const timer of timers.values()) if (timer.delay === 15000) timer.callback();}, choose(choice) {const button = doc.querySelectorAll('.analytics-choice').find(button => button.dataset.analyticsChoice === choice); assert.ok(button); button.emit('click');}};
  controller.mount(); return result;
}

test('preferences expire after 180 days and reject future, invalid or old-version values', () => {
  const now = Date.parse('2026-10-06T12:00:00Z'), days = 180 * 86400000;
  const read = value => readAnalyticsPreference({getItem:() => JSON.stringify(value)}, now);
  assert.equal(read(preference('analytics', now)).choice, 'analytics');
  assert.equal(read(preference('necessary', now - days + 1)).choice, 'necessary');
  assert.equal(read(preference('analytics', now - days)), null);
  assert.equal(read(preference('analytics', now + 1)), null);
  assert.equal(read({...preference('analytics', now), version:'old'}), null);
  assert.equal(read({...preference('analytics', now), choice:'automatic'}), null);
  assert.equal(readAnalyticsPreference({getItem() {throw new Error('Storage unavailable');}}, now), null);
});

test('necessary-only and unset consent never make analytics requests; choices store no token', async () => {
  const ctx = browser();
  for (let i = 0; i < 20; i++) ctx.tick(); ctx.heartbeat(); ctx.controller.setPage('app'); ctx.controller.openSettings();
  await flush(); assert.deepEqual(ctx.requests, []);
  ctx.choose('necessary'); ctx.heartbeat(); await flush(); assert.deepEqual(ctx.requests, []);
  assert.deepEqual(Object.keys(JSON.parse(ctx.values.get(ANALYTICS_STORAGE_KEY))).sort(), ['choice', 'timestamp', 'version']);
  assert.equal(ctx.values.size, 1);
  ctx.controller.destroy();
});

test('consented requests use a fixed page label and no URL, referrer, identity or cookie credentials', async () => {
  const ctx = browser(); ctx.choose('analytics'); await flush();
  assert.deepEqual(ctx.requests[0].body, {page:'home', analytics_consent:true});
  assert.equal(ctx.requests[0].url, 'https://example.test/api/traffic/start');
  assert.equal(ctx.requests[0].credentials, 'omit');
  assert.equal(ctx.requests[0].referrerPolicy, 'no-referrer');
  for (let i = 0; i < 15; i++) ctx.tick(); ctx.heartbeat(); await flush();
  assert.deepEqual(ctx.requests.at(-1).body, {visit_token:'a'.repeat(43), active_seconds:15});
  ctx.controller.setPage('app?account=private@example.test#reset-password=secret'); await flush();
  for (const request of ctx.requests) {assert.equal(request.referrerPolicy, 'no-referrer'); assert.equal(new URL(request.url).search, ''); assert.ok(!JSON.stringify(request.body).includes('private@example.test')); assert.ok(!JSON.stringify(request.body).includes('secret'));}
  assert.ok(!ctx.values.get(ANALYTICS_STORAGE_KEY).includes('a'.repeat(43)));
  ctx.controller.destroy();
});

test('engagement drops background, unfocused and suspended-timer gaps', async () => {
  const ctx = browser({choice:'analytics'}); await flush();
  for (let i = 0; i < 15; i++) ctx.tick(); ctx.heartbeat(); await flush(); assert.equal(ctx.requests.at(-1).body.active_seconds, 15);
  ctx.doc.visibilityState = 'hidden'; ctx.doc.emit('visibilitychange'); ctx.tick(60000); ctx.heartbeat(); await flush(); assert.equal(ctx.requests.filter(request => request.url.endsWith('/heartbeat')).length, 1);
  ctx.doc.visibilityState = 'visible'; ctx.doc.focused = false; ctx.doc.emit('visibilitychange'); for (let i = 0; i < 10; i++) ctx.tick(); ctx.heartbeat(); await flush(); assert.equal(ctx.requests.filter(request => request.url.endsWith('/heartbeat')).length, 1);
  ctx.doc.focused = true; ctx.win.emit('focus'); ctx.tick(60000); ctx.tick(); ctx.heartbeat(); await flush(); assert.equal(ctx.requests.at(-1).body.active_seconds, 16);
  ctx.controller.destroy();
});

test('wall and performance clocks both constrain active seconds', () => {
  let wall = 0, performance = 0; const clock = createEngagementClock({now:() => wall, performanceNow:() => performance}); clock.reset(true);
  wall += 1000; performance += 800; assert.equal(clock.sample(true), 0);
  wall += 1000; performance += 1000; assert.equal(clock.sample(true), 1);
  wall += 60000; performance += 60000; assert.equal(clock.sample(true), 1);
  wall -= 1000; performance += 1000; assert.equal(clock.sample(true), 1);
  wall += 1000; performance += 1000; assert.equal(clock.sample(false), 1);
});

test('withdrawing consent during an in-flight start deletes the late visit and never heartbeats', async () => {
  let resolveStart; const ctx = browser({fetch:(url) => url.endsWith('/start') ? new Promise(resolve => {resolveStart = resolve;}) : Promise.resolve(new Response('{"ok":true}'))});
  ctx.choose('analytics'); await flush(); assert.equal(ctx.requests.length, 1);
  ctx.controller.openSettings(); ctx.choose('necessary');
  resolveStart(new Response(JSON.stringify({visit_token:'b'.repeat(43)}))); await flush();
  assert.deepEqual(ctx.requests.at(-1).body, {visit_token:'b'.repeat(43), active_seconds:0, withdraw:true});
  assert.ok(ctx.requests.at(-1).url.endsWith('/end'));
  for (let i = 0; i < 20; i++) ctx.tick(); ctx.heartbeat(); await flush(); assert.equal(ctx.requests.length, 2);
  ctx.controller.destroy();
});

test('quick re-consent still withdraws the old pending token and starts a fresh visit', async () => {
  let resolveStart, starts = 0; const ctx = browser({fetch:url => url.endsWith('/start') && ++starts === 1 ? new Promise(resolve => {resolveStart = resolve;}) : Promise.resolve(new Response(JSON.stringify(url.endsWith('/start') ? {visit_token:'c'.repeat(43)} : {ok:true})))});
  ctx.choose('analytics'); await flush(); ctx.controller.openSettings(); ctx.choose('necessary'); ctx.controller.openSettings(); ctx.choose('analytics');
  resolveStart(new Response(JSON.stringify({visit_token:'b'.repeat(43)}))); await flush();
  assert.deepEqual(ctx.requests.find(request => request.url.endsWith('/end')).body, {visit_token:'b'.repeat(43), active_seconds:0, withdraw:true});
  assert.equal(ctx.requests.filter(request => request.url.endsWith('/start')).length, 2);
  ctx.controller.destroy();
});

test('pagehide sends cumulative time with keepalive and focus cannot restart an unloaded page', async () => {
  const ctx = browser({choice:'analytics'}); await flush(); ctx.tick(); ctx.tick(); ctx.win.emit('pagehide'); await flush();
  const request = ctx.requests.at(-1); assert.ok(request.url.endsWith('/end')); assert.equal(request.keepalive, true); assert.deepEqual(request.body, {visit_token:'a'.repeat(43), active_seconds:2});
  ctx.win.emit('focus'); ctx.heartbeat(); await flush(); assert.equal(ctx.requests.length, 2);
  ctx.win.emit('pageshow'); await flush(); assert.equal(ctx.requests.filter(request => request.url.endsWith('/start')).length, 2);
  ctx.controller.destroy(); assert.equal(ctx.timers.size, 0);
});

test('withdrawal in another tab stops the current visit', async () => {
  const ctx = browser({choice:'analytics'}); await flush(); ctx.storage.setItem(ANALYTICS_STORAGE_KEY, JSON.stringify(preference('necessary', Date.parse('2026-10-06T12:00:00Z')))); ctx.win.emit('storage', {key:ANALYTICS_STORAGE_KEY}); await flush();
  assert.equal(ctx.requests.at(-1).body.withdraw, true); ctx.heartbeat(); await flush(); assert.equal(ctx.requests.length, 2);
  ctx.controller.destroy();
});

test('DE, EN and SQ offer two equal buttons; disabled transport keeps consent UI usable', async () => {
  const ctx = browser({enabled:false});
  for (const language of ['de', 'en', 'sq']) {
    ctx.controller.setLanguage(language); ctx.controller.openSettings(); const buttons = ctx.doc.querySelectorAll('.analytics-choice');
    assert.equal(buttons.length, 2); assert.equal(buttons[0].className, buttons[1].className); assert.ok(buttons.every(button => button.textContent.length > 0));
  }
  ctx.choose('analytics'); ctx.heartbeat(); await flush(); assert.deepEqual(ctx.requests, []); assert.equal(JSON.parse(ctx.values.get(ANALYTICS_STORAGE_KEY)).choice, 'analytics');
  ctx.controller.destroy();
});

test('slow heartbeats cannot accumulate overlapping requests', async () => {
  let resolveHeartbeat;
  const ctx = browser({choice:'analytics', fetch:url => url.endsWith('/heartbeat')
    ? new Promise(resolve => {resolveHeartbeat=resolve;})
    : Promise.resolve(new Response(JSON.stringify(url.endsWith('/start') ? {visit_token:'d'.repeat(43)} : {ok:true})))});
  await flush(); ctx.tick(); ctx.heartbeat(); ctx.heartbeat(); await flush();
  assert.equal(ctx.requests.filter(request => request.url.endsWith('/heartbeat')).length, 1);
  resolveHeartbeat(new Response('{"ok":true}')); await flush();
  ctx.heartbeat(); await flush();
  assert.equal(ctx.requests.filter(request => request.url.endsWith('/heartbeat')).length, 2);
  resolveHeartbeat(new Response('{"ok":true}')); await flush(); ctx.controller.destroy();
});

test('a day-long tab starts a fresh visit instead of repeatedly using an expired token', async () => {
  const ctx = browser({choice:'analytics'}); await flush();
  ctx.advance(86400000); ctx.heartbeat(); await flush();
  assert.equal(ctx.requests.filter(request => request.url.endsWith('/start')).length, 2);
  assert.equal(ctx.requests.filter(request => request.url.endsWith('/end')).length, 1);
  assert.equal(ctx.requests.find(request => request.url.endsWith('/end')).body.active_seconds, 0);
  ctx.controller.destroy();
});
