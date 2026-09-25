"""Production entry point, for a server other people connect to:

    gunicorn -c gunicorn.conf.py wsgi:app

Sets BIOMANAGER_ENV=production, which makes app/security.py strict: Secure
cookies (the server must be reached over HTTPS, or set BIOMANAGER_HTTPS=0),
and a SECRET_KEY, if one is given, must be long enough to be a real key.
"""
import os

os.environ.setdefault("BIOMANAGER_ENV", "production")

from app.app import app  # noqa: E402

if app.debug:
    raise RuntimeError("Debug mode is on (FLASK_DEBUG?). It must be off on a shared server.")
