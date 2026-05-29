from selectolax.parser import Node

from . import utils
from .extractors import Extractor
from .extractors.extractor_serp_features import FeatureExtractor
from .logger import Logger

log = Logger().start(__name__)


def parse_serp(serp: str | Node) -> dict:
    """Parse a Search Engine Result Page (SERP).

    Args:
        serp: The HTML content of the SERP or a parsed selectolax ``Node``.

    Returns:
        A dict with 'results' and 'features' keys.
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

    return {
        "features": FeatureExtractor.extract_features(soup).model_dump(),
        "results": results,
    }
