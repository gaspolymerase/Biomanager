# BioManager 1.0 pre-release: re-test of the six areas' findings against the fixed code

## 1. Scope and environment

- **Code under test**: `testing/retest/code` (frozen copy, commit fb73ac1). Not edited. The older tree in `the repository` was used only for its `.venv` (symlinked) and for `diff` to see which files changed.
- **Servers**: gunicorn with the repo's `gunicorn.conf.py` (`wsgi:app`, preload, 4 threads, `BIOMANAGER_HTTPS=0`), SQLite with 1 worker on 127.0.0.1:5106, PostgreSQL with 3 workers on 127.0.0.1:5116. The start and stop scripts are `scripts/start-server.sh` and `scripts/stop-server.sh`.
- **PostgreSQL**: PostgreSQL 16 in container `pg-retest` on host port 55506, with databases `pm`, `integ`, `rob` and `emptylab`. The demo labs were loaded with the code's own `scripts/migrate-to-postgres.py`. The container is now removed.
- **Data**: the demo lab from `scripts/demo-data.py` (fictional people alex (admin), sam, jordan and priya), one fresh copy per area. The pilot-mouse lab (riley and 7 others) was rebuilt on PostgreSQL with the original p0–p2 scripts, and the original generated sheets were used: `colony-messy.xlsx`, `colony-titled.xlsx`, `colony-truth.json` and pilot-other's `fish-messy.xlsx`.
- **Browser**: Playwright Chromium 1194, headless, for Lab setup, the import UI, the stale-row PM-59 test and the TEXT-02 sheet autosave.
- **Scripts**: the original scripts were copied to `scripts/<area>/`, with paths and ports changed and nothing else. New scripts written for this re-test:
  - security: `labcopy_retest.py`, `lookalike.py`, `f11_urls.py`, `formula_formats.py`, `signout_other.py`, `key_disabled.py`, `csp_flood*.py`;
  - integrity: `seed_newlines.py`, `sac_dead.py`, `dates_retest.py`, `parity_retest.py`, `pm17_dayfirst.py`, `rt_export.py`, `undo_redo_undo_diffcages.py`;
  - pilot-mouse: `pm59.py`;
  - robustness: `csv_dup.py`, `next_id.py`;
  - pilot-other: `po_retest.py`.
- **Evidence**: `evidence/<area>/`, with server logs in `evidence/logs/`.
- **Not run**:
  - `upgrade-check.py`, as instructed (the main session runs it).
  - The Docker deploy stack itself (Caddy, the watchdog against a live Caddy, and restic). The deploy scripts were run inside the `postgres:16` container instead (see §2).
  - Nothing external was contacted.
- **Server errors across the whole re-test**: exactly **one** HTTP 500, during the deliberate PostgreSQL outage (see ROB-27). There were 0 elsewhere (`grep '" 5[0-9][0-9] '` over every server log).

## 2. Results

