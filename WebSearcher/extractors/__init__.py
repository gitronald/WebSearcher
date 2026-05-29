from selectolax.parser import Node

from .. import logger
from ..components import ComponentList
from .extractor_footer import ExtractorFooter
from .extractor_header import ExtractorHeader
from .extractor_main import ExtractorMain, _unwrap
from .extractor_rhs import ExtractorRightHandSide

log = logger.Logger().start(__name__)


class Extractor:
    def __init__(self, soup):
        self.soup: Node = _unwrap(soup)
        self.components = ComponentList()
        self.rhs_handler = ExtractorRightHandSide(self.soup, self.components)
        self.header_handler = ExtractorHeader(self.soup, self.components)
        self.main_handler = ExtractorMain(self.soup, self.components)
        self.footer_handler = ExtractorFooter(self.soup, self.components)

    def extract_components(self):
        log.debug(f"Extracting Components {'-' * 50}")
        dom_positions = self._get_dom_positions(self.soup)
        self.rhs_handler.extract()
        self.header_handler.extract()
        self.main_handler.extract()
        self.footer_handler.extract()
        self.rhs_handler.append()
        self.components.reorder_by_dom_position(dom_positions)
        log.debug(f"total components: {self.components.cmpt_rank_counter:,}")

    @staticmethod
    def _get_dom_positions(soup: Node) -> dict[int, tuple[int, int]]:
        """Map ``mem_id -> (start_pos, end_pos)`` in pre-order traversal.

        ``end_pos`` is the position of the last descendant tag, so element B is
        inside element A when A.start <= B.start <= A.end.
        """
        # bs4 ``soup.find_all(True)`` = all tags in document order. Native:
        # walk the entire tree (subtree of root + self if relevant). ``soup``
        # here is the root html node; its subtree contains every element.
        all_tags: list[Node] = [soup] + list(soup.css("*"))
        # Dedupe by mem_id (root may appear in css if implementation quirks).
        seen: set[int] = set()
        unique_tags: list[Node] = []
        for t in all_tags:
            if t.mem_id not in seen:
                seen.add(t.mem_id)
                unique_tags.append(t)
        all_tags = unique_tags
        pos: dict[int, int] = {t.mem_id: i for i, t in enumerate(all_tags)}
        end = list(range(len(all_tags)))
        for i in range(len(all_tags) - 1, -1, -1):
            parent = all_tags[i].parent
            if parent is not None and parent.mem_id in pos:
                pi = pos[parent.mem_id]
                if end[i] > end[pi]:
                    end[pi] = end[i]
        return {t.mem_id: (i, end[i]) for i, t in enumerate(all_tags)}
