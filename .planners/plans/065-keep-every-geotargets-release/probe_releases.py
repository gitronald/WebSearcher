"""Probe Google's dated geotargets URLs for every day in a range.

The developer page lists only the current and previous release, but older
releases stay served at a dated static URL. A HEAD request per day finds every
release in a window, including ones the weekly job never saw. Prints one line
per release found.

Run from the repo root:

    uv run python .planners/plans/065-keep-every-geotargets-release/probe_releases.py \
        --start 2026-01-01 --end 2026-10-28
"""

import argparse
import time
from datetime import date, timedelta

import requests

DATED_URL = "https://developers.google.com/static/google-ads/api/data/geo/geotargets-{}.csv.zip"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--delay", type=float, default=0.2, help="seconds between requests")
    args = parser.parse_args()

    day = args.start
    with requests.Session() as session:
        while day <= args.end:
            url = DATED_URL.format(day.isoformat())
            response = session.head(url, timeout=30, allow_redirects=True)
            if response.status_code == 200:
                print(f"{day.isoformat()} {response.headers.get('content-length', '?')} {url}")
            elif response.status_code != 404:
                print(f"{day.isoformat()} status {response.status_code}")
            day += timedelta(days=1)
            time.sleep(args.delay)


if __name__ == "__main__":
    main()
