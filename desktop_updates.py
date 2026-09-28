"""The desktop app's version, its preferences, and checking for a newer one.

A build knows its version from the VERSION file PyInstaller puts beside it
(Biomanager.spec writes it from BIOMANAGER_VERSION, which the release
workflow sets from the tag). Run from source, it asks git.

"Check for Updates…" (and, at most once a day, the app when it opens)
asks GitHub for the latest release on gaspolymerase/biomanager-app. That
request carries only the app's version in its User-Agent; turn the daily
check off with "Check for Updates Automatically". A newer release is
offered, with its notes, and "Download" opens the file for this computer
in the browser. The app never replaces itself.

Preferences (the automatic check, a skipped version, appearance and zoom)
are desktop-prefs.json in the data folder (app/paths.py), not in the lab's
database: they belong to this computer.
"""
from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = "gaspolymerase/biomanager-app"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
GUIDE_URL = "https://gaspolymerase.github.io/biomanager-app/guide.html"
ISSUES_URL = f"https://github.com/{REPO}/issues/new"
CHECK_EVERY = 24 * 3600
DEFAULT_PREFS = {"check_updates": True, "last_check": 0, "skip_version": "", "appearance": "system", "zoom": 1.0}

_ROOT = Path(__file__).resolve().parent


# ---------------------------------------------------------------- version

def version() -> str:
    """"0.5.0" in a build; from source, the latest tag (and "+dev" past it)."""
    bundled = Path(getattr(sys, "_MEIPASS", _ROOT)) / "VERSION"
    try:
        text = bundled.read_text().strip()
        if text:
            return text
    except OSError:
        pass
    try:
        out = subprocess.run(["git", "describe", "--tags", "--abbrev=0"], cwd=_ROOT, capture_output=True,
                             text=True, timeout=3)
        tag = out.stdout.strip()
        if out.returncode == 0 and tag:
            return tag.lstrip("v") + "+dev"
    except (OSError, subprocess.SubprocessError):
        pass
    return "dev"


def parse_version(text: str) -> tuple[int, ...] | None:
    """"v0.5.1" → (0, 5, 1); a "+dev" build counts as its tag."""
    m = re.match(r"^\s*v?(\d+(?:\.\d+)*)", text or "")
    return tuple(int(p) for p in m.group(1).split(".")) if m else None


def is_newer(latest: str, current: str) -> bool:
    a, b = parse_version(latest), parse_version(current)
    if a is None or b is None:
        return False
    width = max(len(a), len(b))
    return a + (0,) * (width - len(a)) > b + (0,) * (width - len(b))


# ---------------------------------------------------------------- preferences

def _prefs_path() -> Path:
    from app.paths import data_dir
    return data_dir() / "desktop-prefs.json"


def load_prefs() -> dict:
    try:
        stored = json.loads(_prefs_path().read_text())
    except (OSError, ValueError):
        stored = {}
    return {**DEFAULT_PREFS, **(stored if isinstance(stored, dict) else {})}


def save_prefs(**changes) -> dict:
    prefs = {**load_prefs(), **changes}
    try:
        _prefs_path().write_text(json.dumps(prefs, indent=2))
    except OSError:
        pass
    return prefs


# ---------------------------------------------------------------- the check

def asset_for_this_computer(names: list[str]) -> str | None:
    """Which release file to download here."""
    system = sys.platform
    if system == "darwin":
        want = "BioManager-macOS-AppleSilicon.zip" if platform.machine() == "arm64" else "BioManager-macOS-Intel.zip"
    elif system.startswith("win"):
        want = "BioManager-Windows.zip"
    else:
        want = "BioManager-Linux.AppImage"
    return want if want in names else None


def fetch_latest(timeout: float = 8.0) -> dict:
    """The latest release: {"version", "notes", "page", "download"}.
    Raises OSError (no network, GitHub down) or ValueError (an odd answer)."""
    request = urllib.request.Request(LATEST_API, headers={
        "Accept": "application/vnd.github+json", "User-Agent": f"BioManager/{version()}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (a fixed https URL)
        data = json.loads(response.read().decode("utf-8"))
    tag = str(data.get("tag_name") or "")
    if parse_version(tag) is None:
        raise ValueError("GitHub's answer had no version in it.")
    assets = {a.get("name"): a.get("browser_download_url") for a in data.get("assets") or [] if a.get("name")}
    wanted = asset_for_this_computer(list(assets))
    return {"version": tag.lstrip("v"), "notes": summary(str(data.get("body") or "")),
            "page": str(data.get("html_url") or RELEASES_PAGE),
            "download": assets.get(wanted) if wanted else None}


def summary(notes: str, limit: int = 700) -> str:
    """Release notes as plain text for a dialog: what's new (the notes open
    with a table of downloads and end with how to install), no Markdown
    marks, short."""
    new = re.search(r"^\W*New in\b.*$", notes, flags=re.M)
    if new:
        notes = notes[new.start():]
        ends = [i for i in (notes.find("\nUpdate a lab server"), notes.find("\n**First launch")) if i > 0]
        notes = notes[:min(ends)] if ends else notes
    notes = "\n".join(line for line in notes.splitlines() if not line.lstrip().startswith("|"))
    text = re.sub(r"<!--.*?-->", "", notes, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    text = re.sub(r"[*_`]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def check(manual: bool, now: float | None = None, fetch=fetch_latest) -> dict:
    """What to tell the person:

    {"state": "newer", "release": {...}}   a newer version (not skipped, unless asked)
    {"state": "current", "version": "0.5.0"}
    {"state": "error", "message": "..."}  only when asked
    {"state": "quiet"}                     an automatic check with nothing to say
    """
    now = time.time() if now is None else now
    prefs = load_prefs()
    if not manual and (not prefs["check_updates"] or now - float(prefs["last_check"] or 0) < CHECK_EVERY):
        return {"state": "quiet"}
    current = version()
    try:
        release = fetch()
    except (OSError, ValueError) as error:
        return {"state": "error", "message": f"BioManager couldn't reach GitHub to check ({error})."} if manual \
            else {"state": "quiet"}
    save_prefs(last_check=now)
    if is_newer(release["version"], current) and (manual or release["version"] != prefs["skip_version"]):
        return {"state": "newer", "release": release, "current": current}
    return {"state": "current", "version": current} if manual else {"state": "quiet"}
