# BioManager 1.0 pre-release test: robustness (load, concurrency, failure)

## 1. Scope and environment

- **Code**: `the repository` at `76371cf` (v0.10.2 + icon), used read-only. `scripts/upgrade-check.py`
  runs `git worktree add`, so it was run from a local clone (`robustness/repo`) and nothing was written to the source checkout.
- **Server mode**: gunicorn 23 with the repository's `gunicorn.conf.py` (preload, gthread, 4 threads, 60 s timeout),
  `wsgi:app`, `BIOMANAGER_HTTPS=0`, loopback on port 5104 or 5114 (`evidence/scripts/serve.sh`). The worker count is the default:
  **1 worker on SQLite, 3 on PostgreSQL**.
- **Databases**: SQLite (journal mode `delete`, the app's default), and PostgreSQL 16 (`postgres:16` container
  `pg-robust`, port 55504). The PostgreSQL labs were made with `scripts/migrate-to-postgres.py` from the SQLite ones.
- **Data**:
  - the demo lab (`scripts/demo-data.py`: 4 people, alex = admin, 39 mice);
  - the big lab (`scripts/load-test.py`: 100,000 mice, 25,000 cages, 16,666 litters, 50,000 weights, 3,333 tanks, 16,666 fish rows,
    10,000 vials, 40,000 inventory items and 2,500 notebook pages, a 34 MB SQLite file);
  - demo labs made by v0.7.0 and v0.10.1, and by every tag through `upgrade-check.py`.
- **Clients**: Python `requests` sessions that really sign in (cookie session, `Origin` header) and post the same form fields the
  pages post. Row forms were scraped from the rendered sheet (`evidence/scripts/bm.py:scrape_form`). One test used a real browser
  (Playwright Chromium).
- **Machine**: 4 vCPU and 15 GB RAM, shared with five other test agents (load average 3–5). Timings are therefore noisy upper
  bounds. Compare them with each other, not with a quiet server.
- **Not tested**: the full Docker stack (Caddy, the backup container, the watchdog timers), restic off-site copies, a gunicorn
  worker timeout (no request ran for 60 s), and memory limits or OOM.

## 2. Test log

