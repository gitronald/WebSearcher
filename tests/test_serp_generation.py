import glob
import pytest
import WebSearcher as ws

from syrupy.extensions.json import JSONSnapshotExtension

@pytest.fixture
def snapshot_json(snapshot):
    """Store or retrieve json for init or testing"""
    return snapshot.use_extension(JSONSnapshotExtension)

def pytest_generate_tests(metafunc):
    """Create file_name list that test_parsing inputs"""
    file_list = glob.glob("./data/demo-ws-v0.3.10/html/*")
    metafunc.parametrize("file_name", file_list)

def test_parsing(snapshot_json, file_name):
    """Parse each file_name and compare to existing snapshot"""
    soup = ws.load_soup(file_name)
    results = ws.parse_serp(soup)
    assert results == snapshot_json
