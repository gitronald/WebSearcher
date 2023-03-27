"""SERP component classifiers
"""

from . import webutils

def classify_type(cmpt):
    """Component classifier

    Args:
        cmpt (bs4 object): A Search component

    Returns:
        str: A classification of the component type
    """
    
    # Default unknown
    cmpt_type = "unknown"
    g_tray = cmpt.find("g-tray-header")
    g_section = cmpt.find("g-section-with-header")
    carousel = cmpt.find("g-scrolling-carousel")
    g_accordian = cmpt.find("g-accordion")
    related_question_pair = cmpt.find("related-question-pair")
    knowledge = cmpt.find("div", {"class": ["knowledge-panel", "knavi", "kp-blk"]})
    finance = cmpt.find("div", {"id": "knowledge-finance-wholepage__entity-summary"})
    img_box = cmpt.find("div", {"id": "imagebox_bigimages"})
    hybrid = cmpt.find("div", {"class": "ifM9O"})
    twitter = cmpt.find_previous().text == "Twitter Results"


    # Checks a g-scrolling-carousel for a specific id to classify as not all 
    # top_stories have an h3 tag
    if carousel:
        if webutils.check_dict_value(cmpt.attrs, "class", ["F8yfEe"]):
            cmpt_type = "top_stories"

    if cmpt_type == "unknown":
        cmpt_type = classify_header(cmpt, level=2)
        
    if cmpt_type == "unknown":
        cmpt_type = classify_header(cmpt, level=3)

    if cmpt_type == "unknown" and "class" in cmpt.attrs:
        if any(s in ["hlcw0c", "MjjYud"] for s in cmpt.attrs["class"]):
            cmpt_type = "general"

            if cmpt.find("block-component"):
                # Check for image card block
                cmpt_type = "image_cards"
                
    # Twitter subtype
    if twitter or cmpt_type == "twitter":
        cmpt_type = "twitter_cards" if carousel else "twitter_result"

    # Check for binary match only divs (exists/doesn't exist)
    if cmpt_type == "unknown":
        if img_box:
            cmpt_type = "images"
        elif knowledge:
            cmpt_type = "knowledge"
        elif finance:
            cmpt_type = "knowledge"
        elif hybrid and g_accordian:
            cmpt_type = "general_questions"

    # Check for available on divs
    if "/Available on" in cmpt.text:
        cmpt_type = "available_on"

    # Check if component is only of class 'g'
    if webutils.check_dict_value(cmpt.attrs, "class", ["g"]):
        cmpt_type = "general"

    # check for people also ask
    if cmpt_type == "unknown":
        cmpt_type = classify_people_also_ask(cmpt)

    # check for flights, maps, hotels, events, jobs
    if cmpt_type == "unknown":
        cmpt_type = classify_knowledge_box(cmpt)

    # Check for hidden components
    condition = webutils.check_dict_value(cmpt.attrs, "class", ["ULSxyf"])
    if cmpt_type == "unknown" and condition:

        if cmpt.find('promo-throttler'):
            cmpt_type = "hidden-survey"
        
        elif cmpt.find('block-component'):
            cmpt_type = 'knowledge'
    
    # Return type or unknown (default)
    return cmpt_type


def classify_header(cmpt, level):
    """Check text in common headers for dict matches"""

    # Find headers
    if level == 2:
        header_dict = {
            "Featured snippet from the web": "knowledge",
            "Unit Converter": "knowledge",
            "Sports Results": "knowledge",
            "Weather Result": "knowledge",
            "Finance Results": "knowledge",
            "Calculator Result": "knowledge",
            "Translation Result": "knowledge",
            "Resultado de traducción": "knowledge",
            "Knowledge Result": "knowledge",
            "Jobs": "jobs",
            "Top stories": "top_stories",
            "Web results": "general",
            "Resultados de la Web": "general",
            "Web Result with Site Links": "general",
            "Local Results": "local_results",
            "Map Results": "map_results",
            "People also ask": "people_also_ask",
            "Twitter Results": "twitter",
            "Related searches": "searches_related",
            "Directions": "directions",
        }
    elif level == 3:
        header_dict = {
            "Videos": "videos",
            "Top stories": "top_stories",
            "Quotes in the news": "news_quotes",
            "Latest from": "latest_from",
            "View more videos": "view_more_videos",
            "View more news": "view_more_news",
            "Images for": "images",
            "Scholarly articles for": "scholarly_articles",
            "Recipes": "recipes",
            "Popular products": "products",
            "Related searches": "searches_related",
        }

    # Find headers, eg for level 2: <h2> or <div aria-level="2" role="heading">
    header_list = [
        cmpt.find(f"h{level}"),
        cmpt.find("div", {'aria-level':f"{level}", "role":"heading"})
    ]

   # Check for string matches in header text e.g. `h2.text`
    for header in filter(None, header_list):
        for text, label in header_dict.items():
            if header.text.startswith(text):
                return label

    # Return unknown if no matches
    return "unknown"


def classify_people_also_ask(cmpt):
    """Secondary check for people also ask, see classify_header for primary"""
    class_list = ["g", "kno-kp", "mnr-c", "g-blk"]
    conditions = webutils.check_dict_value(cmpt.attrs, "class", class_list)
    return 'people_also_ask' if conditions else "unknown"


def classify_knowledge_box(cmpt):
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
