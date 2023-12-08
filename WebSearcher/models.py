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
    qry: str
    loc: Optional[str] = None
    url: str
    html: str
    headers: Dict[str, str]
    timestamp: str
    response_code: int
    serp_id: str
    crawl_id: str