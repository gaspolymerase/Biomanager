"""Routes for fly and worm stocks (vials / plates).

One page per database, in tabs: the vials (a sheet with a rack grid you
can pick by incubator and rack), the schedule (flips, egg collections,
emerging progeny, temperature shifts), genotypes, incubators and racks,
frozen stocks (worms) and settings."""

from __future__ import annotations

import json
import zlib
from datetime import date, datetime, timedelta

from flask import (
    Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for,
)
from sqlalchemy import func, select

from . import access, audit, positions
from . import stock_service as svc
from . import stocks as presets
from .db import SessionLocal
from .formutil import form_changed
from .models import (
    StockFrozen, StockGenotype, StockIncubator, StockModule, StockRack, StockUnit,
)

bp = Blueprint("stocks", __name__, url_prefix="/stocks")

VIEWS = ("units", "schedule", "genotypes", "setup", "frozen", "settings")


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


def _int(raw, default: int = 0) -> int:
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def _module_or_404(session, key: str) -> StockModule:
    module = svc.get_module(session, key)
    if module is None:
        abort(404)
    return module


def _wants_json() -> bool:
    return request.headers.get("X-Autosave") == "1"


def _back(key: str, view: str = "units", message: str = "", error: str = ""):
    if _wants_json():
        if error:
            return jsonify({"ok": False, "error": error}), 409
        return jsonify({"ok": True, "message": message})
    if error:
        flash(error, "error")
    if message:
        flash(message, "success")
    referrer = request.referrer or ""
    if referrer.startswith(request.host_url) and "/stocks/" in referrer:
        return redirect(referrer)
    return redirect(url_for("stocks.module", key=key, view=view))


def can_edit(unit: StockUnit) -> bool:
    """Stocks, backups and maintenance plates are the lab's; crosses,
    experiments and progeny belong to whoever set them up."""
    shared = unit.purpose in ("stock", "backup", "maintenance", "starved")
    return access.can_edit(unit, shared=shared)


# ---------------------------------------------------------------------------
# Creating a database
# ---------------------------------------------------------------------------


@bp.route("/new", methods=["GET", "POST"])
def new_module():
    with SessionLocal() as session:
        if request.method == "POST":
            kind = request.form.get("kind", "fly")
            label = (request.form.get("label") or "").strip()
            if not label:
                flash("Give the database a name.", "error")
                return redirect(url_for("stocks.new_module", kind=kind))
            module = svc.create_module(session, kind, label, created_by=g.user.username)
            session.commit()
            flash(f"Created {module.label}. Add an incubator and a rack to start.", "success")
            return redirect(url_for("stocks.module", key=module.key, view="setup"))
        return render_template("stocks/new.html", presets=presets.PRESETS,
                               kind=request.args.get("kind", "fly"))


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------


def _next_due(mv, unit: StockUnit, today: date) -> dict | None:
    """The one date that matters most for this vial right now."""
    rack = unit.rack
    if unit.shift_on and not unit.shifted_on:
        return {"label": f"Shift to {unit.shift_to or '?'} °C", "on": unit.shift_on}
    if unit.ready_on:
        return {"label": mv.s["ready_label"], "on": unit.ready_on}
    if unit.purpose == presets.CROSS:
        last = unit.last_collected_on or unit.set_up_on
        if last:
            return {"label": mv.s["collect_verb"],
                    "on": last + timedelta(days=mv.interval("collect", svc.unit_temperature(mv, unit)))}
    if unit.score_on and not unit.attrs_dict.get("scored_on"):
        return {"label": "Score", "on": unit.score_on}
    if rack is not None:
        due = svc.next_flip(mv, rack)
        if due:
            return {"label": mv.s["flip_verb"], "on": due}
    return None


def unit_payload(mv, unit: StockUnit) -> dict:
    return {
        "id": unit.id, "_label": mv.code(unit), "_locked": not can_edit(unit),
        "genotype": unit.genotype, "purpose": unit.purpose,
        "female_genotype": unit.female_genotype, "male_genotype": unit.male_genotype,
        "rack_id": unit.rack_id_fk or "", "position": svc.position_label(unit),
        "set_up_on": unit.set_up_on.isoformat() if unit.set_up_on else "",
        "owner": unit.owner, "ready_on": unit.ready_on.isoformat() if unit.ready_on else "",
        "shift_on": unit.shift_on.isoformat() if unit.shift_on else "", "shift_to": unit.shift_to,
        "score_on": unit.score_on.isoformat() if unit.score_on else "",
        "generation": unit.attrs_dict.get("generation", ""),
        "notes": unit.notes, "count": 1,
    }


