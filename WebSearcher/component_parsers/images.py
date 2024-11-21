from ..webutils import get_text, get_link, get_div

def parse_images(cmpt) -> list:
    """Parse an image component
    
    Args:
        cmpt (bs4 object): an image component
    
    Returns:
        list: list of parsed subcomponent dictionaries
    """

    parsed_list = []

    # Small images: thumbnails with text labels
    if cmpt.find('g-expandable-container'):
        subs = cmpt.find_all('a', {'class': 'dgdd6c'})
        sub_type = 'small'
        parsed_subs = [parse_image_small(div, sub_rank) for sub_rank, div in enumerate(subs)]
        parsed_list.extend(parsed_subs)

    if cmpt.find('g-scrolling-carousel'):
        # Medium images or video previews, no text labels
        subs = cmpt.find_all('div', {'class':'eA0Zlc'})
        sub_type = 'multimedia'
        parsed_subs = [parse_image_multimedia(sub, sub_rank + len(parsed_list)) for sub_rank, sub in enumerate(subs)]
        parsed_list.extend(parsed_subs)
    else:
        # Medium images with titles and urls
        subs = cmpt.find_all('div', {'class':'eA0Zlc'})
        sub_type = 'medium'
        parsed_subs = [parse_image_medium(sub, sub_rank + len(parsed_list)) for sub_rank, sub in enumerate(subs)]
        parsed_list.extend(parsed_subs)

    # Filter empty results
    parsed_list = [p for p in parsed_list if any([p['title'], p['url']])]
    
    return parsed_list


def parse_image_multimedia(sub, sub_rank=0) -> dict:
    """Parse an image subcomponent
    
    Args:
        sub (bs4 object): an image subcomponent
    
    Returns:
        dict : parsed subresult
    """
    return {
        "type": "images",
        "sub_type": "multimedia",
        "sub_rank": sub_rank,
        "title": get_img_alt(sub),
        "url": get_img_url(sub)
    }

def parse_image_medium(sub, sub_rank=0) -> dict:
    """Parse an image subcomponent
    
    Args:
        sub (bs4 object): an image subcomponent
    
    Returns:
        dict : parsed subresult
    """
    
    title_div = get_div(sub, 'a', {'class':'EZAeBe'})
    title = get_text(title_div) if title_div else get_img_alt(sub)
    url = get_link(sub) if title_div else get_img_url(sub)

    return {
        "type": "images",
        "sub_type": "medium",
        "sub_rank": sub_rank,
        "title": title,
        "url": url,
        "cite": get_text(sub, 'div', {'class':'ptes9b'})
    }

def parse_image_small(sub, sub_rank=0) -> dict:
    """Parse an image subcomponent
    
    Args:
        sub (bs4 object): an image subcomponent
    
    Returns:
        dict : parsed subresult
    """
    return {
        "type": "images", 
        "sub_type": "small",
        "sub_rank": sub_rank,
        "title": get_text(sub, 'div', {'class':'xlY4q'}),
        "url": None
    }

def get_img_url(sub):
    """Get image source"""
    try:
        return sub.attrs['data-lpage']
    except Exception:
        return None


def get_img_alt(sub):
    """Get image alt text"""
    try:
        return f"alt-text: {sub.find('img').attrs['alt']}"
    except Exception:
        return None