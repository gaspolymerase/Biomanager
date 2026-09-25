"""Database integrity (app/integrity.py): ids are never reused, foreign keys
are enforced, and undo keeps ids and references valid.

Most tests run on the suite's shared database. The boot-time migration of
an *old* database (tables without AUTOINCREMENT, dangling references) needs
an app started on a different file, so those tests run a short child
Python process each (the engine is bound at import)."""
from tests.base import *  # noqa: F401,F403
from tests.base import AppTestCase, ROOT, batch_of, one, only_sqlite, row, rows, uniq

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import audit, db as appdb, integrity
from app import undo as undo_service
from app.app import app
from app.db import Base, SessionLocal, engine
from app.models import (BatchRecord, MouseRecord, MouseWeight, NotebookPage, NotebookTab,
                        StockUnit)


def model_tables_with_ids():
    return [name for name, table in Base.metadata.tables.items() if table.autoincrement_column is not None]


@only_sqlite  # PostgreSQL has these natively: sequences, enforced keys, rollback on return
class FreshSchema(unittest.TestCase):
    def test_every_model_table_has_autoincrement_and_deferred_foreign_keys(self):
        stored = dict(rows("select name, sql from sqlite_master where type='table'"))
        stale = [n for n in model_tables_with_ids() if n in stored and not integrity._is_current(stored[n])]
        self.assertEqual(stale, [])

    def test_foreign_keys_are_enforced_on_app_connections(self):
        self.assertIs(appdb.FOREIGN_KEYS_ENFORCED, True)
        with engine.connect() as conn:
            self.assertEqual(conn.exec_driver_sql("pragma foreign_keys").scalar(), 1)

    def test_a_current_database_needs_no_rebuild(self):
        raw = engine.raw_connection()
        try:
            self.assertEqual(integrity.tables_needing_rebuild(raw.driver_connection), [])
        finally:
            raw.close()


class IdsAreNeverReused(AppTestCase):
    def test_deleted_strain_id_is_not_handed_out_again(self):
        first = uniq("Strain ")
        self.a.post("/colony/strains/create", data={"strain_name": first})
        sid = one("select id from strains where strain_name=?", first)
        self.a.post(f"/colony/strains/{sid}/delete")
        self.assertIsNone(one("select id from strains where id=?", sid))
        second = uniq("Strain ")
        self.a.post("/colony/strains/create", data={"strain_name": second})
        self.assertGreater(one("select id from strains where strain_name=?", second), sid)

    def test_deleted_mouse_row_id_is_not_reused(self):
        mouse = self.make_mouse(self.a, self.admin, cage=uniq("C"))
        self.a.post(f"/colony/mice/{mouse}/delete")
        self.assertIsNone(one("select id from mice where id=?", mouse))
        again = self.make_mouse(self.a, self.admin, cage=uniq("C"))
        self.assertGreater(again, mouse)

    @only_sqlite  # PostgreSQL has these natively: sequences, enforced keys, rollback on return
    def test_sqlite_sequence_is_at_least_the_highest_id(self):
        self.make_line(self.a)
        seq = dict(rows("select name, seq from sqlite_sequence"))
        top = one("select max(id) from fish_lines")
        self.assertGreaterEqual(seq.get("fish_lines", 0), top)


