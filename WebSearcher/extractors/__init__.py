from selectolax.lexbor import LexborNode as Node

from .. import logger
from ..components import ComponentList
from .extractor_footer import ExtractorFooter
from .extractor_header import ExtractorHeader
from .extractor_main import ExtractorMain
from .extractor_rhs import ExtractorRightHandSide

log = logger.Logger().start(__name__)


class Extractor:
    def __init__(self, soup: Node):
        self.soup: Node = soup
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
        # ``soup.css('*')`` returns self + all descendants in document order
        # (selectolax CSS ``*`` matches self) -- a single C-level walk.
        all_tags: list[Node] = list(soup.css("*"))
        pos: dict[int, int] = {t.mem_id: i for i, t in enumerate(all_tags)}
        end = list(range(len(all_tags)))
        # Walk backwards: by the time we visit element i, end[i] already holds
        # the max position of its descendants (set by later iterations), so
        # propagating end[i] up to its parent chains the max correctly.
        for i in range(len(all_tags) - 1, -1, -1):
            parent = all_tags[i].parent
            if parent is None:
                continue
            pi = pos.get(parent.mem_id)
            if pi is not None and end[i] > end[pi]:
                end[pi] = end[i]
        return {t.mem_id: (i, end[i]) for i, t in enumerate(all_tags)}
