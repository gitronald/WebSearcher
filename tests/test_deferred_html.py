"""Deferred ``jsl.dh`` fragments, and the card fields that come with them."""

from selectolax.lexbor import LexborNode as Node

from WebSearcher import utils
from WebSearcher.parsers.components._deferred_html import fill_deferred_html, unescape_js_string
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
