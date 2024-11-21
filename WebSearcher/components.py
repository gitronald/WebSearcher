from .models import BaseResult
from .classifiers import ClassifyMain, ClassifyFooter, ClassifyHeaderComponent
from .component_parsers import main_parser_dict, footer_parser_dict, header_parser_dict
from .component_parsers import parse_unknown, parse_not_implemented
from .logger import Logger
log = Logger().start(__name__)

import bs4
import traceback
from typing import Dict

class Component:
    def __init__(self, elem: bs4.element.Tag, section="unknown", type="unknown", cmpt_rank=None):
        self.elem: bs4.element.Tag = elem
        self.section: str = section
        self.type = type
        self.cmpt_rank = cmpt_rank
        self.result_list = []
        self.result_counter = 0

    def __str__(self) -> str:
        return str(vars(self))

    def to_dict(self) -> Dict:
        return self.__dict__
    
    def get_metadata(self, key_filter=["section", "cmpt_rank"]) -> Dict:
        return {k:v for k,v in self.to_dict().items() if k in key_filter}
    
    def classify_component(self, classify_type_func: callable = None):
        """Classify the component type"""
        if classify_type_func:
            self.type = classify_type_func(self.elem)
        else:
            if self.type == "unknown":
                if self.section == "header":
                    self.type = ClassifyHeaderComponent.classify(self.elem)
                    log.debug(f"header classification: {self.type}")
                if self.section == "main":
                    self.type = ClassifyMain.classify(self.elem)
                elif self.section == "footer":
                    self.type = ClassifyFooter.classify(self.elem)

    def select_parser(self, parser_type_func: callable = None) -> callable:
        if parser_type_func:
            parser_func = parser_type_func
        else:
            if self.type == "unknown":
                parser_func = parse_unknown
            elif self.section == "header":
                parser_func = header_parser_dict.get(self.type, parse_not_implemented)
            elif self.section == "footer":
                parser_func = footer_parser_dict.get(self.type, parse_not_implemented)
            elif self.section in {"main", "rhs"}:
                parser_func = main_parser_dict.get(self.type, parse_not_implemented)
            else:
                parser_func = parse_not_implemented
        return parser_func

    def run_parser(self, parser_func: callable) -> list:
        log.debug(f"parsing: {self.cmpt_rank} | {self.section} | {self.type}")
        try:
            if parser_func in {parse_unknown, parse_not_implemented}:
                parsed_list = parser_func(self)
            else:
                parsed_list = parser_func(self.elem)
        except Exception:
            parsed_list = self.create_parsed_list_error("parsing exception", is_exception=True)
        return parsed_list

    def parse_component(self, parser_type_func: callable = None):
        
        if not self.type:
            parsed_list = self.create_parsed_list_error("null component type")
        else:
            # Select and run parser
            parser_func = self.select_parser(parser_type_func)
            parsed_list = self.run_parser(parser_func)
            
            # Check parsed_list
            if not isinstance(parsed_list, (list, dict)):
                parsed_list = self.create_parsed_list_error("parser output not list or dict")
            elif len(parsed_list) == 0:
                parsed_list = self.create_parsed_list_error("no subcomponents parsed")

        parsed_list = parsed_list if isinstance(parsed_list, list) else [parsed_list]
        self.add_parsed_result_list(parsed_list)

    def create_parsed_list_error(self, error_msg: str, is_exception: bool = False) -> list:
        if is_exception:
            log.exception(f"{error_msg}: {self.cmpt_rank} | {self.section} | {self.type}")
            error_traceback = traceback.format_exc()
        else:
            log.debug(f"{error_msg}: {self.cmpt_rank} | {self.section} | {self.type}")
        return [{
            "type": self.type,
            "cmpt_rank": self.cmpt_rank,
            "text": self.elem.get_text("<|>", strip=True),
            "error": error_msg if not is_exception else f"{error_msg}: {error_traceback}"
        }]

    def add_parsed_result_list(self, parsed_result_list):
        for parsed_result in parsed_result_list:
            self.add_parsed_result(parsed_result)

    def add_parsed_result(self, parsed_result):
        """Add a parsed result with BaseResult validation to results_list"""
        parsed_result_validated = BaseResult(**parsed_result).model_dump()
        self.result_list.append(parsed_result_validated)

    def export_results(self):
        """Export the list of results"""
        result_metadata = {"section":self.section, "cmpt_rank":self.cmpt_rank}
        results_list = [{**result_metadata, **result} for result in self.result_list]
        return results_list


class ComponentList:
    def __init__(self):
        self.components = []
        self.cmpt_rank_counter = 0
        self.serp_rank_counter = 0

    def __iter__(self):
        for component in self.components:
            yield component

    def add_component(self, elem:bs4.element.Tag, section="unknown", type="unknown", cmpt_rank=None):
        """Add a component to the list of components"""
        cmpt_rank = self.cmpt_rank_counter if not cmpt_rank else cmpt_rank
        component = Component(elem, section, type, cmpt_rank)

        self.components.append(component)
        self.cmpt_rank_counter += 1

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
        return [Component.to_dict() for Component in self.components]
