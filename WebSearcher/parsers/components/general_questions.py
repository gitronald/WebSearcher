"""Parse a "General + People Also Ask" hybrid component.

A general result followed by a People Also Ask cluster (typically 3 questions).
The questions ride on the general row's ``details``; when the PAA cluster
yields nothing, the general row keeps its own details (submenu links, ratings)
rather than having them replaced with ``None``.
"""

from typing import Any

from selectolax.lexbor import LexborNode as Node

from .general import parse_general_results
from .people_also_ask import parse_people_also_ask


def parse_general_questions(elem: Node) -> list[dict[str, Any]]:
    parsed_list_general = parse_general_results(elem)
    parsed_list_ppa = parse_people_also_ask(elem)
    general = parsed_list_general[0]
    paa = parsed_list_ppa[0]
    paa_details = paa.get("details")
    if paa_details:
        general["details"] = paa_details
        # Carry the PAA sub_type (e.g. an embedded AI-overview answer) when the
        # general row has none of its own, so the two shapes stay distinguishable.
        if paa.get("sub_type") and not general.get("sub_type"):
            general["sub_type"] = paa["sub_type"]
    general["type"] = "general_questions"
    return parsed_list_general
