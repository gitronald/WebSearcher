""" Parsers for ad components

Changelog
---------
2024-05-08: 
- added new div class for text field
- added labels (e.g., "Provides abortions") from <span class="mXsQRe">, appended to text field

2025-04-27: added carousel sub_type, global parsed output

"""

from .. import webutils
from .shopping_ads import parse_shopping_ads
import bs4

PARSED = {
    'type': 'ad',
    'sub_type': '',
    'sub_rank': 0,
    'title': '',
    'url': '',
    'cite': '',
    'text': '',
}

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
        for sub_rank, sub in enumerate(subs):
            sub_classes = sub.attrs.get("class", [])
            if "commercial-unit-desktop-top" in sub_classes:
                parsed_list.extend(parse_shopping_ads(sub))
            elif "uEierd" in sub_classes:
                parsed_list.append(parse_ad(sub, sub_rank=sub_rank))
    elif sub_type == 'carousel':
        parsed_list = parse_ad_carousel(cmpt, sub_type)
    return parsed_list


def classify_ad_type(cmpt: bs4.element.Tag) -> str:
    """Classify the type of ad component"""
    label_divs = {
        "legacy": webutils.find_all_divs(cmpt, 'div', {'class': 'ad_cclk'}),
        "secondary": webutils.find_all_divs(cmpt, 'div', {'class': 'd5oMvf'}),
        "standard": webutils.find_all_divs(cmpt, 'div', {'class': ['uEierd', 'commercial-unit-desktop-top']}),
        "carousel": webutils.find_all_divs(cmpt, 'g-scrolling-carousel'),
    }
    for label, divs in label_divs.items():
        if divs:
            return label
    return 'unknown'


def parse_ad_carousel(cmpt: bs4.element.Tag, sub_type: str, filter_visible: bool = True) -> list:

    def parse_ad_carousel_div(sub: bs4.element.Tag, sub_type: str, sub_rank: int) -> dict:
        """Parse ad carousel div, seen 2025-02-06"""
        parsed = PARSED.copy()
        parsed['sub_type'] = sub_type
        parsed['sub_rank'] = sub_rank
        parsed['title'] = webutils.get_text(sub, 'div', {'class':'e7SMre'})
        parsed['url'] = webutils.get_link(sub)
        parsed['text'] = webutils.get_text(sub, 'div', {"class":"vrAZpb"})
        parsed['cite'] = webutils.get_text(sub, 'div', {"class":"zpIwr"})
        parsed['visible'] = not (sub.has_attr('data-has-shown') and sub['data-has-shown'] == 'false')
        return parsed
    
    def parse_ad_carousel_card(sub: bs4.element.Tag, sub_type: str, sub_rank: int) -> dict:
        """Parse ad carousel card, seen 2024-09-21"""
        parsed = PARSED.copy()
        parsed['sub_type'] = sub_type
        parsed['sub_rank'] = sub_rank
        parsed['title'] = webutils.get_text(sub, 'div', {'class':'gCv54b'})
        parsed['url'] = webutils.get_link(sub, {"class": "KTsHxd"})
        parsed['text'] = webutils.get_text(sub, 'div', {"class":"VHpBje"})
        parsed['cite'] = webutils.get_text(sub, 'div', {"class":"j958Pd"})
        parsed['visible'] = not (sub.has_attr('data-viewurl') and sub['data-viewurl'])
        return parsed

    ad_carousel_parsers = [
        {'find_kwargs': {'name': 'g-inner-card'}, 
         'parser': parse_ad_carousel_card},
        {'find_kwargs': {'name': 'div', 'attrs': {'class': 'ZPze1e'}},
         'parser': parse_ad_carousel_div}
    ]

    output_list = []
    ad_carousel = cmpt.find('g-scrolling-carousel')
    if ad_carousel:
        for parser_details in ad_carousel_parsers:
            parser_func = parser_details['parser']
            kwargs = parser_details['find_kwargs']
            sub_cmpts = webutils.find_all_divs(ad_carousel, **kwargs)
            if sub_cmpts:
                for sub_rank, sub in enumerate(sub_cmpts):
                    parsed = parser_func(sub, sub_type, sub_rank)
                    output_list.append(parsed)

    if filter_visible:
        output_list = [{k:v for k,v in x.items() if k != 'visible'} for x in output_list if x['visible']]
    return output_list


def parse_ad(sub: bs4.element.Tag, sub_rank: int = 0) -> dict:
    """Parse details of a single ad subcomponent, similar to general"""
    parsed = PARSED.copy()
    parsed["sub_type"] = "standard"
    parsed["sub_rank"] = sub_rank

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
    parsed = PARSED.copy()
    parsed["sub_type"] = "secondary"
    parsed["sub_rank"] = sub_rank

    parsed['title'] = webutils.get_text(sub, 'div', {'role':'heading'})
    link_div = sub.find('div', {'class':'d5oMvf'})
    parsed['url'] = webutils.get_link(link_div) if link_div else ''
    parsed['cite'] = webutils.get_text(sub, 'span', {'class':'gBIQub'})

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
    parsed = PARSED.copy()
    parsed["sub_type"] = "legacy"
    parsed["sub_rank"] = sub_rank
    
    header = sub.find('div', {'class':'ad_cclk'})
    parsed['title'] = webutils.get_text(header, 'h3')
    parsed['url'] = webutils.get_text(header, 'cite')
    parsed['text'] = webutils.get_text(sub, 'div', {'class':'ads-creative'})
    
    bottom_text = sub.find('ul')
    if bottom_text:
        bottom_li = bottom_text.find_all('li')
        parsed['details'] = [li.get_text(separator=' ') for li in bottom_li]

    return parsed
