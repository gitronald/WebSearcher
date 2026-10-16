"""Follow-up probe: wall time of every text-walker consumer per corpus pass (selectolax 1.0)."""

import bz2
import sys
import time
from collections import Counter

import orjson

import WebSearcher as ws
from WebSearcher import _slx
from WebSearcher.extractors.extractor_main import ExtractorMain

raw = bz2.decompress(open("tests/fixtures/serps.json.bz2", "rb").read())
htmls = [orjson.loads(line)["html"] for line in raw.splitlines() if line.strip()]
secs: Counter[str] = Counter()


def timed(name, fn):
    def inner(*a, **k):
        t0 = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            secs[name] += time.perf_counter() - t0

    return inner


patches = {"has_text": _slx.has_text}
for mod in list(sys.modules.values()):
    for name, fn in patches.items():
        if getattr(mod, name, None) is fn:
            setattr(mod, name, timed(name, fn))
ExtractorMain.is_valid = staticmethod(timed("is_valid", ExtractorMain.is_valid))

ITER = 5
for h in htmls:
    ws.parse_serp(h)
secs.clear()
t0 = time.perf_counter()
for _ in range(ITER):
    for h in htmls:
        ws.parse_serp(h)
total = time.perf_counter() - t0
print(f"pass {total / ITER * 1000:.0f} ms")
for k, v in secs.most_common():
    print(f"{k:10s} {v / ITER * 1000:6.1f} ms/pass  {v / total * 100:4.1f}%")
