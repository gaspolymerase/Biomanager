from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Flask, Response, flash, g, get_flashed_messages, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from markupsafe import Markup, escape
from werkzeug.datastructures import ImmutableMultiDict
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload
from werkzeug.security import check_password_hash, generate_password_hash

from .db import SessionLocal
from . import access, positions
from .formutil import form_changed
# Importing this registers the SQLAlchemy flush listener that writes
# audit_log rows for every tracked change; nothing here calls into it.
from . import audit  # noqa: F401
from . import undo as undo_service
from .models import (
    COLONY_VIEWS,
    CageRecord,
    CalendarEvent,
    CalendarSubscription,
    ClutchRecord,
    FishLine,
    FishRack,
    FishRecord,
    FishSacLog,
    GoogleCalendarLink,
    TANK_PURPOSE_OPTIONS,
    FISH_SEX_OPTIONS,
    FISH_STATUS_OPTIONS,
    TankRecord,
    WaterLog,
    WaterSystem,
    ChemicalReference,
    DropdownOption,
    Experiment,
    ExperimentMouse,
    LitterRecord,
    InventoryItem,
    InventoryModule,
    MouseRack,
    MouseWeight,
    MOUSE_STATUS_OPTIONS,
    MouseRecord,
    AuditEntry,
    BatchRecord,
    NotebookEntry,
    NotebookPage,
    NotebookTab,
    NotebookTemplate,
    PlasmidRecord,
    ORDER_STATUS_OPTIONS,
    Order,
    SAMPLE_TYPE_OPTIONS,
    StrainRecord,
    TASK_STATUS_OPTIONS,
    AnimalRecord,
    NotificationRecord,
    SampleRecord,
    TaskItem,
    UserAccount,
)
from .services import (
    add_notification,
    breeder_mice,
    derive_auto_calendar_items,
    fetch_ics_subscription,
    fetch_google_calendar_items,
    google_client_config,
    google_oauth_configured,
    GOOGLE_OAUTH_SCOPES,
    breeder_summary,
    cage_derived_dates,
    cage_is_active,
    calculate_reagent_requirements,
    current_lab_usernames,
    mouse_is_active,
    apply_status_rules,
    END_STATUSES,
    mouse_racks,
    normalize_status,
    sample_source_label,
    sample_sources,
    dropdown_options_map,
    dropdown_records_map,
    export_mouse_rows,
    generate_litter_id,
    get_or_create_cage,
    get_or_create_litter,
    init_database,
    mouse_display_row,
    next_cage_id,
    next_litter_id,
    next_mouse_id,
    reserve_mouse_ids,
    parse_date,
    recent_notifications,
    save_uploaded_file,
    save_uploaded_image,
    sync_mouse_transgenes,
    transgene_values_from_form,
)


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
init_database()

# Configurable organism modules (flies, worms, and anything a lab adds) live
# in their own blueprint — none of it is species-specific, so it does not
# belong in this file. See app/organisms.py for the capability vocabulary.
from .organism_routes import bp as organism_bp  # noqa: E402
from .inventory_routes import bp as inventory_bp  # noqa: E402
from .stock_routes import bp as stocks_bp  # noqa: E402
from .labels import bp as labels_bp  # noqa: E402

