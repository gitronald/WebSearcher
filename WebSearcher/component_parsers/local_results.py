"""Parse a "Local Results" component.

An embedded map followed by vertically stacked locations — typically
businesses relevant to the query, with rating, contact, and address details.
"""

import bs4

from .. import utils

_HEADER_SELECTORS = [
    ("h2", {"role": "heading"}),
    ("div", {"aria-level": "2", "role": "heading"}),
]


def parse_local_results(cmpt: bs4.element.Tag) -> list:
    subs = cmpt.find_all("div", {"class": "VkpGBb"})
    parsed_list = [parse_local_result(sub, sub_rank) for sub_rank, sub in enumerate(subs)]
    if parsed_list:
        # First non-empty header becomes the sub_type (e.g. "Places" -> "places")
        header = utils.get_text_by_selectors(cmpt, _HEADER_SELECTORS)
        if header:
            header_lower = header.lower()
            sub_type = (
                "results_for"
                if header_lower.startswith("results for")
                else header_lower.replace(" ", "_")
            )
            for parsed in parsed_list:
                parsed.update({"sub_type": sub_type})

        return parsed_list
    else:
        return [
            {
                "type": "local_results",
                "sub_rank": 0,
                "text": utils.get_text(cmpt, "div", {"class": "n6tePd"}),  # No results message
            }
        ]


def parse_local_result(sub: bs4.element.Tag, sub_rank: int = 0) -> dict:
    parsed: dict = {"type": "local_results", "sub_rank": sub_rank}
    parsed["title"] = utils.get_text(sub, "div", {"class": "dbg0pd"})

    links = [a.attrs["href"] for a in sub.find_all("a") if "href" in a.attrs]
    links_text = [a.text.lower() for a in sub.find_all("a") if "href" in a.attrs]
    links_dict = dict(zip(links_text, links))
    parsed["url"] = links_dict.get("website", None)

    text = utils.get_text(sub, "div", {"class": "rllt__details"}, separator="<|>")
    label = utils.get_text(sub, "span", {"class": "X0w5lc"})
    parsed["text"] = f"{text} <label>{label}</label>" if label else text
    parsed["details"] = parse_local_details(sub)

    return parsed


def parse_local_details(sub: bs4.element.Tag) -> dict:
    local_details: dict = {"type": "ratings"}

    detail_div = sub.find("span", {"class": "rllt__details"})
    detail_divs = detail_div.find_all("div") if detail_div else None

    if detail_divs:
        rating_div = detail_divs[0]
        rating = rating_div.find("span", {"class": "BTtC6e"})
        if rating:
            local_details["rating"] = float(rating.text)
            n_reviews = utils.get_between_parentheses(rating_div.text).replace(",", "")
            local_details["n_reviews"] = int(n_reviews)
        local_details["loc_label"] = rating_div.text.split("·")[-1].strip()

        if len(detail_divs) > 1:
            contact_div = detail_divs[1]
            local_details["contact"] = contact_div.text

    links = [a.attrs["href"] for a in sub.find_all("a") if "href" in a.attrs]
    links_text = [a.text.lower() for a in sub.find_all("a") if "href" in a.attrs]
    links_dict = dict(zip(links_text, links))
    local_details.update(links_dict)
    return local_details
