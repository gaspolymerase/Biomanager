"""A renamed database moves to its new name's address and keeps the old one
(app/database_keys.py): old links, printed labels and @mentions still find it."""
from __future__ import annotations

import json

from tests.base import client_for, count, execute, location, make_user, one, uniq
from tests.test_inventory import InventoryCase


class RenameInventory(InventoryCase):
    def rename(self, key, label):
        self.post(self.a, f"/inventory/{key}/configure", data=self.configure_form(key, label=label))
        return one("select key from inventory_modules where label=?", label)

    def test_a_new_name_gives_a_new_address_and_the_old_one_leads_there(self):
        old = self.new_module(self.a, "antibodies", label=uniq("Abs "))
        label = uniq("Primary antibodies ")
        new = self.rename(old, label)
        self.assertNotEqual(new, old)
        self.assertTrue(new.startswith("primary_antibodies"))
        r = self.a.get(f"/inventory/{old}?scope=mine")
        self.assertEqual((r.status_code, location(r)), (302, f"/inventory/{new}?scope=mine"))
        self.assertEqual(location(self.a.get(f"/inventory/{old}/configure")), f"/inventory/{new}/configure")
        self.assertIn(label, self.get_ok(self.a, f"/inventory/{new}"))
        # A form from a page opened before the rename still saves.
        self.a.post(f"/inventory/{old}/items/save", data={"id": "", "name": uniq("anti-GFP ")})
        self.assertEqual(one("select count(*) from inventory_items i join inventory_modules m on m.id=i.module_id_fk "
                             "where m.key=?", new), 1)

    def test_an_old_mention_in_a_page_still_finds_the_record(self):
        old = self.new_module(self.a, "antibodies", label=uniq("Abs "))
        item = self.make_item(self.a, old, uniq("anti-p53 "))
        number = one("select number from inventory_items where id=?", item)
        page = self.a.post("/notebook/api/pages/new", data=json.dumps({"title": uniq("Blot ")}),
                           content_type="application/json").get_json()["page_id"]
        self.a.post(f"/notebook/pages/{page}/update", data={"body": f"Probed with @{old} {number} overnight."})
        new = self.rename(old, uniq("Primary antibodies "))
        self.assertTrue(self.a.get(f"/notebook/lookup/{old}/{number}").get_json()["ok"])
        self.assertIn(f"/inventory/{new}", location(self.a.get(f"/notebook/open/{old}/{number}")))
        # The record's "Used in notebook pages", asked by its new key, finds the old mention.
        found = self.a.get(f"/notebook/backlinks/{new}/{number}").get_json()["items"]
        self.assertEqual([i["page_id"] for i in found], [page])
        html = self.get_ok(self.a, f"/notebook?page={page}")
        self.assertIn(f'"key": "{old}"', html)                   # the chip still reads as one

    def test_an_order_put_into_stock_follows_the_rename(self):
        old = self.new_module(self.a, "reagents", label=uniq("Reagents "))
        orders = one("select key from inventory_modules where kind='orders' order by id limit 1")
        order = self.make_item(self.a, orders, uniq("PBS "))
        attrs = json.loads(one("select attrs from inventory_items where id=?", order) or "{}")
        attrs["stocked_as"] = f"{old}:3"
        execute("update inventory_items set attrs=? where id=?", json.dumps(attrs), order)
        new = self.rename(old, uniq("Chemicals "))
        self.assertEqual(json.loads(one("select attrs from inventory_items where id=?", order))["stocked_as"], f"{new}:3")

    def test_renaming_back_takes_the_first_address_again(self):
        label = uniq("Enzymes ")
        first = self.new_module(self.a, "custom", label=label)
        middle = self.rename(first, uniq("Restriction enzymes "))
        back = self.rename(middle, label)
        self.assertEqual(back, first)
        self.assertEqual(location(self.a.get(f"/inventory/{middle}")), f"/inventory/{first}")
        self.assertEqual(count("database_aliases", "kind='inventory' and old_key=?", first), 0)

    def test_another_database_does_not_take_an_old_address(self):
        label = uniq("Buffers ")
        old = self.new_module(self.a, "custom", label=label)
        self.rename(old, uniq("Solutions "))
        other = self.new_module(self.a, "custom", label=label)
        self.assertNotEqual(other, old)
        self.assertEqual(self.a.get(f"/inventory/{old}").status_code, 302)   # still the renamed one's

    def test_a_name_the_app_uses_for_a_page_is_not_an_address(self):
        r = self.a.post("/inventory/new", data={"preset": "custom", "label": "New", "audience": "lab"})
        key = location(r).split("?")[0].rsplit("/", 1)[1]
        self.assertNotIn(key, ("new", ""))
        self.assertEqual(self.a.get(f"/inventory/{key}").status_code, 200)

    def test_someone_else_s_personal_database_stays_hidden_at_its_old_address(self):
        owner = make_user()
        mine = client_for(owner)
        r = mine.post("/inventory/new", data={"preset": "custom", "label": uniq("Private "), "audience": "me"})
        old = location(r).split("?")[0].rsplit("/", 1)[1]
        mine.post(f"/inventory/{old}/configure", data=self.configure_form(old, label=uniq("Still private ")))
        self.assertEqual(self.m.get(f"/inventory/{old}").status_code, 404)


