from . import webutils
from .component_classifier import classify_type
from .component_parsers import type_functions, Footer
from .extractors import Extractor
from .models import Component, ComponentList
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
        
        # Classify component
        if cmpt.section == "main" and cmpt.type == "unknown":
            cmpt.classify_component(classify_type)
        elif cmpt.section == "footer":
            cmpt.classify_component(Footer.classify_component)

        # Parse component
        cmpt = parse_component(cmpt)
    results = components.export_component_results()

    return results


def parse_component(cmpt: Component, cmpt_type: str = None) -> list:
    """Parse a SERP component
    
    Args:
        cmpt (bs4 object): A parsed SERP component
        cmpt_type (str, optional): The type of component it is
    
    Returns:
        list: The parsed results and/or subresults
    """

    cmpt.type = cmpt_type if cmpt_type else cmpt.type
    log.debug(f"{cmpt.cmpt_rank} | {cmpt.section} | {cmpt.type}")
    assert cmpt.type, 'Null component type'
    
    # Parse component
    try:
        parser = get_component_parser(cmpt)
        if parser == parse_not_implemented or parser == parse_unknown:
            parsed = parser(cmpt)
        else:
            parsed = parser(cmpt.soup)
        assert type(parsed) in [list, dict], f'parsed must be list or dict: {type(parsed)}'
        parsed_list = parsed if isinstance(parsed, list) else [parsed]
   
    except Exception:
        log.exception(f'Parsing Exception | {cmpt.cmpt_rank} | {cmpt.type}')
        parsed_list = parse_exception(cmpt)

    # Validate and add results
    for parsed_result in parsed_list:
        cmpt.add_parsed_result(parsed_result)

    return cmpt


def get_component_parser(cmpt:Component, cmpt_funcs:dict=type_functions) -> callable:
    """Returns the parser for a given component type"""
    if cmpt.type in cmpt_funcs:
        return cmpt_funcs[cmpt.type]
    elif cmpt.type == 'unknown':
        return parse_unknown
    else:
        return parse_not_implemented


def parse_unknown(cmpt: Component) -> list:
    parsed_result = {'type': cmpt.type,
                     'cmpt_rank': cmpt.cmpt_rank,
                     'text': cmpt.soup.get_text("<|>", strip=True) if cmpt.soup else None}
    return [parsed_result]


def parse_not_implemented(cmpt: Component) -> list:
    """Placeholder function for component parsers that are not implemented"""
    parsed_result = {'type': cmpt.type,
                     'cmpt_rank': cmpt.cmpt_rank,
                     'text': cmpt.soup.get_text("<|>", strip=True),
                     'error': 'not implemented'}
    return [parsed_result]


def parse_exception(cmpt: Component) -> list:
    """Placeholder function for component parsers that raise an exception"""
    parsed_result = {'type': cmpt.type,
                     'cmpt_rank': cmpt.cmpt_rank,
                     'text': cmpt.soup.get_text("<|>", strip=True),
                     'error': traceback.format_exc()}
    return [parsed_result]