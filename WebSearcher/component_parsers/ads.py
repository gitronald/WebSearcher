""" Parsers for ad components

Changelog
---------
2024-05-08: 
- added new div class for text field
- added labels (e.g., "Provides abortions") from <span class="mXsQRe">, appended to text field

2025-04-27: added carousel sub_type, global parsed output

"""

import bs4
from .. import webutils
from ..models.data import BaseResult, DetailsItem
from .shopping_ads import parse_shopping_ads

SUB_TYPES = [
    "legacy",
    "secondary",
    "standard",
    "shopping",
    "carousel",
]


def classify_ad_type(cmpt: bs4.element.Tag) -> str:
    """Classify the type of ad component"""
    label_divs = {
        "legacy": webutils.find_all_divs(cmpt, 'div', {'class': 'ad_cclk'}),
        "secondary": webutils.find_all_divs(cmpt, 'div', {'class': 'd5oMvf'}),
        "shopping": webutils.find_all_divs(cmpt, 'div', {'class': 'commercial-unit-desktop-top'}),
        "standard": webutils.find_all_divs(cmpt, 'div', {'class': 'uEierd'}),
        "carousel": webutils.find_all_divs(cmpt, 'g-scrolling-carousel'),
    }
    for label, divs in label_divs.items():
        if divs:
            return label
    return 'unknown'


def parse_ads(cmpt: bs4.element.Tag) -> list:
    """Parse ads from ad component"""

    subtype_parsers = {
        'legacy': parse_ad_legacy,
        'secondary': parse_ad_secondary,
        'shopping': parse_ad_shopping,
        'standard': parse_ad_standard,
        'carousel': parse_ad_carousel,
    }
    parsed_list = []
    sub_type = classify_ad_type(cmpt)
    if sub_type in subtype_parsers:
        parser = subtype_parsers.get(sub_type)
        parsed_list = parser(cmpt)
    return parsed_list

# ------------------------------------------------------------------------------

