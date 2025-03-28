import typer
import WebSearcher as ws

# driver_executable_path locations:
# /opt/homebrew/Caskroom/chromedriver/133.0.6943.53 # Mac
# /opt/google/chrome/google-chrome  # Google Chrome 134.0.6998.88 | permissions error
# ~/.local/share/undetected_chromedriver/undetected_chromedriver # ChromeDriver 133.0.6943.141

app = typer.Typer()

@app.command()
def main(
    query: str = typer.Argument("why is the sky blue?", help="Search query to use"),
    method: str = typer.Argument("selenium", help="Search method to use: 'selenium' or 'requests'"),
    headless: bool = typer.Option(False, help="Run browser in headless mode"),
    use_subprocess: bool = typer.Option(False, help="Run browser in a separate subprocess"),
    version_main: int = typer.Option(133, help="Main version of Chrome to use"),
    ai_expand: bool = typer.Option(True, help="Expand AI overviews if present"),
    driver_executable_path: str = typer.Option("", help="Path to ChromeDriver executable"),
    output_prefix: str = typer.Option("output", help="Prefix for output files")
) -> None:
    typer.echo(f"query: {query}\nmethod: {method}")
    se = ws.SearchEngine(
        method=method,
        selenium_config={
            "headless": headless,
            "use_subprocess": use_subprocess,
            "driver_executable_path": driver_executable_path,
            "version_main": version_main,
        }
    )
    se.search(qry=query, ai_expand=ai_expand)
    se.parse_results()
    se.save_serp(append_to=f'{output_prefix}_serps.json')
    se.save_search(append_to=f'{output_prefix}_searches.json')
    se.save_parsed(append_to=f'{output_prefix}_parsed.json')

if __name__ == "__main__":
    app()