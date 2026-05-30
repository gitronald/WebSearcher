"""Parse a "Local Results" component.

An embedded map followed by vertically stacked locations — typically
businesses relevant to the query, with rating, contact, and address details.
"""

import re

from selectolax.lexbor import LexborNode as Node

from .._slx import class_tokens, get_text, subtree_css, subtree_first
from ..utils import slugify


def parse_local_results(elem) -> list:
    node: Node = elem
    # bs4 find_all is descendants-only; elem itself may carry ``VkpGBb`` and must
    # not be its own first sub-result.
    subs = subtree_css(node, "div.VkpGBb")
    parsed_list = [parse_local_result(sub, sub_rank) for sub_rank, sub in enumerate(subs)]
    if parsed_list:
        # First non-empty header becomes the sub_type (e.g. "Places" -> "places")
        header = None
        for sel in ('h2[role="heading"]', 'div[aria-level="2"][role="heading"]'):
            found = subtree_first(node, sel)
            text = get_text(found, " ") if found is not None else None
            if text:
                header = text
                break
        if header:
            header_lower = header.lower()
            sub_type = (
                "results_for" if header_lower.startswith("results for") else slugify(header_lower)
            )
            for parsed in parsed_list:
                parsed["sub_type"] = sub_type
                # Preserve the raw component header (the sub_type slug is lossy
                # and the per-result title is the business name, not this).
                details = parsed.get("details")
                if isinstance(details, dict):
                    details["heading"] = header

        return parsed_list
    return [
        {
            "type": "local_results",
            "sub_rank": 0,
            "text": get_text(node.css_first("div.n6tePd"), " "),  # No results message
        }
    ]


def parse_local_result(sub: Node, sub_rank: int = 0) -> dict:
    parsed: dict = {"type": "local_results", "sub_rank": sub_rank}
    parsed["title"] = get_text(sub.css_first("div.dbg0pd"), " ")

    links_dict = _link_text_to_url(sub)
    parsed["url"] = links_dict.get("website")

    text = get_text(sub.css_first("div.rllt__details"), separator="<|>")
    label = get_text(sub.css_first("span.X0w5lc"), " ")
    parsed["text"] = f"{text} <label>{label}</label>" if label else text
    parsed["details"] = parse_local_details(sub, links_dict)
    return parsed


def parse_local_details(sub: Node, links_dict: dict[str, str]) -> dict:
    details: dict = {"type": "place"}
    rllt = sub.css_first(".rllt__details")
    if rllt is not None:
        # ``find_all("div", recursive=False)``: direct element children only.
        for row in rllt.iter(include_text=False):
            if row.tag != "div":
                continue
            cls = class_tokens(row)
            if "dbg0pd" in cls:
                continue  # title; already extracted to top level
            if "pJ3Ci" in cls:
                snippet = (get_text(row, " ", strip=True) or "").strip('"').strip()
                if snippet:
                    details["review_snippet"] = snippet
                continue
            _classify_row(get_text(row, " ", strip=True) or "", details)

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


def _link_text_to_url(sub: Node) -> dict[str, str]:
    """Pull the well-known utility links out of a local-results card.

    Keys off stable structural classes (locale-independent) rather than the
    visible anchor text -- the old text-keyed lookup missed
    ``website``/``directions`` on localized SERPs and broke whenever
    ``get_text(strip=True)`` left stray whitespace on the key.
    """
    out: dict[str, str] = {}
    website = sub.css_first("a.L48Cpd")
    if website is not None and website.attributes.get("href"):
        out["website"] = str(website.attributes["href"])
    # A card can carry several ``a.VDgVie`` anchors (e.g. a "Schedule"/booking
    # button alongside "Directions"); the Directions button is the one also
    # tagged ``Q7PwXb`` (the booking button uses ``pYH8Dd``). Keying off the
    # class is locale-independent and still works for sponsored cards whose
    # Directions href is an ``/aclk`` ad redirect rather than ``/maps/dir``.
    directions = sub.css_first("a.Q7PwXb.VDgVie")
    if directions is not None and directions.attributes.get("href"):
        out["directions"] = str(directions.attributes["href"])
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
