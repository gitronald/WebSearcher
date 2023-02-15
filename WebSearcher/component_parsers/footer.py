from .. import component_classifier
from .. import logger
log = logger.Logger().start(__name__)

import traceback

def get_footer_parser(cmpt_type):
    if cmpt_type == 'image_cards':
        return parse_image_cards
    elif cmpt_type == 'searches_related':
        return parse_searches_related
    elif cmpt_type == 'discover_more':
        return parse_discover_more

def extract_footer(soup):
    return soup.find('div', {'id':'botstuff'})

def find_all_divs(soup, name, attr, filter_empty=True):
    divs = soup.find_all(name, attr)
    if filter_empty:
        divs = [c for c in divs if c]
        divs = [c for c in divs if c.text != '']
    return divs if divs else None

def extract_footer_components(footer):
    footer_cmpts = find_all_divs(footer, 'div', {'id':['bres', 'brs']})

    # Expand component list with alternative layouts
    expanded = []
    for cmpt in footer_cmpts:
        divs = find_all_divs(cmpt, "div", {"class":"MjjYud"})
        if divs and len(divs) > 1:
            expanded.extend(divs)
        else:
            expanded.append(cmpt)
    
    return expanded

def classify_footer_component(cmpt):

    gsection = cmpt.find('g-section-with-header')
    subs = cmpt.find_all('div', {'class':'g'})
    h3 = cmpt.find('h3')

    if 'id' in cmpt.attrs and cmpt.attrs['id'] == 'bres':
        if subs:
            return 'image_cards'
        elif cmpt.find('g-scrolling-carousel'):
            return 'discover_more'
        elif h3 and h3.text.strip() == 'Related searches':
            return 'searches_related'
        elif h3 and h3.text.strip() == 'People also search for':
            return 'searches_related'
        else:
            return 'unknown'
    elif gsection:
        return 'searches_related'
    else:
        return 'unknown'


def parse_footer_cmpt(cmpt, cmpt_type='', cmpt_rank=0):
    """Classify the footer component and parse it""" 
    cmpt_type = cmpt_type if cmpt_type else classify_footer_component(cmpt)
    parsed = {
        'type': cmpt_type,
        'cmpt_rank':cmpt_rank,
        'sub_rank':0
    }
       
    if cmpt_type == 'unknown':
        return [parsed]
    else:
        parser = get_footer_parser(cmpt_type)
        try: 
            parsed = parser(cmpt)
        except Exception:
            log.exception('Failed to parse footer component')
            parsed['error'] = traceback.format_exc()
        return parsed

def parse_footer(cmpt):
    """Parse footer component
    
    Args:
        soup (bs4 object): a SERP
    
    Returns:
        list: list of parsed footer component dictionaries
    """
    cmpts = extract_footer_components(cmpt)
    parsed_list = []
    for cmpt_rank, cmpt in enumerate(cmpts):
        cmpt_type = classify_footer_component(cmpt)
        parsed = parse_footer_cmpt(cmpt, cmpt_type, cmpt_rank)
        parsed_list.extend(parsed)

    return parsed_list

def parse_discover_more(cmpt):
    carousel = cmpt.find('g-scrolling-carousel')
    parsed = [{
        'type':'discover_more', 
        'sub_rank':0,
        'text': '|'.join(c.text for c in carousel.find_all('g-inner-card'))
    }]
    return parsed

def parse_image_cards(cmpt):
    """Parse a horiontally stacked row of image results relevant to query"""
    subs = cmpt.find_all('div', {'class':'g'})
    parsed = [parse_image_card(sub, sub_rank) for sub_rank, sub in enumerate(subs)]
    return parsed

def parse_image_card(sub, sub_rank=0):
    parsed = {'type':'img_cards', 'sub_rank':sub_rank}
    parsed['details'] = [{'text':i['alt'], 'url':i['src']} for i in sub.find_all('img')]
    return parsed

def parse_alink(a): 
    return {'text':a.text,'url':a.attrs['href']}

def parse_searches_related(cmpt, sub_rank=0):
    """Parse a one or two column list of related search queries"""
    parsed = {'type':'searches_related', 'sub_rank':sub_rank}
    # subs = cmpt.find('g-section-with-header').find_all('p')
    parsed['details'] = [parse_alink(a) for a in cmpt.find_all('a')]
    return [parsed]
    