class ForeignKeysEnforced(AppTestCase):
    def _tab_with_page(self):
        with SessionLocal() as s:
            tab = NotebookTab(owner_username=self.admin, title=uniq("tab"))
            s.add(tab)
            s.flush()
            s.add(NotebookPage(tab_id_fk=tab.id, title="p"))
            s.commit()
            return tab.id

    def test_deleting_a_parent_that_still_has_children_is_refused_at_commit(self):
        tab_id = self._tab_with_page()
        with SessionLocal() as s:
            s.execute(text("delete from notebook_tabs where id=:i"), {"i": tab_id})
            with self.assertRaises(IntegrityError):
                s.commit()
            s.rollback()  # see test_a_failed_commit_does_not_leave_the_connection_in_a_transaction
        self.assertEqual(one("select count(*) from notebook_tabs where id=?", tab_id), 1)

    def test_a_reference_to_a_missing_record_is_refused(self):
        with SessionLocal() as s:
            s.add(NotebookPage(tab_id_fk=987654321, title="orphan"))
            with self.assertRaises(IntegrityError):
                s.commit()
            s.rollback()

    # On SQLite a commit refused by a deferred foreign key leaves the
    # transaction open; the views close their session without an explicit
    # rollback. app/db.py rolls back any open transaction when a connection
    # returns to the pool, so the next request never sees the refused change.
    @only_sqlite  # PostgreSQL has these natively: sequences, enforced keys, rollback on return
    def test_a_failed_commit_does_not_leave_the_connection_in_a_transaction(self):
        engine.dispose()  # one pooled connection from here on, so the next checkout gets the same one
        tab_id = self._tab_with_page()
        with SessionLocal() as s:
            s.execute(text("delete from notebook_tabs where id=:i"), {"i": tab_id})
            with self.assertRaises(IntegrityError):
                s.commit()
            # no explicit rollback, as in the app's views
        try:
            with engine.connect() as conn:
                in_transaction = conn.connection.dbapi_connection.in_transaction
                still_there = conn.execute(text("select count(*) from notebook_tabs where id=:i"),
                                           {"i": tab_id}).scalar()
        finally:
            engine.dispose()  # never hand the poisoned connection to later tests
        self.assertFalse(in_transaction)
        self.assertEqual(still_there, 1)

    def test_unlinking_children_then_deleting_the_parent_commits(self):
        """Deferred checks: the order of statements inside one transaction
        does not matter, only the state at commit."""
        tab_id = self._tab_with_page()
        with SessionLocal() as s:
            s.execute(text("delete from notebook_tabs where id=:i"), {"i": tab_id})
            s.execute(text("delete from notebook_pages where tab_id_fk=:i"), {"i": tab_id})
            s.commit()
        self.assertEqual(one("select count(*) from notebook_pages where tab_id_fk=?", tab_id), 0)

    def test_deleting_a_mouse_with_weights_and_an_experiment_place_works(self):
        mouse = self.make_mouse(self.a, self.admin, cage=uniq("C"))
        name = uniq("Exp ")
        self.a.post("/colony/experiments/create", data={"name": name})
        exp = one("select id from experiments where name=?", name)
        self.a.post(f"/colony/experiments/{exp}/add-mouse", data={"mouse_row_id": mouse})
        self.a.post(f"/colony/mice/{mouse}/weights/create", data={"grams": "21.5", "weigh_date": T})
        self.assertEqual(one("select count(*) from experiment_mice where mouse_id_fk=?", mouse), 1)
        self.assertEqual(one("select count(*) from mouse_weights where mouse_id_fk=?", mouse), 1)
        r = self.a.post(f"/colony/mice/{mouse}/delete")
        self.assertEqual(r.status_code, 302)
        self.assertIsNone(one("select id from mice where id=?", mouse))
        self.assertEqual(one("select count(*) from mouse_weights where mouse_id_fk=?", mouse), 0)
        self.assertEqual(one("select count(*) from experiment_mice where mouse_id_fk=?", mouse), 0)


class UndoKeepsIdsAndReferences(AppTestCase):
    def test_undo_of_a_plasmid_delete_restores_the_same_id(self):
        pid = self.make_plasmid(self.a)
        self.a.post(f"/plasmids/{pid}/delete")
        self.assertIsNone(one("select id from plasmids where id=?", pid))
        batch = batch_of("plasmids", pid, "delete")
        self.assertIsNotNone(batch)
        self.post(self.a, f"/batches/{batch}/undo")
        self.assertEqual(one("select id from plasmids where id=?", pid), pid)

    def test_undo_of_a_tank_delete_after_its_line_was_deleted_clears_the_link(self):
        line = self.make_line(self.a)
        tank = self.make_tank(self.a, line_id_fk=line)
        self.assertEqual(one("select line_id_fk from tanks where id=?", tank), line)
        self.a.post(f"/zebrafish/tanks/{tank}/delete")
        tank_batch = batch_of("tanks", tank, "delete")
        self.a.post(f"/zebrafish/lines/{line}/delete")
        self.assertIsNone(one("select id from fish_lines where id=?", line))
        r = self.post(self.a, f"/batches/{tank_batch}/undo")
        self.assertEqual(row("select id, line_id_fk from tanks where id=?", tank), (tank, None))
        self.assertIn("no longer exists", r.get_data(as_text=True))

    def test_undo_of_a_create_keeps_a_row_something_still_needs(self):
        code = one("select coalesce(max(mouse_id), 0) from mice") + 1  # mouse numbers are integers
        with app.test_request_context():
            with SessionLocal() as s:
                with audit.batch(s, "create", "test create mouse", "mice") as batch_row:
                    mouse = MouseRecord(mouse_id=code)
                    s.add(mouse)
                s.commit()
                s.add(MouseWeight(mouse_id_fk=mouse.id, grams=20))  # a required link to it
                s.commit()
                result = undo_service.undo(s, s.get(BatchRecord, batch_row.id), self.admin, force=True)
                s.commit()
        self.assertEqual(one("select count(*) from mice where mouse_id=?", code), 1)
        self.assertTrue(any("still used by" in note for note in result["notes"]), result)

    def test_undo_of_a_create_clears_optional_links_to_it_and_removes_it(self):
        key = self.make_stock_module(self.a)
        module = self.stock_module_id(key)
        with app.test_request_context():
            with SessionLocal() as s:
                with audit.batch(s, "create", "test create vial", "stock_units") as batch_row:
                    parent = StockUnit(module_id_fk=module, number=900001)
                    s.add(parent)
                s.commit()
                s.add(StockUnit(module_id_fk=module, number=900002, parent_id_fk=parent.id))
                s.commit()
                parent_id = parent.id
                undo_service.undo(s, s.get(BatchRecord, batch_row.id), self.admin, force=True)
                s.commit()
        self.assertIsNone(one("select id from stock_units where id=?", parent_id))
        self.assertEqual(one("select count(*) from stock_units where module_id_fk=? and number=900002", module), 1)
        self.assertIsNone(one("select parent_id_fk from stock_units where module_id_fk=? and number=900002", module))