def grid_payload(mv, racks, units) -> dict:
    tone = {presets.CROSS: "cross", presets.PROGENY: "progeny", "experiment": "experiment",
            "virgins": "virgins", "stock": "stock", "maintenance": "stock", "backup": "backup",
            "starved": "inactive"}
    return {
        "racks": [{"id": r.id, "name": r.name, "rows": r.rows, "cols": r.cols,
                   "group": r.incubator.name if r.incubator else "",
                   "naming": positions.scheme(r.naming),
                   "edit": {"data-record-edit": "rack-dialog", "data-record-payload": json.dumps(rack_payload(mv, r))}}
                  for r in racks],
        "items": [{
            "id": u.id, "label": mv.code(u),
            "sub": (svc.cross_label(u) if u.purpose == presets.CROSS else u.genotype) or mv.purpose_label(u.purpose),
            "badge": mv.purpose_label(u.purpose)[:1] if u.purpose not in ("stock", "maintenance") else "",
            "tone": tone.get(u.purpose, ""), "flag": bool(u.ready_on and u.ready_on <= date.today()),
            "rack": u.rack_id_fk, "row": u.rack_row, "col": u.rack_col,
            "title": " · ".join(filter(None, [mv.code(u), mv.purpose_label(u.purpose), svc.cross_label(u), u.owner])),
            "search": " ".join(filter(None, [mv.code(u), u.genotype, u.female_genotype, u.male_genotype,
                                             u.purpose, u.owner, u.notes])).lower(),
            "edit": {"data-record-edit": "unit-dialog", "data-record-payload": json.dumps(unit_payload(mv, u))},
        } for u in units if u.active],
        "create": {"attrs": {"data-record-edit": "unit-dialog"},
                   "payload": {"owner": g.user.username, "purpose": mv.default_purpose, "count": 1,
                               "set_up_on": date.today().isoformat()},
                   "rack_field": "rack_id", "text_field": "position"},
    }


def rack_payload(mv, rack: StockRack) -> dict:
    return {"id": rack.id, "_label": rack.name, "name": rack.name, "rows": rack.rows, "cols": rack.cols,
            "incubator_id": rack.incubator_id_fk or "", "flip_days": rack.flip_days or "",
            "last_flipped_on": rack.last_flipped_on.isoformat() if rack.last_flipped_on else "",
            "notes": rack.notes,
            **{f"naming_{k}": v for k, v in positions.scheme(rack.naming).items()}}


@bp.route("/<key>")
def module(key: str):
    from .services import current_lab_usernames

    view_name = request.args.get("view", "units")
    if view_name not in VIEWS:
        view_name = "units"
    today = date.today()
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        if view_name == "frozen" and not mv.s.get("frozen"):
            view_name = "units"
        racks = svc.racks_of(session, row.id)
        incubators = svc.incubators_of(session, row.id)
        units = list(session.scalars(select(StockUnit).where(StockUnit.module_id_fk == row.id)
                                     .order_by(StockUnit.active.desc(), StockUnit.number.desc())))
        genotypes = list(session.scalars(select(StockGenotype).where(StockGenotype.module_id_fk == row.id)
                                         .order_by(StockGenotype.genotype)))
        schedule = svc.schedule(session, mv, today, horizon=_int(request.args.get("horizon"), 14))
        me = g.user.username
        rows = []
        for u in units:
            nxt = _next_due(mv, u, today) if u.active else None
            rows.append({"unit": u, "code": mv.code(u), "editable": can_edit(u), "mine": u.owner == me,
                         "position": svc.position_label(u), "temp": svc.unit_temperature(mv, u),
                         "incubator": u.rack.incubator.name if u.rack and u.rack.incubator else "",
                         "next": nxt, "overdue": bool(nxt and nxt["on"] < today),
                         "payload": unit_payload(mv, u)})
        active_counts = {}
        for u in units:
            if u.active:
                active_counts[u.genotype] = active_counts.get(u.genotype, 0) + 1
        rack_rows = []
        for r in racks:
            count = sum(1 for u in units if u.active and u.rack_id_fk == r.id)
            rack_rows.append({"rack": r, "count": count, "interval": svc.flip_interval(mv, r),
                              "temp": svc.rack_temperature(mv, r), "next": svc.next_flip(mv, r),
                              "payload": rack_payload(mv, r)})
        frozen = list(session.scalars(select(StockFrozen).where(StockFrozen.module_id_fk == row.id)
                                      .order_by(StockFrozen.genotype, StockFrozen.frozen_on.desc()))) \
            if mv.s.get("frozen") else []
        context = {
            "module": mv, "view": view_name, "rows": rows, "racks": racks, "incubators": incubators,
            "rack_rows": rack_rows, "genotypes": genotypes, "active_counts": active_counts,
            "grid": grid_payload(mv, racks, units), "schedule": schedule, "frozen": frozen,
            "usernames": current_lab_usernames(session), "today": today,
            "next_number": svc.next_number(session, row.id),
            "overdue": sum(1 for i in schedule if i["overdue"] or i["today"]),
            "counts": {
                "active": sum(1 for u in units if u.active),
                "mine": sum(1 for u in units if u.active and u.owner == me),
                "discarded": sum(1 for u in units if not u.active),
                **{p["key"]: sum(1 for u in units if u.active and u.purpose == p["key"]) for p in mv.purposes},
            },
        }
        # Remembered layout is by column position; a changed purpose list
        # or parent labels mean a fresh start.
        context["col_sig"] = format(zlib.crc32(json.dumps(mv.s["parents"]).encode()), "x")
        return render_template("stocks/module.html", **context)


