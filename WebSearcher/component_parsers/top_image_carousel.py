from .. import webutils
from ..models.data import DetailsItem, DetailsList


def parse_top_image_carousel(cmpt, sub_rank=0) -> list:
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
    
    details = DetailsList()
    for a in alinks:
        if 'href' in a.attrs or 'data-url' in a.attrs:
            details.append(parse_alink(a))
    parsed['details'] = details.to_dicts()

    return [parsed]

def parse_alink(a):
    url = a.attrs.get('href') or a.attrs.get('data-url', '')
    return DetailsItem(url=url, text=a.get_text('|'))
