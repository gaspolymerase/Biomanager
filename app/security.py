"""What it takes to put BioManager on a network other people can reach.

The app started life on one laptop, where nobody else can send it a
request. On a lab server anyone on the network can, so the decisions about
which requests to trust live here, in one place:

- **The signing key.** Session cookies are signed with SECRET_KEY. Without
  one set, a random key is made once and kept in the data folder (owner-only),
  so no two installs share a key and nobody can forge a login cookie.
- **Cross-site requests.** A change (any POST) is refused when the browser
  says it came from another site: `Sec-Fetch-Site` on modern browsers, the
  `Origin`/`Referer` host otherwise. This is the check Go's net/http ships
  as CrossOriginProtection; it needs no token in every form, so every form
  and every autosave is covered, including ones written later. Requests
  without any of those headers are not from a browser and are let through.
- **Cookies.** HttpOnly, SameSite=Lax, Secure when served over HTTPS, and a
  rolling lifetime. A session is bound to the password it was made with,
  so changing or resetting a password signs out every other session.
- **Uploads.** Only signed-in users can fetch them, and they are served
  so that an uploaded HTML or SVG file cannot run script as the app.
- **Sign-in.** Failed attempts are rate-limited per address and per
  username, and passwords must be at least MIN_PASSWORD_LENGTH characters.
- **The first account.** The first person to register becomes admin, so on
  a server that needs the setup code the server prints at start-up; the
  desktop app, which only listens on this machine, does not ask for it.

Settings, all optional:

  BIOMANAGER_ENV=production     set by wsgi.py; stricter defaults
  BIOMANAGER_HTTPS=1|0          Secure cookies (default: on in production)
  BIOMANAGER_PROXY_HOPS=1       behind nginx/Caddy: trust its X-Forwarded-*
  BIOMANAGER_TRUSTED_ORIGINS    other origins allowed to post, comma separated
  BIOMANAGER_SESSION_DAYS=7     idle days before a sign-in expires
  BIOMANAGER_MAX_UPLOAD_MB=64   largest request body accepted
"""
from __future__ import annotations

import hmac
import logging
import os
import secrets
import threading
import time
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse

from flask import current_app, flash, g, jsonify, redirect, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from .paths import data_dir

log = logging.getLogger("biomanager.security")

DEV_SECRET = "dev-only-change-me"
MIN_SECRET_LENGTH = 32
MIN_PASSWORD_LENGTH = 12
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
UPLOADS_PREFIX = "/static/uploads/"
# Uploads a browser may show in the page; everything else is downloaded.
INLINE_UPLOADS = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp", "application/pdf"}


def production() -> bool:
    return os.environ.get("BIOMANAGER_ENV", "").strip().lower() == "production"


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        raise RuntimeError(f"{name} must be a whole number") from None


def _read_or_create(path: Path, make) -> str:
    """The contents of `path`, creating it (readable by its owner only) on
    first use. Several worker processes may start at once: the file is
    written in full under a temporary name and linked into place, so the
    loser of the race reads the winner's file, never a half-written one."""
    try:
        return path.read_text().strip()
    except FileNotFoundError:
        pass
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(make() + "\n")
    try:
        os.link(tmp, path)
    except FileExistsError:
        pass
    finally:
        tmp.unlink(missing_ok=True)
    return path.read_text().strip()


# ---------------------------------------------------------------- signing key

def secret_key() -> str:
    key = os.environ.get("SECRET_KEY", "").strip()
    if key == DEV_SECRET:
        log.warning("SECRET_KEY is the published development value; ignoring it.")
        key = ""
    if key:
        if production() and len(key) < MIN_SECRET_LENGTH:
            raise RuntimeError(
                f"SECRET_KEY is too short for a shared server (use {MIN_SECRET_LENGTH}+ random "
                "characters: python -c 'import secrets; print(secrets.token_urlsafe(48))'), "
                "or unset it to use the key kept in the data folder.")
        return key
    return _read_or_create(data_dir() / "secret_key", lambda: secrets.token_urlsafe(48))


