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
    parsed['details'] = [parse_question(q) for q in questions] if questions else None
    return [parsed]

def parse_question(question):
    """Parse an individual question in a "People Also Ask" component"""
    alinks = question.find_all('a')

    if not alinks:
        return None
        
    parsed = {
        'qry': alinks[-1].text,
        'qry_url': alinks[-1]['href'],
    }

    # Get title
    title_div1 = question.find('div', {'class':'rc'})
    title_div2 = question.find('div', {'class':'yuRUbf'})
    if title_div1:
        parsed['title'] = title_div1.find('h3').text
        parsed['url'] = title_div1.find('a')['href']
    elif title_div2:
        parsed['title'] = title_div2.find('h3').text
        parsed['url'] = title_div2.find('a')['href']

    # Get citation
    cite = question.find('cite')
    if cite:
        parsed['cite'] = cite.text

    # Get text
    replace = ['qry', 'title', 'cite']
    text = question.text.replace('Search for: ', '')
    for r in replace:
        if r in parsed.keys():
            text = text.replace(parsed[r], '')
    parsed['text'] = text

    return parsed