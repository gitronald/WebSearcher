""" Parsers for ad components

Changelog
---------
2024-05-08: 
- added new div class for text field
- added labels (e.g., "Provides abortions") from <span class="mXsQRe">, appended to text field


"""

from .. import webutils
from ..models import BaseResult
import bs4

def parse_ads(cmpt: bs4.element.Tag):
    """Parse ads from ad component"""

    if cmpt.find_all('li', {'class':'ads-ad'}):
        # Check for legacy ad format
        subs = cmpt.find_all('li', {'class':'ads-ad'})
        parser = parse_ad_legacy
    elif cmpt.find_all('li', {'class':'ads-fr'}):
        # Check for secondary ad format
        subs = cmpt.find_all('li', {'class':'ads-fr'})
        parser = parse_ad_secondary
    else:
        # Check for latest ad format
        subs = cmpt.find_all('div', {'class':'uEierd'})
        parser = parse_ad

    return [parser(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def parse_ad(sub: bs4.element.Tag, sub_rank: int = 0) -> dict:
    """Parse details of a single ad subcomponent, similar to general"""
    parsed = {"type": "ad", 
              "sub_type": "standard", 
              "sub_rank": sub_rank}
    
    parsed['title'] = webutils.get_text(sub, 'div', {'role':'heading'})
    parsed['url'] = webutils.get_link(sub, {"class":"sVXRqc"})
    parsed['cite'] = webutils.get_text(sub, 'span', {"role":"text"})
    
    name_attrs = [{"name":"div", "attrs":{"class":"yDYNvb"}}, 
                  {"name":"div", "attrs":{"class":"Va3FIb"}}]
    for kwargs in name_attrs:
        text = webutils.get_text(sub, **kwargs)
        if text:
            break
    label = webutils.get_text(sub, 'span', {'class':'mXsQRe'})
    parsed['text'] = f"{text} | {label}" if label else text

    submenu = parse_ad_menu(sub)
    if submenu:
        parsed['sub_type'] = 'submenu'
        parsed['details'] = submenu

    validated = BaseResult(**parsed)
    return validated.model_dump()


def parse_ad_menu(sub: bs4.element.Tag) -> list:
    """Parse menu items for a large ad with additional subresults"""

    parsed_items = []
    menu_items = sub.find_all('div', {'class':'MhgNwc'})
    for item in menu_items:
        parsed_item = {}
        item_divs = item.find_all('div', {'class':'MUxGbd'})
        for div in item_divs:
            if webutils.check_dict_value(div.attrs, 'role', 'listitem'):
                parsed_item['url'] = webutils.get_link(div)
                parsed_item['title'] = webutils.get_text(div)
            else:
                parsed_item['text'] = webutils.get_text(div)
        parsed_items.append(parsed_item)
    return parsed_items if parsed_items else None


def parse_ad_secondary(sub: bs4.element.Tag, sub_rank: int = 0) -> dict:
    """Parse details of a single ad subcomponent, similar to general"""

    parsed = {'type':'ad', 'sub_rank':sub_rank}
    parsed['title'] = sub.find('div', {'role':'heading'}).text
    parsed['url'] = sub.find('div', {'class':'d5oMvf'}).find('a')['href']
    parsed['cite'] = sub.find('span', {'class':'gBIQub'}).text

    # Take the top div with this class, should be main result abstract
    text_divs = sub.find_all('div', {'class':'yDYNvb'})
    parsed['text'] = '|'.join([d.text for d in text_divs]) if text_divs else ''
    
    bottom_section = sub.find('div', {'role':'list'})
    if bottom_section:
        list_items = sub.find_all('div', {'role':'listitem'})
        if list_items:
            parsed['details'] = [i.find('a')['href'] for i in list_items]

    elif sub.find('div', {'class':'bOeY0b'}):
        bottom_alinks = sub.find('div', {'class':'bOeY0b'}).find_all('a')
        if bottom_alinks:
            parsed['details'] = [a.attrs['href'] for a in bottom_alinks]

    return parsed

def parse_ad_secondary(sub: bs4.element.Tag, sub_rank: int = 0) -> dict:
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
