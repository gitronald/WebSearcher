import bs4
from .. import webutils
from .. import logger

log = logger.Logger().start(__name__)

class ExtractorFooter:
    def __init__(self, soup: bs4.BeautifulSoup, components):
        self.soup = soup
        self.components = components

    def extract(self):
        """Extract the footer section of the SERP"""

        footer_div = self.soup.find('div', {'id':'botstuff'})
        footer_component_list = []

        if footer_div:
            footer_component_divs = webutils.find_all_divs(
                self.soup, 'div', {'id': ['bres', 'brs']}
            )
            if footer_component_divs:
                for footer_component_div in footer_component_divs:
                    expanded_divs = webutils.find_all_divs(
                        footer_component_div, "div", {"class": "MjjYud"}
                    )
                    if expanded_divs and len(expanded_divs) > 1:
                        footer_component_list.extend(expanded_divs)
                    else:
                        footer_component_list.append(footer_component_div)

        omitted_notice = self.soup.find('div', {'class':'ClPXac'})
        if omitted_notice:
            footer_component_list.append(omitted_notice)

        footer_component_list = [
            e for e in footer_component_list
            if not ExtractorFooter.is_hidden_footer(e)
        ]
        log.debug(f'footer_components: {len(footer_component_list)}')

        for footer_component in footer_component_list:
            self.components.add_component(footer_component, section='footer')

    @staticmethod
    def is_hidden_footer(element):
        """Filter out hidden footer components (no visual presence)."""
        conditions = [
            element.find("span", {"class":"oUAcPd"}),
            element.find("div", {"class": "RTaUke"}),
            element.find("div", {"class": "KJ7Tg"}),
        ]
        return any(conditions)