"""Copies of the lab on every computer (app/lab_copy.py): the keys, the
snapshot the server hands out, and the desktop app keeping copies."""
from __future__ import annotations

import io
import json
import re
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError
from urllib.parse import urlsplit

from sqlalchemy import create_engine, text

from tests.base import AppTestCase, app, client_for, execute, flash_text, location, make_user, one, uniq

INTERNET = {"X-BioManager-Entry": "internet"}


def set_permission(on: bool) -> None:
    from app import lab
    from app.db import SessionLocal
    with SessionLocal() as s:
        lab._set_flag(s, "members_keep_copies", on)
        s.commit()


class CopyCase(AppTestCase):

    def setUp(self):
        super().setUp()
        from app import lab_copy
        lab_copy.key_throttle.reset()
        set_permission(False)
        self.addCleanup(set_permission, False)

    def make_key(self, client=None, label=None) -> str:
        r = (client or self.a).post("/settings/lab-copies", data={"label": label or uniq("Computer ")})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:300])
        return re.search(r'id="lab-copy-key"[^>]*>(bmk_[a-z0-9]+)<', r.get_data(as_text=True)).group(1)

    def api(self, path, key, headers=None):
        return app.test_client().get(path, headers={"Authorization": f"Bearer {key}", **(headers or {})})

    def fresh(self, key):
        """Let this key take another snapshot straight away."""
        from app.lab_copy import key_hash
        execute("update lab_copy_keys set last_used_at=NULL where key_hash=?", key_hash(key))


# ======================================================================= keys

class KeyTests(CopyCase):

    def test_an_admin_makes_a_key_shown_once_and_kept_only_as_a_hash(self):
        label = uniq("Lab iMac ")
        key = self.make_key(label=label)
        self.assertTrue(key.startswith("bmk_") and len(key) == 36)
        stored = one("select key_hash from lab_copy_keys where label=?", label)
        self.assertNotIn(key, stored)
        self.assertNotIn(key, self.get_ok(self.a, "/settings"))
        self.assertIn(label, self.get_ok(self.a, "/settings"))

    def test_members_need_lab_setup_to_allow_it(self):
        member = client_for(make_user(uniq("member")))
        self.assertEqual(member.post("/settings/lab-copies", data={"label": "Laptop"}).status_code, 403)
        self.assertNotIn("Copies of the lab on your computers", self.get_ok(member, "/settings"))
        set_permission(True)
        key = self.make_key(self.m)
        self.assertEqual(self.api("/api/lab-copy/files", key).status_code, 200)
        set_permission(False)
        self.assertEqual(self.api("/api/lab-copy/files", key).status_code, 403)

    def test_a_key_needs_a_computer_name(self):
        r = self.post(self.a, "/settings/lab-copies", data={"label": " "})
        self.assertIn("Say which computer", flash_text(r))

    def test_admins_see_every_computer_members_only_their_own(self):
        set_permission(True)
        mine = uniq("Member laptop ")
        self.make_key(self.m, mine)
        theirs = uniq("Admin desktop ")
        self.make_key(self.a, theirs)
        admin_page, member_page = self.get_ok(self.a, "/settings"), self.get_ok(self.m, "/settings")
        self.assertIn(mine, admin_page)
        self.assertIn(theirs, admin_page)
        self.assertIn(mine, member_page)
        self.assertNotIn(theirs, member_page)

    def test_a_revoked_key_stops_working(self):
        label = uniq("Old PC ")
        key = self.make_key(label=label)
        kid = one("select id from lab_copy_keys where label=?", label)
        self.post(self.a, f"/settings/lab-copies/{kid}/revoke")
        r = self.api("/api/lab-copy/snapshot", key)
        self.assertEqual(r.status_code, 401)
        self.assertIn("revoked", r.get_json()["error"])

    def test_someone_else_cannot_revoke_a_key(self):
        label = uniq("Admin box ")
        self.make_key(label=label)
        kid = one("select id from lab_copy_keys where label=?", label)
        self.assertEqual(self.m.post(f"/settings/lab-copies/{kid}/revoke").status_code, 404)

    def test_a_disabled_account_s_keys_stop_working(self):
        admin2 = make_user(uniq("admin"), role="admin")
        key = self.make_key(client_for(admin2))
        execute("update users set disabled=? where username=?", True, admin2)
        self.assertEqual(self.api("/api/lab-copy/files", key).status_code, 401)


# ======================================================================= the snapshot

