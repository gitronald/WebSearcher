import bs4
from .. import webutils
from .. import logger

log = logger.Logger().start(__name__)

class ExtractorHeader:
    def __init__(self, soup: bs4.BeautifulSoup, components):
        self.soup = soup
        self.components = components
        self.exists = False

    def extract(self):
        """Extract the header section: appbar and notices."""
        self.extract_appbar()
        self.extract_notices()

    def extract_appbar(self):
        """Extract the top bar section, often a carousel of images or other suggestions."""
        appbar = self.soup.find('div', {'id':'appbar'})
        if appbar:
            has_img = appbar.find(lambda tag: tag.has_attr('src') and not tag.has_attr('data-src'))
            if appbar.find('g-scrolling-carousel') and has_img:
                self.components.add_component(appbar, section='header', type='top_image_carousel')
                self.exists = True

    def extract_notices(self):
        """Append notices to the components list at the end."""
        notices = webutils.find_all_divs(self.soup, "div", {"id": "oFNiHe"}, filter_empty=True)
        if notices:
            self.exists = True
            for notice in notices:
                self.components.add_component(notice, section="header", type="notice")