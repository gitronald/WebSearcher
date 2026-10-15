"""Persistent browser profiles (plan 054): config, cookie handling, CLI, and save/load."""

import importlib
import logging
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from WebSearcher import utils
from WebSearcher.demos import cli
from WebSearcher.models.configs import PatchrightConfig
from WebSearcher.models.searches import SearchParams
from WebSearcher.searchers.patchright_searcher import PatchrightSearcher

# The demos package re-exports the `search` function under the module's name
demo_search = importlib.import_module("WebSearcher.demos.search")
LOG = logging.getLogger("test_profiles")

# Config ------------------------------------------------------------------------


def test_clear_cookies_defaults_true():
    assert PatchrightConfig().clear_cookies is True


def test_default_user_data_dir_names_the_app():
    path = utils.default_user_data_dir()
    assert path.parts[-2:] == ("WebSearcher", "profile")


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="XDG paths are Linux-only")
def test_default_user_data_dir_follows_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert utils.default_user_data_dir() == tmp_path / "WebSearcher" / "profile"


# Cookie clearing in send_request -----------------------------------------------


class _FakeContext:
    def __init__(self) -> None:
        self.cleared = 0

    def clear_cookies(self) -> None:
        self.cleared += 1


class _FakePage:
    url = "about:blank"

    def goto(self, url: str, wait_until: str) -> None:
        raise RuntimeError("no navigation in tests")


def _searcher_with_fakes(**config: Any) -> tuple[PatchrightSearcher, _FakeContext]:
    searcher = PatchrightSearcher(PatchrightConfig(**config), LOG)
    context = _FakeContext()
    searcher.context = context
    searcher.page = _FakePage()
    return searcher, context


@pytest.mark.parametrize(("clear_cookies", "expected"), [(True, 1), (False, 0)])
def test_send_request_clears_cookies_per_config(clear_cookies, expected):
    searcher, context = _searcher_with_fakes(clear_cookies=clear_cookies)
    searcher.send_request(SearchParams.create({"qry": "test"}))
    assert context.cleared == expected


# CLI and demo wiring -----------------------------------------------------------


def _run_cli(monkeypatch, argv: list[str]) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    class _Engine:
        def close(self) -> None:
            pass

    def fake_search(query, method, **kwargs):
        captured.update(kwargs, query=query, method=method)
        return _Engine()

    monkeypatch.setattr(cli, "search", fake_search)
    cli.main(argv)
    return captured


def test_cli_user_data_dir_defaults_off(monkeypatch):
    assert _run_cli(monkeypatch, ["search", "q"])["user_data_dir"] is None


def test_cli_bare_user_data_dir_uses_default(monkeypatch):
    got = _run_cli(monkeypatch, ["search", "q", "--user-data-dir"])
    assert got["user_data_dir"] == str(utils.default_user_data_dir())


def test_cli_user_data_dir_path(monkeypatch, tmp_path):
    got = _run_cli(monkeypatch, ["search", "q", "--user-data-dir", str(tmp_path)])
    assert got["user_data_dir"] == str(tmp_path)


def test_cli_user_data_dir_rejects_requests(monkeypatch):
    with pytest.raises(SystemExit):
        _run_cli(monkeypatch, ["search", "q", "requests", "--user-data-dir"])


def test_demo_engine_keeps_cookies_on_persistent_profile(monkeypatch):
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(demo_search.ws, "SearchEngine", lambda **kw: calls.append(kw))
    demo_search._search_engine("patchright", None)
    demo_search._search_engine("patchright", "/some/profile")
    assert calls[0] == {"method": "patchright"}
    assert calls[1]["patchright_config"] == {
        "user_data_dir": "/some/profile",
        "clear_cookies": False,
    }


# Profile save/load with a real browser (local only, no navigation) -------------

COOKIE_URL = "https://example.com"


def _launch(user_data_dir: str = "") -> PatchrightSearcher:
    searcher = PatchrightSearcher(PatchrightConfig(headless=True, user_data_dir=user_data_dir), LOG)
    try:
        searcher.init_driver()
    except Exception as e:
        searcher.cleanup()
        pytest.skip(f"Chrome unavailable for patchright: {e}")
    return searcher


def _set_cookie(searcher: PatchrightSearcher) -> None:
    searcher.context.add_cookies(
        [{"name": "ws_probe", "value": "1", "url": COOKIE_URL, "expires": time.time() + 3600}]
    )


def _cookie_names(searcher: PatchrightSearcher) -> set[str]:
    return {c["name"] for c in searcher.context.cookies(COOKIE_URL)}


def test_persistent_profile_saves_and_reloads_cookies(tmp_path):
    profile = tmp_path / "profile"
    first = _launch(str(profile))
    _set_cookie(first)
    first.cleanup()
    assert profile.is_dir()  # a persistent profile is kept on close

    second = _launch(str(profile))
    try:
        assert "ws_probe" in _cookie_names(second)
    finally:
        second.cleanup()


def test_temp_profile_is_removed_and_not_reused():
    first = _launch()
    tmp_profile = Path(first._tmp_profile)
    _set_cookie(first)
    first.cleanup()
    assert not tmp_profile.exists()

    second = _launch()
    try:
        assert "ws_probe" not in _cookie_names(second)
    finally:
        second.cleanup()


def test_persistent_profile_expands_user(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    searcher = _launch("~/ws-profile")
    searcher.cleanup()
    assert (tmp_path / "ws-profile").is_dir()
