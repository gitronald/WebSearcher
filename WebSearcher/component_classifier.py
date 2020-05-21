# Classifications based on H2 Headings
h2_matches = {
    "Featured snippet from the web": "knowledge",
    "Unit Converter": "knowledge",
    "Sports Results": "knowledge",
    "Web results": "general",
    "Resultados de la Web": "general",
    "Web Result with Site Links": "general",
    "Local Results": "local_results",
    "Map Results": "map_results",
    "People also ask": "people_also_ask",
    "Twitter Results": "twitter"
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
    "Scholarly articles for": "scholarly_articles"
}

def classify_type(cmpt, cmpt_type='unknown'):
    """Component classifier
    
    Args:
        cmpt (bs4 object): A Search component
    
    Returns:
        str: A classification of the component type
    """

    # Define HTML references (sets to `None` if it doesn't exist)
    h2 = cmpt.find('h2')
    h3 = cmpt.find('h3')
    g_tray = cmpt.find('g-tray-header')
    g_section = cmpt.find('g-section-with-header')
    g_accordian = cmpt.find('g-accordion')
    related_question_pair = cmpt.find('related-question-pair')
    knowledge = cmpt.find('div', {'class':['knowledge-panel','knavi','kp-blk']})
    img_box = cmpt.find('div', {'id':'imagebox_bigimages'})
    hybrid = cmpt.find('div', {'class':'ifM9O'})
    twitter = cmpt.find_previous().text == "Twitter Results"

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
    
    if twitter or cmpt_type == 'twitter':
        cmpt_type = 'twitter_cards' if g_section else 'twitter_result'

    # Check for binary match only divs (exists/doesn't exist)
    if cmpt_type == 'unknown':
        if img_box: cmpt_type = 'images'
        if knowledge: cmpt_type = 'knowledge'
        if hybrid and g_accordian: cmpt_type = 'general_questions'

    # Check for available on divs
    if '/Available on' in cmpt.text:
        cmpt_type = 'available_on'

    # Check if component is only of class 'g'
    if 'class' in cmpt.attrs:
        if cmpt.attrs['class'][0] == 'g':
            cmpt_type = 'general'

    # Return type or unknown (default)
    return cmpt_type