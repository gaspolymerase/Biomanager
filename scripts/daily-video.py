#!/usr/bin/env python3
"""A short video for each launch day, in Chinese and in English.

    python scripts/feature-clips.py promo/out <clips…> --plain   # the footage, first
    python scripts/daily-video.py                  # every day, both languages
    python scripts/daily-video.py 1 2 --lang zh    # some days, one language

Each video, about 40 seconds: the day's question on an animated card, the
feature's footage while its lines are read (with subtitles), three points
to remember, and a closing card with the website. The storyboard is
promo/daily.json, whose "voices" are BioManager's own Qwen3-TTS voices
("qwen:zh-a", see scripts/qwen-voice.py) or a macOS voice; the titles come
from promo/posts.json. Cards, music,
sounds and mixing are scripts/explainer-video.py's.

Writes promo/out/daily/dayNN-zh.mp4 (Bilibili), dayNN-en.mp4 (X, LinkedIn,
Facebook) and dayNN-cover-zh.png.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import tempfile
import wave
from pathlib import Path

import numpy as np
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("explainer", ROOT / "scripts/explainer-video.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)
OUT = ROOT / "promo/out/daily"
SR, W, H = ev.SR, ev.W, ev.H

WORDS = {
    "zh": {"day": "第 {n} 天", "series": "BioManager · 每天一个功能", "recap": "今天记住三点",
           "free": "永久免费 · <em>开源</em>", "hint": "链接在简介里 · 有问题欢迎评论区留言",
           "outro": "永久免费开源，链接在简介里。关注我，每天一个新功能。"},
    "en": {"day": "Day {n}", "series": "BioManager · one feature a day", "recap": "Three things to remember",
           "free": "Free and <em>open source</em>, forever", "hint": "The link is in the post · questions welcome",
           "outro": "Free and open source. The link is in the post. Follow for a new feature every day."},
}
FONT = {"zh": ('"PingFang SC", "Hiragino Sans GB", sans-serif', "STHeiti", 58),
        "en": ('-apple-system, "SF Pro Display", "Helvetica Neue", sans-serif', "Helvetica Neue", 52)}


def css(colours, lang):
    return f"""<style>{ev.BASE_CSS}
:root {{ --a:{colours[0]}; --b:{colours[1]}; }}
body {{ font-family: {FONT[lang][0]}; }}
.logo svg {{ width:100%; height:100%; }}
"""


def hook_html(colours, lang, n, hook, title):
    w = WORDS[lang]
    return css(colours, lang) + f"""
.badge {{ position:absolute; left:50%; top:150px; transform:translateX(-50%); }}
.badge span {{ display:inline-block; padding:14px 40px; border-radius:999px; background:#0f8a74; color:#fff;
  font-size:46px; font-weight:800; opacity:0; animation: popin .5s ease-out .1s forwards; }}
.hook {{ position:absolute; left:160px; right:160px; top:330px; text-align:center; font-size:{96 if lang == 'zh' else 88}px;
  font-weight:800; line-height:1.2; text-wrap:balance; opacity:0; animation: rise .6s cubic-bezier(.2,.9,.3,1.2) .35s forwards; }}
.title {{ position:absolute; left:200px; right:200px; top:690px; text-align:center; font-size:48px; color:#0f8a74;
  font-weight:700; opacity:0; animation: rise .5s ease-out 1.1s forwards; }}
