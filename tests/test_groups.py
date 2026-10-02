"""Project groups: a layer between a person and the lab. Admins make groups
and choose members (leads may add and remove them); whatever can be shared
with the lab can be shared with one group instead, which its members edit
(databases: see), and the calendar has lab and group to-dos."""
from __future__ import annotations

import unittest

from tests.base import *  # noqa: F401,F403
from tests.base import AppTestCase, client_for, flash_text, make_user, one, uniq

from app.db import SessionLocal
from app.models import LabGroup, LabGroupMember


def make_group(name=None, members=(), leads=()) -> int:
    with SessionLocal() as s:
        group = LabGroup(name=name or uniq("Group"))
        s.add(group)
        s.flush()
        for who in members:
            s.add(LabGroupMember(group_id_fk=group.id, username=who, lead=who in leads))
        s.commit()
        return group.id


class GroupCase(AppTestCase):
    """An admin, a member and a colleague in one group; `other` outside it."""

    def setUp(self):
        super().setUp()
        self.colleague = make_user(uniq("colleague"))
        self.c = client_for(self.colleague)
        self.gid = make_group(members=(self.member, self.colleague))


class GroupPageTests(GroupCase):
    def test_everyone_sees_the_groups_and_who_is_in_them(self):
        html = self.get_ok(self.o, "/groups")
        self.assertIn(f'id="group-{self.gid}"', html)
        self.assertIn(self.colleague, html)
        self.assertNotIn('action="/groups/create"', html)

    def test_an_admin_makes_a_group_with_members(self):
        name = uniq("Sleep")
        r = self.a.post("/groups/create", data={"name": name, "members": [self.member, self.other]})
        self.assertEqual(r.status_code, 302)
        gid = one("select id from lab_groups where name=?", name)
        self.assertEqual(sorted(one_col("select username from lab_group_members where group_id_fk=?", gid)),
                         sorted([self.member, self.other]))

    def test_a_member_may_not_make_a_group_or_add_people(self):
        self.assertEqual(self.m.post("/groups/create", data={"name": uniq("G")}).status_code, 403)
        self.assertEqual(self.m.post(f"/groups/{self.gid}/members", data={"username": self.other}).status_code, 403)

    def test_a_lead_adds_and_takes_out_members_but_not_another_lead(self):
        lead = make_user(uniq("lead"))
        gid = make_group(members=(lead, self.colleague), leads=(lead, self.colleague))
        client = client_for(lead)
        self.assertEqual(client.post(f"/groups/{gid}/members", data={"username": self.other}).status_code, 302)
        self.assertEqual(one("select count(*) from lab_group_members where group_id_fk=? and username=?",
                             gid, self.other), 1)
        client.post(f"/groups/{gid}/members/{self.other}/remove")
        self.assertEqual(one("select count(*) from lab_group_members where group_id_fk=? and username=?",
                             gid, self.other), 0)
        r = client.post(f"/groups/{gid}/members/{self.colleague}/remove", follow_redirects=True)
        self.assertIn("Only an admin can take a lead out", flash_text(r))

    def test_a_name_is_needed_and_used_once(self):
        name = one("select name from lab_groups where id=?", self.gid)
        r = self.a.post("/groups/create", data={"name": name}, follow_redirects=True)
        self.assertIn("already a group called", flash_text(r))


def one_col(sql, *args):
    from tests.base import rows
    return [r[0] for r in rows(sql, *args)]


if __name__ == "__main__":
    unittest.main()
