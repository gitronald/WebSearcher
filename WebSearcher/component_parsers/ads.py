def parse_ads(cmpt):
    """Parse ads from ad component"""

    if cmpt.find_all('li', {'class':'ads-ad'}):
        # Check for legacy ad format
        subs = cmpt.find_all('li', {'class':'ads-ad'})
        parser = parse_ad_legacy
    elif cmpt.find_all('li', {'class':'ads-fr'}):
        # Check for secondary ad format
        subs = cmpt.find_all('li', {'class':'ads-fr'})
        parser = parse_ad_secondary
    else:
        # Check for latest ad format
        subs = cmpt.find_all('div', {'class':'uEierd'})
        parser = parse_ad

    return [parser(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def get_link(soup, kwargs, key='href'):
    """Utility for soup.find('a')['href'] that checks if 'a' exists and has an href key"""
    a = soup.find('a', kwargs)
    return a.attrs[key] if a.attrs and key in a.attrs else None


def get_text(soup, div, kwargs):
    """Utility for soup.find('div', ...).text that checks if div exists"""
    div = sub.find(div, kwargs)
    return div.text if div else None
    

def parse_ad(sub, sub_rank=0, visible=None):
    """Parse details of a single ad subcomponent, similar to general"""
    parsed = {'type':'ad', 'sub_rank': 0}

    parsed['title'] = get_text(sub, 'div', {'role':'heading'})
    parsed['url'] = get_link(sub, {"class":"sVXRqc"})
    parsed['cite'] = get_text(sub, 'span', {'class':'Zu0yb'})

    # Take the top div with this class, should be main result abstract
    text_divs = sub.find_all('div', {'class':'yDYNvb'})
    parsed['text'] = '|'.join([d.text for d in text_divs]) if text_divs else ''

    bottom_section = sub.find('div', {'role':'list'})
    if bottom_section:
        list_items = sub.find_all('div', {'role':'listitem'})
        if list_items:
            alinks = [i.find('a') for i in list_items]
            parsed['details'] = [a['href'] for a in alinks if a]
    return parsed


def parse_ad_secondary(sub, sub_rank=0, visible=None):
    """Parse details of a single ad subcomponent, similar to general"""

    parsed = {'type':'ad', 'sub_rank':sub_rank}

    parsed['title'] = sub.find('div', {'role':'heading'}).text
    parsed['url'] = sub.find('div', {'class':'d5oMvf'}).find('a')['href']
    parsed['cite'] = sub.find('span', {'class':'gBIQub'}).text

    # Take the top div with this class, should be main result abstract
    text_divs = sub.find_all('div', {'class':'yDYNvb'})
    parsed['text'] = '|'.join([d.text for d in text_divs]) if text_divs else ''
    
    bottom_section = sub.find('div', {'role':'list'})
    if bottom_section:
        list_items = sub.find_all('div', {'role':'listitem'})
        if list_items:
            parsed['details'] = [i.find('a')['href'] for i in list_items]

    elif sub.find('div', {'class':'bOeY0b'}):
        bottom_alinks = sub.find('div', {'class':'bOeY0b'}).find_all('a')
        if bottom_alinks:
            parsed['details'] = [a.attrs['href'] for a in bottom_alinks]

    return parsed

def parse_ad_legacy(sub, sub_rank=0, visible=None):
    """[legacy] Parse details of a single ad subcomponent, similar to general"""
    parsed = {'type':'ad', 'sub_rank':sub_rank}

    header = sub.find('div', {'class':'ad_cclk'})
    parsed['title'] = header.find('h3').text
    parsed['url'] = header.find('cite').text
    parsed['text'] = sub.find('div', {'class':'ads-creative'}).text
    
    bottom_text = sub.find('ul')
    if bottom_text:
        bottom_li = bottom_text.find_all('li')
        parsed['details'] = [li.get_text(separator=' ') for li in bottom_li]

    return parsed
