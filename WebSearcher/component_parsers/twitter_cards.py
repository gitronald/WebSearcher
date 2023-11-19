from .. import webutils
from ..models import BaseResult

def parse_twitter_cards(cmpt):
    """Parse a Twitter carousel component

    These components contain an carousel of Tweets from an account or about a
    topic
    
    Args:
        cmpt (bs4 object): A twitter cards component
    
    Returns:
        list : list of parsed subcomponent dictionaries
    """
    # header, carousel = list(cmpt.find('g-section-with-header').children)[:2]
    carousel = cmpt.find('g-scrolling-carousel')
    parsed_list = parse_twitter_header(cmpt)
    subs = carousel.find_all('g-inner-card')
    parsed_cards = [parse_twitter_card(sub, sub_rank) for sub_rank, sub in enumerate(subs)]
    parsed_list.extend(parsed_cards)
    return parsed_list

def parse_twitter_header(header, sub_rank=0):
    """Parse the Twitter component header"""

    parsed = BaseResult(
        type='twitter_cards',
        sub_type='header',
        sub_rank=sub_rank,
        title='',
        url='',
        cite=webutils.get_text(header, 'cite')
    )

    header_details = get_header_details(header)
    parsed.title = header_details['title']
    parsed.url = header_details['url']

    return [parsed.model_dump()]


def get_header_details(header):
    """Handle legacy and current formats"""

    if header.find('h3'):

        if header.find('h3', {'class':'r'}):
            # Legacy format
            element = header.find('h3', {'class':'r'})
            header_details = {
                'url': webutils.url_unquote(element['href']), 
                'title': webutils.get_text(element, 'a')
            }
        else:
            # Current
            glink = header.find('g-link')
            header_details = {
                'url': webutils.url_unquote(glink.a['href']) if glink else '', 
                'title': webutils.get_text(glink)
            }
    else:
        glink = header.find('g-link')
        header_details = {
            'url': webutils.get_link(glink) if glink else '', 
            'title': webutils.get_text(glink)
        }
    return header_details


def parse_twitter_card(sub, sub_rank=0):
    """Parse a Twitter cards subcomponent
    
    Args:
        sub (bs4 object): A local results subcomponent
    
    Returns:
        dict : parsed subresult
    """
    parsed = BaseResult(
        type='twitter_cards',
        sub_type='card',
        sub_rank=sub_rank + 1,  # Add one to rank to account for header
    )

    # Tweet account
    title = sub.find('g-link')
    if title:
        parsed.title = webutils.get_text(title, 'a')

    # Bottom div containing timestamp and tweet link
    div = sub.find('div', {'class':'Brgz0'})
    if div:
        parsed.cite = webutils.get_text(div, 'div', {'class':'rmxqbe'})
        
        url = webutils.get_link(div)
        parsed.url = webutils.url_unquote(url) if url else None
        parsed.text = webutils.get_text(div, 'div', {'class':'xcQxib'})
    return parsed.model_dump()

# Deprecated: text processing should be done post-parse
# def get_details(div):
#     details = {}
#     post_content = div.find('div', {'class':'xcQxib'})
#     links = [a for a in post_content.find_all('a') if 'href' in a.attrs]
#     details['urls'] = [webutils.url_unquote(a['href']) for a in links]
#     details['hashtags'] = webutils.parse_hashtags(parsed.text)
#     # details['emojis'] = webutils.parse_emojis(parsed['text'])
#     return details