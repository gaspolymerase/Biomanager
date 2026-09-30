"""notebook_page_info.body_state: which live edits a page's saved text holds,
so a tab that has fallen behind can't save an older text over it."""
from __future__ import annotations

import sqlalchemy as sa

from migrations.helpers import add_column

revision = "0012_notebook_body_state"
down_revision = "0011_database_aliases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column("notebook_page_info", sa.Column("body_state", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    pass