# ---------------------------------------------------------------------------
# Vials / plates
# ---------------------------------------------------------------------------


def _unit_from_form(session, mv, unit: StockUnit, form, placing: bool = True) -> str | None:
    """Copy the fields the form sent; returns a position problem, if any."""
    user = g.user.username
    for name, limit in (("genotype", 400), ("female_genotype", 400), ("male_genotype", 400),
                        ("owner", 80), ("shift_to", 10)):
        if name in form:
            setattr(unit, name, (form.get(name) or "").strip()[:limit])
    if "purpose" in form:
        purpose = (form.get("purpose") or "").strip()
        if purpose in {p["key"] for p in mv.purposes} or (purpose and purpose == unit.purpose):
            unit.purpose = purpose
        elif not unit.purpose:
            unit.purpose = mv.default_purpose
    for name in ("set_up_on", "ready_on", "shift_on", "score_on"):
        if name in form:
            setattr(unit, name, _date(form.get(name)))
    if "notes" in form:
        unit.notes = (form.get("notes") or "").strip()
    if "generation" in form:
        attrs = unit.attrs_dict
        attrs["generation"] = (form.get("generation") or "").strip()[:40]
        unit.attrs = json.dumps(attrs)
    # A cross written only as its parents is labelled by them.
    if unit.purpose == presets.CROSS and not unit.genotype and (unit.female_genotype or unit.male_genotype):
        unit.genotype = svc.cross_label(unit)
    for text in (unit.genotype or "", unit.female_genotype or "", unit.male_genotype or ""):
        if not text.startswith("F1 of "):
            svc.remember_genotype(session, mv.id, text, user)
    if placing and "rack_id" in form and form_changed(form, "rack_id", "position"):
        return svc.apply_position(session, unit, form.get("rack_id"), form.get("position"))
    return None


@bp.route("/<key>/units/save", methods=["POST"])
def save_unit(key: str):
    """The dialog: update one (id set), or create one or many identical
    vials placed side by side."""
    user = g.user.username
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        unit_id = request.form.get("id", "").strip()
        if unit_id.isdigit():
            unit = session.get(StockUnit, int(unit_id))
            if unit is None or unit.module_id_fk != row.id:
                abort(404)
            if not can_edit(unit):
                return _back(key, error=access.reason_denied(unit))
            problem = _unit_from_form(session, mv, unit, request.form)
            unit.updated_at, unit.updated_by = datetime.utcnow(), user
            session.commit()
            return _back(key, message=f"Saved {mv.code(unit)}." if not problem else "",
                         error=f"Saved {mv.code(unit)}, but: {problem}" if problem else "")

        count = max(1, min(60, _int(request.form.get("count"), 1)))
        rack_raw = (request.form.get("rack_id") or "").strip()
        rack = session.get(StockRack, int(rack_raw)) if rack_raw.isdigit() else None
        if rack is not None and rack.module_id_fk != row.id:
            abort(404)
        cells = []
        problem = None
        if rack is not None:
            start = None
            pos = (request.form.get("position") or "").strip()
            if pos:
                start = positions.parse(pos, rack.naming, rack.rows, rack.cols)
                if start is None:
                    return _back(key, error=f"“{pos}” is not a position in {rack.name}.")
                if start in svc.occupied(session, rack.id):
                    return _back(key, error=f"{rack.name} · {pos} is already taken.")
            cells = svc.free_cells(session, rack, count, start)
            if len(cells) < count:
                problem = f"{rack.name} had room for {len(cells)} of {count}; the rest are unplaced."
        number = svc.next_number(session, row.id)
        created = []
        with audit.batch(session, "create", f"New {mv.units} ×{count}" if count > 1 else f"New {mv.unit}",
                         "stock_units") if count > 1 else _null():
            for i in range(count):
                unit = StockUnit(module_id_fk=row.id, number=number + i, owner=user,
                                 purpose=mv.default_purpose, set_up_on=date.today(), updated_by=user)
                _unit_from_form(session, mv, unit, request.form, placing=False)
                if rack is not None:
                    unit.rack_id_fk = rack.id
                    unit.rack = rack
                    if i < len(cells):
                        unit.rack_row, unit.rack_col = cells[i]
                if unit.purpose == presets.PROGENY and not unit.ready_on and unit.set_up_on:
                    unit.ready_on = unit.set_up_on + timedelta(days=mv.interval("develop", svc.rack_temperature(mv, rack)))
                session.add(unit)
                created.append(unit)
            session.flush()
        session.commit()
        codes = [mv.code(u) for u in created]
        where = f" in {rack.name}" if rack else ""
        label = codes[0] if len(codes) == 1 else f"{codes[0]}–{codes[-1]}"
        return _back(key, message=f"Created {label}{where}.", error=problem or "")


