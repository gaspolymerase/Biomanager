#!/usr/bin/env python3
"""Make the Bilibili explainer: animated cards, the app's own footage,
Chinese narration with subtitles, music and sound.

    python scripts/feature-clips.py promo/out <clips…> --plain   # the footage, first
    python scripts/explainer-video.py                            # promo/out/explainer/

The storyboard is promo/explainer.json: an intro, one scene per feature
(a chapter card, then that clip's footage while its lines are read), and
an outro. The narration is macOS's own Mandarin voice (`say`); the music
and the sounds are made here, so nothing in the video needs a licence.

Writes promo/out/explainer/explainer.mp4 (1920×1080, 30 fps, AAC) and
cover.png (Bilibili's 16:9 cover).
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "promo/out/explainer"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H, FPS, SR = 1920, 1080, 30, 48000
CARD = 2.2           # seconds of chapter card before each clip
GAP = 0.35           # between narration lines
ICON_SVG = (ROOT / "app/static/icon.svg").read_text()
PALETTE = [("#dbeafe", "#ede9fe"), ("#dcfce7", "#e0f2fe"), ("#fef3c7", "#fce7f3"),
           ("#e0e7ff", "#fae8ff"), ("#ccfbf1", "#e0e7ff"), ("#ffe4e6", "#fef9c3")]


def run(*cmd, **kw):
    return subprocess.run([str(c) for c in cmd], check=True, capture_output=True, **kw)


def duration(path: Path) -> float:
    err = subprocess.run([FFMPEG, "-i", str(path)], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


# ---------------------------------------------------------------------------
# Narration
# ---------------------------------------------------------------------------

def speak(text: str, voice: str, rate: int, tmp: Path) -> np.ndarray:
    aiff, raw = tmp / "line.aiff", tmp / "line.raw"
    run("say", "-v", voice, "-r", rate, "-o", aiff, text)
    run(FFMPEG, "-y", "-loglevel", "error", "-i", aiff, "-ac", "1", "-ar", SR, "-f", "f32le", raw)
    return np.fromfile(raw, dtype=np.float32)


# ---------------------------------------------------------------------------
# Music and sounds, made here
# ---------------------------------------------------------------------------

def note(freq, dur, sr=SR):
    t = np.arange(int(dur * sr)) / sr
    # A soft electric piano: a few harmonics, a quick attack, a long decay.
    tone = (np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(4 * np.pi * freq * t + 0.3)
            + 0.12 * np.sin(6 * np.pi * freq * t + 0.7)) * np.exp(-t * 2.2)
    return tone * np.minimum(1, t / 0.01)


def music(seconds: float) -> np.ndarray:
    """A calm loop at 88 bpm: Cmaj7 – Am7 – Fmaj7 – G6, bass, soft drums."""
    beat = 60 / 88
    bar = beat * 4
    n = int((seconds + 2) * SR)
    left, right = np.zeros(n), np.zeros(n)
    chords = [[60, 64, 67, 71], [57, 60, 64, 67], [53, 57, 60, 64], [55, 59, 62, 64]]
    roots = [36, 33, 29, 31]
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    rng = np.random.default_rng(3)
    t_bar = 0.0
    k = 0
    while t_bar < seconds + 2:
        chord, root = chords[k % 4], roots[k % 4]
        for b in range(4):
            start = t_bar + b * beat
            i = int(start * SR)
            if i >= n:
                break
            # Chord stabs on 1 and the "and" of 2, spread across the stereo field.
            if b in (0, 2):
                for j, m in enumerate(chord):
                    s = note(hz(m), bar * 0.9) * 0.11
                    pan = 0.35 + 0.1 * j
                    e = min(n, i + len(s))
                    left[i:e] += s[:e - i] * (1 - pan)
                    right[i:e] += s[:e - i] * pan
            # Bass on 1 and 3.
            if b in (0, 2):
                t = np.arange(int(beat * 1.8 * SR)) / SR
                s = np.sin(2 * np.pi * hz(root + 12) * t) * np.exp(-t * 1.5) * 0.22
                e = min(n, i + len(s))
                left[i:e] += s[:e - i]
                right[i:e] += s[:e - i]
            # Kick on 1 and 3, a soft clap on 2 and 4, a hat on every half beat.
            t = np.arange(int(0.25 * SR)) / SR
            if b in (0, 2):
                s = np.sin(2 * np.pi * (45 + 70 * np.exp(-t * 30)) * t) * np.exp(-t * 14) * 0.35
            else:
                s = rng.normal(0, 1, len(t)) * np.exp(-t * 28) * 0.06
            e = min(n, i + len(s))
            left[i:e] += s[:e - i]
            right[i:e] += s[:e - i]
            for half in (0, 0.5):
                ih = int((start + half * beat + (0.04 if half else 0)) * SR)
                th = np.arange(int(0.05 * SR)) / SR
                hat = np.diff(rng.normal(0, 1, len(th) + 1)) * np.exp(-th * 90) * 0.025
                e = min(n, ih + len(hat))
                if ih < n:
                    left[ih:e] += hat[:e - ih] * 0.8
                    right[ih:e] += hat[:e - ih]
        t_bar += bar
        k += 1
    mix = np.stack([left, right], 1)[: int(seconds * SR)]
    fade = np.minimum(1, np.minimum(np.arange(len(mix)) / (1.5 * SR), (len(mix) - np.arange(len(mix))) / (2.5 * SR)))
    return mix * fade[:, None]


def whoosh(seconds=0.55):
    t = np.arange(int(seconds * SR)) / SR
    noise = np.random.default_rng(7).normal(0, 1, len(t))
    # A crude sweep: smooth the noise less and less as it rises.
    out, y = np.zeros(len(t)), 0.0
    for i, x in enumerate(noise):
        a = 0.03 + 0.5 * (i / len(t)) ** 2
        y += a * (x - y)
        out[i] = y
    env = np.sin(np.pi * np.minimum(1, t / seconds)) ** 2
    return out * env * 0.5


def pop(freq=880, seconds=0.12):
    t = np.arange(int(seconds * SR)) / SR
    return np.sin(2 * np.pi * freq * t * (1 + 0.6 * np.exp(-t * 40))) * np.exp(-t * 35) * 0.35


def place(track, sound, at):
    i = int(at * SR)
    if i >= len(track):
        return
    e = min(len(track), i + len(sound))
    track[i:e] += sound[: e - i] if track.ndim == 1 else sound[: e - i, None]


# ---------------------------------------------------------------------------
# Animated cards: HTML, stepped frame by frame
# ---------------------------------------------------------------------------

BASE_CSS = """
* { margin: 0; box-sizing: border-box; }
html, body { width: 1920px; height: 1080px; overflow: hidden; }
body { font-family: "PingFang SC", "Hiragino Sans GB", "STHeiti", sans-serif; color: #111827;
       background: linear-gradient(135deg, var(--a), var(--b)); position: relative; }
