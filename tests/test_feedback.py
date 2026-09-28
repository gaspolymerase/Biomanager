"""Send feedback and the usage report (app/feedback.py): kept in the lab,
sent on only by the person, and counts without names."""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

# tests.base first: it points the app at a throwaway database before app is imported.
from tests.base import AppTestCase, count, location, one, uniq


class Feedback(AppTestCase):
    def send(self, client, text, **extra):
        return client.post("/feedback", data={"text": text, "kind": "idea", **extra})

    def test_kept_for_the_lab_and_offered_as_an_issue(self):
        text = uniq("It would help to print tube labels from the grid ")
        r = self.send(self.m, text, **{"from": "http://localhost/inventory/samples?view=grid"})
        self.assertEqual(r.status_code, 302)
        row = one("select id from feedback where text=?", text)
        self.assertEqual(one("select page from feedback where id=?", row), "/inventory/samples?view=grid")
        self.assertTrue(one("select app_version from feedback where id=?", row))
        page = self.get_ok(self.m, location(r))
        self.assertIn("Open as a GitHub issue", page)
        link = next(part.split('"')[0] for part in page.split('href="')
                    if part.startswith("https://github.com/gaspolymerase/biomanager-app/issues/new"))
        query = parse_qs(urlparse(link.replace("&amp;", "&")).query)
        self.assertTrue(query["title"][0].startswith("An idea: It would help"))
        self.assertIn("/inventory/samples?view=grid", query["body"][0])
        self.assertNotIn(self.member, query["body"][0])               # not who sent it
        self.assertNotIn("localhost", query["body"][0])               # nor the server's address

    def test_admins_read_it_and_mark_it_done(self):
        text = uniq("Sac button unclear ")
        self.send(self.m, text)
        other = uniq("Admin's own note ")
        self.send(self.a, other)
        self.assertIn(text, self.get_ok(self.a, "/feedback"))
        self.assertNotIn(other, self.get_ok(self.m, "/feedback"))    # a member sees only their own
        self.assertGreaterEqual(count("notifications", "recipient_username=? and title like ?",
                                      self.admin, "%sent feedback"), 1)
        row = one("select id from feedback where text=?", text)
        self.assertEqual(self.m.post(f"/feedback/{row}/status", data={"status": "done"}).status_code, 403)
        self.a.post(f"/feedback/{row}/status", data={"status": "done"})
        self.assertEqual(one("select status from feedback where id=?", row), "done")

    def test_a_link_from_elsewhere_is_not_kept(self):
        text = uniq("From elsewhere ")
        self.send(self.m, text, **{"from": "https://example.org/secret"})
        self.assertEqual(one("select page from feedback where text=?", text), "")


class Usage(AppTestCase):
    def test_counts_without_names(self):
        self.make_mouse(self.a, self.admin, cage=uniq("C"))
        self.assertEqual(self.m.get("/feedback/usage").status_code, 403)
        html = self.get_ok(self.a, "/feedback/usage")
        self.assertIn("Mouse colony", html)
        from app import feedback
        from app.db import SessionLocal
        with SessionLocal() as s:
            report = feedback.usage(s)
        this_week = report["weeks"][-1]
        self.assertGreaterEqual(this_week["areas"]["Mouse colony"], 1)
        self.assertGreaterEqual(this_week["people"], 1)
        text = feedback.usage_text(report)
        self.assertNotIn(self.admin, text)
        self.assertIn("Mice alive", text)