class _null:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


@bp.route("/<key>/units/<int:unit_id>/update", methods=["POST"])
def update_unit(key: str, unit_id: int):
    """Inline edit from the sheet (JSON)."""
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        unit = session.get(StockUnit, unit_id)
        if unit is None or unit.module_id_fk != row.id:
            return jsonify({"ok": False, "error": "That record no longer exists."}), 404
        if not can_edit(unit):
            return jsonify({"ok": False, "error": access.reason_denied(unit)}), 403
        problem = _unit_from_form(session, mv, unit, request.form)
        if problem:
            session.rollback()
            return jsonify({"ok": False, "error": problem}), 409
        unit.updated_at, unit.updated_by = datetime.utcnow(), g.user.username
        session.commit()
        return jsonify({"ok": True, "position": svc.position_label(unit), "rack_id": unit.rack_id_fk or "",
                        "genotype": unit.genotype,
                        "incubator": unit.rack.incubator.name if unit.rack and unit.rack.incubator else ""})


@bp.route("/<key>/units/<int:unit_id>/place", methods=["POST"])
def place_unit(key: str, unit_id: int):
    """Move on the grid; an occupied cell swaps; no rack unplaces."""
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        unit = session.get(StockUnit, unit_id)
        if unit is None or unit.module_id_fk != row.id:
            return jsonify({"ok": False, "error": "That record no longer exists."}), 404
        rack_id = request.form.get("rack_id", "").strip()
        if not rack_id:
            unit.rack_row = unit.rack_col = None
            session.commit()
            return jsonify({"ok": True})
        rack = session.get(StockRack, int(rack_id)) if rack_id.isdigit() else None
        r, c = _int(request.form.get("row")), _int(request.form.get("col"))
        if rack is None or rack.module_id_fk != row.id or not (1 <= r <= rack.rows and 1 <= c <= rack.cols):
            return jsonify({"ok": False, "error": "That position is not in the rack."}), 400
        holder = session.scalar(select(StockUnit).where(
            StockUnit.rack_id_fk == rack.id, StockUnit.rack_row == r, StockUnit.rack_col == c,
            StockUnit.active.is_(True), StockUnit.id != unit.id))
        if holder is not None:
            holder.rack_id_fk, holder.rack_row, holder.rack_col = unit.rack_id_fk, unit.rack_row, unit.rack_col
        unit.rack_id_fk, unit.rack_row, unit.rack_col = rack.id, r, c
        session.commit()
    return jsonify({"ok": True})


@bp.route("/<key>/units/<int:unit_id>/collect", methods=["POST"])
def collect(key: str, unit_id: int):
    """Egg collection: a new progeny vial from this cross."""
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        unit = session.get(StockUnit, unit_id)
        if unit is None or unit.module_id_fk != row.id:
            abort(404)
        if unit.purpose != presets.CROSS or not unit.active:
            return _back(key, error=f"{mv.code(unit)} is not an active cross; set its purpose to "
                                    f"{mv.purpose_label(presets.CROSS)} first.")
        progeny, note = svc.collect_eggs(session, mv, unit, g.user.username)
        session.commit()
        where = f" at {progeny.rack.name} · {svc.position_label(progeny)}" if progeny.rack and progeny.rack_row else ""
        return _back(key, message=f"{mv.s['collect_verb']}: {mv.code(unit)} → new {mv.unit} {mv.code(progeny)}{where}; "
                                  f"{mv.s['ready_label'].lower()} around {progeny.ready_on:%d %b}. {note}".strip())


@bp.route("/<key>/units/<int:unit_id>/duplicate", methods=["POST"])
def duplicate_unit(key: str, unit_id: int):
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        unit = session.get(StockUnit, unit_id)
        if unit is None or unit.module_id_fk != row.id:
            abort(404)
        copy = _copy_unit(session, mv, unit)
        session.commit()
        return _back(key, message=f"Copied {mv.code(unit)} as {mv.code(copy)}.")