app.register_blueprint(organism_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(stocks_bp)
app.register_blueprint(labels_bp)


# When running as a frozen .app/.exe, uploads live in the user's data folder
# (outside the read-only bundle). Flask's default /static/ handler only sees
# files inside app/static/, so we add an explicit route that resolves
# /static/uploads/<name> against the writable uploads dir. In dev, Flask's
# static handler matches first so this is a no-op.
from .paths import is_frozen, uploads_dir as _uploads_dir  # noqa: E402

if is_frozen():
    @app.route("/static/uploads/<path:filename>")
    def _serve_uploads(filename):
        return send_from_directory(_uploads_dir(), filename)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        if g.user.role != "admin":
            flash("Admin access required.", "error")
            return redirect(url_for("colony"))
        return view(*args, **kwargs)

    return wrapped_view


def autosave_response(default_view: str):
    if request.headers.get("X-Autosave") == "1":
        # A background save has no page to show a flash on, so errors are
        # returned to the sheet instead of surfacing on the next page load.
        messages = get_flashed_messages(with_categories=True)
        errors = [text for category, text in messages if category == "error"]
        for category, text in messages:
            if category != "error":
                flash(text, category)
        if errors:
            return jsonify({"ok": False, "error": " ".join(errors)}), 409
        return jsonify({"ok": True})
    # A regular form post (a dialog or a detail page) goes back where it
    # came from — the fish line page, or the colony with its scope intact —
    # but only to this site.
    referrer = request.referrer or ""
    if referrer.startswith(request.host_url):
        return redirect(referrer)
    return redirect(url_for("colony", view=default_view))


def log_delete(db_session, table_name: str, record_id: int, record_label: str = "", details: str = "") -> None:
    """Insert an AuditEntry capturing a deletion. The caller is responsible
    for the db_session commit (we just add the entry to the same transaction
    as the delete itself).

    Tables in audit.TRACKED_TABLES are skipped: the flush listener already
    records their deletes, with the full snapshot undo needs, and a second
    bare entry only doubled every delete in the audit log."""
    from .audit import TRACKED_TABLES

    if g.user is None or table_name in TRACKED_TABLES:
        return
    db_session.add(AuditEntry(
        table_name=table_name,
        record_id=record_id,
        record_label=record_label or str(record_id),
        action="delete",
        changed_by=g.user.username,
        details=details,
    ))


def stamp_updated(record, fields_changed: int = 1) -> None:
    """Mark a record as edited by the current user. Skips silently if no
    user is in the request context (e.g. management commands)."""
    if g.user is None or not fields_changed:
        return
    record.updated_at = datetime.utcnow()
    record.updated_by = g.user.username


@app.before_request
def load_current_user():
    user_id = session.get("user_id")
    g.user = None
    if user_id is None:
        return
    with SessionLocal() as db_session:
        user = db_session.get(UserAccount, user_id)
        if user is None or getattr(user, "disabled", False):
            session.clear()
            g.user = None
            return
        g.user = user


@app.errorhandler(IntegrityError)
def handle_integrity_error(error: IntegrityError):
    """A duplicate ID (or similar) is a message for the person, not a 500.

    Routes open their session in a `with` block, so by the time this runs
    the failed transaction has already been rolled back and closed.
    """
    detail = str(getattr(error, "orig", error))
    # "UNIQUE constraint failed: organism_lines.module_id_fk, organism_lines.code":
    # the last column is the one the person typed (the others scope it).
    match = re.search(r"UNIQUE constraint failed: ([\w.]+(?:,\s*[\w.]+)*)", detail)
    if match:
        column = match.group(1).split(",")[-1].strip().split(".")[-1]
        field = column.replace("_id", " ID").replace("_", " ")
        message = f"That {field} is already used. Choose another."
    else:
        message = "That change conflicts with an existing record, so it was not saved."
    app.logger.info("integrity error on %s: %s", request.path, detail)
    if request.headers.get("X-Autosave") == "1":
        return jsonify({"ok": False, "error": message}), 409
    flash(message, "error")
    referrer = request.referrer or ""
    return redirect(referrer if referrer.startswith(request.host_url) else url_for("home_dashboard"))


@app.context_processor
def inject_icon():
    """`{{ icon('mouse') }}` renders one symbol from the sprite.

    Icons live in a single static/icons.svg sprite referenced with <use>,
    so they inherit currentColor, need no JavaScript, cost one cached
    request, and work offline in the packaged app.
    """
    from markupsafe import Markup

    from .icons import resolve

    def icon(name: str, extra: str = "") -> Markup:
        classes = ("icon " + extra).strip()
        return Markup(
            f'<svg class="{classes}" aria-hidden="true">'
            f'<use href="/static/icons.svg#{resolve(name)}"></use></svg>'
        )

    return {"icon": icon}


@app.context_processor
def inject_user():
    return {"current_user": g.get("user")}


# ---------------------------------------------------------------------------
# Navigation model
#
# The rail, the "+" quick-launch menu and the workspace tab strip all need the
# same list of destinations (label + lucide icon + URL), so it is defined once
# here rather than repeated in base.html. `tab_icon_rules` is handed to
# tab-bar.js so a restored tab can pick the right glyph from its URL alone.
# ---------------------------------------------------------------------------

NAV_SECTIONS: list[dict] = [
    {
        "label": "Workspace",
        "links": [
            {"key": "home", "label": "Home", "icon": "grid",
             "endpoint": "home_dashboard", "match": ("home_dashboard", "index")},
            {"key": "calendar", "label": "Calendar", "icon": "calendar",
             "endpoint": "calendar"},
            {"key": "notebook", "label": "Notebook", "icon": "notebook",
             "endpoint": "notebook", "match": ("notebook", "notebook_templates")},
        ],
    },
    {
        "label": "Databases",
        "links": [
            {"key": "colony", "label": "Mouse colony", "short": "Mouse", "icon": "mouse",
             "endpoint": "colony", "args": {"view": "mice"},
             "match": ("colony", "experiment_detail")},
            {"key": "zebrafish", "label": "Zebrafish", "short": "Fish", "icon": "fish",
             "endpoint": "zebrafish", "match": ("zebrafish", "zebrafish_line_detail")},
            {"key": "plasmids", "label": "Plasmids", "icon": "plasmid",
             "endpoint": "plasmids", "match": ("plasmids", "plasmid_detail")},
            {"key": "new-db", "label": "Add database", "icon": "plus",
             "endpoint": "organisms.new_module", "match": ("organisms.new_module",)},
        ],
    },
]

NAV_FOOTER: list[dict] = [
    {"key": "utilities", "label": "Utilities", "icon": "flask", "endpoint": "utilities"},
    {"key": "admin-colony", "label": "Colony overview", "short": "Overview",
     "icon": "list", "endpoint": "admin_colony_overview", "admin_only": True},
    {"key": "batches", "label": "Batches", "icon": "layers", "endpoint": "batches_view"},
    {"key": "audit", "label": "Audit log", "icon": "history", "endpoint": "audit_log_view",
     "admin_only": True},
    {"key": "settings", "label": "Settings", "icon": "settings", "endpoint": "settings",
     "match": ("settings", "admin_users")},
]

# Colony sub-views: label, icon and one-line description for the segmented
# tab row on the colony page. Keyed by the view keys in models.COLONY_VIEWS.
COLONY_VIEW_META: dict[str, dict[str, str]] = {
    "mice":        {"label": "Mice", "icon": "mouse",
                    "blurb": "Every mouse record, editable in place"},
    "cages":       {"label": "Cages", "icon": "cage",
                    "blurb": "Mice grouped by cage, with breeding actions"},
    "litters":     {"label": "Litters", "icon": "baby",
                    "blurb": "Cohorts and the dates derived from their DOB"},
    "breeders":    {"label": "Breeders", "icon": "heart",
                    "blurb": "Breeding cages and their productivity"},
    "experiments": {"label": "Experiments", "icon": "flask",
                    "blurb": "Cohorts assembled for a specific experiment"},
    "strains":     {"label": "Strains", "icon": "sitemap",
                    "blurb": "Strain and allele reference list"},
    "settings":    {"label": "Presets", "icon": "sliders",
                    "blurb": "Saved dropdown values for the colony columns"},
}


# URL prefix -> lucide icon, longest prefix wins. Used for workspace tabs.
TAB_ICON_RULES: list[tuple[str, str]] = [
    ("/", "home"),
    ("/home", "home"),
    ("/calendar", "calendar"),
    ("/notebook", "notebook"),
    ("/colony", "mouse"),
    ("/colony/experiments", "flask"),
    ("/zebrafish", "fish"),
    ("/plasmids", "plasmid"),
    ("/samples", "vial"),
    ("/orders", "cart"),
    ("/utilities", "calculator"),
    ("/audit", "history"),
    ("/settings", "settings"),
    ("/admin/users", "users"),
    ("/organisms", "database"),
]


def _resolve_nav_item(item: dict, active_endpoint: str) -> dict | None:
    """Turn a NAV_SECTIONS entry into something the template can render, or
    None when the current user may not see it."""
    if item.get("admin_only") and getattr(g.get("user"), "role", None) != "admin":
        return None

    resolved = {
        "key": item["key"],
        "label": item["label"],
        "short": item.get("short", item["label"]),
        "icon": item["icon"],
        "soon": item.get("soon"),
        "url": None,
        "active": False,
    }
    endpoint = item.get("endpoint")
    if endpoint:
        resolved["url"] = url_for(endpoint, **item.get("args", {}))
        resolved["active"] = active_endpoint in item.get("match", (endpoint,))
    return resolved


def builtin_labels() -> dict[str, str]:
    """Names of the built-in databases (the lab may have renamed them)."""
    from . import inventory_service as inventories
    try:
        with SessionLocal() as db_session:
            return inventories.builtin_labels(db_session)
    except Exception:
        return {key: default for key, (default, _short) in inventories.BUILTIN_DATABASES.items()}


def _inventory_module_links() -> list[dict]:
    """Rail entries for the lab inventories (samples, orders, reagents…)."""
    from . import inventory_service as inventories
    from .icons import resolve as resolve_icon

    current_key = request.view_args.get("key") if request.view_args else None
    on_inventory = (request.endpoint or "").startswith("inventory.")
    links = []
    try:
        with SessionLocal() as db_session:
            for module in inventories.list_modules(db_session):
                links.append({
                    "key": f"inventory:{module.key}", "label": module.label, "short": module.label,
                    "icon": resolve_icon(module.icon), "soon": None,
                    "url": url_for("inventory.module", key=module.key),
                    "active": on_inventory and current_key == module.key,
                })
    except Exception:
        return []
    return links


def _stock_module_links() -> list[dict]:
    """Rail entries for the fly and worm vial/plate databases."""
    from . import stock_service as stocks
    from .icons import resolve as resolve_icon

    current_key = request.view_args.get("key") if request.view_args else None
    on_stocks = (request.endpoint or "").startswith("stocks.")
    links = []
    try:
        with SessionLocal() as db_session:
            for module in stocks.list_modules(db_session):
                links.append({
                    "key": f"stock:{module.key}", "label": module.label, "short": module.label,
                    "icon": resolve_icon(module.icon), "soon": None,
                    "url": url_for("stocks.module", key=module.key),
                    "active": on_stocks and current_key == module.key,
                })
    except Exception:
        return []
    return links


def _organism_module_links() -> list[dict]:
    """Rail entries for the configurable organism modules.

    These are rows in the database rather than entries in NAV_SECTIONS, so a
    lab that adds a species sees it in the sidebar immediately.
    """
    from . import organism_service as organisms
    from .icons import resolve as resolve_icon

    current_key = request.view_args.get("key") if request.view_args else None
    on_organisms = (request.endpoint or "").startswith("organisms.")
    links = []
    try:
        with SessionLocal() as db_session:
            for module in organisms.list_modules(db_session):
                links.append({
                    "key": f"organism:{module.key}",
                    "label": module.label,
                    "short": module.label,
                    "icon": resolve_icon(module.icon),
                    "soon": None,
                    "url": url_for("organisms.module", key=module.key),
                    "active": on_organisms and current_key == module.key,
                })
    except Exception:
        # A brand-new database may not have the tables yet; the rail should
        # still render.
        return []
    return links


@app.context_processor
def inject_nav():
    if g.get("user") is None:
        return {"nav_sections": [], "nav_footer": [], "tab_icon_rules": [],
                "colony_view_meta": COLONY_VIEW_META, "db_labels": {}}

    active = request.endpoint or ""
    g.db_labels = builtin_labels()
    sections = []
    tab_icon_rules = list(TAB_ICON_RULES)
    for section in NAV_SECTIONS:
        links = [r for r in (_resolve_nav_item(i, active) for i in section["links"]) if r]
        if section["label"] == "Databases":
            # Configurable modules sit with the built-in ones, above "Add".
            renamed = g.db_labels
            for link in links:
                if link["key"] in renamed and renamed[link["key"]] != link["label"]:
                    link["label"] = link["short"] = renamed[link["key"]]
            extras = _stock_module_links() + _organism_module_links() + _inventory_module_links()
            tail = [l for l in links if l["key"] in ("drosophila", "new-db")]
            head = [l for l in links if l["key"] not in ("drosophila", "new-db")]
            links = head + extras + [l for l in tail if l["key"] == "new-db"]
            # Each database's tabs show its own glyph, not the generic one.
            tab_icon_rules += [(l["url"], l["icon"]) for l in extras]

        if links:
            sections.append({"label": section["label"], "links": links})
    footer = [r for r in (_resolve_nav_item(i, active) for i in NAV_FOOTER) if r]
    return {
        "nav_sections": sections,
        "nav_footer": footer,
        "tab_icon_rules": tab_icon_rules,
        "colony_view_meta": COLONY_VIEW_META,
        "db_labels": g.db_labels,
    }


@app.context_processor
def inject_asset_version():
    """Expose `asset_version('relative/path')` to templates so we can bust the
    browser cache whenever a built JS bundle changes on disk."""
    import os as _os

    static_root = _os.path.join(_os.path.dirname(__file__), "static")

    def asset_version(rel_path: str) -> str:
        try:
            return str(int(_os.path.getmtime(_os.path.join(static_root, rel_path))))
        except OSError:
            return "0"

    return {"asset_version": asset_version}


def _get_user_directory():
    """Cache username -> {short_name, display_name} for the current request."""
    cache = g.get("user_directory")
    if cache is not None:
        return cache
    cache = {}
    try:
        with SessionLocal() as db_session:
            for u in db_session.scalars(select(UserAccount)).all():
                cache[u.username] = {"short": u.short_name or u.username[:5], "display": u.display_name or u.username}
    except Exception:
        pass
    g.user_directory = cache
    return cache


def _name_color(seed: str) -> tuple[int, int, int]:
    """Stable HSL hue from a name string."""
    h = 0
    for ch in seed:
        h = (h * 31 + ord(ch)) & 0xFFFFFF
    return h % 360, 55, 32


@app.template_filter("relative_day")
def relative_day_filter(value) -> str:
    """"today", "tomorrow", "in 3 d", "2 d ago", or a date further out."""
    if not value:
        return ""
    days = (value - date.today()).days
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    if days == -1:
        return "yesterday"
    if 1 < days <= 13:
        return f"in {days} d"
    if -13 <= days < -1:
        return f"{-days} d ago"
    return value.strftime("%d %b")


@app.template_filter("owner_short")
def owner_short_filter(name: str) -> str:
    if not name:
        return ""
    info = _get_user_directory().get(name)
    if info and info["short"]:
        return info["short"]
    return name[:5]


@app.template_filter("owner_badge")
def owner_badge_filter(name: str) -> Markup:
    if not name:
        return Markup("")
    info = _get_user_directory().get(name)
    if info and info["short"]:
        text = info["short"][:3].upper() if len(info["short"]) > 3 else info["short"].upper()
        tooltip = info["display"] or name
    else:
        cleaned = name.strip()
        parts = cleaned.split()
        if len(parts) >= 2:
            text = (parts[0][0] + parts[1][0]).upper()
        else:
            text = cleaned[:2].upper()
        tooltip = name
    hue, sat, light = _name_color(name)
    bg = f"hsl({hue}, {sat}%, 90%)"
    fg = f"hsl({hue}, {sat}%, {light}%)"
    # data-tooltip drives the CSS popover; aria-label keeps it accessible.
    # We deliberately avoid the native `title` attribute so the browser doesn't
    # show its own delayed tooltip on top of ours.
    return Markup(
        f'<span class="owner-badge" data-tooltip="{escape(tooltip)}" aria-label="{escape(tooltip)}" style="background:{bg};color:{fg};">{escape(text)}</span>'
    )


@app.template_filter("owner_with_badge")
def owner_with_badge_filter(name: str) -> Markup:
    """Badge + name, useful when both are needed in compact rows."""
    if not name:
        return Markup("")
    badge = owner_badge_filter(name)
    label = owner_short_filter(name)
    return Markup(f'<span class="owner-cell">{badge}<span class="owner-cell-name">{escape(label)}</span></span>')


def can_edit_mouse(mouse: MouseRecord) -> bool:
    """Delegates to the single access policy in app/access.py."""
    return access.can_edit_mouse(mouse)


def can_edit_cage(cage: CageRecord) -> bool:
    return access.can_edit_cage(cage)


def deny(record, view: str = "mice"):
    """Return a response when the user may not edit `record`, else None.

    Routes call this right after loading the record:

        blocked = deny(cage, "cages")
        if blocked:
            return blocked

    Keeping it a returned response rather than an abort lets the colony's
    autosave endpoints answer in the shape their caller expects.
    """
    if record is None:
        return None
    if isinstance(record, MouseRecord):
        allowed = access.can_edit_mouse(record)
    elif isinstance(record, CageRecord):
        allowed = access.can_edit_cage(record)
    else:
        allowed = access.can_edit(record)
    if allowed:
        return None
    flash(access.reason_denied(record), "error")
    return autosave_response(view)


def populate_mouse_from_form(db_session, mouse: MouseRecord, form, preserve_owner_on_transfer: bool = True) -> tuple[str | None, str | None]:
    original_owner = mouse.owner
    transfer_recipient = None
    litter_code = form.get("litter_id", "").strip()
    dob = parse_date(form.get("date_of_birth"))
    mouse.litter = get_or_create_litter(db_session, litter_code, dob) if litter_code else None

    cage_input = form.get("cage_id", "").strip()
    if cage_input:
        mouse.cage = get_or_create_cage(db_session, cage_input)
    elif form.get("auto_new_cage") == "1":
        mouse.cage = get_or_create_cage(db_session, "new")
    else:
        mouse.cage = None

    if mouse.cage is not None:
        # Rack, position and location note belong to the cage; see form_changed.
        if form_changed(form, "cage_location"):
            mouse.cage.cage_location = form.get("cage_location", "").strip()
        if "cage_rack" in form and form_changed(form, "cage_rack", "cage_position"):
            error = apply_cage_position(db_session, mouse.cage, form.get("cage_rack"), form.get("cage_position"))
            if error:
                flash(error, "error")

    transgenes = transgene_values_from_form(form)
    sync_mouse_transgenes(mouse, transgenes)
    mouse.gender = form.get("gender", "").strip()
    previous_status = mouse.status
    mouse.status = form.get("status", "").strip()
    status_normalized = mouse.status.lower()
    requested_owner = form.get("owner", "").strip()
    mouse.note = form.get("note", "").strip()
    mouse.date_of_death = parse_date(form.get("date_of_death"))

    lab_users = set(current_lab_usernames(db_session))
    apply_status_rules(mouse, previous_status)

    if status_normalized == "transfer" and requested_owner and requested_owner in lab_users and requested_owner != original_owner:
        transfer_recipient = requested_owner
        if preserve_owner_on_transfer:
            mouse.owner = original_owner
            transfer_note = f"Transferred to {requested_owner} on {date.today().isoformat()}."
            mouse.note = f"{mouse.note} {transfer_note}".strip()
        else:
            mouse.owner = requested_owner
    else:
        mouse.owner = requested_owner

    return transfer_recipient, original_owner


def create_transfer_copy(db_session, source_mouse: MouseRecord, recipient_username: str, sender_username: str | None) -> MouseRecord:
    copied_mouse = MouseRecord(
        mouse_id=next_mouse_id(db_session),
        gender=source_mouse.gender,
        status="experiment",
        owner=recipient_username,
        note=f"Transferred from {sender_username or source_mouse.owner} on {date.today().isoformat()}.",
        date_of_death=None,
        litter=source_mouse.litter,
        cage=get_or_create_cage(db_session, "new"),
    )
    sync_mouse_transgenes(
        copied_mouse,
        [source_mouse.transgene_1, source_mouse.transgene_2, source_mouse.transgene_3, source_mouse.transgene_4],
    )
    db_session.add(copied_mouse)
    add_notification(
        db_session,
        recipient_username,
        title="Mouse transfer received",
        message=f"Mouse {source_mouse.mouse_id} was transferred to you. A new record {copied_mouse.mouse_id} was created in your colony.",
        category="transfer",
    )
    return copied_mouse


def _merged_choices(*groups) -> list[str]:
    """Unique non-empty values in first-seen order, compared without case,
    so the built-in values lead and a lab's own presets follow."""
    seen, out = set(), []
    for group in groups:
        for value in group:
            value = (value or "").strip()
            if value and value.lower() not in seen:
                seen.add(value.lower())
                out.append(value)
    return out


def mouse_sheet_meta(mouse_rows: list[dict], dropdowns: dict, racks=()) -> dict:
    """What the mouse sheet needs beyond the rows themselves: the choices
    for its dropdown cells, and which transgene columns hold anything (an
    empty TG3/TG4 starts hidden, and one click brings it back)."""
    return {
        "status_choices": _merged_choices(
            MOUSE_STATUS_OPTIONS, dropdowns.get("status", []),
            (r["status"] for r in mouse_rows)),
        "gender_choices": _merged_choices(
            ["F", "M", "Unknown"], dropdowns.get("gender", []),
            (r["gender"] for r in mouse_rows)),
        "tg_used": [any(r[f"transgene_{n}"] for r in mouse_rows) for n in range(1, 5)],
        "active_count": sum(1 for r in mouse_rows if r["active"]),
        "racks": [{"id": r.id, "name": r.name} for r in racks],
        "location_notes_used": any(r["cage_location"] for r in mouse_rows),
    }


def colony_context(active_view: str, scope: str = access.DEFAULT_SCOPE) -> dict[str, object]:
    """Build the colony page context.

    `scope` filters which slice of the colony is listed — your own animals,
    the shared breeder cages, or everything. It is a view filter only: what
    you may *edit* is decided per record by app/access.py, and is the same
    whichever scope you are looking at.
    """
    with SessionLocal() as db_session:
        mice = db_session.scalars(select(MouseRecord).order_by(MouseRecord.mouse_id)).all()
        cages = db_session.scalars(select(CageRecord).order_by(CageRecord.cage_id)).all()

        totals = {
            "all_mice": len(mice),
            "all_cages": len(cages),
            "my_mice": sum(1 for m in mice if access.owns(m)),
            "my_cages": sum(1 for c in cages if access.owns(c)),
            "shared_cages": sum(1 for c in cages if access.is_shared_cage(c)),
        }
        mice = [m for m in mice
                if access.in_scope(m, scope, shared=access.is_shared_cage(m.cage))]
        cages = [c for c in cages
                 if access.in_scope(c, scope, shared=access.is_shared_cage(c))]
        litters = db_session.scalars(select(LitterRecord).order_by(LitterRecord.litter_id)).all()
        strains = db_session.scalars(select(StrainRecord).order_by(StrainRecord.strain_name)).all()
        dropdowns = dropdown_options_map(db_session)
        dropdown_records = dropdown_records_map(db_session)
        usernames = current_lab_usernames(db_session)
        notifications = recent_notifications(db_session, g.user.username if g.user else "", limit=10) if g.user else []

        mouse_rows = [mouse_display_row(mouse, g.user.username if g.user else None, g.user.role if g.user else None) for mouse in mice]
        cage_racks = mouse_rack_payload(db_session, cages) if active_view == "cages" else None
        sheet_racks = mouse_racks(db_session)
        # The sheet renders rows you may not edit as read-only, using the
        # same rule the update routes enforce, rather than letting an edit
        # appear to save and then be refused.
        for mouse, row in zip(mice, mouse_rows):
            row["editable"] = can_edit_mouse(mouse)
        cage_rows = []
        for cage in cages:
            derived = cage_derived_dates(cage)
            cage_rows.append(
                {
                    "id": cage.id,
                    "cage_id": cage.cage_id,
                    "cage_location": cage.cage_location,
                    "purpose": cage.purpose,
                    "active": cage_is_active(cage),
                    "notes": cage.notes,
                    "date_give_birth": cage.date_give_birth.isoformat() if cage.date_give_birth else "",
                    "genotyping_date": derived["genotyping_date"],
                    "weaning_date": derived["weaning_date"],
                    "card_id": cage.card_id,
                    "rack_id": cage.rack_id_fk,
                    "position": cage_position_label(cage),
                    "genotype_summary": cage.genotype_summary,
                    "location_detail": cage.location_detail,
                    "room": cage.room,
                    "owner": cage.owner,
                    "is_shared": access.is_shared_cage(cage),
                    "can_edit": access.can_edit_cage(cage),
                    "can_breed": cage.purpose.lower() == "breeding",
                    "default_father": next((str(mouse.mouse_id) for mouse in sorted(cage.mice, key=lambda item: item.mouse_id) if mouse.gender == "M"), ""),
                    "default_mother": next((str(mouse.mouse_id) for mouse in sorted(cage.mice, key=lambda item: item.mouse_id) if mouse.gender == "F"), ""),
                    "mice": [mouse_display_row(mouse, g.user.username, g.user.role) for mouse in sorted(cage.mice, key=lambda item: item.mouse_id)],
                }
            )
        litter_rows = []
        for litter in litters:
            litter_rows.append(
                {
                    "id": litter.id,
                    "litter_id": litter.litter_id,
                    "date_of_birth": litter.date_of_birth.isoformat() if litter.date_of_birth else "",
                    "cohort_name": litter.cohort_name,
                    "father_info": litter.father_info,
                    "mother_info": litter.mother_info,
                    "total_pups": litter.total_pups,
                    "notes": litter.notes,
                    "mice": [mouse_display_row(mouse, g.user.username, g.user.role) for mouse in sorted(litter.mice, key=lambda item: item.mouse_id)],
                }
            )
        strain_rows = [
            {
                "id": strain.id,
                "strain_number": strain.strain_number,
                "strain_name": strain.strain_name,
                "strain_background": strain.strain_background,
                "supplier": strain.supplier,
                "description": strain.description,
            }
            for strain in strains
        ]
        breeder_rows = breeder_mice(db_session, g.user.username if g.user else None, g.user.role if g.user else None)
        breeder_summary_rows = breeder_summary(db_session)
        next_mouse_id_value = next_mouse_id(db_session)
        next_cage_id_value = next_cage_id(db_session)
        next_litter_id_value = next_litter_id(db_session)
        # The mice view needs the open experiments too: the selection bar
        # offers "add to experiment", so the list has to be there even when
        # you are not on the experiments tab.
        open_experiments = []
        if active_view in ("mice", "cages", "breeders"):
            open_experiments = [
                {"id": e.id, "name": e.name}
                for e in db_session.scalars(
                    select(Experiment)
                    .where(Experiment.status.in_(["active", "paused"]))
                    .order_by(Experiment.name)
                ).all()
            ]

        experiments_list = []
        if active_view == "experiments":
            experiments = db_session.scalars(
                select(Experiment).order_by(Experiment.status, Experiment.created_at.desc())
            ).all()
            for exp in experiments:
                experiments_list.append({
                    "id": exp.id,
                    "name": exp.name,
                    "description": exp.description,
                    "status": exp.status,
                    "owner": exp.owner_username,
                    "member_count": len(exp.memberships),
                    "start_date": exp.start_date.strftime("%b %d, %Y") if exp.start_date else "",
                    "end_date": exp.end_date.strftime("%b %d, %Y") if exp.end_date else "",
                })

    return {
        "active_view": active_view,
        "colony_views": COLONY_VIEWS,
        "mouse_rows": mouse_rows,
        "mouse_sheet": mouse_sheet_meta(mouse_rows, dropdowns, sheet_racks),
        "cage_racks": cage_racks,
        "cage_rows": cage_rows,
        "litter_rows": litter_rows,
        "strain_rows": strain_rows,
        "dropdowns": dropdowns,
        "dropdown_records": dropdown_records,
        "next_mouse_id_value": next_mouse_id_value,
        "next_cage_id_value": next_cage_id_value,
        "next_litter_id_value": next_litter_id_value,
        "usernames": usernames,
        "notifications": notifications,
        "status_options": MOUSE_STATUS_OPTIONS,
        "breeder_rows": breeder_rows,
        "breeder_summary": breeder_summary_rows,
        "experiments_list": experiments_list,
        "open_experiments": open_experiments,
        "totals": totals,
    }


@app.route("/")
def index():
    if g.user is None:
        return redirect(url_for("login"))
    # If the user picked a default landing page (settings → default_landing),
    # honor it. Otherwise show the dashboard.
    default_landing = (g.user.default_landing or "").strip()
    if default_landing and default_landing in ALLOWED_LANDING_ENDPOINTS:
        return redirect(url_for(default_landing))
    return redirect(url_for("home_dashboard"))


@app.route("/home")
@login_required
def home_dashboard():
    """Home dashboard: counts, sac reminders, upcoming weanings, genotyping
    queue, recent orders. Read-only — every card links into the relevant
    page for actual edits."""
    today = date.today()
    week_ahead = today + timedelta(days=7)

    with SessionLocal() as db_session:
        # ---- Counts ------------------------------------------------------
        total_mice = db_session.scalar(select(func.count(MouseRecord.id))) or 0
        active_mice = db_session.scalar(
            select(func.count(MouseRecord.id)).where(MouseRecord.date_of_death.is_(None))
        ) or 0
        my_mice = db_session.scalar(
            select(func.count(MouseRecord.id)).where(MouseRecord.owner == g.user.username)
        ) or 0
        order_modules = [m.id for m in db_session.scalars(
            select(InventoryModule).where(InventoryModule.kind == "orders"))]
        pending_orders = db_session.scalar(
            select(func.count(InventoryItem.id)).where(
                InventoryItem.module_id_fk.in_(order_modules),
                InventoryItem.status.in_(["requested", "ordered"]))
        ) or 0
        notebook_pages = db_session.scalar(
            select(func.count(NotebookPage.id))
            .join(NotebookTab, NotebookPage.tab_id_fk == NotebookTab.id)
            .where(NotebookTab.owner_username == g.user.username)
        ) or 0

        # ---- Mice older than 30 weeks (sac candidates) -------------------
        # Mouse age comes from its litter's date_of_birth. Active mice only.
        old_mice = db_session.scalars(
            select(MouseRecord)
            .join(LitterRecord, MouseRecord.litter_id_fk == LitterRecord.id)
            .where(MouseRecord.date_of_death.is_(None))
            .where(LitterRecord.date_of_birth.is_not(None))
            .where(LitterRecord.date_of_birth <= today - timedelta(days=210))
            .order_by(LitterRecord.date_of_birth.asc())
            .limit(15)
        ).all()
        sac_candidates = []
        for mouse in old_mice:
            dob = mouse.litter.date_of_birth if mouse.litter else None
            if not dob:
                continue
            age_weeks = (today - dob).days // 7
            sac_candidates.append({
                "mouse_id": mouse.mouse_id,
                "gender": mouse.gender,
                "genotype": mouse.genotype,
                "owner": mouse.owner,
                "status": mouse.status,
                "age_weeks": age_weeks,
                "cage_id": mouse.cage.cage_id if mouse.cage else "",
            })

        # ---- Upcoming weanings (litters whose DOB+21d is in the next 7d
        # or already past wean date) ---------------------------------------
        wean_window_start = today - timedelta(days=14)  # already-overdue P21+
        wean_window_end = today - timedelta(days=14)  # 21 - 7 = 14
        # We want litters where DOB+21 is within ±7 days of today:
        upcoming_litters = db_session.scalars(
            select(LitterRecord)
            .where(LitterRecord.date_of_birth.is_not(None))
            .where(LitterRecord.date_of_birth >= today - timedelta(days=28))
            .where(LitterRecord.date_of_birth <= today - timedelta(days=14))
            .order_by(LitterRecord.date_of_birth.asc())
            .limit(10)
        ).all()
        weanings = []
        for litter in upcoming_litters:
            dob = litter.date_of_birth
            wean_date = dob + timedelta(days=21)
            days_to_wean = (wean_date - today).days
            weanings.append({
                "litter_id": litter.litter_id,
                "dob": dob.strftime("%b %d") if dob else "",
                "wean_date": wean_date.strftime("%b %d"),
                "days_to_wean": days_to_wean,
                "overdue": days_to_wean < 0,
                "pups": litter.total_pups,
                "cohort": litter.cohort_name,
            })

        # ---- Genotyping queue: mice with status='geno' OR recently born
        # (over 2 weeks old, no genotype set) ------------------------------
        geno_status_mice = db_session.scalars(
            select(MouseRecord)
            .where(MouseRecord.date_of_death.is_(None))
            .where(MouseRecord.status == "geno")
            .order_by(MouseRecord.mouse_id.desc())
            .limit(10)
        ).all()
        geno_queue = [{
            "mouse_id": m.mouse_id,
            "gender": m.gender,
            "owner": m.owner,
            "cage_id": m.cage.cage_id if m.cage else "",
            "genotype": m.genotype,
            "reason": "status=geno",
        } for m in geno_status_mice]

        # ---- Recent orders ------------------------------------------------
        recent_orders = db_session.scalars(
            select(InventoryItem).where(InventoryItem.module_id_fk.in_(order_modules))
            .order_by(InventoryItem.created_at.desc()).limit(6)
        ).all()
        orders_list = [{
            "id": o.number,
            "vendor": o.vendor,
            "item": o.name,
            "status": o.status,
            "qty": o.quantity,
            "created_at": o.created_at.strftime("%b %d, %Y"),
        } for o in recent_orders]

        # ---- Upcoming calendar events ------------------------------------
        upcoming_events = db_session.scalars(
            select(CalendarEvent)
            .where(CalendarEvent.event_date >= today)
            .where(CalendarEvent.event_date <= today + timedelta(days=14))
            .order_by(CalendarEvent.event_date.asc())
            .limit(6)
        ).all()
        events_list = [{
            "title": e.title,
            "event_date": e.event_date.strftime("%b %d"),
            "days_until": (e.event_date - today).days,
            "event_type": e.event_type,
        } for e in upcoming_events]

    # Fly / worm work due soon: flips, egg collections, shifts, scoring.
    from . import stock_service
    stock_due = []
    with SessionLocal() as db_session:
        for module in stock_service.list_modules(db_session):
            mv = stock_service.view(module)
            for item in stock_service.schedule(db_session, mv, today, horizon=2):
                stock_due.append({"module": mv.label, "key": mv.key, "icon": mv.icon, "title": item["title"],
                                  "due": item["due"], "overdue": item["overdue"], "is_today": item["today"], "kind": item["kind"]})
    stock_due.sort(key=lambda i: i["due"])

    # Schedule items from the configurable organism databases (wean, retire…).
    from . import organism_service
    with SessionLocal() as db_session:
        organism_due = organism_service.home_due(db_session, horizon_days=2)
        db_session.commit()

    hour = datetime.now().hour
    greeting = "Good morning" if hour < 12 else ("Good afternoon" if hour < 18 else "Good evening")

    return render_template(
        "home.html",
        stock_due=stock_due[:12],
        stock_due_total=len(stock_due),
        organism_due=organism_due[:12],
        organism_due_total=len(organism_due),
        greeting=greeting,
        today_str=today.strftime("%A, %b %d, %Y"),
        counts={
            "total_mice": total_mice,
            "active_mice": active_mice,
            "my_mice": my_mice,
            "pending_orders": pending_orders,
            "notebook_pages": notebook_pages,
        },
        sac_candidates=sac_candidates,
        weanings=weanings,
        geno_queue=geno_queue,
        orders_list=orders_list,
        events_list=events_list,
    )


ALLOWED_LANDING_ENDPOINTS = {"colony", "notebook", "calendar", "orders", "samples", "plasmids"}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with SessionLocal() as db_session:
            user = db_session.scalar(select(UserAccount).where(UserAccount.username == username))
            if user is None or not check_password_hash(user.password_hash, password):
                flash("Incorrect username or password.", "error")
            elif getattr(user, "disabled", False):
                flash("This account is disabled. Contact an admin.", "error")
            else:
                session.clear()
                session["user_id"] = user.id
                flash(f"Welcome, {user.display_name or user.username}.", "success")
                landing = (user.default_landing or "").strip()
                if landing in ALLOWED_LANDING_ENDPOINTS:
                    fallback = url_for(landing)
                else:
                    fallback = url_for("colony")
                destination = request.args.get("next") or fallback
                return redirect(destination)
    return render_template("auth.html", mode="login")


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    profile_error = None
    with SessionLocal() as db_session:
        user = db_session.get(UserAccount, g.user.id)
        if user is None:
            return redirect(url_for("logout"))
        if request.method == "POST":
            action = request.form.get("action", "profile")
            if action == "profile":
                user.display_name = request.form.get("display_name", "").strip()
                short = request.form.get("short_name", "").strip()
                user.short_name = short[:5]
                user.email = request.form.get("email", "").strip()
                user.role_title = request.form.get("role_title", "").strip()
                landing = request.form.get("default_landing", "").strip()
                user.default_landing = landing if landing in ALLOWED_LANDING_ENDPOINTS else ""
                db_session.commit()
                flash("Profile updated.", "success")
            elif action == "notifications":
                user.notify_transfer = request.form.get("notify_transfer") == "1"
                user.notify_picked = request.form.get("notify_picked") == "1"
                user.notify_breeder_aging = request.form.get("notify_breeder_aging") == "1"
                db_session.commit()
                flash("Notification preferences updated.", "success")
            elif action == "password":
                current = request.form.get("current_password", "")
                new_pw = request.form.get("new_password", "")
                confirm = request.form.get("confirm_password", "")
                if not check_password_hash(user.password_hash, current):
                    flash("Current password is incorrect.", "error")
                elif len(new_pw) < 6:
                    flash("New password must be at least 6 characters.", "error")
                elif new_pw != confirm:
                    flash("New passwords do not match.", "error")
                else:
                    user.password_hash = generate_password_hash(new_pw)
                    db_session.commit()
                    flash("Password updated.", "success")
            return redirect(url_for("settings"))
        user_data = {
            "username": user.username,
            "display_name": user.display_name,
            "short_name": user.short_name,
            "email": user.email,
            "role_title": user.role_title,
            "default_landing": user.default_landing,
            "role": user.role,
            "created_at": user.created_at.strftime("%Y-%m-%d") if user.created_at else "",
            "notify_transfer": user.notify_transfer,
            "notify_picked": user.notify_picked,
            "notify_breeder_aging": user.notify_breeder_aging,
        }
    from . import mailer

    return render_template(
        "settings.html",
        user_settings=user_data,
        landing_choices=sorted(ALLOWED_LANDING_ENDPOINTS),
        mail_status=mailer.status_line(),
        mail_configured=mailer.is_configured(),
    )


@app.route("/settings/export")
@login_required
def export_my_data():
    import csv as _csv
    import io as _io
    import json as _json
    import re as _re
    import zipfile

    username = g.user.username
    buf = _io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        with SessionLocal() as db_session:
            user = db_session.get(UserAccount, g.user.id)

            mice = db_session.scalars(
                select(MouseRecord).where(MouseRecord.owner == username).order_by(MouseRecord.mouse_id)
            ).all()
            mice_csv = _io.StringIO()
            writer = _csv.writer(mice_csv)
            writer.writerow(["mouse_id", "gender", "genotype", "status", "owner", "cage_id", "litter_id", "dob", "dod", "note"])
            for m in mice:
                writer.writerow([
                    m.mouse_id, m.gender, m.genotype, m.status, m.owner,
                    m.cage.cage_id if m.cage else "",
                    m.litter.litter_id if m.litter else "",
                    m.litter.date_of_birth.isoformat() if (m.litter and m.litter.date_of_birth) else "",
                    m.date_of_death.isoformat() if m.date_of_death else "",
                    m.note,
                ])
            zf.writestr("mice.csv", mice_csv.getvalue())

            plasmids = db_session.scalars(
                select(PlasmidRecord).where(PlasmidRecord.owner == username).order_by(PlasmidRecord.plasmid_id)
            ).all()
            plasmid_csv = _io.StringIO()
            writer = _csv.writer(plasmid_csv)
            writer.writerow(["plasmid_id", "name", "backbone", "insert", "resistance", "owner", "location", "notes"])
            for p in plasmids:
                writer.writerow([
                    p.plasmid_id, p.name, p.backbone, p.insert_seq, p.resistance,
                    p.owner, p.location, p.notes,
                ])
            zf.writestr("plasmids.csv", plasmid_csv.getvalue())

            tabs = db_session.scalars(
                select(NotebookTab).where(NotebookTab.owner_username == username).order_by(NotebookTab.position, NotebookTab.id)
            ).all()
            for tab in tabs:
                safe_tab = _re.sub(r"[^\w\-_. ]", "_", tab.title or f"tab_{tab.id}").strip() or f"tab_{tab.id}"
                for page in tab.pages:
                    safe_page = _re.sub(r"[^\w\-_. ]", "_", page.title or f"page_{page.id}").strip() or f"page_{page.id}"
                    path = f"notebook/{safe_tab}/{safe_page}.md"
                    body = page.body or ""
                    header = f"# {page.title}\n\n_Created: {page.created_at.isoformat()} · Updated: {page.updated_at.isoformat()}_\n\n"
                    zf.writestr(path, header + body)

            profile = {
                "username": user.username,
                "display_name": user.display_name,
                "short_name": user.short_name,
                "email": user.email,
                "role_title": user.role_title,
                "role": user.role,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "exported_at": datetime.utcnow().isoformat(),
                "counts": {
                    "mice": len(mice),
                    "plasmids": len(plasmids),
                    "notebook_pages": sum(len(t.pages) for t in tabs),
                },
            }
            zf.writestr("profile.json", _json.dumps(profile, indent=2))

    buf.seek(0)
    filename = f"biomanager_{username}_{datetime.utcnow().strftime('%Y%m%d')}.zip"
    return Response(
        buf.getvalue(),
        mimetype="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/admin/colony")
@admin_required
def admin_colony_overview():
    """Everyone's cages on one page, grouped by who manages them.

    The colony views are scoped to the person looking at them, which is what
    you want day to day but useless when someone leaves and their animals
    need reassigning. This is the whole-facility picture: who holds what,
    how full it is, and what has gone quiet.
    """
    today = date.today()
    with SessionLocal() as db_session:
        cages = db_session.scalars(
            select(CageRecord).options(selectinload(CageRecord.mice)).order_by(CageRecord.cage_id)
        ).all()
        unhoused = db_session.scalars(
            select(MouseRecord).where(MouseRecord.cage_id_fk.is_(None),
                                      MouseRecord.date_of_death.is_(None))
        ).all()

        groups: dict[str, dict] = {}
        for cage in cages:
            living = [m for m in cage.mice if m.date_of_death is None]
            shared = access.is_shared_cage(cage)
            # A shared breeder cage belongs to the lab, not to one person.
            key = "__shared__" if shared else (cage.owner or "").strip() or "__unowned__"
            group = groups.setdefault(key, {
                "owner": key, "cages": [], "mice": 0, "active_cages": 0,
            })
            last_touch = max(
                [m.updated_at for m in cage.mice if m.updated_at] or [cage.created_at]
            )
            group["cages"].append({
                "id": cage.id,
                "cage_id": cage.cage_id,
                "purpose": cage.purpose,
                "room": cage.room or cage.cage_location,
                "count": len(living),
                "total": len(cage.mice),
                "shared": shared,
                "active": cage_is_active(cage),
                "owner": cage.owner,
                "idle_days": (today - last_touch.date()).days if last_touch else None,
            })
            group["mice"] += len(living)
            group["active_cages"] += 1 if cage_is_active(cage) else 0

        def sort_key(item):
            name = item[0]
            return (name in ("__shared__", "__unowned__"), name)

        ordered = [
            {
                "label": {"__shared__": "Shared breeder cages",
                          "__unowned__": "Unassigned"}.get(name, name),
                "owner": "" if name.startswith("__") else name,
                "is_pool": name.startswith("__"),
                **data,
            }
            for name, data in sorted(groups.items(), key=sort_key)
        ]

        return render_template(
            "admin_colony.html",
            groups=ordered,
            unhoused=unhoused,
            totals={
                "cages": len(cages),
                "mice": sum(g["mice"] for g in ordered),
                "owners": sum(1 for g in ordered if not g["is_pool"]),
                "shared": sum(len(g["cages"]) for g in ordered if g["label"].startswith("Shared")),
            },
        )


@app.route("/admin/users")
@admin_required
def admin_users():
    with SessionLocal() as db_session:
        users = db_session.scalars(select(UserAccount).order_by(UserAccount.created_at)).all()
        rows = [
            {
                "id": u.id,
                "username": u.username,
                "display_name": u.display_name,
                "short_name": u.short_name,
                "email": u.email,
                "role_title": u.role_title,
                "role": u.role,
                "disabled": u.disabled,
                "created_at": u.created_at.strftime("%Y-%m-%d") if u.created_at else "",
            }
            for u in users
        ]
    return render_template("admin_users.html", users=rows)


@app.route("/admin/users/<int:user_id>/role", methods=["POST"])
@admin_required
def admin_toggle_role(user_id: int):
    with SessionLocal() as db_session:
        target = db_session.get(UserAccount, user_id)
        if target is None:
            flash("User not found.", "error")
            return redirect(url_for("admin_users"))
        if target.id == g.user.id:
            flash("You cannot change your own role.", "error")
            return redirect(url_for("admin_users"))
        target.role = "member" if target.role == "admin" else "admin"
        db_session.commit()
        flash(f"{target.username} is now {target.role}.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/disable", methods=["POST"])
@admin_required
def admin_toggle_disabled(user_id: int):
    with SessionLocal() as db_session:
        target = db_session.get(UserAccount, user_id)
        if target is None:
            flash("User not found.", "error")
            return redirect(url_for("admin_users"))
        if target.id == g.user.id:
            flash("You cannot disable your own account.", "error")
            return redirect(url_for("admin_users"))
        target.disabled = not target.disabled
        db_session.commit()
        flash(f"{target.username} {'disabled' if target.disabled else 'enabled'}.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/reset-password", methods=["POST"])
@admin_required
def admin_reset_password(user_id: int):
    new_password = (request.form.get("new_password") or "").strip()
    if len(new_password) < 6:
        flash("Reset password must be at least 6 characters.", "error")
        return redirect(url_for("admin_users"))
    with SessionLocal() as db_session:
        target = db_session.get(UserAccount, user_id)
        if target is None:
            flash("User not found.", "error")
            return redirect(url_for("admin_users"))
        target.password_hash = generate_password_hash(new_password)
        db_session.commit()
        flash(f"Password reset for {target.username}.", "success")
    return redirect(url_for("admin_users"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        display_name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if not username or not password:
            flash("Username and password are required.", "error")
        elif password != confirm_password:
            flash("Passwords do not match.", "error")
        else:
            with SessionLocal() as db_session:
                existing = db_session.scalar(select(UserAccount).where(UserAccount.username == username))
                if existing is not None:
                    flash("That username already exists.", "error")
                else:
                    user_count = len(db_session.scalars(select(UserAccount)).all())
                    role = "admin" if user_count == 0 else "member"
                    user = UserAccount(
                        username=username,
                        display_name=display_name,
                        password_hash=generate_password_hash(password),
                        role=role,
                    )
                    db_session.add(user)
                    db_session.commit()
                    flash("Account created. You can sign in now.", "success")
                    return redirect(url_for("login"))
    return render_template("auth.html", mode="register")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("login"))


@app.route("/notifications/mark-read", methods=["POST"])
@login_required
def mark_notifications_read():
    with SessionLocal() as db_session:
        rows = db_session.scalars(select(NotificationRecord).where(NotificationRecord.recipient_username == g.user.username, NotificationRecord.is_read.is_(False))).all()
        for row in rows:
            row.is_read = True
        db_session.commit()
    return redirect(url_for("colony", view=request.form.get("view", "mice")))


@app.route("/colony")
@login_required
def colony():
    active_view = request.args.get("view", "mice")
    scope = access.resolve_scope(request.args.get("scope"))
    context = colony_context(active_view, scope)
    context["scope"] = scope
    context["scopes"] = access.SCOPES
    context["end_statuses"] = sorted(END_STATUSES)
    return render_template("colony.html", **context)


# ---------------------------------------------------------------------------
# Experiments: a cohort of mice under a shared treatment plan + timeline,
# with longitudinal body-weight tracking per mouse.
# ---------------------------------------------------------------------------


@app.route("/colony/experiments/create", methods=["POST"])
@login_required
def create_experiment():
    name = (request.form.get("name") or "").strip() or "Untitled experiment"
    description = (request.form.get("description") or "").strip()
    treatment = (request.form.get("treatment_plan") or "").strip()
    start_date = parse_date(request.form.get("start_date"))
    cage_id_raw = (request.form.get("from_cage_id") or "").strip()

    with SessionLocal() as db_session:
        exp = Experiment(
            name=name,
            description=description,
            treatment_plan=treatment,
            status="active",
            owner_username=g.user.username,
            start_date=start_date,
        )
        db_session.add(exp)
        db_session.flush()

        # Optional: seed members from a cage's active mice.
        if cage_id_raw:
            cage = db_session.scalar(select(CageRecord).where(CageRecord.cage_id == cage_id_raw))
            if cage is not None:
                for mouse in cage.mice:
                    if mouse.date_of_death is None:
                        db_session.add(ExperimentMouse(
                            experiment_id_fk=exp.id,
                            mouse_id_fk=mouse.id,
                            treatment_group="",
                        ))
        db_session.commit()
        return redirect(url_for("experiment_detail", experiment_id=exp.id))


@app.route("/colony/experiments/<int:experiment_id>")
@login_required
def experiment_detail(experiment_id: int):
    with SessionLocal() as db_session:
        exp = db_session.get(Experiment, experiment_id)
        if exp is None:
            flash("Experiment not found.", "error")
            return redirect(url_for("colony", view="experiments"))

        # Members + each mouse's full weight history.
        members = []
        for em in sorted(exp.memberships, key=lambda m: m.mouse.mouse_id if m.mouse else 0):
            mouse = em.mouse
            if mouse is None:
                continue
            weights = db_session.scalars(
                select(MouseWeight)
                .where(MouseWeight.mouse_id_fk == mouse.id)
                .order_by(MouseWeight.weigh_date.asc())
            ).all()
            members.append({
                "membership_id": em.id,
                "mouse_row_id": mouse.id,
                "mouse_id": mouse.mouse_id,
                "gender": mouse.gender,
                "genotype": mouse.genotype,
                "cage_id": mouse.cage.cage_id if mouse.cage else "",
                "treatment_group": em.treatment_group,
                "weights": [
                    {"date": w.weigh_date.isoformat(), "grams": w.grams, "notes": w.notes}
                    for w in weights
                ],
            })

        # Collect a unified date axis (every weigh_date observed across all
        # mice, sorted) for the weight matrix view.
        all_dates = sorted({w["date"] for m in members for w in m["weights"]})

        # All cages for the "add cage" picker.
        all_cages = db_session.scalars(select(CageRecord).order_by(CageRecord.cage_id)).all()
        cages_data = [{"id": c.id, "cage_id": c.cage_id, "mouse_count": len(c.mice)} for c in all_cages]

        # Available mice to add individually.
        existing_ids = {m["mouse_row_id"] for m in members}
        candidate_mice = db_session.scalars(
            select(MouseRecord).where(MouseRecord.date_of_death.is_(None)).order_by(MouseRecord.mouse_id)
        ).all()
        candidate_mice_data = [
            {"id": m.id, "mouse_id": m.mouse_id, "label": f"#{m.mouse_id} · {m.gender or '?'} · {m.genotype or '(no geno)'}"}
            for m in candidate_mice if m.id not in existing_ids
        ]

        exp_data = {
            "id": exp.id,
            "name": exp.name,
            "description": exp.description,
            "treatment_plan": exp.treatment_plan,
            "status": exp.status,
            "owner": exp.owner_username,
            "start_date": exp.start_date.isoformat() if exp.start_date else "",
            "end_date": exp.end_date.isoformat() if exp.end_date else "",
        }
    return render_template(
        "experiment_detail.html",
        experiment=exp_data,
        members=members,
        all_dates=all_dates,
        cages=cages_data,
        candidate_mice=candidate_mice_data,
    )


@app.route("/colony/experiments/<int:experiment_id>/update", methods=["POST"])
@login_required
def update_experiment(experiment_id: int):
    with SessionLocal() as db_session:
        exp = db_session.get(Experiment, experiment_id)
        if exp is None:
            return jsonify({"ok": False}), 404
        if "name" in request.form:
            exp.name = (request.form.get("name") or "").strip() or exp.name
        if "description" in request.form:
            exp.description = request.form.get("description", exp.description)
        if "treatment_plan" in request.form:
            exp.treatment_plan = request.form.get("treatment_plan", exp.treatment_plan)
        if "status" in request.form:
            exp.status = request.form.get("status", exp.status).strip() or "active"
        if "start_date" in request.form:
            exp.start_date = parse_date(request.form.get("start_date"))
        if "end_date" in request.form:
            exp.end_date = parse_date(request.form.get("end_date"))
        exp.updated_at = datetime.utcnow()
        db_session.commit()
    if request.headers.get("X-Autosave") == "1":
        return jsonify({"ok": True})
    return redirect(url_for("experiment_detail", experiment_id=experiment_id))


@app.route("/colony/experiments/<int:experiment_id>/delete", methods=["POST"])
@login_required
def delete_experiment(experiment_id: int):
    with SessionLocal() as db_session:
        exp = db_session.get(Experiment, experiment_id)
        if exp is not None:
            log_delete(
                db_session, "experiments", exp.id,
                record_label=f"Experiment: {exp.name}",
                details=f"members={len(exp.memberships)}",
            )
            db_session.delete(exp)
            db_session.commit()
    return redirect(url_for("colony", view="experiments"))


@app.route("/colony/experiments/<int:experiment_id>/add-cage", methods=["POST"])
@login_required
def experiment_add_cage(experiment_id: int):
    cage_id_raw = (request.form.get("cage_id") or "").strip()
    with SessionLocal() as db_session:
        exp = db_session.get(Experiment, experiment_id)
        if exp is None or not cage_id_raw:
            return redirect(url_for("colony", view="experiments"))
        cage = db_session.scalar(select(CageRecord).where(CageRecord.cage_id == cage_id_raw))
        if cage is None:
            flash(f"Cage '{cage_id_raw}' not found.", "error")
            return redirect(url_for("experiment_detail", experiment_id=experiment_id))
        existing = {em.mouse_id_fk for em in exp.memberships}
        for mouse in cage.mice:
            if mouse.id in existing or mouse.date_of_death is not None:
                continue
            db_session.add(ExperimentMouse(
                experiment_id_fk=exp.id,
                mouse_id_fk=mouse.id,
                treatment_group="",
            ))
        db_session.commit()
    return redirect(url_for("experiment_detail", experiment_id=experiment_id))


@app.route("/colony/experiments/<int:experiment_id>/add-mouse", methods=["POST"])
@login_required
def experiment_add_mouse(experiment_id: int):
    mouse_row_id = request.form.get("mouse_row_id", type=int)
    treatment_group = (request.form.get("treatment_group") or "").strip()
    if not mouse_row_id:
        return redirect(url_for("experiment_detail", experiment_id=experiment_id))
    with SessionLocal() as db_session:
        exp = db_session.get(Experiment, experiment_id)
        mouse = db_session.get(MouseRecord, mouse_row_id)
        if exp is None or mouse is None:
            return redirect(url_for("colony", view="experiments"))
        if not any(em.mouse_id_fk == mouse.id for em in exp.memberships):
            db_session.add(ExperimentMouse(
                experiment_id_fk=exp.id,
                mouse_id_fk=mouse.id,
                treatment_group=treatment_group,
            ))
            db_session.commit()
    return redirect(url_for("experiment_detail", experiment_id=experiment_id))


@app.route("/colony/experiments/<int:experiment_id>/members/<int:membership_id>/update", methods=["POST"])
@login_required
def experiment_member_update(experiment_id: int, membership_id: int):
    with SessionLocal() as db_session:
        em = db_session.get(ExperimentMouse, membership_id)
        if em is None or em.experiment_id_fk != experiment_id:
            return jsonify({"ok": False}), 404
        em.treatment_group = (request.form.get("treatment_group") or em.treatment_group).strip()
        if "note" in request.form:
            em.note = request.form.get("note", em.note).strip()
        db_session.commit()
        return jsonify({"ok": True})


@app.route("/colony/experiments/<int:experiment_id>/members/<int:membership_id>/remove", methods=["POST"])
@login_required
def experiment_member_remove(experiment_id: int, membership_id: int):
    with SessionLocal() as db_session:
        em = db_session.get(ExperimentMouse, membership_id)
        if em is not None and em.experiment_id_fk == experiment_id:
            db_session.delete(em)
            db_session.commit()
    return redirect(url_for("experiment_detail", experiment_id=experiment_id))


@app.route("/colony/mice/<int:mouse_row_id>/weights/create", methods=["POST"])
@login_required
def mouse_weight_create(mouse_row_id: int):
    raw_date = request.form.get("weigh_date") or ""
    raw_grams = request.form.get("grams") or ""
    notes = (request.form.get("notes") or "").strip()
    try:
        grams = float(raw_grams)
    except ValueError:
        return jsonify({"ok": False, "error": "grams must be a number"}), 400
    weigh_date = parse_date(raw_date) or date.today()
    with SessionLocal() as db_session:
        mouse = db_session.get(MouseRecord, mouse_row_id)
        if mouse is None:
            return jsonify({"ok": False, "error": "mouse not found"}), 404
        if not can_edit_mouse(mouse):
            return jsonify({"ok": False, "error": access.reason_denied(mouse)}), 403
        # Upsert: if a weight for this mouse + date exists, update it.
        existing = db_session.scalar(
            select(MouseWeight)
            .where(MouseWeight.mouse_id_fk == mouse.id)
            .where(MouseWeight.weigh_date == weigh_date)
        )
        if existing is not None:
            existing.grams = grams
            if notes:
                existing.notes = notes
            existing.recorded_by = g.user.username
        else:
            db_session.add(MouseWeight(
                mouse_id_fk=mouse.id,
                weigh_date=weigh_date,
                grams=grams,
                notes=notes,
                recorded_by=g.user.username,
            ))
        db_session.commit()
    if request.headers.get("X-Autosave") == "1":
        return jsonify({"ok": True})
    return redirect(request.referrer or url_for("colony", view="experiments"))


@app.route("/colony/mice/<int:mouse_row_id>/weights/<int:weight_id>/delete", methods=["POST"])
@login_required
def mouse_weight_delete(mouse_row_id: int, weight_id: int):
    with SessionLocal() as db_session:
        w = db_session.get(MouseWeight, weight_id)
        if w is not None and w.mouse_id_fk == mouse_row_id:
            mouse = db_session.get(MouseRecord, mouse_row_id)
            if not can_edit_mouse(mouse):
                flash(access.reason_denied(mouse), "error")
                return redirect(request.referrer or url_for("colony", view="experiments"))
            db_session.delete(w)
            db_session.commit()
    return redirect(request.referrer or url_for("colony", view="experiments"))


@app.route("/colony/mice/create", methods=["POST"])
@login_required
def create_mouse():
    with SessionLocal() as db_session:
        mouse = MouseRecord(mouse_id=next_mouse_id(db_session), owner=request.form.get("owner", "").strip())
        transfer_recipient, sender_username = populate_mouse_from_form(db_session, mouse, request.form, preserve_owner_on_transfer=False)
        if not mouse.owner and g.user is not None:
            mouse.owner = g.user.username
        db_session.add(mouse)
        if transfer_recipient:
            create_transfer_copy(db_session, mouse, transfer_recipient, sender_username)
        db_session.commit()
    return redirect(url_for("colony", view="mice"))


@app.route("/colony/mice/new-record", methods=["POST"])
@login_required
def create_blank_mouse():
    with SessionLocal() as db_session:
        mouse = MouseRecord(mouse_id=next_mouse_id(db_session), owner=g.user.username)
        db_session.add(mouse)
        db_session.commit()
    return redirect(url_for("colony", view="mice"))


@app.route("/colony/mice/<int:mouse_row_id>/update", methods=["POST"])
@login_required
def update_mouse(mouse_row_id: int):
    with SessionLocal() as db_session:
        mouse = db_session.get(MouseRecord, mouse_row_id)
        if mouse is None:
            return autosave_response("mice")
        if not can_edit_mouse(mouse):
            flash(access.reason_denied(mouse), "error")
            return autosave_response("mice")

        original_litter_id = mouse.litter.litter_id if mouse.litter else ""
        original_dob = mouse.litter.date_of_birth if mouse.litter else None
        form_litter_id = request.form.get("litter_id", "").strip()
        confirm_cohort_change = request.form.get("confirm_cohort_dob_change") == "1"
        requested_dob = parse_date(request.form.get("date_of_birth"))
        keeping_same_litter = bool(original_litter_id) and form_litter_id == original_litter_id

        if keeping_same_litter and requested_dob and requested_dob != original_dob and not confirm_cohort_change:
            flash("DOB belongs to the cohort. Confirm to remove this mouse from the cohort before changing DOB.", "error")
            return autosave_response("mice")

        transfer_recipient, sender_username = populate_mouse_from_form(db_session, mouse, request.form)

        if keeping_same_litter and requested_dob and requested_dob != original_dob and confirm_cohort_change:
            if mouse.litter is not None and mouse.litter.litter_id == original_litter_id:
                mouse.litter.date_of_birth = original_dob
            new_litter = get_or_create_litter(db_session, next_litter_id(db_session), requested_dob)
            mouse.litter = new_litter
        if transfer_recipient:
            create_transfer_copy(db_session, mouse, transfer_recipient, sender_username)
        stamp_updated(mouse)
        db_session.commit()
        state = cage_state(mouse.cage)
        litter = mouse.litter
        mouse_state = {"id": mouse.id, "active": mouse_is_active(mouse), "status": mouse.status,
                       "date_of_death": mouse.date_of_death.isoformat() if mouse.date_of_death else "",
                       "litter_id": litter.litter_id if litter else "",
                       "date_of_birth": litter.date_of_birth.isoformat() if litter and litter.date_of_birth else ""}
    result = autosave_response("mice")
    if request.headers.get("X-Autosave") == "1" and not isinstance(result, tuple):
        return jsonify({"ok": True, "cage": state, "mouse": mouse_state})
    return result


@app.route("/colony/mice/<int:mouse_row_id>/duplicate", methods=["POST"])
@login_required
def duplicate_mouse(mouse_row_id: int):
    with SessionLocal() as db_session:
        source_mouse = db_session.get(MouseRecord, mouse_row_id)
        if source_mouse is None:
            return redirect(url_for("colony", view="mice"))
        blocked = deny(source_mouse, "mice")
        if blocked:
            return blocked
        duplicate = MouseRecord(
            mouse_id=next_mouse_id(db_session),
            gender=source_mouse.gender,
            status=source_mouse.status,
            owner=source_mouse.owner,
            note=source_mouse.note,
            date_of_death=None,
            cage=source_mouse.cage,
            litter=source_mouse.litter,
        )
        sync_mouse_transgenes(duplicate, [source_mouse.transgene_1, source_mouse.transgene_2, source_mouse.transgene_3, source_mouse.transgene_4])
        db_session.add(duplicate)
        db_session.commit()
    return redirect(url_for("colony", view="mice"))


@app.route("/colony/mice/<int:mouse_row_id>/delete", methods=["POST"])
@login_required
def delete_mouse(mouse_row_id: int):
    with SessionLocal() as db_session:
        mouse = db_session.get(MouseRecord, mouse_row_id)
        if mouse is not None and can_edit_mouse(mouse):
            log_delete(
                db_session, "mice", mouse.id,
                record_label=f"Mouse #{mouse.mouse_id}",
                details=f"gender={mouse.gender} genotype={mouse.genotype} owner={mouse.owner}",
            )
            db_session.delete(mouse)
            db_session.commit()
    return redirect(url_for("colony", view="mice"))


@app.route("/colony/mice/<int:mouse_row_id>/pick", methods=["POST"])
@login_required
def pick_mouse(mouse_row_id: int):
    with SessionLocal() as db_session:
        mouse = db_session.get(MouseRecord, mouse_row_id)
        if mouse is None:
            return redirect(url_for("colony", view="breeders"))
        blocked = deny(mouse, "breeders")
        if blocked:
            return blocked
        previous_owner = mouse.owner
        mouse.owner = g.user.username
        if previous_owner and previous_owner != g.user.username:
            add_notification(
                db_session,
                previous_owner,
                title="Mouse picked from breeder cage",
                message=f"Mouse {mouse.mouse_id} was picked by {g.user.username}.",
                category="picked",
            )
        db_session.commit()
    return redirect(url_for("colony", view="breeders"))


@app.route("/colony/mice/bulk-sac", methods=["POST"])
@login_required
def bulk_sac_mice():
    ids = [int(value) for value in request.form.getlist("selected_ids") if value.isdigit()]
    with SessionLocal() as db_session, audit.batch(
            db_session, "update", "mark as sac", "mice") as batch_row:
        mice = db_session.scalars(select(MouseRecord).where(MouseRecord.id.in_(ids))).all() if ids else []
        done = 0
        for mouse in mice:
            if can_edit_mouse(mouse):
                mouse.status = "sac"
                mouse.date_of_death = date.today()
                done += 1
        batch_row.record_count = done
        db_session.commit()
    return redirect(url_for("colony", view="mice"))


# ---------------------------------------------------------------------------
# Batch actions on a selection of mice.
#
# All of these take repeated `selected_ids` fields (see
# static/selection-bar.js) and share one rule: apply to every record the
# user may edit, skip the rest, and say how many were skipped rather than
# failing the whole operation.
# ---------------------------------------------------------------------------


def _selected_mice(db_session, form) -> list:
    ids = [int(v) for v in form.getlist("selected_ids") if v.isdigit()]
    if not ids:
        return []
    return list(db_session.scalars(
        select(MouseRecord).where(MouseRecord.id.in_(ids))
    ).all())


def _report(changed: int, skipped: int, what: str) -> None:
    if changed:
        flash(f"{what} on {changed} {'mouse' if changed == 1 else 'mice'}."
              + (f" {skipped} skipped — not yours to edit." if skipped else ""),
              "success")
    elif skipped:
        flash(f"Nothing changed — {skipped} record(s) are not yours to edit.", "error")
    else:
        flash("Nothing was selected.", "error")


# Fields the bulk editor may set, and how to apply each one.
BULK_FIELDS = {
    "owner": "Owner",
    "status": "Status",
    "genotype": "Genotype",
    "cage_id": "Cage",
    "note": "Note",
    "date_of_death": "Date of death",
}


@app.route("/colony/mice/bulk-update", methods=["POST"])
@login_required
def bulk_update_mice():
    """Set one field to one value across the selection."""
    field = (request.form.get("field") or "").strip()
    value = (request.form.get("value") or "").strip()
    if field not in BULK_FIELDS:
        flash("Pick a field to set.", "error")
        return redirect(request.referrer or url_for("colony", view="mice"))

    changed = skipped = 0
    with SessionLocal() as db_session, audit.batch(
            db_session, "update",
            f"set {BULK_FIELDS[field].lower()} = {value or '(blank)'}", "mice") as batch_row:
        for mouse in _selected_mice(db_session, request.form):
            if not can_edit_mouse(mouse):
                skipped += 1
                continue
            if field == "cage_id":
                # Reuse the normal cage plumbing so "new" still allocates
                # and the cage's derived dates stay correct.
                mouse.cage = get_or_create_cage(db_session, value) if value else None
            elif field == "date_of_death":
                mouse.date_of_death = parse_date(value)
            elif field == "status":
                previous_status = mouse.status
                mouse.status = value
                apply_status_rules(mouse, previous_status)
            else:
                setattr(mouse, field, value)
            stamp_updated(mouse)
            changed += 1
        batch_row.record_count = changed
        db_session.commit()
    _report(changed, skipped, f"Set {BULK_FIELDS[field].lower()}")
    return redirect(request.referrer or url_for("colony", view="mice"))


@app.route("/colony/mice/bulk-experiment", methods=["POST"])
@login_required
def bulk_add_to_experiment():
    """Add the selection to an experiment, all in one treatment group.

    This is the "set up an experiment with N mice under the same
    manipulation" case: pick the mice, pick the experiment, name the group.
    """
    experiment_id = request.form.get("experiment_id")
    group = (request.form.get("treatment_group") or "").strip()
    if not (experiment_id or "").isdigit():
        flash("Pick an experiment.", "error")
        return redirect(request.referrer or url_for("colony", view="mice"))

    added = skipped = already = 0
    with SessionLocal() as db_session:
        exp = db_session.get(Experiment, int(experiment_id))
        if exp is None:
            flash("That experiment no longer exists.", "error")
            return redirect(request.referrer or url_for("colony", view="mice"))
        batch_ctx = audit.batch(db_session, "create",
                                f"add to experiment {exp.name}"
                                + (f" as {group}" if group else ""),
                                "experiment_mice")
        batch_row = batch_ctx.__enter__()
        existing = {em.mouse_id_fk for em in exp.memberships}
        for mouse in _selected_mice(db_session, request.form):
            if not can_edit_mouse(mouse):
                skipped += 1
                continue
            if mouse.id in existing:
                already += 1
                continue
            db_session.add(ExperimentMouse(
                experiment_id_fk=exp.id,
                mouse_id_fk=mouse.id,
                treatment_group=group,
            ))
            added += 1
        batch_row.record_count = added
        batch_ctx.__exit__(None, None, None)
        db_session.commit()
        name = exp.name
        exp_id = exp.id

    parts = [f"Added {added} {'mouse' if added == 1 else 'mice'} to {name}"]
    if group:
        parts.append(f"as “{group}”")
    if already:
        parts.append(f"({already} already in it)")
    if skipped:
        parts.append(f"— {skipped} skipped, not yours to edit")
    flash(" ".join(parts) + ".", "success" if added else "error")
    return redirect(url_for("experiment_detail", experiment_id=exp_id))


# ---------------------------------------------------------------------------
# Batch creation: one specification, many mice.
#
# Two ways in — type a prototype and a count, or upload a CSV — and both land
# in the same editable preview before anything is written. One confirm step,
# one validation path, one place where IDs are allocated.
#
# IDs are shown in the preview but allocated again at save time: the preview
# can sit on screen while someone else adds mice, and a stale block would
# collide on the unique index.
# ---------------------------------------------------------------------------

# Columns the preview grid understands, in display order.
BATCH_COLUMNS = [
    ("gender", "Sex", 70),
    ("transgene_1", "TG1", 120),
    ("transgene_2", "TG2", 120),
    ("transgene_3", "TG3", 120),
    ("transgene_4", "TG4", 120),
    ("genotype", "Genotype", 150),
    ("cage_id", "Cage", 90),
    ("cage_location", "Location", 110),
    ("owner", "Owner", 110),
    ("litter_id", "Litter", 90),
    ("date_of_birth", "DOB", 130),
    ("status", "Status", 110),
    ("note", "Note", 170),
]
BATCH_FIELDS = [key for key, _label, _width in BATCH_COLUMNS]
MAX_BATCH = 200


def _blank_row() -> dict:
    return {key: "" for key in BATCH_FIELDS}


def _rows_from_prototype(form) -> list[dict]:
    """N copies of the prototype, optionally split by sex.

    The sex split exists because "6 females and 6 males" is how litters and
    orders actually arrive, and making someone retype the prototype twice to
    get it would defeat the point.
    """
    prototype = {key: (form.get(key) or "").strip() for key in BATCH_FIELDS}
    females = max(0, _batch_int(form.get("count_female")))
    males = max(0, _batch_int(form.get("count_male")))
    plain = max(0, _batch_int(form.get("count")))

    rows: list[dict] = []
    if females or males:
        for _ in range(females):
            rows.append({**prototype, "gender": "F"})
        for _ in range(males):
            rows.append({**prototype, "gender": "M"})
    else:
        rows = [dict(prototype) for _ in range(plain or 1)]
    return rows[:MAX_BATCH]


def _rows_from_csv(upload) -> tuple[list[dict], list[str]]:
    """Parse an uploaded CSV into preview rows.

    Unknown columns are ignored rather than rejected — vendor exports carry
    all sorts of extra fields, and refusing the file over a stray column
    helps nobody.
    """
    import csv as _csv, io as _io

    raw = upload.read()
    try:
        text_data = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text_data = raw.decode("latin-1")

    reader = _csv.DictReader(_io.StringIO(text_data))
    rows, warnings = [], []
    aliases = {"sex": "gender", "dob": "date_of_birth", "cage": "cage_id",
               "litter": "litter_id", "notes": "note"}

    for index, raw_row in enumerate(reader, start=2):
        if index - 1 > MAX_BATCH:
            warnings.append(f"Only the first {MAX_BATCH} rows were loaded.")
            break
        row = _blank_row()
        for header, value in (raw_row or {}).items():
            if header is None:
                continue
            key = aliases.get(header.strip().lower(), header.strip().lower())
            if key in row:
                row[key] = (value or "").strip()
        if any(row.values()):
            rows.append(row)
    if not rows:
        warnings.append("No usable rows found in that file.")
    return rows, warnings


def _rows_from_grid(form) -> list[dict]:
    """Read back the edited preview grid (fields named rows-<i>-<key>)."""
    indexes = set()
    for key in form.keys():
        if key.startswith("rows-") and key.count("-") >= 2:
            _, index, _field = key.split("-", 2)
            if index.isdigit():
                indexes.add(int(index))

    rows = []
    for index in sorted(indexes):
        if form.get(f"rows-{index}-drop"):
            continue
        row = {key: (form.get(f"rows-{index}-{key}") or "").strip() for key in BATCH_FIELDS}
        if any(row.values()):
            rows.append(row)
    return rows[:MAX_BATCH]


def _batch_int(raw) -> int:
    try:
        return int(str(raw or "").strip())
    except ValueError:
        return 0


@app.route("/colony/mice/batch", methods=["GET"])
@login_required
def batch_mice():
    """The setup step: prototype + count, or a CSV."""
    with SessionLocal() as db_session:
        return render_template(
            "batch_mice.html",
            stage="setup",
            columns=BATCH_COLUMNS,
            rows=[],
            warnings=[],
            prototype=_blank_row() | {"owner": g.user.username, "status": "experiment"},
            dropdowns=dropdown_options_map(db_session),
            usernames=current_lab_usernames(db_session),
            strain_rows=db_session.scalars(
                select(StrainRecord).order_by(StrainRecord.strain_name)).all(),
            next_id=next_mouse_id(db_session),
            max_batch=MAX_BATCH,
        )


@app.route("/colony/mice/batch/preview", methods=["POST"])
@login_required
def batch_mice_preview():
    """Turn a prototype, a CSV or an edited grid into the preview."""
    warnings: list[str] = []
    upload = request.files.get("file")

    if upload is not None and upload.filename:
        rows, warnings = _rows_from_csv(upload)
    elif request.form.get("source") == "grid":
        rows = _rows_from_grid(request.form)
    else:
        rows = _rows_from_prototype(request.form)

    if not rows:
        flash("Nothing to preview — set a count or choose a file.", "error")
        return redirect(url_for("batch_mice"))

    with SessionLocal() as db_session:
        # Shown so you can see what you will get; re-allocated on save.
        proposed = reserve_mouse_ids(db_session, len(rows))
        return render_template(
            "batch_mice.html",
            stage="preview",
            columns=BATCH_COLUMNS,
            rows=rows,
            proposed_ids=proposed,
            warnings=warnings,
            prototype=_blank_row(),
            dropdowns=dropdown_options_map(db_session),
            usernames=current_lab_usernames(db_session),
            strain_rows=db_session.scalars(
                select(StrainRecord).order_by(StrainRecord.strain_name)).all(),
            next_id=proposed[0] if proposed else 0,
            max_batch=MAX_BATCH,
        )


@app.route("/colony/mice/batch/create", methods=["POST"])
@login_required
def batch_mice_create():
    """Write the previewed rows, with one contiguous block of IDs."""
    rows = _rows_from_grid(request.form)
    if not rows:
        flash("Nothing to create.", "error")
        return redirect(url_for("batch_mice"))

    created = 0
    with SessionLocal() as db_session, audit.batch(
            db_session, "create", f"add {len(rows)} mice in bulk", "mice") as batch_row:
        ids = reserve_mouse_ids(db_session, len(rows))

        # Resolve "new" once for the whole batch. Six littermates arriving
        # together belong in one cage; allocating a cage per row would make
        # the common case the wrong one, and typing an explicit number per
        # row still splits them however you like.
        shared_new_cage = None
        if any((row.get("cage_id") or "").strip().lower() == "new" for row in rows):
            shared_new_cage = get_or_create_cage(db_session, "new").cage_id

        for row, mouse_id in zip(rows, ids):
            if shared_new_cage and (row.get("cage_id") or "").strip().lower() == "new":
                row = {**row, "cage_id": shared_new_cage}
            mouse = MouseRecord(mouse_id=mouse_id, owner=row.get("owner", ""))
            # Reuse the single-record path so cage allocation, litter
            # linking and DOB inheritance behave identically.
            populate_mouse_from_form(
                db_session, mouse, ImmutableMultiDict(row),
                preserve_owner_on_transfer=False)
            if not mouse.owner and g.user is not None:
                mouse.owner = g.user.username
            sync_mouse_transgenes(mouse, [
                row.get("transgene_1", ""), row.get("transgene_2", ""),
                row.get("transgene_3", ""), row.get("transgene_4", ""),
            ])
            if row.get("genotype"):
                mouse.genotype = row["genotype"]
            db_session.add(mouse)
            created += 1
        batch_row.record_count = created
        batch_id = batch_row.id
        db_session.commit()
        first, last = (ids[0], ids[-1]) if ids else (0, 0)

    flash(Markup(
        f"Created {created} mice — #{first} to #{last}. "
        f'<a href="{url_for("batches_view")}">Undo</a>'), "success")
    return redirect(url_for("colony", view="mice"))


@app.route("/colony/mice/export")
@login_required
def export_mice():
    export_format = request.args.get("format", "csv")
    context = colony_context("mice")
    if export_format == "pdf":
        return render_template("print_mice.html", mouse_rows=context["mouse_rows"], printed_on=date.today().isoformat())
    payload, filename, mimetype = export_mouse_rows(context["mouse_rows"], export_format)
    return Response(
        payload,
        mimetype=mimetype,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/colony/cages/create", methods=["POST"])
@login_required
def create_cage():
    with SessionLocal() as db_session:
        # A blank ID means "next free one" (get_or_create_cage allocates it).
        cage = get_or_create_cage(db_session, request.form.get("cage_id", "").strip())
        cage.cage_location = request.form.get("cage_location", "").strip()
        cage.purpose = request.form.get("purpose", "").strip()
        cage.notes = request.form.get("notes", "").strip()
        cage.date_give_birth = parse_date(request.form.get("date_give_birth"))
        cage.card_id = request.form.get("card_id", "").strip()
        cage.genotype_summary = request.form.get("genotype_summary", "").strip()
        cage.location_detail = request.form.get("location_detail", "").strip()
        cage.room = request.form.get("room", "").strip()
        if not cage.owner and g.user:
            cage.owner = g.user.username
        if "rack_id" in request.form:
            error = apply_cage_position(db_session, cage, request.form.get("rack_id"), request.form.get("position"))
            if error:
                flash(f"Cage {cage.cage_id} was created but not placed: {error}", "error")
        db_session.commit()
    return autosave_response("cages")


# ---- Cage racks -------------------------------------------------------------
# A cage sits at (rack_row, rack_col) of its rack; the rack's naming scheme
# (app/positions.py) decides what that position is called: D7, 4-7, 37…


def rack_naming_payload(rack) -> dict:
    """What rack-grid.js needs to label a rack's rows, columns and cells."""
    return positions.scheme(rack.naming)


def _mouse_rack_from_form(db_session, rack, form) -> str | None:
    name = (form.get("name") or "").strip()
    if not name:
        return "A rack needs a name."
    clash = db_session.scalar(select(MouseRack.id).where(
        func.lower(MouseRack.name) == name.lower(), MouseRack.id != (rack.id or 0)))
    if clash:
        return f"There is already a rack called {name}."
    rack.name = name
    rack.rows = max(1, min(26, int(form.get("rows") or 8)))
    rack.cols = max(1, min(40, int(form.get("cols") or 10)))
    rack.room = (form.get("room") or "").strip()
    rack.naming = json.dumps(positions.scheme_from_form(form))
    return None


def cage_state(cage) -> dict | None:
    """A cage's shared fields, returned after a save so the sheet can update
    every row of that cage at once."""
    if cage is None:
        return None
    return {"cage_id": cage.cage_id, "rack_id": cage.rack_id_fk or "",
            "rack_name": cage.rack.name if cage.rack else "",
            "position": cage_position_label(cage), "location": cage.cage_location}


def apply_cage_position(db_session, cage, rack_raw, position_raw) -> str | None:
    """Put `cage` in the rack and position a person typed; return an error
    message instead of guessing. An empty rack takes the cage out of racks;
    a rack with no position keeps it in that rack but unplaced. Typing a
    position that another cage holds is refused rather than moving that
    cage (dragging on the grid is how you swap)."""
    rack_raw = str(rack_raw or "").strip()
    position_raw = str(position_raw or "").strip()
    if not rack_raw:
        cage.rack_id_fk = cage.rack_row = cage.rack_col = None
        return None
    rack = db_session.get(MouseRack, int(rack_raw)) if rack_raw.isdigit() else db_session.scalar(
        select(MouseRack).where(func.lower(MouseRack.name) == rack_raw.lower()))
    if rack is None:
        return f"There is no rack called {rack_raw}."
    if not position_raw:
        cage.rack_id_fk, cage.rack_row, cage.rack_col = rack.id, None, None
        return None
    cell = positions.parse(position_raw, rack.naming, rack.rows, rack.cols)
    if cell is None:
        first = positions.label(1, 1, rack.naming, rack.cols)
        last = positions.label(rack.rows, rack.cols, rack.naming, rack.cols)
        return f"“{position_raw}” is not a position in rack {rack.name} ({first}–{last})."
    holder = db_session.scalar(select(CageRecord).where(
        CageRecord.rack_id_fk == rack.id, CageRecord.rack_row == cell[0],
        CageRecord.rack_col == cell[1], CageRecord.id != (cage.id or 0)))
    if holder is not None:
        name = positions.label(*cell, rack.naming, rack.cols)
        return f"{rack.name} · {name} already holds cage {holder.cage_id}. Drag on the rack grid to swap."
    cage.rack_id_fk, (cage.rack_row, cage.rack_col) = rack.id, cell
    return None


def cage_position_label(cage) -> str:
    """"D7" under the cage's rack scheme, or "" when not placed."""
    if cage is None or cage.rack is None:
        return ""
    return positions.label(cage.rack_row, cage.rack_col, cage.rack.naming, cage.rack.cols)


@app.route("/colony/racks/save", methods=["POST"])
@login_required
def save_mouse_rack():
    with SessionLocal() as db_session:
        rack_id = request.form.get("id", "").strip()
        rack = db_session.get(MouseRack, int(rack_id)) if rack_id.isdigit() else MouseRack(name="")
        if rack is None:
            flash("That rack no longer exists.", "error")
            return redirect(url_for("colony", view="cages"))
        error = _mouse_rack_from_form(db_session, rack, request.form)
        if error:
            flash(error, "error")
            return redirect(url_for("colony", view="cages"))
        if rack.id is None:
            db_session.add(rack)
        db_session.commit()
        flash(f"Saved rack {rack.name}.", "success")
    return redirect(url_for("colony", view="cages"))


@app.route("/colony/racks/<int:rack_id>/delete", methods=["POST"])
@login_required
def delete_mouse_rack(rack_id: int):
    """Delete a rack. Its cages are kept, just unplaced."""
    with SessionLocal() as db_session:
        rack = db_session.get(MouseRack, rack_id)
        if rack is not None:
            name = rack.name
            for cage in db_session.scalars(select(CageRecord).where(CageRecord.rack_id_fk == rack.id)):
                cage.rack_id_fk = cage.rack_row = cage.rack_col = None
            db_session.delete(rack)
            db_session.commit()
            flash(f"Deleted rack {name}. Its cages are now unplaced.", "success")
    return redirect(url_for("colony", view="cages"))


@app.route("/colony/cages/<int:cage_row_id>/place", methods=["POST"])
@login_required
def place_cage(cage_row_id: int):
    """Move a cage on the rack grid; answers JSON. Dropping onto an occupied
    position swaps the two cages; an empty rack id unplaces the cage."""
    with SessionLocal() as db_session:
        cage = db_session.get(CageRecord, cage_row_id)
        if cage is None:
            return jsonify({"ok": False, "error": "That cage no longer exists."}), 404
        if not can_edit_cage(cage):
            return jsonify({"ok": False, "error": access.reason_denied(cage)}), 403
        rack_id = request.form.get("rack_id", "").strip()
        if not rack_id:
            # Dropped on the Unplaced tray: out of the rack altogether.
            cage.rack_id_fk = cage.rack_row = cage.rack_col = None
            db_session.commit()
            return jsonify({"ok": True})
        rack = db_session.get(MouseRack, int(rack_id)) if rack_id.isdigit() else None
        try:
            row, col = int(request.form.get("row", "")), int(request.form.get("col", ""))
        except ValueError:
            return jsonify({"ok": False, "error": "Missing row or column."}), 400
        if rack is None or not (1 <= row <= rack.rows and 1 <= col <= rack.cols):
            return jsonify({"ok": False, "error": "That position is not in the rack."}), 400
        holder = db_session.scalar(select(CageRecord).where(
            CageRecord.rack_id_fk == rack.id, CageRecord.rack_row == row,
            CageRecord.rack_col == col, CageRecord.id != cage.id))
        if holder is not None:
            if not can_edit_cage(holder):
                return jsonify({"ok": False, "error": f"That position holds cage {holder.cage_id}, which you may not move."}), 403
            holder.rack_id_fk, holder.rack_row, holder.rack_col = cage.rack_id_fk, cage.rack_row, cage.rack_col
        cage.rack_id_fk, cage.rack_row, cage.rack_col = rack.id, row, col
        db_session.commit()
    return jsonify({"ok": True})


def mouse_rack_payload(db_session, cages) -> dict:
    """Racks and the cages in scope, for the rack grid."""
    racks = mouse_racks(db_session)
    items = []
    for cage in cages:
        live = [m for m in cage.mice if mouse_is_active(m)]
        strains = sorted({(m.transgene_1 or "").strip() for m in live if (m.transgene_1 or "").strip()})
        sexes = "".join(m.gender[:1] for m in live if m.gender in ("F", "M"))
        where = f"{cage.rack.name} · {cage_position_label(cage)}" if cage.rack and cage.rack_row else ""
        items.append({
            "id": cage.id,
            "label": cage.cage_id,
            "sub": cage.genotype_summary or ", ".join(strains[:2]) or cage.purpose or "",
            "badge": f"{len(live)}" if live else "",
            "tone": normalize_status(cage.purpose) if live else "inactive",
            "rack": cage.rack_id_fk,
            "row": cage.rack_row,
            "col": cage.rack_col,
            "title": "\n".join(filter(None, [
                f"Cage {cage.cage_id}" + (f" · {where}" if where else ""),
                cage.purpose, f"{len(live)} live ({sexes.count('F')}F {sexes.count('M')}M)" if live else "empty",
                ", ".join(str(m.mouse_id) for m in live[:12]),
            ])),
            "search": " ".join([cage.cage_id, cage.cage_location, cage.purpose, cage.owner,
                                cage.genotype_summary, *strains, *(str(m.mouse_id) for m in live)]).lower(),
            "edit": {"data-record-edit": "cage-dialog", "data-record-payload": json.dumps({
                "id": cage.id, "_label": cage.cage_id, "_locked": not can_edit_cage(cage),
                "rack_id": cage.rack_id_fk or "", "position": cage_position_label(cage),
                "cage_location": cage.cage_location, "purpose": cage.purpose, "room": cage.room,
                "card_id": cage.card_id, "genotype_summary": cage.genotype_summary,
                "location_detail": cage.location_detail, "notes": cage.notes,
                "date_give_birth": cage.date_give_birth.isoformat() if cage.date_give_birth else "",
            })},
        })
    return {
        "racks": [{"id": r.id, "name": r.name, "rows": r.rows, "cols": r.cols,
                   "naming": rack_naming_payload(r),
                   "edit": {"data-record-payload": json.dumps({
                       "id": r.id, "_label": r.name, "name": r.name, "rows": r.rows,
                       "cols": r.cols, "room": r.room,
                       **{f"naming_{k}": v for k, v in rack_naming_payload(r).items()}})}} for r in racks],
        "items": items,
        "create": {"attrs": {"data-record-edit": "cage-dialog"}, "payload": {"purpose": "Experiments"},
                   "rack_field": "rack_id", "text_field": "position"},
    }


@app.route("/colony/cages/<int:cage_row_id>/update", methods=["POST"])
@login_required
def update_cage(cage_row_id: int):
    with SessionLocal() as db_session:
        cage = db_session.get(CageRecord, cage_row_id)
        if cage is None:
            return autosave_response("cages")
        blocked = deny(cage, "cages")
        if blocked:
            return blocked
        cage.cage_location = request.form.get("cage_location", "").strip()
        cage.purpose = request.form.get("purpose", "").strip()
        cage.notes = request.form.get("notes", "").strip()
        cage.date_give_birth = parse_date(request.form.get("date_give_birth"))
        cage.card_id = request.form.get("card_id", "").strip()
        cage.genotype_summary = request.form.get("genotype_summary", "").strip()
        cage.location_detail = request.form.get("location_detail", "").strip()
        cage.room = request.form.get("room", "").strip()
        if "rack_id" in request.form and form_changed(request.form, "rack_id", "position"):
            error = apply_cage_position(db_session, cage, request.form.get("rack_id"), request.form.get("position"))
            if error:
                db_session.rollback()
                flash(error, "error")
                return autosave_response("cages")
        db_session.commit()
        state = cage_state(cage)
    result = autosave_response("cages")
    if request.headers.get("X-Autosave") == "1" and not isinstance(result, tuple):
        return jsonify({"ok": True, "cage": state})
    return result


@app.route("/colony/cages/<int:cage_row_id>/add-mouse", methods=["POST"])
@login_required
def add_mouse_from_cage(cage_row_id: int):
    with SessionLocal() as db_session:
        cage = db_session.get(CageRecord, cage_row_id)
        if cage is None:
            return redirect(url_for("colony", view="cages"))
        blocked = deny(cage, "cages")
        if blocked:
            return blocked
        requested_mouse_id = request.form.get("mouse_id", "").strip()
        if not requested_mouse_id.isdigit():
            flash("Enter an existing numeric Mouse_ID.", "error")
            return redirect(url_for("colony", view="cages"))
        mouse = db_session.scalar(select(MouseRecord).where(MouseRecord.mouse_id == int(requested_mouse_id)))
        if mouse is None:
            flash(f"Mouse_ID {requested_mouse_id} was not found.", "error")
            return redirect(url_for("colony", view="cages"))
        mouse.cage = cage
        db_session.commit()
    return redirect(url_for("colony", view="cages"))


@app.route("/colony/cages/<int:cage_row_id>/give-birth", methods=["POST"])
@login_required
def cage_give_birth(cage_row_id: int):
    with SessionLocal() as db_session:
        cage = db_session.get(CageRecord, cage_row_id)
        blocked = deny(cage, "cages")
        if blocked:
            return blocked
        if cage is not None:
            cage.date_give_birth = date.today()
            db_session.commit()
    return redirect(url_for("colony", view="cages"))


@app.route("/colony/cages/<int:cage_row_id>/genotyping", methods=["POST"])
@login_required
def cage_genotyping(cage_row_id: int):
    with SessionLocal() as db_session:
        cage = db_session.get(CageRecord, cage_row_id)
        if cage is None:
            return redirect(url_for("colony", view="cages"))
        blocked = deny(cage, "cages")
        if blocked:
            return blocked
        total_pups = int(request.form.get("total_pups", "0") or "0")
        father_info = request.form.get("father_info", "").strip()
        mother_info = request.form.get("mother_info", "").strip()
        litter = get_or_create_litter(db_session, generate_litter_id(db_session, cage), cage.date_give_birth or date.today())
        litter.father_info = father_info
        litter.mother_info = mother_info
        litter.total_pups = total_pups
        litter.cohort_name = f"Cage {cage.cage_id}"
        litter.notes = f"Generated by genotyping for cage {cage.cage_id}."
        for _ in range(total_pups):
            mouse = MouseRecord(
                mouse_id=next_mouse_id(db_session),
                status="geno",
                owner=g.user.username,
                cage=cage,
                litter=litter,
            )
            db_session.add(mouse)
            db_session.flush()
        db_session.commit()
    return redirect(url_for("colony", view="cages"))


@app.route("/colony/cages/<int:cage_row_id>/wean", methods=["POST"])
@login_required
def cage_wean(cage_row_id: int):
    with SessionLocal() as db_session:
        cage = db_session.get(CageRecord, cage_row_id)
        blocked = deny(cage, "cages")
        if blocked:
            return blocked
        if cage is not None:
            cage.date_give_birth = None
            db_session.commit()
    return redirect(url_for("colony", view="cages"))


@app.route("/colony/cages/<int:cage_row_id>/wean-distribute", methods=["POST"])
@login_required
def cage_wean_distribute(cage_row_id: int):
    """Wean the source cage and distribute its pups to new or existing cages.

    Form arrays (one entry per UI row):
      mouse_ids[]   : comma-separated Mouse_IDs to move
      gender[]      : M / F / Unknown — applied to those mice
      cage_id[]     : existing Cage_ID; if filled, mice go there (card_id ignored)
      card_id[]     : if cage_id[] empty, a fresh cage is created with this card label
    Empty rows are skipped. Mice not listed stay in the source cage.
    """
    mouse_ids_field = request.form.getlist("mouse_ids[]")
    genders_field = request.form.getlist("gender[]")
    cage_ids_field = request.form.getlist("cage_id[]")
    card_ids_field = request.form.getlist("card_id[]")
    rows = list(zip(mouse_ids_field, genders_field, cage_ids_field, card_ids_field))

    moved_count = 0
    skipped_ids: list[str] = []
    source_cage_label = ""

    with SessionLocal() as db_session:
        source_cage = db_session.get(CageRecord, cage_row_id)
        if source_cage is None:
            flash("Cage not found.", "error")
            return redirect(url_for("colony", view="cages"))
        blocked = deny(source_cage, "cages")
        if blocked:
            return blocked
        source_cage_label = source_cage.cage_id

        for mouse_ids_str, gender_raw, cage_id_input, card_id_input in rows:
            mouse_ids_str = (mouse_ids_str or "").strip()
            if not mouse_ids_str:
                continue
            mouse_id_list: list[int] = []
            for token in mouse_ids_str.replace(";", ",").split(","):
                token = token.strip()
                if token.isdigit():
                    mouse_id_list.append(int(token))
                elif token:
                    skipped_ids.append(token)
            if not mouse_id_list:
                continue

            cage_id_input = (cage_id_input or "").strip()
            card_id_input = (card_id_input or "").strip()
            gender_value = (gender_raw or "").strip()

            if cage_id_input:
                target_cage = db_session.scalar(select(CageRecord).where(CageRecord.cage_id == cage_id_input))
                if target_cage is None:
                    target_cage = CageRecord(cage_id=cage_id_input)
                    db_session.add(target_cage)
                    db_session.flush()
            else:
                target_cage = CageRecord(cage_id=next_cage_id(db_session), card_id=card_id_input)
                db_session.add(target_cage)
                db_session.flush()

            for mouse_id_value in mouse_id_list:
                mouse = db_session.scalar(select(MouseRecord).where(MouseRecord.mouse_id == mouse_id_value))
                if mouse is None:
                    skipped_ids.append(str(mouse_id_value))
                    continue
                mouse.cage = target_cage
                if gender_value:
                    mouse.gender = gender_value
                moved_count += 1

        source_cage.date_give_birth = None
        db_session.commit()

    if moved_count:
        flash(f"Distributed {moved_count} mice and weaned cage {source_cage_label}.", "success")
    else:
        flash(f"Cage {source_cage_label} weaned (no mice were moved).", "success")
    if skipped_ids:
        flash(f"Skipped IDs (not numeric or not found): {', '.join(skipped_ids)}.", "error")
    return redirect(url_for("colony", view="cages"))


@app.route("/colony/litters/create", methods=["POST"])
@login_required
def create_litter():
    with SessionLocal() as db_session:
        litter = get_or_create_litter(db_session, request.form["litter_id"].strip(), parse_date(request.form.get("date_of_birth")))
        litter.cohort_name = request.form.get("cohort_name", "").strip()
        litter.notes = request.form.get("notes", "").strip()
        db_session.commit()
    return redirect(url_for("colony", view="litters"))


@app.route("/colony/litters/<int:litter_row_id>/update", methods=["POST"])
@login_required
def update_litter(litter_row_id: int):
    with SessionLocal() as db_session:
        litter = db_session.get(LitterRecord, litter_row_id)
        if litter is None:
            return autosave_response("litters")
        litter.date_of_birth = parse_date(request.form.get("date_of_birth"))
        litter.cohort_name = request.form.get("cohort_name", "").strip()
        litter.notes = request.form.get("notes", "").strip()
        db_session.commit()
    return autosave_response("litters")


@app.route("/colony/litters/<int:litter_row_id>/add-existing-mouse", methods=["POST"])
@login_required
def add_existing_mouse_to_litter(litter_row_id: int):
    with SessionLocal() as db_session:
        litter = db_session.get(LitterRecord, litter_row_id)
        if litter is None:
            return redirect(url_for("colony", view="litters"))
        requested_mouse_id = request.form.get("mouse_id", "").strip()
        if not requested_mouse_id.isdigit():
            flash("Enter an existing numeric Mouse_ID.", "error")
            return redirect(url_for("colony", view="litters"))
        mouse = db_session.scalar(select(MouseRecord).where(MouseRecord.mouse_id == int(requested_mouse_id)))
        if mouse is None:
            flash(f"Mouse_ID {requested_mouse_id} was not found.", "error")
            return redirect(url_for("colony", view="litters"))
        mouse.litter = litter
        db_session.commit()
    return redirect(url_for("colony", view="litters"))


@app.route("/colony/litters/<int:litter_row_id>/add-mouse", methods=["POST"])
@login_required
def add_mouse_from_litter(litter_row_id: int):
    with SessionLocal() as db_session:
        litter = db_session.get(LitterRecord, litter_row_id)
        if litter is None:
            return redirect(url_for("colony", view="litters"))
        mouse = MouseRecord(mouse_id=next_mouse_id(db_session), owner=request.form.get("owner", g.user.username))
        populate_mouse_from_form(db_session, mouse, request.form, preserve_owner_on_transfer=False)
        mouse.litter = litter
        db_session.add(mouse)
        db_session.commit()
    return redirect(url_for("colony", view="litters"))


@app.route("/colony/strains/create", methods=["POST"])
@login_required
def create_strain():
    with SessionLocal() as db_session:
        strain_name = request.form["strain_name"].strip()
        existing = db_session.scalar(select(StrainRecord).where(StrainRecord.strain_name == strain_name))
        if existing is None and strain_name:
            db_session.add(
                StrainRecord(
                    strain_number=request.form.get("strain_number", "").strip(),
                    strain_name=strain_name,
                    strain_background=request.form.get("strain_background", "").strip(),
                    supplier=request.form.get("supplier", "").strip(),
                    description=request.form.get("description", "").strip(),
                )
            )
            db_session.commit()
    return redirect(url_for("colony", view="strains"))


@app.route("/colony/strains/<int:strain_row_id>/update", methods=["POST"])
@login_required
def update_strain(strain_row_id: int):
    with SessionLocal() as db_session:
        strain = db_session.get(StrainRecord, strain_row_id)
        if strain is None:
            return autosave_response("strains")
        new_name = request.form.get("strain_name", "").strip()
        if new_name and new_name != strain.strain_name:
            conflict = db_session.scalar(
                select(StrainRecord).where(StrainRecord.strain_name == new_name, StrainRecord.id != strain.id)
            )
            if conflict is None:
                strain.strain_name = new_name
        strain.strain_number = request.form.get("strain_number", "").strip()
        strain.strain_background = request.form.get("strain_background", "").strip()
        strain.supplier = request.form.get("supplier", "").strip()
        strain.description = request.form.get("description", "").strip()
        db_session.commit()
    return autosave_response("strains")


@app.route("/colony/options/create", methods=["POST"])
@login_required
def create_option():
    field_name = request.form["field_name"].strip()
    option_value = request.form["option_value"].strip()
    with SessionLocal() as db_session:
        existing = db_session.scalar(
            select(DropdownOption).where(
                DropdownOption.field_name == field_name,
                DropdownOption.option_value == option_value,
            )
        )
        if existing is None and field_name and option_value:
            db_session.add(DropdownOption(field_name=field_name, option_value=option_value))
            db_session.commit()
    return redirect(url_for("colony", view="settings"))


@app.route("/colony/options/<int:option_id>/update", methods=["POST"])
@login_required
def update_option(option_id: int):
    new_value = request.form.get("option_value", "").strip()
    with SessionLocal() as db_session:
        option = db_session.get(DropdownOption, option_id)
        if option is None or not new_value:
            return autosave_response("settings")
        duplicate = db_session.scalar(
            select(DropdownOption).where(
                DropdownOption.field_name == option.field_name,
                DropdownOption.option_value == new_value,
                DropdownOption.id != option.id,
            )
        )
        if duplicate is None:
            option.option_value = new_value
            db_session.commit()
    return autosave_response("settings")


@app.route("/colony/options/<int:option_id>/delete", methods=["POST"])
@login_required
def delete_option(option_id: int):
    with SessionLocal() as db_session:
        option = db_session.get(DropdownOption, option_id)
        if option is not None:
            db_session.delete(option)
            db_session.commit()
    return redirect(url_for("colony", view="settings"))


# ---------------------------------------------------------------------------
# Orders and samples now live in the lab inventory engine (inventory_routes).
# The old addresses keep working and land on the first inventory of that kind.
# ---------------------------------------------------------------------------


def _inventory_redirect(kind: str):
    from . import inventory_service as inventories
    with SessionLocal() as db_session:
        module = inventories.first_of_kind(db_session, kind)
        key = module.key if module else None
    if key is None:
        flash(f"There is no {kind} inventory yet. Add one from Add database.", "info")
        return redirect(url_for("organisms.index"))
    return redirect(url_for("inventory.module", key=key))


@app.route("/orders")
@login_required
def orders():
    return _inventory_redirect("orders")


@app.route("/samples")
@login_required
def samples():
    return _inventory_redirect("samples")


@app.route("/calendar", methods=["GET"])
@login_required
def calendar():
    """Calendar page — TOAST UI Calendar mount + custom list view.
    Data is fetched async from /calendar/events.json so the page itself is light."""
    with SessionLocal() as db_session:
        animals = db_session.scalars(select(AnimalRecord).order_by(AnimalRecord.animal_id)).all()
    return render_template("calendar.html", animals=animals, task_statuses=TASK_STATUS_OPTIONS)


def _serialize_calendar_event(e: CalendarEvent) -> dict:
    """Translate a CalendarEvent row into TOAST UI Calendar's schedule shape."""
    if e.start_at and e.end_at:
        start_iso, end_iso = e.start_at.isoformat(), e.end_at.isoformat()
        is_all_day = bool(e.is_all_day)
    else:
        d = e.event_date
        start_iso = datetime.combine(d, datetime.min.time()).isoformat()
        end_iso = datetime.combine(d, datetime.max.time()).isoformat()
        is_all_day = True
    return {
        "id": f"event-{e.id}",
        "kind": "event",
        "calendarId": "events",
        "title": e.title or "(untitled)",
        "category": "allday" if is_all_day else "time",
        "isAllday": is_all_day,
        "start": start_iso,
        "end": end_iso,
        "backgroundColor": e.color or "#7c3aed",
        "borderColor": e.color or "#7c3aed",
        "body": e.description or "",
        "raw": {
            "rowId": e.id,
            "owner": e.owner or "",
            "animalId": e.animal_id_fk,
            "eventType": e.event_type or "",
        },
    }


def _serialize_task(t: TaskItem) -> dict:
    """Translate a TaskItem row into TOAST UI Calendar's schedule shape, with
    extra metadata our custom renderer uses to draw the done-checkbox."""
    if t.start_at and t.end_at:
        start_iso, end_iso = t.start_at.isoformat(), t.end_at.isoformat()
        is_all_day = False
    elif t.due_date:
        d = t.due_date
        start_iso = datetime.combine(d, datetime.min.time()).isoformat()
        end_iso = datetime.combine(d, datetime.max.time()).isoformat()
        is_all_day = True
    else:
        # No date at all → put it on today, all-day, so it doesn't get lost.
        d = date.today()
        start_iso = datetime.combine(d, datetime.min.time()).isoformat()
        end_iso = datetime.combine(d, datetime.max.time()).isoformat()
        is_all_day = True
    is_done = bool(t.done_at) or (t.status or "").lower() in ("done", "completed", "closed")
    return {
        "id": f"task-{t.id}",
        "kind": "task",
        "calendarId": "tasks",
        "title": t.title or "(untitled)",
        "category": "task",  # TOAST UI native task category — shows in task strip
        "isAllday": is_all_day,
        "start": start_iso,
        "end": end_iso,
        "backgroundColor": t.color or ("#94a3b8" if is_done else "#0ea5e9"),
        "borderColor": t.color or ("#94a3b8" if is_done else "#0ea5e9"),
        "body": t.notes or "",
        "raw": {
            "rowId": t.id,
            "owner": t.owner or "",
            "status": t.status or "todo",
            "done": is_done,
            "priority": t.priority or "medium",
        },
    }


@app.route("/calendar/events.json")
@login_required
def calendar_events_json():
    """Unified feed of CalendarEvent + TaskItem rows for the calendar view.
    Optional ?start=&end= ISO bounds let TOAST UI fetch only the visible window;
    we pad ±1 month to keep month-view scrolling snappy without re-fetching."""
    from datetime import datetime as _dt
    start = request.args.get("start")
    end = request.args.get("end")

    def _parse_iso(v):
        if not v:
            return None
        try:
            return _dt.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return None

    start_dt = _parse_iso(start)
    end_dt = _parse_iso(end)

    with SessionLocal() as db_session:
        ev_q = select(CalendarEvent)
        tk_q = select(TaskItem)
        if start_dt:
            ev_q = ev_q.where(CalendarEvent.event_date >= start_dt.date())
            # Tasks may have no due_date; only filter rows that have one.
            tk_q = tk_q.where(
                (TaskItem.due_date.is_(None)) | (TaskItem.due_date >= start_dt.date())
            )
        if end_dt:
            ev_q = ev_q.where(CalendarEvent.event_date <= end_dt.date())
            tk_q = tk_q.where(
                (TaskItem.due_date.is_(None)) | (TaskItem.due_date <= end_dt.date())
            )
        events = db_session.scalars(ev_q.order_by(CalendarEvent.event_date)).all()
        tasks_ = db_session.scalars(tk_q.order_by(TaskItem.due_date)).all()

        # Auto-derived items from colony / experiment tables (weaning,
        # genotyping, sac threshold, experiment start/end).
        auto_items = derive_auto_calendar_items(db_session, start_dt, end_dt)

        # External subscriptions (ICS + Google) — owner-scoped for now.
        owner = g.user.username if g.user else ""
        subs = db_session.scalars(
            select(CalendarSubscription)
            .where(CalendarSubscription.owner == owner)
            .where(CalendarSubscription.enabled == True)  # noqa: E712
        ).all()
        sub_items: list[dict] = []
        for sub in subs:
            sub_items.extend(fetch_ics_subscription(sub, db_session))

        # Google Calendar events (if user connected) — Pass 3 attaches a fetcher here.
        google_items: list[dict] = []
        try:
            from .services import fetch_google_calendar_items  # optional, may not exist yet
            for link in db_session.scalars(
                select(GoogleCalendarLink)
                .where(GoogleCalendarLink.owner == owner)
                .where(GoogleCalendarLink.enabled == True)  # noqa: E712
            ).all():
                google_items.extend(fetch_google_calendar_items(link, db_session, start_dt, end_dt))
        except ImportError:
            pass
        except Exception as exc:  # don't break the feed for transient Google errors
            app.logger.warning("Google Calendar fetch failed: %s", exc)

        return jsonify({
            "ok": True,
            "items": [_serialize_calendar_event(e) for e in events]
            + [_serialize_task(t) for t in tasks_]
            + auto_items
            + sub_items
            + google_items,
        })


# ---------------------------------------------------------------------------
# Calendar subscriptions (ICS) — CRUD
# ---------------------------------------------------------------------------


@app.route("/calendar/subscriptions", methods=["GET", "POST"])
@login_required
def calendar_subscriptions():
    """GET → list current user's subscriptions. POST → create a new one."""
    owner = g.user.username if g.user else ""
    with SessionLocal() as db_session:
        if request.method == "POST":
            payload = request.get_json(silent=True) or {}
            name = (payload.get("name") or "").strip() or "Subscription"
            url = (payload.get("url") or "").strip()
            color = (payload.get("color") or "#10b981").strip()
            if not url:
                return jsonify({"ok": False, "error": "url required"}), 400
            # Allow webcal:// URLs — most calendars publish their iCal feed
            # with that scheme; swap to https for urllib.
            if url.startswith("webcal://"):
                url = "https://" + url[len("webcal://"):]
            sub = CalendarSubscription(owner=owner, name=name, url=url, color=color, enabled=True)
            db_session.add(sub)
            db_session.commit()
            # Eagerly fetch once so the user sees instant results.
            items = fetch_ics_subscription(sub, db_session, force=True)
            return jsonify({
                "ok": True,
                "subscription": {
                    "id": sub.id, "name": sub.name, "url": sub.url, "color": sub.color,
                    "enabled": sub.enabled, "last_error": sub.last_error,
                    "last_fetched_at": sub.last_fetched_at.isoformat() if sub.last_fetched_at else None,
                    "event_count": len(items),
                },
            })

        subs = db_session.scalars(
            select(CalendarSubscription).where(CalendarSubscription.owner == owner).order_by(CalendarSubscription.created_at)
        ).all()
        return jsonify({
            "ok": True,
            "subscriptions": [
                {
                    "id": s.id, "name": s.name, "url": s.url, "color": s.color,
                    "enabled": s.enabled, "last_error": s.last_error,
                    "last_fetched_at": s.last_fetched_at.isoformat() if s.last_fetched_at else None,
                }
                for s in subs
            ],
        })


@app.route("/calendar/subscriptions/<int:sub_id>", methods=["POST"])
@login_required
def calendar_subscription_update(sub_id: int):
    """Update a subscription (toggle enabled, rename, recolor, change URL)."""
    owner = g.user.username if g.user else ""
    payload = request.get_json(silent=True) or {}
    with SessionLocal() as db_session:
        sub = db_session.get(CalendarSubscription, sub_id)
        if sub is None or sub.owner != owner:
            return jsonify({"ok": False}), 404
        if "name" in payload: sub.name = (payload["name"] or "").strip() or sub.name
        if "color" in payload: sub.color = payload["color"] or sub.color
        if "url" in payload and payload["url"]:
            new_url = payload["url"].strip()
            if new_url.startswith("webcal://"):
                new_url = "https://" + new_url[len("webcal://"):]
            sub.url = new_url
            sub.cached_payload = ""  # invalidate cache on URL change
        if "enabled" in payload: sub.enabled = bool(payload["enabled"])
        db_session.commit()
        return jsonify({"ok": True})


@app.route("/calendar/subscriptions/<int:sub_id>/refresh", methods=["POST"])
@login_required
def calendar_subscription_refresh(sub_id: int):
    """Force a re-fetch of one subscription, bypassing the 10-min cache."""
    owner = g.user.username if g.user else ""
    with SessionLocal() as db_session:
        sub = db_session.get(CalendarSubscription, sub_id)
        if sub is None or sub.owner != owner:
            return jsonify({"ok": False}), 404
        items = fetch_ics_subscription(sub, db_session, force=True)
        return jsonify({"ok": True, "event_count": len(items), "last_error": sub.last_error})


@app.route("/calendar/subscriptions/<int:sub_id>/delete", methods=["POST"])
@login_required
def calendar_subscription_delete(sub_id: int):
    owner = g.user.username if g.user else ""
    with SessionLocal() as db_session:
        sub = db_session.get(CalendarSubscription, sub_id)
        if sub is None or sub.owner != owner:
            return jsonify({"ok": False}), 404
        db_session.delete(sub)
        db_session.commit()
        return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Google Calendar OAuth
# ---------------------------------------------------------------------------


def _google_redirect_uri() -> str:
    return url_for("calendar_google_callback", _external=True)


@app.route("/calendar/google/status")
@login_required
def calendar_google_status():
    """Tell the UI whether server-side OAuth is configured and whether THIS
    user has already connected. The status panel in the calendar uses this
    to pick between "Connect", "Connected — refresh/disconnect", and
    "not configured" states."""
    if not google_oauth_configured():
        return jsonify({"ok": True, "configured": False, "connected": False})
    owner = g.user.username if g.user else ""
    with SessionLocal() as db_session:
        link = db_session.scalar(select(GoogleCalendarLink).where(GoogleCalendarLink.owner == owner))
        if link is None:
            return jsonify({"ok": True, "configured": True, "connected": False})
        return jsonify({
            "ok": True, "configured": True, "connected": True,
            "email": link.google_email or "",
            "calendar_id": link.calendar_id,
            "last_synced_at": link.last_synced_at.isoformat() if link.last_synced_at else None,
        })


@app.route("/calendar/google/connect")
@login_required
def calendar_google_connect():
    """Kick off the OAuth dance. Redirects the user to Google's consent screen."""
    if not google_oauth_configured():
        flash("Google Calendar integration isn't configured on this server.", "error")
        return redirect(url_for("calendar"))
    from google_auth_oauthlib.flow import Flow
    redirect_uri = _google_redirect_uri()
    flow = Flow.from_client_config(
        google_client_config(redirect_uri),
        scopes=GOOGLE_OAUTH_SCOPES,
        redirect_uri=redirect_uri,
    )
    # access_type=offline → we get a refresh_token; prompt=consent ensures we
    # always receive a fresh refresh_token even if the user already approved.
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    session["google_oauth_state"] = state
    return redirect(auth_url)


@app.route("/calendar/google/callback")
@login_required
def calendar_google_callback():
    """OAuth redirect target. Exchange the code → tokens, save the link."""
    if not google_oauth_configured():
        return redirect(url_for("calendar"))
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build

    state = session.pop("google_oauth_state", None)
    redirect_uri = _google_redirect_uri()
    flow = Flow.from_client_config(
        google_client_config(redirect_uri),
        scopes=GOOGLE_OAUTH_SCOPES,
        redirect_uri=redirect_uri,
        state=state,
    )
    try:
        flow.fetch_token(authorization_response=request.url)
    except Exception as exc:
        app.logger.warning("Google OAuth callback failed: %s", exc)
        flash(f"Google sign-in failed: {exc}", "error")
        return redirect(url_for("calendar"))

    creds = flow.credentials
    # Fetch the user's email so we can show "Connected as alice@…".
    email = ""
    try:
        svc = build("oauth2", "v2", credentials=creds, cache_discovery=False)
        email = svc.userinfo().get().execute().get("email", "")
    except Exception:
        pass

    owner = g.user.username if g.user else ""
    with SessionLocal() as db_session:
        link = db_session.scalar(select(GoogleCalendarLink).where(GoogleCalendarLink.owner == owner))
        if link is None:
            link = GoogleCalendarLink(owner=owner)
        link.refresh_token = creds.refresh_token or link.refresh_token
        link.access_token = creds.token or ""
        link.token_expiry = creds.expiry
        link.google_email = email
        link.calendar_id = "primary"
        link.enabled = True
        if not link.refresh_token:
            db_session.expunge(link)
            flash("Google didn't return a refresh token. Revoke access at myaccount.google.com/permissions and try connecting again.", "warning")
            return redirect(url_for("calendar"))
        db_session.add(link)
        db_session.commit()
    flash(f"Connected Google Calendar for {email}.", "success")
    return redirect(url_for("calendar"))


@app.route("/calendar/google/refresh", methods=["POST"])
@login_required
def calendar_google_refresh():
    """Force a fresh pull of events from Google (bypasses any in-memory cache
    on the next /calendar/events.json hit)."""
    owner = g.user.username if g.user else ""
    with SessionLocal() as db_session:
        link = db_session.scalar(select(GoogleCalendarLink).where(GoogleCalendarLink.owner == owner))
        if link is None:
            return jsonify({"ok": False, "error": "not connected"}), 404
        try:
            items = fetch_google_calendar_items(link, db_session)
            return jsonify({"ok": True, "event_count": len(items)})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/calendar/google/disconnect", methods=["POST"])
@login_required
def calendar_google_disconnect():
    owner = g.user.username if g.user else ""
    with SessionLocal() as db_session:
        link = db_session.scalar(select(GoogleCalendarLink).where(GoogleCalendarLink.owner == owner))
        if link is None:
            return jsonify({"ok": True})
        db_session.delete(link)
        db_session.commit()
    return jsonify({"ok": True})


@app.route("/calendar/items", methods=["POST"])
@login_required
def calendar_item_create():
    """Create either an event or a task. JSON body:
       { kind: 'event'|'task', title, start, end, isAllday, color, description, ... }"""
    from datetime import datetime as _dt
    payload = request.get_json(silent=True) or {}
    kind = (payload.get("kind") or "event").lower()
    title = (payload.get("title") or "").strip()
    if not title:
        return jsonify({"ok": False, "error": "title required"}), 400

    def _parse(v):
        if not v:
            return None
        try:
            return _dt.fromisoformat(v.replace("Z", "+00:00").replace("+00:00", ""))
        except ValueError:
            return None

    start = _parse(payload.get("start"))
    end = _parse(payload.get("end"))
    is_all_day = bool(payload.get("isAllday", True))
    color = (payload.get("backgroundColor") or payload.get("color") or "").strip()
    owner = g.user.username if g.user else ""

    with SessionLocal() as db_session:
        if kind == "task":
            row = TaskItem(
                title=title,
                due_date=start.date() if start else None,
                start_at=None if is_all_day else start,
                end_at=None if is_all_day else end,
                status=payload.get("status", "todo"),
                priority=payload.get("priority", "medium"),
                color=color,
                notes=payload.get("body", "") or payload.get("description", ""),
                owner=owner,
            )
        else:
            row = CalendarEvent(
                title=title,
                event_date=start.date() if start else date.today(),
                start_at=None if is_all_day else start,
                end_at=None if is_all_day else end,
                is_all_day=is_all_day,
                event_type=payload.get("event_type", "experiment"),
                color=color,
                description=payload.get("body", "") or payload.get("description", ""),
                owner=owner,
            )
        db_session.add(row)
        db_session.commit()
        if kind == "task":
            return jsonify({"ok": True, "item": _serialize_task(row)})
        return jsonify({"ok": True, "item": _serialize_calendar_event(row)})


@app.route("/calendar/items/<string:item_key>", methods=["POST"])
@login_required
def calendar_item_update(item_key: str):
    """Update an existing event or task. item_key is `event-<id>` or `task-<id>`."""
    from datetime import datetime as _dt
    payload = request.get_json(silent=True) or {}
    kind, _, raw_id = item_key.partition("-")
    if not raw_id.isdigit():
        return jsonify({"ok": False, "error": "bad id"}), 400
    row_id = int(raw_id)

    def _parse(v):
        if not v:
            return None
        try:
            return _dt.fromisoformat(v.replace("Z", "+00:00").replace("+00:00", ""))
        except ValueError:
            return None

    with SessionLocal() as db_session:
        if kind == "task":
            row = db_session.get(TaskItem, row_id)
            if row is None:
                return jsonify({"ok": False}), 404
            if "title" in payload: row.title = (payload["title"] or "").strip() or row.title
            if "body" in payload: row.notes = payload["body"] or ""
            if "backgroundColor" in payload: row.color = payload["backgroundColor"] or ""
            if "priority" in payload: row.priority = payload["priority"]
            start = _parse(payload.get("start"))
            end = _parse(payload.get("end"))
            is_all_day = payload.get("isAllday")
            if start is not None:
                row.due_date = start.date()
                row.start_at = None if is_all_day else start
            if end is not None:
                row.end_at = None if is_all_day else end
            db_session.commit()
            return jsonify({"ok": True, "item": _serialize_task(row)})
        elif kind == "event":
            row = db_session.get(CalendarEvent, row_id)
            if row is None:
                return jsonify({"ok": False}), 404
            if "title" in payload: row.title = (payload["title"] or "").strip() or row.title
            if "body" in payload: row.description = payload["body"] or ""
            if "backgroundColor" in payload: row.color = payload["backgroundColor"] or ""
            if "event_type" in payload: row.event_type = payload["event_type"]
            start = _parse(payload.get("start"))
            end = _parse(payload.get("end"))
            is_all_day = payload.get("isAllday")
            if start is not None:
                row.event_date = start.date()
                row.start_at = None if is_all_day else start
                if is_all_day is not None: row.is_all_day = bool(is_all_day)
            if end is not None:
                row.end_at = None if is_all_day else end
            db_session.commit()
            return jsonify({"ok": True, "item": _serialize_calendar_event(row)})
        return jsonify({"ok": False, "error": "unknown kind"}), 400


@app.route("/calendar/items/<string:item_key>/toggle", methods=["POST"])
@login_required
def calendar_item_toggle(item_key: str):
    """Flip a task's done state. No-op for events."""
    kind, _, raw_id = item_key.partition("-")
    if kind != "task" or not raw_id.isdigit():
        return jsonify({"ok": False, "error": "tasks only"}), 400
    with SessionLocal() as db_session:
        row = db_session.get(TaskItem, int(raw_id))
        if row is None:
            return jsonify({"ok": False}), 404
        if row.done_at is None:
            row.done_at = datetime.utcnow()
            row.status = "done"
        else:
            row.done_at = None
            row.status = "todo"
        db_session.commit()
        return jsonify({"ok": True, "item": _serialize_task(row)})


@app.route("/calendar/items/<string:item_key>/delete", methods=["POST"])
@login_required
def calendar_item_delete(item_key: str):
    kind, _, raw_id = item_key.partition("-")
    if not raw_id.isdigit():
        return jsonify({"ok": False, "error": "bad id"}), 400
    row_id = int(raw_id)
    with SessionLocal() as db_session:
        row = db_session.get(TaskItem if kind == "task" else CalendarEvent, row_id)
        if row is None:
            return jsonify({"ok": False}), 404
        db_session.delete(row)
        db_session.commit()
        return jsonify({"ok": True})


@app.route("/tasks", methods=["POST"])
@login_required
def tasks():
    """Legacy endpoint kept for any older form posts."""
    with SessionLocal() as db_session:
        db_session.add(
            TaskItem(
                title=request.form["title"],
                due_date=parse_date(request.form.get("due_date")),
                status=request.form.get("status", "todo"),
                priority=request.form.get("priority", "medium"),
                notes=request.form.get("notes", ""),
                owner=g.user.username if g.user else "",
            )
        )
        db_session.commit()
    return redirect(url_for("calendar"))


def _notebook_owner_filter(query):
    return query.where(NotebookTab.owner_username == g.user.username)


def _serialize_page(page: NotebookPage) -> dict:
    import json as _json
    try:
        props = _json.loads(page.properties) if page.properties else []
    except Exception:
        props = []
    return {
        "id": page.id,
        "tab_id": page.tab_id_fk,
        "title": page.title,
        "body": page.body,
        "entry_date": page.entry_date.isoformat() if page.entry_date else "",
        "properties": props,
        "created_at": page.created_at.isoformat(),
        "updated_at": page.updated_at.isoformat(),
    }


@app.route("/notebook")
@login_required
def notebook():
    selected_tab_id = request.args.get("tab", type=int)
    selected_page_id = request.args.get("page", type=int)
    with SessionLocal() as db_session:
        tabs = db_session.scalars(
            _notebook_owner_filter(select(NotebookTab)).order_by(NotebookTab.position, NotebookTab.id)
        ).all()
        selected_tab = None
        if selected_tab_id is not None:
            selected_tab = next((tab for tab in tabs if tab.id == selected_tab_id), None)
        if selected_tab is None and tabs:
            selected_tab = tabs[0]
        selected_page = None
        if selected_tab is not None:
            if selected_page_id is not None:
                selected_page = next((page for page in selected_tab.pages if page.id == selected_page_id), None)
            if selected_page is None and selected_tab.pages:
                selected_page = selected_tab.pages[0]

        tabs_data = [
            {
                "id": tab.id,
                "title": tab.title,
                "pages": [
                    {"id": page.id, "title": page.title, "tab_id": tab.id, "updated_at": page.updated_at.isoformat()}
                    for page in tab.pages
                ],
            }
            for tab in tabs
        ]
        selected_page_data = _serialize_page(selected_page) if selected_page else None
        selected_tab_id_value = selected_tab.id if selected_tab else None

    return render_template(
        "notebook.html",
        tabs=tabs_data,
        selected_tab_id=selected_tab_id_value,
        selected_page=selected_page_data,
    )


@app.route("/notebook/tabs/create", methods=["POST"])
@login_required
def notebook_create_tab():
    title = (request.form.get("title") or "New topic").strip() or "New topic"
    with SessionLocal() as db_session:
        max_pos = db_session.scalar(
            _notebook_owner_filter(select(func.max(NotebookTab.position)))
        ) or 0
        tab = NotebookTab(owner_username=g.user.username, title=title, position=max_pos + 1)
        db_session.add(tab)
        db_session.commit()
        return jsonify({"ok": True, "id": tab.id, "title": tab.title})


@app.route("/notebook/tabs/<int:tab_id>/rename", methods=["POST"])
@login_required
def notebook_rename_tab(tab_id: int):
    new_title = (request.form.get("title") or "").strip() or "Untitled topic"
    with SessionLocal() as db_session:
        tab = db_session.get(NotebookTab, tab_id)
        if tab is None or tab.owner_username != g.user.username:
            return jsonify({"ok": False}), 404
        tab.title = new_title
        db_session.commit()
        return jsonify({"ok": True, "id": tab.id, "title": tab.title})


@app.route("/notebook/tabs/<int:tab_id>/delete", methods=["POST"])
@login_required
def notebook_delete_tab(tab_id: int):
    with SessionLocal() as db_session:
        tab = db_session.get(NotebookTab, tab_id)
        if tab is not None and tab.owner_username == g.user.username:
            db_session.delete(tab)
            db_session.commit()
    return redirect(url_for("notebook"))


@app.route("/notebook/pages/create", methods=["POST"])
@login_required
def notebook_create_page():
    tab_id = request.form.get("tab_id", type=int)
    if not tab_id:
        return jsonify({"ok": False, "error": "tab_id required"}), 400
    with SessionLocal() as db_session:
        tab = db_session.get(NotebookTab, tab_id)
        if tab is None or tab.owner_username != g.user.username:
            return jsonify({"ok": False}), 404
        max_pos = db_session.scalar(
            select(func.max(NotebookPage.position)).where(NotebookPage.tab_id_fk == tab_id)
        ) or 0
        page = NotebookPage(
            tab_id_fk=tab_id,
            title=(request.form.get("title") or "Untitled page").strip() or "Untitled page",
            body="",
            position=max_pos + 1,
        )
        db_session.add(page)
        db_session.commit()
        return jsonify({"ok": True, "page": _serialize_page(page)})


@app.route("/notebook/pages/create-quick", methods=["POST"])
@login_required
def notebook_create_page_quick():
    with SessionLocal() as db_session:
        first_tab = db_session.scalar(
            _notebook_owner_filter(select(NotebookTab)).order_by(NotebookTab.position, NotebookTab.id).limit(1)
        )
        if first_tab is None:
            first_tab = NotebookTab(owner_username=g.user.username, title="Inbox", position=0)
            db_session.add(first_tab)
            db_session.flush()
        max_pos = db_session.scalar(
            select(func.max(NotebookPage.position)).where(NotebookPage.tab_id_fk == first_tab.id)
        ) or 0
        page = NotebookPage(
            tab_id_fk=first_tab.id,
            title="Untitled page",
            body="",
            position=max_pos + 1,
        )
        db_session.add(page)
        db_session.commit()
        return jsonify({"ok": True, "page": _serialize_page(page), "tab_id": first_tab.id})


@app.route("/search")
@login_required
def global_search():
    """Cross-section search used by the Cmd+K palette.

    Returns up to 5 matches per section: mice, plasmids, orders, samples,
    notebook pages. Each result has { type, id, label, sublabel, url }.
    Empty `q` returns nothing — the palette only fires on non-empty input.
    """
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"ok": True, "results": []})
    like = f"%{q}%"
    is_digit = q.isdigit()
    limit = 5
    results: list[dict] = []
    with SessionLocal() as db_session:
        mouse_stmt = select(MouseRecord)
        if is_digit:
            mouse_stmt = mouse_stmt.where(MouseRecord.mouse_id == int(q))
        else:
            mouse_stmt = mouse_stmt.where(
                MouseRecord.genotype.ilike(like) | MouseRecord.owner.ilike(like) | MouseRecord.note.ilike(like)
            )
        for m in db_session.scalars(mouse_stmt.order_by(MouseRecord.mouse_id.desc()).limit(limit)).all():
            results.append({
                "type": "mouse",
                "id": m.mouse_id,
                "label": f"Mouse #{m.mouse_id}",
                "sublabel": f"{m.gender or '?'} · {m.genotype or '(no genotype)'} · {m.owner or 'no owner'}",
                "url": url_for("colony", view="mice") + f"#mouse-{m.id}",
            })

        plasmid_stmt = select(PlasmidRecord)
        if is_digit:
            plasmid_stmt = plasmid_stmt.where(PlasmidRecord.plasmid_id == int(q))
        else:
            plasmid_stmt = plasmid_stmt.where(
                PlasmidRecord.name.ilike(like) | PlasmidRecord.backbone.ilike(like)
                | PlasmidRecord.insert_seq.ilike(like) | PlasmidRecord.notes.ilike(like)
            )
        for p in db_session.scalars(plasmid_stmt.order_by(PlasmidRecord.plasmid_id.desc()).limit(limit)).all():
            results.append({
                "type": "plasmid",
                "id": p.plasmid_id,
                "label": f"Plasmid #{p.plasmid_id} · {p.name or '(no name)'}",
                "sublabel": f"{p.backbone or '?'} · {p.resistance or 'no resistance'} · {p.owner or 'no owner'}",
                "url": url_for("plasmids"),
            })

        # Every lab inventory: samples, orders, reagents, antibodies, custom.
        kind_type = {"orders": "order", "samples": "sample", "reagents": "reagent", "antibodies": "antibody"}
        modules = {m.id: m for m in db_session.scalars(select(InventoryModule))}
        item_stmt = select(InventoryItem)
        if is_digit:
            item_stmt = item_stmt.where(InventoryItem.number == int(q))
        else:
            item_stmt = item_stmt.where(
                InventoryItem.name.ilike(like) | InventoryItem.category.ilike(like)
                | InventoryItem.vendor.ilike(like) | InventoryItem.catalog_number.ilike(like)
                | InventoryItem.lot.ilike(like) | InventoryItem.notes.ilike(like)
                | InventoryItem.attrs.ilike(like)
            )
        for item in db_session.scalars(item_stmt.order_by(InventoryItem.id.desc()).limit(limit * 2)).all():
            module = modules.get(item.module_id_fk)
            if module is None:
                continue
            results.append({
                "type": kind_type.get(module.kind, "item"),
                "id": item.number,
                "label": f"{module.label} #{item.number} · {item.name or '(unnamed)'}",
                "sublabel": " · ".join(filter(None, [item.category, item.status, item.vendor,
                                                     "lab common" if item.is_shared else item.owner])),
                "url": url_for("inventory.module", key=module.key),
            })

        # Fly vials and worm plates, by genotype (or either cross parent).
        from . import stock_service
        from .models import StockModule, StockUnit
        stock_modules = {m.id: stock_service.view(m) for m in db_session.scalars(select(StockModule))}
        unit_stmt = select(StockUnit).where(StockUnit.active.is_(True))
        if is_digit:
            unit_stmt = unit_stmt.where(StockUnit.number == int(q))
        else:
            unit_stmt = unit_stmt.where(
                StockUnit.genotype.ilike(like) | StockUnit.female_genotype.ilike(like)
                | StockUnit.male_genotype.ilike(like) | StockUnit.notes.ilike(like))
        for unit in db_session.scalars(unit_stmt.order_by(StockUnit.id.desc()).limit(limit * 2)).all():
            mv = stock_modules.get(unit.module_id_fk)
            if mv is None:
                continue
            results.append({
                "type": "vial",
                "id": unit.number,
                "label": f"{mv.code(unit)} · {unit.genotype or '(no genotype)'}",
                "sublabel": " · ".join(filter(None, [mv.label, mv.purpose_label(unit.purpose),
                                                     unit.rack.name if unit.rack else "", unit.owner])),
                "url": url_for("stocks.module", key=mv.key),
            })

        # Animals, housing units and lines in the configurable organism databases.
        from . import organism_service
        results.extend(organism_service.search(db_session, q, limit))

        # Notebook pages — owner-scoped.
        page_stmt = (
            select(NotebookPage)
            .join(NotebookTab, NotebookPage.tab_id_fk == NotebookTab.id)
            .where(NotebookTab.owner_username == g.user.username)
            .where(NotebookPage.title.ilike(like) | NotebookPage.body.ilike(like))
            .order_by(NotebookPage.updated_at.desc())
            .limit(limit)
        )
        for page in db_session.scalars(page_stmt).all():
            results.append({
                "type": "page",
                "id": page.id,
                "label": page.title or "Untitled page",
                "sublabel": f"Notebook · {page.tab.title if page.tab else ''}",
                "url": url_for("notebook") + f"?tab={page.tab_id_fk}&page={page.id}",
            })

    return jsonify({"ok": True, "results": results, "query": q})


@app.route("/import/<entity>", methods=["POST"])
@login_required
def csv_import(entity: str):
    """Import a CSV into one of the data tables.

    Form fields:
      file (uploaded CSV)
      dry_run=1  → returns parsed rows without committing

    Supported entities: mouse, plasmid, order.
    Returns { ok, count, errors, preview } where preview is the first 6 rows.
    """
    if entity not in ("mouse", "plasmid", "order"):
        return jsonify({"ok": False, "error": f"unknown entity: {entity}"}), 400
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify({"ok": False, "error": "missing file"}), 400
    dry_run = (request.form.get("dry_run") or "0") == "1"

    import csv as _csv, io as _io
    raw = upload.read()
    try:
        text_data = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text_data = raw.decode("latin-1")
    reader = _csv.DictReader(_io.StringIO(text_data))
    rows = [r for r in reader]
    if not rows:
        return jsonify({"ok": False, "error": "empty CSV"}), 400

    errors: list[str] = []
    created = 0
    preview: list[dict] = []
    with SessionLocal() as db_session:
        if entity == "mouse":
            # Reserve one contiguous block up front. Calling next_mouse_id()
            # per row used to hand every row the same number, so any CSV
            # without explicit IDs died on the unique index.
            blank_ids = sum(1 for r in rows if not (r.get("mouse_id") or "").strip())
            reserved = reserve_mouse_ids(db_session, blank_ids)
            reserved_iter = iter(reserved)

            for idx, row in enumerate(rows, start=2):
                try:
                    mouse_id_raw = (row.get("mouse_id") or "").strip()
                    mouse_id_value = (int(mouse_id_raw) if mouse_id_raw
                                      else next(reserved_iter))
                    existing = db_session.scalar(select(MouseRecord).where(MouseRecord.mouse_id == mouse_id_value))
                    if existing is not None:
                        errors.append(f"row {idx}: mouse_id {mouse_id_value} already exists")
                        continue
                    mouse = MouseRecord(
                        mouse_id=mouse_id_value,
                        gender=(row.get("gender") or "").strip(),
                        genotype=(row.get("genotype") or "").strip(),
                        owner=(row.get("owner") or "").strip(),
                        status=(row.get("status") or "").strip(),
                        note=(row.get("note") or "").strip(),
                    )
                    if not dry_run:
                        db_session.add(mouse)
                    preview.append({"mouse_id": mouse_id_value, "genotype": mouse.genotype})
                    created += 1
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"row {idx}: {exc}")
        elif entity == "plasmid":
            for idx, row in enumerate(rows, start=2):
                try:
                    pid_raw = (row.get("plasmid_id") or "").strip()
                    pid_value = int(pid_raw) if pid_raw else ((db_session.scalar(select(func.max(PlasmidRecord.plasmid_id))) or 0) + 1 + (created if not dry_run else 0))
                    if not pid_raw and dry_run:
                        # in dry-run, we still want unique-ish ids in preview
                        pid_value = (db_session.scalar(select(func.max(PlasmidRecord.plasmid_id))) or 0) + 1 + created
                    existing = db_session.scalar(select(PlasmidRecord).where(PlasmidRecord.plasmid_id == pid_value))
                    if existing is not None:
                        errors.append(f"row {idx}: plasmid_id {pid_value} already exists")
                        continue
                    p = PlasmidRecord(
                        plasmid_id=pid_value,
                        name=(row.get("name") or "").strip(),
                        backbone=(row.get("backbone") or "").strip(),
                        insert_seq=(row.get("insert_seq") or row.get("insert") or "").strip(),
                        resistance=(row.get("resistance") or "").strip(),
                        owner=(row.get("owner") or g.user.username).strip(),
                        location=(row.get("location") or "").strip(),
                        notes=(row.get("notes") or "").strip(),
                    )
                    if not dry_run:
                        db_session.add(p)
                    preview.append({"plasmid_id": pid_value, "name": p.name})
                    created += 1
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"row {idx}: {exc}")
        elif entity == "order":
            # Orders are an inventory now; import into the one the page named.
            from . import inventory_service as inventories
            module = (inventories.get_module(db_session, request.args.get("module", ""))
                      or inventories.first_of_kind(db_session, "orders"))
            if module is None:
                return jsonify({"ok": False, "error": "There is no orders inventory to import into."}), 400
            number = inventories.next_number(db_session, module.id)
            for idx, row in enumerate(rows, start=2):
                try:
                    o = InventoryItem(
                        module_id_fk=module.id, number=number,
                        owner=(row.get("requester_name") or row.get("requester") or g.user.username).strip(),
                        vendor=(row.get("vendor_name") or row.get("vendor") or "").strip(),
                        name=(row.get("item_name") or row.get("item") or "").strip(),
                        catalog_number=(row.get("catalog_number") or row.get("catalog") or "").strip(),
                        quantity=(row.get("quantity") or "1").strip(),
                        status=(row.get("status") or "requested").strip(),
                        notes=(row.get("notes") or "").strip(),
                    )
                    if not o.name:
                        raise ValueError("no item name")
                    if not dry_run:
                        db_session.add(o)
                    number += 1
                    preview.append({"item": o.name, "vendor": o.vendor})
                    created += 1
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"row {idx}: {exc}")
        if not dry_run:
            db_session.commit()

    return jsonify({
        "ok": True,
        "count": created,
        "errors": errors[:20],
        "preview": preview[:6],
        "dry_run": dry_run,
    })


