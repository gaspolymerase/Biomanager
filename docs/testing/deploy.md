# BioManager 1.0 pre-release test: `deploy` (running a lab server)

## 1. Scope and environment

What was tested: running a lab server the way a lab would, **from the published release files and the docs only**
(`deploy/README.md`, `deploy/RUNBOOK.md`, `BUNDLE.md` in the bundle, `site/server.html`). The server bundles, app
images and the Linux desktop build came from the GitHub releases (v0.10.2 = latest, and v0.10.1). No source from the
checkout was used to run anything, except `desktop_updates.py` for the update check (DEP-55).

| | |
| --- | --- |
| Host | Linux x86-64 container, 4 CPU, 15 GB RAM, Docker 29.3.1 (containerd image store), Compose v5.1.1; no systemd, no Tailscale |
| Stack | the bundle's `compose.yaml`: `db` (postgres:16), `app` (ghcr.io/gaspolymerase/biomanager:0.10.2 / 0.10.1 / 0.9.0 loaded from release files), `caddy` (caddy:2, `TLS=internal`, once `TLS=files`), `backup`/`restore` |
| Database | PostgreSQL 16 in the stack; source SQLite lab for the move-in made by `scripts/demo-data.py` **inside the 0.10.1 image** (390 rows, 85 tables, 4 users, 39 mice) |
| Browser | Playwright Chromium 141 (headless), through Caddy on port 443, name mapped with `--host-resolver-rules` |
| Stacks (compose projects) | `t-deploy-fresh` (fresh 0.10.2), `t-deploy-upg` (0.10.1 + demo lab → 0.10.2 → 0.10.1 → 0.10.2), `t-deploy-lost` (replacement server restored from off-site), `t-deploy-old` (0.9.0 → 0.10.2 → 0.9.0), `t-deploy-race` (migration race). All removed at the end (`down -v`). |

**Sandbox deviations (not product issues):**

- **Ports.** A stack from an earlier session (`bm09`, not mine, left running) held host ports 80/443/8081 and I was
  not permitted to stop it. Each of my stacks therefore published Caddy on `127.0.0.1:x8080/x8443/x8081` through a
  small `compose.t-deploy.yaml` (`ports: !override`), set with `COMPOSE_FILE`/`COMPOSE_PROJECT_NAME` in `.env`
  (`scripts/sandbox/`). All HTTPS tests went to **Caddy's container IP on port 443**, so certificates, names and
  redirects are exactly as on a real server. Nothing else in the bundle was changed.