class SnapshotTests(CopyCase):

    def test_no_key_or_a_wrong_key_gets_nothing(self):
        self.assertEqual(app.test_client().get("/api/lab-copy/snapshot").status_code, 401)
        self.assertEqual(self.api("/api/lab-copy/snapshot", "bmk_" + "x" * 32).status_code, 401)

    def test_the_snapshot_is_the_whole_database_as_a_sqlite_file(self):
        mouse_owner = self.member
        key = self.make_key()
        r = self.api("/api/lab-copy/snapshot", key)
        self.assertEqual(r.status_code, 200)
        data = r.get_data()
        import hashlib
        self.assertEqual(hashlib.sha256(data).hexdigest(), r.headers["X-BioManager-SHA256"])
        rows = json.loads(r.headers["X-BioManager-Rows"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "copy.db"
            path.write_bytes(data)
            with sqlite3.connect(path) as con:
                self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                users = {u for (u,) in con.execute("select username from users")}
                self.assertIn(self.admin, users)
                self.assertIn(mouse_owner, users)
                self.assertEqual(con.execute("select count(*) from users").fetchone()[0], rows["users"])
                self.assertEqual(con.execute("select count(*) from mice").fetchone()[0], one("select count(*) from mice"))
                self.assertEqual(con.execute("select count(*) from inventory_items").fetchone()[0],
                                 one("select count(*) from inventory_items"))

    def test_stored_secrets_are_blanked(self):
        from app.db import SessionLocal
        from app.models import GoogleCalendarLink
        with SessionLocal() as s:
            s.add(GoogleCalendarLink(owner=self.admin, refresh_token="very-secret-refresh", access_token="also-secret"))
            s.commit()
        r = self.api("/api/lab-copy/snapshot", self.make_key())
        self.assertNotIn(b"very-secret-refresh", r.get_data())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "copy.db"
            path.write_bytes(r.get_data())
            e = create_engine(f"sqlite:///{path}")
            with e.connect() as c:
                tokens = c.execute(text("select refresh_token, access_token from google_calendar_links")).all()
            e.dispose()
        self.assertTrue(tokens)
        from app.security import decrypt_text
        self.assertTrue(all((decrypt_text(a) or "") == "" and (decrypt_text(b) or "") == "" for a, b in tokens))

    def test_one_snapshot_every_few_minutes_per_key(self):
        key = self.make_key()
        self.assertEqual(self.api("/api/lab-copy/snapshot", key).status_code, 200)
        self.assertEqual(self.api("/api/lab-copy/snapshot", key).status_code, 429)
        self.fresh(key)
        self.assertEqual(self.api("/api/lab-copy/snapshot", key).status_code, 200)

    def test_the_server_records_when_each_computer_last_copied(self):
        label = uniq("Freezer PC ")
        key = self.make_key(label=label)
        self.api("/api/lab-copy/snapshot", key)
        self.assertIsNotNone(one("select last_used_at from lab_copy_keys where label=?", label))
        self.assertGreater(one("select last_bytes from lab_copy_keys where label=?", label), 0)

    def test_keys_are_refused_from_the_internet(self):
        r = self.api("/api/lab-copy/snapshot", self.make_key(), headers=INTERNET)
        self.assertEqual((r.status_code, location(r)), (302, "/guest"))

    def test_uploaded_files_are_listed_and_served_but_nothing_outside_them(self):
        from app.paths import uploads_dir
        name = f"{uniq('copytest')}.txt"
        (uploads_dir() / name).write_text("gel image")
        self.addCleanup((uploads_dir() / name).unlink)
        key = self.make_key()
        listing = self.api("/api/lab-copy/files", key).get_json()["files"]
        self.assertIn({"path": name, "size": 9}, listing)
        self.assertEqual(self.api(f"/api/lab-copy/files/{name}", key).get_data(as_text=True), "gel image")
        self.assertEqual(self.api("/api/lab-copy/files/../../app.py", key).status_code, 404)

    def test_wrong_keys_are_throttled(self):
        from app import lab_copy
        for _ in range(lab_copy.key_throttle.limit):
            self.api("/api/lab-copy/files", "bmk_" + "y" * 32)
        self.assertEqual(self.api("/api/lab-copy/files", self.make_key()).status_code, 429)


# ======================================================================= the desktop app

class _Response:
    def __init__(self, r):
        self._body = io.BytesIO(r.get_data())
        self.headers = r.headers

    def read(self, *a):
        return self._body.read(*a)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_open(url, key, timeout=300, tamper=None):
    """The desktop app's request, answered by this test's server."""
    r = app.test_client().get(urlsplit(url).path, headers={"Authorization": f"Bearer {key}"})
    if r.status_code >= 400:
        raise HTTPError(url, r.status_code, "refused", r.headers, io.BytesIO(r.get_data()))
    resp = _Response(r)
    if tamper and urlsplit(url).path.endswith("/snapshot"):
        tamper(resp)
    return resp


class DesktopTests(CopyCase):

    def setUp(self):
        super().setUp()
        app.config["LOCAL_SETUP"] = True
        self.addCleanup(app.config.pop, "LOCAL_SETUP", None)
        execute("delete from app_settings where key like 'lab_copy_%'")
        self.server = f"https://{uniq('lab')}.example.ts.net"
        self.key = self.make_key()
        # Settings as the desktop app's own form saves them.
        with mock.patch("app.lab_copy.threading.Thread"):
            self.post(self.a, "/lab-copy/configure", data={"server": self.server, "key": self.key, "keep": "3"})

    def pull(self, tamper=None):
        from app import lab_copy
        with mock.patch.object(lab_copy, "_open", lambda url, key, timeout=300: fake_open(url, key, timeout, tamper)):
            with app.app_context():
                return lab_copy.pull()

    def folder(self) -> Path:
        from app import lab_copy
        return lab_copy.copies_dir(self.server)

    def test_a_copy_arrives_checked_with_its_uploaded_files(self):
        from app.paths import uploads_dir
        name = f"{uniq('mirror')}.txt"
        (uploads_dir() / name).write_text("plasmid map")
        self.addCleanup((uploads_dir() / name).unlink)
        result = self.pull()
        self.assertTrue(result["ok"], result)
        [db] = list((self.folder() / "db").glob("biomanager-*.db"))
        with sqlite3.connect(db) as con:
            self.assertIn(self.admin, {u for (u,) in con.execute("select username from users")})
        info = json.loads(db.with_suffix(".json").read_text())
        self.assertEqual(info["server"], self.server)
        self.assertEqual((self.folder() / "uploads" / name).read_text(), "plasmid map")
        page = self.get_ok(self.a, "/settings")
        self.assertIn("Last copy:", page)
        self.assertIn(db.name, page)

    def test_only_the_newest_copies_are_kept(self):
        from app import lab_copy
        taken = iter(["20260101-000000", "20260102-000000", "20260103-000000", "20260104-000000"])

        def stamp(resp):
            resp.headers = {**dict(resp.headers), "X-BioManager-Taken": next(taken)}
        for _ in range(4):
            self.fresh(self.key)
            self.assertTrue(self.pull(tamper=stamp)["ok"])
        names = sorted(p.name for p in (self.folder() / "db").glob("biomanager-*.db"))
        self.assertEqual(names, [f"biomanager-2026010{d}-000000Z.db" for d in (2, 3, 4)])
        self.assertEqual(len(lab_copy.list_copies(self.server)), 3)

    def test_a_damaged_copy_is_thrown_away(self):
        def corrupt(resp):
            resp.headers = {**dict(resp.headers), "X-BioManager-SHA256": "0" * 64}
        result = self.pull(tamper=corrupt)
        self.assertFalse(result["ok"])
        self.assertIn("damaged", result["error"])
        self.assertEqual(list((self.folder() / "db").glob("*.db")), [])
        self.assertEqual(list(self.folder().glob(".incoming-*")), [])

    def test_a_revoked_key_is_explained(self):
        execute("update lab_copy_keys set revoked_at=CURRENT_TIMESTAMP")
        result = self.pull()
        self.assertFalse(result["ok"])
        self.assertIn("revoked", result["error"])
        self.assertIn("The last copy failed", self.get_ok(self.a, "/settings"))

    def test_the_key_is_stored_encrypted(self):
        stored = one("select value from app_settings where key='lab_copy_key'")
        self.assertNotIn(self.key, stored)

    def test_a_copy_is_due_once_a_day(self):
        from app import lab_copy
        with app.app_context():
            self.assertTrue(lab_copy.due())
            self.pull()
            self.assertFalse(lab_copy.due())

    def test_the_desktop_card_is_only_in_the_desktop_app(self):
        self.assertIn('id="lab-copy"', self.get_ok(self.a, "/settings"))
        app.config.pop("LOCAL_SETUP")
        self.assertNotIn('id="lab-copy"', self.get_ok(self.a, "/settings"))
        self.assertEqual(self.a.post("/lab-copy/now").status_code, 404)


# ======================================================================= a copy rebuilds a server

from tests.base import ON_POSTGRES, POSTGRES_URL  # noqa: E402


@unittest.skipUnless(ON_POSTGRES, "needs a PostgreSQL server (BIOMANAGER_TEST_DATABASE_URL)")
class RestoreFromACopy(CopyCase):
    """A snapshot goes into a new, empty server with migrate-to-postgres,
    as the guide's "Moving from the app to a server" says."""

    def test_a_copy_loads_into_a_fresh_postgres_database(self):
        import os
        import subprocess
        import sys

        import psycopg
        from tests.base import ROOT
        r = self.api("/api/lab-copy/snapshot", self.make_key())
        target = f"biomanager_restore_{uniq('t')}".lower()
        admin_url = POSTGRES_URL.replace("postgresql+psycopg://", "postgresql://")
        with psycopg.connect(admin_url, autocommit=True) as c:
            c.execute(f'CREATE DATABASE "{target}"')
        target_url = admin_url.rsplit("/", 1)[0] + "/" + target

        def drop():
            with psycopg.connect(admin_url, autocommit=True) as c:
                c.execute(f'DROP DATABASE IF EXISTS "{target}" WITH (FORCE)')
        self.addCleanup(drop)
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "copy.db"
            copy.write_bytes(r.get_data())
            p = subprocess.run([sys.executable, str(Path(ROOT) / "scripts" / "migrate-to-postgres.py"), str(copy), target_url],
                               cwd=ROOT, capture_output=True, text=True, timeout=300,
                               env={**os.environ, "SECRET_KEY": "k" * 40})
        self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
        with psycopg.connect(target_url) as c:
            restored = c.execute("select count(*) from users").fetchone()[0]
        self.assertEqual(restored, one("select count(*) from users"))


if __name__ == "__main__":
    unittest.main()
