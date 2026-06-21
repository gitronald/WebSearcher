"""The two-tier result schema: lean core fields + a ``details`` extras bucket.

Every parsed row round-trips through ``BaseResult(**row).model_dump()``. The
top level stays lean (``type`` / ``sub_type`` / ``title`` / ``url`` / ``text`` /
``cite`` / ``sub_rank``, plus ``details``); everything else rides in ``details``.

``details`` is either ``None`` (a clean row) or a dict that ALWAYS carries a
``type`` -- a specific content label (``"ratings"``, ``"hyperlinks"``, ...) when
there is a payload, or the generic ``"item"`` for a metadata-only row. The
reserved metadata keys (``error`` / ``visible`` / ``timestamp`` / ``img_url``)
live inside ``details``, recorded only when they carry information (``visible``
only when ``False``, the rest when present). These tests pin that contract.
"""

from WebSearcher import utils
from WebSearcher.component_parsers._common import (
    mark_hidden_item,
    mark_hidden_row,
    mark_timestamp_row,
)
from WebSearcher.models.data import BaseResult, error_details


def _dump(**row) -> dict:
    """Round-trip a raw parser row through BaseResult, as the pipeline does."""
    return BaseResult(**row).model_dump()


def _hidden_node():
    """A node under an inline ``display:none`` ancestor (is_hidden -> True)."""
    html = '<div style="display:none"><span class="card">x</span></div>'
    return utils.make_soup(html).css_first("span.card")


# --- core tier: lean, no leaked metadata, details None on a clean row -------


def test_clean_row_has_null_details():
    assert _dump(type="general", title="t", url="u")["details"] is None


def test_top_level_is_only_core_fields():
    # error / visible / timestamp / img_url are NOT top-level keys -- they only
    # ever appear inside details.
    assert set(_dump(type="general")) == {
        "sub_rank",
        "type",
        "sub_type",
        "title",
        "url",
        "text",
        "cite",
        "details",
    }


# --- type invariant: a non-empty details always carries a type -------------


def test_typeless_details_backfilled_to_item():
    out = _dump(type="perspectives", details={"heading": "What people are saying"})
    assert out["details"] == {"type": "item", "heading": "What people are saying"}


def test_typed_details_left_untouched():
    d = {"type": "ratings", "rating": "4.6", "n_reviews": "6.3K"}
    assert _dump(type="products", details=dict(d))["details"] == d


def test_empty_details_not_given_a_bare_type():
    # never fabricate a type-only dict from an empty payload
    assert _dump(type="general", details={})["details"] == {}


# --- error rows: metadata-only type:item -----------------------------------


def test_error_details_shape():
    assert error_details("no subcomponents parsed") == {
        "type": "item",
        "error": "no subcomponents parsed",
    }


def test_error_row_through_model():
    out = _dump(type="knowledge_rhs", details=error_details("boom"))
    assert out["details"] == {"type": "item", "error": "boom"}


# --- visible: recorded only when hidden, at the parser ----------------------


def test_visible_unrecorded_when_shown():
    parsed = {"type": "videos"}
    mark_hidden_row(parsed, None)  # is_hidden(None) -> False
    assert "details" not in parsed


def test_hidden_row_metadata_only():
    parsed = {"type": "videos"}
    mark_hidden_row(parsed, _hidden_node())
    assert parsed["details"] == {"type": "item", "visible": False}


def test_hidden_flag_rides_alongside_content():
    parsed = {"type": "shopping_ads", "details": {"type": "ratings", "rating": "4.6"}}
    mark_hidden_row(parsed, _hidden_node())
    assert parsed["details"] == {"type": "ratings", "rating": "4.6", "visible": False}


# --- timestamp: recorded only when present ---------------------------------


def test_timestamp_unrecorded_when_absent():
    parsed = {"type": "videos"}
    mark_timestamp_row(parsed, None)
    assert "details" not in parsed


def test_timestamp_metadata_only():
    parsed = {"type": "videos"}
    mark_timestamp_row(parsed, "2 hours ago")
    assert parsed["details"] == {"type": "item", "timestamp": "2 hours ago"}


# --- nested details["items"]: item-level visible flag ----------------------


def test_hidden_item_flagged():
    item = mark_hidden_item({"url": "u", "text": "t"}, _hidden_node())
    assert item == {"url": "u", "text": "t", "visible": False}


def test_shown_item_unflagged():
    assert mark_hidden_item({"url": "u"}, None) == {"url": "u"}
