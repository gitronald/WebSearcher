"""SERP component classifiers
"""

from .components import Component
from .classifiers import ClassifyByHeader
from . import webutils
import bs4

def classify_type(cmpt: Component) -> str:
    if cmpt.section == "main":
        if cmpt.type == "unknown":
            return classify_type_main(cmpt.elem)
        else:
            return cmpt.type
    elif cmpt.section == "footer":
        return classify_type_footer(cmpt.elem)
    elif cmpt.section == "header" or cmpt.section == "rhs":
        return cmpt.type
    else:
        print(f"Unknown section: {cmpt.section}")


def classify_type_main(cmpt: bs4.element.Tag) -> str:
    """Component classifier - Main section"""
    
    # Default unknown
    cmpt_type = "unknown"
    
   # Component type classifiers (order matters)
    component_classifiers = [
        classify_top_stories,       # Check top stories
        ClassifyByHeader.classify,  # Check levels 2 & 3 header text
        classify_img_cards,         # Check image cards
        classify_images,            # Check images
        classify_knowledge_panel,   # Check knowledge panel
        classify_knowledge_block,   # Check knowledge components
        classify_banner,            # Check for banners
        classify_finance_panel,     # Check finance panel (classify as knowledge)
        classify_map_result,        # Check for map results
        classify_general_questions, # Check hybrid general questions
        classify_twitter,           # Check twitter cards and results
        classify_general,           # Check general components
        classify_people_also_ask,   # Check people also ask
        classify_knowledge_box,     # Check flights, maps, hotels, events, jobs
        classify_local_results,     # Check for local results
    ]
    for classifier in component_classifiers:
        if cmpt_type != "unknown":  break  # Exit if successful classification
        cmpt_type = classifier(cmpt)

        # Ad-hoc check for available on divs
        if "/Available on" in cmpt.text:
            cmpt_type = "available_on"
    
    return cmpt_type


def classify_top_stories(cmpt: bs4.element.Tag) -> str:
    """Classify top stories components
    
    Checks for g-scrolling-carousel & div id, not all top stories have an h3 tag
    
    """
    conditions = [cmpt.find("g-scrolling-carousel"), 
                  cmpt.find("div", {"id": "tvcap"})]
    return 'top_stories' if all(conditions) else "unknown"


def classify_img_cards(cmpt: bs4.element.Tag) -> str:
    """Classify image cards components"""
    if "class" in cmpt.attrs:
        conditions = [
            any(s in ["hlcw0c", "MjjYud"] for s in cmpt.attrs["class"]),
            cmpt.find("block-component"),
        ]
        return 'img_cards' if all(conditions) else "unknown"
    else:
        return "unknown"


def classify_images(cmpt: bs4.element.Tag) -> str:
    conditions = [
        cmpt.find("div", {"id": "imagebox_bigimages"}),  
        cmpt.find("div", {"id":"iur"})
    ]
    return 'images' if any(conditions) else "unknown"


def classify_knowledge_panel(cmpt: bs4.element.Tag) -> str:
    conditions = [
        cmpt.find("div", {"class": ["knowledge-panel", "knavi", "kp-blk", "kp-wholepage-osrp"]}),
        cmpt.find("div", {"aria-label": "Featured results", "role": "complementary"}),
    ]
    return 'knowledge' if any(conditions) else "unknown"


def classify_finance_panel(cmpt: bs4.element.Tag) -> str:
    condition = cmpt.find("div", {"id": "knowledge-finance-wholepage__entity-summary"})
    return 'knowledge' if condition else "unknown"


def classify_general_questions(cmpt: bs4.element.Tag) -> str:
    hybrid = cmpt.find("div", {"class": "ifM9O"})
    g_accordian = cmpt.find("g-accordion")
    return 'general_questions' if hybrid and g_accordian else "unknown"


def classify_twitter(cmpt: bs4.element.Tag) -> str:
    cmpt_type = 'twitter' if cmpt.find('div', {'class': 'eejeod'}) else "unknown"
    cmpt_type = classify_twitter_type(cmpt, cmpt_type)
    return cmpt_type


def classify_twitter_type(cmpt: bs4.element.Tag, cmpt_type="unknown") -> str:
    """ Distinguish twitter types ('twitter_cards', 'twitter_result')"""

    cmpt_prev = cmpt.find_previous()

    conditions = [
        (cmpt_type == 'twitter'),                          # Check if already classified as twitter (header text)
        False if cmpt_prev is None else (cmpt_prev.text == "Twitter Results")  # Check for twitter results text
    ]
    if any(conditions):
        # Differentiate twitter cards (carousel) and twitter result (single)
        carousel = cmpt.find("g-scrolling-carousel")
        cmpt_type = "twitter_cards" if carousel else "twitter_result"
    
    return cmpt_type


