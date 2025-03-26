from pydantic import BaseModel, Field
from typing import Any, Optional, Dict, Union
import subprocess
import requests
from enum import Enum


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


class LogConfig(BaseModel):
    log_fp: str = ''
    log_mode: str = 'a+'
    log_level: str = 'INFO'


class SeleniumConfig(BaseModel):
    headless: bool = False
    version_main: int = 133
    use_subprocess: bool = False
    driver_executable_path: str = ""


class RequestsConfig(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    headers: Dict[str, str] = Field(default_factory=lambda: {
        'Host': 'www.google.com',
        'Referer': 'https://www.google.com/',
        'Accept': '*/*',
        'Accept-Encoding': 'gzip,deflate,br',
        'Accept-Language': 'en-US,en;q=0.5',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0',
    })
    sesh: Optional[requests.Session] = None
    ssh_tunnel: Optional[subprocess.Popen] = None
    unzip: bool = True


class SearchMethod(Enum):
    REQUESTS = "requests"
    SELENIUM = "selenium"

class SearchConfig(BaseModel):
    method: Union[str, SearchMethod] = SearchMethod.SELENIUM
    base: LogConfig = Field(default_factory=LogConfig)
    selenium: SeleniumConfig = Field(default_factory=SeleniumConfig)
    requests: RequestsConfig = Field(default_factory=RequestsConfig)
