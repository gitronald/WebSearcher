import itertools
from typing import Any

import bs4

from .. import logger, utils
from ..component_types import header_text_to_type
from ..utils import Selector

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

    def __init__(self, cmpt: bs4.element.Tag) -> None:
        classes: set[str] = set()
        ids: set[str] = set()
        names: set[str] = set()
        for el in itertools.chain((cmpt,), cmpt.descendants):
            if not isinstance(el, bs4.element.Tag):
                continue
            names.add(el.name)
            cls = el.attrs.get("class")
            if isinstance(cls, list):  # "class" is multi-valued in bs4
                classes.update(cls)
            el_id = el.attrs.get("id")
            if isinstance(el_id, str):
                ids.add(el_id)
        self.classes = classes
        self.ids = ids
        self.names = names


class ClassifyMainHeader:
    """Classify a main-section component by its h2/h3 header text."""

    @staticmethod
    def classify(cmpt: bs4.element.Tag, levels: list[int] = [2, 3]) -> str:
        for level in levels:
            header = ClassifyMainHeader._classify_header(cmpt, level)
            if header != "unknown":
                return header
        return "unknown"

    @staticmethod
    def _classify_header(cmpt: bs4.element.Tag, level: int) -> str:
        """Check text in common headers for dict matches"""
        header_dict = header_text_to_type(level)

        # Define selectors for classifying header divs
        selectors: list[Selector] = [
            Selector(f"h{level}", {"role": "heading"}),
            Selector(f"h{level}", {"class": ["O3JH7", "q8U8x", "mfMhoc"]}),
            Selector(None, {"aria-level": f"{level}", "role": "heading"}),
        ]
        headers = (
            h
            for sel in selectors
            for h in (
                cmpt.find_all(sel.name, attrs=sel.attrs)
                if sel.name
                else cmpt.find_all(attrs=sel.attrs)
            )
        )

        # Filter header divs and check text against dict
        for header in filter(None, headers):
            for text, label in header_dict.items():
                if label == "local_results" and text == "locations":
                    if header.text.strip().endswith(text):
                        return label
                if header.text.strip().startswith(text):
                    return label

        return "unknown"


