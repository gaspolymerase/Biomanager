"""The page before signing in (app.py hello): what BioManager is, what the
lab keeps, the guide, and the way in."""
from __future__ import annotations

# tests.base first: it points the app at a throwaway database before app is imported.
from tests.base import AppTestCase, one
from app.app import app  # noqa: E402


class HelloTests(AppTestCase):
    def anonymous(self):
        return app.test_client()

    def test_signed_out_the_front_page_introduces_the_app(self):
        r = self.anonymous().get("/")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        for text in ("What it does for you", 'href="/login"', 'href="/register"', "guide.html#excel", "Getting started"):
            self.assertIn(text, html)

    def test_it_lists_the_labs_databases_but_not_personal_ones(self):
        self.a.post("/inventory/new", data={"preset": "custom", "label": "Secret stash", "audience": "me"})
        html = self.anonymous().get("/").get_data(as_text=True)
        section = html[html.index("In this lab"):]
        section = section[:section.index("</section>")]
        self.assertIn("Reagents", section)
        self.assertNotIn("Secret stash", section)

    def test_signed_in_the_front_page_is_the_app(self):
        r = self.m.get("/")
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("What it does for you", self.m.get("/", follow_redirects=True).get_data(as_text=True))

    def test_from_the_internet_it_is_still_only_the_guest_page(self):
        r = self.anonymous().get("/", headers={"X-BioManager-Entry": "internet"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("/guest", r.headers["Location"])

    def test_sign_in_links_back_to_it(self):
        html = self.anonymous().get("/login").get_data(as_text=True)
        self.assertIn("What BioManager does", html)
