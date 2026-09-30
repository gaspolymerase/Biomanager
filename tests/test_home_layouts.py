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


class CustomizeHomeTests(AppTestCase):
    """Each person chooses Home's cards, their order and which are wide."""

    def cards(self, html):
        return re.findall(r'data-home-card="([a-z_]+)"', html)

    def save(self, client, order, show, wide=()):
        return self.post(client, "/home/cards", {"order": order, "show": show, "wide": list(wide)})

    def test_a_new_person_gets_the_usual_cards_and_the_optional_ones_off(self):
        fresh = client_for(make_user(uniq("fresh")))
        got = self.cards(self.get_ok(fresh, "/home"))
        self.assertLess(got.index("stats"), got.index("sac"))
        for off in ("todos", "bookings", "notebook", "utilities"):
            self.assertNotIn(off, got)
        self.assertIn('id="home-customize"', self.get_ok(fresh, "/home"))

    def test_hiding_reordering_and_widening_is_kept_for_that_person_only(self):
        who = client_for(make_user(uniq("picky")))
        order = ["utilities", "calendar", "sac", "stats", "databases", "weanings", "geno", "orders"]
        self.save(who, order, show=["utilities", "calendar", "sac", "stats"], wide=["calendar"])
        html = self.get_ok(who, "/home")
        self.assertEqual([k for k in self.cards(html) if k in order], ["utilities", "calendar", "sac", "stats"])
        self.assertIn('class="home-card is-wide" data-home-card="calendar"', html)
        self.assertIn("All utilities", html)                     # the Calculators card is on
        self.assertIn("weanings", self.cards(self.get_ok(self.m, "/home")))
        # Back to the usual.
        self.post(who, "/home/cards", {"reset": "1"})
        self.assertIn("weanings", self.cards(self.get_ok(who, "/home")))

    def test_the_optional_cards_show_their_own_things(self):
        who_name = make_user(uniq("busy"))
        who = client_for(who_name)
        title = uniq("Order primers ")
        who.post("/calendar/items", data='{"kind": "task", "title": "%s", "start": "%sT00:00:00", "isAllday": true}' % (title, days_ago(0)),
                 content_type="application/json")
        order = ["todos", "notebook", "bookings"]
        self.save(who, order, show=order)
        html = self.get_ok(who, "/home")
        self.assertIn(title, html)
        self.assertIn("Recent notebook pages", html)
        self.assertIn("No instrument booked in the next week.", html)