| ID | What | How (steps, users, data) | Expected | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| ROB-01 | Build the big lab | `scripts/load-test.py biglab` | Builds and times pages | PASS: 86 s in all (fill 5 s). Its own in-process timings are in `load-test-sqlite.txt` | evidence/load-test-sqlite.txt |
| ROB-02 | Main pages at 100k mice, SQLite, over HTTP | gunicorn 1 worker; alex; each page fetched twice and the second timed (`time_pages.py`) | Mouse and cage sheets 2–3 s, 30–60 MB (docs/DEVELOPMENT.md) | WARN: mice 3.0 s / 33 MB (as documented). Also cages 5.3 s, litters 6.9 s, fish 6.1 s, reagents 3.6 s, calendar feed 2.4 s, `ended=all` mice 16.5 s / 209 MB. Table in §4 | evidence/timings-big-sqlite.txt/.json |
| ROB-03 | The same on PostgreSQL | gunicorn 3 workers, `bm_big` | Same or faster ("a lab server on PostgreSQL is usually faster") | WARN: slower on every page. Calendar feed 5.1 s, My data export 13.8 s, fish 7.6 s | evidence/timings-big-pg.txt/.json |
| ROB-04 | Exports at 100k mice | CSV, "xlsx", PDF of the mouse sheet, `scope=all` | Complete, under ~10 s | PASS: CSV 100,039 rows / 7.9 MB in 7.5 s; "xlsx" (really tab-separated `.xls`) 7.8 s; PDF view 6.8 s / 8.9 MB. Settings → export zip 5.1 s (SQLite), 13.8 s (PG) | evidence/timings-big-sqlite.txt |
| ROB-05 | Four people open big sheets at once | alex / sam / jordan / priya open mice, cages, reagents and litters together; a fifth session polls /home | Home stays usable | WARN: SQLite, Home 4.4 s median and 5.9 s max; litters took 25.4 s. PG (3 workers), Home 8.0 s median and 8.9 s max. Worker RSS up to 514 MB | evidence/big-conc-sqlite.txt, big-conc-pg.txt |
| ROB-06 | Search at 100k | `/search?q=Ai14`, `100`, `L000123` | Fast, finds records | PASS: 105–314 ms; finds cages, litters and mice by ID | evidence/timings-big-*.txt |
| ROB-07 | Same mouse field, 80 saves at once | 8 admin sessions × 10 autosaves of the same mouse's note (`conc.py` C1) | No errors; final value is one that was sent; one audit entry per change | PASS on both: 80/80 ok, 80 audit entries | evidence/conc-sqlite-part1.txt, conc-pg.txt |
| ROB-08 | Two people, same mouse row, different cells | A changes Sex; B (row loaded before) changes Note (C2) | Both edits kept | **FAIL** on both: A's Sex change silently reverted; both saves answered `ok` | same |
| ROB-09 | Stale row reverts other changes | B has the mouse sheet open. A sacs the mouse, moves it to a new cage, sets its transgenes, or gives it to sam. B then edits only the Note in the old row (`stale_row.py`) | A's change kept | **FAIL** on both: all four reverted. A sac'd mouse comes back alive (status and date of death restored), and the cage move, transgenes and owner are undone. B sees "All changes saved" | evidence/stale-row-pg.txt, stale-row-sqlite.txt |
| ROB-10 | Cages dropped on the same rack cell at once | 8 sessions each drop a different cage on one empty cell, over 15 cells; then 2 at once onto an occupied cell (C3, C3b) | One cage per position | **FAIL** on both: 4 cells double-booked; up to 5 cages (SQLite) and 6 cages (PG) in one cell. Every request answered 200 ok | evidence/conc-*.txt, pg-double-booked.txt |
| ROB-11 | Add many at the same time | 6 sessions × 3 rounds × 40 mice, cage "new", released together (C4) | All created, no duplicate IDs | SQLite PASS: 18/18 batches, 720 mice with consecutive IDs. PG **WARN**: 15/18 refused with "That cage ID is already used. Choose another."; 3 created; nothing duplicated or half-written | evidence/conc-sqlite-part2.txt, conc-pg.txt |
| ROB-12 | New mouse pressed at the same time | 8 sessions × 10 "New mouse" (`/colony/mice/new-record`) (C4b) | 80 mice | **WARN** on both: 37 of 80 created; 43 refused with "That mouse ID is already used. Choose another.", on a button that picks the ID itself | same |
| ROB-13 | ID invariants after the concurrent creates | DB queries (C4c) | Unique IDs, no gaps, an audit create per mouse | PASS: 0 duplicates, 0 gaps among the new IDs, 757/757 (SQLite) and 157/157 (PG) audit creates, 0 duplicate cage IDs | same |
| ROB-14 | CSV import of mice at the same time | 4 × 100-row CSVs without IDs (C5) | All imported, or a clear error | **WARN** on both: 1 imported, 3 refused. The endpoint answers a 302 redirect to /home instead of JSON, so the page shows "Network error: SyntaxError…" and the reason is flashed on a later page. No partial rows | same |
| ROB-15 | CSV with a repeated or colliding mouse_id | File A: same `mouse_id` twice. File B: a blank row, then the next free ID. Dry run, then import (C5b, `csv-import-dup.txt`) | Dry run reports the clash; import skips the bad row | **FAIL**: dry run says `ok`, 2 rows, both with the same ID. The real import refuses the whole file with a redirect to /home ("That mouse ID is already used"). Nothing saved | evidence/csv-import-dup.txt |
| ROB-16 | Weaning the same cage twice at once | Cage with 6 pups at P25; 2 sessions post the same Wean & distribute (3 F, 3 M into new cages) together (C6) | One set of new cages | WARN on both: 4 new cages instead of 2; 2 left empty; pups correctly 3 + 3; litter weaned once | evidence/conc-*.txt |
| ROB-17 | The same wean form resubmitted later | Same form after the first finished (C6b) | Refused | PASS: "Not moved: mouse N is not in cage …", no new cages | same |
| ROB-18 | Double-submit over HTTP | The same New mouse dialog, and the same Add many of 10, posted twice at the same instant (C7) | One record or one batch | WARN: New mouse → 1 (the other refused by the ID collision). Add many → 20 mice on SQLite; 10 on PG (second refused) | same |
| ROB-19 | Double-click in a real browser | Chromium double-clicks "Create 5 mice", and clicks it twice fast (`dblclick.py`, quiet server) | One batch | PASS: 5 mice each time; only one POST in the server log | evidence/dblclick.json |
| ROB-20 | Undo a batch while someone edits its records | Bulk "Set Note" on 12 mice, then Undo while another session autosaves the note of 6 of them (C8) | Undo refuses, or keeps the later edits | **FAIL** on both: undo ran ("Undid 12 change(s)"). 1 of the 6 later edits, acknowledged `ok`, was overwritten | evidence/conc-*.txt |
| ROB-21 | The same batch undone twice at once | 2 admin sessions press Undo together (C8b; `double_undo.py` × 4 on PG) | Second is refused ("Already undone") | WARN: both run; 2 "undo of batch #N" batches recorded. For Add many, the second says "Undid 2 change(s) — 8 could not be reversed". No 500s | evidence/conc-*.txt, double-undo.json |
| ROB-22 | Undo an Add many while its mice are edited | Undo 10 new mice while another session autosaves 3 of them (C8c) | Edits refused cleanly | WARN: SQLite, one autosave answered **500** (`StaleDataError`). PG, the edits answered `ok` and the mice were then deleted by the undo | evidence/gunicorn-sq1.log (17:18:18) |
| ROB-23 | New mouse after re-entering an old mouse | Delete mouse 5, then import it again by CSV with `mouse_id=5`. Then press New mouse 3 times and use the New mouse dialog (`next-mouse-id.txt`) | New mice get 40, 41… | **FAIL**: every press refused with "That mouse ID is already used. Choose another." New mouse stays broken until a higher-numbered mouse is created later | evidence/next-mouse-id.txt |
| ROB-24 | Kill the worker mid-import (SQLite) | 20,000-row CSV import (5 s); SIGKILL the worker at 3.0, 4.6 and 4.9 s (`fail_kill.py`) | All or nothing, DB healthy, back up by itself | PASS: 0 rows kept each time; integrity ok; the master restarted the worker in 0.3–0.4 s; save and Home fine | evidence/kill-sqlite-d*.json |
| ROB-25 | Kill the whole server mid-import (SQLite) | SIGKILL master and worker at the same points, then start again | Same | PASS: 0 rows kept, integrity ok, no leftover journal, up in 2.2–2.6 s | same |
| ROB-26 | Kill workers or server mid-import (PG) | 3 workers; the 20,000-row import takes 20 s on PG; kills at 2.5 and 4.5 s | Same | PASS: 0 rows kept, back in 0.6–1.0 s (worker) and 3.5–3.8 s (server) | evidence/kill-pg-d*.json |
| ROB-27 | PostgreSQL stops while people work | 3 users loop Home / note save / mouse sheet; `docker stop` at 10 s, `docker start` at 25 s (`pg_outage.py`) | Clear errors while down; recovers by itself; nothing acknowledged is lost | WARN: 429 requests answered with the bare "500 Internal Server Error" page while it was down. Recovery was immediate (first 200 at 25.4 s; the last errors at 25.5 s). The last acknowledged save is in the DB | evidence/pg-outage.json |
| ROB-28 | Data disk fills up (SQLite on a 3 MB tmpfs) | Add many × 200 mice with long notes until full; then read, small save, make room, restart on a full disk (`disk_full.py`) | A clear message; DB not damaged; recovers | WARN: the 13th batch got the bare 500 page (`database or disk is full`). The failed batch left nothing; integrity ok; reads still worked; writes worked again as soon as there was room, with no restart; a server started on a 100%-full disk served pages and failed writes with 500 | evidence/disk-full.json, disk-full-restart.txt |
| ROB-29 | SQLite file locked by another program | Another process holds `BEGIN IMMEDIATE`, then `BEGIN EXCLUSIVE`, for 12 s (`sqlite_lock_corrupt.py` L1) | Waits, then a clear message | WARN: after 5.0 s, bare 500 ("database is locked") even for GET /home and GET /colony (they write on GET: `load_current_user`, `remember_milestones`). Works again once the lock is released | evidence/sqlite-lock-corrupt.json, gunicorn-lock.log |
| ROB-30 | A long import while others work (SQLite) | 3 × 20,000-row imports (14–30 s each) while 3 people save and open Home every 0.2 s (`contention.py`) | No errors | PASS: 137/137 saves, 137/137 Home, 0 errors. Slowest save 4.4 s (near the 5 s lock timeout); Home up to 3.5 s | evidence/contention-sqlite.json |
| ROB-31 | Damaged SQLite file | 12 KB of garbage in the middle; the file truncated to half; a text file in its place (L2) | Refuses to start with a clear message; `dbtool check` says it is damaged | WARN: refuses to start (good) with only a Python traceback (`database disk image is malformed` / `file is not a database`). `dbtool.py check` crashes with a traceback instead of reporting | evidence/sqlite-lock-corrupt.json, gunicorn-corrupt-*.log |
| ROB-32 | Zero-byte database file | `biomanager.db` emptied to 0 bytes (a sync client or full disk can do this) | Refuse, or warn loudly | WARN: starts as a brand-new empty lab and prints a setup code to create a new first admin. No sign that a lab was there | same |
| ROB-33 | `upgrade-check.py`, SQLite | Every tag v0.2.0 … v0.10.1 (in the clone) | All ✓ | PASS: 13/13 "upgraded, nothing lost, pages open" (77 s) | evidence/upgrade-check-sqlite.txt |
| ROB-34 | `upgrade-check.py --postgres` | Same, against `pg-robust` | All ✓ | PASS: 13/13 (126 s) | evidence/upgrade-check-pg.txt |
| ROB-35 | Copy before upgrade | Open v0.7.0's demo lab with this version; compare the copy in `backups/` with the original | A copy identical to the original; the pages open | PASS: `before-upgrade-0001_baseline-to-0005_api_tokens-*.db`, same tables, columns and row counts; integrity ok. The only row difference after the upgrade is `dropdown_options` 15→10 (tidied on purpose). A v0.10.1 DB (already at head): no changes, no copy | evidence/upgrade-kill-v070.json, upgrade-kill-v0101.json |
| ROB-36 | Server killed during the upgrade | v0.7.0 lab: SIGKILL the master (which runs the upgrade under preload) at 0.3–1.6 s, 7 times; then a normal start | Upgrade completes, same shape as a clean upgrade, nothing lost | PASS: killed at revision 0001 three times (once after the copy was made); every restart finished at 0005 with the clean upgrade's shape; integrity ok | evidence/upgrade-kill-v070.json |
| ROB-37 | `dbtool backup` on a live SQLite lab under writes | 3 backups during the SQLite soak | Consistent copies | PASS: integrity ok, row counts grow 279 → 284 → 289 | evidence/dbtool-backup-live.txt |
| ROB-38 | `dbtool restore` while the server runs | 2 users keep adding mice; backup; 4 s later restore it without stopping the app (`restore_live.py`) | Refuse while the app runs, or restore safely | WARN: the restore went ahead. One page got 500 ("database disk image is malformed") during the copy, and the server kept writing into the restored file. The 200 mice added between backup and restore are only in the safety copy. Integrity ok this time | evidence/restore-live.json |
| ROB-39 | `deploy/backup/backup.sh` + `restore-test.sh` on a live PG lab | 3 runs during the PG soak, `KEEP_LOCAL=2`; then the restore test | Dumps valid; pruning; test passes | PASS: 3 dumps (316 KB); 2 kept; restore test passed (mice 124/129, audit 348/364) | evidence/backup-sh-pg.txt |
| ROB-40 | `deploy/backup/restore.sh` | Back up `bm_demo`, change data and files, restore dump + files; then again with a connection open | Restored; previous copy kept; refuses while connected | PASS: data and files back; `bm_demo_before_<time>` and `.before-restore-<time>/` kept; refused with "1 connection(s) … Stop the app first" | (output in session; `pgb2/`, `appdata2/`) |
| ROB-41 | `backup.sh` when the files archive fails | `APPDATA_DIR` missing (tar fails) | "BACKUP FAILED" | WARN: exits 2, which `schedule.sh` logs as "OFF-SITE COPY FAILED (local backup kept)". The DB dump is kept, the files archive is not, and a `.partial` file is left and never pruned | evidence/backup-sh-tarfail.txt |
| ROB-42 | Soak, SQLite, 12 min | 6 users (alex × 2, sam × 2, jordan, priya), mixed: pages, note saves, Add many × 5, rack moves, search, calendar feed, about 11 req/s (`soak.py`) | No errors, steady memory and files | PASS: 7,659 requests, 0 errors, 0 5xx. p95 ≤ 601 ms for every kind, max 1.0 s. Worker RSS 76 → 189 MB (rising steadily as the lab grew by 2,600 mice); open fds steady at 21 | evidence/soak-sqlite.json |
| ROB-43 | Soak, PG, 12 min | Same, 3 workers | Same | PASS: 7,285 requests, 0 5xx, one 409 on a note save (cause not found). p95 ≤ 684 ms, max 1.1 s. RSS 85 → 162–185 MB per worker; fds steady at 17–18 | evidence/soak-pg.json |
| ROB-44 | Invariants after the soaks | Integrity, duplicate IDs, double-booked cells | None | PASS: integrity ok, 0 duplicate mouse IDs, 0 double-booked cells (both DBs) | evidence/soak-idle-rss.txt |