.series {{ position:absolute; left:0; right:0; bottom:90px; text-align:center; font-size:34px; color:#4b5563; }}
.series .logo {{ display:inline-block; width:56px; height:56px; vertical-align:middle; margin-right:14px; }}
</style>{ev.blobs()}<div class="badge"><span>{w['day'].format(n=n)}</span></div>
<div class="hook">{hook}</div><div class="title">{title}</div>
<div class="series"><span class="logo">{ev.ICON_SVG}</span>{w['series']}</div>"""


def recap_html(colours, lang, bullets):
    w = WORDS[lang]
    rows = "".join(f'<div class="row" style="animation-delay:{0.35 + 0.45 * i:.2f}s"><b>✓</b>{b}</div>'
                   for i, b in enumerate(bullets))
    return css(colours, lang) + f"""
.head {{ position:absolute; left:0; right:0; top:180px; text-align:center; font-size:64px; font-weight:800; opacity:0;
  animation: rise .5s ease-out .05s forwards; }}
.rows {{ position:absolute; left:50%; top:330px; transform:translateX(-50%); }}
.row {{ display:block; margin:0 0 34px; padding:26px 48px 26px 30px; border-radius:28px; background:rgba(255,255,255,.9);
  box-shadow:0 10px 30px rgba(17,24,39,.08); font-size:58px; font-weight:700; white-space:nowrap; opacity:0;
  animation: popin .5s ease-out forwards; }}
.row b {{ display:inline-block; width:68px; height:68px; line-height:68px; margin-right:26px; border-radius:50%;
  background:#0f8a74; color:#fff; text-align:center; font-size:42px; vertical-align:middle; }}
</style>{ev.blobs()}<div class="head">{w['recap']}</div><div class="rows">{rows}</div>"""


def outro_html(colours, lang):
    w = WORDS[lang]
    if lang == "zh":
        asks = "".join(f'<div class="ask" style="animation-delay:{1.6 + 0.3 * i:.2f}s"><span>{e}</span>{t}</div>'
                       for i, (e, t) in enumerate([("👍", "点赞"), ("🪙", "投币"), ("⭐", "收藏"), ("➕", "关注")]))
    else:
        asks = '<div class="ask wide" style="animation-delay:1.6s"><span>🔔</span>Follow for a feature a day</div>'
    return css(colours, lang) + f"""
.logo {{ position:absolute; left:50%; top:110px; width:200px; height:200px; margin-left:-100px; opacity:0;
  animation: popin .7s cubic-bezier(.2,.9,.3,1.3) .1s forwards; }}
.big {{ position:absolute; left:0; right:0; top:350px; text-align:center; font-size:96px; font-weight:800; opacity:0;
  animation: rise .6s ease-out .4s forwards; }}
.big em {{ font-style:normal; color:#0f8a74; }}
.urlrow {{ position:absolute; left:0; right:0; top:510px; text-align:center; opacity:0; animation: rise .6s ease-out .9s forwards; }}
.url {{ display:inline-block; padding:20px 46px; border-radius:24px; background:#111827; color:#fff; font-size:52px;
  font-family: "SF Mono", Menlo, monospace; }}
.hint {{ position:absolute; left:0; right:0; top:630px; text-align:center; font-size:36px; color:#4b5563; opacity:0;
  animation: rise .5s ease-out 1.2s forwards; }}
.asks {{ position:absolute; left:0; right:0; top:750px; text-align:center; }}
.ask {{ display:inline-block; margin:0 30px; font-size:40px; font-weight:700; opacity:0; animation: popin .5s ease-out forwards; }}
.ask span {{ display:block; font-size:92px; margin-bottom:6px; }}
.ask.wide span {{ display:inline-block; font-size:64px; vertical-align:middle; margin:0 18px 0 0; }}
</style>{ev.blobs()}<div class="logo">{ev.ICON_SVG}</div><div class="big">{w['free']}</div>
<div class="urlrow"><span class="url">biomanager.org</span></div>
<div class="hint">{w['hint']}</div><div class="asks">{asks}</div>"""


def cover_html(colours, n, title):
    """Bilibili's cover: 16:9, everything inside the middle 4:3."""
    return css(colours, "zh") + f"""
.safe {{ position:absolute; left:240px; width:1440px; top:0; height:1080px; text-align:center; }}
.badge {{ display:inline-block; margin-top:120px; padding:16px 46px; border-radius:999px; background:#0f8a74; color:#fff;
  font-size:58px; font-weight:900; }}
.t {{ font-size:118px; font-weight:900; line-height:1.18; margin:60px 40px 0; text-wrap:balance; }}
.s {{ margin-top:50px; font-size:48px; color:#374151; font-weight:700; }}
.s .logo {{ display:inline-block; width:70px; height:70px; vertical-align:middle; margin-right:16px; }}
.free {{ position:absolute; right:30px; top:60px; background:#ef4444; color:#fff; font-size:52px; font-weight:900;
  padding:12px 30px; border-radius:18px; transform:rotate(6deg); }}
</style>{ev.blobs()}<div class="safe"><div class="free">永久免费</div><div class="badge">第 {n} 天</div>
<div class="t">{title}</div><div class="s"><span class="logo">{ev.ICON_SVG}</span>BioManager 1.0 · 免费开源</div></div>"""


def chunks_en(text, limit=46):
    words, out, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > limit:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
        if cur.endswith((",", ".", ":", ";", "?")) and len(cur) > limit * 0.55:
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


def subtitle_events(lang, text, at, seconds):
    parts = ev.chunks(text) if lang == "zh" else chunks_en(text)
    total = sum(len(p) for p in parts)
    out, cur = [], at
    for part in parts:
        d = seconds * len(part) / total
        out.append(f"Dialogue: 0,{ev.ass_time(cur)},{ev.ass_time(cur + d)},Sub,,0,0,0,,{{\\fad(120,80)}}{part}")
        cur += d
    return out


def ass_head(lang):
    _, face, size = FONT[lang]
    return ev.ASS_HEAD.replace("Style: Sub,STHeiti,58", f"Style: Sub,{face},{size}").replace(
        "Style: Tag,STHeiti,36", f"Style: Tag,{face},34")


def make(page, day: dict, lang: str, voices: dict, titles: dict, tmp: Path):
    n, clip = day["day"], day["clip"]
    board, words = day[lang], WORDS[lang]
    voice, rate = voices[lang]
    colours = ev.PALETTE[n % len(ev.PALETTE)]
    title = titles[n].get(f"title_{lang}") or ""
    t, segments, events, narration, sfx, pops = 0.0, [], [], [], [], []

    def say(text):
        return ev.speak(text, voice, rate, tmp)

    # 1. The question.
    v = say(board["hook"])
    length = max(3.4, 0.5 + len(v) / SR + 1.0)
    seg = tmp / f"{lang}-hook.mp4"
    ev.render_card(page, hook_html(colours, lang, n, board["hook"], title), length, seg)
    segments.append(seg)
    narration.append((t + 0.5, v))
    sfx.append(t)
    pops += [t + 0.1, t + 0.4]
    t += length
    # 2. The footage, while the lines are read.
    voices_ = [say(line) for line in board["lines"]]
    talk = sum(len(x) for x in voices_) / SR + ev.GAP * (len(voices_) - 1)
    footage = max(6.0, talk + 1.2)
    seg = tmp / f"{lang}-clip.mp4"
    ev.fit_clip(ROOT / "promo/out" / clip / "plain.mp4", footage, seg)
    segments.append(seg)
    sfx.append(t)
    events.append(f"Dialogue: 1,{ev.ass_time(t + 0.2)},{ev.ass_time(t + footage - 0.2)},Tag,,0,0,0,,"
                  f"{{\\fad(250,250)}}{words['day'].format(n=n)}  {title}")
    at = t + 0.35
    for line, x in zip(board["lines"], voices_):
        narration.append((at, x))
        events += subtitle_events(lang, line, at, len(x) / SR)
        at += len(x) / SR + ev.GAP
    t += footage
    # 3. Three things to remember.
    length = 0.35 + 0.45 * len(board["bullets"]) + 2.4
    seg = tmp / f"{lang}-recap.mp4"
    ev.render_card(page, recap_html(colours, lang, board["bullets"]), length, seg)
    segments.append(seg)
    sfx.append(t)
    pops += [t + 0.35 + 0.45 * i for i in range(len(board["bullets"]))]
    t += length
    # 4. The website.
    v = say(words["outro"])
    length = max(5.0, 0.4 + len(v) / SR + 1.6)
    seg = tmp / f"{lang}-outro.mp4"
    ev.render_card(page, outro_html(colours, lang), length, seg)
    segments.append(seg)
    narration.append((t + 0.4, v))
    sfx.append(t)
    pops += [t + 0.1] + [t + 1.6 + 0.3 * i for i in range(4 if lang == "zh" else 1)]
    t += length

    # Join, subtitle, mix.
    listing = tmp / f"{lang}-list.txt"
    listing.write_text("".join(f"file '{s}'\n" for s in segments))
    joined = tmp / f"{lang}-joined.mp4"
    ev.run(ev.FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing, "-c", "copy", joined)
    ass = tmp / f"{lang}.ass"
    ass.write_text(ass_head(lang) + "\n".join(events) + "\n")
    n_samples = int((t + 0.5) * SR)
    vox = np.zeros(n_samples)
    for when, x in narration:
        ev.place(vox, x.astype(np.float64) * 0.95, when)
    talking = np.convolve((np.abs(vox) > 0.01).astype(float), np.ones(int(0.25 * SR)) / (0.25 * SR), "same")
    duck = 0.30 - 0.20 * np.clip(talking * 4, 0, 1)
    bed = ev.music(n_samples / SR + 0.05)[:n_samples]
    bed = np.pad(bed, ((0, n_samples - len(bed)), (0, 0))) * duck[:, None]
    fx = np.zeros(n_samples)
    for when in sfx:
        ev.place(fx, ev.whoosh(), max(0, when - 0.25))
    for i, when in enumerate(pops):
        ev.place(fx, ev.pop(660 + 110 * (i % 5)) * 0.6, when)
    mix = bed + (vox + fx)[:, None]
    mix /= max(1e-6, np.abs(mix).max() / 0.9)
    wav = tmp / f"{lang}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype("<i2").tobytes())
    final = OUT / f"day{n:02d}-{lang}.mp4"
    ev.run(ev.FFMPEG, "-y", "-loglevel", "error", "-i", joined, "-i", wav, "-vf",
           f"subtitles={ass}:fontsdir=/System/Library/Fonts", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", final)
    if lang == "zh":
        page.set_content(f"<!doctype html><html><head><meta charset='utf-8'></head><body>"
                         f"{cover_html(colours, n, titles[n].get('title_zh', ''))}</body></html>")
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / f"day{n:02d}-cover-zh.png"))
    return final, t


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("days", nargs="*", type=int)
    ap.add_argument("--lang", choices=("zh", "en"))
    args = ap.parse_args()
    board = json.loads((ROOT / "promo/daily.json").read_text())
    titles = {p["day"]: p for p in json.loads((ROOT / "promo/posts.json").read_text())["posts"]}
    voices = board["voices"]
    OUT.mkdir(parents=True, exist_ok=True)
    days = [d for d in board["days"] if not args.days or d["day"] in args.days]
    langs = [args.lang] if args.lang else ["zh", "en"]
    # Qwen voices read every line of these days in one run of the model.
    ev.prefetch([(voices[lang][0], text) for d in days for lang in langs
                 for text in [d[lang]["hook"], *d[lang]["lines"], WORDS[lang]["outro"]]])
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H})
        for day in days:
            if not (ROOT / "promo/out" / day["clip"] / "plain.mp4").exists():
                print(f"day {day['day']}: no footage for {day['clip']}; run feature-clips.py --plain first", flush=True)
                continue
            for lang in langs:
                with tempfile.TemporaryDirectory(prefix="daily-") as tmp:
                    final, seconds = make(page, day, lang, voices, titles, Path(tmp))
                print(f"day {day['day']:2d} {lang}: {final.name} {seconds:.1f} s", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
