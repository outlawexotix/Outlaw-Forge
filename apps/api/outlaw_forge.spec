# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Outlaw Forge FastAPI Geometry Engine Sidecar.

Bundles apps/api/app/cli.py into a standalone --onedir distribution executable
('outlaw-forge-api') with all native C++ extensions (manifold3d, scipy, shapely)
and ASGI server dependencies for supervised execution under Tauri 2.0.
"""

import os
import sys
from pathlib import Path

# PyInstaller provides SPECPATH pointing to the directory of this spec file
SPECPATH = SPECPATH if "SPECPATH" in globals() else str(Path(__file__).resolve().parent)
cli_path = os.path.join(SPECPATH, "app", "cli.py")
app_data = os.path.join(SPECPATH, "app")

try:
    from PyInstaller.utils.hooks import (
        collect_data_files,
        collect_dynamic_libs,
        collect_submodules,
    )
except ImportError:
    collect_data_files = lambda *a, **kw: []
    collect_dynamic_libs = lambda *a, **kw: []
    collect_submodules = lambda *a, **kw: []

block_cipher = None

# Mandatory hidden imports required for ASGI server and geometry engine
hidden_imports = [
    # Uvicorn ASGI internals
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    # Database drivers
    "aiosqlite",
    "sqlite3",
    # Mesh processing and numerical packages
    "trimesh",
    "manifold3d",
    "numpy",
    "scipy",
    "scipy.spatial",
    "scipy.spatial.transform._rotation_groups",
    "shapely",
    "mapbox_earcut",
    # FastAPI & Pydantic
    "fastapi",
    "starlette",
    "pydantic",
    "pydantic_settings",
]

# Additional dynamically discovered submodules
for mod in ["uvicorn", "trimesh", "fastapi", "pydantic"]:
    try:
        hidden_imports.extend(collect_submodules(mod))
    except Exception:
        pass

hidden_imports = sorted(list(set(hidden_imports)))

# Data files to bundle
datas = [
    (app_data, "app"),
]

try:
    datas.extend(collect_data_files("trimesh"))
except Exception:
    pass

# Dynamic libraries / C++ extensions
binaries = []
for pkg in ["scipy", "numpy", "shapely"]:
    try:
        binaries.extend(collect_dynamic_libs(pkg))
    except Exception:
        pass

a = Analysis(
    [cli_path],
    pathex=[SPECPATH],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "notebook", "pytest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="outlaw-forge-api",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Critical for piped stdout handshake on Windows
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="outlaw-forge-api",
)
