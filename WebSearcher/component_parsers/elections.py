"""Parse the election widgets Google embeds in whole-page knowledge panels.

On election queries the ``kp-wholepage`` tab is a mini-SERP that, besides
organics, carries specialized election blocks:

- ``election_dates`` -- a calendar of upcoming primary/general election dates
  ("Election dates - Primaries - <state>", "From <source> and others <range>").
- ``election_results`` -- a live results tracker ("Election results for the …
  are updated live …") or a "Presidential primary results - <state>" panel.
- ``election_resources`` -- an official "Election resources - <state>" panel of
  voter links (register, where/how to vote, …).

Each is classified by its heading via :class:`ClassifyMainHeader`. The parsers
capture the panel heading plus its outbound resource links; the live vote tallies
are intentionally not captured (volatile, and not what an audit keys on).
"""

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text
from ._common import parse_alink_list


def _panel_heading(node: Node) -> str | None:
    heading = node.css_first('[role="heading"], h1, h2, h3')
    return get_text(heading, " ", strip=True) if heading is not None else None


def _resource_links(node: Node) -> list[dict]:
    """Outbound (http) links in the panel, skipping UI chrome (feedback/menu
    actions use ``javascript:``/fragment hrefs)."""
    links = [a for a in node.css("a") if str(a.attributes.get("href", "")).startswith("http")]
    return parse_alink_list(links)


def _parse_election_panel(node: Node, type_name: str) -> list:
    items = _resource_links(node)
    return [
        {
            "type": type_name,
            "sub_rank": 0,
            "title": _panel_heading(node),
            "details": {"type": "hyperlinks", "items": items} if items else None,
        }
    ]


def parse_election_dates(elem) -> list:
    return _parse_election_panel(elem, "election_dates")


def parse_election_results(elem) -> list:
    return _parse_election_panel(elem, "election_results")


def parse_election_resources(elem) -> list:
    return _parse_election_panel(elem, "election_resources")