@app.route("/batches")
@login_required
def batches_view():
    """Recent batch operations, with what undoing each would do.

    Everyone sees their own; admins see the whole lab's, because the
    "someone bulk-edited the colony this morning" question is theirs to
    answer.
    """
    show_all = access.is_admin() and request.args.get("scope") != "mine"
    with SessionLocal() as db_session:
        rows = undo_service.recent(
            db_session, limit=60,
            actor=None if show_all else g.user.username)
        batches = []
        for row in rows:
            summary = undo_service.describe(db_session, row)
            batches.append({
                "id": row.id,
                "action": row.action,
                "description": row.description,
                "table": row.target_table,
                "actor": row.actor,
                "count": row.record_count or summary["entries"],
                "created_at": row.created_at,
                "undone_at": row.undone_at,
                "undone_by": row.undone_by,
                "mine": row.actor == g.user.username,
                "can_undo": (not row.is_undone
                             and (row.actor == g.user.username or access.is_admin())),
                **summary,
            })
    return render_template("batches.html", batches=batches, show_all=show_all)


@app.route("/batches/<int:batch_id>/undo", methods=["POST"])
@login_required
def undo_batch(batch_id: int):
    force = request.form.get("force") == "1"
    with SessionLocal() as db_session:
        row = db_session.get(BatchRecord, batch_id)
        if row is None:
            abort(404)
        if not (row.actor == g.user.username or access.is_admin()):
            flash("Only whoever ran a batch, or an admin, can undo it.", "error")
            return redirect(url_for("batches_view"))

        result = undo_service.undo(db_session, row, g.user.username, force=force)
        if not result["ok"]:
            db_session.rollback()
            for problem in result["problems"]:
                flash(problem, "error")
            return redirect(url_for("batches_view"))
        db_session.commit()

    parts = [f"Undid {result['reverted']} change(s)"]
    if result["skipped"]:
        parts.append(f"{result['skipped']} could not be reversed")
    flash(" — ".join(parts) + ".", "success")
    for note in result["notes"][:5]:
        flash(note, "info")
    return redirect(url_for("batches_view"))


