"""Parse a "Top Stories" component.

These components contain links to news articles and often feature an image.
Sometimes the subcomponents are stacked vertically, and sometimes they are
stacked horizontally and feature a larger image, resembling the video
component.
"""

import bs4

from ..utils import (
    Selector,
    find_all_divs,
    find_children,
    get_link,
    get_text,
    get_text_by_selectors,
)


def parse_top_stories(cmpt: bs4.element.Tag, ctype: str = "top_stories") -> list:
    divs: list = []
    divs.extend(find_all_divs(cmpt, "g-inner-card"))  # Top Stories
    divs.extend(find_children(cmpt, "div", {"class": "qmv19b"}))  # Top Stories
    divs.extend(find_all_divs(cmpt, "div", {"class": "IJl0Z"}))  # Top Stories
    divs.extend(find_all_divs(cmpt, "div", {"class": "JJZKK"}))  # Perspectives

    if not divs:
        # Modern Perspectives: every carousel item is role=listitem (covers both
        # standard cards and embedded tweets, including AI-themed sub-carousels).
        divs.extend(cmpt.find_all(attrs={"role": "listitem"}))

    if not divs:
        # Older Top Stories vertical layout
        link_divs = find_all_divs(cmpt, "a", {"class": "WlydOe"})
        divs.extend([div.parent for div in link_divs])

    divs = list(filter(None, divs))

    if divs:
        return [parse_top_story(div, ctype, i) for i, div in enumerate(divs)]
    else:
        return [{"type": ctype, "sub_rank": 0, "error": "No subcomponents found"}]


def parse_top_story(sub: bs4.element.Tag, ctype: str, sub_rank: int = 0) -> dict:
    title_selectors = [
        Selector("div", {"class": "n0jPhd"}),  # Top Stories
        Selector("div", {"class": "eAaXgc"}),  # Perspectives
        Selector("div", {"class": "xcQxib"}),  # Perspectives - embedded tweet text
    ]
    return {
        "type": ctype,
        "sub_rank": sub_rank,
        "title": get_text_by_selectors(sub, title_selectors),
        "url": get_link(sub, key="href"),
        "text": get_text(sub, "div", {"class": "GI74Re"}),
        "cite": get_cite(sub),
    }


def get_cite(sub: bs4.element.Tag) -> str | None:
    div_cite = sub.find("div", {"class": "Dx69l"})
    tweet_cite = sub.find("div", {"class": "Du2Vwd"})
    img_cite = sub.find("g-img", {"class": "sL0zmc"})
    span_cite = sub.find("g-img", {"class": "QyR1Ze"})

    cite: str | None = None
    if div_cite:
        # Perspectives
        cite = get_text(sub, "div", {"class": "Dx69l"})

    elif tweet_cite:
        # Perspectives - embedded tweet ("{username} · X")
        cite = get_text(sub, "div", {"class": "Du2Vwd"})

    elif img_cite:
        # Top Stories — image cite, get "alt" image text
        img = img_cite.find("img")
        if img and "alt" in img.attrs:
            cite = str(img.attrs["alt"])
    elif span_cite:
        cite = get_text(sub, "span")
    else:
        cite = get_text(sub, "cite")
    return cite


def get_top_story_details(sub: bs4.element.Tag) -> dict:
    details: dict = {}
    details["img_url"] = get_img_url(sub)
    details["orient"] = "v" if sub.find("span", {"class": "uaCsqe"}) else "h"
    details["live_stamp"] = True if sub.find("span", {"class": "EugGe"}) else False
    return details


def get_img_url(soup: bs4.element.Tag) -> str | None:
    img = soup.find("img")
    if img and "data-src" in img.attrs:
        return str(img.attrs["data-src"])
    return None
