from ..models import BaseResult
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
    
    # Known div structures
    divs = []
    divs.extend(find_all_divs(cmpt, 'g-inner-card'))              # Top Stories  
    divs.extend(find_children(cmpt, 'div', {'class': 'qmv19b'}))  # Top Stories
    divs.extend(find_all_divs(cmpt, 'div', {'class': 'IJl0Z'}))   # Top Stories  
    divs.extend(find_all_divs(cmpt, 'div', {'class': 'JJZKK'}))   # Perspectives

    if not divs:
        # This will double count if divs already found above
        link_divs = find_all_divs(cmpt, 'a', {'class': 'WlydOe'}) # Top Stories - Vertical
        divs.extend([div.parent for div in link_divs])  

    divs = list(filter(None, divs))

    if divs:
        return [parse_top_story(div, ctype, i) for i, div in enumerate(divs)]
    else:
        return [{'type': ctype, 'sub_rank': 0, 'error': 'No subcomponents found'}]


def parse_top_story(sub, ctype, sub_rank=0):
    """Parse "Top Stories" component
    
    Args:
        sub (bs4 object): A "Top Stories" subcomponent
    
    Returns:
        dict: A parsed subresult
    """
    parsed = BaseResult(
        type=ctype,
        sub_rank=sub_rank,
        title=get_text(sub, 'div', {'class':'n0jPhd'}),
        url=get_link(sub, key='href'),
        text=get_text(sub, "div", {'class': "GI74Re"}),
        cite=get_cite(sub)
    )

    # Deprecated - too much detail to maintain in dynamic SERPs
    # parsed.timestamp = get_text(sub, "div", {'class': ['f', 'uaCsqe', "ZE0LJd"]})
    # parsed.details = get_top_story_details(sub)

    return parsed.model_dump()


def get_cite(sub):

    div_cite = sub.find("div", {'class': 'Dx69l'})
    img_cite = sub.find('g-img', {'class': 'sL0zmc'})
    span_cite = sub.find('g-img', {'class': 'QyR1Ze'})
    
    if div_cite:
        # Perspectives
        cite = get_text(sub, 'div', {'class': 'Dx69l'})

    elif img_cite:
        # Top Stories (image cite, get "alt" image text)
        img = img_cite.find('img')
        if img and 'alt' in img.attrs:
            cite = img.attrs['alt']
    elif span_cite:
        cite = get_text(sub, 'span')  
    else:
        cite = get_text(sub, 'cite')
    return cite


def get_top_story_details(sub):
    # Extract component specific details
    details = {}
    details['img_url'] = get_img_url(sub)
    details['orient'] = 'v' if sub.find('span', {'class':'uaCsqe'}) else 'h'
    details['live_stamp'] = True if sub.find('span', {'class':'EugGe'}) else False
    return details


def get_img_url(soup):
    """Extract image source"""    
    img = soup.find('img')
    if img and 'data-src' in img.attrs:
        return img.attrs['data-src']
