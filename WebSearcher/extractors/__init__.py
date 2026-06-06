from selectolax.lexbor import LexborNode as Node

from .. import logger
from ..components import ComponentList
from .extractor_footer import ExtractorFooter
from .extractor_header import ExtractorHeader
from .extractor_main import ExtractorMain
from .extractor_rhs import ExtractorRightHandSide

log = logger.Logger().start(__name__)


class Extractor:
    def __init__(self, soup: Node):
        self.soup: Node = soup
        self.components = ComponentList()
        self.rhs_handler = ExtractorRightHandSide(self.soup, self.components)
        self.header_handler = ExtractorHeader(self.soup, self.components)
        self.main_handler = ExtractorMain(self.soup, self.components)
        self.footer_handler = ExtractorFooter(self.soup, self.components)

    def extract_components(self):
        log.debug(f"Extracting Components {'-' * 50}")
        dom_positions = self._get_dom_positions(self.soup)
        self.rhs_handler.extract()
        self.header_handler.extract()
        self.main_handler.extract()
        self.footer_handler.extract()
        self.rhs_handler.append()
        self.components.reorder_by_dom_position(dom_positions)
        log.debug(f"total components: {self.components.cmpt_rank_counter:,}")

    @staticmethod
    def _get_dom_positions(soup: Node) -> dict[int, int]:
        """Map ``mem_id -> pre-order position`` for every element in the document.

        Just the starts; downstream code (``reorder_by_dom_position``) computes
        ``end`` ranges per main-component element on demand instead of walking
        ``.parent`` for every element of the document.
        """
        return {t.mem_id: i for i, t in enumerate(soup.css("*"))}