def session_stamp(user) -> str:
    """Ties a session to the password it was signed in with: the stored hash
    changes with every password change, so older sessions stop matching."""
    return hmac.new(current_app.secret_key.encode(), user.password_hash.encode(), sha256).hexdigest()[:24]


def session_matches(stored: str | None, user) -> bool:
    return bool(stored) and hmac.compare_digest(stored, session_stamp(user))


# ---------------------------------------------------------------- set-up

def init_app(app) -> None:
    """Configure cookies, limits and the request checks. Call after the
    hook that loads g.user, which the uploads check needs."""
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=_flag("BIOMANAGER_HTTPS", production()),
        PERMANENT_SESSION_LIFETIME=timedelta(days=_int("BIOMANAGER_SESSION_DAYS", 7)),
        MAX_CONTENT_LENGTH=_int("BIOMANAGER_MAX_UPLOAD_MB", 64) * 1024 * 1024,
    )
    hops = _int("BIOMANAGER_PROXY_HOPS", 0)
    if hops:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops, x_port=hops)
    app.before_request(refuse_cross_site)
    app.before_request(guard_uploads)
    app.after_request(add_security_headers)
    app.register_error_handler(413, too_large)


# ---------------------------------------------------------------- cross-site requests

def _trusted_hosts() -> set[str]:
    raw = os.environ.get("BIOMANAGER_TRUSTED_ORIGINS", "")
    return {urlparse(o.strip()).netloc or o.strip() for o in raw.split(",") if o.strip()}


def cross_site_reason() -> str | None:
    """Why this request looks like it was sent by another site, or None."""
    if request.method in SAFE_METHODS:
        return None
    origin = request.headers.get("Origin", "")
    if origin and origin != "null" and urlparse(origin).netloc in _trusted_hosts():
        return None
    fetch_site = request.headers.get("Sec-Fetch-Site", "")
    if fetch_site:
        # Only sent to HTTPS (or localhost) origins, and then by every
        # current browser; the header cannot be set by page script.
        return None if fetch_site in {"same-origin", "none"} else f"Sec-Fetch-Site: {fetch_site}"
    if origin:
        if origin != "null" and urlparse(origin).netloc == request.host:
            return None
        return f"Origin: {origin}"
    referer = request.headers.get("Referer", "")
    if referer:
        host = urlparse(referer).netloc
        return None if host == request.host or host in _trusted_hosts() else f"Referer: {referer}"
    return None


def refuse_cross_site():
    reason = cross_site_reason()
    if reason is None:
        return None
    log.warning("refused cross-site %s %s from %s (%s)",
                request.method, request.path, request.remote_addr, reason)
    message = ("This change came from another website, so it was refused. "
               "If you were using BioManager, reload the page and try again.")
    if request.headers.get("X-Autosave") == "1" or request.is_json:
        return jsonify({"ok": False, "error": message}), 403
    return message, 403, {"Content-Type": "text/plain; charset=utf-8"}


# ---------------------------------------------------------------- uploads and headers

def guard_uploads():
    if request.path.startswith(UPLOADS_PREFIX) and g.get("user") is None:
        return redirect(url_for("login", next=request.path))
    return None


def add_security_headers(response):
    headers = response.headers
    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    headers.setdefault("Referrer-Policy", "same-origin")
    if request.is_secure:
        headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    if request.path.startswith(UPLOADS_PREFIX):
        headers["Cache-Control"] = "private, max-age=3600"
        if response.mimetype not in INLINE_UPLOADS:
            headers["Content-Disposition"] = "attachment"
        if response.mimetype != "application/pdf":
            # Should an uploaded page be opened anyway, it runs with no
            # origin: it cannot read the app, its cookies or its data.
            headers["Content-Security-Policy"] = "sandbox; default-src 'none'; img-src 'self'"
    return response


def too_large(_error):
    limit = current_app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
    message = f"That upload is too large. The limit is {limit} MB."
    if request.headers.get("X-Autosave") == "1" or request.is_json:
        return jsonify({"ok": False, "error": message}), 413
    flash(message, "error")
    referrer = request.referrer or ""
    return redirect(referrer if referrer.startswith(request.host_url) else url_for("home_dashboard"))


