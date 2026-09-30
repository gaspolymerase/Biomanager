"""A renamed database takes an address from its new name; database_aliases
keeps the old ones, so links and printed labels still find it."""
from __future__ import annotations

from migrations.helpers import create_table

revision = "0011_database_aliases"
down_revision = "0010_plasmid_lab_common"
branch_labels = None
depends_on = None


def upgrade() -> None:
    create_table("database_aliases")


def downgrade() -> None:
    pass
