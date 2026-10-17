"""Resolve /goto?url=<token> redirects to their target URLs, paced and resumable.

Collects unique tokens from the given capture files (JSON lines, plain or bz2),
skips tokens already recorded in the output, and requests each one without
following the redirect. Each result is appended to ``pairs.jsonl`` as soon as it
arrives, so a stopped or interrupted run resumes where it left off.

Stops at the first sign of blocking: a 429, a redirect to /sorry/, any status
other than a 302 to a non-Google host, or a request error.

    uv run python .planners/plans/062-goto-redirect-resolution/resolve_goto.py data/goto-resolve \\
        data/demo-ws-v0.11.7a2-warm-profile/serps.json data/demo-ws-v0.11.7a2/serps.json \\
        --limit 1000 --rate 10
"""

import argparse
import bz2
import http.cookiejar
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

import orjson
import requests

from WebSearcher.parsers.components._ai_overview_payloads import extract_payloads
from WebSearcher.parsers.components.ai_overview import _index_full_url_by_goto

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36"
)
TOKEN_RE = re.compile(r"/goto\?url=([A-Za-z0-9_\-%]+)")
log = logging.getLogger("resolve_goto")


class Pacer:
    """Start at most ``rate`` requests per second across threads."""

    def __init__(self, rate: float):
        self.interval = 1.0 / rate
        self.next = time.monotonic()
        self.lock = threading.Lock()

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            start = max(now, self.next)
            self.next = start + self.interval
        time.sleep(max(0.0, start - now))


def load_tokens(paths: list[Path]) -> tuple[dict[str, dict], dict[str, str]]:
    """Unique tokens with provenance, and token -> URL known from AI overview payloads."""
    tokens: dict[str, dict] = {}
    known: dict[str, str] = {}
    for path in paths:
        raw = bz2.open(path).read() if path.suffix == ".bz2" else path.read_bytes()
        for line in raw.splitlines():
            record = orjson.loads(line)
            html = record["html"]
            for tok in TOKEN_RE.findall(html):
                tok = unquote(tok)
                entry = tokens.setdefault(
                    tok, {"serp_id": record["serp_id"], "captured": record["timestamp"]}
                )
                entry.setdefault("source", str(path))
            for red, url in _index_full_url_by_goto(extract_payloads(html)).items():
                known[unquote(red.split("url=", 1)[1].split("&")[0])] = url
    return tokens, known


def resolve(session: requests.Session, pacer: Pacer, token: str) -> dict:
    pacer.wait()
    started = time.monotonic()
    resp = session.get(
        f"https://www.google.com/goto?url={token}", allow_redirects=False, timeout=15
    )
    return {
        "status": resp.status_code,
        "location": resp.headers.get("location"),
        "elapsed_ms": round((time.monotonic() - started) * 1000),
    }


def blocked_reason(result: dict) -> str | None:
    status, loc = result["status"], result.get("location") or ""
    if status == 429:
        return "429 Too Many Requests"
    if "/sorry/" in loc:
        return f"redirect to captcha: {loc[:120]}"
    if status != 302:
        return f"unexpected status {status}"
    host = urlsplit(loc).hostname or ""
    if not loc or host.endswith("google.com"):
        return f"302 into google: {loc[:120]}"
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("captures", type=Path, nargs="+")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--rate", type=float, default=10.0)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    pairs_fp = args.out_dir / "pairs.jsonl"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(args.out_dir / "resolve.log"), logging.StreamHandler()],
    )

    tokens, known = load_tokens(args.captures)
    done: set[str] = set()
    if pairs_fp.exists():
        done = {json.loads(line)["token"] for line in pairs_fp.read_text().splitlines() if line}
    todo = [t for t in tokens if t not in done][: args.limit]
    log.info(
        "tokens=%d already_done=%d this_run=%d known_from_payloads=%d rate=%.1f/s workers=%d",
        len(tokens),
        len(done),
        len(todo),
        len(known),
        args.rate,
        args.workers,
    )

    session = requests.Session()
    session.headers["User-Agent"] = UA
    session.cookies.set_policy(http.cookiejar.DefaultCookiePolicy(allowed_domains=[]))
    pacer = Pacer(args.rate)
    stop = threading.Event()
    write_lock = threading.Lock()
    counts = {"ok": 0, "match": 0, "mismatch": 0}
    t0 = time.monotonic()

    def work(token: str) -> None:
        if stop.is_set():
            return
        try:
            result = resolve(session, pacer, token)
        except requests.RequestException as e:
            log.error("request error, stopping: %s", e)
            stop.set()
            return
        reason = blocked_reason(result)
        if reason:
            log.error("BLOCKED after %d ok: %s", counts["ok"], reason)
            stop.set()
            return
        row = {
            "token": token,
            "url": result["location"],
            "resolved_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "elapsed_ms": result["elapsed_ms"],
            **tokens[token],
        }
        expected = known.get(token)
        if expected is not None:
            row["payload_url"] = expected
            counts["match" if expected == result["location"] else "mismatch"] += 1
        with write_lock:
            with pairs_fp.open("a") as f:
                f.write(json.dumps(row) + "\n")
            counts["ok"] += 1
            if counts["ok"] % 100 == 0:
                rate = counts["ok"] / (time.monotonic() - t0)
                log.info("resolved %d (%.1f/s)", counts["ok"], rate)

    with ThreadPoolExecutor(args.workers) as pool:
        for fut in as_completed([pool.submit(work, t) for t in todo]):
            fut.result()

    elapsed = time.monotonic() - t0
    log.info(
        "done: resolved=%d in %.0fs (%.1f/s) stopped=%s payload_check match=%d mismatch=%d",
        counts["ok"],
        elapsed,
        counts["ok"] / elapsed if elapsed else 0,
        stop.is_set(),
        counts["match"],
        counts["mismatch"],
    )


if __name__ == "__main__":
    main()
