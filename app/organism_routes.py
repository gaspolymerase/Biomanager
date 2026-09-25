"""Routes for the configurable organism modules.

A blueprint rather than more of app.py, because none of this is
species-specific: one set of views serves every module, driven by the
module's capabilities.

Login is enforced for the whole blueprint in `before_request`; app.py's own
`before_request` has already resolved `g.user` by then.
"""
from __future__ import annotations

import json
from datetime import date, datetime

from flask import (
    Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for,
)
from sqlalchemy import func, select

from .db import SessionLocal
from .models import (
    ModuleField,
    OrgCohort,
    OrgCross,
    OrgGenotype,
    OrgHousing,
    OrgLine,
    OrgLocation,
    OrgMeasurement,
    OrgPreservationLot,
    Organism,
    OrganismModule,
)
from . import access
from . import organism_service as svc
from . import inventory as inventory_presets
from . import positions
from .icons import housing_icon
from .organisms import (
    AGE_UNITS,
    FIELD_ENTITIES,
    FIELD_TYPES,
    IDENTITY_MODES,
    SCHEDULE_ANCHORS,
    capability_groups,
)

bp = Blueprint("organisms", __name__, url_prefix="/organisms")


# The sub-views a module can show, in order, each gated on a capability.
# `None` means always available.
# The icon for "animals" and "housing" is filled in per module (see
# _views_for), so flies get a fly and vials, worms a worm and plates.
MODULE_VIEWS = [
    ("animals", "Animals", None, None),
    ("housing", "Housing", None, "housing"),
    ("lines", "Lines", "sitemap", "lines"),
    ("crosses", "Crosses", "heart", "crosses"),
    ("cohorts", "Cohorts", "baby", "cohorts"),
    ("schedule", "Schedule", "calendar-clock", "schedule"),
    ("environment", "Environment", "droplet", "environment"),
    ("preservation", "Cryo", "snowflake", "preservation"),
    ("settings", "Configure", "sliders", None),
]


# Header glyph for a custom field, by what kind of value it holds.
FIELD_ICONS = {
    "text": "type", "textarea": "note", "mono": "dna", "number": "count", "date": "calendar",
    "select": "tag", "checkbox": "check", "user": "user", "line": "sitemap", "url": "link",
}


def field_icon(field) -> str:
    return FIELD_ICONS.get(getattr(field, "field_type", ""), "type")


@bp.app_context_processor
def inject_helpers():
    """Helpers the module templates need. `age_label` renders an age in the
    unit the organism's community uses, which only the module knows."""
    return {"age_label": svc.age_label, "field_icon": field_icon}


@bp.before_request
def require_login():
    if g.get("user") is None:
        return redirect(url_for("login"))
    return None


def _parse_date(raw: str | None) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _int(raw, default=0) -> int:
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def _ref(session, model, module_id: int, raw) -> int | None:
    """Resolve a submitted foreign key, but only within this module.

    Every relation in the engine is module-local, so an id belonging to a
    different module is not a valid reference — it is either a stale form or
    a crafted request, and in both cases the right answer is None rather
     than silently linking two species' records together.
    """
    row_id = _int(raw, 0)
    if not row_id:
        return None
    row = session.get(model, row_id)
    if row is None or getattr(row, "module_id_fk", None) != module_id:
        return None
    return row_id


def _module_or_404(session, key: str) -> OrganismModule:
    module = svc.get_module(session, key)
    if module is None:
        abort(404)
    return module


def _views_for(mv: svc.ModuleView) -> list[dict]:
    out = []
    for key, label, icon, capability in MODULE_VIEWS:
        if capability and capability not in mv.capabilities:
            continue
        # "Animals" is meaningless if the module tracks neither.
        if key == "animals" and not mv.any_of("individuals", "group_counts"):
            continue
        if key == "animals":
            icon = mv.icon
        elif key == "housing":
            icon = housing_icon(mv.housing_noun)
        out.append({"key": key, "label": label, "icon": icon})
    return out


# ---------------------------------------------------------------------------
# Index and builder
# ---------------------------------------------------------------------------


@bp.route("/")
def index():
    """Every database in one place: the built-in pages, the organism
    modules and the lab inventories, each renameable."""
    from . import inventory_service as inventories
    from .models import InventoryItem, MouseRecord, PlasmidRecord, TankRecord

    with SessionLocal() as session:
        modules = svc.list_modules(session, include_disabled=True)
        cards = []
        for module in modules:
            cards.append({
                "module": svc.view(module),
                "census": svc.census(session, module),
                "capabilities": svc.capability_labels(module),
            })
        names = inventories.builtin_labels(session)
        count = lambda model: session.scalar(select(func.count()).select_from(model)) or 0
        builtins = [
            {"key": "colony", "icon": "mouse", "url": url_for("colony", view="mice"), "count": count(MouseRecord), "noun": "mice"},
            {"key": "zebrafish", "icon": "fish", "url": url_for("zebrafish"), "count": count(TankRecord), "noun": "tanks"},
            {"key": "plasmids", "icon": "plasmid", "url": url_for("plasmids"), "count": count(PlasmidRecord), "noun": "plasmids"},
        ]
        for b in builtins:
            b["label"] = names[b["key"]]
            b["default"] = inventories.BUILTIN_DATABASES[b["key"]][0]
        item_counts = dict(session.execute(select(InventoryItem.module_id_fk, func.count())
                                           .group_by(InventoryItem.module_id_fk)).all())
        inventory_cards = [{"module": inventories.view(m), "count": item_counts.get(m.id, 0)}
                           for m in inventories.list_modules(session, include_disabled=True)]
        return render_template("organisms/index.html", cards=cards, builtins=builtins,
                               inventory_cards=inventory_cards)