def parse_ad_legacy(cmpt: bs4.element.Tag) -> list:

    def _parse_ad_legacy(cmpt: bs4.element.Tag) -> list:
        subs = cmpt.find_all('li', {'class': 'ads-ad'})
        return [_parse_ad_legacy_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

    def _parse_ad_legacy_sub(sub: bs4.element.Tag, sub_rank: int) -> dict:
        header = sub.find('div', {'class': 'ad_cclk'})
        parsed = BaseResult(
            type='ad', 
            sub_type='legacy', 
            sub_rank=sub_rank,
            title=webutils.get_text(header, 'h3'),
            url=webutils.get_text(header, 'cite'),
            cite=None,
            text=webutils.get_text(sub, 'div', {'class': 'ads-creative'}),
            details=_parse_ad_legacy_sub_details(sub),
            error=None
        ).model_dump()
        return parsed

    def _parse_ad_legacy_sub_details(sub: bs4.element.Tag) -> list:
        details_list = []
        bottom_text = sub.find('ul')
        if bottom_text:
            bottom_text_list = bottom_text.find_all('li')
            details_list = [DetailsItem(text=li.get_text(separator=' ')).to_dict() for li in bottom_text_list]
        return details_list

    return _parse_ad_legacy(cmpt)

# ------------------------------------------------------------------------------

def parse_ad_secondary(cmpt: bs4.element.Tag) -> list:

    def _parse_ad_secondary(cmpt: bs4.element.Tag) -> list:
        subs = cmpt.find_all('li', {'class': 'ads-fr'})
        return [_parse_ad_secondary_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

    def _parse_ad_secondary_sub(sub: bs4.element.Tag, sub_rank: int) -> dict:
        return BaseResult(
            type='ad',
            sub_type='secondary',
            sub_rank=sub_rank,
            title=webutils.get_text(sub, 'div', {'role': 'heading'}),
            url=_parse_ad_secondary_sub_url(sub),
            cite=webutils.get_text(sub, 'span', {'class': 'gBIQub'}),
            text=_parse_ad_secondary_sub_text(sub),
            details=_parse_ad_secondary_sub_details(sub),
            error=None
        ).model_dump()
    
    def _parse_ad_secondary_sub_url(sub: bs4.element.Tag) -> str:
        url_div = webutils.get_div(sub, 'div', {'class': 'd5oMvf'})
        return webutils.get_link(url_div)

    def _parse_ad_secondary_sub_text(sub) -> str:
        text_divs = sub.find_all('div', {'class': 'yDYNvb'})
        return '|'.join([d.text for d in text_divs]) if text_divs else ''

    def _parse_ad_secondary_sub_details(sub: bs4.element.Tag) -> list:
        for selector in [{'role': 'list'}, {'class': 'bOeY0b'}]:
            details_section = sub.find('div', selector)
            if details_section:
                urls = webutils.get_link_list(details_section)
                return [DetailsItem(url=url).to_dict() for url in urls] if urls else None
    
    return _parse_ad_secondary(cmpt)


# ------------------------------------------------------------------------------

def parse_ad_shopping(cmpt: bs4.element.Tag) -> list:
    """Parse shopping ads from component"""
    subs = webutils.find_all_divs(cmpt, 'div', {'class': 'commercial-unit-desktop-top'})
    parsed_list = []
    for sub in subs:
        parsed_list.extend(parse_shopping_ads(sub))
    return parsed_list

# ------------------------------------------------------------------------------

def parse_ad_standard(cmpt: bs4.element.Tag) -> list:
    """Parse standard ads from component"""

    def _parse_ad_standard_sub(sub: bs4.element.Tag, sub_rank: int = 0) -> dict:

        def _parse_ad_standard_text(sub: bs4.element.Tag) -> str:
            name_attrs = [
                {'name': 'div', 'attrs': {'class': 'yDYNvb'}},
                {'name': 'div', 'attrs': {'class': 'Va3FIb'}},
            ]
            for kwargs in name_attrs:
                text = webutils.get_text(sub, **kwargs)
                if text:
                    break
            label = webutils.get_text(sub, 'span', {'class': 'mXsQRe'})
            return f"{text} <label>{label}</label>" if label else text
        
        submenu = parse_ad_menu(sub)
        sub_type = 'submenu' if submenu else 'standard'
        parsed = BaseResult(
            type='ad',
            sub_type=sub_type,
            sub_rank=sub_rank,
            title=webutils.get_text(sub, 'div', {'role': 'heading'}),
            url=webutils.get_link(sub, {'class': 'sVXRqc'}),
            cite=webutils.get_text(sub, 'span', {'role': 'text'}),
            text=_parse_ad_standard_text(sub),
            details=submenu,
            error=None
        ).model_dump()
        return parsed

    subs = webutils.find_all_divs(cmpt, 'div', {'class': 'uEierd'})
    return [_parse_ad_standard_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def parse_ad_menu(sub: bs4.element.Tag) -> list:
    """Parse menu items for a large ad with additional subresults"""

    parsed_items = []
    menu_items = sub.find_all('div', {'class': 'MhgNwc'})
    for item in menu_items:
        parsed_item = DetailsItem().to_dict()
        item_divs = item.find_all('div', {'class': 'MUxGbd'})
        for div in item_divs:
            if webutils.check_dict_value(div.attrs, 'role', 'listitem'):
                parsed_item['url'] = webutils.get_link(div)
                parsed_item['title'] = webutils.get_text(div)
            else:
                parsed_item['text'] = webutils.get_text(div)
        parsed_items.append(parsed_item)
    return parsed_items


# ------------------------------------------------------------------------------

def parse_ad_carousel(
        cmpt: bs4.element.Tag, 
        sub_type: str = 'carousel', 
        filter_visible: bool = True
    ) -> list:

    def is_visible_div(sub: bs4.element.Tag) -> bool:
        """Check if carousel div is visible"""
        return not (sub.has_attr('data-has-shown') and sub['data-has-shown'] == 'false')

    def is_visible_card(sub: bs4.element.Tag) -> bool:
        """Check if carousel card is visible"""
        return not (sub.has_attr('data-viewurl') and sub['data-viewurl'])

    def parse_ad_carousel_div(sub: bs4.element.Tag, sub_type: str, sub_rank: int) -> dict:
        """Parse ad carousel div, seen 2025-02-06"""
        return BaseResult(
            type='ad', 
            sub_type=sub_type, 
            sub_rank=sub_rank,
            title=webutils.get_text(sub, 'div', {'class': 'e7SMre'}),
            url=webutils.get_link(sub),
            text=webutils.get_text(sub, 'div', {'class': 'vrAZpb'}),
            cite=webutils.get_text(sub, 'div', {'class': 'zpIwr'}),
            details=None,
            error=None
        ).model_dump()

    def parse_ad_carousel_card(sub: bs4.element.Tag, sub_type: str, sub_rank: int) -> dict:
        """Parse ad carousel card, seen 2024-09-21"""
        return BaseResult(
            type='ad', 
            sub_type=sub_type, 
            sub_rank=sub_rank,
            title=webutils.get_text(sub, 'div', {'class': 'gCv54b'}),
            url=webutils.get_link(sub, {'class': 'KTsHxd'}),
            text=webutils.get_text(sub, 'div', {'class': 'VHpBje'}),
            cite=webutils.get_text(sub, 'div', {'class': 'j958Pd'}),
            details=None,
            error=None
        ).model_dump()

    # Possible ad carousel item types
    output_list = []
    ad_carousel = cmpt.find('g-scrolling-carousel')
    if ad_carousel:
        ad_carousel_types = {
            'carousel_card': webutils.find_all_divs(ad_carousel, name='g-inner-card'),
            'carousel_div': webutils.find_all_divs(ad_carousel, name='div', attrs={'class': 'ZPze1e'})
        }

        for ad_carousel_type, sub_cmpts in ad_carousel_types.items():
            if sub_cmpts:
                for sub_rank, sub in enumerate(sub_cmpts):
                    if ad_carousel_type == 'carousel_card':
                        if filter_visible and not is_visible_card(sub):
                            continue
                        output = parse_ad_carousel_card(sub, sub_type, sub_rank)
                    elif ad_carousel_type == 'carousel_div':
                        if filter_visible and not is_visible_div(sub):
                            continue
                        output = parse_ad_carousel_div(sub, sub_type, sub_rank)
                    output_list.append(output)
                    
    return output_list
