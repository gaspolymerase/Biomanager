"""The app icon and the accent colour that goes with it.

Each person picks a picture (the double helix, a mouse, a zebrafish…) and one
of six macaron colours in Settings. The picture is drawn here as SVG on
Apple's macOS icon grid: a 1024 canvas with the rounded square inset to
824 × 824 and a 185.4 corner radius. The style is Apple's: one white subject
lit from above, frosted-glass layers for depth, and details in a deeper shade
of the background rather than a second colour.

The colour also becomes the app's accent (`--color-brand-*`), so buttons,
links and selections match the icon. Mint is the default and matches the
accent that tailwind.css ships with, so it needs no override.

The choice is kept in app_settings as "app_icon:<username>" = "glyph/color",
like the home layout, so it follows the person and needs no schema change.

`scripts/build-app-icon.py` renders the default (helix, mint) to the static
icon, the PWA and touch PNGs, the desktop app and the Android launcher.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from functools import lru_cache

from . import inventory_service

DEFAULT_GLYPH = "helix"
DEFAULT_COLOR = "mint"


# ---------------------------------------------------------------- colours

def _hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02X}" for c in rgb)


def _rgb(hex_: str):
    hex_ = hex_.lstrip("#")
    return tuple(int(hex_[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a: str, b: str, t: float) -> str:
    """`a` moved `t` of the way towards `b`."""
    ra, rb = _rgb(a), _rgb(b)
    return _hex(x + (y - x) * t for x, y in zip(ra, rb))


def _light_ramp(base: str) -> dict[str, str]:
    white, black = "#FFFFFF", "#000000"
    return {
        "50": _mix(white, base, 0.09), "100": _mix(white, base, 0.20),
        "200": _mix(white, base, 0.38), "300": _mix(white, base, 0.58),
        "400": _mix(white, base, 0.78), "500": _mix(white, base, 0.92),
        "600": base,
        "700": _mix(base, black, 0.18), "800": _mix(base, black, 0.35),
        "900": _mix(base, black, 0.50), "950": _mix(base, black, 0.68),
    }


def _dark_ramp(base: str) -> dict[str, str]:
    # Mirrors the dark-mode overrides in tailwind.css: a brighter accent, and
    # tinted fills that sit on the dark grey rather than glowing.
    ground, white = "#1C1C1E", "#FFFFFF"
    return {
        "600": _mix(base, white, 0.18), "700": _mix(base, white, 0.06),
        "50": _mix(ground, base, 0.17), "100": _mix(ground, base, 0.23),
        "200": _mix(ground, base, 0.36),
        "800": _mix(base, white, 0.40), "900": _mix(base, white, 0.60),
    }


@dataclass(frozen=True)
class Palette:
    label: str
    top: str      # icon background, top of the gradient
    bottom: str   # icon background, bottom
    deep: str     # details drawn on the white subject
    shade: str    # colour of the shadows
    accent: str   # the app's brand-600 in light mode


PALETTES: dict[str, Palette] = {
    "mint":     Palette("Mint",     "#3FD6BC", "#0B8C7E", "#0A7C70", "#03453E", "#17A38F"),
    "rose":     Palette("Rose",     "#FFA6C1", "#E0527F", "#C23A68", "#5C0F2A", "#DC4478"),
    "lavender": Palette("Lavender", "#C4AEFF", "#7B5CE0", "#6446D0", "#241060", "#7457DB"),
    "sky":      Palette("Sky",      "#94D7FF", "#2F86E0", "#2170C8", "#0A2C5E", "#2A7FDB"),
    "lemon":    Palette("Lemon",    "#FFDD73", "#EBA313", "#C98200", "#5C3A00", "#B97A00"),
    "peach":    Palette("Peach",    "#FFC19C", "#EE7446", "#D65A2C", "#5E220A", "#DC5F2D"),
}

# What tailwind.css already ships; mint must not override it.
_SHIPPED = PALETTES[DEFAULT_COLOR].accent


def brand_css(color: str) -> str:
    """CSS that retints the app to match `color`; empty for the default."""
    pal = PALETTES.get(color)
    if pal is None or pal.accent == _SHIPPED:
        return ""
    light = "".join(f"--color-brand-{k}:{v};" for k, v in _light_ramp(pal.accent).items())
    dark = "".join(f"--color-brand-{k}:{v};" for k, v in _dark_ramp(pal.accent).items())
    return (f":root{{{light}}}"
            f"@media (prefers-color-scheme: dark){{:root:not([data-theme=\"light\"]){{{dark}}}}}"
            f":root[data-theme=\"dark\"]{{{dark}}}")


# ---------------------------------------------------------------- drawing

def _f(x: float) -> str:
    return f"{x:.1f}"


def _defs(pal: Palette) -> str:
    return f'''<linearGradient id="bm-bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{pal.top}"/><stop offset="1" stop-color="{pal.bottom}"/>
    </linearGradient>
    <radialGradient id="bm-light" cx="0.5" cy="0" r="0.9">
      <stop offset="0" stop-color="#fff" stop-opacity="0.28"/>
      <stop offset="1" stop-color="#fff" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="bm-white" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#EEF2F6"/>
    </linearGradient>
    <linearGradient id="bm-glass" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#fff" stop-opacity="0.50"/>
      <stop offset="1" stop-color="#fff" stop-opacity="0.16"/>
    </linearGradient>
    <linearGradient id="bm-rim" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#fff" stop-opacity="0.95"/>
      <stop offset="0.5" stop-color="#fff" stop-opacity="0.25"/>
      <stop offset="1" stop-color="#fff" stop-opacity="0.55"/>
    </linearGradient>
    <linearGradient id="bm-deep" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{_mix(pal.deep, pal.top, 0.35)}"/><stop offset="1" stop-color="{pal.deep}"/>
    </linearGradient>
    <filter id="bm-drop" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="14" stdDeviation="18" flood-color="{pal.shade}" flood-opacity="0.30"/>
    </filter>
    <filter id="bm-soft" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="0" dy="18" stdDeviation="22" flood-color="{pal.shade}" flood-opacity="0.30"/>
    </filter>'''


def _helix(pal: Palette) -> tuple[str, str]:
    """Two strands: white where a strand is in front, glass where behind."""
    amp, y0, y1, n = 118, 262, 762, 240
    phi0, phi1 = -math.pi / 2, 2.5 * math.pi

    def runs(phase: float):
        front, back, cur, cur_front = [], [], [], None
        for i in range(n + 1):
            t = i / n
            phi = phi0 + (phi1 - phi0) * t
            x, y = 512 + amp * math.sin(phi + phase), y0 + (y1 - y0) * t
            is_front = math.cos(phi + phase) >= 0
            if cur_front is None:
                cur_front = is_front
            if is_front != cur_front:
                cur.append((x, y))
                (front if cur_front else back).append(cur)
                cur, cur_front = [(x, y)], is_front
            cur.append((x, y))
        (front if cur_front else back).append(cur)
        return front, back

    def d(pts):
        return "M" + " L".join(f"{_f(x)} {_f(y)}" for x, y in pts)

    fa, ba = runs(0)
    fb, bb = runs(math.pi)
    back = "".join(f'<path d="{d(r)}"/>' for r in ba + bb if len(r) > 4)
    front = "".join(f'<path d="{d(r)}"/>' for r in fa + fb if len(r) > 4)
    return f'''<g fill="none" stroke-linecap="round" stroke-linejoin="round">
    <g stroke="#fff" stroke-opacity="0.38" stroke-width="54">{back}</g>
    <g filter="url(#bm-soft)" stroke="url(#bm-white)" stroke-width="66">{front}</g>
  </g>''', ""


def _mouse(pal: Palette) -> tuple[str, str]:
    body = ("M772 590 C762 538 704 486 632 468 C562 418 424 410 342 470 "
            "C282 514 270 610 322 652 C362 684 424 690 474 688 L690 670 "
            "C742 662 782 632 772 590 Z")
    return f'''<g transform="translate(512 512) scale(1.12) translate(-492 -576)">
    <path d="M326 648 C246 694 214 770 282 796 C338 816 394 786 430 756" fill="none" stroke="#fff" stroke-opacity="0.55" stroke-width="20" stroke-linecap="round"/>
    <g filter="url(#bm-soft)">
      <path d="{body}" fill="url(#bm-white)"/>
      <circle cx="598" cy="428" r="76" fill="url(#bm-white)"/>
    </g>
    <circle cx="602" cy="432" r="46" fill="#FFC2CC"/>
    <circle cx="700" cy="540" r="15" fill="#2C2226"/>
    <circle cx="770" cy="584" r="13" fill="#FF8FA3"/>
  </g>''', ""


def _zebrafish(pal: Palette) -> tuple[str, str]:
    body = ("M776 506 C748 438 626 414 506 420 C420 425 350 452 304 484 "
            "C286 464 262 428 230 410 C248 450 256 484 262 512 C256 540 248 574 230 614 "
            "C262 596 286 560 304 540 C350 572 420 600 506 604 C626 610 748 586 776 518 "
            "Q782 512 776 506 Z")
    extra = f'<clipPath id="bm-fish"><path d="{body}"/></clipPath>'
    stripes = "".join(
        f'<path d="M230 {y} C400 {y - 10} 560 {y + 10} 740 {y - 4}"/>' for y in (470, 512, 554))
    return f'''<g transform="translate(512 512) scale(1.14) translate(-506 -512)">
    <g filter="url(#bm-soft)">
      <path d="M440 428 Q490 352 566 422 Z" fill="url(#bm-white)"/>
      <path d="M458 598 Q510 662 576 600 Z" fill="url(#bm-white)"/>
      <path d="{body}" fill="url(#bm-white)"/>
    </g>
    <g clip-path="url(#bm-fish)" fill="none" stroke="url(#bm-deep)" stroke-width="17" stroke-linecap="round" stroke-opacity="0.9">{stripes}</g>
    <circle cx="714" cy="496" r="19" fill="#1F2330"/>
    <circle cx="720" cy="490" r="6" fill="#fff"/>
  </g>''', extra


def _worm(pal: Palette) -> tuple[str, str]:
    """C. elegans: a sinuous body, a pointed tail, the pharynx near the head."""
    (ax, ay), (bx, by) = (286, 716), (712, 352)
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    width, amp, n = 48, 70, 160

    def centre(t: float):
        off = amp * math.sin(2 * math.pi * 1.2 * t - 0.5)
        return ax + dx * t + nx * off, ay + dy * t + ny * off

    def half(t: float) -> float:
        tail = min(1.0, t / 0.42) ** 0.9
        return max(3.0, width * tail)

    left, right = [], []
    for i in range(n + 1):
        t = i / n
        x, y = centre(t)
        x2, y2 = centre(min(1, t + 1e-3)) if t < 1 else centre(t)
        x1, y1 = centre(max(0, t - 1e-3))
        tx, ty = x2 - x1, y2 - y1
        tl = math.hypot(tx, ty) or 1
        px, py = -ty / tl, tx / tl
        w = half(t)
        left.append((x + px * w, y + py * w))
        right.append((x - px * w, y - py * w))
    hx, hy = centre(1)
    outline = ("M" + " L".join(f"{_f(x)} {_f(y)}" for x, y in left) + " L"
               + " L".join(f"{_f(x)} {_f(y)}" for x, y in reversed(right)) + " Z")
    gut = "M" + " L".join(f"{_f(x)} {_f(y)}" for x, y in (centre(i / 60) for i in range(12, 50)))
    px_, py_ = centre(0.9)
    return f'''<g filter="url(#bm-soft)"><path d="{outline}" fill="url(#bm-white)"/><circle cx="{_f(hx)}" cy="{_f(hy)}" r="{width}" fill="url(#bm-white)"/></g>
  <path d="{gut}" fill="none" stroke="url(#bm-deep)" stroke-opacity="0.35" stroke-width="12" stroke-linecap="round"/>
  <circle cx="{_f(px_)}" cy="{_f(py_)}" r="20" fill="url(#bm-deep)" fill-opacity="0.75"/>''', ""


def _fly(pal: Palette) -> tuple[str, str]:
    """Drosophila from above: red eyes, a banded abdomen, glass wings at rest."""
    extra = '<clipPath id="bm-abdomen"><ellipse cx="512" cy="600" rx="80" ry="138"/></clipPath>'
    wing = ('<ellipse cx="{cx}" cy="628" rx="70" ry="186" transform="rotate({r} {cx} 628)" '
            'fill="url(#bm-glass)" stroke="url(#bm-rim)" stroke-width="4"/>')
    return f'''<g transform="translate(512 512) scale(1.1) translate(-512 -500)"><g filter="url(#bm-soft)">
    <ellipse cx="512" cy="600" rx="80" ry="138" fill="url(#bm-white)"/>
    <ellipse cx="512" cy="436" rx="94" ry="84" fill="url(#bm-white)"/>
    <circle cx="512" cy="326" r="60" fill="url(#bm-white)"/>
  </g>
  <g clip-path="url(#bm-abdomen)" fill="url(#bm-deep)" fill-opacity="0.85">
    <rect x="400" y="566" width="224" height="24"/><rect x="400" y="618" width="224" height="24"/>
    <rect x="400" y="670" width="224" height="24"/>
  </g>
  <ellipse cx="466" cy="316" rx="30" ry="38" fill="#E5484D"/>
  <ellipse cx="558" cy="316" rx="30" ry="38" fill="#E5484D"/>
  {wing.format(cx=630, r=-26)}
  {wing.format(cx=394, r=26)}</g>''', extra


def _cryobox(pal: Palette) -> tuple[str, str]:
    step, r = 150, 52
    caps = []
    for row in range(3):
        for col in range(3):
            cx, cy = 512 + (col - 1) * step, 512 + (row - 1) * step
            if (row, col) == (1, 2):
                caps.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#bm-deep)"/>'
                            f'<circle cx="{cx}" cy="{cy}" r="22" fill="#fff" fill-opacity="0.35"/>')
            else:
                caps.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#bm-white)"/>'
                            f'<circle cx="{cx}" cy="{cy}" r="22" fill="#DDE6F0"/>')
    return f'''<rect x="262" y="262" width="500" height="500" rx="96" fill="url(#bm-glass)"/>
  <rect x="262" y="262" width="500" height="500" rx="96" fill="none" stroke="url(#bm-rim)" stroke-width="4"/>
  <g filter="url(#bm-soft)">{"".join(caps)}</g>''', ""


def _microtube(pal: Palette) -> tuple[str, str]:
    tube = ("M-104 -214 L-104 40 C-104 100 -30 296 -14 322 Q0 342 14 322 "
            "C30 296 104 100 104 40 L104 -214 Z")
    extra = f'<clipPath id="bm-tube"><path d="{tube}"/></clipPath>'
    return f'''<g transform="translate(512 548) rotate(-14)">
    <g filter="url(#bm-soft)">
      <path d="{tube}" fill="url(#bm-glass)"/>
      <g clip-path="url(#bm-tube)">
        <path d="M-120 60 Q0 84 120 60 L120 400 L-120 400 Z" fill="url(#bm-deep)"/>
      </g>
    </g>
    <path d="{tube}" fill="none" stroke="url(#bm-rim)" stroke-width="4"/>
    <rect x="-66" y="-196" width="18" height="206" rx="9" fill="#fff" fill-opacity="0.45"/>
    <g filter="url(#bm-soft)">
      <rect x="-128" y="-262" width="256" height="56" rx="20" fill="url(#bm-white)"/>
      <rect x="-114" y="-326" width="228" height="58" rx="22" fill="url(#bm-white)"/>
    </g>
  </g>''', extra


def _petri(pal: Palette) -> tuple[str, str]:
    colonies = [(438, 452, 46), (596, 418, 26), (604, 602, 36), (470, 610, 16)]
    cols = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="url(#bm-deep)"/>'
                   f'<circle cx="{x - r * 0.25:.0f}" cy="{y - r * 0.3:.0f}" r="{r * 0.35:.0f}" fill="#fff" fill-opacity="0.35"/>'
                   for x, y, r in colonies)
    return f'''<g filter="url(#bm-soft)">
    <circle cx="512" cy="512" r="300" fill="url(#bm-glass)"/>
    <circle cx="512" cy="512" r="262" fill="url(#bm-white)"/>
  </g>
  <circle cx="512" cy="512" r="299" fill="none" stroke="url(#bm-rim)" stroke-width="4"/>
  {cols}
  <path d="M300 372 A262 262 0 0 1 410 270" fill="none" stroke="#fff" stroke-opacity="0.8" stroke-width="12" stroke-linecap="round"/>''', ""


GLYPHS = {
    "helix": ("Helix", _helix),
    "mouse": ("Mouse", _mouse),
    "zebrafish": ("Zebrafish", _zebrafish),
    "worm": ("C. elegans", _worm),
    "fly": ("Drosophila", _fly),
    "cryobox": ("Cryobox", _cryobox),
    "microtube": ("Microtube", _microtube),
    "petri": ("Petri dish", _petri),
}

# How much to enlarge the subject when there is no rounded square around it
# (a phone rounds or masks the full-bleed square itself).
_FULL_SCALE = 1.2


@lru_cache(maxsize=None)
def render(glyph: str, color: str, variant: str = "app") -> str:
    """The icon as SVG.

    variant: "app" (the rounded square with its shadow), "full" (edge to edge,
    for touch and maskable icons), "glyph" (the subject alone on transparent,
    Android's adaptive foreground) or "background" (the colour alone).
    """
    glyph = glyph if glyph in GLYPHS else DEFAULT_GLYPH
    pal = PALETTES.get(color) or PALETTES[DEFAULT_COLOR]
    body, extra = GLYPHS[glyph][1](pal)
    if variant == "full":
        ground = '<rect width="1024" height="1024" fill="url(#bm-bg)"/><rect width="1024" height="1024" fill="url(#bm-light)"/>'
        body = f'<g transform="translate(512 512) scale({_FULL_SCALE}) translate(-512 -512)">{body}</g>'
    elif variant == "background":
        ground = '<rect width="1024" height="1024" fill="url(#bm-bg)"/><rect width="1024" height="1024" fill="url(#bm-light)"/>'
        body = ""
    elif variant == "glyph":
        ground = ""
    else:
        ground = ('<g filter="url(#bm-drop)"><rect x="100" y="100" width="824" height="824" rx="185.4" fill="url(#bm-bg)"/></g>'
                  '<rect x="100" y="100" width="824" height="824" rx="185.4" fill="url(#bm-light)"/>')
        body += ('<rect x="102" y="102" width="820" height="820" rx="184" fill="none" '
                 'stroke="#fff" stroke-opacity="0.16" stroke-width="2"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="1024" height="1024">'
            f'<title>BioManager</title><defs>{_defs(pal)}{extra}</defs>{ground}{body}</svg>\n')


@lru_cache(maxsize=None)
def version(glyph: str, color: str) -> str:
    """Changes whenever the drawing does, so a cached icon is never stale."""
    return hashlib.sha1(render(glyph, color).encode()).hexdigest()[:10]


# ---------------------------------------------------------------- the choice

def _key(username: str) -> str:
    return f"app_icon:{username}"


def parse(value: str) -> tuple[str, str]:
    glyph, _, color = (value or "").partition("/")
    return (glyph if glyph in GLYPHS else DEFAULT_GLYPH,
            color if color in PALETTES else DEFAULT_COLOR)


def get_choice(session, username: str) -> tuple[str, str]:
    return parse(inventory_service.get_setting(session, _key(username), ""))


def set_choice(session, username: str, glyph: str, color: str) -> tuple[str, str]:
    glyph, color = parse(f"{glyph}/{color}")
    inventory_service.set_setting(session, _key(username), f"{glyph}/{color}")
    return glyph, color


def is_default(glyph: str, color: str) -> bool:
    return (glyph, color) == (DEFAULT_GLYPH, DEFAULT_COLOR)
