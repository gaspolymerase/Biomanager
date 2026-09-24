import os

from app.app import app


if __name__ == "__main__":
    # macOS reserves port 5000 for AirPlay/ControlCenter, so allow an override.
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "1") == "1",
    )
