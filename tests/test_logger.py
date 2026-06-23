"""Tests for the JSONL crawl-log sink and the text/console event fallback."""

import io
import json
import logging
from datetime import datetime

from WebSearcher.logger import JsonlFormatter, Logger, TextFormatter, formatters

# The native crawl-log schema: one JSON object per line.
SCHEMA_KEYS = {
    "timestamp",
    "pid",
    "level",
    "event",
    "message",
    "response_code",
    "qry",
    "loc",
    "output",
}


def make_record(msg: str = "", exc_info=None, **extra) -> logging.LogRecord:
    """Build a LogRecord, attaching `extra` fields the way logging.x(extra=) does."""
    record = logging.LogRecord(
        name="WebSearcher.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=exc_info,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


# Registration ----------------------------------------------------------------


def test_jsonl_registered_as_formatter():
    assert formatters["jsonl"] == {"()": JsonlFormatter}


def test_text_formatters_use_textformatter():
    for name in ("minimal", "medium", "detailed"):
        assert formatters[name]["()"] is TextFormatter


def test_logger_emits_structured_search_event(tmp_path):
    # End-to-end through dictConfig: a search event opts into the jsonl file sink.
    fp = tmp_path / "crawl.log"
    log = Logger(console=False, file_name=str(fp), file_format="jsonl").start("ws.jsonl")
    log.info("", extra={"event": "search", "response_code": 200, "qry": "pizza", "loc": "Boston"})
    logging.shutdown()
    payload = json.loads(fp.read_text().splitlines()[0])
    assert payload["event"] == "search"
    assert payload["message"] is None
    assert payload["qry"] == "pizza"


# Formatter schema ------------------------------------------------------------


def test_emits_valid_json_with_full_key_set():
    payload = json.loads(JsonlFormatter().format(make_record(msg="x")))
    assert set(payload) == SCHEMA_KEYS


def test_keys_match_target_schema_exactly():
    payload = json.loads(JsonlFormatter().format(make_record(msg="x")))
    assert sorted(payload) == sorted(SCHEMA_KEYS)


def test_jsonl_omits_logger_name():
    # `name` is constant for WebSearcher's own logs, so the structured sink drops
    # it (it stays in the human text formatters where __package__ de-duplicated it).
    assert "name" not in json.loads(JsonlFormatter().format(make_record(msg="x")))


def test_timestamp_is_iso8601_with_milliseconds():
    payload = json.loads(JsonlFormatter().format(make_record(msg="x")))
    parsed = datetime.fromisoformat(payload["timestamp"])
    assert parsed.tzinfo is not None
    assert payload["timestamp"].count(":") == 3  # HH:MM:SS plus the tz offset colon


# event / message semantics ---------------------------------------------------


def test_structured_event_has_event_and_null_message():
    # Data lives in fields; the message is empty -> null in JSONL.
    record = make_record(msg="", event="search", response_code=200, qry="pizza", loc="x")
    payload = json.loads(JsonlFormatter().format(record))
    assert payload["event"] == "search"
    assert payload["message"] is None
    assert payload["response_code"] == 200


def test_adhoc_log_keeps_message_with_null_event():
    # A non-event log line (e.g. a warning) carries its text and no event.
    payload = json.loads(JsonlFormatter().format(make_record(msg="No parsed results to save")))
    assert payload["event"] is None
    assert payload["message"] == "No parsed results to save"
    assert payload["response_code"] is None
    assert payload["qry"] is None
    assert payload["loc"] is None


def test_event_line_with_detail_keeps_both():
    # An event that also carries residual detail keeps both (e.g. parse + serp_id).
    payload = json.loads(
        JsonlFormatter().format(make_record(msg="serp_id : abc123", event="parse"))
    )
    assert payload["event"] == "parse"
    assert payload["message"] == "serp_id : abc123"


def test_empty_message_is_null():
    assert json.loads(JsonlFormatter().format(make_record(msg="")))["message"] is None


# Traceback -------------------------------------------------------------------


def test_exc_info_flows_into_output():
    import sys

    try:
        raise ValueError("boom")
    except ValueError:
        record = make_record(msg="", event="parse", exc_info=sys.exc_info())
    payload = json.loads(JsonlFormatter().format(record))
    assert payload["event"] == "parse"
    assert "Traceback" in payload["output"]
    assert "ValueError: boom" in payload["output"]


def test_no_exc_info_yields_empty_output():
    assert json.loads(JsonlFormatter().format(make_record(msg="x")))["output"] == ""


# Text/console fallback -------------------------------------------------------


def test_textformatter_falls_back_to_event_when_message_empty():
    out = TextFormatter("%(message)s").format(make_record(msg="", event="search"))
    assert out == "search"


def test_textformatter_keeps_message_when_present():
    out = TextFormatter("%(message)s").format(make_record(msg="hello", event="search"))
    assert out == "hello"


def test_textformatter_does_not_mutate_shared_record():
    # The console formatter must not corrupt the message a JSONL sink reads next
    # off the same record (both handlers see one shared record).
    record = make_record(msg="", event="search")
    TextFormatter("%(message)s").format(record)
    assert json.loads(JsonlFormatter().format(record))["message"] is None


# Emission round-trip ---------------------------------------------------------


def test_search_event_round_trips_through_logger():
    logger = logging.getLogger("ws.jsonl.roundtrip")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonlFormatter())
    logger.addHandler(handler)

    logger.info(
        "",
        extra={"event": "search", "response_code": 200, "qry": "pizza", "loc": "Boston,MA,US"},
    )

    payload = json.loads(stream.getvalue().splitlines()[0])
    assert payload["event"] == "search"
    assert payload["message"] is None
    assert payload["response_code"] == 200
    assert payload["qry"] == "pizza"
    assert payload["loc"] == "Boston,MA,US"
