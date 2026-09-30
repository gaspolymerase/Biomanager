"""Where a box is kept: inventory_racks.stored_at ("−80 °C", "LN₂"). A tube
put in the box takes it as its "Stored at", so moving vials from the −80
transfer box to an LN₂ box no longer leaves them saying −80 °C."""
from __future__ import annotations

import sqlalchemy as sa

from migrations.helpers import add_column

revision = "0007_box_stored_at"
down_revision = "0006_one_cage_per_place"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column("inventory_racks", sa.Column("stored_at", sa.String(40), nullable=False, server_default=""))


def downgrade() -> None:
    pass
