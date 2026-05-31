from dataclasses import dataclass
from typing import Any

from selectolax.lexbor import LexborNode as Node

from .._slx import _iter_text_fragments, class_tokens, get_text, has_text, subtree_css
from ..logger import Logger

log = Logger().start(__name__)


@dataclass(frozen=True)
class _StandardLayout:
    """A ``standard-*`` sub-layout recipe.

    ``detect_css`` locates the tab container and ``detect_sels`` is the set of
    descendant selectors that must match for the layout to claim the page.
    Extraction then reads ``extract_css`` (sometimes a different container than
    detection) via one of two shapes:

    - ``keep_tokens`` set -> direct children carrying the first token that yields
      any matches, concatenated with the top-divs *unfiltered*.
    - ``keep_tokens`` is ``None`` -> all children (text-inclusive) concatenated
      with the top-divs, then bad tags + empty nodes dropped.
    """

    detect_css: str
    detect_sels: tuple[str, ...]
    extract_css: str
    keep_tokens: tuple[str, ...] | None


# Names mirror the observable ``kp-wp-tab-*`` container each sub-layout detects;
# detection precedence follows insertion order. ``standard-fallback`` is the
# empty-rso fallback handled directly in ``extract_from_standard`` (no tab).
_STANDARD_LAYOUTS: dict[str, _StandardLayout] = {
    "standard-overview": _StandardLayout(
        detect_css='div[id="kp-wp-tab-overview"]',
        detect_sels=("div.TzHB6b", "div.A6K0A"),
        extract_css='div[id="kp-wp-tab-overview"]',
        keep_tokens=("TzHB6b", "A6K0A"),
    ),
    "standard-songs": _StandardLayout(
        detect_css='div[id="kp-wp-tab-cont-Songs"][role="tabpanel"]',
        detect_sels=("div",),
        extract_css='div[id="kp-wp-tab-Songs"]',
        keep_tokens=None,
    ),
    "standard-sports-standings": _StandardLayout(
        detect_css='div[id="kp-wp-tab-SportsStandings"]',
        detect_sels=("div",),
        extract_css='div[id="kp-wp-tab-SportsStandings"]',
        keep_tokens=None,
    ),
    "standard-airfares": _StandardLayout(
        detect_css='div[id="kp-wp-tab-AIRFARES"]',
        detect_sels=("div.A6K0A",),
        extract_css='div[id="kp-wp-tab-AIRFARES"]',
        keep_tokens=("A6K0A",),
    ),
}


def _filter_empty(nodes) -> list[Node]:
    return [n for n in nodes if n is not None and has_text(n)]


def _find_all_with_class(node: Node, css: str, *, filter_empty: bool = True) -> list[Node]:
    """``subtree_css`` + optional empty-text filter (bs4 ``find_all`` semantics)."""
    out = subtree_css(node, css)
    return [n for n in out if has_text(n)] if filter_empty else out


