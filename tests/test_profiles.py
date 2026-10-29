"""Persistent browser profiles (plan 054): config, cookie handling, CLI, and save/load."""

import importlib
import logging
import subprocess
import time
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from WebSearcher.demos import cli
from WebSearcher.models.configs import PatchrightConfig
from WebSearcher.models.data import ParsedSERP
from WebSearcher.models.searches import SearchParams
from WebSearcher.searchers.patchright_searcher import PatchrightSearcher, prepare_profile_dir

# The demos package re-exports the `search` function under the module's name
demo_search = importlib.import_module("WebSearcher.demos.search")
LOG = logging.getLogger("test_profiles")

# Config ------------------------------------------------------------------------


def test_clear_cookies_defaults_true():
    assert PatchrightConfig().clear_cookies is True


def test_new_profile_dir_is_git_ignored(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    profile = tmp_path / "nested" / ".ws_profile"
    prepare_profile_dir(profile)
    (profile / "Cookies").write_text("secret")
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert status.stdout == ""


def test_existing_profile_dir_is_left_untouched(tmp_path):
    prepare_profile_dir(tmp_path)
    assert list(tmp_path.iterdir()) == []


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


def _run_cli(monkeypatch, argv: list[str], events: list[str] | None = None) -> dict[str, Any]:
    """Run the CLI on fake engines, recording each close in ``events``.

    Pass the list given to ``_fake_input`` to record prompts and closes in order.
    """
    events = [] if events is None else events
    captured: dict[str, Any] = {}

    class _Engine:
        def close(self) -> None:
            events.append("close")

    def fake_search(query, method, **kwargs):
        captured.update(kwargs, query=query, method=method)
        return _Engine()

    def fake_searches(**kwargs):
        captured.update(kwargs)
        return _Engine()

    monkeypatch.setattr(cli, "search", fake_search)
    monkeypatch.setattr(cli, "searches", fake_searches)
    cli.main(argv)
    return captured


def _fake_input(events: list[str], raises: type[BaseException] | None = None):
    def fake_input(prompt: str = "") -> str:
        events.append("input")
        if raises is not None:
            raise raises
        return ""

    return fake_input


def test_cli_user_data_dir_defaults_off(monkeypatch):
    assert _run_cli(monkeypatch, ["search", "q"])["user_data_dir"] is None


@pytest.mark.parametrize("start", [None, 0, 10])
def test_cli_search_start(monkeypatch, start):
    argv = ["search", "q"]
    if start is not None:
        argv.extend(["--start", str(start)])
    assert _run_cli(monkeypatch, argv)["start"] == start


@pytest.mark.parametrize("command", [["searches"], ["locations", "q"], ["headers", "q"]])
def test_cli_start_only_on_search(monkeypatch, command):
    with pytest.raises(SystemExit) as exc:
        _run_cli(monkeypatch, [*command, "--start", "10"])
    assert exc.value.code == 2


@pytest.mark.parametrize("start", [None, 0, 10])
def test_demo_search_passes_start_and_prints_header(monkeypatch, tmp_path, capsys, start):
    engine = Mock()
    engine.parsed = ParsedSERP()
    engine.serp = {"url": "https://www.google.com/search?q=q"}
    monkeypatch.setattr(demo_search, "_search_engine", lambda *args: engine)
    assert demo_search.search("q", data_dir=str(tmp_path), start=start) is engine
    engine.search.assert_called_once_with("q", ai_expand=True, start=start)
    output = capsys.readouterr().out
    if start is None:
        assert "Start:" not in output
    else:
        assert f"Start: {start}\n" in output


def test_cli_bare_user_data_dir_uses_default(monkeypatch):
    got = _run_cli(monkeypatch, ["search", "q", "--user-data-dir"])
    assert got["user_data_dir"] == ".ws_profile"


def test_cli_user_data_dir_path(monkeypatch, tmp_path):
    got = _run_cli(monkeypatch, ["search", "q", "--user-data-dir", str(tmp_path)])
    assert got["user_data_dir"] == str(tmp_path)


def test_cli_user_data_dir_rejects_requests(monkeypatch):
    with pytest.raises(SystemExit):
        _run_cli(monkeypatch, ["search", "q", "requests", "--user-data-dir"])


def test_cli_closes_without_waiting_by_default(monkeypatch):
    events: list[str] = []
    monkeypatch.setattr("builtins.input", _fake_input(events))
    _run_cli(monkeypatch, ["search", "q"], events)
    assert events == ["close"]


@pytest.mark.parametrize("command", [["search", "q"], ["searches"]])
@pytest.mark.parametrize("raises", [None, EOFError, KeyboardInterrupt])
def test_cli_leave_open_waits_for_input_then_closes(monkeypatch, command, raises):
    events: list[str] = []
    monkeypatch.setattr("builtins.input", _fake_input(events, raises))
    _run_cli(monkeypatch, [*command, "--leave-open"], events)
    assert events == ["input", "close"]


def test_cli_leave_open_rejects_requests(monkeypatch):
    with pytest.raises(SystemExit):
        _run_cli(monkeypatch, ["search", "q", "requests", "--leave-open"])


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
    assert (profile / ".gitignore").read_text().endswith("*\n")

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
