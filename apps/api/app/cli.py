"""Outlaw Forge Desktop Sidecar CLI Entrypoint.

Provides command-line argument parsing, dynamic ephemeral port binding,
frozen AppData path resolution, and startup handshake lifecycle management
for the Tauri 2.0 standalone desktop sidecar.
"""

import argparse
import os
import socket
import sys
from pathlib import Path
from typing import Optional, Sequence

# Ensure apps/api is in sys.path before importing app.*
_app_dir = Path(__file__).resolve().parent.parent
if str(_app_dir) not in sys.path:
    sys.path.insert(0, str(_app_dir))

import uvicorn


def get_default_desktop_dir() -> Path:
    """Return default application data directory for desktop execution."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            appdata = str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "OutlawForge"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "OutlawForge"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        if not xdg:
            xdg = str(Path.home() / ".local" / "share")
        return Path(xdg) / "outlaw-forge"


def resolve_port(port: int, host: str = "127.0.0.1") -> int:
    """Resolve binding port. When port is 0, binds an ephemeral socket to find a free port."""
    if port == 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, 0))
            return int(s.getsockname()[1])
    return port


def configure_environment(
    storage_dir: Optional[str] = None,
    db_path: Optional[str] = None,
    handshake_file: Optional[str] = None,
) -> None:
    """Configure storage, database paths, and handshake file in the runtime environment."""
    if storage_dir:
        os.environ["STORAGE_BASE_DIR"] = str(Path(storage_dir).resolve())
    elif getattr(sys, "frozen", False) and not os.getenv("STORAGE_BASE_DIR"):
        default_storage = get_default_desktop_dir() / "data"
        os.environ["STORAGE_BASE_DIR"] = str(default_storage.resolve())

    if db_path:
        os.environ["SQLITE_DB_PATH"] = str(Path(db_path).resolve())
    elif getattr(sys, "frozen", False) and not os.getenv("SQLITE_DB_PATH"):
        default_db = get_default_desktop_dir() / "data" / "outlaw_forge.db"
        os.environ["SQLITE_DB_PATH"] = str(default_db.resolve())

    if handshake_file:
        os.environ["HANDSHAKE_FILE"] = str(Path(handshake_file).resolve())


def parse_args(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="outlaw-forge-api",
        description="Outlaw Forge Geometry Engine Sidecar",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind (default: 8000, use 0 for ephemeral port assignment)",
    )
    parser.add_argument(
        "--storage-dir",
        default=None,
        help="Base directory for asset storage",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Path to SQLite database file",
    )
    parser.add_argument(
        "--handshake-file",
        default=None,
        help="Optional path to write startup handshake JSON file",
    )
    return parser.parse_args(args)


def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    log_level: str = "info",
    sock: Optional[socket.socket] = None,
) -> None:
    """Configure FastAPI app and launch uvicorn server.

    When port is 0 or a pre-bound socket is supplied, utilizes zero-race socket binding
    so the port discovered is never closed between discovery and listen.
    """
    # Late import to ensure environment variables are configured before settings initialize
    from app.main import app

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level=log_level,
        access_log=False,
    )

    if sock is not None:
        bound_port = int(sock.getsockname()[1])
        os.environ["PORT"] = str(bound_port)
        app.state.port = bound_port
        server = uvicorn.Server(config)
        server.run(sockets=[sock])
    elif port == 0:
        # Zero-race: bind socket immediately via uvicorn and keep it open
        sock = config.bind_socket()
        bound_port = int(sock.getsockname()[1])
        os.environ["PORT"] = str(bound_port)
        app.state.port = bound_port
        server = uvicorn.Server(config)
        server.run(sockets=[sock])
    else:
        os.environ["PORT"] = str(port)
        app.state.port = port
        server = uvicorn.Server(config)
        server.run()


def main(args: Optional[Sequence[str]] = None) -> None:
    """CLI entrypoint."""
    parsed = parse_args(args)
    configure_environment(
        storage_dir=parsed.storage_dir,
        db_path=parsed.db_path,
        handshake_file=parsed.handshake_file,
    )
    if parsed.port == 0:
        run_server(host=parsed.host, port=0)
    else:
        port = resolve_port(parsed.port, host=parsed.host)
        run_server(host=parsed.host, port=port)


if __name__ == "__main__":
    main()
