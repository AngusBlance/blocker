// Chrome blocking rules (declarativeNetRequest) for what the blocker app
// sends: the blocked sites, and focus mode. Pure, so it can be tested
// without Chrome.
//
// Focus mode works like Cold Turkey's "block everything except": one rule
// sends every page you open to focus.html, a higher-priority rule lets the
// allowed sites through, and blocked sites sit higher still, so a site
// blocked by the app stays blocked during focus (blocks stack). Only pages
// you open are checked (main_frame), so an allowed page still loads its
// scripts, fonts and video from other domains.

export const BLOCK_RULE_BASE = 1000;
export const FOCUS_BLOCK_ID = 900;
export const FOCUS_ALLOW_ID = 901;

const BLOCK_PRIORITY = 3;
const FOCUS_ALLOW_PRIORITY = 2;
const FOCUS_BLOCK_PRIORITY = 1;

export function blockRules(domains) {
  return domains.map((domain, i) => ({
    id: BLOCK_RULE_BASE + i,
    priority: BLOCK_PRIORITY,
    action: { type: 'block' },
    condition: {
      urlFilter: `||${domain}^`,
      resourceTypes: ['main_frame', 'sub_frame', 'xmlhttprequest', 'script', 'image', 'media'],
    },
  }));
}

export function focusActive(focus, now) {
  return Boolean(focus && focus.until > now && focus.allow.length > 0);
}

// The page a blocked tab goes to, saying until when and what's allowed.
export function focusPagePath(focus) {
  const query = new URLSearchParams({ until: String(focus.until), allow: focus.allow.join(',') });
  return `/focus.html?${query}`;
}

export function focusRules(focus, now) {
  if (!focusActive(focus, now)) return [];
  return [
    {
      id: FOCUS_ALLOW_ID,
      priority: FOCUS_ALLOW_PRIORITY,
      action: { type: 'allow' },
      // requestDomains matches subdomains too: udemy.com allows www.udemy.com.
      condition: { requestDomains: focus.allow, resourceTypes: ['main_frame'] },
    },
    {
      id: FOCUS_BLOCK_ID,
      priority: FOCUS_BLOCK_PRIORITY,
      action: { type: 'redirect', redirect: { extensionPath: focusPagePath(focus) } },
      // Web pages only; chrome:// and the extension's own pages aren't touched.
      condition: { regexFilter: '^https?://', resourceTypes: ['main_frame'] },
    },
  ];
}

// For tabs already open when focus starts: should this one be sent away?
export function tabAllowed(url, allow) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return true;
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return true;
  const host = parsed.hostname.toLowerCase();
  return allow.some((domain) => host === domain || host.endsWith(`.${domain}`));
}
