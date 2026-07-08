from pydantic import BaseModel


class SERPFeatures(BaseModel):
    """Features extracted from a Search Engine Results Page (SERP)."""

    result_estimate_count: float | None = None
    result_estimate_time: float | None = None
    language: str | None = None
    # no-results and query-truncation notices are emitted as `notice` components
    # (sub_types `no_results` / `query_truncated`), not flags. server_error stays
    # a page-state flag -- it is bare error chrome, not a result component.
    server_error: bool = False
    infinity_scroll: bool = False
    overlay_precise_location: bool = False
    captcha: bool = False
    # Main-section layout label assigned during extraction, e.g. "standard",
    # "standard-overview". None when no layout was detected.
    main_layout: str | None = None
