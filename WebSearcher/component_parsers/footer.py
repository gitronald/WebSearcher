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

def extract_footer_components(footer):
    footer_cmpts = footer.find_all('div', {'id':['bres', 'brs']})
    footer_cmpts = [c for c in footer_cmpts if c]
    footer_cmpts = [c for c in footer_cmpts if c.text != '']
    return footer_cmpts

def classify_footer_component(cmpt):
    if 'id' in cmpt.attrs and cmpt.attrs['id'] == 'bres':
        subs = cmpt.find_all('div', {'class':'g'})
        if subs:
            return 'image_cards'
        elif cmpt.find('g-scrolling-carousel'):
            return 'discover_more'
        else:
            return 'unknown'

    elif cmpt.find('g-section-with-header'):
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
    