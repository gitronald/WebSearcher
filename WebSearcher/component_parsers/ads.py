"""Parsers for ad components

Changelog
---------
2024-05-08:
- added new div class for text field
- added labels (e.g., "Provides abortions") from <span class="mXsQRe">, appended to text field

2025-04-27: added carousel sub_type, global parsed output

"""

from typing import Any

import bs4

from .. import utils
from ..utils import Selector
from .shopping_ads import parse_shopping_ads

_SUBTYPE_CLASSIFICATIONS: dict[str, Selector] = {
    "legacy": Selector("div", {"class": "ad_cclk"}),
    "local_service": Selector("gls-profile-entrypoint"),
    "secondary": Selector("div", {"class": "d5oMvf"}),
    "shopping": Selector("div", {"class": "commercial-unit-desktop-top"}),
    "standard": Selector("div", {"class": "uEierd"}),
    "carousel": Selector("g-scrolling-carousel"),
}


def classify_ad_type(cmpt: bs4.element.Tag) -> str:
    """Classify the type of ad component"""
    for label, sel in _SUBTYPE_CLASSIFICATIONS.items():
        if sel.name and utils.find_all_divs(cmpt, sel.name, sel.attrs):
            return label
    return "unknown"


def parse_ads(cmpt: bs4.element.Tag) -> list:
    """Parse ads from ad component"""

    subtype_parsers = {
        "legacy": parse_ad_legacy,
        "local_service": parse_ad_local_service,
        "secondary": parse_ad_secondary,
        "shopping": parse_ad_shopping,
        "standard": parse_ad_standard,
        "carousel": parse_ad_carousel,
    }
    sub_type = classify_ad_type(cmpt)
    parser = subtype_parsers.get(sub_type)
    return parser(cmpt) if parser else []


# ------------------------------------------------------------------------------


