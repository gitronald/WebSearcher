import requests
import subprocess
from enum import Enum
from typing import Dict, Optional, Union
from pydantic import BaseModel, Field, computed_field

class BaseConfig(BaseModel):
    """Base class for all configuration classes"""
    
    @classmethod
    def create(cls, config=None):
        """Create a config instance from a dictionary or existing instance"""
        if isinstance(config, dict):
            return cls(**config)
        return config or cls()

class LogConfig(BaseConfig):
    console: bool = True
    console_format: str = 'medium'
    console_level: str = 'INFO'
    file_name: str = ''
    file_mode: str = 'a'
    file_format: str = 'detailed'
    file_level: str = 'INFO'

class SeleniumConfig(BaseConfig):
    headless: bool = False
    version_main: int = 141
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
    ssh_tunnel: Optional[subprocess.Popen] = None
    unzip: bool = True

    @computed_field
    def sesh(self) -> requests.Session:
        """Create and configure a requests session with the current headers."""
        sesh = requests.Session()
        sesh.headers.update(self.headers)
        return sesh

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
