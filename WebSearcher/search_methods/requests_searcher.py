import time
import brotli
import requests
from typing import Dict, Any

from ..models.configs import RequestsConfig
from ..models.searches import SearchParams

class RequestsSearcher:
    """Handle Requests-based web interactions for search engines"""
    
    def __init__(self, config: RequestsConfig, logger):
        """Initialize a Requests searcher with the given configuration
        
        Args:
            config: RequestsConfig instance
            headers: Dictionary of HTTP headers
            logger: Logger instance
        """
        self.config = config
        self.log = logger
        self.sesh = self.config.sesh or self._start_session()
        
    def _start_session(self):
        """Start a new requests session with the configured headers"""
        session = requests.Session()
        session.headers.update(self.config.headers)
        return session
        
    def send_request(self, search_params: SearchParams) -> Dict[str, Any]:
        """Send a request and handle the response
        
        Args:
            search_params: SearchParams instance
            serp_id: Optional SERP ID
            crawl_id: Optional crawl ID
            
        Returns:
            Dictionary with response data
        """
        
        response_output = {
            'html': '',
            'url': search_params.url,
            'user_agent': self.config.headers.get('User-Agent'),
            'response_code': 0,
        }
        
        try:
            response = self.sesh.get(search_params.url, timeout=10)
            response_output['html'] = self._handle_response_content(response)
            response_output['response_code'] = response.status_code
        except requests.exceptions.ConnectionError:
            self.log.exception(f'Requests | Connection error')
            self._reset_ssh_tunnel()
        except requests.exceptions.Timeout:
            self.log.exception(f'Requests | Timeout error')
        except Exception:
            self.log.exception(f'Requests | Unknown error')
        finally:
            return response_output

    def _handle_response_content(self, response):
        try:
            if self.config.unzip:  
                html = self._unzip_html(response.content)
            else:
                html = response.content
            return html.decode('utf-8', 'ignore')
        except Exception:
            self.log.exception(f'Response handling error')
            return response.content

    def _unzip_html(self, content) -> bytes:
        """Unzip brotli zipped html"""
        try:
            return brotli.decompress(content)
        except brotli.error:
            return content
        except Exception:
            self.log.exception(f'unzip error')
            return content

    def _reset_ssh_tunnel(self):
        """Reset the SSH tunnel if configured"""
        if self.config.ssh_tunnel:
            self.config.ssh_tunnel.tunnel.kill()
            self.config.ssh_tunnel.open_tunnel()
            self.log.info(f'SERP | Restarted SSH tunnel')
            time.sleep(10)  # Allow time to establish connection
