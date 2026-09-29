# BioManager — developer and operator notes

How BioManager is built and how its internals behave. For what the app
does and how to use it, see the [README](../README.md). For running it on a
lab server, see [`deploy/README.md`](../deploy/README.md) and the
[runbook](../deploy/RUNBOOK.md).

## Stack

- Python
- Flask
- SQLAlchemy
- SQLite for local development
- PostgreSQL for a shared lab server (the test suite runs on both in CI)
- Tailwind CSS v4 for the interface (compiled, no CDN at runtime)

## Interface design

The interface follows Apple's macOS conventions: a translucent vibrant
sidebar, a Finder-style tab strip, a unified toolbar whose separator only
appears once content scrolls under it, 13px system type, AppKit control
metrics (28px buttons, 6px radii) and Apple's system colour palette — with
full dark mode.

Two Apple things are deliberately **not** used, because their licences do
not permit it outside Apple platforms:

- **SF Symbols** — licensed for Apple-platform apps only, not web.
- **Shipping SF Pro** — but the system font stack (`-apple-system`)
  resolves to SF on Apple devices, which is both correct and allowed.

### Icons

One sprite, `app/static/icons.svg`, built by `scripts/build-icons.py`:

```bash
python scripts/build-icons.py path/to/fontawesome-free-6.7.2
```

Referenced as `{{ icon('mouse') }}` in templates, which emits
`<svg class="icon"><use href="/static/icons.svg#mouse"></svg>` — one cached
request, inherits `currentColor`, no JavaScript, works offline in the
packaged app.

Three sources, all permissively licensed:

| Source | Licence | Covers |
| --- | --- | --- |
| [Font Awesome Free 6](https://fontawesome.com) | Icons CC BY 4.0 | the UI, plus `worm`, `mosquito`, `fish`, `frog`, `dna`, `vial`, `microscope`, `bacterium`, `virus`, `syringe` |
| [game-icons.net](https://game-icons.net) by Delapouite | CC BY 3.0 | `mouse` (their *rat*) and `fly`, vendored in `scripts/icon-sources/` |
| This project | — | `plasmid`, `petri`, `cage`, `tank`, `culture-vial` |

Font Awesome has no laboratory mouse and no plasmid. The plasmid and the
labware are drawn here; the mouse and the housefly are not, because both
collapse into a blob below about 24px unless ears, snout, tail — or
compound eyes and wings — are all resolved, which is more drawing than a
16px mark can carry. Hand-drawn versions were tried three times and thrown
away.

Add an icon by adding a name to `FROM_FONTAWESOME`, `FROM_SOURCES` or
`CUSTOM` in the build script and rebuilding. **Check any new icon at 15px**,
not just large — that is where they fail.

### App icon

`app/static/icon.svg` is laid out on Apple's macOS icon grid — an 824×824
rounded square inset in a 1024 canvas with a 185.4 corner radius — so it
sits correctly beside native apps in the Dock. The mark is a double helix,
the one symbol every organism in the app shares.

One drawing in `app/appearance.py` serves every size, from 28px beside a
heading to 512px on a desktop, so it is plain vector shapes: no SVG filters
(a blur or drop shadow is drawn at screen resolution by some browsers, Safari
among them, and turns the white edges to haze) and curves as Béziers, not
runs of short lines. `scripts/build-app-icon.py` re-renders the SVG and every
PNG, `.icns`, `.ico` and Android layer after a change, and the website's
copies (`site/assets/icon.svg`, `icon-192.png`, `apple-touch-icon.png`); it
renders with Quick Look on a Mac and with Chromium (Playwright) elsewhere.

## Interface

The UI is a collapsible icon rail plus a persistent **workspace tab strip**:
every page you open becomes a tab, **+** opens a new one on the person's
start page (Settings; Home if none), tabs survive navigation (they live in
`localStorage`), and they can be reordered by dragging, closed with middle
click, and switched with `Alt+1…9` / `Alt+←` / `Alt+→` (`Alt+W` closes,
`Cmd/Ctrl+B` collapses the rail, `Cmd/Ctrl+K` opens search).

### Styling

`frontend/src/tailwind.css` is the single source of truth: design tokens in
`@theme`, composable primitives as `@utility` (`btn`, `field`, `card`,
`badge`, …), and component classes for anything repeated or referenced by
JavaScript (`dt-*` for data tables, `cmdk-*` for the command palette,
`wtab*` for the tab strip, the `workbench` vocabulary for the dense module
pages). It compiles to `app/static/tailwind.css`:

```bash
cd frontend
npm install        # first time only
npm run build:css  # one-off build
npm run watch:css  # rebuild while editing templates
```

Rebuild after editing templates — Tailwind only emits the classes it finds in
`app/templates/**/*.html` and `app/static/*.js`.

Every page is on Tailwind; the old `styles.css` / `legacy.css` bridge has
been removed. Three pages embed third-party widgets that bring their own
stylesheet (Open Vector Editor on plasmid detail, TOAST UI on the calendar)
and the notebook editor's own CSS lives in `frontend/src/styles.css` and
`frontend/src/blocks.css`, built with `npm run build:notebook`. All three read the theme's colour tokens, so
they follow the app's palette and dark mode.

## Organism modules (configurable species databases)

Mouse colony and zebrafish are hand-written modules with their own tables.
Everything else is configurable: an **organism module** is a row in
`organism_modules` that describes a species, and one generic engine serves it.

A module declares:

- **Vocabulary** — cage/tank/vial/plate, strain/line/stock, litter/clutch/progeny.
  These are what the UI calls things, so a fly database says "vial" and "stock".
- **Identity mode** — individuals (mice), groups with a headcount (flies, worms),
  or hybrid (fish: groups that can resolve into named individuals).
- **Capabilities** — 19 switches covering crosses, cohorts, a nursery stage,
  genotyping, environment logs, cryo inventory, protocol/census, billing and more.
  See `app/organisms.py`.
- **Schedule rules** — `anchor date + offset`, optionally varying by rearing
  temperature. One rule covers "flip flies every 14 days at 25 °C, 28 at 18 °C".
- **Custom fields** — typed per-module columns stored in each row's `attrs`
  JSON, which generate their own form inputs, table columns and validation.

Drosophila and C. elegans are seeded automatically on first run
(`organisms.AUTO_SEED_PRESETS`). Zebrafish and mouse exist as presets so the
engine can be checked against the hand-written modules.

Build a new one at **Add database** in the sidebar (`/organisms/new`): pick a
preset or a blank sheet, name the nouns, choose the capabilities, done — no
migration.

### Shape of the schema

| Table | Holds |
| --- | --- |
| `organism_modules` | one species database + its configuration |
| `organism_module_fields` | user-defined fields per module and entity |
| `organism_locations` | location tree: facility / room / system / rack / incubator |
| `organism_lines` | strains, lines, stocks |
| `organism_housing` | cages, tanks, vials, plates |
| `organisms` | the tracked unit — one animal, or a group with `count` |
| `organism_crosses` | matings and crosses |
| `organism_cohorts` | litters, clutches, progeny batches |
| `organism_events` | append-only lifecycle log |
| `organism_due` | materialised schedule items |
| `organism_measurements` | weights, water chemistry, temperatures |
| `organism_genotypes` | genotyping calls |
| `organism_preservation` | frozen lots, vials remaining, recovery tests |

Every row carries `module_id_fk`, and every relation is resolved through
`_ref()` in `app/organism_routes.py` so a reference can never cross modules.

## Access control

Who may change what lives in one place, `app/access.py`:

- **You manage your own colony.** A record whose `owner` is you is yours to
  edit or delete.
- **Shared resources are everyone's.** Breeder cages are shared implicitly
  (`purpose` of breeder/breeding), and any cage can be shared explicitly with
  its `is_shared` flag. The whole lab can edit them and pick mice out of them.
- **Unowned records stay open**, so records predating ownership don't lock
  anyone out.
- **Admins can do anything.**

Visibility is deliberately *not* restricted — a census with holes is not a
census. The **My colony / Shared / Everyone** switch on the colony page is a
view filter; edit rights are per record and don't change with it.

Admins get **Colony overview** (`/admin/colony`): every cage in the facility
grouped by who manages it, with occupancy, shared-cage pooling, idle-time
flags and a warning for living mice with no cage. That's the page for
reassigning animals when someone leaves.

Cage ownership is backfilled on first run from the mice each cage holds; a
cage whose mice disagree is left unowned rather than guessed at.

## Lab setup and personal databases

`app/lab.py` decides what the lab uses and who sees which database; the
pages are in `app/lab_routes.py`.

- **Switchable functions.** The hand-written databases (mouse colony,
  zebrafish, plasmids) and the calendar and notebook are on unless
  `feature:<key>` in `app_settings` is `off`. A switched-off function leaves
  the sidebar, home and search, and its URL prefixes are refused by a
  before-request hook (a flash and home for a page, 403 for a write); its
  data is untouched. Configurable databases use their own `enabled` flag.
- **The survey** (`/setup`, admins) sets those flags, enables, disables or
  creates the fly/worm and inventory databases by kind, and the member
  permissions, then stamps `lab_setup_done`. `landing_url()` sends an admin
  there until it is done, and anyone with no `users.welcomed_at` to the
  welcome tour (`/welcome`) once.
- **Personal databases.** `private_to` on `organism_modules`,
  `stock_modules` and `inventory_modules` names the one user a database is
  for; empty is the lab's. Each blueprint's `_module_or_404` 404s someone
  else's personal database (admins may open it). In a request, the services'
  `list_modules()` return the lab's databases plus the user's own, which is
  what the sidebar, home, search and the Databases page show; pass
  `everyone=True` for admin views. `first_of_kind()` only ever returns a lab
  database.
- **Member permissions:** `members_create_databases` (default on) and
  `members_share_databases` (default off; the test suite turns it on in
  `tests/base.py`, since most tests have members create shared databases).

## Orders and stock

- **Required columns:** `settings["required"]` lists form names (`vendor`,
  `attr_price`…) a new item must have; `None` (never chosen) falls back to
  the preset's list, so older orders inventories get name, vendor,
  catalogue number and quantity. `ModuleView.required` / `requirable` in
  `inventory_service.py`; `_item_from_form` refuses a new item missing one
  and an edit that empties one, but an old item that never had it still
  saves. An order always needs a name. CSV import is not held to it.
- **Remembered values:** `inventory_service.remembered()` gives each text
  column's earlier values (datalists `inv-rem-<column>`) and a fill map by
  name and catalogue number. Inventories that track a supplier lend each
  other name, vendor and catalogue number, never quantity.
- **Stock kinds:** `inventory_service.RESTOCK_KINDS` (reagents, antibodies,
  viruses) are what a received order can become (`STOCK_KINDS`), what
  offers **Order again**, and what Home's *Expiring & low stock* watches.
- **Plasmid columns:** field type `plasmid` (the Viruses preset's *Made
  from*; any inventory can add one in Configure) stores the plasmid's
  number as text. `_item_from_form` reads a number, `#42`, a name or a
  picked `42 · name` through `inventory_service.resolve_plasmid()` and
  keeps the number; one it can't find is kept as typed, with a note.
  `plasmid_links()` links the sheet's cells; `made_from_plasmid()` fills
  the plasmid page's *Made from this plasmid* card. Import matches it by
  `sheet_import.ATTR_ALIASES` like any preset column.
- **Order again:** a reagent, antibody or virus row links to
  `/inventory/<orders>?reorder=<key>:<id>`; `_reorder_payload()` builds the
  new-order dialog, taking quantity, price and grant from the last order
  of the same thing (by `stocked_as`, then catalogue number).
- **Received → stock:** `_offers_stock()` is true when a save moved an
  order to received and it is not stocked yet; autosave and board moves
  answer `offer_stock`, the dialog redirects with `?offer=<id>`.
  `order_to_reagents` redirects to the new record with `?open=<id>`. These
  one-shot parameters are removed from the address on load and from the
  referrer in `_back()`.

## Copies of the lab on every computer

`app/lab_copy.py`. On a server, someone who may (admins; members when Lab
setup's `members_keep_copies` is on) makes a key per computer under
Settings (`lab_copy_keys`, only a SHA-256 kept). With `Authorization:
Bearer <key>` a computer gets `GET /api/lab-copy/snapshot` (the whole
database written to a SQLite file with the app's own metadata, encrypted
columns blanked; SHA-256 and row counts in `X-BioManager-*` headers; one
per key every 2 minutes), `/api/lab-copy/files` (uploads: path and size)
and `/api/lab-copy/files/<path>`. Wrong keys are throttled; from the
internet (guest access) the gate refuses them like any request without a
session. The desktop app (`LOCAL_SETUP`) stores the address and the key
(encrypted) in `app_settings`, and `start_background()` (from `desktop.py`)
fetches a copy when the last good one is over 20 hours old: checksum and
`PRAGMA integrity_check` first, the newest `lab_copy_keep` kept in
`<data>/lab-copies/<host>/db/`, uploads mirrored into `uploads/` (never
deleted). A snapshot loads into a new server with
`scripts/migrate-to-postgres.py` (`tests/test_lab_copy.py` proves it on
PostgreSQL).

## Notifications

`app/notify.py`. A `before_flush` listener looks at dirty records (mice,
cages, tanks, fish, organisms, housing, vials, inventory items) and new
organism genotype calls, and notes who should hear what: an owner change,
a move to another cage/tank, a genotype recorded, an order status. Notes are
turned into `notifications` rows in `before_commit`, grouped per recipient,
category and kind of change (twenty mice moved: one row listing them), never
to the actor, and dropped on rollback. `send()` respects the
`users.notify_<category>` switches and skips disabled accounts.

The header bell (`base.html`, `static/shell.js`) polls
`/notifications/count` every minute while the tab is visible and fetches
`/notifications/panel` when opened; `/notifications/<id>/open` marks one read
and redirects only to a path in this app. The daily "waiting for genotyping"
reminder is made on a user's first page of the day.

## The lab notebook

Pages are `notebook_pages` inside a person's `notebook_tabs` (topics);
everything added in the rebuild lives beside them, in its own tables
(`app/models.py`, below the lab calendar's), so existing databases need no
column changes. `app/lab_notebook.py` has the routes (`/notebook/api/…`) and
the rules; the editor is `frontend/src/` and the page around it is
`app/static/notebook-page.js` and `app/static/notebook.css`.

| Table | Holds |
| --- | --- |
| `notebook_page_info` | kind (note, experiment, protocol, meeting, seminar, daily), status, tags, start/finish, the protocol an experiment follows, a meeting's series and presenter, the live-editing generation |
| `notebook_shares` | who else may open a page, and whether to view or edit (`*` is the whole lab, guests excepted) |
| `notebook_versions` | the page's history: `auto` (one person's edits within 10 minutes, up to an hour, fold into one), `manual`, `release` (a protocol's v1, v2 …), `restore` |
| `notebook_sync_updates`, `notebook_presence` | live editing: Yjs updates and cursors (below) |
| `notebook_comments` | comments on a page or a quoted passage, and replies |
| `notebook_recipes` | the lab's buffer library (the built-in ones are `PRESET_RECIPES`) |
| `notebook_meeting_series` | a meeting's rotation (`members` in order, `next_index`), day and time |

**Colony experiments in a page.** The `experiment` block
(`frontend/src/blocks/experiment.js`) keeps only `{"id", "show",
"percent"}` and reads `/colony/experiments/<id>/notebook.json`; *Freeze a
copy* stores that payload in the block as `frozen`, so the page's
versions keep it. The payload, the plan and the records are
`app/experiment_steps.py`:

Experiments are on any database's animals (`app/experiments.py`):
`experiments.db` says which (`colony`, `zebrafish`, `stocks:<key>`,
`organisms:<key>`) and `experiments.readout` what is measured (JSON; blank
is the database's usual one). `experiments.Place` is what an experiment
needs to know of its database (nouns, housing, the kinds of manipulation
its animals get, the readouts that fit), and `subjects()` gives its
animals the same shape whatever they are. One page serves them all:
`templates/experiment.html`, drawn by `static/experiment-page.js` from
`/experiments/<id>/data.json`, and every change answers with that data.

| Table | Holds |
| --- | --- |
| `experiment_subjects` | the animals of an experiment that isn't the colony's: a fish row, a vial or plate, an organism; its treatment group and how many there were at the start |
| `experiment_readings` | one readout per animal, readout and day (a mouse's body weight is a `mouse_weights` row instead) |
| `experiment_regimens` | saved regimens: an experiment's lines and days, per kind of animal, to plan the next one from (planning never records anything done) |
| `experiment_steps` | an experiment's manipulations: days (`"2–5"`, day 1 = the start date), kind, agent, dose, route, concentration, treatment group |
| `experiment_step_records` | one per step and day done: date, who, and per mouse the weight used and the amount and volume given (`mice`, JSON) |

A `reading` step (`weigh` in the first version) writes the readout when recorded.
A step may name the inventory item it uses (`reagent_item_id_fk`); a record
keeps that item as it was then (`reagent`: name, lot, expiry) and any sample
records the person chose to make with it (`samples`), made through
`inventory_routes._item_from_form` with the animal as their Source. Subjects
are `mouse`, `fish`, `clutch`, `unit`, `organism` or `cohort`.
`exp_stats.py` compares the groups on each day (Welch, ANOVA, χ²);
`/experiments/<id>/export.xlsx` and bench mode (`/experiments/<id>/bench`,
`static/experiment-bench.js`) are in `experiments.py`. The owner's
morning notification of what is due is `notify.daily_experiment_reminder`
(category `experiments`, `users.notify_experiments`). Undone days are
`auto` items on the calendar (`experiment_steps.calendar_items`). Which
notebook page is a person's for an experiment is the app setting
`experiment_notebook_page:<experiment>:<username>`.

**Signed pages** (`app/signatures.py`, table `record_signatures`): sign,
witness and amend events, each with the SHA-256 of the title and text at
that moment and (for a sign) the version it made. A page is locked while
its newest sign has no amend after it; then `page_payload` gives the
editor role `view` (`real_role` keeps the owner's sharing),
`load_page(need="edit")` answers 423, and so do the live-sync push and
`/notebook/pages/<id>/update`. Signing freezes live `experiment` blocks
into the text and resets live editing so open editors reload it.

**Who may do what** is `lab_notebook.role_for()`: `owner`, `edit`, `view` or
nothing. Viewers read and comment; editors also write; only the owner
shares, moves or deletes. Search, backlinks and the global search use
`accessible_filter()`, so a shared page is found wherever the owner's is.

**Live editing** needs no websocket: each open editor holds the page as a
Yjs document (`frontend/src/collab.js`), posts its updates (base64) to
`/notebook/api/pages/<id>/sync` and polls the same address for everyone
else's, every 1.2 s while someone else is on the page and every 4 s
alone. Yjs merges updates in any order, so two people typing in one
paragraph both keep their words. The first editor to open a page seeds it
from the saved Markdown (`init`, refused if someone else got there first).
Cursors travel as Yjs awareness updates in `notebook_presence`. When the
log grows past a few hundred updates, one editor replaces it with a single
snapshot (`/sync/compact`).

The Markdown in `notebook_pages.body` stays the source for search,
history and export: editors save it after their changes (with
`X-Collab-Gen`), and a version is credited to whoever last typed. Anything
that replaces the text from outside the editor (restoring a version, the
plain-text fallback) bumps `collab_generation` and clears the log; open
editors are told to start again from the saved text.

**Blocks** (data sheets, recipes, calculators, plates, qPCR, diagrams,
equations) are one TipTap node, `labBlock` (`frontend/src/blocks/`). In
Markdown each is a fenced block named by its kind (```` ```sheet ````,
```` ```recipe ````, ```` ```mermaid ```` …) holding JSON or the source, so a
page reads anywhere and GitHub draws the diagrams and maths itself. In the
editor the data is one node attribute rather than text: Yjs merges text
character by character, which would splice two people's JSON, while an
attribute is replaced whole. Statistics (`blocks/stats.js`) and formula
columns (`blocks/formula.js`) are computed in the browser; formulas are
parsed by hand because the security policy forbids `eval`.

Mermaid and KaTeX are large and most pages use neither: `npm run
build:vendor` copies them to `app/static/notebook-build/vendor/`, and they
load the first time a page shows a diagram or an equation.

## Change history

Every create, edit and delete on a tracked table writes an `audit_log` row
with a field-level diff (`genotype: DBH-Cre → ∅`). This is done with a
SQLAlchemy `before_flush` listener in `app/audit.py`, not per-route calls, so
it covers the whole app including the organism engine, and the audit row is
written in the same transaction as the change it describes. Passwords and
tokens are redacted; high-churn tables are excluded. Admins read it at
`/audit`.

## Keeping the data safe

**Schema changes are Alembic revisions** (`migrations/versions/`,
`app/upgrade.py`). On start-up `services.init_database()` asks
`upgrade.plan()` what opening the database will change; if anything, it
copies an SQLite database first (`backups/before-upgrade-<from>-to-<to>-<time>.db`,
ten kept), then runs `create_all()`, the frozen pre-0.8 ALTERs
(`ensure_schema_updates`, which stop at revision `0002_v0_8_schema`), the
one-off data migrations, and `alembic upgrade head`. A new database is
stamped at head instead. Because create_all() runs first, a revision must
tolerate what it adds already being there: use `migrations/helpers.py`
(`create_table`, `add_column`). `scripts/upgrade-check.py` makes a demo
lab with every release tag, opens it with this code and checks the schema,
the row counts, the revision, the copy and the pages. With `--postgres
<url>` it does the same for a lab server: that release's own
`migrate-to-postgres.py` moves its demo lab into a new PostgreSQL database
on that server, and this code opens it (no copy there: the backup service
takes one before an update). `.github/workflows/upgrade-check.yml` runs
both on master and on tags.

**A SQLite file must not live in a cloud-synced folder.** OneDrive, Dropbox
and Google Drive do not honour SQLite's file locking: a sync mid-write, or
two machines with the folder open, corrupts the file outright. The app logs a
loud warning at startup if it detects this.

```bash
python scripts/dbtool.py check                      # location, integrity, sync risk
python scripts/dbtool.py backup                     # consistent snapshot, keeps 30
python scripts/dbtool.py relocate ~/BioManagerData  # move it somewhere local
python scripts/dbtool.py restore <file>
```

These are for a SQLite database on one machine. A server on PostgreSQL is
backed up by the backup service in `deploy/` (`deploy/backup/backup.sh`
runs without Docker too).

`relocate` copies, verifies with an integrity check, and only then retires
the original — then prints the `BIOMANAGER_DATA_DIR` to export. Backups use
SQLite's backup API, so they are consistent even while the app is running.

Schema changes go through **Alembic** (`migrations/`). Existing databases are
stamped at `0001_baseline` automatically on boot:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

The old hand-written ALTERs in `services.ensure_schema_updates()` still run
for backwards compatibility, but new changes belong in a revision.

## Cage cards and QR labels

Printable, correctly-sized cards with a QR that opens the record — so someone
at the rack scans instead of walking back to type an ID.

- Mouse cages: **Cage cards** on the Cages view, or `/labels/cards/cages`
- Zebrafish tanks: **Tank labels**, or `/labels/cards/tanks`
- Organism modules: **Labels** on the Housing view, or `/labels/cards/<module>`
- Fly and worm stocks: **Labels**, or `/labels/cards/stocks/<key>`
- Inventories: **Labels** on the ticked rows, `/labels/cards/inventory/<key>?ids=…`

Each takes `ids=1,2,3` or the selection bar's repeated `selected_ids`.
`?stock=` picks what they print on (`labels.STOCKS`): `sheet`, or a label
printer's size, which prints one label a page (`@page { size }`, no
margin) with type sized by `labels.fit()`; the last choice for each kind is
kept in the session cookie. `?format=zpl&dpi=203|300` returns ZPL II
(`labels.to_zpl`: `^CI28` UTF-8, text through `^FH_` so `^ ~ _` are hex,
`^BQN` QR at the largest magnification that fits). An admin sets the lab's
Zebra (`app_settings.label_printer`, host or host:port, and
`label_printer_dpi`); `POST /labels/send` opens a socket to it on port
9100. `labels.printer_address` only accepts private, loopback, link-local
and Tailscale (100.64/10) addresses, so the server never sends to the
internet.

Cards are laid out in millimetres and print without any app chrome. QR
payloads are absolute URLs built from the incoming request, so a card printed
on the lab server scans to the lab server. Rendering uses `segno` (pure
Python, no image libraries), and cards still print without it — just without
the code.

## The public API

`app/api.py`: `/api/v1`, JSON, for scripts, instruments and other tools;
the reference page is `/api` and the spec `/api/v1/openapi.json`, both made
from `ENDPOINTS`, so a new endpoint goes there too.

- **Tokens** (`api_tokens`): made under Settings → API tokens (`api/_card.html`),
  `bmt_` and 40 random characters, shown once (`api/token.html`); only the
  SHA-256 and the first ten characters (`hint`) are kept. `scope` is `read` or
  `write`; `expires_at` 30, 90, 365 days or never. Members make them only
  while Lab setup's `members_api_tokens` is on (default on); guests never.
  Admins see and revoke everyone's.
- **Signing in**: `app.load_current_user` hands `/api/v1…` to
  `api.authenticate()`, which reads only `Authorization: Bearer` and never
  the session cookie. So `security.cross_site_reason` skips those paths (a
  cross-site request can't carry the token), `lab_routes.remind_once_a_day`
  skips them, and `api._no_cookie` strips any Set-Cookie. A disabled
  account, a revoked or expired token, or members' tokens switched off: 401.
  `g.audit_batch = "API: <label>"` marks the change history.
- `_gate`: 401 without a token, 403 when a read token tries a change, 429
  past `PER_MINUTE` (600) per token per worker (`_Rate`, in memory).
- **Lists** page by row id: `?limit` (100, at most 1000) and `?after`;
  the reply's `next` is the URL of the following page. Filters are in SQL.
- **Writes reuse the pages' code**, so their rules hold: `PATCH /mice/<id>`
  fills a form from `mouse_display_row`, overlays the fields sent, and calls
  `populate_mouse_from_form` (flashed refusals come back as `warnings`);
  inventory items go through `inventory_routes._item_from_form`, vials
  through `stock_routes._unit_from_form` (both copy only the fields sent),
  readouts through `experiments.set_reading`. Permission checks are the
  same functions (`can_edit_mouse`, `_can_edit`, `can_edit`,
  `access.can_edit_experiment`). A switched-off built-in database is a 404.

## Feedback and the usage report

`app/feedback.py`, for a pilot (the plan is `docs/PILOT.md`). **Feedback**
in the rail opens `/feedback?from=<the page>`; a note is a `feedback` row
(kind, text, the page's path, `app_version()`, a short platform string)
and each admin gets a notification. Admins see every note and mark it done;
members see their own. `issue_url()` builds a GitHub "new issue" link on
gaspolymerase/biomanager with the text, path, version and platform —
never the server's host or the person — which the person submits
themselves: nothing is sent by the server.

`/feedback/usage` (admins) is `usage()`: for each of the last eight weeks
(Monday to Sunday), the distinct lab accounts in the change history and
its rows per area (`AREAS`, by table-name prefix), notebook pages and
calendar events created; and totals now. `usage_text()` is the same as
plain text to paste into an email.

## Anonymous daily counts

`app/telemetry.py` (its docstring is the full account). Once a day an
installation posts one PostHog event to `HOST/i/v0/e/`:
`{"api_key", "event": "heartbeat", "distinct_id", "properties"}`. The
properties are `version`, `kind` (`desktop` under `LOCAL_SETUP`, else
`server`), `os` (`platform.system()`), `database` (the dialect),
`members` and `active_7_days` as ranges (`bucket()`: 0, 1, 2-5, 6-15,
16-50, 51+; active accounts, and lab accounts in the change history in the
last 7 days), `functions_on` (keys of `lab.FEATURES` that are on),
`databases_on` (enabled organism databases; stock databases by `kind`;
inventories by preset `kind`, anything else as `custom`), and
`$geoip_disable: true`, `$process_person_profile: false`. Nothing else:
never a name, a label, a key, a host or free text. A new property must keep
to that, and `tests/test_telemetry.py` checks names don't leak.

- **When**: `after_request` checks at most once an hour per process
  (`CHECK_EVERY`), then a daemon thread with the app context calls
  `send_if_due()`, which needs a key, no env switch, the lab switch on and
  the setup survey answered, and claims `telemetry:last_sent` with a
  conditional UPDATE so two gunicorn workers never both send. A failed
  post (5 s timeout, `urllib`) puts the old stamp back, logs at debug and
  is retried the next hour. Never under `TESTING` (the hook checks).
- **app_settings**: `telemetry:enabled` (`on`/`off`, default on; the first
  survey's checkbox, and **Switch on/off** on the Usage report,
  `POST /feedback/usage/heartbeat`), `telemetry:install_id` (a `uuid4`,
  made on first use; the Usage report's preview makes it too, so the JSON
  shown is exact), `telemetry:last_sent` (UTC ISO).
- **Environment**: `BIOMANAGER_TELEMETRY_KEY` (the project's public
  `phc_…` key; overrides `PROJECT_KEY`, which is empty in the source: no
  key, nothing is ever sent), `BIOMANAGER_TELEMETRY=0` or `DO_NOT_TRACK=1`
  (off, whatever the admin chose; the page says "Off (set by the server)").
  The Docker stack passes both switches from `deploy/.env`.

## Reminder emails

A daily digest of what is overdue or imminent: module schedule items (flips,
chunks, re-freezes), litters reaching weaning, breeders past 30 weeks, and
personal tasks. Configure by environment:

```bash
export BIOMANAGER_SMTP_HOST=smtp.example.edu
export BIOMANAGER_SMTP_PORT=587
export BIOMANAGER_SMTP_USER=biomanager@example.edu
export BIOMANAGER_SMTP_PASSWORD='an app password'
export BIOMANAGER_BASE_URL=http://lab-server:5055
```

```bash
scripts/send-reminders.py --dry-run     # print digests, send nothing
scripts/send-reminders.py               # send
```

Daily, via cron:

```
0 8 * * *  cd /path/to/Biomanager && .venv/bin/python scripts/send-reminders.py
```

With SMTP unconfigured the digests are logged rather than sent, so the job is
safe to schedule before a mail server exists. People with no email address on
their account are skipped. Settings shows the current delivery status.

## Batch operations

Two directions of the same idea: one specification applied to many records.

**Acting on records that exist** — tick rows in the mice table and a
selection bar rises from the bottom of the viewport:

- **Set** one field (owner, status, genotype, cage, note, date of death)
  across the selection
- **Add to experiment** with a shared treatment group — this is the "N mice
  under the same manipulation" case
- **Sac**, with a confirmation naming the count

Shift-click extends a range, the header checkbox selects everything
*visible* (never filtered-out rows), and each action applies only to records
you may edit, reporting how many were skipped rather than failing outright.

The bar is generic — `static/selection-bar.js` reads a markup contract, so
another table gets batch actions by adding `data-selection-scope`, row
checkboxes, and a form marked `data-selection-form`. No JavaScript changes.

**Creating records** — **Add many** on the colony page
(`/colony/mice/batch`) is a two-step flow: describe one mouse and say how
many, or upload a CSV, then check and edit an editable preview grid before
anything is written.

- Counts can be split by sex (`4 females, 2 males`) — the usual shape of a
  litter or an order.
- **IDs are assigned in ascending order** and shown in the preview
  (`IDs #25 – #30`). They are allocated again at save time, so a preview left
  open while someone else adds mice cannot collide.
- `new` in the cage field puts the whole batch in **one** freshly allocated
  cage; type numbers per row in the preview to split them.
- **Fill down** copies the first row's value into empty cells below — the
  usual fix after a CSV that only filled the first line.
- Tick **Skip** to leave a row out without deleting it.

CSV headers are matched loosely: `sex`, `dob`, `cage`, `litter` and `notes`
map onto the real columns, unknown columns are ignored, and `mouse_id` should
be left out entirely so IDs are assigned for you.

The older `/import/<entity>` endpoint still serves plasmid and order imports,
and also assigns ascending mouse IDs from a single reserved block via
`services.reserve_mouse_ids()`.

> Previously this path was broken: `next_mouse_id()` was called per row, and
> because the session runs with `autoflush=False` the `max()` query could not
> see pending rows, so every row was handed the same ID and the import died
> on the unique index. Any CSV without explicit `mouse_id` values failed
> outright. The allocators now flush first, and batch paths reserve a
> contiguous block up front.

### Batches and undo

Every bulk action is recorded as a **batch** — one row in `batches` saying
who ran it, what it did and to how many records — and its audit entries
point back at it. **Batches** in the sidebar (`/batches`) lists them with
what undoing each would do.

Undo reverses the recorded changes, newest first:

| The batch | Undo does |
| --- | --- |
| created records | deletes them |
| edited records | puts every column back to its previous value |
| deleted records | re-inserts them from the stored snapshot |

It refuses in two cases, loudly rather than silently: a batch already undone,
and a record **changed again after the batch** — reverting then would discard
whoever's later edit. That second case offers *Undo anyway*. The undo is
itself recorded as a batch, so undoing an undo is a redo.

This needed audit entries to carry a machine-readable diff, not just prose:
`audit_log.changes_json` holds `{"changes": {field: [before, after]}}` for an
edit and `{"snapshot": {...}}` for a delete. Parsing
`genotype: ∅ → C57BL/6` back into a value would have been guesswork.

Two ordering details worth knowing if you touch `app/audit.py`:

- **Inserts are logged in `after_flush`, not `before_flush`.** A new row has
  no primary key until the INSERT runs, so logging it earlier records
  `record_id = 0` and undo has nothing to find.
- **`audit.batch()` flushes on the way out**, so callers that commit after
  the block still get their audit rows attached to the batch.

## Run locally

1. Create and activate a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Build the stylesheet once: `cd frontend && npm install && npm run build:css && cd ..`.
4. Start the app with `python run.py`. On macOS port 5000 is taken by
   AirPlay/Control Center, so use `PORT=5055 python run.py` if the page does
   not load. `FLASK_DEBUG=1` turns on reloading and in-browser tracebacks;
   `run.py` refuses it on anything but a loopback address.
5. Open `http://127.0.0.1:5000` (or the port you set).
6. Register the first user, who becomes `admin`. The page asks for the
   **setup code** printed in the terminal when the app started (it is also
   in `data/setup-code`, which is deleted once the admin exists). The desktop
   app does not ask: only this machine can reach it.

The SQLite database is created automatically at `data/biomanager.db`. No
`SECRET_KEY` is needed: without one, a random key is made on first run and
kept in `data/secret_key` (readable by you only).

## Running the tests

```bash
scripts/test.sh
# which is:
.venv/bin/python -m unittest discover -s tests -t .
```

The suite in `tests/` uses only the standard library's `unittest` (it also
runs under pytest, if you have it). It starts the app once on a fresh
SQLite database in a temp folder — `data/` is never opened — and drives the
real routes with Flask's test client, as an admin and as members, so
permissions and validation are checked along with behaviour. One module per
area (`test_mice.py`, `test_plasmids.py`, `test_stocks.py`, …); shared
set-up and factories are in `tests/base.py`. Run one module, class or test
with `scripts/test.sh tests.test_mice` (or `tests.test_mice.SomeClass`).

The same suite runs on PostgreSQL, against an empty database it is allowed
to wipe (its schema is dropped first):

```bash
BIOMANAGER_TEST_DATABASE_URL=postgresql://localhost/biomanager_test scripts/test.sh
```

Tests of SQLite-only machinery (`app/integrity.py`) skip there, and the
SQLite → PostgreSQL migration tests only run there. CI runs both.

Every test makes its own uniquely named records and must not depend on
another test having run. A test marked `@unittest.expectedFailure`
documents a known bug; when the bug is fixed it shows up as an "unexpected
success" — remove the marker then. GitHub Actions runs the suite on every
push (`.github/workflows/tests.yml`).

### A big lab: the load test

`scripts/load-test.py` fills a demo lab with 100,000 mice (5% alive, the
rest dead on days spread over five years), their cages, litters and weights,
zebrafish, fly vials, 40,000 inventory items and notebook pages, then times
each main page as the demo admin. Run it after changing what a sheet loads:

```bash
.venv/bin/python scripts/load-test.py /tmp/bm-load
```

What keeps the sheets usable at that size:

- `colony_context` loads only the tab being opened (`active_view`), with
  `selectinload` for each row's cage, rack and litter rather than one query
  a row, and counts in SQL.
- What ended over `RECENT_DAYS` (90) ago is left out unless `?ended=all`:
  mice by date of death, cages with no living mouse and no recent death,
  litters over a year old with no living pup (colony), used-up or
  cancelled items and received orders (`inventory_routes._recent_items`,
  by `attrs.used_up_on` and `received_on`), discarded vials
  (`stock_routes`). The sheet says how many and links to them. Search,
  exports and the box grid still see everything.

At 100k mice on SQLite, the mouse and cage sheets take 2–3 s and stream
30–60 MB of rows (about 3 KB a row, a third of it whitespace). The next
step, if a lab needs it, is paging on the server instead of the sheet's
client-side pages.

## Desktop App

**Signed builds.** The release workflow signs and notarises the Mac apps
(`scripts/sign-macos.sh`, entitlements in `desktop/entitlements.plist`) and
signs the Windows exe when these repository secrets exist; without them it
builds unsigned, as before:

| Secret | What |
| --- | --- |
| `MACOS_CERT_P12`, `MACOS_CERT_PASSWORD` | A "Developer ID Application" certificate with its key, exported from Keychain Access as .p12 and base64-encoded (`base64 -i cert.p12 \| pbcopy`), and the export password. Needs an Apple Developer Program membership. |
| `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_PASSWORD` | The developer account's Apple ID, its team ID, and an app-specific password (appleid.apple.com → Sign-In and Security), for notarisation. |
| `WINDOWS_CERT_PFX`, `WINDOWS_CERT_PASSWORD` | A code-signing certificate (.pfx, base64) and its password. |

**Updating itself** (`desktop_updates.install_update`): the file for this
computer is downloaded, checked against the SHA-256 GitHub publishes in the
release's asset `digest`, staged beside the installed copy, and a small
script waits for the app's process to end, moves the old copy aside and the
new one into place, and opens it. A file the app downloads itself carries
no quarantine flag, so an update opens without the first-launch warning
even while the builds are unsigned.

`desktop.py` starts Flask on a free local port and opens it in a
pywebview window. `desktop_menu.py` builds the menus: on a Mac, the whole
menu bar through AppKit (installed on the main thread once the window is
shown, replacing pywebview's two defaults); elsewhere pywebview's own
menus. The Go menu is the sidebar: `static/shell.js` sends the page's
sidebar links to `DesktopApi.set_nav` over pywebview's JavaScript bridge,
which keeps only same-origin paths. `desktop_updates.py` is the version
(the `VERSION` file `Biomanager.spec` bundles from `BIOMANAGER_VERSION`;
from source, the latest tag + "+dev"), the update check against
`api.github.com/repos/gaspolymerase/biomanager/releases/latest`, and
this computer's `desktop-prefs.json` (automatic check, skipped version,
appearance, zoom) in the data folder. Set `BIOMANAGER_MENU_DUMP=<file>` to
have a running app write its menu bar there, for checking a build.

Build a clickable native app (no terminal needed to launch):

```bash
./scripts/build-desktop.sh
open dist/BioManager.app
```

The script installs `pywebview` + `pyinstaller`, ensures the frontend bundle is built, and produces `dist/BioManager.app` (macOS) or `dist/BioManager/` (Windows/Linux). The app's SQLite database and uploads live in `~/Library/Application Support/Biomanager/` so rebuilds don't wipe your data. To skip the bundling step and just run a desktop window from source: `python desktop.py`.

## The phone apps

`android/` (Kotlin, Gradle) and `ios/` (SwiftUI, XcodeGen) are the same
small thing: a setup screen that asks for the lab server's address and
checks `/healthz` answers `ok`, then a web view of that server, plus a
native QR scanner. Links to other hosts open in the system browser.

- **iOS**: `ios/project.yml` generates the Xcode project (`cd ios &&
  xcodegen`; the `.xcodeproj` is not committed). `Scanner.swift` is
  VisionKit's `DataScannerViewController`. A page on the server can borrow
  it: `window.webkit.messageHandlers.bmScan.postMessage('scan')` opens the
  scanner and the code comes back as `window.bmScanned(text)`
  (`LabWebView.swift`, which only answers pages from the server's own
  host). Bench mode (`experiment-bench.js`) uses it for **Scan a card**,
  and in a browser falls back to `BarcodeDetector` on the camera when the
  browser has it. `.github/workflows/ios.yml` builds it for the simulator
  on a macOS runner and screenshots it against a demo server; shipping it
  needs an Apple developer account (`DEVELOPMENT_TEAM`).
- **Android**: `.github/workflows/android.yml` builds the APK, checks it in
  an emulator, and the release workflow publishes it.

## Shared Server Setup

**The supported way is the Docker stack in [`deploy/`](../deploy/README.md)**:
Caddy for HTTPS, the app under gunicorn, PostgreSQL 16, and a backup service
that dumps, checks, prunes, copies off-site with restic and test-restores
every week. `deploy/README.md` is the runbook: first start, moving a lab's
SQLite database over (`scripts/migrate-to-postgres.py`), backups, restoring
and updating.

The rest of this section is for running it without Docker.

Running BioManager for a whole lab means other people can send it requests,
so it runs differently from a laptop. What decides which requests to trust is
in `app/security.py`; its docstring explains each check.

```bash
pip install -r requirements.txt            # includes gunicorn
export DATABASE_URL='postgresql://USERNAME:PASSWORD@localhost:5432/biomanager'
export BIOMANAGER_PROXY_HOPS=1             # behind Caddy/nginx (below)
gunicorn -c gunicorn.conf.py wsgi:app      # never python run.py
```

`wsgi.py` sets `BIOMANAGER_ENV=production`, refuses to start with debug on,
and turns on Secure cookies — so the server **must be reached over HTTPS**.
gunicorn listens on `127.0.0.1:8000` only; put a reverse proxy in front for
TLS. With Caddy that is two lines:

```
lab-biomanager.example.edu {
    reverse_proxy 127.0.0.1:8000
}
```

With nginx, pass the headers the app reads:

```
proxy_set_header Host $host;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Host $host;
client_max_body_size 64m;
```

Settings (environment variables, all optional):

| Variable | Default | Does |
| --- | --- | --- |
| `SECRET_KEY` | kept in the data folder | signs session cookies; 32+ characters in production |
| `BIOMANAGER_HTTPS` | on in production | Secure cookies; `0` only for a trusted plain-HTTP network |
| `BIOMANAGER_PROXY_HOPS` | `0` | proxies in front whose `X-Forwarded-*` headers to trust |
| `BIOMANAGER_TRUSTED_ORIGINS` | — | other origins allowed to post, comma separated |
| `BIOMANAGER_SESSION_DAYS` | `7` | idle days before a sign-in expires |
| `BIOMANAGER_MAX_UPLOAD_MB` | `64` | largest upload accepted |
| `BIOMANAGER_UPLOADS_DIR` | `app/static/uploads` | where uploads are kept; put it next to the database |
| `BIOMANAGER_TELEMETRY` | on | `0`: never send the anonymous daily counts (so does `DO_NOT_TRACK=1`) |
| `WEB_CONCURRENCY` | 1 on SQLite, 3 on Postgres | gunicorn worker processes |

`gunicorn.conf.py` loads the app once before forking (`preload_app`), so the
start-up schema updates and seeding run once, not in every worker at the
same moment. On first start the log prints the setup code for the first
admin account.

Keep the server off the open internet: on the campus network or VPN, or a
private network such as Tailscale.

## Multi-User Notes

- **The first account is the admin**, and on a server needs the setup code
  from the log, so nobody else on the network can claim it first.
- **Everyone after that waits for approval.** A sign-up is created as
  *awaiting approval*; admins get a notification and approve it in
  Settings → Manage users. `scripts/reset-password.py NAME --enable` does the
  same from the command line on SQLite.
- **Passwords are at least 12 characters.** Ten failed sign-ins in 15 minutes
  lock out that username and that address for the rest of the window.
- **Changing or resetting a password signs out every other session** of
  that account — the fix for a lost laptop.
- **Changes from other websites are refused.** Every POST is checked against
  the browser's `Sec-Fetch-Site`/`Origin` headers, so a malicious page cannot
  make a signed-in member's browser edit records. Sign out is a POST too.
- **Uploads need a login**, get unguessable names, and are served so that an
  uploaded HTML or SVG file downloads rather than running in the app.
- **Google Calendar tokens are encrypted in the database** with a key
  derived from the signing key. Tokens saved before are encrypted at the
  next start. Losing or changing the key only means reconnecting Google
  Calendar, which is why backups include the data folder's `secret_key`.

