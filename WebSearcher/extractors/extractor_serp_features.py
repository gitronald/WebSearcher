import re

from .. import utils
from .._slx import SoupNode
from ..models.features import SERPFeatures

# The raw-HTML path searches the original markup. The soup path scopes each probe
# to the smallest relevant element so the whole document is never re-serialized
# (str(soup) was the single largest removable cost per parse -- see plan 023).
RX_RESULT_STATS = re.compile(r'<div id="result-stats">.*?</div>')
RX_RESULT_COUNT = re.compile(r"([0-9,]+) results")
RX_RESULT_TIME = re.compile(r"\(([0-9.]+)s?\s*(?:seconds)?\)")
RX_LANGUAGE = re.compile(r'<html[^>]*\slang="([^"]+)"')
RX_NO_RESULTS = re.compile(r"Your search - .*? - did not match any documents\.")

NOTICE_SHORTENED_QUERY = (
    "(and any subsequent words) was ignored because we limit queries to 32 words."
)
NOTICE_SERVER_ERROR = (
    "We're sorry but it appears that there has been an internal server error "
    "while processing your request."
)
INFINITY_SCROLL_SPAN = '<span class="RVQdVd">More results</span>'


class FeatureExtractor:
    @staticmethod
    def extract_features(html_or_soup: str | SoupNode) -> SERPFeatures:
        """Extract SERP features from HTML or a BeautifulSoup object

        Args:
            html_or_soup: The HTML content or a BeautifulSoup object

        Returns:
            The extracted features
        """
        if isinstance(html_or_soup, SoupNode):
            soup = html_or_soup
            features = FeatureExtractor._extract_from_soup(soup)
        else:
            soup = utils.make_soup(html_or_soup)
            features = FeatureExtractor._extract_from_html(html_or_soup)

        # Structural probes shared by both paths (cheap, scoped lookups).
        lb = soup.find("div", {"id": "lb"})
        features["overlay_precise_location"] = bool(
            lb and "precise location" in lb.get_text().lower()
        )
        features["captcha"] = utils.has_captcha(soup)
        return SERPFeatures(**features)

    @staticmethod
    def _parse_result_estimate(stats_html: str | None) -> dict:
        """Parse count/time from the serialized result-stats div markup."""
        if not stats_html:
            return {"result_estimate_count": None, "result_estimate_time": None}
        count_match = RX_RESULT_COUNT.search(stats_html)
        time_match = RX_RESULT_TIME.search(stats_html)
        return {
            "result_estimate_count": (
                float(count_match.group(1).replace(",", "")) if count_match else None
            ),
            "result_estimate_time": float(time_match.group(1)) if time_match else None,
        }

    @staticmethod
    def _extract_from_html(html: str) -> dict:
        """Regex over the original markup -- no re-serialization cost (html is a string)."""
        stats_match = RX_RESULT_STATS.search(html)
        lang_match = RX_LANGUAGE.search(html)
        return {
            **FeatureExtractor._parse_result_estimate(
                stats_match.group(0) if stats_match else None
            ),
            "language": lang_match.group(1) if lang_match else None,
            "notice_no_results": bool(RX_NO_RESULTS.search(html)),
            "notice_shortened_query": NOTICE_SHORTENED_QUERY in html,
            "notice_server_error": NOTICE_SERVER_ERROR in html,
            "infinity_scroll": INFINITY_SCROLL_SPAN in html,
        }

    @staticmethod
    def _extract_from_soup(soup: SoupNode) -> dict:
        """Structural lookups -- avoids serializing the whole document.

        Each probe is scoped to the smallest element so its result matches the
        old regex-over-str(soup) behavior byte-for-byte (pinned by the snapshot suite).
        """
        # result-stats: apply the same regex to just the matched div's markup.
        stats_div = soup.find("div", {"id": "result-stats"})
        stats_match = RX_RESULT_STATS.search(str(stats_div)) if stats_div is not None else None

        # language: read the <html lang=...> attribute directly.
        html_tag = soup.find("html")
        language = html_tag.get("lang") if html_tag is not None else None

        # Text notices: one get_text() pass replaces three full-document scans.
        page_text = soup.get_text()

        # infinity_scroll: serialize only candidate spans to keep exact-substring semantics.
        infinity_scroll = any(
            INFINITY_SCROLL_SPAN in str(span) for span in soup.find_all("span", {"class": "RVQdVd"})
        )

        return {
            **FeatureExtractor._parse_result_estimate(
                stats_match.group(0) if stats_match else None
            ),
            "language": language,
            "notice_no_results": bool(RX_NO_RESULTS.search(page_text)),
            "notice_shortened_query": NOTICE_SHORTENED_QUERY in page_text,
            "notice_server_error": NOTICE_SERVER_ERROR in page_text,
            "infinity_scroll": infinity_scroll,
        }