**Totals: 44 tests: 22 PASS, 15 WARN, 7 FAIL.**

## 3. Findings

### F1: A stale mouse row silently undoes other people's changes, including a sac (critical: data corruption)
- **Steps**: B opens Colony → Mice. A (another tab or person) marks a mouse sac'd with **Sac** on the selection bar (or moves it
  with Set Cage, re-genotypes it, or changes its owner). B edits only that mouse's Note in the still-open sheet. It autosaves.
- **Happened**: B gets "All changes saved". The mouse is alive again: status and date of death are back as B's row showed them.
  The same happens to its cage, transgenes, owner, sex, litter and date of birth: whatever B's row showed is written back. This
  held on SQLite and PG (ROB-08, ROB-09). The audit log shows B's save as an ordinary edit.
- **Expected**: only the cell B changed is written, or the save is refused as out of date.
- **Evidence**: `evidence/stale-row-pg.txt`, `stale-row-sqlite.txt`, `conc-*.txt` (C2); script `scripts/stale_row.py`.
- **Suspected cause**: `static/sheet.js:80` posts the whole row (`new FormData(form)`). `app/app.py:957-1025`
  (`populate_mouse_from_form`) writes gender, status, owner, note, transgenes, cage, litter and DOB unconditionally.
  `date_of_death` has no `_was` copy, so `form_changed` (app/formutil.py:6) always counts it as edited. Only the cage's
  rack/position/location use the `_was` guard. After a save, the sheet refreshes only status, owner and litter from the reply
  (`app/app.py:2555`), so the rest of the row stays stale.

