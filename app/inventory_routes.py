"""Routes for lab inventories (samples, orders, reagents, antibodies, custom).

One page per inventory with three layouts: a sheet (edit in place), a box
grid for anything stored in freezer boxes or on shelves, and a status board
for workflows such as orders. Each inventory can be renamed and reshaped in
Configure, and a lab can keep as many as it needs.

Who may do what (see access.py for the general rule):
  * a personal item: its owner or an admin;
  * a lab-common item: anyone may edit it, but only its owner or an admin
    may delete it, change its owner or make it personal again;
  * a new item belongs to whoever creates it; only an admin may create one
    for someone else;
  * Configure and deleting an inventory: an admin or whoever created it;
  * editing or deleting a box: an admin or whoever created it.
"""

from __future__ import annotations

import json
import zlib
from datetime import date, datetime

from flask import (
    Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for,
)
from sqlalchemy import select

from . import access, audit, positions
from . import inventory as presets
from . import inventory_service as svc
from .db import SessionLocal
from . import lab, notify
from .lab import lab_audience
from .formutil import form_changed
from .models import InventoryItem, InventoryModule, InventoryRack

bp = Blueprint("inventory", __name__, url_prefix="/inventory")


@bp.before_request
def require_login():
    if g.get("user") is None:
        return redirect(url_for("login", next=request.path))


class Refused(Exception):
    """A save that must not happen at all: nothing is written."""

    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.status = status


