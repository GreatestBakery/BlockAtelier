"""Use the locally configured OpenCode 2.x CLI as a model source."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from .base import LLMError, _mime


class OpenCodeClient:
    def __init__(self, cfg):
        self.cfg = cfg
        command = str(Path(cfg.get("opencode_path") or "opencode").expanduser())
        self.command = shutil.which(command)
        if not self.command and command == "opencode":
            # Finder-launched macOS apps do not inherit the terminal's PATH.
            self.command = next((str(p) for p in (
                Path.home() / ".opencode/bin/opencode",
                Path("/opt/homebrew/bin/opencode"), Path("/usr/local/bin/opencode")
            ) if p.is_file()), None)
        if not self.command:
            raise LLMError("找不到 opencode，请安装 opencode 2.x 或在设置中填写可执行文件路径。")

    def chat(self, system, messages, task=None):
        with tempfile.TemporaryDirectory(prefix="blockatelier-opencode-") as directory:
            root = Path(directory)
            # A model-only agent: the existing BlockAtelier pipeline executes the output.
            (root / "opencode.json").write_text(json.dumps({"agents": {"blockatelier": {
                "description": "Generate BlockAtelier building data", "mode": "primary",
                "system": system, "permissions": [{"action": "*", "resource": "*", "effect": "deny"}]
            }}}), "utf-8")
            args = [self.command, "run", "--format", "json", "--agent", "blockatelier", "--standalone"]
            if self.cfg.get("model"):
                args += ["--model", self.cfg["model"]]
            prompt = []
            for index, message in enumerate(messages):
                prompt.append(f"{message['role']}:\n{message['text']}")
                for number, image in enumerate(message.get("images", []) if self.cfg.get("vision", True) else []):
                    path = root / f"image-{index}-{number}.{_mime(image).split('/')[1]}"
                    path.write_bytes(image)
                    args += ["--file", str(path)]
            try:
                result = subprocess.run(args, input="\n\n".join(prompt), cwd=root,
                                        env={**os.environ, "PWD": str(root)},
                                        capture_output=True, text=True, encoding="utf-8", timeout=600)
            except (OSError, subprocess.TimeoutExpired) as error:
                raise LLMError(f"opencode: {error}") from error
            parts = []
            for line in result.stdout.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "error":
                    raise LLMError(f"opencode: {event.get('error')}")
                if event.get("type") == "text":
                    parts.append(event["part"]["text"])
            if result.returncode:
                raise LLMError(f"opencode: {result.stderr.strip()[:600] or result.stdout.strip()[:600]}")
            text = "".join(parts)
            if not text:
                raise LLMError("opencode 没有返回文本。")
            return text
