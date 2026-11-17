"""Codex model-source protocol and shared settings regression checks."""
import json
from pathlib import Path
import subprocess

import pytest

from atelier import config
from atelier.llm import LLMError, extract_json, make_client
from atelier.llm.codex import CodexClient


def test_codex_prompt_and_images(monkeypatch):
    monkeypatch.setattr("atelier.llm.codex.shutil.which", lambda command: "/local/codex")
    directories = []

    def run(args, **kwargs):
        root = kwargs["cwd"]
        directories.append(root)
        assert kwargs["env"]["PWD"] == str(root)
        assert args[:2] == ["/local/codex", "exec"] and args[-1] == "-"
        assert "--ignore-user-config" in args and "--ephemeral" in args
        assert args[args.index("--sandbox") + 1] == "read-only"
        assert 'forced_login_method="chatgpt"' in args
        assert "features.shell_tool=false" in args
        assert args[args.index("--model") + 1] == "test-model"
        assert Path(args[args.index("--image") + 1]).read_bytes() == b"\x89PNGreference"
        instruction = next(a for a in args if a.startswith("developer_instructions="))
        assert json.loads(instruction.split("=", 1)[1]) == '只返回 JSON\n"quoted"'
        assert kwargs["input"] == "user:\n设计小屋\n\nassistant:\nprevious\n\nuser:\nrepair"
        Path(args[args.index("--output-last-message") + 1]).write_text('{"ok":true}', "utf-8")
        return subprocess.CompletedProcess(args, 0, "progress must not enter JSON", "")

    monkeypatch.setattr("atelier.llm.codex.subprocess.run", run)
    client = make_client({"provider": "codex", "model": "test-model"})
    assert extract_json(client.chat('只返回 JSON\n"quoted"', [
        {"role": "user", "text": "设计小屋", "images": [b"\x89PNGreference"]},
        {"role": "assistant", "text": "previous"}, {"role": "user", "text": "repair"},
    ])) == {"ok": True}
    assert not directories[0].exists()


def test_codex_default_model_and_vision_disabled(monkeypatch):
    monkeypatch.setattr("atelier.llm.codex.shutil.which", lambda command: command)

    def run(args, **kwargs):
        assert "--model" not in args and "--image" not in args
        Path(args[args.index("--output-last-message") + 1]).write_text("ok", "utf-8")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("atelier.llm.codex.subprocess.run", run)
    assert make_client({"provider": "codex", "vision": False}).chat(
        "sys", [{"role": "user", "text": "hi", "images": [b"image"]}]) == "ok"


@pytest.mark.parametrize("result,match", [
    (subprocess.CompletedProcess([], 1, "", "ChatGPT login required"), "ChatGPT login required"),
    (subprocess.CompletedProcess([], 0, "progress", ""), "没有返回文本"),
    (subprocess.TimeoutExpired("codex", 600), "timed out"),
    (OSError("cannot execute"), "cannot execute"),
])
def test_codex_errors(monkeypatch, result, match):
    monkeypatch.setattr("atelier.llm.codex.shutil.which", lambda command: command)

    def run(*args, **kwargs):
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr("atelier.llm.codex.subprocess.run", run)
    with pytest.raises(LLMError, match=match):
        make_client({"provider": "codex"}).chat("sys", [{"role": "user", "text": "hi"}])


def test_codex_finder_path(monkeypatch, tmp_path):
    monkeypatch.setattr("atelier.llm.codex.shutil.which", lambda command: None)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    executable = tmp_path / ".local/bin/codex"
    executable.parent.mkdir(parents=True)
    executable.touch()
    assert CodexClient({}).command == str(executable)
    with pytest.raises(LLMError, match="找不到 Codex"):
        CodexClient({"codex_path": "/missing/codex"})


def test_codex_settings_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "WORKSPACE", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    from atelier.server import meta, set_config
    result = set_config({"provider": "codex", "model": "", "codex_path": "/local/codex"})
    assert result["config"]["codex_path"] == "/local/codex"
    assert meta()["config"]["provider"] == "codex"
    assert {"codex", "opencode", "openai", "mock"} <= result["presets"].keys()
    assert "api_key" not in result["config"]
