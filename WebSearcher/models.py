from pydantic import BaseModel
from typing import Any, Dict, Optional

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
    def __init__(self, cmpt, type='unknown', cmpt_rank=0):
        self.soup = cmpt
        self.type = type
        self.cmpt_rank = cmpt_rank

    def to_dict(self):
        return self.__dict__
    
    def get_metadata(self):
        return {k:v for k,v in self.to_dict().items() if k not in ['soup']}


class ComponentList:
    def __init__(self):
        self.components = []
        self.rank_counter = 0

    def add_component(self, component, type='unknown'):
        component = Component(component, type=type, cmpt_rank=self.rank_counter)
        self.components.append(component)
        self.rank_counter += 1

    def to_records(self):
        return [Component.to_dict() for Component in self.components]
    