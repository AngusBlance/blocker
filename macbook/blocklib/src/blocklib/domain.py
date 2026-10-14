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
]


def known_domains() -> list:
    return [replace(d) for d in _KNOWN_DOMAINS]
