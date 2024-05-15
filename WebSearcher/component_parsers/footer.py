from . import parse_general_results, parse_people_also_ask, parse_searches_related
from .. import component_classifier
from .. import logger
from ..models import BaseResult
from ..webutils import get_text, find_all_divs

log = logger.Logger().start(__name__)

import traceback


# ------------------------------------------------------------------------------
# Extractors


def extract_footer(soup):
    """Extract footer div from a SERP"""
    return soup.find('div', {'id':'botstuff'})


def extract_footer_components(footer):
    """Extract footer components from a footer div"""
    footer_cmpts = find_all_divs(footer, 'div', {'id':['bres', 'brs']})
    expanded = []
    if footer_cmpts:
        # Expand component list with alternative layouts
        for cmpt in footer_cmpts:
            divs = find_all_divs(cmpt, "div", {"class":"MjjYud"})
            if divs and len(divs) > 1:
                expanded.extend(divs)
            else:
                expanded.append(cmpt)
    
    omitted_notice = footer.find('div', {'class':'ClPXac'})
    if omitted_notice:
        expanded.append(omitted_notice)

    # Filter hidden people also ask components
    expanded = [e for e in expanded if not is_hidden(e)]
    log.debug(f'Expanded footer components: {len(expanded)}')

    return expanded


def is_hidden(element):
    """Check if a hidden people also ask class"""
    conditions = [
        element.find("span", {"class":"oUAcPd"}),   # Empty `general`
        element.find("div", {"class": "RTaUke"}),   # Empty `people_also_ask`
        element.find("div", {"class": "KJ7Tg"}),    # Empty `people_also_ask`
    ]
    return any(conditions)


# ------------------------------------------------------------------------------
# Classifiers


def classify_footer_component(cmpt, cmpt_type='unknown'):
    """Classify a single footer component, fallback to main classifier"""

    gsection = cmpt.find('g-section-with-header')
    subs = cmpt.find_all('div', {'class':'g'})

    conditions = [
        ('id' in cmpt.attrs and cmpt.attrs['id'] == 'bres'),
        ('class' in cmpt.attrs and cmpt.attrs['class'] == ['MjjYud'])
    ]

    if any(conditions):
        if subs:
            cmpt_type = 'img_cards'
        elif cmpt.find('g-scrolling-carousel'):
            cmpt_type = 'discover_more'
        elif cmpt.find('h3'):
            cmpt_type = classify_searches_related(cmpt)

    elif cmpt.find("p", {"id":"ofr"}):
        cmpt_type = 'omitted_notice'

    elif gsection:
        cmpt_type = 'searches_related'
    
    if cmpt_type == 'unknown':
        log.debug('falling back to main classifier')
        cmpt_type = component_classifier.classify_type(cmpt)

    return cmpt_type


def classify_searches_related(cmpt):
    log.debug('classifying searches related component')
    known_labels = {'Related', 
                    'Related searches', 
                    'People also search for', 
                    'Related to this search'}
    h3 = cmpt.find('h3')
    if h3:
        h3_matches = [h3.text.strip().startswith(text) for text in known_labels]
        if any(h3_matches):
            return 'searches_related'
    return 'unknown'


# ------------------------------------------------------------------------------
# Parsers


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
        parsed = parse_footer_cmpt(cmpt, cmpt_rank=cmpt_rank)
        parsed_list.extend(parsed)

    return parsed_list


def get_footer_parser(cmpt_type: str) -> callable:
    if cmpt_type == 'img_cards':
        return parse_image_cards
    elif cmpt_type == 'searches_related':
        return parse_searches_related
    elif cmpt_type == 'discover_more':
        return parse_discover_more
    elif cmpt_type == 'general':
        return parse_general_results
    elif cmpt_type == 'people_also_ask':
        return parse_people_also_ask
    elif cmpt_type == 'omitted_notice':
        return parse_omitted_notice


def parse_footer_cmpt(cmpt, cmpt_type='', cmpt_rank=0) -> list:
    """Classify the footer component and parse it""" 

    # Classify Component
    cmpt_type = cmpt_type if cmpt_type else classify_footer_component(cmpt)
    assert cmpt_type, 'Null component type'

    # Return unknown components
    if cmpt_type == 'unknown':
        parsed = {'type': 'footer',
                  'sub_type': cmpt_type,
                  'cmpt_rank': cmpt_rank,
                  'sub_rank': 0}
        validated = BaseResult(**parsed).model_dump()
        return [validated]

    # Parse component
    try: 
        parser = get_footer_parser(cmpt_type)
        parsed = parser(cmpt)

        # Add cmpt rank to parsed
        if isinstance(parsed, list):
            for sub_rank, sub in enumerate(parsed):
                sub.update({'sub_rank':sub_rank, 'cmpt_rank':cmpt_rank})
        elif isinstance(parsed, dict):
            parsed.update({'sub_rank':0, 'cmpt_rank':cmpt_rank})
            validated = BaseResult(**parsed).model_dump()
            return [validated]
        else:
            raise TypeError(f'Parsed component must be list or dict: {parsed}')

    except Exception:
        log.exception('Parsing Exception - Footer')
        err = traceback.format_exc()
        parsed = {'type': 'footer',
                  'sub_type': cmpt_type,
                  'cmpt_rank': cmpt_rank,
                  'sub_rank': 0}
        validated = BaseResult(**parsed).model_dump()
        validated['error'] = err        
        return [validated]
    
    return parsed


# ------------------------------------------------------------------------------
# Component Parsers


def parse_omitted_notice(cmpt):
    return [{'type':'omitted_notice', 'sub_rank':0, 'text':cmpt.text}]

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
    parsed['title'] = get_text(sub, "div", {'aria-level':"3", "role":"heading"})
    images = sub.find_all('img')
    if images:
        parsed['details'] = [{'text':i['alt'], 'url':i['src']} for i in images]
    
    return parsed
