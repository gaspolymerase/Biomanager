"""@links from a notebook page to any inventory record ("@antibodies 12"):
the editor's @ menu finds it, the chip's popover describes it, the link
opens it, and the record lists the pages that link it."""
from __future__ import annotations

import json

from tests.base import client_for, make_user, one, uniq
from tests.test_inventory import InventoryCase


class RecordLinks(InventoryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.abs = cls.new_module(cls.a, "antibodies", uniq("Antibodies "))
        cls.name = uniq("anti-GFP ")
        cls.item = cls.make_item(cls.m, cls.abs, cls.name, vendor="Acme", lot="L-4471")
        cls.number = one("select number from inventory_items where id=?", cls.item)

    def new_page(self, client, body: str) -> int:
        r = client.post("/notebook/api/pages/new", data=json.dumps({"title": uniq("Western ")}),
                        content_type="application/json")
        page = r.get_json()["page_id"]
        client.post(f"/notebook/pages/{page}/update", data={"body": body})
        return page

    def test_the_notebook_lists_every_inventory_it_can_link(self):
        html = self.get_ok(self.m, "/notebook")
        types = json.loads(html.split('id="nb-mention-types">', 1)[1].split("</script>", 1)[0])
        self.assertIn(self.abs, [t["key"] for t in types])

    def test_the_at_menu_finds_a_record_by_name_or_lot(self):
        for q in (self.name.split()[-1], "L-4471"):
            got = self.m.get(f"/notebook/search/{self.abs}?q={q}").get_json()
            self.assertEqual([i["id"] for i in got["items"]], [self.number], q)
        got = self.m.get(f"/notebook/search/all?q={self.name.split()[-1]}").get_json()
        self.assertIn({"type": self.abs, "id": self.number}, [{"type": i["type"], "id": i["id"]} for i in got["items"]])

    def test_a_lot_number_typed_comes_before_records_that_have_that_number(self):
        # A busy lab: record #12 in several databases, and a tube of lot 0012.
        for _ in range(14):
            self.make_item(self.a, self.abs, uniq("filler "))
        lot_item = self.make_item(self.m, self.abs, uniq("anti-actin "), lot="0012")
        number = one("select number from inventory_items where id=?", lot_item)
        got = self.m.get("/notebook/search/all?q=0012").get_json()["items"]
        self.assertEqual((got[0]["type"], got[0]["id"]), (self.abs, number))
        got = self.m.get(f"/notebook/search/{self.abs}?q=0012").get_json()["items"]
        self.assertEqual(got[0]["id"], number)
        # "12" is still record #12.
        got = self.m.get(f"/notebook/search/{self.abs}?q=12").get_json()["items"]
        self.assertEqual(got[0]["id"], 12)

    def test_many_matches_in_one_database_fill_the_menu(self):
        stem = uniq("SO-RNA-").replace("_", "")
        for n in range(6):
            self.make_item(self.m, self.abs, f"{stem}{n}")
        got = self.m.get(f"/notebook/search/all?q={stem}").get_json()["items"]
        self.assertEqual(len([i for i in got if i["type"] == self.abs]), 6)

    def test_ctrl_k_finds_a_lot_number(self):
        lot = "0" + "".join(ch for ch in uniq("7") if ch.isdigit())[-5:] + "M4817V"
        item = self.make_item(self.m, self.abs, uniq("anti-actin "), lot=lot)
        got = self.m.get("/search", query_string={"q": lot[:6]}).get_json()["results"]
        self.assertIn(one("select number from inventory_items where id=?", item), [r["id"] for r in got][:3])

    def test_an_order_is_found_by_part_of_its_catalogue_number(self):
        orders = one("select key from inventory_modules where kind='orders' order by id limit 1")
        digits = "".join(ch for ch in uniq("9") if ch.isdigit())[-5:]
        order = self.make_item(self.m, orders, uniq("anti-GAPDH "), catalog_number=f"ab{digits}-100")
        number = one("select number from inventory_items where id=?", order)
        got = self.m.get(f"/notebook/search/order?q={digits}").get_json()["items"]
        self.assertIn(number, [i["id"] for i in got])
        self.assertTrue(self.m.get(f"/notebook/lookup/order/{number}").get_json()["ok"])

    def test_the_at_menu_offers_people_and_finds_numbers_in_catalogue_and_lot(self):
        who = make_user(uniq("jordana"))
        got = self.m.get(f"/notebook/search/all?q={who[:6]}").get_json()["items"]
        self.assertEqual((got[0]["type"], got[0]["id"]), ("person", who))
        cat = uniq("29").replace("_", "")
        digits = "".join(ch for ch in cat if ch.isdigit())
        item = self.make_item(self.m, self.abs, uniq("anti-p21 "), catalog_number=f"{digits}S")
        number = one("select number from inventory_items where id=?", item)
        found = self.m.get(f"/notebook/search/{self.abs}?q={digits}").get_json()["items"]
        self.assertIn(number, [i["id"] for i in found])

    def test_the_popover_describes_it_and_the_link_opens_it(self):
        got = self.m.get(f"/notebook/lookup/{self.abs}/{self.number}").get_json()
        self.assertTrue(got["ok"])
        self.assertIn(["Lot", "L-4471"], got["fields"])
        self.assertEqual(got["name"], one("select name from inventory_items where id=?", self.item))  # the chip's name
        r = self.m.get(f"/notebook/open/{self.abs}/{self.number}")
        self.assertIn(f"/inventory/{self.abs}?open={self.item}", r.headers["Location"])
        self.assertEqual(self.m.get(f"/notebook/lookup/{self.abs}/99999").status_code, 404)

    def test_the_record_lists_the_pages_that_link_it_and_only_ones_you_may_open(self):
        mine = self.new_page(self.m, f"Blot 1:1000 with @{self.abs} {self.number} overnight")
        self.new_page(self.m, f"@{self.abs} {self.number}0 is another one")
        got = self.m.get(f"/notebook/backlinks/{self.abs}/{self.number}").get_json()
        self.assertEqual([i["page_id"] for i in got["items"]], [mine])
        stranger = client_for(make_user())
        self.assertEqual(stranger.get(f"/notebook/backlinks/{self.abs}/{self.number}").get_json()["items"], [])

    def test_someone_else_s_personal_database_is_not_linkable(self):
        r = self.m.post("/inventory/new", data={"preset": "samples", "label": uniq("Mine "), "audience": "me"})
        key = r.headers["Location"].split("?")[0].rsplit("/", 1)[1]
        self.make_item(self.m, key, "S-1")
        other = client_for(make_user())
        self.assertEqual(other.get(f"/notebook/lookup/{key}/1").status_code, 404)
        self.assertEqual(other.get(f"/notebook/backlinks/{key}/1").status_code, 400)
        self.assertEqual(self.m.get(f"/notebook/lookup/{key}/1").status_code, 200)
