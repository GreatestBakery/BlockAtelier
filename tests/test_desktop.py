"""Desktop bridge tests that do not open native windows."""
import io
import json
import sys
from types import SimpleNamespace
from pathlib import Path
import pytest
from run_desktop import DesktopApi, workspace_path


def test_workspace_override(monkeypatch, tmp_path):
    monkeypatch.setenv('ATELIER_WORKSPACE', str(tmp_path))
    assert workspace_path() == tmp_path


def test_desktop_preferences(tmp_path):
    api = DesktopApi('http://127.0.0.1:12345', tmp_path)
    assert api.get_preferences() == {}
    assert api.set_ui_language('zh-CN') is True
    assert api.get_preferences() == {'language': 'zh-CN'}
    assert api.set_ui_language('arbitrary') is False
    assert api.get_preferences() == {'language': 'zh-CN'}
    (tmp_path / 'desktop.json').write_text('not-json')
    assert api.get_preferences() == {}


def test_download_origin_and_path_validation(tmp_path):
    api = DesktopApi('http://127.0.0.1:12345', tmp_path)
    url, name = api._file_url('/api/builds/build-1/file/build.litematic?download=1')
    assert url == 'http://127.0.0.1:12345/api/builds/build-1/file/build.litematic?download=1'
    assert name == 'build.litematic'
    for unsafe in [
        'https://example.com/api/builds/id/file/build.schem',
        'http://127.0.0.1:9999/api/builds/id/file/build.schem',
        '//example.com/api/builds/id/file/build.schem',
        '/api/builds/id/file/../config.json',
        '/api/builds/id/file/%2e%2e%2fconfig.json',
        '/api/config',
    ]:
        with pytest.raises(ValueError):
            api._file_url(unsafe)


def test_native_save_and_cancel(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, 'webview', SimpleNamespace(FileDialog=SimpleNamespace(SAVE=30)))
    api = DesktopApi('http://127.0.0.1:12345', tmp_path)
    output = tmp_path / 'test.schem'
    class Window:
        def create_file_dialog(self, *args, **kwargs):
            return (str(output),)
    api._window = Window()
    monkeypatch.setattr('urllib.request.urlopen', lambda *args, **kwargs: io.BytesIO(b'test structure'))
    result = api.save_file('/api/builds/build-1/file/build.schem')
    assert result['path'] == str(output)
    assert output.read_bytes() == b'test structure'
    assert not list(tmp_path.glob('.blockatelier-*'))
    monkeypatch.setattr(api._window, 'create_file_dialog', lambda *args, **kwargs: None)
    assert api.save_file('/api/builds/build-1/file/build.schem') == {'cancelled': True}
