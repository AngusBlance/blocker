"""The "Adult sites" filter on the Mac: its own section of /etc/hosts.

Like most filters it combines a block list with forced SafeSearch (filters
that only match keywords block health pages too, Richardson et al., JAMA
2002):

- every name in adult-domains.txt (from StevenBlack/hosts; Android ships
  the same file);
- Google search pinned to forcesafesearch.google.com, the address Google
  documents for networks that enforce SafeSearch, so explicit results and
  thumbnails are filtered in every browser.

The Chrome extension adds what a hosts file can't: any site with "porn" in
its name, and the adult-only top-level domains (.xxx, .porn, .adult, .sex).
These names never go to the extension's block rules: there are far more of
them than Chrome allows.
"""

from pathlib import Path
from typing import List

from .schedule_helper import valid_hostname

LIST_FILE = Path(__file__).resolve().parent / "adult-domains.txt"
BEGIN = "# BLOCKER-ADULT-BEGIN"
END = "# BLOCKER-ADULT-END"

# support.google.com/websearch/answer/186669
SAFESEARCH_V4 = "216.239.38.120"
SAFESEARCH_V6 = "2001:4860:4802:32::78"
GOOGLE_HOSTS = ("google.com", "www.google.com", "google.co.uk", "www.google.co.uk")


def load_names(path: Path = LIST_FILE) -> List[str]:
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().lower()
        if line and not line.startswith("#") and valid_hostname(line):
            names.append(line)
    return names


def section(names: List[str]) -> List[str]:
    lines = [BEGIN]
    for host in GOOGLE_HOSTS:
        lines += [f"{SAFESEARCH_V4} {host}", f"{SAFESEARCH_V6} {host}"]
    for name in names:
        lines += [f"127.0.0.1 {name}", f"::1 {name}"]
    return [*lines, END]


def without_section(lines: List[str]) -> List[str]:
    """Lines outside the section. An unmatched BEGIN runs to the end."""
    out, inside = [], False
    for line in lines:
        if line == BEGIN:
            inside = True
        elif line == END:
            inside = False
        elif not inside:
            out.append(line)
    return out


def is_on(content: str) -> bool:
    return BEGIN in content.splitlines()


def turned_on(content: str, names: List[str]) -> str:
    return "\n".join([*without_section(content.splitlines()), *section(names)]) + "\n"


def turned_off(content: str) -> str:
    lines = without_section(content.splitlines())
    return "\n".join(lines) + "\n" if lines else ""
