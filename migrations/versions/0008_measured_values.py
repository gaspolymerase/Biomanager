"""Measured values as numbers.

- plasmids.concentration and plasmids.a260_280: a miniprep's ng/µL and
  purity on the tube.
- Samples databases made before 1.0 get the columns new ones have: Conc.,
  Conc. unit, 260/280, 260/230 and Volume (µL). A database that already has
  a column of that name (or key) keeps its own and gets no second one.
"""
from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

from migrations.helpers import add_column, has_table

revision = "0008_measured_values"
down_revision = "0007_box_stored_at"
branch_labels = None
depends_on = None

UNITS = ["ng/µL", "µg/mL", "mg/mL", "nM", "µM", "cells/mL"]
MEASURES = [
    {"key": "concentration", "label": "Conc.", "type": "number", "icon": "amount", "width": 92},
    {"key": "conc_unit", "label": "Conc. unit", "type": "select", "options": UNITS, "icon": "amount", "width": 100},
    {"key": "a260_280", "label": "260/280", "type": "number", "icon": "amount", "width": 84},
    {"key": "a260_230", "label": "260/230", "type": "number", "icon": "amount", "width": 84, "in_table": False},
    {"key": "volume_ul", "label": "Volume (µL)", "type": "number", "icon": "droplet", "width": 100},
]
# Names a lab may have given the same thing already.
SAME = {"concentration": {"conc.", "concentration", "conc"}, "conc_unit": {"conc. unit", "unit"},
        "a260_280": {"260/280", "a260/280"}, "a260_230": {"260/230", "a260/230"},
        "volume_ul": {"volume (µl)", "volume", "vol"}}


def upgrade() -> None:
    add_column("plasmids", sa.Column("concentration", sa.String(40), nullable=False, server_default=""))
    add_column("plasmids", sa.Column("a260_280", sa.String(20), nullable=False, server_default=""))
    if not has_table("inventory_modules"):
        return
    bind = op.get_bind()
    for module_id, raw in bind.execute(sa.text("select id, settings from inventory_modules where kind = 'samples'")).all():
        try:
            settings = json.loads(raw or "{}")
        except ValueError:
            continue
        fields = settings.get("fields")
        if not isinstance(fields, list):
            continue
        keys = {str(f.get("key", "")).lower() for f in fields if isinstance(f, dict)}
        labels = {str(f.get("label", "")).strip().lower() for f in fields if isinstance(f, dict)}
        new = [dict(m) for m in MEASURES if m["key"] not in keys and not (SAME[m["key"]] & labels)]
        if not new:
            continue
        # After Amount when it is there, else at the end.
        at = next((i + 1 for i, f in enumerate(fields) if isinstance(f, dict) and f.get("key") == "amount"), len(fields))
        settings["fields"] = fields[:at] + new + fields[at:]
        bind.execute(sa.text("update inventory_modules set settings = :s where id = :i"),
                     {"s": json.dumps(settings), "i": module_id})


def downgrade() -> None:
    pass
