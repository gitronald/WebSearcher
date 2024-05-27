from .models import BaseResult
from .classifiers import ClassifyMain, ClassifyFooter
from typing import Dict
import bs4

class Component:
    def __init__(self, elem: bs4.element.Tag, section="unknown", type='unknown', cmpt_rank=None):
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
    
    def get_metadata(self) -> Dict:
        key_filter = ['section', 'cmpt_rank']
        return {k:v for k,v in self.to_dict().items() if k in key_filter}
    
    def classify_component(self, classify_type_func: callable = None):
        """Classify the component type"""
        if classify_type_func:
            self.type = classify_type_func(self.elem)
        else:
            if self.type == "unknown":
                if self.section == "main":
                    self.type = ClassifyMain.classify(self.elem)
                elif self.section == "footer":
                    self.type = ClassifyFooter.classify(self.elem)

    def parse_component(self, parser_type_func: callable):
        """Parse the component using a parser function"""
        parsed_list = parser_type_func(self.elem)
        self.add_parsed_result_list(parsed_list)

    def add_parsed_result_list(self, parsed_result_list):
        """Add a list of parsed results with BaseResult validation to results_list"""
        for parsed_result in parsed_result_list:
            parsed_result_validated = BaseResult(**parsed_result).model_dump()
            self.result_list.append(parsed_result_validated)

    def add_parsed_result(self, parsed_result):
        """Add a parsed result with BaseResult validation to results_list"""
        parsed_result_validated = BaseResult(**parsed_result).model_dump()
        self.result_list.append(parsed_result_validated)

    def export_results(self):
        """Export the list of results"""

        results_metadata_list = []
        for result in self.result_list:
            result_metadata = {"section":self.section, "cmpt_rank":self.cmpt_rank}
            result_metadata.update(result)
            results_metadata_list.append(result_metadata)

        return results_metadata_list


class ComponentList:
    def __init__(self, serp_id=None, crawl_id=None):
        self.components = []
        self.crawl_id = crawl_id
        self.serp_id = serp_id
        self.cmpt_rank_counter = 0
        self.serp_rank_counter = 0

    def __iter__(self):
        for component in self.components:
            yield component

    def add_component(self, elem:bs4.element.Tag, section="unknown", type='unknown', cmpt_rank=None):
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
                result['crawl_id'] = self.crawl_id
                result['serp_id'] = self.serp_id
                result['serp_rank'] = self.serp_rank_counter
                results.append(result)
                self.serp_rank_counter += 1
        return results


    def to_records(self):
        return [Component.to_dict() for Component in self.components]
    