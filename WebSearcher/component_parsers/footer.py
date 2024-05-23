from . import parse_general_results, parse_people_also_ask, parse_searches_related
from .. import component_classifier
from .. import logger
from ..models import BaseResult, Component, ComponentList
from ..webutils import get_text, find_all_divs

log = logger.Logger().start(__name__)

import traceback


def parse_footer(soup):
    footer = Footer(soup)
    footer.extract_components()
    return footer.parse_footer()


class Footer:
    def __init__(self, soup):
        self.soup = soup
        self.footer_soup = None
        self.components = ComponentList()


    def extract(self):
        self.footer_soup = self.soup.find('div', {'id':'botstuff'})


    def extract_components(self):
        footer_cmpts = find_all_divs(self.soup, 'div', {'id':['bres', 'brs']})
        expanded = []
        if footer_cmpts:
            for cmpt in footer_cmpts:
                divs = find_all_divs(cmpt, "div", {"class":"MjjYud"})
                if divs and len(divs) > 1:
                    expanded.extend(divs)
                else:
                    expanded.append(cmpt)

        omitted_notice = self.soup.find('div', {'class':'ClPXac'})
        if omitted_notice:
            expanded.append(omitted_notice)

        expanded = [e for e in expanded if not self.is_hidden(e)]
        log.debug(f'Expanded footer components: {len(expanded)}')

        for cmpt in expanded:
            self.components.add_component(cmpt, type=self.classify_component(cmpt))


    def is_hidden(self, element):
        conditions = [
            element.find("span", {"class":"oUAcPd"}),   
            element.find("div", {"class": "RTaUke"}),   
            element.find("div", {"class": "KJ7Tg"}),    
        ]
        return any(conditions)


    @classmethod
    def classify_component(self, component_soup, cmpt_type="unknown"):
        cmpt = component_soup
        gsection = cmpt.find('g-section-with-header')
        subs = cmpt.find_all('div', {'class':'g'})

        conditions = [
            ('id' in cmpt.attrs and cmpt.attrs['id'] == 'bres'),
            ('class' in cmpt.attrs and cmpt.attrs['class'] == ['MjjYud'])
        ]

        if any(conditions):
            if subs:
                cmpt_type = 'img_cards'
            elif cmpt.find('g-scrolling-carousel'):
                cmpt_type = 'discover_more'
            elif cmpt.find('h3'):
                cmpt_type = self.classify_searches_related(cmpt)

        elif self.classify_omitted_notice(cmpt):
            cmpt_type = 'omitted_notice'

        elif gsection:
            cmpt_type = 'searches_related'

        if cmpt_type == 'unknown':
            log.debug('falling back to main classifier')
            cmpt_type = component_classifier.classify_type(cmpt)

        return cmpt_type


    @classmethod
    def classify_omitted_notice(self, cmpt):
        conditions = [
            cmpt.find("p", {"id":"ofr"}),
            (get_text(cmpt, "h2") == "Notices about Filtered Results"),
        ]
        return any(conditions)


    @classmethod
    def classify_searches_related(self, cmpt):
        log.debug('classifying searches related component')
        known_labels = {'Related', 
                        'Related searches', 
                        'People also search for', 
                        'Related to this search'}
        h3 = cmpt.find('h3')
        if h3:
            h3_matches = [h3.text.strip().startswith(text) for text in known_labels]
            if any(h3_matches):
                return 'searches_related'
        return 'unknown'


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