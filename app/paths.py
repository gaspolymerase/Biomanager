"""Path resolution for dev vs. frozen (PyInstaller) execution.

In dev (`python run.py`), data lives next to the source tree at `./data/`
and `app/static/uploads/`. In a frozen `.app`, those paths are inside a
read-only bundle, so we redirect writable state to a per-user folder:

  macOS:   ~/Library/Application Support/Biomanager/
  Windows: %APPDATA%/Biomanager/
  Linux:   ~/.local/share/Biomanager/

Read-only assets (templates, the built notebook JS/CSS) stay inside the
bundle and are resolved via sys._MEIPASS when frozen.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def resource_root() -> Path:
    """Directory containing read-only app resources (templates, static files)."""
    if is_frozen():
        # PyInstaller unpacks data files under sys._MEIPASS.
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def user_data_root() -> Path:
    """Writable per-user directory for DB and uploads."""
    if not is_frozen():
        return Path(__file__).resolve().parent.parent

    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "Biomanager"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home())) / "Biomanager"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "Biomanager"
    base.mkdir(parents=True, exist_ok=True)
    return base


def data_dir() -> Path:
    """Directory for the SQLite database file.

    BIOMANAGER_DATA_DIR overrides everything, which is how the database gets
    moved off a cloud-synced folder without moving the code. Cloud sync does
    not honour SQLite's file locking and will eventually corrupt the file —
    see scripts/dbtool.py.
    """
    override = os.environ.get("BIOMANAGER_DATA_DIR", "").strip()
    if override:
        target = Path(override).expanduser()
    else:
        target = user_data_root() / "data"
    target.mkdir(parents=True, exist_ok=True)
    return target


# Folder names that indicate a cloud-sync client is managing this path.
SYNC_MARKERS = ("CloudStorage", "OneDrive", "Dropbox", "Google Drive",
                "GoogleDrive", "iCloud", "Box Sync", "Nextcloud")


def sync_risk(path: Path) -> str | None:
    """Return the sync provider managing `path`, if any."""
    for part in Path(path).resolve().parts:
        for marker in SYNC_MARKERS:
            if marker.lower() in part.lower():
                return marker
    return None


def uploads_dir() -> Path:
    """Directory for user-uploaded images and files.

    When frozen we need a writable location *and* it must be served at
    /static/uploads/ — so the Flask app adds a separate static route for
    this folder (see app.py).

    BIOMANAGER_UPLOADS_DIR puts them anywhere, which is how a server keeps
    them on the data volume, next to the database, rather than in the code."""
    override = os.environ.get("BIOMANAGER_UPLOADS_DIR", "").strip()
    if override:
        target = Path(override).expanduser()
    elif is_frozen():
        target = user_data_root() / "uploads"
    else:
        target = resource_root() / "app" / "static" / "uploads"
    target.mkdir(parents=True, exist_ok=True)
    return target
