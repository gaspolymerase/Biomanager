# BioManager 1.0 pre-release test: data integrity

Area: **integrity**: is data correct and consistent everywhere it appears, and does it survive
export, import, copying, migration and undo unchanged?

## 1. Scope and environment

- **Code**: `the repository` at `76371cf` (v0.10.2 + icon), read-only. Nothing in the repository was changed.
- **Server**: gunicorn, run like a lab server (`gunicorn -c gunicorn.conf.py wsgi:app`, `BIOMANAGER_HTTPS=0`),
  on 127.0.0.1:5105. SQLite runs 1 worker × 4 threads. PostgreSQL runs 3 workers.
- **Databases**: SQLite files, and PostgreSQL 16 in container `pg-integrity` on host port 55505. Both are removed now.
- **Data**: the demo lab from `scripts/demo-data.py` (4 fictional people: alex (admin), sam, jordan and priya; 39 mice,
  14 cages, 2 racks, fly stocks, inventories), plus test records added through the app's own routes:
  - one mouse for each of 16 awkward strings (Greek, CJK, emoji, combining and precomposed accents, Hebrew and Arabic,
    leading and trailing spaces, `001`, `1E5`, `3/4`, `=1+1`, line breaks, tab, quotes, 200 and 300 characters, and a
    10,000-character note);
  - the same strings in plasmids, reagents and fly vials, brought in with Import from Excel.

  Two fresh, empty labs were used as import targets. Race tests added up to about 870 mice.
- **Clients**:
  - Python `requests` for the pages, the forms and the API (tokens made in Settings → API tokens);
  - Chromium through Playwright for the sheet's autosave, the browser-side Export button and screenshots of cage cards.
- **Where things are**:
  - Scripts: `testing/integrity/scripts/`. `bm.py` is the client, and each other file is one test group.
  - Evidence: `testing/integrity/evidence/`.
  - Servers are started with `start-server.sh <dir> [db-url]` and stopped with `stop-server.sh <dir>`.
- **Time**: tests ran on 2026-09-29, about 17:05–17:35 UTC. The server's own zone is UTC. Lab zones used in the tests:
  Pacific/Kiritimati (UTC+14, already 30 Sep there) and America/New_York.

## 2. Test log

