from bs4 import BeautifulSoup

from . import utils
from .extractors import Extractor
from .feature_extractor import FeatureExtractor
from .logger import Logger

log = Logger().start(__name__)


def parse_serp(serp: str | BeautifulSoup, extract_features: bool = False) -> list[dict] | dict:
    """Parse a Search Engine Result Page (SERP)

    Args:
        serp: The HTML content of the SERP or a BeautifulSoup object
        extract_features: Whether to also extract SERP features. Defaults to False.

    Returns:
        If extract_features is False, returns a list of result components.
        If extract_features is True, returns a dict with 'results' and 'features' keys.
    """
    # Extract components
    soup = utils.make_soup(serp)
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
            "features": FeatureExtractor.extract_features(soup).to_dict(),
            "results": results,
        }

    return results
