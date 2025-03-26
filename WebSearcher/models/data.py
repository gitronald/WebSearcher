from pydantic import BaseModel
from typing import Any, Optional

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
    lang: Optional[str] = None # Language if set
    url: str                   # URL of SERP   
    html: str                  # Raw HTML of SERP
    timestamp: str             # Timestamp of crawl
    response_code: int         # HTTP response code
    user_agent: str            # User agent used for the crawl
    serp_id: str               # Search Engine Results Page (SERP) ID
    crawl_id: str              # Crawl ID for grouping SERPs
    version: str               # WebSearcher version
    method: str                # Search method used
