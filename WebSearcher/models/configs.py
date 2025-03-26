from pydantic import BaseModel, Field
from typing import Dict, Optional, Union
import subprocess
import requests
from enum import Enum

class BaseConfig(BaseModel):
    """Base class for all configuration classes"""
    
    @classmethod
    def create(cls, config=None):
        """Create a config instance from a dictionary or existing instance"""
        if isinstance(config, dict):
            return cls(**config)
        return config or cls()

class LogConfig(BaseConfig):
    log_fp: str = ''
    log_mode: str = 'a+'
    log_level: str = 'INFO'


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

class SearchConfig(BaseModel):
    method: Union[str, SearchMethod] = SearchMethod.SELENIUM
    base: LogConfig = Field(default_factory=LogConfig)
    selenium: SeleniumConfig = Field(default_factory=SeleniumConfig)
    requests: RequestsConfig = Field(default_factory=RequestsConfig)
