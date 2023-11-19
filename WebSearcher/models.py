from pydantic import BaseModel
from typing import Any, Optional

class BaseResult(BaseModel):
    type: str = 'unclassified'
    sub_type: Optional[str] = None
    sub_rank: int = 0
    title: Optional[str] = None
    url: Optional[str] = None
    text: Optional[str] = None
    cite: Optional[str] = None
    details: Optional[Any] = None

