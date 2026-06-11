import base64
import csv
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from google.protobuf.internal import decoder, encoder  # uv add protobuf

from . import logger, utils

# Private protobuf APIs not exposed in stubs; access via getattr to silence type checker.
_varint_bytes = getattr(encoder, "_VarintBytes")
_decode_varint = getattr(decoder, "_DecodeVarint")

log = logger.Logger().start(__name__)

GEOTARGETS_URL = "https://developers.google.com/adwords/api/docs/appendix/geotargeting"

# Upstream header, unchanged 2018 -> 2026 across the seeded archive; drift
# means the schema consumers rely on has moved, so fail loudly.
GEOTARGETS_HEADER = [
    "Criteria ID",
    "Name",
    "Canonical Name",
    "Parent ID",
    "Country Code",
    "Target Type",
    "Status",
]

REQUEST_TIMEOUT = 60  # seconds per socket read; unattended cron must not hang


def convert_canonical_name_to_uule(canon_name: str) -> str:
    """
    Get UULE parameter based on a location's canonical name.
    Args: canon_name: Canonical name of the location
    Returns: UULE parameter for Google search
    """
    fields = {1: 2, 2: 32, 4: canon_name}
    encoded_string = encode_protobuf_string(fields)
    return f"w+{encoded_string}"


def encode_protobuf_string(fields: dict[int, str | int]) -> str:
    """
    Encode a dictionary of field numbers and values into a base64-encoded protobuf string.
    Args: fields: A dictionary where keys are protobuf field numbers and values are the data to encode
    Returns: A base64-encoded protobuf message string
    """
    encoded = bytearray()  # Buffer to store encoded bytes

    for field_number, value in fields.items():
        wire_type = 2 if isinstance(value, str) else 0  # Determine wire type based on value type
        tag = field_number << 3 | wire_type  # Combine field number and wire type into tag
        encoded.extend(_varint_bytes(tag))

        # Encode the value based on wire type
        if wire_type == 0:
            encoded.extend(_varint_bytes(value))
        elif wire_type == 2 and isinstance(value, str):
            value_bytes = value.encode("utf-8")
            encoded.extend(_varint_bytes(len(value_bytes)))
            encoded.extend(value_bytes)

    return base64.b64encode(bytes(encoded)).decode(
        "utf-8"
    )  # Convert to base64 and decode to string


def decode_protobuf_string(encoded_string: str) -> dict[int, Any]:
    """
    Decode a base64-encoded protobuf string into a dictionary of field numbers and values.
    Args: encoded_string: A base64-encoded protobuf message
    Returns: dictionary where keys are protobuf field numbers and values are the decoded values
    """

    pos = 0  # Position tracker for decoding
    fields = {}  # Dictionary to store decoded field numbers and values

    protobuf_bytes = base64.b64decode(encoded_string)  # Convert to protobuf bytes
    while pos < len(protobuf_bytes):
        # Get field number and wire type
        tag, pos_new = _decode_varint(protobuf_bytes, pos)
        field_number, wire_type = (tag >> 3, tag & 7)

        # Decode value based on wire type (0: varint, 2: length-delimited; others not supported)
        value: Any = None
        if wire_type == 0:
            value, pos_new = _decode_varint(protobuf_bytes, pos_new)
        elif wire_type == 2:
            length, pos_start = _decode_varint(protobuf_bytes, pos_new)
            value_bytes = protobuf_bytes[pos_start : pos_start + length]
            pos_new = pos_start + length
            value = value_bytes.decode("utf-8")
        else:
            raise ValueError(f"unsupported wire type: {wire_type}")

        fields[field_number] = value
        pos = pos_new
    return fields


def download_locations(
    data_dir: str | Path = "data/locations",
    url: str = GEOTARGETS_URL,
) -> None:
    """Download the latest geolocations, check if already exists locally first.

    Args:
        data_dir (str): Where to save the data as a csv
        url (str, optional): Defaults to the current URL

    Returns:
        None: Saves to file in the default or selected data_dir

    """
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    url_latest = get_latest_url(url)
    fp = data_dir / url_latest.split("/")[-1]
    fp_unzip = fp.with_suffix("")

    # Check if the current version already exists
    if fp.exists():
        print(f"Version up to date: {fp}")
    elif fp_unzip.exists():
        print(f"Version up to date: {fp_unzip}")
    else:
        print("Version out of date")
        download_csv(url_latest, fp_unzip)


