"""Direct unit tests for the selectolax helpers in ``WebSearcher._slx``.

The helpers were previously covered only indirectly through whole-SERP
snapshots; these pin the bs4-compatibility contracts each one documents.
"""

from WebSearcher import _slx
from WebSearcher._slx import make_soup


def _first(html: str, css: str):
    node = make_soup(html).css_first(css)
    assert node is not None
    return node


# get_text ---------------------------------------------------------------------


def test_get_text_none_passthrough():
    assert _slx.get_text(None) is None


def test_get_text_joins_fragments_with_separator():
    node = _first("<p><b>a</b> <i>b</i></p>", "p")
    assert _slx.get_text(node) == "a b"
    assert _slx.get_text(node, "|") == "a| |b"


def test_get_text_strip_drops_empty_fragments():
    node = _first("<p>  <b>a</b>   <i>b</i>  </p>", "p")
    assert _slx.get_text(node, " ", strip=True) == "a b"


def test_get_text_skips_script_style_template_descendants():
    html = "<div>a<script>var x = 1;</script><style>p{}</style><template>t</template>b</div>"
    assert _slx.get_text(_first(html, "div")) == "ab"


def test_get_text_script_root_returns_its_body():
    # Documented caveat: only *descendant* script/style/template are skipped.
    assert _slx.get_text(_first("<div><script>x</script></div>", "script")) == "x"


# has_text / class_tokens / is_element -----------------------------------------


def test_has_text():
    assert _slx.has_text(None) is False
    assert _slx.has_text(_first("<div>  \n </div>", "div")) is False
    assert _slx.has_text(_first("<div><span><b>x</b></span></div>", "div")) is True


def test_class_tokens():
    assert _slx.class_tokens(_first('<div class="a  b c"></div>', "div")) == ["a", "b", "c"]
    assert _slx.class_tokens(_first("<div></div>", "div")) == []


def test_is_element_filters_comment_and_text_nodes():
    div = _first("<div><!-- c --><span>x</span>text</div>", "div")
    kinds = [(_slx.is_element(c), c.tag) for c in div.iter(include_text=True)]
    assert kinds == [(False, "-comment"), (True, "span"), (False, "-text")]
    assert _slx.is_element(None) is False


# subtree_* / walk_descendants --------------------------------------------------


def test_subtree_first_excludes_self():
    root = _first('<div class="g"><div class="g" id="inner">x</div></div>', "div.g")
    self_match = root.css_first("div.g")  # selectolax matches self
    assert self_match is not None and self_match.mem_id == root.mem_id
    found = _slx.subtree_first(root, "div.g")
    assert found is not None and found.id == "inner"
    assert _slx.subtree_first(root, "p") is None


def test_subtree_css_excludes_self_and_keeps_order():
    root = _first(
        '<div class="g"><div class="g" id="a"></div><div class="g" id="b"></div></div>', "div.g"
    )
    assert [n.id for n in _slx.subtree_css(root, "div.g")] == ["a", "b"]


def test_walk_descendants_preorder_without_self():
    root = _first("<div id='r'><p id='p'><b id='b'></b></p><i id='i'></i></div>", "#r")
    assert [n.id for n in _slx.walk_descendants(root)] == ["p", "b", "i"]


# is_hidden ----------------------------------------------------------------------


def test_is_hidden_walks_ancestors_and_tolerates_whitespace():
    html = '<div style="display: none"><p><span id="s">x</span></p></div><em id="e">y</em>'
    soup = make_soup(html)
    assert _slx.is_hidden(soup.css_first("#s")) is True
    assert _slx.is_hidden(soup.css_first("#e")) is False
    assert _slx.is_hidden(None) is False


# siblings -----------------------------------------------------------------------


def test_sibling_helpers_are_text_inclusive():
    p = _first("<p><b>a</b> mid <i>c</i></p>", "p")
    b = p.css_first("b")
    i = p.css_first("i")
    assert b is not None and i is not None
    nxt = _slx.next_sibling(b)
    assert nxt is not None and nxt.tag == "-text" and _slx.get_text(nxt) == " mid "
    nxt_el = _slx.next_sibling(b, include_text=False)
    assert nxt_el is not None and nxt_el.tag == "i"
    prev = _slx.previous_sibling(i)
    assert prev is not None and prev.tag == "-text"
    assert [n.tag for n in _slx.next_siblings(b)] == ["-text", "i"]
    assert _slx.next_sibling(i) is None
    assert _slx.previous_sibling(b) is None


# node_string / reparse_fragment / make_soup --------------------------------------


def test_node_string_semantics():
    assert _slx.node_string(_first("<p>only</p>", "p")) == "only"
    assert _slx.node_string(_first("<p><b>deep</b></p>", "p")) == "deep"
    assert _slx.node_string(_first("<p>a<b>b</b></p>", "p")) is None
    assert _slx.node_string(_first("<p></p>", "p")) is None


def test_reparse_fragment_is_independent_copy():
    node = _first("<div><p id='x'>t</p></div>", "div")
    copy = _slx.reparse_fragment(node)
    assert copy.mem_id != node.mem_id
    assert copy.tag == "div"
    assert _slx.get_text(copy) == "t"


def test_make_soup_accepts_bytes_and_nodes():
    root = make_soup(b"<p>caf\xc3\xa9</p>")
    assert _slx.get_text(root.css_first("p")) == "café"
    assert make_soup(root) is root
