from .. import webutils

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
    # questions = cmpt.find_all('g-accordion-expander')
    # questions = cmpt.find('section').find_all('div', {'class':'yTrXHe'})
    questions = cmpt.find_all("div", {"class":"related-question-pair"})

    parsed['details'] = [parse_question(q) for q in questions] if questions else None
    return [parsed]

def parse_question(question):
    """Parse an individual question in a "People Also Ask" component"""
    
    alinks = question.find_all('a')
    if not alinks:
        return None
    
    # Get query and URL fragments
    parsed = {
        'qry': webutils.get_text(alinks[-1]),
        'qry_url': alinks[-1]['href'],
    }

    # Get title
    title_divs = [
        question.find('div', {'class':'rc'}),
        question.find('div', {'class':'yuRUbf'})
    ]
    for title_div in filter(None, title_divs):
        parsed['title'] = webutils.get_text(title_div, 'h3')
        parsed['url'] = webutils.get_link(title_div)

    # Get citation
    parsed['cite'] = webutils.get_text(question, 'cite')
    
    # Get text
    replace = ['qry', 'title', 'cite']
    text = question.text.replace('Search for: ', '')
    for key in replace:
        if key in parsed.keys() and parsed[key]:
            text = text.replace(parsed[key], '')
    parsed['text'] = text if text else None

    return parsed