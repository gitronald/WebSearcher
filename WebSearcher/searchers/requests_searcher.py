import logging
import time

import brotli
import requests

from .. import utils
from ..models.configs import RequestsConfig
from ..models.data import ResponseOutput
from ..models.searches import SearchParams


class RequestsSearcher:
    """Handle Requests-based web interactions for search engines"""

    def __init__(self, config: RequestsConfig, logger: logging.Logger):
        """Initialize a Requests searcher with the given configuration

        Args:
            config: RequestsConfig instance (headers, optional session and SSH tunnel)
            logger: Logger instance
        """
        self.config = config
        self.log = logger
        # Reuse a caller-supplied session; otherwise build one from the headers.
        self.sesh = self.config.sesh or self._start_session()

    def _start_session(self):
        """Start a new requests session with the configured headers"""
        session = requests.Session()
        session.headers.update(self.config.headers)
        return session

    def cleanup(self) -> bool:
        """Close the requests session (uniform interface with the browser backend)."""
        try:
            if self.sesh is not None:
                self.sesh.close()
            return True
        except Exception as e:
            self.log.debug(f"Failed to close session: {e}", extra={"event": "cleanup"})
            return False

    def send_request(self, search_params: SearchParams) -> ResponseOutput:
        """Send a request and handle the response

        Args:
            search_params: SearchParams instance

        Returns:
            ResponseOutput with response data
        """

        # Per-search headers ride on this request only (requests merges them over
        # the session headers); updating the shared Session would leak them into
        # every later search.
        headers = dict(search_params.headers) if search_params.headers else None
        user_agent = (headers or {}).get("User-Agent") or self.sesh.headers.get("User-Agent", "")
        response_output = ResponseOutput(
            url=search_params.url,
            user_agent=str(user_agent),
            timestamp=utils.utc_timestamp(),
        )

        try:
            response = self.sesh.get(search_params.url, headers=headers, timeout=10)
            # Final URL after redirects -- a /sorry/ target marks a CAPTCHA block
            response_output.url = response.url
            response_output.html = self._handle_response_content(response)
            response_output.response_code = response.status_code
        except requests.exceptions.ConnectionError:
            self.log.exception("Requests | Connection error", extra={"event": "fetch"})
            self._reset_ssh_tunnel()
        except requests.exceptions.Timeout:
            self.log.exception("Requests | Timeout error", extra={"event": "fetch"})
        except Exception:
            self.log.exception("Requests | Unknown error", extra={"event": "fetch"})

        return response_output

    def _handle_response_content(self, response: requests.Response) -> str:
        try:
            if self.config.unzip:
                html = self._unzip_html(response.content)
            else:
                html = response.content
            return html.decode("utf-8", "ignore")
        except Exception:
            self.log.exception("", extra={"event": "response"})
            return response.text

    def _unzip_html(self, content: bytes) -> bytes:
        """Unzip brotli zipped html"""
        try:
            return brotli.decompress(content)
        except brotli.error:
            return content
        except Exception:
            self.log.exception("", extra={"event": "unzip"})
            return content

    def _reset_ssh_tunnel(self):
        """Reset the SSH tunnel if configured"""
        ssh_tunnel = self.config.ssh_tunnel
        if ssh_tunnel and ssh_tunnel.tunnel:
            ssh_tunnel.tunnel.kill()
            ssh_tunnel.open_tunnel()
            self.log.info("Restarted SSH tunnel", extra={"event": "ssh_tunnel"})
            time.sleep(10)  # Allow time to establish connection
