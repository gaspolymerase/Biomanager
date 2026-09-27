"""A copy of the lab's database on every computer that runs the desktop app.

The lab server stays the one place people work. But a server can be lost —
a deleted VM, a lapsed account, a disk — so each desktop app can keep its
own copy of the whole lab, refreshed every day while it runs:

  Server   Someone who may (admins; members if Lab setup allows it) makes a
           key for a computer under Settings → Copies of the lab. It is
           shown once and only its hash is kept. With it the computer asks
             GET /api/lab-copy/snapshot     the whole database, as a SQLite file
             GET /api/lab-copy/files        uploaded files: names and sizes
             GET /api/lab-copy/files/<name> one uploaded file
           Keys are refused from the internet (guest access) like any
           request without a session, and are throttled when wrong.

  Desktop  Settings → Keep a copy of your lab server: the address and the
           key. While the app is open it fetches a snapshot a day (or on
           Copy now), checks it arrived whole (its SHA-256 and SQLite's own
           integrity check) and keeps the newest KEEP; uploaded files are
           mirrored, only new ones downloaded, never deleted.

A snapshot is a complete BioManager database in the desktop app's own
format, so it is also a restore point: scripts/migrate-to-postgres.py loads
it into a new server (see the Run it for your lab guide). Stored secrets
(Google Calendar tokens and the like) are blanked in it: they are encrypted
with the server's own key and would be useless anywhere else.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import sqlite3
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from flask import (Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request,
                   send_file, send_from_directory, url_for)
from sqlalchemy import create_engine, select

from . import lab, security
from .db import Base, SessionLocal, engine
from .models import EncryptedText, LabCopyKey, UserAccount
from .paths import data_dir, uploads_dir

bp = Blueprint("lab_copy", __name__)

PERMISSION = "members_keep_copies"
KEY_PREFIX = "bmk_"
ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"
KEEP_DEFAULT = 14
EVERY_HOURS = 20                     # a copy a day, even if the app opens at different times
MIN_SECONDS_BETWEEN = 120            # per key: a snapshot is a whole-database read
key_throttle = security.LoginThrottle(limit=20, window=15 * 60)


# ---------------------------------------------------------------------------
# Server: who may keep copies, and their keys
# ---------------------------------------------------------------------------


def may_keep_copies(session, user) -> bool:
    return user is not None and (user.role == "admin" or lab.permission(session, PERMISSION))


def new_key() -> str:
    return KEY_PREFIX + "".join(secrets.choice(ALPHABET) for _ in range(32))


def key_hash(key: str) -> str:
    return hashlib.sha256((key or "").strip().encode()).hexdigest()


def settings_card() -> dict | None:
    """What Settings shows about copies (None: nothing, on the desktop app
    there is the other card)."""
    user = g.get("user")
    if user is None or current_app.config.get("LOCAL_SETUP"):
        return None
    with SessionLocal() as s:
        allowed = may_keep_copies(s, user)
        stmt = select(LabCopyKey).order_by(LabCopyKey.created_at.desc())
        if user.role != "admin":
            stmt = stmt.where(LabCopyKey.user_id_fk == user.id)
        keys = list(s.scalars(stmt))
        owners = {u.id: u.username for u in s.scalars(select(UserAccount).where(
            UserAccount.id.in_({k.user_id_fk for k in keys})))} if keys else {}
        now = datetime.utcnow()
        rows = [{"key": k, "owner": owners.get(k.user_id_fk, "?"), "active": k.revoked_at is None,
                 "fresh": k.last_used_at is not None and now - k.last_used_at < timedelta(hours=36)}
                for k in keys]
    return {"allowed": allowed, "rows": rows, "is_admin": user.role == "admin"}


@bp.app_context_processor
def inject():
    return {"lab_copy_card": settings_card}


@bp.route("/settings/lab-copies", methods=["POST"])
def make_key():
    if g.get("user") is None:
        return redirect(url_for("login"))
    label = " ".join((request.form.get("label") or "").split())[:80]
    with SessionLocal() as s:
        if not may_keep_copies(s, g.user):
            abort(403)
        if not label:
            flash("Say which computer the key is for, e.g. “Lab iMac”.", "error")
            return redirect(url_for("settings") + "#lab-copies")
        key = new_key()
        s.add(LabCopyKey(user_id_fk=g.user.id, label=label, key_hash=key_hash(key)))
        s.commit()
    base = (os.environ.get("BIOMANAGER_BASE_URL") or request.host_url).rstrip("/")
    # Shown on this page only: never stored, never in a redirect.
    return render_template("lab_copy/key.html", key=key, label=label, server=base)


@bp.route("/settings/lab-copies/<int:key_id>/revoke", methods=["POST"])
def revoke_key(key_id: int):
    if g.get("user") is None:
        return redirect(url_for("login"))
    with SessionLocal() as s:
        k = s.get(LabCopyKey, key_id)
        if k is None or (k.user_id_fk != g.user.id and g.user.role != "admin"):
            abort(404)
        if k.revoked_at is None:
            k.revoked_at = datetime.utcnow()
            s.commit()
        flash(f"The key for {k.label} no longer works. Copies already on that computer stay there.", "success")
    return redirect(url_for("settings") + "#lab-copies")


def _authorised(s) -> tuple[LabCopyKey, UserAccount]:
    """The key in the Authorization header, if it may take a copy now."""
    throttle_keys = (("lab-copy",), ("lab-copy-ip", request.remote_addr or ""))
    if key_throttle.retry_after(*throttle_keys):
        abort(429)
    header = request.headers.get("Authorization", "")
    raw = header[7:].strip() if header.lower().startswith("bearer ") else ""
    k = s.scalar(select(LabCopyKey).where(LabCopyKey.key_hash == key_hash(raw))) if raw.startswith(KEY_PREFIX) else None
    user = s.get(UserAccount, k.user_id_fk) if k is not None and k.revoked_at is None else None
    now = datetime.utcnow()
    if (user is None or user.disabled or user.role == "pending"
            or (user.expires_at is not None and user.expires_at <= now)):
        key_throttle.failed(*throttle_keys)
        abort(401)
    if not may_keep_copies(s, user):
        abort(403)
    return k, user


def _json_error(code: int, message: str):
    return jsonify({"ok": False, "error": message}), code


@bp.errorhandler(401)
def _unauthorised(_e):
    return _json_error(401, "This key is not valid, or it was revoked. Make a new one in Settings on the server.")


@bp.errorhandler(403)
def _forbidden(_e):
    return _json_error(403, "This account may not keep copies of the lab. An admin can allow it in Lab setup.")


@bp.errorhandler(429)
def _too_many(_e):
    return _json_error(429, "Too many requests. Try again in a few minutes.")


# ---------------------------------------------------------------------------
# Server: the snapshot and the uploaded files
# ---------------------------------------------------------------------------


def write_snapshot(path: Path) -> dict[str, int]:
    """The whole database, as a SQLite file at `path`, in the schema the app
    itself makes (so the desktop app and migrate-to-postgres read it).
    Returns the rows copied per table. Encrypted columns are blanked."""
    target = create_engine(f"sqlite:///{path}")
    counts: dict[str, int] = {}
    try:
        Base.metadata.create_all(target)
        with engine.connect() as src, target.begin() as out:
            for table in Base.metadata.sorted_tables:
                secret = [c.name for c in table.columns if isinstance(c.type, EncryptedText)]
                result = src.execution_options(stream_results=True).execute(select(table))
                n = 0
                while True:
                    batch = result.fetchmany(1000)
                    if not batch:
                        break
                    rows = [dict(r._mapping) for r in batch]
                    for row in rows:
                        for column in secret:
                            row[column] = ""
                    out.execute(table.insert(), rows)
                    n += len(rows)
                counts[table.name] = n
    finally:
        target.dispose()
    return counts


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@bp.route("/api/lab-copy/snapshot")
def snapshot():
    with SessionLocal() as s:
        k, _user = _authorised(s)
        now = datetime.utcnow()
        if k.last_used_at is not None and (now - k.last_used_at).total_seconds() < MIN_SECONDS_BETWEEN:
            abort(429)
        k.last_used_at = now
        k.uses = (k.uses or 0) + 1
        s.commit()
        key_id = k.id
    fd, name = tempfile.mkstemp(prefix="biomanager-copy-", suffix=".db")
    os.close(fd)
    path = Path(name)
    path.unlink()                   # create_engine makes a fresh file
    try:
        counts = write_snapshot(path)
        size, digest = path.stat().st_size, _sha256(path)
    except Exception:
        path.unlink(missing_ok=True)
        current_app.logger.exception("lab copy: the snapshot failed")
        return _json_error(500, "The server could not make a copy. Its log says why.")
    with SessionLocal() as s:
        k = s.get(LabCopyKey, key_id)
        k.last_bytes = size
        s.commit()
    response = send_file(path, mimetype="application/vnd.sqlite3", as_attachment=True,
                         download_name=f"biomanager-{now:%Y%m%d-%H%M%S}Z.db", max_age=0)
    response.headers["X-BioManager-SHA256"] = digest
    response.headers["X-BioManager-Taken"] = now.strftime("%Y%m%d-%H%M%S")
    response.headers["X-BioManager-Rows"] = json.dumps(counts, separators=(",", ":"))
    response.headers["Cache-Control"] = "no-store"
    response.call_on_close(lambda: path.unlink(missing_ok=True))
    return response


def _upload_files() -> list[dict]:
    root = uploads_dir()
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]   # e.g. .before-restore-<time>
        for name in filenames:
            if name.startswith("."):
                continue
            full = Path(dirpath) / name
            files.append({"path": full.relative_to(root).as_posix(), "size": full.stat().st_size})
    return sorted(files, key=lambda f: f["path"])


@bp.route("/api/lab-copy/files")
def files():
    with SessionLocal() as s:
        _authorised(s)
    return jsonify({"ok": True, "files": _upload_files()})


@bp.route("/api/lab-copy/files/<path:name>")
def file(name: str):
    with SessionLocal() as s:
        _authorised(s)
    # send_from_directory refuses anything outside the uploads folder.
    return send_from_directory(uploads_dir(), name, max_age=0)


# ---------------------------------------------------------------------------
# Desktop: fetching and keeping copies
# ---------------------------------------------------------------------------


SETTING_SERVER, SETTING_KEY, SETTING_KEEP, SETTING_STATUS = (
    "lab_copy_server", "lab_copy_key", "lab_copy_keep", "lab_copy_status")
_lock = threading.Lock()
_running = threading.Event()


def _settings():
    from .inventory_service import get_setting, set_setting
    return get_setting, set_setting


def config(s) -> dict:
    get_setting, _ = _settings()
    try:
        keep = max(1, min(365, int(get_setting(s, SETTING_KEEP, "") or KEEP_DEFAULT)))
    except ValueError:
        keep = KEEP_DEFAULT
    return {"server": get_setting(s, SETTING_SERVER, ""), "key": security.decrypt_text(get_setting(s, SETTING_KEY, "")) or "",
            "keep": keep}


def status(s) -> dict:
    get_setting, _ = _settings()
    try:
        return json.loads(get_setting(s, SETTING_STATUS, "") or "{}")
    except ValueError:
        return {}


def _save_status(**fields) -> None:
    _, set_setting = _settings()
    with SessionLocal() as s:
        current = status(s)
        current.update(fields)
        set_setting(s, SETTING_STATUS, json.dumps(current))
        s.commit()


def copies_dir(server: str) -> Path:
    """Where copies of this server go: <data folder>/lab-copies/<host>/."""
    host = re.sub(r"[^A-Za-z0-9.-]", "_", urlsplit(server).netloc or server) or "server"
    target = data_dir() / "lab-copies" / host
    (target / "db").mkdir(parents=True, exist_ok=True)
    (target / "uploads").mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(target.parent, 0o700)
    except OSError:
        pass
    return target


def list_copies(server: str) -> list[dict]:
    if not server:
        return []
    out = []
    for db in sorted((copies_dir(server) / "db").glob("biomanager-*.db"), reverse=True):
        info = {}
        sidecar = db.with_suffix(".json")
        if sidecar.exists():
            try:
                info = json.loads(sidecar.read_text())
            except ValueError:
                pass
        out.append({"name": db.name, "path": str(db), "size": db.stat().st_size, **info})
    return out


def _open(url: str, key: str, timeout: int = 300):
    """One request to the server; tests replace it."""
    return urlopen(Request(url, headers={"Authorization": f"Bearer {key}", "User-Agent": "BioManager desktop"}),
                   timeout=timeout)


def _reason(error: Exception) -> str:
    if isinstance(error, HTTPError):
        try:
            detail = json.loads(error.read().decode() or "{}").get("error", "")
        except ValueError:
            detail = ""
        return detail or f"The server answered {error.code}."
    if isinstance(error, URLError):
        text = str(error.reason)
        if "CERTIFICATE" in text.upper():
            return ("The server's certificate is not trusted on this computer. If the lab uses its own "
                    "certificate, install it here first.")
        return f"Could not reach the server ({text}). Is this computer on the lab's network, VPN or Tailscale?"
    return str(error) or error.__class__.__name__


def pull() -> dict:
    """Fetch a copy now. Returns the new status (also saved)."""
    with SessionLocal() as s:
        cfg = config(s)
    if not cfg["server"] or not cfg["key"]:
        return {"ok": False, "error": "Set the server's address and a key first."}
    if not _lock.acquire(blocking=False):
        return {"ok": False, "error": "A copy is already being made."}
    _running.set()
    _save_status(running=True, started=datetime.utcnow().isoformat(timespec="seconds"))
    server = cfg["server"].rstrip("/")
    target = copies_dir(server)
    try:
        # 1. The database.
        fd, name = tempfile.mkstemp(dir=target, prefix=".incoming-", suffix=".db")
        with os.fdopen(fd, "wb") as out, _open(f"{server}/api/lab-copy/snapshot", cfg["key"]) as r:
            shutil.copyfileobj(r, out, 1 << 20)
            digest, taken = r.headers.get("X-BioManager-SHA256", ""), r.headers.get("X-BioManager-Taken", "")
            try:
                rows = json.loads(r.headers.get("X-BioManager-Rows", "") or "{}")
            except ValueError:
                rows = {}
        incoming = Path(name)
        if not digest or _sha256(incoming) != digest:
            incoming.unlink(missing_ok=True)
            raise RuntimeError("The copy arrived damaged (its checksum did not match). It was thrown away.")
        with sqlite3.connect(incoming) as con:
            check = con.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            incoming.unlink(missing_ok=True)
            raise RuntimeError(f"The copy failed SQLite's integrity check ({check}). It was thrown away.")
        taken = re.sub(r"[^0-9-]", "", taken) or datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        final = target / "db" / f"biomanager-{taken}Z.db"
        incoming.replace(final)
        final.with_suffix(".json").write_text(json.dumps({"server": server, "taken": taken, "rows": rows,
                                                           "sha256": digest}, indent=1))
        # 2. Keep the newest copies.
        dbs = sorted((target / "db").glob("biomanager-*.db"))
        for old in dbs[:-cfg["keep"]]:
            old.unlink(missing_ok=True)
            old.with_suffix(".json").unlink(missing_ok=True)
        # 3. Uploaded files: only what is new or changed; nothing is deleted here.
        with _open(f"{server}/api/lab-copy/files", cfg["key"], timeout=60) as r:
            listing = json.loads(r.read().decode() or "{}").get("files", [])
        fetched = 0
        for item in listing:
            rel = Path(item["path"])
            if rel.is_absolute() or ".." in rel.parts:
                continue
            dest = target / "uploads" / rel
            if dest.exists() and dest.stat().st_size == item["size"]:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            part = dest.with_name(dest.name + ".part")
            with open(part, "wb") as out, _open(f"{server}/api/lab-copy/files/{quote(item['path'])}", cfg["key"]) as r:
                shutil.copyfileobj(r, out, 1 << 20)
            part.replace(dest)
            fetched += 1
        result = {"ok": True, "error": "", "last_ok": datetime.utcnow().isoformat(timespec="seconds"),
                  "last_name": final.name, "last_size": final.stat().st_size,
                  "records": sum(v for v in rows.values() if isinstance(v, int)),
                  "files": len(listing), "files_fetched": fetched}
    except Exception as error:  # noqa: BLE001 — every failure becomes a message on Settings
        result = {"ok": False, "error": _reason(error),
                  "last_error_at": datetime.utcnow().isoformat(timespec="seconds")}
    finally:
        for stray in target.glob(".incoming-*"):
            stray.unlink(missing_ok=True)
        _running.clear()
        _lock.release()
    _save_status(running=False, **result)
    return result


def due() -> bool:
    with SessionLocal() as s:
        cfg, st = config(s), status(s)
    if not cfg["server"] or not cfg["key"]:
        return False
    last = st.get("last_ok")
    if not last:
        return True
    try:
        return datetime.utcnow() - datetime.fromisoformat(last) > timedelta(hours=EVERY_HOURS)
    except ValueError:
        return True


def start_background(app, first_delay: int = 60, every: int = 30 * 60) -> threading.Thread:
    """The desktop app's timer: a copy when one is due, checked every half hour."""
    def loop():
        time.sleep(first_delay)
        while True:
            try:
                with app.app_context():
                    if due():
                        pull()
            except Exception:  # noqa: BLE001 — never take the app down
                app.logger.exception("lab copy: the scheduled copy failed")
            time.sleep(every)

    thread = threading.Thread(target=loop, name="lab-copy", daemon=True)
    thread.start()
    return thread