def _copy_unit(session, mv, unit: StockUnit) -> StockUnit:
    copy = StockUnit(module_id_fk=unit.module_id_fk, number=svc.next_number(session, unit.module_id_fk),
                     genotype=unit.genotype, purpose=unit.purpose, female_genotype=unit.female_genotype,
                     male_genotype=unit.male_genotype, set_up_on=date.today(), owner=g.user.username,
                     shift_on=unit.shift_on, shift_to=unit.shift_to, score_on=unit.score_on,
                     attrs=json.dumps({k: v for k, v in unit.attrs_dict.items() if k in ("generation",)}),
                     notes=unit.notes, updated_by=g.user.username)
    session.add(copy)
    if unit.rack is not None:
        cells = svc.free_cells(session, unit.rack, 1)
        copy.rack_id_fk = unit.rack_id_fk
        copy.rack = unit.rack
        if cells:
            copy.rack_row, copy.rack_col = cells[0]
    session.flush()
    return copy


def _set_active(unit: StockUnit, active: bool) -> None:
    unit.active = active
    unit.discarded_on = None if active else date.today()
    if not active:
        # A discarded vial frees its cell.
        unit.rack_row = unit.rack_col = None


@bp.route("/<key>/units/<int:unit_id>/<action>", methods=["POST"])
def unit_action(key: str, unit_id: int, action: str):
    """discard · restore · delete · shifted · ready-done · scored."""
    if action not in ("discard", "restore", "delete", "shifted", "ready-done", "scored"):
        abort(404)
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        unit = session.get(StockUnit, unit_id)
        if unit is None or unit.module_id_fk != row.id:
            abort(404)
        code = mv.code(unit)
        if action in ("discard", "restore", "delete") and not can_edit(unit):
            return _back(key, error=access.reason_denied(unit))
        if action == "discard":
            _set_active(unit, False)
            message = f"Discarded {code}."
        elif action == "restore":
            _set_active(unit, True)
            if unit.rack is not None:
                cells = svc.free_cells(session, unit.rack, 1)
                if cells:
                    unit.rack_row, unit.rack_col = cells[0]
            message = f"Restored {code}."
        elif action == "delete":
            for child in session.scalars(select(StockUnit).where(StockUnit.parent_id_fk == unit.id)):
                child.parent_id_fk = None
            session.delete(unit)
            message = f"Deleted {code}."
        elif action == "shifted":
            unit.shifted_on = date.today()
            target = request.form.get("rack_id", "").strip()
            message = f"Shifted {code} to {unit.shift_to or 'the new'} °C."
            if target.isdigit():
                problem = svc.apply_position(session, unit, target, "")
                if problem:
                    message += f" {problem}"
                elif unit.rack:
                    message = f"Shifted {code} to {unit.rack.name} · {svc.position_label(unit)}."
        elif action == "ready-done":
            unit.ready_on = None
            message = f"Done: {code}."
        else:
            attrs = unit.attrs_dict
            attrs["scored_on"] = date.today().isoformat()
            unit.attrs = json.dumps(attrs)
            message = f"Scored {code}."
        unit_is_gone = action == "delete"
        if not unit_is_gone:
            unit.updated_at, unit.updated_by = datetime.utcnow(), g.user.username
        session.commit()
        return _back(key, message=message)


