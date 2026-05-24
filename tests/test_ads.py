"""Tests for ad subtype classification"""

from WebSearcher import utils
from WebSearcher.component_parsers.ads import classify_ad_type


def comp(inner: str):
    """Wrap inner HTML in a component Tag (selectors match descendants, not self)."""
    return utils.make_soup(f'<div class="wrap">{inner}</div>').find("div", {"class": "wrap"})


def test_classify_standard_ad():
    cmpt = comp('<div class="uEierd">Sponsored result text</div>')
    assert classify_ad_type(cmpt) == "standard"


def test_classify_shopping_ad():
    cmpt = comp('<div class="commercial-unit-desktop-top">Shopping ads</div>')
    assert classify_ad_type(cmpt) == "shopping"


def test_classify_unknown_when_no_ad_container():
    cmpt = comp('<div class="g">An organic result</div>')
    assert classify_ad_type(cmpt) == "unknown"


def test_classify_empty_container_still_matches():
    # Deliberate behavior of the existence check: classification keys off the
    # presence of the subtype container (cmpt.find), not its text content. The
    # earlier find_all_divs path filtered text-empty divs, so an empty container
    # classified as "unknown"; the find-based check classifies it as its subtype.
    # Real ad containers are never empty, so this edge does not occur in practice
    # -- pinned here so the loosening stays intentional rather than silent.
    cmpt = comp('<div class="uEierd"></div>')
    assert classify_ad_type(cmpt) == "standard"
