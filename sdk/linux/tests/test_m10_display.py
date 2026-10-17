import json
import os
import stat

import pytest

from musegadget.m10_display import apply_request
from musegadget.executor import Executor, Account


def test_display_chinese_roundtrip_and_private_file(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = apply_request({"op": "show", "text": "你好，Muse", "title": "行空板"})
    assert result["ok"]
    path = tmp_path / ".local/share/muse-m10/display.json"
    assert json.loads(path.read_text())["text"] == "你好，Muse"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not list(path.parent.glob(".display-*"))
    assert apply_request({"op": "clear"})["ok"]
    assert json.loads(path.read_text())["text"] == ""


@pytest.mark.parametrize("case", [
    {"op": "show", "text": ""}, {"op": "show", "text": 5},
    {"op": "show", "text": "x" * 2001},
    {"op": "show", "text": "ok", "title": "x" * 41}, {"op": "other"},
])
def test_invalid_display_request_does_not_write(monkeypatch, tmp_path, case):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert not apply_request(case)["ok"]
    assert not (tmp_path / ".local").exists()


def test_executor_uses_child_account_options(monkeypatch, tmp_path):
    account = Account.current()
    ex = Executor(Account(account.name, account.uid, account.gid, str(tmp_path)))
    original = ex._child_options
    def options():
        opts = original()
        opts["env"]["PYTHONPATH"] = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
        return opts
    monkeypatch.setattr(ex, "_child_options", options)
    assert ex.run("display.show", {"text": "工具调用"})["ok"]
    assert json.loads((tmp_path / ".local/share/muse-m10/display.json").read_text())["text"] == "工具调用"
    assert ex.run("display.clear", {})["ok"]
