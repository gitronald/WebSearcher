from ..models import BaseResult
from ..components import Component, ComponentList
from . import parse_general_results, parse_people_also_ask, parse_searches_related
from ..webutils import get_text, find_all_divs

from .. import logger
log = logger.Logger().start(__name__)

import traceback

class Footer:
    def __init__(self, soup):
        self.soup = soup
        self.footer_soup = None
        self.components = ComponentList()


    def parse_footer(self):
        parsed_list = sum([self.parse_component(c) for c in self.components.components], [])
        return parsed_list


    def parse_component(self, component:Component):
        assert component.type, 'Null component type'

        if component.type == 'unknown':
            validated = BaseResult(**component.get_metadata()).model_dump()
            return [validated]

        try: 
            parser = self.get_parser(component.type)
            parsed = parser(component.soup)

            if isinstance(parsed, list):
                for sub in parsed:
                    sub.update(component.get_metadata())
            elif isinstance(parsed, dict):
                parsed.update(component.get_metadata())
            else:
                raise TypeError(f'Parsed component must be list or dict: {parsed}')

        except Exception:
            log.exception('Parsing Exception - Footer')
            validated = BaseResult(**component.get_metadata()).model_dump()
            validated['error'] = traceback.format_exc()        
            return [validated]
        
        return parsed


    @classmethod
    def get_parser(self, cmpt_type: str) -> callable:
        if cmpt_type == 'img_cards':
            return self.parse_image_cards
        elif cmpt_type == 'searches_related':
            return parse_searches_related
        elif cmpt_type == 'discover_more':
            return self.parse_discover_more
        elif cmpt_type == 'general':
            return parse_general_results
        elif cmpt_type == 'people_also_ask':
            return parse_people_also_ask
        elif cmpt_type == 'omitted_notice':
            return self.parse_omitted_notice


    @classmethod
    def parse_image_cards(self, cmpt):
        subs = cmpt.find_all('div', {'class':'g'})
        return [self.parse_image_card(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


    @classmethod
    def parse_image_card(self, sub, sub_rank=0):
        parsed = {'type':'img_cards', 'sub_rank':sub_rank}
        parsed['title'] = get_text(sub, "div", {'aria-level':"3", "role":"heading"})
        images = sub.find_all('img')
        if images:
            parsed['details'] = [{'text':i['alt'], 'url':i['src']} for i in images]

        return parsed


    @classmethod
    def parse_discover_more(self, cmpt):
        carousel = cmpt.find('g-scrolling-carousel')
        return [{
            'type':'discover_more', 
            'sub_rank':0,
            'text': '|'.join(c.text for c in carousel.find_all('g-inner-card'))
        }]


    @classmethod
    def parse_omitted_notice(self, cmpt):
        return [{'type':'omitted_notice', 'sub_rank':0, 'text':cmpt.text}]