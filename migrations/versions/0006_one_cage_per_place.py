"""One cage per place in a rack: a unique index on mouse_cages(rack_id_fk,
rack_row, rack_col). Two people dropping cages on one place at the same
moment both got "ok", and up to six cages ended up in one place.

A database may already hold such places. The oldest cage keeps each; the
others are taken off the rack (their rack, row and column cleared), with a
line in their notes saying where they were, so someone can place them again.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from migrations.helpers import create_index, has_index, has_table

revision = "0006_one_cage_per_place"
down_revision = "0005_api_tokens"
branch_labels = None
depends_on = None

INDEX = "uq_mouse_cages_place"


def upgrade() -> None:
    if not has_table("mouse_cages") or has_index("mouse_cages", INDEX):
        return
    bind = op.get_bind()
    shared = bind.execute(sa.text(
        "SELECT c.id, c.rack_id_fk, c.rack_row, c.rack_col, c.notes FROM mouse_cages c "
        "WHERE c.rack_id_fk IS NOT NULL AND c.rack_row IS NOT NULL AND c.rack_col IS NOT NULL "
        "AND EXISTS (SELECT 1 FROM mouse_cages o WHERE o.rack_id_fk = c.rack_id_fk AND o.rack_row = c.rack_row "
        "AND o.rack_col = c.rack_col AND o.id < c.id)")).all()
    for cage_id, rack, row, col, notes in shared:
        line = f"Taken off rack #{rack} row {row}, column {col} on upgrading: another cage has that place."
        bind.execute(sa.text("UPDATE mouse_cages SET rack_id_fk = NULL, rack_row = NULL, rack_col = NULL, "
                             "notes = :notes WHERE id = :id"),
                     {"id": cage_id, "notes": "\n".join(filter(None, [(notes or "").strip(), line]))})
    create_index("mouse_cages", INDEX, ["rack_id_fk", "rack_row", "rack_col"], unique=True)


def downgrade() -> None:
    if has_index("mouse_cages", INDEX):
        op.drop_index(INDEX, table_name="mouse_cages")