@app.route("/audit")
@admin_required
def audit_log_view():
    """Admin-only change history across the app.

    Every create, edit and delete on a tracked table lands here via the
    flush listener in app/audit.py, with a field-level diff — so the
    question is no longer just "who deleted that mouse?" but "what was its
    genotype before someone changed it?"."""
    with SessionLocal() as db_session:
        rows = db_session.scalars(
            select(AuditEntry).order_by(AuditEntry.changed_at.desc()).limit(200)
        ).all()
        entries = [
            {
                "id": e.id,
                "table_name": e.table_name,
                "record_id": e.record_id,
                "record_label": e.record_label or f"#{e.record_id}",
                "action": e.action,
                "changed_by": e.changed_by,
                "changed_at": e.changed_at.strftime("%Y-%m-%d %H:%M:%S"),
                "details": e.details or "",
            }
            for e in rows
        ]
    return render_template("audit.html", entries=entries)


@app.route("/notebook/templates")
@login_required
def notebook_templates_list():
    with SessionLocal() as db_session:
        rows = db_session.scalars(
            select(NotebookTemplate)
            .where(NotebookTemplate.owner_username == g.user.username)
            .order_by(NotebookTemplate.updated_at.desc())
        ).all()
        return jsonify({"ok": True, "templates": [
            {
                "id": t.id,
                "title": t.title,
                "icon": t.icon,
                "body_preview": (t.body or "")[:160],
                "updated_at": t.updated_at.isoformat(),
            }
            for t in rows
        ]})


