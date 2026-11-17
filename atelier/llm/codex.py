"""Use Codex CLI with ChatGPT sign-in for the shared model pipeline."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from .base import LLMError, _mime


class CodexClient:
    def __init__(self, cfg):
        self.cfg = cfg
        command = str(Path(cfg.get("codex_path") or "codex").expanduser())
        self.command = shutil.which(command)
        if not self.command and command == "codex":
            # Finder does not inherit the terminal's PATH.
            self.command = next((str(p) for p in (
                Path.home() / ".local/bin/codex",
                Path("/opt/homebrew/bin/codex"), Path("/usr/local/bin/codex")
            ) if p.is_file()), None)
        if not self.command:
            raise LLMError("找不到 Codex，请安装 Codex CLI 或在设置中填写可执行文件路径。")

    def chat(self, system, messages, task=None):
        with tempfile.TemporaryDirectory(prefix="blockatelier-codex-") as directory:
            root = Path(directory)
            output = root / "reply.txt"
            # Keep authentication, but do not load user agents, MCP servers or project config.
            args = [self.command, "exec", "--ignore-user-config", "--ephemeral",
                    "--skip-git-repo-check", "--sandbox", "read-only", "--color", "never",
                    "--output-last-message", str(output),
                    "-c", 'forced_login_method="chatgpt"',
                    "-c", "features.shell_tool=false", "-c", "features.multi_agent=false",
                    "-c", 'web_search="disabled"',
                    "-c", "developer_instructions=" + json.dumps(system, ensure_ascii=False)]
            if self.cfg.get("model"):
                args += ["--model", self.cfg["model"]]
            prompt = []
            for index, message in enumerate(messages):
                prompt.append(f"{message['role']}:\n{message['text']}")
                for number, image in enumerate(message.get("images", []) if self.cfg.get("vision", True) else []):
                    path = root / f"image-{index}-{number}.{_mime(image).split('/')[1]}"
                    path.write_bytes(image)
                    args += ["--image", str(path)]
            try:
                result = subprocess.run(args + ["-"], input="\n\n".join(prompt), cwd=root,
                                        env={**os.environ, "PWD": str(root)},
                                        capture_output=True, text=True, encoding="utf-8", timeout=600)
            except (OSError, subprocess.TimeoutExpired) as error:
                raise LLMError(f"Codex: {error}") from error
            if result.returncode:
                raise LLMError(f"Codex: {result.stderr.strip()[-1200:] or result.stdout.strip()[-1200:]}")
            text = output.read_text("utf-8").strip() if output.exists() else ""
            if not text:
                raise LLMError("Codex 没有返回文本，请先运行 codex login 并使用 ChatGPT 账号登录。")
            return text