@bp.route("/<key>/units/bulk", methods=["POST"])
def bulk(key: str):
    """Batch actions on ticked vials: set a field, collect eggs, copy,
    discard, restore. Recorded as one batch, so it can be undone."""
    action = request.form.get("action", "")
    ids = [int(i) for i in request.form.getlist("selected_ids") if i.isdigit()]
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        units = [u for u in session.scalars(select(StockUnit).where(
            StockUnit.module_id_fk == row.id, StockUnit.id.in_(ids)).order_by(StockUnit.number))]
        if not units:
            return _back(key, error=f"No {mv.units} selected.")
        editable = [u for u in units if can_edit(u)]
        skipped = len(units) - len(editable)
        done, notes = 0, []
        with audit.batch(session, "mixed" if action in ("collect", "copy") else "update",
                         f"{action} ×{len(units)} {mv.units}", "stock_units"):
            if action == "set":
                field = request.form.get("field", "")
                value = (request.form.get("value") or "").strip()
                if field not in ("purpose", "genotype", "owner", "rack_id", "set_up_on", "shift_on", "shift_to",
                                 "score_on", "notes", "female_genotype", "male_genotype"):
                    return _back(key, error="Pick what to set.")
                for u in editable:
                    if field == "rack_id":
                        if value and u.rack_id_fk != _int(value):
                            u.rack_row = u.rack_col = None  # take the next free cell there
                        problem = svc.apply_position(session, u, value, "")
                        session.flush()  # so the next vial sees this cell as taken
                        if problem:
                            notes.append(f"{mv.code(u)}: {problem}")
                            continue
                    else:
                        _unit_from_form(session, mv, u, {field: value}, placing=False)
                    u.updated_at, u.updated_by = datetime.utcnow(), g.user.username
                    done += 1
                message = f"Set {field.replace('_', ' ')} on {done} {mv.unit if done == 1 else mv.units}."
            elif action == "collect":
                crosses = [u for u in units if u.purpose == presets.CROSS and u.active]
                made = []
                for u in crosses:
                    progeny, note = svc.collect_eggs(session, mv, u, g.user.username)
                    made.append(mv.code(progeny))
                    if note:
                        notes.append(note)
                done = len(made)
                message = (f"{mv.s['collect_verb']} from {done} cross{'es' if done != 1 else ''}: new "
                           f"{mv.units} {', '.join(made)}." if made else f"None of those are crosses.")
                skipped = 0
            elif action == "copy":
                made = [mv.code(_copy_unit(session, mv, u)) for u in units]
                done, skipped = len(made), 0
                message = f"Copied {done}: {', '.join(made)}."
            elif action in ("discard", "restore"):
                for u in editable:
                    _set_active(u, action == "restore")
                    if action == "restore" and u.rack is not None:
                        cells = svc.free_cells(session, u.rack, 1)
                        if cells:
                            u.rack_row, u.rack_col = cells[0]
                    session.flush()
                    done += 1
                message = f"{'Discarded' if action == 'discard' else 'Restored'} {done} {mv.unit if done == 1 else mv.units}."
            else:
                return _back(key, error="Unknown action.")
        session.commit()
    if skipped:
        message += f" {skipped} belong to someone else and were left alone."
    for note in notes[:5]:
        flash(note, "info")
    return _back(key, message=message)


# ---------------------------------------------------------------------------
# Racks and incubators
# ---------------------------------------------------------------------------


@bp.route("/<key>/racks/save", methods=["POST"])
def save_rack(key: str):
    form = request.form
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        rack_id = form.get("id", "").strip()
        rack = session.get(StockRack, int(rack_id)) if rack_id.isdigit() else None
        if rack is not None and rack.module_id_fk != row.id:
            abort(404)
        if rack is None:
            rack = StockRack(module_id_fk=row.id)
            session.add(rack)
        rack.name = (form.get("name") or "").strip() or mv.rack_noun.capitalize()
        rack.rows = max(1, min(26, _int(form.get("rows"), mv.s["rack_rows"])))
        rack.cols = max(1, min(40, _int(form.get("cols"), mv.s["rack_cols"])))
        rack.naming = json.dumps(positions.scheme_from_form(form))
        inc = form.get("incubator_id", "").strip()
        rack.incubator_id_fk = int(inc) if inc.isdigit() and session.get(StockIncubator, int(inc)) else None
        rack.flip_days = _int(form.get("flip_days")) or None
        if "last_flipped_on" in form:
            rack.last_flipped_on = _date(form.get("last_flipped_on"))
        rack.notes = (form.get("notes") or "").strip()
        session.commit()
        return _back(key, view="setup", message=f"Saved {rack.name}.")


@bp.route("/<key>/racks/<int:rack_id>/delete", methods=["POST"])
def delete_rack(key: str, rack_id: int):
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        rack = session.get(StockRack, rack_id)
        if rack is None or rack.module_id_fk != row.id:
            abort(404)
        for u in session.scalars(select(StockUnit).where(StockUnit.rack_id_fk == rack.id)):
            u.rack_id_fk = u.rack_row = u.rack_col = None
        name = rack.name
        session.delete(rack)
        session.commit()
        return _back(key, view="setup", message=f"Deleted {name}; what was in it is unplaced.")


@bp.route("/<key>/racks/<int:rack_id>/flipped", methods=["POST"])
def rack_flipped(key: str, rack_id: int):
    """The whole rack was flipped (or chunked) today, or on a given date."""
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        rack = session.get(StockRack, rack_id)
        if rack is None or rack.module_id_fk != row.id:
            abort(404)
        rack.last_flipped_on = _date(request.form.get("on")) or date.today()
        session.commit()
        return _back(key, view="schedule",
                     message=f"{rack.name}: {mv.s['flip_verb'].lower()} recorded for {rack.last_flipped_on:%d %b}; "
                             f"next on {svc.next_flip(mv, rack):%a %d %b}.")


@bp.route("/<key>/incubators/save", methods=["POST"])
def save_incubator(key: str):
    form = request.form
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        inc_id = form.get("id", "").strip()
        inc = session.get(StockIncubator, int(inc_id)) if inc_id.isdigit() else None
        if inc is not None and inc.module_id_fk != row.id:
            abort(404)
        if inc is None:
            inc = StockIncubator(module_id_fk=row.id)
            session.add(inc)
        inc.name = (form.get("name") or "").strip() or "Incubator"
        inc.temperature = (form.get("temperature") or "").strip()[:10]
        inc.notes = (form.get("notes") or "").strip()
        session.commit()
        return _back(key, view="setup", message=f"Saved {inc.name}.")