@app.route("/notebook/templates/create", methods=["POST"])
@login_required
def notebook_template_create():
    """Create a template either from scratch or from an existing page.

    Form fields:
      title (str, required)
      icon  (str, optional — emoji/single-character)
      body  (str, optional)
      from_page_id (int, optional — if set, copies the page body into the template)
    """
    title = (request.form.get("title") or "").strip() or "Untitled template"
    icon = (request.form.get("icon") or "").strip()
    body = request.form.get("body", "")
    from_page_id = request.form.get("from_page_id", type=int)

    with SessionLocal() as db_session:
        if from_page_id:
            page = db_session.get(NotebookPage, from_page_id)
            if page is None or page.tab.owner_username != g.user.username:
                return jsonify({"ok": False, "error": "page not found"}), 404
            body = page.body or body
        template = NotebookTemplate(
            owner_username=g.user.username,
            title=title,
            icon=icon,
            body=body,
        )
        db_session.add(template)
        db_session.commit()
        return jsonify({
            "ok": True,
            "template": {"id": template.id, "title": template.title, "icon": template.icon},
        })


@app.route("/notebook/templates/<int:template_id>/delete", methods=["POST"])
@login_required
def notebook_template_delete(template_id: int):
    with SessionLocal() as db_session:
        template = db_session.get(NotebookTemplate, template_id)
        if template is None or template.owner_username != g.user.username:
            return jsonify({"ok": False}), 404
        db_session.delete(template)
        db_session.commit()
        return jsonify({"ok": True})


