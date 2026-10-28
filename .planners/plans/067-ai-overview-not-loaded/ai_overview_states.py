"""Plan 067 repro: the AI overview's state markers, per capture.

For each SERP with an AI overview row, prints the parsed sub_type, whether the
body container (``div.mZJni``) is present, and, for each decline message, the
ancestor that hides it. Reads the committed fixture corpus, plus any HTML files
given as arguments.

    uv run python .planners/plans/067-ai-overview-not-loaded/ai_overview_states.py [capture.html ...]
"""

import bz2
import sys
from pathlib import Path

import orjson

import WebSearcher as ws
from WebSearcher import utils

CORPUS = Path("tests/fixtures/serps.json.bz2")
DECLINE_PREFIXES = ("An AI Overview is not available", "Can't generate an AI overview")


def hidden_by(node) -> str:
    """The first ancestor-or-self that hides ``node``, or "shown"."""
    cur = node
    while cur is not None and cur.tag != "html":
        attrs = cur.attrs
        style = (attrs.get("style") or "").replace(" ", "")
        if "display:none" in style:
            return f"display:none on {cur.tag}.{attrs.get('class')}"
        if attrs.get("aria-hidden") == "true" or "hidden" in attrs:
            return f"hidden on {cur.tag}.{attrs.get('class')}"
        cur = cur.parent
    return "shown"


def report(name: str, html: str) -> None:
    rows = [r for r in ws.parse_serp(html)["results"] if r["type"] == "ai_overview"]
    if not rows:
        return
    soup = utils.make_soup(html)
    declines = [
        (text[:32], hidden_by(n))
        for n in soup.css("div, span")
        if (text := (n.text(deep=False) or "").strip()).startswith(DECLINE_PREFIXES)
    ]
    print(
        f"{name[:55]:55} sub_type={rows[0]['sub_type']:11} "
        f"body={soup.css_first('div.mZJni') is not None!s:5} declines={declines}"
    )


def main() -> None:
    with bz2.open(CORPUS) as f:
        for line in f:
            r = orjson.loads(line)
            report(f"corpus {r.get('method') or '?'} {r['qry']}", r["html"])
    for path in sys.argv[1:]:
        report(path, Path(path).read_text())


if __name__ == "__main__":
    main()
