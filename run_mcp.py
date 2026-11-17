#!/usr/bin/env python3
"""Launch the stdio MCP server from any working directory.

`python -m atelier.mcp_server` only works when the client starts the process inside the project
directory. Some clients (for example `opencode mcp add`) cannot set a working directory, so this
launcher puts the project root on the import path itself: `python /absolute/path/to/run_mcp.py`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from atelier.mcp_server import mcp  # noqa: E402

if __name__ == "__main__":
    mcp.run()
