import pytest
import json
import WebSearcher as ws

def test_serp_1684516032_is_correct(snapshot):
    # TODO: run for all dates in the test_html_pages folder
    html_file_name = './tests/test_html_pages/1684516032.html'

    # read html
    with open(html_file_name) as file:
        html = file.read()
    
    # Initialize crawler
    se = ws.SearchEngine()
    
    # Conduct Search
    se.mock_search(html)

    # Parse Results
    se.parse_results()

    results_as_json = json.dumps(se.results, indent=4)

    assert results_as_json == snapshot