@app.route("/notebook/pages/create-from-template", methods=["POST"])
@login_required
def notebook_create_page_from_template():
    """Create a new page seeded from a template. Optionally targets a specific
    tab; defaults to the first available (or creates an Inbox like
    create-quick)."""
    template_id = request.form.get("template_id", type=int)
    tab_id = request.form.get("tab_id", type=int)
    if not template_id:
        return jsonify({"ok": False, "error": "template_id required"}), 400

    with SessionLocal() as db_session:
        template = db_session.get(NotebookTemplate, template_id)
        if template is None or template.owner_username != g.user.username:
            return jsonify({"ok": False, "error": "template not found"}), 404

        if tab_id:
            tab = db_session.get(NotebookTab, tab_id)
            if tab is None or tab.owner_username != g.user.username:
                return jsonify({"ok": False}), 404
        else:
            tab = db_session.scalar(
                _notebook_owner_filter(select(NotebookTab)).order_by(NotebookTab.position, NotebookTab.id).limit(1)
            )
            if tab is None:
                tab = NotebookTab(owner_username=g.user.username, title="Inbox", position=0)
                db_session.add(tab)
                db_session.flush()

        max_pos = db_session.scalar(
            select(func.max(NotebookPage.position)).where(NotebookPage.tab_id_fk == tab.id)
        ) or 0
        page = NotebookPage(
            tab_id_fk=tab.id,
            title=template.title or "Untitled page",
            body=template.body or "",
            position=max_pos + 1,
        )
        db_session.add(page)
        db_session.commit()
        return jsonify({"ok": True, "page": _serialize_page(page), "tab_id": tab.id})


@app.route("/notebook/pages/<int:page_id>/move", methods=["POST"])
@login_required
def notebook_move_page(page_id: int):
    new_tab_id = request.form.get("tab_id", type=int)
    if not new_tab_id:
        return jsonify({"ok": False, "error": "tab_id required"}), 400
    with SessionLocal() as db_session:
        page = db_session.get(NotebookPage, page_id)
        if page is None or page.tab.owner_username != g.user.username:
            return jsonify({"ok": False}), 404
        new_tab = db_session.get(NotebookTab, new_tab_id)
        if new_tab is None or new_tab.owner_username != g.user.username:
            return jsonify({"ok": False}), 404
        page.tab_id_fk = new_tab_id
        max_pos = db_session.scalar(
            select(func.max(NotebookPage.position)).where(NotebookPage.tab_id_fk == new_tab_id)
        ) or 0
        page.position = max_pos + 1
        db_session.commit()
        return jsonify({"ok": True, "tab_id": new_tab_id, "page_id": page.id})


@app.route("/notebook/pages/<int:page_id>/update", methods=["POST"])
@login_required
def notebook_update_page(page_id: int):
    with SessionLocal() as db_session:
        page = db_session.get(NotebookPage, page_id)
        if page is None or page.tab.owner_username != g.user.username:
            return jsonify({"ok": False}), 404
        if "title" in request.form:
            page.title = (request.form.get("title") or "").strip() or "Untitled page"
        if "body" in request.form:
            page.body = request.form.get("body", "")
        if "entry_date" in request.form:
            raw_date = (request.form.get("entry_date") or "").strip()
            page.entry_date = parse_date(raw_date) if raw_date else None
        if "properties" in request.form:
            # JSON blob from the client — validated/normalized server-side.
            import json as _json
            try:
                parsed = _json.loads(request.form.get("properties") or "[]")
                if isinstance(parsed, list):
                    page.properties = _json.dumps(parsed)
            except _json.JSONDecodeError:
                pass
        page.updated_at = datetime.utcnow()
        db_session.commit()
        return jsonify({"ok": True, "updated_at": page.updated_at.isoformat()})


@app.route("/notebook/pages/<int:page_id>/delete", methods=["POST"])
@login_required
def notebook_delete_page(page_id: int):
    with SessionLocal() as db_session:
        page = db_session.get(NotebookPage, page_id)
        if page is None or page.tab.owner_username != g.user.username:
            return redirect(url_for("notebook"))
        tab_id = page.tab_id_fk
        db_session.delete(page)
        db_session.commit()
    return redirect(url_for("notebook", tab=tab_id))


@app.route("/notebook/upload-image", methods=["POST"])
@login_required
def notebook_upload_image():
    upload = request.files.get("image")
    if upload is None or not upload.filename:
        return jsonify({"ok": False}), 400
    saved = save_uploaded_image(upload)
    if not saved:
        return jsonify({"ok": False}), 400
    return jsonify({"ok": True, "url": url_for("static", filename=saved)})


@app.route("/notebook/upload-file", methods=["POST"])
@login_required
def notebook_upload_file():
    upload = request.files.get("file")
    saved = save_uploaded_file(upload)
    if not saved:
        return jsonify({"ok": False}), 400
    return jsonify({
        "ok": True,
        "url": url_for("static", filename=saved["path"]),
        "name": saved["original_name"],
        "size": saved["size_bytes"],
    })


@app.route("/notebook/lookup/mouse/<int:mouse_id>")
@login_required
def notebook_lookup_mouse(mouse_id: int):
    with SessionLocal() as db_session:
        mouse = db_session.scalar(select(MouseRecord).where(MouseRecord.mouse_id == mouse_id))
        if mouse is None:
            return jsonify({"ok": False}), 404
        cage_id = mouse.cage.cage_id if mouse.cage else ""
        label = f"Mouse #{mouse.mouse_id} · {mouse.gender or '?'} · {mouse.genotype or '(no genotype)'} · cage {cage_id or '—'} · {mouse.owner or 'no owner'}"
        return jsonify(
            {
                "ok": True,
                "label": label,
                "mouse_id": mouse.mouse_id,
                "gender": mouse.gender,
                "genotype": mouse.genotype,
                "status": mouse.status,
                "owner": mouse.owner,
                "cage_id": cage_id,
            }
        )


@app.route("/notebook/lookup/plasmid/<int:plasmid_id>")
@login_required
def notebook_lookup_plasmid(plasmid_id: int):
    with SessionLocal() as db_session:
        plasmid = db_session.scalar(select(PlasmidRecord).where(PlasmidRecord.plasmid_id == plasmid_id))
        if plasmid is None:
            return jsonify({"ok": False}), 404
        label = f"Plasmid #{plasmid.plasmid_id} · {plasmid.name or '(no name)'} · {plasmid.backbone or '?'} · {plasmid.resistance or 'no resistance'} · {plasmid.owner or 'no owner'}"
        return jsonify(
            {
                "ok": True,
                "label": label,
                "plasmid_id": plasmid.plasmid_id,
                "name": plasmid.name,
                "backbone": plasmid.backbone,
                "insert_seq": plasmid.insert_seq,
                "resistance": plasmid.resistance,
                "owner": plasmid.owner,
                "location": plasmid.location,
            }
        )


