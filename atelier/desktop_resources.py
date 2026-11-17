"""Install local rendering profiles without bundling Minecraft assets in releases."""
import json
from pathlib import Path
import tempfile

FILES = ('version.json', 'blocks.json', 'blockstates.json', 'models.json', 'atlas.json', 'atlas.png', 'colors.json')


def profile_ready(data: Path, version: str) -> bool:
    folder = Path(data) / 'versions' / version
    if not all((folder / name).is_file() for name in FILES):
        return False
    try:
        return json.loads((folder / 'version.json').read_text('utf-8'))['id'] == version
    except (OSError, ValueError, KeyError, TypeError):
        return False


def ensure_profile(data: Path, version: str = '1.21.11') -> Path:
    data = Path(data)
    if profile_ready(data, version):
        return data / 'versions' / version
    from tools.update_version import main as prepare_profile
    data.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='profile-', dir=data) as temporary:
        stage = Path(temporary)
        prepare_profile([version], output_root=stage / 'versions')
        if not profile_ready(stage, version):
            raise RuntimeError('The downloaded rendering profile is incomplete. Please retry.')
        destination = data / 'versions' / version
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            # Preserve any pre-existing incomplete profile instead of deleting it.
            import time
            destination.rename(destination.with_name(version + '.incomplete-' + str(time.time_ns())))
        (stage / 'versions' / version).replace(destination)
    return destination
