"""Plan 059b: show where native skip_empty text differs from the walker."""

import bz2
import sys
from collections import Counter

import orjson
from selectolax.lexbor import LexborHTMLParser

sys.path.insert(0, ".")
from WebSearcher import _slx  # noqa: E402

raw = bz2.decompress(open("tests/fixtures/serps.json.bz2", "rb").read())
htmls = [orjson.loads(line)["html"] for line in raw.splitlines() if line.strip()]
diffs = Counter()
for h in htmls:
    for n in LexborHTMLParser(h).root.css("*"):
        if n.tag in _slx._SKIP_TEXT_TAGS or n.css_first("script,style,template") is not None:
            continue
        w = "|".join(s for s in (f.strip() for f in _slx._iter_text_fragments(n)) if s)
        nat = n.text(deep=True, separator="|", strip=True, skip_empty=True)
        if w != nat:
            i = next((k for k, (a, b) in enumerate(zip(w, nat)) if a != b), min(len(w), len(nat)))
            diffs[(repr(w[max(0, i - 3) : i + 4]), repr(nat[max(0, i - 3) : i + 4]))] += 1
for k, v in diffs.most_common(8):
    print(v, k)
