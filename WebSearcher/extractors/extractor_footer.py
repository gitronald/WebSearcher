import logging

from selectolax.lexbor import LexborNode as Node

from ..parsers.component_list import ComponentList
from ..parsers.components._common import under_any
from .extractor_main import _find_all_with_class

log = logging.getLogger(__name__)


class ExtractorFooter:
    def __init__(self, soup: Node | None, components: ComponentList):
        self.soup: Node | None = soup
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

        footer_component_list = [
            e for e in footer_component_list if not ExtractorFooter.is_hidden_footer(e)
        ]

        omitted_notice = self.soup.css_first("div.ClPXac")
        if omitted_notice is not None and not ExtractorFooter.is_hidden_footer(omitted_notice):
            # A notice nested inside a kept #bres (or an expanded MjjYud) is
            # already part of that component; adding it again would double-count
            # it. Dedup against the filtered list so a notice whose container was
            # dropped as hidden is still emitted on its own.
            ids = {c.mem_id for c in footer_component_list}
            if omitted_notice.mem_id not in ids and not under_any(omitted_notice, ids, -1):
                footer_component_list.append(omitted_notice)
        log.debug(f"footer_components: {len(footer_component_list)}")

        for footer_component in footer_component_list:
            self.components.add_component(footer_component, section="footer")

    @staticmethod
    def is_hidden_footer(element: Node) -> bool:
        """Filter out hidden footer components (no visual presence)."""
        # Comma-union boolean OR of the three probes -- one short-circuiting walk.
        return element.css_first("span.oUAcPd, div.RTaUke, div.KJ7Tg") is not None
