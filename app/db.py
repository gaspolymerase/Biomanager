from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .paths import data_dir, resource_root


BASE_DIR = resource_root()
DATA_DIR = data_dir()


def _default_sqlite_url() -> str:
    return f"sqlite:///{DATA_DIR / 'biomanager.db'}"


def get_database_url() -> str:
    raw_url = os.environ.get("DATABASE_URL", "").strip()
    if not raw_url:
        return _default_sqlite_url()

    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+psycopg://", 1)
    if raw_url.startswith("postgresql://") and "+psycopg" not in raw_url:
        return raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw_url


DATABASE_URL = get_database_url()


class Base(DeclarativeBase):
    pass


engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


# SQLite does not enforce foreign keys unless every connection asks it to.
# app/integrity.py decides at start-up (init_database), after checking the
# existing data: True turns enforcement on for every connection from then
# on; False keeps it off for a database whose data still has references it
# could not repair (it says so loudly), so the app keeps working until
# someone fixes the data. None (not yet checked) behaves as off, so the
# schema steps that run before the check see the database as they always did.
FOREIGN_KEYS_ENFORCED: bool | None = None


if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def _sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute(f"PRAGMA foreign_keys={'ON' if FOREIGN_KEYS_ENFORCED else 'OFF'}")
        cursor.close()

    # A commit refused by a deferred foreign-key check leaves pysqlite's
    # transaction open (SQLite keeps the transaction when COMMIT fails), and
    # a session closed without an explicit rollback hands that connection
    # back to the pool still holding the refused change and the write lock.
    # Roll back anything still open whenever a connection returns.
    @event.listens_for(engine, "checkin")
    def _sqlite_rollback_on_return(dbapi_connection, connection_record) -> None:
        if getattr(dbapi_connection, "in_transaction", False):
            try:
                dbapi_connection.rollback()
            except Exception:  # a broken connection is dropped by the pool anyway
                connection_record.invalidate()