# ---------------------------------------------------------------- sign-in

def safe_next(target: str | None) -> str | None:
    """`target` if it is a path on this site, else None: a `next=` link
    must not send someone who just signed in to another site."""
    target = (target or "").strip()
    if not target.startswith("/") or target.startswith("//") or "\\" in target:
        return None
    if any(ord(ch) < 0x20 for ch in target):  # browsers drop tabs/newlines: "/\t/evil"
        return None
    parsed = urlparse(target)
    return target if not parsed.scheme and not parsed.netloc else None


def password_problem(password: str, username: str = "") -> str | None:
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Use a password of at least {MIN_PASSWORD_LENGTH} characters."
    if username and password.strip().lower() == username.strip().lower():
        return "Your password cannot be your username."
    return None


_DUMMY_HASH: list[str] = []


def check_password(user, password: str) -> bool:
    """check_password_hash, taking as long for an unknown username as for a
    wrong password, so the timing does not reveal which accounts exist."""
    if user is None:
        if not _DUMMY_HASH:
            _DUMMY_HASH.append(generate_password_hash(secrets.token_hex(16)))
        check_password_hash(_DUMMY_HASH[0], password)
        return False
    return check_password_hash(user.password_hash, password)


class LoginThrottle:
    """At most `limit` failed sign-ins per key in any `window` seconds.

    Kept in memory, so each worker process counts on its own and a restart
    forgets: with N workers someone gets up to N x `limit` guesses per
    window, which still turns a brute-force attack from hours into years."""

    def __init__(self, limit: int = 10, window: int = 15 * 60):
        self.limit = limit
        self.window = window
        self._failures: dict[tuple, list[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key, now: float) -> list[float]:
        stamps = [t for t in self._failures.get(key, ()) if now - t < self.window]
        if stamps:
            self._failures[key] = stamps
        else:
            self._failures.pop(key, None)
        return stamps

    def retry_after(self, *keys) -> int:
        """Seconds until these keys may try again; 0 when they may now."""
        now = time.monotonic()
        with self._lock:
            waits = [int(self.window - (now - stamps[-self.limit])) + 1
                     for stamps in (self._recent(k, now) for k in keys) if len(stamps) >= self.limit]
        return max(waits, default=0)

    def failed(self, *keys) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._failures) > 10_000:  # a scan of many names: drop what has aged out
                for key in list(self._failures):
                    self._recent(key, now)
            for key in keys:
                self._failures.setdefault(key, []).append(now)

    def succeeded(self, *keys) -> None:
        with self._lock:
            for key in keys:
                self._failures.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()


login_throttle = LoginThrottle()


def login_keys(username: str) -> tuple:
    return (("ip", request.remote_addr or ""), ("user", username.strip().lower()))


def https_required_but_missing() -> bool:
    """True when cookies are Secure but this request came over plain HTTP,
    where the browser will silently drop them and sign-in cannot work."""
    return bool(current_app.config.get("SESSION_COOKIE_SECURE")) and not request.is_secure


# ---------------------------------------------------------------- the first account

def _setup_code_path() -> Path:
    return data_dir() / "setup-code"


def setup_code() -> str:
    return _read_or_create(_setup_code_path(),
                           lambda: "-".join(secrets.token_hex(2) for _ in range(3)))


def setup_code_required() -> bool:
    """The desktop app sets LOCAL_SETUP: it listens on 127.0.0.1 only, and
    the person at the keyboard is the only one who can reach it."""
    return not current_app.config.get("LOCAL_SETUP")


def setup_code_matches(entered: str | None) -> bool:
    entered = (entered or "").strip().lower()
    return bool(entered) and hmac.compare_digest(entered, setup_code())


def clear_setup_code() -> None:
    _setup_code_path().unlink(missing_ok=True)


def announce_setup_code(logger) -> None:
    """Print the code needed to create the first (admin) account."""
    code = setup_code()
    logger.warning("No accounts yet. Create the first admin at /register with setup code %s "
                   "(also saved in %s).", code, _setup_code_path())
