import traceback
from collections.abc import Callable

from selectolax.lexbor import LexborNode as Node

from ._slx import get_text
from .classifiers import ClassifyFooter, ClassifyMain
from .component_parsers import (
    footer_parser_dict,
    header_parser_dict,
    main_parser_dict,
    parse_unknown,
)
from .logger import Logger
from .models.data import BaseResult

log = Logger().start(__name__)


def _last_descendant(elem: Node) -> Node:
    """The last element of ``elem.css('*')`` (self + descendants, pre-order)
    without materializing the whole subtree.

    The last node a pre-order walk visits is reached by repeatedly descending to
    the last *element* child (selectolax pseudo-nodes -- text/comment -- carry a
    ``-``-prefixed or empty tag and are excluded from ``css('*')``, so they are
    skipped here too). Returns ``elem`` itself when it has no element children,
    matching ``elem.css('*')[-1]`` for a leaf.
    """
    node = elem
    while True:
        last: Node | None = None
        for ch in node.iter(include_text=False):
            if ch.tag and not ch.tag.startswith("-"):
                last = ch
        if last is None:
            return node
        node = last


class Component:
    """A SERP component extracted from HTML"""

    def __init__(
        self,
        elem: Node,
        section: str = "unknown",
        type: str = "unknown",
        cmpt_rank: int | None = None,
    ) -> None:
        """Initialize a Component

        Args:
            elem: The selectolax ``Node`` containing the component HTML
            section: The SERP section (header, main, footer, rhs)
            type: The component type (e.g., general, ads, top_stories)
            cmpt_rank: The component's rank position on the SERP
        """
        self.elem: Node = elem
        self.section = section
        self.type = type
        self.cmpt_rank = cmpt_rank
        self.result_list: list[dict] = []

    def __str__(self) -> str:
        return str(vars(self))

    def to_dict(self) -> dict:
        return self.__dict__

    def classify_component(self, classify_type_func: Callable | None = None):
        """Classify the component type"""
        if classify_type_func:
            self.type = classify_type_func(self.elem)
        else:
            if self.type == "unknown":
                if self.section == "main":
                    self.type = ClassifyMain.classify(self.elem)
                elif self.section == "footer":
                    self.type = ClassifyFooter.classify(self.elem)

    def select_parser(self, parser_type_func: Callable | None = None) -> Callable | None:
        """Return the parser for this component, or ``None`` if the (known)
        type has no registered parser -- the caller reports that as a
        ``"not implemented"`` error."""
        if parser_type_func:
            return parser_type_func
        if self.type == "unknown":
            return parse_unknown
        if self.section == "header":
            return header_parser_dict.get(self.type)
        if self.section == "footer":
            return footer_parser_dict.get(self.type)
        if self.section in {"main", "rhs"}:
            return main_parser_dict.get(self.type)
        return None

    def run_parser(self, parser_func: Callable) -> list:
        log.debug(f"parsing: {self.cmpt_rank} | {self.section} | {self.type}")
        try:
            parsed_list = parser_func(self.elem)
        except Exception:
            parsed_list = self.create_parsed_list_error("parsing exception", is_exception=True)
        return parsed_list

    def parse_component(self, parser_type_func: Callable | None = None):

        if not self.type:
            parsed_list = self.create_parsed_list_error("null component type")
        else:
            # Select and run parser; a missing parser is "not implemented".
            parser_func = self.select_parser(parser_type_func)
            if parser_func is None:
                parsed_list = self.create_parsed_list_error("not implemented")
            else:
                parsed_list = self.run_parser(parser_func)

                # Check parsed_list
                if not isinstance(parsed_list, (list, dict)):
                    parsed_list = self.create_parsed_list_error("parser output not list or dict")
                elif len(parsed_list) == 0:
                    parsed_list = self.create_parsed_list_error("no subcomponents parsed")

        parsed_list = parsed_list if isinstance(parsed_list, list) else [parsed_list]
        self.add_parsed_result_list(parsed_list)

    def create_parsed_list_error(self, error_msg: str, is_exception: bool = False) -> list:
        error_traceback = ""
        if is_exception:
            log.exception(f"{error_msg}: {self.cmpt_rank} | {self.section} | {self.type}")
            error_traceback = traceback.format_exc()
        else:
            log.debug(f"{error_msg}: {self.cmpt_rank} | {self.section} | {self.type}")
        return [
            {
                "type": self.type,
                "cmpt_rank": self.cmpt_rank,
                "text": get_text(self.elem, "<|>", strip=True),
                "error": error_msg if not is_exception else f"{error_msg}: {error_traceback}",
            }
        ]

    def add_parsed_result_list(self, parsed_result_list):
        for parsed_result in parsed_result_list:
            self.add_parsed_result(parsed_result)

    def add_parsed_result(self, parsed_result):
        """Add a parsed result with BaseResult validation to results_list"""
        parsed_result_validated = BaseResult(**parsed_result).model_dump()
        self.result_list.append(parsed_result_validated)

    def export_results(self):
        """Export the list of results"""
        result_metadata = {"section": self.section, "cmpt_rank": self.cmpt_rank}
        results_list = [{**result_metadata, **result} for result in self.result_list]
        return results_list


