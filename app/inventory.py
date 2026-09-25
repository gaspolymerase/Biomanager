"""Lab inventory presets: what a samples, orders, reagents or antibodies
database tracks, and how it behaves.

An inventory module's `settings` JSON holds:

  features    which built-in behaviours are on:
                storage   freezer boxes / shelves with positions (rack grid)
                board     a status board (orders: requested → ordered → received)
                sharing   "Mine" vs "Lab common" stock
                quantity  quantity + unit columns
                supplier  vendor, catalogue number, lot
                expiry    an expiry date, with expired / expiring-soon flags
                received  a received date
  categories  the choices for the category column ("Type", "Kind"…)
  category_label
  statuses    the status workflow, first is the default
  fields      extra, preset-specific columns kept in `attrs`:
                {key, label, type, options?, icon?, width?, in_table?}

Presets are starting points; everything is editable in Configure.
"""

from __future__ import annotations

import json

FIELD_TYPES = ("text", "textarea", "number", "date", "select", "user", "url", "source")

FEATURES = {
    "storage": "Freezer boxes and shelves with positions, shown as a grid",
    "board": "A status board (e.g. requested → ordered → received)",
    "sharing": "Separate my own stock from lab common stock",
    "quantity": "Quantity and unit",
    "supplier": "Vendor, catalogue number and lot",
    "expiry": "Expiry date, with expired and expiring-soon warnings",
    "received": "Date received",
}

STORAGE_TEMPS = ["RT", "4 °C", "−20 °C", "−80 °C", "LN₂"]

