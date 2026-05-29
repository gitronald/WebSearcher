"""Compare the lxml+BeautifulSoup parse tree against selectolax (lexbor) over the
stored SERP fixtures.

The prerequisite deliverable for plan 026 (selectolax backend exploration). Plan
023 found that lxml parse (~16-18%) and bs4 find/find_all traversal (~60%) are the
two biggest remaining costs in `parse_serp`, and 026 proposes replacing both with
selectolax. The binding constraint is that `parse_serp` output stays
byte-identical (the snapshot suite). The largest unknown is whether lexbor and
lxml build the *same tree* on Google's real markup -- if they don't, the parser's
`find()`/`find_all()` calls would see a different node set and output would drift.

This script quantifies that risk before any rewrite. It does NOT import the
WebSearcher package (so it is unaffected by the pipeline's runtime deps); it
parses each SERP with both backends directly -- mirroring `utils.make_soup`'s
`BeautifulSoup(html, "lxml")` -- and reports:

  1. Structural divergence: per-SERP total element-count and per-tag-name count
     deltas (the broad "different tree" net).
  2. Custom-element focus: Google's `<g-*>` / `<promo-throttler>` style elements,
     the most likely place two HTML5 parsers disagree.
  3. Signal parity: for the exact class/id/tag/attr signals the classifier and
     extractor key on, how many nodes each backend matches. The selectolax query
     is built to be provably equivalent to the bs4 query (class tokens via the CSS
     `[class~="x"]` whitespace-token match == bs4 `class_="x"`), so any count
     delta is a genuine tree divergence, not a selector-semantics artifact.

    uv run python scripts/diff_parsers.py
    uv run python scripts/diff_parsers.py --fixtures tests/fixtures/serps-v0.6.8.json.bz2 --verbose
"""

import bz2
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import orjson
import typer
from bs4 import BeautifulSoup
from selectolax.parser import HTMLParser

app = typer.Typer(add_completion=False)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


# Structural signals the classifier (classifiers/main.py) and extractor
# (extractors/extractor_main.py) actually key on. A divergence here would change a
# real classify/extract decision. kind in {"id", "class", "tag", "attr"}.
@dataclass(frozen=True)
class Probe:
    kind: str
    value: str
    attr: str = ""  # only for kind == "attr"

    @property
    def label(self) -> str:
        if self.kind == "attr":
            return f"[{self.attr}={self.value}]"
        sigil = {"id": "#", "class": ".", "tag": "<>"}[self.kind]
        return f"{sigil}{self.value}"

    def css(self) -> str:
        if self.kind == "id":
            return f'[id="{self.value}"]'
        if self.kind == "class":
            # [class~="x"] matches a whitespace-separated token -- identical
            # semantics to bs4 class_="x", so a count delta is a tree delta.
            return f'[class~="{self.value}"]'
        if self.kind == "tag":
            return self.value
        return f'[{self.attr}="{self.value}"]'

    def bs4_count(self, soup: BeautifulSoup) -> int:
        if self.kind == "id":
            return len(soup.find_all(attrs={"id": self.value}))
        if self.kind == "class":
            return len(soup.find_all(class_=self.value))
        if self.kind == "tag":
            return len(soup.find_all(self.value))
        return len(soup.find_all(attrs={self.attr: self.value}))

    def sx_count(self, tree: HTMLParser) -> int:
        return len(tree.css(self.css()))


PROBES: list[Probe] = [
    # Layout / extraction ids
    *(
        Probe("id", v)
        for v in [
            "rso",
            "rcnt",
            "atvcap",
            "tads",
            "tadsb",
            "tvcap",
            "imagebox_bigimages",
            "iur",
            "kp-wp-tab-overview",
            "kp-wp-tab-SportsStandings",
            "kp-wp-tab-AIRFARES",
        ]
    ),
    # Custom elements (highest tree-divergence risk between HTML5 parsers)
    *(
        Probe("tag", v)
        for v in [
            "g-scrolling-carousel",
            "promo-throttler",
            "product-viewer-group",
            "g-inner-card",
            "block-component",
            "g-accordion",
            "g-tray-header",
            "g-card",
            "g-section-with-header",
            "g-more-link",
            "g-review-stars",
            "g-img",
        ]
    ),
    # Classifier class signals
    *(
        Probe("class", v)
        for v in [
            "g",
            "ULSxyf",
            "MjjYud",
            "hlcw0c",
            "PmEWq",
            "Ww4FFb",
            "IFnjPb",
            "Fzsovc",
            "uzjuFc",
            "lu_map_section",
            "ifM9O",
            "JNkvid",
            "eejeod",
            "Qq3Lb",
            "VkpGBb",
            "yuRUbf",
            "VwiC3b",
            "d4rhi",
            "d86Vh",
            "knowledge-panel",
            "kp-wholepage-osrp",
            "TzHB6b",
            "A6K0A",
            "VibNM",
        ]
    ),
    # Attribute signals
    Probe("attr", "heading", "role"),
    Probe("attr", "apg-product-result", "data-attrid"),
    Probe("attr", "DictionaryHeader", "data-attrid"),
    Probe("attr", "qTdDb", "jscontroller"),
    Probe("attr", "Z2bSc", "jscontroller"),
]


