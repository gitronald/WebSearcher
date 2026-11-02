"""Deferred ``jsl.dh`` fragments, and the card fields that come with them."""

import pytest
from selectolax.lexbor import LexborNode as Node

import WebSearcher as ws
from WebSearcher import utils
from WebSearcher.parsers.components._deferred_html import (
    DeferredCalls,
    fill_deferred_html,
    read_deferred_calls,
    unescape_js_string,
)
from WebSearcher.parsers.components.ai_overview import parse_ai_overview
from WebSearcher.parsers.components.knowledge import parse_knowledge_panel
from WebSearcher.parsers.components.perspectives import parse_perspectives
from WebSearcher.parsers.components.recent_posts import parse_recent_posts


def _scope(html: str) -> Node:
    """The ``#scope`` element of a page."""
    node = utils.make_soup(html).css_first("#scope")
    assert node is not None
    return node


def _text(scope: Node, selector: str) -> str:
    node = scope.css_first(selector)
    assert node is not None
    return node.text()


def _fragment(target_id: str, body: str) -> str:
    return f"<script>[{{id:'{target_id}'}},function(){{jsl.dh(this.id,\"{body}\");}}]</script>"


def test_unescape_js_string_decodes_each_escape_form():
    body = r"\x3ca href=\"/goto?url=T&gsessionid\x3dS\">it\'s\n\ud83d\ude00\x3c/a>"
    assert unescape_js_string(body) == '<a href="/goto?url=T&gsessionid=S">it\'s\n😀</a>'


def test_fill_runs_in_document_order_so_a_fragment_can_fill_a_later_target():
    scope = _scope(
        '<div id="scope"><div id="outer"></div></div>'
        + _fragment("outer", r"\x3cdiv id=\"inner\">\x3c/div>")
        + _fragment("inner", "text")
    )
    assert len(fill_deferred_html(scope)) == 2
    assert _text(scope, "#inner") == "text"


def test_fill_leaves_a_target_that_already_holds_content():
    scope = _scope(
        '<div id="scope"><div id="done">loaded</div></div>' + _fragment("done", "original")
    )
    assert fill_deferred_html(scope) == []
    assert _text(scope, "#done") == "loaded"


def test_fill_stays_inside_the_scope():
    scope = _scope(
        '<div id="scope"><div id="in"></div></div><div id="out"></div>'
        + _fragment("in", "a")
        + _fragment("out", "b")
    )
    assert len(fill_deferred_html(scope)) == 1
    assert "b" not in (scope.text() or "")


def test_perspectives_reads_deferred_cards_and_their_collapsed_section():
    card = (
        r"\x3ca class=\"aJWbwf\" href=\"/goto?url=POST\">\x3cdiv class=\"eAaXgc\">Post\x3c/div>"
        r"\x3catx-attribution>\x3cdiv class=\"sTl1Td\">fan · Instagram\x3c/div>"
        r"\x3c/atx-attribution>\x3c/a>"
    )
    scope = _scope(
        '<div id="scope"><span role="heading" aria-level="2">What people are saying</span>'
        '<div role="list">'
        '<div role="listitem" data-init-vis="true"><a href="/goto?url=SHOWN"></a>'
        '<div class="eAaXgc">Shown</div></div>'
        '<div role="listitem" data-init-vis="false" id="tail"></div>'
        "</div>"
        '<div role="button" aria-expanded="false" aria-controls="panel">'
        '<span>Team loses</span><span class="nmhWwf">A summary.</span></div>'
        '<div id="panel"><div role="listitem" data-init-vis="true" id="hidden"></div></div></div>'
        + _fragment("tail", card)
        + _fragment("hidden", card)
    )
    shown, tail, hidden = parse_perspectives(scope)
    assert shown["url"] == "/goto?url=SHOWN"
    assert "visible" not in shown["details"]
    assert "section_heading" not in shown["details"]
    assert tail["cite"] == "fan · Instagram"
    assert tail["details"]["visible"] is False
    assert "section_heading" not in tail["details"]
    assert hidden["details"]["visible"] is False
    assert hidden["details"]["section_heading"] == "Team loses"
    assert hidden["details"]["section_summary"] == "A summary."


def test_expanded_section_keeps_its_cards_visible():
    scope = _scope(
        '<div id="scope"><div role="button" aria-expanded="true" aria-controls="panel">'
        "<span>Team loses</span></div>"
        '<div id="panel"><div role="listitem"><a href="/goto?url=POST"></a>'
        '<div class="eAaXgc">Post</div></div></div></div>'
    )
    details = parse_perspectives(scope)[0]["details"]
    assert details["section_heading"] == "Team loses"
    assert "visible" not in details


def test_embedded_post_keeps_its_age_and_author_link():
    scope = _scope(
        '<div id="scope"><div role="listitem">'
        '<a href="/goto?url=POST"></a>'
        '<div class="xcQxib">A post</div>'
        '<span jsname="biJjHb" data-ts="1">19 hours ago</span>'
        '<div id="twitter_attribution_x"><a href="/goto?url=AUTHOR">'
        '<div class="Du2Vwd">NFL</div></a></div>'
        "</div></div>"
    )
    row = parse_perspectives(scope)[0]
    assert row["url"] == "/goto?url=POST"
    assert row["cite"] == "NFL"
    assert row["details"]["timestamp"] == "19 hours ago"
    assert row["details"]["author_url"] == "/goto?url=AUTHOR"


def test_recent_post_cite_joins_author_and_platform():
    scope = _scope(
        '<div id="scope"><div role="listitem"><a href="/goto?url=POST"></a>'
        '<div class="eAaXgc">Highlights</div>'
        '<div class="R8BTeb">San Francisco 49ers</div><div class="xuPcX">YouTube</div>'
        "</div></div>"
    )
    assert parse_recent_posts(scope)[0]["cite"] == "San Francisco 49ers · YouTube"


