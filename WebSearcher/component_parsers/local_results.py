"""Parse a "Local Results" component.

An embedded map followed by vertically stacked locations — typically
businesses relevant to the query, with rating, contact, and address details.
"""

import re

import bs4

from ..utils import Selector, get_text, get_text_by_selectors


def parse_local_results(cmpt: bs4.element.Tag) -> list:
    subs = cmpt.find_all("div", {"class": "VkpGBb"})
    parsed_list = [parse_local_result(sub, sub_rank) for sub_rank, sub in enumerate(subs)]
    if parsed_list:
        # First non-empty header becomes the sub_type (e.g. "Places" -> "places")
        header_selectors = [
            Selector("h2", {"role": "heading"}),
            Selector("div", {"aria-level": "2", "role": "heading"}),
        ]
        header = get_text_by_selectors(cmpt, header_selectors)
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
                "text": get_text(cmpt, "div", {"class": "n6tePd"}),  # No results message
            }
        ]


def parse_local_result(sub: bs4.element.Tag, sub_rank: int = 0) -> dict:
    parsed: dict = {"type": "local_results", "sub_rank": sub_rank}
    parsed["title"] = get_text(sub, "div", {"class": "dbg0pd"})

    links_dict = _link_text_to_url(sub)
    parsed["url"] = links_dict.get("website")

    text = get_text(sub, "div", {"class": "rllt__details"}, separator="<|>")
    label = get_text(sub, "span", {"class": "X0w5lc"})
    parsed["text"] = f"{text} <label>{label}</label>" if label else text
    parsed["details"] = parse_local_details(sub, links_dict)
    return parsed


def parse_local_details(sub: bs4.element.Tag, links_dict: dict[str, str]) -> dict:
    details: dict = {"type": "place"}
    rllt = sub.find(class_="rllt__details")
    if rllt:
        for row in rllt.find_all("div", recursive=False):
            cls = row.get("class") or []
            if "dbg0pd" in cls:
                continue  # title; already extracted to top level
            if "pJ3Ci" in cls:
                snippet = row.get_text(" ", strip=True).strip('"').strip()
                if snippet:
                    details["review_snippet"] = snippet
                continue
            _classify_row(row.get_text(" ", strip=True), details)

    for key in ("website", "directions"):
        if key in links_dict:
            details[key] = links_dict[key]
    return details


_PHONE_RE = re.compile(r"^\(?\d{3}\)?[\s\-.]\d{3}[\s\-.]\d{4}$|^\+?\d{10,15}$")
_RATING_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*\(([\d,]+)\)$")
_TIME_RE = re.compile(r"^\d{1,2}(:\d{2})?\s*(am|pm)", re.IGNORECASE)
_YEARS_RE = re.compile(r"^\d+\+?\s+years?\s+in\s+business", re.IGNORECASE)
_STREET_RE = re.compile(
    r"\b(St|Ave|Blvd|Rd|Pl|Dr|Ln|Way|Center|Ctr|Pkwy|Sq|Ct|Hwy|Suite|Ste)\b",
    re.IGNORECASE,
)
_HOURS_PREFIX = ("open", "closed", "closes", "opens")


def _link_text_to_url(sub: bs4.element.Tag) -> dict[str, str]:
    out: dict[str, str] = {}
    for a in sub.find_all("a"):
        if "href" not in a.attrs:
            continue
        key = a.get_text(strip=True).lower()
        if key and key not in out:
            out[key] = str(a.attrs["href"])
    return out


def _classify_row(text: str, details: dict) -> None:
    """Classify each `·`-separated part of a local-result row into a detail field."""
    for part in (p.strip() for p in re.split(r"\s*·\s*", text) if p.strip()):
        rating_match = _RATING_RE.match(part)
        if rating_match:
            details["rating"] = float(rating_match.group(1))
            details["n_reviews"] = int(rating_match.group(2).replace(",", ""))
            continue
        if part.lower() == "no reviews":
            details.setdefault("n_reviews", 0)
            continue
        if part.startswith("$"):
            details["price"] = part
            continue
        if _PHONE_RE.match(part):
            details["phone"] = part
            continue
        if _YEARS_RE.match(part):
            details["years_in_business"] = part
            continue
        if any(part.lower().startswith(h) for h in _HOURS_PREFIX) or _TIME_RE.match(part):
            details["hours"] = details["hours"] + " · " + part if "hours" in details else part
            continue
        if "," in part or _STREET_RE.search(part) or re.match(r"^\d+\s+\w", part):
            details["address"] = details["address"] + " · " + part if "address" in details else part
            continue
        details.setdefault("category", part)
