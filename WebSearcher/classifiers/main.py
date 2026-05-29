from typing import Any

from selectolax.lexbor import LexborNode as Node

from .. import logger
from .._slx import class_tokens, get_text
from ..component_types import header_text_to_type

log = logger.Logger().start(__name__)

_VIDEO_CLASSES = {"VibNM", "mLmaBd", "RzdJxc", "sHEJob"}
_LOCAL_CLASSES = {"Qq3Lb", "VkpGBb"}


class _ComponentSignals:
    """One-pass summary of a component's class names, ids, and tag names.

    The classifier chain consults this to skip a classifier whose necessary
    structural signal is absent, replacing many full-subtree ``find()`` misses
    with set lookups. Preconditions are necessary conditions only, so a skip can
    never change a classification (pinned by the snapshot suite).
    """

    __slots__ = ("classes", "ids", "names")

    def __init__(self, cmpt: Node) -> None:
        classes: set[str] = set()
        ids: set[str] = set()
        names: set[str] = set()
        for el in cmpt.css("*"):
            names.add(el.tag)
            attrs = el.attributes
            cls = attrs.get("class")
            if cls:
                classes.update(cls.split())
            el_id = attrs.get("id")
            if el_id:
                ids.add(el_id)
        self.classes = classes
        self.ids = ids
        self.names = names


_HEADER_CSS_BY_LEVEL: dict[int, tuple[str, ...]] = {
    level: (
        f'h{level}[role="heading"]',
        f"h{level}.O3JH7, h{level}.q8U8x, h{level}.mfMhoc",
        f'[aria-level="{level}"][role="heading"]',
    )
    for level in (2, 3)
}


class ClassifyMainHeader:
    """Classify a main-section component by its h2/h3 header text."""

    @staticmethod
    def classify(cmpt, levels: tuple[int, ...] = (2, 3)) -> str:
        node: Node = cmpt
        for level in levels:
            header = ClassifyMainHeader._classify_header(node, level)
            if header != "unknown":
                return header
        return "unknown"

    @staticmethod
    def _classify_header(node: Node, level: int) -> str:
        """Check text in common headers for dict matches."""
        markers = header_text_to_type(level)
        for css in _HEADER_CSS_BY_LEVEL[level]:
            for header in node.css(css):
                text = (get_text(header) or "").strip()
                # local_results' "locations" is the lone endswith marker.
                if text.endswith("locations"):
                    return "local_results"
                for marker, label in markers.items():
                    if marker == "locations":
                        continue
                    if text.startswith(marker):
                        return label
        return "unknown"


