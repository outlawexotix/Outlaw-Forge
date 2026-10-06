# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Outlaw Forge FastAPI Geometry Engine Sidecar.

Bundles apps/api/app/cli.py into a standalone executable ('outlaw-forge-api.exe')
with all native C++ extensions (manifold3d, scipy, numpy, geos, mapbox_earcut)
and ASGI server dependencies for supervised execution under Tauri 2.0 or standalone use.
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
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    # Database drivers
    "aiosqlite",
    "sqlite3",
    # Mesh processing and numerical packages
    "trimesh",
    "trimesh.exchange",
    "trimesh.exchange.stl",
    "trimesh.exchange.obj",
    "trimesh.exchange.threemf",
    "trimesh.exchange.gltf",
    "manifold3d",
    "numpy",
    "scipy",
    "scipy.spatial",
    "scipy.spatial.transform._rotation_groups",
    "shapely",
    "mapbox_earcut",
    "mapbox_earcut._core",
    # FastAPI, Starlette & Pydantic
    "fastapi",
    "starlette",
    "starlette.middleware",
    "starlette.middleware.cors",
    "starlette.routing",
    "pydantic",
    "pydantic_core",
    "pydantic_settings",
    "multipart",
    "multipart.multipart",
]

# Additional dynamically discovered submodules
for mod in ["uvicorn", "trimesh", "fastapi", "pydantic", "shapely"]:
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
for pkg in ["scipy", "numpy", "shapely", "mapbox_earcut"]:
    try:
        binaries.extend(collect_dynamic_libs(pkg))
    except Exception:
        pass

# Explicitly collect manifold3d C++ extension if present in site-packages
try:
    import manifold3d
    m_path = Path(manifold3d.__file__).resolve()
    if m_path.is_file():
        binaries.append((str(m_path), "."))
    elif m_path.is_dir():
        for pyd in m_path.glob("*.pyd"):
            binaries.append((str(pyd), "."))
        for dll in m_path.glob("*.dll"):
            binaries.append((str(dll), "."))
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

# Toggle between single-file executable and directory distribution via env var
# Default to True (onefile) to satisfy standalone executable requirement
onefile_mode = os.environ.get("PYINSTALLER_ONEFILE", "true").lower() in ("true", "1", "yes")

if onefile_mode:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="outlaw-forge-api",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,  # UPX disabled to protect C++ extension DLLs (manifold3d, scipy, numpy, geos)
        console=True,  # Critical for piped stdout handshake on Windows
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="outlaw-forge-api",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=True,
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
        upx=False,
        upx_exclude=[],
        name="outlaw-forge-api",
    )