### F2: New mouse stops working after a lower-numbered mouse is imported (high: blocks work)
- **Steps**: delete a mouse (say #5) and re-enter it with Import CSV (`mouse_id=5`), or import any mouse whose number is below
  the highest. Then press **New mouse**, or save the New mouse dialog.
- **Happened**: every attempt is refused: "That mouse ID is already used. Choose another." This lasts until a mouse with a
  higher number is made some other way (Add many works). See ROB-23.
- **Suspected cause**: `app/services.py:689-707`. `next_mouse_id` returns `latest_mouse_record().mouse_id + 1`, where
  "latest" is the newest by `created_at`, not the highest number. `max()` is used only when there is no latest record.

### F3: Rack positions can be double-booked (high: wrong data shown)
- **Steps**: two or more people drop different cages on the same empty rack cell at about the same moment (ROB-10).
- **Happened**: every drop answered ok. 4 cells ended up holding 2–6 cages each, on SQLite and on PG. The grid can only show one
  of them.
- **Suspected cause**: `app/app.py:3446-3479` (`place_cage`) checks the holder and then writes, with no lock. There is no
  unique constraint on `(rack_id_fk, rack_row, rack_col)` (`app/models.py:278-280`). The same check-then-write is in the
  swap path.

### F4: Undo can overwrite an edit made while it runs (medium: data loss, rare)
- **Steps**: Undo a bulk edit while someone saves one of its mice (ROB-20).
- **Happened**: the undo ran. One later edit, acknowledged as saved, was reverted. Two Undos of the same batch at once both
  run and each records an undo batch (ROB-21).
- **Suspected cause**: `app/undo.py:61-95` (`blockers`) and the `is_undone` check (`undo.py:98-102`) are read before the
  revert, without a row lock (`SELECT … FOR UPDATE`) or a version check. The docstring promises that it "will not touch a
  record that has been changed again since the batch".

### F5: A CSV import with a repeated or colliding mouse_id passes the dry run, then fails as a whole (medium)
- **Steps**: import a CSV that has the same `mouse_id` twice, or a blank-ID row followed by a row whose ID is the next free
  number (ROB-15).
- **Happened**: the dry run says ok (preview shows two rows with the same ID). The import answers a 302 to /home rather than
  JSON, and `csv-import.js:107` shows "Network error: SyntaxError…". The real reason is flashed on the next page. The same
  happens when two imports run at once (ROB-14). No partial data (good).
- **Suspected cause**: `app/app.py:5256-5275`. The `existing` check cannot see rows added earlier in the same file (session
  `autoflush=False`) or the IDs reserved for blank rows. The IntegrityError handler (`app/app.py:372-397`) redirects any
  non-autosave request, including this JSON endpoint. Mouse CSV imports are also not wrapped in `audit.batch`, so unlike
  plasmid and order imports they cannot be undone from Batches.

### F6: Pressing "New mouse" or Add many at the same time often fails (medium)
- **Steps**: several people create mice at the same moment (ROB-11, ROB-12, ROB-18).
- **Happened**: nothing was duplicated or lost (unique indexes hold, and the IntegrityError handler turns the clash into a
  message). But people are told "That mouse ID is already used. Choose another." or "That cage ID is already used" for IDs
  they never chose: 43 of 80 New mouse presses, and 15 of 18 Add many batches on PG with cage "new".
- **Suspected cause**: IDs are read as `max+1` and inserted later: `app/services.py:693` and `710` (mice), `:740`
  `reserve_cage_ids` and `app/app.py:2696` `new_owned_cage` (cages). There is no retry on the unique violation. On SQLite,
  Add many happens to be serialised because `audit.batch` writes first.

### F7: Database trouble shows a bare "500 Internal Server Error" page (medium)
- **What**: PostgreSQL down (ROB-27), disk full (ROB-28), SQLite locked more than 5 s (ROB-29), a row deleted under an autosave
  (ROB-22, `StaleDataError`). Each answers the bare page with no app styling, no hint, and no JSON for autosave. Recovery
  afterwards was automatic and nothing acknowledged was lost.
- **Suspected cause**: there are handlers for `IntegrityError` and `DataError` (`app/app.py:372`, `399`), but none for
  `OperationalError` or `StaleDataError`. SQLite uses pysqlite's default 5 s busy timeout (`app/db.py:39`, no `timeout` in
  `connect_args`). GET pages also write (`app/app.py:285` `load_current_user`, `app/lab_routes.py:205`
  `remember_milestones`), so they fail too when the database is locked.

