__version__ = "0.12.1"

import logging
from typing import TYPE_CHECKING

from .classifiers import ClassifyFooter, ClassifyMain
from .extractors import Extractor
from .extractors.extractor_serp_features import FeatureExtractor
from .locations import download_locations, update_locations_file
from .parsers.parse_serp import parse_serp
from .utils import load_html, load_soup, make_soup

# Own only the package logger: the NullHandler keeps unconfigured (parse-only) use
# silent -- no lastResort stderr fallback -- while root stays the application's.
logging.getLogger(__name__).addHandler(logging.NullHandler())

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
    # Lazy-load SearchEngine so parse-only consumers don't pay the searcher stack's
    # import cost (requests, brotli, the models) on `import WebSearcher`; patchright
    # itself is imported later still, inside PatchrightSearcher.init_driver.
    if name == "SearchEngine":
        from .searchers import SearchEngine

        globals()["SearchEngine"] = SearchEngine  # cache: __getattr__ runs once
        return SearchEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
