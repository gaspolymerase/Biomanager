"""Fly and worm stock presets.

A stock module keeps vials (flies) or plates (worms). What each kind needs
differs in the details, and those details are settings, so a lab can edit
them:

  unit_noun / rack_noun / room_noun   vial · rack · incubator, or plate · box · incubator
  code_prefix       what goes in front of a vial's number ("V12", "P12")
  purposes          what a vial can be for; "cross" and "progeny" drive the
                    cross and egg-collection behaviour
  parents           what the two sides of a cross are called
  temperatures      the incubator temperatures in use, with, per temperature:
                      flip     days between flips (flies) / chunks (worms)
                      develop  days from egg to adult, for progeny due dates
                      collect  days between egg collections from a cross
  default_temperature
  frozen            show the frozen-stock list (worms)
  flip_verb         "Flip" or "Chunk" (flip_done: "Flipped", "Chunked")
  collect_verb      "Collect eggs" or "Pick progeny"
"""

from __future__ import annotations

import copy
import json

PRESETS: dict[str, dict] = {
    "fly": {
        "label": "Drosophila",
        "icon": "fly",
        "blurb": "Fly vials in racks inside incubators. Label a vial with its genotype and "
                 "purpose; set crosses, collect eggs into new vials and keep racks flipped.",
        "settings": {
            "unit_noun": "vial", "unit_noun_plural": "vials",
            "rack_noun": "rack", "rack_noun_plural": "racks",
            "room_noun": "incubator", "room_noun_plural": "incubators",
            "code_prefix": "V",
            "purposes": [
                {"key": "stock", "label": "Stock"},
                {"key": "experiment", "label": "Experiment"},
                {"key": "cross", "label": "Cross"},
                {"key": "virgins", "label": "Virgins"},
                {"key": "progeny", "label": "Progeny"},
                {"key": "expansion", "label": "Expansion"},
                {"key": "backup", "label": "Backup"},
            ],
            "parents": {"female": "♀ Virgins", "male": "♂ Males"},
            "temperatures": [
                {"temp": "18", "flip": 28, "develop": 19, "collect": 4},
                {"temp": "22", "flip": 18, "develop": 13, "collect": 3},
                {"temp": "25", "flip": 14, "develop": 10, "collect": 2},
                {"temp": "29", "flip": 10, "develop": 8, "collect": 2},
            ],
            "default_temperature": "25",
            "rack_rows": 10, "rack_cols": 10,
            "rack_naming": {"mode": "grid", "rows": "letters", "cols": "numbers"},
            "frozen": False,
            "flip_verb": "Flip",
            "flip_done": "Flipped",
            "collect_verb": "Collect eggs",
            "ready_label": "Progeny eclose",
        },
    },
    "worm": {
        "label": "C. elegans",
        "icon": "worm",
        "blurb": "Worm plates in boxes inside incubators. Chunk boxes on schedule, set "
                 "crosses and pick progeny onto new plates, and keep frozen stocks thaw-tested.",
        "settings": {
            "unit_noun": "plate", "unit_noun_plural": "plates",
            "rack_noun": "box", "rack_noun_plural": "boxes",
            "room_noun": "incubator", "room_noun_plural": "incubators",
            "code_prefix": "P",
            "purposes": [
                {"key": "maintenance", "label": "Maintenance"},
                {"key": "experiment", "label": "Experiment"},
                {"key": "cross", "label": "Cross"},
                {"key": "progeny", "label": "Progeny"},
                {"key": "synchronized", "label": "Synchronized"},
                {"key": "rnai", "label": "RNAi"},
                {"key": "males", "label": "Males"},
                {"key": "starved", "label": "Starved"},
            ],
            "parents": {"female": "⚥ Hermaphrodites", "male": "♂ Males"},
            "temperatures": [
                {"temp": "15", "flip": 12, "develop": 6, "collect": 2},
                {"temp": "20", "flip": 7, "develop": 4, "collect": 1},
                {"temp": "25", "flip": 4, "develop": 3, "collect": 1},
            ],
            "default_temperature": "20",
            "rack_rows": 4, "rack_cols": 6,
            "rack_naming": {"mode": "sequential"},
            "frozen": True,
            "flip_verb": "Chunk",
            "flip_done": "Chunked",
            "collect_verb": "Pick progeny",
            "ready_label": "Progeny adult",
        },
    },
}

KIND_LABELS = {"fly": "Drosophila", "worm": "C. elegans"}

# The purposes that behave specially.
CROSS = "cross"
PROGENY = "progeny"


def load(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw or "{}")
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def settings_for(kind: str, raw) -> dict:
    """Stored settings over the preset's, so a setting added later still
    has a value in an older module."""
    out = copy.deepcopy(PRESETS.get(kind, PRESETS["fly"])["settings"])
    for key, value in load(raw).items():
        if value not in (None, "", []):
            out[key] = value
    # Guarantee the two purposes the behaviour depends on.
    keys = [p["key"] for p in out["purposes"]]
    for special, label in ((CROSS, "Cross"), (PROGENY, "Progeny")):
        if special not in keys:
            out["purposes"].append({"key": special, "label": label})
    return out


def preset_settings(kind: str) -> dict:
    return copy.deepcopy(PRESETS.get(kind, PRESETS["fly"])["settings"])
