"""Parse ad components.

Six layouts dispatched by classify_ad_type: legacy text ads, local-service
profile cards, secondary text ads, shopping ads, standard text ads (with
optional submenu sitelinks), and the horizontal sponsored carousel.
"""

from typing import Any

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text, has_text
from .shopping_ads import parse_shopping_ads

# bs4 ``find("div", {"class": "X"})`` -> CSS class selector. The order matters:
# classify_ad_type returns the first label whose selector matches.
AD_SUBTYPE_SELECTORS: dict[str, str] = {
    "legacy": "div.ad_cclk",
    "local_service": "gls-profile-entrypoint",
    "secondary": "div.d5oMvf",
    "shopping": "div.commercial-unit-desktop-top",
    "standard": "div.uEierd",
    "carousel": "g-scrolling-carousel",
}


def classify_ad_type(elem) -> str:
    node: Node = elem
    for label, css in AD_SUBTYPE_SELECTORS.items():
        if node.css_first(css) is not None:
            return label
    return "unknown"


def parse_ads(elem) -> list:
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
        "carousel": parse_ad_carousel,
    }
    parsed: list = []
    for label, css in AD_SUBTYPE_SELECTORS.items():
        if node.css_first(css) is not None:
            parser = subtype_parsers.get(label)
            if parser:
                parsed.extend(parser(node))
    return parsed


# ------------------------------------------------------------------------------


