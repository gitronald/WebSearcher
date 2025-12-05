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
        self.rhs_handler.extract()
        self.header_handler.extract()
        self.main_handler.extract()
        self.footer_handler.extract()
        self.rhs_handler.append()
        log.debug(f"total components: {self.components.cmpt_rank_counter:,}")
