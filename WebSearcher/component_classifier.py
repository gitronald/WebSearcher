"""SERP component classifiers
"""

from . import webutils
import bs4

# Header (e.g., <h2> and <div aria-level="2" role="heading">) text -> WS type
HEADER_LVL2_MAPPING = {
    'Calculator Result': 'knowledge',
    'Directions': 'directions',
    'Discussions and forums': 'discussions_and_forums',
    'Featured snippet from the web': 'knowledge',
    'Finance Results': 'knowledge',
    'Jobs': 'jobs',
    'Knowledge Result': 'knowledge',
    'Local Results': 'local_results',
    'Map Results': 'map_results',
    'People also ask': 'people_also_ask',
    'Perspectives & opinions': 'perspectives',
    'Perspectives': 'perspectives',
    'Related searches': 'searches_related',
    'Resultado de traducción': 'knowledge',
    'Resultados de la Web': 'general',
    'Sports Results': 'knowledge',
    'Top stories': 'top_stories',
    'Local news': 'local_news',
    'Translation Result': 'knowledge',
    'Twitter Results': 'twitter',
    'Unit Converter': 'knowledge',
    'Weather Result': 'knowledge',
    'Web Result with Site Links': 'general',
    'Web results': 'general',
    'Complementary Results': 'general',
    'Videos': 'videos',
}

# Header (e.g., <h3> and <div aria-level="3" role="heading">) text -> WS type
HEADER_LVL3_MAPPING = {
    'Images for': 'images',
    'Latest from': 'latest_from',
    'Popular products': 'products',
    'Quotes in the news': 'news_quotes',
    'Recipes': 'recipes',
    'Related searches': 'searches_related',
    'Scholarly articles for': 'scholarly_articles',
    'Top stories': 'top_stories',
    'Videos': 'videos',
    'View more news': 'view_more_news',
    'View more videos': 'view_more_videos'
}


def classify_type(cmpt: bs4.element.Tag) -> str:
    """Component classifier

    Args:
        cmpt (bs4.element.Tag): A search component

    Returns:
        str: A classification of the component type (default: "unknown")
    """
    
    # Default unknown
    cmpt_type = "unknown"
    
   # Component type classifiers (order matters)
    component_classifiers = [
        classify_top_stories,        # Check top stories
        classify_header_lvl2,        # Check level 2 header text
        classify_header_lvl3,        # Check level 3 header text
        classify_img_cards,          # Check image cards
        classify_images,             # Check images
        classify_knowledge_panel,    # Check knowledge panel
        classify_knowledge_block,    # Check knowledge components
        classify_banner,             # Check for banners
        classify_finance_panel,      # Check finance panel (classify as knowledge)
        classify_map_result,         # Check for map results
        classify_general_questions,  # Check hybrid general questions
        classify_twitter,            # Check twitter cards and results
        classify_general,            # Check general components
        classify_general_subresult,  # Check general result with submenu
        classify_people_also_ask,    # Check people also ask
        classify_knowledge_box,      # Check flights, maps, hotels, events, jobs
        classify_hidden_survey,      # Check for hidden surveys
        classify_local_results,      # Check for local results
    ]
    for classifier in component_classifiers:
        if cmpt_type != "unknown":  break  # Exit if successful classification
        cmpt_type = classifier(cmpt)

        # Ad-hoc check for available on divs
        if "/Available on" in cmpt.text:
            cmpt_type = "available_on"
    
    return cmpt_type


def classify_header_lvl2(cmpt: bs4.element.Tag):
    # Wrapper for header level 2
    return classify_header(cmpt, level=2)

def classify_header_lvl3(cmpt: bs4.element.Tag):
    # Wrapper for header level 2
    return classify_header(cmpt, level=3)

def classify_header(cmpt: bs4.element.Tag, level):
    """Check text in common headers for dict matches"""

    # Find headers
    if level == 2:
        header_dict = HEADER_LVL2_MAPPING
    elif level == 3:
        header_dict = HEADER_LVL3_MAPPING
    
    # Find headers, eg for level 2: <h2> and <div aria-level="2" role="heading">
    header_list = []
    header_list.extend(cmpt.find_all(f"h{level}", {"role":"heading"}))
    header_list.extend(cmpt.find_all("div", {'aria-level':f"{level}", "role":"heading"}))

   # Check for string matches in header text e.g. `h2.text`
    for header in filter(None, header_list):
        for text, label in header_dict.items():
            if header.text.strip().startswith(text):
                return label

    # Return unknown if no matches
    return "unknown"


