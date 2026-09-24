#!/usr/bin/env python3
"""Reset a BioManager account password from the command line.

For when someone is locked out and there is no other admin to do it from
Settings -> Manage users. The new password is typed at a prompt, so it never
lands in shell history.

    python scripts/reset-password.py                 # list accounts
    python scripts/reset-password.py alex         # reset that account
    python scripts/reset-password.py alex --admin # …and make them admin

Talks to SQLite directly rather than importing the app, which keeps it fast
and means it still works when the app itself will not start. For a Postgres
deployment, use Settings -> Manage users instead.
"""
from __future__ import annotations

import argparse
import getpass
import sqlite3
import sys
from pathlib import Path

try:
    from werkzeug.security import generate_password_hash
except ImportError:
    sys.exit("werkzeug is not installed in this interpreter — run this with "
             "the same Python you start the app with, e.g. .venv/bin/python")

MIN_LENGTH = 6
DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "biomanager.db"


def connect(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        sys.exit(f"No database at {db_path}\n"
                 f"Pass --db if it lives somewhere else (a packaged .app keeps it in\n"
                 f"~/Library/Application Support/Biomanager/data/).")
    return sqlite3.connect(db_path)


def list_accounts(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "select username, coalesce(nullif(display_name,''),'-'), role, disabled"
        " from users order by id"
    ).fetchall()
    if not rows:
        sys.exit("No accounts in this database yet — register one in the app.")
    print(f"{'USERNAME':<18} {'NAME':<20} {'ROLE':<8} STATUS")
    for username, display_name, role, disabled in rows:
        print(f"{username:<18} {display_name:<20} {role:<8} "
              f"{'disabled' if disabled else 'active'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("username", nargs="?", help="account to reset; omit to list accounts")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="path to biomanager.db")
    parser.add_argument("--admin", action="store_true", help="also promote to admin")
    parser.add_argument("--enable", action="store_true", help="also re-enable a disabled account")
    args = parser.parse_args()

    conn = connect(args.db)
    try:
        if not args.username:
            list_accounts(conn)
            print("\nPass a username to reset it.")
            return 0

        row = conn.execute(
            "select id, role, disabled from users where username = ?", (args.username,)
        ).fetchone()
        if row is None:
            print(f"No account named {args.username!r}.\n")
            list_accounts(conn)
            return 1
        user_id, role, disabled = row

        print(f"Resetting the password for {args.username} (role: {role}"
              f"{', disabled' if disabled else ''}).")
        password = getpass.getpass("New password: ")
        if len(password) < MIN_LENGTH:
            sys.exit(f"Too short — use at least {MIN_LENGTH} characters.")
        if password != getpass.getpass("Confirm: "):
            sys.exit("The two entries did not match. Nothing was changed.")

        updates = {"password_hash": generate_password_hash(password)}
        if args.admin:
            updates["role"] = "admin"
        if args.enable:
            updates["disabled"] = 0

        assignments = ", ".join(f"{column} = ?" for column in updates)
        conn.execute(f"update users set {assignments} where id = ?",
                     (*updates.values(), user_id))
        conn.commit()

        print(f"\nDone. Sign in as {args.username} with the new password.")
        if args.admin and role != "admin":
            print("Promoted to admin.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
