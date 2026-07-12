import logging
import traceback
from collections.abc import Callable

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text
from ..classifiers import ClassifyFooter, ClassifyMain
from ..models.data import (
    ERR_BAD_OUTPUT,
    ERR_EXCEPTION,
    ERR_NO_SUBCOMPONENTS,
    ERR_NOT_IMPLEMENTED,
    ERR_NULL_TYPE,
    BaseResult,
    error_details,
)
from .components import (
    footer_parser_dict,
    header_parser_dict,
    main_parser_dict,
    parse_unknown,
)

log = logging.getLogger(__name__)


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
        # Shallow copy so callers can't mutate the Component's attribute table
        # through the returned dict (``__dict__`` is the live instance namespace).
        return dict(self.__dict__)

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
            parsed_list = self.create_parsed_list_error(ERR_EXCEPTION, is_exception=True)
        return parsed_list

    def parse_component(self, parser_type_func: Callable | None = None):

        if not self.type:
            parsed_list = self.create_parsed_list_error(ERR_NULL_TYPE)
        else:
            # Select and run parser; a missing parser is "not implemented".
            parser_func = self.select_parser(parser_type_func)
            if parser_func is None:
                parsed_list = self.create_parsed_list_error(ERR_NOT_IMPLEMENTED)
            else:
                parsed_list = self.run_parser(parser_func)

                # Check parsed_list
                if not isinstance(parsed_list, (list, dict)):
                    parsed_list = self.create_parsed_list_error(ERR_BAD_OUTPUT)
                elif len(parsed_list) == 0:
                    parsed_list = self.create_parsed_list_error(ERR_NO_SUBCOMPONENTS)

        parsed_list = parsed_list if isinstance(parsed_list, list) else [parsed_list]
        self.add_parsed_result_list(parsed_list)

    def create_parsed_list_error(self, error_msg: str, is_exception: bool = False) -> list:
        error_traceback = ""
        if is_exception:
            log.exception(f"{error_msg}: {self.cmpt_rank} | {self.section} | {self.type}")
            error_traceback = traceback.format_exc()
        else:
            log.debug(f"{error_msg}: {self.cmpt_rank} | {self.section} | {self.type}")
        error = error_msg if not is_exception else f"{error_msg}: {error_traceback}"
        return [
            {
                "type": self.type,
                "text": get_text(self.elem, "<|>", strip=True),
                "details": error_details(error),
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
