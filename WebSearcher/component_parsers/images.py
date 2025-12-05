""" Parsers for image components

Changelog
2025-04-28: added div subcomponent class and sub_type labels

"""

from ..webutils import get_text, get_link, get_div

def parse_images(cmpt) -> list:
    """Parse an images component"""

    parsed_list = []

    if cmpt.find('g-expandable-container'):
        # Small images: thumbnails with text labels
        subs = cmpt.find_all('a', {'class': 'dgdd6c'})
        parsed_subs = [parse_image_small(div, sub_rank) for sub_rank, div in enumerate(subs)]
        parsed_list.extend(parsed_subs)

    if cmpt.find('g-scrolling-carousel'):
        # Medium images or video previews, no text labels
        subs = cmpt.find_all('div', {'class':'eA0Zlc'})
        parsed_subs = [parse_image_multimedia(sub, sub_rank + len(parsed_list)) for sub_rank, sub in enumerate(subs)]
        parsed_list.extend(parsed_subs)
    else:
        # Medium images with titles and urls
        subs = cmpt.find_all('div', {'class': ['eA0Zlc', 'vCUuC']})
        parsed_subs = [parse_image_medium(sub, sub_rank + len(parsed_list)) for sub_rank, sub in enumerate(subs)]
        parsed_list.extend(parsed_subs)

    # Filter empty results
    parsed_list = [p for p in parsed_list if any([p['title'], p['url']])]
    
    return parsed_list

def parse_image_multimedia(sub, sub_rank=0) -> dict:
    """Parse an images multimedia subcomponent"""
    return {
        "type": "images",
        "sub_type": "multimedia",
        "sub_rank": sub_rank,
        "title": get_img_alt(sub),
        "url": get_img_url(sub),
        "text": None,
    }

def parse_image_medium(sub, sub_rank=0) -> dict:
    """Parse an images medium subcomponent"""
    
    title_div = get_div(sub, 'a', {'class':'EZAeBe'})
    title = get_text(title_div) if title_div else get_text(sub, 'span', {'class':'Yt787'})
    url = get_link(sub) if title_div else get_img_url(sub)

    if not title:
        title = get_img_alt(sub)
    if not url:
        url = get_link(sub, attrs={'class':['EZAeBe', 'ddkIM']})

    return {
        "type": "images",
        "sub_type": "medium",
        "sub_rank": sub_rank,
        "title": title,
        "url": url,
        "text": None,
        "cite": get_text(sub, 'div', {'class':'ptes9b'})
    }

def parse_image_small(sub, sub_rank=0) -> dict:
    """Parse an images small subcomponent"""

    return {
        "type": "images", 
        "sub_type": "small",
        "sub_rank": sub_rank,
        "title": get_text(sub, 'div', {'class':'xlY4q'}),
        "url": None,
        "text": None,
    }

def get_img_url(sub):
    """Get image source"""

    def get_image_url_from_img_src(sub):
        img_src = sub.find('img').attrs['src']
        if img_src.startswith('data:image'):
            raise ValueError(f"Data URL: {img_src}")
        else:
            return img_src
    
    def get_image_url_from_img_title(sub):
        return sub.find('img').attrs['title']
        
    def get_image_url_from_attrs(sub):
        return sub.attrs['data-lpage']

    func_list = [
        get_image_url_from_img_src,
        get_image_url_from_attrs,
        get_image_url_from_img_title,
    ]

    # Try each function in the list
    for func in func_list:
        try:
            url = func(sub)
            if url.startswith('data:image'):
                raise ValueError(f"Data URL: {url}")
            else:
                return url
        except Exception as e:
            pass
    return None


def get_img_alt(sub):
    """Get image alt text"""
    try:
        return f"alt-text: {sub.find('img').attrs['alt']}"
    except Exception:
        return None