"""Tests for protobuf encoding/UULE generation and the geotargets update flow"""

import csv
import io
import zipfile

import WebSearcher.locations as locations
from WebSearcher.locations import (
    append_ledger_row,
    convert_canonical_name_to_uule,
    decode_protobuf_string,
    encode_protobuf_string,
    read_ledger_last_filename,
    update_locations_file,
)


def test_encode_decode_roundtrip_integers():
    fields = {1: 2, 2: 32}
    encoded = encode_protobuf_string(fields)
    decoded = decode_protobuf_string(encoded)
    assert decoded == fields


def test_encode_decode_roundtrip_string():
    fields = {1: 2, 4: "Boston,Massachusetts,United States"}
    encoded = encode_protobuf_string(fields)
    decoded = decode_protobuf_string(encoded)
    assert decoded == fields


def test_encode_decode_roundtrip_mixed():
    fields = {1: 2, 2: 32, 4: "New York,New York,United States"}
    encoded = encode_protobuf_string(fields)
    decoded = decode_protobuf_string(encoded)
    assert decoded == fields


def test_encode_decode_unicode():
    fields = {1: 0, 4: "Zurich,Zurich,Switzerland"}
    encoded = encode_protobuf_string(fields)
    decoded = decode_protobuf_string(encoded)
    assert decoded == fields


def test_uule_starts_with_prefix():
    result = convert_canonical_name_to_uule("Boston,Massachusetts,United States")
    assert result.startswith("w+")


def test_uule_deterministic():
    name = "New York,New York,United States"
    assert convert_canonical_name_to_uule(name) == convert_canonical_name_to_uule(name)


def test_uule_different_locations_differ():
    a = convert_canonical_name_to_uule("Boston,Massachusetts,United States")
    b = convert_canonical_name_to_uule("New York,New York,United States")
    assert a != b


def test_uule_encodes_expected_fields():
    """UULE should encode fields {1: 2, 2: 32, 4: canon_name}"""
    name = "Austin,Texas,United States"
    uule = convert_canonical_name_to_uule(name)
    encoded = uule[2:]  # strip "w+" prefix
    decoded = decode_protobuf_string(encoded)
    assert decoded[1] == 2
    assert decoded[2] == 32
    assert decoded[4] == name


# ---------------------------------------------------------------------------
# update_locations_file / ledger


CSV_TEXT = (
    "Criteria ID,Name,Canonical Name,Parent ID,Country Code,Target Type,Status\r\n"
    '1000002,Kabul,"Kabul,Kabul,Afghanistan",9075393,AF,City,Active\r\n'
)


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        pass


def mock_upstream(monkeypatch, url_latest: str, content: bytes) -> list[str]:
    """Stub the listing-page scrape and the download; return the call log."""
    download_calls = []
    monkeypatch.setattr(locations, "get_latest_url", lambda url: url_latest)

    def fake_get(url):
        download_calls.append(url)
        return FakeResponse(content)

    monkeypatch.setattr(locations.requests, "get", fake_get)
    return download_calls


def test_update_first_run_writes_file_and_ledger(tmp_path, monkeypatch):
    mock_upstream(
        monkeypatch,
        "https://developers.google.com/geotargets-2026-02-25.csv",
        CSV_TEXT.encode("utf-8"),
    )
    fp = tmp_path / "geotargets.csv"
    ledger_fp = tmp_path / "ledger.csv"

    pulled = update_locations_file(fp=fp, ledger_fp=ledger_fp)

    assert pulled == "geotargets-2026-02-25.csv"
    assert fp.read_bytes() == CSV_TEXT.encode("utf-8")
    with open(ledger_fp, encoding="utf-8", newline="") as infile:
        rows = list(csv.DictReader(infile))
    assert len(rows) == 1
    assert rows[0]["filename"] == "geotargets-2026-02-25.csv"
    assert rows[0]["date_collected"]  # run date recorded, value not pinned


def test_update_skips_when_ledger_current(tmp_path, monkeypatch):
    download_calls = mock_upstream(
        monkeypatch,
        "https://developers.google.com/geotargets-2026-02-25.csv",
        CSV_TEXT.encode("utf-8"),
    )
    fp = tmp_path / "geotargets.csv"
    ledger_fp = tmp_path / "ledger.csv"
    append_ledger_row(ledger_fp, date_collected="2026-06-10", filename="geotargets-2026-02-25.csv")

    pulled = update_locations_file(fp=fp, ledger_fp=ledger_fp)

    assert pulled is None
    assert not download_calls  # no download attempted
    assert not fp.exists()
    assert read_ledger_last_filename(ledger_fp) == "geotargets-2026-02-25.csv"


def test_update_new_release_overwrites_and_appends(tmp_path, monkeypatch):
    mock_upstream(
        monkeypatch,
        "https://developers.google.com/geotargets-2026-02-25.csv",
        CSV_TEXT.encode("utf-8"),
    )
    fp = tmp_path / "geotargets.csv"
    ledger_fp = tmp_path / "ledger.csv"
    fp.write_text("stale contents")
    append_ledger_row(ledger_fp, date_collected="", filename="geotargets-2025-10-29.csv")

    pulled = update_locations_file(fp=fp, ledger_fp=ledger_fp)

    assert pulled == "geotargets-2026-02-25.csv"
    assert fp.read_bytes() == CSV_TEXT.encode("utf-8")
    with open(ledger_fp, encoding="utf-8", newline="") as infile:
        rows = list(csv.DictReader(infile))
    assert [r["filename"] for r in rows] == [
        "geotargets-2025-10-29.csv",
        "geotargets-2026-02-25.csv",
    ]


def test_update_is_byte_deterministic(tmp_path, monkeypatch):
    mock_upstream(
        monkeypatch,
        "https://developers.google.com/geotargets-2026-02-25.csv",
        CSV_TEXT.encode("utf-8"),
    )
    fp = tmp_path / "geotargets.csv"

    update_locations_file(fp=fp, ledger_fp=tmp_path / "ledger_a.csv")
    first = fp.read_bytes()
    update_locations_file(fp=fp, ledger_fp=tmp_path / "ledger_b.csv")

    assert fp.read_bytes() == first


def test_update_zip_variant(tmp_path, monkeypatch):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_ref:
        zip_ref.writestr("geotargets-2026-02-25.csv", CSV_TEXT)
    mock_upstream(
        monkeypatch,
        "https://developers.google.com/geotargets-2026-02-25.csv.zip",
        buffer.getvalue(),
    )
    fp = tmp_path / "geotargets.csv"
    ledger_fp = tmp_path / "ledger.csv"

    pulled = update_locations_file(fp=fp, ledger_fp=ledger_fp)

    assert pulled == "geotargets-2026-02-25.csv"  # .zip suffix stripped
    assert fp.read_bytes() == CSV_TEXT.encode("utf-8")
    assert read_ledger_last_filename(ledger_fp) == "geotargets-2026-02-25.csv"