class ExtractorMain:
    def __init__(self, soup: Node | None, components):
        self.soup: Node | None = soup
        self.components = components

        self.layout_divs: dict[str, Any] = {
            "rso": None,
            "top-bars": None,
            "left-bar": None,
        }
        self.layouts = {
            "top-bars": False,
            "left-bar": False,
            "standard": False,
            "no-rso": False,
        }
        self.layout_label: str | None = None
        self.layout_extractors = {
            "standard": self.extract_from_standard,
            "top-bars": self.extract_from_top_bar,
            "left-bar": self.extract_from_left_bar,
            "no-rso": self.extract_from_no_rso,
        }

    def extract(self):
        self.get_layout()
        self._ads_top_carousel()
        self._ads_top()
        self._ads_bottom()
        self._main_column()
        log.debug(f"main_components: {self.components.cmpt_rank_counter:,}")

    def get_layout(self):
        """Divide and label the page layout."""
        assert self.soup is not None
        layout_divs: dict[str, Any] = {}
        layout_divs["rso"] = self.soup.css_first('div[id="rso"]')
        layout_divs["left-bar"] = self.soup.css_first("div.OeVqAd")

        rcnt = self.soup.css_first('div[id="rcnt"]')
        # bs4 ``find_all("div", {"class": ["XqFnDf","M8OgIe"]})`` = OR of tokens.
        layout_divs["top-bars"] = (
            _find_all_with_class(rcnt, "div.XqFnDf, div.M8OgIe") if rcnt is not None else []
        )

        layouts: dict[str, bool] = {
            "top-bars": bool(layout_divs["top-bars"]),
            "left-bar": layout_divs["left-bar"] is not None,
            "standard": False,
            "no-rso": layout_divs["rso"] is None,
        }
        layouts["standard"] = (
            layout_divs["rso"] is not None and not layouts["top-bars"] and not layouts["left-bar"]
        )

        if layouts["top-bars"] and layout_divs["rso"] is not None and not layouts["left-bar"]:
            layout_label = "standard"
        else:
            label_matches = [k for k, v in layouts.items() if v]
            layout_label = label_matches[0] if label_matches else None

        log.debug(f"main_layout: {layout_label}")
        self.layout_label = layout_label
        self.layouts.update(layouts)
        self.layout_divs.update(layout_divs)

    def _ads_top_carousel(self):
        """Extract sponsored carousel ads (e.g. Sponsored hotels via atvcap)."""
        assert self.soup is not None
        ads = self.soup.css_first('div[id="atvcap"]')
        if ads is not None and (get_text(ads) or ""):
            ads.remove(recursive=False)
            self.components.add_component(ads, section="main", type="shopping_ads")

    def _ads_top(self):
        assert self.soup is not None
        ads = self.soup.css_first('div[id="tads"]')
        if ads is not None and (get_text(ads) or ""):
            ads.remove(recursive=False)
            self.components.add_component(ads, section="main", type="ad")

    def _ads_bottom(self):
        assert self.soup is not None
        ads = self.soup.css_first('div[id="tadsb"]')
        if ads is not None and (get_text(ads) or ""):
            ads.remove(recursive=False)
            self.components.add_component(ads, section="main", type="ad")

    def _main_column(self, drop_tags: set | None = None):
        if drop_tags is None:
            drop_tags = {"script", "style", None}
        if self.layout_label is None:
            raise ValueError("no layout_label set")
        try:
            extractor = self.layout_extractors[self.layout_label]
        except KeyError:
            raise ValueError(f"no extractor for layout_label: {self.layout_label}")

        column = extractor(drop_tags)
        column = _filter_empty(column)
        for c in column:
            if ExtractorMain.is_valid(c):
                self.components.add_component(c, section="main")

    def extract_from_standard(self, drop_tags: set | None = None) -> list:
        rso_div = self.layout_divs["rso"]
        if rso_div is None:
            return []
        drop_tags = drop_tags or {"script", "style", None}
        for layout_name, spec in _STANDARD_LAYOUTS.items():
            container = rso_div.css_first(spec.detect_css)
            if container is not None and any(
                _find_all_with_class(container, sel, filter_empty=False) for sel in spec.detect_sels
            ):
                return self._extract_from_standard_sub_type(layout_name)

        top_divs = (
            ExtractorMain.extract_top_divs(
                self.layout_divs["top-bars"], rso=self.layout_divs["rso"]
            )
            or []
        )
        col = ExtractorMain.extract_children(rso_div, drop_tags)
        col = top_divs + col
        col = [c for c in col if ExtractorMain.is_valid(c)]
        if not col:
            self.layout_label = "standard-fallback"
            log.debug(f"main_layout: {self.layout_label} (update)")
            divs = _find_all_with_class(rso_div, 'div[id="kp-wp-tab-overview"]', filter_empty=False)
            col = []
            for d in divs:
                col.extend(_find_all_with_class(d, "div.TzHB6b", filter_empty=False))
            if not col:
                # ``recursive=False`` direct-children variant
                for d in divs:
                    col.extend(c for c in d.iter(include_text=False) if "A6K0A" in class_tokens(c))
        return col

    def _extract_from_standard_sub_type(self, sub_type: str = "") -> list:
        self.layout_label = sub_type
        rso_div = self.layout_divs["rso"]
        if rso_div is None:
            return []
        log.debug(f"main_layout: {self.layout_label} (update)")

        spec = _STANDARD_LAYOUTS.get(sub_type)
        if spec is None:
            # Unknown/empty sub_type -> no recipe; preserve "empty result".
            return []
        top_divs = (
            ExtractorMain.extract_top_divs(
                self.layout_divs["top-bars"], rso=self.layout_divs["rso"]
            )
            or []
        )
        container = rso_div.css_first(spec.extract_css)

        if spec.keep_tokens is not None:
            # Shape A: direct children carrying the first token that matches;
            # result is top_divs + main_divs, returned unfiltered.
            main_divs: list[Node] = []
            if container is not None:
                children = list(container.iter(include_text=False))
                for token in spec.keep_tokens:
                    main_divs = [c for c in children if token in class_tokens(c)]
                    if main_divs:
                        break
            column = top_divs + main_divs
            log.debug(f"main_components: {len(column):,}")
            return column

        # Shape B: all children (text-inclusive) + top_divs, then drop bad tags
        # and empty nodes from the combined column.
        main_divs = list(container.iter(include_text=True)) if container is not None else []
        column = top_divs + main_divs
        column = [
            d
            for d in column
            if d.tag and not d.tag.startswith("-") and d.tag not in {"script", "style"}
        ]
        return _filter_empty(column)

    def extract_from_top_bar(self, drop_tags: set | None = None) -> list:
        drop_tags = drop_tags or {"script", "style", None}
        out: list = []
        tops = ExtractorMain.extract_top_divs(
            self.layout_divs["top-bars"], rso=self.layout_divs["rso"]
        )
        out.extend(tops)

        div_classes_css = ", ".join(
            f"div.{c}" for c in ("cUnQKe", "g", "Lv2Cle", "oIk2Cb", "Ww4FFb", "vtSz8d", "uVMCKf")
        )
        rso_div = self.layout_divs["rso"]
        rso_divs = (
            _find_all_with_class(rso_div, div_classes_css, filter_empty=False)
            if rso_div is not None
            else []
        )
        if rso_divs:
            self.layout_label = "top-bars-divs"
            col = [div for div in rso_divs if div.tag not in drop_tags]
        else:
            self.layout_label = "top-bars-children"
            col = ExtractorMain.extract_children(self.layout_divs["rso"], drop_tags)
        log.debug(f"main_layout: {self.layout_label} (update)")
        out.extend(col)
        return out

    @staticmethod
    def extract_top_divs(top_bars, drop_tags: set | None = None, rso=None) -> list:
        out: list = []
        if not top_bars:
            return out
        for tb in top_bars:
            # bs4 ``check_dict_value(attrs, "class", ["M8OgIe"])`` is EXACT
            # list equality, not token membership.
            if class_tokens(tb) == ["M8OgIe"]:
                # bs4 ``{"jscontroller": ["qTdDb","OWrb3e"]}`` = OR.
                kd = _find_all_with_class(
                    tb,
                    'div[jscontroller="qTdDb"], div[jscontroller="OWrb3e"]',
                    filter_empty=True,
                )
                if kd:
                    out.extend(kd)
                else:
                    # Extract non-ad children (tvcap/tads handled by _ads_top).
                    # bs4 guard ``if not hasattr(ch,"name") or not ch.name``
                    # filtered text nodes; iter(include_text=False) does the same.
                    for ch in tb.iter(include_text=False):
                        if (
                            ch.css_first('div[id="tvcap"]') is not None
                            or ch.css_first('div[id="tads"]') is not None
                        ):
                            continue
                        if ch.tag == "h1":
                            continue
                        out.append(ch)
            elif ExtractorMain.is_dictionary_header(tb, rso):
                continue
            else:
                out.append(tb)
        return out

    @staticmethod
    def is_dictionary_header(elem: Node, rso=None) -> bool:
        """Check if element is a dictionary word header that duplicates an inline
        definitions component in the rso column."""
        if elem.css_first("div.kp-wholepage-osrp") is None:
            return False
        if rso is None:
            return False
        if rso.css_first('div[data-attrid="DictionaryHeader"]') is not None:
            return True
        return any(
            (get_text(b, strip=True) or "") == "Dictionary" for b in rso.css('div[role="button"]')
        )

    def extract_from_left_bar(self, drop_tags: set | None = None) -> list:
        assert self.soup is not None
        return _find_all_with_class(self.soup, "div.TzHB6b", filter_empty=False)

    def extract_from_no_rso(self, drop_tags: set | None = None) -> list:
        drop_tags = drop_tags or {"script", "style", None}
        assert self.soup is not None
        out: list[Node] = []
        # bs4 ``find_all("div", {"class": "UDZeY OTFaAf"})`` is multi-token EXACT.
        sec1 = [
            d for d in self.soup.css("div.UDZeY.OTFaAf") if class_tokens(d) == ["UDZeY", "OTFaAf"]
        ]
        for div in sec1:
            h2 = div.css_first("h2")
            if h2 is not None and (get_text(h2) or "") == "Twitter Results":
                inner_div = div.css_first("div")
                if inner_div is not None and inner_div.parent is not None:
                    out.append(inner_div.parent)
            elif (sec_header := div.css_first("g-section-with-header")) is not None:
                if sec_header.parent is not None:
                    out.append(sec_header.parent)
            elif div.css_first("g-more-link") is not None:
                out.append(div)
            elif div.css_first("div.oIk2Cb") is not None:
                out.append(div)
            else:
                out.extend(n for n in div.css("div.g") if n.mem_id != div.mem_id)
        # Page-level trailing section -- appended once, not per sec1 div.
        sec2 = self.soup.css_first("div.WvKfwe.a3spGf")
        if sec2 is not None and class_tokens(sec2) == ["WvKfwe", "a3spGf"]:
            out.extend(sec2.iter(include_text=True))
        return [
            c
            for c in out
            if c is not None and c.tag and not c.tag.startswith("-") and c.tag not in drop_tags
        ]

    @staticmethod
    def extract_children(soup, drop_tags: set | None = None) -> list:
        """bs4 ``soup.children`` -> direct children. The original then expanded
        children that have no attrs by inlining their ``.contents`` (text-
        inclusive)."""
        drop_tags = drop_tags or {"script", "style", None}
        if soup is None:
            return []
        cts: list = []
        for ch in soup.iter(include_text=False):
            if ch.tag in drop_tags:
                continue
            if not ch.attributes:
                # ``contents`` was text-inclusive; preserve that.
                cts.extend(ch.iter(include_text=True))
            else:
                cts.append(ch)
        return cts

    @staticmethod
    def is_valid(c) -> bool:
        if c is None:
            return False
        if not c.tag or c.tag.startswith("-"):
            return False
        bad = {"Main results", "Twitter Results", ""}
        # Bound the text scan: the longest bad label is 15 chars, so once the
        # accumulated text exceeds that it cannot match and we stop walking.
        text = ""
        for s in _iter_text_fragments(c):
            text += s
            if len(text) > 15:
                break
        if text in bad:
            return False
        # Skip bottom ads wrapper (extracted separately)
        if c.css_first('div[id="tadsb"]') is not None:
            return False
        # Drop the redundant results-wrapper variant of a promo-throttler block.
        if (
            class_tokens(c) == ["ULSxyf"]
            and c.css_first("promo-throttler") is not None
            and c.css_first("div.g") is not None
        ):
            return False
        return True
