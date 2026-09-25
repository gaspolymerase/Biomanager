"""Routes for lab inventories (samples, orders, reagents, antibodies, custom).

One page per inventory with three layouts: a sheet (edit in place), a box
grid for anything stored in freezer boxes or on shelves, and a status board
for workflows such as orders. Each inventory can be renamed and reshaped in
Configure, and a lab can keep as many as it needs."""

from __future__ import annotations

import json
import zlib
from datetime import date, datetime

from flask import (
    Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for,
)
from sqlalchemy import select

from . import access, positions
from . import inventory as presets
from . import inventory_service as svc
from .db import SessionLocal
from .formutil import form_changed
from .models import InventoryItem, InventoryModule, InventoryRack

bp = Blueprint("inventory", __name__, url_prefix="/inventory")


@bp.before_request
def require_login():
    if g.get("user") is None:
        return redirect(url_for("login", next=request.path))


def _date(raw) -> date | None:
    raw = (raw or "").strip()
    try:
        return date.fromisoformat(raw) if raw else None
    except ValueError:
        return None


def _module_or_404(session, key: str) -> InventoryModule:
    module = svc.get_module(session, key)
    if module is None:
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
# Creating an inventory
# ---------------------------------------------------------------------------


@bp.route("/")
def index():
    return redirect(url_for("organisms.index"))


@bp.route("/new", methods=["GET", "POST"])
def new_module():
    with SessionLocal() as session:
        if request.method == "POST":
            preset = request.form.get("preset", "custom")
            label = (request.form.get("label") or "").strip()
            if not label:
                flash("Give the inventory a name.", "error")
                return redirect(url_for("inventory.new_module", preset=preset))
            module = svc.create_module(session, preset, label, created_by=g.user.username)
            if request.form.get("blurb", "").strip():
                module.blurb = request.form["blurb"].strip()
            session.commit()
            flash(f"Created {module.label}.", "success")
            return redirect(url_for("inventory.module", key=module.key))
        preset = request.args.get("preset", "")
        return render_template("inventory/new.html", presets=presets.PRESETS, preset=preset,
                               features=presets.FEATURES)


# ---------------------------------------------------------------------------
# The inventory page
# ---------------------------------------------------------------------------


