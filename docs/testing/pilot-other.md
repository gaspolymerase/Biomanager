# pilot-other: fish/fly/worm lab and inventory lab (BioManager 0.10.2 + icon, pre-1.0)

## 1. Scope and environment

Simulated pilot labs 2 and 3 from `docs/PILOT.md`, a zebrafish / *Drosophila* / *C. elegans* lab that also keeps a custom
*Xenopus* database and its own inventories, driven through the UI with Playwright as three fictional users:

| User | Role | Used for |
| --- | --- | --- |
| `ada` (Ada Fishwick) | first admin | setup survey, approvals, Xenopus database, receiving orders |
| `ben` (Ben Zebra) | member | fish room, Xenopus, plasmids import, custom inventory |
| `cara` (Cara Vial) | member | flies, worms, orders, reagents, viruses, plasmids, calendar |

- **Code**: the repository, read-only (master, v0.10.2 + icon). Nothing edited.
- **Server**: `run.py` dev server on 127.0.0.1:5102 (`scripts/start.sh`).
  - **SQLite (desktop-style)**: fresh lab in `lab/`, no demo data. Every record was made through the UI or Import from Excel.
  - **PostgreSQL 16**: container `pg-pilotother` on host port 55502. The lab's own keep-a-copy snapshot was loaded with
    `scripts/migrate-to-postgres.py`, and the key flows were repeated on it (section PO-87/88).
- **Lab time zone** set to `Pacific/Auckland` in the setup survey. The server ran on UTC, so the lab date (30 Sep) was
  a day ahead of the server date (29 Sep) throughout. Browsers ran in `America/Los_Angeles`, `America/New_York` and
  `Pacific/Auckland`, so every date was checked with three different clocks.
- **Browser**: Playwright Chromium 1194, headless, 1400×900, light and dark colour schemes.
- **Data at the end**: 417 rows in 36 tables. That is 7 tanks, about 19 fish rows, 16 vials, 4 plates, 3 frogs, 8 plasmids, about 35 inventory
  items across 6 inventories, 2 calendar items and 2 to-dos (plus 2 by API), and 9 import runs.
- **Evidence**: `evidence/steps.log` (590 lines: every step, URL, flash message and browser error), `evidence/shots/`
  (228 screenshots, named `<user>-<tag>.png`), page text dumps (`*.txt`), ZPL output (`lbl*.zpl`), the messy sheets
  (`evidence/files/`), a lab-copy snapshot (`evidence/snapshot.db`). Scripts are in `scripts/` (`s01`…`s95`, `lib.py`).
- No external service was contacted. The telemetry heartbeat was switched off in the survey. Chromium's own
  background connections to Google were refused by the proxy.
- Server and container were stopped and removed at the end.

## 2. Test log

