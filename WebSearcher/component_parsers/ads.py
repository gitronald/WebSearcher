def parse_ads(cmpt):
    """Parse ads from ad component"""
    subs = cmpt.find_all('li', {'class':'ads-ad'})
    return [parse_ad(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

def parse_ad(sub, sub_rank=0, visible=None):
    """Parse details of a single ad subcomponent, similar to general"""
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
