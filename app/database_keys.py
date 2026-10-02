"""A database's address follows its name.

Every inventory, stock collection and organism database has a key, its
address: /inventory/antibodies, /stocks/drosophila. Renaming "Antibodies"
to "Primary antibodies" moves it to /inventory/primary_antibodies, and the
old key is kept in database_aliases, so whatever holds the old address still
finds it: printed QR labels, bookmarks and saved tabs, old notifications,
"@antibodies 5" in notebook pages (signed ones can't be rewritten), and
scripts using the API. A page opened at an old address is sent on to the
new one (the routes' _module_or_404).

What the app stores with a key in it, it rewrites here, so exact matches
keep matching: an order's "stocked_as", an experiment's database, a
sample's source. Organism codes keep the stem of the first key (DROS-A012
stays DROS-A013 after a rename), see first_key().
"""
from __future__ import annotations

import json

from sqlalchemy import select

from .models import (DatabaseAlias, Experiment, InventoryItem, InventoryModule, OrganismModule, StockModule)

MODELS = {"inventory": InventoryModule, "stocks": StockModule, "organisms": OrganismModule}
MAX_KEY = 60


def resolve(session, kind: str, key: str):
    """The database that had this address, or None."""
    alias = session.scalar(select(DatabaseAlias).where(DatabaseAlias.kind == kind, DatabaseAlias.old_key == key))
    return session.get(MODELS[kind], alias.module_id) if alias is not None else None


def to_current(module, key: str) -> None:
    """A page asked for by an old address goes on to the current one (a
    redirect, same query and view); a form sent from a page opened before the
    rename is simply saved. Called by the routes' _module_or_404."""
    from flask import abort, redirect, request, url_for
    if module is None or key == module.key or request.method != "GET" or not request.endpoint:
        return
    args = {name: (module.key if value == key else value) for name, value in (request.view_args or {}).items()}
    target = url_for(request.endpoint, **args)
    if request.query_string:
        target += "?" + request.query_string.decode("latin-1")
    abort(redirect(target, code=302))


def old_keys(session, kind: str, module_id: int) -> list[str]:
    return list(session.scalars(select(DatabaseAlias.old_key).where(
        DatabaseAlias.kind == kind, DatabaseAlias.module_id == module_id).order_by(DatabaseAlias.id)))


def first_key(session, kind: str, module) -> str:
    """The key the database was made with, before any rename."""
    keys = old_keys(session, kind, module.id) if module.id else []
    return keys[0] if keys else module.key


def aliases_by_key(session, kind: str) -> dict[str, int]:
    """{old key: module id} for this kind."""
    return {a.old_key: a.module_id for a in session.scalars(select(DatabaseAlias).where(DatabaseAlias.kind == kind))}


# What "@mouse 12", "@plasmid 4" and "@order 7" already mean in a notebook page.
MENTION_WORDS = frozenset({"mouse", "plasmid", "order"})


def taken(session, kind: str, key: str, module=None) -> bool:
    """Whether another database, of any kind, has or had this address: a
    live key, an old one someone's labels still carry, or a word the app's
    own pages or @links use. One address per database across the app, so
    "@<key> 5" in a notebook page never means two."""
    from .organisms import RESERVED_KEYS
    if key in RESERVED_KEYS or key in MENTION_WORDS:
        return True
    mine = module.id if module is not None else None
    for k in MODELS:
        model = MODELS[k]
        other = session.scalar(select(model.id).where(model.key == key))
        if other is not None and not (k == kind and other == mine):
            return True
        alias = session.scalar(select(DatabaseAlias).where(DatabaseAlias.kind == k, DatabaseAlias.old_key == key))
        if alias is not None and not (k == kind and alias.module_id == mine):
            return True
    return False


def name_clash(session, label: str, kind: str | None = None, module=None, builtin: str | None = None) -> str:
    """The name of another database already called `label` (whatever the
    case), or "". Every database has a name of its own: the sidebar, search
    and "@<name> 5" in a notebook page never mean two. `module` (of `kind`)
    or `builtin` (colony, zebrafish, plasmids) is the one being named."""
    from .inventory_service import BUILTIN_DATABASES, builtin_labels
    want = (label or "").strip().casefold()
    if not want:
        return ""
    for k, model in MODELS.items():
        for row in session.scalars(select(model)):
            if (row.label or "").strip().casefold() == want and not (
                    module is not None and k == kind and row.id == module.id):
                return row.label
    for key, name in builtin_labels(session).items():
        if key != builtin and want in (name.strip().casefold(), BUILTIN_DATABASES[key][1].casefold()):
            return name
    return ""


def free_key(session, kind: str, label: str, module=None) -> str:
    """The address a name gives: its slug, or slug_2, slug_3… if taken."""
    from .organism_service import slugify
    base = slugify(label)[:MAX_KEY - 4].strip("_") or kind
    key, n = base, 2
    while taken(session, kind, key, module):
        key, n = f"{base}_{n}", n + 1
    return key


def rekey(session, kind: str, module) -> str | None:
    """After a rename: move the database to its new name's address and keep
    the old one. Returns the new key, or None when it stays."""
    from .organism_service import slugify
    wanted = slugify(module.label)[:MAX_KEY - 4].strip("_")
    old = module.key
    if not wanted or wanted == old or (old.startswith(f"{wanted}_") and old[len(wanted) + 1:].isdigit()):
        return None          # the same name, or it already has that name's address (antibodies_2)
    new = free_key(session, kind, module.label, module)
    if new == old:
        return None
    if session.scalar(select(DatabaseAlias.id).where(DatabaseAlias.kind == kind, DatabaseAlias.old_key == old)) is None:
        session.add(DatabaseAlias(kind=kind, old_key=old, module_id=module.id))
    # Renamed back to an earlier name: that address is its own again.
    for alias in session.scalars(select(DatabaseAlias).where(
            DatabaseAlias.kind == kind, DatabaseAlias.old_key == new, DatabaseAlias.module_id == module.id)):
        session.delete(alias)
    module.key = new
    session.flush()
    _follow(session, kind, old, new)
    return new


def _follow(session, kind: str, old: str, new: str) -> None:
    """Stored references to the old key, rewritten to the new one."""
    if kind in ("stocks", "organisms"):
        for exp in session.scalars(select(Experiment).where(Experiment.db == f"{kind}:{old}")):
            exp.db = f"{kind}:{new}"
    if kind == "inventory":
        # An order put into stock: "stocked_as": "<inventory key>:<number>".
        for item in session.scalars(select(InventoryItem).where(InventoryItem.attrs.like(f"%{old}:%"))):
            attrs = item.attrs_dict
            if str(attrs.get("stocked_as", "")).startswith(f"{old}:"):
                attrs["stocked_as"] = new + attrs["stocked_as"][len(old):]
                item.attrs = json.dumps(attrs)
    if kind == "organisms":
        # A sample's source: {"kind": "organism:<key>", "ref": …}.
        for item in session.scalars(select(InventoryItem).where(InventoryItem.attrs.like(f"%organism:{old}%"))):
            attrs, changed = item.attrs_dict, False
            for value in attrs.values():
                if isinstance(value, dict) and value.get("kind") == f"organism:{old}":
                    value["kind"], changed = f"organism:{new}", True
            if changed:
                item.attrs = json.dumps(attrs)

