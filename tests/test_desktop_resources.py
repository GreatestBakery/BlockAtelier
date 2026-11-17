"""First-run profile installation is atomic and reuses existing local data."""
import json
from pathlib import Path
import pytest
from atelier.desktop_resources import FILES, ensure_profile, profile_ready


def write_profile(root, version):
    folder = Path(root) / 'versions' / version
    folder.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        (folder / name).write_text(json.dumps({'id': version}) if name == 'version.json' else '{}')
    return folder


def test_install_and_reuse_profile(monkeypatch, tmp_path):
    calls = []
    def prepare(argv, output_root=None):
        calls.append(argv)
        write_profile(Path(output_root).parent, argv[0])
    monkeypatch.setattr('tools.update_version.main', prepare)
    destination = ensure_profile(tmp_path / 'data')
    assert destination == tmp_path / 'data/versions/1.21.11'
    assert profile_ready(tmp_path / 'data', '1.21.11')
    assert ensure_profile(tmp_path / 'data') == destination
    assert calls == [['1.21.11']]


def test_incomplete_download_is_not_published(monkeypatch, tmp_path):
    def prepare(argv, output_root=None):
        folder = Path(output_root) / argv[0]
        folder.mkdir(parents=True)
        (folder / 'version.json').write_text(json.dumps({'id': argv[0]}))
    monkeypatch.setattr('tools.update_version.main', prepare)
    with pytest.raises(RuntimeError, match='incomplete'):
        ensure_profile(tmp_path / 'data')
    assert not (tmp_path / 'data/versions/1.21.11').exists()
    assert not list((tmp_path / 'data').glob('profile-*'))
