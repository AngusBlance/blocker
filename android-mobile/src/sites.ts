// Same list as blocklib/domain.py, grouped by site. Subdomains (m.youtube.com,
// www.netflix.com) are covered by the parent domain on Android.
export type Site = { name: string; domains: string[] };

export const SITES: Site[] = [
  { name: 'YouTube', domains: ['youtube.com', 'googlevideo.com'] },
  { name: 'Netflix', domains: ['netflix.com'] },
  { name: 'Crunchyroll', domains: ['crunchyroll.com'] },
];

export function isSiteBlocked(site: Site, blocked: string[]): boolean {
  return site.domains.every((d) => blocked.includes(d));
}
