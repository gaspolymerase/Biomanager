"""Lab common plasmids: plasmids.is_shared. Anyone may edit a lab common
plasmid; deleting it or changing its owner stays with its owner."""
from __future__ import annotations

import sqlalchemy as sa

from migrations.helpers import add_column, create_index

revision = "0010_plasmid_lab_common"
down_revision = "0009_template_kind_and_lab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column("plasmids", sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.false()))
    create_index("plasmids", "ix_plasmids_is_shared", ["is_shared"])


def downgrade() -> None:
    pass
