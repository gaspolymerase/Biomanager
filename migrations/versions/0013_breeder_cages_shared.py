"""Only a breeder cage can be shared, and it starts out shared: the breeder
cages a lab already has keep being shared by setting their flag, which
before this was implied by the purpose. (Breeding and stock cages, which
were shared by their purpose too, are now their owner's.)"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from migrations.helpers import has_column

revision = "0013_breeder_cages_shared"
down_revision = "0012_notebook_body_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if has_column("mouse_cages", "is_shared"):
        op.execute(sa.text("UPDATE mouse_cages SET is_shared = :yes WHERE lower(trim(purpose)) = 'breeder'")
                   .bindparams(yes=True))


def downgrade() -> None:
    pass
