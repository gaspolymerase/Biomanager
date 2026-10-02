"""Devices that work on the lab (app/devices.py): each computer's key also
remembers how the computer uses the lab, its version, where it shares the
lab when it is the master, and when it was last heard from."""
from __future__ import annotations

import sqlalchemy as sa

from migrations.helpers import add_column

revision = "0014_lab_devices"
down_revision = "0013_breeder_cages_shared"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column("lab_copy_keys", sa.Column("device_role", sa.String(20), nullable=False, server_default=""))
    add_column("lab_copy_keys", sa.Column("device_version", sa.String(40), nullable=False, server_default=""))
    add_column("lab_copy_keys", sa.Column("device_url", sa.String(300), nullable=False, server_default=""))
    add_column("lab_copy_keys", sa.Column("last_seen_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    pass
