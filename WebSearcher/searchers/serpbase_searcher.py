"""SerpBase REST API searcher backend.

A no-browser, no-scraping alternative to the ``requests`` method: results are
fetched from the SerpBase Google Search Results API as JSON and rendered into a
minimal Google-style SERP document, so the existing parser pipeline
(``#rso`` > ``div.g`` > ``yuRUbf``/``VwiC3b``) produces the usual ``general``
results with the standard schema.

Graceful degradation: when no API key is configured the searcher logs a warning
and returns an empty ``ResponseOutput`` (``response_code`` 0) instead of
raising, so a crawl run without ``SERPBASE_API_KEY`` leaves the other backends
unaffected.
"""

import html
import os
from datetime import UTC, datetime

import requests

from ..models.configs import SerpBaseConfig
from ..models.data import ResponseOutput
from ..models.searches import SearchParams


class SerpBaseSearcher:
    """Handle SerpBase REST API-based web interactions for search engines"""

    def __init__(self, config: SerpBaseConfig, logger):
        """Initialize a SerpBase searcher with the given configuration

        Args:
            config: SerpBaseConfig instance
            logger: Logger instance
        """
        self.config = config
        self.log = logger
        self.sesh = requests.Session()
        self.sesh.headers.update({"Accept": "application/json"})

    def cleanup(self) -> bool:
        """Close the requests session (uniform interface with the other backends)."""
        try:
            self.sesh.close()
            return True
        except Exception as e:
            self.log.debug(f"Failed to close session: {e}", extra={"event": "cleanup"})
            return False

    def send_request(self, search_params: SearchParams) -> ResponseOutput:
        """Send a request to the SerpBase API and return a parseable response.

        Args:
            search_params: SearchParams instance

        Returns:
            ResponseOutput with the SERP rendered as minimal Google-style HTML.
            When no API key is available, returns an empty ResponseOutput
            (response_code 0) so the caller's pipeline degrades gracefully.
        """
        api_key = self.config.api_key or os.environ.get("SERPBASE_API_KEY", "")
        ts = datetime.now(UTC).replace(tzinfo=None).isoformat()
        url = f"{self.config.base_url}/google/search"
        user_agent = "SerpBaseSearcher/1.0"

        if not api_key:
            self.log.warning(
                "SERPBASE_API_KEY not set - skipping SerpBase request. Get a key at https://serpbase.dev",
                extra={"event": "fetch"},
            )
            return ResponseOutput(url=url, user_agent=user_agent, timestamp=ts)

        params = {"q": search_params.qry, "api_key": api_key}
        if search_params.num_results:
            params["num"] = search_params.num_results
        if search_params.lang:
            params["hl"] = search_params.lang

        response_output = ResponseOutput(url=url, user_agent=user_agent, timestamp=ts)
        try:
            response = self.sesh.get(url, params=params, timeout=self.config.timeout)
            response_output.url = response.url
            response_output.response_code = response.status_code
            if response.status_code == 200:
                response_output.html = self._json_to_html(response.json())
            else:
                self.log.warning(
                    f"SerpBase API returned {response.status_code}",
                    extra={"event": "fetch"},
                )
        except requests.exceptions.RequestException:
            self.log.exception("SerpBase | Request error", extra={"event": "fetch"})
        except ValueError:
            self.log.exception("SerpBase | Invalid JSON response", extra={"event": "fetch"})

        return response_output

    @staticmethod
    def _json_to_html(payload: dict) -> str:
        """Render SerpBase JSON results as a minimal Google-style SERP document.

        The synthesized markup targets the classic result structure the parser
        already handles: ``div#rso`` > ``div.g`` > ``div.yuRUbf`` (``h3``/``a``)
        with a ``div.VwiC3b`` snippet and ``cite`` URL.
        """
        blocks = []
        for result in payload.get("organic_results", []):
            title = html.escape(str(result.get("title", "")))
            link = html.escape(str(result.get("link", "")))
            snippet = html.escape(str(result.get("snippet", "")))
            blocks.append(
                '<div class="g">'
                f'<div class="yuRUbf"><a href="{link}"><h3>{title}</h3></a></div>'
                f'<div class="VwiC3b">{snippet}</div>'
                f"<cite>{link}</cite>"
                "</div>"
            )
        body = "".join(blocks)
        return (
            "<!DOCTYPE html><html><head><title>SerpBase results</title></head>"
            f'<body><div id="rcnt"><div id="rso">{body}</div></div></body></html>'
        )
