#!/usr/bin/env python3
"""BlockAtelier desktop launcher; native window with a private local backend."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request


def workspace_path() -> Path:
    override = os.environ.get('ATELIER_WORKSPACE')
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'BlockAtelier'
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'BlockAtelier'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'BlockAtelier'


def native_error(message: str) -> None:
    logging.error(message)
    if sys.platform == 'darwin':
        import subprocess
        # Pass the message as argv, never interpolate it into AppleScript source.
        script = 'on run argv\ndisplay alert "BlockAtelier" message (item 1 of argv) as critical\nend run'
        subprocess.run(['/usr/bin/osascript', '-e', script, message], check=False)
    elif sys.stderr:
        print(message, file=sys.stderr)


class DesktopApi:
    def __init__(self, base_url: str, workspace: Path):
        self._base_url = base_url
        self._workspace = workspace
        self._window = None
        self._lock = threading.Lock()

    def _file_url(self, value: str) -> tuple[str, str]:
        parsed = urllib.parse.urlsplit(str(value))
        base = urllib.parse.urlsplit(self._base_url)
        if parsed.scheme and (parsed.scheme != base.scheme or parsed.netloc != base.netloc):
            raise ValueError('Only files from this BlockAtelier session can be opened.')
        if parsed.netloc and parsed.netloc != base.netloc:
            raise ValueError('Invalid file origin.')
        path = urllib.parse.unquote(parsed.path)
        if not re.fullmatch(r'/api/builds/[\w-]+/file/[\w.-]+', path) or '..' in path:
            raise ValueError('Invalid build file path.')
        name = path.rsplit('/', 1)[-1]
        return self._base_url + parsed.path + '?download=1', name

    def get_preferences(self) -> dict:
        try:
            data = json.loads((self._workspace / 'desktop.json').read_text('utf-8'))
            return {'language': data.get('language')} if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def set_ui_language(self, language: str) -> bool:
        if language not in ('zh-CN', 'en'):
            return False
        with self._lock:
            path = self._workspace / 'desktop.json'
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps({'language': language}), 'utf-8')
            temporary.replace(path)
        return True

    def install_resources(self) -> bool:
        from atelier.desktop_resources import ensure_profile
        from atelier import config
        with self._lock:
            ensure_profile(config.DATA, '1.21.11')
        self._window.load_url(self._base_url)
        return True

    def save_file(self, value: str) -> dict:
        import webview
        url, name = self._file_url(value)
        selection = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=name)
        if not selection:
            return {'cancelled': True}
        path = Path(selection if isinstance(selection, str) else selection[0])
        temporary = None
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.blockatelier-', delete=False) as output:
                    temporary = Path(output.name)
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
            temporary.replace(path)
            return {'cancelled': False, 'path': str(path)}
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def copy_text(self, text: str) -> bool:
        if sys.platform == 'darwin':
            from AppKit import NSPasteboard, NSPasteboardTypeString
            pasteboard = NSPasteboard.generalPasteboard()
            pasteboard.clearContents()
            return bool(pasteboard.setString_forType_(str(text), NSPasteboardTypeString))
        import subprocess
        if os.name == 'nt':
            subprocess.run(['clip'], input=str(text), text=True, check=True)
            return True
        return False

    def open_preview(self, value: str) -> bool:
        import webview
        url, name = self._file_url(value)
        if not name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            raise ValueError('Only preview images can be opened in a preview window.')
        webview.create_window('BlockAtelier — ' + name, url=url.replace('?download=1', ''), width=1000, height=760)
        return True


def prepare_environment(log_name: str) -> Path:
    """Point the shared core at the desktop storage. The window and `--mcp` modes both start here,
    so they read the same configuration, version profiles, and build library."""
    workspace = workspace_path()
    workspace.mkdir(parents=True, exist_ok=True)
    os.environ['ATELIER_WORKSPACE'] = str(workspace)
    os.environ.setdefault('ATELIER_DATA', str(workspace / 'data'))
    # Finder-launched applications do not inherit an interactive shell's PATH.
    os.environ['PATH'] = os.pathsep.join(['/opt/homebrew/bin', '/usr/local/bin', os.environ.get('PATH', '')])
    logging.basicConfig(filename=str(workspace / log_name), level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s', force=True)
    return workspace


def detect_blender() -> None:
    from atelier import config
    if sys.platform == 'darwin':
        blender = Path('/Applications/Blender.app/Contents/MacOS/Blender')
        if blender.exists():
            config.DEFAULTS['blender_path'] = str(blender)


def mcp_main() -> int:
    """Serve the stdio MCP tools from the packaged application: `BlockAtelier --mcp`.

    No window is opened. The tools are the ones in `atelier.mcp_server`, the same module the source
    launchers start, running on the same `atelier` package as the desktop window."""
    workspace = prepare_environment('mcp.log')
    try:
        from atelier.mcp_server import mcp
        detect_blender()
        mcp.run()          # stdout carries protocol messages only; diagnostics go to mcp.log / stderr
        return 0
    except Exception as exc:
        logging.exception('MCP startup failed')
        print(f'Could not start the BlockAtelier MCP server: {exc}\nLog: {workspace / "mcp.log"}', file=sys.stderr)
        return 1


def main() -> int:
    workspace = prepare_environment('desktop.log')
    server = None
    worker = None
    sock = None
    try:
        import truststore
        truststore.inject_into_ssl()
        import uvicorn
        import webview
        from atelier import config
        from atelier.server import app

        detect_blender()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        url = f'http://127.0.0.1:{port}'
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port,
                                               loop='asyncio', http='h11', ws='none',
                                               log_config=None, access_log=False))
        worker = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
        worker.start()
        for _ in range(300):
            if server.started:
                break
            if not worker.is_alive():
                raise RuntimeError('The local application service stopped during startup.')
            time.sleep(0.1)
        else:
            raise RuntimeError('The local application service did not start in time.')
        from atelier.desktop_resources import profile_ready
        ready = profile_ready(config.DATA, '1.21.11')
        if ready:
            with urllib.request.urlopen(url + '/api/meta', timeout=15) as response:
                json.load(response)

        bridge = DesktopApi(url, workspace)
        window = webview.create_window('BlockAtelier',
                                       url=url if ready else None,
                                       html=None if ready else (config.ROOT / 'web' / 'desktop-setup.html').read_text('utf-8'),
                                       js_api=bridge, width=1440, height=960,
                                       min_size=(900, 650), background_color='#121418', text_select=True)
        bridge._window = window

        def close_server():
            server.should_exit = True
            for other in list(webview.windows):
                if other is not window:
                    other.destroy()
        window.events.closed += close_server
        webview.settings['ALLOW_DOWNLOADS'] = False  # Downloads use the native save bridge.
        webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = False
        webview.start(gui='cocoa' if sys.platform == 'darwin' else None,
                      private_mode=False, storage_path=str(workspace / 'webview'), debug=False)
        return 0
    except Exception as exc:
        logging.exception('Desktop startup failed')
        native_error(f'Could not start BlockAtelier.\n\n{exc}\n\nLog: {workspace / "desktop.log"}')
        return 1
    finally:
        if server is not None:
            server.should_exit = True
        if worker is not None:
            worker.join(timeout=5)
        if sock is not None:
            sock.close()


if __name__ == '__main__':
    raise SystemExit(mcp_main() if '--mcp' in sys.argv[1:] else main())
