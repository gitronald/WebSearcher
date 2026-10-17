"""Extract payload data embedded alongside the AI overview HTML.

Google ships per-UUID JSON blobs that back the citation buttons and source tray
in the AI overview. Three delivery forms appear in practice:

1. HTML comment ``<!--TgQPHd|<json>-->`` — most common (97% of button-bearing
   SERPs in the audit). The role-heading layout (2026-10) writes
   ``<!--TgQPHd|||<json>-->``, and some captures put jsuid keys before or
   between the pipes (``<!--TgQPHd<keys>||<json>-->``,
   ``<!--TgQPHd|<keys>|<json>-->``), so any prefix up to the last pipe before
   the JSON is skipped.
2. HTML comment ``<!--Sv6Kpe<json>-->`` — same payload shapes, no ``|``
   separator before the JSON.
3. Script push ``(j.lDPB=j.lDPB||[]).push([["<jsid>","<escaped-json>"]])`` —
   the ~3% fallback.

Each UUID can have multiple payloads of three shapes:

- ``header``  — ``[[null, null, <uuid>, null, null, 1, 0, <favicon>, <publisher>, <total_count>]]``,
  or in the role-heading layout
  ``[[<uuid>, null, null, 0, <favicon>, <publisher>, <total_count>, <full_url>, ...]]``,
  which also carries the full URL of the button's lead source.
- ``type_a``  — ``[[<uuid>, [<title>, <snippet>, <favicon>, <domain>, [<publisher>], <full_url>, null, null, "<data-src-id>", ...]]]``
  (``data-src-id`` is at ``inner[1][8]`` and may be int or str.) In the
  role-heading layout ``<full_url>`` is a ``/goto?url=`` redirect instead.
- ``type_b``  — ``[[<uuid>, "<index>", 0, <full_url>, <favicon>, ""]]``
"""

from __future__ import annotations

import functools
import html
import json
import re
from typing import Any

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

_COMMENT_TGQPHD = re.compile(r"<!--TgQPHd[^\[>]*\|(\[.+?)-->", re.DOTALL)
_COMMENT_SV6KPE = re.compile(r"<!--Sv6Kpe(.+?)-->", re.DOTALL)
_LDPB_PUSH = re.compile(
    r'\["[a-zA-Z0-9_]+","(\[\[\\"[0-9a-f-]{36}\\".*?\]\])"\]',
    re.DOTALL,
)


@functools.lru_cache(maxsize=2)
def extract_payloads(raw_html: str) -> dict[str, dict[str, Any]]:
    """Return ``{uuid: {"header": payload | None, "type_a": [...], "type_b": [...]}}``.

    Scans the raw HTML string for all three delivery forms, decodes each JSON
    blob, classifies by shape, and groups by UUID. Cached so adjacent AI
    overview cmpts within one parse skip the rescan; ``maxsize=2`` keeps the
    cache from holding multiple SERPs' worth of payloads.
    """
    out: dict[str, dict[str, Any]] = {}
    for raw in _iter_payload_blobs(raw_html):
        classified = _classify(raw)
        if classified is None:
            continue
        kind, uuid, value = classified
        bucket = out.setdefault(uuid, {"header": None, "type_a": [], "type_b": []})
        if kind == "header":
            bucket["header"] = value
        else:
            bucket[kind].append(value)
    return out


def _iter_payload_blobs(raw_html: str):
    for m in _COMMENT_TGQPHD.finditer(raw_html):
        yield html.unescape(m.group(1))
    for m in _COMMENT_SV6KPE.finditer(raw_html):
        yield html.unescape(m.group(1))
    for m in _LDPB_PUSH.finditer(raw_html):
        # The JS push stores the JSON as a JS string literal (``\"`` -> ``"``,
        # ``\x3d`` -> ``=``, ``\uXXXX`` escapes). Decode it as a string literal
        # rather than through ``unicode_escape``, which reads UTF-8 bytes as
        # Latin-1 (``Café`` -> ``CafÃ©``) and leaves ``😀`` pairs as
        # lone surrogates that fail later UTF-8 encoding.
        decoded = _decode_js_string(m.group(1))
        if decoded is not None:
            yield decoded


_JS_HEX_ESCAPE = re.compile(r"\\x([0-9a-fA-F]{2})")


def _decode_js_string(literal: str) -> str | None:
    """Decode the body of a JS double-quoted string literal to text.

    JSON string syntax covers everything JS emits here except ``\\xHH`` (mapped
    to ``\\u00HH``) and ``\\'`` (JSON forbids escaping ``'``). ``strict=False``
    tolerates raw control characters inside the literal."""
    body = _JS_HEX_ESCAPE.sub(lambda m: "\\u00" + m.group(1), literal).replace("\\'", "'")
    try:
        value = json.loads(f'"{body}"', strict=False)
    except (json.JSONDecodeError, ValueError):
        return None
    return value if isinstance(value, str) else None


def _classify(raw: str) -> tuple[str, str, object] | None:
    """Return ``(kind, uuid, value)`` or None for unrecognized shapes."""
    if not raw or raw == "[]":
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        return None
    inner = data[0]

    # Header
    if (
        len(inner) >= 10
        and inner[0] is None
        and isinstance(inner[2], str)
        and _UUID_RE.match(inner[2])
    ):
        return (
            "header",
            inner[2],
            {
                "favicon": inner[7] or "",
                "publisher": inner[8] or "",
                "total": inner[9] if isinstance(inner[9], int) else 0,
                "url": None,
            },
        )

    # Role-heading layout header: uuid first, full URL of the lead source at [7]
    if (
        len(inner) >= 8
        and isinstance(inner[0], str)
        and _UUID_RE.match(inner[0])
        and inner[1] is None
        and inner[2] is None
        and isinstance(inner[7], str)
    ):
        return (
            "header",
            inner[0],
            {
                "favicon": inner[4] if isinstance(inner[4], str) else "",
                "publisher": inner[5] if isinstance(inner[5], str) else "",
                "total": inner[6] if isinstance(inner[6], int) else 0,
                "url": inner[7],
            },
        )

    # Type A / Type B share inner[0] = uuid
    if len(inner) >= 2 and isinstance(inner[0], str) and _UUID_RE.match(inner[0]):
        uuid = inner[0]
        body = inner[1]
        if isinstance(body, list) and len(body) >= 6:
            title = body[0] if isinstance(body[0], str) else None
            snippet = body[1] if isinstance(body[1], str) else None
            favicon = body[2] if isinstance(body[2], str) else None
            domain = body[3] if isinstance(body[3], str) else None
            publisher_list: list[Any] = body[4] if isinstance(body[4], list) else []
            publisher = (
                publisher_list[0] if publisher_list and isinstance(publisher_list[0], str) else None
            )
            full_url = body[5] if isinstance(body[5], str) else None
            src_id_raw = body[8] if len(body) > 8 else None
            src_id = _coerce_src_id(src_id_raw)
            return (
                "type_a",
                uuid,
                {
                    "title": title,
                    "snippet": snippet,
                    "favicon": favicon,
                    "domain": domain,
                    "publisher": publisher,
                    "url": full_url,
                    "source_id": src_id,
                },
            )
        if isinstance(body, str) and len(inner) >= 4 and isinstance(inner[3], str):
            return (
                "type_b",
                uuid,
                {
                    "source_id": body,
                    "url": inner[3],
                    "favicon": inner[4] if len(inner) > 4 and isinstance(inner[4], str) else None,
                },
            )

    return None


def _coerce_src_id(raw: object) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, str)):
        s = str(raw)
        return s if s else None
    return None
