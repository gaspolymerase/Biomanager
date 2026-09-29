"""Notebook templates keep the page type (an Experiment stays one) and can
be the lab's: notebook_templates.kind and notebook_templates.lab."""
from __future__ import annotations

import sqlalchemy as sa

from migrations.helpers import add_column

revision = "0009_template_kind_and_lab"
down_revision = "0008_measured_values"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column("notebook_templates", sa.Column("kind", sa.String(20), nullable=False, server_default=""))
    add_column("notebook_templates", sa.Column("lab", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    pass
