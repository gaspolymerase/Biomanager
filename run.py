"""Development server. For a lab server use gunicorn (see wsgi.py).

    python run.py                 # http://127.0.0.1:5000
    FLASK_DEBUG=1 python run.py   # reload on edit, tracebacks in the browser
"""
import os
import sys

from app.app import app


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    # The debugger runs any Python typed into an error page: on an address
    # other machines can reach, that is a shell on this machine for anyone.
    if debug and host not in {"127.0.0.1", "localhost", "::1"}:
        sys.exit(f"Refusing to start the debugger on {host}. To share BioManager on a network, "
                 "run it with gunicorn (gunicorn -c gunicorn.conf.py wsgi:app); see the README.")
    # macOS reserves port 5000 for AirPlay/ControlCenter, so allow an override.
    app.run(host=host, port=int(os.environ.get("PORT", "5000")), debug=debug)
