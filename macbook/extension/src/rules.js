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
export const GOOGLE_IMAGES_RULE_ID = 800;
export const ADULT_RULE_ID = 801;

// Google image search is a page on www.google.com (udm=2, or tbm=isch in
// older links) rather than its own host, so blocking images.google.com
// blocks it with this rule too.
export const GOOGLE_IMAGE_SEARCH =
  '^https?://(www\\.)?google\\.[a-z.]+/(imghp|search\\?([^#]*&)?(udm=2|tbm=isch)(&|#|$))';

// The "Adult sites" filter's list lives in /etc/hosts. This adds what a list
// can't name in advance: "porn" anywhere in the host, and the adult-only
// top-level domains.
export const ADULT_HOST = '^https?://[^/?#]*(porn|\\.(xxx|adult|sex)\\.?(:[0-9]+)?([/?#]|$))';

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

// Google Images and the adult filter: blocks like the sites', so focus mode
// can't let them through either (an allowed google.com still has no image
// search).
export function filterRules(blocked, adult) {
  const rules = [];
  if (blocked.includes('images.google.com')) {
    rules.push(pageRule(GOOGLE_IMAGES_RULE_ID, GOOGLE_IMAGE_SEARCH));
  }
  if (adult) rules.push(pageRule(ADULT_RULE_ID, ADULT_HOST));
  return rules;
}

function pageRule(id, regexFilter) {
  return {
    id,
    priority: BLOCK_PRIORITY,
    action: { type: 'block' },
    condition: { regexFilter, resourceTypes: ['main_frame', 'sub_frame'] },
  };
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
