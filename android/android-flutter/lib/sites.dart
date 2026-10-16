// Same sites as blocklib/domain.py on the Mac, grouped by site.
// Subdomains (m.youtube.com) are covered by the parent domain on Android.
// `apps` are each site's Android app, blocked along with the site.
class Site {
  const Site(this.name, this.domains, this.apps, {this.note});

  final String name;
  final List<String> domains;
  final List<String> apps;
  final String? note;

  /// The line under the name on the sites screen.
  String get detail => note ?? '${domains.join(', ')} + app';
}

/// Blocks the "Adult sites" filter (androidlib's AdultSites.ID): not a host,
/// but blocked and scheduled like one.
const adultSitesId = '#adult-sites';

const sites = [
  Site(
    'YouTube',
    ['youtube.com', 'googlevideo.com'],
    ['com.google.android.youtube'],
  ),
  Site('Netflix', ['netflix.com'], ['com.netflix.mediaclient']),
  Site('Crunchyroll', ['crunchyroll.com'], ['com.crunchyroll.crunchyroid']),
  Site('Instagram', ['instagram.com'], ['com.instagram.android']),
  Site('TikTok', ['tiktok.com'], ['com.zhiliaoapp.musically']),
  Site(
    'Facebook',
    ['facebook.com'],
    ['com.facebook.katana', 'com.facebook.lite'],
  ),
  // Image search is a page on google.com; androidlib blocks it whenever
  // images.google.com is blocked.
  Site(
    'Google Images',
    ['images.google.com'],
    [],
    note: 'image search on google.com',
  ),
  Site(
    'Adult sites',
    [adultSitesId],
    [],
    note: 'porn sites: a list of 76,000+, and any with porn in the name',
  ),
];
