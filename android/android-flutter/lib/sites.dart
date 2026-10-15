// Same sites as blocklib/domain.py on the Mac, grouped by site.
// Subdomains (m.youtube.com) are covered by the parent domain on Android.
// `apps` are each site's Android app, blocked along with the site.
class Site {
  const Site(this.name, this.domains, this.apps);

  final String name;
  final List<String> domains;
  final List<String> apps;
}

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
];