@bp.route("/<key>/incubators/<int:inc_id>/delete", methods=["POST"])
def delete_incubator(key: str, inc_id: int):
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        inc = session.get(StockIncubator, inc_id)
        if inc is None or inc.module_id_fk != row.id:
            abort(404)
        for rack in session.scalars(select(StockRack).where(StockRack.incubator_id_fk == inc.id)):
            rack.incubator_id_fk = None
        name = inc.name
        session.delete(inc)
        session.commit()
        return _back(key, view="setup", message=f"Deleted {name}; its racks are kept, with no incubator.")


# ---------------------------------------------------------------------------
# Genotypes
# ---------------------------------------------------------------------------


@bp.route("/<key>/genotypes/save", methods=["POST"])
def save_genotype(key: str):
    """Add or edit a genotype. Renaming one relabels every vial that
    carries it (and crosses that use it as a parent)."""
    form = request.form
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        text = (form.get("genotype") or "").strip()[:400]
        if not text:
            return _back(key, view="genotypes", error="A genotype needs text.")
        gid = form.get("id", "").strip()
        item = session.get(StockGenotype, int(gid)) if gid.isdigit() else None
        if item is not None and item.module_id_fk != row.id:
            abort(404)
        clash = session.scalar(select(StockGenotype).where(
            StockGenotype.module_id_fk == row.id, StockGenotype.genotype == text,
            StockGenotype.id != (item.id if item else 0)))
        if clash is not None:
            return _back(key, view="genotypes", error=f"“{text}” is already in the list.")
        relabelled = 0
        if item is None:
            item = StockGenotype(module_id_fk=row.id, genotype=text, created_by=g.user.username)
            session.add(item)
        elif item.genotype != text:
            old = item.genotype
            for column in (StockUnit.genotype, StockUnit.female_genotype, StockUnit.male_genotype):
                for u in session.scalars(select(StockUnit).where(StockUnit.module_id_fk == row.id, column == old)):
                    setattr(u, column.key, text)
                    relabelled += 1
            # Cross labels ("A × B", "F1 of A × B") that name it as a parent.
            for u in session.scalars(select(StockUnit).where(StockUnit.module_id_fk == row.id,
                                                             StockUnit.genotype.contains(" × "))):
                prefix = "F1 of " if u.genotype.startswith("F1 of ") else ""
                sides = u.genotype[len(prefix):].split(" × ")
                if old in sides:
                    u.genotype = prefix + " × ".join(text if side == old else side for side in sides)
                    relabelled += 1
            item.genotype = text
        for name in ("alias", "source", "stock_number", "notes"):
            if name in form:
                setattr(item, name, (form.get(name) or "").strip())
        session.commit()
        extra = f" Relabelled {relabelled} {'vial field' if relabelled == 1 else 'vial fields'}." if relabelled else ""
        return _back(key, view="genotypes", message=f"Saved {text}.{extra}")


@bp.route("/<key>/genotypes/<int:gid>/delete", methods=["POST"])
def delete_genotype(key: str, gid: int):
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        item = session.get(StockGenotype, gid)
        if item is None or item.module_id_fk != row.id:
            abort(404)
        in_use = session.scalar(select(func.count(StockUnit.id)).where(
            StockUnit.module_id_fk == row.id, StockUnit.active.is_(True), StockUnit.genotype == item.genotype))
        if in_use:
            return _back(key, view="genotypes", error=f"{in_use} active vial(s) still carry {item.genotype}.")
        text = item.genotype
        session.delete(item)
        session.commit()
        return _back(key, view="genotypes", message=f"Removed {text} from the list.")


# ---------------------------------------------------------------------------
# Frozen stocks (worms)
# ---------------------------------------------------------------------------


@bp.route("/<key>/frozen/save", methods=["POST"])
def save_frozen(key: str):
    form = request.form
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        fid = form.get("id", "").strip()
        lot = session.get(StockFrozen, int(fid)) if fid.isdigit() else None
        if lot is not None and lot.module_id_fk != row.id:
            abort(404)
        if lot is None:
            lot = StockFrozen(module_id_fk=row.id, owner=g.user.username)
            session.add(lot)
        lot.genotype = (form.get("genotype") or "").strip()[:400]
        lot.frozen_on = _date(form.get("frozen_on"))
        lot.vials = max(0, _int(form.get("vials")))
        lot.vials_left = max(0, _int(form.get("vials_left"), lot.vials))
        lot.location = (form.get("location") or "").strip()
        lot.thaw_tested_on = _date(form.get("thaw_tested_on"))
        ok = form.get("thaw_ok", "")
        lot.thaw_ok = True if ok == "1" else False if ok == "0" else None
        lot.owner = (form.get("owner") or lot.owner).strip()
        lot.notes = (form.get("notes") or "").strip()
        svc.remember_genotype(session, row.id, lot.genotype, g.user.username)
        session.commit()
        return _back(key, view="frozen", message=f"Saved frozen {lot.genotype}.")


