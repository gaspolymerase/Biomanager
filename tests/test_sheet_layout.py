"""Sheets laid out for reading at a glance: the dot before an animal's ID
says how old it is (blue young, green adult, red old; red for an expired
reagent), the bottom bar's New button adds an empty row to type in, a
cage's number is typed over to renumber it, and every database puts its
Table / grid / cards switch in the same place."""
from __future__ import annotations

import re
import unittest
from datetime import date, timedelta
from types import SimpleNamespace

from tests.base import *  # noqa: F401,F403
from tests.base import AppTestCase, days_ago, one, uniq

from app import life_stage, stock_service


def dot_of(html: str, row_marker: str) -> str:
    """The life dot's tag in the row that starts at `row_marker`."""
    start = html.index(row_marker)
    m = re.search(r'<span class="life-dot[^>]*>', html[start:])
    return m.group(0) if m else ""


class LifeStageBands(unittest.TestCase):
    def test_a_mouse_is_young_under_8_weeks_adult_to_30_and_old_past_30(self):
        self.assertEqual([life_stage.stage("mouse", d) for d in (0, 55, 56, 210, 211)],
                         ["young", "young", "adult", "adult", "old"])

    def test_a_zebrafish_is_young_under_3_months_and_old_past_18(self):
        self.assertEqual([life_stage.stage("zebrafish", d) for d in (10, 90, 548, 600)],
                         ["young", "adult", "adult", "old"])

    def test_no_age_or_no_bands_means_no_colour(self):
        self.assertEqual((life_stage.stage("mouse", None), life_stage.stage("mouse", ""),
                          life_stage.stage("custom", 400)), ("", "", ""))

    def test_the_tooltip_says_what_the_colour_means(self):
        self.assertEqual(life_stage.describe("mouse", "adult"), "adult, 8 weeks to 30 weeks")
        self.assertEqual(life_stage.describe("mouse", "old"), "older than 30 weeks")


class VialStage(unittest.TestCase):
    """A vial is young while its progeny develop, old past its rack's flip."""

    def mv(self):
        mv = SimpleNamespace(s={"ready_label": "Progeny eclose", "flip_verb": "Flip", "default_temperature": "25"},
                             interval=lambda what, temp: {"flip": 14, "develop": 10}[what])
        return mv

    def unit(self, **fields):
        rack = SimpleNamespace(flip_days=None, last_flipped_on=fields.pop("flipped", None), incubator=None)
        return SimpleNamespace(**{"active": True, "ready_on": None, "set_up_on": None, "rack": rack, **fields})

    def test_developing_progeny_are_young(self):
        today = date(2026, 10, 2)
        stage, title = stock_service.unit_stage(self.mv(), self.unit(ready_on=today + timedelta(days=3)), today)
        self.assertEqual(stage, "young")
        self.assertIn("Progeny eclose", title)

    def test_past_the_flip_interval_is_old_and_a_fresh_flip_is_adult(self):
        today = date(2026, 10, 2)
        old = self.unit(set_up_on=today - timedelta(days=20))
        self.assertEqual(stock_service.unit_stage(self.mv(), old, today)[0], "old")
        flipped = self.unit(set_up_on=today - timedelta(days=20), flipped=today - timedelta(days=2))
        self.assertEqual(stock_service.unit_stage(self.mv(), flipped, today)[0], "adult")

    def test_a_discarded_vial_has_no_colour(self):
        self.assertEqual(stock_service.unit_stage(self.mv(), self.unit(active=False)), ("", ""))


