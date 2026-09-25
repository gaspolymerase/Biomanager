"""gunicorn settings for a lab server: gunicorn -c gunicorn.conf.py wsgi:app

Listens on 127.0.0.1 only: put Caddy or nginx in front for HTTPS, and set
BIOMANAGER_PROXY_HOPS=1 so the app sees the real client address and scheme.
"""
import os

bind = os.environ.get("BIOMANAGER_BIND", "127.0.0.1:8000")

# SQLite takes one writer at a time, so one process (with threads) is the
# honest setting for it; PostgreSQL can use more.
_postgres = os.environ.get("DATABASE_URL", "").startswith(("postgres://", "postgresql"))
workers = int(os.environ.get("WEB_CONCURRENCY", "3" if _postgres else "1"))
threads = int(os.environ.get("BIOMANAGER_THREADS", "4"))
timeout = 60

# Load the app once, in the master, before forking: start-up creates tables,
# runs schema updates and seeds the built-in databases, which must not run
# in several workers at the same moment.
preload_app = True

accesslog = "-"
errorlog = "-"


def post_fork(server, worker):
    # Connections opened by the master during start-up must not be shared
    # with the workers; each worker opens its own.
    from app.db import engine
    engine.dispose(close=False)
