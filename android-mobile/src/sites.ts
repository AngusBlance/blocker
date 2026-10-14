// Same list as blocklib/domain.py, grouped by site. Subdomains (m.youtube.com,
// www.netflix.com) are covered by the parent domain on Android. `apps` are the
// Android package names of each site's own app, blocked along with the site.
export type Site = { name: string; domains: string[]; apps: string[] };

export const SITES: Site[] = [
  {
    name: 'YouTube',
    domains: ['youtube.com', 'googlevideo.com'],
    apps: ['com.google.android.youtube'],
  },
  { name: 'Netflix', domains: ['netflix.com'], apps: ['com.netflix.mediaclient'] },
  { name: 'Crunchyroll', domains: ['crunchyroll.com'], apps: ['com.crunchyroll.crunchyroid'] },
];

export type Blocked = { domains: string[]; apps: string[] };

export function isSiteBlocked(site: Site, blocked: Blocked): boolean {
  return (
    site.domains.every((d) => blocked.domains.includes(d)) &&
    site.apps.every((a) => blocked.apps.includes(a))
  );
}
