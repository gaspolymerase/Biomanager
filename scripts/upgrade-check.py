#!/usr/bin/env python3
"""Check that this version upgrades every earlier release's database.

For each release tag (or those given), in a scratch folder:

1. that release makes a demo lab (its own scripts/demo-data.py, its own code);
2. this version opens it, which upgrades it (app/upgrade.py);
3. the check: every table and column a new database has is there, no table
   lost rows, the database is at the newest revision, a copy was taken
   before the upgrade, and the demo admin can sign in and open the pages.

    python scripts/upgrade-check.py                 # every tag from v0.2.0
    python scripts/upgrade-check.py v0.7.0 v0.8.0

Exit status 1 when any release fails. SQLite only (PostgreSQL servers are
backed up and upgraded by deploy/host/maintenance.sh).
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
# Rows start-up deliberately tidies away: the built-in mouse statuses, which
# the first boot of an older version stored as dropdown choices.
TIDIED = {"dropdown_options"}
PAGES = ["/home", "/colony?view=mice", "/colony?view=experiments", "/calendar", "/notebook", "/settings",
         "/zebrafish?view=fish", "/plasmids"]


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def counts(db: Path) -> dict[str, int]:
    with sqlite3.connect(str(db)) as c:
        tables = [r[0] for r in c.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")]
        return {t: c.execute(f'select count(*) from "{t}"').fetchone()[0] for t in tables}


def columns(db: Path) -> dict[str, set[str]]:
    with sqlite3.connect(str(db)) as c:
        tables = [r[0] for r in c.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")]
        return {t: {r[1] for r in c.execute(f'pragma table_info("{t}")')} for t in tables}


OPEN_WITH_THIS_VERSION = r'''
import json, os, sys
sys.path.insert(0, os.environ["BM_ROOT"])
from app.app import app
from app.db import SessionLocal
from app.models import UserAccount
from app import upgrade
from app.db import engine
from sqlalchemy import select
out = {"revision": upgrade.current_revision(engine), "head": upgrade.head_revision(), "pages": {}}
password = open(os.path.join(os.environ["BIOMANAGER_DATA_DIR"], "demo-password")).read().strip()
with SessionLocal() as s:
    admin = s.scalar(select(UserAccount).where(UserAccount.role == "admin").order_by(UserAccount.id))
    username = admin.username
c = app.test_client()
r = c.post("/login", data={"username": username, "password": password}, headers={"Origin": "http://localhost"})
out["login"] = r.status_code
for page in json.loads(os.environ["BM_PAGES"]):
    out["pages"][page] = c.get(page).status_code
print("RESULT " + json.dumps(out))
'''


def fresh_schema(tmp: Path) -> dict[str, set[str]]:
    data = tmp / "fresh"
    data.mkdir()
    env = {**os.environ, "BIOMANAGER_DATA_DIR": str(data), "DATABASE_URL": f"sqlite:///{data / 'biomanager.db'}",
           "BIOMANAGER_SEED_DEFAULTS": "1", "PYTHONPATH": str(ROOT)}
    r = run([PY, "-c", "import sys; sys.path.insert(0, '.'); from app.app import app"], cwd=ROOT, env=env)
    if r.returncode:
        sys.exit(f"This version can't make a new database:\n{r.stderr[-2000:]}")
    return columns(data / "biomanager.db")


def check(tag: str, tmp: Path, want: dict[str, set[str]]) -> list[str]:
    problems = []
    tree = tmp / f"src-{tag}"
    data = tmp / f"lab-{tag}"
    r = run(["git", "worktree", "add", "--detach", "-f", str(tree), tag], cwd=ROOT)
    if r.returncode:
        return [f"can't check out {tag}: {r.stderr.strip()}"]
    try:
        env = {k: v for k, v in os.environ.items() if not k.startswith("BIOMANAGER_") and k != "DATABASE_URL"}
        env["PYTHONPATH"] = str(tree)
        r = run([PY, "scripts/demo-data.py", str(data)], cwd=tree, env=env)
        if r.returncode or not (data / "biomanager.db").exists():
            return [f"{tag} couldn't make its demo lab here (not a problem with this version):\n{(r.stderr or r.stdout)[-1500:]}"]
        before = counts(data / "biomanager.db")
        env = {**os.environ, "BIOMANAGER_DATA_DIR": str(data), "DATABASE_URL": f"sqlite:///{data / 'biomanager.db'}",
               "BM_ROOT": str(ROOT), "BM_PAGES": json.dumps(PAGES), "PYTHONPATH": str(ROOT)}
        env.pop("BIOMANAGER_SEED_DEFAULTS", None)
        r = run([PY, "-c", OPEN_WITH_THIS_VERSION], cwd=ROOT, env=env)
        line = next((l for l in r.stdout.splitlines() if l.startswith("RESULT ")), None)
        if r.returncode or line is None:
            return [f"this version couldn't open {tag}'s database:\n{r.stderr[-2500:]}"]
        result = json.loads(line[7:])
        after = counts(data / "biomanager.db")
        have = columns(data / "biomanager.db")
        for table, cols in want.items():
            if table not in have:
                problems.append(f"table {table} is missing")
            elif cols - have[table]:
                problems.append(f"{table} is missing {', '.join(sorted(cols - have[table]))}")
        for table, n in before.items():
            if table in after and after[table] < n and table not in TIDIED:
                problems.append(f"{table} lost rows: {n} → {after[table]}")
            if table not in after:
                problems.append(f"table {table} disappeared ({n} rows)")
        if result["revision"] != result["head"]:
            problems.append(f"at revision {result['revision']}, not {result['head']}")
        if not list((data / "backups").glob("before-upgrade-*.db")):
            problems.append("no copy was taken before the upgrade")
        if result["login"] not in (302, 303):
            problems.append(f"the demo admin couldn't sign in ({result['login']})")
        problems += [f"{page} answered {code}" for page, code in result["pages"].items() if code >= 400]
    finally:
        run(["git", "worktree", "remove", "--force", str(tree)], cwd=ROOT)
    return problems


def main() -> int:
    tags = sys.argv[1:] or [t for t in run(["git", "tag", "--sort=creatordate"], cwd=ROOT).stdout.split()
                            if t.startswith("v") and t >= "v0.2.0"]
    failed = 0
    with tempfile.TemporaryDirectory(prefix="bm-upgrade-") as scratch:
        tmp = Path(scratch)
        want = fresh_schema(tmp)
        for tag in tags:
            problems = check(tag, tmp, want)
            if problems:
                failed += 1
                print(f"✗ {tag}")
                for p in problems:
                    print(f"    {p}")
            else:
                print(f"✓ {tag}: upgraded, nothing lost, pages open")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
