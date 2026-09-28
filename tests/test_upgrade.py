"""Upgrading a database safely (app/upgrade.py). The whole path, from each
release, is scripts/upgrade-check.py (CI: upgrade-check.yml)."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

# tests.base first: it points the app at a throwaway database before app is imported.
from tests.base import ON_POSTGRES  # noqa: F401
from app import upgrade  # noqa: E402
from app.db import engine  # noqa: E402
from app.services import ensure_schema_updates  # noqa: E402


class Upgrade(unittest.TestCase):
    def test_this_database_is_at_the_newest_revision_and_needs_nothing(self):
        self.assertEqual(upgrade.current_revision(engine), upgrade.head_revision())
        self.assertEqual(ensure_schema_updates(apply=False), [])
        self.assertFalse(upgrade.plan(engine).changes)

    def test_the_revisions_form_one_line_from_the_baseline(self):
        from alembic.script import ScriptDirectory
        script = ScriptDirectory.from_config(upgrade.alembic_config())
        self.assertEqual(len(script.get_heads()), 1)
        chain = [r.revision for r in script.walk_revisions()]
        self.assertEqual(chain[-2:], ["0002_v0_8_schema", "0001_baseline"])

    @unittest.skipIf(ON_POSTGRES, "the copy before an upgrade is SQLite's")
    def test_a_copy_is_taken_before_an_upgrade_and_only_ten_kept(self):
        from sqlalchemy import create_engine
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "biomanager.db"
            with sqlite3.connect(db) as c:
                c.execute("create table users (id integer primary key)")
                c.execute("insert into users values (1)")
            eng = create_engine(f"sqlite:///{db}")
            plan = upgrade.Plan(fresh=False, current="0001_baseline", head=upgrade.head_revision())
            for _ in range(12):
                copy = upgrade.backup_before(eng, plan)
            self.assertTrue(copy.exists())
            with sqlite3.connect(copy) as c:
                self.assertEqual(c.execute("select count(*) from users").fetchone()[0], 1)
            self.assertLessEqual(len(list((Path(tmp) / "backups").glob("before-upgrade-*.db"))), upgrade.KEEP_BACKUPS)
            eng.dispose()
