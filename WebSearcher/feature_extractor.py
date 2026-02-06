import re
from bs4 import BeautifulSoup

from . import webutils
from .models.features import SERPFeatures


class FeatureExtractor:
    @staticmethod
    def extract_features(html_or_soup: str | BeautifulSoup) -> SERPFeatures:
        """Extract SERP features from HTML or a BeautifulSoup object

        Args:
            html_or_soup: The HTML content or a BeautifulSoup object

        Returns:
            The extracted features
        """

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
            result_estimate_count = None
            result_estimate_time = None
        else:
            count_match = re.search(r'([0-9,]+) results', result_estimate_div)
            time_match = re.search(r'([0-9.]+) seconds', result_estimate_div)
            result_estimate_count = float(count_match.group(1).replace(",","")) if count_match else None
            result_estimate_time = float(time_match.group(1)) if time_match else None

        # Extract language
        rx_language = re.compile(r'<html[^>]*\slang="([^"]+)"')
        match = rx_language.search(html)
        language = match.group(1) if match else None

        # No results notice
        rx_no_results = re.compile(r"Your search - .*? - did not match any documents\.")
        match = rx_no_results.search(html)
        notice_no_results = bool(match)

        string_match_dict = {
            'notice_shortened_query': "(and any subsequent words) was ignored because we limit queries to 32 words.",
            'notice_server_error': "We're sorry but it appears that there has been an internal server error while processing your request.",
            'infinity_scroll': '<span class="RVQdVd">More results</span>'
        }
        string_matches = {key: (pattern in html) for key, pattern in string_match_dict.items()}

        # Location prompt overlay (id="lb" with "precise location" text)
        lb = soup.find('div', {'id': 'lb'})
        overlay_precise_location = bool(lb and 'precise location' in lb.get_text().lower())

        return SERPFeatures(
            result_estimate_count=result_estimate_count,
            result_estimate_time=result_estimate_time,
            language=language,
            notice_no_results=notice_no_results,
            overlay_precise_location=overlay_precise_location,
            **string_matches,
        )
