from importlib import metadata
from pathlib import Path

from . import logger, parsers, utils
from .models.configs import (
    LogConfig,
    RequestsConfig,
    SearchConfig,
    SearchMethod,
    SeleniumConfig,
)
from .models.data import BaseSERP, ParsedSERP
from .models.searches import SearchParams
from .search_methods.requests_searcher import RequestsSearcher
from .search_methods.selenium_searcher import SeleniumDriver

WS_VERSION = metadata.version("WebSearcher")


class SearchEngine:
    """Collect Search Engine Results Pages (SERPs)"""

    def __init__(
        self,
        method: str | SearchMethod = SearchMethod.SELENIUM,
        log_config: dict | LogConfig = {},
        selenium_config: dict | SeleniumConfig = {},
        requests_config: dict | RequestsConfig = {},
        crawl_id: str = "",
    ) -> None:
        """Initialize the search engine

        Args:
            method: The method to use for searching, either 'requests' or 'selenium'. Defaults to SearchMethod.SELENIUM.
            log_config: Common search configuration. Defaults to {}.
            selenium_config: Selenium-specific configuration. Defaults to {}.
            requests_config: Requests-specific configuration. Defaults to {}.
            crawl_id: A unique identifier for the crawl. Defaults to ''.
        """

        # Initialize config settings, log, and session data
        self.method = method.value if isinstance(method, SearchMethod) else method
        self.config = SearchConfig.create(
            {
                "method": SearchMethod.create(method),
                "log": LogConfig.create(log_config),
                "selenium": SeleniumConfig.create(selenium_config),
                "requests": RequestsConfig.create(requests_config),
            }
        )
        self.log = logger.Logger(**self.config.log.model_dump()).start(__name__)
        self.session_data = {
            "method": self.config.method.value,
            "version": WS_VERSION,
            "crawl_id": crawl_id,
        }

        # Initialize searcher based on method
        self.searcher: SeleniumDriver | RequestsSearcher
        if self.config.method == SearchMethod.SELENIUM:
            self.searcher = SeleniumDriver(config=self.config.selenium, logger=self.log)
            self.searcher.init_driver()
        elif self.config.method == SearchMethod.REQUESTS:
            self.searcher = RequestsSearcher(config=self.config.requests, logger=self.log)

        # Initialize search params and output
        self.search_params = SearchParams.create()
        self.parsed = ParsedSERP()

    def search(
        self,
        qry: str,
        location: str | None = None,
        lang: str | None = None,
        num_results: int | None = None,
        ai_expand: bool = False,
        headers: dict[str, str] = {},
    ):
        """Conduct a search and save HTML

        Args:
            qry: The search query
            location: A location's Canonical Name
            lang: A language code (e.g., 'en')
            num_results: The number of results to return
            ai_expand: Whether to use selenium to expand AI overviews
            headers: Custom headers to include in the request
        """

        self.log.debug("starting search config")
        self.search_params = SearchParams.create(
            {
                "qry": str(qry),
                "loc": str(location) if location is not None else "",
                "lang": str(lang) if lang is not None else "",
                "num_results": num_results,
                "ai_expand": ai_expand,
                "headers": headers,
            }
        )

        self.response_output = self.searcher.send_request(self.search_params)
        serp_output = self.search_params.to_serp_output()
        serp_output.update(self.session_data)
        serp_output.update(self.response_output.model_dump())
        self.serp = BaseSERP(**serp_output).model_dump()
        self.log.info(
            " | ".join([f"{self.serp[k]}" for k in {"response_code", "qry", "loc"} if self.serp[k]])
        )

    # ==========================================================================
    # Parsing

    def parse_serp(self):
        try:
            parsed = parsers.parse_serp(self.serp["html"])
            self.parsed = ParsedSERP(
                crawl_id=self.serp["crawl_id"],
                serp_id=self.serp["serp_id"],
                version=self.serp["version"],
                method=self.serp["method"],
                features=parsed["features"],
                results=parsed["results"],
            )
        except Exception:
            self.log.exception(f"Parsing error | serp_id : {self.serp['serp_id']}")

    def parse_results(self):
        """Backwards compatibility for parsing results"""
        self.parse_serp()
        self.results = self.parsed.results

    # ==========================================================================
    # Saving

    def save_serp(self, save_dir: str | Path = "", append_to: str | Path = ""):
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
            fp = Path(save_dir) / f"{self.serp['serp_id']}.html"
            with open(fp, "w") as outfile:
                outfile.write(self.serp["html"])

    def save_parsed(self, save_dir: str | Path = "", append_to: str | Path = ""):
        """Save parsed SERP to file"""
        if not save_dir and not append_to:
            self.log.warning("Must provide a save_dir or append_to file path to save parsed SERP")
            return
        if not self.parsed.results and not self.parsed.features:
            self.log.warning("No parsed SERP available to save")
            return

        fp = append_to if append_to else Path(save_dir) / "parsed.json"
        utils.write_lines([self.parsed.model_dump()], fp)

    def save_search(self, append_to: str | Path = ""):
        """Save SERP metadata (excludes HTML) to file"""
        if not append_to:
            self.log.warning("Must provide an append_to file path to save SERP metadata")
            return

        self.serp_metadata = {k: v for k, v in self.serp.items() if k != "html"}
        utils.write_lines([self.serp_metadata], append_to)

    def save_results(self, save_dir: str | Path = "", append_to: str | Path = ""):
        """Save parsed results

        Args:
            save_dir (str, optional): Save results as `save_dir/results/{serp_id}.json`
            append_to (bool, optional): Append results to this file path
        """
        if not save_dir and not append_to:
            self.log.warning("Must provide a save_dir or append_to file path to save results")
            return
        if not self.parsed.results:
            self.log.warning("No parsed results to save")
            return

        # Add metadata to results
        result_metadata = {k: self.serp[k] for k in ["crawl_id", "serp_id", "version"]}
        results_output = [{**result, **result_metadata} for result in self.parsed.results]
        fp = append_to if append_to else Path(save_dir) / "results.json"
        utils.write_lines(results_output, fp)
