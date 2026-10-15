"""Follow-up probe: how much parse time does get_text's Python walker cost on selectolax 1.0?"""

import bz2
import sys
import time
from collections import Counter

import orjson

import WebSearcher as ws
from WebSearcher import _slx

raw = bz2.decompress(open("tests/fixtures/serps.json.bz2", "rb").read())
htmls = [orjson.loads(line)["html"] for line in raw.splitlines() if line.strip()]

orig = _slx.get_text
calls: Counter[str] = Counter()
secs: Counter[str] = Counter()


def classify(node, separator, strip):
    if node is None:
        return "none"
    if node.tag in _slx._SKIP_TEXT_TAGS or node.css_first("script,style,template") is not None:
        return "walker:script-style"
    if separator == "" or not strip:
        return "native"
    return f"walker:strip+sep={separator!r}"


def wrapped(node, separator="", strip=False):
    key = classify(node, separator, strip)
    t0 = time.perf_counter()
    out = orig(node, separator, strip)
    secs[key] += time.perf_counter() - t0
    calls[key] += 1
    return out


# get_text is imported by name into many modules; patch every binding.
for mod in list(sys.modules.values()):
    if getattr(mod, "get_text", None) is orig:
        mod.get_text = wrapped

ITER = 5
t0 = time.perf_counter()
for _ in range(ITER):
    for h in htmls:
        ws.parse_serp(h)
total = time.perf_counter() - t0
print(f"total parse {total:.2f}s over {ITER}x{len(htmls)} (includes wrapper overhead)")
for k in sorted(calls, key=lambda k: -secs[k]):
    print(
        f"{k:28s} calls/iter {calls[k] // ITER:7d}  {secs[k] / ITER * 1000:8.1f} ms/iter  {secs[k] / total * 100:5.1f}%"
    )
