"""Home layouts: Classic, Tracks and Freezer (app/home_layouts.py).

Each person picks one; it is kept for them alone. Tracks and Freezer read
the same agenda the Classic cards show."""
from __future__ import annotations

import re

from tests.base import AppTestCase, client_for, days_ago, make_user, uniq


class HomeLayoutTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.post(self.m, "/home/layout", {"layout": "classic"})

    def home(self, client=None, query=""):
        return self.get_ok(client or self.m, "/home" + query)

    def test_classic_is_the_default(self):
        fresh = client_for(make_user(uniq("fresh")))
        html = self.get_ok(fresh, "/home")
        self.assertIn("Mice older than 30 weeks", html)
        self.assertRegex(html, re.compile(r'value="classic"[^>]*aria-pressed="true"'))
        self.assertNotIn('class="trk"', html)

    def test_switching_is_kept_per_person(self):
        self.post(self.m, "/home/layout", {"layout": "tracks"})
        self.assertIn('class="trk"', self.home())
        self.assertIn('class="trk"', self.home())
        self.assertNotIn('class="trk"', self.home(self.o))

    def test_an_unknown_layout_falls_back_to_classic(self):
        self.post(self.m, "/home/layout", {"layout": "tracks"})
        self.post(self.m, "/home/layout", {"layout": "nonsense"})
        self.assertIn("Mice older than 30 weeks", self.home())

    def test_settings_saves_the_layout_too(self):
        self.post(self.m, "/settings", {"action": "profile", "display_name": "", "home_layout": "freezer"})
        self.assertIn('class="frz"', self.home())
        self.assertIn('<option value="freezer" selected>Freezer</option>', self.get_ok(self.m, "/settings"))

    def test_settings_without_the_field_leaves_the_layout_alone(self):
        self.post(self.m, "/home/layout", {"layout": "tracks"})
        self.post(self.m, "/settings", {"action": "profile", "display_name": ""})
        self.assertIn('class="trk"', self.home())


class TracksTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.post(self.m, "/home/layout", {"layout": "tracks"})

    def test_a_weaning_lands_on_its_day(self):
        colony = self.make_colony(self.m, self.member, n_mice=1, dob=days_ago(19))
        html = self.get_ok(self.m, "/home")
        self.assertIn(f"Wean Litter {colony['litter']} · cage {colony['cage']}", html)
        self.assertIn("Weaning · P21", html)

    def test_mice_past_30_weeks_are_overdue(self):
        colony = self.make_colony(self.m, self.member, n_mice=1, dob=days_ago(30 * 7 + 10))
        html = self.get_ok(self.m, "/home")
        self.assertIn("Past 30 w:", html)
        self.assertIn(f"cage {colony['cage']}", html)

    def test_span_chooses_the_days_and_ignores_odd_values(self):
        self.assertIn("7 d", self.get_ok(self.m, "/home?span=7"))
        self.assertIn("28 d", self.get_ok(self.m, "/home?span=28"))
        self.assertIn("14 d", self.get_ok(self.m, "/home?span=999"))
        self.assertIn("14 d", self.get_ok(self.m, "/home?span=abc"))


class FreezerTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.post(self.m, "/home/layout", {"layout": "freezer"})

    def test_work_in_a_placed_cage_is_on_the_pull_list_and_ringed_on_the_rack(self):
        rack = uniq("Rack")
        self.m.post("/colony/racks/save", data={"id": "", "name": rack, "rows": "3", "cols": "3"})
        rack_id = self.get_rack(rack)
        colony = self.make_colony(self.m, self.member, n_mice=1, dob=days_ago(30 * 7 + 10),
                                  rack_id=str(rack_id), position="B2")
        html = self.get_ok(self.m, "/home")
        self.assertIn(f"cage {colony['cage']} · {rack} · B2", html)
        box = html[html.index(f">{rack}<"):]
        self.assertIn("frz-hole is-full is-red", box[:box.index("</article>")])
        self.assertIn(f"<span>{colony['cage']}</span>", box)

    @staticmethod
    def get_rack(name: str) -> int:
        from tests.base import one
        return one("select id from mouse_racks where name=?", name)
