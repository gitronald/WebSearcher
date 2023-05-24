import pytest
import json
import WebSearcher as ws

from syrupy.extensions.json import JSONSnapshotExtension

@pytest.fixture
def snapshot_json(snapshot):
    return snapshot.use_extension(JSONSnapshotExtension)

def test_serp_1684837514_is_correct(snapshot_json):
    # TODO: run for all dates in the test_html_pages folder
    html_file_name = './tests/test_html_pages/1684837514.html'

    # read html
    with open(html_file_name) as file:
        html = file.read()
    
    # Initialize crawler
    se = ws.SearchEngine()
    
    # Conduct Search
    se.mock_search(html)

    # Parse Results
    se.parse_results()

    # results_as_json = json.dumps(se.results, indent=4)

    assert se.results == snapshot_json

def test_serp_1684959591_is_correct(snapshot_json):
    # TODO: run for all dates in the test_html_pages folder
    html_file_name = './tests/test_html_pages/1684959591.html'

    # read html
    with open(html_file_name) as file:
        html = file.read()
    
    # Initialize crawler
    se = ws.SearchEngine()
    
    # Conduct Search
    se.mock_search(html)

    # Parse Results
    se.parse_results()

    assert se.results == snapshot_json

# import os
# import pytest

# def test_snapshot(file_path):
#     # Your test logic here
#     assert file_path.endswith('.html')  # Example test condition

# # Discover files and run tests
# @pytest.mark.parametrize('file_path', [
#     os.path.join('tests', 'test_html_pages', file_name)
#     for file_name in os.listdir('tests/test_html_pages')
#     if file_name.endswith('.html')
# ])

# def test_snapshots(file_path):
#     test_snapshot(file_path)
