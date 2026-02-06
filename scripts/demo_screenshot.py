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
    "knowledge":              "#4285f4",
    "general":                "#34a853",
    "discussions_and_forums": "#fbbc05",
    "perspectives":           "#ea4335",
    "top_stories":            "#ff6d01",
    "people_also_ask":        "#46bdc6",
    "searches_related":       "#7b1fa2",
    "unknown":                "#d32f2f",
    "ad":                     "#f44336",
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
    """Extract, classify, and inject highlights into the actual HTML.

    Uses the same extractor and classifier pipeline as parse_serp, then
    modifies the BeautifulSoup elements in-place with colored borders
    and type labels before serializing back to HTML.

    Returns:
        (modified_html, type_counts)
    """
    from bs4 import Tag

    soup = ws.make_soup(html)
    ext = ws.Extractor(soup)
    ext.extract_components()

    type_counts = {}
    for cmpt in ext.components:
        cmpt.classify_component()
        ctype = cmpt.type
        type_counts[ctype] = type_counts.get(ctype, 0) + 1

        color = TYPE_COLORS.get(ctype, DEFAULT_COLOR)
        elem = cmpt.elem

        # Add border style to the element
        existing_style = elem.get("style", "")
        border_style = (
            f"border: 3px solid {color} !important; "
            f"border-radius: 4px !important; "
            f"margin-top: 24px !important; "
            f"position: relative !important; "
        )
        elem["style"] = f"{existing_style}; {border_style}"

        # Create a label tag
        label = soup.new_tag("div")
        label.string = f"{cmpt.cmpt_rank}: {ctype}"
        label["style"] = (
            f"position: absolute; top: -18px; left: 4px; z-index: 9999; "
            f"font: bold 11px monospace; color: {color}; "
            f"background: white; padding: 0 4px; "
            f"border: 1px solid {color}; border-radius: 2px; "
        )
        elem.insert(0, label)

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