.blob { position: absolute; border-radius: 50%; filter: blur(60px); opacity: .55; animation: drift 12s ease-in-out infinite alternate; }
@keyframes drift { from { transform: translate(0,0) scale(1); } to { transform: translate(80px,-40px) scale(1.15); } }
@keyframes rise { from { opacity: 0; transform: translateY(40px); } to { opacity: 1; transform: none; } }
@keyframes popin { 0% { opacity: 0; transform: scale(.4); } 70% { opacity: 1; transform: scale(1.08); } 100% { opacity: 1; transform: scale(1); } }
@keyframes wipe { from { clip-path: inset(0 100% 0 0); } to { clip-path: inset(0 0 0 0); } }
@keyframes grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@keyframes fadeout { to { opacity: 0; transform: scale(1.04); } }
"""


def blobs():
    return ('<div class="blob" style="width:700px;height:700px;left:-120px;top:-180px;background:#fff"></div>'
            '<div class="blob" style="width:600px;height:600px;right:-100px;bottom:-160px;background:#fff;animation-delay:-4s"></div>')


def intro_html(colours):
    tiles = []
    rng = np.random.default_rng(11)
    for i in range(20):
        x, r = rng.uniform(60, 1660), rng.uniform(-18, 18)
        y = rng.uniform(60, 290) if i % 2 else rng.uniform(640, 880)   # above and below the question
        dx, dy = (x - 860) * 1.6, (y - 480) * 1.6 - 300
        tiles.append(f'<div class="tile" style="left:{x:.0f}px;top:{y:.0f}px;--r:{r:.0f}deg;--dx:{dx:.0f}px;--dy:{dy:.0f}px;'
                     f'animation-delay:{0.08 * i:.2f}s, 2.75s"><b>X</b> 表格{i + 1}.xlsx<i></i><i></i><i></i></div>')
    chips = ["🐭 小鼠", "🐟 斑马鱼", "🪰 果蝇", "🪱 线虫", "🧬 质粒", "🧪 试剂", "🛒 订单", "📅 日历", "📓 记录本"]
    chip_html = "".join(f'<span class="chip" style="animation-delay:{4.3 + 0.12 * i:.2f}s">{c}</span>' for i, c in enumerate(chips))
    q = "还在用 20 个 Excel 管实验室？"
    q_html = "".join(f'<span style="animation-delay:{0.3 + 0.045 * i:.3f}s">{c if c != " " else "&nbsp;"}</span>' for i, c in enumerate(q))
    return f"""<style>{BASE_CSS}
