"""In-app notifications: something happened that someone should know about.

What tells whom (the category decides the Settings switch that silences it):

  transfer    an animal, cage, tank or vial of yours was moved or given away
              by someone else; one was given to you; a mouse was put in your cage
  picked      someone took a mouse of yours from a breeder cage
  genotyping  a genotype was recorded for your animal, or it was marked for
              genotyping, by someone else; once a day, what of yours waits
  orders      an order you placed was ordered, received or cancelled
  lab         a database or function was added or switched on for the lab
  account     sign-ups waiting for approval (admins)

Changes are noticed where the change history notices them, at the flush,
so every route and every bulk edit is covered without a call in each.
Notifications are made at commit: none for a change that is rolled back,
none to the person who made it, and one per person per kind of change,
so moving twenty mice sends one message listing them, not twenty.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import date, datetime

from flask import g, has_request_context, url_for
from sqlalchemy import event, func, inspect as sa_inspect, select
from sqlalchemy.orm import Session

from .models import (CageRecord, FishRecord, InventoryItem, InventoryModule, MouseRecord, NotificationRecord,
                     OrgGenotype, OrgHousing, Organism, OrganismModule, StockModule, StockUnit, TankRecord,
                     UserAccount)

CATEGORIES = {
    "transfer": ("Transfers", "Your animals, cages, tanks or vials moved or given by someone else"),
    "picked": ("Picked from breeders", "Someone took one of your mice from a breeder cage"),
    "genotyping": ("Genotyping", "Genotypes recorded or requested for your animals, and what is waiting"),
    "orders": ("Orders", "Your orders placed, received or cancelled"),
    "lab": ("Lab news", "Databases or functions added for the lab"),
    "notebook": ("Notebook", "Pages shared with you, comments and @mentions, meeting notes and action items"),
    "experiments": ("Experiments", "Once a day: manipulations and readouts due in your experiments"),
}
MAX_LISTED = 5


def _actor() -> str | None:
    if not has_request_context():
        return None
    user = g.get("user")
    return user.username if user is not None else None


def _change(obj, attr: str):
    """(before, after) if `attr` changed in this flush, else None."""
    history = sa_inspect(obj).attrs[attr].history
    if not history.has_changes():
        return None
    before = history.deleted[0] if history.deleted else None
    after = history.added[0] if history.added else None
    if before == after:
        return None
    return before, after


def _note(recipient, category, group, item, one, many, link="", **extra):
    """A thing to tell `recipient`. Notes with the same recipient, category
    and group become one notification: `one` for a single item, `many`
    (with {n} and {items}) for several."""
    return {"recipient": recipient, "category": category, "group": group, "item": item,
            "one": one, "many": many, "link": link, **extra}


# ---------------------------------------------------------------- what each kind of record notices

def _mouse(obj: MouseRecord, actor: str) -> list[dict]:
    notes = []
    label = f"mouse #{obj.mouse_id}"
    link = ("mouse", obj.id)
    owner = _change(obj, "owner")
    if owner:
        before, after = owner
        if after and after != actor:
            notes.append(_note(after, "transfer", ("given", actor), label,
                               f"{actor} gave you {label}", f"{actor} gave you {{n}} mice: {{items}}", link))
        if before and before != actor:
            if after == actor:
                notes.append(_note(before, "picked", ("taken", actor), label,
                                   f"{actor} took {label} from you", f"{actor} took {{n}} of your mice: {{items}}",
                                   link))
            elif not after:
                notes.append(_note(before, "transfer", ("unowned", actor), label,
                                   f"{actor} removed you as the owner of {label}",
                                   f"{actor} removed you as the owner of {{n}} mice: {{items}}", link))
            else:
                notes.append(_note(before, "transfer", ("given-away", actor, after), label,
                                   f"{actor} gave your {label} to {after}",
                                   f"{actor} gave {{n}} of your mice to {after}: {{items}}", link))
    cage = _change(obj, "cage_id_fk")
    current_owner = obj.owner or ""
    if cage and cage[1]:
        if current_owner and current_owner != actor:
            notes.append(_note(current_owner, "transfer", ("moved", actor, cage[1]), label,
                               f"{actor} moved your {label} to cage {{cage}}",
                               f"{actor} moved {{n}} of your mice to cage {{cage}}: {{items}}", link,
                               cage_id=cage[1]))
        notes.append(_note(None, "transfer", ("into-cage", actor, cage[1]), label,
                           f"{actor} moved {label} into your cage {{cage}}",
                           f"{actor} moved {{n}} mice into your cage {{cage}}: {{items}}", link,
                           cage_owner_of=cage[1], skip=(actor, current_owner)))
    if current_owner and current_owner != actor:
        typed = [_change(obj, f) for f in ("genotype", "transgene_1", "transgene_2", "transgene_3", "transgene_4")]
        if any(typed) and (obj.genotype or "").strip():
            notes.append(_note(current_owner, "genotyping", ("genotyped", actor), f"{label} ({obj.genotype.strip()})",
                               f"{actor} recorded the genotype of {label}: {obj.genotype.strip()}",
                               f"{actor} recorded genotypes for {{n}} of your mice: {{items}}", link))
        status = _change(obj, "status")
        if status and status[1] == "geno":
            notes.append(_note(current_owner, "genotyping", ("to-genotype", actor), label,
                               f"{actor} marked your {label} for genotyping",
                               f"{actor} marked {{n}} of your mice for genotyping: {{items}}", link))
    return notes


def _cage(obj: CageRecord, actor: str) -> list[dict]:
    owner = _change(obj, "owner")
    if owner and owner[1] and owner[1] != actor:
        label = f"cage {obj.cage_id}"
        return [_note(owner[1], "transfer", ("cage-given", actor), label, f"{actor} gave you {label}",
                      f"{actor} gave you {{n}} cages: {{items}}", ("cage", obj.id))]
    return []


def _tank(obj: TankRecord, actor: str) -> list[dict]:
    notes = []
    label = f"tank {obj.tank_id}"
    owner = _change(obj, "owner")
    if owner and owner[1] and owner[1] != actor:
        notes.append(_note(owner[1], "transfer", ("tank-given", actor), label, f"{actor} gave you {label}",
                           f"{actor} gave you {{n}} tanks: {{items}}", ("tank", obj.id)))
    flag = _change(obj, "needs_genotyping")
    if flag and obj.owner and obj.owner != actor:
        if flag[1]:
            notes.append(_note(obj.owner, "genotyping", ("tank-geno", actor), label,
                               f"{actor} flagged your {label} for genotyping",
                               f"{actor} flagged {{n}} of your tanks for genotyping: {{items}}", ("tank", obj.id)))
        else:
            notes.append(_note(obj.owner, "genotyping", ("tank-geno-done", actor), label,
                               f"{actor} finished genotyping your {label}",
                               f"{actor} finished genotyping {{n}} of your tanks: {{items}}", ("tank", obj.id)))
    return notes


def _fish(obj: FishRecord, actor: str) -> list[dict]:
    tank = _change(obj, "tank_id_fk")
    if not tank:
        return []
    label = f"fish {obj.individual_id or ('group of ' + str(obj.count or 1))}"
    notes = []
    if tank[1]:
        notes.append(_note(None, "transfer", ("fish-in", actor, tank[1]), label,
                           f"{actor} moved {label} into your tank {{tank}}",
                           f"{actor} moved {{n}} fish into your tank {{tank}}: {{items}}", ("tank", tank[1]),
                           tank_owner_of=tank[1], skip=(actor,)))
    if tank[0]:
        notes.append(_note(None, "transfer", ("fish-out", actor, tank[0]), label,
                           f"{actor} moved {label} out of your tank {{tank}}",
                           f"{actor} moved {{n}} fish out of your tank {{tank}}: {{items}}", ("tank", tank[0]),
                           tank_owner_of=tank[0], skip=(actor,)))
    return notes


def _organism(obj: Organism, actor: str) -> list[dict]:
    notes = []
    label = obj.code or f"#{obj.id}"
    link = ("organism", obj.module_id_fk)
    owner = _change(obj, "owner")
    if owner:
        before, after = owner
        if after and after != actor:
            notes.append(_note(after, "transfer", ("org-given", actor, obj.module_id_fk), label,
                               f"{actor} gave you {label}", f"{actor} gave you {{n}} animals: {{items}}", link))
        if before and before != actor and before != after:
            notes.append(_note(before, "transfer", ("org-given-away", actor, obj.module_id_fk), label,
                               f"{actor} gave your {label} to {after}" if after
                               else f"{actor} removed you as the owner of {label}",
                               f"{actor} gave {{n}} of your animals away: {{items}}", link))
    housing = _change(obj, "housing_id_fk")
    if housing and obj.owner and obj.owner != actor:
        notes.append(_note(obj.owner, "transfer", ("org-moved", actor, obj.module_id_fk), label,
                           f"{actor} moved your {label}", f"{actor} moved {{n}} of your animals: {{items}}", link))
    if obj.owner and obj.owner != actor and _change(obj, "genotype") and (obj.genotype or "").strip():
        notes.append(_note(obj.owner, "genotyping", ("org-genotyped", actor, obj.module_id_fk),
                           f"{label} ({obj.genotype.strip()})",
                           f"{actor} recorded the genotype of your {label}: {obj.genotype.strip()}",
                           f"{actor} recorded genotypes for {{n}} of your animals: {{items}}", link))
    return notes


def _housing(obj: OrgHousing, actor: str) -> list[dict]:
    owner = _change(obj, "owner")
    if owner and owner[1] and owner[1] != actor:
        label = obj.code or f"#{obj.id}"
        return [_note(owner[1], "transfer", ("housing-given", actor, obj.module_id_fk), label,
                      f"{actor} gave you {label}", f"{actor} gave you {{n}}: {{items}}",
                      ("organism", obj.module_id_fk))]
    return []


def _unit(obj: StockUnit, actor: str) -> list[dict]:
    owner = _change(obj, "owner")
    if owner and owner[1] and owner[1] != actor:
        label = f"#{obj.number}"
        return [_note(owner[1], "transfer", ("unit-given", actor, obj.module_id_fk), label,
                      f"{actor} gave you {label}", f"{actor} gave you {{n}}: {{items}}", ("stock", obj.module_id_fk),
                      stock_module=obj.module_id_fk)]
    return []


ORDER_WORDS = {"ordered": "ordered", "received": "received", "cancelled": "cancelled"}


def _item(obj: InventoryItem, actor: str) -> list[dict]:
    status = _change(obj, "status")
    if not status or not obj.owner or obj.owner == actor:
        return []
    word = ORDER_WORDS.get((status[1] or "").lower())
    if not word:
        return []
    label = obj.name or f"#{obj.number}"
    return [_note(obj.owner, "orders", ("order", actor, word, obj.module_id_fk), label,
                  f"Your order {label} was {word} by {actor}",
                  f"{{n}} of your orders were {word} by {actor}: {{items}}", ("inventory", obj.module_id_fk),
                  orders_module=obj.module_id_fk, one_link=("inventory-item", obj.id))]


DIRTY_RULES = {MouseRecord: _mouse, CageRecord: _cage, TankRecord: _tank, FishRecord: _fish,
               Organism: _organism, OrgHousing: _housing, StockUnit: _unit, InventoryItem: _item}


def _genotype_call(obj: OrgGenotype, actor: str) -> list[dict]:
    return [_note(None, "genotyping", ("org-call", actor, obj.module_id_fk), f"{obj.assay or 'genotype'}: {obj.result}",
                  f"{actor} recorded a genotype for your {{subject}}: {obj.assay or ''} {obj.result}".replace("  ", " "),
                  f"{actor} recorded {{n}} genotypes for your animals: {{items}}", ("organism", obj.module_id_fk),
                  subject=(obj.subject_kind, obj.subject_id), skip=(actor,))]


@event.listens_for(Session, "before_flush")
def _notice(session, flush_context, instances):
    actor = _actor()
    if not actor:
        return
    notes = session.info.setdefault("notify_notes", [])
    for obj in list(session.dirty):
        rule = DIRTY_RULES.get(type(obj))
        if rule and session.is_modified(obj, include_collections=False):
            notes.extend(rule(obj, actor))
    for obj in list(session.new):
        if isinstance(obj, OrgGenotype):
            notes.extend(_genotype_call(obj, actor))


@event.listens_for(Session, "after_rollback")
def _forget(session):
    session.info.pop("notify_notes", None)


@event.listens_for(Session, "before_commit")
def _deliver(session):
    notes = session.info.pop("notify_notes", None)
    if not notes:
        return
    deliver(session, notes)


# ---------------------------------------------------------------- turning notes into notifications

def _resolve(session, note: dict) -> dict | None:
    """Fill in what the note could not know at flush time: whose cage or
    tank it is, codes, whether an inventory is an orders one."""
    if "cage_owner_of" in note:
        cage = session.get(CageRecord, note["cage_owner_of"])
        if cage is None or not cage.owner or cage.owner in note["skip"]:
            return None
        note["recipient"] = cage.owner
    if "cage_id" in note or "cage_owner_of" in note:
        cage = session.get(CageRecord, note.get("cage_id") or note.get("cage_owner_of"))
        code = cage.cage_id if cage else "?"
        note["one"] = note["one"].replace("{cage}", code)
        note["many"] = note["many"].replace("{cage}", code)
    if "tank_owner_of" in note:
        tank = session.get(TankRecord, note["tank_owner_of"])
        if tank is None or not tank.owner or tank.owner in note["skip"]:
            return None
        note["recipient"] = tank.owner
        note["one"] = note["one"].replace("{tank}", tank.tank_id)
        note["many"] = note["many"].replace("{tank}", tank.tank_id)
    if "orders_module" in note:
        module = session.get(InventoryModule, note["orders_module"])
        if module is None or module.kind != "orders":
            return None
    if "subject" in note:
        kind, subject_id = note["subject"]
        model = {"organism": Organism, "housing": OrgHousing}.get(kind)
        subject = session.get(model, subject_id) if model else None
        if subject is None or not subject.owner or subject.owner in note["skip"]:
            return None
        note["recipient"] = subject.owner
        note["one"] = note["one"].replace("{subject}", subject.code or f"#{subject.id}")
    return note if note.get("recipient") else None


def _link(session, target) -> str:
    kind, ident = target
    try:
        if kind == "mouse":
            return url_for("colony", view="mice", scope="all") + f"#mouse-update-{ident}"
        if kind == "cage":
            return url_for("colony", view="cages", scope="all") + f"#cage-{ident}"
        if kind == "tank":
            return url_for("zebrafish") + f"#tank-{ident}"
        if kind == "organism":
            module = session.get(OrganismModule, ident)
            return url_for("organisms.module", key=module.key) if module else ""
        if kind == "stock":
            module = session.get(StockModule, ident)
            return url_for("stocks.module", key=module.key) if module else ""
        if kind == "inventory":
            module = session.get(InventoryModule, ident)
            return url_for("inventory.module", key=module.key) if module else ""
        if kind == "inventory-item":
            # The order itself, opened in its dialog (?open=, inventory_routes).
            item = session.get(InventoryItem, ident)
            module = session.get(InventoryModule, item.module_id_fk) if item else None
            return url_for("inventory.module", key=module.key, open=item.id) if module else ""
    except Exception:  # noqa: BLE001 — a link is a convenience; the message still goes
        return ""
    return ""


def deliver(session, notes: list[dict]) -> int:
    groups: "OrderedDict[tuple, list[dict]]" = OrderedDict()
    for note in notes:
        note = _resolve(session, dict(note))
        if note is None:
            continue
        key = (note["recipient"], note["category"], note["group"])
        groups.setdefault(key, [])
        if note["item"] not in {n["item"] for n in groups[key]}:
            groups[key].append(note)
    sent = 0
    for (recipient, category, _group), items in groups.items():
        first = items[0]
        if len(items) == 1:
            title = first["one"]
        else:
            listed = ", ".join(n["item"] for n in items[:MAX_LISTED])
            if len(items) > MAX_LISTED:
                listed += f" and {len(items) - MAX_LISTED} more"
            title = first["many"].replace("{n}", str(len(items))).replace("{items}", listed)
        # One item links to that item where there is a page for it; several
        # to the list they are in.
        target = first.get("one_link") if len(items) == 1 and first.get("one_link") else first.get("link")
        link = _link(session, target) if target else ""
        actor = first["group"][1] if len(first["group"]) > 1 else ""
        if send(session, recipient, title, category=category, link=link, actor=actor):
            sent += 1
    return sent


def send(session, recipient: str, title: str, message: str = "", category: str = "general",
         link: str = "", actor: str = "") -> bool:
    """One notification, if the recipient exists, is active, wants this
    category, and is not the person who caused it."""
    if not recipient or recipient == actor:
        return False
    user = session.scalar(select(UserAccount).where(UserAccount.username == recipient))
    if user is None or user.disabled:
        return False
    if getattr(user, f"notify_{category}", True) is False:
        return False
    session.add(NotificationRecord(recipient_username=recipient, title=title[:200], message=message,
                                   category=category, link=link[:300], actor=actor))
    return True


def tell_lab(session, actor: str, title: str, message: str = "", link: str = "") -> int:
    """A "lab" notification for every active member but the actor."""
    from . import lab
    return sum(send(session, name, title, message, category="lab", link=link, actor=actor)
               for name in lab.everyone_but(session, actor))


# ---------------------------------------------------------------- reading

def unread_count(session, username: str) -> int:
    return session.scalar(select(func.count(NotificationRecord.id)).where(
        NotificationRecord.recipient_username == username, NotificationRecord.is_read.is_(False))) or 0


def recent(session, username: str, limit: int = 8, unread_only: bool = False, category: str = "") -> list:
    stmt = select(NotificationRecord).where(NotificationRecord.recipient_username == username)
    if unread_only:
        stmt = stmt.where(NotificationRecord.is_read.is_(False))
    if category:
        stmt = stmt.where(NotificationRecord.category == category)
    return session.scalars(stmt.order_by(NotificationRecord.created_at.desc(), NotificationRecord.id.desc())
                           .limit(limit)).all()


# ---------------------------------------------------------------- the daily reminder

def daily_genotyping_reminder(session, user) -> bool:
    """Once a day, the first time someone opens the app: what of theirs is
    waiting for genotyping. Silent when nothing is, or they turned it off."""
    if not getattr(user, "notify_genotyping", True):
        return False
    today_start = datetime.combine(date.today(), datetime.min.time())
    already = session.scalar(select(func.count(NotificationRecord.id)).where(
        NotificationRecord.recipient_username == user.username, NotificationRecord.category == "genotyping",
        NotificationRecord.actor == "", NotificationRecord.created_at >= today_start))
    if already:
        return False
    from . import lab
    features = lab.features_on(session)
    parts = []
    if features.get("colony", True):
        mice = session.scalar(select(func.count(MouseRecord.id)).where(
            MouseRecord.owner == user.username, MouseRecord.status == "geno",
            MouseRecord.date_of_death.is_(None))) or 0
        if mice:
            parts.append(f"{mice} {'mouse' if mice == 1 else 'mice'}")
    if features.get("zebrafish", True):
        tanks = session.scalar(select(func.count(TankRecord.id)).where(
            TankRecord.owner == user.username, TankRecord.needs_genotyping.is_(True),
            TankRecord.active.is_(True))) or 0
        if tanks:
            parts.append(f"{tanks} {'tank' if tanks == 1 else 'tanks'}")
    if not parts:
        return False
    link = url_for("colony", view="mice", scope="mine") if features.get("colony", True) else url_for("zebrafish")
    session.add(NotificationRecord(recipient_username=user.username,
                                   title="Waiting for genotyping: " + " and ".join(parts),
                                   category="genotyping", link=link, actor=""))
    return True


def daily_experiment_reminder(session, user) -> bool:
    """Once a day, the first time someone opens the app: the manipulations
    and readout days due today (and any overdue) in their active
    experiments. Silent when nothing is, or they turned it off. Each is
    still recorded on the experiment's page."""
    if not getattr(user, "notify_experiments", True):
        return False
    today_start = datetime.combine(date.today(), datetime.min.time())
    already = session.scalar(select(func.count(NotificationRecord.id)).where(
        NotificationRecord.recipient_username == user.username, NotificationRecord.category == "experiments",
        NotificationRecord.actor == "", NotificationRecord.created_at >= today_start))
    if already:
        return False
    from . import experiment_steps as xs
    from . import experiments as ex
    from .models import Experiment
    due, overdue, first = [], 0, None
    for exp in session.scalars(select(Experiment).where(Experiment.owner_username == user.username,
                                                        Experiment.status == "active",
                                                        Experiment.start_date.is_not(None))):
        if not exp.steps:
            continue
        place = ex.place_for(session, exp.db or "colony")
        if place is None:
            continue
        for row in xs.schedule(session, exp, place):
            if row["state"] == "today":
                due.append(f"{row['title']} ({exp.name}, day {row['day']})")
                first = first or ex.page_url(exp) + f"#day-{row['day']}"
            elif row["state"] == "overdue":
                overdue += 1
                first = first or ex.page_url(exp) + f"#day-{row['day']}"
    if not due and not overdue:
        return False
    title = ("Due today: " + "; ".join(due[:3]) + (f" and {len(due) - 3} more" if len(due) > 3 else "")) if due \
        else "Nothing due today in your experiments"
    if overdue:
        title += f" · {overdue} overdue, not recorded yet"
    session.add(NotificationRecord(recipient_username=user.username, title=title[:200], category="experiments",
                                   link=first or "", actor=""))
    return True
