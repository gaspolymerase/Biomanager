"""Project groups (app/groups.py): some of the lab's people who share
animals, stock, databases, to-dos and notebook pages among themselves. Each
shared record can name the group it is shared with; to-dos can be the
lab's or a group's as well as their owner's."""
from __future__ import annotations

import sqlalchemy as sa

from migrations.helpers import add_column, create_index, create_table

revision = "0015_project_groups"
down_revision = "0014_lab_devices"
branch_labels = None
depends_on = None

SHARED_WITH_A_GROUP = ("mouse_cages", "plasmids", "inventory_items", "tanks", "stock_units",
                       "organism_modules", "stock_modules", "inventory_modules", "tasks", "notebook_templates")


def upgrade() -> None:
    create_table("lab_groups")
    create_table("lab_group_members")
    add_column("tasks", sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.false()))
    for table in SHARED_WITH_A_GROUP:
        add_column(table, sa.Column("share_group_id", sa.Integer(), nullable=True))
        create_index(table, f"ix_{table}_share_group_id", ["share_group_id"])
    create_index("tasks", "ix_tasks_is_shared", ["is_shared"])


def downgrade() -> None:
    pass
