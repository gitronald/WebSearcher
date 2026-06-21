__version__ = "0.10.0"

from typing import TYPE_CHECKING

from .classifiers import ClassifyFooter, ClassifyMain
from .extractors import Extractor
from .extractors.extractor_serp_features import FeatureExtractor
from .locations import download_locations, update_locations_file
from .parsers import parse_serp
from .utils import load_html, load_soup, make_soup

if TYPE_CHECKING:
    from .searchers import SearchEngine

__all__ = [
    "ClassifyFooter",
    "ClassifyMain",
    "Extractor",
    "FeatureExtractor",
    "download_locations",
    "update_locations_file",
    "parse_serp",
    "SearchEngine",
    "load_html",
    "load_soup",
    "make_soup",
]


def __getattr__(name: str):
    # Lazy-load SearchEngine so parse-only consumers don't pay the Selenium /
    # undetected-chromedriver import cost on `import WebSearcher`.
    if name == "SearchEngine":
        from .searchers import SearchEngine

        globals()["SearchEngine"] = SearchEngine  # cache: __getattr__ runs once
        return SearchEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