@app.route("/notebook/lookup/order/<int:order_id>")
@login_required
def _order_items_query(db_session, query: str, limit: int):
    """Orders for @order mentions: items of the first orders inventory,
    where an order's number is what @order <n> refers to."""
    from . import inventory_service as inventories
    module = inventories.first_of_kind(db_session, "orders")
    if module is None:
        return []
    stmt = select(InventoryItem).where(InventoryItem.module_id_fk == module.id)
    if query.isdigit():
        stmt = stmt.where(InventoryItem.number == int(query))
    elif query:
        like = f"%{query}%"
        stmt = stmt.where(InventoryItem.name.ilike(like) | InventoryItem.vendor.ilike(like)
                          | InventoryItem.catalog_number.ilike(like))
    return db_session.scalars(stmt.order_by(InventoryItem.number.desc()).limit(limit)).all()


def notebook_lookup_order(order_id: int):
    with SessionLocal() as db_session:
        found = _order_items_query(db_session, str(order_id), 1)
        if not found:
            return jsonify({"ok": False}), 404
        order = found[0]
        label = (
            f"Order #{order.number} · {order.vendor or '(no vendor)'} · "
            f"{order.name or '(no item)'} · cat# {order.catalog_number or '—'} · "
            f"qty {order.quantity or '?'} · {order.status or 'requested'} · "
            f"requested by {order.owner or '—'}"
        )
        return jsonify(
            {
                "ok": True,
                "label": label,
                "order_id": order.number,
                "vendor_name": order.vendor,
                "item_name": order.name,
                "catalog_number": order.catalog_number,
                "quantity": order.quantity,
                "status": order.status,
                "requester_name": order.owner,
            }
        )


@app.route("/notebook/backlinks/<entity_type>/<int:entity_id>")
@login_required
def notebook_backlinks(entity_type: str, entity_id: int):
    """Return notebook pages whose body mentions @<type> <id>.

    Scoped to pages the current user owns (via their tabs). Returns a list of
    {page_id, page_title, tab_id, tab_title, snippet, updated_at}.
    """
    if entity_type not in ("mouse", "plasmid", "order"):
        return jsonify({"ok": False, "error": "bad type"}), 400
    needle = f"@{entity_type} {entity_id}"
    with SessionLocal() as db_session:
        stmt = (
            select(NotebookPage)
            .join(NotebookTab, NotebookPage.tab_id_fk == NotebookTab.id)
            .where(NotebookTab.owner_username == g.user.username)
            .where(NotebookPage.body.ilike(f"%{needle}%"))
            .order_by(NotebookPage.updated_at.desc())
            .limit(25)
        )
        rows = db_session.scalars(stmt).all()
        items = []
        # Use a word-boundary check to avoid `@mouse 12` matching `@mouse 123`.
        import re
        pattern = re.compile(rf"@{entity_type}\s+{entity_id}(?!\d)")
        for page in rows:
            body = page.body or ""
            m = pattern.search(body)
            if not m:
                continue
            start = max(0, m.start() - 40)
            end = min(len(body), m.end() + 60)
            snippet = body[start:end].replace("\n", " ").strip()
            if start > 0:
                snippet = "…" + snippet
            if end < len(body):
                snippet = snippet + "…"
            items.append({
                "page_id": page.id,
                "page_title": page.title or "Untitled page",
                "tab_id": page.tab_id_fk,
                "tab_title": page.tab.title if page.tab else "",
                "snippet": snippet,
                "updated_at": page.updated_at.isoformat(),
            })
        return jsonify({"ok": True, "count": len(items), "items": items})


