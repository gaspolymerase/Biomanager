"""What this lab uses, and who sees which database.

Four questions, answered in one place so the sidebar, the home page, the
setup survey and the routes all agree:

- **Is a lab function switched on?** The three hand-written databases
  (mouse colony, zebrafish, plasmids) and the calendar and notebook are on
  unless an admin turned them off (`feature:<key>` in app_settings). The
  configurable databases (fly and worm stocks, organism databases,
  inventories) use their own `enabled` flag.
- **Has the lab been set up?** The first admin answers a short survey
  (/setup) choosing what the lab keeps; until then everything stays on, as
  it always was.
- **Who may add databases?** Admins always. Members may add their own
  (personal) databases unless an admin turned that off, and may add
  databases for the whole lab only if an admin allowed it.
- **Who sees a database?** A lab database: everyone. A personal one
  (`private_to` = its owner): its owner, and admins, who look after the lab.
  In the sidebar and on the home page each person sees the lab's databases
  and their own, not other people's personal ones.

Turning something off hides it and refuses its pages; nothing is deleted,
and turning it back on brings everything back.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from flask import g


@dataclass(frozen=True)
class Feature:
    key: str
    label: str
    blurb: str
    icon: str
    kind: str                  # "database" | "function"
    path_prefixes: tuple[str, ...]


# The hand-written parts of the app that can be switched off lab-wide.
FEATURES: dict[str, Feature] = {f.key: f for f in (
    Feature("colony", "Mouse colony", "Mice, cages, litters, breeders, experiments and strains.",
            "mouse", "database", ("/colony",)),
    Feature("zebrafish", "Zebrafish", "Tanks on racks, fish, lines, clutches and matings.",
            "fish", "database", ("/zebrafish",)),
    Feature("plasmids", "Plasmids", "Plasmids with sequence maps, in boxes.",
            "plasmid", "database", ("/plasmids",)),
    Feature("calendar", "Calendar", "Lab events, to-dos and colony dates in one calendar.",
            "calendar", "function", ("/calendar",)),
    Feature("notebook", "Notebook", "Protocols and lab notes, linked to animals.",
            "notebook", "function", ("/notebook",)),
)}

# Configurable databases the survey offers, by the preset they are made from.
STOCK_CHOICES = {
    "fly": ("Fruit flies", "Drosophila vials in racks and incubators, with flip schedules.", "fly"),
    "worm": ("C. elegans", "Worm plates, chunking and freezing.", "worm"),
}
INVENTORY_CHOICES = {
    "samples": ("Samples", "Tissue, DNA and other samples, in boxes.", "vial"),
    "orders": ("Orders", "What the lab has asked to buy, and when it arrived.", "cart"),
    "reagents": ("Reagents", "Chemicals and kits, with lots, expiry and low-stock warnings.", "flask"),
    "antibodies": ("Antibodies", "Antibodies with host, target and dilution.", "antibody"),
}

# Member permissions (app_settings), with their defaults.
MEMBER_PERMISSIONS = {
    "members_create_databases": ("Members may create their own databases",
                                 "A personal database only its owner (and admins) sees.", True),
    "members_share_databases": ("Members may add databases for the whole lab",
                                "Otherwise only admins add lab databases, and members share theirs through an admin.", False),
}

SETUP_DONE_KEY = "lab_setup_done"


# ---------------------------------------------------------------- settings

def _settings():
    from .inventory_service import get_setting, set_setting
    return get_setting, set_setting


def _flag(session, key: str, default: bool) -> bool:
    get_setting, _ = _settings()
    raw = get_setting(session, key, "")
    return default if raw == "" else raw == "on"


def _set_flag(session, key: str, on: bool) -> None:
    _, set_setting = _settings()
    set_setting(session, key, "on" if on else "off")


def feature_on(session, key: str) -> bool:
    return _flag(session, f"feature:{key}", True)


def set_feature(session, key: str, on: bool) -> None:
    _set_flag(session, f"feature:{key}", on)


def features_on(session) -> dict[str, bool]:
    return {key: feature_on(session, key) for key in FEATURES}


def permission(session, key: str) -> bool:
    return _flag(session, key, MEMBER_PERMISSIONS[key][2])


def setup_done(session) -> bool:
    get_setting, _ = _settings()
    return bool(get_setting(session, SETUP_DONE_KEY, ""))


def mark_setup_done(session) -> None:
    _, set_setting = _settings()
    set_setting(session, SETUP_DONE_KEY, datetime.utcnow().isoformat(timespec="seconds"))


def lab_name(session) -> str:
    get_setting, _ = _settings()
    return get_setting(session, "lab_name", "")


def request_features() -> dict[str, bool]:
    """features_on for this request, read once."""
    if "lab_features" not in g:
        from .db import SessionLocal
        with SessionLocal() as session:
            g.lab_features = features_on(session)
    return g.lab_features


def feature_for_path(path: str) -> Feature | None:
    for feature in FEATURES.values():
        if any(path == p or path.startswith(p + "/") for p in feature.path_prefixes):
            return feature
    return None


# ---------------------------------------------------------------- who sees what

def is_personal(module) -> bool:
    return bool(getattr(module, "private_to", "") or "")


def can_see(module, user=None) -> bool:
    """May this person open the database at all?"""
    user = user if user is not None else g.get("user")
    if not is_personal(module):
        return True
    if user is None:
        return False
    return user.role == "admin" or module.private_to == user.username


def in_sidebar(module, user=None) -> bool:
    """Is it one of *their* databases: the lab's, or their own?"""
    user = user if user is not None else g.get("user")
    if not is_personal(module):
        return True
    return user is not None and module.private_to == user.username