| Finding (area ID) | Original result | How re-tested | Now | Evidence |
| --- | --- | --- | --- | --- |
| Security F-1 (SEC-37): a guest takes a lab copy | FAIL: whole database incl. password hashes | Guest pass → internet entrance → POST /settings/lab-copies (members' copies switched on in Lab setup through Chromium). Also: a member's key after an admin disables the member | **FIXED**: the guest is refused with 403 and no key is issued. A disabled member's key answers 401 for files and for the snapshot | security/labcopy_retest.txt, key_disabled.txt |
| Security F-2 (SEC-35): a member's snapshot | FAIL: admin's hash, others' unshared pages, audit log, feedback | Seeded jordan's unshared page (with a version and a comment), jordan's personal database with an item, feedback, an API token, a guest pass, and a page priya shares with sam. sam's key → `/api/lab-copy/snapshot` | **FIXED**:<br>• password hashes non-blank: 0 of 5<br>• pages: only sam's own and priya's shared one<br>• 0 versions and 0 comments of jordan's<br>• `audit_log`, `feedback`, `api_tokens`, `lab_copy_keys`, `guest_passes`, `user_identities`: 0 rows each<br>• jordan's personal database and its items: 0<br>• notifications: sam's only<br>• the raw file bytes hold none of the removed text (`grep -a` of the .db) | security/labcopy_retest.txt/.json, snapshot-member-retest.db |
| Security F-2: a member's `/api/lab-copy/files` | FAIL (whole uploads folder) | 5 uploads: sam's (on sam's page), priya's (on the page shared with sam), jordan's private page file, a file in jordan's personal database, and an unreferenced admin file | **FIXED**: the list holds the 2 files that sam's records name. The other 3 answer 404 when fetched directly | security/labcopy_retest.txt |
| Security SEC-34: the admin's copy is whole | WARN | alex's key: every table counted against the live database | **FIXED** (whole, as designed): hashes 5/5, pages 3/3, audit 178/178, feedback, tokens, keys, guest passes, versions, comments, inventory, mice and notifications all equal the live counts; files 5/5 | security/labcopy_retest.txt |
| Security F-3 (SEC-22): sign-out ends the session | WARN: a copied cookie still worked | sessions.py, plus signout_other.py | **FIXED**: the replayed cookie is signed out. The same user's other browser stays signed in (per-session) | security/sessions.txt, signout_other.txt |
| Security F-6 (SEC-24): disable → enable | WARN: the old cookie worked again | sessions.py step 3 | **FIXED**: the old session stays out after re-enabling | security/sessions.txt |
| Security F-5 (SEC-38): 20 wrong anonymous lab-copy keys | WARN: the valid key got 429 | lab_copy_throttle.py | **FIXED**: 20 × 401 and 1 × 429 for the stranger; the admin's valid key right after gets 200 | security/lab_copy_throttle.txt |
| Security F-4 (SEC-45): CSV/xlsx formula injection | WARN: live `=HYPERLINK`, `+`, `@` | formula_injection.py, plus the export in format csv / excel / xlsx | **FIXED**: CSV cells are written `'=HYPERLINK…`, `'+SUM`, `'@SUM` (with a UTF-8 BOM). The xlsx has 0 formula cells (text type). Export my data is also prefixed. See new issue N1 | security/formula_injection.txt, formula_formats.txt |
| Security F-11 (SEC-41): 500s on bad numbers | WARN: 14 × 500 | injection_fuzz.py (routes re-dumped from the fixed code: 390 rules, 48 parameters × 13 payloads), plus each listed URL | **FIXED**: 1,625 requests, 0 × 500, 0 injections. `limit=x` → 400 JSON. The 21-digit numbers in search, notebook `page` and stocks `horizon` → 200. `/notebook/search/1` → 400. Calendar windows in year 1 or 9999 → 400 | security/injection_fuzz.txt, f11_urls.txt |
| Security F-7 (SEC-32): sign-up flood | WARN: 60 in 9.1 s, 60 admin notifications | register_spam.py | **FIXED**: 5 accepted, then 55 refused ("Too many sign-ups from here in the last hour"). alex got 5 notifications. The limit is per address and per worker (in memory); see N9 | security/register_spam.txt |
| Security F-8 (SEC-33): look-alike usernames | WARN: Alex, ALEX, Cyrillic а, `*` all accepted | lookalike.py, after a restart so the sign-up limit was clear | **FIXED**: `Alex`, `ALEX` and `alex ` → "That username already exists". `аlex` (Cyrillic) and `*` → refused by the letters rule. (`aIex` with a capital i and `alex.` are accepted; see N9) | security/lookalike.txt |
| Security F-13 (SEC-49): current-password check in Settings | WARN: none refused in 30 | misc.py | **FIXED**: 10 answered "incorrect", then refused (the right password is refused too while the limit holds) | security/misc.txt |
| Security F-12 (SEC-50): /csp-report | WARN: forged log line, no limit | misc.py, csp_flood.py, csp_flood2.py | **FIXED**: the newline is logged as `'x\n[2026-01-01] ERROR forged line'` (repr, one line). About 30 reports a minute per address are logged, and the rest answer 204 silently. See N12 for one unexplained stall | security/misc.txt, csp_flood*.txt, logs/security-server.log |
| Security F-16 (SEC-48): Set-Cookie on API replies | WARN: re-set | api_tokens.py | **FIXED**: `Set-Cookie: None` on a token + cookie request | security/api_tokens.txt |
| Pilot-mouse PM-14: merged Cage # cells | FAIL: 51 mice in the wrong or no cage | Original p3_import.py through the UI (PostgreSQL, 3 workers), then verify_import.py against colony-truth.json | **FIXED**: cage wrong 0 of 352 (was 51); rack/position differ 0 (was 16) | pilot-mouse/import-verify.txt |
| Pilot-mouse PM-24: imported cages owned by the importer | FAIL: 115/115 riley's; 253 mice in someone else's cage | Same run | **FIXED**: "cage owned by someone else than its mouse" is 0. Cages: dana 20, eli 23, fern 20, gus 11, hana 16, riley 25 | pilot-mouse/import-verify.txt |
| Pilot-mouse PM-16: DOB `12-May-26` text | FAIL: 19 DOBs blank, text lost | Same run; also `12-May-26` in dates_retest | **FIXED**: 0 DOBs wrong or lost (was 19); 12-May-26 → 2026-05-12 | pilot-mouse/import-verify.txt, integrity/dates-retest-*.txt |
| Pilot-mouse PM-17: ambiguous day-first Sac dates | FAIL: 16 wrong, one in the future; no switch | pm17_dayfirst.py: Lab setup date style = day, then import colony-messy.xlsx | **FIXED** (through Lab setup's date style): 0 of 17 sac dates wrong and 0 DOBs wrong. The preview says "read day first … as Lab setup's date style says". On a month-first lab (the default) the same column still reads month first, with the note (16 differ in the PM-14 run) | pilot-mouse/pm17-dayfirst.txt |
| Pilot-mouse PM-26: future DOB 2062 | FAIL: imported as 2062-03-12 | Same import; dates_retest rows `30/12/2026` and `12/03/2062` | **FIXED**: left blank, and "Date of birth in the spreadsheet: 2062-03-12" is kept in the notes, with a warning in the preview | pilot-mouse/import-verify.txt, integrity/dates-retest-sqlite.txt |
| Pilot-mouse PM-59: a stale row undoes Animal care's change | FAIL: status reverted | pm59.py (Chromium): casey sets dana's mouse to breeder; dana's older sheet then types a note | **FIXED**: status stays `breeder` and the note is saved (dana's row still shows the old status; see N13) | pilot-mouse/results.jsonl |
| Pilot-mouse PM-103: 28 simultaneous New mouse | FAIL: 8/28 saved, false "already used" | p11_concurrency.py (PostgreSQL, 3 workers) | **FIXED**: 28/28 created, 28 distinct IDs, all 302, 0 × 500 | pilot-mouse/results.jsonl |
| Pilot-mouse PM-104: 7 simultaneous Add many | FAIL: 2/7 batches | p11b_batch_race.py | **FIXED**: 35 mice, 35 distinct IDs, 7 cages; 7 "Created 5 mice" flashes | pilot-mouse/results.jsonl |
| Pilot-mouse PM-97b / Integrity INT-02: the Excel export is a real .xlsx that re-imports | FAIL: TSV named .xls; refused | Mice → export `format=excel`, then Import from Excel into a fresh lab | **FIXED**: `mice_export.xlsx` (PK zip, xlsx MIME type). 39/39 mice imported | integrity/rt-mice_export.xlsx, roundtrip-xlsx.txt |
| Pilot-mouse PM-08: a title line taken as the header | FAIL | p3_import.py with colony-titled.xlsx | **STILL FAILS**: the headers shown are still "Colony list, Column 2, Column 3, Updated:, 09/03/2026". The new rule (`split_header`, app/sheet_import.py:226) takes the first row with ≥ 60 % of the widest row. That title has 3 of 5 cells filled, which meets `need = max(2, round(0.6·5)) = 3` | pilot-mouse/import-mapping.txt, shots/p3-titled-match.png |
| Integrity UNDO-12 / PAR-07: undo → redo → undo empties cages | FAIL (critical), both databases | undo_redo_undo.py, plus a variant with mice from 3 different cages, on SQLite and PostgreSQL | **FIXED**: mice back in their first cages on both; no empty cage left; audit `cage_id_fk: 16 → 1/2/3` matches the database | integrity/undo-redo-undo*-{sqlite,pg}.txt |
| Integrity INT-10: snapshot race | FAIL: 1–11 orphaned mice per copy | snapshot_race.py: 3 writers, 5 copies (SQLite) and 6 (PostgreSQL) | **FIXED**: 0 mice pointing at a missing cage, 0 `foreign_key_check` rows and 0 mice without a create audit in all 11 copies (339 and 308 mice added during the runs) | integrity/snapshot-race-*.txt/.json, race-*.db |
| Integrity TEXT-02 / TEXT-03: line breaks survive editing another cell | FAIL (high) | seed_newlines.py (API notes with `\n`/`\r\n`, a tab, 10k characters; a CSV import making "Healthy\nID in the spreadsheet: R1…"), then newline_autosave.py in Chromium, changing only Sex (SQLite) | **FIXED**: only `gender` changed on all 5 mice. Line breaks, tab, long text and the import's note were kept (the input still *shows* them squashed) | integrity/newline-autosave.json/.png |
| Integrity UNDO-14: Sac on already-dead mice | FAIL: date overwritten with today | sac_dead.py (death date 2026-09-26, then selection-bar Sac), both databases | **FIXED**: date of death stays 2026-09-26 (status becomes `sac`) | integrity/sac-dead-*.txt |
| Integrity UNDO-10 / UNDO-11: weaning is a batch and undoable | FAIL: no batch | undo_tests.py, both databases | **FIXED**: "wean cage 101 (2 mice moved)" and "wean cage 101" batches. Undo residue 0, redo residue 0, final 0 on both. (The other bulk actions still leave only `updated_at`/`updated_by` behind after an undo, the original L2 WARN) | integrity/undo-results-*.json/.txt |
| Integrity DATE-07: day-first lab import | FAIL: read month first; a future DOB imported | dates_retest.py: date style day; 03/04/2026, 05/06/2026, 11/02/2026, 30/12/2026, 12/03/2062, 15-03-26; both databases | **FIXED**: 2026-04-03, 2026-06-05, 2026-02-11, 2026-03-15. The future ones are blank, kept in the notes, and warned in the preview | integrity/dates-retest-*.txt |
| Integrity TEXT-07: 1.5e-7 in an xlsx | FAIL: stored "0" | dates_retest.py: Reagents Concentration 1.5e-7, 1e20, 0.1+0.2, 2.5 | **FIXED**: "1.5e-07", "1e+20", "0.3", "2.5" (both databases) | integrity/dates-retest-*.txt |
| Integrity PAR-03: SQLite case-insensitive search beyond ASCII | FAIL | parity_retest.py: notes "Δ-Cre/+ αβγ", "Café" | **FIXED**: `δ-cre`, `Δ-CRE`, `CAFÉ` and `café` are found on SQLite, as on PostgreSQL | integrity/parity-retest-*.txt |
| Integrity PAR-05: API refused value on PostgreSQL | FAIL: 302 to /home | PATCH `/api/v1/mice/1` with a 201-character genotype / transgene | **FIXED**: 409 JSON "One of the values is longer than its field allows (200 characters), so nothing was saved." (SQLite still saves it: the original PAR-02 WARN, not re-tested as a fix) | integrity/parity-retest-pg.txt |
| Integrity PAR-06: `%` and `_` in search | WARN: match everything | `zz%zz` / `zz_zz` against notes "zzAAzz" / "zzBzz" | **FIXED**: 0 results for both on both databases ("zzAAzz" itself is found) | integrity/parity-retest-*.txt |
| Integrity INT-03: mice export → import round trip | FAIL | rt_export.py + roundtrip_mice.py: demo lab → xlsx and CSV → fresh lab with the same users and racks; 17 fields × 39 mice | **PARTLY**:<br>• xlsx: transgene 2–4 map to transgene columns and are kept; Active/Age are skipped (not in the notes); notes and `=1+1` are kept.<br>• Still: status `breeding` → `breeder` (21 mice).<br>• CSV: 8 mice now get a leading `'` in their note, genotype or transgene (N1) | integrity/roundtrip-xlsx.txt, roundtrip-csv.txt |
| Pilot-other PO-56: `15-03-26` → 2026-03-15 | FAIL: 2015-03-26 and 2031-12-25 | dates_retest.py with pilot-other's fish-messy.xlsx (DOF), SQLite and PostgreSQL | **FIXED**: 15-03-26 → 2026-03-15 and 31-12-25 → 2025-12-31 on both. (DOF is now matched to Fertilised automatically) | integrity/dates-retest-*.txt |
| Pilot-other PO-57: `5 Mar 2026` | WARN: left blank | Same | **FIXED**: 2026-03-05 | integrity/dates-retest-*.txt |
| Pilot-other PO-27: progeny moved 25 → 18 °C | WARN: eclosion kept at 25 °C timing | po_retest.py: Collect eggs from cross V8 at 25 °C (ready 09 Oct), then move the vial to the 18 °C rack (the sheet's update) | **FIXED**: 09 Oct → 18 Oct, the same date a collection made at 18 °C gets. (The rack-grid `place` path was not re-tested: my request lacked a position) | pilot-other/po_retest.txt |
| Integrity DATE-08 / Pilot-other PO-22: 21/30 °C and RT | WARN: default 25 °C schedule | po_retest.py: incubator temperature 18, 21, 22, 25, 29, 30, RT, abc; Stocks 1 flip interval from the calendar feed | **FIXED**: 21 → 18 d (22's), 30 → 10 d (29's), RT → 18 d (22's). 18/25/29 as listed; "abc" → the default 14 d | pilot-other/po_retest.txt |
| Pilot-other PO-58: undo of an undo | WARN: the import row still reads "undone" | po_retest.py: plasmid import → undo → undo that undo → plain Undo on the import | **FIXED**: after the redo the import row is no longer "undone". Plain Undo on it works again (plasmids 2 → 0) | pilot-other/po_retest.txt |
| Pilot-other PO-55: import notes when making new tanks and lines | WARN: silent | dates_retest.py preview | **FIXED**: e.g. "Row 9 (2 in T-099): There was no tank T-099, so it's made new" and "There was no line “Unknown line”, so it's made new…" | integrity/dates-retest-sqlite.txt |
| Pilot-other PO-85: unstyled 404 | WARN | GET /stocks/fly signed in; /no/such/page signed out | **FIXED**: the app's styled page "There's nothing here", with the navigation links | pilot-other/po_retest.txt |
| Robustness ROB-08 / ROB-09: stale row | FAIL on both | stale_row.py (sac, cage move, transgenes, owner), plus conc.py C2, both databases | **FIXED**: 0 of A's changes reverted in 4 cases on each database; C2 keeps both edits | robustness/stale-row-*.txt, conc-*.txt |
| Robustness ROB-10: rack double-booking | FAIL: 4 cells with 2–6 cages | conc.py C3 (8 cages × 15 cells) and C3b | **FIXED**: 0 double-booked cells on both. The losers get 409 (SQLite 52, PostgreSQL 66) | robustness/conc-*.txt |
| Robustness ROB-11 / ROB-12: concurrent creates | PostgreSQL WARN 15/18 refused; 37/80 New mouse | conc.py C4, C4b, C4c | **FIXED** (within "rare clean failures"): SQLite 18/18 batches (720 mice) and 80/80 New mouse. PostgreSQL 17/18 batches (1 refused "That mouse ID is already used") and 80/80 New mouse. 0 duplicate IDs, 0 gaps, one audit create per mouse. (During the snapshot race on SQLite, 3 of about 339 New mouse posts were still refused; N8) | robustness/conc-*.txt, logs/integ-sqlite-server.log |
| Robustness ROB-18: double-submit over HTTP | WARN | conc.py C7 | **STILL FAILS** (WARN level): New mouse posted twice at once now makes **2** mice (was 1, when the ID clash refused the second). Add many ×2 makes 20 on both databases (PostgreSQL was 10). The browser double-click (ROB-19) was not re-run | robustness/conc-*.txt |
| Robustness ROB-14: concurrent CSV imports | WARN: 302 redirect; "Network error" | conc.py C5, csv_dup.py | **PARTLY**: now JSON, 1 of 4 imported, no partial rows, 0 duplicates. But the 3 others answer 400 `{"error":"empty CSV"}`, which is wrong (N2) | robustness/csv-dup-*.txt |
| Robustness ROB-15: CSV repeated ID passes the dry run | FAIL | csv_dup.py dry run; conc.py C5b | **FIXED**: the dry run reports "row 3: mouse_id N already exists" (count 1). A blank row followed by an explicit next-free ID no longer collides | robustness/csv-dup-*.txt |
| Robustness ROB-20: undo while someone edits | FAIL on both | conc.py C8: 1 run in the full set, 3 repeats on PostgreSQL, 2 on SQLite | **PARTLY**: SQLite refused, or undid only unedited rows, in 3/3 runs, with 0 edits lost. PostgreSQL ran the undo and overwrote 1–2 acknowledged edits in **4/4 runs** | robustness/conc-pg*.txt/json, conc-sqlite-c8-repeats.txt |
| Robustness ROB-21: the same batch undone twice at once | WARN: both ran | conc.py C8b | **FIXED**: "Undid 6 change(s)" + "Already undone."; 1 undo batch recorded, on both | robustness/conc-*.txt |
| Robustness ROB-23: New mouse after re-importing an old ID | FAIL: every press refused | next_id.py: delete #5, CSV import mouse_id=5, New mouse ×3 + the dialog | **FIXED**: #1078–#1081 created | robustness/next-mouse-id-sqlite.txt |
| Robustness ROB-27: PostgreSQL stops | WARN: 429 bare 500 pages | pg_outage.py (stop at 10 s, start at 25.5 s) | **PARTLY**:<br>• While down: 430 answers, all 503 (the app's page, or JSON "The database didn't answer in time, so nothing was saved…").<br>• 1 bare "Internal Server Error" at the moment the connections were cut (N4).<br>• Recovery 0.3 s after start; the last acknowledged save is in the database | robustness/pg-outage.json, logs/rob-pg-server.log |
| Robustness ROB-28: disk full | WARN: bare 500 | disk_full.py on a 3 MB tmpfs | **FIXED**: 503 with the app's page ("database or disk is full" logged); integrity ok; saves worked again once there was room. (The harness's restart on a 100 %-full disk failed on gunicorn's own pid file: a harness artefact) | robustness/disk-full.txt, logs/gunicorn-diskfull.log |
| Robustness ROB-29: SQLite locked | WARN: bare 500, even for GET | sqlite_lock_corrupt.py L1 (IMMEDIATE and EXCLUSIVE held 12 s) | **FIXED**: 503 with the app's page after 5 s. GET /home now answers 200 under an IMMEDIATE lock. Works again after release | robustness/sqlite-lock-corrupt.json |
| Robustness ROB-32: zero-byte database | WARN: started as a new lab | sqlite_lock_corrupt.py L2 | **FIXED**: refuses to start: "BioManager won't start: the lab's database … is an empty file (0 bytes)… Put back a backup…". dbtool check: "EMPTY" | robustness/sqlite-lock-corrupt.json |
| Robustness ROB-31: dbtool check on a damaged file | WARN: traceback | Same: garbage in the middle, truncated to half, a text file | **FIXED**: "status : DAMAGED — SQLite can't read it (…)… Put back the newest backup" for all three. (The server with garbage mid-file still starts and serves pages, as before; the truncated and text-file cases still refuse with a traceback in the log) | robustness/sqlite-lock-corrupt.json |
| Robustness ROB-38: dbtool restore | WARN: replaced the file under a running app | dbtool-restore test: a truncated backup, a text file, answer n, stdin closed, answer y | **FIXED**:<br>• damaged or text backup → "not a healthy BioManager database; nothing was changed";<br>• answer n → nothing changed;<br>• answer y → safety copy (backup API), then restore.<br>(It asks rather than detects a running server. Closed stdin → EOFError traceback, nothing changed; N11) | robustness/dbtool-restore.txt |
| Deploy F-01: off-site copy of an empty lab | FAIL (critical) | backup.sh run inside postgres:16 on a lab with 0 accounts, with RESTIC_REPOSITORY set; RUNBOOK read | **FIXED**: "no accounts in emptylab yet: nothing to back up (and nothing sent off-site)", exit 0, no files, restic never called. RUNBOOK now says `restic snapshots --tag biomanager`, then `restic restore <ID>`, picked by time from before the loss | deploy-backup.txt, code/deploy/RUNBOOK.md:136-146 |
| Deploy F-02: restore.sh with a mistyped files path | FAIL (high) | restore.sh inside postgres:16 with `biomanager-<t>.tar.gz` (no `-files`), and with a non-gzip file | **FIXED**: "no such files archive … nothing was changed" and "not a readable archive — nothing was changed". The database is not renamed and /appdata is untouched. The correct restore then works (previous database and files kept); restore-test.sh passes on a named older dump | deploy-restore.txt |
| Deploy F-03: start-up backup after `up -d --build` | FAIL (high) | schedule.sh `recent_backup` run in the container; RUNBOOK read | **FIXED**: dump present → skipped; 13 h old → taken; none → taken. The RUNBOOK says so under "Updating went wrong" | deploy-schedule.txt |
| Deploy F-04: the watchdog reads .env; TLS=internal | FAIL | The watchdog's `env_value` run on server.html's `.env` lines (trailing comments, quotes); code read for TLS | **FIXED** (parsing run; TLS path by reading only). DOMAIN, TLS, BACKUP_DIR and a quoted RESTIC_REPOSITORY are parsed right. With no BACKUP_DIR the default is `<deploy>/backups`. With TLS=internal it checks with `--cacert` (Caddy's root, taken via `docker compose exec caddy`) and skips the certificate-age check. Not run against a live Caddy | code/deploy/host/watchdog.sh:16-40, 68-79, 119-122 |
| Deploy F-05: off-site retention never forgets | FAIL | Read backup.sh | **FIXED** (by reading; restic not available here): `restic forget … --group-by host,tags --keep-daily 30 --keep-weekly 12 --keep-monthly 24 --prune` | code/deploy/backup/backup.sh:76-79 |
| Deploy F-06: updated scripts don't reach the containers | FAIL | Read compose.yaml, RUNBOOK, maintenance.sh, load-image.sh | **PARTLY**:<br>• Fixed: `restore` now runs `image: biomanager-backup:local` (`pull_policy: never`), the image the backup service builds. The RUNBOOK bundle update and maintenance.sh (`build --pull`) rebuild it.<br>• Still: `host/load-image.sh:35` prints "Start or update with: … docker compose up -d", with no `--build` (file unchanged) | code/deploy/compose.yaml:93-135, host/load-image.sh |
| Deploy F-07: server.html commands | FAIL | Read site/server.html; `env_value` test above | **FIXED**: "`sudo host/install.sh` (in the `deploy` folder)". Inline `# comments` in `.env` are stripped by watchdog.sh and offsite-setup.sh (`get()`) | code/site/server.html:204,290,330 |

## 3. New or remaining problems noticed

- **N1 (medium, new, from the F-4 fix): the CSV export's `'` prefix changes data on a round trip.**
  - What: `sheet_safe` (app/services.py:1275) prefixes `'` to any value starting with `= + - @`. That includes the ordinary wild-type genotype `+/+`, and notes such as `-5 …`.
  - Import from Excel keeps the apostrophe. In the CSV round trip, 8 of 39 mice came back changed: transgene_1 `+/+` → `'+/+` and genotype `+/+; Ai14/+` → `'+/+; Ai14/+` (2 mice), plus notes `'=1+1…`, `'-5…`, `'@home`.
  - Export my data's `mice.csv` is prefixed the same way.
  - The xlsx export is not affected (cells are typed as text).
  - Either the importer should drop a leading `'` before `= + - @`, or genotype-like values such as `+/+` should not be prefixed. Evidence: integrity/roundtrip-csv.txt, rt-mice_export.csv.
- **N2 (low–medium, new): concurrent mouse CSV imports (`/import/mouse`) fail with a false "empty CSV".**
  - 3 of 4 simultaneous imports answered 400 `{"error":"empty CSV"}`, on SQLite and PostgreSQL.
  - Suspected cause: the `next_number_retried` wrapper (app/app.py:201) runs the view again after an IntegrityError, but the upload stream was already read on the first try.
  - Evidence: robustness/csv-dup-*.txt.
- **N3 (medium, remaining): ROB-20 on PostgreSQL.** An undo that runs while someone edits the batch's mice still overwrites 1–2 acknowledged edits (4 of 4 runs). SQLite is fine. The blocker check still appears to be read without a row lock on PostgreSQL.
- **N4 (low): one bare 500 during the PostgreSQL outage.**
  - `handle_server_error` renders `error_plain.html`, whose context processor `inject_user` → `notify.unread_count` (app/app.py:536, app/notify.py:395) queries the database that just failed. The handler therefore fails too.
  - Evidence: the traceback in logs/rob-pg-server.log (about line 1175).
- **N5 (low, new): redoing an import gives the cage back to the importer.** After import → undo → undo-of-undo, a re-created cage's owner is `alex` (the importer) instead of `sam` (its mouse's owner). The new "cage belongs to its first mouse's owner" step (`finish`) is apparently not in the audit rows the redo replays. Evidence: integrity/undo-results-*.json, "UNDO-import" redo residue `mouse_cages#…owner: 'sam' -> 'alex'`.
- **N6 (low): a double-submitted New mouse now makes two mice** (ROB-18 above). The ID clash used to stop the second one by accident.
- **N7 (low, remaining): PM-08.** A 3-cell title line over a 5-column header is still taken as the header.
- **N8 (low): under snapshot load on SQLite, New mouse can still be refused.** 3 of about 339 concurrent New mouse posts were refused with "UNIQUE constraint failed: mice.mouse_id" after the 4 retries, while lab copies held read transactions (logs/integ-sqlite-server.log). Otherwise 80/80.
- **N9 (low, observations):**
  - The sign-up limit (5 an hour) is kept per address and per worker: 7 sign-ups from one address passed on 3 PostgreSQL workers. On a 1-worker SQLite server, a lab whose people all sign up from one NAT address in the same hour would be stopped at 5.
  - `aIex` (capital i) and `alex.` are accepted next to `alex`.
- **N10 (low, observation):** a lab-copy key works again when its disabled owner is re-enabled, unlike sessions after the F-6 fix (security/key_disabled.txt).
- **N11 (low):** `dbtool.py restore` with no terminal (stdin closed) ends in an EOFError traceback. Nothing is changed.
- **N12 (not reproduced):**
  - The first misc.py run (30 wrong current passwords, then 200 anonymous 8 KB CSP reports) stalled after about 69 reports. For about 3 minutes, /healthz timed out (8 s); all 4 worker threads were waiting on sockets.
  - It recovered at once when the client was killed.
  - Three re-runs (misc.py again; 60 and 200 reports) showed no stall, so the cause is unknown. It may involve the new early `return` in `csp_report` for throttled reports, which doesn't read the request body. Worth one more look before release.
- **N13 (cosmetic):** after dana's note save (PM-59), dana's row still shows the old status (empty) until reload, although the database holds casey's `breeder`.
- **Still as before, not in the re-test list but seen:**
  - the mid-sheet subtotal line becomes mouse #1 (PM-13);
  - sex `M?` becomes `M` (PM-21);
  - SQLite saves over-long values (PAR-02);
  - "1 rows were skipped" (PO-66);
  - undo leaves `updated_at`/`updated_by` (L2);
  - status `breeding` → `breeder` on import (INT-03).

## 4. Numbers

- **Findings re-tested**: 64 rows in §2.
  - **FIXED 57.** Two of these were checked by reading the code plus a parsing run, not on a live stack: Deploy F-04 and F-05.
  - **STILL FAILS 2**: PM-08, ROB-18.
  - **PARTLY 5**: INT-03, ROB-14, ROB-20, ROB-27, Deploy F-06.
  - **NOT RE-RUN 0** of those asked.
  - Not run at all: upgrade-check (by instruction), ROB-19 (browser double-click), the rack-grid `place` path for PO-27, and the live Docker/Caddy/restic stack.
- **Import accuracy** (colony-messy.xlsx, 352 mice, PostgreSQL):
  - cage wrong 51 → 0; cage owner mismatches 253 → 0; DOB lost 19 → 0; rack/position differ 16 → 0;
  - sac dates wrong 16 → 0 with date style day; 1 subtotal junk mouse remains;
  - 4.6 s for 353 rows.
- **Concurrency**:

  | Test | SQLite | PostgreSQL |
  | --- | --- | --- |
  | New mouse at once | 80/80 | 28/28 (7 users) and 80/80 |
  | Add many 6 × 3 × 40 | 18/18 | 17/18 |
  | Add many 7 users × 5 | – | 35/35 |
  | Double-booked rack cells | 0 | 0 |
  | Duplicate IDs | 0 | 0 |
  | Stale-row reverts | 0/5 | 0/5 |

- **Lab copies**:
  - member snapshot: 1,265,664 bytes, 0 hashes, 2 pages, 0 rows in 6 admin-only tables, 2 of 5 files;
  - snapshot race: 11 copies with 0 orphans (647 mice added during the runs).
- **Security fuzz**: 390 URL rules; 1,625 requests; 0 × 500 (was 14).
- **PostgreSQL outage**: 430 × 503 (the app's page or JSON), 1 bare 500; recovery 0.3 s after `docker start`.
- **Clean-up**: every gunicorn server on 5106/5116 was stopped, the tmpfs unmounted, and `pg-retest` removed.
