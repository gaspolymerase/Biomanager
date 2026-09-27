"""Import from Excel (app/sheet_import.py): reading sheets, matching their
columns to a database's, tidying values, and importing through each
database's own save code."""
from __future__ import annotations

import io
import json
import re
from datetime import datetime

from app import sheet_import as si
from tests.base import AppTestCase, count, flash_text, last_batch, one, row, uniq


def xlsx(rows: list[list], sheet: str = "Sheet1", extra: dict | None = None) -> bytes:
    from openpyxl import Workbook
    book = Workbook()
    ws = book.active
    ws.title = sheet
    for r in rows:
        ws.append(r)
    for name, more in (extra or {}).items():
        other = book.create_sheet(name)
        for r in more:
            other.append(r)
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


class Matching(AppTestCase):
    def fields(self, target_key="plasmids"):
        from app.app import app
        from app.db import SessionLocal
        with app.test_request_context(), SessionLocal() as s:
            return si.target_for(s, target_key).fields

    def test_names_are_compared_loosely(self):
        self.assertEqual(si.norm("Cat. No."), "cat number")
        self.assertEqual(si.norm("Positions"), "position")
        self.assertEqual(si.norm("Plasmid #"), "plasmid number")

    def test_synonyms_and_values_decide(self):
        fields = self.fields()
        headers = ["Plasmid Name", "Vector", "Antibiotic", "Location", "Freezer", "Who made it", "Box"]
        columns = [["pA"], ["pUC19"], ["Amp"], ["A1", "B2", "C10"], ["-80 top"], ["me"], ["Box 1"]]
        got = {headers[i]: key for i, (key, _s, _w) in si.auto_match(headers, columns, fields).items()}
        self.assertEqual(got["Plasmid Name"], "name")
        self.assertEqual(got["Vector"], "backbone")
        self.assertEqual(got["Antibiotic"], "resistance")
        self.assertEqual(got["Location"], "position")          # it holds A1, B2…
        self.assertEqual(got["Freezer"], "location")
        self.assertEqual(got["Box"], "box")

    def test_a_location_of_words_is_a_location(self):
        fields = self.fields()
        got = si.auto_match(["Location"], [["Freezer 2, shelf 3", "Cold room"]], fields)
        self.assertEqual(got[0][0], "location")

    def test_near_spellings_match(self):
        got = si.auto_match(["Resistence"], [["Kan"]], self.fields())
        self.assertEqual(got[0][0], "resistance")

    def test_a_name_with_a_unit_or_a_generic_word_is_that_column(self):
        fields = [si.Field("attr_hazard", "Hazard", custom=True), si.Field("attr_weight", "Weight", kind="number"),
                  si.Field("cage_id", "Cage", ("cage",))]
        fields.append(si.Field("mouse_id", "Mouse ID", ("mouse",)))
        got = si.auto_match(["Hazard class", "Weight (g)", "Cage colour", "Mouse age"],
                            [["toxic"], ["4.5"], ["blue"], ["8"]], fields)
        self.assertEqual({i: k for i, (k, _s, _w) in got.items()}, {0: "attr_hazard", 1: "attr_weight"})

    def test_each_database_column_takes_one_sheet_column(self):
        got = si.auto_match(["Name", "Plasmid name"], [["a"], ["b"]], self.fields())
        self.assertEqual([k for k, _s, _w in got.values()].count("name"), 1)


class Tidying(AppTestCase):
    def test_dates_day_or_month_first_per_column(self):
        out, notes = si.tidy_dates(["14/03/2026", "03/04/2026", ""])
        self.assertEqual(out[:2], ["2026-03-14", "2026-04-03"])
        out, notes = si.tidy_dates(["03/14/2026", "04/03/2026"])
        self.assertEqual(out, ["2026-03-14", "2026-04-03"])
        out, notes = si.tidy_dates(["03/04/2026"])
        self.assertEqual(out, ["2026-03-04"])
        self.assertIn("month first", " ".join(notes))

    def test_excel_date_numbers_and_iso(self):
        out, _ = si.tidy_dates(["46095", "2026-03-14 00:00", "not a date"])
        self.assertEqual(out[:2], ["2026-03-14", "2026-03-14"])
        self.assertEqual(out[2], "")

    def test_a_lab_s_own_mouse_statuses_win(self):
        from app.app import app
        from app.db import SessionLocal
        from tests.base import execute
        execute("insert into dropdown_options (field_name, option_value, created_at) values ('status', 'Stock', '2026-01-01')")
        with app.test_request_context(), SessionLocal() as s:
            choices = si._mouse_statuses(s)
        self.assertEqual(si.tidy_choice("stock", choices), ("Stock", True))
        self.assertEqual(si.tidy_choice("Sacrificed", choices), ("sac", True))
        execute("delete from dropdown_options where field_name='status' and option_value='Stock'")

    def test_sexes_and_choices(self):
        self.assertEqual(si.tidy_choice("Male", si.SEXES), ("M", True))
        self.assertEqual(si.tidy_choice("♀", si.SEXES)[0], "F")
        self.assertEqual(si.tidy_choice("Sacrificed", si.MOUSE_STATUSES), ("sac", True))
        self.assertEqual(si.tidy_choice("weird", si.MOUSE_STATUSES), ("weird", False))


