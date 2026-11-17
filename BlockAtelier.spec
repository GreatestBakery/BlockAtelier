# Build with: python -m PyInstaller --noconfirm BlockAtelier.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata
root = Path(SPECPATH)
datas = [(str(root / 'web'), 'web')]
for name in ['LICENSE', 'COPYRIGHT', 'THIRD_PARTY_NOTICES.md', 'README.md', 'LICENSES', 'DESKTOP.md', 'BUNDLED_DEPENDENCIES.md', 'BUNDLED_LICENSES']:
    path = root / name
    if path.exists():
        datas.append((str(path), name if path.is_dir() else '.'))
datas += collect_data_files('webview')
for name in ['pywebview', 'trimesh', 'litemapy', 'numpy', 'scipy', 'pillow', 'fastapi', 'uvicorn', 'python-multipart', 'pydantic', 'mcp']:
    datas += copy_metadata(name)
hidden = collect_submodules('webview.platforms.cocoa') + ['tools.update_version', 'atelier.mcp_server', 'uvicorn.logging', 'uvicorn.loops.asyncio', 'uvicorn.protocols.http.h11_impl', 'uvicorn.lifespan.on', 'PIL.PngImagePlugin', 'PIL.JpegImagePlugin', 'PIL.WebPImagePlugin']
a = Analysis([str(root / 'run_desktop.py')], pathex=[str(root)], binaries=[], datas=datas,
    hiddenimports=hidden, hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['pytest', 'bpy', 'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'gi', 'matplotlib', 'pandas', 'IPython', 'notebook', 'scipy.spatial.tests'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='BlockAtelier', debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=False,
    argv_emulation=False, target_arch='arm64', codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='BlockAtelier')
app = BUNDLE(coll, name='BlockAtelier.app', icon=str(root / 'desktop.icns'),
    bundle_identifier='com.greatestbakery.blockatelier',
    info_plist={'CFBundleName': 'BlockAtelier', 'CFBundleDisplayName': 'BlockAtelier',
      'CFBundleShortVersionString': '0.3.0', 'CFBundleVersion': '3',
      'NSHighResolutionCapable': True, 'LSMinimumSystemVersion': '14.0',
      'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True, 'NSAllowsArbitraryLoads': True},
      'NSHumanReadableCopyright': 'Copyright © 2026 getbake and BlockAtelier contributors'})
