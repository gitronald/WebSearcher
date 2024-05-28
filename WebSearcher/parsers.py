from . import webutils
from .extractors import Extractor
from .logger import Logger
log = Logger().start(__name__)

from bs4 import BeautifulSoup
from typing import Union, List, Dict


def parse_serp(serp: Union[str, BeautifulSoup]) -> List[Dict]:
    """Parse a Search Engine Result Page (SERP)"""

    # Extract components
    soup = webutils.make_soup(serp)
    extractor = Extractor(soup)
    extractor.extract_components()
    component_list = extractor.components

    # Classify and parse components
    for cmpt in component_list:
        cmpt.classify_component()
        cmpt.parse_component()
    
    return component_list.export_component_results()
