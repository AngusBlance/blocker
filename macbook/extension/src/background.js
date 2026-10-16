import { blockRules, focusActive, focusPagePath, focusRules, tabAllowed } from './rules.js';

const WS_URL = 'ws://127.0.0.1:8766';
const ALARM_NAME = 'blocker-sync-fallback';
const FOCUS_END_ALARM = 'blocker-focus-end';

let socket = null;

async function applyState({ blocked, focus }) {
  const now = Date.now();
  const existing = await chrome.declarativeNetRequest.getDynamicRules();
  await chrome.declarativeNetRequest.updateDynamicRules({
    removeRuleIds: existing.map((r) => r.id),
    addRules: [...blockRules(blocked), ...focusRules(focus, now)],
  });
  const wasOn = existing.some((r) => r.action.type === 'redirect');
  if (focusActive(focus, now)) {
    // Ends on time even if the app isn't running then.
    chrome.alarms.create(FOCUS_END_ALARM, { when: focus.until });
    if (!wasOn) await sendAwayOpenTabs(focus);
  } else {
    chrome.alarms.clear(FOCUS_END_ALARM);
  }
}

// The rules only catch pages opened from now on; tabs already open on other
// sites go to the focus page when focus starts.
async function sendAwayOpenTabs(focus) {
  const url = chrome.runtime.getURL(focusPagePath(focus));
  const tabs = await chrome.tabs.query({});
  await Promise.all(
    tabs
      .filter((tab) => tab.url && !tabAllowed(tab.url, focus.allow))
      .map((tab) => chrome.tabs.update(tab.id, { url })),
  );
}

async function endFocus() {
  const existing = await chrome.declarativeNetRequest.getDynamicRules();
  await chrome.declarativeNetRequest.updateDynamicRules({
    removeRuleIds: existing.filter((r) => r.action.type !== 'block').map((r) => r.id),
  });
}

function connect() {
  if (
    socket &&
    (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)
  ) {
    return; // already connected or connecting
  }

  socket = new WebSocket(WS_URL);

  socket.addEventListener('message', (event) => {
    const data = JSON.parse(event.data);
    applyState({ blocked: data.blocked, focus: data.focus ?? null });
  });

  socket.addEventListener('close', () => {
    socket = null;
  });

  socket.addEventListener('error', () => {
    socket = null;
  });
}

function start() {
  chrome.alarms.create(ALARM_NAME, { periodInMinutes: 0.5 });
  connect();
}

chrome.runtime.onInstalled.addListener(start);
chrome.runtime.onStartup.addListener(start);
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM_NAME) {
    // reconnects if the socket was ever lost (e.g. the TUI restarted);
    // a no-op if already connected
    connect();
  } else if (alarm.name === FOCUS_END_ALARM) {
    endFocus();
  }
});
