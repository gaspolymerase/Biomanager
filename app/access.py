"""Who may change what.

The lab model this encodes:

  * You manage your own colony. A record you own is yours to edit or delete.
  * Shared resources are everyone's. Breeder cages are the case that matters
    in practice — the whole lab picks mice out of them, so the whole lab has
    to be able to edit them.
  * Unowned records stay open. Records predating ownership have an empty
    owner, and locking the lab out of its own history helps nobody.
  * Admins can do anything, always.

Visibility is deliberately *not* restricted: everyone can read the whole
colony, because a census with holes in it is not a census. What the scope
switch changes is the default filter, not permission.

Keep this the single source of truth — a second copy of these rules in a
route is how they drift apart.
"""
from __future__ import annotations

from flask import g

# Cage purposes that make a cage a shared lab resource rather than one
# person's. Matched case-insensitively against a trimmed value.
SHARED_PURPOSES = {"breeder", "breeding", "shared", "stock"}


def current_user():
    return g.get("user") if g else None


def is_admin(user=None) -> bool:
    user = user or current_user()
    return getattr(user, "role", None) == "admin"


def username(user=None) -> str:
    user = user or current_user()
    return getattr(user, "username", "") or ""


def owns(record, user=None) -> bool:
    """True when `record.owner` names this user."""
    owner = (getattr(record, "owner", "") or "").strip()
    return bool(owner) and owner == username(user)


def is_unowned(record) -> bool:
    return not (getattr(record, "owner", "") or "").strip()


def is_shared_cage(cage) -> bool:
    """A breeder cage, or one explicitly flagged as shared."""
    if cage is None:
        return False
    if getattr(cage, "is_shared", False):
        return True
    purpose = (getattr(cage, "purpose", "") or "").strip().lower()
    return purpose in SHARED_PURPOSES


def can_edit(record, user=None, shared: bool = False) -> bool:
    """The general rule, used for anything carrying an `owner`."""
    if record is None:
        return False
    if is_admin(user):
        return True
    if shared:
        return True
    return owns(record, user) or is_unowned(record)


def can_edit_cage(cage, user=None) -> bool:
    return can_edit(cage, user, shared=is_shared_cage(cage))


def can_edit_mouse(mouse, user=None) -> bool:
    """A mouse is editable if it is yours, unowned, or sitting in a shared
    breeder cage that the whole lab works out of."""
    if mouse is None:
        return False
    return can_edit(mouse, user, shared=is_shared_cage(getattr(mouse, "cage", None)))


def can_configure(module, user=None) -> bool:
    """Changing a database's definition — its fields, schedule rules,
    racks and locations, vocabulary, or deleting it — is for an admin or
    whoever created it. Records inside it follow can_edit."""
    if module is None:
        return False
    if is_admin(user):
        return True
    creator = (getattr(module, "created_by", "") or "").strip()
    return bool(creator) and creator == username(user)


def reason_denied(record, user=None) -> str:
    """A message worth showing someone, rather than a bare 403."""
    owner = (getattr(record, "owner", "") or "").strip() or "someone else"
    return (f"That record belongs to {owner}. Ask them, or an admin, to make "
            f"the change — or move it to a shared breeder cage.")


# ---------------------------------------------------------------------------
# Scope: which slice of the colony a list view shows by default
# ---------------------------------------------------------------------------

SCOPES = (
    ("mine", "My colony"),
    ("shared", "Shared"),
    ("all", "Everyone"),
)
VALID_SCOPES = {key for key, _ in SCOPES}
DEFAULT_SCOPE = "mine"


def resolve_scope(raw: str | None) -> str:
    scope = (raw or "").strip().lower()
    return scope if scope in VALID_SCOPES else DEFAULT_SCOPE


def in_scope(record, scope: str, shared: bool = False, user=None) -> bool:
    """Filter predicate for list views. Applied in Python rather than SQL
    because 'shared' depends on the cage a mouse happens to sit in."""
    if scope == "all":
        return True
    if scope == "shared":
        return shared
    # "mine" still shows shared resources — they are part of your working set.
    return owns(record, user) or shared or is_unowned(record)
