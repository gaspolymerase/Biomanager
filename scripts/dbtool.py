#!/usr/bin/env python3
"""Database maintenance: backup, restore, relocate, and health checks.

A SQLite file needs real file locking. Cloud-sync clients (OneDrive,
Dropbox, Google Drive) do not provide it: they copy the file out from under
you mid-write and sync it back, and two machines touching the same synced
database will corrupt it. That is not a merge conflict you can resolve — it
is an unreadable file.

    python scripts/dbtool.py check      # where is it, is it healthy, is it at risk
    python scripts/dbtool.py backup     # timestamped consistent copy
    python scripts/dbtool.py restore <file>      (quit the app first; --yes skips the question)
    python scripts/dbtool.py relocate ~/BioManagerData   # move it off the sync folder

Uses SQLite's own backup API, so a backup taken while the app is running is
still consistent — unlike `cp`.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Folder names that mean "something is syncing this to the cloud".
SYNC_MARKERS = ("CloudStorage", "OneDrive", "Dropbox", "Google Drive",
                "GoogleDrive", "iCloud", "Box Sync", "pCloud", "Nextcloud")

KEEP_BACKUPS = 30


def database_path() -> Path:
    """Where the app will look, honouring the same env vars it does."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        if not url.startswith("sqlite"):
            sys.exit("DATABASE_URL points at a server database. Back it up with "
                     "deploy/backup/backup.sh (see deploy/README.md), not this script.")
        return Path(url.split("///", 1)[-1])
    override = os.environ.get("BIOMANAGER_DATA_DIR", "").strip()
    base = Path(override).expanduser() if override else PROJECT_ROOT / "data"
    return base / "biomanager.db"


def sync_risk(path: Path) -> str | None:
    parts = set(path.resolve().parts)
    for marker in SYNC_MARKERS:
        if any(marker.lower() in part.lower() for part in parts):
            return marker
    return None


def backup_dir() -> Path:
    override = os.environ.get("BIOMANAGER_BACKUP_DIR", "").strip()
    target = Path(override).expanduser() if override else Path.home() / "BioManagerBackups"
    target.mkdir(parents=True, exist_ok=True)
    return target


def cmd_check(_args) -> int:
    path = database_path()
    print(f"database : {path}")
    if not path.exists():
        print("status   : MISSING — the app has not created it yet")
        return 1
    size_mb = path.stat().st_size / 1_048_576
    print(f"size     : {size_mb:.2f} MB")

    if path.stat().st_size == 0:
        print("status   : EMPTY — the file is 0 bytes; put back a backup (dbtool.py restore <file>)")
        return 1
    conn = sqlite3.connect(path)
    try:
        result = conn.execute("pragma integrity_check").fetchone()[0]
        print(f"integrity: {result}")
        journal = conn.execute("pragma journal_mode").fetchone()[0]
        print(f"journal  : {journal}")
        tables = conn.execute(
            "select count(*) from sqlite_master where type='table'").fetchone()[0]
        print(f"tables   : {tables}")
    except sqlite3.DatabaseError as exc:
        print(f"status   : DAMAGED — SQLite can't read it ({exc}).")
        print("           Put back the newest backup: python scripts/dbtool.py restore <file>")
        return 1
    finally:
        conn.close()

    marker = sync_risk(path)
    if marker:
        print()
        print(f"!! AT RISK: this database is inside a {marker} folder.")
        print("   Cloud sync does not honour SQLite's file locking. A sync during a")
        print("   write, or two machines opening it, can corrupt the file outright.")
        print()
        print("   Move it somewhere local:")
        print("       python scripts/dbtool.py relocate ~/BioManagerData")
        return 2

    print("\nlocation looks safe (not inside a synced folder).")
    return 0


