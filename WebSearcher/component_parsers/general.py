def parse_general_results(cmpt):
    """Parse a general component

    The ubiquitous blue title, green citation, and black text summary results.
    Sometimes grouped into components of multiple general results. The
    subcomponent general results tend to have a similar theme.
    
    Args:
        cmpt (bs4 object): A general component
    
    Returns:
        list : list of parsed subcomponent dictionaries
    """

    # Legacy compatibility
    subs = cmpt.find_all('div', {'class':'g'})
    subs = subs if subs else [cmpt] 
    
    return [parse_general_result(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

def parse_general_result(sub, sub_rank=0):
    """Parse a general subcomponent
    
    Args:
        sub (bs4 object): A general subcomponent
    
    Returns:
        dict : parsed subresult
    """
    parsed = {
        'type': 'general', 
        'sub_rank': sub_rank
    }

    # Get title
    # title_div = sub.find('h3').find('a')
    title_div = sub.find('div', {'class':'rc'})
    if title_div:
        parsed['title'] = title_div.find('h3').text
        parsed['url'] = title_div.find('a')['href']

    # Get citation
    cite = sub.find('cite')
    parsed['cite'] = cite.text if cite else None
    
    # Get design details
    top_logo = sub.find('img', {'class':'xA33Gc'})
    top_menu = sub.find('div', {'class':'yWc32e'})
    
    parsed['details'] = 'top_cite_logo' if top_logo else ''
    
    if top_menu:
        # If menu has children, ignore URLs and get correct title URL
        has_children = list(top_menu.children)
        if has_children: 
            parsed['details'] += '_menu' 

            for child in top_menu.children:
                child.decompose()
            parsed['url'] = title_div.find('a')['href']

    # Get snippet text
    body = sub.find('span', {'class':'st'})
    if body:
        if ' - ' in body.text[:20]:
            split_body = body.text.split(' - ')
            timestamp = split_body[0]
            parsed['text'] = ' - '.join(split_body[1:])
            parsed['timestamp'] = timestamp
        else:
            parsed['text'] = body.text
            parsed['timestamp'] = None

    # Check for submenu and parse
    if sub.find('div', {'class':'P1usbc'}):
        parsed['type'] = 'general_submenu'
        alinks = sub.find('div', {'class':'P1usbc'}).find_all('a')
        parsed['details'] = parse_general_extra(sub)
    elif sub.find('table'):
        parsed['type'] = 'general_submenu'
        alinks = sub.find('table').find_all('a')
        parsed['details'] = [parse_alink(a) for a in alinks]

    return parsed

def parse_alink(a): 
    return {'text':a.text,'url':a.attrs['href']}

def parse_general_extra(sub):
    """Parse submenu that appears below some general components"""
    item_list = list(sub.find('div', {'class':'P1usbc'}).children)
    ' | '.join([i.text for i in item_list])
    return 