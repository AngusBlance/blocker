import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  FOCUS_ALLOW_ID,
  FOCUS_BLOCK_ID,
  blockRules,
  focusActive,
  focusPagePath,
  focusRules,
  tabAllowed,
} from '../src/rules.js';

const now = 1_760_000_000_000;
const focus = {
  until: now + 3_600_000,
  allow: ['docs.google.com', 'accounts.google.com', 'udemy.com'],
};

test('focus blocks every page, lets the allowed ones through, and blocks still win', () => {
  const rules = [...blockRules(['youtube.com']), ...focusRules(focus, now)];
  const byId = Object.fromEntries(rules.map((r) => [r.id, r]));
  const allow = byId[FOCUS_ALLOW_ID];
  const blockAll = byId[FOCUS_BLOCK_ID];
  assert.equal(allow.action.type, 'allow');
  assert.deepEqual(allow.condition.requestDomains, focus.allow);
  assert.equal(blockAll.action.type, 'redirect');
  assert.deepEqual(blockAll.condition.resourceTypes, ['main_frame']);
  assert.ok(blockAll.priority < allow.priority);
  assert.ok(byId[1000].priority > allow.priority); // a blocked site stays blocked
  assert.equal(new Set(rules.map((r) => r.id)).size, rules.length);
});

test('no rules when focus is off, over, or allows nothing', () => {
  assert.deepEqual(focusRules(null, now), []);
  assert.deepEqual(focusRules({ ...focus, until: now }, now), []);
  assert.deepEqual(focusRules({ ...focus, allow: [] }, now), []);
  assert.equal(focusActive(focus, now), true);
});

test('the focus page says until when and what is allowed', () => {
  const path = focusPagePath(focus);
  assert.ok(path.startsWith('/focus.html?'));
  const params = new URLSearchParams(path.split('?')[1]);
  assert.equal(params.get('until'), String(focus.until));
  assert.equal(params.get('allow'), 'docs.google.com,accounts.google.com,udemy.com');
});

test('open tabs: allowed sites and subdomains stay, others go, non-web pages stay', () => {
  assert.equal(tabAllowed('https://docs.google.com/document/d/1', focus.allow), true);
  assert.equal(tabAllowed('https://www.udemy.com/course/x', focus.allow), true);
  assert.equal(tabAllowed('https://mail.google.com/', focus.allow), false);
  assert.equal(tabAllowed('https://notudemy.com/', focus.allow), false);
  assert.equal(tabAllowed('chrome://extensions', focus.allow), true);
  assert.equal(tabAllowed('not a url', focus.allow), true);
});
