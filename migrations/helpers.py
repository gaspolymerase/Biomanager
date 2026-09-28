"""Helpers for revisions that must also run on a database that already has
the change.

A database can reach a revision two ways: upgraded from an older one, or
created new by create_all() (which already makes every table and column
the models have) and stamped. And every start-up still runs create_all(),
so a new table exists before its revision runs. So a revision adds what is
missing, and never assumes it is:

    from migrations.helpers import add_column, create_table

    def upgrade():
        create_table("things")                     # from the model, if missing
        add_column("mice", sa.Column("colour", sa.String(40), server_default=""))
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


def _inspector():
    return sa.inspect(op.get_bind())


def has_table(name: str) -> bool:
    return _inspector().has_table(name)


def has_column(table: str, column: str) -> bool:
    return has_table(table) and column in {c["name"] for c in _inspector().get_columns(table)}


def create_table(name: str) -> None:
    """The model's table, if the database hasn't got it."""
    if not has_table(name):
        from app.db import Base
        from app import models  # noqa: F401  (registers the tables)
        Base.metadata.tables[name].create(bind=op.get_bind())


def add_column(table: str, column: sa.Column) -> None:
    if has_table(table) and not has_column(table, column.name):
        with op.batch_alter_table(table) as batch:
            batch.add_column(column)