def visible_list(modules):
    """The databases the signed-in person should see listed: the lab's and
    their own. Outside a request (a script, a reminder email): all."""
    from flask import has_request_context
    if not has_request_context():
        return modules
    return [m for m in modules if in_sidebar(m)]


def may_create_database(session, user=None) -> bool:
    user = user if user is not None else g.get("user")
    if user is None:
        return False
    return user.role == "admin" or permission(session, "members_create_databases")


def may_create_lab_database(session, user=None) -> bool:
    user = user if user is not None else g.get("user")
    if user is None:
        return False
    return user.role == "admin" or permission(session, "members_share_databases")


def audience_for_new(session, requested: str, user=None) -> str:
    """The private_to value for a database this person is creating:
    "" for the lab when they asked for it and may, else their username.
    No choice at all (a script, an older form) means each role's default:
    the lab's for an admin, their own for a member."""
    user = user if user is not None else g.get("user")
    if requested not in ("lab", "me"):
        requested = "lab" if user.role == "admin" else "me"
    if requested == "lab" and may_create_lab_database(session, user):
        return ""
    return user.username


def lab_audience(session, user=None) -> dict:
    """For a "new database" form: may this person choose the whole lab, and
    which choice starts selected."""
    user = user if user is not None else g.get("user")
    may_lab = may_create_lab_database(session, user)
    return {"may_lab": may_lab, "default": "lab" if (user is not None and user.role == "admin") else "me"}


def can_change_audience(session, module, user=None) -> bool:
    user = user if user is not None else g.get("user")
    if user is None:
        return False
    if user.role == "admin":
        return True
    return is_personal(module) and module.private_to == user.username \
        and permission(session, "members_share_databases")


# ---------------------------------------------------------------- the survey

def _stock_by_kind(session, kind):
    from .models import StockModule
    from sqlalchemy import select
    return session.scalars(select(StockModule).where(StockModule.kind == kind, StockModule.private_to == "")
                           .order_by(StockModule.position, StockModule.id)).all()


def _inventory_by_kind(session, kind):
    from .models import InventoryModule
    from sqlalchemy import select
    return session.scalars(select(InventoryModule).where(InventoryModule.kind == kind,
                                                         InventoryModule.private_to == "")
                           .order_by(InventoryModule.position, InventoryModule.id)).all()