def classify_top_stories(cmpt: bs4.element.Tag):
    """Classify top stories components
    
    Checks for g-scrolling-carousel & div id, not all top stories have an h3 tag
    
    """
    conditions = [cmpt.find("g-scrolling-carousel"), 
                  cmpt.find("div", {"id": "tvcap"})]
    return 'top_stories' if all(conditions) else "unknown"


def classify_img_cards(cmpt: bs4.element.Tag):
    """Classify image cards components"""
    if "class" in cmpt.attrs:
        conditions = [
            any(s in ["hlcw0c", "MjjYud"] for s in cmpt.attrs["class"]),
            cmpt.find("block-component"),
        ]
        return 'img_cards' if all(conditions) else "unknown"
    else:
        return "unknown"


def classify_images(cmpt: bs4.element.Tag):
    conditions = [
        cmpt.find("div", {"id": "imagebox_bigimages"}),  
        cmpt.find("div", {"id":"iur"})
    ]
    return 'images' if any(conditions) else "unknown"


def classify_knowledge_panel(cmpt: bs4.element.Tag):
    condition = cmpt.find("div", {"class": ["knowledge-panel", "knavi", "kp-blk"]})
    return 'knowledge' if condition else "unknown"


def classify_finance_panel(cmpt: bs4.element.Tag):
    condition = cmpt.find("div", {"id": "knowledge-finance-wholepage__entity-summary"})
    return 'knowledge' if condition else "unknown"


def classify_general_questions(cmpt: bs4.element.Tag):
    hybrid = cmpt.find("div", {"class": "ifM9O"})
    g_accordian = cmpt.find("g-accordion")
    return 'general_questions' if hybrid and g_accordian else "unknown"


def classify_twitter(cmpt: bs4.element.Tag):
    cmpt_type = 'twitter' if cmpt.find('div', {'class': 'eejeod'}) else "unknown"
    cmpt_type = classify_twitter_type(cmpt, cmpt_type)
    return cmpt_type


def classify_twitter_type(cmpt: bs4.element.Tag, cmpt_type="unknown"):
    """ Distinguish twitter types ('twitter_cards', 'twitter_result')"""
    conditions = [
        (cmpt_type == 'twitter'),                         # Check if already classified as twitter (header text)
        (cmpt.find_previous().text == "Twitter Results")  # Check for twitter results text
    ]
    if any(conditions):
        # Differentiate twitter cards (carousel) and twitter result (single)
        carousel = cmpt.find("g-scrolling-carousel")
        cmpt_type = "twitter_cards" if carousel else "twitter_result"
    
    return cmpt_type


def classify_general(cmpt: bs4.element.Tag):
    """Classify general components"""
    if "class" in cmpt.attrs:
        conditions = [
            cmpt.attrs["class"] == ["g"],                                # Only class is 'g'
            (("g" in cmpt.attrs["class"]) &                              # OR contains 'g' and 'Ww4FFb'
            any(s in ["Ww4FFb"] for s in cmpt.attrs["class"])),
            any(s in ["hlcw0c", "MjjYud"] for s in cmpt.attrs["class"]), # OR contains 'hlcw0c' or 'MjjYud'
            cmpt.find('div', {'class': ['g', 'Ww4FFb']}),                # OR contains 'g' and 'Ww4FFb' element
        ]
        return 'general' if any(conditions) else "unknown"
    else:
        return "unknown"


def classify_general_subresult(cmpt: bs4.element.Tag):
    # A general result followed by an indented result from the same domain
    mask_class1 = cmpt.find_all('div', {'class':'g'})
    mask_class2 = cmpt.find_all('div', {'class':'d4rhi'})
    mask_sum = len(mask_class1) + len(mask_class2)
    return 'general_subresult' if mask_sum > 1 else "unknown"


def classify_banner(cmpt: bs4.element.Tag):
    conditions = [
        webutils.check_dict_value(cmpt.attrs, "class", ["ULSxyf"]),
        cmpt.find("div", {"class": "uzjuFc"}),
    ]
    return 'banner' if all(conditions) else "unknown"


def classify_hidden_survey(cmpt: bs4.element.Tag):
    """Classify hidden survey components"""
    conditions = [
        webutils.check_dict_value(cmpt.attrs, "class", ["ULSxyf"]),
        cmpt.find('promo-throttler'),
    ]
    return 'hidden_survey' if all(conditions) else "unknown"


def classify_knowledge_block(cmpt: bs4.element.Tag):
    """Classify knowledge block components"""
    conditions = [
        webutils.check_dict_value(cmpt.attrs, "class", ["ULSxyf"]),
        cmpt.find('block-component'),
    ]
    return 'knowledge' if all(conditions) else "unknown"


def classify_people_also_ask(cmpt: bs4.element.Tag):
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


def classify_knowledge_box(cmpt: bs4.element.Tag):
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
        return condition_type if conditions else "unknown"