def update_locations_file(
    fp: str | Path = "data/locations/geotargets.csv",
    ledger_fp: str | Path = "data/locations/ledger.csv",
    url: str = GEOTARGETS_URL,
) -> str | None:
    """Download the latest geotargets CSV, overwrite ``fp``, and log the pull.

    Change detection keys on the upstream filename, which embeds the real
    release date (``geotargets-YYYY-MM-DD.csv``): if it matches the last
    ledger row, nothing is downloaded. On a new release, ``fp`` is overwritten
    in place and one ``date_collected,filename`` row is appended to
    ``ledger_fp``.

    Args:
        fp: Stable path the CSV is written to (overwritten each release)
        ledger_fp: Append-only CSV logging each successful pull
        url: Page listing the geotargets CSV downloads

    Returns:
        The upstream CSV filename if a new version was pulled, else None.
    """
    fp = Path(fp)
    ledger_fp = Path(ledger_fp)

    url_latest = get_latest_url(url)
    filename = url_latest.split("/")[-1].removesuffix(".zip")

    if filename == read_ledger_last_filename(ledger_fp):
        print(f"Version up to date: {filename}")
        return None

    fp.parent.mkdir(parents=True, exist_ok=True)
    download_csv(url_latest, fp)
    check_geotargets_header(fp)

    date_collected = datetime.now(UTC).date().isoformat()
    append_ledger_row(ledger_fp, date_collected=date_collected, filename=filename)
    return filename


def download_csv(url_latest: str, fp: str | Path) -> None:
    """Fetch a geotargets CSV URL (plain or zipped) and write it to ``fp``."""
    print(f"getting: {url_latest}")
    response = requests.get(url_latest, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    if url_latest.endswith(".zip"):
        save_zip_response(response, str(fp))
    else:
        write_csv(str(fp), normalize_csv_text(response.content.decode("utf-8")))


def check_geotargets_header(fp: str | Path) -> None:
    """Raise if the downloaded CSV's header drifted from the known schema."""
    with open(fp, encoding="utf-8", newline="") as infile:
        header = next(csv.reader(infile), None)
    if header != GEOTARGETS_HEADER:
        raise ValueError(f"geotargets header drift: {header} != {GEOTARGETS_HEADER}")


def normalize_csv_text(text: str) -> list[list[str]]:
    """Round-trip raw CSV text through the csv module for stable output bytes."""
    return list(csv.reader(io.StringIO(text, newline=""), delimiter=","))


def read_ledger_last_filename(ledger_fp: str | Path) -> str | None:
    """Return the ``filename`` of the last ledger row, or None if no rows yet."""
    ledger_fp = Path(ledger_fp)
    if not ledger_fp.exists():
        return None
    with open(ledger_fp, encoding="utf-8", newline="") as infile:
        rows = list(csv.DictReader(infile))
    return rows[-1]["filename"] if rows else None


def append_ledger_row(ledger_fp: str | Path, date_collected: str, filename: str) -> None:
    """Append one pull record to the ledger, writing the header if it is new."""
    ledger_fp = Path(ledger_fp)
    write_header = not ledger_fp.exists()
    with open(ledger_fp, "a", encoding="utf-8", newline="") as outfile:
        writer = csv.writer(outfile)
        if write_header:
            writer.writerow(["date_collected", "filename"])
        writer.writerow([date_collected, filename])


def get_latest_url(url: str) -> str:
    html = requests.get(url, timeout=REQUEST_TIMEOUT).content
    soup = utils.make_soup(html)
    links = utils.get_link_list(soup) or []
    url_list = [u for u in links if u]
    geo_urls = [u for u in url_list if "geotargets" in u]

    # Get current CSV url and use as filename
    geo_url = sorted(geo_urls)[-1]
    return "https://developers.google.com" + geo_url


def save_zip_response(response: requests.Response, fp: str) -> None:
    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
        for member in zip_ref.namelist():
            if member.endswith(".csv"):
                with zip_ref.open(member) as csv_file:
                    reader = csv.reader(io.TextIOWrapper(csv_file, "utf-8"))
                    write_csv(fp, reader=reader)


def write_csv(fp: str, lines: list | None = None, reader: Any = None) -> None:
    with open(fp, "w", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        if reader:
            writer.writerows(reader)
        elif lines:
            writer.writerows(lines)
    print(f"saved: {fp}")


def main() -> None:
    """Update the tracked geotargets CSV and report what happened."""
    fp = Path("data/locations/geotargets.csv")
    filename = update_locations_file(fp=fp)
    if filename is None:
        return
    with open(fp, encoding="utf-8", newline="") as infile:
        n_rows = sum(1 for _ in csv.reader(infile)) - 1
    print(f"pulled: {filename} ({n_rows:,} locations)")


if __name__ == "__main__":
    main()