class RenameOthers(InventoryCase):
    def test_a_renamed_organism_database_moves_and_keeps_numbering_its_codes(self):
        from app.db import SessionLocal
        from app import organism_service
        old = self.make_organism_module(self.a, label=uniq("Axolotls "))
        new_label = uniq("Salamanders ")
        self.post(self.a, f"/organisms/{old}/configure", {"_full": "1", "label": new_label, "capabilities": ["housing"]})
        new = one("select key from organism_modules where label=?", new_label)
        self.assertNotEqual(new, old)
        self.assertEqual(location(self.a.get(f"/organisms/{old}?view=housing")), f"/organisms/{new}?view=housing")
        with SessionLocal() as s:
            module = organism_service.get_module(s, new)
            self.assertTrue(organism_service.code_prefix(module, "organism").startswith(old.upper()[:4]))

    def test_a_renamed_stock_database_moves_and_its_experiments_follow(self):
        old = self.make_stock_module(self.a, "fly", label=uniq("Flies "))
        from app.db import SessionLocal
        from app.models import Experiment
        with SessionLocal() as s:
            s.add(Experiment(name=uniq("Cross "), owner_username=self.admin, db=f"stocks:{old}"))
            s.commit()
        label = uniq("Fly room ")
        form = {"label": label, "temp_count": "0"}
        self.post(self.a, f"/stocks/{old}/settings", form)
        new = one("select key from stock_modules where label=?", label)
        self.assertNotEqual(new, old)
        self.assertEqual(location(self.a.get(f"/stocks/{old}")), f"/stocks/{new}")
        self.assertEqual(count("experiments", "db=?", f"stocks:{old}"), 0)
        self.assertEqual(count("experiments", "db=?", f"stocks:{new}"), 1)


class EveryDatabaseHasItsOwnName(InventoryCase):
    """No two databases share a name or an address, whatever their kind:
    "@<name> 5" in a notebook page, the sidebar and search never mean two."""

    def test_a_new_database_may_not_take_another_ones_name(self):
        label = uniq("Ferrets ")
        self.make_stock_module(self.a, "fly", label=label)
        for url, data in (("/inventory/new", {"preset": "custom"}), ("/stocks/new", {"kind": "worm"}),
                          ("/organisms/new", {"preset_key": "custom"})):
            r = self.post(self.a, url, data={**data, "label": label.upper(), "audience": "lab"})
            self.assertFlash(r, "already a database called", "error")
        self.assertEqual(sum(one(f"select count(*) from {t} where lower(label)=lower(?)", label)
                             for t in ("inventory_modules", "stock_modules", "organism_modules")), 1)

    def test_renaming_to_another_databases_name_is_refused_but_keeping_ones_own_is_fine(self):
        taken_label = uniq("Otters ")
        self.new_module(self.a, "custom", label=taken_label)
        key = self.new_module(self.a, "custom", label=uniq("Voles "))
        mine = one("select label from inventory_modules where key=?", key)
        r = self.post(self.a, f"/inventory/{key}/configure", data=self.configure_form(key, label=taken_label))
        self.assertFlash(r, "already a database called", "error")
        self.assertEqual(one("select label from inventory_modules where key=?", key), mine)
        r = self.post(self.a, f"/inventory/{key}/configure", data=self.configure_form(key, blurb="kept"))
        self.assertNoErrors(r)

    def test_a_built_in_database_name_is_taken_too(self):
        r = self.post(self.a, "/inventory/new", data={"preset": "custom", "label": "Plasmids", "audience": "lab"})
        self.assertFlash(r, "already a database called Plasmids", "error")

    def test_an_address_is_never_shared_across_kinds(self):
        inv = self.new_module(self.a, "custom", label=uniq("Shrews "))
        stock_label = one("select label from inventory_modules where key=?", inv) + "."
        key = self.make_stock_module(self.a, "fly", label=stock_label)   # the same address, by its name
        self.assertNotEqual(key, inv)
        self.assertTrue(key.startswith(inv + "_"))

    def test_the_at_words_of_mice_plasmids_and_orders_are_not_an_address(self):
        key = self.new_module(self.a, "custom", label="Order")
        self.assertNotEqual(key, "order")
