import re
from ..models import BaseResult
from ..webutils import get_text, get_link

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
    
    if is_general_video(sub):
        return parse_general_video(sub, sub_rank=sub_rank)

    # Get title and text body divs
    title_div = sub.find('div', {'class':'rc'}) or sub.find('div', {'class':'yuRUbf'})
    body_div = sub.find('span', {'class':'st'}) or sub.find('div', {'class': 'VwiC3b'})

    parsed = BaseResult(
        type='general',
        sub_rank=sub_rank,
        title=get_text(title_div, 'h3') if title_div else '',
        url=get_link(title_div) if title_div else '',
        text=get_text(body_div) if body_div else '',
        cite=get_text(sub, 'cite')
    )

    # Get subtype details
    parsed = parse_subtype_details(sub, parsed)
    return parsed.model_dump()


def parse_alink(a): 
    return {'text':a.text,'url':a.attrs['href']}


def parse_alink_list(alinks):
    return [parse_alink(a) for a in alinks if 'href' in a.attrs]


def parse_subtype_details(sub, parsed):
    # Check for subtype and parse details

    details = {}

    # If top menu with children, ignore URLs and get correct title URL
    top_menu = sub.find('div', {'class':'yWc32e'})    
    if top_menu:
        has_children = list(top_menu.children)
        if has_children: 
            for child in top_menu.children:
                child.decompose()
            if sub.find('h3'):
                parsed.url = sub.find('h3').find('a')['href']

    # Subtype specific detail parsing
    if 'class' in sub.attrs:
        if sub.attrs['class'] == 'd4rhi':
            parsed.sub_type == 'subresult'
    
    # Submenu - rating
    elif sub.find('g-review-stars'):
        parsed.sub_type = 'submenu_rating'
        sibling = sub.find('g-review-stars').next_sibling
        if sibling:
            text = str(sibling).strip()
            if len(text):
                ratings = parse_ratings(text.split('-'))
                details.update(ratings)
    
    # Submenu - list format
    elif sub.find('div', {'class': ['P1usbc', 'IThcWe']}):
        parsed.sub_type = 'submenu'
        submenu_div = sub.find('div', {'class': ['P1usbc', 'IThcWe']})
        if submenu_div:
            alinks = submenu_div.find_all('a')
            details['links'] = parse_alink_list(alinks)

    # Submenu - table format
    elif sub.find('table'):
        parsed.sub_type = 'submenu'
        alinks = sub.find('table').find_all('a')
        details['links'] = parse_alink_list(alinks)

    # Mini submenu
    elif sub.find('div', {'class': ['osl', 'jYOxx']}):
        parsed.sub_type = 'submenu_mini'  
        alinks = sub.find('div', {'class':['osl','jYOxx']}).find_all('a')
        details['links'] = parse_alink_list(alinks)

    elif sub.find('div', {'class': re.compile('fG8Fp')}):

        # Scholar results
        alinks = sub.find('div', {'class': re.compile('fG8Fp')}).find_all('a')
        if len(alinks) and 'Cited by' in alinks[0].text:
            parsed.sub_type = 'submenu_scholarly'
            details['links'] = parse_alink_list(alinks)

        # Product results
        text = get_text(sub, 'div', {'class': re.compile('fG8Fp')})
        if not alinks and '$' in text:
            parsed.sub_type = 'submenu_product'
            product_details = parse_product(text) 
            details.update(product_details)
    
    parsed.details = details if details else None          
    return parsed


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


# ------------------------------------------------------------------------------
# General Video Results


def is_general_video(cmpt):
    """Check for a unique class name specific to video results"""
    class_list = cmpt.get('class', [])
    return 'PmEWq' in class_list


def parse_general_video(sub, sub_rank: int = 0):
    """Parse a general video component

    Args:
        cmpt (bs4 object): A general video component
    
    Returns:
        VideoResult: Parsed information of the video
    """

    video_result = BaseResult(
        type='general',
        sub_type='video',
        sub_rank=sub_rank,
        title=get_result_text(sub, 'h3.LC20lb'),
        url=sub.select_one('a[href]').get('href', '') if sub.select_one('a[href]') else '',
        text=get_result_text(sub, '.ITZIwc'),
        cite=get_result_text(sub, 'cite', strip=False),
        details=get_result_details(sub),
    )
    return video_result.model_dump()


def get_result_text(cmpt, selector, strip=True):
    element = cmpt.select_one(selector)
    return element.get_text(strip=strip) if element else ''


def get_result_details(cmpt):
    details = {"source": get_result_text(cmpt, '.gqF9jc', strip=False),
               "duration": get_result_text(cmpt, '.JIv15d')}
    return details