@bp.route("/builtin/<key>/rename", methods=["POST"])
def rename_builtin(key: str):
    """Rename the mouse colony, zebrafish or plasmid pages. An empty name
    goes back to the default."""
    from . import inventory_service as inventories

    if key not in inventories.BUILTIN_DATABASES:
        abort(404)
    label = (request.form.get("label") or "").strip()[:80]
    with SessionLocal() as session:
        inventories.set_setting(session, f"db_label:{key}", label)
        session.commit()
    flash(f"Renamed to {label or inventories.BUILTIN_DATABASES[key][0]}.", "success")
    return redirect(url_for("organisms.index"))


@bp.route("/new", methods=["GET", "POST"])
def new_module():
    with SessionLocal() as session:
        if request.method == "POST":
            spec = _spec_from_form(request.form)
            if not spec["label"]:
                flash("Give the database a name.", "error")
                return redirect(url_for("organisms.new_module"))
            spec["key"] = svc.unique_key(session, spec["label"])
            module = svc.create_module(session, spec, created_by=g.user.username)
            svc.recompute_due(session, module)
            session.commit()
            flash(f"Created the {module.label} database.", "success")
            return redirect(url_for("organisms.module", key=module.key, view="settings"))

        preset_key = request.args.get("preset", "")
        prefill = svc.preset_spec(preset_key) if preset_key else {}
        return render_template(
            "organisms/new.html",
            presets=svc.available_presets(),
            prefill=prefill,
            preset_key=preset_key,
            capability_groups=capability_groups(),
            identity_modes=IDENTITY_MODES,
            age_units=AGE_UNITS,
            inventory_presets=inventory_presets.PRESETS,
        )


def _spec_from_form(form) -> dict:
    """Build a module spec from the builder form.

    A preset can be used as the base, in which case the form only overrides
    what the user actually changed — that keeps the preset's schedule rules
    and field definitions, which the form does not expose.
    """
    base = svc.preset_spec(form.get("preset_key", "")) or {}
    label = (form.get("label") or "").strip()

    spec = dict(base)
    spec.pop("key", None)
    spec["label"] = label
    spec["label_plural"] = (form.get("label_plural") or label).strip()
    spec["icon"] = (form.get("icon") or base.get("icon") or "circle-dashed").strip()
    spec["blurb"] = (form.get("blurb") or "").strip()
    spec["identity_mode"] = form.get("identity_mode") or base.get("identity_mode") or "hybrid"
    spec["age_unit"] = form.get("age_unit") or base.get("age_unit") or "days"
    spec["capabilities"] = form.getlist("capabilities")

    for noun in ("organism_noun", "organism_noun_plural", "housing_noun",
                 "housing_noun_plural", "container_noun", "line_noun",
                 "line_noun_plural", "cohort_noun", "cohort_noun_plural",
                 "cross_noun"):
        value = (form.get(noun) or "").strip()
        if value:
            spec[noun] = value

    # Keep the preset's rules only for capabilities that survived.
    caps = set(svc.normalize_capabilities(spec["capabilities"])) if spec["capabilities"] else set()
    if "schedule" not in caps:
        spec["schedule_rules"] = []
    return spec


# ---------------------------------------------------------------------------
# Module workbench
# ---------------------------------------------------------------------------


@bp.route("/<key>")
def module(key: str):
    with SessionLocal() as session:
        row = _module_or_404(session, key)
        mv = svc.view(row)
        views = _views_for(mv)
        active = request.args.get("view") or (views[0]["key"] if views else "settings")
        if active not in {v["key"] for v in views}:
            active = views[0]["key"] if views else "settings"

        fields = svc.fields_by_entity(session, row.id)
        ctx = {
            "module": mv,
            "module_row": row,
            "views": views,
            "active_view": active,
            "census": svc.census(session, row),
            "fields": fields,
            "usernames": _usernames(session),
            "field_types": FIELD_TYPES,
            "field_entities": FIELD_ENTITIES,
            "capability_groups": capability_groups(),
            "identity_modes": IDENTITY_MODES,
            "age_units": AGE_UNITS,
            "schedule_anchors": SCHEDULE_ANCHORS,
            "today": date.today().isoformat(),
            "metrics_text": svc.metrics_to_text(svc.measurement_metrics(mv)),
            "housing_icon": housing_icon(mv.housing_noun),
        }

        lines = session.scalars(
            select(OrgLine).where(OrgLine.module_id_fk == row.id)
            .order_by(OrgLine.retired, OrgLine.code)
        ).all()
        ctx["lines"] = lines

        housing = session.scalars(
            select(OrgHousing).where(OrgHousing.module_id_fk == row.id)
            .order_by(OrgHousing.active.desc(), OrgHousing.code)
        ).all()
        ctx["housing_units"] = housing

        if active == "animals":
            ctx["organisms"] = session.scalars(
                select(Organism).where(Organism.module_id_fk == row.id)
                .order_by(Organism.death_on.is_(None).desc(), Organism.id.desc())
            ).all()
            ctx["cohorts"] = session.scalars(
                select(OrgCohort).where(OrgCohort.module_id_fk == row.id)
                .order_by(OrgCohort.code)
            ).all()
            ctx["next_code"] = svc.next_code(session, row, "organism")

        elif active == "housing":
            ctx["locations"] = svc.location_tree(session, row.id)
            ctx["occupancy"] = _occupancy(session, row.id)
            ctx["next_code"] = svc.next_code(session, row, "housing")
            ctx["unit_positions"] = {u.id: housing_position_label(u) for u in housing}
            if mv.has("housing_grid"):
                ctx["housing_racks"] = housing_rack_payload(
                    mv, ctx["locations"], housing, ctx["occupancy"], ctx["next_code"], ctx["today"])

        elif active == "lines":
            ctx["line_counts"] = _line_counts(session, row.id)
            ctx["next_code"] = svc.next_code(session, row, "line")

        elif active == "crosses":
            ctx["crosses"] = session.scalars(
                select(OrgCross).where(OrgCross.module_id_fk == row.id)
                .order_by(OrgCross.collected_on.is_(None).desc(), OrgCross.set_up_on.desc())
            ).all()
            ctx["next_code"] = svc.next_code(session, row, "cross")

        elif active == "cohorts":
            ctx["cohorts"] = session.scalars(
                select(OrgCohort).where(OrgCohort.module_id_fk == row.id)
                .order_by(OrgCohort.birth_on.desc())
            ).all()
            ctx["crosses"] = session.scalars(
                select(OrgCross).where(OrgCross.module_id_fk == row.id).order_by(OrgCross.code)
            ).all()
            ctx["next_code"] = svc.next_code(session, row, "cohort")

        elif active == "schedule":
            svc.recompute_due(session, row)
            session.commit()
            ctx["due"] = svc.due_items(session, row, horizon_days=_int(request.args.get("horizon"), 21))
            ctx["horizon"] = _int(request.args.get("horizon"), 21)

        elif active == "environment":
            ctx["locations"] = svc.location_tree(session, row.id)
            ctx["metrics"] = svc.measurement_metrics(mv)
            ctx["readings"] = session.scalars(
                select(OrgMeasurement)
                .where(OrgMeasurement.module_id_fk == row.id,
                       OrgMeasurement.subject_kind == "location")
                .order_by(OrgMeasurement.recorded_at.desc()).limit(200)
            ).all()

        elif active == "preservation":
            ctx["lots"] = session.scalars(
                select(OrgPreservationLot).where(OrgPreservationLot.module_id_fk == row.id)
                .order_by(OrgPreservationLot.frozen_on.desc())
            ).all()
            ctx["methods"] = mv.settings.get("preservation_methods") or [
                "-80 °C", "liquid nitrogen", "sperm", "embryo"
            ]

        return render_template("organisms/module.html", **ctx)


