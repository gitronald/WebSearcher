from pydantic import BaseModel, Field, model_validator

# Closed vocabulary of parse-error messages, recorded in a result's
# ``details["error"]``. An error row carries no content payload, so its
# ``details`` uses the generic ``type: "item"`` (see :class:`BaseResult`).
# ``ERR_EXCEPTION`` and ``ERR_UNKNOWN_SUBTYPE`` are prefixes -- the caller
# appends a dynamic suffix (a traceback / the offending value); the rest are
# emitted verbatim.
ERR_NOT_IMPLEMENTED = "not implemented"
ERR_NULL_TYPE = "null component type"
ERR_BAD_OUTPUT = "parser output not list or dict"
ERR_NO_SUBCOMPONENTS = "no subcomponents parsed"
ERR_EXCEPTION = "parsing exception"  # "parsing exception: <traceback>"
ERR_UNKNOWN_SUBTYPE = "unknown sub_type"  # "unknown sub_type: <value>"
ERR_NO_HOTELS = "no hotel items found"


def error_details(error: str) -> dict:
    """Build a metadata-only ``details`` dict for a parse failure.

    A generic ``type: "item"`` row (no content payload) carrying just the
    ``error`` message. See the two-tier schema note on :class:`BaseResult`.
    """
    return {"type": "item", "error": error}


class ResponseOutput(BaseModel):
    """Response data from a search request."""

    html: str = ""
    url: str = ""
    user_agent: str = ""
    response_code: int = 0
    timestamp: str = ""

    def __getitem__(self, key: str):
        return getattr(self, key)


class ParsedSERP(BaseModel):
    """Parsed output from a SERP."""

    crawl_id: str = ""
    serp_id: str = ""
    version: str = ""
    method: str = ""
    features: dict = Field(default_factory=dict)
    results: list[dict] = Field(default_factory=list)


class BaseResult(BaseModel):
    """
    Represents a single search result item extracted from a SERP.

    Contains the structured data of one search result including its rank,
    type, title, URL, and other metadata.

    Two-tier schema: the fields below are the lean *core* tier (the common
    "what / where / what-it-says" case). ``details`` is the *extras* bucket --
    the typed content payload plus reserved metadata keys (``error``,
    ``visible``, ``timestamp``) that matter for digging into specific
    components or debugging. ``details`` always carries a ``type``: a specific
    content label (``"hyperlinks"``, ``"ratings"``, ...) when there is a
    payload, or the generic ``"item"`` for a metadata-only row (e.g. a parse
    error, or a hidden item with no content). Metadata keys are recorded only
    when they carry information (``error`` when set, ``visible`` only when
    ``False``, ``timestamp`` only when present), so a clean row's ``details``
    stays ``None``.
    """

    sub_rank: int = Field(0, description="Position within a results component")
    type: str = Field("unclassified", description="Result type (general, ad, etc.)")
    sub_type: str | None = Field(None, description="Result sub-type (e.g., header, item)")
    title: str | None = Field(None, description="Title of the search result")
    url: str | None = Field(None, description="URL of the search result")
    text: str | None = Field(None, description="Snippet text from the search result")
    cite: str | None = Field(None, description="Citation or source information")
    details: dict | None = Field(
        None, description="Typed content payload plus reserved metadata keys; see class docstring"
    )

    @model_validator(mode="after")
    def _ensure_details_type(self):
        """A non-empty ``details`` always carries a ``type`` -- the generic
        ``"item"`` when a parser supplied content/metadata keys but no specific
        content label. Never fabricates a ``type``-only dict: an empty
        ``details`` is left untouched (the "unless that would be the only key"
        rule)."""
        d = self.details
        if isinstance(d, dict) and d and "type" not in d:
            self.details = {"type": "item", **d}
        return self


class BaseSERP(BaseModel):
    """
    Represents a complete Search Engine Results Page (SERP).

    Contains all data related to a single search query including the query itself,
    raw HTML response, metadata about the request, and identifiers for tracking.
    """

    qry: str = Field(..., description="Search query")
    loc: str | None = Field(None, description="Location if set, in Canonical Name format")
    lang: str | None = Field(None, description="Language code if set")
    url: str = Field(..., description="URL of the SERP")
    html: str = Field(..., description="Raw HTML of the SERP")
    timestamp: str = Field(..., description="ISO format timestamp of the crawl")
    response_code: int = Field(..., description="HTTP response code")
    user_agent: str = Field(..., description="User agent used for the request")
    serp_id: str = Field(..., description="Unique identifier for this SERP")
    crawl_id: str = Field(..., description="Identifier for grouping related SERPs")
    version: str = Field(..., description="WebSearcher version used")
    method: str = Field(..., description="Search method used (selenium/requests)")
