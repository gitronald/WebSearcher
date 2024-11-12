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

    def parse_component(self, parser_type_func: callable = None):
        
        log.debug(f"parsing: {self.cmpt_rank} | {self.section} | {self.type}")
        assert self.type, "Null component type"

        if not parser_type_func:
            # Assign parser function and run on component
            try:
                if self.type == "unknown":
                    parsed_list = parse_unknown(self)

                if self.section == "header":
                    header_parser = header_parser_dict.get(self.type, None)
                    parsed_list = header_parser(self.elem)

                elif self.type not in main_parser_dict and self.type not in footer_parser_dict:
                    parsed_list = parse_not_implemented(self)

                elif self.section == "footer":
                    footer_parser = footer_parser_dict.get(self.type, None)
                    parsed_list = footer_parser(self.elem)

                elif self.section in {"main", "header", "rhs"}:
                    # TODO: Update component_parsers/* to accept a Component object, currently expects a bs4 element
                    main_parser = main_parser_dict.get(self.type, None)
                    parsed_list = main_parser(self.elem)

            except Exception:
                log.exception(f"Parsing Exception | {self.cmpt_rank} | {self.type}")
                parsed_list = [{"type": self.type,
                                "cmpt_rank": self.cmpt_rank,
                                "text": self.elem.get_text("<|>", strip=True),
                                "error": traceback.format_exc()}]
        else:
            # Run provided parser function on component
            try:
                parser_type_func(self)
                
            except Exception:
                log.exception(f"Parsing Exception | {self.cmpt_rank} | {self.type}")
                parsed_list = [{"type": self.type,
                                "cmpt_rank": self.cmpt_rank,
                                "text": self.elem.get_text("<|>", strip=True),
                                "error": traceback.format_exc()}]


        # Check for empty results list
        if len(parsed_list) == 0:
            log.debug(f"No subcomponents parsed for {self.cmpt_rank} | {self.type}")
            parsed_list = [{"type": self.type,
                            "cmpt_rank": self.cmpt_rank,
                            "text": self.elem.get_text("<|>", strip=True),
                            "error": "No results parsed"}]
        
        # Track parsed results
        assert type(parsed_list) in [list, dict], f"parser output must be list or dict: {type(parsed_list)}"
        assert len(parsed_list) > 0, f"Empty parsed list: {parsed_list}"
        parsed_list = parsed_list if isinstance(parsed_list, list) else [parsed_list]
        self.add_parsed_result_list(parsed_list)

    def add_parsed_result_list(self, parsed_result_list):
        """Add a list of parsed results with BaseResult validation to results_list"""
        assert len(parsed_result_list) > 0, "Empty parsed result list"
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
    