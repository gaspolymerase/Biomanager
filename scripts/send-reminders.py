#!/usr/bin/env python3
"""Email each lab member what needs doing.

Run once a day from cron or launchd:

    0 8 * * *  cd /path/to/Biomanager && .venv/bin/python scripts/send-reminders.py

What goes in a person's digest:

  * overdue and imminent schedule items from the configurable organism
    modules (flip a vial, chunk a plate, re-freeze a strain)
  * litters reaching weaning age
  * breeder mice past the age the lab retires them
  * their own open tasks that are due

Nothing is sent to someone with an empty digest, and nothing at all is sent
to an account without an email address. With SMTP unconfigured the messages
are logged instead, so this is safe to run before any mail server exists —
try it with --dry-run first.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    CageRecord, LitterRecord, MouseRecord, OrgDue, OrganismModule, TaskItem, UserAccount,
)
from app import mailer  # noqa: E402
from app import organism_service as svc  # noqa: E402

WEAN_AGE_DAYS = 21
BREEDER_RETIRE_WEEKS = 30


def _urgency(days: int) -> str:
    if days < 0:
        return "overdue"
    if days == 0:
        return "today"
    return "soon"


def _when(days: int) -> str:
    if days < 0:
        return f"{-days} day{'s' if days != -1 else ''} overdue"
    if days == 0:
        return "due today"
    return f"in {days} day{'s' if days != 1 else ''}"


def collect(session, horizon: int) -> dict[str, list[dict]]:
    """Build every user's sections, keyed by username."""
    today = date.today()
    cutoff = today + timedelta(days=horizon)
    per_user: dict[str, list[dict]] = {}

    def add(owner: str, title: str, item: dict) -> None:
        owner = (owner or "").strip()
        if not owner:
            return
        sections = per_user.setdefault(owner, [])
        section = next((s for s in sections if s["title"] == title), None)
        if section is None:
            section = {"title": title, "items": []}
            sections.append(section)
        section["items"].append(item)

    # --- Configurable organism modules -----------------------------------
    for module in svc.list_modules(session):
        mv = svc.view(module)
        if not mv.has("schedule"):
            continue
        svc.recompute_due(session, module)
        session.commit()
        rules = {r["key"]: r for r in mv.schedule_rules}
        rows = session.scalars(
            select(OrgDue).where(
                OrgDue.module_id_fk == module.id,
                OrgDue.done_on.is_(None),
                OrgDue.due_on <= cutoff,
            ).order_by(OrgDue.due_on)
        ).all()
        for row in rows:
            model = svc.RULE_SUBJECTS.get(row.subject_kind)
            subject = session.get(model, row.subject_id) if model else None
            if subject is None:
                continue
            label = getattr(subject, "code", None) or f"#{row.subject_id}"
            days = (row.due_on - today).days
            rule = rules.get(row.rule_key, {})
            add(row.assigned_to or getattr(subject, "owner", ""), module.label, {
                "label": f"{rule.get('label', row.rule_key)} · {label}",
                "detail": _when(days),
                "urgency": _urgency(days),
                "url": f"/organisms/{module.key}?view=schedule",
            })

    # --- Mouse litters reaching weaning ----------------------------------
    for litter in session.scalars(
        select(LitterRecord).where(LitterRecord.date_of_birth.is_not(None))
    ).all():
        wean_on = litter.date_of_birth + timedelta(days=WEAN_AGE_DAYS)
        days = (wean_on - today).days
        if days > horizon or days < -30:
            continue
        owners = {(m.owner or "").strip() for m in litter.mice if (m.owner or "").strip()}
        for owner in owners or {""}:
            add(owner, "Mouse colony", {
                "label": f"Wean litter {litter.litter_id}",
                "detail": f"{_when(days)} (born {litter.date_of_birth})",
                "urgency": _urgency(days),
                "url": "/colony?view=litters",
            })

    # --- Breeders past retirement age ------------------------------------
    for mouse in session.scalars(
        select(MouseRecord).where(MouseRecord.date_of_death.is_(None))
    ).all():
        litter = mouse.litter
        if litter is None or litter.date_of_birth is None:
            continue
        weeks = (today - litter.date_of_birth).days // 7
        if weeks < BREEDER_RETIRE_WEEKS:
            continue
        add(mouse.owner, "Mouse colony", {
            "label": f"Mouse #{mouse.mouse_id} is {weeks}w old",
            "detail": f"past the {BREEDER_RETIRE_WEEKS}-week mark",
            "urgency": "soon",
            "url": "/colony?view=mice",
        })

    # --- Personal tasks ---------------------------------------------------
    for task in session.scalars(
        select(TaskItem).where(TaskItem.due_date.is_not(None),
                               TaskItem.status != "done")
    ).all():
        days = (task.due_date - today).days
        if days > horizon:
            continue
        add(getattr(task, "owner", "") or getattr(task, "assigned_to", ""), "Your tasks", {
            "label": task.title,
            "detail": _when(days),
            "urgency": _urgency(days),
            "url": "/calendar",
        })

    return per_user


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--horizon", type=int, default=7,
                        help="how many days ahead to include (default 7)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the digests instead of sending them")
    parser.add_argument("--only", help="limit to one username")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    base_url = mailer.config()["base_url"]

    if not mailer.is_configured() and not args.dry_run:
        print("SMTP is not configured — digests will be logged, not sent.\n"
              "Set BIOMANAGER_SMTP_HOST and friends, or pass --dry-run.\n")

    with SessionLocal() as session:
        per_user = collect(session, args.horizon)
        users = {
            u.username: u for u in session.scalars(
                select(UserAccount).where(UserAccount.disabled.is_(False))
            ).all()
        }

        sent = skipped = 0
        for username, sections in sorted(per_user.items()):
            if args.only and username != args.only:
                continue
            user = users.get(username)
            if user is None:
                continue
            count = sum(len(s["items"]) for s in sections)
            if not count:
                continue

            text, html = mailer.render_digest(
                user.display_name or user.username, sections, base_url)
            overdue = sum(1 for s in sections for i in s["items"] if i["urgency"] == "overdue")
            subject = (f"BioManager: {overdue} overdue" if overdue
                       else f"BioManager: {count} item{'s' if count != 1 else ''} coming up")

            if args.dry_run:
                print("=" * 68)
                print(f"To: {user.email or '(no email address)'}   Subject: {subject}")
                print("=" * 68)
                print(text)
                print()
                sent += 1
                continue

            if not (user.email or "").strip():
                logging.info("skipping %s — no email address on the account", username)
                skipped += 1
                continue
            if mailer.send(user.email, subject, text, html):
                sent += 1
            else:
                skipped += 1

        verb = "would send" if args.dry_run else "sent"
        print(f"{verb} {sent} digest(s); {skipped} skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
