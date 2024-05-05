from .. import webutils
from ..models import BaseResult


def parse_twitter_cards(cmpt):
    """Parse a Twitter carousel component

    These components consist of a header and a carousel of cards:
    - header: linked header of a Twitter carousel (account or topic)
    - card: single Tweet from a Twitter carousel

    Args:
        cmpt (bs4 object): A twitter cards component
    
    Returns:
        list : list of parsed subcomponent dictionaries
    """
    # header, carousel = list(cmpt.find('g-section-with-header').children)[:2]
    parsed_header = parse_twitter_header(cmpt)
    carousel = cmpt.find('g-scrolling-carousel')
    subs = carousel.find_all('g-inner-card')
    parsed_cards = [parse_twitter_card(sub, sub_rank + 1) for sub_rank, sub in enumerate(subs)]
    parsed_list = [parsed_header] + parsed_cards
    return parsed_list


def parse_twitter_header(cmpt, sub_rank:int = 0):
    """Parse a Twitter header from the main component"""
    parsed = {"type": "twitter_cards", 
              "sub_type": "header", 
              "sub_rank": sub_rank}
    element_current = cmpt.find('g-link')
    element_legacy = cmpt.find('h3', {'class':'r'})
    if cmpt.find('h3'):
        if element_legacy:
            parsed['url'] = webutils.url_unquote(element_legacy.get('href', ''))
            parsed['title'] = webutils.get_text(element_legacy, 'a')
        elif element_current:
            parsed['url'] = webutils.url_unquote(webutils.get_link(element_current))
            parsed['title'] = webutils.get_text(element_current)
    elif element_current:
        parsed['url'] = webutils.get_link(element_current)
        parsed['title'] = webutils.get_text(element_current)
    parsed["cite"] = webutils.get_text(cmpt, 'cite')

    validated = BaseResult(**parsed)
    return validated.model_dump()


def parse_twitter_card(sub, sub_rank:int = 0):
    """Parse a Twitter card from a subcomponent"""
    parsed = {"type": "twitter_cards",
              "sub_type": "card",
              "sub_rank": sub_rank}

    # Tweet account
    title = sub.find('g-link')
    parsed["title"] = webutils.get_text(title, 'a') if title else None

    # Bottom div containing details
    div = sub.find('div', {'class':'Brgz0'})
    if div:
        url = webutils.get_link(div)
        parsed["url"] = webutils.url_unquote(url) if url else None
        parsed["text"] = webutils.get_text(div, 'div', {'class':'xcQxib'})
        parsed["cite"] = webutils.get_text(div, 'div', {'class':'rmxqbe'})

    validated = BaseResult(**parsed)
    return validated.model_dump()