| ID | What | How (steps, users, data) | Expected | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| INT-01 | Mice CSV export matches the database | alex; `/colony/mice/export?format=csv&scope=all`; compare 10 fields for all 55 mice with the `mice`, `mouse_cages` and `litters` tables | Identical | PASS: 0 differences, no mouse missing, tricky text intact (line breaks quoted) | `mice_export_all.csv` |
| INT-02 | The Excel mice export re-imports | Excel link (`format=excel`) → `mice_export.xls` → Import from Excel in a fresh lab | Imports | **FAIL**: the file is tab-separated text named `.xls`, and the importer refuses it ("That's an old-style .xls file…") | `mice_export_all.xls` |
| INT-03 | Mice: export → import into a fresh lab → compare every field | Fresh lab with the same users and racks; import `mice_export_all.csv` with the suggested matches; compare 17 fields for all 55 mice | Same as the source | **FAIL**: see list below | `roundtrip_mice_diffs.json`, `roundtrip_mice_preview.html` |
| INT-04 | Other sheets: browser Export → import into a fresh lab | Chromium clicks **Export** on Plasmids, Reagents and Drosophila vials; the CSVs are imported into a fresh lab; rows compared by name | Same as the source | **FAIL**: see list below | `browser-export-*.csv`, `roundtrip-sheets.json` |
| INT-05 | Import keeps awkward text | 15 strings × 3 sheets (plasmids, reagents, fly vials) imported from CSV, then stored values compared | Same, except edges may be trimmed | PASS for Unicode, `001`, `1E5`, `3/4`, `=1+1`, line breaks, tabs and quotes. Leading and trailing spaces are trimmed. **WARN**: longer values are cut to the column length (name 210→200, vendor 200→120) and the preview doesn't say so | `sheets-import-fidelity.json` |
| INT-06 | migrate-to-postgres refuses values PostgreSQL can't hold | SQLite lab holding a 300-character transgene (the app let it be saved) | Refuses and names the values | PASS: "2 value(s) PostgreSQL would refuse… Nothing was written." | `migrate-demo-with-long.log` |
| INT-07 | SQLite → PostgreSQL migration, every value | `migrate-to-postgres.py demo.db`, then `compare_dbs.py` checks every table, row and column | Identical | PASS: 5,990 values, 0 differences (489 rows in 34 tables) | `compare-demo-vs-mig1.txt` |
| INT-08 | The lab copy (Keep a copy) matches the server | Key from Settings; `GET /api/lab-copy/snapshot`; check the SHA-256 header; compare every value | Identical; encrypted columns blank | PASS: SHA-256 matches, 6,007 values. The only differences: no `alembic_version` table, and the copy key's own `last_bytes`, which is written after the copy | `compare-demo-vs-labcopy.txt`, `labcopy-demo.db` |
| INT-09 | Lab copy → migrate-to-postgres → compare with the original | Snapshot from INT-08 loaded into a new PostgreSQL database | Identical | PASS: 6,008 values, only `last_bytes` differs | `compare-demo-vs-labcopy-mig2.txt` |
| INT-10 | Lab copy taken while people are working | 3 clients keep adding mice, each in a new cage; 6 snapshots on PostgreSQL and 4 on SQLite; each checked with `PRAGMA foreign_key_check` | Each copy is consistent | **FAIL**: every snapshot has mice pointing at cages that are not in it (PostgreSQL 11/4/1/3/3/3, SQLite 5/2/2/4). `PRAGMA integrity_check` still says `ok`. migrate-to-postgres then "cleared the reference": those mice lose their cage | `snapshot-race-par-*.json`, `race-*.db`, `migrate-race-snap.log` |
| INT-11 | Lab copy throttle | Second snapshot with the same key within 2 minutes | 429 | PASS | (INT-08 run) |
| INT-12 | Settings → Export my data | Zip's `mice.csv` compared with alex's 36 mice | Identical | PASS: 0 differences | `export-my-data.txt` |
| UNDO-01 | Add many | 4 F + 2 M in a new cage → undo → redo (undo of the undo) → undo; full rows of mice, cages, litters, experiment_mice, weights, racks and strains compared | Exactly the state before, and after | PASS: 9 audit rows, no difference after undo or redo | `undo-results-2.txt` |
| UNDO-02 | Bulk set transgenes (5 mice) | As above | As above | PASS for the values. **WARN**: `updated_at`/`updated_by` stay as the bulk edit left them | `undo-results.txt` |
| UNDO-03 | Bulk set cage = new (3 mice) | As above | As above | PASS for undo and for redo (cage deleted, then re-made) | `undo-results.txt` |
| UNDO-04 | Bulk set cage = existing cage | As above | As above | PASS | `undo-results.txt` |
| UNDO-05 | Bulk status → sac | 3 living mice | Date of death stamped; undo clears it | PASS | `undo-results.txt` |
| UNDO-06 | Bulk note, owner, date of death | As above | As above | PASS (values). WARN as in UNDO-02 | `undo-results.txt` |
| UNDO-07 | Sac (selection bar) | 3 living mice | As above | PASS | `undo-results.txt` |
| UNDO-08 | Cages → Move to rack (positions) | 3 placed cages moved from Rack A to Rack B | Rack, row and column restored | PASS: positions restored exactly | `undo-results.txt` |
| UNDO-09 | Import from Excel | 2-row CSV imported, then undo and redo | Mice, cage and litters removed, then re-made | PASS | `undo-results.txt` |
| UNDO-10 | Wean and distribute | `/colony/cages/<id>/wean-distribute`, 2 mice to a new cage | Listed in Batches, can be undone | **FAIL**: no batch is recorded, so it can't be undone (the mice moved, a cage was made, the birth date was cleared) | `undo-results-2.txt` |
| UNDO-11 | Wean | `/colony/cages/<id>/wean` | As above | **FAIL**: no batch recorded | `undo-results-2.txt` |
| UNDO-12 | Undo → redo → undo | Bulk "set cage = new" on 2 mice; Undo; undo the undo (redo); Undo again | Mice back in their first cages | **FAIL (critical)**: after the third step `cage_id_fk` is NULL for every mouse, while the audit log says "cage_id_fk: 49 → 47". Same on SQLite and PostgreSQL | `undo-redo-undo-sqlite.txt`, `parity-*-undo.txt` |
| UNDO-13 | Undo after a later edit | alex bulk-sets a note; sam then edits one of those mice in the sheet; alex undoes | Refused; Undo anyway restores | PASS: "1 record(s) changed after this batch…"; force restores both | `undo-conflict.txt` |
| UNDO-14 | Sac on mice that are already dead | Selection bar **Sac** on 2 mice that died on 2026-09-26 | Keeps 2026-09-26 | **FAIL**: date of death overwritten to today. The bulk *status = sac* action keeps it. Undo does restore it | (console, re-run with `undo_tests.py`) |
| AUD-01 | Changes through the API are in the Audit log | Tokens for alex and sam; PATCH a mouse's transgenes, note and status | Who, what, and a mark that it came from the API | PASS: `changed_by` is the token's owner, details `[API: <token label>] field: old → new`, and `changes_json` holds before and after | `audit-who.txt` |
| AUD-02 | Sheet edit by a member | sam edits a note in the sheet (autosave) | `changed_by = sam`; /audit shows it in lab time | PASS | `audit-who.txt` |
| VIEW-01 | A mouse's age, cage, rack/position, status and genotype agree everywhere | 9 mice (incl. awkward text), read from the mice sheet, the CSV export, API mouse and cage, the rack grid, the cage card (HTML and ZPL), the experiment page's data and search | All agree | PASS: 0 disagreements | `views-1.json` |
| VIEW-02 | Change a fact in one place, check the others | Cage moved on the rack grid (A3 → Rack B C5); status via sheet autosave; genotype via API; cage via the sheet; litter date of birth via the litters sheet | Every view follows | PASS: all views agree, and the age follows the litter's new date (271 d) | `views-2-after-changes.json` |
| VIEW-03 | Genotype shown for a cage | Cage 103 has 4 mice with 3 different genotypes | Can be read | **WARN**: the card's Genotype line is "+/+; Ai14/+; DAT-IRES-Cre/+; DAT-IRES-Cre/+; Ai14/+". Distinct genotypes are joined with the same "; " that joins one mouse's transgenes. The rack grid shows only the first transgenes ("+/+, DAT-IRES-Cre/+") | `views-2-after-changes.json`, `tricky-cards.png` |
| VIEW-04 | Home cards agree with the sheet | "Mice older than 30 weeks" and "Upcoming weanings" compared with sheet ages and P21 | Agree | PASS (#4 38w = 271 d; cage 110 weaning in 2 d) | `view-home-2.html` |
| TEXT-01 | Awkward text saved through the New mouse form | 16 strings in transgene, note, cage ID and litter ID | Stored as typed | PASS. Spaces at the edges are trimmed (as elsewhere). **WARN**: SQLite keeps a 300-character transgene in a 200-character column; PostgreSQL refuses it (PAR-01) | `text-seed-sqlite.json` |
| TEXT-02 | Editing one cell keeps the others unchanged | Chromium: change only **Sex** on mice whose note or transgene has line breaks, a tab, 10k characters or quotes | Only sex changes | **FAIL (high)**: line breaks are removed from note, transgene and genotype ("line1\nline2\r\nline3" → "line1line2line3"). Tab, long text and quotes are kept | `newline-autosave.json`, `newline-autosave.png` |
| TEXT-03 | Import's notes survive the first edit | Import a mouse with extra columns: the importer writes "Healthy\nID in the spreadsheet: R1\nCoat: black"; then change its Sex in the sheet | Note unchanged | **FAIL**: the note becomes "HealthyID in the spreadsheet: R1Coat: black" | `import-note-squashed.json` |
| TEXT-04 | Cage cards with awkward text | Cards for 6 cages with CJK, emoji, accents, line breaks, 200 characters and RTL | Readable, nothing spills out | PASS: no overflow. Emoji show as boxes (the font has none) | `tricky-cards.png`, `tricky-cards.html` |
| TEXT-05 | ZPL labels | `format=zpl` for the same cages, plus a genotype `^XZ~JA_caret^FDinject` | `^`, `~` and `_` escaped | PASS (escaped as `_5E`, `_7E`, `_5F`). **WARN**: a line break goes into `^FD` as a raw line break. `^A0` (the printer's built-in font) has no CJK or emoji and no right-to-left shaping; this was not checked on a real printer | `tricky-cages.zpl`, `zpl-tricky.txt` |
| TEXT-06 | Exports opened in Excel | Read the export bytes | Values safe | **WARN (by inspection; no Excel available)**: `=1+1` is written as is (formula injection); `001`, `1E5` and `3/4` are not protected from Excel changing them; the server's CSV has no BOM, so Excel on Windows shows accents and CJK as garbage (the browser Export has a BOM) | `mice_export_all.*` |
| TEXT-07 | Numbers in an Excel workbook | `.xlsx` with Concentration cells 1.5e-7, 1e20, 0.1+0.2 imported into Reagents | Kept | **FAIL**: 1.5e-7 is stored as "0". 1e20 → "100000000000000000000"; 0.30000000000000004 → "0.3" | `xlsx-import.txt`, `tricky.xlsx` |
| TEXT-08 | A genotype with a comma | API `PATCH` `genotype: "Tg(Thy1-EGFP)MJrs, hom"`; then GET and PATCH the same genotype back | Unchanged | **WARN**: split into two transgenes ["Tg(Thy1-EGFP)MJrs", "hom"]; sending a mouse's own genotype back changes it | `genotype-comma.txt` |
| DATE-01 | Lab zone ahead of the server | Lab setup zone Pacific/Kiritimati (30 Sep) while the server is at 29 Sep UTC | "Today" is the lab's day everywhere | PASS: date of birth 30 Sep accepted (not "future"), age 0 d, sac stamps 30 Sep, API accepts date of death 30 Sep, /audit shows lab time | `dates-1.json` |
| DATE-02 | A zone change reaches every worker | PostgreSQL, 3 workers; change the zone; 15 fresh requests at t+0, 5, 15, 25 and 35 s | All agree | **WARN**: for about 30 s workers disagree on today's date (12/3, then 8/7, then 15/0) | `tz-worker-lag.txt` |
| DATE-03 | Born on 29 Feb | Date of birth 2024-02-29; also 2025-02-29, 29/02/2024, 02/29/2024, 240229 and 20240229 posted to the form | Right age; bad dates refused | PASS: 944 d, API shows 2024-02-29. **WARN**: 2025-02-29 and slash forms are dropped without a word and the mouse is saved with no date of birth (the date picker never sends these; other clients could) | `dates-1.json` |
| DATE-04 | Dates far in the past or future | Date of birth 0001-01-01, 1899-12-31, 1900-01-01, 2099 and 9999; API date of death 1800 and 2099 | Past kept, future refused | PASS: kept in the sheet, export, Home and migration; future refused by the form and the API. **WARN**: `/calendar/events.json` for a window in year 1 or 9999 answers 500 (OverflowError in `weaning_due`, `booking_items`) | `dates-1.json`, server log |
| DATE-05 | P21 weaning and genotyping day land on the right day | Cages born 2024-02-08 (leap), 2026-02-01 (month end) and the lab's today | Wean born+21, genotype born+28 | PASS: 2024-02-29 / 2024-03-07, 2026-02-22 / 2026-03-01, 2026-10-21 / 2026-10-28 | `reminders.json` |
| DATE-06 | Calendar across midnight and DST (New York) | Events 23:00→01:30, 01:30 on the DST-end day, 02:30 in the DST-start gap, overnight across DST end | Stored as typed; shown on each day | PASS: wall-clock times kept as sent. **WARN**: the overnight event is not in `events.json` for its second day (15 Oct) | `calendar-dst.json` |
| DATE-07 | Day-first lab importing dates | Lab setup date style "day" (26 Sep 2026); import `03/04/2026`, `05/06/2026`, `11/02/2026` | Read day first, or ask; no future birth dates | **FAIL**: read month first (4 Mar, 6 May, 2 Nov) with only the note "read month first". **2 Nov 2026 is in the future and was imported**, a birth date every other path refuses. Add many from CSV also reads month first | `dayfirst-import.txt` |
| DATE-08 | Fly flips due at different temperatures | Stocks 1 rack (flipped 09-09) in an incubator set to 18, "18.0", "18 °C", 21, 29, 30 and "abc" °C | 18 → +28 d, 29 → +10 d, others per the preset | PASS: 18/"18.0"/"18 °C" → 10-07, 29 → 09-19, 25 °C rack → 10-04. **WARN**: 21 °C and 30 °C (not in the table) get the 25 °C schedule (14 d), not the nearest (18 d, 10 d); the code comment says "then to the nearest" | `flips.json` |
| PAR-01 | SQLite and PostgreSQL run the same scenario | Same starting lab (migrated); 58 observations: creates, 17 searches, API lists and filters, order of sheets and exports, Home counts, calendar, far dates, sac on dead mice | Same results | **FAIL/WARN**: 16 differ, from 3 causes (next rows). Order of sheets, API and export, and case-insensitive ASCII search (`dat`/`DAT`, `ai14`/`AI14`), are identical | `parity-sqlite.json`, `parity-pg.json` |
| PAR-02 | Over-long value | Transgene of 300 characters (column holds 200) | Same on both | **WARN**: SQLite saves it; PostgreSQL refuses: "One of the values is longer than its field allows (200 characters), so nothing was saved." | as above |
| PAR-03 | Case-insensitive search beyond ASCII | Search `δ-cre` for "Δ-Cre/+ αβγ" and `CAFÉ` for "Café" | Found on both | **FAIL**: PostgreSQL finds both; SQLite finds neither (desktop and SQLite labs) | as above |
| PAR-04 | Calendar time with an offset | POST `/calendar/items` with start `2026-10-21T10:00:00+05:30` | Same on both | **WARN**: SQLite stores 10:00; PostgreSQL stores 04:30. A `Z` time is stored as wall-clock 14:00 on both. The calendar page itself sends offset-free times | as above |
| PAR-05 | API reply to a refused value on PostgreSQL | API `PATCH /api/v1/mice/1` with a 201-character transgene | JSON 400 | **FAIL**: `302` to `/home`. A client that follows it gets the HTML sign-in page with 200 | (console; `app.py:399–411`) |
| PAR-06 | `%` and `_` in search | Search `%` and `_` | Literal characters | **WARN**: both match everything, on both databases (LIKE wildcards are not escaped) | as PAR-01 |
| PAR-07 | Undo → redo → undo on PostgreSQL | UNDO-12 repeated | Mice back in their cages | **FAIL**: same as SQLite | `parity-pg-undo.txt` |

Totals: **56 tests**: 30 PASS, 14 FAIL, 12 WARN. 17 of the PASS rows also carry a WARN note, which is counted in Findings.

INT-03 differences:
- Transgene 2–4 go to the notes. Genotype loses them for 8 of 55 mice (`DAT-IRES-Cre/+; Ai14/+` → `DAT-IRES-Cre/+`).
- Active, Age_weeks and Age_days are added to every note (55/55).
- Status `breeding` becomes `breeder` (21).
- Owner alex becomes the importer, as expected because the fresh lab has no alex.
- Cage, rack, position, litter, DOB, DOD, sex and all tricky text: identical.

INT-04 differences:
- Line breaks are lost (`line1line2line3`), so those rows don't match.
- Empty cells are exported as "–". On import they become values: the notes get "Sequence: –", "Incubator: –", "Next: –", and reagent fields `storage_temp` and `hazard` become "–".
- Reagent numbers are not kept (#15 → #8). The "#" column becomes a new field with the internal key `organism`.
- Plasmid and vial IDs, Unicode, `001`, `1E5`, `=1+1` and tabs survive.

## 3. Findings

Ranked by severity. Each gives the steps to reproduce, what happened against what was expected, the evidence and the
suspected cause.

### F1: Undoing a redo empties the mice's cage, and the Audit log says the opposite (critical: data corruption)
- **Steps**:
  1. Tick 2 mice and use **Set → Cage = new**.
  2. In **Batches**, undo it. The undo is correct.
  3. Undo the undo (redo). This is also correct.
  4. Undo that.
- **Happened**:
  - Both mice now have no cage (`cage_id_fk` NULL).
  - The audit rows of that undo say `cage_id_fk: 49 → 47` and `49 → 48`.
  - The Batches flash says "Undid 3 change(s)".
  - Same on SQLite and PostgreSQL.
- **Expected**: the mice are back in cages 47 and 48, as step 2 did.
- **Evidence**:
  - `evidence/undo-redo-undo-sqlite.txt`, `evidence/parity-pg-undo.txt`;
  - first seen on demo mice #6–#8 (`undo-results.txt`, `final_residue_n: 9`);
  - script: `scripts/undo_redo_undo.py`.
- **Suspected cause**: `app/undo.py`:
  - Entries are reversed newest first (lines 106–110).
  - In a redo batch the re-inserted cage is logged *after* the mouse updates, because inserts are logged in `after_flush`
    and updates in `before_flush`. So undoing the redo meets the cage's "create" first.
  - `_unlink_references` (lines 204–234) sets the mice's `cage_id_fk` to NULL and the cage is deleted.
  - The later `setattr(row, field, 47)` is then lost when the ORM flushes the delete of the parent (the relationship
    nulls its children).
  - Any batch whose reversal deletes a row that other reverted rows point at is at risk.

### F2: A lab copy taken while people are working is inconsistent; loading it loses links (high)
- **Steps**:
  1. On a server (PostgreSQL or SQLite), have 3 people add mice in new cages.
  2. Take `GET /api/lab-copy/snapshot`. The desktop app's *Keep a copy* does this daily.
- **Happened**:
  - 10 of 10 copies had mice whose `cage_id_fk` names a cage missing from the copy (1–11 each).
  - `PRAGMA integrity_check` says `ok`, so the desktop app would keep it as a good copy.
  - `migrate-to-postgres.py` on such a copy "cleared the reference": the restored lab has those mice with no cage.
- **Expected**: a copy is a single point in time (every table from the same transaction).
- **Evidence**: `evidence/snapshot-race-par-pg.json`, `snapshot-race-par-sqlite.json`, `race-*.db`,
  `migrate-race-snap.log`; script: `scripts/snapshot_race.py`.
- **Suspected cause**: `app/lab_copy.py:194`. `write_snapshot` reads table after table on one `engine.connect()`
  without a snapshot isolation level. On PostgreSQL READ COMMITTED, each SELECT sees newer commits. Parents (cages) are
  read before children (mice), so a mouse and cage committed in between appear as an orphan. The copy should be read
  in one REPEATABLE READ / serializable transaction (on SQLite, one explicit read transaction).

### F3: Editing any cell of a row removes line breaks from its note and transgenes (high: silent change)
- **Steps**:
  1. Have a mouse whose note has line breaks. The importer writes notes like this itself ("Healthy\nID in the
     spreadsheet: R1\nCoat: black"); the API or a pasted cell can too.
  2. In the mice sheet, change only its **Sex**.
- **Happened**: the autosave also rewrites note, transgene_1 and genotype without the line breaks
  ("HealthyID in the spreadsheet: R1Coat: black"). Seen in Chromium.
- **Expected**: only Sex changes.
- **Evidence**: `evidence/newline-autosave.json`/`.png`, `import-note-squashed.json`/`.png`;
  script: `scripts/newline_autosave.py`.
- **Suspected cause**:
  - The note and transgene cells are single-line `<input value="…">`: `app/templates/colony.html:247, 279`, and the
    cage card's mouse rows at `:679, :688`. Browsers strip CR/LF from an input's value.
  - The row form posts every field, and `populate_mouse_from_form` (`app/app.py:1006`) saves them all.
  - The same stripping is visible in the browser Export CSVs (F8).

### F4: Sac on mice that are already dead replaces their date of death with today (high: silent change)
- **Steps**: tick mice that died earlier (the sheet shows deaths of the last 90 days, and the header box ticks every
  visible row), then press **Sac**.
- **Happened**: 2026-09-26 → 2026-09-29 and status `sacrificed` → `sac`. **Set → Status = sac** on the same mice keeps
  2026-09-26. Undo restores it, if someone notices.
- **Expected**: an existing date of death is kept, as the status rule does.
- **Evidence**: console run in the session, and `parity-*.json` key `bulk-sac-dead` (both databases).
- **Suspected cause**: `app/app.py:2638–2639` sets `date_of_death = date.today()` without checking it first. It also
  doesn't call `stamp_updated`, so "updated by" isn't set.

### F5: Day-first dates are read month first, and import accepts a birth date in the future (high: wrong data)
- **Steps**:
  1. In Lab setup, set the date style to "26 Sep 2026" (day first).
  2. Import mice with DOB `03/04/2026`, `05/06/2026`, `11/02/2026`.
- **Happened**:
  - Stored as 2026-03-04, 2026-05-06 and **2026-11-02**. The only sign is the preview note "read month first".
  - The last is in the future, and the mouse was imported (age 0). The New mouse form, Add many, litters and the API
    all refuse a future birth date.
  - Add many from CSV also reads month first.
- **Expected**: an ambiguous column follows the lab's date style (or asks), and a future birth date is refused as
  everywhere else.
- **Evidence**: `evidence/dayfirst-import.txt`.
- **Suspected cause**: `app/sheet_import.py:324–374` (`tidy_dates`) never reads `lab.date_style()`, and `MiceTarget.create`
  doesn't apply `future_birth`. The same applies to `app/app.py:2947–2976` for Add many.

### F6: Mice export → import doesn't give the same mice back (medium)
- **Steps**:
  1. Export the mice as CSV (**Excel** is not accepted at all; see F7).
  2. Import the file with **Import from Excel** in a lab with the same people and racks, using the suggested matches.
- **Happened**:
  - Transgene_2–4 go to the notes, not the genotype. 8 of 55 mice lost part of their genotype
    (`DAT-IRES-Cre/+; Ai14/+` → `DAT-IRES-Cre/+`).
  - Active, Age_weeks and Age_days are added to every note.
  - Status `breeding` → `breeder`, and `dead` → `sac`, `stock`/`holding` → `experiment` (`MOUSE_STATUSES`,
    `sheet_import.py:456`).
- **Expected**: the app's own export re-imports field for field.
- **Evidence**: `evidence/roundtrip_mice_diffs.json`, `roundtrip_mice_preview.html`; script: `scripts/roundtrip_mice.py`.

### F7: The "Excel" mice export is tab-separated text that Import from Excel refuses (medium)
- **Steps**: Mice → **Excel**, then import that file.
- **Happened**: the download is `mice_export.xls`, which is TSV with `application/vnd.ms-excel`. The importer says
  "That's an old-style .xls file… Save As… (.xlsx)".
- **Expected**: an `.xlsx` file that re-imports.
- **Evidence**: `evidence/mice_export_all.xls`.
- **Suspected cause**: `app/services.py:1256–1309` and `app/sheet_import.py:148–150`.

### F8: The browser's Export writes "–" for empty cells and drops line breaks; re-importing stores the "–" (medium)
- **Steps**: Plasmids, Reagents or Drosophila → **Export**, then import the CSV into a fresh lab.
- **Happened**:
  - Empty Box, Sequence, Stored at, Hazard, Incubator and Next cells are exported as "–". On import they become values:
    "Sequence: –" in the notes, and reagent fields `storage_temp`/`hazard` set to "–".
  - Line breaks are gone.
  - Reagent item numbers are not kept (#15 → #8).
  - The "#" column becomes a new column with the internal key `organism`: `sheet_import.py:935` uses
    `slugify(label) or "column"`, but `slugify` returns "organism" for any non-Latin header, so the fallback never runs.
- **Evidence**: `evidence/browser-export-*.csv`, `roundtrip-sheets.json`.
- **Suspected cause**: `app/static/data-table.js:552–560` (`_cellText` exports the placeholder text and collapses
  whitespace).

### F9: Weaning is not a batch, so it can't be undone (medium)
- **Steps**: a cage with a litter → **Wean**, or **Wean and distribute** two pups into a new cage.
- **Happened**: no entry in Batches. The moves, the new cage and the cleared birth date can only be undone by hand.
  The README says "Every bulk action can be undone".
- **Evidence**: `evidence/undo-results-2.txt`.
- **Suspected cause**: `app/app.py:3778–3927` has no `audit.batch(...)`.

### F10: Small numbers from an Excel workbook become 0 (medium: silent change)
- **Steps**: import an `.xlsx` into Reagents with a numeric Concentration cell of `1.5E-07`.
- **Happened**: stored as "0".
- **Evidence**: `evidence/xlsx-import.txt`, `tricky.xlsx`.
- **Suspected cause**: `app/sheet_import.py:102`. `format(value, "f")` keeps only 6 decimals.

### F11: SQLite search is not case-insensitive beyond A–Z (medium: parity)
- **Steps**: search `δ-cre` or `CAFÉ` on a SQLite lab (every desktop app) and on a PostgreSQL server.
- **Happened**: PostgreSQL finds "Δ-Cre/+ αβγ" and "Café"; SQLite finds nothing.
- **Evidence**: `evidence/parity-*.json`, keys `search:δ-cre` and `search:CAFÉ`.
- **Suspected cause**: SQLite's built-in `lower()`/`LIKE` fold ASCII only.

### F12: The API answers a refused value with a redirect to /home (medium)
- **Steps**: on PostgreSQL, `PATCH /api/v1/mice/1` with a 201-character transgene.
- **Happened**: `302 Location: /home`. A client that follows it gets the HTML sign-in page with 200, so a script can't
  tell that nothing was saved.
- **Expected**: 400 JSON with the message.
- **Suspected cause**: `app/app.py:399–411` `handle_data_error`, and `IntegrityError` just above it, handle only
  `X-Autosave`, not `/api/v1`.

### F13: Import cuts long text to the column's length without saying so (medium)
- **Steps**: import a Name of 210 characters and a Vendor of 200.
- **Happened**: stored as 200 and 120 characters. The preview shows no note.
- **Evidence**: `evidence/sheets-import-fidelity.json`.

### Low
- **L1**: SQLite lets forms save values longer than the column: a 300-character transgene in `String(200)`. PostgreSQL
  refuses them, and migrate-to-postgres later blocks on them until they are edited (PAR-02, INT-06).
- **L2**: Undo doesn't restore `updated_at`/`updated_by`, so "last edited by" still names the undone bulk edit (UNDO-02).
  Sac doesn't set them at all.
- **L3**: The API's and **Set → Transgenes**' `genotype` splits on commas (`services.split_genotype`, `app/services.py:846`),
  so a transgene name containing a comma becomes two, and sending a mouse's own genotype back changes it (TEXT-08).
- **L4**: The cage card's Genotype line can't be read back ("; " both inside and between genotypes). The rack grid shows
  only first transgenes (VIEW-03).
- **L5**: ZPL: raw line breaks inside `^FD`; `^A0` can't print CJK, emoji or right-to-left text. Not checked on a
  printer (TEXT-05).
- **L6**: Exports are not protected for Excel: `=…` formula injection, `001`/`1E5`/`3/4` coercion, and no UTF-8 BOM on the
  server's CSV. Checked by inspection only (TEXT-06). The browser Export's file name uses the UTC date, not the lab's.
- **L7**: A calendar event that crosses midnight is not returned for its second day. A time with an offset is stored
  differently on SQLite (offset dropped) and PostgreSQL (converted to UTC) (DATE-06, PAR-04). `_parse` is at
  `app/app.py:4637`.
- **L8**: An incubator at a temperature not in the table (21 °C, 30 °C) gets the default 25 °C flip interval, not the
  nearest, contrary to the comment in `stock_service.ModuleView.interval` (DATE-08).
- **L9**: After a lab time-zone change, workers disagree on today's date for up to about 30 s (DATE-02; by design of
  `lab.refresh_timezone`).
- **L10**: `/calendar/events.json` returns 500 for windows in year 1 or 9999. Invalid typed dates in a non-browser POST
  are dropped silently (DATE-03, DATE-04).
- **L11**: `%` and `_` in search are LIKE wildcards and match everything (PAR-06).

## 4. Numbers

- Values compared in full-database diffs:
  - SQLite → PostgreSQL: 5,990 values in 34 tables, 0 differences;
  - lab copy: 6,007;
  - lab copy → PostgreSQL: 6,008.
- Mice round trip: 55 mice × 17 fields. Other sheets: 45 rows (15 per sheet) × 4–7 fields.
- Undo: 14 batch actions, each done → undone → redone → undone, with 7 tables compared in full at every step.
- Views: 9 mice × up to 9 places, before and after 5 changes in 5 different places.
- Parity: 58 observations; 16 differ, from 3 causes.
- Lab copy race: about 870 mice (PostgreSQL) and 655 (SQLite) added during 6 and 4 snapshots; 1–11 orphaned mice per
  snapshot.
- Sizes and times: the demo lab builds in 4.0 s; a lab copy of the demo is 1.28 MB; migrate-to-postgres of the demo takes
  about 3 s.
