"""Notice components: the true-empty no-results card and the 32-word
query-truncation card are `notice` components (not feature flags); server_error
stays a flag and must not stop a parse attempt."""

import WebSearcher as ws


def _notices(html: str) -> list[dict]:
    out = ws.parse_serp(html)
    return [r for r in out["results"] if r.get("type") == "notice"]


def test_no_results_card_becomes_notice_component():
    # True-empty page: the card renders in #topstuff (no #rso).
    html = (
        '<html><body><div id="main"><div id="cnt"><div id="rcnt"><div id="center_col">'
        '<div id="res"><div id="topstuff"><div class="mnr-c"><div class="card-section">'
        "<p>Your search - asdfqwerty - did not match any documents.</p>"
        "<div>Suggestions: Make sure all words are spelled correctly.</div>"
        "</div></div></div></div></div></div></div></body></html>"
    )
    notices = _notices(html)
    assert len(notices) == 1
    n = notices[0]
    assert n["sub_type"] == "no_results"
    assert "did not match any documents" in (n["title"] or "")
    assert "Suggestions" in (n["text"] or "")
    # no longer a SERP feature flag
    assert "notice_no_results" not in ws.parse_serp(html)["features"]


def test_no_results_card_in_botstuff():
    # The true-empty card can render in #botstuff instead of #topstuff.
    html = (
        '<html><body><div id="main"><div id="cnt"><div id="rcnt"><div id="center_col">'
        '<div id="botstuff"><div class="mnr-c"><div class="card-section">'
        "<p>Your search - zzqqxx1234 - did not match any documents.</p>"
        "</div></div></div></div></div></div></div></body></html>"
    )
    notices = _notices(html)
    assert [n["sub_type"] for n in notices] == ["no_results"]


def test_query_truncated_card_becomes_notice_component():
    html = (
        '<html><body><div id="main"><div id="cnt">'
        '<div class="card-section M7simc">'
        '"foo bar" (and any subsequent words) was ignored because we limit '
        "queries to 32 words."
        "</div></div></div></body></html>"
    )
    notices = _notices(html)
    assert len(notices) == 1
    assert notices[0]["sub_type"] == "query_truncated"
    assert "32 words" in (notices[0]["text"] or "")
    assert "notice_shortened_query" not in ws.parse_serp(html)["features"]


def test_low_relevance_banner_is_not_a_no_results_notice():
    # "Your search did not match any documents" as a low-relevance banner (in #rso,
    # results exist) must not be reclassified as a no_results notice.
    html = (
        '<html><body><div id="rso"><div class="ULSxyf"><div class="uzjuFc">'
        '<div class="v3jTId">Your search did not match any documents</div>'
        "</div></div></div></body></html>"
    )
    notices = _notices(html)
    assert not any(n["sub_type"] == "no_results" for n in notices)


def test_server_error_flag_does_not_stop_parse():
    # A page carrying the server-error chrome plus a normal result must still
    # parse: the flag is set AND extraction completes (results is a list).
    html = (
        '<html><body><div id="rso"><div class="g"><a href="https://example.com">'
        "<h3>Example</h3></a></div></div>"
        "<h1>Server Error</h1> We're sorry but it appears that there has been an "
        "internal server error while processing your request."
        "</body></html>"
    )
    out = ws.parse_serp(html)
    assert out["features"]["server_error"] is True
    assert isinstance(out["results"], list)  # parse ran to completion, no early abort
