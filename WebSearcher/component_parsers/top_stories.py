from ..webutils import find_all_divs, find_children, get_text, get_link


def parse_top_stories(cmpt, ctype='top_stories'):
    """Parse a "Top Stories" component

    These components contain links to news articles and often feature an image.
    Sometimes the subcomponents are stacked vertically, and sometimes they are
    stacked horizontally and feature a larger image, resembling the video 
    component.
    
    Args:
        cmpt (bs4 object): A "Top Stories" component
    
    Returns:
        list : list of parsed subcomponent dictionaries
    """
    # Known div structures, this returns a 2d list of divs
    div_list = [
        find_all_divs(cmpt, 'g-inner-card'),
        find_children(cmpt, 'div', {'class': 'qmv19b'}),
        # TODO: choose one of these stragegies
        # cmpt.select('div.Dnzdlc > div'), # triple
        # [c for c in cmpt.find_all('div') if 'data-hveid' in c.attrs], # triple
        find_all_divs(cmpt, 'div', {'class': 'MkXWrd'}), # quad
        find_all_divs(cmpt, 'div', {'class': 'JJZKK'}),  # perspectives
    ]

    # flatten 2d div list
    subcomponent_divs = [div for divs in div_list for div in divs]

    if len(div_list) > 1:
        return [parse_top_story(div, ctype, i) for i, div in enumerate(subcomponent_divs)]

    return [{'type': ctype, 'sub_rank': 0, 'error': 'No subcomponents found'}]


def parse_top_story(sub, ctype, sub_rank=0):
    """Parse "Top Stories" component
    
    Args:
        sub (bs4 object): A "Top Stories" subcomponent
    
    Returns:
        dict: A parsed subresult
    """
    parsed = {'type': ctype, 'sub_rank': sub_rank}

    parsed['title'] = get_text(sub, 'a', separator=' | ')
    parsed['url'] = get_link(sub, key='href')
    parsed['cite'] = get_text(sub, 'cite')
    
    if ctype == 'perspectives':
        parsed['text'] = get_text(sub, "div", {'class': "GI74Re"})

    parsed['timestamp'] = get_text(sub, "div", {'class': ['f', 'uaCsqe', "ZE0LJd"]})

    # Extract component specific details
    details = {}
    details['img_url'] = get_img_url(sub)
    details['orient'] = 'v' if sub.find('span', {'class':'uaCsqe'}) else 'h'
    details['live_stamp'] = True if sub.find('span', {'class':'EugGe'}) else False
    parsed['details'] = details
    
    return parsed


def get_img_url(soup):
    """Extract image source"""    
    img = soup.find('img')
    if img and 'data-src' in img.attrs:
        return img.attrs['data-src']