def _usernames(session) -> list[str]:
    from .models import UserAccount
    return list(session.scalars(
        select(UserAccount.username).where(UserAccount.disabled.is_(False))
        .order_by(UserAccount.username)
    ).all())


def _occupancy(session, module_id: int) -> dict[int, int]:
    rows = session.execute(
        select(Organism.housing_id_fk, func.coalesce(func.sum(Organism.count), 0))
        .where(Organism.module_id_fk == module_id, Organism.death_on.is_(None))
        .group_by(Organism.housing_id_fk)
    ).all()
    return {hid: total for hid, total in rows if hid is not None}


def _line_counts(session, module_id: int) -> dict[int, int]:
    rows = session.execute(
        select(Organism.line_id_fk, func.coalesce(func.sum(Organism.count), 0))
        .where(Organism.module_id_fk == module_id, Organism.death_on.is_(None))
        .group_by(Organism.line_id_fk)
    ).all()
    return {lid: total for lid, total in rows if lid is not None}


# ---------------------------------------------------------------------------
# Entity write handlers
#
# One pair of routes per entity, sharing the attribute reader so a module's
# custom fields are handled identically everywhere.
# ---------------------------------------------------------------------------


def _redirect_back(key: str, view: str):
    return redirect(url_for("organisms.module", key=key, view=view))


@bp.route("/<key>/line/save", methods=["POST"])
def save_line(key: str):
    with SessionLocal() as session:
        module = _module_or_404(session, key)
        form = request.form
        row_id = _int(form.get("id"), 0)
        field_rows = svc.fields_for(session, module.id, "line")

        if row_id:
            row = session.get(OrgLine, row_id)
            if row is None or row.module_id_fk != module.id:
                abort(404)
            if not access.can_edit(row):
                flash(access.reason_denied(row), "error")
                return _redirect_back(key, request.form.get("return_view") or "animals")
        else:
            row = OrgLine(module_id_fk=module.id)
            session.add(row)

        row.code = (form.get("code") or "").strip() or svc.next_code(session, module, "line")
        row.name = (form.get("name") or "").strip()
        row.genotype = (form.get("genotype") or "").strip()
        row.owner = (form.get("owner") or "").strip()
        row.protocol = (form.get("protocol") or "").strip()
        row.source = (form.get("source") or "").strip()
        row.external_ref = (form.get("external_ref") or "").strip()
        row.parent_line_id_fk = _ref(session, OrgLine, module.id, form.get("parent_line_id_fk"))
        row.last_refreshed_on = _parse_date(form.get("last_refreshed_on"))
        row.last_frozen_on = _parse_date(form.get("last_frozen_on"))
        row.retired = bool(form.get("retired"))
        row.notes = (form.get("notes") or "").strip()
        row.attrs = svc.dump(svc.read_attrs(form, field_rows, svc.load_dict(row.attrs)))

        session.flush()
        svc.log_event(session, module, "line", row.id,
                      "update" if row_id else "create", recorded_by=g.user.username)
        svc.recompute_due(session, module)
        session.commit()
        flash(f"Saved {row.code}.", "success")
        return _redirect_back(key, "lines")


