"""A new lab's first run: it starts empty, the setup survey creates only
what the lab keeps (with the details asked for), and Getting started on the
home page walks people through their first steps (app/lab.py,
app/lab_routes.py)."""
from tests.base import *  # noqa: F401,F403
from tests.base import ROOT, execute, one, uniq, user_id

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

from app.app import app
from app.db import SessionLocal
from tests.test_lab import PASSWORD, LabSettingsCase, real_user

# Run in a separate process: a brand-new installation, answered survey and all.
FRESH_LAB = textwrap.dedent("""
    import json, os, sys
    sys.path.insert(0, os.environ["ROOT"])
    from app.app import app
    from app import security
    from app.db import SessionLocal, engine
    from app.models import UserAccount

    def q(sql):
        with engine.connect() as con:
            return [tuple(r) for r in con.exec_driver_sql(sql).fetchall()]

    before = {"stocks": q("select key from stock_modules"), "inventories": q("select key from inventory_modules"),
              "features": dict(q("select key, value from app_settings where key like 'feature:%'"))}
    with SessionLocal() as s:
        s.add(UserAccount(username="pi", password_hash="x", role="admin"))
        s.commit()
        user = s.query(UserAccount).filter_by(username="pi").one()
        uid, stamp = user.id, None
        with app.app_context():
            stamp = security.session_stamp(user)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"], sess["auth"] = uid, stamp
    sidebar_before = client.get("/setup").get_data(as_text=True)
    client.post("/setup", data={
        "feature:colony": "1", "name:colony": "Mouse room B",
        "racks:count": "2", "racks:rows": "4", "racks:cols": "6", "racks:labels": "numbers",
        "stock:fly": "1", "temps:fly": ["18", "29"],
        "inventory:orders": "1", "name:inventory:orders": "Purchasing",
        "feature:calendar": "1",
    })
    home = client.get("/home").get_data(as_text=True)
    print(json.dumps({
        "before": before,
        "sidebar_before_has_mice": 'href="/colony' in sidebar_before.split("</aside>")[0],
        "stocks": q("select kind, label, json_extract(settings, '$.default_temperature') from stock_modules"),
        "incubators": sorted(q("select name, temperature from stock_incubators")),
        "inventories": q("select kind, label from inventory_modules"),
        "racks": q("select name, rows, cols, naming from mouse_racks"),
        "features": dict(q("select key, value from app_settings where key like 'feature:%'")),
        "colony_label": q("select value from app_settings where key='db_label:colony'"),
        "home_has_getting_started": "Getting started" in home,
    }))
""")


class ANewLab(unittest.TestCase):
    """A fresh installation, in its own process and data folder."""

    @classmethod
    def setUpClass(cls):
        if os.environ.get("BIOMANAGER_TEST_DATABASE_URL"):
            raise unittest.SkipTest("the fresh lab runs on its own SQLite file")
        with tempfile.TemporaryDirectory() as folder:
            env = {k: v for k, v in os.environ.items() if k != "BIOMANAGER_SEED_DEFAULTS"}
            env.update(ROOT=ROOT, BIOMANAGER_DATA_DIR=folder, DATABASE_URL=f"sqlite:///{folder}/fresh.db",
                       SECRET_KEY="fresh-lab-test-key")
            done = subprocess.run([sys.executable, "-c", FRESH_LAB], env=env, capture_output=True, text=True,
                                  timeout=120)
        if done.returncode != 0:
            raise AssertionError(done.stderr[-3000:])
        cls.lab = json.loads(done.stdout.strip().splitlines()[-1])

    def test_nothing_exists_before_the_survey(self):
        before = self.lab["before"]
        self.assertEqual((before["stocks"], before["inventories"]), ([], []))
        self.assertEqual({k: v for k, v in before["features"].items() if k in ("feature:colony", "feature:zebrafish",
                                                                             "feature:plasmids")},
                         {"feature:colony": "off", "feature:zebrafish": "off", "feature:plasmids": "off"})
        self.assertFalse(self.lab["sidebar_before_has_mice"])

    def test_the_survey_creates_only_what_was_ticked(self):
        self.assertEqual([kind for kind, *_ in self.lab["stocks"]], ["fly"])
        self.assertEqual(self.lab["inventories"], [["orders", "Purchasing"]])
        features = self.lab["features"]
        self.assertEqual((features["feature:colony"], features["feature:zebrafish"], features["feature:plasmids"],
                          features["feature:notebook"]), ("on", "off", "off", "off"))

    def test_its_details_are_used(self):
        self.assertEqual(self.lab["colony_label"], [["Mouse room B"]])
        self.assertEqual(len(self.lab["racks"]), 2)
        name, rows, cols, naming = self.lab["racks"][0]
        self.assertEqual((name, rows, cols), ("Rack 1", 4, 6))
        self.assertEqual((json.loads(naming)["rows"], json.loads(naming)["separator"]), ("numbers", "-"))
        self.assertEqual(self.lab["incubators"], [["Incubator 18 °C", "18"], ["Incubator 29 °C", "29"]])
        # 25 °C was not ticked, so the default temperature is one the lab has.
        self.assertEqual(self.lab["stocks"][0][2], "18")

    def test_home_then_shows_getting_started(self):
        self.assertTrue(self.lab["home_has_getting_started"])


class GettingStarted(LabSettingsCase):
    KEYS = LabSettingsCase.KEYS

    def setUp(self):
        super().setUp()
        self.set("lab_setup_done", "2026-01-01T00:00:00")

    def login(self, username):
        client = app.test_client()
        r = client.post("/login", data={"username": username, "password": PASSWORD})
        return client, r.headers["Location"]

    def test_someone_new_starts_at_home_until_it_is_hidden(self):
        member = real_user()
        client, landing = self.login(member)
        self.assertEqual(landing, "/home")
        card = 'id="getting-started-title"'
        self.assertIn(card, client.get("/home").get_data(as_text=True))
        client.post("/getting-started/hide")
        self.assertNotIn(card, client.get("/home").get_data(as_text=True))
        _client, landing = self.login(member)
        self.assertEqual(landing, "/colony")

    def test_a_chosen_start_page_still_wins(self):
        member = real_user()
        execute("update users set default_landing='calendar' where username=?", member)
        _client, landing = self.login(member)
        self.assertEqual(landing, "/calendar")

    def test_opening_the_guide_and_printing_cards_tick_their_steps(self):
        member = real_user()
        client, _ = self.login(member)
        uid = user_id(member)
        self.assertIsNone(one("select value from app_settings where key=?", f"did:{uid}:guide"))
        self.assertEqual(client.post("/milestone/guide").status_code, 204)
        self.assertTrue(one("select value from app_settings where key=?", f"did:{uid}:guide"))
        client.get("/labels/cards/cages")
        self.assertTrue(one("select value from app_settings where key=?", f"did:{uid}:cage_cards"))

    def test_the_steps_follow_what_the_lab_keeps(self):
        self.survey(self.a, feature__plasmids=False)
        html = self.get_ok(self.a, "/home")
        self.assertIn("Bring in your mice", html)
        self.assertNotIn("Add a plasmid", html)

    def test_the_guide_link_goes_to_the_website(self):
        r = self.m.get("/guide?section=mice")
        self.assertEqual(r.headers["Location"], "https://gaspolymerase.github.io/biomanager-app/guide.html#mice")
        self.assertIn("guide.html", self.get_ok(self.m, "/home"))  # Help in the sidebar
