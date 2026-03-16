from pydantic import BaseModel


class SERPFeatures(BaseModel):
    """Features extracted from a Search Engine Results Page (SERP)."""

    result_estimate_count: float | None = None
    result_estimate_time: float | None = None
    language: str | None = None
    notice_no_results: bool = False
    notice_shortened_query: bool = False
    notice_server_error: bool = False
    infinity_scroll: bool = False
    overlay_precise_location: bool = False
    captcha: bool = False
