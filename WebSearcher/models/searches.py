from pydantic import Field, computed_field
from typing import Dict, Optional, Any, List
from datetime import datetime, timezone

from ..utils import hash_id
from ..import webutils as wu
from ..import locations
from .configs import BaseConfig


class SearchParams(BaseConfig):
    """Contains parameters for a search request and utility methods for URL generation"""
    qry: str = Field('', description="The search query text")
    num_results: Optional[int] = Field(None, description="Number of results to return")
    lang: Optional[str] = Field(None, description="Language code (e.g., 'en')")
    loc: Optional[str] = Field(None, description="Location in Canonical Name format")
    base_url: str = Field("https://www.google.com/search", description="Base search engine URL")
    
    @computed_field
    def url_params(self) -> Dict[str, Any]:
        """Generates a dictionary of URL parameters based on the search parameters"""
        params = {'q': wu.encode_param_value(self.qry)}
        opt_params = {
            'num': self.num_results,
            'hl': self.lang,
            'uule': locations.convert_canonical_name_to_uule(self.loc) if self.loc else None,
        }
        opt_params = {k: v for k, v in opt_params.items() if v and v not in {'None', 'nan'}}
        params.update(opt_params)
        return params
    
    @computed_field
    def url(self) -> str:
        """Returns the fully formed search URL with all parameters"""
        return f"{self.base_url}?{wu.join_url_quote(self.url_params)}"
    
    @computed_field
    def serp_id(self) -> str:
        """Computes a unique SERP ID based on query, location, and timestamp"""
        timestamp = datetime.now().isoformat()
        return hash_id(f"{self.qry}{self.loc}{timestamp}")
    
    def to_dict_output(self) -> Dict[str, Any]:
        """Outputs the variables needed for SERPDetails as a dictionary"""
        timestamp = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        return {
            "qry": self.qry,
            "loc": self.loc,
            "lang": self.lang,
            "url": self.url,
            "serp_id": hash_id(f"{self.qry}{self.loc}{timestamp}"),
            "timestamp": timestamp,
        }


class SERPDetails(BaseConfig):
    """
    Contains details about a Search Engine Results Page (SERP).
    
    This class stores all the information related to a SERP, including
    search parameters, response data, parsed results and features.
    """
    version: str = Field(None, description="WebSearcher version")
    method: str = Field(None, description="Search method used (requests or selenium)")
    crawl_id: Optional[str] = Field(None, description="ID for the crawl session")
    serp_id: Optional[str] = Field(None, description="Unique ID for this SERP")
    qry: Optional[str] = Field(None, description="Search query")
    loc: Optional[str] = Field(None, description="Location used for search")
    lang: Optional[str] = Field(None, description="Language used for search")
    url: Optional[str] = Field(None, description="Full search URL")
    response_code: Optional[int] = Field(None, description="HTTP response code")
    user_agent: Optional[str] = Field(None, description="User agent used for request")
    timestamp: Optional[str] = Field(None, description="ISO timestamp of search")
    html: Optional[str] = Field(None, description="Raw HTML response")
    results: List[Dict[str, Any]] = Field(default_factory=list, description="Parsed search results")
    features: Dict[str, Any] = Field(default_factory=dict, description="Extracted SERP features")
