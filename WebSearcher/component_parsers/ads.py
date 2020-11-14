def parse_ads(cmpt):
    """Parse ads from ad component"""
    subs = cmpt.find_all('li', {'class':'ads-ad'})
    if subs:
        # Check for legacy ad format
        parser = parse_ad_legacy
    else:
        # Check for latest ad format
        subs = cmpt.find_all('div', {'class':'uEierd'})
        parser = parse_ad

    return [parser(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def parse_ad(sub, sub_rank=0, visible=None):
    """Parse details of a single ad subcomponent, similar to general"""
    parsed = {'type':'ad', 'sub_rank':sub_rank}

    parsed['title'] = sub.find('div', {'role':'heading'}).text
    parsed['url'] = sub.find('div', {'class':'d5oMvf'}).find('a')['href']
    parsed['cite'] = sub.find('span', {'class':'Zu0yb'}).text

    # Take the top div with this class, should be main result abstract
    text_divs = sub.find_all('div', {'class':'yDYNvb'})
    parsed['text'] = '|'.join([d.text for d in text_divs]) if text_divs else ''

    bottom_section = sub.find('div', {'role':'list'})
    if bottom_section:
        list_items = sub.find_all('div', {'role':'listitem'})
        if list_items:
            parsed['details'] = [i.find('a')['href'] for i in list_items]
    
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
