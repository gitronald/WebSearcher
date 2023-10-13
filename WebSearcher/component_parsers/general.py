import re
from ..webutils import get_text

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

    # 2023.05.09 - finds subs
    additional = cmpt.find_all('div', {'class': 'd4rhi'})
    if additional:
        # Catch general_subresult
        # this means that there is a sub-element, with class d4rhi
        # the first div child of the div.g is the first sub element
        first = cmpt.find('div')
        subs = [first] + additional

    # 2023.05.09 - handles duplicate .g tags within one component
    if cmpt.find('div', {'class':'g'}):
        parent_g = cmpt.find('div', {'class':'g'})
        if parent_g.find_all('div', {'class':'g'}):
            # this means that there is a .g element inside of another .g element,
            # and it would otherwise get double-counted
            # we just want to keep the parent .g element in this case
            subs = [parent_g]
    subs = subs if subs else [cmpt]

    parsed = [parse_general_result(sub, sub_rank) for sub_rank, sub in enumerate(subs)]
    return parsed

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
    title_div1 = sub.find('div', {'class':'rc'})
    title_div2 = sub.find('div', {'class':'yuRUbf'})
    if title_div1:
        parsed['title'] = title_div1.find('h3').text
        parsed['url'] = title_div1.find('a')['href']
    elif title_div2:
        parsed['title'] = title_div2.find('h3').text
        parsed['url'] = title_div2.find('a')['href']

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
    body = sub.find('span', {'class':'st'}) or sub.find('div', {'class': 'VwiC3b'})
    if body:
        if ' - ' in body.text[:20]:
            split_body = body.text.split(' - ')
            timestamp = split_body[0]
            parsed['text'] = ' - '.join(split_body[1:])
            parsed['timestamp'] = timestamp
        if ' \u2014 ' in body.text[:23]:
            split_body = body.text.split(' \u2014 ')
            timestamp = split_body[0]
            parsed['text'] = ' \u2014 '.join(split_body[1:])
            parsed['timestamp'] = timestamp
        else:
            parsed['text'] = body.text
            parsed['timestamp'] = None

    parsed['text'] = get_text(sub, 'div', {'class':'VwiC3b'})

    # Check for subtype and parse 
    if 'class' in sub.attrs:
        if sub.attrs['class'] == 'd4rhi':
            parsed['subtype'] == 'subresult'
    elif sub.find('g-review-stars'):
        parsed['subtype'] = 'submenu_rating'
        sibling = sub.find('g-review-stars').next_sibling
        if sibling:
            text = str(sibling).strip()
            if len(text):
                parsed['details'] = parse_ratings(text.split('-'))
    elif sub.find('div', {'class': ['P1usbc', 'IThcWe']}):
        parsed['subtype'] = 'submenu'
        alinks = sub.find('div', {'class': ['P1usbc', 'IThcWe']}).find_all('a')
        #parsed['details'] = parse_general_extra(sub)
        parsed['details'] = [parse_alink(a) for a in alinks if 'href' in a.attrs]
    elif sub.find('table'):
        parsed['subtype'] = 'submenu'
        alinks = sub.find('table').find_all('a')
        parsed['details'] = [parse_alink(a) for a in alinks if 'href' in a.attrs]
    elif sub.find('div', {'class': ['osl', 'jYOxx']}):
        parsed['subtype'] = 'submenu_mini'  
        alinks = sub.find('div', {'class':['osl','jYOxx']}).find_all('a')
        parsed['details'] = [parse_alink(a) for a in alinks if 'href' in a.attrs]
    elif sub.find('div', {'class': re.compile('fG8Fp')}):
        alinks = sub.find('div', {'class': re.compile('fG8Fp')}).find_all('a')
        text = sub.find('div', {'class': re.compile('fG8Fp')}).text
        if len(alinks) and 'Cited by' in alinks[0].text:
            parsed['subtype'] = 'submenu_scholarly'
            parsed['details'] = [parse_alink(a) for a in alinks if 'href' in a.attrs]
        elif '$' in text:
            parsed['subtype'] = 'submenu_product'
            parsed['details'] = parse_product(text) 
    return parsed

def parse_alink(a): 
    return {'text':a.text,'url':a.attrs['href']}

def parse_general_extra(sub):
    """Parse submenu that appears below some general components"""
    item_list = list(sub.find('div', {'class':'P1usbc'}).children)
    return ' | '.join([i.text for i in item_list])

def parse_ratings(text):
    """Parse ratings that appear below some general components"""

    text = [t.strip() for t in text]
    numeric = re.compile('^\d*[.]?\d*$')
    rating = re.split('Rating: ', text[0])[-1]
    if numeric.match(rating):
        details = {'rating': float(rating)}
    else:
        details = {'rating': rating}
    
    if len(text) > 1:
        str_match_0 = re.compile(' vote[s]?| review[s]?')
        str_match_1 = re.compile('Review by')
        if str_match_0.search(text[1]):
            reviews = re.split(str_match_0, text[1])[0]
            reviews = reviews.replace(',','')[1:] # [1:] drops unicode char
            details['reviews'] = int(reviews)
        elif str_match_1.search(text[1]):
            details['reviews'] = 1
        
    # could parse other fields
    # (price, os, category) for products
    # (time, cals) for recipes

    return details

def parse_product(text):
    """Parse price and stock that appears below some general components"""
    split_match = re.compile('-|·')
    text = re.split(split_match, text)
    if len(text) == 1:
        return {'price': text[0].strip()[1:]}
    else:
        return {'price': text[0].strip()[1:], 'stock': text[1].strip()[1:]}