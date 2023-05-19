import pytest
import json
import WebSearcher as ws

def test_serp_generation_is_correct():
    # TODO: run for all dates in the test_html_pages folder
    date = '1684516032'

    html_file_name = './tests/test_html_pages/{0}.html'.format(date)
    serp_json_file_name = './tests/test_serps_json/{0}.json'.format(date)

    # read html
    with open(html_file_name) as file:
        html = file.read()
    
    # Initialize crawler
    se = ws.SearchEngine()
    
    # Conduct Search
    se.mock_search(html)

    # Parse Results
    se.parse_results()

    # Check if results are correct
    assert se.results == json.load(open(serp_json_file_name))
