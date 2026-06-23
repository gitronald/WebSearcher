"""Tests for the JSONL crawl-log sink and the text/console event fallback."""

import io
import json
import logging
from datetime import datetime

from WebSearcher.logger import JsonlFormatter, Logger, TextFormatter, formatters

# Keys always present on every emitted record.
ALWAYS_KEYS = {"timestamp", "pid", "level"}
# All keys the schema can carry; the rest appear only when non-null.
ALL_KEYS = ALWAYS_KEYS | {
    "event",
    "message",
    "response_code",
    "qry",
    "loc",
    "output",
    "source",
}


def make_record(
    msg: str = "", exc_info=None, name: str = "WebSearcher.test", **extra
) -> logging.LogRecord:
    """Build a LogRecord, attaching `extra` fields the way logging.x(extra=) does."""
    record = logging.LogRecord(
        name=name,
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


def emit(**kwargs) -> dict:
    return json.loads(JsonlFormatter().format(make_record(**kwargs)))


# Registration ----------------------------------------------------------------


def test_jsonl_registered_as_formatter():
    assert formatters["jsonl"] == {"()": JsonlFormatter}


def test_text_formatters_use_textformatter():
    for name in ("minimal", "medium", "detailed"):
        assert formatters[name]["()"] is TextFormatter


# Null fields are dropped -----------------------------------------------------


def test_payload_never_contains_null_values():
    # Whatever the record, no key is ever emitted with a null value.
    for record in (
        make_record(msg="x"),
        make_record(msg="", event="search"),
        make_record(name="x"),
    ):
        payload = json.loads(JsonlFormatter().format(record))
        assert all(v is not None for v in payload.values())
        assert set(payload) <= ALL_KEYS


def test_always_present_keys_and_nothing_null():
    # A bare ad-hoc line: the three always-on keys plus its message, nothing else.
    assert set(emit(msg="hello there")) == ALWAYS_KEYS | {"message"}


def test_search_event_carries_only_its_fields():
    # No message/output/source noise on a search line -- just event + search fields.
    payload = emit(msg="", event="search", response_code=200, qry="pizza", loc="x")
    assert set(payload) == ALWAYS_KEYS | {"event", "response_code", "qry", "loc"}
    assert payload["response_code"] == 200


def test_parse_log_drops_qry_loc_response_code():
    # The case the user called out: a parsed/non-search line never needs qry/loc.
    payload = emit(msg="serp_id : abc123", event="parse")
    assert "qry" not in payload
    assert "loc" not in payload
    assert "response_code" not in payload
    assert payload["event"] == "parse"
    assert payload["message"] == "serp_id : abc123"


def test_jsonl_omits_logger_name():
    # `name` is constant for WebSearcher's own logs, so the structured sink drops it.
    assert "name" not in emit(msg="x")


# event / message semantics ---------------------------------------------------


def test_structured_event_drops_empty_message():
    payload = emit(msg="", event="search", response_code=200)
    assert payload["event"] == "search"
    assert "message" not in payload
    assert payload["response_code"] == 200


def test_adhoc_log_keeps_message_and_drops_event():
    payload = emit(msg="No parsed results to save")
    assert payload["message"] == "No parsed results to save"
    assert "event" not in payload


def test_event_line_with_detail_keeps_both():
    payload = emit(msg="serp_id : abc123", event="parse")
    assert payload["event"] == "parse"
    assert payload["message"] == "serp_id : abc123"


# source: tracking foreign (third-party) log lines ----------------------------


def test_source_absent_for_websearcher_logs():
    for name in ("WebSearcher", "WebSearcher.searchers", "WebSearcher.parsers.x"):
        assert "source" not in emit(msg="x", name=name)


def test_source_names_foreign_loggers():
    # Third-party logs (urllib3/requests/asyncio) bubble up to the root handler;
    # `source` labels them so the WARNING noise stays trackable in the JSONL.
    for name in ("urllib3.connectionpool", "requests", "asyncio", "root"):
        assert emit(msg="boom", name=name)["source"] == name


def test_foreign_logs_tagged_event_external():
    # Foreign records carry event="external" regardless of any event extra.
    payload = emit(msg="boom", name="urllib3.connectionpool")
    assert payload["event"] == "external"
    assert payload["source"] == "urllib3.connectionpool"


# timestamp -------------------------------------------------------------------


def test_timestamp_is_iso8601_with_milliseconds():
    payload = emit(msg="x")
    parsed = datetime.fromisoformat(payload["timestamp"])
    assert parsed.tzinfo is not None
    assert payload["timestamp"].count(":") == 3  # HH:MM:SS plus the tz offset colon


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


def test_no_exc_info_drops_output():
    assert "output" not in emit(msg="x")


# Text/console fallback -------------------------------------------------------


def test_textformatter_falls_back_to_event_when_message_empty():
    assert TextFormatter("%(message)s").format(make_record(msg="", event="search")) == "search"


def test_textformatter_keeps_message_when_present():
    assert TextFormatter("%(message)s").format(make_record(msg="hello", event="search")) == "hello"


def test_textformatter_does_not_mutate_shared_record():
    # The console formatter must not corrupt the message a JSONL sink reads next
    # off the same record (both handlers see one shared record).
    record = make_record(msg="", event="search")
    TextFormatter("%(message)s").format(record)
    assert "message" not in json.loads(JsonlFormatter().format(record))


# End-to-end through dictConfig ----------------------------------------------


def test_logger_emits_structured_search_event(tmp_path):
    fp = tmp_path / "crawl.log"
    log = Logger(console=False, file_name=str(fp), file_format="jsonl").start("WebSearcher.test")
    log.info("", extra={"event": "search", "response_code": 200, "qry": "pizza", "loc": "Boston"})
    logging.shutdown()
    payload = json.loads(fp.read_text().splitlines()[0])
    assert payload["event"] == "search"
    assert "message" not in payload
    assert payload["qry"] == "pizza"


def test_search_event_round_trips_through_logger():
    logger = logging.getLogger("WebSearcher.roundtrip")
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
    assert "message" not in payload
    assert payload["response_code"] == 200
    assert payload["qry"] == "pizza"
    assert payload["loc"] == "Boston,MA,US"
