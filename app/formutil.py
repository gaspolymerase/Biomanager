"""Small helpers for reading submitted forms."""

from __future__ import annotations


def form_changed(form, *names) -> bool:
    """True when any of `names` was edited in this form.

    A value that appears in several places (a cage's rack on every mouse row
    of that cage, an item's box on its row and on the rack grid) can go
    stale. Each form also sends `<name>_was`, the value it was showing; a
    field only counts as edited when it differs. Without this, saving any
    other cell of a stale row would post the old value and undo a change
    made elsewhere. Forms without `_was` fields (dialogs) always count as
    edited."""
    for name in names:
        if name not in form:
            continue
        was = form.get(f"{name}_was")
        if was is None or form.get(name, "").strip() != was.strip():
            return True
    return False


def like_pattern(text: str) -> str:
    """ "%text%" for .ilike(…, escape="\\"), with the text's own % and _
    kept literal: a search for "50%" is not a search for everything."""
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
