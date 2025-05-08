import bs4
from .. import webutils
from .. import logger

log = logger.Logger().start(__name__)

class ExtractorRightHandSide:
    def __init__(self, soup: bs4.BeautifulSoup, components):
        self.soup = soup
        self.components = components
        self.rhs = {}

    def extract(self):
        """Extract the RHS Knowledge Panel, if present."""
        rhs_div = self.soup.find('div', {'id': 'rhs'})
        if not rhs_div:
            return
        rhs_div.extract()
        layout, div = self._get_layout(rhs_div)
        if layout:
            log.debug(f"rhs_layout: {layout}")
            self.rhs = {
                "elem": div,
                "section": "rhs",
                "type": "knowledge_rhs"
            }
        else:
            log.debug("no rhs_layout")

    def append(self):
        """Append the RHS panel as a component at the end."""
        if self.rhs:
            log.debug("appending rhs")
            self.components.add_component(**self.rhs)
            self.rhs = {}

    def _get_layout(self, rhs_div):
        rhs_layouts = {
            'rhs_complementary': rhs_div if webutils.check_dict_value(rhs_div.attrs, "role", "complementary") else None,
            'rhs_knowledge': rhs_div.find('div', {'class': ['kp-wholepage', 'knowledge-panel', 'TzHB6b']})
        }
        found = next((name for name, node in rhs_layouts.items() if node), None)
        return (found, rhs_div) if found else (None, rhs_div)