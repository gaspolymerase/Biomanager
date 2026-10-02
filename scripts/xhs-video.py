#!/usr/bin/env python3
"""The day's narrated video on a 3:4 canvas, for Xiaohongshu.

    python scripts/daily-video.py 1 --lang zh     # the Chinese video, first
    python scripts/xhs-video.py 1                 # then this, for some days
    python scripts/xhs-video.py                   # or every day that has one

Puts promo/out/daily/dayNN-zh.mp4 (16:9, with its voice, music and
subtitles) on the same portrait card as the note's cover: the clip's title
and subtitle above, its three points and the brand below (feature-clips.py's
Layout); for day 0 it is promo/out/explainer/explainer.mp4, on the tour's card.
Writes promo/out/daily/dayNN-xhs.mp4, which post-pack.py uses as
xhs.mp4 in place of the silent clip.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("feature_clips", ROOT / "scripts/feature-clips.py")
fc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fc)
DAILY = ROOT / "promo/out/daily"
CANVAS = (1080, 1440)


def ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def seconds(video: Path) -> float:
    info = subprocess.run([ffmpeg(), "-i", str(video)], capture_output=True, text=True).stderr
    h, m, sec = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info).groups()
    return int(h) * 3600 + int(m) * 60 + float(sec)


def make(day: dict, meta: dict, colours, tmp: Path) -> Path | None:
    source = (ROOT / "promo/out/explainer/explainer.mp4" if day["day"] == 0
              else DAILY / f"day{day['day']:02d}-zh.mp4")
    if not source.exists():
        return None
    layout = fc.Layout(CANVAS, meta.get("title_zh", day["clip"]), meta.get("subtitle_zh", ""), "zh",
                       colours, meta.get("bullets_zh", ()))
    cw, ch = CANVAS
    top, bottom = layout.area
    w = int(cw * 0.92) // 2 * 2
    h = min(int(w * 9 / 16), bottom - top) // 2 * 2
    w = int(h * 16 / 9) // 2 * 2
    at = ((cw - w) // 2, top + (bottom - top - h) // 2)
    radius = int(w * 0.02)
    # The card, with a soft shadow where the video sits.
    bg = layout.bg.convert("RGBA")
    shadow = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((at[0], at[1] + 14, at[0] + w, at[1] + h + 14), radius,
                                             fill=(30, 41, 59, 70))
    bg = Image.alpha_composite(bg, shadow.filter(ImageFilter.GaussianBlur(26)))
    bg.convert("RGB").save(tmp / "bg.png")
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius, fill=255)
    mask.save(tmp / "mask.png")
    out = DAILY / f"day{day['day']:02d}-xhs.mp4"
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-loop", "1", "-i", str(tmp / "bg.png"), "-i", str(source),
                    "-loop", "1", "-i", str(tmp / "mask.png"),
                    "-filter_complex",
                    f"[1:v]scale={w}:{h}:flags=lanczos,format=rgba[v];[2:v]format=gray[m];[v][m]alphamerge[r];"
                    f"[0:v][r]overlay={at[0]}:{at[1]}:shortest=1,format=yuv420p[out]",
                    "-map", "[out]", "-map", "1:a", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
                    "-r", "30", "-c:a", "copy", "-t", f"{seconds(source):.3f}", "-movflags", "+faststart", str(out)], check=True)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("days", nargs="*", type=int)
    args = ap.parse_args()
    board = json.loads((ROOT / "promo/daily.json").read_text())
    info = fc.titles()
    clips, _ = fc.load_clips()
    order = list(clips)
    for day in [{"day": 0, "clip": "tour"}, *board["days"]]:   # day 0, the launch, shows the tour
        if args.days and day["day"] not in args.days:
            continue
        meta = info.get(day["clip"], {})
        colours = tuple(meta.get("gradient") or fc.GRADIENTS[order.index(day["clip"]) % len(fc.GRADIENTS)])
        with tempfile.TemporaryDirectory(prefix="xhs-") as tmp:
            out = make(day, meta, colours, Path(tmp))
        print(f"day {day['day']:2d}: {out.name if out else 'no dayNN-zh.mp4 yet; run daily-video.py first'}",
              flush=True)


if __name__ == "__main__":
    main()
