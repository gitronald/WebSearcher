from pydantic import BaseModel
from typing import Any, Dict, Optional
import bs4

class BaseResult(BaseModel):
    type: str = 'unclassified'
    sub_type: Optional[str] = None
    sub_rank: int = 0
    title: Optional[str] = None
    url: Optional[str] = None
    text: Optional[str] = None
    cite: Optional[str] = None
    details: Optional[Any] = None

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
        self.soup = cmpt
        self.section = section
        self.type = type
        self.cmpt_rank = cmpt_rank

    def __str__(self):
        """Return a string representation of the Component"""
        return str(vars(self))

    def to_dict(self):
        return self.__dict__
    
    def get_metadata(self):
        return {k:v for k,v in self.to_dict().items() if k not in ['soup']}


class ComponentList:
    def __init__(self):
        self.components = []
        self.rank_counter = 0

    def __iter__(self):
        for component in self.components:
            yield component

    def add_component(self, component, section="unknown", type='unknown', cmpt_rank=None):
        """Add a component to the list of components"""
        if isinstance(component, Component):
            component.cmpt_rank = component.cmpt_rank if not cmpt_rank else cmpt_rank
            self.components.append(component)
        elif isinstance(component, bs4.element.Tag):
            cmpt_rank = self.rank_counter if not cmpt_rank else cmpt_rank
            component = Component(component, section, type, cmpt_rank)
            self.components.append(component)
        self.rank_counter += 1

    def to_records(self):
        return [Component.to_dict() for Component in self.components]
    