@bp.route("/<key>/housing/save", methods=["POST"])
def save_housing(key: str):
    with SessionLocal() as session:
        module = _module_or_404(session, key)
        form = request.form
        row_id = _int(form.get("id"), 0)
        field_rows = svc.fields_for(session, module.id, "housing")

        if row_id:
            row = session.get(OrgHousing, row_id)
            if row is None or row.module_id_fk != module.id:
                abort(404)
            if not access.can_edit(row):
                flash(access.reason_denied(row), "error")
                return _redirect_back(key, request.form.get("return_view") or "animals")
        else:
            row = OrgHousing(module_id_fk=module.id)
            session.add(row)

        row.code = (form.get("code") or "").strip() or svc.next_code(session, module, "housing")
        row.location_id_fk = _ref(session, OrgLocation, module.id, form.get("location_id_fk"))
        if "position" in form:
            error = _apply_position(session, row, form.get("position"))
            if error:
                flash(error, "error")
        else:
            row.row = _int(form.get("row"), 0) or None
            row.col = _int(form.get("col"), 0) or None
        row.purpose = (form.get("purpose") or "").strip()
        row.line_id_fk = _ref(session, OrgLine, module.id, form.get("line_id_fk"))
        row.owner = (form.get("owner") or "").strip()
        row.protocol = (form.get("protocol") or "").strip()
        row.card_id = (form.get("card_id") or "").strip()
        row.established_on = _parse_date(form.get("established_on"))
        row.last_serviced_on = _parse_date(form.get("last_serviced_on"))
        row.active = not form.get("retired")
        row.needs_attention = bool(form.get("needs_attention"))
        row.notes = (form.get("notes") or "").strip()
        row.attrs = svc.dump(svc.read_attrs(form, field_rows, svc.load_dict(row.attrs)))
        row.updated_at = datetime.utcnow()
        row.updated_by = g.user.username

        session.flush()
        svc.log_event(session, module, "housing", row.id,
                      "update" if row_id else "create", recorded_by=g.user.username)
        svc.recompute_due(session, module)
        session.commit()
        flash(f"Saved {row.code}.", "success")
        return _redirect_back(key, "housing")


def location_naming(location) -> dict:
    return positions.scheme(svc.load_dict(location.settings).get("naming") if location else None)


def housing_position_label(unit) -> str:
    loc = unit.location
    if loc is None or not loc.cols:
        return ""
    return positions.label(unit.row, unit.col, location_naming(loc), loc.cols)


def _apply_position(session, unit, raw) -> str | None:
    """Set a vial / plate's position from what was typed ("D7"), read with
    its rack's naming scheme; an error message instead of a guess."""
    raw = (raw or "").strip()
    if not raw:
        unit.row = unit.col = None
        return None
    loc = session.get(OrgLocation, unit.location_id_fk) if unit.location_id_fk else None
    if loc is None or not loc.rows or not loc.cols:
        return f"Pick a rack with rows and columns before giving a position (“{raw}” was not saved)."
    cell = positions.parse(raw, location_naming(loc), loc.rows, loc.cols)
    if cell is None:
        n = location_naming(loc)
        return (f"“{raw}” is not a position in {loc.name} "
                f"({positions.label(1, 1, n, loc.cols)}–{positions.label(loc.rows, loc.cols, n, loc.cols)}).")
    holder = session.scalar(select(OrgHousing).where(
        OrgHousing.location_id_fk == loc.id, OrgHousing.row == cell[0],
        OrgHousing.col == cell[1], OrgHousing.id != (unit.id or 0)))
    if holder is not None:
        return f"{loc.name} · {raw} already holds {holder.code}. Drag on the rack grid to swap."
    unit.row, unit.col = cell
    return None


@bp.route("/<key>/housing/<int:unit_id>/place", methods=["POST"])
def place_housing(key: str, unit_id: int):
    """Move a vial / plate on the rack grid; answers JSON. An occupied cell
    swaps; an empty rack id takes it out of its position (it stays in its
    incubator)."""
    with SessionLocal() as session:
        module = _module_or_404(session, key)
        unit = session.get(OrgHousing, unit_id)
        if unit is None or unit.module_id_fk != module.id:
            return jsonify({"ok": False, "error": "That record no longer exists."}), 404
        if not access.can_edit(unit):
            return jsonify({"ok": False, "error": access.reason_denied(unit)}), 403
        rack_id = _int(request.form.get("rack_id"), 0)
        if not rack_id:
            unit.row = unit.col = None
            session.commit()
            return jsonify({"ok": True})
        rack = session.get(OrgLocation, rack_id)
        row, col = _int(request.form.get("row"), 0), _int(request.form.get("col"), 0)
        if (rack is None or rack.module_id_fk != module.id or not rack.rows or not rack.cols
                or not (1 <= row <= rack.rows and 1 <= col <= rack.cols)):
            return jsonify({"ok": False, "error": "That position is not in the rack."}), 400
        occupant = session.scalar(select(OrgHousing).where(
            OrgHousing.location_id_fk == rack.id, OrgHousing.row == row,
            OrgHousing.col == col, OrgHousing.id != unit.id))
        if occupant is not None:
            if not access.can_edit(occupant):
                return jsonify({"ok": False, "error": f"That cell holds {occupant.code}, which you may not move."}), 403
            occupant.location_id_fk, occupant.row, occupant.col = unit.location_id_fk, unit.row, unit.col
        unit.location_id_fk, unit.row, unit.col = rack.id, row, col
        session.commit()
    return jsonify({"ok": True})


