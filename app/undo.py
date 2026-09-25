"""Undoing a batch.

Reverses the audit entries belonging to a BatchRecord, newest first, using
the structured before/after values the flush listener stored:

  * a **create** is undone by deleting the row
  * an **update** is undone by putting each column back to its "before"
  * a **delete** is undone by re-inserting the row from its snapshot

Two things it refuses to do. It will not touch a record that has been
changed again since the batch — reverting then would silently discard
whoever's later edit — and it will not undo a batch twice. Both are
reported rather than skipped quietly, because "undo did less than you
think" is worse than "undo declined".

The undo is itself audited, as its own batch, so the history stays honest.
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import or_, select

from . import audit
from .models import AuditEntry, BatchRecord

# Only tables the app knows how to rebuild a row for.
UNDOABLE_TABLES = set(audit.TRACKED_TABLES) - {"users"}


def _model_for(table: str):
    """The mapped class behind a table name."""
    from .db import Base

    for mapper in Base.registry.mappers:
        if mapper.class_.__tablename__ == table:
            return mapper.class_
    return None


def describe(session, batch: BatchRecord) -> dict:
    """What undoing this batch would do, without doing it."""
    entries = session.scalars(
        select(AuditEntry).where(AuditEntry.batch_id_fk == batch.id)
    ).all()
    counts = {"create": 0, "update": 0, "delete": 0}
    for entry in entries:
        if entry.action in counts:
            counts[entry.action] += 1
    return {
        "entries": len(entries),
        "creates": counts["create"],
        "updates": counts["update"],
        "deletes": counts["delete"],
        "blocked": blockers(session, batch),
    }


def blockers(session, batch: BatchRecord) -> list[str]:
    """Reasons this batch cannot be cleanly reversed."""
    problems: list[str] = []
    if batch.is_undone:
        problems.append(f"Already undone by {batch.undone_by} "
                        f"on {batch.undone_at:%Y-%m-%d %H:%M}.")
        return problems

    entries = session.scalars(
        select(AuditEntry).where(AuditEntry.batch_id_fk == batch.id)
    ).all()
    if not entries:
        problems.append("No recorded changes to reverse.")
        return problems

    touched_since = 0
    for entry in entries:
        if entry.table_name not in UNDOABLE_TABLES:
            problems.append(f"Table {entry.table_name} cannot be reversed automatically.")
            break
        later = session.scalar(
            select(AuditEntry.id).where(
                AuditEntry.table_name == entry.table_name,
                AuditEntry.record_id == entry.record_id,
                AuditEntry.id > entry.id,
                or_(AuditEntry.batch_id_fk.is_(None),
                    AuditEntry.batch_id_fk != batch.id),
            ).limit(1)
        )
        if later is not None:
            touched_since += 1
    if touched_since:
        problems.append(
            f"{touched_since} record(s) changed after this batch — reverting "
            "would throw those later edits away.")
    return problems


def undo(session, batch: BatchRecord, actor: str, force: bool = False) -> dict:
    """Reverse a batch. Returns a summary; raises nothing on partial work."""
    problems = blockers(session, batch)
    if problems and not force:
        return {"ok": False, "problems": problems, "reverted": 0}
    if batch.is_undone:
        return {"ok": False, "problems": ["Already undone."], "reverted": 0}

    entries = session.scalars(
        select(AuditEntry)
        .where(AuditEntry.batch_id_fk == batch.id)
        .order_by(AuditEntry.id.desc())
    ).all()

    reverted = skipped = 0
    notes: list[str] = []

    # The reversal is itself a batch, so the log shows both directions.
    with audit.batch(session, "update", f"undo of batch #{batch.id}",
                     batch.target_table) as undo_row:
        for entry in entries:
            model = _model_for(entry.table_name)
            if model is None:
                skipped += 1
                continue
            payload = {}
            if entry.changes_json:
                try:
                    payload = json.loads(entry.changes_json)
                except ValueError:
                    payload = {}

            if entry.action == "create":
                row = session.get(model, entry.record_id)
                if row is None:
                    skipped += 1
                    continue
                # Write the reverts made so far first. A cage created by the
                # batch still has the batch's mice pointing at it in the
                # database; deleting it before their restored cage is
                # flushed would let the ORM null that restored value.
                session.flush()
                session.delete(row)
                reverted += 1

            elif entry.action == "update":
                row = session.get(model, entry.record_id)
                changes = payload.get("changes") or {}
                if row is None or not changes:
                    skipped += 1
                    continue
                for field, pair in changes.items():
                    if not isinstance(pair, list) or len(pair) != 2:
                        continue
                    if hasattr(row, field):
                        setattr(row, field, audit._decode(pair[0]))
                reverted += 1

            elif entry.action == "delete":
                snapshot = payload.get("snapshot") or {}
                if not snapshot:
                    skipped += 1
                    notes.append(f"{entry.record_label}: no snapshot to restore from")
                    continue
                if session.get(model, snapshot.get("id")) is not None:
                    skipped += 1
                    notes.append(f"{entry.record_label}: that id is in use again")
                    continue
                values = {k: audit._decode(v) for k, v in snapshot.items()
                          if hasattr(model, k)}
                session.add(model(**values))
                reverted += 1

        batch.undone_at = datetime.utcnow()
        batch.undone_by = actor
        undo_row.record_count = reverted

    return {"ok": True, "reverted": reverted, "skipped": skipped,
            "problems": problems if force else [], "notes": notes}


def recent(session, limit: int = 50, actor: str | None = None) -> list[BatchRecord]:
    stmt = select(BatchRecord).order_by(BatchRecord.created_at.desc()).limit(limit)
    if actor:
        stmt = stmt.where(BatchRecord.actor == actor)
    return list(session.scalars(stmt).all())
