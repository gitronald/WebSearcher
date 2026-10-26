"""Parse ad components.

Seven layouts, each detected by a selector in ``AD_SUBTYPE_SELECTORS`` and parsed
by its own function: legacy text ads, local-service profile cards, secondary
text ads, shopping ads, standard text ads (with optional submenu sitelinks),
2026-10 text ads (the standard ad without its ``div.uEierd`` wrapper), and the
horizontal sponsored carousel. ``parse_ads`` runs every layout whose
selector matches, since one ``#tads`` block can host more than one.
"""

from typing import Any

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text, has_text
from .shopping_ads import parse_shopping_ads

# bs4 ``find("div", {"class": "X"})`` -> CSS class selector. Insertion order is
# the order the matching layouts' rows are emitted in.
AD_SUBTYPE_SELECTORS: dict[str, str] = {
    "legacy": "div.ad_cclk",
    "local_service": "gls-profile-entrypoint",
    "secondary": "div.d5oMvf",
    "shopping": "div.commercial-unit-desktop-top",
    "standard": "div.uEierd",
    "text": "div[data-text-ad]",
    "carousel": "g-scrolling-carousel",
}


def parse_ads(elem: Node) -> list[dict[str, Any]]:
    """Parse every ad sub-type present in the component.

    A single #tads element can host more than one ad layout (e.g. a shopping
    carousel above a standard text ad). Walk through every selector and
    aggregate results so no ad gets dropped.
    """
    node: Node = elem
    subtype_parsers = {
        "legacy": parse_ad_legacy,
        "local_service": parse_ad_local_service,
        "secondary": parse_ad_secondary,
        "shopping": parse_ad_shopping,
        "standard": parse_ad_standard,
        "text": parse_ad_text,
        "carousel": parse_ad_carousel,
    }
    parsed: list[dict[str, Any]] = []
    for label, css in AD_SUBTYPE_SELECTORS.items():
        if node.css_first(css) is not None:
            parsed.extend(subtype_parsers[label](node))
    # Each layout parser numbers its own rows from 0, so a block hosting two
    # layouts would repeat sub_rank; renumber across the whole component so
    # (cmpt_rank, sub_rank) stays unique.
    for sub_rank, row in enumerate(parsed):
        row["sub_rank"] = sub_rank
    return parsed


# ------------------------------------------------------------------------------


