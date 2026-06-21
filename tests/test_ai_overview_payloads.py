"""Unit tests for the AI overview payload extractor."""

from WebSearcher.parsers.components._ai_overview_payloads import extract_payloads

UUID = "12345678-1234-1234-1234-123456789abc"


def test_header_payload():
    raw = (
        "<div>x</div>"
        f"<!--TgQPHd|[[null,null,&quot;{UUID}&quot;,null,null,1,0,"
        "&quot;https://favicon&quot;,&quot;Yahoo Finance&quot;,2]]-->"
    )
    out = extract_payloads(raw)
    assert UUID in out
    assert out[UUID]["header"] == {
        "favicon": "https://favicon",
        "publisher": "Yahoo Finance",
        "total": 2,
    }
    assert out[UUID]["type_a"] == []
    assert out[UUID]["type_b"] == []


def test_type_a_payload():
    raw = (
        f"<!--TgQPHd|[[&quot;{UUID}&quot;,[&quot;Title&quot;,&quot;Snippet&quot;,"
        "&quot;https://fav&quot;,&quot;https://dom&quot;,[&quot;Pub&quot;],"
        "&quot;https://full.url/page&quot;,null,null,&quot;3&quot;,null,null,null]]]-->"
    )
    out = extract_payloads(raw)
    assert UUID in out
    type_a = out[UUID]["type_a"]
    assert len(type_a) == 1
    assert type_a[0] == {
        "title": "Title",
        "snippet": "Snippet",
        "favicon": "https://fav",
        "domain": "https://dom",
        "publisher": "Pub",
        "url": "https://full.url/page",
        "source_id": "3",
    }


def test_type_a_int_source_id():
    """Integer data-src-id should be coerced to string."""
    raw = (
        f"<!--TgQPHd|[[&quot;{UUID}&quot;,[&quot;T&quot;,&quot;S&quot;,"
        "&quot;f&quot;,&quot;d&quot;,[&quot;P&quot;],&quot;u&quot;,"
        "null,null,7,null,null,null]]]-->"
    )
    out = extract_payloads(raw)
    assert out[UUID]["type_a"][0]["source_id"] == "7"


def test_type_b_payload():
    raw = (
        f"<!--TgQPHd|[[&quot;{UUID}&quot;,&quot;2&quot;,0,"
        "&quot;https://full.url&quot;,&quot;https://fav&quot;,&quot;&quot;]]-->"
    )
    out = extract_payloads(raw)
    type_b = out[UUID]["type_b"]
    assert len(type_b) == 1
    assert type_b[0] == {
        "source_id": "2",
        "url": "https://full.url",
        "favicon": "https://fav",
    }


def test_sv6kpe_variant():
    """Sv6Kpe form has no ``|`` separator before the JSON."""
    raw = (
        f"<!--Sv6Kpe[[null,null,&quot;{UUID}&quot;,null,null,1,0,"
        "&quot;&quot;,&quot;Busuu&quot;,3]]-->"
    )
    out = extract_payloads(raw)
    assert UUID in out
    assert out[UUID]["header"]["publisher"] == "Busuu"
    assert out[UUID]["header"]["total"] == 3


def test_ldpb_push():
    raw = (
        r'(j.lDPB=j.lDPB||[]).push([["abc_67","[[\"'
        + UUID
        + r'\",[\"Title\",\"Snippet\",\"https://fav\",\"https://dom\",[\"Pub\"],\"https://url\",null,null,\"5\",null,null,null]]]"]])'
    )
    out = extract_payloads(raw)
    assert UUID in out
    type_a = out[UUID]["type_a"]
    assert len(type_a) == 1
    assert type_a[0]["title"] == "Title"
    assert type_a[0]["source_id"] == "5"


def test_empty_comments_ignored():
    raw = "<!--TgQPHd|[]--><!--Sv6Kpe[]-->"
    assert extract_payloads(raw) == {}


def test_malformed_json_ignored():
    raw = "<!--TgQPHd|not json-->"
    assert extract_payloads(raw) == {}


def test_unknown_shape_ignored():
    """``[[0, 0]]`` and other non-citation payloads should be skipped."""
    raw = "<!--TgQPHd|[[0,0]]--><!--TgQPHd|[[9,0,[null,null,null,null,null,1]]]-->"
    assert extract_payloads(raw) == {}


def test_multiple_payloads_per_uuid():
    raw = (
        f"<!--TgQPHd|[[null,null,&quot;{UUID}&quot;,null,null,1,0,&quot;f&quot;,&quot;Pub&quot;,2]]-->"
        f"<!--TgQPHd|[[&quot;{UUID}&quot;,[&quot;T1&quot;,&quot;S1&quot;,&quot;f1&quot;,"
        "&quot;d1&quot;,[&quot;P1&quot;],&quot;u1&quot;,null,null,&quot;1&quot;,null,null,null]]]-->"
        f"<!--TgQPHd|[[&quot;{UUID}&quot;,[&quot;T2&quot;,&quot;S2&quot;,&quot;f2&quot;,"
        "&quot;d2&quot;,[&quot;P2&quot;],&quot;u2&quot;,null,null,&quot;2&quot;,null,null,null]]]-->"
    )
    out = extract_payloads(raw)
    assert out[UUID]["header"]["total"] == 2
    assert [p["source_id"] for p in out[UUID]["type_a"]] == ["1", "2"]
