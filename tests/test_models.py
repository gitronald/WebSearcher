"""Tests for config models and search params"""

import pytest

from WebSearcher.models.configs import (
    LogConfig,
    RequestsConfig,
    SearchConfig,
    SearchMethod,
    SeleniumConfig,
)
from WebSearcher.models.data import BaseResult, DetailsItem, DetailsList
from WebSearcher.models.searches import SearchParams

# BaseConfig.create ------------------------------------------------------------


def test_base_config_create_from_dict():
    cfg = LogConfig.create({"console": False, "console_level": "DEBUG"})
    assert cfg.console is False
    assert cfg.console_level == "DEBUG"


def test_base_config_create_from_instance():
    original = LogConfig(console=False)
    result = LogConfig.create(original)
    assert result is original


def test_base_config_create_default():
    cfg = LogConfig.create()
    assert cfg.console is True  # default value


def test_base_config_create_none():
    cfg = LogConfig.create(None)
    assert isinstance(cfg, LogConfig)


# SearchMethod -----------------------------------------------------------------


def test_search_method_from_string():
    assert SearchMethod.create("selenium") == SearchMethod.SELENIUM
    assert SearchMethod.create("requests") == SearchMethod.REQUESTS


def test_search_method_case_insensitive():
    assert SearchMethod.create("SELENIUM") == SearchMethod.SELENIUM
    assert SearchMethod.create("Requests") == SearchMethod.REQUESTS


def test_search_method_from_enum():
    assert SearchMethod.create(SearchMethod.SELENIUM) == SearchMethod.SELENIUM


def test_search_method_default():
    assert SearchMethod.create(None) == SearchMethod.SELENIUM


def test_search_method_invalid_string():
    with pytest.raises(ValueError, match="Invalid search method"):
        SearchMethod.create("invalid")


def test_search_method_invalid_type():
    with pytest.raises(TypeError, match="Expected string or SearchMethod"):
        SearchMethod.create(123)


# SeleniumConfig ---------------------------------------------------------------


def test_selenium_config_defaults():
    cfg = SeleniumConfig()
    assert cfg.headless is False
    assert cfg.version_main == 144
    assert cfg.use_subprocess is False


def test_selenium_config_create():
    cfg = SeleniumConfig.create({"headless": True, "version_main": 130})
    assert cfg.headless is True
    assert cfg.version_main == 130


# RequestsConfig ---------------------------------------------------------------


def test_requests_config_has_default_headers():
    cfg = RequestsConfig()
    assert "User-Agent" in cfg.headers
    assert "Host" in cfg.headers


def test_requests_config_sesh():
    cfg = RequestsConfig()
    sesh = cfg.sesh
    assert "User-Agent" in sesh.headers


# SearchConfig -----------------------------------------------------------------


def test_search_config_defaults():
    cfg = SearchConfig()
    assert cfg.method == SearchMethod.SELENIUM
    assert isinstance(cfg.log, LogConfig)
    assert isinstance(cfg.selenium, SeleniumConfig)
    assert isinstance(cfg.requests, RequestsConfig)


# SearchParams -----------------------------------------------------------------


def test_search_params_url_basic():
    params = SearchParams.create({"qry": "hello world"})
    assert "q=hello+world" in params.url
    assert params.url.startswith("https://www.google.com/search?")


def test_search_params_url_with_lang():
    params = SearchParams.create({"qry": "test", "lang": "en"})
    assert "hl=en" in params.url


def test_search_params_url_with_num_results():
    params = SearchParams.create({"qry": "test", "num_results": 20})
    assert "num=20" in params.url


def test_search_params_url_with_location():
    params = SearchParams.create({"qry": "pizza", "loc": "Boston,Massachusetts,United States"})
    assert "uule=" in params.url


def test_search_params_url_omits_none():
    params = SearchParams.create({"qry": "test", "lang": None, "num_results": None})
    assert "hl=" not in params.url
    assert "num=" not in params.url


def test_search_params_serp_id_is_hex():
    params = SearchParams.create({"qry": "test"})
    assert len(params.serp_id) == 56  # sha224 hex length
    assert all(c in "0123456789abcdef" for c in params.serp_id)


def test_search_params_to_serp_output():
    params = SearchParams.create({"qry": "test query", "loc": "New York"})
    output = params.to_serp_output()
    assert output["qry"] == "test query"
    assert output["loc"] == "New York"
    assert "url" in output
    assert "serp_id" in output


def test_search_params_special_chars():
    params = SearchParams.create({"qry": "cats & dogs"})
    assert "q=cats+%26+dogs" in params.url


# DetailsItem / DetailsList ----------------------------------------------------


def test_details_item_model_dump():
    item = DetailsItem(url="https://example.com", title="Example", text="desc")
    d = item.model_dump()
    assert d == {"url": "https://example.com", "title": "Example", "text": "desc", "misc": {}}


def test_details_list_append_valid():
    dl = DetailsList()
    dl.append(DetailsItem(title="a"))
    dl.append(DetailsItem(title="b"))
    assert len(dl) == 2


def test_details_list_append_invalid():
    dl = DetailsList()
    with pytest.raises(TypeError, match="Expected DetailsItem"):
        dl.append({"title": "not a DetailsItem"})


def test_details_list_to_dicts():
    dl = DetailsList()
    dl.append(DetailsItem(url="/a", title="A"))
    dl.append(DetailsItem(url="/b", title="B"))
    dicts = dl.to_dicts()
    assert len(dicts) == 2
    assert dicts[0]["url"] == "/a"
    assert dicts[1]["title"] == "B"


# BaseResult -------------------------------------------------------------------


def test_base_result_defaults():
    r = BaseResult()
    assert r.type == "unclassified"
    assert r.sub_rank == 0
    assert r.title is None
    assert r.url is None
    assert r.error is None