class ComponentList:
    def __init__(self):
        self.components = []
        self.cmpt_rank_counter = 0
        self.serp_rank_counter = 0

    def __iter__(self):
        yield from self.components

    def add_component(self, elem, section="unknown", type="unknown", cmpt_rank=None):
        """Add a component to the list of components"""
        cmpt_rank = self.cmpt_rank_counter if cmpt_rank is None else cmpt_rank
        component = Component(elem, section, type, cmpt_rank)

        self.components.append(component)
        self.cmpt_rank_counter += 1

    def reorder_by_dom_position(self, positions):
        """Reorder components by DOM position within each section.

        ``positions`` maps ``mem_id -> pre-order index`` for every element in
        the document. End ranges for main components are derived on demand from
        the last descendant (``_last_descendant``, the last node a pre-order walk
        of the subtree visits -- its index is the end of the subtree). When a
        component's range contains another component's start, the ancestor's
        effective position shifts to the first direct child positioned after the
        nested subtree.
        """
        section_order = {"header": 0, "main": 1, "footer": 2, "rhs": 3}
        main_components = [c for c in self.components if c.section == "main"]

        def _range(elem):
            start = positions.get(elem.mem_id)
            if start is None:
                return None
            # The last descendant's index is the end of the subtree. Find it via
            # a right-spine descent rather than materializing the whole subtree
            # (``elem.css('*')``) only to read its last entry.
            end = positions.get(_last_descendant(elem).mem_id, start)
            return start, end

        ranges = {id(c): _range(c.elem) for c in main_components}

        def _effective_pos(cmpt):
            rng = ranges[id(cmpt)]
            if rng is None:
                return float("inf")
            start, end = rng
            for other in main_components:
                if other is cmpt:
                    continue
                other_rng = ranges[id(other)]
                if other_rng is None:
                    continue
                o_start, o_end = other_rng
                if start <= o_start <= end:
                    # cmpt.elem is an ancestor of other.elem -- find the first
                    # direct child positioned after the nested subtree.
                    best = float("inf")
                    for ch in cmpt.elem.iter(include_text=False):
                        ch_start = positions.get(ch.mem_id)
                        if ch_start is not None and o_end < ch_start < best:
                            best = ch_start
                    if best != float("inf"):
                        return best
            return start

        def sort_key(cmpt):
            section_idx = section_order.get(cmpt.section, 1)
            if cmpt.section == "main":
                return (section_idx, _effective_pos(cmpt))
            return (section_idx, cmpt.cmpt_rank)

        self.components.sort(key=sort_key)
        for i, cmpt in enumerate(self.components):
            cmpt.cmpt_rank = i
        self.cmpt_rank_counter = len(self.components)

    def export_component_results(self):
        """Export the results of all components"""
        results = []
        for cmpt in self.components:
            for result in cmpt.export_results():
                result["serp_rank"] = self.serp_rank_counter
                results.append(result)
                self.serp_rank_counter += 1
        return results

    def to_records(self):
        return [cmpt.to_dict() for cmpt in self.components]