class ClassifyMain:
    """Classify a component from the main section based on its selectolax Node."""

    @staticmethod
    def classify(cmpt) -> str:
        node: Node = cmpt
        signals = _ComponentSignals(node)

        component_classifiers = [
            (ClassifyMain.locations, None),
            (ClassifyMain.top_stories, lambda s: "g-scrolling-carousel" in s.names),
            (ClassifyMain.discussions_and_forums, lambda s: "IFnjPb" in s.classes),
            (ClassifyMainHeader.classify, None),
            (ClassifyMain.news_quotes, lambda s: "g-tray-header" in s.names),
            (ClassifyMain.img_cards, lambda s: "block-component" in s.names),
            (ClassifyMain.images, lambda s: "imagebox_bigimages" in s.ids or "iur" in s.ids),
            (ClassifyMain.ai_overview, lambda s: "Fzsovc" in s.classes or "h2" in s.names),
            (ClassifyMain.available_on, None),
            (ClassifyMain.knowledge_panel, None),
            (ClassifyMain.knowledge_block, lambda s: "block-component" in s.names),
            (ClassifyMain.banner, lambda s: "uzjuFc" in s.classes),
            (
                ClassifyMain.finance_panel,
                lambda s: "knowledge-finance-wholepage__entity-summary" in s.ids,
            ),
            (ClassifyMain.map_result, lambda s: "lu_map_section" in s.classes),
            (ClassifyMain.general_questions, lambda s: "ifM9O" in s.classes),
            (ClassifyMain.short_videos, lambda s: "IFnjPb" in s.classes),
            (ClassifyMain.videos, lambda s: bool(s.classes & _VIDEO_CLASSES)),
            (ClassifyMain.knowledge_subcard, lambda s: "JNkvid" in s.classes),
            (ClassifyMain.twitter, None),
            (ClassifyMain.flights, None),
            (ClassifyMain.promo, lambda s: "promo-throttler" in s.names),
            (
                ClassifyMain.products,
                lambda s: "product-viewer-group" in s.names or "g-more-link" in s.names,
            ),
            (ClassifyMain.general, None),
            (ClassifyMain.people_also_ask, None),
            (ClassifyMain.knowledge_box, None),
            (ClassifyMain.local_results, lambda s: bool(s.classes & _LOCAL_CLASSES)),
        ]

        for classifier, precondition in component_classifiers:
            if precondition is not None and not precondition(signals):
                continue
            cmpt_type = classifier(node)
            if cmpt_type != "unknown":
                return cmpt_type
        return "unknown"

    @staticmethod
    def discussions_and_forums(cmpt) -> str:
        node: Node = cmpt
        # bs4 ``find("div", {"class": "IFnjPb", "role": "heading"})`` = AND of
        # both conditions; CSS compound div.IFnjPb[role="heading"] = same.
        heading = node.css_first('div.IFnjPb[role="heading"]')
        if heading is not None and (get_text(heading, strip=True) or "").startswith(
            "Discussions and forums"
        ):
            return "discussions_and_forums"
        return "unknown"

    @staticmethod
    def available_on(cmpt) -> str:
        node: Node = cmpt
        for heading in node.css("span.mgAbYb"):
            if (get_text(heading, strip=True) or "") == "Available on":
                return "available_on"
        text = get_text(node) or ""
        return "available_on" if "/Available on" in text else "unknown"

    @staticmethod
    def banner(cmpt) -> str:
        node: Node = cmpt
        if "ULSxyf" not in class_tokens(node):
            return "unknown"
        return "banner" if node.css_first("div.uzjuFc") is not None else "unknown"

    @staticmethod
    def finance_panel(cmpt) -> str:
        node: Node = cmpt
        return (
            "knowledge"
            if node.css_first('div[id="knowledge-finance-wholepage__entity-summary"]') is not None
            else "unknown"
        )

    @staticmethod
    def flights(cmpt) -> str:
        node: Node = cmpt
        heading = node.css_first('[role="heading"]')
        if heading is not None and (get_text(heading, strip=True) or "").startswith("Flight"):
            return "flights"
        return "unknown"

    @staticmethod
    def general(cmpt) -> str:
        """Classify general components."""
        node: Node = cmpt
        node_id = node.mem_id
        cls = class_tokens(node)
        # bs4 distinguished "class" present vs absent via ``"class" in cmpt.attrs``
        # -- preserve that distinction explicitly.
        if "class" in node.attributes:
            conditions = {
                "format-01": cls == ["g"],
                "format-02": ("g" in cls) and ("Ww4FFb" in cls),
                "format-03": any(s in {"hlcw0c", "MjjYud", "PmEWq"} for s in cls),
                # bs4 ``find("div", {"class": ["g","Ww4FFb"]})`` = OR of tokens.
                "format-04": any(
                    n.mem_id != node_id for n in node.css("div.g, div.Ww4FFb")
                ),
            }
        else:
            conditions = {
                "format-05": all(
                    any(n.mem_id != node_id for n in node.css(f"div.{c}"))
                    for c in ("g", "d4rhi")
                ),
            }
        return "general" if any(conditions.values()) else "unknown"

    @staticmethod
    def general_questions(cmpt) -> str:
        node: Node = cmpt
        hybrid = node.css_first("div.ifM9O")
        g_accordion = node.css_first("g-accordion")
        return "general_questions" if hybrid is not None and g_accordion is not None else "unknown"

    @staticmethod
    def img_cards(cmpt) -> str:
        node: Node = cmpt
        if "class" not in node.attributes:
            return "unknown"
        cls = class_tokens(node)
        if not any(s in {"hlcw0c", "MjjYud"} for s in cls):
            return "unknown"
        return "img_cards" if node.css_first("block-component") is not None else "unknown"

    @staticmethod
    def images(cmpt) -> str:
        node: Node = cmpt
        for css in ('div[id="imagebox_bigimages"]', 'div[id="iur"]'):
            if node.css_first(css) is not None:
                return "images"
        return "unknown"

    @staticmethod
    def ai_overview(cmpt) -> str:
        """Classify AI Overview components.

        Skip the sibling "Related Links" expansion that also contains a
        ``Fzsovc`` div -- that surface is a different component (extended
        sources and follow-up sections) and is not parsed here.
        """
        node: Node = cmpt
        h2 = node.css_first("h2")
        h2_text = (get_text(h2, strip=True) or "") if h2 is not None else ""
        if h2_text == "Related Links":
            return "unknown"
        if node.css_first("div.Fzsovc") is not None or h2_text == "AI Overview":
            return "ai_overview"
        return "unknown"

    @staticmethod
    def knowledge_block(cmpt) -> str:
        node: Node = cmpt
        if class_tokens(node) != ["ULSxyf"]:
            return "unknown"
        return "knowledge" if node.css_first("block-component") is not None else "unknown"

    @staticmethod
    def knowledge_box(cmpt) -> str:
        """Classify knowledge component types."""
        node: Node = cmpt
        attrs = node.attributes
        condition: dict[str, Any] = {}
        condition["flights"] = (
            attrs.get("jscontroller") == "Z2bSc"
            or node.css_first('div[jscontroller="Z2bSc"]') is not None
        )
        condition["maps"] = attrs.get("data-hveid") == "CAMQAA"
        condition["locations"] = node.css_first("div.zd2Jbb") is not None
        condition["events"] = node.css_first("g-card.URhAHe") is not None
        condition["jobs"] = node.css_first("g-card.cvoI5e") is not None
        # bs4 ``next(iter(cmpt.stripped_strings), None)`` -- first non-blank
        # text fragment in the subtree. Use the _slx walker indirectly via
        # iter_text_fragments-style filter.
        first_text: str | None = None
        for s in (get_text(node) or "").splitlines():
            s2 = s.strip()
            if s2:
                first_text = s2
                break
        if first_text is None:
            # fallback: pull first non-whitespace fragment from text walker
            text = get_text(node) or ""
            first_text = text.strip().split()[0] if text.strip() else None
        # Simpler & more faithful: replicate stripped_strings exactly via the
        # _slx iter_text_fragments walker.
        from .._slx import _iter_text_fragments

        for raw in _iter_text_fragments(node):
            stripped = raw.strip()
            if stripped:
                first_text = stripped
                break
        else:
            first_text = None
        if first_text is not None:
            condition["covid_alert"] = first_text == "COVID-19 alert"
        for condition_type, conditions in condition.items():
            if conditions:
                return condition_type
        return "unknown"

    @staticmethod
    def knowledge_panel(cmpt) -> str:
        node: Node = cmpt
        for css in (
            "h1.VW3apb",
            "div.knowledge-panel, div.knavi, div.kp-blk, div.kp-wholepage-osrp",
            'div[aria-label="Featured results"][role="complementary"]',
            'div[jscontroller="qTdDb"]',
            "div.obcontainer",
        ):
            if node.css_first(css) is not None:
                return "knowledge"
        if node.attributes.get("jscontroller") == "qTdDb":
            return "knowledge"
        return "unknown"

    @staticmethod
    def local_results(cmpt) -> str:
        node: Node = cmpt
        for css in ("div.Qq3Lb", "div.VkpGBb"):
            if node.css_first(css) is not None:
                return "local_results"
        return "unknown"

    @staticmethod
    def map_result(cmpt) -> str:
        node: Node = cmpt
        return "map_results" if node.css_first("div.lu_map_section") is not None else "unknown"

    @staticmethod
    def people_also_ask(cmpt) -> str:
        """Secondary check for people also ask (header text is primary)."""
        node: Node = cmpt
        # bs4 ``check_dict_value(cmpt.attrs, "class", ["g","kno-kp","mnr-c","g-blk"])``
        # is EXACT list equality on the class attribute.
        return "people_also_ask" if class_tokens(node) == ["g", "kno-kp", "mnr-c", "g-blk"] else "unknown"

    @staticmethod
    def products(cmpt) -> str:
        """Classify organic shopping packs that otherwise fall into ``general``."""
        node: Node = cmpt
        if node.css_first('[data-attrid="apg-product-result"]') is not None:
            return "products"
        if (
            node.css_first("product-viewer-group") is not None
            and node.css_first("g-inner-card") is not None
        ):
            return "products"
        heading = node.css_first('[role="heading"]')
        if heading is not None and (get_text(heading, strip=True) or "") == "Explore brands":
            return "products"
        return "unknown"

    @staticmethod
    def promo(cmpt) -> str:
        node: Node = cmpt
        return "promo" if node.css_first("promo-throttler") is not None else "unknown"

    @staticmethod
    def short_videos(cmpt) -> str:
        node: Node = cmpt
        heading = node.css_first('span[role="heading"].IFnjPb')
        if heading is not None and (get_text(heading, strip=True) or "") == "Short videos":
            return "short_videos"
        return "unknown"

    @staticmethod
    def videos(cmpt) -> str:
        """Classify video carousel components."""
        node: Node = cmpt
        return (
            "videos"
            if node.css_first("div.VibNM, div.mLmaBd, div.RzdJxc, div.sHEJob") is not None
            else "unknown"
        )

    @staticmethod
    def knowledge_subcard(cmpt) -> str:
        """Catch knowledge-panel extension subcards by structural pattern."""
        node: Node = cmpt
        if node.css_first("div.JNkvid") is None:
            return "unknown"
        if node.css_first('[role="heading"][aria-level="2"]') is None:
            return "unknown"
        return "knowledge"

    @staticmethod
    def locations(cmpt) -> str:
        """Classify locations components (hotels, etc.)."""
        node: Node = cmpt
        heading = node.css_first('[role="heading"]')
        if heading is not None:
            text = get_text(heading, strip=True) or ""
            if text.startswith("Hotels") or text.startswith("More Hotels"):
                return "locations"
        return "unknown"

    @staticmethod
    def top_stories(cmpt) -> str:
        node: Node = cmpt
        if node.css_first("g-scrolling-carousel") is None:
            return "unknown"
        if node.css_first('div[id="tvcap"]') is None:
            return "unknown"
        return "top_stories"

    @staticmethod
    def news_quotes(cmpt) -> str:
        node: Node = cmpt
        header_div = node.css_first('g-tray-header[role="heading"]')
        text = get_text(header_div, strip=True) if header_div is not None else None
        return "news_quotes" if text == "News quotes" else "unknown"

    @staticmethod
    def twitter(cmpt) -> str:
        node: Node = cmpt
        cmpt_type = "twitter" if node.css_first("div.eejeod") is not None else "unknown"
        return ClassifyMain.twitter_type(node, cmpt_type)

    @staticmethod
    def twitter_type(cmpt, cmpt_type: str = "unknown") -> str:
        """Distinguish twitter types ('twitter_cards', 'twitter_result')."""
        node: Node = cmpt
        if cmpt_type == "twitter" or (get_text(node, strip=True) or "") == "Twitter Results":
            return "twitter_cards" if node.css_first("g-scrolling-carousel") is not None else "twitter_result"
        return cmpt_type
