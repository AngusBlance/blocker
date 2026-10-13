const WS_URL = "ws://127.0.0.1:8766";
const ALARM_NAME = "blocker-sync-fallback";
const RULE_ID_BASE = 1000;

let socket = null;

async function applyRules(domains) {
  const existing = await chrome.declarativeNetRequest.getDynamicRules();
  const removeRuleIds = existing.map((r) => r.id);

  const addRules = domains.map((domain, i) => ({
    id: RULE_ID_BASE + i,
    priority: 1,
    action: { type: "block" },
    condition: {
      urlFilter: `||${domain}^`,
      resourceTypes: [
        "main_frame",
        "sub_frame",
        "xmlhttprequest",
        "script",
        "image",
        "media",
      ],
    },
  }));

  await chrome.declarativeNetRequest.updateDynamicRules({
    removeRuleIds,
    addRules,
  });
}

function connect() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return; // already connected or connecting
  }

  socket = new WebSocket(WS_URL);

  socket.addEventListener("message", (event) => {
    const data = JSON.parse(event.data);
    applyRules(data.blocked);
  });

  socket.addEventListener("close", () => {
    socket = null;
  });

  socket.addEventListener("error", () => {
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