def housing_rack_payload(mv, locations, units, occupancy, next_code, today) -> dict:
    """Racks (locations with rows and columns) and the housing units, for
    the rack grid. Clicking a tile or an empty cell opens the housing
    dialog, the same one the table uses."""
    names = {loc.id: loc.name for loc in locations}
    racks = [loc for loc in locations if loc.rows and loc.cols]
    grid_ids = {loc.id for loc in racks}
    items = []
    for unit in units:
        attrs = unit.attrs_dict
        payload = {
            "id": unit.id, "code": unit.code, "location_id_fk": unit.location_id_fk,
            "position": housing_position_label(unit), "purpose": unit.purpose,
            "line_id_fk": unit.line_id_fk, "owner": unit.owner,
            "protocol": unit.protocol, "card_id": unit.card_id,
            "established_on": unit.established_on.isoformat() if unit.established_on else "",
            "last_serviced_on": unit.last_serviced_on.isoformat() if unit.last_serviced_on else "",
            "retired": not unit.active, "needs_attention": unit.needs_attention,
            "notes": unit.notes, "attrs": attrs,
        }
        in_grid = unit.location_id_fk in grid_ids
        count = occupancy.get(unit.id, 0)
        items.append({
            "id": unit.id, "label": unit.code,
            "sub": (unit.line.code if unit.line else "") or unit.purpose,
            "badge": str(count) if count else "",
            "tone": unit.purpose if unit.active else "inactive",
            "flag": unit.needs_attention,
            "rack": unit.location_id_fk if in_grid else None,
            "row": unit.row if in_grid else None, "col": unit.col if in_grid else None,
            "title": " · ".join(filter(None, [unit.code, unit.line.code if unit.line else "",
                                             unit.purpose, names.get(unit.location_id_fk, ""),
                                             f"{count} held" if count else ""])),
            "search": " ".join(filter(None, [unit.code, unit.purpose, unit.owner, unit.card_id,
                                             unit.line.code if unit.line else "",
                                             unit.line.name if unit.line else ""])).lower(),
            "edit": {"data-org-edit": "housing-dialog", "data-org-payload": json.dumps(payload)},
        })
    return {
        "racks": [{
            "id": loc.id,
            "name": f"{names[loc.parent_id_fk]} › {loc.name}" if loc.parent_id_fk in names else loc.name,
            "rows": loc.rows, "cols": loc.cols, "naming": location_naming(loc),
            "edit": {"data-record-payload": json.dumps({
                "id": loc.id, "_label": loc.name, "name": loc.name, "rows": loc.rows,
                "cols": loc.cols, "kind": loc.kind, "parent_id_fk": loc.parent_id_fk or "",
                **{f"naming_{k}": v for k, v in location_naming(loc).items()}})},
        } for loc in racks],
        "items": items,
        "create": {"attrs": {"data-org-edit": "housing-dialog"},
                   "payload": {"code": next_code, "established_on": today},
                   "rack_field": "location_id_fk", "text_field": "position"},
    }


@bp.route("/<key>/animal/save", methods=["POST"])
def save_animal(key: str):
    with SessionLocal() as session:
        module = _module_or_404(session, key)
        mv = svc.view(module)
        form = request.form
        row_id = _int(form.get("id"), 0)
        field_rows = svc.fields_for(session, module.id, "organism")

        if row_id:
            row = session.get(Organism, row_id)
            if row is None or row.module_id_fk != module.id:
                abort(404)
            if not access.can_edit(row):
                flash(access.reason_denied(row), "error")
                return _redirect_back(key, request.form.get("return_view") or "animals")
        else:
            row = Organism(module_id_fk=module.id)
            session.add(row)

        code = (form.get("code") or "").strip()
        # Individually tracked records need an ID; anonymous groups do not.
        if not code and mv.identity_mode == "individual":
            code = svc.next_code(session, module, "organism")
        row.code = code or None
        row.housing_id_fk = _ref(session, OrgHousing, module.id, form.get("housing_id_fk"))
        row.line_id_fk = _ref(session, OrgLine, module.id, form.get("line_id_fk"))
        row.cohort_id_fk = _ref(session, OrgCohort, module.id, form.get("cohort_id_fk"))
        row.count = max(1, _int(form.get("count"), 1))
        row.sex = (form.get("sex") or "").strip()
        row.status = (form.get("status") or "").strip()
        row.birth_on = _parse_date(form.get("birth_on"))
        row.death_on = _parse_date(form.get("death_on"))
        row.genotype = (form.get("genotype") or "").strip()
        row.owner = (form.get("owner") or "").strip()
        row.protocol = (form.get("protocol") or "").strip()
        row.parent_a_id_fk = _ref(session, Organism, module.id, form.get("parent_a_id_fk"))
        row.parent_b_id_fk = _ref(session, Organism, module.id, form.get("parent_b_id_fk"))
        row.notes = (form.get("notes") or "").strip()
        row.attrs = svc.dump(svc.read_attrs(form, field_rows, svc.load_dict(row.attrs)))
        row.updated_at = datetime.utcnow()
        row.updated_by = g.user.username

        session.flush()
        svc.log_event(session, module, "organism", row.id,
                      "update" if row_id else "create", count=row.count,
                      recorded_by=g.user.username)
        session.commit()
        flash("Saved.", "success")
        return _redirect_back(key, "animals")


@bp.route("/<key>/cross/save", methods=["POST"])
def save_cross(key: str):
    with SessionLocal() as session:
        module = _module_or_404(session, key)
        form = request.form
        row_id = _int(form.get("id"), 0)
        field_rows = svc.fields_for(session, module.id, "cross")

        if row_id:
            row = session.get(OrgCross, row_id)
            if row is None or row.module_id_fk != module.id:
                abort(404)
            if not access.can_edit(row):
                flash(access.reason_denied(row), "error")
                return _redirect_back(key, request.form.get("return_view") or "animals")
        else:
            row = OrgCross(module_id_fk=module.id)
            session.add(row)

        row.code = (form.get("code") or "").strip() or svc.next_code(session, module, "cross")
        row.housing_id_fk = _ref(session, OrgHousing, module.id, form.get("housing_id_fk"))
        row.cross_type = (form.get("cross_type") or "pair").strip()
        row.sire_line_id_fk = _ref(session, OrgLine, module.id, form.get("sire_line_id_fk"))
        row.dam_line_id_fk = _ref(session, OrgLine, module.id, form.get("dam_line_id_fk"))
        row.sire_label = (form.get("sire_label") or "").strip()
        row.dam_label = (form.get("dam_label") or "").strip()
        row.set_up_on = _parse_date(form.get("set_up_on"))
        row.expected_on = _parse_date(form.get("expected_on"))
        row.collected_on = _parse_date(form.get("collected_on"))
        row.owner = (form.get("owner") or "").strip()
        row.notes = (form.get("notes") or "").strip()
        row.attrs = svc.dump(svc.read_attrs(form, field_rows, svc.load_dict(row.attrs)))

        session.flush()
        svc.log_event(session, module, "cross", row.id,
                      "update" if row_id else "create", recorded_by=g.user.username)
        session.commit()
        flash(f"Saved {row.code}.", "success")
        return _redirect_back(key, "crosses")


