"""Live-search demos: a single query (``search``) and a battery spanning component types (``searches``)."""

import random
import time
from pathlib import Path

import WebSearcher as ws

from ._common import _default_data_dir, _print_results_table

# Queries organized by target component type (3 per type) for the `searches` battery.
# Some queries trigger multiple types (e.g. ad + shopping_ads).
QUERIES = {
    "ad": ["best credit cards", "car insurance quotes", "cheap flights to new york"],
    "available_on": ["watch the office", "stream stranger things", "where to watch breaking bad"],
    "discussions_and_forums": [
        "best budget headphones reddit",
        "is it worth learning rust reddit",
        "best mattress forum",
    ],
    "general": ["why is the sky blue", "how does photosynthesis work", "what causes earthquakes"],
    "images": ["golden retriever puppies", "northern lights", "art deco architecture"],
    "knowledge": ["population of france", "define serendipity", "100 fahrenheit to celsius"],
    "knowledge_panel": ["albert einstein", "apple inc", "taylor swift"],
    "knowledge_live": ["weather today", "nba scores", "aapl stock price"],
    "knowledge_translate": [
        "translate hello to japanese",
        "translate good morning to french",
        "translate thank you to korean",
    ],
    "local_results": [
        "restaurants near austin tx",
        "coffee shops portland oregon",
        "hotels in manhattan",
    ],
    "local_news": ["news near chicago", "local news san francisco", "houston news today"],
    "perspectives": [
        "best programming language to learn",
        "is college worth it",
        "tips for first marathon",
    ],
    "scholarly_articles": [
        "effects of sleep deprivation on cognition",
        "climate change coral reef impact",
        "machine learning protein folding",
    ],
    "top_stories": ["latest world news", "election results", "technology news today"],
    "twitter": ["@nasa", "@nytimes", "@elaboratetweet"],
    "videos": ["how to change a tire", "yoga for beginners", "python tutorial for beginners"],
}


def _engine_kwargs(
    method: str,
    headless: bool,
    use_subprocess: bool,
    version_main: int | None,
    driver_executable_path: str,
) -> dict:
    """Build SearchEngine kwargs, routing shared flags to the method's config."""
    kwargs: dict = {"method": method}
    if method == "selenium":
        kwargs["selenium_config"] = {
            "headless": headless,
            "use_subprocess": use_subprocess,
            "driver_executable_path": driver_executable_path,
            "version_main": version_main,
        }
    elif method == "zendriver":
        kwargs["zendriver_config"] = {"headless": headless}
    elif method == "patchright":
        kwargs["patchright_config"] = {"headless": headless}
    elif method == "playwright":
        kwargs["playwright_config"] = {"headless": headless}
    return kwargs


def _chrome_version() -> str:
    """Best-effort installed-Chrome version for the search header (never raises)."""
    try:
        from ..search_methods.selenium_searcher import detect_chrome_version

        return detect_chrome_version() or "unknown"
    except Exception:
        return "unknown"


def search(
    query: str = "why is the sky blue?",
    method: str = "selenium",
    data_dir: str | None = None,
    headless: bool = False,
    use_subprocess: bool = False,
    version_main: int | None = None,
    ai_expand: bool = True,
    driver_executable_path: str = "",
):
    """Search and parse a single query (selenium or requests), saving serps/parsed/searches."""
    data_path = Path(data_dir) if data_dir else _default_data_dir()
    data_path.mkdir(parents=True, exist_ok=True)
    fps = {k: data_path / f"{k}.json" for k in ("serps", "parsed", "searches")}

    header = f"WebSearcher v{ws.__version__}\nSearch Query: {query}\n"
    if method == "selenium":
        header += f"Chrome Version: {_chrome_version()}\n"
    header += f"Output Dir: {data_path}\n"
    print(header)

    se = ws.SearchEngine(
        **_engine_kwargs(method, headless, use_subprocess, version_main, driver_executable_path)
    )
    se.search(query, ai_expand=ai_expand)
    se.parse_serp()
    se.save_serp(append_to=fps["serps"])
    se.save_search(append_to=fps["searches"])
    se.save_parsed(append_to=fps["parsed"])

    _print_results_table(se.parsed.results)
    return se


def searches(
    types: list[str] | None = None,
    method: str = "selenium",
    data_dir: str | None = None,
    headless: bool = False,
    use_subprocess: bool = False,
    version_main: int | None = None,
    ai_expand: bool = True,
    driver_executable_path: str = "",
    delay: float = 30.0,
):
    """Search a battery of queries spanning SERP component types, reusing one browser session.

    Saves serps/parsed/searches like ``search``. Pass ``types`` to limit to specific QUERIES
    groups. Handles CAPTCHAs (waits 5 min and retries once) and jitters the inter-query delay.
    """
    data_path = Path(data_dir) if data_dir else _default_data_dir()
    data_path.mkdir(parents=True, exist_ok=True)
    fps = {k: data_path / f"{k}.json" for k in ("serps", "parsed", "searches")}

    if types:
        queries = [q for t in types if t in QUERIES for q in QUERIES[t]]
    else:
        queries = [q for group in QUERIES.values() for q in group]
    print(f"Running {len(queries)} queries, saving to {data_path}")

    se = ws.SearchEngine(
        **_engine_kwargs(method, headless, use_subprocess, version_main, driver_executable_path)
    )

    for i, qry in enumerate(queries):
        se.search(qry, ai_expand=ai_expand)
        se.parse_serp()
        se.save_serp(append_to=fps["serps"])
        se.save_search(append_to=fps["searches"])

        if se.parsed.features.get("captcha"):
            print(f"\n[{i + 1}/{len(queries)}] CAPTCHA for {qry!r}, waiting 5 min...")
            time.sleep(300)
            se.search(qry, ai_expand=ai_expand)
            se.parse_serp()
            se.save_serp(append_to=fps["serps"])
            se.save_search(append_to=fps["searches"])
            if se.parsed.features.get("captcha"):
                print("CAPTCHA still present, stopping.")
                break

        # Always save the raw SERP above (CAPTCHA pages included); only persist a
        # parse for a non-CAPTCHA page -- the original, or a recovered retry.
        se.save_parsed(append_to=fps["parsed"])

        if se.parsed.results:
            print(f"\n[{i + 1}/{len(queries)}] {qry}")
            _print_results_table(se.parsed.results)

        if i < len(queries) - 1:
            time.sleep(delay + random.uniform(0, 5))

    return se
