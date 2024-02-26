""" Parsers for video components

Changelog
2021-05-08: added find_all for divs with class 'VibNM'
2021-05-08: added adjustment for new cite and timestamp

"""

from .. import webutils
from ..models import BaseResult

def parse_videos(cmpt):
    """Parse a videos component

    These components contain links to videos, frequently to YouTube.
    
    Args:
        cmpt (bs4 object): A videos component
    
    Returns:
        list : list of parsed subcomponent dictionaries
    """

    # Get known div structures
    divs = []
    name_attrs = [
        {'name':'g-inner-card'},
        {'name':'div', 'attrs':{'class':'VibNM'}},
        {'name':'div', 'attrs':{'class':'mLmaBd'}},
        {'name':'div', 'attrs':{'class':'RzdJxc'}},
    ]
    for kwargs in name_attrs:
        divs = webutils.find_all_divs(cmpt, **kwargs)
        if divs:
            break
    divs = list(filter(None, divs))

    if divs:
        return [parse_video(div, i) for i, div in enumerate(divs)]
    else:
        return [{'type': 'videos', 'sub_rank': 0, 'error': 'No subcomponents found'}]


def parse_video(sub, sub_rank=0):
    """Parse a videos subcomponent
    
    Args:
        sub (bs4 object): A video subcomponent
    
    Returns:
        dict : parsed subresult
    """

    parsed = BaseResult(
        type='videos',
        sub_rank=sub_rank,
        url=get_url(sub),
        title=webutils.get_text(sub, 'div', {'role':'heading'}),
        text=webutils.get_text(sub, 'div', {'class':'MjS0Lc'}),
    )

    details = sub.find_all('div', {'class':'MjS0Lc'})
    if details:
        text_div, citetime_div = details
        parsed.text = text_div.text if text_div else None

        if citetime_div:
            # Sometimes there is only a cite
            citetime = citetime_div.find('div',{'class':'zECGdd'})
            citetime = list(citetime.children)
            if len(citetime) == 2:
                cite, timestamp = citetime       
                parsed.cite = cite.text
                # parsed.timestamp = timestamp.replace(' - ', '')
            else:
                parsed.cite = citetime[0].text
    elif sub.find('span', {'class':'ocUPSd'}):
        parsed.cite = sub.text
        # parsed.timestamp = get_div_text(sub, {'class':'rjmdhd'})
    elif sub.find("cite"):
        parsed.cite = webutils.get_text(sub, "cite")
        # parsed.timestamp = webutils.get_text(sub, "div", {'class':'hMJ0yc'})

    return parsed.model_dump()


def get_url(sub):
    """Get video URL by filtering for non-hash links"""
    all_urls = sub.find_all('a')
    for url in all_urls:
        if "href" in url.attrs and not url.attrs['href'].startswith('#'):
            return url.attrs["href"]
    return None


def get_div_text(soup, details):
    div = soup.find('div', details)
    return div.text if div else None


def get_img_url(soup):
    """Extract image source"""    
    img = soup.find('img')
    if img and 'data-src' in img.attrs:
        return img.attrs['data-src']


# Deprecated: images now have the same link, key moments are rare or gone
# def get_video_details(sub):
#     parsed['details'] = {} 
#     parsed['details']['img_url'] = get_img_url(sub)

#     # Check for "key moments" in video
#     key_moments_div = sub.find('div', {'class':'AvBz0e'})
#     parsed['details']['key_moments'] = True if key_moments_div else False
#     return parsed