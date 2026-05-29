from selectolax.parser import Node

from .. import logger
from .extractor_main import _find_all_with_class

log = logger.Logger().start(__name__)


class ExtractorHeader:
    def __init__(self, soup: Node | None, components):
        self.soup: Node | None = soup
        self.components = components
        self.exists = False

    def extract(self):
        """Extract the header section: appbar and notices."""
        self.extract_appbar()
        self.extract_notices()

    def extract_appbar(self):
        """Extract the top bar section, often a carousel of images or other suggestions."""
        assert self.soup is not None
        appbar = self.soup.css_first('div[id="appbar"]')
        if appbar is None:
            return
        # bs4 ``find(lambda tag: tag.has_attr("src") and not tag.has_attr("data-src"))``
        # -- predicate over all descendant elements.
        has_img = None
        for el in appbar.css("*"):
            if "src" in el.attributes and "data-src" not in el.attributes:
                has_img = el
                break
        if appbar.css_first("g-scrolling-carousel") is not None and has_img is not None:
            self.components.add_component(appbar, section="header", type="top_image_carousel")
            self.exists = True

    def extract_notices(self):
        """Append notices to the components list at the end."""
        assert self.soup is not None
        notices = _find_all_with_class(self.soup, 'div[id="oFNiHe"]', filter_empty=True)
        if notices:
            self.exists = True
            for notice in notices:
                self.components.add_component(notice, section="header", type="notice")
