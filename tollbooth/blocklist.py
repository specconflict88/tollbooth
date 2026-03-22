import ipaddress
import logging
import threading
from bisect import bisect_right
from pathlib import Path
from urllib.request import urlopen

log = logging.getLogger("tollbooth.blocklist")

BLOCKLIST_URL = (
    "https://github.com/tn3w/IPBlocklist" "/releases/latest/download/blocklist.txt"
)


def _parse_line(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    try:
        if "/" in line:
            net = ipaddress.ip_network(line, strict=False)
            return (
                net.version,
                int(net.network_address),
                int(net.broadcast_address),
            )
        if "-" in line:
            a, b = line.split("-", 1)
            start = ipaddress.ip_address(a.strip())
            end = ipaddress.ip_address(b.strip())
            return start.version, int(start), int(end)
        addr = ipaddress.ip_address(line)
        return addr.version, int(addr), int(addr)
    except ValueError:
        return None


def _merge(ranges):
    if not ranges:
        return []
    merged = [list(ranges[0])]
    for start, end in ranges[1:]:
        if start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _load_text(source):
    if source.startswith(("http://", "https://")):
        with urlopen(source) as resp:
            return resp.read().decode()
    return Path(source).read_text()


def parse_blocklist(text):
    v4, v6 = [], []
    for line in text.splitlines():
        result = _parse_line(line)
        if not result:
            continue
        version, start, end = result
        (v4 if version == 4 else v6).append((start, end))
    v4.sort()
    v6.sort()
    return _merge(v4), _merge(v6)


def _contains(starts, ends, val):
    idx = bisect_right(starts, val) - 1
    return idx >= 0 and val <= ends[idx]


class IPBlocklist:
    def __init__(self):
        self._v4_starts: list[int] = []
        self._v4_ends: list[int] = []
        self._v6_starts: list[int] = []
        self._v6_ends: list[int] = []

    def load(self, source=BLOCKLIST_URL):
        text = _load_text(source)
        v4, v6 = parse_blocklist(text)
        self._v4_starts = [r[0] for r in v4]
        self._v4_ends = [r[1] for r in v4]
        self._v6_starts = [r[0] for r in v6]
        self._v6_ends = [r[1] for r in v6]

    def contains(self, ip):
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if addr.version == 4:
            return _contains(
                self._v4_starts,
                self._v4_ends,
                int(addr),
            )
        return _contains(
            self._v6_starts,
            self._v6_ends,
            int(addr),
        )

    def start_updates(self, interval=86400, source=BLOCKLIST_URL):
        def run():
            while True:
                threading.Event().wait(interval)
                try:
                    self.load(source)
                    log.info("Blocklist updated: %d ranges", len(self))
                except Exception:
                    log.warning("Blocklist update failed", exc_info=True)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    def __len__(self):
        return len(self._v4_starts) + len(self._v6_starts)
