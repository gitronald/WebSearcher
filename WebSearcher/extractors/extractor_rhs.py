from selectolax.parser import Node

from .. import logger
from .extractor_main import _unwrap

log = logger.Logger().start(__name__)


class ExtractorRightHandSide:
    def __init__(self, soup, components):
        self.soup: Node | None = _unwrap(soup)
        self.components = components
        self.rhs: dict = {}

    def extract(self):
        """Extract the RHS Knowledge Panel, if present."""
        assert self.soup is not None
        rhs_div = self.soup.css_first('div[id="rhs"]')
        if rhs_div is None:
            return
        rhs_div.remove(recursive=False)
        layout, div = self._get_layout(rhs_div)
        if layout:
            log.debug(f"rhs_layout: {layout}")
            self.rhs = {"elem": div, "section": "rhs", "type": "knowledge_rhs"}
        else:
            log.debug("no rhs_layout")

    def append(self):
        """Append the RHS panel as a component at the end."""
        if self.rhs:
            log.debug("appending rhs")
            self.components.add_component(**self.rhs)
            self.rhs = {}

    def _get_layout(self, rhs_div: Node) -> tuple[str | None, Node]:
        if rhs_div.attributes.get("role") == "complementary":
            return "rhs_complementary", rhs_div
        # bs4 list-of-classes = OR -> CSS comma selector.
        if rhs_div.css_first("div.kp-wholepage, div.knowledge-panel, div.TzHB6b") is not None:
            return "rhs_knowledge", rhs_div
        return None, rhs_div