class Reading(AppTestCase):
    def test_xlsx_with_a_title_row_and_real_dates(self):
        data = xlsx([["Our plasmids"], ["Name", "Date", "N"], ["pA", datetime(2026, 3, 14), 3.0]])
        sheets = si.read_workbook("x.xlsx", data)
        headers, rows, first = si.split_header(sheets["Sheet1"])
        self.assertEqual(headers, ["Name", "Date", "N"])
        self.assertEqual((rows, first), ([["pA", "2026-03-14", "3"]], 3))

    def test_csv_semicolons_and_old_encodings(self):
        data = "Name;Notes\npA;café\n".encode("cp1252")
        headers, rows, _first = si.split_header(si.read_workbook("x.csv", data)["Sheet 1"])
        self.assertEqual((headers, rows), (["Name", "Notes"], [["pA", "café"]]))

    def test_old_xls_says_what_to_do(self):
        with self.assertRaises(si.ImportProblem) as caught:
            si.read_workbook("old.xls", b"\xd0\xcf\x11\xe0")
        self.assertIn("Save As", str(caught.exception))


class Importing(AppTestCase):
    def upload(self, client, target, filename, data):
        r = client.post(f"/import-sheet/{target}/upload", data={"file": (io.BytesIO(data), filename)},
                        content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302, r.get_data(as_text=True)[:500])
        token = r.headers["Location"].rsplit("/", 1)[1]
        return token, self.get_ok(client, f"/import-sheet/file/{token}")

    @staticmethod
    def chosen(html) -> dict[str, str]:
        """{select name: the option selected} on the match page."""
        out = {}
        for name, body in re.findall(r'<select name="((?:map|kind)-\d+)"[^>]*>(.*?)</select>', html, re.S):
            picked = re.search(r'<option value="([^"]*)" selected', body)
            out[name] = picked.group(1) if picked else ""
        return out

    def test_every_database_has_the_button(self):
        self.assertIn("/import-sheet/mice", self.get_ok(self.a, "/colony?view=mice"))
        self.assertIn("/import-sheet/plasmids", self.get_ok(self.a, "/plasmids"))
        self.assertIn("/import-sheet/fish", self.get_ok(self.a, "/zebrafish?view=fish"))
        self.assertIn("/import-sheet/inventory:reagents", self.get_ok(self.a, "/inventory/reagents"))
        key = self.make_stock_module(self.a)
        self.assertIn(f"/import-sheet/stocks:{key}", self.get_ok(self.a, f"/stocks/{key}"))
        key = self.make_organism_module(self.a)
        self.assertIn(f"/import-sheet/organisms:{key}", self.get_ok(self.a, f"/organisms/{key}"))

    def test_mice_from_excel(self):
        tag = uniq("TG")
        data = xlsx([["Ear tag", "Sex", "DOB", "Strain", "Cage #", "Room", "Status", "Cage colour"],
                     ["", "Male", "14/03/2026", tag, "", "B12", "Breeding", "blue"],
                     ["", "f", "03/04/2026", tag, "", "B12", "sacrificed", "red"]])
        token, html = self.upload(self.a, "mice", "colony.xlsx", data)
        chosen = self.chosen(html)
        self.assertEqual(chosen["map-1"], "gender")
        self.assertEqual(chosen["map-2"], "date_of_birth")
        self.assertEqual(chosen["map-3"], "genotype")
        self.assertEqual(chosen["map-5"], "cage_location")       # B12 is a room here, not a box position
        self.assertEqual(chosen["map-6"], "status")
        self.assertEqual(chosen["map-7"], "_notes")               # the colony's columns are fixed
        self.assertIn("isn't in your sheet", html)               # no owner column: every row gets one
        form = {**chosen, "sheet": "Sheet1", "fill-owner": "me"}
        before = count("mice")
        preview = self.a.post(f"/import-sheet/file/{token}/preview", data=form).get_data(as_text=True)
        self.assertIn("2 of 2 rows", preview)
        self.assertEqual(count("mice"), before)                  # a preview writes nothing
        r = self.post(self.a, f"/import-sheet/file/{token}/run", data=form)
        self.assertIn("Imported 2 mice", flash_text(r))
        self.assertEqual(count("mice"), before + 2)
        got = row("select gender, status, owner, note from mice order by id desc limit 1")
        self.assertEqual(got[:3], ("F", "sac", self.admin))
        self.assertIn("Cage colour: red", got[3])
        self.assertIn("Room: B12", got[3])                       # no cage to hold the room
        self.assertEqual(last_batch()[2], "create")

    def test_plasmids_with_boxes_positions_and_a_location_column(self):
        box = uniq("Box ")
        name = uniq("pImp")
        data = (f"Plasmid #,Construct,Vector,Antibiotic,Box,Location,Freezer,Made by\n"
                f",{name}-1,pUC19,Amp,{box},A1,-80 top,{self.member}\n"
                f",{name}-2,pUC19,Kan,{box},A1,-80 top,nobody-here\n").encode()
        token, html = self.upload(self.a, "plasmids", "plasmids.csv", data)
        chosen = self.chosen(html)
        self.assertEqual(chosen["map-5"], "position")
        self.assertEqual(chosen["map-6"], "location")
        self.assertEqual(chosen["map-7"], "owner")
        form = {**chosen, "sheet": "Sheet 1"}
        preview = self.a.post(f"/import-sheet/file/{token}/preview", data=form).get_data(as_text=True)
        self.assertIn("already holds plasmid", preview)          # both want A1
        self.assertIn("isn&#39;t anyone in the lab", preview)
        self.post(self.a, f"/import-sheet/file/{token}/run", data=form)
        first = row("select owner, backbone, resistance, location, box_row, box_col from plasmids where name=?",
                    f"{name}-1")
        self.assertEqual(first, (self.member, "pUC19", "Amp", "-80 top", 0, 0))
        second = row("select owner, box_row, notes from plasmids where name=?", f"{name}-2")
        self.assertEqual(second[:2], (self.admin, None))         # unknown owner → you; the cell was taken
        self.assertIn("nobody-here", second[2])

    def fresh_inventory(self, preset="reagents") -> str:
        r = self.a.post("/inventory/new", data={"preset": preset, "label": uniq("Chemicals "), "audience": "lab"})
        return r.headers["Location"].split("?")[0].rstrip("/").rsplit("/", 1)[1]

    def test_an_inventory_gains_the_columns_it_lacks(self):
        key = self.fresh_inventory()
        name = uniq("Reagent ")
        data = xlsx([["Product", "Supplier", "Cat. No.", "Expiry date", "Shelf life", "Batch"],
                     [name, "Sigma", "S-1", "2027-01-31", "flammable", "L7"]])
        token, html = self.upload(self.a, f"inventory:{key}", "reagents.xlsx", data)
        chosen = self.chosen(html)
        self.assertEqual([chosen[f"map-{i}"] for i in range(6)],
                         ["name", "vendor", "catalog_number", "expires_on", "_new", "lot"])
        self.post(self.a, f"/import-sheet/file/{token}/run", data={**chosen, "sheet": "Sheet1"})
        item = row("select vendor, catalog_number, expires_on, lot, attrs from inventory_items where name=?", name)
        self.assertEqual(item[:2], ("Sigma", "S-1"))
        self.assertEqual(str(item[2])[:10], "2027-01-31")
        self.assertEqual(json.loads(item[4])["shelf_life"], "flammable")
        settings = json.loads(one("select settings from inventory_modules where key=?", key))
        self.assertIn("Shelf life", [f["label"] for f in settings["fields"]])

    def test_a_member_cannot_add_columns_to_a_lab_inventory(self):
        name = uniq("Reagent ")
        token, html = self.upload(self.m, "inventory:reagents", "r.csv", f"Name,Odd column\n{name},x\n".encode())
        chosen = self.chosen(html)
        self.assertEqual(chosen["map-1"], "_notes")
        self.post(self.m, f"/import-sheet/file/{token}/run", data={**chosen, "sheet": "Sheet 1"})
        self.assertIn("Odd column: x", one("select notes from inventory_items where name=?", name))

    def test_fly_vials_into_racks(self):
        key = self.make_stock_module(self.a)
        rack = self.make_stock_rack(self.a, key)
        rack_name = one("select name from stock_racks where id=?", rack)
        gt = uniq("w1118; ")
        data = xlsx([["Stock", "Bloomington #", "Rack", "Slot", "Type"], [gt, "5905", rack_name, "A1", "Stock"]])
        token, html = self.upload(self.a, f"stocks:{key}", "flies.xlsx", data)
        chosen = self.chosen(html)
        self.assertEqual([chosen[f"map-{i}"] for i in range(5)],
                         ["genotype", "stock_number", "rack", "position", "purpose"])
        self.post(self.a, f"/import-sheet/file/{token}/run", data={**chosen, "sheet": "Sheet1"})
        self.assertEqual(row("select rack_id_fk, rack_row, rack_col from stock_units where genotype=?", gt),
                         (rack, 1, 1))

    def test_fish_make_their_tanks_and_lines(self):
        tank, line = uniq("T"), uniq("Line ")
        data = f"Tank,Line,Number of fish,Gender,DOF\n{tank},{line},12,mix,2026-01-05\n".encode()
        token, html = self.upload(self.a, "fish", "fish.csv", data)
        chosen = self.chosen(html)
        self.post(self.a, f"/import-sheet/file/{token}/run", data={**chosen, "sheet": "Sheet 1"})
        got = row("select f.count, f.sex, l.name from fish f join tanks t on t.id=f.tank_id_fk "
                  "left join fish_lines l on l.id=f.line_id_fk where t.tank_id=?", tank)
        self.assertEqual(got, (12, "mixed", line))

    def test_an_organism_database_gains_columns_and_housing(self):
        key = self.make_organism_module(self.a)
        data = xlsx([["Newt ID", "Sex", "Tank", "Weight (g)"], ["N-1", "Male", "T-9", "4.5"]])
        token, html = self.upload(self.a, f"organisms:{key}", "newts.xlsx", data)
        chosen = self.chosen(html)
        self.assertEqual(chosen["map-2"], "housing")
        self.assertEqual((chosen["map-3"], chosen["kind-3"]), ("_new", "number"))
        self.post(self.a, f"/import-sheet/file/{token}/run", data={**chosen, "sheet": "Sheet1"})
        mid = self.organism_module_id(key)
        got = row("select o.sex, h.code, o.attrs from organisms o join organism_housing h on h.id=o.housing_id_fk "
                  "where o.module_id_fk=? and o.code='N-1'", mid)
        self.assertEqual(got[:2], ("male", "T-9"))
        self.assertEqual(float(json.loads(got[2])["weight_g"]), 4.5)

    def test_problems_name_the_sheet_s_own_row(self):
        data = xlsx([["Plasmids of the lab"], ["Name", "Vector"], ["pOk", "pUC19"], [], ["", "no name"]])
        token, html = self.upload(self.a, "plasmids", "p.xlsx", data)
        self.assertIn("2 rows", html)
        preview = self.a.post(f"/import-sheet/file/{token}/preview",
                              data={**self.chosen(html), "sheet": "Sheet1"}).get_data(as_text=True)
        self.assertIn("Row 5: It has no name.", preview)

    def test_missing_must_haves_stop_the_import(self):
        token, html = self.upload(self.a, "plasmids", "p.csv", b"Vector,Notes\npUC19,x\n")
        r = self.post(self.a, f"/import-sheet/file/{token}/preview",
                      data={"map-0": "backbone", "map-1": "_notes", "sheet": "Sheet 1"})
        self.assertIn("Name", flash_text(r))

    def test_an_import_can_be_undone(self):
        name = uniq("pUndo")
        token, html = self.upload(self.a, "plasmids", "p.csv", f"Name\n{name}\n".encode())
        self.post(self.a, f"/import-sheet/file/{token}/run", data={**self.chosen(html), "sheet": "Sheet 1"})
        self.assertEqual(count("plasmids", "name=?", name), 1)
        self.assertIn("upload is finished", flash_text(self.a.get(f"/import-sheet/file/{token}", follow_redirects=True)))
        batch_id = last_batch()[0]
        self.post(self.a, f"/batches/{batch_id}/undo")
        self.assertEqual(count("plasmids", "name=?", name), 0)

    def test_an_upload_is_only_its_owners(self):
        token, _html = self.upload(self.a, "plasmids", "p.csv", b"Name\npX\n")
        self.assertEqual(self.m.get(f"/import-sheet/file/{token}").status_code, 404)
