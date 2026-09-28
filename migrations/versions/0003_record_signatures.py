"""Signed notebook pages: record_signatures (app/signatures.py)."""
from __future__ import annotations

from migrations.helpers import create_table

revision = "0003_record_signatures"
down_revision = "0002_v0_8_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    create_table("record_signatures")


def downgrade() -> None:
    pass
