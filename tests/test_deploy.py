"""Running on a server: the SQLite → PostgreSQL copy, tokens encrypted at
rest, the health check and uploads kept outside the code."""
from tests.base import *  # noqa: F401,F403
from tests.base import ON_POSTGRES, POSTGRES_URL, AppTestCase, ROOT, one, uniq

import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from sqlalchemy import create_engine, text

from app import security, services
from app.app import app
from app.db import SessionLocal, engine
from app.models import GoogleCalendarLink

MIGRATE = Path(ROOT) / "scripts" / "migrate-to-postgres.py"


def run(args, env=None, timeout=300):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, "SECRET_KEY": "k" * 40, **(env or {})})


class HealthCheck(AppTestCase):
    def test_it_answers_without_a_login(self):
        r = app.test_client().get("/healthz")
        self.assertEqual((r.status_code, r.get_data(as_text=True)), (200, "ok\n"))

    def test_it_says_so_when_the_database_is_down(self):
        with mock.patch("app.app.SessionLocal", side_effect=RuntimeError("down")):
            r = app.test_client().get("/healthz")
        self.assertEqual(r.status_code, 503)
        self.assertNotIn("down", r.get_data(as_text=True))  # no detail to the outside


class TokensAtRest(AppTestCase):
    def raw(self, link_id):
        with engine.connect() as c:
            return c.execute(text("SELECT refresh_token, access_token FROM google_calendar_links WHERE id=:i"),
                             {"i": link_id}).one()

    def make_link(self, refresh="1//refresh-secret", access="ya29.access-secret"):
        with SessionLocal() as s:
            link = GoogleCalendarLink(owner=self.member, refresh_token=refresh, access_token=access)
            s.add(link)
            s.commit()
            return link.id

    def test_tokens_are_stored_encrypted_and_read_back_plain(self):
        link_id = self.make_link()
        refresh, access = self.raw(link_id)
        self.assertTrue(refresh.startswith("enc:v1:") and access.startswith("enc:v1:"))
        self.assertNotIn("refresh-secret", refresh)
        with SessionLocal() as s:
            link = s.get(GoogleCalendarLink, link_id)
            self.assertEqual((link.refresh_token, link.access_token), ("1//refresh-secret", "ya29.access-secret"))

    def test_plain_tokens_from_before_are_read_and_then_encrypted_at_start_up(self):
        link_id = self.make_link()
        with engine.begin() as c:
            c.execute(text("UPDATE google_calendar_links SET refresh_token='old-plain', access_token='' WHERE id=:i"),
                      {"i": link_id})
        with SessionLocal() as s:
            self.assertEqual(s.get(GoogleCalendarLink, link_id).refresh_token, "old-plain")
        self.assertGreaterEqual(services.encrypt_stored_tokens(), 1)
        self.assertTrue(self.raw(link_id)[0].startswith("enc:v1:"))
        self.assertEqual(services.encrypt_stored_tokens(), 0)  # nothing left to do

    def test_a_token_from_another_key_reads_as_missing(self):
        with mock.patch.object(security, "_fernet_cache", []), \
                mock.patch.object(security, "secret_key", lambda: "a different key entirely"):
            foreign = security.encrypt_text("secret")
        self.assertEqual(security.decrypt_text(foreign), "")


class UploadsOutsideTheCode(unittest.TestCase):
    def test_uploads_dir_override_is_served_behind_a_login(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "gel.png").write_bytes(b"\x89PNG fake")
            script = textwrap.dedent("""
                from app.app import app
                from app.paths import uploads_dir
                print(uploads_dir())
                c = app.test_client()
                print(c.get("/static/uploads/gel.png").status_code)
            """)
            p = run([sys.executable, "-c", script], env={"BIOMANAGER_UPLOADS_DIR": tmp})
            self.assertEqual(p.returncode, 0, p.stderr[-2000:])
            out = p.stdout.strip().splitlines()
            self.assertEqual(Path(out[-2]).resolve(), Path(tmp).resolve())
            self.assertEqual(out[-1], "302")  # to the login page


