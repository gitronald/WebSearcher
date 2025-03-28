from . import webutils
from .extractors import Extractor
from .logger import Logger
log = Logger().start(__name__)

import re
from bs4 import BeautifulSoup
from typing import Union, List, Dict, Tuple


def parse_serp(
        serp: Union[str, BeautifulSoup], 
        extract_features: bool = False
    ) -> Union[List[Dict], Tuple[List[Dict], Dict]]:
    """Parse a Search Engine Result Page (SERP)
    
    Args:
        serp (Union[str, BeautifulSoup]): The HTML content of the SERP or a BeautifulSoup object
        extract_features (bool, optional): Whether to also extract SERP features. Defaults to False.
        
    Returns:
        Union[List[Dict], Tuple[List[Dict], Dict]]: If extract_features is False, returns a list of result components.
            If extract_features is True, returns a tuple of (results, features).
    """
    # Extract components
    soup = webutils.make_soup(serp)
    extractor = Extractor(soup)
    extractor.extract_components()
    component_list = extractor.components

    # Classify and parse components
    for cmpt in component_list:
        cmpt.classify_component()
        cmpt.parse_component()
    results = component_list.export_component_results()
    
    if extract_features:
        return {
            "features": FeatureExtractor.extract_features(soup),
            "results": results
        }
    
    return results


class FeatureExtractor:
    @staticmethod
    def extract_features(html_or_soup: Union[str, BeautifulSoup]) -> dict:
        """Extract SERP features from HTML or a BeautifulSoup object
        
        Args:
            html_or_soup (Union[str, BeautifulSoup]): The HTML content or a BeautifulSoup object
            
        Returns:
            dict: The extracted features
        """
        
        output = {}
        if isinstance(html_or_soup, BeautifulSoup):
            soup = html_or_soup
            html = str(soup)
        else:
            html = html_or_soup
            soup = webutils.make_soup(html)

        # Extract result estimate count and time
        rx_estimate = re.compile(r'<div id="result-stats">.*?</div>')
        match = rx_estimate.search(html)
        result_estimate_div = match.group(0) if match else None
        if result_estimate_div is None:
            output["result_estimate_count"] = None
            output["result_estimate_time"] = None
        else:
            count_match = re.search(r'([0-9,]+) results', result_estimate_div)
            time_match = re.search(r'([0-9.]+) seconds', result_estimate_div)
            output["result_estimate_count"] = float(count_match.group(1).replace(",","")) if count_match else None
            output["result_estimate_time"] = float(time_match.group(1)) if time_match else None

        # Extract language
        rx_language = re.compile(r'<html[^>]*\slang="([^"]+)"')
        match = rx_language.search(html)
        output['language'] = match.group(1) if match else None

        # No results notice
        rx_no_results = re.compile(r"Your search - .*? - did not match any documents\.")
        match = rx_no_results.search(html)
        output['notice_no_results'] = bool(match)

        string_match_dict = {
            'notice_shortened_query': "(and any subsequent words) was ignored because we limit queries to 32 words.",
            'notice_server_error': "We're sorry but it appears that there has been an internal server error while processing your request.",
            'infinity_scroll': '<span class="RVQdVd">More results</span>'
        }
        for key, pattern in string_match_dict.items():
            output[key] = (pattern in html)
        
        return output
