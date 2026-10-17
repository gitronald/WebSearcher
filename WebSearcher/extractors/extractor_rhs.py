import logging
from typing import Any

from selectolax.lexbor import LexborNode as Node

from .._slx import has_text
from ..parsers.component_list import ComponentList

log = logging.getLogger(__name__)


class ExtractorRightHandSide:
    def __init__(self, soup: Node | None, components: ComponentList):
        self.soup: Node | None = soup
        self.components = components
        self.rhs: dict[str, Any] = {}

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
        elif has_text(rhs_div):
            # The panel was detached from the tree above, so an unrecognized
            # layout would otherwise vanish from the parse. Keep it as an
            # ``unknown`` rhs component (the catch-all parser records its text).
            log.debug("no rhs_layout; keeping as unknown")
            self.rhs = {"elem": div, "section": "rhs", "type": "unknown"}
        else:
            log.debug("no rhs_layout")

    def append(self):
        """Append the RHS panel as a component at the end."""
        if self.rhs:
            log.debug("appending rhs")
            self.components.add_component(**self.rhs)
            self.rhs = {}

    def _get_layout(self, rhs_div: Node) -> tuple[str | None, Node]:
        if rhs_div.attrs.get("role") == "complementary":
            return "rhs_complementary", rhs_div
        # bs4 list-of-classes = OR -> CSS comma selector.
        if rhs_div.css_first("div.kp-wholepage, div.knowledge-panel, div.TzHB6b") is not None:
            return "rhs_knowledge", rhs_div
        # Entity panels without those wrappers (the ``jOAHU``/``rhs_column`` and
        # ``A6K0A`` layouts, "See results about" disambiguation boxes) still carry
        # knowledge-graph ``data-attrid`` markers, which the knowledge_rhs parser
        # reads directly.
        if rhs_div.css_first("[data-attrid]") is not None:
            return "rhs_knowledge_attrid", rhs_div
        return None, rhs_div