PRESETS: dict[str, dict] = {
    "samples": {
        "label": "Samples",
        "icon": "vial",
        "item_noun": "sample", "item_noun_plural": "samples",
        "blurb": "Harvested tissue, blood, DNA and RNA, traced back to the animal they came from and kept in freezer boxes.",
        "features": ["storage", "sharing"],
        "category_label": "Type",
        "categories": ["tissue", "blood", "serum", "DNA", "RNA", "protein", "organoid", "cells", "other"],
        "statuses": ["available", "in use", "used up", "discarded"],
        "fields": [
            {"key": "source", "label": "Source", "type": "source", "icon": "signpost", "width": 190},
            {"key": "collected_on", "label": "Collected", "type": "date", "icon": "calendar", "width": 136},
            {"key": "amount", "label": "Amount", "type": "text", "icon": "amount", "width": 100},
            {"key": "storage_temp", "label": "Stored at", "type": "select", "options": STORAGE_TEMPS, "icon": "snowflake", "width": 104},
        ],
    },
    "orders": {
        "label": "Orders",
        "icon": "cart",
        "item_noun": "order", "item_noun_plural": "orders",
        "blurb": "What the lab has asked for and where each order stands, on a board from requested to received.",
        "features": ["board", "quantity", "supplier", "received"],
        "category_label": "Category",
        "categories": ["reagent", "antibody", "consumable", "equipment", "service", "other"],
        "statuses": ["requested", "ordered", "received", "cancelled"],
        "fields": [
            {"key": "price", "label": "Price", "type": "number", "icon": "receipt", "width": 96},
            {"key": "account", "label": "Account / grant", "type": "text", "icon": "barcode", "width": 140},
            {"key": "url", "label": "Link", "type": "url", "icon": "link", "width": 160, "in_table": False},
        ],
    },
    "reagents": {
        "label": "Reagents",
        "icon": "flask",
        "item_noun": "reagent", "item_noun_plural": "reagents",
        "blurb": "Chemicals, buffers, enzymes and kits. Keep your own stock apart from the lab's common shelf.",
        "features": ["storage", "sharing", "quantity", "supplier", "expiry", "received"],
        "category_label": "Kind",
        "categories": ["chemical", "buffer", "enzyme", "kit", "media", "primer", "dye", "other"],
        "statuses": ["in stock", "low", "empty", "discarded"],
        "fields": [
            {"key": "cas", "label": "CAS", "type": "text", "icon": "barcode", "width": 110},
            {"key": "concentration", "label": "Concentration", "type": "text", "icon": "amount", "width": 116},
            {"key": "storage_temp", "label": "Stored at", "type": "select", "options": STORAGE_TEMPS, "icon": "snowflake", "width": 104},
            {"key": "hazard", "label": "Hazard", "type": "select",
             "options": ["none", "flammable", "corrosive", "toxic", "oxidiser", "irritant", "biohazard"], "icon": "warning", "width": 110},
        ],
    },
    "antibodies": {
        "label": "Antibodies",
        "icon": "antibody",
        "item_noun": "antibody", "item_noun_plural": "antibodies",
        "blurb": "Primary and secondary antibodies with host, clone, conjugate, validated applications and working dilutions.",
        "features": ["storage", "sharing", "quantity", "supplier", "expiry", "received"],
        "category_label": "Role",
        "categories": ["primary", "secondary", "isotype control"],
        "statuses": ["in stock", "low", "empty", "discarded"],
        "fields": [
            {"key": "host", "label": "Host", "type": "select",
             "options": ["mouse", "rabbit", "rat", "goat", "donkey", "chicken", "sheep", "guinea pig", "hamster", "other"],
             "icon": "paw", "width": 100},
            {"key": "clonality", "label": "Clonality", "type": "select",
             "options": ["monoclonal", "polyclonal", "recombinant"], "icon": "sitemap", "width": 116},
            {"key": "clone", "label": "Clone", "type": "text", "icon": "dna", "width": 96},
            {"key": "conjugate", "label": "Conjugate", "type": "text", "icon": "sparkle", "width": 116},
            {"key": "reactivity", "label": "Reactivity", "type": "text", "icon": "target", "width": 120},
            {"key": "applications", "label": "Applications", "type": "text", "icon": "microscope", "width": 130},
            {"key": "dilution", "label": "Dilution", "type": "text", "icon": "droplet", "width": 110},
            {"key": "isotype", "label": "Isotype", "type": "text", "icon": "tag", "width": 90, "in_table": False},
            {"key": "rrid", "label": "RRID", "type": "text", "icon": "link", "width": 130},
        ],
    },
    "custom": {
        "label": "Custom list",
        "icon": "list",
        "item_noun": "item", "item_noun_plural": "items",
        "blurb": "An empty list. Pick the features you need and add your own columns.",
        "features": ["sharing"],
        "category_label": "Category",
        "categories": [],
        "statuses": [],
        "fields": [],
    },
}

# Created automatically on first start, so every lab has them.
AUTO_SEED = ("samples", "orders", "reagents", "antibodies")


def load(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw or "{}")
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def normalise_settings(raw) -> dict:
    """Settings with every key present and junk dropped."""
    s = load(raw)
    fields = []
    for f in s.get("fields") or []:
        if not isinstance(f, dict) or not f.get("key") or f.get("type") not in FIELD_TYPES:
            continue
        fields.append({
            "key": str(f["key"]), "label": str(f.get("label") or f["key"]), "type": f["type"],
            "options": [str(o) for o in f.get("options") or []],
            "icon": str(f.get("icon") or ""), "width": int(f.get("width") or 130),
            "in_table": f.get("in_table", True) is not False,
        })
    return {
        "features": [x for x in (s.get("features") or []) if x in FEATURES],
        "category_label": str(s.get("category_label") or "Category"),
        "categories": [str(c) for c in s.get("categories") or []],
        "statuses": [str(c) for c in s.get("statuses") or []],
        "fields": fields,
    }


def preset_settings(key: str) -> dict:
    preset = PRESETS.get(key) or PRESETS["custom"]
    return normalise_settings({k: preset.get(k) for k in ("features", "category_label", "categories", "statuses", "fields")})


# Icon for a field type, used when a custom field has none.
FIELD_TYPE_ICONS = {"text": "type", "textarea": "note", "number": "count", "date": "calendar",
                    "select": "tag", "user": "user", "url": "link", "source": "signpost"}
