"""The app in English or Chinese (app/i18n.py): who gets which language, and
that every translation keeps the values its English carries."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from tests.base import *  # noqa: F401,F403
from tests.base import AppTestCase, app, client_for, make_user, uniq

from app import i18n

ROOT = Path(__file__).resolve().parent.parent
ZH = "zh-CN,zh;q=0.9,en;q=0.8"


class WhichLanguage(unittest.TestCase):
    def test_the_first_language_the_browser_asks_for_that_the_app_has(self):
        self.assertEqual(i18n.from_header(ZH), "zh")
        self.assertEqual(i18n.from_header("en-US,en;q=0.9,zh;q=0.8"), "en")
        self.assertEqual(i18n.from_header("fr-FR,zh-TW;q=0.5"), "zh")
        self.assertEqual(i18n.from_header("en;q=0.1,zh;q=0.9"), "zh")
        self.assertEqual(i18n.from_header(""), "en")
        self.assertEqual(i18n.from_header("de"), "en")


class TheSignInPage(AppTestCase):
    def test_a_chinese_browser_gets_chinese_and_others_english(self):
        c = app.test_client()
        zh = c.get("/login", headers={"Accept-Language": ZH}).get_data(as_text=True)
        self.assertIn('<html lang="zh-CN">', zh)
        self.assertIn("登录", zh)
        en = app.test_client().get("/login", headers={"Accept-Language": "en-US"}).get_data(as_text=True)
        self.assertIn('<html lang="en">', en)
        self.assertIn("Sign in", en)
        self.assertNotIn("登录", en)

    def test_the_switch_is_remembered_by_this_browser(self):
        c = app.test_client()
        r = c.post("/language", data={"language": "zh", "next": "/login"},
                   headers={"Accept-Language": "en-US"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/login"))
        self.assertIn("登录", c.get("/login", headers={"Accept-Language": "en-US"}).get_data(as_text=True))

    def test_the_switch_goes_back_only_to_this_site(self):
        r = app.test_client().post("/language", data={"language": "zh", "next": "//evil.example/x"})
        self.assertNotIn("evil.example", r.headers["Location"])


class APersonsChoice(AppTestCase):
    def test_settings_keeps_the_language_for_that_person(self):
        who = make_user(uniq("lang"))
        c = client_for(who)
        self.assertEqual(c.post("/settings", data={"action": "language", "language": "zh"},
                                headers={"Accept-Language": "en-US"}).status_code, 302)
        page = c.get("/settings", headers={"Accept-Language": "en-US"}).get_data(as_text=True)
        self.assertIn('<html lang="zh-CN">', page)
        # A new sign-in elsewhere (an English browser) still gets their choice.
        other = client_for(who)
        self.assertIn('<html lang="zh-CN">', other.get("/settings", headers={"Accept-Language": "en-US"}).get_data(as_text=True))
        # Automatic again: the browser decides.
        c.post("/settings", data={"action": "language", "language": ""})
        self.assertIn('<html lang="en">', client_for(who).get("/settings", headers={"Accept-Language": "en-US"}).get_data(as_text=True))

    def test_the_guide_link_follows_the_language(self):
        who = make_user(uniq("guide"))
        c = client_for(who)
        r = c.get("/guide", headers={"Accept-Language": ZH})
        self.assertIn("/zh/guide.html", r.headers.get("Location", ""))


class TheTranslations(unittest.TestCase):
    """Every catalog is valid JSON, and each translation keeps the %(name)s
    values of its English: a missing one would show the raw placeholder."""

    def test_each_translation_keeps_its_values(self):
        for path in sorted((ROOT / "app" / "translations").glob("*/*.json")):
            words = json.loads(path.read_text(encoding="utf-8"))
            for english, translated in words.items():
                if translated:
                    self.assertEqual(i18n.placeholders(english), i18n.placeholders(translated),
                                     f"{path.name}: {english!r}")

    def test_no_english_appears_twice_with_different_chinese(self):
        seen: dict[str, tuple[str, str]] = {}
        for path in sorted((ROOT / "app" / "translations" / "zh").glob("*.json")):
            for english, translated in json.loads(path.read_text(encoding="utf-8")).items():
                if english in seen and seen[english][1] != translated:
                    self.fail(f"{english!r}: {seen[english][0]} says {seen[english][1]!r}, "
                              f"{path.name} says {translated!r}")
                seen[english] = (path.name, translated)

    def test_every_wrapped_text_in_a_translated_template_has_its_chinese(self):
        """A template that uses _() is translated whole: each of its texts has
        an entry (a template not yet translated has no _() and stays English)."""
        zh = i18n.catalog("zh")
        env = app.jinja_env
        missing = []
        for path in sorted((ROOT / "app" / "templates").rglob("*.html")):
            source = path.read_text(encoding="utf-8")
            for _lineno, _func, message in env.extract_translations(source):
                for text in ([message] if isinstance(message, str) else [m for m in message if m]):
                    if text not in zh:
                        missing.append(f"{path.relative_to(ROOT)}: {text!r}")
        self.assertEqual(missing, [], "\n".join(missing[:40]))

    def test_every_gettext_in_python_has_its_chinese(self):
        zh = i18n.catalog("zh")
        call = re.compile(r'\bgettext\(\s*"((?:[^"\\]|\\.)*)"')
        missing = []
        for path in sorted((ROOT / "app").glob("*.py")):
            for text in call.findall(path.read_text(encoding="utf-8")):
                text = text.encode().decode("unicode_escape") if "\\" in text else text
                if text not in zh:
                    missing.append(f"{path.name}: {text!r}")
        self.assertEqual(missing, [], "\n".join(missing[:40]))
