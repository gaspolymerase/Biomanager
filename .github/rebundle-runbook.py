#!/usr/bin/env python3
"""Put this checkout's deploy/RUNBOOK.md into a published server bundle.

    python .github/rebundle-runbook.py old.tar.gz new.tar.gz

Every other file is copied as it is (contents, modes, times, order), so a
bundle keeps its version and scripts, except that the example words in
EXAMPLES become the neutral ones deploy/ uses now. Used by
.github/workflows/rebundle-old-releases.yml for the bundles published
before deploy/RUNBOOK.md stopped naming our own server. Exit status 1 if
the result still names it.
"""
from __future__ import annotations

import io
import re
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEMBER = "Biomanager/deploy/RUNBOOK.md"
# Our server's names (docs/OUR-SERVER.md), our names and address; none may be in a bundle.
OURS = re.compile(rb"tail1234|\bbiomanager-vm\b|biomanager_key|alex|barbara|\blab member\b|\bmcclintock lab\b|52350568|university", re.I)

# Examples that named our institution, and what deploy/ says instead now.
EXAMPLES = {b"CampusKey": b"CampusKey", b"you@university.edu": b"you@university.edu"}


def rebundle(source: Path, target: Path) -> list[str]:
    runbook = (ROOT / "deploy" / "RUNBOOK.md").read_bytes()
    found = []
    with tarfile.open(source) as old, tarfile.open(target, "w:gz") as new:
        for member in old.getmembers():
            data = old.extractfile(member).read() if member.isfile() else None
            if member.name == MEMBER:
                data = runbook
            elif data is not None:
                for was, now in EXAMPLES.items():
                    data = data.replace(was, now)
            if data is not None:
                member.size = len(data)
                if OURS.search(data):
                    found.append(member.name)
                new.addfile(member, io.BytesIO(data))
            else:
                new.addfile(member)
    return found


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    found = rebundle(Path(sys.argv[1]), Path(sys.argv[2]))
    if found:
        sys.exit("Still names our server: " + ", ".join(found))
    print(f"{sys.argv[2]}: {MEMBER} replaced")
