from importlib import metadata
from pathlib import Path

from . import logger, parsers, utils
from .models.configs import (
    LogConfig,
    PatchrightConfig,
    RequestsConfig,
    SearchConfig,
    SearchMethod,
    SeleniumConfig,
    ZendriverConfig,
)
from .models.data import BaseSERP, ParsedSERP
from .models.searches import SearchParams
from .search_methods.patchright_searcher import PatchrightSearcher, PlaywrightSearcher
from .search_methods.requests_searcher import RequestsSearcher
from .search_methods.selenium_searcher import SeleniumDriver
from .search_methods.zendriver_searcher import ZendriverSearcher

WS_VERSION = metadata.version("WebSearcher")


class SearchEngine:
    """Collect Search Engine Results Pages (SERPs)"""

    def __init__(
        self,
        method: str | SearchMethod = SearchMethod.SELENIUM,
        log_config: dict | LogConfig = {},
        selenium_config: dict | SeleniumConfig = {},
        requests_config: dict | RequestsConfig = {},
        zendriver_config: dict | ZendriverConfig = {},
        patchright_config: dict | PatchrightConfig = {},
        playwright_config: dict | PatchrightConfig = {},
        crawl_id: str = "",
    ) -> None:
        """Initialize the search engine

        Args:
            method: The method to use for searching: 'selenium', 'requests', or a
                PoC browser backend ('zendriver', 'patchright'; plan 039, requires
                the `spike` dep group). Defaults to SearchMethod.SELENIUM.
            log_config: Common search configuration. Defaults to {}.
            selenium_config: Selenium-specific configuration. Defaults to {}.
            requests_config: Requests-specific configuration. Defaults to {}.
            zendriver_config: Zendriver-specific configuration. Defaults to {}.
            patchright_config: Patchright-specific configuration. Defaults to {}.
            playwright_config: Plain-playwright configuration (same shape as patchright). Defaults to {}.
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
                "zendriver": ZendriverConfig.create(zendriver_config),
                "patchright": PatchrightConfig.create(patchright_config),
                "playwright": PatchrightConfig.create(playwright_config),
            }
        )
        self.log = logger.Logger(**self.config.log.model_dump()).start(__name__)
        self.session_data = {
            "method": self.config.method.value,
            "version": WS_VERSION,
            "crawl_id": crawl_id,
        }

        # Initialize searcher based on method
        self.searcher: (
            SeleniumDriver
            | RequestsSearcher
            | ZendriverSearcher
            | PatchrightSearcher
            | PlaywrightSearcher
        )
        if self.config.method == SearchMethod.SELENIUM:
            self.searcher = SeleniumDriver(config=self.config.selenium, logger=self.log)
            self.searcher.init_driver()
        elif self.config.method == SearchMethod.REQUESTS:
            self.searcher = RequestsSearcher(config=self.config.requests, logger=self.log)
        elif self.config.method == SearchMethod.ZENDRIVER:
            self.searcher = ZendriverSearcher(config=self.config.zendriver, logger=self.log)
            self.searcher.init_driver()
        elif self.config.method == SearchMethod.PATCHRIGHT:
            self.searcher = PatchrightSearcher(config=self.config.patchright, logger=self.log)
            self.searcher.init_driver()
        elif self.config.method == SearchMethod.PLAYWRIGHT:
            self.searcher = PlaywrightSearcher(config=self.config.playwright, logger=self.log)
            self.searcher.init_driver()

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
        # Reset first: a swallowed parse error must not leave the previous
        # query's parse (and its captcha feature) attributed to this one.
        self.parsed = ParsedSERP()
        try:
            parsed = parsers.parse_serp(self.serp["html"], url=self.serp["url"])
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

    def to_record(self) -> dict:
        """Build one merged per-SERP record: metadata (excludes HTML) + features + results.

        Each key appears once. Identity and metadata are taken from ``self.serp``;
        only ``features`` and ``results`` are taken from ``self.parsed`` -- so the
        identity fields ``ParsedSERP`` also carries (crawl_id/serp_id/version/method)
        are not duplicated into the record. This merges ``save_search`` and
        ``save_parsed`` into a single write of one logical record.
        """
        meta = {k: v for k, v in self.serp.items() if k != "html"}
        return {**meta, "features": self.parsed.features, "results": self.parsed.results}

    def save_record(self, append_to: str | Path = "", ws_version: str = ""):
        """Save the merged metadata+parsed record (one JSON line per SERP).

        Args:
            append_to: File path to append the record to.
            ws_version: Optional parser-version stamp. When set, it is written as a
                distinct ``ws_version`` field, so a later reparse version never
                clobbers the collection-time ``version`` already on the record.
        """
        if not append_to:
            self.log.warning("Must provide an append_to file path to save a record")
            return

        record = self.to_record()
        if ws_version:
            record["ws_version"] = ws_version
        utils.write_lines([record], append_to)

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
