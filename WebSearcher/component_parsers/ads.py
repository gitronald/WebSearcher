""" Parsers for ad components

Changelog
---------
2024-05-08: 
- added new div class for text field
- added labels (e.g., "Provides abortions") from <span class="mXsQRe">, appended to text field


"""

from .. import webutils
from .shopping_ads import parse_shopping_ads
import bs4

def parse_ads(cmpt: bs4.element.Tag) -> list:
    """Parse ads from ad component"""

    parsed_list = []
    sub_type = classify_ad_type(cmpt)

    if sub_type == 'legacy':
        subs = cmpt.find_all('li', {'class': 'ads-ad'})
        parsed_list = [parse_ad_legacy(sub, sub_rank) for sub_rank, sub in enumerate(subs)]
    elif sub_type == 'secondary':
        subs = cmpt.find_all('li', {'class': 'ads-fr'})
        parsed_list = [parse_ad_secondary(sub, sub_rank) for sub_rank, sub in enumerate(subs)]
    elif sub_type == 'standard':
        subs = webutils.find_all_divs(cmpt, 'div', {'class': ['uEierd', 'commercial-unit-desktop-top']})
        for sub in subs:
            sub_classes = sub.attrs.get("class", [])
            if "commercial-unit-desktop-top" in sub_classes:
                parsed_list.extend(parse_shopping_ads(sub))
            elif "uEierd" in sub_classes:
                parsed_list.append(parse_ad(sub))
    return parsed_list


def classify_ad_type(cmpt: bs4.element.Tag) -> str:
    """Classify the type of ad component"""
    label_divs = {
        "legacy": webutils.find_all_divs(cmpt, 'div', {'class': 'ad_cclk'}),
        "secondary": webutils.find_all_divs(cmpt, 'div', {'class': 'd5oMvf'}),
        "standard": webutils.find_all_divs(cmpt, 'div', {'class': ['uEierd', 'commercial-unit-desktop-top']})
    }
    for label, divs in label_divs.items():
        if divs:
            return label
    return 'unknown'


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
    parsed['text'] = f"{text} <label>{label}</label>" if label else text

    submenu = parse_ad_menu(sub)
    if submenu:
        parsed['sub_type'] = 'submenu'
        parsed['details'] = submenu

    return parsed


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

    parsed = {"type": "ad", 
              "sub_type": "secondary", 
              "sub_rank": sub_rank}
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

def parse_ad_legacy(sub: bs4.element.Tag, sub_rank: int = 0) -> dict:
    """[legacy] Parse details of a single ad subcomponent, similar to general"""

    parsed = {"type": "ad", 
              "sub_type": "legacy", 
              "sub_rank": sub_rank}
    header = sub.find('div', {'class':'ad_cclk'})
    parsed['title'] = header.find('h3').text
    parsed['url'] = header.find('cite').text
    parsed['text'] = sub.find('div', {'class':'ads-creative'}).text
    
    bottom_text = sub.find('ul')
    if bottom_text:
        bottom_li = bottom_text.find_all('li')
        parsed['details'] = [li.get_text(separator=' ') for li in bottom_li]

    return parsed