def load_records(fixtures: list[Path], limit: int | None) -> list[dict]:
    records: list[dict] = []
    for path in fixtures:
        with bz2.open(path, "rt") as f:
            records.extend(orjson.loads(line) for line in f)
    return records[:limit] if limit else records


def serp_label(rec: dict) -> str:
    return rec.get("qry") or rec.get("serp_id", "")[:16] or "?"


@dataclass
class SerpDiff:
    label: str
    bs_total: int
    sx_total: int
    tag_deltas: dict[str, int]  # tag -> bs4_count - sx_count (nonzero only)
    probe_deltas: dict[str, int]  # probe.label -> bs4_count - sx_count (nonzero only)


def diff_serp(rec: dict) -> SerpDiff:
    html = rec["html"]
    soup = BeautifulSoup(html, "lxml")  # mirrors utils.make_soup
    tree = HTMLParser(html)

    bs_tags = Counter(t.name for t in soup.find_all(True))
    sx_tags = Counter(n.tag for n in tree.css("*"))
    tag_deltas = {
        tag: bs_tags[tag] - sx_tags[tag]
        for tag in set(bs_tags) | set(sx_tags)
        if bs_tags[tag] != sx_tags[tag]
    }

    probe_deltas: dict[str, int] = {}
    for p in PROBES:
        d = p.bs4_count(soup) - p.sx_count(tree)
        if d != 0:
            probe_deltas[p.label] = d

    return SerpDiff(
        label=serp_label(rec),
        bs_total=sum(bs_tags.values()),
        sx_total=sum(sx_tags.values()),
        tag_deltas=tag_deltas,
        probe_deltas=probe_deltas,
    )


@app.command()
def main(
    fixtures: list[Path] = typer.Option(
        None, "--fixtures", help="bz2 fixture paths (default: all tests/fixtures/serps-*.json.bz2)"
    ),
    limit: int = typer.Option(0, help="Cap number of SERPs (0 = all)"),
    top: int = typer.Option(25, help="Rows in the ranked tables"),
    verbose: bool = typer.Option(False, "--verbose", help="List each diverging SERP's deltas"),
):
    """Diff the lxml+bs4 tree against selectolax over the fixture corpus."""
    paths = fixtures or sorted(FIXTURES_DIR.glob("serps-*.json.bz2"))
    if not paths:
        typer.echo(f"No fixtures found in {FIXTURES_DIR}")
        raise typer.Exit(1)

    records = load_records(paths, limit or None)
    typer.echo(f"Loaded {len(records)} SERPs from {len(paths)} fixture(s):")
    for p in paths:
        typer.echo(f"  {p.name}")

    diffs = [diff_serp(rec) for rec in records]

    report_structural(diffs, top, verbose)
    report_probes(diffs, top)


def report_structural(diffs: list[SerpDiff], top: int, verbose: bool) -> None:
    n = len(diffs)
    total_mismatch = [d for d in diffs if d.bs_total != d.sx_total]
    tag_mismatch = [d for d in diffs if d.tag_deltas]

    typer.echo("\n=== Structural divergence (lxml+bs4 vs selectolax) ===")
    typer.echo(f"  SERPs with differing total element count: {len(total_mismatch)}/{n}")
    typer.echo(f"  SERPs with any per-tag count difference:  {len(tag_mismatch)}/{n}")

    # Tags ranked by summed absolute delta across the corpus.
    summed: Counter[str] = Counter()
    for d in diffs:
        for tag, delta in d.tag_deltas.items():
            summed[tag] += abs(delta)
    if summed:
        typer.echo(f"\n  Top {top} tags by summed |delta| (bs4 - selectolax):")
        for tag, total in summed.most_common(top):
            serps = sum(1 for d in diffs if tag in d.tag_deltas)
            net = sum(d.tag_deltas.get(tag, 0) for d in diffs)
            typer.echo(f"    {tag:<28} sum|d|={total:<6} net={net:<+6} in {serps} SERP(s)")
    else:
        typer.echo("\n  No per-tag count differences anywhere in the corpus.")

    if verbose and tag_mismatch:
        typer.echo("\n  Per-SERP tag deltas:")
        for d in tag_mismatch:
            typer.echo(f"    {d.label!r} (total bs4={d.bs_total} sx={d.sx_total}): {d.tag_deltas}")


def report_probes(diffs: list[SerpDiff], top: int) -> None:
    typer.echo("\n=== Signal parity (classifier/extractor find() targets) ===")
    diverging = {
        label: sum(1 for d in diffs if label in d.probe_deltas)
        for label in (p.label for p in PROBES)
    }
    diverging = {k: v for k, v in diverging.items() if v}
    if not diverging:
        typer.echo("  Every probed signal matches on every SERP -- no query-level divergence.")
        return
    typer.echo(f"  {len(diverging)} of {len(PROBES)} signals diverge on >=1 SERP:")
    for label, serps in sorted(diverging.items(), key=lambda kv: -kv[1])[:top]:
        worst = max((d.probe_deltas.get(label, 0) for d in diffs), key=abs, default=0)
        net = sum(d.probe_deltas.get(label, 0) for d in diffs)
        typer.echo(
            f"    {label:<28} diverges in {serps:>3} SERP(s)  net={net:<+5} worst={worst:+d}"
        )


if __name__ == "__main__":
    app()
