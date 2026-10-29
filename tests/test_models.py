"""Tests for config models and search params"""

import pytest

from WebSearcher.models.configs import (
    LogConfig,
    PatchrightConfig,
    RequestsConfig,
    SearchConfig,
    SearchMethod,
)
from WebSearcher.models.data import BaseResult
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
    assert SearchMethod.create("patchright") == SearchMethod.PATCHRIGHT
    assert SearchMethod.create("requests") == SearchMethod.REQUESTS


def test_search_method_case_insensitive():
    assert SearchMethod.create("PATCHRIGHT") == SearchMethod.PATCHRIGHT
    assert SearchMethod.create("Requests") == SearchMethod.REQUESTS


def test_search_method_from_enum():
    assert SearchMethod.create(SearchMethod.PATCHRIGHT) == SearchMethod.PATCHRIGHT


def test_search_method_default():
    assert SearchMethod.create(None) == SearchMethod.PATCHRIGHT


def test_search_method_invalid_string():
    with pytest.raises(ValueError, match="Invalid search method"):
        SearchMethod.create("invalid")


def test_search_method_invalid_type():
    with pytest.raises(TypeError, match="Expected string or SearchMethod"):
        SearchMethod.create(123)  # pyrefly: ignore[bad-argument-type]


# PatchrightConfig -------------------------------------------------------------


def test_patchright_config_defaults():
    cfg = PatchrightConfig()
    assert cfg.headless is False
    assert cfg.channel == "chrome"
    assert cfg.user_data_dir == ""


def test_patchright_config_create():
    cfg = PatchrightConfig.create({"headless": True, "channel": "chromium"})
    assert cfg.headless is True
    assert cfg.channel == "chromium"


# RequestsConfig ---------------------------------------------------------------


def test_requests_config_has_default_headers():
    cfg = RequestsConfig()
    assert "User-Agent" in cfg.headers
    assert "Host" in cfg.headers


def test_requests_config_sesh_defaults_to_none_and_is_not_dumped():
    cfg = RequestsConfig()
    assert cfg.sesh is None
    assert "sesh" not in cfg.model_dump()


# SearchConfig -----------------------------------------------------------------


def test_search_config_defaults():
    cfg = SearchConfig()
    assert cfg.method == SearchMethod.PATCHRIGHT
    assert isinstance(cfg.log, LogConfig)
    assert isinstance(cfg.patchright, PatchrightConfig)
    assert isinstance(cfg.requests, RequestsConfig)


# SearchParams -----------------------------------------------------------------


def test_search_params_url_basic():
    params = SearchParams.create({"qry": "hello world"})
    assert "q=hello+world" in params.url
    assert params.url.startswith("https://www.google.com/search?")


def test_search_params_url_with_lang():
    params = SearchParams.create({"qry": "test", "lang": "en"})
    assert "hl=en" in params.url


@pytest.mark.parametrize("start", [5, 10])
def test_search_params_url_with_start(start):
    params = SearchParams.create({"qry": "test", "start": start, "lang": "en"})
    assert params.url == f"https://www.google.com/search?q=test&start={start}&hl=en"


@pytest.mark.parametrize("start", [None, 0, -10])
def test_search_params_url_omits_nonpositive_start(start):
    config = {"qry": "test", "lang": "en", "loc": "Boston,Massachusetts,United States"}
    params = SearchParams.create({**config, "start": start})
    assert "start=" not in params.url
    assert params.url == SearchParams.create(config).url


def test_search_params_ignores_stale_num_results():
    params = SearchParams.create({"qry": "test", "num_results": 20})
    assert "num=" not in params.url


def test_search_params_url_with_location():
    params = SearchParams.create({"qry": "pizza", "loc": "Boston,Massachusetts,United States"})
    assert "uule=" in params.url


def test_search_params_url_omits_none():
    params = SearchParams.create({"qry": "test", "lang": None})
    assert "hl=" not in params.url
    assert "num=" not in params.url


def test_search_params_serp_id_is_hex():
    params = SearchParams.create({"qry": "test"})
    assert len(params.serp_id) == 56  # sha224 hex length
    assert all(c in "0123456789abcdef" for c in params.serp_id)


@pytest.mark.parametrize("start", [None, 0, 10])
def test_search_params_to_serp_output(start):
    params = SearchParams.create({"qry": "test query", "loc": "New York", "start": start})
    output = params.to_serp_output()
    assert output["qry"] == "test query"
    assert output["loc"] == "New York"
    assert output["start"] == start
    assert "url" in output
    assert "serp_id" in output


def test_search_params_special_chars():
    params = SearchParams.create({"qry": "cats & dogs"})
    assert "q=cats+%26+dogs" in params.url


# BaseResult -------------------------------------------------------------------


def test_base_result_defaults():
    r = BaseResult()
    assert r.type == "unclassified"
    assert r.sub_rank == 0
    assert r.title is None
    assert r.url is None
    assert r.details is None