def survey_state(session) -> dict:
    """What the survey form should show as chosen right now."""
    return {
        "features": features_on(session),
        "stocks": {kind: any(m.enabled for m in _stock_by_kind(session, kind)) for kind in STOCK_CHOICES},
        "inventories": {kind: any(m.enabled for m in _inventory_by_kind(session, kind)) for kind in INVENTORY_CHOICES},
        "permissions": {key: permission(session, key) for key in MEMBER_PERMISSIONS},
        "lab_name": lab_name(session),
    }


def apply_survey(session, form, actor: str) -> list[str]:
    """Save the survey. Returns the labels of databases and functions it
    switched on that were off, for telling the lab. Nothing is deleted:
    a database the lab stops using is only switched off."""
    from . import inventory_service, stock_service
    _, set_setting = _settings()
    before = survey_state(session)
    switched_on: list[str] = []

    for key, feature in FEATURES.items():
        on = form.get(f"feature:{key}") == "1"
        if on and not before["features"][key]:
            switched_on.append(feature.label)
        set_feature(session, key, on)

    for kind, (label, _blurb, _icon) in STOCK_CHOICES.items():
        wanted = form.get(f"stock:{kind}") == "1"
        existing = _stock_by_kind(session, kind)
        if wanted and not existing:
            stock_service.create_module(session, kind, label, actor)
            switched_on.append(label)
        for module in existing:
            if wanted and not module.enabled:
                switched_on.append(module.label)
            module.enabled = wanted

    for kind, (label, _blurb, _icon) in INVENTORY_CHOICES.items():
        wanted = form.get(f"inventory:{kind}") == "1"
        existing = _inventory_by_kind(session, kind)
        if wanted and not existing:
            inventory_service.create_module(session, kind, label, actor)
            switched_on.append(label)
        for module in existing:
            if wanted and not module.enabled:
                switched_on.append(module.label)
            module.enabled = wanted

    for key in MEMBER_PERMISSIONS:
        _set_flag(session, key, form.get(key) == "1")
    set_setting(session, "lab_name", (form.get("lab_name") or "").strip()[:80])
    mark_setup_done(session)
    return switched_on


def custom_databases(session) -> list[dict]:
    """Every configurable database the survey does not cover by kind: made
    from the organism builder, a custom inventory, or someone's own."""
    from . import inventory_service, organism_service, stock_service
    out = []
    for kind_label, service, prefix in (("Animals", organism_service, "organisms"),
                                        ("Stocks", stock_service, "stocks"),
                                        ("Inventory", inventory_service, "inventory")):
        for module in service.list_modules(session, include_disabled=True, everyone=True):
            covered = ((prefix == "stocks" and module.kind in STOCK_CHOICES and not is_personal(module))
                       or (prefix == "inventory" and module.kind in INVENTORY_CHOICES and not is_personal(module)))
            if covered:
                continue
            out.append({"kind": prefix, "kind_label": kind_label, "key": module.key, "label": module.label,
                        "enabled": module.enabled, "private_to": module.private_to or "",
                        "created_by": module.created_by or ""})
    return out


def set_module_enabled(session, kind: str, key: str, on: bool):
    module = _module(session, kind, key)
    if module is not None:
        module.enabled = on
    return module


def _module(session, kind: str, key: str):
    from . import inventory_service, organism_service, stock_service
    service = {"organisms": organism_service, "stocks": stock_service, "inventory": inventory_service}.get(kind)
    return service.get_module(session, key) if service else None


def module_for(session, kind: str, key: str):
    return _module(session, kind, key)


def everyone_but(session, username: str) -> list[str]:
    from sqlalchemy import select
    from .models import UserAccount
    return list(session.scalars(select(UserAccount.username).where(
        UserAccount.username != username, UserAccount.disabled.is_(False),
        UserAccount.role != "pending")).all())