# ---------------------------------------------------------------- old databases (child processes)

_BOOT = r"""
import json, os, sys
sys.path.insert(0, os.environ["BIOMANAGER_ROOT"])
from app.app import app  # noqa: F401  (init_database runs here)
from app import db as appdb
print("RESULT " + json.dumps({"enforced": appdb.FOREIGN_KEYS_ENFORCED}))
"""


def boot_app_on(path: str) -> dict:
    """Start the app (init_database) on the SQLite file at `path` in a child
    process; returns what the child reports."""
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{path}", "BIOMANAGER_DATA_DIR": os.path.dirname(path),
           "BIOMANAGER_ROOT": ROOT, "SECRET_KEY": "test"}
    out = subprocess.run([sys.executable, "-c", _BOOT], capture_output=True, text=True, env=env, cwd=ROOT, timeout=120)
    if out.returncode != 0:
        raise AssertionError(f"child failed:\n{out.stderr[-3000:]}")
    line = [ln for ln in out.stdout.splitlines() if ln.startswith("RESULT ")][-1]
    return json.loads(line[len("RESULT "):])


def strip_integrity(con, table: str) -> None:
    """Rewrite `table` the way databases made before integrity.py were:
    no AUTOINCREMENT, foreign keys checked per statement."""
    sql = con.execute("select sql from sqlite_master where name=?", (table,)).fetchone()[0]
    old = sql.replace("AUTOINCREMENT", "").replace("DEFERRABLE INITIALLY DEFERRED", "")
    old = old.replace(f"CREATE TABLE {table}", f"CREATE TABLE {table}__old", 1).replace(
        f'CREATE TABLE "{table}"', f'CREATE TABLE "{table}__old"', 1)
    con.execute(old)
    con.execute(f'insert into "{table}__old" select * from "{table}"')
    con.execute(f'drop table "{table}"')
    con.execute(f'alter table "{table}__old" rename to "{table}"')


