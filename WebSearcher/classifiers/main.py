from typing import Any

import bs4

from .. import logger, utils
from ..component_types import header_text_to_type

log = logger.Logger().start(__name__)


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

        # Lazy generator over potential header divs (defers find_all until iterated)
        selectors: list[tuple[str | None, dict]] = [
            (f"h{level}", {"role": "heading"}),
            (f"h{level}", {"class": ["O3JH7", "q8U8x", "mfMhoc"]}),
            (None, {"aria-level": f"{level}", "role": "heading"}),
        ]
        headers = (
            h
            for name, attrs in selectors
            for h in (cmpt.find_all(name, attrs=attrs) if name else cmpt.find_all(attrs=attrs))
        )

        # Check header text for known title matches
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

        # Ordered list of classifiers to try
        component_classifiers = [
            ClassifyMain.locations,  # Check locations (hotels, etc.) before top_stories
            ClassifyMain.top_stories,  # Check top stories
            ClassifyMain.discussions_and_forums,  # Check discussions and forums
            ClassifyMainHeader.classify,  # Check levels 2 & 3 header text
            ClassifyMain.news_quotes,  # Check news quotes
            ClassifyMain.img_cards,  # Check image cards
            ClassifyMain.images,  # Check images
            ClassifyMain.ai_overview,  # Check AI overview
            ClassifyMain.knowledge_panel,  # Check knowledge panel
            ClassifyMain.knowledge_block,  # Check knowledge components
            ClassifyMain.banner,  # Check for banners
            ClassifyMain.finance_panel,  # Check finance panel (classify as knowledge)
            ClassifyMain.map_result,  # Check for map results
            ClassifyMain.general_questions,  # Check hybrid general questions
            ClassifyMain.short_videos,  # Check short videos carousel
            ClassifyMain.twitter,  # Check twitter cards and results
            ClassifyMain.flights,  # Check flights widgets
            ClassifyMain.general,  # Check general components
            ClassifyMain.people_also_ask,  # Check people also ask
            ClassifyMain.knowledge_box,  # Check flights, maps, hotels, events, jobs
            ClassifyMain.local_results,  # Check for local results
            ClassifyMain.available_on,  # Check for available on
        ]

        # Default unknown, exit on first successful classification
        cmpt_type = "unknown"
        for classifier in component_classifiers:
            if cmpt_type != "unknown":
                break
            cmpt_type = classifier(cmpt)

        return cmpt_type

    @staticmethod
    def discussions_and_forums(cmpt: bs4.element.Tag) -> str:
        heading = cmpt.find("div", {"class": "IFnjPb", "role": "heading"})
        if heading and heading.get_text(strip=True).startswith("Discussions and forums"):
            return "discussions_and_forums"
        return "unknown"

    @staticmethod
    def available_on(cmpt: bs4.element.Tag) -> str:
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
        """Classify AI Overview components"""
        h2 = cmpt.find("h2")
        conditions = [
            cmpt.find("div", {"class": "Fzsovc"}),
            h2 is not None and h2.get_text(strip=True) == "AI Overview",
        ]
        return "knowledge" if any(conditions) else "unknown"

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
        text_list = list(cmpt.stripped_strings)
        if text_list:
            condition["covid_alert"] = text_list[0] == "COVID-19 alert"
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
    def short_videos(cmpt: bs4.element.Tag) -> str:
        """Classify short videos carousel"""
        heading = cmpt.find("span", {"role": "heading", "class": "IFnjPb"})
        if heading and heading.get_text(strip=True) == "Short videos":
            return "short_videos"
        return "unknown"

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
