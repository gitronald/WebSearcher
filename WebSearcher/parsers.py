from . import webutils
from .extractors import Extractor
from .logger import Logger
log = Logger().start(__name__)

from bs4 import BeautifulSoup
from typing import Union, Optional, List, Dict


def parse_serp(serp: Union[str, BeautifulSoup], 
               serp_id: Optional[str] = None, 
               crawl_id: Optional[str] = None) -> List[Dict]:
    """Parse a Search Engine Result Page (SERP)"""

    log.debug(f'SERP ID: {serp_id} | Crawl ID: {crawl_id}')
    soup = webutils.make_soup(serp)

    # Extract components
    extractor = Extractor(soup, serp_id=serp_id, crawl_id=crawl_id)
    extractor.extract_components()
    component_list = extractor.components

    # Parse components
    for cmpt in component_list:
        cmpt.classify_component()
        cmpt.parse_component()
    
    return component_list.export_component_results()
