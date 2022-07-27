# Classifications based on H2 Headings
h2_matches = {
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
    "Web results": "general",
    "Resultados de la Web": "general",
    "Web Result with Site Links": "general",
    "Local Results": "local_results",
    "Map Results": "map_results",
    "People also ask": "people_also_ask",
    "Twitter Results": "twitter",
}

# Classifications based on H3 Headings
h3_matches = {
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


def classify_type(cmpt, cmpt_type="unknown"):
    """Component classifier

    Args:
        cmpt (bs4 object): A Search component

    Returns:
        str: A classification of the component type
    """

    # Define HTML references (sets to `None` if it doesn't exist)
    h2 = cmpt.find("h2")
    h3 = cmpt.find("h3")
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

    if "class" in cmpt.attrs.keys() and cmpt.attrs["class"][0] == "hlcw0c":
        cmpt_type = "general"

    # Checks a g-scrolling-carousel for a specific id to classify as top stories as not all
    # top stories have an h3 tag
    if carousel:
        if "class" in carousel.attrs and carousel.attrs["class"][0] == "F8yfEe":
            cmpt_type = "top_stories"

    # Check component header
    cmpt_header = cmpt.find("div", {"class": "mfMhoc"})
    if cmpt_header:
        for text, ctype in h3_matches.items():
            if cmpt_header.text.startswith(text):
                cmpt_type = ctype

    # Check `h2.text` for string matches
    if h2:
        for text, ctype in h2_matches.items():
            if h2.text.startswith(text):
                cmpt_type = ctype

    # Check `h3.text` for string matches
    if h3:
        for text, ctype in h3_matches.items():
            if h3.text.startswith(text):
                cmpt_type = ctype

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
    if "class" in cmpt.attrs:
        if cmpt.attrs["class"] == ["g"]:
            cmpt_type = "general"

    # check for people also ask
    if "class" in cmpt.attrs.keys() and cmpt.attrs["class"] == [
        "g",
        "kno-kp",
        "mnr-c",
        "g-blk",
    ]:
        cmpt_type = "people_also_ask"

    # check for flights, maps, hotels, events, jobs
    if cmpt_type == "unknown":
        if (
            "jscontroller" in cmpt.attrs.keys()
            and cmpt.attrs["jscontroller"] == "Z2bSc"
        ):
            cmpt_type = "flights"
        elif cmpt.find("div", {"jscontroller": "Z2bSc"}):
            cmpt_type = "flights"
        elif "data-hveid" in cmpt.attrs.keys() and cmpt.attrs["data-hveid"] == "CAMQAA":
            cmpt_type = "maps"
        elif cmpt.find("div", {"jsmodel": "xjY0Ec"}):
            cmpt_type = "hotels"
        elif cmpt.find("div", {"data-hveid": ["CAEQAQ", "CAEQAw"]}):
            cmpt_type = "hotels"
        elif cmpt.find("g-card", {"class": "URhAHe"}):
            cmpt_type = "events"
        elif cmpt.find("g-card", {"class": "cvoI5e"}):
            cmpt_type = "jobs"
        else:
            cmpt_text = [text for text in cmpt.stripped_strings]
            if len(cmpt_text) >= 1 and cmpt_text[0] == "COVID-19 alert":
                cmpt_type = "covid_alert"

    # Return type or unknown (default)
    return cmpt_type
