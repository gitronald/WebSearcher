from . import webutils
from .extractors import Extractor
from .logger import Logger
log = Logger().start(__name__)

import re
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


class FeatureExtractor:
    @staticmethod
    def extract_features(html: str) -> dict:
        rx_estimate = re.compile(r'<div id="result-stats">.*?</div>')
        rx_language = re.compile(r'<html[^>]*\slang="([^"]+)"')
        rx_no_results = re.compile(r"Your search - .*? - did not match any documents\.")
        output = {}

        # Extract result estimate count and time
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
        match = rx_language.search(html)
        output['language'] = match.group(1) if match else None

        # No results notice
        match = rx_no_results.search(html)
        output['notice_no_results'] = bool(match)

        # Shortened query notice
        pattern = "(and any subsequent words) was ignored because we limit queries to 32 words."
        output['notice_shortened_query'] = (pattern in html)

        # Server error notice
        pattern = "We're sorry but it appears that there has been an internal server error while processing your request."
        output['notice_server_error'] = (pattern in html)

        # Infinity scroll button
        pattern = '<span class="RVQdVd">More results</span>'
        output['infinity_scroll'] = (pattern in html)

        return output
