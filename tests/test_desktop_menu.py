"""The desktop app's version, update check and menus (desktop_updates.py,
desktop_menu.py). Nothing here reaches GitHub or opens a window."""
from __future__ import annotations

import sys
import unittest
from unittest import mock

# tests.base first: it points the app at a throwaway database (and data folder).
from tests.base import AppTestCase  # noqa: F401
import desktop_menu  # noqa: E402
import desktop_updates as du  # noqa: E402

RELEASE = {"version": "0.6.0", "notes": "New things", "page": "https://example.org/r", "download": "https://example.org/d.zip"}


class Versions(unittest.TestCase):
    def test_comparing(self):
        self.assertTrue(du.is_newer("0.6.0", "0.5.0"))
        self.assertTrue(du.is_newer("v0.5.1", "0.5"))
        self.assertTrue(du.is_newer("0.10.0", "0.9.9"))
        self.assertFalse(du.is_newer("0.5.0", "0.5.0+dev"))
        self.assertFalse(du.is_newer("0.4.2", "0.5.0"))
        self.assertFalse(du.is_newer("nonsense", "0.5.0"))

    def test_a_build_reads_its_version_file(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "VERSION").write_text("0.7.1\n")
            with mock.patch.object(sys, "_MEIPASS", tmp, create=True):
                self.assertEqual(du.version(), "0.7.1")

    def test_notes_become_plain_text(self):
        text = du.summary("## What's new\n\n- **Import** from [Excel](https://x)\n<!-- hidden -->\n`code`")
        self.assertEqual(text, "What's new\n\n- Import from Excel\n\ncode")
        self.assertTrue(du.summary("word " * 400).endswith("…"))

    def test_notes_show_what_is_new_not_the_downloads(self):
        notes = ("**Download** the file below.\n\n| File | For |\n| --- | --- |\n| `a.zip` | Macs |\n\n"
                 "**New in 0.6.0: sheets**\n\n- **Import from Excel** in every database.\n\n"
                 "Update a lab server: unpack it.\n\n**First launch:** right-click.")
        self.assertEqual(du.summary(notes), "New in 0.6.0: sheets\n\n- Import from Excel in every database.")

    def test_the_file_for_this_computer(self):
        names = ["BioManager-macOS-AppleSilicon.zip", "BioManager-macOS-Intel.zip", "BioManager-Windows.zip",
                 "BioManager-Linux.AppImage"]
        with mock.patch.object(du.sys, "platform", "darwin"), mock.patch.object(du.platform, "machine", return_value="arm64"):
            self.assertEqual(du.asset_for_this_computer(names), "BioManager-macOS-AppleSilicon.zip")
        with mock.patch.object(du.sys, "platform", "win32"):
            self.assertEqual(du.asset_for_this_computer(names), "BioManager-Windows.zip")
        with mock.patch.object(du.sys, "platform", "linux"):
            self.assertEqual(du.asset_for_this_computer(names[:3]), None)


class Checking(unittest.TestCase):
    def setUp(self):
        du.save_prefs(**du.DEFAULT_PREFS)

    def check(self, manual, fetch=lambda: RELEASE, now=1_000_000.0, current="0.5.0"):
        with mock.patch.object(du, "version", return_value=current):
            return du.check(manual=manual, now=now, fetch=fetch)

    def test_asking_says_newer_current_or_why_not(self):
        self.assertEqual(self.check(True)["state"], "newer")
        self.assertEqual(self.check(True, current="0.6.0"), {"state": "current", "version": "0.6.0"})

        def offline():
            raise OSError("no network")
        answer = self.check(True, fetch=offline)
        self.assertEqual(answer["state"], "error")
        self.assertIn("no network", answer["message"])

    def test_the_automatic_check_is_daily_quiet_and_can_be_off(self):
        self.assertEqual(self.check(False)["state"], "newer")
        self.assertEqual(self.check(False, now=1_000_000.0 + 3600)["state"], "quiet")      # checked an hour ago
        self.assertEqual(self.check(False, now=1_000_000.0 + 2 * 86400)["state"], "newer")

        def offline():
            raise OSError("no network")
        self.assertEqual(self.check(False, fetch=offline, now=5_000_000.0)["state"], "quiet")
        du.save_prefs(check_updates=False)
        self.assertEqual(self.check(False, now=9_000_000.0)["state"], "quiet")

    def test_a_skipped_version_is_only_offered_when_asked(self):
        du.save_prefs(skip_version="0.6.0")
        self.assertEqual(self.check(False)["state"], "quiet")
        self.assertEqual(self.check(True)["state"], "newer")


class Bridge(unittest.TestCase):
    def test_the_go_menu_keeps_only_this_app_s_pages(self):
        api = desktop_menu.DesktopApi()
        with mock.patch.dict(sys.modules, {"PyObjCTools": mock.MagicMock(), "PyObjCTools.AppHelper": mock.MagicMock()}):
            api.set_nav([
                {"label": "Databases", "links": [
                    {"label": "Mouse colony", "url": "/colony?view=mice"},
                    {"label": "Elsewhere", "url": "https://evil.example/"},
                    {"label": "Also elsewhere", "url": "//evil.example/x"},
                    {"label": "", "url": "/nameless"},
                ]},
                {"label": "Empty", "links": [{"label": "x", "url": "javascript:alert(1)"}]},
                "not a section",
            ])
        self.assertEqual(desktop_menu._state["nav"],
                         [{"label": "Databases", "links": [{"label": "Mouse colony", "url": "/colony?view=mice"}]}])

    @unittest.skipUnless(__import__("importlib").util.find_spec("webview"), "pywebview isn't installed (CI)")
    def test_windows_and_linux_get_plain_menus(self):
        titles = [m.title for m in desktop_menu.plain_menus()]
        self.assertEqual(titles, ["File", "Go", "Help"])
