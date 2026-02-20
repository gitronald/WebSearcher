import bs4
from ..components import ComponentList
from .extractor_rhs import ExtractorRightHandSide
from .extractor_main import ExtractorMain
from .extractor_header import ExtractorHeader
from .extractor_footer import ExtractorFooter

from .. import logger
log = logger.Logger().start(__name__)

class Extractor:
    def __init__(self, soup: bs4.BeautifulSoup):
        self.soup = soup
        self.components = ComponentList()
        self.rhs_handler = ExtractorRightHandSide(self.soup, self.components)
        self.header_handler = ExtractorHeader(self.soup, self.components)
        self.main_handler = ExtractorMain(self.soup, self.components)
        self.footer_handler = ExtractorFooter(self.soup, self.components)

    def extract_components(self):
        log.debug(f"Extracting Components {'-'*50}")
        dom_positions = self._get_dom_positions(self.soup)
        self.rhs_handler.extract()
        self.header_handler.extract()
        self.main_handler.extract()
        self.footer_handler.extract()
        self.rhs_handler.append()
        self.components.reorder_by_dom_position(dom_positions)
        log.debug(f"total components: {self.components.cmpt_rank_counter:,}")

    @staticmethod
    def _get_dom_positions(soup):
        """Map element id -> (start_pos, end_pos) in pre-order traversal.

        end_pos is the position of the last descendant tag, so element B is
        inside element A when A.start <= B.start <= A.end.
        """
        all_tags = list(soup.find_all(True))
        pos = {id(t): i for i, t in enumerate(all_tags)}
        end = list(range(len(all_tags)))
        for i in range(len(all_tags) - 1, -1, -1):
            parent = all_tags[i].parent
            if parent and id(parent) in pos:
                pi = pos[id(parent)]
                if end[i] > end[pi]:
                    end[pi] = end[i]
        return {id(t): (i, end[i]) for i, t in enumerate(all_tags)}
