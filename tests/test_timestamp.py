"""Per-item metadata routed into ``details`` (two-tier schema): timestamps for
four layouts, plus the ``view_more_news`` thumbnail ``img_url``.

These component layouts are absent from (or not exercised for these fields by)
the bulk SERP fixture corpus, so their paths are pinned here with minimal
synthetic markup. Each parser previously wrote a top-level key (``timestamp`` /
``img_url``) that the ``BaseResult`` round-trip silently dropped; the value now
rides in ``details`` (recorded only when present).
"""

from WebSearcher import utils
from WebSearcher.component_parsers.news_quotes import parse_news_quote
from WebSearcher.component_parsers.twitter_result import parse_twitter_result
from WebSearcher.component_parsers.videos import parse_video
from WebSearcher.component_parsers.view_more_news import parse_sub


def _node(html: str):
    return utils.make_soup(f"<div>{html}</div>").css_first("div")


def test_view_more_news_timestamp_in_details():
    sub = _node(
        '<div><a href="http://x"><div class="jBgGLd">Title</div></a>'
        '<span class="wqg8ad">Source</span>'
        '<span class="FGlSad">2 hours ago</span></div>'
    )
    parsed = parse_sub(sub)
    assert parsed["details"]["timestamp"] == "2 hours ago"
    assert parsed["details"]["type"] == "item"


def test_view_more_news_img_url_in_details():
    sub = _node(
        '<div><a href="http://x"><div class="jBgGLd">Title</div></a>'
        '<span class="wqg8ad">Source</span>'
        '<span class="FGlSad">2 hours ago</span>'
        '<img data-src="http://img/thumb.jpg"></div>'
    )
    parsed = parse_sub(sub)
    # thumbnail rides in details alongside the timestamp (a top-level img_url is
    # dropped by the BaseResult round-trip)
    assert parsed["details"]["img_url"] == "http://img/thumb.jpg"
    assert parsed["details"]["timestamp"] == "2 hours ago"
    assert parsed["details"]["type"] == "item"


def test_view_more_news_clean_row_has_no_details():
    sub = _node(
        '<div><a href="http://x"><div class="jBgGLd">Title</div></a>'
        '<span class="wqg8ad">Source</span></div>'
    )
    parsed = parse_sub(sub)
    # no timestamp, no thumbnail -> recorded-only-when-present leaves details None
    assert parsed.get("details") is None


def test_twitter_result_timestamp_rides_with_tweet_details():
    elem = _node(
        '<div class="tw-res"><div>tweet body</div>'
        '<div><span>3h</span><a href="http://twitter.com/x/status/1">link</a></div></div>'
    )
    [parsed] = parse_twitter_result(elem)
    assert parsed["details"]["type"] == "tweet"
    assert parsed["details"]["url"] == "http://twitter.com/x/status/1"
    assert parsed["details"]["timestamp"] == "3h"


def test_videos_timestamp_in_details():
    sub = _node(
        '<div><div role="heading">Vid Title</div>'
        '<div class="MjS0Lc">snippet text</div>'
        '<div class="MjS0Lc"><div class="zECGdd"><span>CNN</span>'
        "<span>5 days ago</span></div></div></div>"
    )
    parsed = parse_video(sub, sub_type="videos")
    assert parsed["cite"] == "CNN"
    assert parsed["details"]["timestamp"] == "5 days ago"


def test_news_quotes_timestamp_in_details():
    # result_children == 2 branch: title link + meta(cite, timestamp)
    sub = _node(
        "<g-inner-card><div>the pull quote</div>"
        '<div><a href="http://a">Article Title</a>'
        "<div><span>Source</span><span>2 days ago</span></div></div></g-inner-card>"
    )
    inner = sub.css_first("g-inner-card")
    parsed = parse_news_quote(inner)
    assert parsed["details"]["timestamp"] == "2 days ago"
