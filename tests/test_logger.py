"""Tests for the JSONL crawl-log sink (logger.JsonlFormatter)."""

import io
import json
import logging
from datetime import datetime

from WebSearcher.logger import JsonlFormatter, Logger, formatters

# The native crawl-log schema: one JSON object per line.
SCHEMA_KEYS = {
    "timestamp",
    "pid",
    "level",
    "name",
    "message",
    "response_code",
    "qry",
    "loc",
    "output",
}


def make_record(msg: str = "search", exc_info=None, **extra) -> logging.LogRecord:
    """Build a LogRecord, attaching `extra` fields the way logging.info(extra=) does."""
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
    # The Logger asserts the format is registered; "jsonl" must be a valid choice.
    assert "jsonl" in formatters
    assert formatters["jsonl"] == {"()": JsonlFormatter}


def test_logger_accepts_jsonl_file_format(tmp_path):
    fp = tmp_path / "crawl.log"
    log = Logger(console=False, file_name=str(fp), file_format="jsonl").start("ws.jsonl")
    log.info("search", extra={"response_code": 200, "qry": "pizza", "loc": "Boston"})
    logging.shutdown()
    line = fp.read_text().splitlines()[0]
    assert json.loads(line)["qry"] == "pizza"


# Formatter unit tests --------------------------------------------------------


def test_emits_valid_json_with_full_key_set():
    payload = json.loads(JsonlFormatter().format(make_record()))
    assert set(payload) == SCHEMA_KEYS


def test_keys_match_target_schema_exactly():
    # Parity: no missing and no extra keys versus the documented schema.
    payload = json.loads(JsonlFormatter().format(make_record()))
    assert sorted(payload) == sorted(SCHEMA_KEYS)


def test_timestamp_is_iso8601_with_milliseconds():
    payload = json.loads(JsonlFormatter().format(make_record()))
    # Parses as ISO-8601 and carries millisecond precision + tz offset.
    parsed = datetime.fromisoformat(payload["timestamp"])
    assert parsed.tzinfo is not None
    assert payload["timestamp"].count(":") == 3  # HH:MM:SS plus the tz offset colon


def test_non_search_record_has_null_structured_fields():
    payload = json.loads(JsonlFormatter().format(make_record(msg="some message")))
    assert payload["message"] == "some message"
    assert payload["response_code"] is None
    assert payload["qry"] is None
    assert payload["loc"] is None
    assert payload["output"] == ""


def test_exc_info_flows_into_output():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = make_record(msg="Parsing error", exc_info=sys.exc_info())
    payload = json.loads(JsonlFormatter().format(record))
    assert "Traceback" in payload["output"]
    assert "ValueError: boom" in payload["output"]


def test_no_exc_info_yields_empty_output():
    payload = json.loads(JsonlFormatter().format(make_record()))
    assert payload["output"] == ""


# Emission round-trip ---------------------------------------------------------


def test_search_extra_round_trips_through_logger():
    # Mirrors searchers.py: a deterministic summary message + structured extra=
    # fields that must round-trip to response_code/qry/loc in the JSONL output.
    logger = logging.getLogger("ws.jsonl.roundtrip")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonlFormatter())
    logger.addHandler(handler)

    fields = {"response_code": 200, "qry": "pizza", "loc": "Boston,Massachusetts,United States"}
    logger.info(" | ".join(f"{v}" for v in fields.values() if v), extra=fields)

    payload = json.loads(stream.getvalue().splitlines()[0])
    assert payload["message"] == "200 | pizza | Boston,Massachusetts,United States"
    assert payload["response_code"] == 200
    assert payload["qry"] == "pizza"
    assert payload["loc"] == "Boston,Massachusetts,United States"