def _item_payload(mv, item: InventoryItem) -> dict:
    attrs = item.attrs_dict
    payload = {
        "id": item.id, "_label": item.name or f"#{item.number}",
        "_locked": not access.can_edit(item, shared=item.is_shared),
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


def _grid_payload(mv, racks, items) -> dict:
    return {
        "racks": [{"id": r.id, "name": r.name, "rows": r.rows, "cols": r.cols,
                   "naming": positions.scheme(r.naming),
                   "edit": {"data-record-payload": json.dumps({
                       "id": r.id, "_label": r.name, "name": r.name, "rows": r.rows, "cols": r.cols,
                       "kind": r.kind, **{f"naming_{k}": v for k, v in positions.scheme(r.naming).items()}})}}
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
        sources = sample_sources(session) if any(f["type"] == "source" for f in mv.fields) else []
        rows = []
        for item in items:
            attrs = item.attrs_dict
            rows.append({
                "item": item, "attrs": attrs,
                "editable": access.can_edit(item, shared=item.is_shared),
                "mine": item.owner == me,
                "position": svc.rack_label(item),
                "expiry": svc.expiry_state(item),
                "source_labels": {f["key"]: sample_source_label((attrs.get(f["key"]) or {}).get("kind", ""), sources)
                                  for f in mv.fields if f["type"] == "source" and isinstance(attrs.get(f["key"]), dict)},
                "payload": _item_payload(mv, item),
            })
        # Saved column widths / hidden columns are by position, so a
        # reconfigured sheet starts fresh instead of hiding the wrong ones.
        layout = json.dumps([mv.settings["features"], [f["key"] for f in mv.table_fields], bool(mv.statuses)])
        context = {
            "module": mv, "rows": rows, "racks": racks, "col_sig": format(zlib.crc32(layout.encode()), "x"),
            "grid": _grid_payload(mv, racks, items) if mv.has("storage") else None,
            "usernames": current_lab_usernames(session), "sources": sources,
            "next_number": svc.next_number(session, row.id),
            "reagents_module": svc.first_of_kind(session, "reagents") if row.kind == "orders" else None,
            "counts": {
                "all": len(items),
                "mine": sum(1 for i in items if i.owner == me),
                "lab": sum(1 for i in items if i.is_shared),
                "open": sum(1 for i in items if i.status in mv.open_statuses),
                "expired": sum(1 for i in items if svc.expiry_state(i) == "expired"),
            },
        }
    return render_template("inventory/module.html", **context)


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


def _item_from_form(session, mv, item: InventoryItem, form) -> str | None:
    """Copy the submitted fields onto `item` (only fields the form sent)."""
    def text(name, attr=None, limit=200):
        if name in form:
            setattr(item, attr or name, (form.get(name) or "").strip()[:limit])

    text("name")
    if "name" in form and not item.name and mv.row.kind == "orders":
        return "An order needs an item name."
    text("category", limit=80)
    text("status", limit=40)
    text("owner", limit=80)
    if "is_shared" in form:
        item.is_shared = form.get("is_shared") in ("1", "true", "on")
    for name, limit in (("quantity", 60), ("unit", 30), ("vendor", 120), ("catalog_number", 120),
                        ("lot", 120), ("location_note", 200)):
        text(name, limit=limit)
    for name in ("received_on", "expires_on"):
        if name in form:
            setattr(item, name, _date(form.get(name)))
    if "notes" in form:
        item.notes = (form.get("notes") or "").strip()

    attrs = item.attrs_dict
    for field in mv.fields:
        k = field["key"]
        if field["type"] == "source":
            if f"attr_{k}_kind" in form or f"attr_{k}_ref" in form:
                attrs[k] = {"kind": (form.get(f"attr_{k}_kind") or "").strip(),
                            "ref": (form.get(f"attr_{k}_ref") or "").strip()}
        elif f"attr_{k}" in form:
            attrs[k] = (form.get(f"attr_{k}") or "").strip()
    item.attrs = json.dumps(attrs)

    if mv.has("storage") and "rack_id" in form and form_changed(form, "rack_id", "position"):
        return svc.apply_position(session, item, form.get("rack_id"), form.get("position"))
    return None


@bp.route("/<key>/items/save", methods=["POST"])
def save_item(key: str):
    """Create an item, or update one from the dialog (id in the form)."""
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        item_id = request.form.get("id", "").strip()
        if item_id.isdigit():
            item = session.get(InventoryItem, int(item_id))
            if item is None or item.module_id_fk != row.id:
                abort(404)
            if not access.can_edit(item, shared=item.is_shared):
                return _done(key, error=access.reason_denied(item))
        else:
            item = InventoryItem(module_id_fk=row.id, number=svc.next_number(session, row.id),
                                 owner=g.user.username, status=mv.statuses[0] if mv.statuses else "")
            session.add(item)
        error = _item_from_form(session, mv, item, request.form)
        if error and not item.id and "name" in error:
            session.rollback()
            return _done(key, error=error)
        item.updated_at, item.updated_by = datetime.utcnow(), g.user.username
        session.commit()
        label = item.name or f"#{item.number}"
        if error:
            return _done(key, error=f"Saved {label}, but: {error}")
        return _done(key, message=f"Saved {label}.")


@bp.route("/<key>/items/<int:item_id>/update", methods=["POST"])
def update_item(key: str, item_id: int):
    """Inline edit from the sheet; answers JSON."""
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        item = session.get(InventoryItem, item_id)
        if item is None or item.module_id_fk != row.id:
            return jsonify({"ok": False, "error": "That record no longer exists."}), 404
        if not access.can_edit(item, shared=item.is_shared):
            return jsonify({"ok": False, "error": access.reason_denied(item)}), 403
        error = _item_from_form(session, svc.view(row), item, request.form)
        if error:
            session.rollback()
            return jsonify({"ok": False, "error": error}), 409
        item.updated_at, item.updated_by = datetime.utcnow(), g.user.username
        session.commit()
        return jsonify({"ok": True, "position": svc.rack_label(item), "rack_id": item.rack_id_fk or ""})


@bp.route("/<key>/items/<int:item_id>/delete", methods=["POST"])
def delete_item(key: str, item_id: int):
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        item = session.get(InventoryItem, item_id)
        if item is not None and item.module_id_fk == row.id:
            if not access.can_edit(item, shared=item.is_shared):
                return _done(key, error=access.reason_denied(item))
            label = item.name or f"#{item.number}"
            session.delete(item)
            session.commit()
            return _done(key, message=f"Deleted {label}.")
    return _done(key)


@bp.route("/<key>/items/<int:item_id>/duplicate", methods=["POST"])
def duplicate_item(key: str, item_id: int):
    """A copy for the next aliquot or re-order: same details, no position."""
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        item = session.get(InventoryItem, item_id)
        if item is None or item.module_id_fk != row.id:
            abort(404)
        copy = InventoryItem(
            module_id_fk=row.id, number=svc.next_number(session, row.id), name=item.name,
            category=item.category, status=(svc.view(row).statuses or [""])[0], owner=g.user.username,
            is_shared=item.is_shared, quantity=item.quantity, unit=item.unit, vendor=item.vendor,
            catalog_number=item.catalog_number, lot="", attrs=item.attrs, notes=item.notes)
        session.add(copy)
        session.commit()
        return _done(key, message=f"Duplicated {item.name or '#' + str(item.number)} as #{copy.number}.")


@bp.route("/<key>/items/<int:item_id>/place", methods=["POST"])
def place_item(key: str, item_id: int):
    """Move on the box grid; an occupied cell swaps; no rack unplaces."""
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        item = session.get(InventoryItem, item_id)
        if item is None or item.module_id_fk != row.id:
            return jsonify({"ok": False, "error": "That record no longer exists."}), 404
        if not access.can_edit(item, shared=item.is_shared):
            return jsonify({"ok": False, "error": access.reason_denied(item)}), 403
        rack_id = request.form.get("rack_id", "").strip()
        if not rack_id:
            item.rack_id_fk = item.rack_row = item.rack_col = None
            session.commit()
            return jsonify({"ok": True})
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
            if not access.can_edit(holder, shared=holder.is_shared):
                return jsonify({"ok": False, "error": f"That cell holds {holder.name}, which you may not move."}), 403
            holder.rack_id_fk, holder.rack_row, holder.rack_col = item.rack_id_fk, item.rack_row, item.rack_col
        item.rack_id_fk, item.rack_row, item.rack_col = rack.id, r, c
        session.commit()
    return jsonify({"ok": True})


@bp.route("/<key>/items/<int:item_id>/status", methods=["POST"])
def set_status(key: str, item_id: int):
    """Board drag and the sheet's status pill; answers JSON."""
    status = (request.form.get("status") or "").strip()
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        item = session.get(InventoryItem, item_id)
        if item is None or item.module_id_fk != row.id:
            return jsonify({"ok": False, "error": "That record no longer exists."}), 404
        if not access.can_edit(item, shared=item.is_shared):
            return jsonify({"ok": False, "error": access.reason_denied(item)}), 403
        if mv.statuses and status not in mv.statuses:
            return jsonify({"ok": False, "error": f"Unknown status “{status}”."}), 400
        item.status = status
        if mv.has("received") and status == "received" and not item.received_on:
            item.received_on = date.today()
        item.updated_at, item.updated_by = datetime.utcnow(), g.user.username
        session.commit()
    return jsonify({"ok": True})


@bp.route("/<key>/items/<int:item_id>/to-reagents", methods=["POST"])
def order_to_reagents(key: str, item_id: int):
    """A received order becomes a reagent (or antibody) in stock, with its
    vendor, catalogue number and quantity carried over."""
    target_key = request.form.get("target", "")
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        order = session.get(InventoryItem, item_id)
        target = svc.get_module(session, target_key) if target_key else svc.first_of_kind(session, "reagents")
        if order is None or order.module_id_fk != row.id or target is None:
            return _done(key, error="There is no reagents inventory to add it to.")
        tv = svc.view(target)
        stock = InventoryItem(
            module_id_fk=target.id, number=svc.next_number(session, target.id), name=order.name,
            status=tv.statuses[0] if tv.statuses else "", owner=g.user.username,
            is_shared=request.form.get("shared") == "1", quantity=order.quantity, unit=order.unit,
            vendor=order.vendor, catalog_number=order.catalog_number,
            received_on=order.received_on or date.today(),
            notes=f"From order #{order.number}" + (f". {order.notes}" if order.notes else ""))
        session.add(stock)
        attrs = order.attrs_dict
        attrs["stocked_as"] = f"{target.key}:{stock.number}"
        order.attrs = json.dumps(attrs)
        session.commit()
        flash(f"Added {stock.name} to {target.label} as #{stock.number}.", "success")
        return redirect(url_for("inventory.module", key=target.key))


# ---------------------------------------------------------------------------
# Boxes and shelves
# ---------------------------------------------------------------------------


@bp.route("/<key>/racks/save", methods=["POST"])
def save_rack(key: str):
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        rack_id = request.form.get("id", "").strip()
        rack = session.get(InventoryRack, int(rack_id)) if rack_id.isdigit() else None
        if rack is not None and rack.module_id_fk != row.id:
            abort(404)
        if rack is None:
            rack = InventoryRack(module_id_fk=row.id)
            session.add(rack)
        rack.name = (request.form.get("name") or "").strip() or "Box"
        rack.kind = (request.form.get("kind") or "box").strip()[:40]
        rack.rows = max(1, min(26, int(request.form.get("rows") or 9)))
        rack.cols = max(1, min(40, int(request.form.get("cols") or 9)))
        rack.naming = json.dumps(positions.scheme_from_form(request.form))
        session.commit()
        flash(f"Saved {rack.name}.", "success")
    return redirect(url_for("inventory.module", key=key))


@bp.route("/<key>/racks/<int:rack_id>/delete", methods=["POST"])
def delete_rack(key: str, rack_id: int):
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        rack = session.get(InventoryRack, rack_id)
        if rack is not None and rack.module_id_fk == row.id:
            for item in session.scalars(select(InventoryItem).where(InventoryItem.rack_id_fk == rack.id)):
                item.rack_id_fk = item.rack_row = item.rack_col = None
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


@bp.route("/<key>/configure", methods=["GET", "POST"])
def configure(key: str):
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        if request.method == "POST":
            form = request.form
            label = (form.get("label") or "").strip()
            if not label:
                flash("An inventory needs a name.", "error")
                return redirect(url_for("inventory.configure", key=key))
            row.label = label
            row.blurb = (form.get("blurb") or "").strip()
            row.item_noun = (form.get("item_noun") or "item").strip()[:60]
            row.item_noun_plural = (form.get("item_noun_plural") or row.item_noun + "s").strip()[:60]
            if form.get("icon") in ICON_CHOICES:
                row.icon = form["icon"]
            row.enabled = "1" in form.getlist("enabled")
            lines = lambda name: [x.strip() for x in (form.get(name) or "").replace(",", "\n").split("\n") if x.strip()]
            fields = []
            for i in range(int(form.get("field_count") or 0)):
                flabel = (form.get(f"field_{i}_label") or "").strip()
                if not flabel or form.get(f"field_{i}_remove"):
                    continue
                from .organism_service import slugify
                fields.append({
                    "key": form.get(f"field_{i}_key") or slugify(flabel) or f"field_{i}",
                    "label": flabel, "type": form.get(f"field_{i}_type") or "text",
                    "options": [o.strip() for o in (form.get(f"field_{i}_options") or "").split(",") if o.strip()],
                    "icon": form.get(f"field_{i}_icon") or "",
                    "width": int(form.get(f"field_{i}_width") or 130),
                    "in_table": form.get(f"field_{i}_in_table") == "1",
                })
            row.settings = json.dumps(presets.normalise_settings({
                "features": form.getlist("features"),
                "category_label": (form.get("category_label") or "Category").strip(),
                "categories": lines("categories"), "statuses": lines("statuses"), "fields": fields,
            }))
            session.commit()
            flash(f"Saved {row.label}.", "success")
            return redirect(url_for("inventory.module", key=key))
        return render_template("inventory/configure.html", module=svc.view(row), features=presets.FEATURES,
                               field_types=presets.FIELD_TYPES, icons=ICON_CHOICES,
                               item_count=len(list(session.scalars(select(InventoryItem.id).where(InventoryItem.module_id_fk == row.id)))))


@bp.route("/<key>/delete", methods=["POST"])
def delete_module(key: str):
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        if not (access.is_admin() or row.created_by == g.user.username):
            flash("Only an admin, or whoever created it, can delete an inventory.", "error")
            return redirect(url_for("inventory.configure", key=key))
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
