"""How old an animal is for its kind: the colour of the dot before its ID.

Young animals show blue, adults green and old ones red (a dead or removed
one stays grey, whatever its age). The bands are the ones labs go by:

    mouse      young under 8 weeks, old past 30 weeks
    zebrafish  young under 3 months post fertilisation, old past 18 months

Fly vials and worm plates go by their own timing (app/stock_service.py
unit_stage), and an expired reagent's dot is red too (inventory).
"""

# kind: (young below this many days, old above this many, how to say each)
BANDS = {
    "mouse": (56, 210, "8 weeks", "30 weeks"),
    "zebrafish": (90, 548, "3 months", "18 months"),
}


def stage(kind: str, age_days) -> str:
    """"young", "adult" or "old" for an animal `age_days` old; "" when its
    kind has no bands or its age is not known."""
    band = BANDS.get(kind)
    if band is None or age_days is None or age_days == "":
        return ""
    days = int(age_days)
    young, old = band[0], band[1]
    if days < young:
        return "young"
    if days > old:
        return "old"
    return "adult"


def describe(kind: str, which: str) -> str:
    """What the colour means, for the dot's tooltip: "adult, 8 to 30 weeks"."""
    band = BANDS.get(kind)
    if band is None or not which:
        return ""
    young, old = band[2], band[3]
    return {"young": f"young, under {young}", "adult": f"adult, {young} to {old}",
            "old": f"older than {old}"}.get(which, "")
