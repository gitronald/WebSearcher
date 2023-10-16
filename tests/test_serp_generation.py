import pytest
import glob
import WebSearcher as ws

from syrupy.extensions.json import JSONSnapshotExtension

@pytest.fixture
def snapshot_json(snapshot):
    return snapshot.use_extension(JSONSnapshotExtension)

def pytest_generate_tests(metafunc):
    file_list = glob.glob('./tests/html_pages/*.html')
    metafunc.parametrize("file_name", file_list )

def test_parsing(snapshot_json, file_name):
    # read html
    with open(file_name) as file:
        html = file.read()
    
    results = ws.parse_serp(html, make_soup=True)
    assert results == snapshot_json
