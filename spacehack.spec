# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for spacehack — standalone macOS .app / Windows .exe.

Usage:
    pyinstaller spacehack.spec          # one-shot build
    pyinstaller --clean spacehack.spec  # fresh build (pick up data changes)
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Hidden imports — tcod uses cffi + numpy, both of which can be missed by
# PyInstaller's auto-detection.  collect_submodules grabs every spacehack
# submodule so dynamic/delayed imports don't get missed.
# ---------------------------------------------------------------------------
from PyInstaller.utils.hooks import collect_submodules

_hidden = [
    'cffi',
    'numpy',
    'tcod',
] + collect_submodules('spacehack')

# ---------------------------------------------------------------------------
# Data files: bundle the entire data/ tree so tilesheets, fonts, and
# .layout files are available at runtime via sys._MEIPASS/spacehack/data/.
# ---------------------------------------------------------------------------
_src_data = Path('src/spacehack/data')
_datas: list[tuple[str, str]] = []

if _src_data.is_dir():
    for _p in _src_data.rglob('*'):
        if _p.is_dir():
            continue
        # Compute the destination directory: spacehack/data/<relative_parent>
        _rel = _p.relative_to(_src_data)
        _dst = str(Path('spacehack') / 'data' / _rel).replace('\\', '/')
        _datas.append((str(_p), str(Path(_dst).parent)))

# ---------------------------------------------------------------------------
# Entry-point script: a tiny launcher that imports and runs the game.
# We don't use __main__.py directly because PyInstaller runs it in a weird
# namespace.  This standalone launcher avoids import-path footguns.
# ---------------------------------------------------------------------------
_LAUNCHER = """\
import sys
from spacehack.__main__ import main
sys.exit(main())
"""

_launcher_path = Path('_spacehack_launcher.py')
_launcher_path.write_text(_LAUNCHER, encoding='utf-8')

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [str(_launcher_path)],
    pathex=['src'],
    binaries=[],
    datas=_datas,
    hiddenimports=_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data)

# ---------------------------------------------------------------------------
# onefile executable — self-contained binary with all Python + libs + data.
# BUNDLE wraps this into a double-clickable .app on macOS.
# ---------------------------------------------------------------------------
# NOTE: PyInstaller emits a deprecation warning about onefile + BUNDLE
# ("don't make sense") but it works correctly — the .app contains a
# self-contained executable.  This will only become an error in v7.0.
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='spacehack',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# ---------------------------------------------------------------------------
# macOS .app bundle (only built on macOS).
# ---------------------------------------------------------------------------
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='spacehack.app',
        icon=None,
        bundle_identifier='com.spacehack.game',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'CFBundleShortVersionString': '0.0.1',
            'CFBundleName': 'spacehack',
        },
    )

# Clean up the temp launcher
_launcher_path.unlink(missing_ok=True)
