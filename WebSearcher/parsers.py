from . import webutils
from .component_classifier import classify_type
from .component_parsers import get_component_parser, parse_unknown, parse_not_implemented, Footer
from .extractors import Extractor
from .components import Component, ComponentList
from .logger import Logger
log = Logger().start(__name__)

import traceback
from bs4 import BeautifulSoup


def parse_serp(serp: BeautifulSoup, serp_id: str = None, crawl_id: str = None, 
               verbose: bool = False, make_soup: bool = False) -> list:
    """Parse a Search Engine Result Page (SERP)"""

    log.debug(f'SERP ID: {serp_id} | Crawl ID: {crawl_id}')
    soup = webutils.make_soup(serp) if make_soup and type(serp) is not BeautifulSoup else serp
    assert type(soup) is BeautifulSoup, 'Input must be BeautifulSoup'

    # Extract components
    extractor = Extractor(soup, serp_id=serp_id, crawl_id=crawl_id)
    extractor.extract_components()

    # Parse components
    results = parse_component_list(extractor.components)
    return results


def parse_component_list(components: ComponentList) -> list:
    """Parse a list of SERP components"""
    
    results = []
    for cmpt in components.components:
        
        # Classify component (some main are already classified e.g., ads)
        if cmpt.section == "main" and cmpt.type == "unknown":
            cmpt.classify_component(classify_type)
        elif cmpt.section == "footer":
            cmpt.classify_component(Footer.classify_component)

        # Parse component
        cmpt = parse_component(cmpt)
    results = components.export_component_results()

    return results


def parse_component(cmpt: Component, cmpt_type: str = None) -> list:
    """Parse a SERP component"""

    cmpt.type = cmpt_type if cmpt_type else cmpt.type
    log.debug(f"{cmpt.cmpt_rank} | {cmpt.section} | {cmpt.type}")
    assert cmpt.type, 'Null component type'
    
    # Parse component
    try:
        parser = get_component_parser(cmpt)
        if parser == parse_not_implemented or parser == parse_unknown:
            parsed = parser(cmpt)
        else:
            # All existing parsers expect a soup element
            parsed = parser(cmpt.elem)
        assert type(parsed) in [list, dict], f'parsed must be list or dict: {type(parsed)}'
        parsed_list = parsed if isinstance(parsed, list) else [parsed]
   
    except Exception:
        log.exception(f'Parsing Exception | {cmpt.cmpt_rank} | {cmpt.type}')
        parsed_list = [{'type': cmpt.type,
                       'cmpt_rank': cmpt.cmpt_rank,
                       'text': cmpt.elem.get_text("<|>", strip=True),
                       'error': traceback.format_exc()}]

    # Validate and add results
    cmpt.add_parsed_result_list(parsed_list)

    return cmpt

