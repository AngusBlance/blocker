const WS_URL = 'ws://127.0.0.1:8766';
const ALARM_NAME = 'blocker-sync-fallback';
const RULE_ID_BASE = 1000;
const GOOGLE_IMAGES_RULE_ID = 800;
const ADULT_RULE_ID = 801;

// Google image search is a page on www.google.com (udm=2, or tbm=isch in
// older links) rather than its own host, so blocking images.google.com
// blocks it with this rule too.
const GOOGLE_IMAGE_SEARCH =
  '^https?://(www\\.)?google\\.[a-z.]+/(imghp|search\\?([^#]*&)?(udm=2|tbm=isch)(&|#|$))';

// The "Adult sites" filter's list lives in /etc/hosts. This adds what a list
// can't name in advance: "porn" anywhere in the host, and the adult-only
// top-level domains.
const ADULT_HOST = '^https?://[^/?#]*(porn|\\.(xxx|adult|sex)\\.?(:[0-9]+)?([/?#]|$))';

let socket = null;

async function applyRules(domains, adult) {
  const existing = await chrome.declarativeNetRequest.getDynamicRules();
  const removeRuleIds = existing.map((r) => r.id);

  const addRules = domains.map((domain, i) => ({
    id: RULE_ID_BASE + i,
    priority: 1,
    action: { type: 'block' },
    condition: {
      urlFilter: `||${domain}^`,
      resourceTypes: ['main_frame', 'sub_frame', 'xmlhttprequest', 'script', 'image', 'media'],
    },
  }));
  if (domains.includes('images.google.com')) {
    addRules.push(pageRule(GOOGLE_IMAGES_RULE_ID, GOOGLE_IMAGE_SEARCH));
  }
  if (adult) {
    addRules.push(pageRule(ADULT_RULE_ID, ADULT_HOST));
  }

  await chrome.declarativeNetRequest.updateDynamicRules({
    removeRuleIds,
    addRules,
  });
}

function pageRule(id, regexFilter) {
  return {
    id,
    priority: 1,
    action: { type: 'block' },
    condition: { regexFilter, resourceTypes: ['main_frame', 'sub_frame'] },
  };
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
    applyRules(data.blocked, data.adult === true);
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
  }
});