| ID | What | How (steps, users, data) | Expected | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| PO-01 | First admin | `/register` with the printed setup code, as ada | admin created, sign-in page | PASS | s01; shots/admin-02 |
| PO-02 | Setup survey for a fish/fly/worm lab | ada ticks Zebrafish, Fruit flies (18, 25 °C), C. elegans (20 °C), Plasmids, all five inventories, Calendar, Notebook, members-keep-copies; mouse colony off; heartbeat off; lab name `Tank & Vial Lab <b>&amp;</b>`; zone Pacific/Auckland | only those databases, incubators per temperature; name escaped | PASS (incubators 18/25 and 15?/20/25 made; the name was shown literally on the member welcome page) | s03; shots/admin-05 |
| PO-03 | Members join | ben and cara register → "awaiting approval"; ada presses Approve (confirmation dialog) | pending until approved, then sign in | PASS | s04; shots/admin-06/07 |
| PO-04 | "Today" follows the lab | Home at 17:04 UTC | "Good morning … Wednesday, Sep 30" (Auckland) | PASS | shots/admin-05 |
| PO-05 | Water system | ben: System A, target 28.5 °C / pH 7.4 / 500 µS | saved with targets | PASS | shots/ben-zf-10 |
| PO-06 | Fish rack on a system | Rack grid → New rack, 5×6, System A | rack A1–E6 | PASS | shots/ben-zf-11 |
| PO-07 | Lines with awkward names | `Tg(kdrl:EGFP)` (ZFIN name, allele) and `casper^mut ~x_y é` | saved and shown as typed | PASS | shots/ben-zf-12/13 |
| PO-08 | Tanks at positions | T-001 at A1, T-002 at A2 | placed (row/col 0,0 and 0,1) | PASS | DB check |
| PO-09 | Tank at an occupied position | New tank T-003 / T-005 at A1 | refused or clearly created | WARN: tank is created unplaced, but the red message reopens the **New tank** dialog with the same values; pressing Create again gives "T-005 is already used by another tank" | shots/ben-zf-16, zf-18, zf-19 |
| PO-10 | Tank position outside the rack | T-004 at Z9 in a 5×6 rack | clear message | PASS ("“Z9” is not a position in Rack Z1 (A1–E6)", created unplaced) | steps.log |
| PO-11 | Fish rows | 12 mixed in T-001; male M1 in T-002; 2 F in T-003 | rows, ages in mpf, Fish tab counts 18 | PASS | shots/ben-zf-20..22 |
| PO-12 | Fish with a future fertilisation date | 3 F, fertilised today+40 d | refused (the colony refuses future births) | WARN: accepted (2026-11-08), age shown "–" | DB `fish` #4 |
| PO-13 | Negative fish count | count −5 | refused | PASS (the form's own validation stops it) | shots/ben-zf-24 |
| PO-14 | Mating | Set up a mating: T-002 ♂ × T-003 2 ♀, return in 3 days | mating tank, return date in the lab's days | PASS ("MT001 … return by Oct 3" = lab date + 3; server date + 3 would be Oct 2) | shots/ben-zf-25 |
| PO-15 | Return a mating | return dialog on MT001 → Returned | fish back in their tanks, MT001 retired, undoable | PASS ("1 fish to T-002, 2 fish to T-003"; DB confirms) | shots/ben-zf-31 |
| PO-16 | Clutches | New clutch 150 embryos | ID `C<lab date>-n` | PASS (C260930-1) | DB `clutches` |
| PO-17 | Water reading outside the targets | log 31.2 °C, pH 6.1 against 28.5 / 7.4 | flagged or highlighted | WARN: shown plainly ("Latest … 31.2 °C · pH 6.1"); no alarm, no colour; a single reading draws an empty chart | shots/ben-zf-28 |
| PO-18 | Tank labels, HTML | Tank labels (no tick = all) | one card per active tank, retired MT001 left out, printed date in the lab's days | PASS (5 cards, "Printed 2026-09-30") | shots/ben-lbl_labels_cards_tanks |
| PO-19 | Tank labels, ZPL | `?format=zpl&stock=` 51x25, 102x64, 33x13; `s14_labels.py` checks ^XA/^XZ balance, ^FH_ in every field, no raw `^`/`~` in field data, only valid `_hh` escapes, QR within the label | valid ZPL | PASS (`casper_5Emut _7Ex_5Fy é`; ^CI28; QR 5 dots/module fits 200-dot height) | lbl_labels_cards_tanks-*.zpl |
| PO-20 | ZPL response header | same downloads | `text/plain; charset=utf-8` | WARN: `Content-Type: text/plain; charset=utf-8; charset=utf-8` (duplicated) | steps.log `[labels]` |
| PO-21 | ZPL characters outside the printer font | vial genotype `…_x~ Δ`, `×` | substituted or warned | WARN (not verified on a printer): only ♀ ♂ — – are replaced; Δ (and α, β…) are sent as UTF-8 to font 0, which is unlikely to have Greek glyphs | lbl_labels_cards_stocks_drosophila-51x25.zpl |
| PO-22 | Incubator with a non-numeric temperature | New incubator "Bench (room temp)", temperature `RT` | a clear rule | WARN: flash says "the nearest listed temperature is used", but there is no nearest for "RT"; it silently uses the default 25 °C (14-day flips) and shows "RT °C" | shots/cara-fly-10; drosophila-racks.txt |
| PO-23 | Fly racks follow the incubator temperature | F18-A (18 °C, last flip −20 d), F25-A (25 °C, −16 d), RT-1 | 28 d / 14 d; next and overdue by the lab date | PASS ("28 d (18 °C) … in 8 d", "14 d (25 °C) … 2 d ago") | drosophila-racks.txt |
| PO-24 | Vials | stock, stock with `^ ~ _ Δ`, cross (♀ w; UAS-X × ♂ elav-GAL4, set up −3 d), stock at B3; one at an occupied cell | created at positions; occupied refused | PASS ("F25-A · A1 is already taken") | shots/cara-fly-13* |
| PO-25 | Fly schedule | Schedule tab | flip F25-A 2 d overdue; collect V3 due yesterday (2 d at 25 °C) | PASS | drosophila-schedule.txt |
| PO-26 | Collect eggs and Flipped today | Collect eggs on V3 from Schedule; Flipped today on F25-A | progeny vial in the next free cell, eclose +10 d at 25 °C; next flip +14 d | PASS ("new vial V5 at F25-A · A3; eclose around 10 Oct"; "next on Wed 14 Oct") | shots/cara-drosophila-21/22 |
| PO-27 | Temperature change after collection | move the progeny vial V5 and the cross V3 from 25 °C to the 18 °C rack | both schedules follow 18 °C | **WARN**: the cross's next collection follows (4 d at 18 °C), but the progeny's eclosion stays at 10 Oct (25 °C timing); at 18 °C it is 19 d (19 Oct) | drosophila-schedule-moved.txt; DB `stock_units` #5 |
| PO-28 | C. elegans | boxes W15/W20/W25 (sequential 1–20), plates N2, `unc-119(ed3) III…`, cross dpy-5 × him-5 | chunk 12/7/4 d by temperature; pick progeny 1 d at 25 °C | PASS (8 d overdue, today, 2 d overdue: all correct against the lab date); "A1" in a sequential box refused clearly | c_elegans-schedule.txt |
| PO-29 | Home: flies and worms due | Home as cara | overdue flip and collection listed | PASS | drosophila-home-before.txt |
| PO-30 | Add database: custom organism | ada: Custom organism "Xenopus", frog/tank/rack/line/clutch/mating, weeks, hybrid counting, 10 capabilities, whole lab; description containing `<script>` | database made; text escaped | PASS (script shown as text) | shots/ada-org-12 |
| PO-31 | Custom fields | select (good, fair, poor), date, required number on housing; the same name twice | added; duplicate refused | PASS ("already has a field “Oocyte quality”") | steps.log `[org-20-*]` |
| PO-32 | Schedule rules | Tank clean: housing, last serviced +7 d, recurring; Metamorphosis check: cohort birth +56 d with `18:80, 23:56, 25:45` | rules saved | PASS (stored with temp offsets; the temperature variant was not reached within the 21-day window, so not checked end to end) | org-settings.txt |
| PO-33 | Member adds a rack to the lab's Xenopus database | ben: Tanks → Rack grid → New rack | either allowed or the button hidden | WARN: button shown, the save is refused ("Only an admin or whoever created this database can change its setup") and ben lands on Configure | shots/ben-org-30-rack |
| PO-34 | Housing, animals, cohorts | ben: tank XT-1 without the required water volume (blocked by the form), then with 12.5 L; frog XF-1 with custom fields; clutch XC-1 | saved; "Tank clean" 2 d overdue | PASS (attrs in DB; schedule "Sep 28 · 2d overdue") | org-schedule-after.txt |
| PO-35 | Experiment on a custom organism | Experiments → New experiment (body weight), Add frogs XF-1 in group HCG | experiment page with the frog | PASS (weighing not tested) | shots/ben-org-43 |
| PO-36 | Plasmid box and GenBank | cara: 9×9 box; upload GenBank with a CDS, a complement promoter, a wrap-around `join(2800..3000,1..50)` origin, `^ ~ _ é` in a note | map, features, sequence | PASS (3000 bp, 3 features, wrap-around kept as start 2799 → end 49; map renders) | shots/cara-pl-13-map |
| PO-37 | FASTA upload | 2730 bp FASTA | sequence kept | PASS | steps.log |
| PO-38 | Broken GenBank | `CDS 5..zz`, sequence `acgtnnnxyz` | refused or warned | WARN: "Added plasmid #3 with a GENBANK sequence (8 bp · 0 features)"; x, z and the bad feature are dropped with no word | DB `plasmids` #3 |
| PO-39 | Unreadable .dna | garbage file named `.dna` | clear message | PASS ("isn't a sequence file this app can read … saved without a sequence") | steps.log |
| PO-40 | Occupied box well | pDup at A1 | placed or clearly unplaced | PASS ("already holds plasmid #1 … in Plasmid box 1 but not placed") | steps.log |
| PO-41 | Viruses: Made from | virus from `pAAV-CAG-EGFP` (by name), `#2` (by number), `pDoesNotExist` | links both ways; warning for unknown | PASS (virus rows link to /plasmids/1 and /2, each plasmid page lists its virus; "saved as typed" warning) | tmp_pl.py output in steps.log |
| PO-42 | Orders: request | cara: 3 orders (reagent, antibody, virus) with vendor, catalogue no., quantity, price, grant | requested | PASS | shots/cara-ord-10..12 |
| PO-43 | Order incomplete | status *ordered* with no vendor/catalogue/quantity | refused | PASS (the form blocks it) | shots/cara-ord-13 |
| PO-44 | Board | ada drags cards requested → ordered → received | status changes, received date, requester told | PASS (received_on = lab date 2026-09-30; cara's bell shows "Your order … was received by ada") | shots/ada-ord-20/21; home-tracks.txt |
| PO-45 | Add it to stock | on received: Add to stock → Reagents / Antibodies / Viruses | a stock record with name, vendor, catalogue no., quantity | PASS (all three; on PG the target defaulted to Antibodies for an antibody order) | shots/ada-ord-30/31, ada-pg-04 |
| PO-46 | Who owns the new stock record | as above (order by cara, received by ada, "Lab common") | the requester or the lab | WARN (low): owner is ada, the person who dragged the card, not the requester | DB `inventory_items` 4–6 |
| PO-47 | Receive twice | received → ordered → received again (PG) | no second offer | PASS (no dialog) | shots/ada-pg-05 |
| PO-48 | Order again | cara: cart button on reagent Tricaine | new order prefilled with vendor, catalogue no., quantity, price and grant | PASS (notes "Reorder of Reagents #1") | steps.log `[ord-40]` |
| PO-49 | Reagents: lot, expiry, low | PFA (lot, CAS, toxic, expires +10 d), Proteinase K expired −5 d, Agarose low, Tris +60 d, one expiring today; antibody expiring +20 d | Home "Expiring & low stock" lists expired, today, 10 d, 20 d, low, not 60 d | PASS | home-cara-inv.txt |
| PO-50 | Calendar auto items | events.json over 60 days | flips, chunks, collections, eclosion, tank clean, expiries on their dates | PASS (17 items, all on the dates computed above) | cal-events.json |
| PO-51 | Samples | ben: DNA sample from fish row 1 | saved with source | PASS; WARN (low): the source list offers **mouse** in a lab without the mouse colony, and no fly or worm vials | inv-samp.html |
| PO-52 | Member's own inventory | ben: New inventory "Morpholinos" (custom); "The whole lab" is disabled for members; Configure: quantity, supplier, expiry, storage + 3 columns (text, select, number) | a private database with the columns | PASS (`private_to=ben`; item saved with the three attrs; cara gets 404 for it) | shots/ben-inv-custom-*; lbl…morpholinos 404 |
| PO-53 | Import fish (messy sheet) | title row, merged cells, blank rows, `Male/♀/m/F/mixed/X`, `7 ` as text, −3 count, Total row, formula cell | matched, previewed, one batch | PASS for rows, count, sex, total, bad row (row numbers as in Excel) | imp-fish-preview.txt |
| PO-54 | Import fish: "DOF" column | same sheet, header `DOF` | fertilisation date | WARN: "DOF" (the usual fish-room abbreviation) is not matched and goes **into the notes** by default; it has to be mapped by hand | imp-fish-match.txt |
| PO-55 | Import makes new tanks and lines unasked | rows naming tank `T-099` and lines `AB`, `Unknown line` that don't exist | said in the preview, or refused | WARN: tank T-099 and two lines are created silently; the preview only says "2 in T-099" | DB `tanks` #7, `fish_lines` 3–4 |
| PO-56 | **Import dates written dd-mm-yy** | DOF mapped by hand: `15-03-26`, `31-12-25`, `03/04/2026`, `5 Mar 2026`, `2026-13-01`, an Excel date | 15 Mar 2026, 31 Dec 2025, or a warning | **FAIL**: `15-03-26` saved as **2015-03-26** and `31-12-25` as **2031-12-25**, with no warning (the preview warns only about the slash date and the two blanks). The same on PostgreSQL | imp-fish3-preview.txt; DB fish 16–17; PG fish 26–27 |
| PO-57 | Import: text month dates | `5 Mar 2026` | read (README: "Excel dates in any style") | WARN: left blank ("isn't a date"), so any CSV exported with `d-mmm-yy` dates loses them | imp-fish3-preview.txt |
| PO-58 | Undo an import from Batch history | ben undoes the imports | records gone | WARN: works, but "undo of batch #N" rows are themselves undoable at the top of the list. Undoing one re-creates the import while the import row still reads "undone by ben". The only way out is "Undo anyway" on a batch warning that it will throw away later edits | batches-after.txt; shots/ben-batches-* |
| PO-59 | Import flies | `Stock #`, genotype with `::` and `^ ~ _`, Rack/Slot, owner by display name, unknown owner, bad slot Z9, missing rack, duplicate slot, no-genotype row, Excel number date, `Bloomington #` | each problem in the preview, by Excel row | PASS (all five reported; "Cara Vial" matched to cara). WARN (low): "Date set up" is not matched (goes to notes) | imp-flies-preview.txt |
| PO-60 | Import reagents | `Item/Supplier/Cat. No./Lot/Expiry/Location/Qty/Hazard class/Price (€)`; day-first `13/02/2027` and `01/03/2027`; `expired`; Total | day-first for the whole column; location as a note | PASS (2027-02-13, 2027-03-01; "expired" blanked with warning; Total left out) | DB reagents 14–17 |
| PO-61 | Import plasmids CSV | UTF-8 BOM, multi-line cell, `é^~_`, occupied well, a `=HYPERLINK(...)` name, a nameless row | preview lists problems | PASS (formula-looking name stored as text; export not checked) | imp-plasmids-preview.txt |
| PO-62 | Import Xenopus | IDs, tank, `Female/M/F`, `Born` mixed ISO/slash, select column `Good` / `excellent`, a duplicate ID | duplicates skipped; select values checked | PASS for the duplicate (skipped); WARN (low): `excellent` and `Good` saved in the good/fair/poor select without a word | DB `organisms` XF-10/11 |
| PO-63 | Import orders | `What/Vendor/Catalog #/Qty/Status/Requested by/Cost/Grant` | item matched | WARN (low): "What" isn't matched to the item, so it stops at "Match a column … for: Item"; Cost and Grant go to notes rather than price and account | steps.log `[imp-orders]` |
| PO-64 | Import custom inventory | Morpholinos sheet with an extra column | new column made | PASS ("New column “Injected dose (ng)”") | steps.log `[imp-morph]` |
| PO-65 | Import a non-workbook and an empty workbook | garbage.xlsx, empty.xlsx | clear messages | PASS | steps.log |
| PO-66 | Wording after imports | any import with a skipped row | "1 row was skipped" | WARN (cosmetic): "1 rows were skipped" (sheet_import.py:1349) | steps.log |
| PO-67 | Labels for every stock | vials, plates, Xenopus tanks, reagents/viruses by `?ids=` | valid ZPL, escapes | PASS (10 vial, 4 plate, 1 tank, 2+2 inventory labels; no problems found by the checker) | lbl_*.zpl |
| PO-68 | Inventory labels with nothing ticked | Reagents → labels URL with no ids | all, or "tick some first" | WARN (low): "Nothing to print here yet." while the list has items (vials and tanks print all) | shots/cara-lbl_labels_cards_inventory_reagents |
| PO-69 | Home layouts | cara: Classic, Tracks, Freezer | each renders its due/expiring content | PASS (Tracks: lab 2026-09-30…10-13, 15 items; no browser errors) | home-*.txt; shots/cara-home-* |
| PO-70 | Calendar event | cara (browser New York): New event 2 Oct 09:00–10:30 | stored as typed; on Home "Next 14 days" | PASS | DB `calendar_events`; home-classic.txt |
| PO-71 | To-do "today" with the browser in another zone | cara (New York, 29 Sep) → New event ▸ To-do, due preset | due in the lab's day | WARN (low): due saved as 29 Sep (the browser's today) while the lab's today is 30 Sep; the calendar highlights 29 as "today" while Home says Wed 30 | DB `tasks` #1; shots/cara-cal-11-task |
| PO-72 | To-dos on Home | to-dos due yesterday, today and in 3 days | on Home | WARN (low): no to-do appears anywhere on Home (Next 14 days shows events only) | tmp_task.py lines in steps.log |
| PO-73 | Search | ⌘K / `/search?q=` for lines, tanks, genotypes, plasmids, reagents, viruses, samples, frogs, `é`, `^` | found; private DB only for its owner | PASS (morpholino found by ben, not by cara) | steps.log `[search]` |
| PO-74 | Search wildcards | `%`, `_`, `16%` | literal | WARN (low): `%` and `_` match all 38 records; `16%` matches anything containing "16" | steps.log `[search-ben]` |
| PO-75 | Search by vial/plate code and experiment | `V3`, `P3`, `HCG dose` | found | WARN (low): nothing; the code printed on the label (V3) can't be searched, nor the Xenopus experiment | steps.log |
| PO-76 | Settings: icon picker and appearance | cara picks zebrafish + peach | favicon and accent follow; bad names refused | PASS (`/app-icon/zebrafish/peach.svg` 200; injected glyph or colour 404); dark mode renders with the accent | shots/cara-home-dark, cara-sched-dark |
| PO-77 | Keep a copy: make a key | cara (members allowed): Settings → make a key "Lab iMac <b>" | key shown once | PASS | shots/cara-copy-1 |
| PO-78 | Snapshot with the key | curl `/api/lab-copy/snapshot` with the key; a wrong key | SQLite file, checksum header, integrity; 401 | PASS (SHA-256 header = file; integrity ok; row counts equal in all 85 tables; wrong key 401) | snap-headers.txt; snapshot.db |
| PO-79 | Desktop side of keep-a-copy | `s91_desktop_pull.py`: a desktop-mode (`LOCAL_SETUP`) app in `desk/` pulls from the lab | copy kept and checked | PASS (417 records, kept under `lab-copies/127.0.0.1_5102/db/`). WARN (low): the first try within 120 s of another copy says only "Too many requests. Try again in a few minutes." | steps.log; desk/ |
| PO-80 | Snapshot as a restore point | migrate the snapshot to PostgreSQL | loads | PASS (417 rows, 2.2 s). WARN (low): the snapshot has no `alembic_version` table, so the restore treats it as "pre-0.8" and runs every upgrade step | migrate output in steps.log |
| PO-81 | No internet | 18 pages (Home, calendar, notebook, every database, plasmid map, experiment, labels, settings, import, Add database) with every non-local request aborted | work, no external requests | PASS (0 external requests, 0 errors) | s92; steps.log `[offline]` |
| PO-82 | Help with no internet | Help → user guide | offline copy or a message | WARN (low): `/guide` redirects to the website, so it's a browser network error offline | s92 first run |
| PO-83 | PostgreSQL repeat of key flows | on the migrated lab: Flipped today, Collect eggs at 18 °C, order → board → Add to stock, tank at occupied cell, frog with custom select, search, fish and fly imports, tank/vial ZPL | same as SQLite | PASS (eclosion 19 Oct at 18 °C = 19 d; everything else identical, including the PO-56 date bug) | shots/*-pg-*; pg-schedule.txt |
| PO-84 | Errors | server logs of both runs, browser console, 5xx listener | none | PASS (0 HTTP 5xx, 0 tracebacks, 0 page errors) | lab/server.log, pgdata/server.log |
| PO-85 | Wrong URL | `/stocks/fly` (the kind, not the key) | a page with a way back | WARN (cosmetic): unstyled Werkzeug "Not Found" page with no link back | shots/cara-fly-01 |

**Totals: 85 tests. 55 PASS, 29 WARN, 1 FAIL.** Rows marked "PASS; WARN" or "PASS … WARN" are counted as WARN.

## 3. Findings

### F-1 (high): Import from Excel reads day-first dates with dashes and a two-digit year as yy-mm-dd, with no warning
- **Steps**: Fish → Import from Excel with `evidence/files/fish-messy.xlsx`. Map `DOF` → *Fertilised*, then Preview and
  Import.
- **Happened**: `15-03-26` (15 March 2026) was saved as **2015-03-26** and `31-12-25` (31 Dec 2025) as **2031-12-25**,
  a date in the future. The preview's "Worth a look" says nothing about either. It does warn about `03/04/2026`,
  `5 Mar 2026` and `2026-13-01`. The same happens on PostgreSQL.
- **Expected**: the column's day/month order is decided as for slash dates (the code already does this for
  `03/04/2026`), and `15-03-26` becomes 2026-03-15. At the least, a warning.
- **Why it matters**: this is silent wrong data on first import, the week-1 step the pilot checks. Any column
  typed `dd-mm-yy` is hit: fertilisation dates, set-up dates, reagent expiries, birth dates for any organism.
- **Suspected cause**: `app/sheet_import.py:348` calls `services.parse_date(raw)` before the day/month-first logic.
  `app/services.py:78` tries `"%y-%m-%d"` (and `"%y%m%d"`), so `15-03-26` parses as year 15, month 03, day 26. The
  `_SLASH` pattern (sheet_import.py:321) would have read it correctly.
- **Evidence**: `evidence/imp-fish3-preview.txt`, `evidence/shots/ben-imp-fish4-*`, DB rows fish 16–17 (SQLite) and
  26–27 (PG).

### F-2 (medium): Progeny eclosion date doesn't follow a temperature change
- **Steps**: cross V3 at 25 °C → Collect eggs, and V5 is due to eclose in 10 d (10 Oct). Edit V5 (and V3) → rack F18-A
  (18 °C).
- **Happened**: the cross's next collection moves to the 18 °C timing (4 d), but V5 still ecloses on 10 Oct. At 18 °C
  it should be 19 d (19 Oct), which is what a collection made at 18 °C gets (PO-83).
- **Expected**: "temperature-aware" schedules (README) move the eclosion date with the vial, or at least say it was
  kept.
- **Suspected cause**: `ready_on` is stored once at collection (`app/stock_service.py:330`), while flip and collect
  intervals are worked out on every read.
- **Evidence**: `evidence/drosophila-schedule-moved.txt`, `shots/cara-fly-26-schedule.png`.

### F-3 (medium): Import creates tanks and lines without saying so
- **Steps**: import a fish sheet naming tank `T-099` and lines `AB`, `Unknown line` that don't exist.
- **Happened**: all three are created. The preview says only "2 in T-099", and the result says "Imported 5 rows".
  A typo in a tank ID therefore makes a new tank.
- **Expected**: the preview lists "New tank T-099, new lines AB, Unknown line", or asks.
- **Evidence**: `evidence/imp-fish-preview.txt`; DB `tanks` #7, `fish_lines` #3–4.

### F-4 (medium): Batch history after an undo of an undo
- **Steps**: Batches → Undo an import. The new "undo of batch #13" row appears at the top with its own **Undo**; press
  it.
- **Happened**: the import's records come back, while the import row still reads "undone by ben · Sep 30". To remove
  them again, you must use "Undo anyway" on "undo of batch #14", which warns that later edits will be thrown away.
  Each undo is listed as action "update", and imports are described as "import 6 rows" when 5 were made.
- **Expected**: an undo can't itself be undone, or it's labelled "Redo". The import's state reflects its records.
- **Evidence**: `evidence/batches-after.txt`, `shots/ben-batches-1..3.png`.

### F-5 (medium): Fish import doesn't know "DOF"
- `DOF` (date of fertilisation, the usual fish-room header) is sent **into the notes** by default, so a lab that
  clicks through loses the dates into free text. Similarly "Date set up" for vials, and "What" / "Cost" / "Grant" for
  orders (low). Evidence: `imp-fish-match.txt`, `imp-flies-preview.txt`, steps.log `[imp-orders]`.

### F-6 (medium): Text-month dates are blanked on import
- `5 Mar 2026` (how Excel shows `d-mmm-yyyy` in CSV exports) is left blank with a warning. The README says "Excel dates
  in any style". Cause: `services.parse_date` has no month-name formats. Evidence: `imp-fish3-preview.txt`.

### F-7 (low–medium): "Created but not placed" reopens the New dialog
- A tank at an occupied position is created unplaced. The red flash triggers form-memory, which reopens **New tank**
  with the same values, so the natural next click (Create) gives "T-005 is already used by another tank".
  `static/form-memory.js` treats this partial success as a failure. Evidence: `shots/ben-zf-16`, `zf-18`, `zf-19`.

### F-8 (low): Unchecked values accepted
- A future fertilisation date for fish is accepted (PO-12), while the mouse colony refuses future births.
- Values outside a custom select's choices (`excellent`, `Good`) are saved on import (PO-62).
- A broken GenBank file is accepted, with the bad characters and the bad feature dropped silently (PO-38).

### F-9 (low): Water readings outside the targets are not flagged
- A reading of 31.2 °C and pH 6.1 against targets of 28.5 °C and pH 7.4 looks like any other reading. The chart is
  empty with a single point. Evidence: `shots/ben-zf-28-waterlog.png`.

### F-10 (low): Non-numeric incubator temperature
- An incubator with temperature `RT` gets the message "the nearest listed temperature is used", but really gets the
  module default (25 °C) and shows "RT °C" (`app/stock_routes.py:838`). Cosmetic: "Not in a incubator"
  (`templates/stocks/module.html:40`).

### F-11 (low): The calendar and to-dos use the browser's day, Home uses the lab's
- With the browser in New York (29 Sep) and the lab in Auckland (30 Sep), the calendar highlights 29 Sep and a to-do
  "today" is due 29 Sep, while Home says Wednesday 30 Sep. To-dos never appear on Home at all (PO-72).
- This matters little for a desktop user (same zone). It does matter for a lab server whose members travel, or when
  the lab zone differs from the laptops'.

### F-12 (low): Search
- LIKE wildcards are not escaped (`%` or `_` return every record; `app/app.py:5001`, `like = f"%{q}%"`).
- Vial and plate codes (`V3`, `P3`), which are printed on labels, can't be searched. Organism-database experiments are
  not searched either.

### F-13 (low): Labels
- The ZPL download's `Content-Type` repeats the charset (`app/labels.py:419`: `mimetype` already carries the charset,
  and Flask adds another).
- Greek letters common in genotypes (Δ) are sent unchanged to a Zebra font that likely lacks them. This is not verified
  on hardware.
- Inventory labels with nothing ticked show "Nothing to print here yet." rather than "tick items first".

### F-14 (low): Permissions shown but refused
- A member sees **New rack** in a lab-wide custom database but is refused on save and sent to Configure (PO-33).
- The Samples source list offers *mouse* in a lab without a mouse colony, and offers no fly or worm vials (PO-51).
- A stock record made from a received order is owned by whoever received it, not the requester (PO-46).

### F-15 (low): Keep-a-copy details
- A snapshot requested within 120 s of the previous one is refused with the generic "Too many requests".
- The snapshot has no `alembic_version`, so restoring it runs every upgrade step from "pre-0.8". It worked.
- By code reading (not exercised): the key throttle includes a global key (`("lab-copy",)`, `app/lab_copy.py:145`),
  so 20 wrong keys from anyone in 15 minutes block every computer's copy for that time.

### F-16 (low): Offline Help, 404 page, wording
- Help → user guide is a redirect to the website, so it's a browser error with no internet.
- A mistyped URL gives the bare Werkzeug "Not Found" page with no way back.
- "1 rows were skipped" (`app/sheet_import.py:1349`).

## 4. Numbers

| What | Value |
| --- | --- |
| Tests | 85 (55 PASS, 29 WARN, 1 FAIL) |
| Steps logged | 590 lines in `evidence/steps.log`; 228 screenshots |
| HTTP 5xx / tracebacks / JS page errors | 0 / 0 / 0 (SQLite and PostgreSQL runs) |
| Imports run | 9 good sheets (fish ×4 incl. re-runs, flies ×2, reagents, plasmids CSV, Xenopus, orders, morpholinos) + 2 bad files |
| ZPL files checked | 30 (10 label sets × 3 stocks); structural problems found: 0 |
| Lab-copy snapshot | 1.28 MB, 417 records, 85 tables, SHA-256 verified; pulled by the desktop code in < 1 s |
| SQLite → PostgreSQL migration of the snapshot | 417 rows, 36 non-empty tables, 2.2 s, row counts verified |
| Pages loaded with no internet | 18/18 working, 0 external requests (Help is the exception) |
| Date checks against three clocks (server UTC, lab Auckland, browser LA/NY) | mating return, clutch ID, received date, flip, collect, chunk, expiry, label print date, water-log time: all in the lab's day. Calendar "today" and to-do presets: in the browser's day (F-11) |

Not tested: printing on real Brother or Zebra hardware, Send to Zebra (no printer on the network), phone camera
scanning, a gunicorn server, the notebook, experiment weighing and regimen for fish/frogs, CSV export of
formula-looking names, the Android and iOS apps, and the desktop app's own window (only its keep-a-copy code, run
headless).