@only_sqlite  # PostgreSQL has these natively: sequences, enforced keys, rollback on return
class MigratingAnOldDatabase(unittest.TestCase):
    """One old-style database, booted twice: once to migrate, once to show
    that a second start changes nothing."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="biomanager-integrity-")
        cls.path = os.path.join(cls.dir, "old.db")
        boot_app_on(cls.path)  # a current schema to start from
        con = sqlite3.connect(cls.path)
        con.execute("PRAGMA foreign_keys=OFF")
        for name in ("Alpha", "Beta", "Gamma"):
            con.execute("insert into strains (strain_number, strain_name, strain_background, supplier, description,"
                        " created_by, created_at) values ('', ?, '', '', '', 't', '2026-01-01')", (name,))
        con.commit()
        strip_integrity(con, "strains")
        strip_integrity(con, "mouse_weights")
        con.execute("alter table strains add column legacy_note TEXT DEFAULT ''")
        con.execute("update strains set legacy_note='row ' || id")
        cls.top = con.execute("select max(id) from strains").fetchone()[0]
        # An id that only the audit log remembers (its row was deleted before
        # the migration): it must not be handed out again either.
        con.execute("insert into audit_log (table_name, record_id, record_label, action, changed_by, changed_at,"
                    " details, changes_json) values ('strains', ?, 'gone', 'delete', 't', '2026-01-01 00:00:00', '', '')",
                    (cls.top + 40,))
        con.execute("delete from sqlite_sequence where name='strains'")
        con.commit()
        cls.before = con.execute("select id, strain_name, legacy_note from strains order by id").fetchall()
        con.close()
        cls.first = boot_app_on(cls.path)
        cls.backups_after_first = sorted(f for f in os.listdir(cls.dir) if ".pre-integrity-" in f)
        cls.second = boot_app_on(cls.path)

    def sql_of(self, table):
        con = sqlite3.connect(self.path)
        try:
            return con.execute("select sql from sqlite_master where name=?", (table,)).fetchone()[0]
        finally:
            con.close()

    def test_old_tables_are_rebuilt_with_autoincrement_and_deferred_keys(self):
        self.assertTrue(integrity._is_current(self.sql_of("strains")))
        self.assertTrue(integrity._is_current(self.sql_of("mouse_weights")))

    def test_every_row_and_a_legacy_column_survive_the_rebuild(self):
        con = sqlite3.connect(self.path)
        after = con.execute("select id, strain_name, legacy_note from strains order by id").fetchall()
        con.close()
        self.assertEqual(after, self.before)

    def test_a_backup_is_written_next_to_the_database(self):
        self.assertEqual(len(self.backups_after_first), 1, self.backups_after_first)
        backup = sqlite3.connect(os.path.join(self.dir, self.backups_after_first[0]))
        sql = backup.execute("select sql from sqlite_master where name='strains'").fetchone()[0]
        backup.close()
        self.assertNotIn("AUTOINCREMENT", sql)

    def test_the_sequence_continues_past_ids_only_the_audit_log_remembers(self):
        con = sqlite3.connect(self.path)
        seq = con.execute("select seq from sqlite_sequence where name='strains'").fetchone()[0]
        con.close()
        self.assertGreaterEqual(seq, self.top + 40)

    def test_success_is_recorded_and_foreign_keys_are_enforced(self):
        con = sqlite3.connect(self.path)
        flag = con.execute("select value from app_settings where key=?", (integrity.FLAG_AUTOINCREMENT,)).fetchone()
        con.close()
        self.assertIsNotNone(flag)
        self.assertIn("backup", flag[0])
        self.assertTrue(self.first["enforced"])

    def test_a_second_start_rebuilds_nothing_and_makes_no_new_backup(self):
        backups = sorted(f for f in os.listdir(self.dir) if ".pre-integrity-" in f)
        self.assertEqual(backups, self.backups_after_first)
        self.assertTrue(self.second["enforced"])


@only_sqlite  # PostgreSQL has these natively: sequences, enforced keys, rollback on return
class DanglingReferencesInAnOldDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="biomanager-dangling-")
        cls.path = os.path.join(cls.dir, "dangling.db")
        boot_app_on(cls.path)
        con = sqlite3.connect(cls.path)
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute("insert into mice (mouse_id, cage_id_fk, gender, transgene_1, transgene_2, transgene_3, transgene_4,"
                    " genotype, status, owner, note, created_at, updated_by)"
                    " values (990001, 987654, '', '', '', '', '', '', '', '', '', '2026-01-01', '')")
        con.execute("insert into mouse_weights (mouse_id_fk, weigh_date, grams, notes, recorded_by, created_at)"
                    " values (987654, '2026-01-01', 20, '', 't', '2026-01-01 00:00:00')")
        con.commit()
        con.close()
        cls.first = boot_app_on(cls.path)
        con = sqlite3.connect(cls.path)
        cls.cage_after = con.execute("select cage_id_fk from mice where mouse_id=990001").fetchone()[0]
        cls.weights_after = con.execute("select count(*) from mouse_weights where mouse_id_fk=987654").fetchone()[0]
        cls.flag_after = con.execute("select value from app_settings where key=?", (integrity.FLAG_FOREIGN_KEYS,)).fetchone()[0]
        con.execute("delete from mouse_weights where mouse_id_fk=987654")
        con.commit()
        con.close()
        cls.fixed = boot_app_on(cls.path)
        con = sqlite3.connect(cls.path)
        cls.flag_fixed = con.execute("select value from app_settings where key=?", (integrity.FLAG_FOREIGN_KEYS,)).fetchone()[0]
        con.close()

    def test_a_dangling_nullable_reference_is_cleared(self):
        self.assertIsNone(self.cage_after)

    def test_a_dangling_required_reference_is_kept_not_deleted(self):
        self.assertEqual(self.weights_after, 1)

    def test_enforcement_stays_off_while_a_required_reference_dangles(self):
        self.assertIs(self.first["enforced"], False)
        self.assertTrue(self.flag_after.startswith("off"), self.flag_after)

    def test_once_fixed_enforcement_turns_on_at_the_next_start(self):
        self.assertIs(self.fixed["enforced"], True)
        self.assertEqual(self.flag_fixed, "on")


if __name__ == "__main__":
    unittest.main()
