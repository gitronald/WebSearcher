__version__ = "0.5.2"
from .searchers import SearchEngine
from .parsers import parse_serp, FeatureExtractor
from .extractors import Extractor
from .locations import download_locations
from .classifiers import ClassifyMain, ClassifyFooter
from .webutils import load_html, make_soup, load_soup
