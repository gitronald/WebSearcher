from pydantic import BaseModel, Field, computed_field
from typing import Dict, Optional, Union, Any
import subprocess
import requests
from enum import Enum

from .. import webutils as wu
from .. import locations


class BaseConfig(BaseModel):
    """Base class for all configuration classes"""
    
    @classmethod
    def create(cls, config=None):
        """Create a config instance from a dictionary or existing instance"""
        if isinstance(config, dict):
            return cls(**config)
        return config or cls()

class SearchParams(BaseConfig):
    """
    Contains parameters for a search request and utility methods for URL generation.
    
    This class stores search query parameters and provides methods to convert
    them into properly formatted URL parameters and complete search URLs.
    """
    qry: str = Field('', description="The search query text")
    num_results: Optional[int] = Field(None, description="Number of results to return")
    lang: Optional[str] = Field(None, description="Language code (e.g., 'en')")
    loc: Optional[str] = Field(None, description="Location in Canonical Name format")
    base_url: str = Field("https://www.google.com/search", description="Base search engine URL")
    
    """
    Generates a dictionary of URL parameters based on the search parameters.
    
    Converts the search parameters to a dictionary format suitable for URL encoding,
    removing any None values and handling special parameters like location.
    """
    @computed_field
    def url_params(self) -> Dict[str, Any]:
        params = {'q': wu.encode_param_value(self.qry)}
        opt_params = {
            'num': self.num_results,
            'hl': self.lang,
            'uule': locations.convert_canonical_name_to_uule(self.loc) if self.loc else None,
        }
        opt_params = {k: v for k, v in opt_params.items() if v and v not in {'None', 'nan'}}
        params.update(opt_params)
        return params
    
    """
    Returns the fully formed search URL with all parameters.
    
    Combines the base URL with the encoded parameters to create a complete,
    properly escaped search URL.
    """
    @computed_field
    def url(self) -> str:
        return f"{self.base_url}?{wu.join_url_quote(self.url_params)}"

class LogConfig(BaseConfig):
    fp: str = ''
    mode: str = 'a'
    level: str = 'INFO'


class SeleniumConfig(BaseConfig):
    headless: bool = False
    version_main: int = 133
    use_subprocess: bool = False
    driver_executable_path: str = ""


class RequestsConfig(BaseConfig):
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

    @classmethod
    def create(cls, method=None):
        """Convert string to SearchMethod enum or return existing enum instance"""
        if method is None:
            return cls.SELENIUM
        if isinstance(method, cls):
            return method
        if isinstance(method, str):
            try:
                return cls(method.lower())
            except ValueError:
                valid_values = [e.value for e in cls]
                raise ValueError(f"Invalid search method: {method}. Valid values are: {valid_values}")
        raise TypeError(f"Expected string or SearchMethod, got {type(method)}")


class SearchConfig(BaseConfig):
    method: Union[str, SearchMethod] = SearchMethod.SELENIUM
    log: LogConfig = Field(default_factory=LogConfig)
    selenium: SeleniumConfig = Field(default_factory=SeleniumConfig)
    requests: RequestsConfig = Field(default_factory=RequestsConfig)
