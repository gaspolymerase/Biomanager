# BioManager: notes for Claude

How the app is built and tested is in `docs/DEVELOPMENT.md`; running a lab
server is in `deploy/RUNBOOK.md`.

`deploy/` goes to every lab in the public server bundle, so it names no one
lab's server: our own (its VM, tailnet, Mac and off-site storage) is in
`docs/OUR-SERVER.md`, which is not bundled. A change to one runbook usually
belongs in the other too.

## Changing the database's shape

Never add a column or table by hand-written ALTER at start-up any more
(`services.ensure_schema_updates` is frozen at 0.8). Make an Alembic
revision after the newest in `migrations/versions/`, using
`migrations/helpers.py` so it also runs where the change already exists,
and run `python scripts/upgrade-check.py` before a release (and with
`--postgres <url>` for lab servers; CI runs both): every earlier release's
database must still open with nothing lost.

## The docs follow the app

A change people will see or use is not finished until the pages that describe
it say so. In the same piece of work, update:

| Where | What it covers |
| --- | --- |
| `README.md` (this repo) | What each database and function does, features across the app, accounts, data and backups |
| `index.html` in [gaspolymerase/biomanager-app](https://github.com/gaspolymerase/biomanager-app) | The website's front page: the tour of each database, the feature cards, downloads |
| `guide.html` in the same repo | The user guide: one section per area (a sheet, finding things, each database, calendar, notebook, working as a lab, phones, data) |
| `server.html`, `deploy-with-ai.md`, `llms.txt` there | Only when running a server, deploying or the downloads change |
| `docs/DEVELOPMENT.md` | Internals: tables, modules, how things fit together |

The website is its own repo, served by GitHub Pages: clone it into the
scratchpad (`gh repo clone gaspolymerase/biomanager-app`), edit, and publish
it when the app change is pushed, so the site never describes what users
can't get yet. Pushing it publishes it within a minute.

- Write for the people in the lab: what it does for them and where to find it,
  in plain words, as the surrounding text does. Name buttons as the app does.
- Put a change where a reader would look for it; don't add a "what's new"
  list. Fix text the change made wrong (a removed button, a renamed tab).
- Before publishing the website, check the edited pages still parse (every
  list and section closed).
- When a change alters a page that has a screenshot, retake the screenshots
  from a fresh demo lab (`scripts/demo-data.py`, then `scripts/screenshots.py`)
  and copy them to `docs/screenshots/` and the website's `assets/screenshots/`.
- Internal changes with nothing to see (a refactor, a test, a fix that restores
  documented behaviour) need no docs.
