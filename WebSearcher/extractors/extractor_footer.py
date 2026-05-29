from selectolax.parser import Node

from .. import logger
from .extractor_main import _find_all_with_class, _unwrap

log = logger.Logger().start(__name__)


class ExtractorFooter:
    def __init__(self, soup, components):
        self.soup: Node | None = _unwrap(soup)
        self.components = components

    def extract(self):
        """Extract the footer section of the SERP."""
        assert self.soup is not None
        footer_div = self.soup.css_first('div[id="botstuff"]')
        footer_component_list: list[Node] = []

        if footer_div is not None:
            # bs4 ``find_all("div", {"id": ["bres","brs"]})`` = OR.
            footer_component_divs = _find_all_with_class(
                self.soup, 'div[id="bres"], div[id="brs"]', filter_empty=True
            )
            for footer_component_div in footer_component_divs:
                expanded_divs = _find_all_with_class(
                    footer_component_div, "div.MjjYud", filter_empty=True
                )
                if expanded_divs and len(expanded_divs) > 1:
                    footer_component_list.extend(expanded_divs)
                else:
                    footer_component_list.append(footer_component_div)

        omitted_notice = self.soup.css_first("div.ClPXac")
        if omitted_notice is not None:
            footer_component_list.append(omitted_notice)

        footer_component_list = [
            e for e in footer_component_list if not ExtractorFooter.is_hidden_footer(e)
        ]
        log.debug(f"footer_components: {len(footer_component_list)}")

        for footer_component in footer_component_list:
            self.components.add_component(footer_component, section="footer")

    @staticmethod
    def is_hidden_footer(element: Node) -> bool:
        """Filter out hidden footer components (no visual presence)."""
        for css in ("span.oUAcPd", "div.RTaUke", "div.KJ7Tg"):
            if element.css_first(css) is not None:
                return True
        return False