def parse_ad_legacy(elem) -> list:
    node: Node = elem
    subs = list(node.css("li.ads-ad"))
    return [_parse_ad_legacy_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def _parse_ad_legacy_sub(sub: Node, sub_rank: int) -> dict:
    header = sub.css_first("div.ad_cclk")
    h3 = header.css_first("h3") if header is not None else None
    cite_el = header.css_first("cite") if header is not None else None
    creative = sub.css_first("div.ads-creative")
    return {
        "type": "ad",
        "sub_type": "legacy",
        "sub_rank": sub_rank,
        "title": get_text(h3, " ") if h3 is not None else None,
        "url": get_text(cite_el, " ") if cite_el is not None else None,
        "cite": None,
        "text": get_text(creative, " ") if creative is not None else None,
        "details": _parse_ad_legacy_sub_details(sub),
    }


def _parse_ad_legacy_sub_details(sub: Node) -> dict | None:
    ulist = sub.css_first("ul")
    if ulist is None:
        return None
    items = [get_text(li, " ") for li in ulist.css("li")]
    items = [i for i in items if i is not None]
    return {"type": "text", "items": items} if items else None


# ------------------------------------------------------------------------------


def parse_ad_local_service(elem) -> list:
    node: Node = elem
    profiles = list(node.css("gls-profile-entrypoint"))
    return [_parse_local_service_profile(p, i) for i, p in enumerate(profiles)]


def _parse_local_service_profile(profile: Node, sub_rank: int) -> dict:
    title = get_text(profile.css_first("span.bk5vhd"), " ")
    a = profile.css_first("a")
    url = a.attributes.get("href") if a is not None else None

    detail_rows = list(profile.css("div.P4vvKf"))
    text = (
        " · ".join((get_text(row, " ", strip=True) or "") for row in detail_rows)
        if detail_rows
        else None
    )

    details = None
    rating_span = profile.css_first("span[aria-label]")
    if rating_span is not None:
        details = {"type": "text", "items": [rating_span.attributes["aria-label"]]}

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


def parse_ad_secondary(elem) -> list:
    node: Node = elem
    subs = list(node.css("li.ads-fr"))
    return [_parse_ad_secondary_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def _parse_ad_secondary_sub(sub: Node, sub_rank: int) -> dict:
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
    return (a.attributes.get("href") if a is not None else None) or ""


def _parse_ad_secondary_sub_text(sub: Node) -> str:
    text_divs = list(sub.css("div.yDYNvb"))
    return "|".join((get_text(d) or "") for d in text_divs) if text_divs else ""


def _parse_ad_secondary_sub_details(sub: Node) -> dict | None:
    for css in ('div[role="list"]', "div.bOeY0b"):
        details_section = sub.css_first(css)
        if details_section is not None:
            urls = [
                str(a.attributes["href"])
                for a in details_section.css("a")
                if has_text(a) and a.attributes.get("href")
            ]
            if urls:
                return {"type": "links", "items": urls}
            return None
    return None


# ------------------------------------------------------------------------------


def parse_ad_shopping(elem) -> list:
    node: Node = elem
    parsed_list = []
    for sub in node.css("div.commercial-unit-desktop-top"):
        if has_text(sub):
            parsed_list.extend(parse_shopping_ads(sub))
    return parsed_list


# ------------------------------------------------------------------------------


def parse_ad_standard(elem) -> list:
    node: Node = elem
    subs = [d for d in node.css("div.uEierd") if has_text(d)]
    return [_parse_ad_standard_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def _parse_ad_standard_sub(sub: Node, sub_rank: int = 0) -> dict:
    submenu = parse_ad_menu(sub)
    sub_type = "submenu" if submenu else "standard"
    sVXRqc = sub.css_first("a.sVXRqc")
    return {
        "type": "ad",
        "sub_type": sub_type,
        "sub_rank": sub_rank,
        "title": get_text(sub.css_first('div[role="heading"]'), " "),
        "url": sVXRqc.attributes.get("href") if sVXRqc is not None else None,
        "cite": get_text(sub.css_first('span[role="text"]'), " "),
        "text": _parse_ad_standard_text(sub),
        "details": submenu,
    }


def _parse_ad_standard_text(sub: Node) -> str:
    text = ""
    for css in ("div.yDYNvb", "div.Va3FIb"):
        t = get_text(sub.css_first(css), " ")
        if t:
            text = t
            break
    label = get_text(sub.css_first("span.mXsQRe"), " ")
    return f"{text} <label>{label}</label>" if label else text


def parse_ad_menu(sub: Node) -> dict | None:
    """Menu items / sitelinks for a large ad with additional sub-results."""
    items = []

    # Format 1: MhgNwc items with MUxGbd sub-divs
    for item in sub.css("div.MhgNwc"):
        parsed_item: dict[str, Any] = {"url": "", "title": "", "text": ""}
        for div in item.css("div.MUxGbd"):
            if div.attributes.get("role") == "listitem":
                a = div.css_first("a")
                parsed_item["url"] = (a.attributes.get("href") if a is not None else None) or ""
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
                href = link.attributes.get("href", "") or ""
                if text and href:
                    items.append({"url": href, "title": text})

    # Format 3: ynAwRc sitelink anchors (one per Va3FIb wrapper row)
    if not items:
        for link in sub.css("a.ynAwRc"):
            text = get_text(link, " ", strip=True) or ""
            href = link.attributes.get("href", "") or ""
            if text and href:
                items.append({"url": href, "title": text})

    return {"type": "menu", "items": items} if items else None


# ------------------------------------------------------------------------------


def parse_ad_carousel(elem, sub_type: str = "carousel", filter_visible: bool = True) -> list:
    node: Node = elem

    output_list = []
    ad_carousel = node.css_first("g-scrolling-carousel")
    if ad_carousel is None:
        return output_list

    # Possible ad carousel item types -- card layout first, then div fallback.
    carousel_cards = [d for d in ad_carousel.css("g-inner-card") if has_text(d)]
    if carousel_cards:
        for sub_rank, sub in enumerate(carousel_cards):
            if filter_visible and _is_hidden_card(sub):
                continue
            output_list.append(_parse_ad_carousel_card(sub, sub_type, sub_rank))
        return output_list

    carousel_divs = [d for d in ad_carousel.css("div.ZPze1e") if has_text(d)]
    for sub_rank, sub in enumerate(carousel_divs):
        if filter_visible and _is_hidden_div(sub):
            continue
        output_list.append(_parse_ad_carousel_div(sub, sub_type, sub_rank))
    return output_list


def _is_hidden_div(sub: Node) -> bool:
    return sub.attributes.get("data-has-shown") == "false"


def _is_hidden_card(sub: Node) -> bool:
    return bool(sub.attributes.get("data-viewurl"))


def _parse_ad_carousel_div(sub: Node, sub_type: str, sub_rank: int) -> dict:
    a = sub.css_first("a")
    return {
        "type": "ad",
        "sub_type": sub_type,
        "sub_rank": sub_rank,
        "title": get_text(sub.css_first("div.e7SMre"), " "),
        "url": a.attributes.get("href") if a is not None else None,
        "text": get_text(sub.css_first("div.vrAZpb"), " "),
        "cite": get_text(sub.css_first("div.zpIwr"), " "),
    }


def _parse_ad_carousel_card(sub: Node, sub_type: str, sub_rank: int) -> dict:
    a = sub.css_first("a.KTsHxd")
    return {
        "type": "ad",
        "sub_type": sub_type,
        "sub_rank": sub_rank,
        "title": get_text(sub.css_first("div.gCv54b"), " "),
        "url": a.attributes.get("href") if a is not None else None,
        "text": get_text(sub.css_first("div.VHpBje"), " "),
        "cite": get_text(sub.css_first("div.j958Pd"), " "),
    }
