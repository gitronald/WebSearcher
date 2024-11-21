from .. import webutils

class Footer:

    @classmethod
    def parse_image_cards(self, elem) -> list:
        subs = webutils.find_all_divs(elem, 'div', {'class':'g'})
        return [self.parse_image_card(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

    @classmethod
    def parse_image_card(self, sub, sub_rank=0) -> dict:
        parsed = {'type':'img_cards', 'sub_rank':sub_rank}
        parsed['title'] = webutils.get_text(sub, "div", {'aria-level':"3", "role":"heading"})
        images = sub.find_all('img')
        if images:
            parsed['details'] = [{'text':i['alt'], 'url':i['src']} for i in images]
        return parsed

    @classmethod
    def parse_discover_more(self, elem) -> list:
        carousel = elem.find('g-scrolling-carousel')
        return [{
            'type':'discover_more', 
            'sub_rank':0,
            'text': '|'.join(c.text for c in carousel.find_all('g-inner-card'))
        }]

    @classmethod
    def parse_omitted_notice(self, elem) -> list:
        return [{
            'type':'omitted_notice',
            'sub_rank':0, 
            'text': webutils.get_text(elem)
        }]