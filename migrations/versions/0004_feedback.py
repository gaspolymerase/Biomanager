"""Send feedback: the feedback table (app/feedback.py)."""
from __future__ import annotations

from migrations.helpers import create_table

revision = "0004_feedback"
down_revision = "0003_record_signatures"
branch_labels = None
depends_on = None


def upgrade() -> None:
    create_table("feedback")


def downgrade() -> None:
    pass
