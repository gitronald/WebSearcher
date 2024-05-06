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
