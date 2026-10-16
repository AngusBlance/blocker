from dataclasses import dataclass, replace


@dataclass
class Domain:
    url: str
    name: str
    is_blocked: bool = False


_KNOWN_DOMAINS = [
    Domain("netflix.com", "Netflix"),
    Domain("www.netflix.com", "Netflix"),
    Domain("youtube.com", "YouTube"),
    Domain("www.youtube.com", "YouTube"),
    Domain("m.youtube.com", "YouTube"),
    Domain("googlevideo.com", "YouTube"),
    Domain("www.googlevideo.com", "YouTube"),
    Domain("crunchyroll.com", "Crunchyroll"),
    Domain("www.crunchyroll.com", "Crunchyroll"),
    Domain("instagram.com", "Instagram"),
    Domain("www.instagram.com", "Instagram"),
    Domain("tiktok.com", "TikTok"),
    Domain("www.tiktok.com", "TikTok"),
    Domain("m.tiktok.com", "TikTok"),
    Domain("facebook.com", "Facebook"),
    Domain("www.facebook.com", "Facebook"),
    Domain("m.facebook.com", "Facebook"),
    # Image search on www.google.com (udm=2) is a page, not a host: the
    # Chrome extension blocks it whenever images.google.com is blocked.
    Domain("images.google.com", "Google Images"),
]


def known_domains() -> list:
    return [replace(d) for d in _KNOWN_DOMAINS]
