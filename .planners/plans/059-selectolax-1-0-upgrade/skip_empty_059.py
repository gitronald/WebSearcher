"""Plan 059b: under selectolax 1.0, is get_text's strip+separator slow path equal to
native text(deep=True, separator=s, strip=True, skip_empty=True)? Also checks the
existing fast path still matches the walker under 1.0. Run in an env with the target
selectolax: uv run --no-project --with selectolax==1.0.0 --with orjson python <this>"""

import bz2
import importlib.metadata
import sys
from collections import Counter

import orjson
from selectolax.lexbor import LexborHTMLParser

sys.path.insert(0, ".")
from WebSearcher import _slx  # noqa: E402  (only needs selectolax)

raw = bz2.decompress(open("tests/fixtures/serps.json.bz2", "rb").read())
htmls = [orjson.loads(line)["html"] for line in raw.splitlines() if line.strip()]
print("selectolax", importlib.metadata.version("selectolax"), len(htmls), "SERPs")


def walker(node, sep, strip):
    frags = _slx._iter_text_fragments(node)
    parts = [s for s in (f.strip() for f in frags) if s] if strip else list(frags)
    return sep.join(parts)


stats = Counter()
examples = []
for h in htmls:
    root = LexborHTMLParser(h).root
    for n in root.css("*"):
        if n.tag in _slx._SKIP_TEXT_TAGS or n.css_first("script,style,template") is not None:
            continue
        for sep, strip in ((" ", True), ("|", True), ("", True), (" ", False), ("", False)):
            w = walker(n, sep, strip)
            if strip and sep:
                nat = n.text(deep=True, separator=sep, strip=True, skip_empty=True)
                key = f"skip_empty sep={sep!r}"
            else:
                nat = n.text(deep=True, separator=sep, strip=strip)
                key = f"fast sep={sep!r} strip={strip}"
            stats[key, w == nat] += 1
            if w != nat and len(examples) < 5:
                examples.append((key, n.tag, w[:80], nat[:80]))
for k, v in sorted(stats.items()):
    print(k, v)
for e in examples:
    print(e)