def parse_ad_legacy(elem: Node) -> list[dict[str, Any]]:
    node: Node = elem
    subs = list(node.css("li.ads-ad"))
    return [_parse_ad_legacy_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def _parse_ad_legacy_sub(sub: Node, sub_rank: int) -> dict[str, Any]:
    header = sub.css_first("div.ad_cclk")
    h3 = header.css_first("h3") if header is not None else None
    cite_el = header.css_first("cite") if header is not None else None
    creative = sub.css_first("div.ads-creative")
    return {
        "type": "ad",
        "sub_type": "legacy",
        "sub_rank": sub_rank,
        "title": get_text(h3, " "),
        "url": get_text(cite_el, " "),
        "cite": None,
        "text": get_text(creative, " "),
        "details": _parse_ad_legacy_sub_details(sub),
    }


def _parse_ad_legacy_sub_details(sub: Node) -> dict[str, Any] | None:
    ulist = sub.css_first("ul")
    if ulist is None:
        return None
    items = [get_text(li, " ") for li in ulist.css("li")]
    items = [i for i in items if i is not None]
    return {"type": "text", "items": items} if items else None


# ------------------------------------------------------------------------------


def parse_ad_local_service(elem: Node) -> list[dict[str, Any]]:
    node: Node = elem
    profiles = list(node.css("gls-profile-entrypoint"))
    return [_parse_local_service_profile(p, i) for i, p in enumerate(profiles)]


def _parse_local_service_profile(profile: Node, sub_rank: int) -> dict[str, Any]:
    title = get_text(profile.css_first("span.bk5vhd"), " ")
    a = profile.css_first("a")
    url = a.attrs.get("href") if a is not None else None

    detail_rows = list(profile.css("div.P4vvKf"))
    text = (
        " · ".join((get_text(row, " ", strip=True) or "") for row in detail_rows)
        if detail_rows
        else None
    )

    details = None
    rating_span = profile.css_first("span[aria-label]")
    if rating_span is not None:
        details = {"type": "text", "items": [rating_span.attrs["aria-label"]]}

    return {
        "type": "ad",
        "sub_type": "local_service",
        "sub_rank": sub_rank,
        "title": title,
        "url": url,
        "cite": None,
        "text": text,
        "details": details,
    }


# ------------------------------------------------------------------------------


def parse_ad_secondary(elem: Node) -> list[dict[str, Any]]:
    node: Node = elem
    subs = list(node.css("li.ads-fr"))
    return [_parse_ad_secondary_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def _parse_ad_secondary_sub(sub: Node, sub_rank: int) -> dict[str, Any]:
    return {
        "type": "ad",
        "sub_type": "secondary",
        "sub_rank": sub_rank,
        "title": get_text(sub.css_first('div[role="heading"]'), " "),
        "url": _parse_ad_secondary_sub_url(sub),
        "cite": get_text(sub.css_first("span.gBIQub"), " "),
        "text": _parse_ad_secondary_sub_text(sub),
        "details": _parse_ad_secondary_sub_details(sub),
    }


def _parse_ad_secondary_sub_url(sub: Node) -> str:
    url_div = sub.css_first("div.d5oMvf")
    if url_div is None:
        return ""
    a = url_div.css_first("a")
    return (a.attrs.get("href") if a is not None else None) or ""


def _parse_ad_secondary_sub_text(sub: Node) -> str:
    text_divs = list(sub.css("div.yDYNvb"))
    return "|".join((get_text(d) or "") for d in text_divs) if text_divs else ""


def _parse_ad_secondary_sub_details(sub: Node) -> dict[str, Any] | None:
    for css in ('div[role="list"]', "div.bOeY0b"):
        details_section = sub.css_first(css)
        if details_section is not None:
            urls = [
                str(a.attrs["href"])
                for a in details_section.css("a")
                if has_text(a) and a.attrs.get("href")
            ]
            if urls:
                return {"type": "links", "items": urls}
            return None
    return None


# ------------------------------------------------------------------------------


def parse_ad_shopping(elem: Node) -> list[dict[str, Any]]:
    node: Node = elem
    parsed_list = []
    for sub in node.css("div.commercial-unit-desktop-top"):
        if has_text(sub):
            parsed_list.extend(parse_shopping_ads(sub))
    return parsed_list


# ------------------------------------------------------------------------------


def parse_ad_standard(elem: Node) -> list[dict[str, Any]]:
    node: Node = elem
    subs = [d for d in node.css("div.uEierd") if has_text(d)]
    return [_parse_ad_standard_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


# Description selectors, first non-empty wins. The 2026-10 text ad puts Va3FIb
# on its heading, so it reads only its own description div.
_STANDARD_TEXT_CSS = ("div.yDYNvb", "div.Va3FIb")
_TEXT_AD_TEXT_CSS = ("div.p4wth",)


def _parse_ad_standard_sub(
    sub: Node, sub_rank: int = 0, text_css: tuple[str, ...] = _STANDARD_TEXT_CSS
) -> dict[str, Any]:
    submenu = parse_ad_menu(sub)
    sub_type = "submenu" if submenu else "standard"
    sVXRqc = sub.css_first("a.sVXRqc")
    return {
        "type": "ad",
        "sub_type": sub_type,
        "sub_rank": sub_rank,
        "title": get_text(sub.css_first('div[role="heading"]'), " "),
        "url": sVXRqc.attrs.get("href") if sVXRqc is not None else None,
        "cite": get_text(sub.css_first('span[role="text"]'), " "),
        "text": _parse_ad_standard_text(sub, text_css),
        "details": submenu,
    }


def _parse_ad_standard_text(sub: Node, text_css: tuple[str, ...]) -> str:
    text = ""
    for css in text_css:
        t = get_text(sub.css_first(css), " ")
        if t:
            text = t
            break
    label = get_text(sub.css_first("span.mXsQRe"), " ")
    return f"{text} <label>{label}</label>" if label else text


def parse_ad_menu(sub: Node) -> dict[str, Any] | None:
    """Menu items / sitelinks for a large ad with additional sub-results."""
    items = []

    # Format 1: MhgNwc items with MUxGbd sub-divs
    for item in sub.css("div.MhgNwc"):
        parsed_item: dict[str, Any] = {"url": "", "title": "", "text": ""}
        for div in item.css("div.MUxGbd"):
            if div.attrs.get("role") == "listitem":
                a = div.css_first("a")
                parsed_item["url"] = (a.attrs.get("href") if a is not None else None) or ""
                parsed_item["title"] = get_text(div, " ") or ""
            else:
                parsed_item["text"] = get_text(div, " ") or ""
        items.append(parsed_item)

    # Format 2: bOeY0b sitelinks section
    if not items:
        sitelink_div = sub.css_first("div.bOeY0b")
        if sitelink_div is not None:
            for link in sitelink_div.css("a[href]"):
                text = get_text(link, strip=True) or ""
                href = link.attrs.get("href", "") or ""
                if text and href:
                    items.append({"url": href, "title": text})

    # Format 3: ynAwRc sitelink anchors (one per Va3FIb wrapper row)
    if not items:
        for link in sub.css("a.ynAwRc"):
            text = get_text(link, " ", strip=True) or ""
            href = link.attrs.get("href", "") or ""
            if text and href:
                items.append({"url": href, "title": text})

    # Format 4: qmaLCb sitelink row (2026-10 text ads)
    if not items:
        for link in sub.css("div.qmaLCb a[href]"):
            text = get_text(link, " ", strip=True) or ""
            href = link.attrs.get("href", "") or ""
            if text and href:
                items.append({"url": href, "title": text})

    return {"type": "menu", "items": items} if items else None


# ------------------------------------------------------------------------------


def parse_ad_text(elem: Node) -> list[dict[str, Any]]:
    """2026-10 text ads: one ``div[data-text-ad]`` per ad, with the standard
    layout's link, heading, and display URL but no ``div.uEierd`` wrapper.

    Older text ads carry ``data-text-ad`` inside that wrapper, so this layout
    yields to ``parse_ad_standard`` whenever one is present; otherwise those ads
    would be parsed twice.
    """
    node: Node = elem
    if node.css_first("div.uEierd") is not None:
        return []
    subs = [d for d in node.css("div[data-text-ad]") if has_text(d)]
    return [
        _parse_ad_standard_sub(sub, sub_rank, _TEXT_AD_TEXT_CSS)
        for sub_rank, sub in enumerate(subs)
    ]


# ------------------------------------------------------------------------------


def parse_ad_carousel(elem: Node) -> list[dict[str, Any]]:
    node: Node = elem
    ad_carousel = node.css_first("g-scrolling-carousel")
    if ad_carousel is None:
        return []

    # Possible ad carousel item types -- card layout first, then div fallback.
    # Hidden (not-yet-shown) items are dropped before numbering so sub_rank
    # stays contiguous.
    carousel_cards = [d for d in ad_carousel.css("g-inner-card") if has_text(d)]
    if carousel_cards:
        visible = [d for d in carousel_cards if not _is_hidden_card(d)]
        return [_parse_ad_carousel_card(sub, sub_rank) for sub_rank, sub in enumerate(visible)]

    carousel_divs = [
        d for d in ad_carousel.css("div.ZPze1e") if has_text(d) and not _is_hidden_div(d)
    ]
    return [_parse_ad_carousel_div(sub, sub_rank) for sub_rank, sub in enumerate(carousel_divs)]


def _is_hidden_div(sub: Node) -> bool:
    return sub.attrs.get("data-has-shown") == "false"


def _is_hidden_card(sub: Node) -> bool:
    return bool(sub.attrs.get("data-viewurl"))


def _parse_ad_carousel_div(sub: Node, sub_rank: int) -> dict[str, Any]:
    a = sub.css_first("a")
    return {
        "type": "ad",
        "sub_type": "carousel",
        "sub_rank": sub_rank,
        "title": get_text(sub.css_first("div.e7SMre"), " "),
        "url": a.attrs.get("href") if a is not None else None,
        "text": get_text(sub.css_first("div.vrAZpb"), " "),
        "cite": get_text(sub.css_first("div.zpIwr"), " "),
    }


def _parse_ad_carousel_card(sub: Node, sub_rank: int) -> dict[str, Any]:
    a = sub.css_first("a.KTsHxd")
    return {
        "type": "ad",
        "sub_type": "carousel",
        "sub_rank": sub_rank,
        "title": get_text(sub.css_first("div.gCv54b"), " "),
        "url": a.attrs.get("href") if a is not None else None,
        "text": get_text(sub.css_first("div.VHpBje"), " "),
        "cite": get_text(sub.css_first("div.j958Pd"), " "),
    }