def test_match_header_reads_deferred_highlight_clips():
    scope = _scope(
        '<div id="scope"><div class="imso_mh__mh-bma"><g-scrolling-carousel>'
        '<a href="/goto?url=FIRST">Game recap</a><div id="clip"></div>'
        "</g-scrolling-carousel></div></div>"
        + _fragment("clip", r"\x3ca href=\"/goto?url=CLIP\">Touchdown\x3c/a>")
    )
    first, clip = parse_knowledge_panel(scope)[0]["details"]["urls"]
    assert first["url"] == "/goto?url=FIRST"
    assert "visible" not in first
    assert clip["url"] == "/goto?url=CLIP"
    assert clip["visible"] is False


_TRAY = (
    r"\x3cdiv style=\"display:none\">\x3cul>"
    r"\x3cli class=\"LLtSOc\">\x3ca class=\"KEVENd\" href=\"/goto?url=T1\">\x3c/a>"
    r"\x3cdiv class=\"R8BTeb\">one.example\x3c/div>\x3c/li>"
    r"\x3cli class=\"LLtSOc\">\x3ca class=\"KEVENd\" href=\"/goto?url=T2\">\x3c/a>"
    r"\x3cdiv class=\"R8BTeb\">two.example\x3c/div>\x3c/li>"
    r"\x3c/ul>\x3c/div>"
)


def _overview_page() -> Node:
    return _scope(
        '<div id="scope"><div class="mZJni"><div class="n6owBd">The answer.</div></div>'
        '<div data-src-id="1"><a href="/goto?url=CARD">Card</a></div>'
        '<div id="tray"></div><div id="other"></div></div>'
        + _fragment("tray", _TRAY)
        + _fragment("other", r"\x3cdiv class=\"n6owBd\">Not the answer.\x3c/div>")
    )


def test_overview_reads_its_tray_apart_from_its_source_cards():
    [row] = parse_ai_overview(_overview_page())
    details = row["details"]
    assert [s["url"] for s in details["sources"]] == ["/goto?url=CARD"]
    assert [(s["url"], s["publisher"], s["visible"]) for s in details["source_tray"]] == [
        ("/goto?url=T1", "one.example", False),
        ("/goto?url=T2", "two.example", False),
    ]


def test_overview_tray_fill_leaves_the_body_and_other_fragments_alone():
    scope = _overview_page()
    [row] = parse_ai_overview(scope)
    assert row["text"] == "The answer."
    other = scope.css_first("#other")
    assert other is not None
    assert not (other.inner_html or "").strip()


def test_fill_can_be_limited_to_fragments_holding_a_marker():
    scope = _scope(
        '<div id="scope"><div id="a"></div><div id="b"></div></div>'
        + _fragment("a", "wanted")
        + _fragment("b", "other")
    )
    assert [t.attrs.get("id") for t in fill_deferred_html(scope, containing="wanted")] == ["a"]


@pytest.mark.parametrize(
    "call",
    [
        """<script>[{id:'t'},function(){jsl.dh(this.id,"\\x3cb>x\\x3c/b>");}]</script>""",
        """<script>[{id:'t'},function(){jsl.dh(this.id,'\\x3cb>x\\x3c/b>');}]</script>""",
        """<script>(function(){window.jsl.dh('t',"\\x3cb>x\\x3c/b>");})();</script>""",
        """<script>(function(){window.jsl.dh('t','\\x3cb>x\\x3c/b>');})();</script>""",
        """<script>(function(){window.jsl.dh("t","\\x3cb>x\\x3c/b>");})();</script>""",
        """<script>[{id: 't'}, function() { window.jsl.dh( this.id , "\\x3cb>x\\x3c/b>" ); }]</script>""",
    ],
)
def test_fill_reads_every_form_of_the_call(call):
    scope = _scope(f'<div id="scope"><div id="t"></div></div>{call}')
    assert [t.attrs.get("id") for t in fill_deferred_html(scope)] == ["t"]
    assert _text(scope, "#t b") == "x"


def test_read_handles_a_quote_of_the_other_kind_and_an_escaped_one_in_a_body():
    html = """window.jsl.dh('a',"it's \\"x\\"");window.jsl.dh("b",'say "y" isn\\'t');"""
    assert read_deferred_calls(html) == DeferredCalls(
        2, (("a", 'it\'s \\"x\\"'), ("b", 'say "y" isn\\\'t'))
    )


@pytest.mark.parametrize(
    "html",
    [
        "jsl.dh(someVar,'x')",  # the id is not a literal
        "jsl.dh('a',someVar)",  # the body is not a literal
        "jsl.dh('a')",  # no body
        "jsl.dh(this.id,'x')",  # no owner object before it
        "jsl.dh('a','unterminated",
    ],
)
def test_a_call_that_cannot_be_read_is_counted_and_not_returned(html):
    assert read_deferred_calls(html) == DeferredCalls(1, ())


def test_the_name_alone_is_not_a_call():
    assert read_deferred_calls("window.jsl.dh=function(){};x('jsl.dh');").n_calls == 0


def test_parse_serp_reports_the_share_of_calls_read():
    html = "<html><body><script>window.jsl.dh('a','x');jsl.dh(v,'y');</script></body></html>"
    features = ws.parse_serp(html)["features"]
    assert (features["deferred_calls"], features["deferred_read"]) == (2, 1)


def test_parse_serp_without_raw_markup_reports_no_counts():
    features = ws.parse_serp(utils.make_soup("<html><body></body></html>"))["features"]
    assert (features["deferred_calls"], features["deferred_read"]) == (None, None)
