#!/usr/bin/env python3
"""Take the README and website screenshots from a running demo lab.

    python scripts/demo-data.py /tmp/biomanager-demo
    BIOMANAGER_DATA_DIR=/tmp/biomanager-demo PORT=5077 python run.py
    python scripts/screenshots.py http://127.0.0.1:5077 /tmp/biomanager-demo docs/screenshots

Needs Playwright, which is not an app dependency:
    pip install playwright && playwright install chromium
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

if len(sys.argv) != 4:
    sys.exit(__doc__)
BASE, DATA, OUT = sys.argv[1].rstrip("/"), Path(sys.argv[2]), Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
PASSWORD = (DATA / "demo-password").read_text().strip()

# name, path, color scheme, and anything to do before the shot
DESKTOP = [
    ("home", "/home", "light", None),
    ("home-dark", "/home", "dark", None),
    ("mice", "/colony?view=mice", "light", None),
    ("cages", "/colony?view=cages", "light", None),
    ("rack-grid", "/colony?view=cages", "light", "[data-layout=grid]"),
    ("fly-stocks", "/stocks/drosophila", "light", None),
    ("fly-grid", "/stocks/drosophila", "light", "[data-layout=grid]"),
    ("plasmid-map", "/plasmids/2", "light", None),
    ("orders", "/orders", "light", "[data-layout=board]"),
    ("reagents", "/inventory/reagents", "light", None),
    ("calendar", "/calendar", "light", None),
    ("new-database", "/organisms/new", "light", None),
    ("cage-cards", "/labels/cards/cages", "light", None),
]
PHONE = [
    ("phone-cage", "/colony?view=cages&scope=all#cage-1", "light"),
    ("phone-home", "/home", "light"),
]


def sign_in(page):
    page.goto(f"{BASE}/login")
    page.fill("input[name=username]", "alex")
    page.fill("input[name=password]", PASSWORD)
    page.press("input[name=password]", "Enter")
    page.wait_for_load_state("networkidle")


def shoot(page, name, path, click=None, full=False):
    page.goto(f"{BASE}{path}")
    page.wait_for_load_state("networkidle")
    if click:
        page.locator(click).first.click()
        page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)  # let maps, grids and fonts settle
    if "#" not in path:  # a page that focuses a field scrolls to it; start at the top
        page.evaluate("document.activeElement && document.activeElement.blur();"
                      "document.querySelectorAll('*').forEach(e => { if (e.scrollTop) e.scrollTop = 0 });"
                      "window.scrollTo(0, 0)")
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)
    print(f"  {name}.png")


with sync_playwright() as p:
    browser = p.chromium.launch()
    for scheme in ("light", "dark"):
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2,
                                  color_scheme=scheme)
        page = ctx.new_page()
        sign_in(page)
        for name, path, want, click in DESKTOP:
            if want == scheme:
                shoot(page, name, path, click)
        ctx.close()

    phone = browser.new_context(**p.devices["iPhone 13"], color_scheme="light")
    page = phone.new_page()
    sign_in(page)
    for name, path, _ in PHONE:
        shoot(page, name, path)
    phone.close()
    browser.close()