:root {{ --a:{colours[0]}; --b:{colours[1]}; }}
.tile {{ position:absolute; width:220px; height:150px; background:#fff; border-radius:14px; border:3px solid #1d6f42;
  box-shadow:0 12px 30px rgba(29,111,66,.25); padding:14px; font-size:22px; color:#1d6f42; font-weight:600;
  transform: rotate(var(--r)); opacity:0; animation: drop .6s cubic-bezier(.2,.9,.3,1.2) forwards, scatter .6s ease-in forwards; }}
.tile b {{ display:inline-block; background:#1d6f42; color:#fff; border-radius:6px; padding:0 8px; margin-right:6px; }}
.tile i {{ display:block; height:10px; margin-top:12px; background:repeating-linear-gradient(90deg,#c7e6d4 0 46px,transparent 46px 52px); }}
@keyframes drop {{ from {{ opacity:0; transform: translateY(-500px) rotate(var(--r)); }} to {{ opacity:1; transform: rotate(var(--r)); }} }}
@keyframes scatter {{ to {{ opacity:0; transform: translate(var(--dx),var(--dy)) rotate(calc(var(--r) * 6)); }} }}
.q {{ position:absolute; left:0; right:0; top:410px; text-align:center; font-size:96px; font-weight:800; letter-spacing:2px;
  z-index:10; animation: fadeout .4s ease-in 2.75s forwards; }}
.q div {{ display:inline-block; padding:26px 56px; border-radius:36px; background:rgba(255,255,255,.88);
  box-shadow:0 18px 50px rgba(17,24,39,.12); }}
.q span {{ display:inline-block; opacity:0; animation: popin .45s ease-out forwards; }}
.logo {{ position:absolute; left:50%; top:200px; width:300px; height:300px; margin-left:-150px; opacity:0;
  animation: popin .8s cubic-bezier(.2,.9,.3,1.3) 3.15s forwards; filter: drop-shadow(0 20px 40px rgba(15,138,116,.35)); }}
.logo svg {{ width:100%; height:100%; }}
.name {{ position:absolute; left:0; right:0; top:530px; text-align:center; font-size:120px; font-weight:800; opacity:0;
  font-family: -apple-system, "SF Pro Display", "PingFang SC", sans-serif; animation: rise .7s ease-out 3.55s forwards; }}
.name em {{ font-style:normal; color:#0f8a74; }}
.tag {{ position:absolute; left:0; right:0; top:690px; text-align:center; font-size:48px; color:#374151; opacity:0;
  animation: rise .6s ease-out 3.9s forwards; }}
.chips {{ position:absolute; left:0; right:0; top:820px; text-align:center; }}
.chip {{ display:inline-block; margin:0 10px; padding:14px 26px; border-radius:999px; background:rgba(255,255,255,.85);
  font-size:36px; box-shadow:0 6px 18px rgba(0,0,0,.08); opacity:0; animation: popin .45s ease-out forwards; }}
</style>{blobs()}{''.join(tiles)}<div class="q"><div>{q_html}</div></div>
<div class="logo">{ICON_SVG}</div><div class="name">BioManager <em>1.0</em></div>
<div class="tag">永久免费 · 开源 · 数据在你自己手里</div><div class="chips">{chip_html}</div>"""


def chapter_html(colours, number, title, subtitle):
    return f"""<style>{BASE_CSS}
:root {{ --a:{colours[0]}; --b:{colours[1]}; }}
.wrap {{ position:absolute; left:220px; top:330px; animation: fadeout .35s ease-in {CARD - 0.35:.2f}s forwards; }}
.num {{ font-size:220px; font-weight:800; color:#0f8a74; line-height:1; opacity:0;
  font-family: -apple-system, "SF Pro Display", sans-serif; animation: rise .55s cubic-bezier(.2,.9,.3,1.2) .05s forwards; }}
.bar {{ width:900px; height:10px; border-radius:5px; background:#0f8a74; margin:30px 0 34px; transform-origin:left;
  transform:scaleX(0); animation: grow .5s ease-out .3s forwards; }}
.title {{ font-size:104px; font-weight:800; animation: wipe .6s ease-out .35s both; white-space:nowrap; }}
.sub {{ font-size:46px; color:#4b5563; margin-top:26px; opacity:0; animation: rise .5s ease-out .75s forwards; }}
.logo {{ position:absolute; right:140px; bottom:110px; width:150px; height:150px; opacity:0;
  animation: popin .6s ease-out .5s forwards; }}
.logo svg {{ width:100%; height:100%; }}
</style>{blobs()}<div class="wrap"><div class="num">{number}</div><div class="bar"></div>
<div class="title">{title}</div><div class="sub">{subtitle}</div></div><div class="logo">{ICON_SVG}</div>"""


def outro_html(colours):
    asks = [("👍", "点赞"), ("🪙", "投币"), ("⭐", "收藏"), ("➕", "关注")]
    ask_html = "".join(f'<div class="ask" style="animation-delay:{2.2 + 0.35 * i:.2f}s"><span>{e}</span>{w}</div>'
                       for i, (e, w) in enumerate(asks))
    return f"""<style>{BASE_CSS}
:root {{ --a:{colours[0]}; --b:{colours[1]}; }}
.logo {{ position:absolute; left:50%; top:110px; width:220px; height:220px; margin-left:-110px; opacity:0;
  animation: popin .7s cubic-bezier(.2,.9,.3,1.3) .1s forwards; }}
.logo svg {{ width:100%; height:100%; }}
.big {{ position:absolute; left:0; right:0; top:370px; text-align:center; font-size:110px; font-weight:800; opacity:0;
  animation: rise .6s ease-out .5s forwards; }}
.big em {{ font-style:normal; color:#0f8a74; }}
.urlrow {{ position:absolute; left:0; right:0; top:540px; text-align:center; opacity:0; animation: rise .6s ease-out 1.1s forwards; }}
.url {{ display:inline-block; padding:22px 48px; border-radius:24px; background:#111827; color:#fff; font-size:54px;
  font-family: "SF Mono", Menlo, monospace; white-space:nowrap; }}
.hint {{ position:absolute; left:0; right:0; top:660px; text-align:center; font-size:38px; color:#4b5563; opacity:0;
  animation: rise .5s ease-out 1.5s forwards; }}
.asks {{ position:absolute; left:0; right:0; top:780px; text-align:center; }}
.ask {{ display:inline-block; margin:0 34px; font-size:40px; font-weight:700; opacity:0; animation: popin .5s ease-out forwards; }}
.ask span {{ display:block; font-size:96px; margin-bottom:8px; }}
</style>{blobs()}<div class="logo">{ICON_SVG}</div><div class="big">永久免费 · <em>开源</em></div>
<div class="urlrow"><span class="url">gaspolymerase.github.io/biomanager</span></div><div class="hint">链接在简介里 · 有问题欢迎评论区留言</div>
<div class="asks">{ask_html}</div>"""


def cover_html(colours):
    chips = ["🐭 小鼠", "🐟 斑马鱼", "🪰 果蝇", "🧬 质粒", "🧪 试剂", "📓 记录本"]
    return f"""<style>{BASE_CSS}
:root {{ --a:{colours[0]}; --b:{colours[1]}; }}
.logo {{ position:absolute; left:130px; top:180px; width:360px; height:360px; filter: drop-shadow(0 24px 40px rgba(15,138,116,.35)); }}
.logo svg {{ width:100%; height:100%; }}
.t1 {{ position:absolute; left:560px; top:170px; font-size:132px; font-weight:900; line-height:1.12; }}
.t1 em {{ font-style:normal; color:#0f8a74; }}
.t2 {{ position:absolute; left:566px; top:520px; font-size:58px; color:#374151; font-weight:700; }}
.badge {{ position:absolute; right:110px; top:80px; background:#ef4444; color:#fff; font-size:56px; font-weight:900;
  padding:14px 34px; border-radius:20px; transform:rotate(6deg); box-shadow:0 10px 24px rgba(239,68,68,.35); }}
.chips {{ position:absolute; left:130px; right:130px; top:720px; }}
.chip {{ display:inline-block; margin:0 18px 22px 0; padding:16px 30px; border-radius:999px; background:rgba(255,255,255,.9);
  font-size:46px; font-weight:600; box-shadow:0 6px 18px rgba(0,0,0,.08); }}
</style>{blobs()}<div class="badge">永久免费</div><div class="logo">{ICON_SVG}</div>
<div class="t1">实验室管理<br><em>不用再开 20 个 Excel</em></div>
<div class="t2">BioManager 1.0 · 免费开源</div>
<div class="chips">{''.join(f'<span class="chip">{c}</span>' for c in chips)}</div>"""


STEP_JS = """t => { for (const a of document.getAnimations()) { a.pause(); a.currentTime = t * 1000; } }"""


def render_card(page, html, seconds, path: Path):
    page.set_content(f"<!doctype html><html><head><meta charset='utf-8'></head><body>{html}</body></html>")
    page.wait_for_timeout(300)
    proc = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS),
                             "-c:v", "mjpeg", "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                             "-pix_fmt", "yuv420p", "-r", str(FPS), str(path)], stdin=subprocess.PIPE)
    for n in range(int(round(seconds * FPS))):
        page.evaluate(STEP_JS, n / FPS)
        proc.stdin.write(page.screenshot(type="jpeg", quality=92))
    proc.stdin.close()
    proc.wait()


def fit_clip(src: Path, seconds: float, path: Path):
    """The clip's footage in exactly `seconds`: sped up a little if long, its last frame held if short."""
    have = duration(src)
    speed = min(max(have / seconds, 0.85), 1.8)
    hold = max(0.0, seconds - have / speed) + 0.5
    run(FFMPEG, "-y", "-loglevel", "error", "-i", src, "-vf",
        f"setpts=PTS/{speed:.4f},tpad=stop_mode=clone:stop_duration={hold:.2f},fps={FPS},"
        f"trim=duration={seconds:.3f},setpts=PTS-STARTPTS",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", path)


# ---------------------------------------------------------------------------
# Subtitles
# ---------------------------------------------------------------------------

def ass_time(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def chunks(text: str, limit: int = 24) -> list[str]:
    """Split a line at its punctuation into pieces short enough for one subtitle row."""
    parts = re.findall(r"[^，。、：？！；]+[，。、：？！；]?", text)
    out, cur = [], ""
    for p in parts:
        if cur and len(cur) + len(p) > limit:
            out.append(cur)
            cur = p
        else:
            cur += p
    if cur:
        out.append(cur)
    return [c.strip().rstrip("，、；") for c in out if c.strip()]


ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,STHeiti,58,&H00FFFFFF,&H00FFFFFF,&H00271811,&H64271811,0,0,0,0,100,100,1,0,1,4,2,2,80,80,46,1
Style: Tag,STHeiti,36,&H00FFFFFF,&H00FFFFFF,&H00748A0F,&H00748A0F,0,0,0,0,100,100,1,0,3,10,0,7,60,60,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


# ---------------------------------------------------------------------------

def main():
    board = json.loads((ROOT / "promo/explainer.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="explainer-"))
    segments, events, narration, sfx_at, pops_at = [], [], [], [], []
    t = 0.0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H})
        for n, scene in enumerate(board["scenes"]):
            colours = PALETTE[n % len(PALETTE)]
            voices = [speak(line, board["voice"], board["rate"], tmp) for line in scene["lines"]]
            talk = sum(len(v) for v in voices) / SR + GAP * (len(voices) - 1)
            kind = scene["kind"]
            print(f"{n:02d} {kind:5} {scene.get('clip', '')}: {talk:.1f} s of narration", flush=True)
            if kind in ("intro", "outro"):
                # The first line over the opening animation; the rest after it
                # (in the intro, once the name is up).
                first = 0.5 if kind == "intro" else 0.4
                later = 3.6 if kind == "intro" else 0.0
                cursor = t + first
                for i, v in enumerate(voices):
                    at = cursor if i == 0 else max(cursor, t + later)
                    narration.append((at, v))
                    events += subtitle_events(scene["lines"][i], at, len(v) / SR)
                    cursor = at + len(v) / SR + GAP
                length = max(7.6 if kind == "intro" else 7.5, cursor - t + (1.0 if kind == "intro" else 2.0))
                if kind == "intro":
                    html = intro_html(colours)
                    pops_at += [t + 0.3, t + 3.2] + [t + 4.3 + 0.12 * i for i in range(9)]
                else:
                    html = outro_html(colours)
                    pops_at += [t + 0.1] + [t + 2.2 + 0.35 * i for i in range(4)]
                seg = tmp / f"{n:02d}.mp4"
                render_card(page, html, length, seg)
                segments.append(seg)
                sfx_at.append(t)
                t += length
                continue
            # A chapter: its card, then its footage while the lines are read.
            card = tmp / f"{n:02d}-card.mp4"
            render_card(page, chapter_html(colours, scene["number"], scene["title"], scene["subtitle"]), CARD, card)
            sfx_at.append(t)
            pops_at.append(t + 0.4)
            t += CARD
            footage = max(6.0, talk + 1.2)
            clip = tmp / f"{n:02d}-clip.mp4"
            fit_clip(ROOT / "promo/out" / scene["clip"] / "plain.mp4", footage, clip)
            segments += [card, clip]
            events.append(f"Dialogue: 1,{ass_time(t + 0.2)},{ass_time(t + footage - 0.2)},Tag,,0,0,0,,"
                          f"{{\\fad(250,250)}}{scene['number']}  {scene['title']}")
            at = t + 0.35
            for line, v in zip(scene["lines"], voices):
                narration.append((at, v))
                events += subtitle_events(line, at, len(v) / SR)
                at += len(v) / SR + GAP
            t += footage
        cover = OUT / "cover.png"
        page.set_content(f"<!doctype html><html><head><meta charset='utf-8'></head><body>{cover_html(PALETTE[0])}</body></html>")
        page.wait_for_timeout(500)
        page.screenshot(path=str(cover))
        browser.close()
    total = t
    print(f"total {total:.1f} s", flush=True)

    # Pictures: the segments end to end, then the subtitles burned in.
    listing = tmp / "list.txt"
    listing.write_text("".join(f"file '{s}'\n" for s in segments))
    joined = tmp / "joined.mp4"
    run(FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing, "-c", "copy", joined)
    ass = tmp / "subs.ass"
    ass.write_text(ASS_HEAD + "\n".join(events) + "\n")

    # Sound: narration, music ducked under it, and the transitions.
    n_samples = int((total + 0.5) * SR)
    voice = np.zeros(n_samples)
    for at, v in narration:
        place(voice, v.astype(np.float64) * 0.95, at)
    talking = np.convolve((np.abs(voice) > 0.01).astype(float), np.ones(int(0.25 * SR)) / (0.25 * SR), "same")
    duck = 0.30 - 0.20 * np.clip(talking * 4, 0, 1)
    bed = music(n_samples / SR + 0.05)[:n_samples]
    bed = np.pad(bed, ((0, n_samples - len(bed)), (0, 0))) * duck[:, None]
    fx = np.zeros(n_samples)
    for at in sfx_at:
        place(fx, whoosh(), max(0, at - 0.25))
    for i, at in enumerate(pops_at):
        place(fx, pop(660 + 110 * (i % 5)) * 0.6, at)
    mix = bed + (voice + fx)[:, None]
    mix /= max(1e-6, np.abs(mix).max() / 0.9)
    wav = tmp / "mix.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype("<i2").tobytes())

    final = OUT / "explainer.mp4"
    run(FFMPEG, "-y", "-loglevel", "error", "-i", joined, "-i", wav, "-vf",
        f"subtitles={ass}:fontsdir=/System/Library/Fonts", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", final)
    print(final, f"{duration(final):.1f} s")
    print(cover)


def subtitle_events(line, at, seconds):
    parts = chunks(line)
    total = sum(len(p) for p in parts)
    out, cur = [], at
    for part in parts:
        d = seconds * len(part) / total
        out.append(f"Dialogue: 0,{ass_time(cur)},{ass_time(cur + d)},Sub,,0,0,0,,{{\\fad(120,80)}}{part}")
        cur += d
    return out


if __name__ == "__main__":
    sys.exit(main())