def _date(raw) -> date | None:
    """A date from YYYY-MM-DD; blank is None; anything else is refused
    rather than silently clearing what was stored."""
    raw = str(raw or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise Refused(f"“{raw}” is not a date. Use YYYY-MM-DD.") from None


def _int(raw, default: int, low: int, high: int) -> int:
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


def _module_or_404(session, key: str) -> InventoryModule:
    module = svc.get_module(session, key)
    # Someone else's personal database does not exist, as far as this
    # person can tell (app/lab.py).
    if module is None or not lab.can_see(module):
        abort(404)
    return module


def _wants_json() -> bool:
    return request.headers.get("X-Autosave") == "1"


def _done(key: str, message: str = "", error: str = ""):
    """Answer a save: JSON for inline edits, a redirect back otherwise."""
    if _wants_json():
        if error:
            return jsonify({"ok": False, "error": error}), 409
        return jsonify({"ok": True})
    if error:
        flash(error, "error")
    elif message:
        flash(message, "success")
    referrer = request.referrer or ""
    return redirect(referrer if referrer.startswith(request.host_url) else url_for("inventory.module", key=key))


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


def _can_edit(item: InventoryItem) -> bool:
    return access.can_edit(item, shared=item.is_shared)


def _can_manage(item: InventoryItem) -> bool:
    """Delete it, change its owner, move it between personal and lab
    common: the owner or an admin (anyone, for an unowned item)."""
    return access.is_admin() or access.owns(item) or access.is_unowned(item)


def _manage_denied(mv, item: InventoryItem, what: str) -> str:
    if not _can_edit(item):
        return access.reason_denied(item, noun=mv.item_noun)
    return (f"Anyone can edit a lab-common {mv.item_noun}, but only {item.owner or 'its owner'} "
            f"or an admin can {what}.")


def _can_configure(module: InventoryModule) -> bool:
    return access.is_admin() or (module.created_by or "") == access.username()


def _can_manage_rack(rack: InventoryRack) -> bool:
    return access.can_edit_rack(rack)


# ---------------------------------------------------------------------------
# Creating an inventory
# ---------------------------------------------------------------------------


@bp.route("/")
def index():
    return redirect(url_for("organisms.index"))


@bp.route("/new", methods=["GET", "POST"])
def new_module():
    with SessionLocal() as session:
        if not lab.may_create_database(session):
            flash("An admin has turned off adding databases for members. Ask a lab admin.", "error")
            return redirect(url_for("organisms.index"))
        if request.method == "POST":
            preset = request.form.get("preset", "custom")
            label = (request.form.get("label") or "").strip()
            if not label:
                flash("Give the inventory a name.", "error")
                return redirect(url_for("inventory.new_module", preset=preset))
            module = svc.create_module(session, preset, label, created_by=g.user.username)
            module.private_to = lab.audience_for_new(session, request.form.get("audience", ""))
            if module.private_to and request.form.get("audience") == "lab":
                flash("It is yours for now: only lab admins add databases for everyone. "
                      "Ask one to share it with the lab.", "info")
            if not module.private_to:
                notify.tell_lab(session, g.user.username,
                                f"{g.user.display_name or g.user.username} added {module.label} for the lab")
            if request.form.get("blurb", "").strip():
                module.blurb = request.form["blurb"].strip()
            session.commit()
            flash(f"Created {module.label}.", "success")
            return redirect(url_for("inventory.module", key=module.key))
        preset = request.args.get("preset", "")
        return render_template("inventory/new.html", presets=presets.PRESETS, preset=preset,
                               features=presets.FEATURES, audience=lab_audience(session))


# ---------------------------------------------------------------------------
# The inventory page
# ---------------------------------------------------------------------------


def _item_payload(mv, item: InventoryItem) -> dict:
    attrs = item.attrs_dict
    payload = {
        "id": item.id, "_label": item.name or f"#{item.number}",
        "_locked": not _can_edit(item), "_manage": _can_manage(item),
        "name": item.name, "category": item.category, "status": item.status, "owner": item.owner,
        "is_shared": "1" if item.is_shared else "0", "quantity": item.quantity, "unit": item.unit,
        "vendor": item.vendor, "catalog_number": item.catalog_number, "lot": item.lot,
        "rack_id": item.rack_id_fk or "", "position": svc.rack_label(item),
        "location_note": item.location_note,
        "received_on": item.received_on.isoformat() if item.received_on else "",
        "expires_on": item.expires_on.isoformat() if item.expires_on else "",
        "notes": item.notes,
    }
    for field in mv.fields:
        value = attrs.get(field["key"], "")
        if field["type"] == "source":
            value = value if isinstance(value, dict) else {}
            payload[f"attr_{field['key']}_kind"] = value.get("kind", "")
            payload[f"attr_{field['key']}_ref"] = value.get("ref", "")
        else:
            payload[f"attr_{field['key']}"] = value
    return payload


# Cells the server may change behind the user's back (a status that stamps
# a received date, a grid move, a refused owner change); an answer to a
# save carries their stored values so the row and its "_was" copies match.
ROW_VALUES = ("status", "owner", "is_shared", "rack_id", "position", "received_on", "expires_on")


def _row_json(mv, item: InventoryItem) -> dict:
    """What sheet.js and the page need after a save: the availability dot,
    the cells above, and a fresh payload for the Open dialog."""
    payload = _item_payload(mv, item)
    row = {"values": {k: payload[k] for k in ROW_VALUES}}
    active = svc.is_available(mv, item.status)
    if active is not None:
        row["active"] = active
    return {"ok": True, "row": row, "payload": payload, "id": item.id,
            "position": payload["position"], "rack_id": payload["rack_id"]}


def _grid_payload(mv, racks, items) -> dict:
    return {
        "racks": [{"id": r.id, "name": r.name, "rows": r.rows, "cols": r.cols,
                   "naming": positions.scheme(r.naming),
                   **({"edit": {"data-record-payload": json.dumps({
                       "id": r.id, "_label": r.name, "name": r.name, "rows": r.rows, "cols": r.cols,
                       "kind": r.kind, **{f"naming_{k}": v for k, v in positions.scheme(r.naming).items()}})}}
                      if _can_manage_rack(r) else {})}
                  for r in racks],
        "items": [{
            "id": i.id, "label": i.name or f"#{i.number}",
            "sub": " · ".join(filter(None, [i.category, i.attrs_dict.get("conjugate") or i.attrs_dict.get("host") or ""])),
            "tone": "stock" if i.is_shared else "", "flag": svc.expiry_state(i) == "expired",
            "badge": i.quantity or "",
            "rack": i.rack_id_fk, "row": i.rack_row, "col": i.rack_col,
            "title": " · ".join(filter(None, [i.name, i.category, i.status, i.owner, "lab common" if i.is_shared else ""])),
            "search": " ".join(filter(None, [i.name, i.category, i.status, i.owner, i.vendor, i.catalog_number,
                                             *[str(v) for v in i.attrs_dict.values() if isinstance(v, str)]])).lower(),
            "edit": {"data-record-edit": "item-dialog", "data-record-payload": json.dumps(_item_payload(mv, i))},
        } for i in items],
        "create": {"attrs": {"data-record-edit": "item-dialog"},
                   "payload": {"owner": g.user.username, "status": mv.statuses[0] if mv.statuses else "",
                               "is_shared": "0"},
                   "rack_field": "rack_id", "text_field": "position"},
    }


MOUSE_SOURCE_KINDS = ("mouse", "colony")


def _mouse_links(session, rows_attrs: list[dict], fields: list[dict]) -> dict[str, int]:
    """{mouse ID typed as a source: that mouse's row id}, for linking the
    source chip to the colony."""
    from .models import MouseRecord

    refs = set()
    for attrs in rows_attrs:
        for f in fields:
            src = attrs.get(f["key"])
            if f["type"] == "source" and isinstance(src, dict) and src.get("kind") in MOUSE_SOURCE_KINDS:
                ref = str(src.get("ref") or "").strip()
                if ref.isdigit():
                    refs.add(int(ref))
    if not refs:
        return {}
    return {str(mid): rid for mid, rid in session.execute(
        select(MouseRecord.mouse_id, MouseRecord.id).where(MouseRecord.mouse_id.in_(refs)))}


@bp.route("/<key>")
def module(key: str):
    from .services import current_lab_usernames, sample_sources, sample_source_label

    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        items = list(session.scalars(select(InventoryItem).where(InventoryItem.module_id_fk == row.id)
                                     .order_by(InventoryItem.number.desc())))
        racks = list(session.scalars(select(InventoryRack).where(InventoryRack.module_id_fk == row.id)
                                     .order_by(InventoryRack.name)))
        me = g.user.username
        source_fields = [f for f in mv.fields if f["type"] == "source"]
        sources = sample_sources(session) if source_fields else []
        mouse_links = _mouse_links(session, [i.attrs_dict for i in items], source_fields) if source_fields else {}
        rows = []
        for item in items:
            attrs = item.attrs_dict
            rows.append({
                "item": item, "attrs": attrs,
                "editable": _can_edit(item),
                "manageable": _can_manage(item),
                "mine": item.owner == me,
                "position": svc.rack_label(item),
                "expiry": svc.expiry_state(item),
                "available": svc.is_available(mv, item.status),
                "ended_on": attrs.get(svc.ENDED_ATTR, ""),
                "source_labels": {f["key"]: sample_source_label((attrs.get(f["key"]) or {}).get("kind", ""), sources)
                                  for f in source_fields if isinstance(attrs.get(f["key"]), dict)},
                "payload": _item_payload(mv, item),
            })
        # Saved column widths / hidden columns are by position, so a
        # reconfigured sheet starts fresh instead of hiding the wrong ones.
        layout = json.dumps([mv.settings["features"], [f["key"] for f in mv.table_fields], bool(mv.statuses), 2])
        stock_targets = ([m for m in svc.list_modules(session) if m.kind in ("reagents", "antibodies")]
                         if row.kind == "orders" else [])
        context = {
            "module": mv, "rows": rows, "racks": racks, "col_sig": format(zlib.crc32(layout.encode()), "x"),
            "manageable_racks": {r.id for r in racks if _can_manage_rack(r)},
            "grid": _grid_payload(mv, racks, items) if mv.has("storage") else None,
            "usernames": current_lab_usernames(session), "sources": sources, "mouse_links": mouse_links,
            "next_number": svc.next_number(session, row.id),
            "reagents_module": stock_targets[0] if stock_targets else None,
            "can_configure": _can_configure(row), "is_admin": access.is_admin(),
            "terminal_statuses": sorted(svc.TERMINAL_STATUSES),
            "counts": {
                "all": len(items),
                "mine": sum(1 for i in items if i.owner == me),
                "lab": sum(1 for i in items if i.is_shared),
                "open": sum(1 for i in items if i.status in mv.open_statuses),
                "expired": sum(1 for r in rows if r["expiry"] == "expired"),
                "soon": sum(1 for r in rows if r["expiry"] == "soon"),
            },
        }
    return render_template("inventory/module.html", **context)


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


def _mouse_exists(session, ref: str) -> bool:
    from .models import MouseRecord

    return ref.isdigit() and session.scalar(
        select(MouseRecord.id).where(MouseRecord.mouse_id == int(ref))) is not None


def _item_from_form(session, mv, item: InventoryItem, form, creating: bool = False) -> tuple[str | None, list[str]]:
    """Copy the submitted fields onto `item` (only fields the form sent).

    Raises Refused when the save must not happen (a blank order name, a
    date that is not a date, an unknown status, a change the user may not
    make); the caller rolls back. Returns (a position problem, notes):
    a position that cannot be taken leaves the rest saved."""
    notes: list[str] = []
    manage = creating or _can_manage(item)
    me = access.username()

    def text(name, limit=200):
        if name in form:
            setattr(item, name, (form.get(name) or "").strip()[:limit])

    if "name" in form:
        name = (form.get("name") or "").strip()[:200]
        if not name and mv.row.kind == "orders":
            raise Refused("An order needs an item name.")
        item.name = name
    text("category", limit=80)

    if "owner" in form:
        owner = (form.get("owner") or "").strip()[:80]
        if creating and not access.is_admin() and owner != me:
            if owner:
                notes.append(f"Only an admin can add a {mv.item_noun} for someone else, so this one is yours.")
            owner = me
        if owner != (item.owner or ""):
            if not manage:
                raise Refused(_manage_denied(mv, item, "change who it belongs to"), 403)
            item.owner = owner
    if "is_shared" in form:
        shared = form.get("is_shared") in ("1", "true", "on")
        if shared != bool(item.is_shared):
            if not manage:
                raise Refused(_manage_denied(mv, item, "make it personal"), 403)
            item.is_shared = shared

    for name, limit in (("quantity", 60), ("unit", 30), ("vendor", 120), ("catalog_number", 120),
                        ("lot", 120), ("location_note", 200)):
        text(name, limit=limit)
    for name in ("received_on", "expires_on"):
        if name in form and form_changed(form, name):
            setattr(item, name, _date(form.get(name)))
    if "notes" in form:
        item.notes = (form.get("notes") or "").strip()

    attrs = item.attrs_dict
    before = json.dumps(attrs, sort_keys=True)
    for field in mv.fields:
        k = field["key"]
        if field["type"] == "source":
            if f"attr_{k}_kind" in form or f"attr_{k}_ref" in form:
                value = {"kind": (form.get(f"attr_{k}_kind") or "").strip(),
                         "ref": (form.get(f"attr_{k}_ref") or "").strip()}
                old = attrs.get(k) if isinstance(attrs.get(k), dict) else {}
                if (value["kind"] in MOUSE_SOURCE_KINDS and value["ref"] and value != old
                        and not _mouse_exists(session, value["ref"])):
                    notes.append(f"There is no mouse {value['ref']} in the colony; the source was saved as typed.")
                attrs[k] = value
        elif f"attr_{k}" in form:
            value = (form.get(f"attr_{k}") or "").strip()
            if field["type"] == "date" and value:
                value = _date(value).isoformat()
            attrs[k] = value
    if json.dumps(attrs, sort_keys=True) != before:
        item.attrs = json.dumps(attrs)

    # Status last: it may fill the received date or stamp a used-up date.
    if "status" in form and (creating or form_changed(form, "status")):
        problem = svc.apply_status(mv, item, form.get("status"))
        if problem:
            raise Refused(problem)

    if mv.has("storage") and "rack_id" in form and form_changed(form, "rack_id", "position"):
        return svc.apply_position(session, item, form.get("rack_id"), form.get("position")), notes
    return None, notes


@bp.route("/<key>/items/save", methods=["POST"])
def save_item(key: str):
    """Create an item, or update one from the dialog (id in the form)."""
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        item_id = request.form.get("id", "").strip()
        creating = not item_id.isdigit()
        if not creating:
            item = session.get(InventoryItem, int(item_id))
            if item is None or item.module_id_fk != row.id:
                abort(404)
            if not _can_edit(item):
                return _done(key, error=access.reason_denied(item, noun=mv.item_noun))
        else:
            if (request.form.get("names") or "").strip() or (request.form.get("count") or "1").strip() != "1":
                return _create_many(session, row, mv, request.form)
            item = InventoryItem(module_id_fk=row.id, number=svc.next_number(session, row.id),
                                 owner=g.user.username, status=mv.statuses[0] if mv.statuses else "")
            session.add(item)
        try:
            error, notes = _item_from_form(session, mv, item, request.form, creating=creating)
        except Refused as refused:
            session.rollback()
            return _done(key, error=str(refused))
        item.updated_at, item.updated_by = datetime.utcnow(), g.user.username
        session.commit()
        label = item.name or f"#{item.number}"
        for note in notes:
            flash(note, "warning")
        if error:
            return _done(key, error=f"Saved {label}, but: {error}")
        return _done(key, message=f"Saved {label}.")


MAX_AT_ONCE = 50

# Fields a batch of new items does not copy from the dialog as they are.
MANY_ONLY = ("id", "count", "names", "rack_id", "position")


def _create_many(session, row: InventoryModule, mv, form):
    """How many > 1, or pasted names: identical items with consecutive
    numbers (one per pasted name, named after it), side by side in the
    chosen box from the given position, taking the next free cells. One
    batch, so Batch history can undo them; nothing is created when any of
    them would be refused."""
    key = row.key
    names = [x.strip()[:200] for x in (form.get("names") or "").splitlines() if x.strip()]
    if names:
        count = len(names)
        if count > MAX_AT_ONCE:
            return _done(key, error=f"Paste at most {MAX_AT_ONCE} names at a time ({count} given).")
    else:
        count = _int(form.get("count"), 0, -1, 10_000)
        if not 1 <= count <= MAX_AT_ONCE:
            return _done(key, error=f"Add between 1 and {MAX_AT_ONCE} {mv.item_noun_plural} at a time.")

    rack, cells, pos = None, [], (form.get("position") or "").strip()
    rack_raw = (form.get("rack_id") or "").strip() if mv.has("storage") else ""
    if rack_raw:
        rack = session.get(InventoryRack, int(rack_raw)) if rack_raw.isdigit() else None
        if rack is None or rack.module_id_fk != row.id:
            return _done(key, error="That box is not part of this inventory.")
        start = None
        if pos:
            start = positions.parse(pos, rack.naming, rack.rows, rack.cols)
            if start is None:
                return _done(key, error=(
                    f"“{pos}” is not a position in {rack.name} "
                    f"({positions.label(1, 1, rack.naming, rack.cols)}–{positions.label(rack.rows, rack.cols, rack.naming, rack.cols)})."))
        cells = svc.free_cells(session, rack, count, start)

    fresh = {k: v for k, v in form.items() if not k.endswith("_was") and k not in MANY_ONLY}
    number = svc.next_number(session, row.id)
    first_status = mv.statuses[0] if mv.statuses else ""
    created, notes = [], []
    try:
        with audit.batch(session, "create", f"New {mv.item_noun_plural} ×{count}", "inventory_items"):
            for i in range(count):
                item = InventoryItem(module_id_fk=row.id, number=number + i, owner=g.user.username, status=first_status)
                session.add(item)
                data = dict(fresh, name=names[i]) if names else fresh
                _, item_notes = _item_from_form(session, mv, item, data, creating=True)
                notes += [n for n in item_notes if n not in notes]
                if rack is not None:
                    item.rack_id_fk = rack.id
                    if i < len(cells):
                        item.rack_row, item.rack_col = cells[i]
                item.updated_at, item.updated_by = datetime.utcnow(), g.user.username
                created.append(item)
            session.flush()
    except Refused as refused:
        session.rollback()
        return _done(key, error=str(refused))
    session.commit()
    for note in notes:
        flash(note, "warning")
    where = f" in {rack.name}" if rack is not None else ""
    span = f"#{created[0].number}" if count == 1 else f"#{created[0].number}–#{created[-1].number} ({count} {mv.item_noun_plural})"
    flash(f"Created {span}{where}.", "success")
    unplaced = created[len(cells):] if rack is not None else []
    if unplaced:
        labels = ", ".join(i.name or f"#{i.number}" for i in unplaced[:5]) + ("…" if len(unplaced) > 5 else "")
        return _done(key, error=(f"{rack.name} had room for {len(cells)} of {count}"
                                 f"{' from ' + pos if pos else ''}: {len(unplaced)} did not fit ({labels}) "
                                 f"and are in it without a position."))
    return _done(key)


@bp.route("/<key>/items/<int:item_id>/update", methods=["POST"])
def update_item(key: str, item_id: int):
    """Inline edit from the sheet; answers JSON (see _row_json)."""
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        item = session.get(InventoryItem, item_id)
        if item is None or item.module_id_fk != row.id:
            return jsonify({"ok": False, "error": "That record no longer exists."}), 404
        if not _can_edit(item):
            return jsonify({"ok": False, "error": access.reason_denied(item, noun=mv.item_noun)}), 403
        try:
            error, notes = _item_from_form(session, mv, item, request.form)
        except Refused as refused:
            session.rollback()
            return jsonify({"ok": False, "error": str(refused)}), refused.status
        if error:
            session.rollback()
            return jsonify({"ok": False, "error": error}), 409
        item.updated_at, item.updated_by = datetime.utcnow(), g.user.username
        session.commit()
        answer = _row_json(mv, item)
        if notes:
            answer["notes"] = notes
        return jsonify(answer)


@bp.route("/<key>/items/<int:item_id>/delete", methods=["POST"])
def delete_item(key: str, item_id: int):
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        item = session.get(InventoryItem, item_id)
        if item is not None and item.module_id_fk == row.id:
            if not _can_manage(item):
                return _done(key, error=_manage_denied(mv, item, "delete it"))
            label = item.name or f"#{item.number}"
            session.delete(item)
            session.commit()
            return _done(key, message=f"Deleted {label}.")
    return _done(key)


# attrs that describe one physical item, not what it is: a copy starts
# without them.
NOT_COPIED_ATTRS = ("stocked_as", svc.ENDED_ATTR)


@bp.route("/<key>/items/<int:item_id>/duplicate", methods=["POST"])
def duplicate_item(key: str, item_id: int):
    """A copy for the next aliquot or re-order: same details, no position,
    owned by whoever made the copy."""
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        item = session.get(InventoryItem, item_id)
        if item is None or item.module_id_fk != row.id:
            abort(404)
        attrs = {k: v for k, v in item.attrs_dict.items() if k not in NOT_COPIED_ATTRS}
        copy = InventoryItem(
            module_id_fk=row.id, number=svc.next_number(session, row.id), name=item.name,
            category=item.category, status=(svc.view(row).statuses or [""])[0], owner=g.user.username,
            is_shared=item.is_shared, quantity=item.quantity, unit=item.unit, vendor=item.vendor,
            catalog_number=item.catalog_number, lot="", attrs=json.dumps(attrs), notes=item.notes)
        session.add(copy)
        session.commit()
        return _done(key, message=f"Duplicated {item.name or '#' + str(item.number)} as #{copy.number}.")


@bp.route("/<key>/items/<int:item_id>/place", methods=["POST"])
def place_item(key: str, item_id: int):
    """Move on the box grid; no rack unplaces. Dropping on an occupied cell
    swaps the two, but only when the moved item has a cell to give back:
    an unplaced item cannot push another out of its place."""
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        item = session.get(InventoryItem, item_id)
        if item is None or item.module_id_fk != row.id:
            return jsonify({"ok": False, "error": "That record no longer exists."}), 404
        if not _can_edit(item):
            return jsonify({"ok": False, "error": access.reason_denied(item, noun=mv.item_noun)}), 403
        rack_id = request.form.get("rack_id", "").strip()
        if not rack_id:
            item.rack_id_fk = item.rack_row = item.rack_col = None
            session.commit()
            return jsonify(_row_json(mv, item))
        rack = session.get(InventoryRack, int(rack_id)) if rack_id.isdigit() else None
        try:
            r, c = int(request.form.get("row", "")), int(request.form.get("col", ""))
        except ValueError:
            return jsonify({"ok": False, "error": "Missing row or column."}), 400
        if rack is None or rack.module_id_fk != row.id or not (1 <= r <= rack.rows and 1 <= c <= rack.cols):
            return jsonify({"ok": False, "error": "That position is not in the box."}), 400
        holder = session.scalar(select(InventoryItem).where(
            InventoryItem.rack_id_fk == rack.id, InventoryItem.rack_row == r,
            InventoryItem.rack_col == c, InventoryItem.id != item.id))
        if holder is not None:
            holder_label = holder.name or f"#{holder.number}"
            if item.rack_id_fk is None or item.rack_row is None or item.rack_col is None:
                return jsonify({"ok": False, "error": f"That cell holds {holder_label}. Drop it on an empty cell, "
                                                      f"or move {holder_label} out first."}), 409
            if not _can_edit(holder):
                return jsonify({"ok": False, "error": f"That cell holds {holder_label}, which you may not move."}), 403
            holder.rack_id_fk, holder.rack_row, holder.rack_col = item.rack_id_fk, item.rack_row, item.rack_col
        item.rack_id_fk, item.rack_row, item.rack_col = rack.id, r, c
        session.commit()
        return jsonify(_row_json(mv, item))


@bp.route("/<key>/items/<int:item_id>/status", methods=["POST"])
def set_status(key: str, item_id: int):
    """Board drag; answers JSON like an inline save."""
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        item = session.get(InventoryItem, item_id)
        if item is None or item.module_id_fk != row.id:
            return jsonify({"ok": False, "error": "That record no longer exists."}), 404
        if not _can_edit(item):
            return jsonify({"ok": False, "error": access.reason_denied(item, noun=mv.item_noun)}), 403
        problem = svc.apply_status(mv, item, request.form.get("status"))
        if problem:
            session.rollback()
            return jsonify({"ok": False, "error": problem}), 400
        item.updated_at, item.updated_by = datetime.utcnow(), g.user.username
        session.commit()
        return jsonify(_row_json(mv, item))


STOCK_KINDS = ("reagents", "antibodies")


@bp.route("/<key>/items/<int:item_id>/to-reagents", methods=["POST"])
def order_to_reagents(key: str, item_id: int):
    """A received order becomes a reagent (or antibody) in stock, once, with
    its vendor, catalogue number and quantity carried over."""
    target_key = request.form.get("target", "")
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        order = session.get(InventoryItem, item_id)
        if order is None or order.module_id_fk != row.id or row.kind != "orders":
            return _done(key, error="That order no longer exists.")
        if not _can_edit(order):
            return _done(key, error=access.reason_denied(order, noun="order"))
        if (order.status or "").lower() != "received":
            return _done(key, error=f"Mark {order.name or 'the order'} received before adding it to stock.")
        stocked = order.attrs_dict.get("stocked_as")
        if stocked:
            return _done(key, error=f"{order.name or 'That order'} is already in stock ({stocked.replace(':', ' #')}).")
        target = svc.get_module(session, target_key) if target_key else svc.first_of_kind(session, "reagents")
        if target is None or target.kind not in STOCK_KINDS or not lab.can_see(target):
            return _done(key, error="Pick a reagents or antibodies inventory to add it to.")
        tv = svc.view(target)
        with audit.batch(session, "mixed", f"order #{order.number} to {target.label}", "inventory_items"):
            stock = InventoryItem(
                module_id_fk=target.id, number=svc.next_number(session, target.id), name=order.name,
                status=tv.statuses[0] if tv.statuses else "", owner=g.user.username,
                is_shared=request.form.get("shared") == "1", quantity=order.quantity, unit=order.unit,
                vendor=order.vendor, catalog_number=order.catalog_number,
                received_on=order.received_on or date.today(),
                notes=f"From {mv.item_noun} #{order.number}" + (f". {order.notes}" if order.notes else ""))
            session.add(stock)
            attrs = order.attrs_dict
            attrs["stocked_as"] = f"{target.key}:{stock.number}"
            order.attrs = json.dumps(attrs)
        session.commit()
        flash(f"Added {stock.name} to {target.label} as #{stock.number}.", "success")
        return redirect(url_for("inventory.module", key=target.key))


# ---------------------------------------------------------------------------
# Batch actions on ticked rows
# ---------------------------------------------------------------------------


BULK_ACTIONS = {
    # action: (who may, past tense for the message)
    "status": ("edit", "Set the status of"),
    "rack": ("edit", "Moved"),
    "owner": ("manage", "Changed the owner of"),
    "shared": ("manage", "Changed who can edit"),
    "delete": ("manage", "Deleted"),
}


@bp.route("/<key>/items/bulk", methods=["POST"])
def bulk(key: str):
    """Set status, move to a box, set owner, personal / lab common, delete.
    One batch, so it can be undone; rows the user may not change are
    skipped and counted."""
    action = request.form.get("action", "")
    value = (request.form.get("value") or "").strip()
    ids = [int(i) for i in request.form.getlist("selected_ids") if i.isdigit()]
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        if action not in BULK_ACTIONS:
            return _done(key, error="Pick what to do with them.")
        items = list(session.scalars(select(InventoryItem).where(
            InventoryItem.module_id_fk == row.id, InventoryItem.id.in_(ids)).order_by(InventoryItem.number)))
        if not items:
            return _done(key, error=f"No {mv.item_noun_plural} selected.")
        rack = None
        if action == "status" and mv.statuses and svc.match_status(mv, value) is None:
            return _done(key, error=f"“{value}” is not a status here.")
        if action == "owner" and not value:
            return _done(key, error="Type whose they should be.")
        if action == "rack" and value:
            rack = session.get(InventoryRack, int(value)) if value.isdigit() else None
            if rack is None or rack.module_id_fk != row.id:
                return _done(key, error="That box is not part of this inventory.")
        need, verb = BULK_ACTIONS[action]
        done = skipped = 0
        notes: list[str] = []
        with audit.batch(session, "delete" if action == "delete" else "update",
                         f"{action} ×{len(items)} {mv.item_noun_plural}", "inventory_items"):
            for item in items:
                allowed = _can_edit(item) if need == "edit" else _can_manage(item)
                if not allowed:
                    skipped += 1
                    continue
                if action == "delete":
                    session.delete(item)
                    done += 1
                    continue
                if action == "status":
                    svc.apply_status(mv, item, value)
                elif action == "owner":
                    item.owner = value[:80]
                elif action == "shared":
                    item.is_shared = value == "1"
                elif action == "rack":
                    if rack is None:
                        item.rack_id_fk = item.rack_row = item.rack_col = None
                    elif item.rack_id_fk != rack.id:
                        cell = svc.free_cell(session, rack)
                        item.rack_id_fk = rack.id
                        item.rack_row, item.rack_col = cell if cell else (None, None)
                        if cell is None:
                            notes.append(f"{rack.name} is full: {item.name or '#' + str(item.number)} is in it without a position.")
                        session.flush()  # the next item sees this cell as taken
                item.updated_at, item.updated_by = datetime.utcnow(), g.user.username
                done += 1
        noun = mv.item_noun if done == 1 else mv.item_noun_plural
        session.commit()
    message = f"{verb} {done} {noun}."
    if skipped:
        message += (f" {skipped} left alone: only their owner or an admin can do that."
                    if need == "manage" else f" {skipped} belong to someone else and were left alone.")
    for note in notes[:5]:
        flash(note, "info")
    if not done:
        return _done(key, error=message)
    return _done(key, message=message)


# ---------------------------------------------------------------------------
# Boxes and shelves
# ---------------------------------------------------------------------------


@bp.route("/<key>/racks/save", methods=["POST"])
def save_rack(key: str):
    form = request.form
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        rack_id = form.get("id", "").strip()
        rack = session.get(InventoryRack, int(rack_id)) if rack_id.isdigit() else None
        if rack is not None and rack.module_id_fk != row.id:
            abort(404)
        if rack is not None and not _can_manage_rack(rack):
            flash(f"Only {rack.created_by or 'an admin'}{' or an admin' if rack.created_by else ''} can change {rack.name}.", "error")
            return redirect(url_for("inventory.module", key=key))
        rows = _int(form.get("rows"), rack.rows if rack else 9, 1, 26)
        cols = _int(form.get("cols"), rack.cols if rack else 9, 1, 40)
        if rack is not None and (rows < rack.rows or cols < rack.cols):
            outside = session.scalars(select(InventoryItem).where(
                InventoryItem.rack_id_fk == rack.id,
                (InventoryItem.rack_row > rows) | (InventoryItem.rack_col > cols))).all()
            if outside:
                n = len(outside)
                flash(f"{rack.name} cannot shrink to {rows} × {cols}: {n} "
                      f"{mv.item_noun if n == 1 else mv.item_noun_plural} sit outside that "
                      f"({', '.join(i.name or '#' + str(i.number) for i in outside[:4])}{'…' if n > 4 else ''}). "
                      f"Move them first.", "error")
                return redirect(url_for("inventory.module", key=key))
        if rack is None:
            rack = InventoryRack(module_id_fk=row.id, created_by=g.user.username)
            session.add(rack)
        rack.name = (form.get("name") or "").strip()[:120] or "Box"
        rack.kind = (form.get("kind") or "box").strip()[:40]
        rack.rows, rack.cols = rows, cols
        rack.naming = json.dumps(positions.scheme_from_form(form))
        session.commit()
        flash(f"Saved {rack.name}.", "success")
    return redirect(url_for("inventory.module", key=key))


@bp.route("/<key>/racks/<int:rack_id>/delete", methods=["POST"])
def delete_rack(key: str, rack_id: int):
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        rack = session.get(InventoryRack, rack_id)
        if rack is not None and rack.module_id_fk == row.id:
            if not _can_manage_rack(rack):
                flash(f"Only {rack.created_by or 'an admin'}{' or an admin' if rack.created_by else ''} can delete {rack.name}.", "error")
                return redirect(url_for("inventory.module", key=key))
            with audit.batch(session, "mixed", f"delete box {rack.name}", "inventory_racks"):
                for item in session.scalars(select(InventoryItem).where(InventoryItem.rack_id_fk == rack.id)):
                    item.rack_id_fk = item.rack_row = item.rack_col = None
                session.flush()
                name = rack.name
                session.delete(rack)
            session.commit()
            flash(f"Deleted {name}. What was in it is now unplaced.", "success")
    return redirect(url_for("inventory.module", key=key))


# ---------------------------------------------------------------------------
# Configure: rename, features, columns, delete
# ---------------------------------------------------------------------------


ICON_CHOICES = ["vial", "vials", "flask", "flask-vial", "antibody", "cart", "box", "dna", "plasmid",
                "snowflake", "microscope", "syringe", "droplet", "bacterium", "virus", "seedling",
                "list", "tag", "archive", "file"]


def _fields_from_form(form) -> list[dict]:
    """The Columns table; every column gets a key of its own, even two new
    ones with the same name."""
    from .organism_service import slugify

    fields, used = [], set()
    for i in range(_int(form.get("field_count"), 0, 0, 200)):
        flabel = (form.get(f"field_{i}_label") or "").strip()
        if not flabel or form.get(f"field_{i}_remove"):
            continue
        base = (form.get(f"field_{i}_key") or "").strip()
        if not base:
            slug = slugify(flabel)
            base = slug if slug != "organism" or flabel.lower() == "organism" else f"field_{i}"
        key, n = base, 2
        while key in used:
            key, n = f"{base}_{n}", n + 1
        used.add(key)
        fields.append({
            "key": key, "label": flabel, "type": form.get(f"field_{i}_type") or "text",
            "options": [o.strip() for o in (form.get(f"field_{i}_options") or "").split(",") if o.strip()],
            "icon": form.get(f"field_{i}_icon") or "",
            "width": _int(form.get(f"field_{i}_width"), 130, 60, 400),
            "in_table": form.get(f"field_{i}_in_table") == "1",
        })
    return fields


@bp.route("/<key>/configure", methods=["GET", "POST"])
def configure(key: str):
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        if not _can_configure(row):
            flash(f"Only an admin, or whoever created {row.label}, can configure it.", "error")
            return redirect(url_for("inventory.module", key=key))
        if request.method == "POST":
            form = request.form
            label = (form.get("label") or "").strip()
            if not label:
                flash("An inventory needs a name.", "error")
                return redirect(url_for("inventory.configure", key=key))
            row.label = label[:120]
            row.blurb = (form.get("blurb") or "").strip()
            row.item_noun = (form.get("item_noun") or "item").strip()[:60]
            row.item_noun_plural = (form.get("item_noun_plural") or row.item_noun + "s").strip()[:60]
            if form.get("icon") in ICON_CHOICES:
                row.icon = form["icon"]
            row.enabled = "1" in form.getlist("enabled")
            lines = lambda name: [x.strip() for x in (form.get(name) or "").replace(",", "\n").split("\n") if x.strip()]
            choices, plans = {}, {}
            for name, (column, limit) in svc.CHOICE_COLUMNS.items():
                rows = _choice_rows(form, name, limit)
                if rows is None:  # an older form: a plain list, nothing relabelled
                    choices[name] = lines(name)
                    continue
                plan = svc.plan_choices(rows, svc.choice_counts(session, row.id, column))
                choices[name], plans[column] = plan.values, plan
            problems = [(column, old) for column, plan in plans.items() for old in plan.problems]
            if problems:
                session.rollback()
                counts = {column: svc.choice_counts(session, row.id, column) for column, _ in problems}
                mv = svc.view(row)
                flash("Not saved: " + " ".join(
                    f"{_n(counts[column][old], mv)} still {'have' if counts[column][old] != 1 else 'has'} the "
                    f"{'status' if column == 'status' else mv.category_label.lower()} “{old}”. "
                    f"Pick what {'they' if counts[column][old] != 1 else 'it'} should become, or keep it."
                    for column, old in problems), "error")
                return redirect(url_for("inventory.configure", key=key))
            settings = json.dumps(presets.normalise_settings({
                "features": form.getlist("features"),
                "category_label": (form.get("category_label") or "Category").strip(),
                "categories": choices["categories"], "statuses": choices["statuses"], "fields": _fields_from_form(form),
            }))
            category_label = presets.normalise_settings(settings)["category_label"]
            changes = []
            for column, plan in plans.items():
                counts = svc.choice_counts(session, row.id, column)
                what = "status" if column == "status" else category_label.lower()
                for old, (new, how) in plan.relabel.items():
                    if counts.get(old):
                        verb = "Rename" if how == "rename" else "Replace"
                        changes.append(f"{verb} {what} ‘{old}’ → ‘{new}’ ({_n(counts[old], row)})")
            if changes:
                # One batch with the new settings, so Batch history puts the
                # list and the items back together.
                with audit.batch(session, "update", "; ".join(changes), "inventory_items"):
                    row.settings = settings
                    for column, plan in plans.items():
                        svc.relabel_items(session, row.id, column, plan.relabel)
            else:
                row.settings = settings
            session.commit()
            flash(f"Saved {row.label}." + (" " + "; ".join(changes) + "." if changes else ""), "success")
            return redirect(url_for("inventory.module", key=key))
        mv = svc.view(row)
        return render_template("inventory/configure.html", module=mv, features=presets.FEATURES,
                               field_types=presets.FIELD_TYPES, icons=ICON_CHOICES,
                               status_counts=svc.choice_counts(session, row.id, "status"),
                               category_counts=svc.choice_counts(session, row.id, "category"),
                               item_count=len(list(session.scalars(select(InventoryItem.id).where(InventoryItem.module_id_fk == row.id)))))


def _n(count: int, mv) -> str:
    return f"{count} {mv.item_noun if count == 1 else mv.item_noun_plural}"


def _choice_rows(form, name: str, limit: int) -> list[dict] | None:
    """The Configure rows of a choice list (statuses_0_value, _was, _remove,
    _replace…), or None when the form sent the list as plain text."""
    if f"{name}_count" not in form:
        return None
    return [{"value": (form.get(f"{name}_{i}_value") or "").strip()[:limit],
             "was": (form.get(f"{name}_{i}_was") or "").strip(),
             "remove": bool(form.get(f"{name}_{i}_remove")),
             "replace": (form.get(f"{name}_{i}_replace") or "").strip()}
            for i in range(_int(form.get(f"{name}_count"), 0, 0, 200))]


@bp.route("/<key>/delete", methods=["POST"])
def delete_module(key: str):
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        if not _can_configure(row):
            flash("Only an admin, or whoever created it, can delete an inventory.", "error")
            return redirect(url_for("inventory.module", key=key))
        if (request.form.get("confirm") or "").strip() != row.label:
            flash(f"Type the name “{row.label}” to confirm deleting it.", "error")
            return redirect(url_for("inventory.configure", key=key))
        for item in session.scalars(select(InventoryItem).where(InventoryItem.module_id_fk == row.id)):
            session.delete(item)
        for rack in session.scalars(select(InventoryRack).where(InventoryRack.module_id_fk == row.id)):
            session.delete(rack)
        label = row.label
        session.delete(row)
        session.commit()
        flash(f"Deleted {label} and everything in it.", "success")
    return redirect(url_for("organisms.index"))