@bp.route("/<key>/cohort/save", methods=["POST"])
def save_cohort(key: str):
    with SessionLocal() as session:
        module = _module_or_404(session, key)
        form = request.form
        row_id = _int(form.get("id"), 0)
        field_rows = svc.fields_for(session, module.id, "cohort")

        if row_id:
            row = session.get(OrgCohort, row_id)
            if row is None or row.module_id_fk != module.id:
                abort(404)
            if not access.can_edit(row):
                flash(access.reason_denied(row), "error")
                return _redirect_back(key, request.form.get("return_view") or "animals")
        else:
            row = OrgCohort(module_id_fk=module.id)
            session.add(row)

        row.code = (form.get("code") or "").strip() or svc.next_code(session, module, "cohort")
        row.line_id_fk = _ref(session, OrgLine, module.id, form.get("line_id_fk"))
        row.cross_id_fk = _ref(session, OrgCross, module.id, form.get("cross_id_fk"))
        row.birth_on = _parse_date(form.get("birth_on"))
        row.stage = (form.get("stage") or "").strip()
        row.location_id_fk = _ref(session, OrgLocation, module.id, form.get("location_id_fk"))
        row.count_initial = _int(form.get("count_initial"), 0)
        row.count_current = _int(form.get("count_current"), row.count_initial)
        row.owner = (form.get("owner") or "").strip()
        row.notes = (form.get("notes") or "").strip()
        row.attrs = svc.dump(svc.read_attrs(form, field_rows, svc.load_dict(row.attrs)))

        session.flush()
        svc.log_event(session, module, "cohort", row.id,
                      "update" if row_id else "create", count=row.count_current,
                      recorded_by=g.user.username)
        svc.recompute_due(session, module)
        session.commit()
        flash(f"Saved {row.code}.", "success")
        return _redirect_back(key, "cohorts")


@bp.route("/<key>/location/save", methods=["POST"])
def save_location(key: str):
    with SessionLocal() as session:
        module = _module_or_404(session, key)
        form = request.form
        row_id = _int(form.get("id"), 0)
        if row_id:
            row = session.get(OrgLocation, row_id)
            if row is None or row.module_id_fk != module.id:
                abort(404)
            if not access.can_edit(row):
                flash(access.reason_denied(row), "error")
                return _redirect_back(key, request.form.get("return_view") or "animals")
        else:
            row = OrgLocation(module_id_fk=module.id)
            session.add(row)

        row.name = (form.get("name") or "").strip() or "Unnamed"
        row.kind = (form.get("kind") or "rack").strip()
        row.parent_id_fk = _ref(session, OrgLocation, module.id, form.get("parent_id_fk"))
        row.rows = _int(form.get("rows"), 0) or None
        row.cols = _int(form.get("cols"), 0) or None
        row.notes = (form.get("notes") or "").strip()
        if "naming_mode" in form:
            settings = svc.load_dict(row.settings)
            settings["naming"] = positions.scheme_from_form(form)
            row.settings = svc.dump(settings)
        session.commit()
        flash(f"Saved {row.name}.", "success")
        return _redirect_back(key, "housing")


@bp.route("/<key>/reading/save", methods=["POST"])
def save_reading(key: str):
    with SessionLocal() as session:
        module = _module_or_404(session, key)
        mv = svc.view(module)
        form = request.form
        location_id = _ref(session, OrgLocation, module.id, form.get("location_id_fk"))
        if location_id is None:
            flash(f"Pick a {mv.container_noun} to log against.", "error")
            return _redirect_back(key, "environment")

        recorded = 0
        for metric in svc.measurement_metrics(mv):
            raw = (form.get(f"metric_{metric['key']}") or "").strip()
            if raw == "":
                continue
            try:
                value = float(raw)
            except ValueError:
                continue
            session.add(OrgMeasurement(
                module_id_fk=module.id,
                subject_kind="location",
                subject_id=location_id,
                metric=metric["key"],
                value_num=value,
                unit=metric.get("unit", ""),
                recorded_by=g.user.username,
                alarm=bool(form.get(f"alarm_{metric['key']}")),
                notes=(form.get("notes") or "").strip(),
            ))
            recorded += 1
        session.commit()
        flash(f"Logged {recorded} reading{'' if recorded == 1 else 's'}.", "success")
        return _redirect_back(key, "environment")


