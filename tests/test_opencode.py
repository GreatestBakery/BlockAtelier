"""Model-source protocol checks; no provider credentials or live model needed."""
import json
from pathlib import Path
import subprocess

import pytest

from atelier import config
from atelier.llm import LLMError, extract_json, make_client
from atelier.llm.opencode import OpenCodeClient


def test_opencode_prompt_and_images(monkeypatch):
    monkeypatch.setattr("atelier.llm.opencode.shutil.which", lambda command: "/local/opencode")
    directories = []

    def run(args, **kwargs):
        root = kwargs["cwd"]
        assert kwargs["env"]["PWD"] == str(root)
        directories.append(root)
        assert args[:6] == ["/local/opencode", "run", "--format", "json", "--agent", "blockatelier"]
        assert args[6:9] == ["--standalone", "--model", "provider/model#high"]
        assert args[9] == "--file"
        assert Path(args[10]).read_bytes() == b"\x89PNGreference"
        assert kwargs["input"] == 'user:\n设计小屋\n\nassistant:\nprevious\n\nuser:\nrepair'
        agent = json.loads((root / "opencode.json").read_text())["agents"]["blockatelier"]
        assert agent["system"] == "return building JSON"
        assert agent["permissions"] == [{"action": "*", "resource": "*", "effect": "deny"}]
        return subprocess.CompletedProcess(args, 0, '\n'.join([
            'startup log', json.dumps({"type": "reasoning", "part": {"text": "hidden"}}),
            json.dumps({"type": "text", "part": {"text": '{"ok":'}}),
            json.dumps({"type": "text", "part": {"text": 'true}'}}),
        ]), "")

    monkeypatch.setattr("atelier.llm.opencode.subprocess.run", run)
    client = make_client({"provider": "opencode", "model": "provider/model#high"})
    assert extract_json(client.chat("return building JSON", [
        {"role": "user", "text": "设计小屋", "images": [b"\x89PNGreference"]},
        {"role": "assistant", "text": "previous"}, {"role": "user", "text": "repair"},
    ])) == {"ok": True}
    assert not directories[0].exists()


def test_opencode_default_model_without_vision(monkeypatch):
    monkeypatch.setattr("atelier.llm.opencode.shutil.which", lambda command: command)

    def run(args, **kwargs):
        assert "--model" not in args and "--file" not in args
        return subprocess.CompletedProcess(args, 0, '{"type":"text","part":{"text":"ok"}}', "")

    monkeypatch.setattr("atelier.llm.opencode.subprocess.run", run)
    assert make_client({"provider": "opencode", "vision": False}).chat(
        "sys", [{"role": "user", "text": "hi", "images": [b"image"]}]) == "ok"


@pytest.mark.parametrize("result,match", [
    (subprocess.CompletedProcess([], 1, "", "authentication failed"), "authentication failed"),
    (subprocess.CompletedProcess([], 0, '{"type":"error","error":{"message":"model missing"}}', ""), "model missing"),
    (subprocess.CompletedProcess([], 0, '{"type":"step_finish"}', ""), "没有返回文本"),
    (subprocess.TimeoutExpired("opencode", 600), "timed out"),
])
def test_opencode_errors(monkeypatch, result, match):
    monkeypatch.setattr("atelier.llm.opencode.shutil.which", lambda command: command)

    def run(*args, **kwargs):
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr("atelier.llm.opencode.subprocess.run", run)
    with pytest.raises(LLMError, match=match):
        make_client({"provider": "opencode"}).chat("sys", [{"role": "user", "text": "hi"}])


def test_opencode_finder_path(monkeypatch, tmp_path):
    monkeypatch.setattr("atelier.llm.opencode.shutil.which", lambda command: None)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    executable = tmp_path / ".opencode/bin/opencode"
    executable.parent.mkdir(parents=True)
    executable.touch()
    assert OpenCodeClient({}).command == str(executable)
    with pytest.raises(LLMError, match="找不到 opencode"):
        OpenCodeClient({"opencode_path": "/missing/opencode"})


def test_opencode_settings_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "WORKSPACE", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    from atelier.server import meta, set_config
    result = set_config({"provider": "opencode", "model": "", "opencode_path": "/local/opencode"})
    assert result["config"]["opencode_path"] == "/local/opencode"
    assert meta()["config"]["provider"] == "opencode"
    assert "opencode" in result["presets"]
    assert "api_key" not in result["config"]
