"""Regenerates adult-domains.txt from StevenBlack/hosts' porn-only list (MIT;
it merges Clefspeare13/pornhosts, hostsVN adult, Sinfonietta and others).

    python3 macbook/blocklib/scripts/update_adult_domains.py

Keeps only valid hostnames, lowercased and sorted, one per line. The list
already has the www. forms it needs: the Mac writes these names to
/etc/hosts as they are, and Android also blocks their subdomains.
"""

import re
import urllib.request
from datetime import date
from pathlib import Path

SOURCE = (
    "https://raw.githubusercontent.com/StevenBlack/hosts/master/"
    "alternates/porn-only/hosts"
)
OUT = Path(__file__).resolve().parents[1] / "src" / "blocklib" / "adult-domains.txt"

# Same as blocklib.schedule_helper's.
_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_TLD = r"(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})"
_HOSTNAME = re.compile(rf"(?=.{{1,253}}\Z)(?:{_LABEL}\.)+{_TLD}")


def main() -> None:
    with urllib.request.urlopen(SOURCE, timeout=60) as r:
        text = r.read().decode("utf-8")
    names = set()
    for line in text.splitlines():
        parts = line.split("#", 1)[0].split()
        if len(parts) == 2 and parts[0] == "0.0.0.0":
            name = parts[1].lower().rstrip(".")
            if _HOSTNAME.fullmatch(name):
                names.add(name)
    header = [
        '# Adult sites, for the blocker\'s "Adult sites" filter.',
        f"# From {SOURCE}",
        "# (MIT, https://github.com/StevenBlack/hosts/blob/master/license.txt)",
        f"# on {date.today().isoformat()}. Regenerate with blocklib/scripts/update_adult_domains.py.",
    ]
    OUT.write_text("\n".join(header + sorted(names)) + "\n", encoding="utf-8")
    print(f"{len(names)} names -> {OUT}")


if __name__ == "__main__":
    main()
