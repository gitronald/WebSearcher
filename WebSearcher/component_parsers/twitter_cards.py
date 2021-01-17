from .. import webutils

def parse_twitter_cards(cmpt):
    """Parse a Twitter carousel component

    These components contain an carousel of Tweets from an account or about a
    topic
    
    Args:
        cmpt (bs4 object): A twitter cards component
    
    Returns:
        list : list of parsed subcomponent dictionaries
    """
    header, carousel = list(cmpt.find('g-section-with-header').children)[:2]
    parsed_list = parse_twitter_header(cmpt)

    subs = carousel.find_all('g-inner-card')
    parsed_cards = [parse_twitter_card(sub, sub_rank) for sub_rank, sub in enumerate(subs)]
    parsed_list.extend(parsed_cards)
    return parsed_list

def parse_twitter_header(header, sub_rank=0):
    """Parse the Twitter component header"""
    parsed = {
        'type': 'twitter_cards', 
        'sub_type':'header', 
        'sub_rank': sub_rank,
        'title': '',
        'url': '',
        'cite': ''
    }

    if header.find('h3'):

        # Handle legacy and current formats
        if header.find('h3', {'class':'r'}):
            header_parsed = find_header_legacy(header)
        else:
            header_parsed = find_header(header)
        parsed.update(header_parsed)

    else:
        glink = header.find('g-link')
        parsed['title'] = glink.text
        parsed['url'] = glink.a['href']

    parsed['cite'] = header.find('cite').text

    return [parsed]

def find_header_legacy(header):
    """A legacy version to find the header of a twitter card

    Args:
        header (bs4 object): A twitter card

    Returns:
        dict: the header text and url
    """
    element = header.find('h3', {'class':'r'}).find('a')
    url = webutils.url_unquote(element['href'])
    return {'url' : url, 'title' : element.text}

def find_header(header):
    """A updated version to find the header of a twitter card

    Args:
        header (bs4 object): A twitter card

    Returns:
        dict: the header text and url
    """
    
    glink = header.find('g-link')
    url = webutils.url_unquote(glink.a['href']) if glink else ''

    title_h3 = header.find('h3', {'class':'NsiYH'})
    title = title_h3.text if title_h3 else ''

    return {'url' : url, 'title' : title}

def parse_twitter_card(sub, sub_rank=0):
    """Parse a Twitter cards subcomponent
    
    Args:
        sub (bs4 object): A local results subcomponent
    
    Returns:
        dict : parsed subresult
    """
    parsed = {
        'type': 'twitter_cards', 
        'sub_type': 'card', 
        'sub_rank': sub_rank + 1,  # Add one to rank to account for header
        'cmpt_rank': None,
        'title':'',
        'url':'',
        'text':'',
        'details':None,
        'timestamp':None
    }

    # Tweet account
    title = sub.find('g-link')
    if title:
        parsed['title'] = title.find('a').text

    # Bottom div containing timestamp and tweet link
    div = sub.find('div', {'class':'Brgz0'})
    link = div.find('a')
    if 'href' in link.attrs:
        parsed['url'] = webutils.url_unquote(link['href'])

    ts = div.find('span', {'class':'f'})
    if ts:
        parsed['timestamp'] = div.find_all('span', {'class':'f'})[-1].text

    # Tweet text
    subdiv = div.find('div', {'class':'xcQxib'})
    parsed['text'] = subdiv.text if subdiv else None

    # Tweet details
    details = {}
    links = subdiv.find_all('a')
    details['urls'] = [webutils.url_unquote(a['href']) for a in links if 'href' in a.attrs]
    details['hashtags'] = webutils.parse_hashtags(parsed['text'])
    # details['emojis'] = webutils.parse_emojis(parsed['text'])
    parsed['details'] = details

    return parsed