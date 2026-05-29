"""Parse ad components.

Six layouts dispatched by classify_ad_type: legacy text ads, local-service
profile cards, secondary text ads, shopping ads, standard text ads (with
optional submenu sitelinks), and the horizontal sponsored carousel.
"""

from typing import Any

from selectolax.parser import Node

from ..utils import (
    Selector,
    check_dict_value,
    find_all_divs,
    get_div,
    get_link,
    get_link_list,
    get_text,
    get_text_by_selectors,
)
from .shopping_ads import parse_shopping_ads

AD_SUBTYPE_SELECTORS: dict[str, Selector] = {
    "legacy": Selector("div", {"class": "ad_cclk"}),
    "local_service": Selector("gls-profile-entrypoint"),
    "secondary": Selector("div", {"class": "d5oMvf"}),
    "shopping": Selector("div", {"class": "commercial-unit-desktop-top"}),
    "standard": Selector("div", {"class": "uEierd"}),
    "carousel": Selector("g-scrolling-carousel"),
}


def classify_ad_type(cmpt: Node) -> str:
    for label, sel in AD_SUBTYPE_SELECTORS.items():
        if sel.name and cmpt.find(sel.name, attrs=sel.attrs):
            return label
    return "unknown"


def parse_ads(cmpt: Node) -> list:
    """Parse every ad sub-type present in the component.

    A single #tads element can host more than one ad layout (e.g. a shopping
    carousel above a standard text ad). Walk through every selector and
    aggregate results so no ad gets dropped.
    """
    subtype_parsers = {
        "legacy": parse_ad_legacy,
        "local_service": parse_ad_local_service,
        "secondary": parse_ad_secondary,
        "shopping": parse_ad_shopping,
        "standard": parse_ad_standard,
        "carousel": parse_ad_carousel,
    }
    parsed: list = []
    for label, sel in AD_SUBTYPE_SELECTORS.items():
        if sel.name and cmpt.find(sel.name, attrs=sel.attrs):
            parser = subtype_parsers.get(label)
            if parser:
                parsed.extend(parser(cmpt))
    return parsed


# ------------------------------------------------------------------------------