class ClassifyMain:
    """Classify a component from the main section based on its bs4.element.Tag"""

    @staticmethod
    def classify(cmpt: bs4.element.Tag) -> str:
        signals = _ComponentSignals(cmpt)

        # Ordered (classifier, precondition) chain. The precondition is a cheap
        # NECESSARY structural signal -- when it is absent the classifier cannot
        # match, so it is skipped without a full-subtree find(). None = always run
        # (text/heading/root-class classifiers that general results also trigger).
        component_classifiers = [
            (ClassifyMain.locations, None),  # hotels, etc. (heading text)
            (ClassifyMain.top_stories, lambda s: "g-scrolling-carousel" in s.names),
            (ClassifyMain.discussions_and_forums, lambda s: "IFnjPb" in s.classes),
            (ClassifyMainHeader.classify, None),  # levels 2 & 3 header text
            (ClassifyMain.news_quotes, lambda s: "g-tray-header" in s.names),
            (ClassifyMain.img_cards, lambda s: "block-component" in s.names),
            (ClassifyMain.images, lambda s: "imagebox_bigimages" in s.ids or "iur" in s.ids),
            (ClassifyMain.ai_overview, lambda s: "Fzsovc" in s.classes or "h2" in s.names),
            (ClassifyMain.available_on, None),  # span.mgAbYb or text fallback
            (ClassifyMain.knowledge_panel, None),  # several selectors incl. aria-label
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
            (ClassifyMain.twitter, None),  # div.eejeod or "Twitter Results" text
            (ClassifyMain.flights, None),  # heading text
            (
                ClassifyMain.products,
                lambda s: "product-viewer-group" in s.names or "g-more-link" in s.names,
            ),
            (ClassifyMain.general, None),  # root class
            (ClassifyMain.people_also_ask, None),  # root class
            (ClassifyMain.knowledge_box, None),  # several attr/structural paths
            (ClassifyMain.local_results, lambda s: bool(s.classes & _LOCAL_CLASSES)),
        ]

        # Default unknown, exit on first successful classification.
        for classifier, precondition in component_classifiers:
            if precondition is not None and not precondition(signals):
                continue
            cmpt_type = classifier(cmpt)
            if cmpt_type != "unknown":
                return cmpt_type

        return "unknown"

    @staticmethod
    def discussions_and_forums(cmpt: bs4.element.Tag) -> str:
        heading = cmpt.find("div", {"class": "IFnjPb", "role": "heading"})
        if heading and heading.get_text(strip=True).startswith("Discussions and forums"):
            return "discussions_and_forums"
        return "unknown"

    @staticmethod
    def available_on(cmpt: bs4.element.Tag) -> str:
        for heading in cmpt.find_all("span", class_="mgAbYb"):
            if heading.get_text(strip=True) == "Available on":
                return "available_on"
        text = utils.get_text(cmpt) or ""
        return "available_on" if "/Available on" in text else "unknown"

    @staticmethod
    def banner(cmpt: bs4.element.Tag) -> str:
        conditions = [
            "ULSxyf" in cmpt.attrs.get("class", []),
            cmpt.find("div", {"class": "uzjuFc"}),
        ]
        return "banner" if all(conditions) else "unknown"

    @staticmethod
    def finance_panel(cmpt: bs4.element.Tag) -> str:
        condition = cmpt.find("div", {"id": "knowledge-finance-wholepage__entity-summary"})
        return "knowledge" if condition else "unknown"

    @staticmethod
    def flights(cmpt: bs4.element.Tag) -> str:
        """Classify Google Flights widgets (prices, status)"""
        heading = cmpt.find(attrs={"role": "heading"})
        if heading and heading.get_text(strip=True).startswith("Flight"):
            return "flights"
        return "unknown"

    @staticmethod
    def general(cmpt: bs4.element.Tag) -> str:
        """Classify general components"""

        if "class" in cmpt.attrs:
            conditions_dict = {
                "format-01": cmpt.attrs["class"] == ["g"],
                "format-02": (
                    ("g" in cmpt.attrs["class"]) & any(s in ["Ww4FFb"] for s in cmpt.attrs["class"])
                ),
                "format-03": any(s in ["hlcw0c", "MjjYud", "PmEWq"] for s in cmpt.attrs["class"]),
                "format-04": cmpt.find("div", {"class": ["g", "Ww4FFb"]}),
            }
        else:
            conditions_dict = {
                "format-05": all(cmpt.find("div", {"class": c}) for c in ["g", "d4rhi"]),
            }

        layout_matches = [k for k, v in conditions_dict.items() if v]
        # log.debug(f"general layout: {layout_matches}")

        return "general" if any(layout_matches) else "unknown"

    @staticmethod
    def general_questions(cmpt: bs4.element.Tag) -> str:
        hybrid = cmpt.find("div", {"class": "ifM9O"})
        g_accordian = cmpt.find("g-accordion")
        return "general_questions" if hybrid and g_accordian else "unknown"

    @staticmethod
    def img_cards(cmpt: bs4.element.Tag) -> str:
        """Classify image cards components"""
        if "class" in cmpt.attrs:
            conditions = [
                any(s in ["hlcw0c", "MjjYud"] for s in cmpt.attrs["class"]),
                cmpt.find("block-component"),
            ]
            return "img_cards" if all(conditions) else "unknown"
        else:
            return "unknown"

    @staticmethod
    def images(cmpt: bs4.element.Tag) -> str:
        selectors = [
            {"name": "div", "attrs": {"id": "imagebox_bigimages"}},
            {"name": "div", "attrs": {"id": "iur"}},
        ]
        return "images" if utils.find_by_selectors(cmpt, selectors) else "unknown"

    @staticmethod
    def ai_overview(cmpt: bs4.element.Tag) -> str:
        """Classify AI Overview components.

        Skip the sibling "Related Links" expansion that also contains a
        ``Fzsovc`` div — that surface is a different component (extended
        sources and follow-up sections) and is not parsed here.
        """
        h2 = cmpt.find("h2")
        if h2 is not None and h2.get_text(strip=True) == "Related Links":
            return "unknown"
        conditions = [
            cmpt.find("div", {"class": "Fzsovc"}),
            h2 is not None and h2.get_text(strip=True) == "AI Overview",
        ]
        return "ai_overview" if any(conditions) else "unknown"

    @staticmethod
    def knowledge_block(cmpt: bs4.element.Tag) -> str:
        """Classify knowledge block components"""
        conditions = [
            utils.check_dict_value(cmpt.attrs, "class", ["ULSxyf"]),
            cmpt.find("block-component"),
        ]
        return "knowledge" if all(conditions) else "unknown"

    @staticmethod
    def knowledge_box(cmpt: bs4.element.Tag) -> str:
        """Classify knowledge component types"""
        attrs = cmpt.attrs
        condition: dict[str, Any] = {}
        condition["flights"] = (utils.check_dict_value(attrs, "jscontroller", "Z2bSc")) | bool(
            cmpt.find("div", {"jscontroller": "Z2bSc"})
        )
        condition["maps"] = utils.check_dict_value(attrs, "data-hveid", "CAMQAA")
        condition["locations"] = cmpt.find("div", {"class": "zd2Jbb"})
        condition["events"] = cmpt.find("g-card", {"class": "URhAHe"})
        condition["jobs"] = cmpt.find("g-card", {"class": "cvoI5e"})
        first_text = next(iter(cmpt.stripped_strings), None)
        if first_text is not None:
            condition["covid_alert"] = first_text == "COVID-19 alert"
        for condition_type, conditions in condition.items():
            if conditions:
                return condition_type
        return "unknown"

    @staticmethod
    def knowledge_panel(cmpt: bs4.element.Tag) -> str:
        selectors = [
            {"name": "h1", "attrs": {"class": "VW3apb"}},
            {
                "name": "div",
                "attrs": {"class": ["knowledge-panel", "knavi", "kp-blk", "kp-wholepage-osrp"]},
            },
            {"name": "div", "attrs": {"aria-label": "Featured results", "role": "complementary"}},
            {"name": "div", "attrs": {"jscontroller": "qTdDb"}},
            {"name": "div", "attrs": {"class": "obcontainer"}},
        ]
        cmpt_check = utils.find_by_selectors(cmpt, selectors)
        attr_check = utils.check_dict_value(cmpt.attrs, "jscontroller", "qTdDb")
        if cmpt_check or attr_check:
            return "knowledge"
        return "unknown"

    @staticmethod
    def local_results(cmpt: bs4.element.Tag) -> str:
        selectors = [
            {"name": "div", "attrs": {"class": "Qq3Lb"}},  # Places
            {"name": "div", "attrs": {"class": "VkpGBb"}},  # Local Results
        ]
        return "local_results" if utils.find_by_selectors(cmpt, selectors) else "unknown"

    @staticmethod
    def map_result(cmpt: bs4.element.Tag) -> str:
        condition = cmpt.find("div", {"class": "lu_map_section"})
        return "map_results" if condition else "unknown"

    @staticmethod
    def people_also_ask(cmpt: bs4.element.Tag) -> str:
        """Secondary check for people also ask, see classify_header for primary"""
        class_list = ["g", "kno-kp", "mnr-c", "g-blk"]
        conditions = utils.check_dict_value(cmpt.attrs, "class", class_list)
        return "people_also_ask" if conditions else "unknown"

    @staticmethod
    def products(cmpt: bs4.element.Tag) -> str:
        """Classify organic shopping packs that otherwise fall into ``general``.

        Two layouts: the immersive popular-products grid (each product is a
        ``data-attrid="apg-product-result"`` card) and the "Explore brands"
        merchant carousel. Runs before ``general`` so these are not claimed by
        its greedy ``MjjYud``/``hlcw0c`` (``format-03``) and nested-``div.g``
        (``format-04``) markers; the positive signal is the product/brand
        structure itself, not the shared container class.
        """
        if cmpt.find(attrs={"data-attrid": "apg-product-result"}):
            return "products"
        heading = cmpt.find(attrs={"role": "heading"})
        if heading and heading.get_text(strip=True) == "Explore brands":
            return "products"
        return "unknown"

    @staticmethod
    def short_videos(cmpt: bs4.element.Tag) -> str:
        """Classify short videos carousel"""
        heading = cmpt.find("span", {"role": "heading", "class": "IFnjPb"})
        if heading and heading.get_text(strip=True) == "Short videos":
            return "short_videos"
        return "unknown"

    @staticmethod
    def videos(cmpt: bs4.element.Tag) -> str:
        """Classify video carousel components (e.g. 'Trailers & clips' on entity SERPs).

        Matches the layout-class vocabulary used by parse_videos for individual
        video subcards. g-inner-card is intentionally excluded as too generic.
        """
        if cmpt.find("div", {"class": ["VibNM", "mLmaBd", "RzdJxc", "sHEJob"]}):
            return "videos"
        return "unknown"

    @staticmethod
    def knowledge_subcard(cmpt: bs4.element.Tag) -> str:
        """Catch knowledge-panel extension subcards by structural pattern.

        Entity-panel sections (e.g. Cast, Based on the book, Reviews, Behind the
        scenes) share the JNkvid wrapper class and an aria-level=2 heading.
        Specific classifiers (Header.classify, videos, images, people_also_ask)
        must run earlier so their section types win for known headings.
        """
        if not cmpt.find("div", {"class": "JNkvid"}):
            return "unknown"
        if not cmpt.find(attrs={"role": "heading", "aria-level": "2"}):
            return "unknown"
        return "knowledge"

    @staticmethod
    def locations(cmpt: bs4.element.Tag) -> str:
        """Classify locations components (hotels, etc.)"""
        heading = cmpt.find(attrs={"role": "heading"})
        if heading:
            text = heading.get_text(strip=True)
            if text.startswith("Hotels") or text.startswith("More Hotels"):
                return "locations"
        return "unknown"

    @staticmethod
    def top_stories(cmpt: bs4.element.Tag) -> str:
        """Classify top stories components"""
        conditions = [
            cmpt.find("g-scrolling-carousel"),
            cmpt.find("div", {"id": "tvcap"}),
        ]
        return "top_stories" if all(conditions) else "unknown"

    @staticmethod
    def news_quotes(cmpt: bs4.element.Tag) -> str:
        """Classify top stories components"""
        header_div = cmpt.find("g-tray-header", role="heading")
        condition = utils.get_text(header_div, strip=True) == "News quotes"
        return "news_quotes" if condition else "unknown"

    @staticmethod
    def twitter(cmpt: bs4.element.Tag) -> str:
        cmpt_type = "twitter" if cmpt.find("div", {"class": "eejeod"}) else "unknown"
        cmpt_type = ClassifyMain.twitter_type(cmpt, cmpt_type)
        return cmpt_type

    @staticmethod
    def twitter_type(cmpt: bs4.element.Tag, cmpt_type="unknown") -> str:
        """Distinguish twitter types ('twitter_cards', 'twitter_result')"""
        conditions = [
            (cmpt_type == "twitter"),  # Check type (header text)
            utils.get_text(cmpt, strip=True) == "Twitter Results",  # Check text
        ]
        if any(conditions):
            # Differentiate twitter cards (carousel) and twitter result (single)
            carousel = cmpt.find("g-scrolling-carousel")
            cmpt_type = "twitter_cards" if carousel else "twitter_result"
        return cmpt_type