def classify_general(cmpt: bs4.element.Tag) -> str:
    """Classify general components"""
    if "class" in cmpt.attrs:
        conditions = [
            cmpt.attrs["class"] == ["g"],                                # Only class is 'g'
            (("g" in cmpt.attrs["class"]) &                              # OR contains 'g' and 'Ww4FFb'
            any(s in ["Ww4FFb"] for s in cmpt.attrs["class"])),
            any(s in ["hlcw0c", "MjjYud"] for s in cmpt.attrs["class"]), # OR contains 'hlcw0c' (subresults) or 'MjjYud'
            cmpt.find('div', {'class': ['g', 'Ww4FFb']}),                # OR contains 'g' and 'Ww4FFb' element
        ]
    else:
        conditions = [
            all(cmpt.find("div", {"class": c}) for c in ["g", "d4rhi"]), # Contains 'g' and 'd4rhi' elements
        ]
    return 'general' if any(conditions) else "unknown"


def classify_banner(cmpt: bs4.element.Tag) -> str:
    conditions = [
        "ULSxyf" in cmpt.attrs.get("class", []),
        cmpt.find("div", {"class": "uzjuFc"}),
    ]
    return 'banner' if all(conditions) else "unknown"


def classify_knowledge_block(cmpt: bs4.element.Tag) -> str:
    """Classify knowledge block components"""
    conditions = [
        webutils.check_dict_value(cmpt.attrs, "class", ["ULSxyf"]),
        cmpt.find('block-component'),
    ]
    return 'knowledge' if all(conditions) else "unknown"


def classify_people_also_ask(cmpt: bs4.element.Tag) -> str:
    """Secondary check for people also ask, see classify_header for primary"""
    class_list = ["g", "kno-kp", "mnr-c", "g-blk"]
    conditions = webutils.check_dict_value(cmpt.attrs, "class", class_list)
    return 'people_also_ask' if conditions else "unknown"


def classify_map_result(cmpt):
    condition = cmpt.find("div", {"class": "lu_map_section"})
    return 'map_results' if condition else "unknown"


def classify_local_results(cmpt):
    conditions = [
        cmpt.find("div", {"class": "Qq3Lb"}),  # Places
        cmpt.find("div", {"class": "VkpGBb"})  # Local Results
    ]
    return 'local_results' if any(conditions) else "unknown"


def classify_knowledge_box(cmpt: bs4.element.Tag) -> str:
    """Classify knowledge component types
    
    Creates conditions for each label in a dictionary then assigns the 
    label as the component type if it's conditions are met using one, or some 
    combination, of the following three methods:

    1. Check if a component has a specific attribute value
    2. Check if a component contains a specific div
    3. Check if a component has a matching string in its text
    
    """
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

# ------------------------------------------------------------------------------
# Footer Components

def classify_type_footer(cmpt: bs4.element.Tag) -> str:
    """Component classifier

    Args:
        cmpt (bs4.element.Tag): A search component

    Returns:
        str: A classification of the component type (default: "unknown")
    """
    
    # Default unknown
    cmpt_type = "unknown"
    
    layout_1_conditions = [
        ('id' in cmpt.attrs and cmpt.attrs['id'] == 'bres'),
        ('class' in cmpt.attrs and cmpt.attrs['class'] == ['MjjYud']),
    ]

   # Component type classifiers (order matters)
    classifiers_layout_1 = [
        classify_img_cards,
        classify_discover_more,
        classify_searches_related,
    ]

    classifiers_layout_2 = [
        classify_omitted_notice,
    ]
    classifier_list = classifiers_layout_1 if any(layout_1_conditions) else classifiers_layout_2

    for classifier in classifier_list:
        if cmpt_type != "unknown":  break  # Exit if successful classification
        cmpt_type = classifier(cmpt)

    if cmpt_type == 'unknown':
        cmpt_type = classify_type_main(cmpt)
    
    return cmpt_type


def classify_discover_more(cmpt):
    conditions = [
        cmpt.find("g-scrolling-carousel"),
    ]
    return 'discover_more' if all(conditions) else "unknown"


def classify_searches_related(cmpt):
    # log.debug('classifying searches related component')
    known_labels = {'Related', 
                    'Related searches', 
                    'People also search for', 
                    'Related to this search'}
    h3 = cmpt.find('h3')
    h3_matches = [h3.text.strip().startswith(text) for text in known_labels] if h3 else []
    return 'searches_related' if any(h3_matches) else 'unknown'


def classify_omitted_notice(cmpt):
    conditions = [
        cmpt.find("p", {"id":"ofr"}),
        (get_text(cmpt, "h2") == "Notices about Filtered Results"),
    ]
    return "omitted_notice" if any(conditions) else "unknown"

