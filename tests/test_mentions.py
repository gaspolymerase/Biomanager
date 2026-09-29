"""Notices that reach the right person (app/notify.py): a new order
request tells the admins, and @someone in any record's notes tells them."""
from __future__ import annotations

from tests.base import AppTestCase, count, execute, make_user, uniq
from tests.test_inventory import InventoryCase


def notices(username: str, like: str = "%") -> list[tuple]:
    from tests.base import rows
    return rows("select title, link, category from notifications where recipient_username=? and title like ? "
                "order by id", username, like)


class OrderRequests(InventoryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.orders = cls.new_module(cls.a, "orders")

    def test_a_new_request_tells_the_admins_and_not_the_requester(self):
        name = uniq("SYBR 2X ")
        self.make_item(self.m, self.orders, name)
        got = notices(self.admin, f"%asked for {name}%")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][2], "orders")
        self.assertIn(f"/inventory/{self.orders}", got[0][1])
        self.assertEqual(notices(self.member, f"%{name}%"), [])

    def test_an_admin_who_turned_order_notices_off_is_not_told(self):
        quiet = make_user(uniq("admin"), role="admin")
        execute("update users set notify_orders=? where username=?", False, quiet)
        name = uniq("ECL ")
        self.make_item(self.m, self.orders, name)
        self.assertEqual(notices(quiet, f"%{name}%"), [])


class MentionsInNotes(InventoryCase):
    def test_at_someone_in_a_plasmid_s_notes_tells_them_once_with_a_link(self):
        pid = self.make_plasmid(self.m, notes=f"For @{self.admin}: verified clone 3")
        got = notices(self.admin, "%mentioned you%")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][1], f"/plasmids/{pid}")
        # Saving the notes again with the same mention is not a new mention.
        self.m.post(f"/plasmids/{pid}/update", data={"notes": f"For @{self.admin}: verified clone 3, glycerol"},
                    headers={"X-Autosave": "1"})
        self.assertEqual(len(notices(self.admin, "%mentioned you%")), 1)

    def test_a_name_that_is_no_one_tells_no_one(self):
        before = count("notifications")
        self.make_plasmid(self.m, notes="for @nobody_here_at_all")
        self.assertEqual(count("notifications"), before)

    def test_an_order_note_naming_the_lab_manager_reaches_them(self):
        orders = self.new_module(self.a, "orders")
        manager = make_user(uniq("manager"))
        self.make_item(self.m, orders, uniq("DpnI "), notes=f"@{manager} same as last time please")
        self.assertEqual(len(notices(manager, "%mentioned you%")), 1)
