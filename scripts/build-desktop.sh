#!/usr/bin/env bash
# Build the BioManager desktop .app.
#
# Run once after pulling changes that touch the frontend or any Python file.
# Output: dist/BioManager.app (macOS) / dist/BioManager/ (Win/Linux).

set -euo pipefail

cd "$(dirname "$0")/.."

# 1. Ensure the notebook editor bundle is built. The .app embeds whatever is
#    in app/static/notebook-build/ at build time.
if [ ! -f app/static/notebook-build/notebook-app.js ]; then
  echo "Notebook bundle missing — running 'npm install && npm run build'..."
  (cd frontend && npm install && npm run build)
fi

# 1b. Always rebuild the Tailwind stylesheet. It is compiled from the
#     templates, so a stale app/static/tailwind.css would ship a .app whose
#     classes no longer match the markup.
echo "Building app/static/tailwind.css..."
if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm install)
fi
(cd frontend && npm run build:css)

# 2. Make sure desktop deps are installed in the active interpreter.
python -m pip install --quiet pywebview pyinstaller

# 3. Clean previous build artifacts, then run PyInstaller.
rm -rf build dist
pyinstaller Biomanager.spec --clean --noconfirm

echo
echo "Done. Open dist/BioManager.app to launch."