@bp.route("/<key>/lot/save", methods=["POST"])
def save_lot(key: str):
    with SessionLocal() as session:
        module = _module_or_404(session, key)
        form = request.form
        row_id = _int(form.get("id"), 0)
        if row_id:
            row = session.get(OrgPreservationLot, row_id)
            if row is None or row.module_id_fk != module.id:
                abort(404)
            if not access.can_edit(row):
                flash(access.reason_denied(row), "error")
                return _redirect_back(key, request.form.get("return_view") or "animals")
        else:
            row = OrgPreservationLot(module_id_fk=module.id)
            session.add(row)

        row.line_id_fk = _ref(session, OrgLine, module.id, form.get("line_id_fk"))
        row.code = (form.get("code") or "").strip()
        row.method = (form.get("method") or "").strip()
        row.frozen_on = _parse_date(form.get("frozen_on"))
        row.frozen_by = (form.get("frozen_by") or g.user.username).strip()
        row.vial_count = _int(form.get("vial_count"), 0)
        row.vials_remaining = _int(form.get("vials_remaining"), row.vial_count)
        row.storage_text = (form.get("storage_text") or "").strip()
        row.position = (form.get("position") or "").strip()
        row.recovery_tested_on = _parse_date(form.get("recovery_tested_on"))
        recovery = form.get("recovery_ok")
        row.recovery_ok = None if recovery in (None, "") else recovery == "yes"
        row.notes = (form.get("notes") or "").strip()

        # Freezing a line resets its re-freeze clock.
        if row.line_id_fk and row.frozen_on:
            line = session.get(OrgLine, row.line_id_fk)
            if line is not None and (line.last_frozen_on is None or row.frozen_on > line.last_frozen_on):
                line.last_frozen_on = row.frozen_on

        session.flush()
        svc.log_event(session, module, "line", row.line_id_fk or 0, "freeze",
                      occurred_on=row.frozen_on, count=row.vial_count,
                      recorded_by=g.user.username)
        svc.recompute_due(session, module)
        session.commit()
        flash("Saved frozen lot.", "success")
        return _redirect_back(key, "preservation")


@bp.route("/<key>/genotype/save", methods=["POST"])
def save_genotype(key: str):
    with SessionLocal() as session:
        module = _module_or_404(session, key)
        form = request.form
        session.add(OrgGenotype(
            module_id_fk=module.id,
            subject_kind=(form.get("subject_kind") or "organism").strip(),
            subject_id=_int(form.get("subject_id"), 0),
            assay=(form.get("assay") or "").strip(),
            result=(form.get("result") or "").strip(),
            zygosity=(form.get("zygosity") or "").strip(),
            called_on=_parse_date(form.get("called_on")) or date.today(),
            called_by=g.user.username,
            notes=(form.get("notes") or "").strip(),
        ))
        session.commit()
        flash("Recorded genotype.", "success")
        return _redirect_back(key, request.form.get("return_view") or "animals")


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------


@bp.route("/<key>/due/<int:due_id>/done", methods=["POST"])
def complete_due(key: str, due_id: int):
    with SessionLocal() as session:
        module = _module_or_404(session, key)
        row = svc.complete_due(session, module, due_id, g.user.username)
        session.commit()
        flash("Marked done." if row else "Already done.", "success" if row else "info")
        return _redirect_back(key, "schedule")


# ---------------------------------------------------------------------------
# Deleting
# ---------------------------------------------------------------------------


DELETABLE = {
    "line": OrgLine, "housing": OrgHousing, "animal": Organism,
    "cross": OrgCross, "cohort": OrgCohort, "location": OrgLocation,
    "lot": OrgPreservationLot,
}
DELETE_RETURN = {
    "line": "lines", "housing": "housing", "animal": "animals",
    "cross": "crosses", "cohort": "cohorts", "location": "housing",
    "lot": "preservation",
}


@bp.route("/<key>/<entity>/<int:row_id>/delete", methods=["POST"])
def delete_row(key: str, entity: str, row_id: int):
    model = DELETABLE.get(entity)
    if model is None:
        abort(404)
    with SessionLocal() as session:
        module = _module_or_404(session, key)
        row = session.get(model, row_id)
        if row is None or row.module_id_fk != module.id:
            abort(404)
        if not access.can_edit(row):
            flash(access.reason_denied(row), "error")
            return _redirect_back(key, DELETE_RETURN.get(entity, "animals"))
        label = getattr(row, "code", None) or getattr(row, "name", None) or f"#{row_id}"
        if entity == "location":
            # Whatever sat in it stays, just unplaced; children move up a level.
            for unit in session.scalars(select(OrgHousing).where(OrgHousing.location_id_fk == row.id)):
                unit.location_id_fk, unit.row, unit.col = row.parent_id_fk, None, None
            for child in session.scalars(select(OrgLocation).where(OrgLocation.parent_id_fk == row.id)):
                child.parent_id_fk = row.parent_id_fk
        session.delete(row)
        svc.log_event(session, module, entity, row_id, "delete",
                      recorded_by=g.user.username, notes=f"Deleted {label}")
        session.commit()
        flash(f"Deleted {label}.", "success")
        return _redirect_back(key, DELETE_RETURN.get(entity, "animals"))


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@bp.route("/<key>/configure", methods=["POST"])
def configure(key: str):
    with SessionLocal() as session:
        module = _module_or_404(session, key)
        if not (access.is_admin() or access.username() == (module.created_by or "")
                or (module.created_by or "") in ("", "system")):
            flash("Only an admin or whoever created this database can reconfigure it.", "error")
            return _redirect_back(key, "settings")
        form = request.form

        module.label = (form.get("label") or module.label).strip()
        module.label_plural = (form.get("label_plural") or module.label).strip()
        module.icon = (form.get("icon") or module.icon).strip()
        module.blurb = (form.get("blurb") or "").strip()
        module.identity_mode = form.get("identity_mode") or module.identity_mode
        module.age_unit = form.get("age_unit") or module.age_unit
        for noun in ("organism_noun", "organism_noun_plural", "housing_noun",
                     "housing_noun_plural", "container_noun", "line_noun",
                     "line_noun_plural", "cohort_noun", "cohort_noun_plural",
                     "cross_noun"):
            value = (form.get(noun) or "").strip()
            if value:
                setattr(module, noun, value)

        capabilities = svc.normalize_capabilities(form.getlist("capabilities"))
        if module.identity_mode == "individual":
            capabilities = [c for c in capabilities if c != "group_counts"] + ["individuals"]
        elif module.identity_mode == "group":
            capabilities = [c for c in capabilities if c != "individuals"] + ["group_counts"]
        module.capabilities = svc.dump(svc.normalize_capabilities(capabilities))

        for name, key_name in (("housing_purposes", "housing_purposes"),
                               ("statuses", "statuses"),
                               ("sexes", "sexes")):
            raw = form.get(name)
            if raw is not None:
                values = [v.strip() for v in raw.split(",") if v.strip()]
                setattr(module, key_name, svc.dump(values))

        raw_metrics = form.get("environment_metrics")
        if raw_metrics is not None:
            settings = svc.load_dict(module.settings)
            settings["environment_metrics"] = svc.metrics_from_text(raw_metrics)
            module.settings = svc.dump(settings)

        module.enabled = not form.get("disabled")
        session.commit()
        flash("Configuration saved.", "success")
        return _redirect_back(key, "settings")