class MouseDots(AppTestCase):
    def test_the_mouse_sheet_colours_each_living_mouse_by_age(self):
        young = self.make_mouse(self.m, self.member, litter=uniq("L"), date_of_birth=days_ago(20))
        old = self.make_mouse(self.m, self.member, litter=uniq("L"), date_of_birth=days_ago(250))
        dead = self.make_mouse(self.m, self.member, litter=uniq("L"), date_of_birth=days_ago(250),
                               date_of_death=days_ago(1))
        html = self.get_ok(self.m, "/colony?view=mice&scope=all")

        def marker(row_id):
            return f'data-id="{row_id}"'
        self.assertIn('data-stage="young"', dot_of(html, marker(young)))
        self.assertIn("is-alive", dot_of(html, marker(young)))
        self.assertIn('data-stage="old"', dot_of(html, marker(old)))
        self.assertIn("older than 30 weeks", dot_of(html, marker(old)))
        self.assertNotIn("is-alive", dot_of(html, marker(dead)))   # grey, whatever its age

    def test_a_cage_panel_colours_its_mice_too(self):
        colony = self.make_colony(self.m, self.member, n_mice=1, dob=days_ago(30))
        html = self.get_ok(self.m, "/colony?view=cages&scope=all")
        panel = html[html.index(f'id="cage-detail-{colony["cage_id"]}"'):]
        self.assertIn('data-stage="young"', dot_of(panel, "cage-mice-table"))


class ExpiredItemDot(AppTestCase):
    def test_an_expired_reagent_is_red(self):
        expired = self.make_item(self.a, "reagents", uniq("R"), expires_on=days_ago(2))
        fine = self.make_item(self.a, "reagents", uniq("R"))
        html = self.get_ok(self.a, "/inventory/reagents")
        self.assertIn('data-stage="expired"', dot_of(html, f'<tr data-id="{expired}"'))
        self.assertIn("is-expired", re.search(rf'<tr data-id="{expired}"[^>]*>', html).group(0))
        self.assertNotIn("data-stage", dot_of(html, f'<tr data-id="{fine}"'))


class QuickAdd(AppTestCase):
    """The bottom bar's New button: an empty record at once, back to the
    sheet it came from."""

    def test_each_sheet_has_one_at_the_bottom_left(self):
        for url, action in (("/colony?view=mice&scope=all", "/colony/mice/new-record"),
                            ("/colony?view=cages&scope=all", "/colony/cages/create"),
                            ("/colony?view=litters&scope=all", "/colony/litters/create"),
                            ("/zebrafish?view=tanks", "/zebrafish/tanks/create"),
                            ("/inventory/reagents", "/inventory/reagents/items/save")):
            html = self.get_ok(self.a, url)
            bar = html[html.index('<div class="dt-bottom-bar">'):]
            first = re.search(r"<(form|button|span)\b[^>]*>", bar[len('<div class="dt-bottom-bar">'):]).group(0)
            self.assertIn("data-quick-add", first, url)
            self.assertIn(f'action="{action}"', first, url)

    def test_a_new_mouse_goes_back_to_the_sheet_it_came_from(self):
        before = one("select coalesce(max(mouse_id), 0) from mice")
        back = "http://localhost/colony?view=mice&scope=all"
        r = self.m.post("/colony/mice/new-record", headers={"Referer": back})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["Location"], back)
        self.assertEqual(one("select owner from mice where mouse_id>?", before), self.member)

    def test_an_organism_database_adds_an_empty_record_and_housing_of_yours(self):
        key = self.make_organism_module(self.a)
        mid = self.organism_module_id(key)
        for view, path, table in (("animals", "animal", "organisms"), ("housing", "housing", "organism_housing")):
            html = self.get_ok(self.a, f"/organisms/{key}?view={view}")
            bar = html[html.index('<div class="dt-bottom-bar">'):]
            form = re.search(r"<form[^>]*data-quick-add[^>]*>(.*?)</form>", bar, re.S)
            self.assertIn(f'action="/organisms/{key}/{path}/save"', form.group(0), view)
            fields = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', form.group(1)))
            before = one(f"select count(*) from {table} where module_id_fk=?", mid)
            self.a.post(f"/organisms/{key}/{path}/save", data=fields)
            self.assertEqual(one(f"select count(*) from {table} where module_id_fk=?", mid), before + 1, view)
            self.assertEqual(one(f"select owner from {table} where module_id_fk=? order by id desc limit 1", mid),
                             self.admin, view)

    def test_where_a_record_needs_a_name_first_it_opens_the_form(self):
        html = self.get_ok(self.a, "/colony?view=strains")
        bar = html[html.index('<div class="dt-bottom-bar">'):]
        self.assertIn('data-record-edit="strain-dialog"', bar[:600])


