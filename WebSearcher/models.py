from pydantic import BaseModel
from typing import Any, Dict, Optional
import bs4


class BaseResult(BaseModel):
    sub_rank: int = 0
    type: str = 'unclassified'
    sub_type: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    text: Optional[str] = None
    cite: Optional[str] = None
    details: Optional[Any] = None
    error: Optional[str] = None


class BaseSERP(BaseModel):
    qry: str                   # Search query 
    loc: Optional[str] = None  # Location if set, "Canonical Name"
    url: str                   # URL of SERP   
    html: str                  # Raw HTML of SERP
    timestamp: str             # Timestamp of crawl
    response_code: int         # HTTP response code
    user_agent: str            # User agent used for the crawl
    serp_id: str               # Search Engine Results Page (SERP) ID
    crawl_id: str              # Crawl ID for grouping SERPs
    version: str               # WebSearcher version


class Component:
    def __init__(self, cmpt, section='unknown', type='unknown', cmpt_rank=0):
        self.soup: bs4.element.Tag = cmpt
        self.crawl_id: Optional[str] = None
        self.serp_id: Optional[str] = None
        self.section: str = section
        self.type = type
        self.cmpt_rank = cmpt_rank
        self.result_list = []
        self.result_counter = 0

    def __str__(self):
        """Return a string representation of the Component"""
        return str(vars(self))

    def to_dict(self):
        return self.__dict__
    
    def get_metadata(self):
        # return {k:v for k,v in self.to_dict().items() if k in {'crawl_id', 'serp_id', 'section', 'cmpt_rank'}}
        return {k:v for k,v in self.to_dict().items() if k in {'section', 'cmpt_rank'}}
    
    def classify_component(self, classify_type_func: callable):
        """Classify the component type"""
        self.type = classify_type_func(self.soup)

    def parse_component(self, parser_type_func: callable):
        """Parse the component using a parser function"""
        parsed_result = parser_type_func(self.soup)
        self.add_parsed_result(parsed_result)

    def add_parsed_result(self, parsed_result):
        """Add a parsed result with BaseResult validation to results_list"""
        parsed_result_validated = BaseResult(**parsed_result).model_dump()
        self.result_list.append(parsed_result_validated)

    def export_results(self):
        """Export the list of results"""

        results_metadata_list = []
        for result in self.result_list:
            result_metadata = {}
            result_metadata.update(self.get_metadata())
            result_metadata.update(result)
            results_metadata_list.append(result_metadata)

        return results_metadata_list


class ComponentList:
    def __init__(self, serp_id=None, crawl_id=None):
        self.components = []
        self.crawl_id = crawl_id
        self.serp_id = serp_id
        self.cmpt_rank_counter = 0

    def __iter__(self):
        for component in self.components:
            yield component

    def add_component(self, component, section="unknown", type='unknown', cmpt_rank=None):
        """Add a component to the list of components"""
        if isinstance(component, Component):
            component.cmpt_rank = component.cmpt_rank if not cmpt_rank else cmpt_rank
            component.crawl_id = self.crawl_id
            component.serp_id = self.serp_id
            self.components.append(component)
        elif isinstance(component, bs4.element.Tag):
            cmpt_rank = self.cmpt_rank_counter if not cmpt_rank else cmpt_rank
            component = Component(component, section, type, cmpt_rank)
            component.crawl_id = self.crawl_id
            component.serp_id = self.serp_id
            self.components.append(component)
        self.cmpt_rank_counter += 1

    def export_component_results(self):
        """Export the results of all components"""
        results = []
        serp_rank = 0
        for cmpt in self.components:
            for result in cmpt.export_results():
                result['serp_rank'] = serp_rank
                results.append(result)
                serp_rank += 1
        return results


    def to_records(self):
        return [Component.to_dict() for Component in self.components]
    