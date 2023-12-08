def get_text(div):
    return '|'.join([d.get_text(separator=' ') for d in div if d.text])

def parse_alink(a):
    return {'url': a['href'], 'text': a.get_text('|')}

def parse_knowledge_panel(cmpt, sub_rank=0):
    """Parse the Knowledge Box
    
    Args:
        cmpt (bs4 object): a knowledge component
    
    Returns:
        list: Return parsed dictionary in a list
    """
    parsed = {'type':'knowledge', 'sub_rank':sub_rank}

    # Get embedded result if it exists
    result = cmpt.find('div', {'class':'rc'})
    if result:
        parsed['title'] = result.find('h3').text
        parsed['url'] = result.find('a')['href']
        parsed['cite'] = result.find('cite').text

    # Get details
    details = {}

    heading = cmpt.find('div', {'role':'heading'})
    details['heading'] = heading.text if heading else None

    alinks = cmpt.find_all('a')
    if alinks:
        details['urls'] = [
            parse_alink(a) 
            for a in alinks 
            if 'href' in a.attrs and a['href'] != '#'
        ] 

    # Get all text
    if (
        cmpt.find('h2') and cmpt.find('h2').text == 'Featured snippet from the web' or 
        cmpt.find('div', {'class':'answered-question'})
    ):
        parsed['sub_type'] = 'featured_snippet'
        span = cmpt.find_all(['span'])
        details['text'] = get_text(span) if span else None

    elif cmpt.find('h2') and cmpt.find('h2').text == 'Unit Converter':
        parsed['sub_type'] = 'unit_converter'
        span = cmpt.find_all(['span'])
        details['text'] = get_text(span) if span else None

    elif cmpt.find('h2') and cmpt.find('h2').text == 'Sports Results':
        parsed['sub_type'] = 'sports'
        div = cmpt.find('div', {'class':'SwsxUd'})
        details['text'] = div.text if div else None

    elif cmpt.find('h2') and cmpt.find('h2').text == 'Weather Result':
        parsed['sub_type'] = 'weather'

    elif (
        cmpt.find('h2') and cmpt.find('h2').text == 'Finance Results' or
        cmpt.find('div', {'id':'knowledge-finance-wholepage__entity-summary'})
    ):
        parsed['sub_type'] = 'finance'

    elif cmpt.find('div', {'role':'button'}) and cmpt.find('div', {'role':'button'}).text == 'Dictionary':
        parsed['sub_type'] = 'dictionary'
        span_first = cmpt.find('span', {'jsslot':''})
        if span_first:
            span = span_first.find_all('span')
            details['text'] = get_text(span).split('Translate')[0] if span else None

    elif (
        cmpt.find('h2') and cmpt.find('h2').text == 'Translation Result' or
        cmpt.find('h2') and cmpt.find('h2').text == 'Resultado de traducción'
    ):
        parsed['sub_type'] = 'translate'
        span = cmpt.find_all('span')
        details['text'] = get_text(span).split('Community Verified')[0] if span else None

    elif cmpt.find('h2') and cmpt.find('h2').text == 'Calculator Result':
        parsed['sub_type'] = 'calculator'

    elif details['heading'] == '2020 US election results':
        parsed['sub_type'] = 'election'
        span = cmpt.find_all(['span'])
        details['text'] = get_text(span) if span else None

    else:
        parsed['sub_type'] = 'panel'
        div = cmpt.find_all(['span','div','a'], text=True)
        details['text'] = get_text(div) if div else None

    # Get image
    img_div = cmpt.find('div', {'class':'img-brk'})
    details['img_url'] = img_div.find('a')['href'] if img_div else None
    parsed['details'] = details

    return [parsed]
