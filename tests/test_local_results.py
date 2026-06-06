"""Tests for local_results sub_type categorization (plan 034).

The component header is query-/location-dependent display text. It is mapped to a
closed category set by phrase; headers that match no category leave ``sub_type``
None rather than slugifying free text into a per-query value. The raw header is
preserved losslessly in ``details["heading"]``.
"""

import pytest

from WebSearcher import utils
from WebSearcher.component_parsers.local_results import (
    _LOCAL_RESULTS_CATEGORIES,
    _header_to_sub_type,
    parse_local_results,
)
from WebSearcher.component_types import TYPES_BY_NAME

# --- header -> sub_type mapping --------------------------------------------


@pytest.mark.parametrize(
    "header,expected",
    [
        # "results for" matched anywhere, not just as a prefix -- the key fix:
        # these used to slugify into per-query junk.
        ("Results for  Palo Alto, CA 94301", "results_for"),
        ("These are results for amour de hair nyc | tuatara", "results_for"),
        # known categories map to their canonical slug (case-insensitive)
        ("Places", "places"),
        ("Locations", "locations"),
        ("Businesses", "businesses"),
        ("In-store availability", "in-store_availability"),
        # free/locality/address headers resolve to None (no slugify)
        ("River Forest, IL", None),
        ("Orlando, FL", None),
        ("Pints, 412 NW 5th Ave, Portland", None),
        ("United States", None),
    ],
)
def test_header_to_sub_type(header, expected):
    assert _header_to_sub_type(header) == expected


def test_categories_are_declared_sub_types():
    """Every category the mapping can emit is a declared local_results sub_type."""
    declared = set(TYPES_BY_NAME["local_results"].sub_types)
    emitted = {"results_for", *_LOCAL_RESULTS_CATEGORIES.values()}
    assert emitted <= declared


# --- integration: heading preserved even when no category matches ----------


def _local_results(header: str):
    html = (
        '<div class="wrap">'
        f'<h2 role="heading">{header}</h2>'
        '<div class="VkpGBb"><div class="rllt__details">'
        '<div class="dbg0pd">Amour de Hair</div></div></div>'
        "</div>"
    )
    return parse_local_results(utils.make_soup(html).css_first("div.wrap"))


def test_unknown_header_drops_sub_type_but_keeps_heading():
    parsed = _local_results("River Forest, IL")
    assert parsed
    for r in parsed:
        # junk locality header -> no sub_type slug, but raw header preserved
        assert r.get("sub_type") is None
        assert r["details"]["heading"] == "River Forest, IL"


def test_known_header_sets_sub_type_and_heading():
    parsed = _local_results("These are results for amour de hair nyc")
    assert parsed
    for r in parsed:
        assert r["sub_type"] == "results_for"
        assert r["details"]["heading"] == "These are results for amour de hair nyc"
