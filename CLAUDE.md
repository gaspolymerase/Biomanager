# BioManager: notes for Claude

How the app is built and tested is in `docs/DEVELOPMENT.md`; running a lab
server is in `deploy/RUNBOOK.md`.

## Changing the database's shape

Never add a column or table by hand-written ALTER at start-up any more
(`services.ensure_schema_updates` is frozen at 0.8). Make an Alembic
revision after the newest in `migrations/versions/`, using
`migrations/helpers.py` so it also runs where the change already exists,
and run `python scripts/upgrade-check.py` before a release: every earlier
release's database must still open with nothing lost.

## The docs follow the app

A change people will see or use is not finished until the pages that describe
it say so. In the same piece of work, update:

| Where | What it covers |
| --- | --- |
| `README.md` (this repo) | What each database and function does, features across the app, accounts, data and backups |
| `site/index.html` | The website's front page: the tour of each database, the feature cards, downloads |
| `site/guide.html` | The user guide: one section per area (a sheet, finding things, each database, calendar, notebook, working as a lab, phones, data) |
| `site/server.html`, `deploy-with-ai.md`, `llms.txt` | Only when running a server, deploying or the downloads change |
| `docs/DEVELOPMENT.md` | Internals: tables, modules, how things fit together |

The website is `site/`, served by GitHub Pages at
gaspolymerase.github.io/biomanager: pushing a change under `site/` to master
publishes it within a minute (`.github/workflows/pages.yml`), so push the
site with the app change it describes, never ahead of it. The old
gaspolymerase/biomanager-app repository only redirects there, and keeps a
copy of each release for desktop apps from before the move.

- Write for the people in the lab: what it does for them and where to find it,
  in plain words, as the surrounding text does. Name buttons as the app does.
- Put a change where a reader would look for it; don't add a "what's new"
  list. Fix text the change made wrong (a removed button, a renamed tab).
- Before publishing the website, check the edited pages still parse (every
  list and section closed).
- When a change alters a page that has a screenshot, retake the screenshots
  from a fresh demo lab (`scripts/demo-data.py`, then `scripts/screenshots.py`)
  and copy them to `docs/screenshots/` and `site/assets/screenshots/`.
- Internal changes with nothing to see (a refactor, a test, a fix that restores
  documented behaviour) need no docs.
