from .. import webutils

def parse_top_image_carousel(cmpt, sub_rank=0):
    """parse image carousel that appears at top of page above search results

    Args:
        cmpt (bs4 object): A top_image_carousel component

    Returns:
        list: list of parsed subcomponent dictionaries
    """
    
    parsed = {'type':'top_image_carousel', 'sub_rank':sub_rank}

    title = cmpt.find_all('span', {'class': 'Wkr6U'})
    if title:
        parsed['title'] = '|'.join([t.text for t in title])
        parsed['url'] = webutils.get_link(cmpt)

    images = cmpt.find('div', {'role':'list'})
    if images:
        alinks = images.children
    else:
        alinks = cmpt.find('g-scrolling-carousel').find_all('a')
    
    parsed['details'] = [
        parse_alink(a) for a in alinks
        if 'href' in a.attrs or 'data-url' in a.attrs
    ]

    return [parsed]

def parse_alink(a): 
    parsed = {'text': a.get_text('|')}
    if 'href' in a.attrs:
        parsed['url'] = a['href']
    elif 'data-url' in a.attrs:
        parsed['url'] = a['data-url']
    return parsed  