def parse_ad_legacy(cmpt: bs4.element.Tag) -> list:

    def _parse_ad_legacy(cmpt: bs4.element.Tag) -> list:
        subs = cmpt.find_all("li", {"class": "ads-ad"})
        return [_parse_ad_legacy_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

    def _parse_ad_legacy_sub(sub: bs4.element.Tag, sub_rank: int) -> dict:
        header = sub.find("div", {"class": "ad_cclk"})
        return {
            "type": "ad",
            "sub_type": "legacy",
            "sub_rank": sub_rank,
            "title": utils.get_text(header, "h3"),
            "url": utils.get_text(header, "cite"),
            "cite": None,
            "text": utils.get_text(sub, "div", {"class": "ads-creative"}),
            "details": _parse_ad_legacy_sub_details(sub),
        }

    def _parse_ad_legacy_sub_details(sub: bs4.element.Tag) -> dict | None:
        items = []
        ulist = sub.find("ul")
        if ulist:
            items = [li.get_text(separator=" ") for li in ulist.find_all("li")]
        return {"type": "text", "items": items} if items else None

    return _parse_ad_legacy(cmpt)


# ------------------------------------------------------------------------------


def parse_ad_local_service(cmpt: bs4.element.Tag) -> list:
    """Parse local service ads (gls-profile-entrypoint elements)"""

    def _parse_profile(profile: bs4.element.Tag, sub_rank: int) -> dict:
        title = utils.get_text(profile, "span", {"class": "bk5vhd"})
        url = utils.get_link(profile)

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


def parse_ad_secondary(cmpt: bs4.element.Tag) -> list:

    def _parse_ad_secondary(cmpt: bs4.element.Tag) -> list:
        subs = cmpt.find_all("li", {"class": "ads-fr"})
        return [_parse_ad_secondary_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

    def _parse_ad_secondary_sub(sub: bs4.element.Tag, sub_rank: int) -> dict:
        return {
            "type": "ad",
            "sub_type": "secondary",
            "sub_rank": sub_rank,
            "title": utils.get_text(sub, "div", {"role": "heading"}),
            "url": _parse_ad_secondary_sub_url(sub),
            "cite": utils.get_text(sub, "span", {"class": "gBIQub"}),
            "text": _parse_ad_secondary_sub_text(sub),
            "details": _parse_ad_secondary_sub_details(sub),
        }

    def _parse_ad_secondary_sub_url(sub: bs4.element.Tag) -> str:
        url_div = utils.get_div(sub, "div", {"class": "d5oMvf"})
        if not isinstance(url_div, bs4.element.Tag):
            return ""
        return utils.get_link(url_div) or ""

    def _parse_ad_secondary_sub_text(sub) -> str:
        text_divs = sub.find_all("div", {"class": "yDYNvb"})
        return "|".join([d.text for d in text_divs]) if text_divs else ""

    def _parse_ad_secondary_sub_details(sub: bs4.element.Tag) -> dict | None:
        selectors: list[dict[str, Any]] = [{"role": "list"}, {"class": "bOeY0b"}]
        for selector in selectors:
            details_section = sub.find("div", attrs=selector)
            if details_section:
                urls = utils.get_link_list(details_section)
                if urls:
                    return {"type": "links", "items": urls}
                return None
        return None

    return _parse_ad_secondary(cmpt)


# ------------------------------------------------------------------------------


def parse_ad_shopping(cmpt: bs4.element.Tag) -> list:
    """Parse shopping ads from component"""
    subs = utils.find_all_divs(cmpt, "div", {"class": "commercial-unit-desktop-top"})
    parsed_list = []
    for sub in subs:
        parsed_list.extend(parse_shopping_ads(sub))
    return parsed_list


# ------------------------------------------------------------------------------


def parse_ad_standard(cmpt: bs4.element.Tag) -> list:
    """Parse standard ads from component"""

    def _parse_ad_standard_sub(sub: bs4.element.Tag, sub_rank: int = 0) -> dict:

        def _parse_ad_standard_text(sub: bs4.element.Tag) -> str:
            selectors = [
                ("div", {"class": "yDYNvb"}),
                ("div", {"class": "Va3FIb"}),
            ]
            text = utils.get_text_by_selectors(sub, selectors) or ""
            label = utils.get_text(sub, "span", {"class": "mXsQRe"})
            return f"{text} <label>{label}</label>" if label else text

        submenu = parse_ad_menu(sub)
        sub_type = "submenu" if submenu else "standard"
        return {
            "type": "ad",
            "sub_type": sub_type,
            "sub_rank": sub_rank,
            "title": utils.get_text(sub, "div", {"role": "heading"}),
            "url": utils.get_link(sub, {"class": "sVXRqc"}),
            "cite": utils.get_text(sub, "span", {"role": "text"}),
            "text": _parse_ad_standard_text(sub),
            "details": submenu,
        }

    subs = [
        s
        for s in utils.find_all_divs(cmpt, "div", {"class": "uEierd"})
        if isinstance(s, bs4.element.Tag)
    ]
    return [_parse_ad_standard_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def parse_ad_menu(sub: bs4.element.Tag) -> dict | None:
    """Parse menu items for a large ad with additional subresults"""

    items = []

    # Format 1: MhgNwc items with MUxGbd sub-divs
    menu_items = sub.find_all("div", {"class": "MhgNwc"})
    for item in menu_items:
        parsed_item = {"url": "", "title": "", "text": ""}
        item_divs = item.find_all("div", {"class": "MUxGbd"})
        for div in item_divs:
            if utils.check_dict_value(div.attrs, "role", "listitem"):
                parsed_item["url"] = utils.get_link(div) or ""
                parsed_item["title"] = utils.get_text(div) or ""
            else:
                parsed_item["text"] = utils.get_text(div) or ""
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


def parse_ad_carousel(
    cmpt: bs4.element.Tag, sub_type: str = "carousel", filter_visible: bool = True
) -> list:

    def is_visible_div(sub: bs4.element.Tag) -> bool:
        """Check if carousel div is visible"""
        return not (sub.has_attr("data-has-shown") and sub["data-has-shown"] == "false")

    def is_visible_card(sub: bs4.element.Tag) -> bool:
        """Check if carousel card is visible"""
        return not (sub.has_attr("data-viewurl") and sub["data-viewurl"])

    def parse_ad_carousel_div(sub: bs4.element.Tag, sub_type: str, sub_rank: int) -> dict:
        """Parse ad carousel div, seen 2025-02-06"""
        return {
            "type": "ad",
            "sub_type": sub_type,
            "sub_rank": sub_rank,
            "title": utils.get_text(sub, "div", {"class": "e7SMre"}),
            "url": utils.get_link(sub),
            "text": utils.get_text(sub, "div", {"class": "vrAZpb"}),
            "cite": utils.get_text(sub, "div", {"class": "zpIwr"}),
        }

    def parse_ad_carousel_card(sub: bs4.element.Tag, sub_type: str, sub_rank: int) -> dict:
        """Parse ad carousel card, seen 2024-09-21"""
        return {
            "type": "ad",
            "sub_type": sub_type,
            "sub_rank": sub_rank,
            "title": utils.get_text(sub, "div", {"class": "gCv54b"}),
            "url": utils.get_link(sub, {"class": "KTsHxd"}),
            "text": utils.get_text(sub, "div", {"class": "VHpBje"}),
            "cite": utils.get_text(sub, "div", {"class": "j958Pd"}),
        }

    # Possible ad carousel item types
    output_list = []
    ad_carousel = cmpt.find("g-scrolling-carousel")
    if ad_carousel:
        ad_carousel_types = {
            "carousel_card": utils.find_all_divs(ad_carousel, name="g-inner-card"),
            "carousel_div": utils.find_all_divs(ad_carousel, name="div", attrs={"class": "ZPze1e"}),
        }

        for ad_carousel_type, sub_cmpts in ad_carousel_types.items():
            if not sub_cmpts:
                continue
            for sub_rank, sub in enumerate(sub_cmpts):
                if not isinstance(sub, bs4.element.Tag):
                    continue
                if ad_carousel_type == "carousel_card":
                    if filter_visible and not is_visible_card(sub):
                        continue
                    output_list.append(parse_ad_carousel_card(sub, sub_type, sub_rank))
                elif ad_carousel_type == "carousel_div":
                    if filter_visible and not is_visible_div(sub):
                        continue
                    output_list.append(parse_ad_carousel_div(sub, sub_type, sub_rank))

    return output_list
