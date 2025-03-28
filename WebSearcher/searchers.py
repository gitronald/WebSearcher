from . import parsers
from . import utils
from . import logger
from .search_methods.selenium_searcher import SeleniumDriver
from .search_methods.requests_searcher import RequestsSearcher
from .models.configs import LogConfig, SeleniumConfig, RequestsConfig, SearchConfig, SearchMethod
from .models.searches import SearchParams
from .models.data import BaseSERP

import os
import pandas as pd
from typing import Dict, Union

from importlib import metadata
WS_VERSION = metadata.version('WebSearcher')

class SearchEngine:
    """Collect Search Engine Results Pages (SERPs)"""
    def __init__(self, 
            method: Union[str, SearchMethod] = SearchMethod.SELENIUM,
            log_config: Union[dict, LogConfig] = {},
            selenium_config: Union[dict, SeleniumConfig] = {},
            requests_config: Union[dict, RequestsConfig] = {},
            crawl_id: str = '',
        ) -> None:
        """Initialize the search engine

        Args: 
            method (Union[str, SearchMethod], optional): The method to use for searching, either 'requests' or 'selenium'. Defaults to SearchMethod.SELENIUM.
            log_config (Union[dict, LogConfig], optional): Common search configuration. Defaults to None.
            selenium_config (Union[dict, SeleniumConfig], optional): Selenium-specific configuration. Defaults to None.
            requests_config (Union[dict, RequestsConfig], optional): Requests-specific configuration. Defaults to None.
        """

        # Initialize configuration
        self.method = method.value if isinstance(method, SearchMethod) else method
        self.config = SearchConfig.create({
            "method": SearchMethod.create(method),
            "log": LogConfig.create(log_config),
            "selenium": SeleniumConfig.create(selenium_config),
            "requests": RequestsConfig.create(requests_config),
        })
        self.session_data = {
            "method": self.config.method.value,
            "version": WS_VERSION,
            "crawl_id": crawl_id,
        }
        
        # Set a log file, prints to console by default
        self.log = logger.Logger(
            console=True if not self.config.log.fp else False,
            console_level=self.config.log.level,
            file_name=self.config.log.fp, 
            file_mode=self.config.log.mode,
            file_level=self.config.log.level,
        ).start(__name__)

        # Initialize search params and output
        self.search_params = SearchParams.create()
        self.parsed = {'results': [], 'features': {}}


    def search(self, 
            qry: str, 
            location: str = None, 
            lang: str = None, 
            num_results: int = None, 
            ai_expand: bool = False,
            headers: Dict[str, str] = {},
        ):
        """Conduct a search and save HTML
        
        Args:
            qry (str): The search query
            location (str, optional): A location's Canonical Name
            num_results (int, optional): The number of results to return
            ai_expand: (bool, optional): Whether to use selenium to expand AI overviews
            crawl_id (str, optional): An identifier for this crawl
        """

        self.search_params = SearchParams.create({
            'qry': str(qry),
            'loc': str(location) if not pd.isnull(location) else '',
            'lang': str(lang) if not pd.isnull(lang) else '',
            'num_results': num_results,
        })

        if self.config.method == SearchMethod.SELENIUM:
            self.selenium_driver = SeleniumDriver(config=self.config.selenium, logger=self.log)
            self.selenium_driver.init_driver()
            self.response_output = self.selenium_driver.send_request(self.search_params, ai_expand=ai_expand)
        
        elif self.config.method == SearchMethod.REQUESTS:
            self.config.requests.update_headers(headers)
            self.requests_searcher = RequestsSearcher(config=self.config.requests, logger=self.log)
            self.response_output = self.requests_searcher.send_request(self.search_params)

        serp_output = self.search_params.to_serp_output()
        serp_output.update(self.session_data)
        serp_output.update(self.response_output)
        self.serp = BaseSERP(**serp_output).model_dump()
        self.log.info(" | ".join([f"{self.serp[k]}" for k in {'response_code','qry','loc'} if self.serp[k]]))

    # ==========================================================================
    # Parsing

    def parse_serp(self, extract_features: bool = True):
        try:
            parsed_metadata = {k:v for k,v in self.serp.items() if k in ['crawl_id', 'serp_id', 'version', 'method']}
            parsed = parsers.parse_serp(self.serp['html'], extract_features=extract_features)
            self.parsed = parsed_metadata | parsed
        except Exception:
            self.log.exception(f'Parsing error | serp_id : {self.serp["serp_id"]}')

    def parse_results(self):
        """Backwards compatibility for parsing results"""
        self.parse_serp()
        self.results = self.parsed['results']

    # ==========================================================================
    # Saving

    def save_serp(self, save_dir: str = "", append_to: str = ""):
        """Save SERP to file

        Args:
            save_dir (str, optional): Save results as `save_dir/{serp_id}.html`
            append_to (str, optional): Append results to this file path
        """
        if not save_dir and not append_to:
            self.log.warning("Must provide a save_dir or append_to file path to save a SERP")
            return
        elif append_to:
            utils.write_lines([self.serp], append_to)
        elif save_dir:
            fp = os.path.join(save_dir, f'{self.serp["serp_id"]}.html')
            with open(fp, 'w') as outfile:
                outfile.write(self.serp['html'])

    def save_parsed(self, save_dir: str = "", append_to: str = ""):
        """Save parsed SERP to file"""
        if not save_dir and not append_to:
            self.log.warning("Must provide a save_dir or append_to file path to save parsed SERP")
            return
        if not self.parsed:
            self.log.warning("No parsed SERP available to save")
            return
        
        fp = append_to if append_to else os.path.join(save_dir, 'parsed.json')
        utils.write_lines([self.parsed], fp)

    def save_search(self, append_to: str = ""):
        """Save SERP metadata (excludes HTML) to file"""
        if not append_to:
            self.log.warning("Must provide an append_to file path to save SERP metadata")
            return
        
        self.serp_metadata = {k: v for k, v in self.serp.items() if k != 'html'}
        utils.write_lines([self.serp_metadata], append_to)

    def save_results(self, save_dir: str = "", append_to: str = ""):
        """Save parsed results
        
        Args:
            save_dir (str, optional): Save results as `save_dir/results/{serp_id}.json`
            append_to (bool, optional): Append results to this file path
        """
        if not save_dir and not append_to:
            self.log.warning("Must provide a save_dir or append_to file path to save results")
            return
        if not self.parsed["results"]:
            self.log.warning(f'No parsed results to save')
            return

        # Add metadata to results
        result_metadata = {k: self.serp[k] for k in ['crawl_id', 'serp_id', 'version']}
        results_output = [{**result, **result_metadata} for result in self.parsed["results"]]
        fp = append_to if append_to else os.path.join(save_dir, 'results.json')        
        utils.write_lines(results_output, fp)
