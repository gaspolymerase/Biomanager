"""Signing a notebook page, which locks it (app/signatures.py)."""
from __future__ import annotations

import json

# tests.base first: it points the app at a throwaway database before app is imported.
from tests.base import AppTestCase, client_for, count, location, make_user, one, uniq
from app import signatures  # noqa: E402

PASSWORD = "correct horse battery"


class Signing(AppTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from werkzeug.security import generate_password_hash
        from tests.base import execute
        cls.author = make_user(uniq("author"))
        cls.witness_user = make_user(uniq("witness"))
        for u in (cls.author, cls.witness_user):
            execute("update users set password_hash=? where username=?", generate_password_hash(PASSWORD), u)
        cls.c = client_for(cls.author)
        cls.w = client_for(cls.witness_user)

    def new_page(self, body="Western blot of lysates.\n"):
        r = self.c.post("/notebook/api/pages/new", json={"title": uniq("Blot ")})
        page = r.get_json()["page_id"]
        self.c.post(f"/notebook/pages/{page}/update", data={"body": body})
        self.c.post(f"/notebook/api/pages/{page}/shares", json={"username": self.witness_user, "role": "edit"})
        return page

    def sign(self, client, page, **body):
        return client.post(f"/notebook/api/pages/{page}/sign", json={"password": PASSWORD, **body})

    def test_signing_locks_the_page_everywhere(self):
        page = self.new_page()
        self.assertEqual(self.sign(self.c, page, password="wrong").status_code, 403)       # who you are, confirmed
        r = self.sign(self.c, page)
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertTrue(r.get_json()["locked"])
        entry = r.get_json()["entries"][0]
        body = one("select body from notebook_pages where id=?", page)
        title = one("select title from notebook_pages where id=?", page)
        self.assertEqual(entry["sha256"], signatures.fingerprint(title, body))
        # No one changes it: the owner, an editor, live or otherwise.
        self.assertEqual(self.c.post(f"/notebook/pages/{page}/update", data={"body": "changed"}).status_code, 423)
        self.assertEqual(self.w.post(f"/notebook/pages/{page}/update", data={"body": "changed"}).status_code, 423)
        push = self.c.post(f"/notebook/api/pages/{page}/sync", json={"client": "x", "updates": ["AAAA"], "gen": 0})
        self.assertEqual(push.status_code, 423)
        self.assertEqual(self.c.post(f"/notebook/api/pages/{page}/meta", json={"tags": "x"}).status_code, 423)
        self.assertEqual(one("select body from notebook_pages where id=?", page), body)
        # It opens read-only, and can't be deleted.
        html = self.get_ok(self.c, f"/notebook?page={page}")
        self.assertIn("nb-signed-callout", html)
        self.assertNotIn('data-more="delete"', html)
        self.c.post(f"/notebook/pages/{page}/delete", headers={"X-Requested-With": "fetch"})
        self.assertEqual(count("notebook_pages", "id=?", page), 1)

    def test_a_witness_and_an_amendment_stay_in_the_record(self):
        page = self.new_page()
        self.sign(self.c, page)
        self.assertEqual(self.sign(self.c, page, action="witness").status_code, 409)       # not the signer
        self.assertEqual(self.sign(self.w, page, action="witness").status_code, 200)
        self.assertEqual(self.sign(self.w, page, action="amend", reason="typo").status_code, 403)   # the owner amends
        self.assertEqual(self.sign(self.c, page, action="amend", reason="").status_code, 400)
        r = self.sign(self.c, page, action="amend", reason="Wrong antibody dilution written")
        self.assertFalse(r.get_json()["locked"])
        self.assertEqual(self.c.post(f"/notebook/pages/{page}/update", data={"body": "Fixed: 1:5000"}).status_code, 200)
        r = self.sign(self.c, page)
        entries = r.get_json()["entries"]
        self.assertEqual([e["action"] for e in entries], ["sign", "witness", "amend", "sign"])
        self.assertFalse(entries[0]["matches"])                 # the first signature was of the old text
        self.assertTrue(entries[-1]["matches"])

    def test_a_live_experiment_in_the_page_is_frozen_when_signed(self):
        r = self.c.post("/colony/experiments/create", data={"name": uniq("TAM ")})
        exp = int(location(r).rsplit("/", 1)[1])
        page = self.new_page("Results:\n\n```experiment\n" + json.dumps({"id": exp, "show": ["plan"]}) + "\n```\n")
        self.sign(self.c, page)
        body = one("select body from notebook_pages where id=?", page)
        data = json.loads(body.split("```experiment\n")[1].split("\n```")[0])
        self.assertIn("frozen", data)
        self.assertEqual(data["frozen"]["experiment"]["id"], exp)

    def test_nothing_asks_for_a_signature(self):
        page = self.new_page()
        self.assertEqual(self.c.post(f"/notebook/pages/{page}/update", data={"body": "edited freely"}).status_code, 200)
        self.assertFalse(signatures.is_locked(__import__("app.db", fromlist=["SessionLocal"]).SessionLocal(), page))
