"""Follow-up probe: native text() speed on the corpus, run once per selectolax version.

uv run --no-project --with selectolax==<v> --with orjson python <this>"""

import bz2
import importlib.metadata
import time

import orjson
from selectolax.lexbor import LexborHTMLParser

raw = bz2.decompress(open("tests/fixtures/serps.json.bz2", "rb").read())
htmls = [orjson.loads(line)["html"] for line in raw.splitlines() if line.strip()]
roots = [LexborHTMLParser(h).root for h in htmls]
elems = [n for r in roots for n in r.css("div")]
texts = [
    n for r in roots for n in r.css("*") for n in n.iter(include_text=True) if n.tag == "-text"
]


def bench(label, fn, reps):
    best = float("inf")
    for _ in range(5):
        t0 = time.perf_counter()
        for _ in range(reps):
            fn()
        best = min(best, (time.perf_counter() - t0) / reps)
    print(f"  {label:44s} {best * 1000:8.2f} ms")


print(
    "selectolax",
    importlib.metadata.version("selectolax"),
    f"{len(elems)} divs, {len(texts)} text nodes",
)
bench("root.text(deep=True) x102", lambda: [r.text(deep=True) for r in roots], 3)
bench(
    "root.text(deep=True, sep=' ', strip=True) x102",
    lambda: [r.text(deep=True, separator=" ", strip=True) for r in roots],
    3,
)
bench("div.text(deep=True) all divs", lambda: [n.text(deep=True) for n in elems], 1)
bench("text(deep=False) all text nodes", lambda: [n.text(deep=False) for n in texts], 1)
bench("parse (LexborHTMLParser) x102", lambda: [LexborHTMLParser(h).root for h in htmls], 3)
