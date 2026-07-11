import re

from selectolax.lexbor import LexborNode as Node

from .. import utils
from .._slx import get_text
from ..models.features import SERPFeatures

# The raw-HTML path searches the original markup. The soup path scopes each probe
# to the smallest relevant element so the whole document is never re-serialized
# (str(soup) was the single largest removable cost per parse -- see plan 023).
RX_RESULT_STATS = re.compile(r'<div id="result-stats">.*?</div>')
# Fallback: on some SERPs the `#result-stats` div is injected client-side and is
# absent from the static markup, so the primary regex/CSS lookup finds nothing.
# The estimate is still present, HTML-escaped inside an inline `<script>` (e.g.
# `result-stats\">About 0 results\x3cnobr> (0.19s)&nbsp;\x3c/nobr>`). Grab a short
# window after the escaped `result-stats"`>` so RX_RESULT_COUNT / RX_RESULT_TIME
# recover count and time exactly as they would from the rendered div. The `\` and
# `"` are optional to tolerate un-escaped and layout variants.
RX_RESULT_STATS_SCRIPT = re.compile(r'result-stats\\?"?>.{0,80}')
RX_RESULT_COUNT = re.compile(r"([0-9,]+) results")
RX_RESULT_TIME = re.compile(r"\(([0-9.]+)s?\s*(?:seconds)?\)")
RX_LANGUAGE = re.compile(r'<html[^>]*\slang="([^"]+)"')

# The no-results and query-truncation notices are parsed into `notice` components
# (see parsers/components/notices.py), not features. server_error stays a flag: it
# is bare error-page chrome, not a component.
NOTICE_SERVER_ERROR = (
    "We're sorry but it appears that there has been an internal server error "
    "while processing your request."
)
INFINITY_SCROLL_SPAN = '<span class="RVQdVd">More results</span>'


class FeatureExtractor:
    @staticmethod
    def extract_features(
        html_or_soup: str | bytes | Node,
        soup: Node | None = None,
        url: str | None = None,
    ) -> SERPFeatures:
        """Extract SERP features. ``parse_serp`` passes both the raw HTML and
        the already-parsed soup so the regex path skips a re-parse and the
        shared structural probes (lb, captcha) reuse the soup. ``url`` is the
        response's final URL when known -- a ``/sorry/`` redirect marks a
        CAPTCHA even when the captured HTML is empty."""
        if isinstance(html_or_soup, Node):
            raw_html: str | None = None
            soup = html_or_soup
            features = FeatureExtractor._extract_from_soup(soup)
        else:
            raw_html = (
                html_or_soup
                if isinstance(html_or_soup, str)
                else html_or_soup.decode("utf-8", errors="replace")
            )
            if soup is None:
                soup = utils.make_soup(raw_html)
            features = FeatureExtractor._extract_from_html(raw_html)

        # Structural probes shared by both paths (cheap, scoped lookups).
        lb = soup.css_first('div[id="lb"]')
        features["overlay_precise_location"] = bool(
            lb is not None and "precise location" in (get_text(lb) or "").lower()
        )
        features["captcha"] = utils.has_captcha(soup, html=raw_html) or utils.is_sorry_redirect(url)
        return SERPFeatures(**features)

    @staticmethod
    def _find_result_stats_html(raw_html: str) -> str | None:
        """Locate the result-stats markup in the raw SERP HTML: the rendered
        `#result-stats` div when present, else -- as a fallback -- its escaped
        copy inside an inline `<script>` (see RX_RESULT_STATS_SCRIPT)."""
        stats_match = RX_RESULT_STATS.search(raw_html)
        if stats_match:
            return stats_match.group(0)
        script_match = RX_RESULT_STATS_SCRIPT.search(raw_html)
        return script_match.group(0) if script_match else None

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
        """Regex over the original markup -- no re-serialization cost."""
        stats_html = FeatureExtractor._find_result_stats_html(html)
        lang_match = RX_LANGUAGE.search(html)
        return {
            **FeatureExtractor._parse_result_estimate(stats_html),
            "language": lang_match.group(1) if lang_match else None,
            "server_error": NOTICE_SERVER_ERROR in html,
            "infinity_scroll": INFINITY_SCROLL_SPAN in html,
        }

    @staticmethod
    def _extract_from_soup(soup: Node) -> dict:
        """Structural lookups -- avoids serializing the whole document."""
        stats_div = soup.css_first('div[id="result-stats"]')
        if stats_div is not None:
            stats_match = RX_RESULT_STATS.search(stats_div.html or "")
            stats_html = stats_match.group(0) if stats_match else None
        else:
            # Fallback: the div is injected client-side, so scan the inline
            # <script> bodies for its escaped copy (see _find_result_stats_html).
            stats_html = None
            for script in soup.css("script"):
                script_match = RX_RESULT_STATS_SCRIPT.search(script.html or "")
                if script_match:
                    stats_html = script_match.group(0)
                    break

        # language: read the <html lang=...> attribute directly. The root passed
        # in is already <html>; for non-root inputs, descend to <html>.
        html_tag = soup if soup.tag == "html" else soup.css_first("html")
        language = html_tag.attributes.get("lang") if html_tag is not None else None

        # Text notices: one get_text() pass replaces three full-document scans.
        page_text = get_text(soup) or ""

        # infinity_scroll: serialize only candidate spans for exact-substring match.
        infinity_scroll = any(
            INFINITY_SCROLL_SPAN in (span.html or "") for span in soup.css("span.RVQdVd")
        )

        return {
            **FeatureExtractor._parse_result_estimate(stats_html),
            "language": language,
            "server_error": NOTICE_SERVER_ERROR in page_text,
            "infinity_scroll": infinity_scroll,
        }