@bp.route("/<key>/field/add", methods=["POST"])
def add_field(key: str):
    with SessionLocal() as session:
        module = _module_or_404(session, key)
        form = request.form
        options = [v.strip() for v in (form.get("options") or "").split(",") if v.strip()]
        row = svc.add_field(session, module, {
            "entity": form.get("entity") or "organism",
            "key": form.get("key") or form.get("label"),
            "label": form.get("label"),
            "field_type": form.get("field_type"),
            "options": options,
            "default_value": form.get("default_value"),
            "help_text": form.get("help_text"),
            "required": bool(form.get("required")),
            "show_in_table": bool(form.get("show_in_table")),
        })
        session.commit()
        flash(f"Added field {row.label}." if row else "Could not add that field.",
              "success" if row else "error")
        return _redirect_back(key, "settings")


@bp.route("/<key>/field/<int:field_id>/delete", methods=["POST"])
def delete_field(key: str, field_id: int):
    with SessionLocal() as session:
        module = _module_or_404(session, key)
        row = session.get(ModuleField, field_id)
        if row is None or row.module_id_fk != module.id:
            abort(404)
        label = row.label
        session.delete(row)
        session.commit()
        flash(f"Removed field {label}. Stored values are kept.", "success")
        return _redirect_back(key, "settings")


@bp.route("/<key>/rule/save", methods=["POST"])
def save_rule(key: str):
    with SessionLocal() as session:
        module = _module_or_404(session, key)
        form = request.form
        rules = svc.load_list(module.schedule_rules)
        rule_key = svc.slugify(form.get("key") or form.get("label") or "")
        if not rule_key:
            flash("Give the rule a name.", "error")
            return _redirect_back(key, "settings")

        rule = {
            "key": rule_key,
            "label": (form.get("label") or rule_key).strip(),
            "applies_to": form.get("applies_to") or "housing",
            "anchor": form.get("anchor") or "last_serviced_on",
            "offset_days": _int(form.get("offset_days"), 7),
            "icon": (form.get("icon") or "calendar-clock").strip(),
            "recurring": bool(form.get("recurring")),
            "temp_offsets": {},
        }
        # "18:28, 25:14" -> {"18": 28, "25": 14}
        for pair in (form.get("temp_offsets") or "").split(","):
            if ":" not in pair:
                continue
            temp, days = pair.split(":", 1)
            if temp.strip() and days.strip().isdigit():
                rule["temp_offsets"][temp.strip()] = int(days.strip())

        rules = [r for r in rules if r.get("key") != rule_key] + [rule]
        module.schedule_rules = svc.dump(rules)
        session.flush()
        svc.recompute_due(session, module)
        session.commit()
        flash(f"Saved rule {rule['label']}.", "success")
        return _redirect_back(key, "settings")


@bp.route("/<key>/rule/<rule_key>/delete", methods=["POST"])
def delete_rule(key: str, rule_key: str):
    with SessionLocal() as session:
        module = _module_or_404(session, key)
        rules = [r for r in svc.load_list(module.schedule_rules) if r.get("key") != rule_key]
        module.schedule_rules = svc.dump(rules)
        session.flush()
        svc.recompute_due(session, module)
        session.commit()
        flash("Removed rule.", "success")
        return _redirect_back(key, "settings")


@bp.route("/<key>/delete", methods=["POST"])
def delete_module(key: str):
    if getattr(g.user, "role", "") != "admin":
        abort(403)
    with SessionLocal() as session:
        module = _module_or_404(session, key)
        if (request.form.get("confirm") or "").strip() != module.label:
            flash("Type the database name exactly to confirm deletion.", "error")
            return _redirect_back(key, "settings")
        label = module.label
        # Child rows are removed explicitly: the soft subject_kind/subject_id
        # references in the log tables have no FK to cascade from.
        for model in (Organism, OrgHousing, OrgCohort, OrgCross, OrgLine,
                      OrgLocation, OrgPreservationLot):
            session.query(model).filter(model.module_id_fk == module.id).delete(
                synchronize_session=False)
        for table in ("organism_events", "organism_due", "organism_measurements",
                      "organism_genotypes", "organism_module_fields"):
            session.execute(
                __import__("sqlalchemy").text(
                    f"DELETE FROM {table} WHERE module_id_fk = :mid"),
                {"mid": module.id},
            )
        session.delete(module)
        session.commit()
        flash(f"Deleted the {label} database.", "success")
        return redirect(url_for("organisms.index"))
