import test from 'node:test';
import assert from 'node:assert/strict';
import {calendarDate, dateRangePreset, validDateRange, activeDuration} from '../js/core/traffic.js';

test('reporting dates use UTC calendar days, including timezone midnight and leap year', () => {
  assert.equal(calendarDate(new Date('2026-10-06T00:30:00+02:00')), '2026-10-05');
  assert.deepEqual(dateRangePreset('today', new Date('2026-10-06T00:30:00+02:00')), {start: '2026-10-05', end: '2026-10-05'});
  assert.deepEqual(dateRangePreset('yesterday', new Date('2024-03-01T12:00:00Z')), {start: '2024-02-29', end: '2024-02-29'});
  assert.deepEqual(dateRangePreset('7', new Date('2026-01-03T12:00:00Z')), {start: '2025-12-28', end: '2026-01-03'});
  assert.deepEqual(dateRangePreset('30', new Date('2026-10-06T12:00:00Z')), {start: '2026-09-07', end: '2026-10-06'});
  assert.throws(() => dateRangePreset('custom'), /Unknown date preset/);
});

test('custom reporting intervals reject impossible dates and reversed bounds; one day is valid', () => {
  assert.equal(validDateRange('2024-02-29', '2024-02-29'), true);
  assert.equal(validDateRange('2026-02-29', '2026-03-01'), false);
  assert.equal(validDateRange('2026-10-07', '2026-10-06'), false);
  assert.equal(validDateRange('', '2026-10-06'), false);
  assert.equal(validDateRange('2026-10-06<script>', '2026-10-07'), false);
});

test('engagement durations remain explicitly measured seconds, including missing data', () => {
  assert.equal(activeDuration(61), '1 min 1 s');
  assert.equal(activeDuration(0), '0 s');
  assert.equal(activeDuration(null), '0 s');
  assert.equal(activeDuration(-8), '0 s');
  assert.equal(activeDuration(14.8), '15 s');
  assert.equal(activeDuration(Infinity), '0 s');
});
