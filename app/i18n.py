"""Languages: BioManager in English or Simplified Chinese.

Text is written in English in the code and the templates, wrapped so it can
be translated: `_("Litter born")` in Python and templates,
`{% trans %}…{% endtrans %}` for a template sentence with values in it, and
`t("…")` in page scripts. The Chinese is in `app/translations/zh/*.json`, one
file per area of the app (`"English": "中文"`; page scripts' words in the
`js*.json` files, which are also sent to the browser); text with no entry
stays English. `docs/i18n-glossary.md` lists the words the translations use.

Which language a page is in: the person's choice in Settings (Language), or,
when they have not chosen (and before signing in), the language their
browser or computer asks for first. `session["lang"]` keeps the choice made
for this browser.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from flask import g, has_request_context, request, session

LANGUAGES = {"en": "English", "zh": "中文"}
DEFAULT = "en"
TRANSLATIONS = Path(__file__).resolve().parent / "translations"

_catalogs: dict[str, dict[str, str]] = {}


def catalog(lang: str) -> dict[str, str]:
    """Every translation for `lang`, from all its files (read once)."""
    if lang not in _catalogs:
        merged: dict[str, str] = {}
        folder = TRANSLATIONS / lang
        for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            merged.update({k: v for k, v in json.loads(path.read_text(encoding="utf-8")).items() if v})
        _catalogs[lang] = merged
    return _catalogs[lang]


def current() -> str:
    """The language of the page being made (English outside a request)."""
    if not has_request_context():
        return DEFAULT
    lang = g.get("lang")
    if lang is None:
        lang = g.lang = choose()
    return lang


def from_header(header: str | None) -> str:
    """The first supported language an Accept-Language header asks for."""
    ranked = []
    for i, part in enumerate((header or "").split(",")):
        tag, _, q = part.strip().partition(";q=")
        try:
            weight = float(q) if q else 1.0
        except ValueError:
            weight = 0.0
        ranked.append((-weight, i, tag.strip().lower()))
    for _w, _i, tag in sorted(ranked):
        base = tag.split("-")[0]
        if base in LANGUAGES:
            return base
    return DEFAULT


def choose() -> str:
    """This browser's language: a choice already made, else what it asks for."""
    chosen = session.get("lang")
    if chosen in LANGUAGES:
        return chosen
    return from_header(request.headers.get("Accept-Language"))


def preference_key(username: str) -> str:
    return f"language.{username}"


def preference(db_session, username: str) -> str:
    """A person's choice in Settings: "en", "zh", or "" (follow the browser)."""
    from . import inventory_service
    value = inventory_service.get_setting(db_session, preference_key(username), "")
    return value if value in LANGUAGES else ""


def set_preference(db_session, username: str, lang: str) -> str:
    from . import inventory_service
    lang = lang if lang in LANGUAGES else ""
    inventory_service.set_setting(db_session, preference_key(username), lang)
    remember(lang)
    return lang


def remember(lang: str) -> None:
    """Use `lang` in this browser from now on ("" = follow the browser)."""
    if lang in LANGUAGES:
        session["lang"] = lang
    else:
        session.pop("lang", None)
    g.lang = choose()


def gettext(message: str, **values) -> str:
    text = catalog(current()).get(message, message) if current() != DEFAULT else message
    return text % values if values else text


def ngettext(singular: str, plural: str, n: int, **values) -> str:
    values.setdefault("num", n)
    if current() != DEFAULT:
        text = catalog(current()).get(singular if n == 1 else plural) or catalog(current()).get(plural)
        if text:
            return text % values
    return (singular if n == 1 else plural) % values


_ = gettext


def js_catalog() -> dict[str, str]:
    """The translations page scripts use (`t("…")`), for the page's language."""
    if current() == DEFAULT:
        return {}
    words: dict[str, str] = {}
    for path in sorted((TRANSLATIONS / current()).glob("js*.json")):
        words.update({k: v for k, v in json.loads(path.read_text(encoding="utf-8")).items() if v})
    return words


_PLACEHOLDER = re.compile(r"%\((\w+)\)[sd]")


def placeholders(text: str) -> set[str]:
    """The %(name)s values a message carries (a translation must keep them)."""
    return set(_PLACEHOLDER.findall(text))


def translate_value(value) -> str:
    """`{{ label|tr }}`: a label that arrives as a value (from Python, or a
    built-in name a lab may have renamed) in the page's language. The text
    of a known label gets its translation; anything else — what a lab typed —
    comes back unchanged. Plain text, so the template still escapes it, and no
    %-formatting, so "GC %" is safe. (`_(value)` would do neither.)"""
    if value is None:
        return ""
    text = str(value)
    if current() == DEFAULT:
        return text
    return catalog(current()).get(text, text)


def init_app(app) -> None:
    app.jinja_env.filters["tr"] = translate_value
    app.jinja_env.add_extension("jinja2.ext.i18n")
    app.jinja_env.install_gettext_callables(gettext, ngettext, newstyle=True)
    app.jinja_env.globals.update(languages=LANGUAGES, current_language=current, js_catalog=js_catalog)
