from pydantic import BaseModel, Field
from typing import Any, Optional, List, Dict


class BaseResult(BaseModel):
    """
    Represents a single search result item extracted from a SERP.
    
    Contains the structured data of one search result including its rank,
    type, title, URL, and other metadata.
    """
    sub_rank: int = Field(0, description="Position within a results component")
    type: str = Field('unclassified', description="Result type (general, ad, etc.)")
    sub_type: Optional[str] = Field(None, description="Result sub-type (e.g., header, item)")
    title: Optional[str] = Field(None, description="Title of the search result")
    url: Optional[str] = Field(None, description="URL of the search result")
    text: Optional[str] = Field(None, description="Snippet text from the search result") 
    cite: Optional[str] = Field(None, description="Citation or source information")
    details: Optional[Any] = Field(None, description="Additional structured details specific to result type")
    error: Optional[str] = Field(None, description="Error message if result parsing failed")


class BaseSERP(BaseModel):
    """
    Represents a complete Search Engine Results Page (SERP).
    
    Contains all data related to a single search query including the query itself,
    raw HTML response, metadata about the request, and identifiers for tracking.
    """
    qry: str = Field(..., description="Search query")
    loc: Optional[str] = Field(None, description="Location if set, in Canonical Name format")
    lang: Optional[str] = Field(None, description="Language code if set")
    url: str = Field(..., description="URL of the SERP")
    html: str = Field(..., description="Raw HTML of the SERP")
    timestamp: str = Field(..., description="ISO format timestamp of the crawl")
    response_code: int = Field(..., description="HTTP response code")
    user_agent: str = Field(..., description="User agent used for the request")
    serp_id: str = Field(..., description="Unique identifier for this SERP")
    crawl_id: str = Field(..., description="Identifier for grouping related SERPs")
    version: str = Field(..., description="WebSearcher version used")
    method: str = Field(..., description="Search method used (selenium/requests)")
