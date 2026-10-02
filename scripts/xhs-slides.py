#!/usr/bin/env python3
"""Pictures for a Xiaohongshu 图文 note: a few 3:4 slides that read on a phone.

    python scripts/xhs-slides.py 0        # day 0's slides

The words are promo/xhs-slides.json, one entry per day: the note's title
and text, and its slides (a cover, a list, a feature with a screenshot and
three points, a closing card). The screenshots are docs/screenshots/, cut
to the part worth reading. Writes promo/out/xhs-slides/dayNN/01.png… and
note.md with the title and text to paste. It never posts anything.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "docs/screenshots"
OUT = ROOT / "promo/out/xhs-slides"
W, H = 1080, 1440
TEAL, INK, GREY = "#0f8a74", "#111827", "#4b5563"
BACKGROUNDS = ["#f3fbf8", "#fff8ef", "#f4f6ff", "#f9f4ff", "#f0f9ff", "#fffbea", "#f3fbf8", "#fff4f4", "#f3fbf8"]

CSS = f"""
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ width:{W}px; height:{H}px; overflow:hidden; font-family:"PingFang SC","Hiragino Sans GB",sans-serif;
  color:{INK}; position:relative; }}
mark {{ background:linear-gradient(transparent 55%, #ffe066 55%); color:inherit; padding:0 6px; }}
.page {{ position:absolute; right:56px; top:52px; font-size:28px; color:#9ca3af; font-weight:500; }}
.brand {{ position:absolute; left:0; right:0; bottom:46px; text-align:center; font-size:30px; color:{GREY}; font-weight:500; }}
.brand img {{ width:44px; height:44px; vertical-align:-12px; margin-right:10px; border-radius:10px; }}
.tag {{ display:inline-block; padding:12px 30px; border-radius:999px; background:{TEAL}; color:#fff; font-size:34px;
  font-weight:600; letter-spacing:2px; }}
.window {{ background:#fff; border-radius:22px; overflow:hidden; box-shadow:0 24px 60px rgba(15,23,42,.16),
  0 2px 6px rgba(15,23,42,.08); border:1px solid #e5e7eb; }}
.bar {{ height:40px; background:#f3f4f6; border-bottom:1px solid #e5e7eb; padding:0 18px; display:flex; gap:10px;
  align-items:center; }}
.bar i {{ width:14px; height:14px; border-radius:50%; display:block; }}
.shot {{ background-repeat:no-repeat; }}
.phone {{ position:absolute; border-radius:46px; background:#111; padding:14px; box-shadow:0 30px 60px rgba(15,23,42,.3); }}
.phone div {{ border-radius:34px; background-size:cover; background-position:top center; }}
"""


def data_uri(path: Path) -> str:
    """Pages set from a string can't load file:// pictures, so they go in whole."""
    kind = {".webp": "image/webp", ".png": "image/png"}[path.suffix]
    return f"data:{kind};base64,{base64.b64encode(path.read_bytes()).decode()}"


def shot(name: str, crop, width: int) -> str:
    """A screenshot cut to crop (x, y, w, h in its own pixels), shown width wide, in a window."""
    from PIL import Image
    path = SHOTS / f"{name}.webp"
    sw, sh = Image.open(path).size
    x, y, w, h = crop
    height = round(width * h / w)
    scale = width / w
    return (f'<div class="window" style="width:{width}px"><div class="bar"><i style="background:#ff5f57"></i>'
            f'<i style="background:#febc2e"></i><i style="background:#28c840"></i></div>'
            f'<div class="shot" style="height:{height}px;background-image:url({data_uri(path)});'
            f'background-size:{sw * scale:.0f}px {sh * scale:.0f}px;background-position:-{x * scale:.0f}px -{y * scale:.0f}px">'
            f'</div></div>')


def phone(name: str, width: int, left: int, top: int) -> str:
    path = SHOTS / f"{name}.webp"
    return (f'<div class="phone" style="left:{left}px;top:{top}px;width:{width}px">'
            f'<div style="height:{round((width - 28) * 1328 / 780)}px;background-image:url({data_uri(path)})"></div></div>')


def lines(title) -> str:
    return "<br>".join(title if isinstance(title, list) else [title])


def slide(s: dict, n: int, total: int, version: str) -> str:
    fill = lambda t: t.replace("{version}", version)  # noqa: E731
    icon = data_uri(ROOT / "app/static/icon-512.png")
    page = f'<div class="page">{n}/{total}</div>'
    brand = f'<div class="brand"><img src="{icon}">BioManager · 免费开源</div>'
    bg = BACKGROUNDS[(n - 1) % len(BACKGROUNDS)]
    kind = s["kind"]
    if kind == "cover":
        chips = "".join(f'<span style="display:inline-block;margin:8px;padding:12px 26px;border-radius:999px;'
                        f'background:#fff;border:2px solid #d1e7df;font-size:32px;font-weight:500">{html.escape(c)}</span>'
                        for c in s["chips"])
        body = (f'<div style="position:absolute;left:70px;right:70px;top:96px">'
                f'<span class="tag">{html.escape(s["tag"])}</span>'
                f'<div style="margin-top:36px;font-size:92px;line-height:1.22;font-weight:800">{lines(s["title"])}</div>'
                f'<div style="margin-top:26px;font-size:38px;color:{GREY};font-weight:500">{html.escape(fill(s["sub"]))}</div></div>'
                f'<div style="position:absolute;left:60px;top:640px;transform:rotate(-2deg)">{shot(s["shot"], s["crop"], 780)}</div>'
                f'{phone(s["phone"], 260, 760, 700)}'
                f'<div style="position:absolute;left:40px;right:40px;bottom:110px;text-align:center">{chips}</div>')
    elif kind == "list":
        items = "".join(f'<div style="display:flex;align-items:center;gap:26px;margin-bottom:26px;padding:34px 38px;'
                        f'background:#fff;border-radius:26px;box-shadow:0 8px 24px rgba(15,23,42,.07);font-size:40px;'
                        f'font-weight:500"><span style="font-size:44px">❌</span>{html.escape(t)}</div>'
                        for t in s["items"])
        body = (f'<div style="position:absolute;left:70px;right:70px;top:120px">'
                f'<div style="font-size:84px;line-height:1.25;font-weight:800;margin-bottom:60px">{lines(s["title"])}</div>'
                f'{items}<div style="margin-top:50px;font-size:50px;font-weight:700;text-align:center">{s["end"]}</div></div>')
    elif kind == "feature":
        points = "".join(f'<div style="display:flex;gap:22px;align-items:flex-start;margin-bottom:24px;font-size:40px;'
                         f'line-height:1.4;font-weight:500"><span style="flex:none;width:52px;height:52px;border-radius:50%;'
                         f'background:{TEAL};color:#fff;font-size:30px;font-weight:700;display:flex;align-items:center;'
                         f'justify-content:center;margin-top:2px">{i}</span><span>{html.escape(t)}</span></div>'
                         for i, t in enumerate(s["points"], 1))
        pic = shot(s["shot"], s["crop"], 940)
        extra = phone(s["phone"], 250, 770, 520) if s.get("phone") else ""
        body = (f'<div style="position:absolute;left:70px;right:70px;top:100px">'
                f'<div style="font-size:88px;font-weight:800;line-height:1.2">{s["emoji"]} {html.escape(s["title"])}</div>'
                f'<div style="margin-top:18px;font-size:42px;color:{TEAL};font-weight:600">{html.escape(s["sub"])}</div></div>'
                f'<div style="position:absolute;left:70px;top:330px">{pic}</div>{extra}'
                f'<div style="position:absolute;left:80px;right:70px;bottom:130px">{points}</div>')
    else:  # end
        items = "".join(f'<div style="display:flex;gap:28px;align-items:center;margin-bottom:18px;padding:22px 34px;'
                        f'background:#fff;border-radius:26px;box-shadow:0 8px 24px rgba(15,23,42,.07)">'
                        f'<span style="font-size:58px">{e}</span><div><div style="font-size:44px;font-weight:700">'
                        f'{html.escape(a)}</div><div style="margin-top:6px;font-size:34px;color:{GREY}">{html.escape(b)}'
                        f'</div></div></div>' for e, a, b in s["items"])
        body = (f'<div style="position:absolute;left:70px;right:70px;top:100px">'
                f'<div style="font-size:82px;line-height:1.22;font-weight:800;margin-bottom:40px">{lines(s["title"])}</div>'
                f'{items}<div style="margin-top:30px;text-align:center"><div style="font-size:34px;color:{GREY}">官网下载</div>'
                f'<div style="display:inline-block;margin-top:16px;padding:22px 40px;border-radius:24px;background:{INK};'
                f'color:#fff;font-size:44px;font-weight:600">{html.escape(s["site"])}</div>'
                f'<div style="margin-top:26px;font-size:36px;color:{TEAL};font-weight:600">{html.escape(s["follow"])}</div>'
                f'</div></div>')
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head>'
            f'<body style="background:{bg}">{page}{body}{brand}</body></html>')


def version() -> str:
    try:
        tag = subprocess.run(["gh", "release", "view", "--repo", "gaspolymerase/biomanager", "--json", "tagName",
                              "-q", ".tagName"], capture_output=True, text=True, timeout=20).stdout.strip().lstrip("v")
    except (OSError, subprocess.TimeoutExpired):
        tag = ""
    return tag[:-2] if tag.endswith(".0") and tag.count(".") == 2 else (tag or "1.0")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("days", nargs="+")
    args = ap.parse_args()
    notes = json.loads((ROOT / "promo/xhs-slides.json").read_text())
    tags = " ".join(json.loads((ROOT / "promo/posts.json").read_text())["tags_zh"])
    ver = version()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H})
        for day in args.days:
            note = notes[day]
            folder = OUT / f"day{int(day):02d}"
            folder.mkdir(parents=True, exist_ok=True)
            for n, s in enumerate(note["slides"], 1):
                page.set_content(slide(s, n, len(note["slides"]), ver), wait_until="load")
                page.wait_for_timeout(300)
                page.screenshot(path=str(folder / f"{n:02d}.png"))
            (folder / "note.md").write_text(f"Title:\n\n{note['title']}\n\nText:\n\n"
                                            f"{note['body'].replace('{version}', ver)}\n\n{tags}\n")
            print(folder, flush=True)
        browser.close()


if __name__ == "__main__":
    main()