@app.route("/notebook/search/<entity_type>")
@login_required
def notebook_search_entity(entity_type: str):
    query = (request.args.get("q") or "").strip()
    limit = min(int(request.args.get("limit", 8)), 25)
    with SessionLocal() as db_session:
        if entity_type == "mouse":
            stmt = select(MouseRecord)
            if query.isdigit():
                stmt = stmt.where(MouseRecord.mouse_id == int(query))
            elif query:
                stmt = stmt.where(MouseRecord.genotype.ilike(f"%{query}%") | MouseRecord.owner.ilike(f"%{query}%"))
            stmt = stmt.order_by(MouseRecord.mouse_id.desc()).limit(limit)
            rows = db_session.scalars(stmt).all()
            return jsonify({"ok": True, "items": [
                {"id": m.mouse_id, "label": f"#{m.mouse_id} · {m.gender or '?'} · {m.genotype or '(no genotype)'}"}
                for m in rows
            ]})
        if entity_type == "plasmid":
            stmt = select(PlasmidRecord)
            if query.isdigit():
                stmt = stmt.where(PlasmidRecord.plasmid_id == int(query))
            elif query:
                stmt = stmt.where(PlasmidRecord.name.ilike(f"%{query}%") | PlasmidRecord.backbone.ilike(f"%{query}%"))
            stmt = stmt.order_by(PlasmidRecord.plasmid_id.desc()).limit(limit)
            rows = db_session.scalars(stmt).all()
            return jsonify({"ok": True, "items": [
                {"id": p.plasmid_id, "label": f"#{p.plasmid_id} · {p.name or '(no name)'} · {p.backbone or '?'}"}
                for p in rows
            ]})
        if entity_type == "order":
            rows = _order_items_query(db_session, query, limit)
            return jsonify({"ok": True, "items": [
                {"id": o.number, "label": f"#{o.number} · {o.vendor or '?'} · {o.name or '(no item)'} · {o.status or 'requested'}"}
                for o in rows
            ]})
        if entity_type == "all":
            # Unified search across mouse + plasmid + order. Each result includes
            # `type` so the editor can build the right `@<type> <id>` chip.
            per_type_limit = max(2, limit // 3)
            items: list[dict] = []

            mouse_stmt = select(MouseRecord)
            if query.isdigit():
                mouse_stmt = mouse_stmt.where(MouseRecord.mouse_id == int(query))
            elif query:
                like = f"%{query}%"
                mouse_stmt = mouse_stmt.where(
                    MouseRecord.genotype.ilike(like) | MouseRecord.owner.ilike(like)
                )
            mouse_stmt = mouse_stmt.order_by(MouseRecord.mouse_id.desc()).limit(per_type_limit)
            for m in db_session.scalars(mouse_stmt).all():
                items.append({
                    "type": "mouse",
                    "id": m.mouse_id,
                    "label": f"Mouse #{m.mouse_id} · {m.gender or '?'} · {m.genotype or '(no genotype)'}",
                })

            plasmid_stmt = select(PlasmidRecord)
            if query.isdigit():
                plasmid_stmt = plasmid_stmt.where(PlasmidRecord.plasmid_id == int(query))
            elif query:
                like = f"%{query}%"
                plasmid_stmt = plasmid_stmt.where(
                    PlasmidRecord.name.ilike(like) | PlasmidRecord.backbone.ilike(like)
                )
            plasmid_stmt = plasmid_stmt.order_by(PlasmidRecord.plasmid_id.desc()).limit(per_type_limit)
            for p in db_session.scalars(plasmid_stmt).all():
                items.append({
                    "type": "plasmid",
                    "id": p.plasmid_id,
                    "label": f"Plasmid #{p.plasmid_id} · {p.name or '(no name)'} · {p.backbone or '?'}",
                })

            for o in _order_items_query(db_session, query, per_type_limit):
                items.append({
                    "type": "order",
                    "id": o.number,
                    "label": f"Order #{o.number} · {o.vendor or '?'} · {o.name or '(no item)'}",
                })

            return jsonify({"ok": True, "items": items[:limit]})
        return jsonify({"ok": False, "error": f"Unknown entity type: {entity_type}"}), 400


@app.route("/plasmids", methods=["GET", "POST"])
@login_required
def plasmids():
    if request.method == "POST":
        import json as _json
        from .sequence_parser import parse_sequence_bytes, parse_sequence_text

        # Optional sequence: a file upload (.dna/.gbk/.fasta/...) or pasted text.
        parsed = None
        upload = request.files.get("sequence_file")
        if upload is not None and upload.filename:
            parsed = parse_sequence_bytes(upload.read(), upload.filename)
        if parsed is None:
            raw_text = (request.form.get("sequence_text") or "").strip()
            if raw_text:
                parsed = parse_sequence_text(raw_text)

        def _int_or_none(s: str):
            s = (s or "").strip()
            return int(s) if s.lstrip("-").isdigit() else None

        with SessionLocal() as db_session:
            plasmid_id_raw = request.form.get("plasmid_id", "").strip()
            if not plasmid_id_raw:
                max_existing = db_session.scalar(select(func.max(PlasmidRecord.plasmid_id))) or 0
                plasmid_id_value = max_existing + 1
            else:
                plasmid_id_value = int(plasmid_id_raw)
            existing = db_session.scalar(select(PlasmidRecord).where(PlasmidRecord.plasmid_id == plasmid_id_value))
            if existing is None:
                name = request.form.get("name", "").strip() or (parsed.get("name") if parsed else "")
                record = PlasmidRecord(
                    plasmid_id=plasmid_id_value,
                    name=name,
                    backbone=request.form.get("backbone", "").strip(),
                    insert_seq=request.form.get("insert_seq", "").strip(),
                    resistance=request.form.get("resistance", "").strip(),
                    owner=request.form.get("owner", g.user.username if g.user else "").strip(),
                    location=request.form.get("location", "").strip(),
                    notes=request.form.get("notes", "").strip(),
                    storage_box=request.form.get("storage_box", "").strip(),
                    box_row=_int_or_none(request.form.get("box_row", "")),
                    box_col=_int_or_none(request.form.get("box_col", "")),
                )
                if parsed and parsed.get("sequence"):
                    record.full_sequence = parsed["sequence"]
                    record.is_circular = bool(parsed.get("is_circular"))
                    record.features_json = _json.dumps(parsed.get("features") or [])
                    record.sequence_format = parsed.get("format", "")
                    record.sequence_uploaded_at = datetime.utcnow()
                db_session.add(record)
                db_session.commit()
                if parsed and parsed.get("sequence"):
                    flash(
                        f"Added plasmid #{plasmid_id_value} with {parsed['format'].upper()} sequence "
                        f"({len(parsed['sequence'])} bp · {len(parsed.get('features') or [])} features).",
                        "success",
                    )
        return redirect(url_for("plasmids"))
    with SessionLocal() as db_session:
        rows = db_session.scalars(select(PlasmidRecord).order_by(PlasmidRecord.plasmid_id.desc())).all()
        next_id = (db_session.scalar(select(func.max(PlasmidRecord.plasmid_id))) or 0) + 1
        # Collect the distinct list of box names that have any plasmid in
        # them — feeds the box selector dropdown in the grid view.
        boxes = sorted({(p.storage_box or "").strip() for p in rows if (p.storage_box or "").strip()})
        active_box = (request.args.get("box") or "").strip()
        if not active_box and boxes:
            active_box = boxes[0]
    return render_template(
        "plasmids.html",
        plasmids=rows,
        next_plasmid_id=next_id,
        boxes=boxes,
        active_box=active_box,
    )


@app.route("/plasmids/<int:row_id>/update", methods=["POST"])
@login_required
def update_plasmid(row_id: int):
    with SessionLocal() as db_session:
        p = db_session.get(PlasmidRecord, row_id)
        if p is None:
            return autosave_response("plasmids")
        p.name = request.form.get("name", p.name).strip()
        p.backbone = request.form.get("backbone", p.backbone).strip()
        p.insert_seq = request.form.get("insert_seq", p.insert_seq).strip()
        p.resistance = request.form.get("resistance", p.resistance).strip()
        p.owner = request.form.get("owner", p.owner).strip()
        p.location = request.form.get("location", p.location).strip()
        p.notes = request.form.get("notes", p.notes).strip()
        stamp_updated(p)
        db_session.commit()
    return autosave_response("plasmids")


@app.route("/plasmids/<int:row_id>/delete", methods=["POST"])
@login_required
def delete_plasmid(row_id: int):
    with SessionLocal() as db_session:
        p = db_session.get(PlasmidRecord, row_id)
        if p is not None:
            log_delete(
                db_session, "plasmids", p.id,
                record_label=f"Plasmid #{p.plasmid_id} {p.name}".strip(),
                details=f"backbone={p.backbone} owner={p.owner}",
            )
            db_session.delete(p)
            db_session.commit()
    return redirect(url_for("plasmids"))


# ---------------------------------------------------------------------------
# Plasmid detail page (sequence view + storage + properties tabs).
# ---------------------------------------------------------------------------


@app.route("/plasmids/<int:row_id>")
@login_required
def plasmid_detail(row_id: int):
    from .sequence_parser import parse_sequence_text  # local import
    import json as _json
    with SessionLocal() as db_session:
        p = db_session.get(PlasmidRecord, row_id)
        if p is None:
            flash("Plasmid not found.", "error")
            return redirect(url_for("plasmids"))
        try:
            features = _json.loads(p.features_json) if p.features_json else []
        except _json.JSONDecodeError:
            features = []
        data = {
            "row_id": p.id,
            "plasmid_id": p.plasmid_id,
            "name": p.name,
            "backbone": p.backbone,
            "insert_seq": p.insert_seq,
            "resistance": p.resistance,
            "owner": p.owner,
            "location": p.location,
            "notes": p.notes,
            "sequence": p.full_sequence or "",
            "is_circular": bool(p.is_circular),
            "features": features,
            "sequence_format": p.sequence_format or "",
            "sequence_uploaded_at": p.sequence_uploaded_at.strftime("%b %d, %Y %H:%M") if p.sequence_uploaded_at else "",
            "length_bp": len(p.full_sequence or ""),
            "updated_at": p.updated_at.strftime("%b %d, %Y") if p.updated_at else "",
            "updated_by": p.updated_by or "",
        }
    return render_template("plasmid_detail.html", plasmid=data)


@app.route("/plasmids/<int:row_id>/upload-sequence", methods=["POST"])
@login_required
def plasmid_upload_sequence(row_id: int):
    """Accept a FASTA / GenBank / SnapGene .dna file (or pasted text) and
    parse it into the plasmid's sequence + features. Replaces any existing
    sequence."""
    import json as _json
    from .sequence_parser import parse_sequence_bytes, parse_sequence_text

    parsed = None
    upload = request.files.get("file")
    if upload is not None and upload.filename:
        raw_bytes = upload.read()
        parsed = parse_sequence_bytes(raw_bytes, upload.filename)
    if parsed is None:
        raw_text = (request.form.get("sequence_text") or "").strip()
        if raw_text:
            parsed = parse_sequence_text(raw_text)

    if not parsed or not parsed.get("sequence"):
        flash("Couldn't parse the sequence. Use FASTA, GenBank, or SnapGene .dna format.", "error")
        return redirect(url_for("plasmid_detail", row_id=row_id))

    with SessionLocal() as db_session:
        p = db_session.get(PlasmidRecord, row_id)
        if p is None:
            return redirect(url_for("plasmids"))
        p.full_sequence = parsed["sequence"]
        p.is_circular = parsed["is_circular"]
        p.features_json = _json.dumps(parsed["features"])
        p.sequence_format = parsed["format"]
        p.sequence_uploaded_at = datetime.utcnow()
        if parsed.get("name") and not p.name:
            p.name = parsed["name"]
        stamp_updated(p)
        db_session.commit()
    flash(f"Loaded {parsed['format'].upper()} · {len(parsed['sequence'])} bp · {len(parsed['features'])} features.", "success")
    return redirect(url_for("plasmid_detail", row_id=row_id))


@app.route("/plasmids/<int:row_id>/move", methods=["POST"])
@login_required
def plasmid_move_in_box(row_id: int):
    """Update a plasmid's storage_box / box_row / box_col. Used by the
    drag-and-drop grid view. If box_row/col is empty the plasmid is moved
    to the "unplaced" pool for that box."""
    new_box = (request.form.get("storage_box") or "").strip()
    row_raw = (request.form.get("box_row") or "").strip()
    col_raw = (request.form.get("box_col") or "").strip()
    new_row = int(row_raw) if row_raw.lstrip("-").isdigit() else None
    new_col = int(col_raw) if col_raw.lstrip("-").isdigit() else None

    with SessionLocal() as db_session:
        p = db_session.get(PlasmidRecord, row_id)
        if p is None:
            return jsonify({"ok": False}), 404
        # If another plasmid is already at the destination cell in the same
        # box, swap them so the user never loses a tube reference.
        if new_box and new_row is not None and new_col is not None:
            occupant = db_session.scalar(
                select(PlasmidRecord)
                .where(PlasmidRecord.storage_box == new_box)
                .where(PlasmidRecord.box_row == new_row)
                .where(PlasmidRecord.box_col == new_col)
                .where(PlasmidRecord.id != p.id)
            )
            if occupant is not None:
                occupant.storage_box = p.storage_box
                occupant.box_row = p.box_row
                occupant.box_col = p.box_col
        p.storage_box = new_box
        p.box_row = new_row
        p.box_col = new_col
        stamp_updated(p)
        db_session.commit()
        return jsonify({"ok": True})


@app.route("/plasmids/<int:row_id>/edit-sequence", methods=["POST"])
@login_required
def plasmid_edit_sequence(row_id: int):
    """Save a hand-edited raw sequence. Strips whitespace/digits/non-ACGTN
    characters. Features whose end falls beyond the new length are dropped;
    those that are still in-range are kept untouched."""
    import json as _json
    import re as _re

    raw = request.form.get("sequence_text", "")
    # Drop FASTA header lines and GenBank metadata lines before flattening.
    lines = [ln for ln in raw.splitlines() if not ln.lstrip().startswith(">")]
    flat = "\n".join(lines)
    # Strip whitespace / digits / punctuation, then keep only IUPAC base codes.
    cleaned = _re.sub(r"[^A-Za-z]", "", flat).upper()
    cleaned = _re.sub(r"[^ACGTUMRWSYKVHDBN]", "", cleaned)

    is_circular_raw = (request.form.get("is_circular") or "").lower()
    new_circular = is_circular_raw in ("1", "true", "on", "yes")

    with SessionLocal() as db_session:
        p = db_session.get(PlasmidRecord, row_id)
        if p is None:
            return redirect(url_for("plasmids"))
        p.full_sequence = cleaned
        p.is_circular = new_circular
        # Trim out-of-range features so the viewer doesn't blow up.
        try:
            features = _json.loads(p.features_json) if p.features_json else []
        except _json.JSONDecodeError:
            features = []
        new_features = [f for f in features if int(f.get("end", -1)) < len(cleaned)]
        if len(new_features) != len(features):
            flash(
                f"Dropped {len(features) - len(new_features)} feature(s) that fell beyond the new sequence length.",
                "warning",
            )
        p.features_json = _json.dumps(new_features)
        if not p.sequence_format:
            p.sequence_format = "manual"
        p.sequence_uploaded_at = datetime.utcnow()
        stamp_updated(p)
        db_session.commit()
    flash(f"Saved sequence · {len(cleaned)} bp.", "success")
    return redirect(url_for("plasmid_detail", row_id=row_id))


@app.route("/plasmids/<int:row_id>/sequence-save", methods=["POST"])
@login_required
def plasmid_sequence_save_json(row_id: int):
    """JSON endpoint hit by the Open Vector Editor onSave callback. The body
    contains OVE's `sequenceData` shape: {sequence, circular, features, name}.
    OVE features look like {id, name, start, end, type, color, forward,
    strand, notes, locations[]}. We translate to our schema and persist."""
    import json as _json

    payload = request.get_json(silent=True) or {}
    sd = payload.get("sequenceData") or payload  # accept either wrapping
    sequence = (sd.get("sequence") or "").upper()
    is_circular = bool(sd.get("circular"))
    raw_features = sd.get("features") or []

    # Translate OVE features → our stored format. Our viewer uses
    # {start, end (inclusive), direction: 1|-1|0, name, type, color, notes}.
    translated = []
    for f in raw_features:
        start = int(f.get("start", 0) or 0)
        end = int(f.get("end", 0) or 0)
        if "forward" in f:
            direction = 1 if f.get("forward") else -1
        elif "strand" in f:
            direction = 1 if int(f.get("strand", 1) or 1) >= 0 else -1
        else:
            direction = 1
        translated.append({
            "name": f.get("name") or "",
            "type": f.get("type") or "misc_feature",
            "start": start,
            "end": end,
            "direction": direction,
            "color": f.get("color") or "#cbd5e1",
            "notes": f.get("notes") or "",
        })

    with SessionLocal() as db_session:
        p = db_session.get(PlasmidRecord, row_id)
        if p is None:
            return jsonify({"ok": False, "error": "not found"}), 404
        p.full_sequence = sequence
        p.is_circular = is_circular
        p.features_json = _json.dumps(translated)
        if not p.sequence_format:
            p.sequence_format = "ove"
        if sd.get("name") and not p.name:
            p.name = sd["name"]
        p.sequence_uploaded_at = datetime.utcnow()
        stamp_updated(p)
        db_session.commit()
    return jsonify({"ok": True, "length": len(sequence), "features": len(translated)})


@app.route("/plasmids/<int:row_id>/sequence.json")
@login_required
def plasmid_sequence_json(row_id: int):
    """Return the plasmid's sequence + features as JSON for SeqViz."""
    import json as _json
    with SessionLocal() as db_session:
        p = db_session.get(PlasmidRecord, row_id)
        if p is None:
            return jsonify({"ok": False}), 404
        try:
            features = _json.loads(p.features_json) if p.features_json else []
        except _json.JSONDecodeError:
            features = []
        # Translate stored features (direction +1/-1) into OVE's shape
        # (forward bool, plus stable `id`s so OVE can diff its render).
        ove_features = []
        for i, f in enumerate(features):
            ove_features.append({
                "id": f.get("id") or f"feat-{i}",
                "name": f.get("name") or "",
                "type": f.get("type") or "misc_feature",
                "start": int(f.get("start", 0) or 0),
                "end": int(f.get("end", 0) or 0),
                "forward": int(f.get("direction", 1) or 1) >= 0,
                "color": f.get("color") or "#cbd5e1",
                "notes": f.get("notes") or "",
            })
        return jsonify({
            "ok": True,
            "name": p.name or f"Plasmid #{p.plasmid_id}",
            "sequence": p.full_sequence or "",
            "is_circular": bool(p.is_circular),
            "circular": bool(p.is_circular),  # OVE uses this key
            "features": ove_features,
        })


@app.route("/utilities", methods=["GET", "POST"])
@login_required
def utilities():
    result = None
    with SessionLocal() as db_session:
        chemicals = db_session.scalars(select(ChemicalReference).order_by(ChemicalReference.name)).all()
        if request.method == "POST":
            mw = float(request.form["molecular_weight"])
            concentration = float(request.form["target_concentration_mm"])
            volume = float(request.form["final_volume_ml"])
            result = calculate_reagent_requirements(mw, concentration, volume)
    return render_template("utilities.html", chemicals=chemicals, result=result)


# ---------------------------------------------------------------------------
# ZEBRAFISH MODULE — parallel to the mouse colony.
# ---------------------------------------------------------------------------

ZEBRAFISH_VIEWS = ("tanks", "fish", "clutches", "lines", "racks", "water", "genotyping", "sac")


def _fish_age_label(dof):
    """dpf (≤30 d) → wpf (≤12 w) → mpf (≤24 mo) → ypf. dof = date_of_fertilization."""
    if not dof:
        return ""
    days = (date.today() - dof).days
    if days < 0:
        return ""
    if days <= 30:
        return f"{days}dpf"
    weeks = days // 7
    if weeks <= 12:
        return f"{weeks}wpf"
    months = days // 30
    if months <= 24:
        return f"{months}mpf"
    years = days // 365
    return f"{years}ypf"


def _zebrafish_context(active_view: str):
    with SessionLocal() as s:
        systems = s.scalars(select(WaterSystem).order_by(WaterSystem.name)).all()
        racks = s.scalars(select(FishRack).order_by(FishRack.name)).all()
        lines = s.scalars(select(FishLine).order_by(FishLine.name)).all()
        # Eager-load tank.line + tank.rack + tank.fish so the template can read
        # them after the session closes without DetachedInstanceError.
        tanks = s.scalars(
            select(TankRecord)
            .options(joinedload(TankRecord.line),
                     joinedload(TankRecord.rack),
                     selectinload(TankRecord.fish))
            .order_by(TankRecord.tank_id)
        ).unique().all()
        fish = s.scalars(
            select(FishRecord).options(joinedload(FishRecord.line))
            .order_by(FishRecord.id.desc()).limit(500)
        ).all()
        clutches = s.scalars(
            select(ClutchRecord).options(joinedload(ClutchRecord.line))
            .order_by(ClutchRecord.date_of_fertilization.desc()).limit(200)
        ).all()

        # Decorate clutches with derived dates + age.
        clutch_rows = []
        for c in clutches:
            tank_up = c.date_of_fertilization + timedelta(days=5) if c.date_of_fertilization else None
            fin_clip = c.date_of_fertilization + timedelta(days=30) if c.date_of_fertilization else None
            adult = c.date_of_fertilization + timedelta(days=90) if c.date_of_fertilization else None
            clutch_rows.append({
                "row": c,
                "age": _fish_age_label(c.date_of_fertilization),
                "tank_up": tank_up,
                "fin_clip": fin_clip,
                "adult": adult,
            })

        # Per-tank rollup: fish count + most-recent water reading for context.
        tank_rows = []
        for t in tanks:
            total = sum(f.count for f in t.fish if (f.status or "alive").lower() == "alive")
            tank_rows.append({"row": t, "total_fish": total, "position": fish_position_label(t)})

        # Per-system most recent water log.
        latest_logs = {}
        for sys_ in systems:
            log = s.scalar(
                select(WaterLog)
                .where(WaterLog.system_id_fk == sys_.id)
                .order_by(WaterLog.recorded_at.desc())
                .limit(1)
            )
            latest_logs[sys_.id] = log

        # Genotyping queue: tanks flagged needs_genotyping=True.
        geno_queue = s.scalars(
            select(TankRecord)
            .options(joinedload(TankRecord.line))
            .where(TankRecord.needs_genotyping == True)  # noqa: E712
            .order_by(TankRecord.tank_id)
        ).all()

        sac_log = s.scalars(
            select(FishSacLog).order_by(FishSacLog.recorded_at.desc()).limit(100)
        ).all()

        # Next free IDs. count + 1 collides as soon as anything is deleted.
        taken_tanks = set(s.scalars(select(TankRecord.tank_id)))
        next_tank_n = len(taken_tanks) + 1
        while f"T{next_tank_n:03d}" in taken_tanks:
            next_tank_n += 1
        taken_clutches = set(s.scalars(select(ClutchRecord.clutch_id)))
        next_clutch_n = len(taken_clutches) + 1
        while f"C{date.today().strftime('%y%m%d')}-{next_clutch_n}" in taken_clutches:
            next_clutch_n += 1

    # Rack grid: tanks store 0-based rows/columns; the grid payload is
    # 1-based and the page tells rack-grid.js to convert back.
    fish_racks = {
        "racks": [{"id": r.id, "name": r.name, "rows": r.rows, "cols": r.cols,
                   "naming": positions.scheme(r.naming),
                   "edit": {"data-record-payload": json.dumps({
                       "id": r.id, "_label": r.name, "name": r.name, "rows": r.rows,
                       "cols": r.cols, "system_id_fk": r.system_id_fk or "",
                       **{f"naming_{k}": v for k, v in positions.scheme(r.naming).items()}})}} for r in racks],
        "items": [{
            "id": tr["row"].id, "label": tr["row"].tank_id,
            "sub": tr["row"].line.name if tr["row"].line else tr["row"].purpose,
            "badge": str(tr["total_fish"]) if tr["total_fish"] else "",
            "tone": tr["row"].purpose if tr["row"].active else "inactive",
            "flag": tr["row"].needs_genotyping,
            "rack": tr["row"].rack_id_fk,
            "row": tr["row"].row + 1 if tr["row"].row is not None else None,
            "col": tr["row"].col + 1 if tr["row"].col is not None else None,
            "title": " · ".join(filter(None, [tr["row"].tank_id, tr["row"].line.name if tr["row"].line else "",
                                             tr["row"].purpose, f'{tr["total_fish"]} fish' if tr["total_fish"] else "",
                                             "needs genotyping" if tr["row"].needs_genotyping else ""])),
            "search": " ".join(filter(None, [tr["row"].tank_id, tr["row"].purpose, tr["row"].owner, tr["row"].card_id,
                                             tr["row"].line.name if tr["row"].line else ""])).lower(),
            "edit": {"data-record-edit": "tank-dialog", "data-record-payload": json.dumps({
                "id": tr["row"].id, "_label": tr["row"].tank_id, "tank_id": tr["row"].tank_id,
                "purpose": tr["row"].purpose, "line_id_fk": tr["row"].line_id_fk or "",
                "owner": tr["row"].owner, "rack_id_fk": tr["row"].rack_id_fk or "",
                "position": fish_position_label(tr["row"]),
                "card_id": tr["row"].card_id, "notes": tr["row"].notes})},
        } for tr in tank_rows],
        "create": {"attrs": {"data-record-edit": "tank-dialog"},
                   "payload": {"tank_id": f"T{next_tank_n:03d}", "purpose": "stock",
                               "owner": g.user.username if g.user else ""},
                   "rack_field": "rack_id_fk", "text_field": "position"},
    }

    return {
        "active_view": active_view if active_view in ZEBRAFISH_VIEWS else "tanks",
        "zebrafish_views": ZEBRAFISH_VIEWS,
        "fish_racks": fish_racks,
        "tank_purpose_options": TANK_PURPOSE_OPTIONS,
        "fish_sex_options": FISH_SEX_OPTIONS,
        "fish_status_options": FISH_STATUS_OPTIONS,
        "systems": systems,
        "racks": racks,
        "lines": lines,
        "tanks": tanks,
        "tank_rows": tank_rows,
        "fish": fish,
        "clutch_rows": clutch_rows,
        "latest_logs": latest_logs,
        "geno_queue": geno_queue,
        "sac_log": sac_log,
        "next_tank_id": f"T{next_tank_n:03d}",
        "next_clutch_id": f"C{date.today().strftime('%y%m%d')}-{next_clutch_n}",
        "now_date": date.today(),
        "today_iso": date.today().isoformat(),
    }


@app.route("/zebrafish")
@login_required
def zebrafish():
    active_view = request.args.get("view", "tanks")
    return render_template("zebrafish.html", **_zebrafish_context(active_view))


# ---- Tanks -----------------------------------------------------------------


def fish_position_label(tank) -> str:
    """A tank's position under its rack's naming scheme ("C3"). Tanks store
    0-based rows and columns."""
    rack = tank.rack
    if rack is None or tank.row is None or tank.col is None:
        return ""
    return positions.label(tank.row + 1, tank.col + 1, rack.naming, rack.cols)


def apply_fish_position(s, tank, raw) -> str | None:
    """Set a tank's row/col from a typed position; an error message instead
    of a guess. Needs the tank's rack to be set first."""
    raw = (raw or "").strip()
    if not raw:
        tank.row = tank.col = None
        return None
    rack = s.get(FishRack, tank.rack_id_fk) if tank.rack_id_fk else None
    if rack is None:
        return f"Pick a rack before giving a position (“{raw}” was not saved)."
    cell = positions.parse(raw, rack.naming, rack.rows, rack.cols)
    if cell is None:
        return (f"“{raw}” is not a position in {rack.name} "
                f"({positions.label(1, 1, rack.naming, rack.cols)}–{positions.label(rack.rows, rack.cols, rack.naming, rack.cols)}).")
    row, col = cell[0] - 1, cell[1] - 1
    holder = s.scalar(select(TankRecord).where(
        TankRecord.rack_id_fk == rack.id, TankRecord.row == row, TankRecord.col == col,
        TankRecord.id != (tank.id or 0)))
    if holder is not None:
        return f"{rack.name} · {raw} already holds tank {holder.tank_id}. Drag on the rack grid to swap."
    tank.row, tank.col = row, col
    return None


@app.route("/zebrafish/tanks/create", methods=["POST"])
@login_required
def zebrafish_create_tank():
    with SessionLocal() as s:
        tank_id = (request.form.get("tank_id") or "").strip()
        if not tank_id:
            taken = set(s.scalars(select(TankRecord.tank_id)))
            n = len(taken) + 1
            while f"T{n:03d}" in taken:
                n += 1
            tank_id = f"T{n:03d}"
        rack_id = request.form.get("rack_id_fk") or None
        line_id = request.form.get("line_id_fk") or None
        tank = TankRecord(
            tank_id=tank_id,
            rack_id_fk=int(rack_id) if rack_id else None,
            row=int(request.form["row"]) if request.form.get("row") else None,
            col=int(request.form["col"]) if request.form.get("col") else None,
            purpose=request.form.get("purpose", "stock"),
            line_id_fk=int(line_id) if line_id else None,
            owner=request.form.get("owner", g.user.username if g.user else "").strip(),
            card_id=request.form.get("card_id", "").strip(),
            notes=request.form.get("notes", "").strip(),
        )
        s.add(tank)
        if "position" in request.form:
            error = apply_fish_position(s, tank, request.form.get("position"))
            if error:
                flash(f"Tank {tank_id} was created but not placed: {error}", "error")
        s.commit()
    return autosave_response("zebrafish")


@app.route("/zebrafish/tanks/<int:tank_row_id>/update", methods=["POST"])
@login_required
def zebrafish_update_tank(tank_row_id: int):
    with SessionLocal() as s:
        t = s.get(TankRecord, tank_row_id)
        if t is None:
            return autosave_response("zebrafish")
        for fld in ("tank_id", "purpose", "owner", "card_id", "notes"):
            if fld in request.form:
                setattr(t, fld, (request.form.get(fld) or "").strip())
        if "rack_id_fk" in request.form:
            v = request.form.get("rack_id_fk") or None
            t.rack_id_fk = int(v) if v else None
        if "line_id_fk" in request.form:
            v = request.form.get("line_id_fk") or None
            t.line_id_fk = int(v) if v else None
        if "row" in request.form:
            v = request.form.get("row") or ""
            t.row = int(v) if v.isdigit() else None
        if "col" in request.form:
            v = request.form.get("col") or ""
            t.col = int(v) if v.isdigit() else None
        if "active" in request.form:
            t.active = request.form.get("active", "1") not in ("0", "false", "no", "off")
        if "position" in request.form:
            error = apply_fish_position(s, t, request.form.get("position"))
            if error:
                s.rollback()
                flash(error, "error")
                return autosave_response("zebrafish")
        s.commit()
    return autosave_response("zebrafish")


@app.route("/zebrafish/tanks/<int:tank_row_id>/move", methods=["POST"])
@login_required
def zebrafish_move_tank(tank_row_id: int):
    """Drag-and-drop within rack grid. Same swap-on-collision behavior as the
    plasmid box move endpoint."""
    new_rack = (request.form.get("rack_id_fk") or "").strip()
    row_raw = (request.form.get("row") or "").strip()
    col_raw = (request.form.get("col") or "").strip()
    new_rack_id = int(new_rack) if new_rack.isdigit() else None
    new_row = int(row_raw) if row_raw.lstrip("-").isdigit() else None
    new_col = int(col_raw) if col_raw.lstrip("-").isdigit() else None
    with SessionLocal() as s:
        t = s.get(TankRecord, tank_row_id)
        if t is None:
            return jsonify({"ok": False}), 404
        if new_rack_id and new_row is not None and new_col is not None:
            occupant = s.scalar(
                select(TankRecord)
                .where(TankRecord.rack_id_fk == new_rack_id)
                .where(TankRecord.row == new_row)
                .where(TankRecord.col == new_col)
                .where(TankRecord.id != t.id)
            )
            if occupant is not None:
                occupant.rack_id_fk = t.rack_id_fk
                occupant.row = t.row
                occupant.col = t.col
        t.rack_id_fk = new_rack_id
        t.row = new_row
        t.col = new_col
        s.commit()
    return jsonify({"ok": True})


@app.route("/zebrafish/tanks/<int:tank_row_id>/delete", methods=["POST"])
@login_required
def zebrafish_delete_tank(tank_row_id: int):
    with SessionLocal() as s:
        t = s.get(TankRecord, tank_row_id)
        if t is not None:
            s.delete(t)
            s.commit()
    return redirect(url_for("zebrafish", view="tanks"))


@app.route("/zebrafish/tanks/<int:tank_row_id>/toggle-geno", methods=["POST"])
@login_required
def zebrafish_toggle_geno(tank_row_id: int):
    with SessionLocal() as s:
        t = s.get(TankRecord, tank_row_id)
        if t is None:
            return jsonify({"ok": False}), 404
        t.needs_genotyping = not bool(t.needs_genotyping)
        s.commit()
        return jsonify({"ok": True, "needs_genotyping": t.needs_genotyping})


# ---- Fish (group rows) -----------------------------------------------------


@app.route("/zebrafish/fish/create", methods=["POST"])
@login_required
def zebrafish_create_fish():
    with SessionLocal() as s:
        tank_fk = request.form.get("tank_id_fk")
        if not tank_fk:
            return redirect(url_for("zebrafish", view="fish"))
        line_id = request.form.get("line_id_fk") or None
        s.add(FishRecord(
            tank_id_fk=int(tank_fk),
            line_id_fk=int(line_id) if line_id else None,
            individual_id=request.form.get("individual_id", "").strip(),
            count=int(request.form.get("count", "1") or 1),
            sex=request.form.get("sex", "mixed"),
            status=request.form.get("status", "alive"),
            date_of_fertilization=parse_date(request.form.get("date_of_fertilization")),
            genotype=request.form.get("genotype", "").strip(),
            notes=request.form.get("notes", "").strip(),
        ))
        s.commit()
    return redirect(url_for("zebrafish", view="fish"))


@app.route("/zebrafish/fish/<int:fish_row_id>/update", methods=["POST"])
@login_required
def zebrafish_update_fish(fish_row_id: int):
    with SessionLocal() as s:
        f = s.get(FishRecord, fish_row_id)
        if f is None:
            return autosave_response("zebrafish")
        for fld in ("individual_id", "sex", "status", "genotype", "notes"):
            if fld in request.form:
                setattr(f, fld, (request.form.get(fld) or "").strip())
        if "count" in request.form:
            v = (request.form.get("count") or "1").strip()
            f.count = int(v) if v.lstrip("-").isdigit() else 1
        if "line_id_fk" in request.form:
            v = request.form.get("line_id_fk") or None
            f.line_id_fk = int(v) if v else None
        if "tank_id_fk" in request.form:
            v = request.form.get("tank_id_fk") or None
            f.tank_id_fk = int(v) if v else f.tank_id_fk
        if "date_of_fertilization" in request.form:
            f.date_of_fertilization = parse_date(request.form.get("date_of_fertilization"))
        s.commit()
    return autosave_response("zebrafish")


@app.route("/zebrafish/fish/<int:fish_row_id>/delete", methods=["POST"])
@login_required
def zebrafish_delete_fish(fish_row_id: int):
    with SessionLocal() as s:
        f = s.get(FishRecord, fish_row_id)
        if f is not None:
            s.delete(f)
            s.commit()
    return redirect(url_for("zebrafish", view="fish"))


# ---- Lines -----------------------------------------------------------------


@app.route("/zebrafish/lines/create", methods=["POST"])
@login_required
def zebrafish_create_line():
    with SessionLocal() as s:
        parent = request.form.get("parent_line_id_fk") or None
        s.add(FishLine(
            name=(request.form.get("name") or "").strip() or "Unnamed line",
            zfin_name=request.form.get("zfin_name", "").strip(),
            background=request.form.get("background", "").strip(),
            transgene_summary=request.form.get("transgene_summary", "").strip(),
            allele=request.form.get("allele", "").strip(),
            iacuc_protocol=request.form.get("iacuc_protocol", "").strip(),
            founder_info=request.form.get("founder_info", "").strip(),
            parent_line_id_fk=int(parent) if parent else None,
            notes=request.form.get("notes", "").strip(),
        ))
        s.commit()
    return redirect(url_for("zebrafish", view="lines"))


@app.route("/zebrafish/lines/<int:line_id>/update", methods=["POST"])
@login_required
def zebrafish_update_line(line_id: int):
    with SessionLocal() as s:
        ln = s.get(FishLine, line_id)
        if ln is None:
            return autosave_response("zebrafish")
        for fld in ("name", "zfin_name", "background", "transgene_summary",
                    "allele", "iacuc_protocol", "founder_info", "notes"):
            if fld in request.form:
                setattr(ln, fld, (request.form.get(fld) or "").strip())
        if "parent_line_id_fk" in request.form:
            v = request.form.get("parent_line_id_fk") or None
            ln.parent_line_id_fk = int(v) if v else None
        s.commit()
    return autosave_response("zebrafish")


@app.route("/zebrafish/lines/<int:line_id>/delete", methods=["POST"])
@login_required
def zebrafish_delete_line(line_id: int):
    with SessionLocal() as s:
        ln = s.get(FishLine, line_id)
        if ln is not None:
            s.delete(ln)
            s.commit()
    return redirect(url_for("zebrafish", view="lines"))


@app.route("/zebrafish/lines/<int:line_id>")
@login_required
def zebrafish_line_detail(line_id: int):
    """Per-line detail page with founder lineage tree."""
    with SessionLocal() as s:
        ln = s.get(FishLine, line_id)
        if ln is None:
            flash("Line not found.", "error")
            return redirect(url_for("zebrafish", view="lines"))

        # Build the ancestor chain.
        ancestors = []
        cursor = ln.parent_line
        while cursor is not None and len(ancestors) < 10:
            ancestors.insert(0, cursor)
            cursor = cursor.parent_line

        # Direct children.
        children = s.scalars(select(FishLine).where(FishLine.parent_line_id_fk == ln.id)).all()

        # Tanks currently holding this line.
        # Racks are read after the session closes, so load them now.
        line_tanks = s.scalars(
            select(TankRecord).options(joinedload(TankRecord.rack))
            .where(TankRecord.line_id_fk == ln.id).order_by(TankRecord.tank_id)
        ).all()

        all_lines = s.scalars(select(FishLine).order_by(FishLine.name)).all()

    return render_template(
        "zebrafish_line_detail.html",
        line=ln, ancestors=ancestors, children=children,
        line_tanks=line_tanks, all_lines=all_lines,
    )


# ---- Racks -----------------------------------------------------------------


@app.route("/zebrafish/racks/create", methods=["POST"])
@login_required
def zebrafish_create_rack():
    with SessionLocal() as s:
        sys_fk = request.form.get("system_id_fk") or None
        s.add(FishRack(
            name=(request.form.get("name") or "").strip() or "Rack",
            system_id_fk=int(sys_fk) if sys_fk else None,
            rows=int(request.form.get("rows", "8") or 8),
            cols=int(request.form.get("cols", "10") or 10),
            naming=json.dumps(positions.scheme_from_form(request.form)),
            notes=request.form.get("notes", "").strip(),
        ))
        s.commit()
    return redirect(url_for("zebrafish", view="tanks", mode="grid"))


@app.route("/zebrafish/racks/<int:rack_id>/update", methods=["POST"])
@login_required
def zebrafish_update_rack(rack_id: int):
    """Rename or resize a rack. Tanks outside a smaller grid keep their
    numbers and show as unplaced until moved."""
    with SessionLocal() as s:
        r = s.get(FishRack, rack_id)
        if r is None:
            flash("That rack no longer exists.", "error")
        else:
            r.name = (request.form.get("name") or "").strip() or r.name
            r.rows = max(1, min(26, int(request.form.get("rows") or r.rows)))
            r.cols = max(1, min(40, int(request.form.get("cols") or r.cols)))
            sys_fk = request.form.get("system_id_fk")
            if sys_fk is not None:
                r.system_id_fk = int(sys_fk) if sys_fk.isdigit() else None
            if "naming_mode" in request.form:
                r.naming = json.dumps(positions.scheme_from_form(request.form))
            s.commit()
            flash(f"Saved rack {r.name}.", "success")
    return redirect(url_for("zebrafish", view="tanks", mode="grid"))


@app.route("/zebrafish/racks/<int:rack_id>/delete", methods=["POST"])
@login_required
def zebrafish_delete_rack(rack_id: int):
    with SessionLocal() as s:
        r = s.get(FishRack, rack_id)
        if r is not None:
            # Detach tanks from the deleted rack rather than cascading delete.
            for t in r.tanks:
                t.rack_id_fk = None
                t.row = None
                t.col = None
            s.delete(r)
            s.commit()
    return redirect(url_for("zebrafish", view="tanks", mode="grid"))


# ---- Water systems + logs --------------------------------------------------


@app.route("/zebrafish/systems/create", methods=["POST"])
@login_required
def zebrafish_create_system():
    with SessionLocal() as s:
        s.add(WaterSystem(
            name=(request.form.get("name") or "").strip() or "System",
            room=request.form.get("room", "").strip(),
            target_temp_c=_safe_float(request.form.get("target_temp_c")),
            target_ph=_safe_float(request.form.get("target_ph")),
            target_conductivity=_safe_float(request.form.get("target_conductivity")),
            notes=request.form.get("notes", "").strip(),
        ))
        s.commit()
    return redirect(url_for("zebrafish", view="water"))


def _safe_float(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@app.route("/zebrafish/water/log", methods=["POST"])
@login_required
def zebrafish_log_water():
    with SessionLocal() as s:
        sys_fk = request.form.get("system_id_fk")
        if not sys_fk:
            return redirect(url_for("zebrafish", view="water"))
        s.add(WaterLog(
            system_id_fk=int(sys_fk),
            ph=_safe_float(request.form.get("ph")),
            conductivity=_safe_float(request.form.get("conductivity")),
            temperature_c=_safe_float(request.form.get("temperature_c")),
            salinity=_safe_float(request.form.get("salinity")),
            alarm=request.form.get("alarm") in ("1", "on", "true", "yes"),
            recorded_by=g.user.username if g.user else "",
            notes=request.form.get("notes", "").strip(),
        ))
        s.commit()
    return redirect(url_for("zebrafish", view="water"))


@app.route("/zebrafish/water/<int:system_id>/series.json")
@login_required
def zebrafish_water_series(system_id: int):
    """Return last 30 days of readings for one system — used by the trend chart."""
    cutoff = datetime.utcnow() - timedelta(days=30)
    with SessionLocal() as s:
        logs = s.scalars(
            select(WaterLog)
            .where(WaterLog.system_id_fk == system_id)
            .where(WaterLog.recorded_at >= cutoff)
            .order_by(WaterLog.recorded_at.asc())
        ).all()
        return jsonify({
            "ok": True,
            "series": [
                {
                    "t": log.recorded_at.isoformat(),
                    "ph": log.ph, "cond": log.conductivity,
                    "temp": log.temperature_c, "salinity": log.salinity,
                    "alarm": bool(log.alarm), "notes": log.notes or "",
                }
                for log in logs
            ],
        })


# ---- Clutches + mating wizard ---------------------------------------------


@app.route("/zebrafish/clutches/create", methods=["POST"])
@login_required
def zebrafish_create_clutch():
    with SessionLocal() as s:
        cn = (s.scalar(select(func.count(ClutchRecord.id))) or 0) + 1
        clutch_id = (request.form.get("clutch_id") or f"C{date.today().strftime('%y%m%d')}-{cn}").strip()
        line_id = request.form.get("line_id_fk") or None
        ftank = request.form.get("father_tank_id") or None
        mtank = request.form.get("mother_tank_id") or None
        s.add(ClutchRecord(
            clutch_id=clutch_id,
            date_of_fertilization=parse_date(request.form.get("date_of_fertilization")) or date.today(),
            line_id_fk=int(line_id) if line_id else None,
            father_tank_id=int(ftank) if ftank else None,
            mother_tank_id=int(mtank) if mtank else None,
            embryo_count=int(request.form.get("embryo_count", "0") or 0),
            larvae_count=int(request.form.get("larvae_count", "0") or 0),
            adults_count=int(request.form.get("adults_count", "0") or 0),
            owner=g.user.username if g.user else "",
            notes=request.form.get("notes", "").strip(),
        ))
        s.commit()
    return redirect(url_for("zebrafish", view="clutches"))


@app.route("/zebrafish/clutches/<int:clutch_row_id>/update", methods=["POST"])
@login_required
def zebrafish_update_clutch(clutch_row_id: int):
    with SessionLocal() as s:
        c = s.get(ClutchRecord, clutch_row_id)
        if c is None:
            return autosave_response("zebrafish")
        for fld in ("clutch_id", "notes"):
            if fld in request.form:
                setattr(c, fld, (request.form.get(fld) or "").strip())
        for ifld in ("embryo_count", "larvae_count", "adults_count"):
            if ifld in request.form:
                v = (request.form.get(ifld) or "0").strip()
                setattr(c, ifld, int(v) if v.lstrip("-").isdigit() else 0)
        if "date_of_fertilization" in request.form:
            c.date_of_fertilization = parse_date(request.form.get("date_of_fertilization")) or c.date_of_fertilization
        if "line_id_fk" in request.form:
            v = request.form.get("line_id_fk") or None
            c.line_id_fk = int(v) if v else None
        s.commit()
    return autosave_response("zebrafish")


@app.route("/zebrafish/clutches/<int:clutch_row_id>/delete", methods=["POST"])
@login_required
def zebrafish_delete_clutch(clutch_row_id: int):
    with SessionLocal() as s:
        c = s.get(ClutchRecord, clutch_row_id)
        if c is not None:
            s.delete(c)
            s.commit()
    return redirect(url_for("zebrafish", view="clutches"))


@app.route("/zebrafish/mate", methods=["POST"])
@login_required
def zebrafish_set_up_mating():
    """Create a mating tank from a ♂×♀ pair. Picks an empty tank position
    if none specified. Sets a return date (default +1 day)."""
    with SessionLocal() as s:
        father_id = request.form.get("father_tank_id")
        mother_id = request.form.get("mother_tank_id")
        if not father_id or not mother_id:
            flash("Pick both a father and mother tank.", "error")
            return redirect(url_for("zebrafish", view="clutches"))
        try:
            return_days = int(request.form.get("return_days", "1") or 1)
        except ValueError:
            return_days = 1
        # Auto-name the mating tank: M-<father>-<mother>-<date>.
        n = (s.scalar(select(func.count(TankRecord.id))) or 0) + 1
        tank = TankRecord(
            tank_id=f"MT{n:03d}",
            purpose="mating",
            mating_father_tank_id=int(father_id),
            mating_mother_tank_id=int(mother_id),
            mating_return_at=date.today() + timedelta(days=return_days),
            owner=g.user.username if g.user else "",
            notes=request.form.get("notes", "").strip(),
        )
        s.add(tank)
        s.commit()
        flash(f"Mating tank {tank.tank_id} set up · return by {tank.mating_return_at.isoformat()}.", "success")
    return redirect(url_for("zebrafish", view="tanks"))


# ---- Sac log ---------------------------------------------------------------


@app.route("/zebrafish/sac/create", methods=["POST"])
@login_required
def zebrafish_create_sac_log():
    with SessionLocal() as s:
        tank_fk = request.form.get("tank_id_fk") or None
        line_fk = request.form.get("line_id_fk") or None
        s.add(FishSacLog(
            tank_id_fk=int(tank_fk) if tank_fk else None,
            line_id_fk=int(line_fk) if line_fk else None,
            count=int(request.form.get("count", "1") or 1),
            reason=(request.form.get("reason") or "").strip(),
            recorded_by=g.user.username if g.user else "",
        ))
        s.commit()
    return redirect(url_for("zebrafish", view="sac"))


@app.route("/zebrafish/tanks/<int:tank_row_id>/card")
@login_required
def zebrafish_tank_card(tank_row_id: int):
    """Printable tank card — one tank, single page."""
    with SessionLocal() as s:
        t = s.get(TankRecord, tank_row_id)
        if t is None:
            return redirect(url_for("zebrafish", view="tanks"))
        return render_template("zebrafish_tank_card.html", tank=t,
                               age_for_clutch=lambda dof: _fish_age_label(dof))


if __name__ == "__main__":
    app.run(debug=True)