- **The backup image cannot be built here.** `deploy/backup/Dockerfile` apt-installs `restic curl ca-certificates`;
  this machine's egress policy refuses `deb.debian.org` and `apt.postgresql.org` over http **and** https (403). I
  built it from `scripts/sandbox/Dockerfile.backup-sandbox`: the same `FROM postgres:16`, the same five scripts, with
  restic 0.18.0 (Debian trixie's version) and a static curl from their GitHub releases. Hooked in through the same
  override file (`build.dockerfile`), so `docker compose build/up --build` behave as documented.
- Docker Hub rate-limited (429) `docker compose pull` in `maintenance.sh`; postgres:16 and caddy:2 were already
  present locally (mirror.gcr.io tags).
- At 17:33:38 something outside my area sent SIGTERM to every gunicorn on the host (all stacks' `app`, including the
  foreign `bm09`, died in the same second). `restart: unless-stopped` brought every app back healthy within ~5 s.
- Not testable here: `host/install.sh` (systemd timers), `host/offsite-setup.sh` (accepts only `s3:https://`, no S3
  endpoint available), Tailscale / Funnel / `host/internet-access.sh`, `TLS=acme`/`tailscale`, the Mac pull scripts,
  `cloud-init.yaml`, arm64.

## 2. Test log

| ID | What | How (steps, users, data) | Expected | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| DEP-01 | Download the latest server bundle | `curl -fsSL` of the README URL | v0.10.2 bundle | PASS: redirects to v0.10.2, 28 KB, `VERSION`=0.10.2 | `dl/` |
| DEP-02 | `host/load-image.sh` (download mode) | run in the unpacked bundle | image `…biomanager:0.10.2` loaded | PASS: 85 MB download + load in 4.4 s | 01 |
| DEP-03 | `docker compose up -d --build` builds the backup image | as README "First start" | image builds | WARN (sandbox): apt 403 from Debian mirrors; see deviations. Product note: F-13 | 02 |
| DEP-04 | Fresh stack starts | `.env` from `.env.example` (DOMAIN, `openssl rand -hex 24`, TZ, TLS=internal) | db/app/backup healthy, Caddy up | PASS: 17.7 s to all started, app healthy | 02 |
| DEP-05 | Setup code from the log | `docker compose logs app \| grep "setup code"` | the code | PASS (the line is printed twice, cosmetic) | 03 |
| DEP-06 | Caddy root CA + healthz over HTTPS | README command `docker compose exec caddy cat …/root.crt > biomanager-root.crt`; `curl --cacert` | `ok`, cert verifies | PASS: `ok`, 200, HSTS set; without the root curl refuses (expected) | 04 |
| DEP-07 | HTTP → HTTPS | `curl http://DOMAIN/` | redirect | PASS: 308 to https | — |
| DEP-08 | First admin with the setup code, sign in, in a browser | Chromium: /register (Ada Admin, setup code) → /login | admin created, signed in | PASS: lands on "Set up your lab"; cookie `session` Secure+HttpOnly+Lax; `/data/setup-code` gone after | 05-*.png, 05 |
| DEP-09 | Backup on start | `docker compose logs backup` | a checked backup | PASS: 296 KB dump + files tarball | — |
| DEP-10 | Install v0.10.1 bundle, image from file | `host/load-image.sh <file>` | image loaded | PASS | — |
| DEP-11 | Move a lab in (README "Moving an existing lab") | 0.10.1 demo SQLite; `build`, `up -d db`, `run … migrate-to-postgres.py`, `up -d` | every row copied | PASS: "389 rows in 33 of 84 tables, row counts verified"; my own count of all 85 tables SQLite vs Postgres: identical | 10, 11-* |
| DEP-12 | Migration race: `up -d db` then `run` immediately | 3× on fresh volumes | works | PASS 3/3 (~4 s each) | 96 |
| DEP-13 | Migrate into a database the app already filled | `run … migrate-to-postgres.py` against the fresh stack | refused, nothing written | PASS: refused, counts unchanged (message gives no next step, F-15) | 97 |
| DEP-14 | Copy uploads (`docker compose cp …/. app:/data/uploads/`) | 1 file | file in volume | PASS; copied files are `root:root` (F-15) | — |
| DEP-15 | Use 0.10.1 through Caddy | alex signs in (browser), makes a write API token, adds 5 reagents via API, uploads a file via the notebook upload | saved | PASS (201 ×5, file served back) | 12, 13 |
| DEP-16 | Upgrade 0.10.1 → 0.10.2 exactly as BUNDLE.md | `exec backup backup.sh`; unpack 0.10.2 over; `host/load-image.sh && docker compose up -d --build` | same data, new version | PASS: all 85 tables' counts identical (401 rows), 5 items, both uploads present, log clean, app 0.10.2 healthy | 14, 15, 16, 17 |
| DEP-17 | "Updating went wrong": is the pre-update backup the newest? | list `/backups/db` after DEP-16; repeat `up -d --build` with no change | newest = the one before the update | **FAIL**: `up -d --build` recreates `backup` every time here, and its start-up backup (of the upgraded DB) becomes the newest (F-03) | 19 |
| DEP-18 | RUNBOOK bundle update uses `docker compose up -d` (no `--build`) | append a marker to `backup/backup.sh`, `up -d`, read the script in the container | new scripts in use | **FAIL**: old script kept until `--build` (F-06) | 18 |
| DEP-19 | Is the `restore` image ever rebuilt? | marker in `backup/restore.sh`, `up -d --build`, then `--profile restore run … tail` | new restore.sh | **FAIL**: backup service has it, restore service still old (F-06) | 24 |
| DEP-20 | Put 0.10.1 back (RUNBOOK) | unpack 0.10.1 bundle, `load-image.sh`, `up -d` | 0.10.1 runs on the data | PASS: healthy, counts unchanged | 20, 21 |
| DEP-21 | Restore the backup taken before the update, on 0.10.1 | add "after-rollback" item; `stop app`; `--profile restore run restore <pre-update dump> <files>`; `start app` | exactly the pre-update data | PASS: counts == before-upgrade; new item gone; old DB kept as `biomanager_before_…`; sign-in works | 22, 23, 25 |
| DEP-22 | Upgrade again with the RUNBOOK's commands verbatim | backup; `tar -xzf`; `host/load-image.sh`; `docker compose up -d`; `curl …/healthz` | ok | PASS | 26 |
| DEP-23 | `restore-test.sh` | `docker compose exec backup restore-test.sh` | passes | PASS in 1.8 s (users 4/4, mice 39/39 …) | 30 |
| DEP-24 | Real restore of a deleted record | delete reagent "UPG-before-3" in the browser; add a newer item; restore newest backup (RUNBOOK "Restore a backup") | deleted record back, newer item gone (documented) | PASS | 31, 33 |
| DEP-25 | Restore with the app still running | `--profile restore run restore …` | refused | PASS: "2 connection(s) … Stop the app first" | 34 |
| DEP-26 | Restore with a mistyped files path | db path right, files `…/biomanager-<time>.tar.gz` (missing `-files`) | refused before anything changes | **FAIL**: DB replaced, every file in `/data` moved aside, tar fails; app then starts with a **new** `secret_key` and an **empty** uploads folder (F-02) | 34 |
| DEP-27 | Drop a kept database | RUNBOOK `DROP DATABASE "biomanager_before_<time>"` | dropped | PASS | — |
| DEP-28 | Off-site with restic (local repository) | `RESTIC_REPOSITORY=/offsite/biomanager` + password in `.env`, extra mount, `up -d --force-recreate backup` | repo created, copy sent | PASS: created, "sent off-site" (4 s) | 40 |
| DEP-29 | Restore test reads off-site back | `restore-test.sh` | passes both | PASS | 41 |
| DEP-30 | "The server is lost", from off-site, verbatim | new stack, same DOMAIN/RESTIC_*, new POSTGRES_PASSWORD, empty SECRET_KEY; `up -d`; RUNBOOK step 4 commands in order | the lost lab comes back | **FAIL (critical)**: the new server's start-up backups of its **empty** DB were sent off-site first; `restic restore latest` picked one; the lab restored has 0 users, 0 mice (F-01) | 43–46 |
| DEP-31 | Same, restoring the right snapshot by ID | `restic restore 3f820c30 …`, restore, start | lab back | PASS: all 85 tables identical to the original at the snapshot; alex signs in; `secret_key` carried over | 47, 48, 49 |
| DEP-32 | Off-site retention (30 d / 12 w / 24 m) | `restic forget --dry-run` with backup.sh's grouping and keep-1 policies | old snapshots would be forgotten | **FAIL**: every snapshot is its own group, nothing is ever forgotten (F-05) | 50 |
| DEP-33 | Admin locked out: list accounts | `docker compose exec app python scripts/reset-password.py` | list | PASS | 60 |
| DEP-34 | Reset + promote from the CLI | `reset-password.py sam --admin --enable` on a pty, password typed twice; sign in as sam in the browser | works, nothing in history | PASS | 61 |
| DEP-35 | Someone joins | Chromium: casey signs up → sign-in shows "waiting for a lab admin"; alex → Manage users → **Approve** → OK; casey signs in | approved member | PASS | 62-* |
| DEP-36 | Someone leaves | alex → **Disable** on casey; casey's next page; casey's own API token | signed out at once, token dead | PASS: redirected to /login; token 200 → 401 | 62, 63 |
| DEP-37 | "Colony overview: reassign their cages and animals" | open /admin/colony as admin | a way to reassign | WARN: the page shows who holds what but has no reassign control; "Open" goes to the whole colony (F-12) | 64.png |
| DEP-38 | The site is down | `stop app` → healthz 502; `up -d` → ok. `stop db` → 503 "database unavailable"; `up -d` → ok | RUNBOOK steps recover it | PASS | 65 |
| DEP-39 | Rotate SECRET_KEY | set in `.env`, `up -d`; reuse a saved signed-in browser session | everyone signs in again | PASS: old session → /login; fresh sign-in works | 66 |
| DEP-40 | Rotate POSTGRES_PASSWORD | RUNBOOK `ALTER USER …`, `.env`, `up -d` | nothing noticed | PASS: db/app/backup recreated, healthy, backup + off-site OK; a wrong password is refused over the network | — |
| DEP-41 | Guest access without Funnel | alex → account menu → Guests → **Make a code**; code used on the lab site; the internet-facing Caddy site (host-only port) probed; **End now** | code page only from "internet"; access ends | PASS: /, /login, /register, /home, /api → 302 /guest; POST /login 403; wrong code 401; right code 302; after End now guest signed out and code refused | 67-* |
| DEP-42 | Entry header can't be forged on the lab site | `X-BioManager-Entry: internet` to :443 | ignored | PASS (Caddy strips it; 8081 bound to 127.0.0.1 only) | 104 |
| DEP-43 | Watchdog with the README's default `BACKUP_DIR=./backups` | `watchdog.sh` once (no ntfy topic; DEPLOY_DIR/STATE_DIR set) | backup checks OK | **FAIL**: looks in `/opt/biomanager/backups`: "last good backup is 277777 hours old", restore-test, offsite, offsite-restore-test all alert; with BACKUP_ROOT set right they pass (F-04) | 70, 71 |
| DEP-44 | Watchdog site/certificate checks with `TLS=internal` | the watchdog's own curl and openssl commands against the running Caddy | OK | **FAIL** (emulated; this sandbox has no DNS for the name): curl without Caddy's root → verify error → "site"; leaf cert lives 12 h → "expires in 0 days" < 14 → "certificate" (F-04) | 72 |
| DEP-45 | site/server.html `.env` lines with trailing `# comments` | paste them, `docker compose config`, and the watchdog's `grep \| cut` | same values | FAIL: compose strips comments, the watchdog's DOMAIN becomes `192.168.1.50   # or the DNS…` (F-07) | 98 |
| DEP-46 | server.html `sudo deploy/host/install.sh` | run from the deploy folder the page `cd`s into | installs | FAIL: no such file (F-07) | 99 |
| DEP-47 | Weekly `maintenance.sh` | run once with DEPLOY_DIR set, no ntfy | backup, pull, build, up | WARN (sandbox): backup OK, then Docker Hub 429 on pull → "weekly update failed", nothing changed (correct behaviour) | 100 |
| DEP-48 | Backup service goes unhealthy after 26 h | set `last-success` to 27 h ago, run `healthcheck.sh` | exit 1 | PASS (exit 1; 0 after putting it back) | — |
| DEP-49 | `TLS=files` | self-signed cert in `deploy/certs/`, `TLS=files`, `up -d` | Caddy serves it | PASS | 101 |
| DEP-50 | Rotate the restic password (RUNBOOK order) | `restic key add` (pty), then `restic key remove` the old one | old key removed | FAIL: "refusing to remove key currently used"; works in the order add → `.env` → recreate backup → remove (F-10) | 102, 103 |
| DEP-51 | "Look at an old backup: run a restore test on it" | `restore-test.sh /backups/db/<oldest>.dump` | tests that one | WARN: the argument is ignored, the newest is tested and dropped (F-10) | 105 |
| DEP-52 | A schema upgrade and going back | 0.9.0 lab (via `BIOMANAGER_IMAGE`) → 0.10.2 → 0.9.0 without restore | log line; old version refuses or the RUNBOOK's restore is needed | PASS: "Upgrading the database from 0001_baseline to 0005_api_tokens…" as documented; counts equal except 5 retired mouse-status presets (by design, `app/services.py:130-140`). WARN: 0.9.0 then starts healthy on the 0005 schema with no warning (F-11) | 92, 93, 94 |
| DEP-53 | Linux desktop download | `BioManager-Linux.tar.gz` from latest | 0.10.2 | PASS: 284 MB, `_internal/VERSION` 0.10.2 | — |
| DEP-54 | Linux desktop headless | `xvfb-run ./BioManager/BioManager`, HOME in work dir, `BIOMANAGER_PORT` pinned | window + local server | WARN: GUI fails (`libEGL.so.1`, then `libwayland-server.so.0` missing: system libraries the tarball does not bundle); its local server answered `/healthz` ok and `/register` 200 (no setup-code field) before exiting; data folder `~/.local/share/Biomanager/{data,uploads}` as the README says (F-14) | 80, 81, 82 |
| DEP-55 | Update check against the latest release | `desktop_updates.check(manual=True)` from the 0.10.2 source, as 0.10.2 / 0.10.1 / 0.9.0 | right answers | PASS: 0.10.2 "current"; 0.10.1 and 0.9.0 offered 0.10.2; asset `BioManager-Linux.AppImage` with sha256; the tar.gz can't self-install (as documented) | 83 |
| DEP-56 | Survives a host-wide SIGTERM to gunicorn | incidental (see deviations) | restarts | PASS: all apps healthy again in ~5 s | — |
| DEP-57 | Local backups per restart | count `/backups/db` during a working session | nightly history kept | WARN: every recreate of `backup` (update, secret change, force-recreate) adds a backup; `KEEP_LOCAL` counts files, not days (F-15) | 19 |

**Totals:** 57 rows: **37 PASS, 11 FAIL, 9 WARN** (of the WARNs, DEP-03 and DEP-47 are sandbox limits).

## 3. Findings

### F-01 (critical) "The server is lost → from off-site" restores an empty lab
- **Steps:** a server with off-site backups (DEP-28). New server as RUNBOOK "The server is lost" steps 3–4: same
  `DOMAIN`, same `RESTIC_*` in `.env`, `docker compose up -d`, then
  `docker compose up -d --force-recreate backup`, `restic snapshots`, `restic restore latest --tag biomanager --target /backups/from-offsite`, `ls …`, restore, start.
- **What happened:** the new server's backup service backs up once when it starts (`schedule.sh:22`) and again at the
  force-recreate. Its database is the new, empty one; `backup.sh:12` only checks that the `users` *table* exists, so
  both empty backups pass and go off-site under the same tag and host. `restic restore latest` then restores the
  newest, i.e. the empty lab. `ls` shows one dump with a timestamp from minutes ago, nothing that says it is wrong.
  After the restore: `users 0, mice 0`. The real copy is still in the repository (snapshot `3f820c30`, DEP-31).
- **Expected:** the lost lab. A lab manager in a disaster will not know to compare snapshot times.
- **Evidence:** 44 (two empty snapshots appear), 45, 46; recovery 47/48.
- **Suspected cause / fix direction:** `backup.sh:12` (`SELECT 1 FROM users LIMIT 1` succeeds on an empty table)
  plus `BACKUP_ON_START=1` on a server that has never had data; RUNBOOK line 139 (`restore latest`). Not sending
  off-site while `users` is empty, and/or restoring a snapshot chosen from `restic snapshots` by time, would avoid it.

### F-02 (high) A mistyped files path in a restore empties the app's data folder
- **Steps:** `docker compose stop app`; `docker compose --profile restore run --rm restore /backups/db/biomanager-X.dump /backups/files/biomanager-X.tar.gz` (a plausible typo: the files are named `biomanager-files-X`); `docker compose start app` (the RUNBOOK's next line).
- **What happened:** the database is replaced, then every file in `/data` (uploads **and `secret_key`**) is moved to
  `.before-restore-<time>/`, then `tar` fails. No "previous ones are in …" line is printed. The app starts, makes a
  **new signing key** (all sessions end; stored Google tokens can no longer be decrypted) and serves an **empty
  uploads folder**: every attachment and image 404s. Recoverable only by moving files back by hand.
- **Expected:** refuse before changing anything, as it does for a missing dump.
- **Evidence:** 34. **Cause:** `deploy/backup/restore.sh:14-15` validates only the dump; the files tarball is first
  touched at `:37-38`, after the move.

### F-03 (high) After `up -d --build`, the newest backup is the upgraded database, not the one before
- **Steps:** update as BUNDLE.md / README "Updating" / server.html say (`… && docker compose up -d --build`), then
  `docker compose exec backup ls -lt /backups/db`.
- **What happened:** on this Docker (29, containerd image store) `--build` makes a new backup image ID even with no
  change, so `backup` is recreated every time, and its start-up backup runs after the new app is healthy (it
  `depends_on` app). The RUNBOOK's "Updating went wrong" says "The backup taken just before is the newest in
  `/backups/db`", so someone rolling back a bad schema upgrade would restore the *post-upgrade* dump. The right one is
  the second newest.
- **Evidence:** 19 (171108Z = before, 171132Z = after), and the repeat with no change in the log above DEP-17.
- **Cause:** `schedule.sh:22` (backup on every container start) + RUNBOOK line 214. Also, the RUNBOOK's own update
  path uses `up -d` without `--build` (F-06), so the two documents disagree.

### F-04 (medium) The watchdog alerts falsely on a default install
- (a) `host/watchdog.sh:16` defaults `BACKUP_ROOT=/opt/biomanager/backups`; `.env.example:30` and the README default
  `BACKUP_DIR=./backups` (= `/opt/biomanager/Biomanager/deploy/backups`), and `install.sh` never tells the watchdog.
  Result: backup, restore-test, offsite and offsite-restore-test alerts from the first run, forever (and real backup
  failures can't be told apart). server.html sets `BACKUP_DIR=/opt/biomanager/backups`, so it only bites README
  followers. Evidence 70 vs 71.
- (b) With `TLS=internal` (the default): the site check (`watchdog.sh:57`, plain `curl https://$DOMAIN/healthz`)
  fails because the server itself doesn't trust Caddy's root; the certificate check gets Caddy's 12-hour leaf
  certificate, 0 days left, below `CERT_MIN_DAYS=14`. Both alert every 6 hours. Evidence 72 (emulated with the
  watchdog's own commands against the running Caddy; the sandbox couldn't resolve the name for the script itself).

### F-05 (medium) Off-site retention never deletes anything
- `backup.sh:63` runs `restic forget --tag biomanager --host biomanager --keep-daily 30 …`; restic groups by host
  **and paths** by default, and every snapshot's paths contain its timestamp, so each snapshot is alone in its group
  and is kept. The README's "kept for 30 days, 12 weeks and 24 months" doesn't happen; the bucket grows by one full
  dump a night (dumps are compressed, so little dedup). Evidence 50 (dry-run keeps each snapshot as "daily, weekly,
  monthly" of its own group). Likely fix: `--group-by host,tags`.

### F-06 (medium) Updated backup/restore scripts don't reach the running containers
- The RUNBOOK's bundle update ends with `docker compose up -d` (no `--build`), and `load-image.sh` prints the same.
  The backup image is only built when missing, so a newer bundle's `backup/*.sh` are never used (DEP-18, evidence 18).
- The `restore` service is behind a profile: neither `up -d --build` nor `maintenance.sh`'s `build --pull` builds it.
  Once a lab has restored once, every later restore uses that first `restore.sh`, whatever the bundle says
  (DEP-19, evidence 24). A fix to F-02 would not reach labs that already restored.

### F-07 (low) server.html commands that fail as written
- `sudo deploy/host/install.sh` (server.html lines 204, 290, 330) is run from `/opt/biomanager/Biomanager/deploy`,
  where the path is `host/install.sh` (evidence 99). The README's absolute path is right.
- The `.env` examples carry trailing `# comments`. Compose strips them, but the watchdog's and `offsite-setup.sh`'s
  `grep | cut` do not: the watchdog then checks `https://192.168.1.50   # or the DNS name IT gave you/healthz`
  (evidence 98). Either drop the inline comments or parse like compose.

### F-10 (low) Two RUNBOOK backup sentences don't match the scripts
- Backup password rotation: "`restic key add`, then `restic key remove` the old one, and update `.env`". The remove
  is refused while `.env` still holds the old password (evidence 103). The order that works: add → update `.env` →
  `docker compose up -d` → remove (verified).
- "To look at an old backup without replacing anything, run a restore test on it": `restore-test.sh` takes no
  argument, always tests the newest, and drops the copy (evidence 105). There is no documented way to look inside an
  older backup.

### F-11 (low) The previous version runs silently on an upgraded database
- RUNBOOK: "the previous version can't open the upgraded database". In practice 0.9.0 started **healthy** on the
  `0005_api_tokens` schema with no warning in the log, and pages worked (evidence 94). So a lab can run old code on a
  new schema without noticing; the app doesn't check that its code knows the database's Alembic revision.

### F-12 (low) "Someone leaves: Colony overview → reassign" has no control there
- /admin/colony lists each person's cages but has no reassign action, and "Open" goes to the whole colony. The way
  seems to be the Mouse list's bulk owner change (`/colony/mice/bulk-update`, field `owner`); the RUNBOOK doesn't say.

### F-13 (low) Restricted networks can't build the backup image
- The bundle ships the app image as a file (`load-image.sh`) but builds the backup image on the server from Debian
  and PostgreSQL apt mirrors. A department server behind a proxy that allows GitHub but not Debian mirrors (like
  this one) can't start the stack; the error is an apt 403 inside a compose build. Not a problem for most labs, but
  there is no note or prebuilt image.

### F-14 (low) Linux tar.gz: missing system libraries give a developer error
- On a system without `libEGL.so.1` / `libwayland-server.so.0` the app exits with pywebview's "You must have either
  QT or GTK with Python extensions installed", printed only to the terminal. The guide's Linux troubleshooting covers
  only the AppImage/libfuse2. (A normal desktop distribution has these libraries; this container doesn't, so the
  window itself was not tested.) Also, the desktop logs a "setup code" line although its register page doesn't ask
  for one (evidence 82).

### F-15 (low) Smaller things a lab manager would trip on
- `migrate-to-postgres.py` into a used database says "Migrate into an empty database" but not how to get one
  (evidence 97).
- `docker compose cp` of uploads leaves the files `root:root` in the app volume (the app can still read them; it
  can't overwrite them).
- Each recreate of `backup` (update, secret change, `--force-recreate`) takes a backup; `KEEP_LOCAL=30` counts
  files, so a busy troubleshooting day shortens the nightly history (five backups in five minutes in evidence 19).
- `biomanager_before_*` databases and `/data/.before-restore-*` folders pile up with nothing to remind anyone.
- The first-start "setup code" line is printed twice.

## 4. Numbers

| | |
| --- | --- |
| Bundle | 28 KB; app image file 85 MB (434 MB loaded); Linux desktop tar.gz 284 MB |
| Fresh install | `load-image.sh` 4.4 s; `up -d --build` to healthy 17.7 s |
| Move-in | 389 rows / 33 tables in ~4 s (3 runs 3.97–4.29 s including db start) |
| Backup | 296–316 KB dump + 4 KB files tarball, ~1 s; restore-test 1.8 s; first off-site copy (repo init) 4 s |
| Restore | database + files ~2 s for this lab |
| Row checks | 85 tables compared at: SQLite → Postgres, before/after upgrade, after rollback, after restore, original vs replacement server: identical every time (except the documented 0.9.0 preset cleanup) |

## 5. Re-running

Scripts in `scripts/` (each has a usage line): `browser_register.py` (first admin + sign-in), `make_token.py`,
`api.py`, `upload_file.py`, `browser_post.py`, `join_leave.py`, `leaver_token.py`, `guest_flow.py`,
`session_state.py`, `shot.py`, `tty_answer.py` (answers password prompts on a pty), `rowcounts.sh`, `healthz.sh`,
`update_check.py`; sandbox build/port overrides in `scripts/sandbox/`. Evidence in `evidence/` (numbers match the
table). Test-only tokens and passwords were deleted; all stacks and volumes were removed.
