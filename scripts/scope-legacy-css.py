#!/usr/bin/env python3
"""Generate app/static/legacy.css from app/static/styles.css.

Transitional tooling for the Tailwind migration. Pages that have not been
converted yet still need their old styling, but the old stylesheet also
contains global element rules (`body`, `nav a`, `table`, …) and the old app
chrome, which would fight the new Tailwind shell.

So every remaining selector is scoped under `.legacy-page` — the class
base.html puts on the content wrapper when a template sets
`{% block legacy %}1{% endblock %}`. Rules for the retired chrome, and for
components the new design system already owns, are dropped entirely.

Delete this script (and legacy.css) once the last template is migrated.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SCOPE = ".legacy-page"

# Selectors for the old shell, and for components now owned by the Tailwind
# design system. Dropping these lets unmigrated pages pick up the new look
# for shared furniture (tables, dialogs, badges, flashes).
DROP_PREFIXES = (
    ".app-shell", ".app-sidebar", ".app-topbar", ".app-tabbar", ".app-tab",
    ".app-main", ".sidebar-", ".brand-mark", ".site-header", ".user-chip",
    ".page-shell", ".owner-badge", ".owner-cell", ".cmdk-", ".dt-",
    ".data-table-card", ".flash-", ".auth-shell", ".auth-card",
    ".dash-", ".settings-", ".admin-users-", ".role-pill", ".page-table-header",
    ".page-subtitle",
    # Buttons are owned by the new design system everywhere, so that an
    # unmigrated page does not mix old blue fills with the new styling.
    ".btn", ".ghost-button", ".button-link", ".danger-button", ".modal-topbar",
    ".modal-close",
)

# Generic button rules from the old sheet, matched anywhere in the selector.
DROP_CONTAINS = ("button:not(",)

# Bare element rules for form controls. `.legacy-page button` out-specifies
# `.btn`, so leaving these in repaints every button on an unmigrated page
# with the old accent colour. Controls are owned by the design system now.
DROP_BARE_ELEMENTS = re.compile(
    r"^(button|input|select|textarea|fieldset|legend)"
    r"(\[[^\]]*\])?(:[a-z-]+(\([^)]*\))?)*$")
DROP_EXACT = {"html", "body", "*", "a", "a:hover", "nav", "nav a", "nav a:hover",
              "p, small", "small", "p", "h1", "h2", "h3", "h4", "h1, h2, h3, h4"}


def scope_selector(selector: str) -> str | None:
    selector = selector.strip()
    if not selector:
        return None

    # The old content wrapper becomes the new scope class.
    selector = selector.replace(".app-content", SCOPE)

    parts = []
    for part in selector.split(","):
        part = part.strip()
        if not part or part in DROP_EXACT:
            continue
        if part.startswith(DROP_PREFIXES):
            continue
        if any(token in part for token in DROP_CONTAINS):
            continue
        if DROP_BARE_ELEMENTS.match(part):
            continue
        if part.startswith(":root"):
            parts.append(part.replace(":root", SCOPE, 1))
            continue
        if SCOPE in part:
            parts.append(part)
            continue
        # `::selection` and friends need the scope ahead of the element.
        parts.append(f"{SCOPE} {part}")
    return ", ".join(parts) if parts else None


def transform(css: str) -> str:
    out: list[str] = []
    i = 0
    length = len(css)

    def read_block(start: int) -> tuple[str, int]:
        """Return the {...} body starting at `start` (which is the '{')."""
        depth = 0
        j = start
        while j < length:
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
                if depth == 0:
                    return css[start + 1 : j], j + 1
            j += 1
        return css[start + 1 :], length

    while i < length:
        brace = css.find("{", i)
        if brace == -1:
            break
        prelude = css[i:brace]
        # Strip comments from the prelude but keep them out of the output.
        prelude_clean = re.sub(r"/\*.*?\*/", "", prelude, flags=re.S).strip()
        body, after = read_block(brace)

        if prelude_clean.startswith("@keyframes") or prelude_clean.startswith("@font-face"):
            out.append(f"{prelude_clean}{{{body}}}\n")
        elif prelude_clean.startswith("@media") or prelude_clean.startswith("@supports"):
            inner = transform(body)
            if inner.strip():
                out.append(f"{prelude_clean}{{\n{inner}}}\n")
        elif prelude_clean.startswith("@"):
            # @import / @charset and friends: not meaningful here.
            pass
        else:
            scoped = scope_selector(prelude_clean)
            if scoped and body.strip():
                out.append(f"{scoped}{{{body}}}\n")
        i = after

    return "".join(out)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    source = root / "app" / "static" / "styles.css"
    target = root / "app" / "static" / "legacy.css"
    if not source.exists():
        print(f"missing {source}", file=sys.stderr)
        return 1

    header = (
        "/* GENERATED FILE — do not edit.\n"
        "   Built by scripts/scope-legacy-css.py from styles.css. Every rule is\n"
        "   scoped under .legacy-page so the old styling only reaches templates\n"
        "   that have not been migrated to Tailwind yet. */\n"
    )
    target.write_text(header + transform(source.read_text()))
    print(f"wrote {target.relative_to(root)} ({target.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
