"""Lab inventories: creating them, reading their settings, and the helpers
their routes and the rest of the app share. Presets live in inventory.py."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select

from . import inventory as presets
from . import positions
from .db import SessionLocal
from .models import AppSetting, InventoryItem, InventoryModule, InventoryRack


# ---------------------------------------------------------------------------
# Module view
# ---------------------------------------------------------------------------


@dataclass
class ModuleView:
    row: InventoryModule
    settings: dict

    def __getattr__(self, name):
        return getattr(self.row, name)

    def has(self, feature: str) -> bool:
        return feature in self.settings["features"]

    @property
    def fields(self) -> list[dict]:
        return self.settings["fields"]

    @property
    def table_fields(self) -> list[dict]:
        return [f for f in self.settings["fields"] if f["in_table"]]

    @property
    def statuses(self) -> list[str]:
        return self.settings["statuses"]

    @property
    def categories(self) -> list[str]:
        return self.settings["categories"]

    @property
    def category_label(self) -> str:
        return self.settings["category_label"]

    @property
    def name_label(self) -> str:
        return {"samples": "Sample ID", "orders": "Item", "antibodies": "Target"}.get(self.row.kind, "Name")

    @property
    def open_statuses(self) -> list[str]:
        """Statuses that still need action (for an Open chip on boards)."""
        s = self.statuses
        return s[:-2] if len(s) > 2 else s[:1]


def view(module: InventoryModule) -> ModuleView:
    return ModuleView(module, presets.normalise_settings(module.settings))


def list_modules(session, include_disabled: bool = False) -> list[InventoryModule]:
    stmt = select(InventoryModule).order_by(InventoryModule.position, InventoryModule.label)
    if not include_disabled:
        stmt = stmt.where(InventoryModule.enabled.is_(True))
    return list(session.scalars(stmt))


def get_module(session, key: str) -> InventoryModule | None:
    return session.scalar(select(InventoryModule).where(InventoryModule.key == key))


def first_of_kind(session, kind: str) -> InventoryModule | None:
    return session.scalar(select(InventoryModule).where(InventoryModule.kind == kind)
                          .order_by(InventoryModule.position, InventoryModule.id))


def unique_key(session, label: str) -> str:
    from .organism_service import slugify
    base = slugify(label) or "inventory"
    key, n = base, 2
    while get_module(session, key) is not None:
        key, n = f"{base}_{n}", n + 1
    return key


def create_module(session, preset_key: str, label: str = "", created_by: str = "") -> InventoryModule:
    preset = presets.PRESETS.get(preset_key) or presets.PRESETS["custom"]
    label = (label or preset["label"]).strip()
    count = session.scalar(select(func.count(InventoryModule.id))) or 0
    module = InventoryModule(
        key=unique_key(session, label), label=label, kind=preset_key if preset_key in presets.PRESETS else "custom",
        icon=preset["icon"], blurb=preset["blurb"],
        item_noun=preset["item_noun"], item_noun_plural=preset["item_noun_plural"],
        settings=json.dumps(presets.preset_settings(preset_key)),
        position=300 + count, created_by=created_by,
    )
    session.add(module)
    session.flush()
    return module


# ---------------------------------------------------------------------------
# Settings kept in app_settings
# ---------------------------------------------------------------------------


def get_setting(session, key: str, default: str = "") -> str:
    row = session.get(AppSetting, key)
    return row.value if row else default


def set_setting(session, key: str, value: str) -> None:
    row = session.get(AppSetting, key)
    if row is None:
        session.add(AppSetting(key=key, value=value))
    else:
        row.value = value


# Built-in databases a lab can rename: {key: (default name, short name)}.
# The chosen name is kept in app_settings as "db_label:<key>".
BUILTIN_DATABASES = {
    "colony": ("Mouse colony", "Mouse"),
    "zebrafish": ("Zebrafish", "Fish"),
    "plasmids": ("Plasmids", "Plasmids"),
}


def builtin_labels(session) -> dict[str, str]:
    """{key: name} for every built-in database, renamed or not."""
    rows = session.scalars(select(AppSetting).where(AppSetting.key.like("db_label:%")))
    renamed = {r.key.split(":", 1)[1]: r.value.strip() for r in rows if r.value.strip()}
    return {key: renamed.get(key, default) for key, (default, _short) in BUILTIN_DATABASES.items()}


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


def next_number(session, module_id: int) -> int:
    top = session.scalar(select(func.max(InventoryItem.number)).where(InventoryItem.module_id_fk == module_id))
    return (top or 0) + 1


def rack_label(item: InventoryItem) -> str:
    rack = item.rack
    if rack is None:
        return ""
    return positions.label(item.rack_row, item.rack_col, rack.naming, rack.cols)


def expiry_state(item: InventoryItem, today: date | None = None) -> str:
    """"expired", "soon" (within 30 days) or ""."""
    if not item.expires_on:
        return ""
    today = today or date.today()
    if item.expires_on < today:
        return "expired"
    if item.expires_on <= today + timedelta(days=30):
        return "soon"
    return ""


def apply_position(session, item: InventoryItem, rack_raw, position_raw) -> str | None:
    """Place an item from a typed rack + position ("D7" under that box's
    naming scheme); an error message instead of a guess."""
    rack_raw = str(rack_raw or "").strip()
    position_raw = str(position_raw or "").strip()
    if not rack_raw:
        item.rack_id_fk = item.rack_row = item.rack_col = None
        return None
    rack = session.get(InventoryRack, int(rack_raw)) if rack_raw.isdigit() else None
    if rack is None or rack.module_id_fk != item.module_id_fk:
        return "That box is not part of this inventory."
    if not position_raw:
        item.rack_id_fk, item.rack_row, item.rack_col = rack.id, None, None
        return None
    cell = positions.parse(position_raw, rack.naming, rack.rows, rack.cols)
    if cell is None:
        return (f"“{position_raw}” is not a position in {rack.name} "
                f"({positions.label(1, 1, rack.naming, rack.cols)}–{positions.label(rack.rows, rack.cols, rack.naming, rack.cols)}).")
    holder = session.scalar(select(InventoryItem).where(
        InventoryItem.rack_id_fk == rack.id, InventoryItem.rack_row == cell[0],
        InventoryItem.rack_col == cell[1], InventoryItem.id != (item.id or 0)))
    if holder is not None:
        return f"{rack.name} · {position_raw} already holds {holder.name or '#' + str(holder.number)}. Drag on the grid to swap."
    item.rack_id_fk, (item.rack_row, item.rack_col) = rack.id, cell
    return None


# ---------------------------------------------------------------------------
# Boot: seeding and moving the old samples / orders tables in
# ---------------------------------------------------------------------------


def seed_modules() -> list[str]:
    """Create samples, orders, reagents and antibodies once. Remembered in
    app_settings, so an inventory a lab deletes does not come back."""
    created = []
    with SessionLocal() as session:
        if get_setting(session, "inventory_seeded"):
            return created
        for position, key in enumerate(presets.AUTO_SEED):
            if first_of_kind(session, key) is None:
                module = create_module(session, key, created_by="system")
                module.position = 300 + position
                created.append(key)
        set_setting(session, "inventory_seeded", "1")
        session.commit()
    return created


def migrate_legacy() -> int:
    """Copy rows from the old fixed `samples` and `orders` tables into the
    Samples and Orders inventories, once. The old tables are left in place
    (untouched) as a record."""
    from .models import Order, SampleRecord

    moved = 0
    with SessionLocal() as session:
        if get_setting(session, "legacy_inventory_migrated"):
            return 0
        samples = first_of_kind(session, "samples")
        orders = first_of_kind(session, "orders")
        if samples is not None:
            n = next_number(session, samples.id)
            for s in session.scalars(select(SampleRecord).order_by(SampleRecord.id)):
                attrs = {"source": {"kind": s.source_kind or "", "ref": s.source_ref or ""},
                         "collected_on": s.collection_date.isoformat() if s.collection_date else "",
                         "amount": s.amount or ""}
                session.add(InventoryItem(
                    module_id_fk=samples.id, number=n, name=s.sample_id, category=s.sample_type or "",
                    status="available", owner=s.owner or "", location_note=s.storage_location or "",
                    attrs=json.dumps(attrs), notes=s.notes or "", created_at=s.created_at))
                n += 1
                moved += 1
        if orders is not None:
            n = next_number(session, orders.id)
            for o in session.scalars(select(Order).order_by(Order.id)):
                session.add(InventoryItem(
                    module_id_fk=orders.id, number=n, name=o.item_name, status=o.status or "requested",
                    owner=o.requester_name or "", vendor=o.vendor_name or "", catalog_number=o.catalog_number or "",
                    quantity=o.quantity or "", notes=o.notes or "", created_at=o.created_at))
                n += 1
                moved += 1
        set_setting(session, "legacy_inventory_migrated", "1")
        session.commit()
    return moved