# ---------------------------------------------------------------------------
# Desktop: its Settings card
# ---------------------------------------------------------------------------


def desktop_card() -> dict | None:
    if g.get("user") is None or not current_app.config.get("LOCAL_SETUP"):
        return None
    with SessionLocal() as s:
        cfg, st = config(s), status(s)
    return {"server": cfg["server"], "has_key": bool(cfg["key"]), "keep": cfg["keep"], "status": st,
            "running": _running.is_set(), "copies": list_copies(cfg["server"]),
            "folder": str(copies_dir(cfg["server"])) if cfg["server"] else ""}


@bp.app_context_processor
def inject_desktop():
    return {"lab_copy_desktop": desktop_card}


def _desktop_only():
    if not current_app.config.get("LOCAL_SETUP"):
        abort(404)
    if g.get("user") is None:
        abort(redirect(url_for("login")))


@bp.route("/lab-copy/configure", methods=["POST"])
def configure():
    _desktop_only()
    server = (request.form.get("server") or "").strip().rstrip("/")
    if server and not server.startswith(("https://", "http://")):
        server = "https://" + server
    key = (request.form.get("key") or "").strip()
    _, set_setting = _settings()
    with SessionLocal() as s:
        set_setting(s, SETTING_SERVER, server)
        if key:
            set_setting(s, SETTING_KEY, security.encrypt_text(key))
        if request.form.get("keep", "").isdigit():
            set_setting(s, SETTING_KEEP, str(max(1, min(365, int(request.form["keep"])))))
        if not server:
            set_setting(s, SETTING_KEY, "")
        s.commit()
    if server and (key or request.form.get("copy_now")):
        threading.Thread(target=_pull_in_app, args=(current_app._get_current_object(),), daemon=True).start()
        flash("Saved. Making the first copy now…", "success")
    else:
        flash("Saved." if server else "This computer no longer keeps copies. Those already here stay.", "success")
    return redirect(url_for("settings") + "#lab-copy")


def _pull_in_app(app) -> None:
    with app.app_context():
        pull()


@bp.route("/lab-copy/now", methods=["POST"])
def copy_now():
    _desktop_only()
    threading.Thread(target=_pull_in_app, args=(current_app._get_current_object(),), daemon=True).start()
    return redirect(url_for("settings") + "#lab-copy")


@bp.route("/lab-copy/status")
def status_json():
    _desktop_only()
    with SessionLocal() as s:
        st = status(s)
    return jsonify({**st, "running": _running.is_set()})
