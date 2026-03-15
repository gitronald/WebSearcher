"""Search and parse queries designed to trigger diverse SERP component types"""

import os
import random
import time

import pandas as pd
import typer

import WebSearcher as ws

pd.set_option("display.width", 160)
pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.max_colwidth", 40)

DEFAULT_DATA_DIR = os.path.join("data", f"demo-ws-v{ws.__version__}")

# Queries organized by target component type, 3 per type
# Some queries trigger multiple types (e.g. ads + shopping_ads)
QUERIES = {
    # ad, shopping_ads
    "ad": [
        "best credit cards",
        "car insurance quotes",
        "cheap flights to new york",
    ],
    # available_on
    "available_on": [
        "watch the office",
        "stream stranger things",
        "where to watch breaking bad",
    ],
    # discussions_and_forums
    "discussions_and_forums": [
        "best budget headphones reddit",
        "is it worth learning rust reddit",
        "best mattress forum",
    ],
    # general, people_also_ask, searches_related (common baseline)
    "general": [
        "why is the sky blue",
        "how does photosynthesis work",
        "what causes earthquakes",
    ],
    # images, top_image_carousel, img_cards
    "images": [
        "golden retriever puppies",
        "northern lights",
        "art deco architecture",
    ],
    # knowledge (featured_snippet, calculator, unit_converter, dictionary, etc.)
    "knowledge": [
        "population of france",
        "define serendipity",
        "100 fahrenheit to celsius",
    ],
    # knowledge (ai_overview, panel)
    "knowledge_panel": [
        "albert einstein",
        "apple inc",
        "taylor swift",
    ],
    # knowledge (weather, sports, finance)
    "knowledge_live": [
        "weather today",
        "nba scores",
        "aapl stock price",
    ],
    # knowledge (translate)
    "knowledge_translate": [
        "translate hello to japanese",
        "translate good morning to french",
        "translate thank you to korean",
    ],
    # local_results, map_results
    "local_results": [
        "restaurants near austin tx",
        "coffee shops portland oregon",
        "hotels in manhattan",
    ],
    # local_news
    "local_news": [
        "news near chicago",
        "local news san francisco",
        "houston news today",
    ],
    # perspectives, recent_posts
    "perspectives": [
        "best programming language to learn",
        "is college worth it",
        "tips for first marathon",
    ],
    # scholarly_articles
    "scholarly_articles": [
        "effects of sleep deprivation on cognition",
        "climate change coral reef impact",
        "machine learning protein folding",
    ],
    # top_stories
    "top_stories": [
        "latest world news",
        "election results",
        "technology news today",
    ],
    # twitter_cards, twitter_result
    "twitter": [
        "@nasa",
        "@nytimes",
        "@elaboratetweet",
    ],
    # videos
    "videos": [
        "how to change a tire",
        "yoga for beginners",
        "python tutorial for beginners",
    ],
}

app = typer.Typer()


@app.command()
def main(
    method: str = typer.Argument("selenium", help="Search method to use: 'selenium' or 'requests'"),
    data_dir: str = typer.Option(DEFAULT_DATA_DIR, help="Prefix for output files"),
    headless: bool = typer.Option(False, help="Run browser in headless mode"),
    use_subprocess: bool = typer.Option(False, help="Run browser in a separate subprocess"),
    version_main: int = typer.Option(144, help="Main version of Chrome to use"),
    ai_expand: bool = typer.Option(True, help="Expand AI overviews if present"),
    driver_executable_path: str = typer.Option("", help="Path to ChromeDriver executable"),
    types: list[str] = typer.Option([], help="Only run queries for these target types"),
) -> None:

    # Filepaths
    fps = {k: os.path.join(data_dir, f"{k}.json") for k in ["serps", "parsed", "searches"]}
    os.makedirs(data_dir, exist_ok=True)

    # Filter queries by type if specified
    if types:
        queries = [q for t in types if t in QUERIES for q in QUERIES[t]]
    else:
        queries = [q for group in QUERIES.values() for q in group]

    print(f"Running {len(queries)} queries, saving to {data_dir}")

    # Reuse a single browser session across all queries
    se = ws.SearchEngine(
        method=method,
        selenium_config={
            "headless": headless,
            "use_subprocess": use_subprocess,
            "driver_executable_path": driver_executable_path,
            "version_main": version_main,
        },
    )

    for i, qry in enumerate(queries):
        # Search, parse, and save
        se.search(qry, ai_expand=ai_expand)  # Conduct Search
        se.parse_serp()  # Parse Results
        se.save_serp(append_to=fps["serps"])  # Save SERP to json (html + metadata)
        se.save_search(append_to=fps["searches"])  # Save search to json (metadata only)
        se.save_parsed(append_to=fps["parsed"])  # Save parsed results and SERP features to json

        # Check for CAPTCHA — retry once after waiting
        if se.parsed.get("features", {}).get("captcha"):
            print(f"\n[{i + 1}/{len(queries)}] CAPTCHA detected for '{qry}', waiting 5 min...")
            time.sleep(300)
            se.search(qry, ai_expand=ai_expand)
            se.parse_serp()
            if se.parsed.get("features", {}).get("captcha"):
                print("CAPTCHA still present, stopping.")
                break

        # Convert results to dataframe and print select columns
        if se.parsed["results"]:
            results = pd.DataFrame(se.parsed["results"])
            print(f"\n[{i + 1}/{len(queries)}] {qry}")
            print(results[["type", "sub_type", "title", "url"]])

        if i < len(queries) - 1:
            time.sleep(30 + random.uniform(0, 5))


if __name__ == "__main__":
    app()
