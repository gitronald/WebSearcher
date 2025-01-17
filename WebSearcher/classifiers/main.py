from .. import logger
log = logger.Logger().start(__name__)

from .header_text import ClassifyHeaderText
from .. import webutils
import bs4

class ClassifyMain:
    """Classify a component from the main section based on its bs4.element.Tag """

    @staticmethod
    def classify(cmpt: bs4.element.Tag) -> str:

        # Ordered list of classifiers to try
        component_classifiers = [
            ClassifyMain.top_stories,        # Check top stories
            ClassifyHeaderText.classify,     # Check levels 2 & 3 header text
            ClassifyMain.news_quotes,        # Check news quotes
            ClassifyMain.img_cards,          # Check image cards
            ClassifyMain.images,             # Check images
            ClassifyMain.knowledge_panel,    # Check knowledge panel
            ClassifyMain.knowledge_block,    # Check knowledge components
            ClassifyMain.banner,             # Check for banners
            ClassifyMain.finance_panel,      # Check finance panel (classify as knowledge)
            ClassifyMain.map_result,         # Check for map results
            ClassifyMain.general_questions,  # Check hybrid general questions
            ClassifyMain.twitter,            # Check twitter cards and results
            ClassifyMain.general,            # Check general components
            ClassifyMain.people_also_ask,    # Check people also ask
            ClassifyMain.knowledge_box,      # Check flights, maps, hotels, events, jobs
            ClassifyMain.local_results,      # Check for local results
            ClassifyMain.available_on,       # Check for available on
        ]

        # Default unknown, exit on first successful classification
        cmpt_type = "unknown"
        for classifier in component_classifiers:
            if cmpt_type != "unknown":  break
            cmpt_type = classifier(cmpt)
        
        return cmpt_type


    @staticmethod
    def available_on(cmpt: bs4.element.Tag) -> str:
        conditions = [("/Available on" in webutils.get_text(cmpt))]
        return "available_on" if any(conditions) else "unknown"

    @staticmethod
    def banner(cmpt: bs4.element.Tag) -> str:
        conditions = [
            "ULSxyf" in cmpt.attrs.get("class", []),
            cmpt.find("div", {"class": "uzjuFc"}),
        ]
        return 'banner' if all(conditions) else "unknown"

    @staticmethod
    def finance_panel(cmpt: bs4.element.Tag) -> str:
        condition = cmpt.find("div", {"id": "knowledge-finance-wholepage__entity-summary"})
        return 'knowledge' if condition else "unknown"

    @staticmethod
    def general(cmpt: bs4.element.Tag) -> str:
        """Classify general components"""

        if "class" in cmpt.attrs:
            conditions_dict = {
                "format-01": cmpt.attrs["class"] == ["g"],
                "format-02": ( ("g" in cmpt.attrs["class"]) &                            
                               any(s in ["Ww4FFb"] for s in cmpt.attrs["class"]) ),
                "format-03": any(s in ["hlcw0c", "MjjYud"] for s in cmpt.attrs["class"]),
                "format-04": cmpt.find('div', {'class': ['g', 'Ww4FFb']}),
            }
        else: 
            conditions_dict = {
                'format-05': all(cmpt.find("div", {"class": c}) for c in ["g", "d4rhi"]),
            }

        layout_matches = [k for k, v in conditions_dict.items() if v]
        # log.debug(f"general layout: {layout_matches}")
        
        return 'general' if any(layout_matches) else "unknown"

    @staticmethod
    def general_questions(cmpt: bs4.element.Tag) -> str:
        hybrid = cmpt.find("div", {"class": "ifM9O"})
        g_accordian = cmpt.find("g-accordion")
        return 'general_questions' if hybrid and g_accordian else "unknown"

    @staticmethod
    def img_cards(cmpt: bs4.element.Tag) -> str:
        """Classify image cards components"""
        if "class" in cmpt.attrs:
            conditions = [
                any(s in ["hlcw0c", "MjjYud"] for s in cmpt.attrs["class"]),
                cmpt.find("block-component"),
            ]
            return 'img_cards' if all(conditions) else "unknown"
        else:
            return "unknown"

    @staticmethod
    def images(cmpt: bs4.element.Tag) -> str:
        conditions = [
            cmpt.find("div", {"id": "imagebox_bigimages"}),  
            cmpt.find("div", {"id":"iur"})
        ]
        return 'images' if any(conditions) else "unknown"

    @staticmethod
    def knowledge_block(cmpt: bs4.element.Tag) -> str:
        """Classify knowledge block components"""
        conditions = [
            webutils.check_dict_value(cmpt.attrs, "class", ["ULSxyf"]),
            cmpt.find('block-component'),
        ]
        return 'knowledge' if all(conditions) else "unknown"

    @staticmethod
    def knowledge_box(cmpt: bs4.element.Tag) -> str:
        """Classify knowledge component types"""
        attrs = cmpt.attrs
        condition = {}
        condition['flights'] = (
            (webutils.check_dict_value(attrs, "jscontroller", "Z2bSc")) |
            bool(cmpt.find("div", {"jscontroller": "Z2bSc"}))
        )
        condition['maps'] = webutils.check_dict_value(attrs, "data-hveid", "CAMQAA")
        condition['hotels'] = cmpt.find("div", {"class": "zd2Jbb"})
        condition['events'] = cmpt.find("g-card", {"class": "URhAHe"})
        condition['jobs'] = cmpt.find("g-card", {"class": "cvoI5e"})
        text_list = list(cmpt.stripped_strings)
        if text_list:
            condition['covid_alert'] = (text_list[0] == "COVID-19 alert")
        for condition_type, conditions in condition.items():
            if conditions:
                return condition_type
        return "unknown"

    @staticmethod
    def knowledge_panel(cmpt: bs4.element.Tag) -> str:
        conditions = [
            cmpt.find("h1", {"class": "VW3apb"}),
            cmpt.find("div", {"class": ["knowledge-panel", "knavi", "kp-blk", "kp-wholepage-osrp"]}),
            cmpt.find("div", {"aria-label": "Featured results", "role": "complementary"}),
            webutils.check_dict_value(cmpt.attrs, "jscontroller", "qTdDb")
        ]
        return 'knowledge' if any(conditions) else "unknown"

    @staticmethod
    def local_results(cmpt: bs4.element.Tag) -> str:
        conditions = [
            cmpt.find("div", {"class": "Qq3Lb"}),  # Places
            cmpt.find("div", {"class": "VkpGBb"})  # Local Results
        ]
        return 'local_results' if any(conditions) else "unknown"

    @staticmethod
    def map_result(cmpt: bs4.element.Tag) -> str:
        condition = cmpt.find("div", {"class": "lu_map_section"})
        return 'map_results' if condition else "unknown"

    @staticmethod
    def people_also_ask(cmpt: bs4.element.Tag) -> str:
        """Secondary check for people also ask, see classify_header for primary"""
        class_list = ["g", "kno-kp", "mnr-c", "g-blk"]
        conditions = webutils.check_dict_value(cmpt.attrs, "class", class_list)
        return 'people_also_ask' if conditions else "unknown"

    @staticmethod
    def top_stories(cmpt: bs4.element.Tag) -> str:
        """Classify top stories components"""
        conditions = [
            cmpt.find("g-scrolling-carousel"), 
            cmpt.find("div", {"id": "tvcap"})
        ]
        return 'top_stories' if all(conditions) else "unknown"

    @staticmethod
    def news_quotes(cmpt: bs4.element.Tag) -> str:
        """Classify top stories components"""
        conditions = [
            cmpt.find("g-tray-header", role="heading"),
        ]
        return 'news_quotes' if all(conditions) else "unknown"

    @staticmethod
    def twitter(cmpt: bs4.element.Tag) -> str:
        cmpt_type = 'twitter' if cmpt.find('div', {'class': 'eejeod'}) else "unknown"
        cmpt_type = ClassifyMain.twitter_type(cmpt, cmpt_type)
        return cmpt_type

    @staticmethod
    def twitter_type(cmpt: bs4.element.Tag, cmpt_type="unknown") -> str:
        """ Distinguish twitter types ('twitter_cards', 'twitter_result')"""
        cmpt_prev = cmpt.find_previous()
        conditions = [
            (cmpt_type == 'twitter'),                                # Check type (header text)
            webutils.get_text(cmpt, strip=True) == "Twitter Results" # Check text
        ]
        if any(conditions):
            # Differentiate twitter cards (carousel) and twitter result (single)
            carousel = cmpt.find("g-scrolling-carousel")
            cmpt_type = "twitter_cards" if carousel else "twitter_result"
        return cmpt_type