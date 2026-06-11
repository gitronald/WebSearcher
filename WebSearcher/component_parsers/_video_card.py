"""Hidden ``evlb_*`` "About this result" video-card extraction.

Modern Google SERPs pre-render one hidden card per video result -- a
``<div id="evlb_..." style="display:none">`` inside the tile that opens when
the user clicks the tile's ⋮ icon. Each populated card carries a clean title,
source ("YouTube"), channel/uploader, publish date, and thumbnail URL; the
visible tile itself no longer exposes source or duration in the static HTML.
Older SERPs ship empty template stubs under the same ids, so a card only
counts when it yields at least one field.

The cards sit under ``display:none`` ancestors by design -- reading them is a
data-side enrichment and says nothing about visibility, so callers must not
set ``visible`` based on a card hit.
"""

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text


def parse_evlb_card(scope: Node) -> dict | None:
    """Extract video metadata fields from the first populated ``evlb_*`` card
    inside ``scope`` (a video tile), or ``None`` when no card yields a field.

    Thumbnail URLs may be ``data:image/...`` lazy-load placeholders; they are
    captured as-is for downstream filtering.
    """
    for card in scope.css('div[id^="evlb_"]'):
        img = card.css_first("img.aLL3sb")
        fields = {
            "title": get_text(card.css_first("h1.WQWxe"), strip=True),
            "source": get_text(card.css_first("span.KrMNbf"), strip=True),
            "channel": get_text(card.css_first("span.PNsAZd"), strip=True),
            "publish_date": get_text(card.css_first("span.DKsccc"), strip=True),
            "thumbnail_url": img.attributes.get("src") if img is not None else None,
        }
        fields = {k: v for k, v in fields.items() if v}
        if fields:
            return fields
    return None


def evlb_fields_by_tile(root: Node, tiles: list[Node]) -> dict[int, dict]:
    """Card fields keyed by tile ``mem_id``, for tiles whose card sits BESIDE
    them (e.g. ``short_videos`` anchors) in a per-video wrapper
    (``div.WVV5ke``) rather than inside.

    The wrapper search is scoped to ``root`` (the component element) so a card
    can never be borrowed from a neighboring component, and a wrapper only
    pairs with a tile when it contains exactly one of the given tiles -- an
    ambiguous wrapper (e.g. one wrapping a whole carousel) contributes
    nothing. Nested qualifying wrappers resolve to the innermost (document
    order: outer first, inner overwrites)."""
    tile_ids = {t.mem_id for t in tiles}
    fields_by_tile: dict[int, dict] = {}
    for wrapper in root.css("div.WVV5ke"):
        inside = [n.mem_id for n in wrapper.css("*") if n.mem_id in tile_ids]
        if len(inside) != 1:
            continue
        fields = parse_evlb_card(wrapper)
        if fields:
            fields_by_tile[inside[0]] = fields
    return fields_by_tile
