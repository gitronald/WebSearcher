__version__ = "0.8.2a0"

from .classifiers import ClassifyFooter, ClassifyMain
from .extractors import Extractor
from .extractors.extractor_serp_features import FeatureExtractor
from .locations import download_locations
from .parsers import parse_serp
from .searchers import SearchEngine
from .utils import load_html, load_soup, make_soup

__all__ = [
    "ClassifyFooter",
    "ClassifyMain",
    "Extractor",
    "FeatureExtractor",
    "download_locations",
    "parse_serp",
    "SearchEngine",
    "load_html",
    "load_soup",
    "make_soup",
]
