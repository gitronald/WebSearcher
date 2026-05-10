"""Serve a saved SERP HTML on localhost for visual inspection."""

import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import bs4
import typer

import WebSearcher as ws

DEFAULT_DATA_DIR = str(Path("data") / f"demo-ws-v{ws.__version__}")

_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)

_OVERLAY_RESET_CSS = """
<style>
  html, body { overflow: auto !important; height: auto !important; }
</style>
"""


def strip_overlays(html: str) -> str:
    """Remove dialog elements and lightbox/scrim wrappers that lock scrolling."""
    soup = bs4.BeautifulSoup(html, "lxml")
    # Walk up 2 ancestors from each dialog to also remove the backdrop wrapper.
    # Markup pattern: <div class="mcPPZ ..."><span jsslot><div role="dialog">…
    for el in soup.select('[role="dialog"]'):
        target = el
        for _ in range(2):
            parent = target.parent
            if parent is None or parent.name in ("body", "html", "[document]"):
                break
            target = parent
        target.decompose()
    # Snackbars and stray modal elements
    for el in soup.select("g-snackbar, g-dialog, [aria-modal]"):
        el.decompose()
    # Lightbox container (#lb) and its scrim (.kJFf0c) — the active state
    # paints a full-viewport gray overlay that locks scrolling.
    for el in soup.select("#lb, .kJFf0c"):
        el.decompose()
    # Scroll-lock class on <html> (CSS: position:fixed; overflow:hidden) and
    # the saved-scroll-offset inline style applied alongside it.
    html_el = soup.find("html")
    if html_el:
        for attr in ("class", "style"):
            if attr in html_el.attrs:
                del html_el[attr]
    return str(soup)


app = typer.Typer()


@app.command()
def main(
    query: str = typer.Argument(None, help="Query whose saved SERP to serve"),
    data_dir: str = typer.Option(DEFAULT_DATA_DIR, help="Directory containing serps.json"),
    port: int = typer.Option(8765, help="localhost port"),
    list_queries: bool = typer.Option(False, "--list", help="List available queries and exit"),
    keep_scripts: bool = typer.Option(
        False, "--keep-scripts", help="Keep <script> tags (default: strip to avoid JS overlays)"
    ),
) -> None:
    fp = Path(data_dir) / "serps.json"
    if not fp.exists():
        typer.echo(f"Not found: {fp}")
        raise typer.Exit(1)

    queries: list[str] = []
    html: str | None = None
    with open(fp) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            qry = rec.get("qry")
            queries.append(qry)
            if query and qry == query:
                html = rec.get("html")

    if list_queries or not query:
        for q in queries:
            typer.echo(q)
        raise typer.Exit(0)

    if html is None:
        typer.echo(f"No SERP found for query {query!r}. Use --list to see available queries.")
        raise typer.Exit(1)

    if not keep_scripts:
        html = _SCRIPT_RE.sub("", html)

    html = strip_overlays(html)

    # Body-scroll override in case anything else locks it
    if "</head>" in html:
        html = html.replace("</head>", _OVERLAY_RESET_CSS + "</head>", 1)
    else:
        html = _OVERLAY_RESET_CSS + html

    body = html.encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args, **_kwargs) -> None:
            pass

    httpd = HTTPServer(("127.0.0.1", port), Handler)
    typer.echo(f"Serving SERP for {query!r} at http://127.0.0.1:{port}/  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        typer.echo("\nstopped")


if __name__ == "__main__":
    app()