SOURCE_SETUP = """
import os
from datetime import date
from sqlalchemy import text
from app.app import app
from app.db import SessionLocal, engine
from app.models import GoogleCalendarLink, MouseRecord, StrainRecord, UserAccount
with SessionLocal() as s:
    s.add(UserAccount(username="pi", password_hash="x", role="admin"))
    for name in ("A", "B", "C"):
        s.add(StrainRecord(strain_name=name))
    s.add(MouseRecord(mouse_id=1, gender="F", date_of_death=date(2026, 1, 2), owner="pi"))
    s.add(GoogleCalendarLink(owner="pi", refresh_token="plain-before-migration"))
    s.commit()
    s.delete(s.query(StrainRecord).filter_by(strain_name="C").one())  # id 3 must never come back
    s.commit()
if os.environ.get("MAKE_TOO_LONG"):
    with engine.begin() as c:
        c.execute(text("UPDATE users SET short_name = :v"), {"v": "x" * 50})
"""


@unittest.skipUnless(ON_POSTGRES, "needs a PostgreSQL server (BIOMANAGER_TEST_DATABASE_URL)")
class MigrateToPostgres(unittest.TestCase):
    """Builds a small SQLite database with the app, copies it into a fresh
    PostgreSQL database next to the test one, and checks what arrived."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.source = Path(self.tmp) / "lab.db"
        self.target_name = f"biomanager_migrate_{uniq('t')}".lower()
        admin_url = POSTGRES_URL.replace("postgresql+psycopg://", "postgresql://")
        import psycopg
        with psycopg.connect(admin_url, autocommit=True) as c:
            c.execute(f'CREATE DATABASE "{self.target_name}"')
        self.target_url = admin_url.rsplit("/", 1)[0] + "/" + self.target_name
        self.addCleanup(self.drop_target, admin_url)

    def drop_target(self, admin_url):
        import psycopg
        with psycopg.connect(admin_url, autocommit=True) as c:
            c.execute(f'DROP DATABASE IF EXISTS "{self.target_name}" WITH (FORCE)')

    def make_source(self, **env):
        p = run([sys.executable, "-c", SOURCE_SETUP],
                env={"DATABASE_URL": f"sqlite:///{self.source}", "BIOMANAGER_DATA_DIR": self.tmp, **env})
        self.assertEqual(p.returncode, 0, p.stderr[-3000:])

    def migrate(self, *extra):
        return run([sys.executable, str(MIGRATE), str(self.source), self.target_url, *extra])

    def target(self, sql, **params):
        e = create_engine(self.target_url.replace("postgresql://", "postgresql+psycopg://"))
        try:
            with e.connect() as c:
                return c.execute(text(sql), params).all()
        finally:
            e.dispose()

    def test_rows_types_and_the_id_high_water_mark_arrive(self):
        self.make_source()
        before = self.source.read_bytes()
        p = self.migrate()
        self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
        self.assertIn("row counts verified", p.stdout)
        self.assertEqual(self.source.read_bytes(), before)  # the source is only read
        self.assertEqual(self.target("SELECT strain_name FROM strains ORDER BY id"), [("A",), ("B",)])
        self.assertEqual(self.target("SELECT gender, date_of_death FROM mice WHERE mouse_id=1"),
                         [("F", __import__("datetime").date(2026, 1, 2))])
        # The deleted strain's id 3 is never handed out again.
        (next_id,), = self.target("SELECT nextval(pg_get_serial_sequence('strains', 'id'))")
        self.assertGreater(next_id, 3)
        # At the copy's revision, so the app's first start upgrades nothing.
        from app import upgrade
        self.assertEqual(self.target("SELECT version_num FROM alembic_version"), [(upgrade.head_revision(),)])
        (token,), = self.target("SELECT refresh_token FROM google_calendar_links")
        self.assertTrue(token.startswith("enc:v1:"))  # encrypted on the way (start-up step)

    def test_a_value_too_long_for_postgres_stops_it_before_anything_is_written(self):
        self.make_source(MAKE_TOO_LONG="1")
        p = self.migrate()
        self.assertEqual(p.returncode, 1)
        self.assertIn("users.short_name", p.stdout)
        self.assertIn("Nothing was written", p.stdout)
        self.assertEqual(self.target("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"),
                         [(0,)])

    def test_a_dry_run_keeps_nothing(self):
        self.make_source()
        p = self.migrate("--dry-run")
        self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
        self.assertEqual(self.target("SELECT count(*) FROM strains"), [(0,)])

    def test_it_refuses_a_target_that_already_holds_data(self):
        self.make_source()
        self.assertEqual(self.migrate().returncode, 0)
        p = self.migrate()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("already holds data", p.stderr + p.stdout)


if __name__ == "__main__":
    unittest.main()


class ServerBundle(unittest.TestCase):
    """scripts/make-server-bundle.sh: deploy/ for a server without the
    source, running the published image of the release."""

    def test_the_bundle_runs_the_release_image_and_holds_no_secrets(self):
        import tarfile
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bundle.tar.gz"
            r = run(["bash", "scripts/make-server-bundle.sh", "v1.2.3", str(out)])
            self.assertEqual(r.returncode, 0, r.stderr)
            with tarfile.open(out) as tar:
                names = tar.getnames()
                compose = tar.extractfile("Biomanager/deploy/compose.yaml").read().decode()
            self.assertIn("Biomanager/deploy/BUNDLE.md", names)
            self.assertIn("Biomanager/deploy/host/load-image.sh", names)
            with tarfile.open(out) as tar:
                self.assertEqual(tar.extractfile("Biomanager/deploy/VERSION").read().decode().strip(), "1.2.3")
                self.assertTrue(tar.getmember("Biomanager/deploy/host/load-image.sh").mode & 0o111)
            self.assertIn("Biomanager/deploy/host/internet-access.sh", names)
            self.assertIn("image: ${BIOMANAGER_IMAGE:-ghcr.io/gaspolymerase/biomanager:1.2.3}", compose)
            self.assertNotIn("context: ..", compose)          # nothing to build the app from
            self.assertIn("build: ./backup", compose)          # the backup image is built from the bundle
            self.assertFalse([n for n in names if n.endswith("/.env") or "/backups/" in n], names)
            self.assertFalse([n for n in names if n != "Biomanager" and not n.startswith("Biomanager/deploy")], names)
            self.assertFalse([n for n in names if "/._" in n or n.startswith("._")], names)

    def test_what_ships_names_no_one(self):
        # deploy/ goes out in the public bundle, and app/, scripts/ and migrations/ in
        # every desktop build and server image: no one's server, name or address.
        # Our own server's runbook is docs/OUR-SERVER.md, which ships in neither.
        ours = re.compile(r"\bbiomanager-vm\b|biomanager_key|alex|barbara|\blab member\b|\bmcclintock lab\b|52350568|university", re.I)
        found = []
        for top in ("deploy", "app", "scripts", "migrations"):
            for path in (Path(ROOT) / top).rglob("*"):
                if not path.is_file() or "/backups/" in str(path) or "/uploads/" in str(path) or path.name == ".env":
                    continue
                if path.suffix in (".pyc", ".png", ".webp", ".ico", ".woff", ".woff2", ".ttf", ".icns"):
                    continue
                text = path.read_text(errors="ignore")
                rel = path.relative_to(ROOT)
                found += [f"{rel}: {m}" for m in re.findall(r"([a-z0-9-]+)\.ts\.net", text) if m != "tail1234"]
                found += [f"{rel}: {m}" for m in ours.findall(text)]
        self.assertEqual(found, [])
