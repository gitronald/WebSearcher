from selectolax.lexbor import LexborNode as Node

from .. import utils
from ..extractors import Extractor
from ..extractors.extractor_serp_features import FeatureExtractor
from ..logger import Logger
from .components.ai_overview import raw_serp_html

log = Logger().start(__name__)


def parse_serp(serp: str | Node, url: str | None = None) -> dict:
    """Parse a Search Engine Result Page (SERP).

    Args:
        serp: The HTML content of the SERP or a parsed selectolax ``Node``.
        url: The response's final URL, when known. A ``/sorry/`` redirect
            flags ``features["captcha"]`` even when the HTML is empty.

    Returns:
        A dict with 'results' and 'features' keys.
    """
    soup = utils.make_soup(serp)
    # Publish the raw markup (if we have it) so the AI overview parser skips
    # a full-document serialization per cmpt.
    raw_html: str | None = None
    if isinstance(serp, str):
        raw_html = serp
    elif isinstance(serp, bytes):
        raw_html = serp.decode("utf-8", errors="replace")
    token = raw_serp_html.set(raw_html)
    try:
        extractor = Extractor(soup)
        extractor.extract_components()
        component_list = extractor.components

        for cmpt in component_list:
            cmpt.classify_component()
            cmpt.parse_component()
        results = component_list.export_component_results()
    finally:
        raw_serp_html.reset(token)

    # Forward raw HTML (when available) + soup so feature extraction takes the
    # regex path and reuses the already-parsed soup for shared probes. The main
    # layout label is internal to extraction, so surface it on the features here.
    features = FeatureExtractor.extract_features(serp, soup=soup, url=url)
    features.main_layout = extractor.main_handler.layout_label
    return {
        "features": features.model_dump(),
        "results": results,
    }
