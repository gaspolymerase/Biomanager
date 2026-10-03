"""What's new (app/whats_new.py): the newest version whose note each person
has seen, so the note shows once after an update."""
from __future__ import annotations

import sqlalchemy as sa

from migrations.helpers import add_column

revision = "0016_whats_new"
down_revision = "0015_project_groups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column("users", sa.Column("whats_new_seen", sa.String(40), nullable=False, server_default=""))


def downgrade() -> None:
    pass
