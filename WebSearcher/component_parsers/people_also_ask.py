def parse_people_also_ask(cmpt, sub_rank=0):
    """Parse a "People Also Ask" component

    These components contain a list of questions, which drop down to reveal
    summarized information and/or general component results. However, advanced 
    scraping is required to preserve the information in the dropdown, which only
    loads after a subcomponent is clicked.
    
    Args:
        cmpt (bs4 object): A "People Also Ask" component
    
    Returns:
        list : list of parsed subcomponent dictionaries
    """
    parsed = {'type':'people_also_ask', 'sub_rank':sub_rank}
    questions = cmpt.find_all('g-accordion-expander')
    # questions = cmpt.find('section').find_all('div', {'class':'yTrXHe'})
    parsed['details'] = [q.text for q in questions] if questions else None
    return [parsed]
