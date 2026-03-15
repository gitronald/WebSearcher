"""Screenshot SERP HTML for visual inspection

Renders raw HTML from serps.json in a headless browser and saves a full-page
screenshot. Optionally highlights extracted components with colored borders
showing their classified types. Highlights are injected directly into the
BeautifulSoup elements the extractor actually finds, so borders match exactly.
"""

import json
import os
import tempfile

import typer

import WebSearcher as ws

DEFAULT_DATA_DIR = os.path.join("data", f"demo-ws-v{ws.__version__}")

app = typer.Typer()

TYPE_COLORS = {
    "knowledge": "#4285f4",
    "general": "#34a853",
    "discussions_and_forums": "#fbbc05",
    "perspectives": "#ea4335",
    "top_stories": "#ff6d01",
    "people_also_ask": "#46bdc6",
    "searches_related": "#7b1fa2",
    "locations": "#ff9800",
    "shopping_ads": "#e91e63",
    "unknown": "#d32f2f",
    "ad": "#f44336",
}
DEFAULT_COLOR = "#9e9e9e"


def load_serp_html(serps_path: str, index: int = 0) -> str:
    """Load HTML from a serps.json file at the given line index"""
    with open(serps_path) as f:
        for i, line in enumerate(f):
            if i == index:
                return json.loads(line)["html"]
    raise IndexError(f"No SERP at index {index} in {serps_path}")


def highlight_components(html: str) -> tuple[str, dict]:
    """Classify components and inject CSS highlights without altering DOM layout.

    Runs the extractor/classifier on a copy of the soup to identify and classify
    components. Tags the matching elements in the original soup with data
    attributes, then applies highlights via a <style> block. This avoids DOM
    mutations that break Google's CSS (e.g., oversized PAA chevrons).

    Returns:
        (modified_html, type_counts)
    """
    import copy

    soup = ws.make_soup(html)

    # Tag every element with a unique ID so we can map between copy and original
    for i, elem in enumerate(soup.find_all(True)):
        elem["data-ws-id"] = str(i)

    # Classify on a deep copy (extractor mutates the DOM)
    soup_copy = copy.copy(soup)
    ext = ws.Extractor(soup_copy)
    ext.extract_components()

    type_counts = {}
    classifications = []  # (data-ws-id, rank, type)
    for cmpt in ext.components:
        cmpt.classify_component()
        ctype = cmpt.type
        type_counts[ctype] = type_counts.get(ctype, 0) + 1
        ws_id = cmpt.elem.get("data-ws-id")
        if ws_id:
            classifications.append((ws_id, cmpt.cmpt_rank, ctype))

    # Apply data attributes to the original soup
    for ws_id, rank, ctype in classifications:
        elem = soup.find(attrs={"data-ws-id": ws_id})
        if elem:
            elem["data-ws-rank"] = str(rank)
            elem["data-ws-type"] = ctype

    # Clean up temporary IDs
    for elem in soup.find_all(attrs={"data-ws-id": True}):
        del elem["data-ws-id"]

    # Build highlight CSS
    style_rules = []
    for ws_id, rank, ctype in classifications:
        color = TYPE_COLORS.get(ctype, DEFAULT_COLOR)
        style_rules.append(
            f'[data-ws-rank="{rank}"] {{'
            f"  outline: 3px solid {color};"
            f"  outline-offset: -3px;"
            f"  border-radius: 4px;"
            f"  margin-top: 24px;"
            f"}}"
            f'[data-ws-rank="{rank}"]::before {{'
            f'  content: "{rank}: {ctype}";'
            f"  display: inline-block;"
            f"  font: bold 11px monospace;"
            f"  color: {color};"
            f"  background: white;"
            f"  padding: 0 4px;"
            f"  border: 1px solid {color};"
            f"  border-radius: 2px;"
            f"  position: relative;"
            f"  top: -14px;"
            f"  left: 4px;"
            f"  z-index: 9999;"
            f"}}"
        )

    highlight_style = soup.new_tag("style")
    highlight_style.string = "\n".join(style_rules)
    if soup.head:
        soup.head.append(highlight_style)
    else:
        soup.insert(0, highlight_style)

    return str(soup), type_counts


@app.command()
def main(
    data_dir: str = typer.Option(DEFAULT_DATA_DIR, help="Directory with serps.json"),
    index: int = typer.Option(0, help="SERP index (line number) in serps.json"),
    output: str = typer.Option("", help="Output path (default: data_dir/screenshot.png)"),
    highlight: bool = typer.Option(True, help="Highlight components with type labels"),
    width: int = typer.Option(1400, help="Browser viewport width"),
) -> None:
    """Screenshot a SERP from serps.json for visual inspection"""

    serps_path = os.path.join(data_dir, "serps.json")
    if not os.path.exists(serps_path):
        print(f"Error: {serps_path} not found")
        raise typer.Exit(1)

    output_path = output or os.path.join(data_dir, "screenshot.png")

    print(f"Loading SERP {index} from {serps_path}")
    html = load_serp_html(serps_path, index)

    if highlight:
        html, type_counts = highlight_components(html)
        print(f"Components: {dict(sorted(type_counts.items()))}")

    # Write HTML to temp file (data: URIs truncate large pages)
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False)
    try:
        tmp.write(html)
        tmp.close()

        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        opts = Options()
        opts.add_argument("--headless")
        opts.add_argument("--no-sandbox")
        opts.add_argument(f"--window-size={width},900")

        driver = webdriver.Chrome(options=opts)
        driver.get(f"file://{tmp.name}")

        # Resize to full page height
        height = driver.execute_script("return document.body.scrollHeight")
        driver.set_window_size(width, min(height + 200, 16000))

        driver.save_screenshot(output_path)
        driver.quit()

    finally:
        os.unlink(tmp.name)

    print(f"Screenshot: {output_path}")


if __name__ == "__main__":
    app()