### F8: Big sheets are slow, and one person opening one blocks others (medium: a lab would notice)
- **Numbers**: see §4. Cages 5.3 s, litters 6.9 s, fish 6.1 s, inventories 3.5 s, calendar feed 2.4 s (SQLite) and 5.1 s (PG).
  Four people opening big sheets at once make Home take 4–9 s, and the litters sheet 25 s (ROB-05). PG with 3 workers was
  no better. docs/DEVELOPMENT.md mentions only the mouse and cage sheets ("2–3 s").
- **Suspected cause**: the calendar feed walks every cage and litter, with about 4,900 lazy loads per request
  (`app/services.py:1379`, `derive_auto_calendar_items`; profile in `evidence/profile-calendar-feed.txt`). Sheets render
  every row server-side (see the docs' own note on paging). On SQLite one worker (GIL) serves all rendering.

### F9: dbtool restore replaces the file under a running server (medium)
- **Steps**: `scripts/dbtool.py restore <backup>` while the app runs (ROB-38).
- **Happened**: it copies the file in place with `shutil.copy2` and prints "Restart the app." One request hit "database disk
  image is malformed" during the copy. The server went on writing into the restored file, and the rows made since the backup
  are only in the safety copy. The deploy `restore.sh` refuses while connections are open; this tool does not check.
- **Suspected cause**: `scripts/dbtool.py:128-141`. It does not check that the app is stopped or the backup is healthy, and
  the safety copy is also `copy2` rather than the backup API.

### F10: A zero-byte database starts as a new lab (medium)
- ROB-32: an emptied `biomanager.db` is treated as a first run. The empty lab starts and prints a setup code, with no warning.
  A lab whose file was truncated by sync or a full disk could start typing into an empty lab.
- **Suspected cause**: `app/upgrade.py:84` sets `fresh = not has_table("users")`, and `app/services.py:97-103` then starts
  empty.

### F11: Weaning the same cage twice at once makes extra empty cages (low)
- ROB-16: 4 new cages instead of 2, and 2 of them are left empty. The pups and the litter are correct.
- **Suspected cause**: `app/app.py:3819` has no lock on the source cage.

### F12: A damaged SQLite file gives only a traceback, and dbtool check crashes (low)
- ROB-31: the server refuses to start, which is correct, but the log shows only a Python traceback. `dbtool.py check` raises
  `DatabaseError` at `scripts/dbtool.py:75` instead of printing "integrity: damaged, restore a backup".

### F13: backup.sh misreports a failed files archive as an off-site failure (low)
- ROB-41: `tar` exits 2, so `backup.sh` exits 2 (`deploy/backup/backup.sh:30-32`). `schedule.sh:13-15` reads that as "OFF-SITE
  COPY FAILED (local backup kept)". `last-success` is not updated, so the watchdog still alerts later. The `.partial` archive
  is never pruned.

### Other observations (not counted as findings)
- Importing 20,000 mice by CSV takes 5 s on SQLite and 20 s on PG (one existence query per row).
- The "xlsx" mouse export is a tab-separated `.xls` file.
- Worker memory rose steadily in both soaks (to about 190 MB in 12 min), while the lab grew by about 2,600 mice. Memory was
  not measured on a fixed-size lab, so this is not shown to be a leak.
- One PG soak note save got 409 "conflicts" (1 of 1,809); the cause was not found. The app logs IntegrityErrors at INFO,
  which gunicorn's default log level does not show.

## 4. Numbers

**Page timings at 100k mice** (the second fetch, ms; KB is the response size):

| Page | load-test.py (in-process, SQLite) | HTTP SQLite, 1 worker | HTTP PG, 3 workers | KB |
| --- | --- | --- | --- | --- |
| `/home` | 251 | 310 | 431 | 59 |
| `/colony?view=mice` | 2470 | 2,993 | 3,178 | 33,390 |
| `/colony?view=mice&ended=all` | – | 16,465 | 16,616 | 208,884 |
| `/colony?view=cages` | 4738 | 5,321 | 5,695 | 56,755 |
| `/colony?view=litters` | 6710 | 6,899 | 7,032 | 23,290 |
| `/colony?view=breeders` | 1304 | 1,543 | 2,399 | 12,398 |
| `/zebrafish?view=fish` | 5957 | 6,058 | 7,553 | 65,731 |
| `/stocks/drosophila` | 1120 | 1,242 | 1,427 | 18,124 |
| `/inventory/reagents` | 3490 | 3,600 | 3,789 | 46,369 |
| `/inventory/samples` | 3679 | 3,507 | 4,280 | 40,500 |
| `/notebook` | 17 | 19 | 42 | 30 |
| `/calendar` | 9 | 11 | 31 | 47 |
| `/calendar/events.json` (6 weeks) | 2203 | 2,392 | 5,052 | 92 |
| `/search?q=Ai14` | 122 | 131 | 224 | 1 |
| `/audit` | 14 | 18 | 42 | 183 |
| `/batches` | 12 | 16 | 51 | 30 |
| `/admin/colony` | 2095 | 2,530 | 2,841 | 17,679 |
| mouse export CSV (my scope, 26,916 rows) | – | 5,913 | 6,383 | 2,109 |
| mouse export CSV `scope=all` (100,039 rows) | – | 7,496 | – | 7,874 |
| Settings → export my data (zip) | – | 5,123 | 13,773 | 318 |

- **Worker RSS**: 412 MB after one pass over the big pages (SQLite); 514 MB after the concurrent big-sheet test; 389–444 MB for
  the PG workers that served big pages.
- **Soak latencies (p50 / p95 ms)**:

  | Request | SQLite p50 / p95 | PG p50 / p95 |
  | --- | --- | --- |
  | mouse sheet | 265 / 601 | 278 / 684 |
  | note save | 20 / 123 | 39 / 109 |
  | Add many ×5 | 21 / 112 | 37 / 128 |
  | calendar feed | 68 / 267 | 141 / 332 |
  | search | 26 / 149 | 52 / 159 |

- **Recovery**:
  - worker killed: back in 0.3–1.0 s;
  - whole server killed and restarted: 2.2–3.8 s;
  - PostgreSQL back: the first request succeeded 0.0 s after `docker start`, and errors stopped within 0.1 s.
- **Upgrade**: a v0.7.0 lab upgrades in about 0.7 s of start-up. `upgrade-check.py` takes 77 s for SQLite and 126 s for PG
  (13 releases each).

## Evidence and re-running

Everything is under `testing/robustness/evidence/`. Scripts are in `evidence/scripts/`:

- `serve.sh`: run gunicorn as a lab server does.
- `bm.py`: signed-in sessions and the form scraper.
- `time_pages.py`, `big_conc.py`: the big-lab timings.
- `conc.py <base> <password> <db-url> <label> [C1,…]`: the concurrency tests C1–C8.
- `stale_row.py`, `double_undo.py`, `dblclick.py`, `contention.py`.
- `soak.py`, `rss.sh`.
- `fail_kill.py`, `pg_outage.py`, `disk_full.py`, `sqlite_lock_corrupt.py`, `upgrade_kill.py`, `restore_live.py`.

Server logs are `evidence/gunicorn-*.log`. Every server was stopped, the tmpfs was unmounted, and the `pg-robust` container
was removed at the end.

**Harness notes** (my own mistakes, corrected; the results above are the corrected ones):

- The `mice_created_by_batches` figure in `conc-sqlite-part2.txt` counts part 1's batches too. The real count is 720, and C4c
  confirms it.
- Two setup mistakes in the harness were fixed and those runs repeated:
  - a leftover `--pid` file stopped restarts after a SIGKILL. The production Dockerfile uses no pid file, so this does not
    affect a lab.
  - the first upgrade-kill runs killed the server only after the upgrade had finished.