def cmd_backup(args) -> int:
    source = database_path()
    if not source.exists():
        sys.exit(f"No database at {source}")
    target_dir = Path(args.into).expanduser() if args.into else backup_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = target_dir / f"biomanager-{stamp}.db"

    # SQLite's backup API takes a consistent snapshot even mid-write.
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    dst = sqlite3.connect(target)
    try:
        with dst:
            src.backup(dst)
    finally:
        src.close()
        dst.close()

    size_mb = target.stat().st_size / 1_048_576
    print(f"backed up to {target} ({size_mb:.2f} MB)")

    existing = sorted(target_dir.glob("biomanager-*.db"))
    for stale in existing[:-KEEP_BACKUPS]:
        stale.unlink()
        print(f"  pruned {stale.name}")
    print(f"  {min(len(existing), KEEP_BACKUPS)} backup(s) kept in {target_dir}")
    return 0


def cmd_restore(args) -> int:
    source = Path(args.file).expanduser()
    if not source.exists():
        sys.exit(f"No such backup: {source}")
    try:
        with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as check:
            healthy = check.execute("pragma integrity_check").fetchone()[0] == "ok" and check.execute(
                "select count(*) from sqlite_master where name='users'").fetchone()[0] == 1
    except sqlite3.DatabaseError:
        healthy = False
    if not healthy:
        sys.exit(f"{source} is not a healthy BioManager database; nothing was changed.")
    # Replacing the file under a running app mixes the two: the app keeps
    # writing into the restored file from what it had open.
    if not args.yes:
        try:
            answer = input("Is BioManager closed (the app quit, or the server stopped)? [y/N] ").strip().lower()
        except EOFError:
            sys.exit("Nothing was changed. Quit the app or stop the server, then run this again with --yes.")
        if answer not in ("y", "yes"):
            sys.exit("Nothing was changed. Quit the app or stop the server, then run this again.")
    target = database_path()
    if target.exists() and target.stat().st_size:
        safety = target.with_suffix(f".before-restore-{datetime.now():%Y%m%d-%H%M%S}.db")
        src = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
        dst = sqlite3.connect(safety)
        try:
            with dst:
                src.backup(dst)            # a consistent copy, even of a damaged-looking live file
        except sqlite3.DatabaseError:
            dst.close()
            shutil.copy2(target, safety)
        finally:
            src.close()
            dst.close()
        print(f"current database copied aside to {safety}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"restored {source} -> {target}")
    print("Restart the app.")
    return 0


def cmd_relocate(args) -> int:
    source = database_path()
    if not source.exists():
        sys.exit(f"No database at {source}")
    target_dir = Path(args.destination).expanduser().resolve()
    if sync_risk(target_dir):
        sys.exit(f"{target_dir} is also inside a synced folder. Pick somewhere local.")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "biomanager.db"
    if target.exists():
        sys.exit(f"{target} already exists — move or delete it first.")

    # Copy, verify, and only then retire the original: never leave the lab
    # with no readable database.
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    dst = sqlite3.connect(target)
    try:
        with dst:
            src.backup(dst)
    finally:
        src.close()
        dst.close()

    check = sqlite3.connect(target)
    ok = check.execute("pragma integrity_check").fetchone()[0]
    check.close()
    if ok != "ok":
        target.unlink(missing_ok=True)
        sys.exit(f"Copy failed its integrity check ({ok}). Nothing was changed.")

    retired = source.with_suffix(".db.moved")
    source.rename(retired)

    print(f"moved   : {source}\n     -> : {target}")
    print(f"old file kept as {retired} — delete it once you are happy.")
    print("\nPoint the app at the new location by setting this in your shell profile:\n")
    print(f'    export BIOMANAGER_DATA_DIR="{target_dir}"\n')
    print("Then restart:  BIOMANAGER_DATA_DIR=%s PORT=5055 .venv/bin/python run.py" % target_dir)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="report location, integrity and sync risk")

    backup = sub.add_parser("backup", help="timestamped consistent copy")
    backup.add_argument("--into", help="directory to write into")

    restore = sub.add_parser("restore", help="replace the live database with a backup")
    restore.add_argument("file")
    restore.add_argument("--yes", action="store_true", help="the app is closed; don't ask")

    relocate = sub.add_parser("relocate", help="move the database off a synced folder")
    relocate.add_argument("destination")

    args = parser.parse_args()
    return {"check": cmd_check, "backup": cmd_backup,
            "restore": cmd_restore, "relocate": cmd_relocate}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