class CageNumber(AppTestCase):
    def setUp(self):
        super().setUp()
        self.code = uniq("C")
        self.cage = self.make_cage(self.m, self.code)

    def renumber(self, new, was=None, client=None):
        return self.autosave(client or self.m, f"/colony/cages/{self.cage}/update",
                             {"cage_id": new, "cage_id_was": self.code if was is None else was})

    def test_typing_over_the_number_renumbers_the_cage_and_its_mice_go_with_it(self):
        mouse = self.make_mouse(self.m, self.member, cage=self.code)
        new = uniq("C")
        r = self.renumber(new)
        self.assertSaved(r)
        self.assertEqual(r.get_json()["row"]["values"]["cage_id"], new)
        self.assertEqual(one("select cage_id from mouse_cages where id=?", self.cage), new)
        self.assertEqual(one("select cage_id_fk from mice where id=?", mouse), self.cage)

    def test_a_number_another_cage_has_is_refused(self):
        taken = uniq("C")
        self.make_cage(self.m, taken)
        r = self.renumber(taken)
        self.assertRefused(r)
        self.assertIn(f"already a cage {taken}", r.get_json()["error"])
        self.assertEqual(one("select cage_id from mouse_cages where id=?", self.cage), self.code)

    def test_no_number_or_new_is_refused(self):
        for typed in ("", "  ", "new"):
            self.assertRefused(self.renumber(typed))
        self.assertEqual(one("select cage_id from mouse_cages where id=?", self.cage), self.code)

    def test_a_stale_row_does_not_put_an_old_number_back(self):
        new = uniq("C")
        self.assertSaved(self.renumber(new))
        # Another cell of a row still showing the old number saves.
        r = self.autosave(self.m, f"/colony/cages/{self.cage}/update",
                          {"cage_id": self.code, "cage_id_was": self.code, "notes": "n"})
        self.assertSaved(r)
        self.assertEqual(one("select cage_id from mouse_cages where id=?", self.cage), new)

    def test_someone_who_cannot_edit_the_cage_cannot_renumber_it(self):
        r = self.renumber(uniq("C"), client=self.o)
        self.assertNotEqual(r.status_code, 200)
        self.assertEqual(one("select cage_id from mouse_cages where id=?", self.cage), self.code)

    def test_the_sheet_shows_the_number_as_a_field_saved_when_you_leave_it(self):
        html = self.get_ok(self.m, "/colony?view=cages&scope=all")
        cell = re.search(rf'<input class="ident cage-number" name="cage_id" form="cage-update-{self.cage}"[^>]*>', html)
        self.assertIsNotNone(cell)
        self.assertIn('data-autosave-on="change"', cell.group(0))
        self.assertIn(f'name="cage_id_was" value="{self.code}"', html)


class LayoutSwitches(AppTestCase):
    def test_plasmids_switch_layouts_above_the_sheet(self):
        html = self.get_ok(self.a, "/plasmids")
        self.assertLess(html.index("plasmid-view-switcher"), html.index('id="plasmids-section"'))

    def test_fish_tanks_switch_layouts_on_their_own_line(self):
        html = self.get_ok(self.a, "/zebrafish?view=tanks")
        nav = html[html.index('aria-label="Tank views"') - 80:]
        self.assertIn('class="dt-chips view-switch"', nav[:200])
        self.assertIn('aria-current="page"', nav[:1200])


if __name__ == "__main__":
    unittest.main()
