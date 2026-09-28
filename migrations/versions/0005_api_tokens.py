"""The API's personal access tokens: api_tokens (app/api.py)."""
from __future__ import annotations

from migrations.helpers import create_table

revision = "0005_api_tokens"
down_revision = "0004_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    create_table("api_tokens")


def downgrade() -> None:
    pass
