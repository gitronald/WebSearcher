from ..models import BaseResult
from ..webutils import get_text, get_link


def parse_images(cmpt):
    """Parse an image component
    
    Args:
        cmpt (bs4 object): an image component
    
    Returns:
        list: list of parsed subcomponent dictionaries
    """

    parsed = []

    # Small images: thumbnails with text labels
    if cmpt.find('g-expandable-container'):
        subs_small = cmpt.find_all('a', {'class': 'dgdd6c'})
        parsed_small = [parse_image_small(div, sub_rank) for sub_rank, div in enumerate(subs_small)]
        parsed.extend(parsed_small)

    if cmpt.find('g-scrolling-carousel'):
        # Medium images or video previews, no text labels
        subs = cmpt.find_all('div', {'class':'eA0Zlc'})
        _parsed = [parse_image_multimedia(sub, sub_rank + len(parsed)) for sub_rank, sub in enumerate(subs)]
        parsed.extend(_parsed)
    else:
        # Medium images with titles and urls
        subs = cmpt.find_all('div', {'class':'eA0Zlc'})
        _parsed = [parse_image_medium(sub, sub_rank + len(parsed)) for sub_rank, sub in enumerate(subs)]
        parsed.extend(_parsed)

    # Filter empty results
    parsed = [p for p in parsed if p['title']]
            
    return parsed


def parse_image_multimedia(sub, sub_rank=0):
    """Parse an image subcomponent
    
    Args:
        sub (bs4 object): an image subcomponent
    
    Returns:
        dict : parsed subresult
    """

    parsed = BaseResult(
        type="images",
        sub_type="multimedia",
        sub_rank=sub_rank,
        title=get_img_alt(sub),
        # url=get_img_url(sub), # dynamic load, no source url via requests
    )
    return parsed.model_dump()


def parse_image_medium(sub, sub_rank=0):
    """Parse an image subcomponent
    
    Args:
        sub (bs4 object): an image subcomponent
    
    Returns:
        dict : parsed subresult
    """

    
    parsed = BaseResult(
        type="images",
        sub_type="medium",
        sub_rank=sub_rank,
        title=get_text(sub, 'a', {'class':'EZAeBe'}),
        url=get_link(sub, {'class':'EZAeBe'}),
        cite=get_text(sub, 'div', {'class':'ptes9b'})
    )
    return parsed.model_dump()


def parse_image_small(sub, sub_rank=0):
    """Parse an image subcomponent
    
    Args:
        sub (bs4 object): an image subcomponent
    
    Returns:
        dict : parsed subresult
    """

    parsed = BaseResult(
        type="images",
        sub_type="small",
        sub_rank=sub_rank,
        title=get_text(sub, 'div', {'class':'xlY4q'})
    )
    return parsed.model_dump()


def get_img_url(soup):
    """Get image source"""
    try:
        return soup.find('img').attrs['src']
    except Exception:
        return None


def get_img_alt(soup):
    """Get image alt text"""
    try:
        return f"alt-text: {soup.find('img').attrs['alt']}"
    except Exception:
        return None