def parse_ad_legacy(cmpt: Node) -> list:

    def _parse_ad_legacy(cmpt: Node) -> list:
        subs = cmpt.find_all("li", {"class": "ads-ad"})
        return [_parse_ad_legacy_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

    def _parse_ad_legacy_sub(sub: Node, sub_rank: int) -> dict:
        header = sub.find("div", {"class": "ad_cclk"})
        return {
            "type": "ad",
            "sub_type": "legacy",
            "sub_rank": sub_rank,
            "title": get_text(header, "h3"),
            "url": get_text(header, "cite"),
            "cite": None,
            "text": get_text(sub, "div", {"class": "ads-creative"}),
            "details": _parse_ad_legacy_sub_details(sub),
        }

    def _parse_ad_legacy_sub_details(sub: Node) -> dict | None:
        items = []
        ulist = sub.find("ul")
        if ulist:
            items = [li.get_text(separator=" ") for li in ulist.find_all("li")]
        return {"type": "text", "items": items} if items else None

    return _parse_ad_legacy(cmpt)


# ------------------------------------------------------------------------------


def parse_ad_local_service(cmpt: Node) -> list:
    # Local-service ads are gls-profile-entrypoint elements
    def _parse_profile(profile: Node, sub_rank: int) -> dict:
        title = get_text(profile, "span", {"class": "bk5vhd"})
        url = get_link(profile)

        detail_rows = profile.find_all("div", {"class": "P4vvKf"})
        text = (
            " · ".join(row.get_text(" ", strip=True) for row in detail_rows)
            if list(detail_rows)
            else None
        )

        details = None
        rating_span = profile.find("span", attrs={"aria-label": True})
        if rating_span:
            details = {"type": "text", "items": [rating_span["aria-label"]]}

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

    profiles = cmpt.find_all("gls-profile-entrypoint")
    return [_parse_profile(p, i) for i, p in enumerate(profiles)]


# ------------------------------------------------------------------------------


def parse_ad_secondary(cmpt: Node) -> list:

    def _parse_ad_secondary(cmpt: Node) -> list:
        subs = cmpt.find_all("li", {"class": "ads-fr"})
        return [_parse_ad_secondary_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

    def _parse_ad_secondary_sub(sub: Node, sub_rank: int) -> dict:
        return {
            "type": "ad",
            "sub_type": "secondary",
            "sub_rank": sub_rank,
            "title": get_text(sub, "div", {"role": "heading"}),
            "url": _parse_ad_secondary_sub_url(sub),
            "cite": get_text(sub, "span", {"class": "gBIQub"}),
            "text": _parse_ad_secondary_sub_text(sub),
            "details": _parse_ad_secondary_sub_details(sub),
        }

    def _parse_ad_secondary_sub_url(sub: Node) -> str:
        url_div = get_div(sub, "div", {"class": "d5oMvf"})
        if not url_div:
            return ""
        return get_link(url_div) or ""

    def _parse_ad_secondary_sub_text(sub) -> str:
        text_divs = sub.find_all("div", {"class": "yDYNvb"})
        return "|".join([d.text for d in text_divs]) if text_divs else ""

    def _parse_ad_secondary_sub_details(sub: Node) -> dict | None:
        selectors: list[dict[str, Any]] = [{"role": "list"}, {"class": "bOeY0b"}]
        for selector in selectors:
            details_section = sub.find("div", attrs=selector)
            if details_section:
                urls = get_link_list(details_section)
                if urls:
                    return {"type": "links", "items": urls}
                return None
        return None

    return _parse_ad_secondary(cmpt)


# ------------------------------------------------------------------------------


def parse_ad_shopping(cmpt: Node) -> list:
    parsed_list = []
    for sub in find_all_divs(cmpt, "div", {"class": "commercial-unit-desktop-top"}):
        parsed_list.extend(parse_shopping_ads(sub))
    return parsed_list


# ------------------------------------------------------------------------------


def parse_ad_standard(cmpt: Node) -> list:
    def _parse_ad_standard_sub(sub: Node, sub_rank: int = 0) -> dict:

        def _parse_ad_standard_text(sub: Node) -> str:
            selectors = [
                Selector("div", {"class": "yDYNvb"}),
                Selector("div", {"class": "Va3FIb"}),
            ]
            text = get_text_by_selectors(sub, selectors) or ""
            label = get_text(sub, "span", {"class": "mXsQRe"})
            return f"{text} <label>{label}</label>" if label else text

        submenu = parse_ad_menu(sub)
        sub_type = "submenu" if submenu else "standard"
        return {
            "type": "ad",
            "sub_type": sub_type,
            "sub_rank": sub_rank,
            "title": get_text(sub, "div", {"role": "heading"}),
            "url": get_link(sub, {"class": "sVXRqc"}),
            "cite": get_text(sub, "span", {"role": "text"}),
            "text": _parse_ad_standard_text(sub),
            "details": submenu,
        }

    subs = find_all_divs(cmpt, "div", {"class": "uEierd"})
    return [_parse_ad_standard_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def parse_ad_menu(sub: Node) -> dict | None:
    # Menu items / sitelinks for a large ad with additional sub-results
    items = []

    # Format 1: MhgNwc items with MUxGbd sub-divs
    menu_items = sub.find_all("div", {"class": "MhgNwc"})
    for item in menu_items:
        parsed_item = {"url": "", "title": "", "text": ""}
        item_divs = item.find_all("div", {"class": "MUxGbd"})
        for div in item_divs:
            if check_dict_value(div.attrs, "role", "listitem"):
                parsed_item["url"] = get_link(div) or ""
                parsed_item["title"] = get_text(div) or ""
            else:
                parsed_item["text"] = get_text(div) or ""
        items.append(parsed_item)

    # Format 2: bOeY0b sitelinks section
    if not items:
        sitelink_div = sub.find("div", {"class": "bOeY0b"})
        if sitelink_div:
            for link in sitelink_div.find_all("a", href=True):
                text = link.get_text(strip=True)
                href = link.get("href", "")
                if text and href:
                    items.append({"url": href, "title": text})

    return {"type": "menu", "items": items} if items else None


# ------------------------------------------------------------------------------


def parse_ad_carousel(cmpt: Node, sub_type: str = "carousel", filter_visible: bool = True) -> list:

    def is_visible_div(sub: Node) -> bool:
        return not (sub.has_attr("data-has-shown") and sub["data-has-shown"] == "false")

    def is_visible_card(sub: Node) -> bool:
        return not (sub.has_attr("data-viewurl") and sub["data-viewurl"])

    def parse_ad_carousel_div(sub: Node, sub_type: str, sub_rank: int) -> dict:
        return {
            "type": "ad",
            "sub_type": sub_type,
            "sub_rank": sub_rank,
            "title": get_text(sub, "div", {"class": "e7SMre"}),
            "url": get_link(sub),
            "text": get_text(sub, "div", {"class": "vrAZpb"}),
            "cite": get_text(sub, "div", {"class": "zpIwr"}),
        }

    def parse_ad_carousel_card(sub: Node, sub_type: str, sub_rank: int) -> dict:
        return {
            "type": "ad",
            "sub_type": sub_type,
            "sub_rank": sub_rank,
            "title": get_text(sub, "div", {"class": "gCv54b"}),
            "url": get_link(sub, {"class": "KTsHxd"}),
            "text": get_text(sub, "div", {"class": "VHpBje"}),
            "cite": get_text(sub, "div", {"class": "j958Pd"}),
        }

    # Possible ad carousel item types
    output_list = []
    ad_carousel = cmpt.find("g-scrolling-carousel")
    if ad_carousel:
        ad_carousel_types = {
            "carousel_card": find_all_divs(ad_carousel, name="g-inner-card"),
            "carousel_div": find_all_divs(ad_carousel, name="div", attrs={"class": "ZPze1e"}),
        }

        for ad_carousel_type, sub_cmpts in ad_carousel_types.items():
            if not sub_cmpts:
                continue
            for sub_rank, sub in enumerate(sub_cmpts):
                if ad_carousel_type == "carousel_card":
                    if filter_visible and not is_visible_card(sub):
                        continue
                    output_list.append(parse_ad_carousel_card(sub, sub_type, sub_rank))
                elif ad_carousel_type == "carousel_div":
                    if filter_visible and not is_visible_div(sub):
                        continue
                    output_list.append(parse_ad_carousel_div(sub, sub_type, sub_rank))

    return output_list
