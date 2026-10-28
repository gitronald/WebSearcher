"""Tests for protobuf encoding/UULE generation and the geotargets update flow"""

import csv
import io
import zipfile

import pytest

import WebSearcher.locations as locations
from WebSearcher.locations import (
    append_ledger_row,
    convert_canonical_name_to_uule,
    decode_protobuf_string,
    encode_protobuf_string,
    normalize_csv_text,
    read_ledger_last_filename,
    update_locations_file,
)


def test_encode_decode_roundtrip_integers():
    fields: dict[int, int | str] = {1: 2, 2: 32}
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


def mock_upstream(monkeypatch, url_latest: str | list[str], content: bytes) -> list[str]:
    """Stub the listing-page scrape and the download; return the call log.

    ``url_latest`` is the one listed release, or the listing oldest first."""
    download_calls = []
    release_urls = [url_latest] if isinstance(url_latest, str) else url_latest
    monkeypatch.setattr(locations, "get_release_urls", lambda url: release_urls)

    def fake_get(url, timeout=None):
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


def test_update_rejects_header_drift(tmp_path, monkeypatch):
    drifted = CSV_TEXT.replace("Criteria ID", "Criterion ID")
    mock_upstream(
        monkeypatch,
        "https://developers.google.com/geotargets-2026-02-25.csv",
        drifted.encode("utf-8"),
    )
    fp = tmp_path / "geotargets.csv"
    ledger_fp = tmp_path / "ledger.csv"

    with pytest.raises(ValueError, match="header drift"):
        update_locations_file(fp=fp, ledger_fp=ledger_fp)

    assert not ledger_fp.exists()  # failed pull is not recorded; next run retries


def release_url(release: str) -> str:
    return f"https://developers.google.com/static/geo/geotargets-{release}.csv.zip"


def zipped_csv() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_ref:
        zip_ref.writestr("geotargets.csv", CSV_TEXT)
    return buffer.getvalue()


def read_ledger_filenames(ledger_fp) -> list[str]:
    with open(ledger_fp, encoding="utf-8", newline="") as infile:
        return [row["filename"] for row in csv.DictReader(infile)]


def test_get_release_urls_orders_by_date_and_skips_page_link(monkeypatch):
    page = (
        b"<a href='/google-ads/api/data/geotargets'>page</a>"
        b"<a href='/static/geo/geotargets-2026-10-06.csv.zip'>current</a>"
        b"<a href='/static/geo/geotargets-2026-08-12.csv.zip'>previous</a>"
    )
    monkeypatch.setattr(locations.requests, "get", lambda url, timeout=None: FakeResponse(page))

    assert locations.get_release_urls("https://example.invalid/page") == [
        "https://developers.google.com/static/geo/geotargets-2026-08-12.csv.zip",
        "https://developers.google.com/static/geo/geotargets-2026-10-06.csv.zip",
    ]


def test_release_date_reads_both_filename_shapes():
    assert locations.release_date("geotargets-2026-10-06.csv") == "2026-10-06"
    assert locations.release_date("AdWords API Location Criteria 2018-09-04.csv") == "2018-09-04"
    assert locations.release_date(release_url("2026-08-12")) == "2026-08-12"
    with pytest.raises(ValueError, match="no release date"):
        locations.release_date("geotargets.csv")


def test_update_pulls_oldest_unseen_release(tmp_path, monkeypatch):
    download_calls = mock_upstream(
        monkeypatch, [release_url("2026-08-12"), release_url("2026-10-06")], zipped_csv()
    )
    fp = tmp_path / "geotargets.csv"
    ledger_fp = tmp_path / "ledger.csv"
    append_ledger_row(ledger_fp, date_collected="", filename="geotargets-2026-08-12.csv")

    pulled = update_locations_file(fp=fp, ledger_fp=ledger_fp)

    assert pulled == "geotargets-2026-10-06.csv"
    assert download_calls == [release_url("2026-10-06")]


def test_update_loop_pulls_each_release_in_order(tmp_path, monkeypatch, capsys):
    listing = [release_url("2026-06-15"), release_url("2026-07-06"), release_url("2026-07-16")]
    download_calls = mock_upstream(monkeypatch, listing, zipped_csv())
    fp = tmp_path / "geotargets.csv"
    ledger_fp = tmp_path / "ledger.csv"
    append_ledger_row(ledger_fp, date_collected="", filename="geotargets-2026-06-15.csv")

    pulled = []
    while (filename := update_locations_file(fp=fp, ledger_fp=ledger_fp)) is not None:
        pulled.append(filename)

    assert pulled == ["geotargets-2026-07-06.csv", "geotargets-2026-07-16.csv"]
    assert download_calls == listing[1:]
    assert read_ledger_filenames(ledger_fp) == [
        "geotargets-2026-06-15.csv",
        "geotargets-2026-07-06.csv",
        "geotargets-2026-07-16.csv",
    ]
    assert "Version up to date: geotargets-2026-07-16.csv" in capsys.readouterr().out


def test_update_warns_on_unenumerable_gap(tmp_path, monkeypatch, capsys):
    mock_upstream(monkeypatch, [release_url("2026-08-12"), release_url("2026-10-06")], zipped_csv())
    fp = tmp_path / "geotargets.csv"
    ledger_fp = tmp_path / "ledger.csv"
    append_ledger_row(ledger_fp, date_collected="", filename="geotargets-2026-06-15.csv")

    pulled = update_locations_file(fp=fp, ledger_fp=ledger_fp)

    out = capsys.readouterr().out
    assert "warning: ledger ends at geotargets-2026-06-15.csv" in out
    assert "oldest geotargets-2026-08-12.csv" in out
    assert pulled == "geotargets-2026-08-12.csv"  # still pulls what it can see


def test_update_no_gap_warning_when_ledger_is_listed(tmp_path, monkeypatch, capsys):
    mock_upstream(monkeypatch, [release_url("2026-08-12"), release_url("2026-10-06")], zipped_csv())
    ledger_fp = tmp_path / "ledger.csv"
    append_ledger_row(ledger_fp, date_collected="", filename="geotargets-2026-08-12.csv")

    update_locations_file(fp=tmp_path / "geotargets.csv", ledger_fp=ledger_fp)

    assert "warning: ledger ends" not in capsys.readouterr().out


def test_normalize_csv_text_preserves_quoted_newlines():
    text = 'a,"line1\nline2"\r\nb,c\r\n'
    assert normalize_csv_text(text) == [["a", "line1\nline2"], ["b", "c"]]