@bp.route("/<key>/frozen/<int:fid>/<action>", methods=["POST"])
def frozen_action(key: str, fid: int, action: str):
    """thaw: one vial out, onto a new plate. delete."""
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        lot = session.get(StockFrozen, fid)
        if lot is None or lot.module_id_fk != row.id or action not in ("thaw", "delete"):
            abort(404)
        if action == "delete":
            session.delete(lot)
            session.commit()
            return _back(key, view="frozen", message="Deleted the frozen lot.")
        if lot.vials_left <= 0:
            return _back(key, view="frozen", error="No vials left in that lot.")
        lot.vials_left -= 1
        plate = StockUnit(module_id_fk=row.id, number=svc.next_number(session, row.id), genotype=lot.genotype,
                          purpose=mv.default_purpose, set_up_on=date.today(), owner=g.user.username,
                          notes=f"Thawed from frozen lot ({lot.frozen_on or 'undated'}).",
                          updated_by=g.user.username)
        session.add(plate)
        session.commit()
        return _back(key, view="frozen",
                     message=f"Thawed one vial of {lot.genotype} onto {mv.code(plate)}; {lot.vials_left} left. "
                             f"Record whether it recovered once you can see.")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@bp.route("/<key>/settings", methods=["POST"])
def save_settings(key: str):
    form = request.form
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        label = (form.get("label") or "").strip()
        if not label:
            return _back(key, view="settings", error="The database needs a name.")
        row.label = label
        row.blurb = (form.get("blurb") or "").strip()
        row.enabled = "1" in form.getlist("enabled")
        s = dict(mv.s)
        for name in ("unit_noun", "unit_noun_plural", "rack_noun", "rack_noun_plural", "room_noun",
                     "room_noun_plural", "code_prefix", "flip_verb", "flip_done", "collect_verb", "ready_label"):
            if form.get(name, "").strip():
                s[name] = form[name].strip()[:40]
        s["parents"] = {"female": (form.get("parent_female") or s["parents"]["female"]).strip(),
                        "male": (form.get("parent_male") or s["parents"]["male"]).strip()}
        purposes = []
        for line in (form.get("purposes") or "").splitlines():
            line = line.strip()
            if not line:
                continue
            from .organism_service import slugify
            label_text = line.split("=", 1)[-1].strip() if "=" in line else line
            key_text = line.split("=", 1)[0].strip() if "=" in line else slugify(line)
            purposes.append({"key": key_text or slugify(label_text), "label": label_text})
        if purposes:
            s["purposes"] = purposes
        temps = []
        for i in range(_int(form.get("temp_count"))):
            t = (form.get(f"temp_{i}") or "").strip()
            if not t or form.get(f"temp_{i}_remove"):
                continue
            temps.append({"temp": t, "flip": _int(form.get(f"temp_{i}_flip"), 14),
                          "develop": _int(form.get(f"temp_{i}_develop"), 10),
                          "collect": _int(form.get(f"temp_{i}_collect"), 2)})
        if temps:
            s["temperatures"] = temps
        if form.get("default_temperature"):
            s["default_temperature"] = form["default_temperature"].strip()
        s["frozen"] = "1" in form.getlist("frozen")
        row.settings = json.dumps(s)
        session.commit()
        return _back(key, view="settings", message=f"Saved {row.label}.")


@bp.route("/<key>/delete", methods=["POST"])
def delete_module(key: str):
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        if not (access.is_admin() or row.created_by == g.user.username):
            flash("Only an admin, or whoever created it, can delete this database.", "error")
            return redirect(url_for("stocks.module", key=key, view="settings"))
        if (request.form.get("confirm") or "").strip() != row.label:
            flash(f"Type the name “{row.label}” to confirm.", "error")
            return redirect(url_for("stocks.module", key=key, view="settings"))
        for model in (StockUnit, StockFrozen, StockGenotype):
            for item in session.scalars(select(model).where(model.module_id_fk == row.id)):
                session.delete(item)
        session.flush()
        for model in (StockRack, StockIncubator):
            for item in session.scalars(select(model).where(model.module_id_fk == row.id)):
                session.delete(item)
        session.flush()
        label = row.label
        session.delete(row)
        session.commit()
        flash(f"Deleted {label} and everything in it.", "success")
    return redirect(url_for("organisms.index"))
